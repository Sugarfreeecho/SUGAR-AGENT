import asyncio
import json
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from agent_local_timing import LocalOperationTrace, local_operation, local_step
from runtime_v2.history_ops import RuntimeHistoryOps
from runtime_v2.snapshot_store import SnapshotStore


def fresh_store_class():
    class FreshStore(SnapshotStore):
        _checkpoint_condition = threading.Condition(threading.Lock())
        _checkpoint_pending = {}
        _checkpoint_active = set()
        _checkpoint_cancelled = set()
        _checkpoint_errors = {}
        _checkpoint_workers_started = 0
    return FreshStore


def test_warm_workers_are_bounded_and_first_fact_needs_no_thread_start(tmp_path, monkeypatch):
    store_type = fresh_store_class()
    monkeypatch.setenv("RUNTIME_V2_SNAPSHOT_WORKERS", "2")
    monkeypatch.setenv("RUNTIME_V2_SNAPSHOT_INLINE_GRACE_MS", "0")
    monkeypatch.setenv("RUNTIME_V2_ASYNC_SNAPSHOT_CHECKPOINTS", "true")
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert list(pool.map(lambda _: store_type.start_checkpoint_workers(), range(8))) == [2] * 8
    assert list(tmp_path.iterdir()) == []

    original_start = threading.Thread.start
    def reject_late_start(thread):
        assert not thread.name.startswith("runtime-v2-snapshot-")
        return original_start(thread)
    monkeypatch.setattr(threading.Thread, "start", reject_late_start)
    ops = RuntimeHistoryOps(tmp_path)
    ops.snapshots = store_type(tmp_path)
    try:
        event = ops.append_model_message("warm-session", "assistant", "durable")
        assert event.seq == 1
        assert ops.event_log.read_all("warm-session")[0].payload["content"] == "durable"
        assert ops.snapshots.read("warm-session")["last_seq"] == 1
    finally:
        assert ops.snapshots.wait_for_checkpoint("warm-session", timeout_seconds=5)


def test_web_warmup_runs_off_loop_and_failure_keeps_lazy_fallback(monkeypatch):
    import webui
    observed = []
    def start(cls):
        observed.append(threading.current_thread().name)
        raise OSError("injected startup failure")
    monkeypatch.setattr(SnapshotStore, "start_checkpoint_workers", classmethod(start))
    asyncio.run(webui._warm_runtime_checkpoint_workers())
    assert observed and observed[0] != threading.current_thread().name


def test_sync_operation_filters_short_steps_without_suppressing_exception(monkeypatch):
    captured = []
    monkeypatch.setattr(LocalOperationTrace, "log", lambda trace: captured.append(trace.snapshot()))
    @local_operation("model_commit", slow_ms=0)
    def fail(state, message):
        with local_step("ignored_fast_step", min_ms=10000):
            raise ValueError("original failure")
    outer = LocalOperationTrace("outer")
    with outer.bind():
        with pytest.raises(ValueError, match="original failure"):
            fail({"session_id": "s", "_runtime_v2_run_id": "r", "_current_react_iter": 2}, "private payload")
        with local_step("outer_restored"):
            pass
    assert [s["name"] for s in outer.snapshot()["spans"]] == ["outer_restored"]
    assert captured[0]["spans"] == []
    assert (captured[0]["session_id"], captured[0]["run_id"], captured[0]["react_iter"]) == ("s", "r", 2)
    assert "private payload" not in json.dumps(captured)


@pytest.mark.parametrize("stage", ["snapshot_file_signature", "transaction_os_lock"])
def test_slow_fact_phases_are_identified_and_fact_remains_durable(stage, tmp_path, monkeypatch):
    import time
    from runtime_v2.event_log import SessionEventLog
    ops = RuntimeHistoryOps(tmp_path)
    monkeypatch.setenv("RUNTIME_V2_SNAPSHOT_INLINE_GRACE_MS", "0")
    if stage == "snapshot_file_signature":
        original = SnapshotStore._file_signature
        def delayed(path):
            time.sleep(.025)
            return original(path)
        monkeypatch.setattr(SnapshotStore, "_file_signature", staticmethod(delayed))
    else:
        original = SessionEventLog._lock_file
        def delayed(*args, **kwargs):
            time.sleep(.025)
            return original(*args, **kwargs)
        monkeypatch.setattr(SessionEventLog, "_lock_file", staticmethod(delayed))
    trace = LocalOperationTrace("model_commit", session_id="fact-session")
    try:
        with trace.bind():
            event = ops.append_model_message("fact-session", "tool", "durable result")
        slow = [s for s in trace.snapshot()["spans"] if s["name"] == stage]
        assert slow and max(s["elapsed_ms"] for s in slow) >= 20
        assert event.seq == 1
        assert ops.event_log.read_all("fact-session")[0].payload["content"] == "durable result"
    finally:
        assert ops.snapshots.wait_for_checkpoint("fact-session", timeout_seconds=5)
