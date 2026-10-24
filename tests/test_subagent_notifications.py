"""Background child results wake the parent without a browser producer."""
import asyncio
import sys
from types import SimpleNamespace

import pytest


@pytest.fixture
def wakeup(tmp_path, monkeypatch):
    import agent_harness
    import agent_loop
    import agent_subagent_notifications as notifications

    monkeypatch.setenv("RUNTIME_VERSION", "2")
    manager = agent_harness.SessionManager(tmp_path, tmp_path / "sessions.json")
    owner = manager.get_or_create_session()[0]
    manager.append_ui_event(owner, {"type": "user", "content": "do the work"})
    manager.append_ui_event(owner, {"type": "final", "content": "waiting", "run_id": "parent-run"})
    admission = {"busy": False, "human": 0, "stopped": False}
    calls, released, delivered = [], [], []

    async def reserve(sid, run_id):
        if admission["busy"]:
            return None
        admission["busy"] = True
        return run_id

    def release(sid, token):
        released.append((sid, token))
        admission["busy"] = False

    monkeypatch.setitem(sys.modules, "webui", SimpleNamespace(
        _reserve_session_chat_start_off_loop=reserve,
        _release_session_chat_start=release,
        _session_pending_human_count=lambda sid: admission["human"],
    ))
    monkeypatch.setattr(manager, "is_interrupt_requested", lambda *args: admission["stopped"])

    async def continuation(sid, **kwargs):
        calls.append((sid, kwargs))
        rows = manager.claim_pending_subagent_notifications(sid, kwargs["run_id"])
        delivered.extend(row["result"] for row in rows)
        manager.resolve_pending_subagent_claim(sid, kwargs["run_id"], consumed=True)
        manager.append_ui_event(sid, {
            "type": "final", "content": "combined", "run_id": kwargs["run_id"],
        })
        yield {"type": "final", "content": "combined"}

    monkeypatch.setattr(agent_loop, "astream_events_continuation", continuation)
    notifications._failed_batches.clear()

    def complete(child="child-1", parent_run="parent-run"):
        manager.append_pending_subagent_result(owner, {
            "agent_id": child, "run_id": child + "-run", "parent_run_id": parent_run,
            "status": "completed", "result": child + " result",
        })

    return SimpleNamespace(manager=manager, owner=owner, admission=admission, calls=calls,
                           released=released, delivered=delivered, complete=complete)


def test_busy_parent_retries_then_consumes_late_results_once(wakeup):
    from agent_subagent_notifications import _continue
    w = wakeup
    w.complete()
    w.complete("child-2")
    w.admission["busy"] = True

    async def scenario():
        assert await _continue(w.manager, w.owner) is True
        assert w.calls == []
        assert w.manager.has_pending_subagent_notifications(w.owner)
        w.admission["busy"] = False
        assert await _continue(w.manager, w.owner) is False
        assert await _continue(w.manager, w.owner) is False

    asyncio.run(scenario())
    assert len(w.calls) == 1
    assert w.calls[0][0] == w.owner
    assert w.calls[0][1]["run_id"].startswith("subagent-wakeup-")
    assert sorted(w.delivered) == ["child-1 result", "child-2 result"]
    assert not w.manager.has_pending_subagent_notifications(w.owner)
    assert sum(event["type"] == "user" for event in w.manager._load_ui_events_for_active_runtime(w.owner)) == 1
    assert not w.admission["busy"]


def test_children_finishing_after_separate_continuations_stay_in_original_user_turn(wakeup):
    from agent_subagent_notifications import _continue
    w = wakeup

    async def scenario():
        w.complete()
        await _continue(w.manager, w.owner)
        w.complete("child-2")
        await _continue(w.manager, w.owner)
        # A new human turn prevents an old child result from waking this turn.
        w.manager.append_ui_event(w.owner, {"type": "user", "content": "new task"})
        w.manager.append_ui_event(w.owner, {"type": "final", "content": "new answer", "run_id": "new-run"})
        w.complete("stale-child")
        assert await _continue(w.manager, w.owner) is False

    asyncio.run(scenario())
    assert len(w.calls) == 2
    assert w.delivered == ["child-1 result", "child-2 result"]
    assert w.manager.has_pending_subagent_notifications(w.owner)


def test_result_arriving_during_wakeup_gets_another_run_without_replaying_consumed_results(wakeup, monkeypatch):
    import agent_loop
    from agent_subagent_notifications import _continue
    w = wakeup
    original = agent_loop.astream_events_continuation

    async def continuation(sid, **kwargs):
        async for event in original(sid, **kwargs):
            if len(w.calls) == 1:
                await asyncio.to_thread(w.complete, "late-child")
            yield event

    monkeypatch.setattr(agent_loop, "astream_events_continuation", continuation)
    w.complete()

    async def scenario():
        assert await _continue(w.manager, w.owner) is True
        assert await _continue(w.manager, w.owner) is False

    asyncio.run(scenario())
    assert len(w.calls) == 2
    assert w.delivered == ["child-1 result", "late-child result"]
    assert not w.manager.has_pending_subagent_notifications(w.owner)


@pytest.mark.parametrize("blocked", ["stopped", "archived", "human"])
def test_stop_archive_and_pending_human_interactions_block_automatic_generation(wakeup, blocked):
    from agent_subagent_notifications import _continue
    w = wakeup
    w.complete()
    if blocked == "archived":
        metadata = w.manager._load_metadata(w.owner)
        metadata["archived"] = True
        w.manager._save_metadata(w.owner, metadata)
    else:
        w.admission[blocked] = True
    assert asyncio.run(_continue(w.manager, w.owner)) is (blocked == "human")
    assert w.calls == []
    assert w.manager.has_pending_subagent_notifications(w.owner)
    assert len(w.released) == 1
    if blocked == "human":
        w.admission["human"] = 0
        asyncio.run(_continue(w.manager, w.owner))
        assert len(w.calls) == 1


@pytest.mark.parametrize("outcome", ["error", "no-progress"])
def test_failed_or_empty_automatic_run_does_not_retry_the_same_batch(wakeup, monkeypatch, outcome):
    import agent_loop
    from agent_subagent_notifications import _continue
    w = wakeup
    w.complete()
    attempts = []

    async def failure(sid, **kwargs):
        attempts.append(sid)
        if outcome == "error":
            raise RuntimeError("model unavailable")
        yield {"type": "status", "content": "hook paused"}

    monkeypatch.setattr(agent_loop, "astream_events_continuation", failure)

    async def scenario():
        assert await _continue(w.manager, w.owner) is False
        assert await _continue(w.manager, w.owner) is False
        assert len(attempts) == 1
        assert w.manager.has_pending_subagent_notifications(w.owner)
        w.complete("child-2")
        await _continue(w.manager, w.owner)

    asyncio.run(scenario())
    assert len(attempts) == 2
    assert not w.admission["busy"]


def test_runner_recovers_pending_and_accepts_worker_thread_results_without_browser(wakeup):
    import agent_subagent_notifications as notifications
    w = wakeup
    w.complete("persisted")
    w.admission["busy"] = True

    async def until(predicate):
        async def wait():
            while not predicate():
                await asyncio.sleep(.02)
        await asyncio.wait_for(wait(), 4)

    async def scenario():
        await notifications.start_runner(w.manager)
        try:
            await until(lambda: w.owner in notifications._pending or w.owner in notifications._workers)
            assert w.calls == []
            w.admission["busy"] = False
            await until(lambda: len(w.calls) == 1 and not w.admission["busy"])
            await asyncio.to_thread(w.complete, "worker-thread-child")
            await until(lambda: len(w.calls) == 2 and not w.admission["busy"])
        finally:
            await notifications.stop_runner()
        assert not notifications._pending
        assert not notifications._workers
        assert notifications._runner is None

    asyncio.run(scenario())
    assert w.delivered == ["persisted result", "worker-thread-child result"]


def test_shutdown_cancels_wakeup_and_releases_parent_reservation(wakeup, monkeypatch):
    import agent_loop
    import agent_subagent_notifications as notifications
    w = wakeup

    async def scenario():
        started = asyncio.Event()

        async def waiting(sid, **kwargs):
            started.set()
            await asyncio.Event().wait()
            yield {}

        monkeypatch.setattr(agent_loop, "astream_events_continuation", waiting)
        w.complete()
        await notifications.start_runner(w.manager)
        await asyncio.wait_for(started.wait(), 4)
        await notifications.stop_runner()
        assert not w.admission["busy"]
        assert len(w.released) == 1
        assert w.manager.has_pending_subagent_notifications(w.owner)

    asyncio.run(scenario())
