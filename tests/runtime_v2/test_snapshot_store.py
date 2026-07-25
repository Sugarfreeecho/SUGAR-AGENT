import json
import threading
import time

from app.runtime_v2 import RuntimeHistoryOps, SessionEventLog, SnapshotStore


def test_snapshot_cache_key_is_stable_before_and_after_path_creation(tmp_path):
    store = SnapshotStore(tmp_path)
    path = store.path("s1")
    before = store._cache_key(path)
    path.parent.mkdir(parents=True)
    path.write_text("{}", encoding="utf-8")

    assert store._cache_key(path) == before


def test_nonempty_candidate_is_rejected_when_event_log_disappeared(tmp_path):
    store = SnapshotStore(tmp_path)
    candidate = {
        "last_seq": 1,
        "_event_log": {"size": 10, "mtime_ns": 10},
    }

    assert store._candidate_matches_event_log(store.path("s1"), candidate) is False


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
    assert store.path("s1").exists(), {
        "status": store.checkpoint_status("s1"),
        "writes": writes,
    }
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
    assert "simulated checkpoint failure" in store.checkpoint_status("s1")["last_error"]


def test_background_checkpoint_never_replaces_newer_disk_snapshot(tmp_path):
    store = SnapshotStore(tmp_path)
    store.write("s1", {"last_seq": 2, "value": "newer"})

    store._write_background_checkpoint("s1", {"last_seq": 1, "value": "stale"})

    disk = json.loads(store.path("s1").read_text(encoding="utf-8"))
    assert disk == {"last_seq": 2, "value": "newer"}


def test_pre_repair_background_checkpoint_cannot_resurrect_truncated_tail(tmp_path):
    log = SessionEventLog(tmp_path)
    first = log.append("s1", "message_user", {"content": "one"})
    log.append("s1", "message_assistant_final", {"content": "two"})
    store = SnapshotStore(tmp_path)
    stale = {"last_seq": 2, "value": "before-repair"}
    store.stamp_event_log("s1", stale, log.event_path("s1"))
    store.write("s1", stale)

    log.event_path("s1").write_text(
        json.dumps(first.to_dict(), ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    SessionEventLog._seq_cache.clear()
    repaired = {"last_seq": 1, "value": "repaired"}
    store.stamp_event_log("s1", repaired, log.event_path("s1"))
    store.write("s1", repaired)

    store._write_background_checkpoint("s1", stale)

    disk = json.loads(store.path("s1").read_text(encoding="utf-8"))
    assert disk["last_seq"] == 1
    assert disk["value"] == "repaired"


def test_checkpoint_pool_is_bounded_and_cancel_drops_queued_session(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNTIME_V2_ASYNC_SNAPSHOT_CHECKPOINTS", "true")
    monkeypatch.setenv("RUNTIME_V2_SNAPSHOT_CHECKPOINT_EVENTS", "1")
    monkeypatch.setenv("RUNTIME_V2_SNAPSHOT_INLINE_GRACE_MS", "0")
    monkeypatch.setenv("RUNTIME_V2_SNAPSHOT_WORKERS", "2")
    store = SnapshotStore(tmp_path)
    release = threading.Event()
    started = threading.Condition()
    active_paths = set()
    original_write = store._write_file

    def blocked_write(path, snapshot):
        with started:
            active_paths.add(str(path))
            started.notify_all()
        assert release.wait(timeout=2)
        original_write(path, snapshot)

    monkeypatch.setattr(store, "_write_file", blocked_write)
    store.write_checkpointed("busy-1", {"last_seq": 1})
    store.write_checkpointed("busy-2", {"last_seq": 1})
    with started:
        assert started.wait_for(lambda: len(active_paths) == 2, timeout=1)

    store.write_checkpointed("cancel-me", {"last_seq": 1})
    assert store.checkpoint_status("cancel-me")["pending"] is True
    assert store.cancel_checkpoint("cancel-me", timeout_seconds=0.1) is True
    assert store.checkpoint_status("cancel-me")["cancelled"] is True
    assert store.write_checkpointed("cancel-me", {"last_seq": 2}) is False

    release.set()
    assert store.wait_for_checkpoint("busy-1", timeout_seconds=2)
    assert store.wait_for_checkpoint("busy-2", timeout_seconds=2)
    assert not store.path("cancel-me").exists()
    assert store.checkpoint_status("busy-1")["workers"] == 2
