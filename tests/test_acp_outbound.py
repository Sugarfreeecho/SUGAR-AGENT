import asyncio
import dataclasses
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
from acp_bridge.client import AgentTarget
from acp_bridge.peer import peer_transport, UnsupportedCapability
from acp_bridge.outbound import OutboundStore, OutboundService, fingerprint


def target(path, timeout=10):
    return AgentTarget("peer", sys.executable, (str(ROOT / "tests/fixtures/acp_session_agent.py"), str(path)), timeout=timeout)


async def allowed(row):
    pass


def test_real_session_new_continue_after_transport_reconnect_and_workspace_filter(tmp_path):
    async def scenario():
        agent = target(tmp_path / "peer.json")
        async with peer_transport(agent, str(tmp_path)) as peer:
            sid = await peer.new_session()
            result = await peer.prompt(sid, "first")
            assert result["output"] == "progress:done:first:1"
            assert "PRIVATE" not in result["output"] and "FOREIGN" not in result["output"]
        async with peer_transport(agent, str(tmp_path)) as peer:
            assert (await peer.list_sessions())["sessions"][0]["session_id"] == sid
            assert await peer.resume(sid) == "resume"
            assert (await peer.prompt(sid, "second"))["output"] == "progress:done:second:2"
            rows = json.loads((tmp_path / "peer.json").read_text())
            rows["outside"] = {"cwd": str(tmp_path.parent), "turns": 0}
            (tmp_path / "peer.json").write_text(json.dumps(rows))
            assert len((await peer.list_sessions())["sessions"]) == 1
            with pytest.raises(Exception):
                await peer.resume("missing")
            assert "missing" not in json.loads((tmp_path / "peer.json").read_text())
    asyncio.run(scenario())


def test_service_explicit_new_reuse_owner_scope_and_no_foreground_callback(tmp_path):
    async def scenario():
        delivered = []
        async def deliver(row, item):
            delivered.append(item)
            return {"operation_id": "notice"}
        store = OutboundStore(tmp_path / "jobs.db")
        service = OutboundService(store, enabled=lambda: True, authorize=allowed, deliver=deliver)
        agent = target(tmp_path / "peer.json")
        try:
            session = await service.sessions("source", agent, str(tmp_path), {}, new=True)
            sid = session["session_id"]
            first = await service.submit("source", agent, str(tmp_path), {}, "one", session_id=sid)
            result = await service.wait("source", first["task_id"])
            assert result["session_id"] == sid and result["session_action"] == "existing"
            assert result["status"] == "succeeded" and result["output"] == "progress:done:one:1"
            assert any(row["type"] == "message" for row in result["events"])
            assert result["events"][-1]["phase"] == "final"
            other = await service.submit("source", agent, str(tmp_path), {}, "new")
            assert (await service.wait("source", other["task_id"]))["session_id"] != sid
            with pytest.raises(PermissionError):
                await service.get("foreign-source", first["task_id"])
            with pytest.raises(ValueError):
                await service.submit("foreign-source", agent, str(tmp_path), {}, "bad", session_id=sid)
            changed = dataclasses.replace(agent, args=(*agent.args, "changed"))
            with pytest.raises(ValueError):
                store.require_binding("source", changed, str(tmp_path), sid)
            await service.dispatch()
            assert delivered == []
            assert "authority" not in result and "fingerprint" not in result
            await service.sessions("source", agent, str(tmp_path), {}, close=sid)
        finally:
            await service.stop()
            store.close()
    asyncio.run(scenario())


@pytest.mark.parametrize("notify", ["final", "all", "none"])
def test_background_report_policy_and_fixed_origin(tmp_path, notify):
    async def scenario():
        reports = {}
        async def deliver(row, item):
            reports[item["key"]] = (row["origin"], item["phase"], item["message"])
            return {"operation_id": item["key"]}
        store = OutboundStore(tmp_path / "jobs.db")
        service = OutboundService(store, enabled=lambda: True, authorize=allowed, deliver=deliver)
        try:
            row = await service.submit("origin", target(tmp_path / "peer.json"), str(tmp_path), {}, "ping", background=True, notify=notify)
            done = await service.wait("origin", row["task_id"])
            await service.dispatch()
            phases = [value[1] for value in reports.values()]
            assert phases.count("final") == (0 if notify == "none" else 1)
            assert ("progress" in phases) == (notify == "all")
            assert all(value[0] == "origin" for value in reports.values())
            assert all("FOREIGN_TEXT" not in value[2] and "PRIVATE_REASONING" not in value[2] for value in reports.values())
            await service.dispatch()
            assert len(reports) == len(phases)
            assert done["status"] == "succeeded"
        finally:
            await service.stop()
            store.close()
    asyncio.run(scenario())


def test_cancel_timeout_partial_failure_and_resume_admission(tmp_path):
    async def scenario():
        store = OutboundStore(tmp_path / "jobs.db")
        service = OutboundService(store, enabled=lambda: True, authorize=allowed)
        agent = target(tmp_path / "peer.json")
        try:
            session = await service.sessions("origin", agent, str(tmp_path), {}, new=True)
            row = await service.submit("origin", agent, str(tmp_path), {}, "wait", session_id=session["session_id"])
            while not (await service.get("origin", row["task_id"]))["output"]:
                await asyncio.sleep(.02)
            with pytest.raises(ValueError):
                await service.submit("origin", agent, str(tmp_path), {}, "duplicate", session_id=session["session_id"])
            done = await service.cancel("origin", row["task_id"])
            assert done["status"] == "cancelled" and done["output"] == "progress:"
            row = await service.submit("origin", agent, str(tmp_path), {}, "fail", session_id=session["session_id"])
            done = await service.wait("origin", row["task_id"])
            assert done["status"] == "failed" and done["output"] == "progress:"
            assert "REMOTE_SECRET" not in json.dumps(done)
            row = await service.submit("origin", agent, str(tmp_path), {}, "large", session_id=session["session_id"])
            done = await service.wait("origin", row["task_id"])
            assert done["truncated"] and len(done["output"]) == 32000
            row = await service.submit("origin", dataclasses.replace(agent, timeout=.1), str(tmp_path), {}, "wait")
            done = await service.wait("origin", row["task_id"])
            assert done["status"] == "failed" and done["error"] == "TimeoutError"
        finally:
            await service.stop()
            store.close()
    asyncio.run(scenario())


def test_outbox_retry_uses_same_key_and_rechecks_authorization(tmp_path):
    async def scenario():
        revoked = False
        attempts, accepted = [], set()
        async def check(row):
            if revoked:
                raise PermissionError("revoked")
        async def deliver(row, item):
            attempts.append(item["key"])
            accepted.add(item["key"])
            if len(attempts) == 1:
                raise TimeoutError("response lost after admission")
            return {"operation_id": "same-operation"}
        store = OutboundStore(tmp_path / "jobs.db")
        service = OutboundService(store, enabled=lambda: True, authorize=check, deliver=deliver)
        try:
            row = await service.submit("origin", target(tmp_path / "peer.json"), str(tmp_path), {}, "ping", background=True)
            service.worker.cancel()
            await asyncio.gather(service.worker, return_exceptions=True)
            await service.wait("origin", row["task_id"])
            await service.dispatch()
            item = store.rows("outbox")[0]
            assert item["status"] == "retry"
            item["next_at"] = 0
            store.save_delivery(item)
            await service.dispatch()
            assert len(accepted) == 1 and len(attempts) == 2 and attempts[0] == attempts[1]
            row = await service.submit("origin", target(tmp_path / "peer.json"), str(tmp_path), {}, "ping", background=True)
            await service.wait("origin", row["task_id"])
            revoked = True
            await service.dispatch()
            result = await service.get("origin", row["task_id"])
            assert result["delivery"]["status"] == "blocked"
        finally:
            await service.stop()
            store.close()
    asyncio.run(scenario())


def test_restart_marks_uncertain_execution_and_reports_once_without_rerunning(tmp_path):
    async def scenario():
        reports = []
        async def deliver(row, item):
            reports.append(item["key"])
            return {"operation_id": "recovered-report"}
        store = OutboundStore(tmp_path / "jobs.db")
        first = OutboundService(store, enabled=lambda: True, authorize=allowed, deliver=deliver)
        row = await first.submit("source", target(tmp_path / "peer.json"), str(tmp_path), {}, "one")
        await first.wait("source", row["task_id"])
        await first.stop()
        saved = store.task(row["task_id"])
        saved.update(status="running", background=True, notify="final", output="saved partial output")
        store.save(saved)
        store.close()
        second_store = OutboundStore(tmp_path / "jobs.db")
        def never_start(*args):
            raise AssertionError("Recovery must not repeat an external task")
        second = OutboundService(second_store, enabled=lambda: True, authorize=allowed, deliver=deliver, peer_factory=never_start)
        try:
            await second.start()
            await second.dispatch()
            restored = await second.get("source", row["task_id"])
            assert restored["status"] == "interrupted" and restored["error"] == "host_restarted"
            assert restored["output"] == "saved partial output"
            assert restored["delivery"]["status"] == "accepted" and len(reports) == 1
            await second.dispatch()
            assert len(reports) == 1 and not second.peers
        finally:
            await second.stop()
            second_store.close()
    asyncio.run(scenario())


def test_unknown_resume_and_cross_workspace_fail_without_creating_a_replacement(tmp_path):
    async def scenario():
        store = OutboundStore(tmp_path / "jobs.db")
        service = OutboundService(store, enabled=lambda: True, authorize=allowed)
        agent = target(tmp_path / "peer.json")
        try:
            store.bind("source", agent, str(tmp_path), "missing-remote")
            row = await service.submit("source", agent, str(tmp_path), {}, "task", session_id="missing-remote")
            result = await service.wait("source", row["task_id"])
            assert result["status"] == "failed" and result["session_id"] == "missing-remote"
            assert not (tmp_path / "peer.json").exists()
            elsewhere = tmp_path / "other"
            elsewhere.mkdir()
            with pytest.raises(ValueError):
                await service.submit("source", agent, str(elsewhere), {}, "task", session_id="missing-remote")
        finally:
            await service.stop()
            store.close()
    asyncio.run(scenario())
