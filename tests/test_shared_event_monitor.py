"""Shared event batches scale with candidate rules and preserve live revocation."""
import asyncio
from types import SimpleNamespace

import pytest

from session_control.automation import AutomationService
from session_control.store import ControlStore


def rule(store, identity, kinds=None):
    return store.put("automations", identity, {"name": identity, "owner": "owner", "enabled": True,
        "created_at": 0, "active_since": 0, "policy": {"scope": "all"},
        "action": {"kind": "prompt", "text": identity},
        "trigger": {"kind": "event", "types": kinds or ["job.completed"],
                    "condition": {"field": "data.ready", "op": "eq", "value": True}}})


def events(store, count):
    for i in range(count):
        store.append_event({"source": "runtime/s", "id": str(i), "subject": "s", "time": "2026-10-27T00:00:00+00:00",
                            "type": "job.completed", "data": {"ready": True}})


def test_one_rule_snapshot_per_batch_and_only_matching_types_are_evaluated(tmp_path, monkeypatch):
    import session_control.automation as automation
    store = ControlStore(tmp_path / "control.db")
    rule(store, "matching", ["job.completed", "job.completed"])
    for i in range(499):
        rule(store, str(i), ["run.ended"])
    events(store, 100)
    engine = AutomationService(SimpleNamespace(store=store, manager=SimpleNamespace()))
    reads, predicates, fired = [], [], []
    original_list, match = store.list, automation.match_condition
    def listed(family):
        reads.append(family)
        return original_list(family)
    def predicate(condition, event):
        predicates.append(1)
        return match(condition, event)
    async def fire(task, key, occurrence, **kwargs):
        fired.append((task["id"], key))
    monkeypatch.setattr(store, "list", listed)
    monkeypatch.setattr(automation, "match_condition", predicate)
    monkeypatch.setattr(engine, "fire", fire)
    asyncio.run(engine.consume_events())
    assert reads == ["automations"]
    assert len(predicates) == len(fired) == 100
    assert {row[0] for row in fired} == {"matching"}
    assert store.cursor("rules") == store.cursor("event_highwater") == 100


@pytest.mark.parametrize("change", ["pause", "edit", "delete"])
def test_batch_snapshot_cannot_bypass_live_rule_changes(tmp_path, monkeypatch, change):
    store = ControlStore(tmp_path / "control.db")
    rule(store, "first")
    second = rule(store, "second")
    events(store, 2)
    engine = AutomationService(SimpleNamespace(store=store, manager=SimpleNamespace()))
    fired = []
    async def fire(task, *args, **kwargs):
        fired.append(task["id"])
        if len(fired) == 1:
            await asyncio.sleep(0)  # Another request may run while dispatch awaits.
            if change == "delete":
                store.delete("automations", "second")
            else:
                store.put("automations", "second", {**second, "enabled": change != "pause", "name": "updated"}, expected=second["revision"])
    monkeypatch.setattr(engine, "fire", fire)
    asyncio.run(engine.consume_events())
    assert fired == ["first", "first"]
    assert store.cursor("rules") == 2


def test_failed_rule_is_paused_once_without_blocking_other_subscribers(tmp_path, monkeypatch):
    store = ControlStore(tmp_path / "control.db")
    rule(store, "bad")
    rule(store, "good")
    events(store, 3)
    engine = AutomationService(SimpleNamespace(store=store, manager=SimpleNamespace()))
    fired = []
    async def fire(task, *args, **kwargs):
        fired.append(task["id"])
        if task["id"] == "bad":
            raise OSError("source failed")
    monkeypatch.setattr(engine, "fire", fire)
    asyncio.run(engine.consume_events())
    assert fired.count("bad") == 1 and fired.count("good") == 3
    assert store.get("automations", "bad")["enabled"] is False
    assert store.get("automations", "bad")["last_error"]["message"] == "source failed"
    assert store.cursor("rules") == 3


def test_failed_old_dispatch_does_not_overwrite_a_new_definition(tmp_path, monkeypatch):
    store = ControlStore(tmp_path / "control.db")
    old = rule(store, "rule")
    events(store, 2)
    engine = AutomationService(SimpleNamespace(store=store, manager=SimpleNamespace()))
    attempts = []
    async def fire(task, *args, **kwargs):
        attempts.append(1)
        store.put("automations", "rule", {**old, "name": "new definition"}, expected=old["revision"])
        raise OSError("old dispatch failed")
    monkeypatch.setattr(engine, "fire", fire)
    asyncio.run(engine.consume_events())
    current = store.get("automations", "rule")
    assert current["enabled"] and current["name"] == "new definition"
    assert current["revision"] == 2 and "last_error" not in current
    assert attempts == [1] and store.cursor("rules") == 2
