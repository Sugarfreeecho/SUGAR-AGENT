"""Bounded submissions, durable backpressure and fair execution under load."""
import asyncio
import contextvars
import dataclasses
import threading
from types import SimpleNamespace

import pytest

from session_control.errors import ControlError
from session_control.resources import BoundedWorkPool, QueueLimits
from session_control.store import ControlStore
from tests.test_session_control import composed, new_session, rpc, run_async


async def until(predicate, seconds=5):
    async def waiting():
        while not predicate():
            await asyncio.sleep(.01)
    await asyncio.wait_for(waiting(), seconds)


@run_async
async def test_pool_bounds_submissions_and_cancelled_waiters_retain_running_slots():
    pool = BoundedWorkPool("test-budget", workers=1, pending=1, per_owner=2)
    release, started = threading.Event(), threading.Event()
    actor = contextvars.ContextVar("budget-test")
    actor.set("source-a")
    def work():
        started.set()
        release.wait(5)
        return actor.get()
    first = pool.try_submit("a", work)
    try:
        await until(started.is_set)
        second = pool.try_submit("a", lambda: actor.get())
        assert second is not None
        assert pool.try_submit("b", lambda: None) is None
        assert pool.snapshot()["outstanding"] == 2
        first.cancel()
        assert pool.snapshot()["outstanding"] == 2
        release.set()
        assert await second == "source-a"
        await until(lambda: pool.snapshot()["outstanding"] == 0)
    finally:
        release.set()
        pool.close()


@run_async
async def test_cancelled_reservation_releases_a_token_returned_later_by_the_host():
    from session_control.coordinator import SessionExecutionCoordinator
    pool = BoundedWorkPool("test-reservation", workers=1)
    entered, release = threading.Event(), threading.Event()
    released = []
    def reserve(sid, run):
        entered.set()
        assert release.wait(5)
        return "lease"
    coordinator = SessionExecutionCoordinator(SimpleNamespace(reserve_start=reserve,
        release_start=lambda sid, token: released.append((sid, token))))
    task = asyncio.create_task(coordinator.reserve_async("session", "run", pool=pool))
    try:
        await until(entered.is_set)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert pool.snapshot()["outstanding"] == 1
        release.set()
        await until(lambda: pool.snapshot()["outstanding"] == 0)
        assert released == [("session", "lease")]
    finally:
        release.set()
        pool.close()


@pytest.mark.parametrize("scope,limits,prior,new", [
    ("total", QueueLimits(1, 10, 10, 10), {"session_id": "a"}, {"session_id": "b"}),
    ("source", QueueLimits(10, 1, 10, 10), {"session_id": "a"}, {"session_id": "b"}),
    ("session", QueueLimits(10, 10, 1, 10), {"session_id": "a"}, {"session_id": "a"}),
    ("task", QueueLimits(10, 10, 10, 1), {"session_id": "a", "_automation_id": "rule"}, {"session_id": "b", "_automation_id": "rule"}),
])
def test_durable_admission_caps_are_atomic_and_replays_still_succeed(tmp_path, scope, limits, prior, new):
    store = ControlStore(tmp_path / "control.db")
    store.queue_limits = limits
    old, _ = store.admit("caller", "old", "session.send", {**prior, "message": "old"})
    with pytest.raises(ControlError) as failure:
        store.admit("caller", "new", "session.send", {**new, "message": "new"})
    assert failure.value.code == "queue_full" and failure.value.details["scope"] == scope
    replay, duplicate = store.admit("caller", "old", "session.send", {**prior, "message": "old"})
    assert duplicate and replay["id"] == old["id"]
    assert len(store.operations()) == 1


def test_full_batch_rolls_back_parent_and_every_leaf(tmp_path):
    store = ControlStore(tmp_path / "control.db")
    store.queue_limits = QueueLimits(1, 10, 10, 10)
    with pytest.raises(ControlError, match="budget"):
        store.admit_many("caller", "batch", [{"session_id": "a", "message": "a"}, {"session_id": "b", "message": "b"}])
    assert not store.operations()


@run_async
async def test_schedule_keeps_its_due_occurrence_when_admission_is_full(tmp_path, monkeypatch):
    import session_control.automation as automation
    from session_control.resources import ControlResources
    from session_control.scheduling import validate_trigger
    store = ControlStore(tmp_path / "control.db")
    store.queue_limits = QueueLimits(1, 10, 10, 10)
    occupied, _ = store.admit("caller", "occupied", "session.send", {"session_id": "other", "message": "busy"})
    trigger, due = validate_trigger({"kind": "interval", "seconds": 60}, 1000.)
    task = store.put("automations", "schedule", {"enabled": True, "trigger": trigger, "next_run_at": due})
    resources = ControlResources()
    engine = automation.AutomationService(SimpleNamespace(store=store, resources=resources))
    keys = []
    async def fire(row, key, occurrence):
        keys.append(key)
        op, _ = store.admit("caller", key, "session.send", {"session_id": "target", "message": "scheduled",
                                                           "_automation_id": row["id"]})
        return {"operation_id": op["id"]}
    async def no_bridge(_now):
        pass
    monkeypatch.setattr(engine, "fire", fire)
    monkeypatch.setattr(engine, "bridge", no_bridge)
    monkeypatch.setattr(automation.time, "time", lambda: due)
    try:
        await engine.tick()
        assert store.get("automations", "schedule") == task
        store.update_operation(occupied["id"], status="cancelled")
        await engine.tick()
        current = store.get("automations", "schedule")
        assert current["enabled"] and current["next_run_at"] == due + 60
        assert current["run_count"] == 1 and keys == [str(due), str(due)]
        assert len(store.operations(status="queued")) == 1
    finally:
        resources.close()


@pytest.fixture
def limited(request, monkeypatch):
    monkeypatch.setenv("MYAGENT_CONTROL_RUN_WORKERS", "2")
    monkeypatch.setenv("MYAGENT_CONTROL_RUN_PER_SOURCE", "1")
    return request.getfixturevalue("composed")


@run_async
async def test_source_fairness_run_caps_and_queued_inputs_survive_saturation(limited):
    from runtime_v2 import RuntimeHistoryOps
    c = limited
    release, started = threading.Event(), []
    def commit(sid):
        return RuntimeHistoryOps(c.manager.sessions_dir, path_resolver=c.manager._resolve_session_path)
    async def stream(message, *, session_id, run_id, user_operation_id, **kwargs):
        started.append(message)
        commit(session_id).commit_user_turn(session_id, message, operation_id=user_operation_id, run_id=run_id)
        yield {"type": "user", "content": message}
        while not release.is_set() and not kwargs["should_stop"](session_id):
            await asyncio.sleep(.01)
        commit(session_id).commit_assistant_final(session_id, message, operation_id="final:" + user_operation_id, run_id=run_id)
        yield {"type": "final", "content": message}
    c.service.deps.astream_events = stream
    sessions = [await new_session(c) for _ in range(5)]
    one, two = dataclasses.replace(c.admin, id="source-a"), dataclasses.replace(c.admin, id="source-b")
    await c.control.start()
    operations = []
    try:
        for i, sid in enumerate(sessions):
            op, _ = await c.service.execute(one if i < 4 else two, "session.send", {"session_id": sid, "message": f"work-{i}"}, idempotency_key=str(i))
            operations.append(op)
        await until(lambda: len(started) == 2)
        assert "work-4" in started, "another source must run despite older source-a backlog"
        assert sum(x.startswith("work-") and x != "work-4" for x in started) == 1
        assert c.service.resources.runtime.snapshot()["outstanding"] == 2
        assert len(c.store.operations(status="queued")) == 3
        release.set()
        for op in operations:
            result, _ = await c.service.execute(c.admin, "operation.wait", {"id": op["operation_id"], "timeout": 5})
            assert result["status"] == "succeeded"
        assert len(started) == 5
    finally:
        release.set()
        await c.control.close()


@run_async
async def test_repeated_runs_of_one_task_cannot_occupy_another_tasks_slot(composed):
    import time
    from runtime_v2 import RuntimeHistoryOps
    c = composed
    release, started = threading.Event(), []
    async def stream(message, *, session_id, run_id, user_operation_id, **kwargs):
        started.append(message)
        ops = RuntimeHistoryOps(c.manager.sessions_dir, path_resolver=c.manager._resolve_session_path)
        ops.commit_user_turn(session_id, message, operation_id=user_operation_id, run_id=run_id)
        yield {"type": "user", "content": message}
        while not release.is_set() and not kwargs["should_stop"](session_id):
            await asyncio.sleep(.01)
        ops.commit_assistant_final(session_id, message, operation_id="final:" + user_operation_id, run_id=run_id)
        yield {"type": "final", "content": message}
    c.service.deps.astream_events = stream
    await c.control.start()
    tasks = []
    for name in ("one", "two"):
        row, _ = await c.service.execute(c.admin, "automation.create", {"name": name, "target": {"mode": "new"},
            "workspace": str(c.root), "trigger": {"kind": "interval", "seconds": 3600},
            "action": {"kind": "prompt", "text": name}}, idempotency_key="definition-" + name)
        tasks.append(c.store.get("automations", row["id"]))
    operations = []
    try:
        for i, task in enumerate((tasks[0], tasks[0], tasks[1])):
            operations.append(await c.service.engine.fire(task, "run-" + str(i), time.time(), manual=True))
        await until(lambda: len(started) == 2)
        assert sorted(started) == ["one", "two"]
        assert c.store.get_operation(operations[1]["operation_id"])["status"] == "queued"
        release.set()
        for op in operations:
            result, _ = await c.service.execute(c.admin, "operation.wait", {"id": op["operation_id"], "timeout": 5})
            assert result["status"] == "succeeded"
    finally:
        release.set()
        await c.control.close()


@run_async
async def test_http_backpressure_reports_retry_and_recovers_with_the_original_key(composed):
    from session_control.cli import exit_code
    c = composed
    one, two = await new_session(c), await new_session(c)
    c.active.update({one: "browser", two: "browser"})
    c.store.queue_limits = QueueLimits(1, 10, 10, 10)
    accepted = await rpc(c, "session.send", {"session_id": one, "message": "one"}, key="one")
    try:
        rejected = await rpc(c, "session.send", {"session_id": two, "message": "two"}, key="two")
        assert rejected.status_code == 429 and rejected.headers["Retry-After"] == "1"
        assert rejected.json()["error"]["code"] == "queue_full"
        assert exit_code(ControlError("queue_full", "full", status=429)) == 5
        replay = await rpc(c, "session.send", {"session_id": one, "message": "one"}, key="one")
        assert replay.json()["operation_id"] == accepted.json()["operation_id"]
        await rpc(c, "operation.cancel", {"id": accepted.json()["operation_id"]})
        retried = await rpc(c, "session.send", {"session_id": two, "message": "two"}, key="two")
        assert retried.status_code == 200
    finally:
        c.active.clear()
        await c.control.close()


def test_added_subagent_accounting_metadata_keeps_old_admission_keys_compatible(tmp_path):
    store = ControlStore(tmp_path / "control.db")
    request = {"session_id": "parent", "_source": {"id": "@runtime/subagents", "epoch": 1}, "_require_pending_subagents": True}
    old, _ = store.admit("owner", "stable", "session.continue", request)
    replay, duplicate = store.admit("owner", "stable", "session.continue", {**request, "_subagent_batch": ["result-1"]})
    assert duplicate and replay["id"] == old["id"]
