import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from agent_local_timing import LocalOperationTrace


def setup_entry(monkeypatch, *, fence=True):
    import agent_loop
    from execution_services import integration
    calls, traces = [], []
    monkeypatch.setattr(agent_loop, "_state_run_has_write_fence", lambda state: calls.append("fence") or fence)
    async def reviews(state, emit):
        calls.append("reviews")
    monkeypatch.setattr(agent_loop, "_flush_file_tool_reviews", reviews)
    async def notices(state, persist):
        calls.append("jobs")
        return True
    monkeypatch.setattr(integration, "consume_notices", notices)
    async def push(state, event, *, emit):
        calls.append(event["type"])
    monkeypatch.setattr(agent_loop, "_push_stream_event", push)
    monkeypatch.setattr(LocalOperationTrace, "log", lambda trace: traces.append(trace.snapshot()))
    def inject(**kwargs):
        assert kwargs == {"current_run_only": True}
        calls.append("subagents")
    return agent_loop, calls, traces, inject


def test_round_entry_preserves_order_and_records_the_pre_preparation_barrier(monkeypatch):
    loop, calls, traces, inject = setup_entry(monkeypatch)
    state = {"session_id": "s", "_runtime_v2_run_id": "r", "_current_react_iter": 4,
             "_change_review_batch_active": True}
    assert asyncio.run(loop._prepare_react_iteration(state, None, inject)) == ("", True)
    assert calls == ["fence", "reviews", "subagents", "jobs"]
    assert "_change_review_batch_active" not in state
    assert len(traces) == 1 and traces[0]["kind"] == "round_entry"
    assert (traces[0]["session_id"], traces[0]["run_id"]) == ("s", "r")
    assert [s["name"] for s in traces[0]["spans"]] == [
        "entry_write_fence", "entry_file_reviews", "entry_subagent_notices", "entry_execution_notices"]


def test_round_entry_cancellation_and_pause_keep_the_original_barriers(monkeypatch):
    loop, calls, traces, inject = setup_entry(monkeypatch, fence=False)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(loop._prepare_react_iteration({"session_id": "s"}, None, inject))
    assert calls == ["fence"] and len(traces) == 1
    loop, calls, traces, inject = setup_entry(monkeypatch)
    state = {"session_id": "s", "_workflow_pause_requested": "pause"}
    assert asyncio.run(loop._prepare_react_iteration(state, None, inject)) == ("pause", False)
    assert calls == ["fence", "reviews", "status"]
    assert "_workflow_pause_requested" not in state


def test_notice_commit_failure_does_not_acknowledge_and_records_the_failed_step(monkeypatch):
    from execution_services import integration
    from execution_services import jobs
    calls = []
    async def notices(owner):
        return [{"id": "one", "text": "private notice text"}]
    async def acknowledge(owner, ids):
        calls.append("ack")
    async def service_call(fn, *args):
        return await fn(*args)
    monkeypatch.setattr(jobs, "_SERVICE", SimpleNamespace(
        _closing=False, call=service_call, notices=notices, acknowledge=acknowledge))
    def persist(*args):
        raise OSError("commit failed")
    trace = LocalOperationTrace("round_entry")
    async def run():
        with trace.bind():
            await integration.consume_notices({"session_id": "s", "llm_history": [], "work_messages": []}, persist)
    with pytest.raises(OSError, match="commit failed"):
        asyncio.run(run())
    assert calls == []
    assert [s["name"] for s in trace.snapshot()["spans"]] == ["job_notice_poll", "job_notice_model_commit"]
    assert "private notice text" not in str(trace.snapshot())
