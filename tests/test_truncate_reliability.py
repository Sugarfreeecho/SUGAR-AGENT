import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from truncate_operation_requests import TruncateOperationRequests
from runtime_v2 import RuntimeMirror, RuntimeUiProjection


def test_receipt_single_flight_conflict_and_session_isolation():
    async def scenario():
        receipts = TruncateOperationRequests()
        gate = asyncio.Event()
        calls = []

        async def create():
            calls.append(1)
            await gate.wait()
            return {"ok": True}

        assert receipts.start("s1", "request-1", (2, 3), create)["status"] == "pending"
        assert receipts.start("s1", "request-1", (2, 3), create)["status"] == "pending"
        assert receipts.start("s1", "request-1", (4, 5), create)["error"] == "truncate_request_conflict"
        assert receipts.start("s1", "request-2", (4, 5), create)["error"] == "truncate_session_busy"
        assert receipts.status("s2", "request-1")["status"] == "unknown"
        await asyncio.sleep(0)
        assert calls == [1]
        gate.set()
        await receipts.entries[("s1", "request-1")]["task"]
        result = receipts.status("s1", "request-1")
        assert result["status"] == "completed" and result["ok"] is True
        assert receipts.start("s1", "request-1", (2, 3), create) == result
        assert calls == [1]

    asyncio.run(scenario())


def test_failure_receipts_are_retained_and_exception_is_inconclusive():
    async def scenario():
        receipts = TruncateOperationRequests()

        async def fail():
            return {"ok": False, "error": "truncation failed"}

        async def crash():
            raise OSError("post-commit failure")

        for request, create, error in [
            ("failed-1", fail, "truncation failed"),
            ("failed-2", crash, "truncate_result_unknown"),
        ]:
            receipts.start("s", request, (), create)
            await receipts.entries[("s", request)]["task"]
            result = receipts.start("s", request, (), create)
            assert result["status"] == "completed"
            assert result["ok"] is False and result["error"] == error

    asyncio.run(scenario())


def test_receipts_bound_capacity_without_evicting_active_work():
    async def scenario():
        receipts = TruncateOperationRequests(limit=1)
        gate = asyncio.Event()

        async def create():
            await gate.wait()
            return {"ok": True}

        receipts.start("s1", "request-1", (), create)
        assert receipts.start("s2", "request-2", (), create)["error"] == "truncate_requests_busy"
        gate.set()
        await receipts.entries[("s1", "request-1")]["task"]
        receipts.ttl = 0
        assert receipts.status("s1", "request-1")["error"] == "truncate_result_unknown"

    asyncio.run(scenario())


@pytest.mark.parametrize("explicit", [True, False])
def test_truncate_boundary_uses_one_unhydrated_projection(tmp_path, monkeypatch, explicit):
    mirror = RuntimeMirror(tmp_path)
    first = mirror.mirror_ui_event("s1", {"type": "user", "content": "first"})
    answer = mirror.mirror_ui_event("s1", {"type": "final", "content": "answer"})
    target = mirror.mirror_ui_event("s1", {"type": "user", "content": "rewrite"})
    projection = RuntimeUiProjection(tmp_path)
    replay = Mock(wraps=projection._project_visible_ui_entries)
    monkeypatch.setattr(projection, "_project_visible_ui_entries", replay)
    state = {}
    assert projection.resolve_truncate_boundary(
        "s1", 2, target.seq if explicit else None, history_state=state,
    ) == (2, target.seq, answer.seq)
    replay.assert_called_once()
    assert replay.call_args.args == ("s1",)
    assert replay.call_args.kwargs["hydrate"] is False
    assert replay.call_args.kwargs["history_state"] is state
    assert projection.resolve_truncate_boundary("s1", 0, first.seq) == (0, first.seq, 0)
    assert projection.resolve_truncate_boundary("s1", 2, 999999) is None
    assert projection.resolve_truncate_boundary("s1", 999999) is None


def test_manager_truncate_skips_redundant_full_history_load(tmp_path):
    import agent_harness

    mirror = RuntimeMirror(tmp_path)
    mirror.mirror_ui_event("s1", {"type": "user", "content": "first"})
    previous = mirror.mirror_ui_event("s1", {"type": "final", "content": "answer"})
    target = mirror.mirror_ui_event("s1", {"type": "user", "content": "rewrite"})
    observed = Mock(return_value=True)
    manager = SimpleNamespace(
        repository=SimpleNamespace(sessions_dir=tmp_path),
        _runtime_v2_primary=lambda: True,
        _resolve_session_path=lambda sid: tmp_path / sid,
        _load_ui_events_for_active_runtime=Mock(side_effect=AssertionError("redundant hydrated load")),
        _observe_runtime_v2_history=observed,
    )
    assert agent_harness.SessionManager.truncate_session_at_event_index(
        manager, "s1", 2, truncate_before_seq=target.seq, create_backup=False,
    ) is True
    observed.assert_called_once()
    assert observed.call_args.args == ("truncate_visible_history_before_seq", "s1")
    kwargs = dict(observed.call_args.kwargs)
    outcome = kwargs.pop("outcome")
    assert isinstance(outcome, dict)
    assert kwargs == {
        "target_seq": target.seq,
        "keep_to_seq": previous.seq,
        "reason": "runtime_v2_truncate",
    }


def test_repeated_truncate_of_same_target_is_idempotent(tmp_path):
    """提交后丢失响应再重试：目标 seq 已不可见，必须按成功处理，不能永久 400。"""
    from runtime_v2 import RuntimeHistoryOps

    mirror = RuntimeMirror(tmp_path)
    mirror.mirror_ui_event("s1", {"type": "user", "content": "first"})
    answer = mirror.mirror_ui_event("s1", {"type": "final", "content": "answer"})
    target = mirror.mirror_ui_event("s1", {"type": "user", "content": "rewrite"})
    RuntimeHistoryOps(tmp_path).truncate_visible_history_before_seq(
        "s1", target_seq=target.seq, keep_to_seq=answer.seq,
    )
    state = {}
    assert RuntimeUiProjection(tmp_path).resolve_truncate_boundary(
        "s1", 2, target.seq, history_state=state,
    ) is None
    assert state["already_applied"] is True
    # 未发生裁剪时不能把"不存在"误判成"已生效"
    state2 = {}
    assert RuntimeUiProjection(tmp_path).resolve_truncate_boundary(
        "s1", 2, 999999, history_state=state2,
    ) is None
    assert state2["already_applied"] is False


def test_manager_truncate_counts_committed_without_snapshot_as_applied(tmp_path, monkeypatch):
    """事实已落盘但快照写失败：必须回成功（快照会在下次读取时重建）。"""
    import agent_harness
    from runtime_v2.snapshot_store import SnapshotStore

    sid = "11111111-1111-4111-8111-111111111111"
    mirror = RuntimeMirror(tmp_path)
    mirror.mirror_ui_event(sid, {"type": "user", "content": "first"})
    answer = mirror.mirror_ui_event(sid, {"type": "final", "content": "answer"})
    target = mirror.mirror_ui_event(sid, {"type": "user", "content": "rewrite"})

    def fail_write(self, *args, **kwargs):
        raise PermissionError("simulated snapshot write failure")

    monkeypatch.setattr(SnapshotStore, "write_checkpointed", fail_write)
    manager = agent_harness.SessionManager(tmp_path, tmp_path / "sessions.json")
    assert agent_harness.SessionManager.truncate_session_at_event_index(
        manager, sid, 2, truncate_before_seq=target.seq, create_backup=False,
    ) is True
    types = [event.type for event in
             __import__("runtime_v2").RuntimeHistoryOps(tmp_path).event_log.read_all(sid)]
    assert "visible_range_changed" in types


def test_routes_acknowledge_then_report_same_operation_after_disconnect(monkeypatch):
    import json
    import webui

    async def scenario():
        receipts = TruncateOperationRequests()
        monkeypatch.setattr(webui, "_truncate_session_requests", receipts)
        gate = asyncio.Event()
        calls = []

        async def truncate(*args):
            calls.append(args)
            await gate.wait()
            return webui.JSONResponse({"ok": True})

        monkeypatch.setattr(webui, "_truncate_session_events_once", truncate)
        response = await webui.truncate_session_events("s1", 2, 3, False, "request-1")
        assert response.status_code == 202
        assert json.loads(response.body)["status"] == "pending"
        # The browser can disappear/reconnect without cancelling the work.
        await asyncio.sleep(0)
        assert calls == [("s1", 2, 3, False)]
        response = await webui.truncate_session_events("s1", 2, 3, False, "request-1")
        assert response.status_code == 202 and len(calls) == 1
        gate.set()
        await receipts.entries[("s1", "request-1")]["task"]
        result = json.loads((await webui.get_truncate_session_status("s1", "request-1")).body)
        assert result["status"] == "completed" and result["ok"] is True
        assert json.loads((await webui.get_truncate_session_status("other", "request-1")).body)["status"] == "unknown"

    asyncio.run(scenario())
