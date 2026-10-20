import asyncio
from pathlib import Path
import sys
import threading
from types import SimpleNamespace, MethodType

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from agent_harness import SessionManager
from agent_subagent_events import persist_execution_event
from runtime_v2.event_log import SessionEventLog
from runtime_v2.mirror import RuntimeMirror
from runtime_v2.snapshot_store import SnapshotStore


def manager_for(root, fail=False):
    manager = SimpleNamespace(sessions_dir=root, _resolve_session_path=lambda sid: root / sid)
    def append(sid, event, *, require_commit=False):
        assert require_commit
        assert SessionEventLog(root).read_all(sid)[-1].type == "execution_recorded"
        if fail:
            raise OSError("UI persistence failed")
        RuntimeMirror(root).mirror_ui_event(sid, event)
    manager.append_ui_event = append
    manager.commit_execution_ui_event = MethodType(SessionManager.commit_execution_ui_event, manager)
    return manager


def test_combined_result_batch_keeps_all_facts_and_releases_source(tmp_path, monkeypatch):
    from runtime_v2.execution_journal import ExecutionJournal
    from runtime_v2.derived_cache import source_matches
    manager = manager_for(tmp_path)
    manager.commit_execution_ui_events = MethodType(SessionManager.commit_execution_ui_events, manager)
    events = [{"type": "tool_call", "run_id": "r", "react_iter": 1,
               "tool_call_id": f"call-{i}", "tool_call_index": i,
               "tool": "read_file", "args": {}, "result": f"result-{i}"} for i in range(4)]
    result = manager.commit_execution_ui_events("s", events)
    assert all(row["_runtime_v2_committed"] for row in result)
    log = SessionEventLog(tmp_path)
    facts = log.read_all("s")
    assert len(facts) == 8
    assert all(facts[i].type == "execution_recorded" for i in range(0, 8, 2))
    store = SnapshotStore(tmp_path)
    snapshot = store.read_for_update("s")
    assert store._signature_matches(snapshot, log.event_path("s"))
    journal = ExecutionJournal(tmp_path)
    assert len(journal.read("s")["execution_records"]) == 4
    assert source_matches(log.event_path("s"), journal._state("s")["source"])
    assert store.wait_for_checkpoint("s", 3)


def test_batch_cancellation_stops_later_rows_and_closes_writer(tmp_path):
    manager = manager_for(tmp_path)
    cancelled = threading.Event()
    original = manager.append_ui_event
    def append(*a, **k):
        original(*a, **k)
        cancelled.set()
    manager.append_ui_event = append
    events = [{"type": "tool_call", "run_id": "r", "tool_call_id": str(i), "result": "ok"} for i in range(3)]
    with pytest.raises(asyncio.CancelledError):
        SessionManager.commit_execution_ui_events(manager, "s", events, cancel_event=cancelled)
    assert len(SessionEventLog(tmp_path).read_all("s")) == 2
    SessionEventLog(tmp_path).append("s", "model_user", {"content": "later"})
    assert SnapshotStore(tmp_path).wait_for_checkpoint("s", 3)


@pytest.mark.parametrize("kind", ["tool_call", "llm_reasoning", "llm_response"])
def test_combined_commit_marks_success_only_after_both_facts(tmp_path, monkeypatch, kind):
    import runtime_v2
    monkeypatch.setattr(runtime_v2, "runtime_v2_primary", lambda: True)
    monkeypatch.setattr(runtime_v2, "runtime_v2_strict", lambda: True)
    manager = manager_for(tmp_path)
    event = {"type": kind, "run_id": "r", "react_iter": 1, "tool_call_id": "call",
             "tool": "read_file", "args": {}, "result": "ok", "content": "text"}
    result = asyncio.run(persist_execution_event(manager, "s", event, commit_ui=True))
    assert result["_runtime_v2_committed"] is True
    facts = SessionEventLog(tmp_path).read_all("s")
    assert len(facts) == 2
    assert facts[0].type == "execution_recorded"
    assert "_runtime_v2_committed" not in facts[1].payload
    assert SnapshotStore(tmp_path).wait_for_checkpoint("s", 3)


def test_ui_failure_cannot_claim_combined_commit(tmp_path, monkeypatch):
    import runtime_v2
    monkeypatch.setattr(runtime_v2, "runtime_v2_primary", lambda: True)
    monkeypatch.setattr(runtime_v2, "runtime_v2_strict", lambda: True)
    event = {"type": "tool_call", "run_id": "r", "tool_call_id": "call", "result": "ok"}
    with pytest.raises(OSError, match="UI persistence failed"):
        asyncio.run(persist_execution_event(manager_for(tmp_path, fail=True), "s", event, commit_ui=True))
    assert "_runtime_v2_committed" not in event
    assert [row.type for row in SessionEventLog(tmp_path).read_all("s")] == ["execution_recorded"]


@pytest.mark.parametrize("options", [{}, {"ephemeral": True}, {"_skip_persist": True}])
def test_default_and_nonpersistent_paths_do_not_commit_ui(tmp_path, monkeypatch, options):
    import runtime_v2
    monkeypatch.setattr(runtime_v2, "runtime_v2_primary", lambda: True)
    monkeypatch.setattr(runtime_v2, "runtime_v2_strict", lambda: True)
    manager = manager_for(tmp_path)
    manager.commit_execution_ui_event = lambda *a: pytest.fail("unexpected UI transaction")
    event = {"type": "tool_call", "run_id": "r", "tool_call_id": "call", "result": "ok", **options}
    result = asyncio.run(persist_execution_event(manager, "s", event, commit_ui=bool(options)))
    assert "_runtime_v2_committed" not in result


def test_cancelled_dispatch_does_not_start_ui_after_blocked_journal(tmp_path, monkeypatch):
    import runtime_v2
    from runtime_v2.execution_journal import ExecutionJournal
    monkeypatch.setattr(runtime_v2, "runtime_v2_primary", lambda: True)
    monkeypatch.setattr(runtime_v2, "runtime_v2_strict", lambda: True)
    entered, release, completed = threading.Event(), threading.Event(), threading.Event()
    original = ExecutionJournal.record
    def blocked(*a, **k):
        entered.set()
        assert release.wait(3)
        try:
            return original(*a, **k)
        finally:
            completed.set()
    monkeypatch.setattr(ExecutionJournal, "record", blocked)
    manager = manager_for(tmp_path)
    manager.append_ui_event = lambda *a, **k: pytest.fail("UI started after cancellation")
    async def scenario():
        task = asyncio.create_task(persist_execution_event(
            manager, "s", {"type": "tool_call", "run_id": "r", "tool_call_id": "call"}, commit_ui=True))
        try:
            assert await asyncio.to_thread(entered.wait, 2)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        finally:
            release.set()
            assert await asyncio.to_thread(completed.wait, 2)
    asyncio.run(scenario())
    assert [row.type for row in SessionEventLog(tmp_path).read_all("s")] == ["execution_recorded"]
