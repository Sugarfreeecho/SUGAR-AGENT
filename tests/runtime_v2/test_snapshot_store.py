import json
import threading
import time

from app.runtime_v2 import RuntimeHistoryOps, SnapshotStore


def test_history_append_does_not_wait_for_snapshot_fsync(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNTIME_V2_ASYNC_SNAPSHOT_CHECKPOINTS", "true")
    monkeypatch.setenv("RUNTIME_V2_SNAPSHOT_CHECKPOINT_EVENTS", "1")
    ops = RuntimeHistoryOps(tmp_path)
    entered = threading.Event()
    release = threading.Event()
    original_write = ops.snapshots._write_file

    def blocked_write(path, snapshot):
        entered.set()
        assert release.wait(timeout=2)
        original_write(path, snapshot)

    monkeypatch.setattr(ops.snapshots, "_write_file", blocked_write)
    started = time.monotonic()
    event = ops.append_model_message("s1", "assistant", "done")
    elapsed = time.monotonic() - started

    try:
        assert event.seq == 1
        assert entered.wait(timeout=1)
        assert elapsed < 0.5
        assert ops.snapshots.read("s1")["last_seq"] == 1
        assert ops.event_log.read_all("s1")[0].payload["content"] == "done"
    finally:
        release.set()
        assert ops.snapshots.wait_for_checkpoint("s1", timeout_seconds=2)


def test_deferred_checkpoints_coalesce_without_regressing_memory(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNTIME_V2_ASYNC_SNAPSHOT_CHECKPOINTS", "true")
    monkeypatch.setenv("RUNTIME_V2_SNAPSHOT_CHECKPOINT_EVENTS", "1")
    store = SnapshotStore(tmp_path)
    entered = threading.Event()
    release = threading.Event()
    original_write = store._write_file
    writes = []

    def first_write_blocks(path, snapshot):
        writes.append(int(snapshot["last_seq"]))
        if len(writes) == 1:
            entered.set()
            assert release.wait(timeout=2)
        original_write(path, snapshot)

    monkeypatch.setattr(store, "_write_file", first_write_blocks)
    store.write_checkpointed("s1", {"last_seq": 1, "value": "old"})
    assert entered.wait(timeout=1)
    store.write_checkpointed("s1", {"last_seq": 2, "value": "new"})
    assert store.read("s1")["value"] == "new"

    release.set()
    assert store.wait_for_checkpoint("s1", timeout_seconds=2)
    assert store.read("s1")["last_seq"] == 2
    assert json.loads(store.path("s1").read_text(encoding="utf-8"))["last_seq"] == 2
    assert writes == [1, 2]


def test_deferred_checkpoint_failure_keeps_projection_available(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNTIME_V2_ASYNC_SNAPSHOT_CHECKPOINTS", "true")
    store = SnapshotStore(tmp_path)

    def failed_write(_path, _snapshot):
        raise OSError("simulated checkpoint failure")

    monkeypatch.setattr(store, "_write_file", failed_write)
    assert store.write_checkpointed("s1", {"last_seq": 1, "value": "memory"})
    assert store.wait_for_checkpoint("s1", timeout_seconds=2)
    assert store.read("s1")["value"] == "memory"
    assert not store.path("s1").exists()
