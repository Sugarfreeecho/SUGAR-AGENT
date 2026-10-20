from unittest.mock import Mock

import pytest

from app.runtime_v2 import RuntimeHistoryOps, RuntimeProjector
from app.runtime_v2.versions import PROJECTOR_VERSION


@pytest.fixture
def history(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNTIME_V2_ASYNC_SNAPSHOT_CHECKPOINTS", "false")
    ops = RuntimeHistoryOps(tmp_path)
    ops.append_model_message("s1", "user", "question")
    # Exercise compatibility with the prior on-disk stamp and its indexed
    # suffix/fallback contract. New identity/cursor coverage lives alongside
    # this module in test_snapshot_suffix_cursor.py.
    legacy = ops.snapshots.read("s1")
    legacy["_event_log"].pop("identity", None)
    ops.snapshots.write("s1", legacy)
    return ops


def assert_matches_log(ops):
    expected = RuntimeProjector().project(ops.event_log.read_all("s1"))
    actual = ops.snapshots.read("s1")
    for key in ("_event_log", "_projection"):
        actual.pop(key, None)
    assert actual == expected


def test_append_replays_only_independently_appended_tail(history, monkeypatch):
    ops = history
    ops.event_log.append("s1", "context_tokens", {"estimated": 71})
    ops.event_log.append("s1", "message_assistant_final", {"content": "visible answer"})
    original_read = ops.event_log.read_all
    full_read = Mock(side_effect=original_read)
    suffix_read = Mock(wraps=ops.event_log.read_after_seq)
    monkeypatch.setattr(ops.event_log, "read_all", full_read)
    monkeypatch.setattr(ops.event_log, "read_after_seq", suffix_read)

    event = ops.append_model_message("s1", "assistant", "answer")

    assert event.seq == 4
    full_read.assert_not_called()
    suffix_read.assert_called_once_with("s1", 1)
    snapshot = ops.snapshots.read("s1")
    assert snapshot["last_seq"] == 4
    assert snapshot["visible_messages"][-1]["payload"]["content"] == "visible answer"
    assert_matches_log(ops)


def test_adjacent_append_uses_no_history_read(history, monkeypatch):
    ops = history
    full_read = Mock(wraps=ops.event_log.read_all)
    suffix_read = Mock(wraps=ops.event_log.read_after_seq)
    monkeypatch.setattr(ops.event_log, "read_all", full_read)
    monkeypatch.setattr(ops.event_log, "read_after_seq", suffix_read)

    ops.append_model_message("s1", "assistant", "answer")

    full_read.assert_not_called()
    suffix_read.assert_not_called()
    assert_matches_log(ops)


@pytest.mark.parametrize("extra_tail", [False, True])
def test_stale_projection_version_rebuilds_even_for_adjacent_append(history, monkeypatch, extra_tail):
    ops = history
    stale = ops.snapshots.read("s1")
    stale["_projection"]["projector_version"] = PROJECTOR_VERSION - 1
    stale["model_messages"] = []
    ops.snapshots.write("s1", stale)
    if extra_tail:
        ops.event_log.append("s1", "context_tokens", {"estimated": 71})
    full_read = Mock(wraps=ops.event_log.read_all)
    monkeypatch.setattr(ops.event_log, "read_all", full_read)

    ops.append_model_message("s1", "assistant", "answer")

    full_read.assert_called_once_with("s1")
    assert len(ops.snapshots.read("s1")["model_messages"]) == 2
    assert_matches_log(ops)


def test_missing_suffix_event_falls_back_to_full_log(history, monkeypatch):
    ops = history
    ops.event_log.append("s1", "context_tokens", {"estimated": 71})
    original_suffix = ops.event_log.read_after_seq
    monkeypatch.setattr(ops.event_log, "read_after_seq", lambda *args: original_suffix(*args)[1:])
    full_read = Mock(wraps=ops.event_log.read_all)
    monkeypatch.setattr(ops.event_log, "read_all", full_read)

    ops.append_model_message("s1", "assistant", "answer")

    full_read.assert_called_once_with("s1")
    assert_matches_log(ops)


def boundary_commit(ops, kind):
    if kind == "user":
        return ops.commit_user_turn("s1", "next question", operation_id="turn-2")
    if kind == "final":
        return ops.commit_assistant_final("s1", "answer", operation_id="final-1")
    return ops.reconcile_model_history("s1", [
        {"type": "user", "content": "question"},
        {"type": "assistant", "content": "answer"},
    ], reason="finish")


@pytest.mark.parametrize("kind", ["user", "final", "reconcile"])
def test_fact_boundaries_replay_only_journal_suffix(history, monkeypatch, kind):
    ops = history
    ops.event_log.append("s1", "context_tokens", {"estimated": 71})
    full_read = Mock(wraps=ops.event_log.read_all)
    suffix_read = Mock(wraps=ops.event_log.read_after_seq)
    monkeypatch.setattr(ops.event_log, "read_all", full_read)
    monkeypatch.setattr(ops.event_log, "read_after_seq", suffix_read)

    assert boundary_commit(ops, kind).seq == 3

    full_read.assert_not_called()
    suffix_read.assert_called_once_with("s1", 1)
    assert_matches_log(ops)


@pytest.mark.parametrize("kind", ["user", "final", "reconcile"])
def test_fact_boundaries_rebuild_adjacent_old_projection(history, monkeypatch, kind):
    ops = history
    stale = ops.snapshots.read("s1")
    stale["_projection"]["projector_version"] = PROJECTOR_VERSION - 1
    stale["model_messages"] = []
    ops.snapshots.write("s1", stale)
    full_read = Mock(wraps=ops.event_log.read_all)
    monkeypatch.setattr(ops.event_log, "read_all", full_read)

    boundary_commit(ops, kind)

    full_read.assert_called_once_with("s1")
    assert_matches_log(ops)


@pytest.mark.parametrize("kind", ["user", "final", "reconcile"])
def test_fact_boundaries_rebuild_when_suffix_is_missing(history, monkeypatch, kind):
    ops = history
    ops.event_log.append("s1", "context_tokens", {"estimated": 71})
    monkeypatch.setattr(ops.event_log, "read_after_seq", lambda *args: [])
    full_read = Mock(wraps=ops.event_log.read_all)
    monkeypatch.setattr(ops.event_log, "read_all", full_read)

    boundary_commit(ops, kind)

    full_read.assert_called_once_with("s1")
    assert_matches_log(ops)


@pytest.mark.parametrize("kind", ["user", "final"])
def test_duplicate_boundary_remains_idempotent_after_journal_append(history, monkeypatch, kind):
    ops = history
    boundary_commit(ops, kind)
    last = ops.event_log.append("s1", "context_tokens", {"estimated": 71})
    full_read = Mock(wraps=ops.event_log.read_all)
    monkeypatch.setattr(ops.event_log, "read_all", full_read)

    assert boundary_commit(ops, kind) is None

    full_read.assert_not_called()
    assert ops.event_log.next_seq("s1") == last.seq + 1


@pytest.mark.parametrize("stale", [False, True])
def test_child_append_catches_up_journal_tail_or_rebuilds_old_projection(tmp_path, monkeypatch, stale):
    from app.runtime_v2.subagent_store import RuntimeSubagentStore
    from app.runtime_v2.event_log import SessionEventLog
    from app.runtime_v2.snapshot_store import SnapshotStore

    monkeypatch.setenv("RUNTIME_V2_ASYNC_SNAPSHOT_CHECKPOINTS", "false")
    store = RuntimeSubagentStore(tmp_path)
    store.append_event("parent", "child", "model_user", {"role": "user", "content": "question"})
    root = store.root_for_parent("parent")
    log, snapshots = SessionEventLog(root), SnapshotStore(root)
    if stale:
        snapshot = snapshots.read("child")
        snapshot["_projection"]["projector_version"] = PROJECTOR_VERSION - 1
        snapshot["model_messages"] = []
        snapshots.write("child", snapshot)
    else:
        log.append("child", "context_tokens", {"estimated": 71})
    full_project = Mock(wraps=store.projector.project)
    monkeypatch.setattr(store.projector, "project", full_project)

    store.append_event("parent", "child", "model_assistant", {"role": "assistant", "content": "answer"})

    assert full_project.call_count == int(stale)
    expected = RuntimeProjector().project(log.read_all("child"))
    actual = snapshots.read("child")
    for key in ("_event_log", "_projection"):
        actual.pop(key, None)
    assert actual == expected


@pytest.mark.parametrize("batch", [False, True])
def test_mirror_rebuilds_old_projection_even_for_adjacent_event(tmp_path, monkeypatch, batch):
    from app.runtime_v2 import RuntimeMirror

    monkeypatch.setenv("RUNTIME_V2_ASYNC_SNAPSHOT_CHECKPOINTS", "false")
    mirror = RuntimeMirror(tmp_path)
    mirror.append("s1", "model_user", {"role": "user", "content": "question"})
    stale = mirror.snapshots.read("s1")
    stale["_projection"]["projector_version"] = PROJECTOR_VERSION - 1
    stale["model_messages"] = []
    mirror.snapshots.write("s1", stale)
    full_read = Mock(wraps=mirror.event_log.read_all)
    monkeypatch.setattr(mirror.event_log, "read_all", full_read)

    if batch:
        mirror.append_batch("s1", [{"type": "model_assistant", "payload": {"role": "assistant", "content": "answer"}}])
    else:
        mirror.append("s1", "model_assistant", {"role": "assistant", "content": "answer"})

    full_read.assert_called_once_with("s1")
    assert_matches_log(mirror)
