"""Storage-growth regressions for Runtime V2.

Each test pins one of the write-amplification fixes:

* ``history_ops`` must not duplicate model-history payloads in the snapshot.
* ``model_prefix_compacted`` must store only the changed middle.
* Appended extension-state arrays must use ``/-`` patch operations.
"""
from __future__ import annotations

import json

from app.runtime_v2 import RuntimeHistoryOps, RuntimeProjector, SessionEventLog, SessionExtensionStateStore


def _contents(snapshot):
    return [row["payload"]["content"] for row in snapshot["model_messages"]]


def _history(turns: int, tail: str | None = None):
    rows = []
    for index in range(turns):
        rows.append({"type": "user", "content": f"u{index}"})
        rows.append({"type": "assistant", "content": f"a{index}"})
    if tail is not None:
        rows[-1] = {"type": "assistant", "content": tail}
    return rows


def test_history_ops_do_not_duplicate_model_history_payloads(tmp_path):
    ops = RuntimeHistoryOps(tmp_path)
    history = _history(20)
    ops.replace_model_history("s1", history, reason="seed")

    snapshot = ops.snapshots.read("s1")
    raw = json.dumps(snapshot["history_ops"], ensure_ascii=False)
    assert "u0" not in raw, "history_ops still carries the full model history"
    assert "messages_count" in raw
    # The authoritative copy still lives where the projector reads it.
    assert _contents(snapshot) == [row["content"] for row in history]


def test_prefix_compaction_stores_only_the_changed_middle(tmp_path):
    ops = RuntimeHistoryOps(tmp_path)
    long_history = _history(60)
    ops.replace_model_history("s1", long_history, reason="seed")

    edited = _history(60, tail="a59-regenerated")
    event = ops.reconcile_model_history("s1", edited, reason="tail_edit")

    assert event.type == "model_prefix_compacted"
    assert event.payload["keep_head"] == 119
    assert event.payload["keep_tail"] == 0
    assert len(event.payload["replacement_middle"]) == 1
    assert "replacement_prefix" not in event.payload
    # A tail edit used to write the whole 120-message prefix.
    assert len(json.dumps(event.payload, ensure_ascii=False)) < 512
    assert _contents(ops.snapshots.read("s1")) == [row["content"] for row in edited]


def test_prefix_compaction_keeps_shared_head_and_tail(tmp_path):
    ops = RuntimeHistoryOps(tmp_path)
    base = _history(30)
    ops.replace_model_history("s1", base, reason="seed")

    edited = _history(30)
    edited[40] = {"type": "user", "content": "u20-rewritten"}
    event = ops.reconcile_model_history("s1", edited, reason="middle_edit")

    assert event.type == "model_prefix_compacted"
    assert event.payload["keep_head"] == 40
    assert event.payload["keep_tail"] == 19
    assert len(event.payload["replacement_middle"]) == 1
    assert _contents(ops.snapshots.read("s1")) == [row["content"] for row in edited]


def test_incremental_compaction_replays_identically(tmp_path):
    """A fresh replay of the log must equal the incrementally projected snapshot."""
    ops = RuntimeHistoryOps(tmp_path)
    ops.replace_model_history("s1", _history(25), reason="seed")
    ops.reconcile_model_history("s1", _history(25, tail="a24-v2"), reason="tail")
    ops.reconcile_model_history("s1", _history(30), reason="grow")
    middle = _history(30)
    middle[10] = {"type": "user", "content": "u5-rewritten"}
    ops.reconcile_model_history("s1", middle, reason="middle")

    incremental = ops.snapshots.read("s1")
    replayed = RuntimeProjector().project(SessionEventLog(tmp_path).read_all("s1"))
    assert _contents(replayed) == _contents(incremental) == [row["content"] for row in middle]


def test_legacy_full_prefix_compaction_still_replays(tmp_path):
    """Old events that carry ``replacement_prefix`` must keep working."""
    ops = RuntimeHistoryOps(tmp_path)
    ops.replace_model_history("s1", _history(4), reason="seed")
    ops._append_and_snapshot("s1", "model_prefix_compacted", {
        "reason": "legacy",
        "drop_prefix_count": 8,
        "replacement_prefix": [{"type": "system", "content": "summary"}],
    })

    assert _contents(ops.snapshots.read("s1")) == ["summary"]


def test_appended_extension_arrays_use_append_operations(tmp_path):
    (tmp_path / "s1").mkdir(parents=True, exist_ok=True)
    store = SessionExtensionStateStore(tmp_path)
    # Realistic size: a goal accumulates one usage id per LLM request, so the
    # array reaches hundreds of entries while only the last one is new.
    seed = [f"run-1:llm:{index}" for index in range(400)]
    store.set_latest("s1", "agent-goal", "goal", {"accounted_usage_ids": seed, "used_tokens": 1})

    def append_usage(current):
        goal = dict(current or {})
        ids = list(goal.get("accounted_usage_ids") or [])
        ids.append("run-1:llm:400")
        goal["accounted_usage_ids"] = ids
        goal["used_tokens"] = 2
        return "goal_usage_updated", goal, goal

    store.mutate("s1", "agent-goal", "goal", append_usage)

    events = [
        event for event in SessionEventLog(tmp_path).read_all("s1")
        if event.type == "extension_state_changed"
    ]
    patch = events[-1].payload["patch"]
    assert {"op": "add", "path": "/accounted_usage_ids/-", "value": "run-1:llm:400"} in patch
    assert all(row["path"] != "/accounted_usage_ids" for row in patch)
    assert len(json.dumps(patch, ensure_ascii=False)) < 200
    value = store.get("s1", "agent-goal", "goal")["value"]
    assert value["accounted_usage_ids"] == seed + ["run-1:llm:400"]
