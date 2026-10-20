from pathlib import Path

import pytest

from runtime_v2 import RuntimeHistoryOps, RuntimeProjector, SessionEventLog
from runtime_v2.derived_cache import source_boundary


def test_completed_tools_keep_separate_contiguous_facts_and_one_append(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNTIME_V2_ASYNC_SNAPSHOT_CHECKPOINTS", "false")
    ops = RuntimeHistoryOps(tmp_path)
    ops.append_model_message("s", "assistant", "working", tool_calls=[{"id": "one"}, {"id": "two"}])
    ops.event_log.append("s", "context_tokens", {"estimated": 20})
    path = ops.event_log.event_path("s")
    before = source_boundary(path, path.stat().st_size)
    opened = []
    original = Path.open
    def tracked(self, mode="r", *a, **k):
        if self == path and mode == "a":
            opened.append(True)
        return original(self, mode, *a, **k)
    monkeypatch.setattr(Path, "open", tracked)
    payloads = [{"content": "中文😀", "tool_call_id": "one"},
                {"content": [{"type": "text", "text": "structured"}], "tool_call_id": "two"}]
    events = ops.append_model_tool_results("s", payloads, run_id="r")
    assert [event.seq for event in events] == [3, 4]
    assert [event.type for event in events] == ["model_tool", "model_tool"]
    assert all(event.run_id == "r" for event in events)
    assert opened == [True]
    actual = ops.snapshots.read("s")
    actual.pop("_event_log", None)
    actual.pop("_projection", None)
    assert actual == RuntimeProjector().project(ops.event_log.read_all("s"))
    receipt = ops.event_log.recent_owned_append("s", before, path.stat())
    assert receipt is not None
    assert len(receipt["encoded"].splitlines()) == 2
    assert ops.append_model_tool_results("s", []) == []


def test_batch_failure_propagates_and_never_publishes_partial_projection(tmp_path, monkeypatch):
    ops = RuntimeHistoryOps(tmp_path)
    ops.append_model_message("s", "user", "question")
    before = ops.snapshots.read("s")
    def fail(*a, **k):
        raise OSError("batch write failed")
    monkeypatch.setattr(ops.event_log, "_append_many_unlocked", fail)
    with pytest.raises(OSError, match="batch write failed"):
        ops.append_model_tool_results("s", [{"tool_call_id": "t", "content": "result"}])
    assert ops.snapshots.read("s") == before


def test_large_batch_is_not_retained_as_owned_tail(tmp_path):
    log = SessionEventLog(tmp_path)
    log.append("s", "model_user", {"content": "start"})
    path = log.event_path("s")
    source = source_boundary(path, path.stat().st_size)
    log.append_batch("s", [{"type": "context_tokens", "payload": {"padding": "x" * 20000}} for _ in range(20)])
    assert log.recent_owned_append("s", source, path.stat()) is None
