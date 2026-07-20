from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


def test_discover_runnable_goal_sessions(monkeypatch):
    import agent_goal
    import webui

    class Manager:
        @staticmethod
        def should_continue(session_id):
            return session_id == "active"

    monkeypatch.setattr(agent_goal, "goal_enabled", lambda: True)
    monkeypatch.setattr(agent_goal, "manager_for", lambda _session_manager: Manager())
    monkeypatch.setattr(
        webui.session_manager,
        "list_sessions",
        lambda include_archived=True: [{"id": "active"}, {"id": "paused"}],
    )

    assert webui._discover_runnable_goal_sessions() == ["active"]


def test_background_goal_runner_drains_continuation_without_browser(monkeypatch):
    import agent_goal
    import webui

    events = []
    releases = []

    class Manager:
        @staticmethod
        def should_continue(_session_id):
            return True

        @staticmethod
        def mark_continuation_started(session_id, *, run_id=""):
            events.append(("started", session_id, run_id))

    async def continuation(session_id, **kwargs):
        events.append(("event", session_id, kwargs.get("run_id")))
        yield {"type": "status"}

    monkeypatch.setattr(agent_goal, "manager_for", lambda _session_manager: Manager())
    monkeypatch.setattr(webui, "astream_events_continuation", continuation)
    monkeypatch.setattr(webui, "_reserve_session_chat_start", lambda _sid, _run_id="": "lease")
    monkeypatch.setattr(webui, "_release_session_chat_start", lambda sid, token="": releases.append((sid, token)))

    asyncio.run(webui._run_goal_continuation_background("s1"))

    assert events[0][0] == "started"
    assert events[1][0:2] == ("event", "s1")
    assert events[1][2] == events[0][2]
    assert releases == [("s1", "lease")]


def test_background_goal_runner_accounts_empty_continuation_as_failure(monkeypatch):
    import agent_goal
    import webui

    recorded = []

    class Manager:
        @staticmethod
        def should_continue(_session_id):
            return True

        @staticmethod
        def get(_session_id):
            return {"id": "g1", "status": "active"}

        @staticmethod
        def mark_continuation_started(_session_id, *, run_id=""):
            return {"current_run_id": run_id}

        @staticmethod
        def record_run(session_id, used_tokens, **kwargs):
            recorded.append((session_id, used_tokens, kwargs))

    async def continuation(_session_id, **_kwargs):
        if False:
            yield {}

    monkeypatch.setattr(agent_goal, "manager_for", lambda _session_manager: Manager())
    monkeypatch.setattr(webui, "astream_events_continuation", continuation)
    monkeypatch.setattr(webui, "_reserve_session_chat_start", lambda _sid, _run_id="": "lease")
    monkeypatch.setattr(webui, "_release_session_chat_start", lambda _sid, token="": None)

    asyncio.run(webui._run_goal_continuation_background("s1"))

    assert len(recorded) == 1
    assert recorded[0][2]["outcome"] == "failed"
    assert recorded[0][2]["continuation"] is True
    assert recorded[0][2]["run_id"].startswith("goal-runner-")


def test_hook_stop_persists_goal_pause_and_pushes_live_state(monkeypatch):
    import agent_loop

    actions = []
    emitted = []

    class Manager:
        @staticmethod
        def get(_session_id):
            return {"id": "g1", "status": "active"}

        @staticmethod
        def user_action(session_id, action, **kwargs):
            actions.append((session_id, action, kwargs))
            return {
                "id": "g1",
                "status": "paused",
                "pause_reason": kwargs.get("reason"),
            }

    async def emit(event):
        emitted.append(event)

    monkeypatch.setattr(agent_loop, "goal_enabled", lambda: True)
    monkeypatch.setattr(agent_loop, "goal_manager_for", lambda _session_manager: Manager())

    result = asyncio.run(
        agent_loop._pause_active_goal_for_hook(
            {"session_id": "s1", "_runtime_v2_run_id": "run-1", "stream_events": []},
            "policy denied",
            emit,
        )
    )

    assert result["status"] == "paused"
    assert actions[0][1] == "pause"
    assert actions[0][2]["actor"] == "hook"
    assert actions[0][2]["reason"] == "hook:policy denied"
    assert emitted[-1]["type"] == "goal_state"


def test_goal_control_forwards_budget_and_publishes_live_state(monkeypatch):
    import agent_goal
    import webui

    calls = []
    published = []

    class Manager:
        @staticmethod
        def user_action(session_id, action, **kwargs):
            calls.append((session_id, action, kwargs))
            return {"id": "g1", "status": "active", "token_budget": 120}

    class Request:
        @staticmethod
        async def json():
            return {"additional_budget": 20, "reason": "continue work"}

    async def publish(session_id, event):
        published.append((session_id, event))

    monkeypatch.setattr(agent_goal, "manager_for", lambda _session_manager: Manager())
    monkeypatch.setattr(webui, "publish_session_event", publish)

    response = asyncio.run(webui.control_session_goal("s1", "resume", Request()))
    body = json.loads(response.body)

    assert response.status_code == 200
    assert body["ok"] is True
    assert calls == [
        (
            "s1",
            "resume",
            {"additional_budget": 20, "reason": "continue work", "actor": "user"},
        )
    ]
    assert published[0][0] == "s1"
    assert published[0][1]["type"] == "goal_state"
