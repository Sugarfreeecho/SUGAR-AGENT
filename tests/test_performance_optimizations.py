from __future__ import annotations

import asyncio
import time


def test_thread_bridge_preserves_first_token_and_coalesces_followups(monkeypatch):
    import agent_loop

    async def scenario():
        queue = asyncio.Queue()
        bridge = agent_loop._ThreadToAsyncQueue(asyncio.get_running_loop(), queue)
        monkeypatch.setattr(bridge, "_TEXT_FLUSH_SECONDS", 0.05)

        bridge.put(("content", "a"))
        assert await asyncio.wait_for(queue.get(), timeout=0.02) == ("content", "a")

        bridge.put(("content", "b"))
        bridge.put(("content", "c"))
        await asyncio.sleep(0.01)
        assert queue.empty()
        assert await asyncio.wait_for(queue.get(), timeout=0.1) == ("content", "bc")

        bridge.put(("reasoning", "r"))
        bridge.put(("tool_call_delta", {"index": 0}))
        assert await asyncio.wait_for(queue.get(), timeout=0.02) == ("reasoning", "r")
        assert await asyncio.wait_for(queue.get(), timeout=0.02) == (
            "tool_call_delta",
            {"index": 0},
        )

    asyncio.run(scenario())


def test_steer_control_notifies_async_waiter_without_polling():
    import agent_loop

    async def scenario():
        control = agent_loop._SteerRunControl("s1", "r1")
        loop = asyncio.get_running_loop()
        event = control.subscribe_abort(loop)
        control.abort("test")
        await asyncio.wait_for(event.wait(), timeout=0.05)
        control.unsubscribe_abort(loop, event)

    asyncio.run(scenario())


def test_execution_metrics_coalesce_writes_until_terminal_flush(tmp_path, monkeypatch):
    import execution_metrics

    execution_metrics.configure(tmp_path / "sessions")
    execution_metrics._sessions.clear()
    execution_metrics.flush()
    monkeypatch.setattr(execution_metrics, "_FLUSH_DELAY_SEC", 10.0)
    writes = []
    monkeypatch.setattr(
        execution_metrics,
        "_write_now",
        lambda session_id, data: writes.append((session_id, len(data.get("runs") or []))),
    )

    execution_metrics.start_run("s1", "r1")
    for index in range(20):
        execution_metrics.record_request("s1", "r1", 1, latest=index)
    assert writes == []
    execution_metrics.finish_run("s1", "r1", "finished")
    assert writes == [("s1", 1)]


def test_observability_steady_scan_targets_only_active_sessions(tmp_path):
    import runtime_observability as obs

    obs.configure(tmp_path)
    obs.start_run("active", "run-1")
    obs._last_full_scan_monotonic = time.monotonic()
    paths = obs._stale_scan_paths()
    assert paths == [tmp_path / "active" / "runtime_observability.json"]
    obs.finish_run("active", "run-1", "finished")
    assert obs._stale_scan_paths() == []


def test_goal_and_team_activity_indexes_follow_state():
    import agent_goal
    from agent_team import service as team_service

    goal_sid = "perf-goal-index"
    team_sid = "perf-team-index"
    agent_goal._track_goal_state(goal_sid, {"id": "g", "status": "active"})
    team_service._track_team_state(team_sid, {"team_id": "t", "status": "active"})
    assert goal_sid in agent_goal.active_goal_session_ids()
    assert team_sid in team_service.active_team_session_ids()

    agent_goal._track_goal_state(goal_sid, {"id": "g", "status": "paused"})
    team_service._track_team_state(team_sid, {"team_id": "t", "status": "stopped"})
    assert goal_sid not in agent_goal.active_goal_session_ids()
    assert team_sid not in team_service.active_team_session_ids()


def test_default_power_guards_share_the_process_broker(monkeypatch):
    import runtime_power

    class Broker:
        def __init__(self):
            self.subscribed = []
            self.unsubscribed = []

        async def subscribe(self, monitor, callback):
            token = object()
            self.subscribed.append((token, monitor, callback))
            return token

        async def unsubscribe(self, token):
            self.unsubscribed.append(token)

    async def scenario():
        broker = Broker()
        monkeypatch.setattr(
            runtime_power,
            "_suspension_broker_for_current_loop",
            lambda: broker,
        )
        monkeypatch.setattr(
            runtime_power.WindowsSleepInhibitor,
            "acquire",
            classmethod(lambda cls: runtime_power.WindowsPowerRequest(None, False)),
        )
        first = runtime_power.AgentRunPowerGuard()
        second = runtime_power.AgentRunPowerGuard()

        async def on_resume(_event):
            return None

        await first.start(on_resume)
        await second.start(on_resume)
        assert len(broker.subscribed) == 2
        assert first._monitor_broker is broker
        assert second._monitor_broker is broker
        await first.close()
        await second.close()
        assert broker.unsubscribed == [
            broker.subscribed[0][0],
            broker.subscribed[1][0],
        ]

    asyncio.run(scenario())
