import copy
import json
import os

import pytest

from runtime_v2 import RuntimeProjector, SessionEventLog, SnapshotStore


def seeded(tmp_path):
    log, store, projector = SessionEventLog(tmp_path), SnapshotStore(tmp_path), RuntimeProjector()
    log.append("s", "message_user", {"content": "旧消息😀"})
    snapshot = projector.project(log.read_all("s"))
    store.stamp_event_log("s", snapshot, log.event_path("s"))
    return log, store, projector, snapshot


def test_stamped_suffix_replays_only_new_facts_without_sparse_index(tmp_path, monkeypatch):
    log, store, projector, snapshot = seeded(tmp_path)
    before = copy.deepcopy(snapshot)
    for index in range(70):
        log.append("s", "execution_recorded", {"execution_id": "e", "text_delta": "中文"})
    last = log.append("s", "message_assistant_final", {"content": "完成"})
    monkeypatch.setattr(log, "read_after_seq", lambda *a, **k: pytest.fail("opened sparse index"))
    monkeypatch.setattr(log, "read_all", lambda *a, **k: pytest.fail("replayed full facts"))
    result = store.project_after_append("s", snapshot, log, projector, last.seq)
    assert result["last_seq"] == last.seq
    assert result["messages"][-1]["payload"]["content"] == "完成"
    assert snapshot == before


@pytest.mark.parametrize("fault", ["legacy", "mid_line", "wrong_seq", "wrong_end"])
def test_untrusted_cursor_falls_back_to_existing_index(tmp_path, monkeypatch, fault):
    log, store, projector, snapshot = seeded(tmp_path)
    last = log.append("s", "message_assistant_final", {"content": "答案"})
    expected = projector.project(log.read_all("s"))
    if fault == "legacy":
        snapshot["_event_log"].pop("identity")
    elif fault == "mid_line":
        snapshot["_event_log"]["size"] -= 8
    elif fault == "wrong_seq":
        snapshot["last_seq"] = 7
        last = log.append("s", "context_tokens", {})
    calls = []
    original = log.read_after_seq
    def indexed(*args, **kwargs):
        calls.append(True)
        return original(*args, **kwargs)
    monkeypatch.setattr(log, "read_after_seq", indexed)
    # The guarded helper declines a caller whose through_seq differs from EOF.
    if fault == "wrong_end":
        log.append("s", "context_tokens", {})
    result = store.project_after_append("s", snapshot, log, projector, last.seq)
    if fault != "wrong_seq":
        assert calls
    assert result["last_seq"] == log.next_seq("s") - 1
    if fault in {"legacy", "mid_line"}:
        assert {k: v for k, v in result.items() if not k.startswith("_")} == expected


def test_replaced_log_does_not_apply_suffix_to_old_messages(tmp_path, monkeypatch):
    log, store, projector, snapshot = seeded(tmp_path)
    replacement = log.event_path("s").with_name("replacement")
    first = log.read_all("s")[0].to_dict()
    first["payload"]["content"] = "新消息" * 100
    second = dict(first, seq=2, type="message_assistant_final", payload={"content": "新答案"})
    replacement.write_text(json.dumps(first) + "\n" + json.dumps(second) + "\n", encoding="utf8")
    os.replace(replacement, log.event_path("s"))
    monkeypatch.setattr(log, "read_after_seq", lambda *a, **k: pytest.fail("used stale generation"))
    result = store.project_after_append("s", snapshot, log, projector, 2)
    assert result["messages"][0]["payload"]["content"] == "新消息" * 100
    assert result["last_seq"] == 2


def test_incomplete_suffix_is_not_published(tmp_path):
    log, store, projector, snapshot = seeded(tmp_path)
    log.append("s", "message_assistant_final", {"content": "答案"})
    with log.event_path("s").open("ab") as file:
        file.write(b'{"seq":3')
    assert store._read_stamped_suffix("s", snapshot, log, 2) is None


@pytest.mark.parametrize("kind", ["user", "final", "reconcile"])
def test_stamped_fact_boundaries_match_fresh_replay(tmp_path, monkeypatch, kind):
    from runtime_v2 import RuntimeHistoryOps
    monkeypatch.setenv("RUNTIME_V2_ASYNC_SNAPSHOT_CHECKPOINTS", "false")
    ops = RuntimeHistoryOps(tmp_path)
    ops.append_model_message("s", "user", "question")
    ops.event_log.append("s", "context_tokens", {"estimated": 71})
    monkeypatch.setattr(ops.event_log, "read_after_seq", lambda *a: pytest.fail("sparse index read"))
    if kind == "user":
        ops.commit_user_turn("s", "next", operation_id="turn-2")
    elif kind == "final":
        ops.commit_assistant_final("s", "answer", operation_id="final-1")
    else:
        ops.reconcile_model_history("s", [{"type": "user", "content": "question"},
                                           {"type": "assistant", "content": "answer"}], reason="finish")
    actual = ops.snapshots.read("s")
    actual.pop("_event_log", None)
    actual.pop("_projection", None)
    assert actual == RuntimeProjector().project(ops.event_log.read_all("s"))
