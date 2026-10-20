import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from agent_local_timing import LocalOperationTrace, local_operation, local_step, local_timed, mark_local


def test_spans_follow_to_thread_without_leaking_between_tasks():
    @local_timed("worker")
    def worker():
        mark_local("entered")
        return 42

    async def scenario():
        a, b = LocalOperationTrace("a"), LocalOperationTrace("b")
        async def run(trace):
            with trace.bind():
                assert await asyncio.to_thread(worker) == 42
        await asyncio.gather(run(a), run(b))
        for trace in (a, b):
            data = trace.snapshot()
            assert "entered" in data["anchors"]
            assert [span["name"] for span in data["spans"]] == ["worker"]
        worker()
        assert len(a.snapshot()["spans"]) == 1
    asyncio.run(scenario())


def test_bridge_keeps_payload_and_ack_order_with_correlated_diagnostics(monkeypatch):
    from stream_event_bridge import StreamEventBridge
    captured, delivered = [], []
    monkeypatch.setattr(LocalOperationTrace, "log", lambda trace: captured.append(trace.snapshot()))
    async def emit(event):
        with local_step("slow_sink"):
            await asyncio.sleep(0.11)
            delivered.append(dict(event))
    async def scenario():
        bridge = StreamEventBridge(asyncio.get_running_loop(), emit, session_id="session", run_id="run")
        original = {"type": "tool_call", "react_iter": 3, "content": "sensitive-content"}
        await bridge.send(original)
        assert delivered == [original]
        await bridge.flush()
    asyncio.run(scenario())
    assert len(captured) == 1
    trace = captured[0]
    assert (trace["session_id"], trace["run_id"], trace["react_iter"]) == ("session", "run", 3)
    assert trace["anchors"]["queued"] <= trace["anchors"]["started"]
    assert trace["spans"][0]["name"] == "slow_sink"
    assert "sensitive-content" not in json.dumps(trace)


def test_real_journal_mirror_and_publication_share_one_clock(tmp_path, monkeypatch):
    from agent_subagent_events import persist_execution_event
    from runtime_v2 import SnapshotStore
    from runtime_v2.mirror import RuntimeMirror
    from session_event_bus import publish_session_event
    monkeypatch.setenv("RUNTIME_V2_PRIMARY", "true")
    trace = LocalOperationTrace("delivery", session_id="s", run_id="r", react_iter=2)
    manager = SimpleNamespace(sessions_dir=tmp_path)
    async def scenario():
        event = {"type": "tool_call", "tool": "read_file", "args": {}, "result": "ok",
                 "tool_call_id": "call", "run_id": "r", "react_iter": 2}
        with trace.bind():
            event = await persist_execution_event(manager, "s", event)
            await asyncio.to_thread(RuntimeMirror(tmp_path).mirror_ui_event, "s", event)
            await publish_session_event("s", dict(event))
        assert SnapshotStore(tmp_path).wait_for_checkpoint("s", 3)
    asyncio.run(scenario())
    data = trace.snapshot()
    names = {span["name"] for span in data["spans"]}
    assert {"execution_dispatch", "journal_record", "journal_state", "fact_append",
            "ui_mirror", "ui_projection", "snapshot_publish", "event_publish"} <= names
    a = data["anchors"]
    assert a["journal_queued"] <= a["journal_worker_entered"] <= a["journal_transaction_acquired"]
    assert a["journal_transaction_acquired"] < a["mirror_transaction_acquired"]
    assert "local_operation" not in (tmp_path / "s/events.jsonl").read_text(encoding="utf-8")


def test_failed_operation_preserves_exception_and_bounded_diagnostics(monkeypatch):
    import agent_local_timing as timing
    trace = LocalOperationTrace("bounded")
    with trace.bind():
        for _ in range(70):
            with local_step("part"):
                pass
    assert len(trace.snapshot()["spans"]) == 64
    assert trace.snapshot()["dropped_spans"] == 6
    monkeypatch.setattr(timing._logger, "info", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("logger")))
    @local_operation("cleanup")
    async def fail(**kwargs):
        with local_step("failure"):
            raise ValueError("original")
    with pytest.raises(ValueError, match="original"):
        asyncio.run(fail(session_id="s", state={}))
    assert timing._current.get() is None


def test_operation_resolves_positional_state_without_logging_payload(monkeypatch):
    captured = []
    monkeypatch.setattr(LocalOperationTrace, "log", lambda trace: captured.append(trace.snapshot()))
    @local_operation("hook_dispatch", slow_ms=0)
    async def dispatch(event, state, payload):
        return payload
    payload = {"secret": "must-not-be-logged"}
    assert asyncio.run(dispatch("PostToolUse", {"session_id": "s", "_runtime_v2_run_id": "r",
                            "_current_react_iter": 7}, payload)) is payload
    assert (captured[0]["session_id"], captured[0]["run_id"], captured[0]["react_iter"],
            captured[0]["event_type"]) == ("s", "r", 7, "PostToolUse")
    assert "must-not-be-logged" not in json.dumps(captured)
