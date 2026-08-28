from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


def _load_plugin_module(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


_GOAL_RUNTIME = _load_plugin_module("test_goal_runtime", "plugins/agent-goal/runtime.py")
_GOAL_RUNNER = _load_plugin_module("test_goal_runner_plugin", "plugins/agent-goal/runner.py")
goal_host = _load_plugin_module("test_goal_host", "plugins/agent-goal/host.py")


class _RuntimeProxy:
    def __getattr__(self, name):
        import agent_loop
        _GOAL_RUNTIME.initialize(agent_loop)
        return getattr(_GOAL_RUNTIME, name)


class _RunnerProxy:
    def __getattr__(self, name):
        import webui
        _GOAL_RUNNER._host = webui
        return getattr(_GOAL_RUNNER, name)


goal_runtime = _RuntimeProxy()
goal_runner = _RunnerProxy()


def test_discover_runnable_goal_sessions(monkeypatch):
    import agent_goal
    import webui

    class Manager:
        @staticmethod
        def should_continue(session_id):
            return session_id in {"active", "waiting", "stopped"}

    monkeypatch.setattr(agent_goal, "goal_enabled", lambda: True)
    monkeypatch.setattr(agent_goal, "manager_for", lambda _session_manager: Manager())
    monkeypatch.setattr(
        webui.session_manager,
        "list_sessions",
        lambda include_archived=True: [
            {"id": "active"},
            {"id": "paused"},
            {"id": "waiting"},
            {"id": "stopped"},
        ],
    )
    monkeypatch.setattr(webui, "_session_pending_human_count", lambda sid: 1 if sid == "waiting" else 0)
    monkeypatch.setattr(webui, "_session_was_manually_stopped", lambda sid: sid == "stopped")

    assert goal_runner._discover() == ["active"]


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
        def get(_session_id):
            return {}

        @staticmethod
        def mark_continuation_started(session_id, *, run_id=""):
            events.append(("started", session_id, run_id))

    async def continuation(session_id, **kwargs):
        events.append(("event", session_id, kwargs.get("run_id"), kwargs.get("continuation_source")))
        yield {"type": "status"}

    monkeypatch.setattr(agent_goal, "manager_for", lambda _session_manager: Manager())
    monkeypatch.setattr(webui, "_session_pending_human_count", lambda _sid: 0)
    monkeypatch.setattr(webui, "astream_events_continuation", continuation)
    monkeypatch.setattr(webui, "_reserve_session_chat_start", lambda _sid, _run_id="": "lease")
    monkeypatch.setattr(webui, "_release_session_chat_start", lambda sid, token="": releases.append((sid, token)))

    asyncio.run(goal_runner._continue("s1"))

    assert events[0][0] == "started"
    assert events[1][0:2] == ("event", "s1")
    assert events[1][2] == events[0][2]
    assert events[1][3] == "agent-goal"
    assert releases == [("s1", "lease")]


def test_background_goal_runner_stops_for_pending_human_interaction(monkeypatch):
    import agent_goal
    import webui

    events = []

    class Manager:
        @staticmethod
        def should_continue(_session_id):
            return True

        @staticmethod
        def mark_continuation_started(*_args, **_kwargs):
            events.append("started")

    async def continuation(*_args, **_kwargs):
        events.append("continued")
        yield {"type": "status"}

    monkeypatch.setattr(agent_goal, "manager_for", lambda _session_manager: Manager())
    monkeypatch.setattr(webui, "_session_pending_human_count", lambda _sid: 1)
    monkeypatch.setattr(webui, "astream_events_continuation", continuation)
    monkeypatch.setattr(webui, "_reserve_session_chat_start", lambda _sid, _run_id="": "lease")
    monkeypatch.setattr(webui, "_release_session_chat_start", lambda _sid, token="": None)

    asyncio.run(goal_runner._continue("waiting"))

    assert events == []


def test_background_goal_runner_does_not_restart_a_manually_stopped_session(monkeypatch):
    import agent_goal
    import webui

    events = []

    class Manager:
        @staticmethod
        def should_continue(_session_id):
            return True

        @staticmethod
        def mark_continuation_started(*_args, **_kwargs):
            events.append("started")

    async def continuation(*_args, **_kwargs):
        events.append("continued")
        yield {"type": "status"}

    monkeypatch.setattr(agent_goal, "manager_for", lambda _session_manager: Manager())
    monkeypatch.setattr(webui, "_session_was_manually_stopped", lambda _sid: True)
    monkeypatch.setattr(webui, "_session_pending_human_count", lambda _sid: 0)
    monkeypatch.setattr(webui, "astream_events_continuation", continuation)
    monkeypatch.setattr(webui, "_reserve_session_chat_start", lambda _sid, _run_id="": "lease")
    monkeypatch.setattr(webui, "_release_session_chat_start", lambda _sid, token="": None)

    asyncio.run(goal_runner._continue("stopped"))

    assert events == []


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
    monkeypatch.setattr(webui, "_session_pending_human_count", lambda _sid: 0)
    monkeypatch.setattr(webui, "astream_events_continuation", continuation)
    monkeypatch.setattr(webui, "_reserve_session_chat_start", lambda _sid, _run_id="": "lease")
    monkeypatch.setattr(webui, "_release_session_chat_start", lambda _sid, token="": None)

    asyncio.run(goal_runner._continue("s1"))

    assert len(recorded) == 1
    assert recorded[0][2]["outcome"] == "failed"
    assert recorded[0][2]["continuation"] is True
    assert recorded[0][2]["run_id"].startswith("workflow-runner-")


def test_hook_stop_persists_goal_pause_and_pushes_live_state(monkeypatch):
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

    monkeypatch.setattr(_GOAL_RUNTIME, "goal_enabled", lambda: True)
    monkeypatch.setattr(_GOAL_RUNTIME, "goal_manager_for", lambda _session_manager: Manager())

    result = asyncio.run(
        goal_runtime._pause_active_goal_for_hook(
            {"session_id": "s1", "_runtime_v2_run_id": "run-1", "stream_events": []},
            "policy denied",
            emit,
        )
    )

    assert result["status"] == "paused"
    assert actions[0][1] == "pause"
    assert actions[0][2]["actor"] == "hook"
    assert actions[0][2]["reason"] == "hook:policy denied"
    assert emitted[-1]["type"] == "extension_state_changed"
    assert emitted[-1]["plugin_id"] == "agent-goal"


def test_pending_goal_judge_is_keyed_to_the_completion_request(monkeypatch):
    import agent_goal_judge
    import agent_loop

    recorded = []
    evaluated = []
    pending = {
        "id": "g1",
        "status": "active",
        "completion_request_id": "request-2",
        "completion_requested_at": "2026-08-11T00:00:00Z",
        "completion_requested_run_id": "completion-run",
        "accounted_judge_run_ids": [],
    }

    class Manager:
        @staticmethod
        def should_judge(_session_id):
            return True

        @staticmethod
        def get(_session_id):
            return dict(pending)

        @staticmethod
        def record_judge_result(session_id, verdict, reason, **kwargs):
            recorded.append((session_id, verdict, reason, kwargs))
            judge_run_id = kwargs["run_id"]
            return {
                **pending,
                "last_judge_verdict": verdict,
                "last_judge_reason": reason,
                "accounted_judge_run_ids": [judge_run_id],
            }

    monkeypatch.setattr(_GOAL_RUNTIME, "goal_enabled", lambda: True)
    monkeypatch.setattr(_GOAL_RUNTIME, "goal_manager_for", lambda _session_manager: Manager())
    def evaluate_goal(_session_id, _goal, evidence):
        evaluated.append(evidence)
        return {
            "verdict": "continue",
            "reason": "Add the missing verification.",
            "raw": '{"verdict":"continue"}',
            "usage": {},
        }

    monkeypatch.setattr(agent_goal_judge, "evaluate_goal", evaluate_goal)
    monkeypatch.setattr(
        _GOAL_RUNTIME,
        "_load_goal_judge_dialogue_for_goal",
        lambda session_id, goal: [
            {
                "role": "user" if index % 2 == 0 else "assistant",
                "kind": "question" if index == 0 else (
                    "followup" if index % 2 == 0 else "response"
                ),
                "content": f"recovered-dialogue-{index}",
                "run_id": "goal-run",
            }
            for index in range(40)
        ] if session_id == "s1" and goal.get("id") == "g1" else [],
    )

    emitted = []

    async def emit(event):
        emitted.append(event)

    goal, applied = asyncio.run(
        goal_runtime._run_pending_goal_judge(
            {
                "session_id": "s1",
                "_runtime_v2_run_id": "run-7",
                "_goal_judge_current_dialogue": [
                    {"role": "user", "kind": "question", "content": "next-run-question"}
                ],
                "_goal_judge_prior_work_messages": [],
                "work_messages": [],
                "stream_events": [],
            },
            emit,
        )
    )

    assert applied is True
    assert goal["last_judge_verdict"] == "continue"
    assert recorded[0][3]["run_id"] == "run-7:judge:request-2"
    assert "recovered-dialogue-0" in evaluated[0]["goal_dialogue"]
    assert "recovered-dialogue-39" in evaluated[0]["goal_dialogue"]
    assert evaluated[0]["goal_dialogue"].count("recovered-dialogue-") == 40
    assert "next-run-question" not in evaluated[0]["goal_dialogue"]
    review = next(
        event
        for event in emitted
        if event["type"] == "extension_event" and event["event_name"] == "judge_result"
    )
    assert review["data"]["verdict"] == "continue"
    assert review["data"]["reason"] == "Add the missing verification."
    assert review["data"]["judge_run_id"] == "run-7:judge:request-2"
    assert "ephemeral" not in review


def test_goal_judge_reconstructs_complete_goal_lifecycle_across_runs(monkeypatch):
    import agent_loop

    class Event:
        def __init__(self, seq, event_type, run_id, payload):
            self.seq = seq
            self.type = event_type
            self.run_id = run_id
            self.payload = payload

    events = [
        Event(1, "user_turn_committed", "before-goal", {"content": "unrelated-before-goal"}),
        Event(2, "user_turn_committed", "origin-run", {
            "content": "model-transformed-origin-question",
            "ui_content": "goal-origin-question",
        }),
        Event(3, "model_assistant", "origin-run", {"content": "pre-create-response"}),
        Event(4, "goal_created", "origin-run", {"id": "g1"}),
        Event(5, "model_assistant", "origin-run", {"content": "origin-run-final"}),
        Event(6, "assistant_final_committed", "origin-run", {"content": "origin-run-final"}),
        Event(7, "user_turn_committed", "continuation-1", {
            "content": "<user_followup>goal-followup</user_followup>",
            "ui_content": "goal-followup",
        }),
        Event(8, "model_assistant", "continuation-1", {"content": "continuation-final"}),
        Event(9, "user_turn_committed", "completion-run", {"content": "last-followup"}),
        Event(10, "model_assistant", "completion-run", {"content": "completion-response"}),
        Event(11, "goal_completion_requested", "completion-run", {
            "id": "g1",
            "completion_request_id": "request-2",
        }),
        Event(12, "user_turn_committed", "next-run", {"content": "unrelated-next-run"}),
    ]

    class EventLog:
        @staticmethod
        def iter_events(session_id):
            assert session_id == "s1"
            return iter(events)

    class Ops:
        event_log = EventLog()

    monkeypatch.setattr(agent_loop, "_runtime_v2_is_primary", lambda: True)
    monkeypatch.setattr(agent_loop, "_runtime_v2_react_history_ops", lambda: Ops())

    rows = goal_runtime._load_goal_judge_dialogue_for_goal("s1", {
        "id": "g1",
        "origin_run_id": "origin-run",
        "completion_request_id": "request-2",
        "completion_requested_run_id": "completion-run",
    })

    contents = [row["content"] for row in rows]
    assert contents == [
        "goal-origin-question",
        "pre-create-response",
        "origin-run-final",
        "goal-followup",
        "continuation-final",
        "last-followup",
        "completion-response",
    ]
    assert rows[0]["kind"] == "question"
    assert rows[3]["kind"] == "followup"
    assert "unrelated-before-goal" not in contents
    assert "unrelated-next-run" not in contents
    assert "model-transformed-origin-question" not in contents
    assert not any("<user_followup>" in content for content in contents)


def test_applied_goal_judge_is_appended_to_current_model_history(monkeypatch):
    import agent_loop

    persisted = []

    async def judge(_state, _emit=None):
        return ({
            "id": "g1",
            "status": "active",
            "last_judge_verdict": "continue",
            "last_judge_reason": "Run the end-to-end test.",
        }, True)

    monkeypatch.setattr(_GOAL_RUNTIME, "_run_pending_goal_judge", judge)
    monkeypatch.setattr(
        agent_loop,
        "_persist_state_with_model_append",
        lambda _state, message: persisted.append(message),
    )
    state = {
        "session_id": "s1",
        "work_messages": [],
        "llm_history": [],
    }

    asyncio.run(goal_runtime._judge_pending_goal_and_append_context(state))

    assert len(state["work_messages"]) == 1
    assert state["work_messages"][0] is state["llm_history"][0]
    assert state["llm_history"][0] is persisted[0]
    assert "Verdict: continue" in state["llm_history"][0].content
    assert "Run the end-to-end test." in state["llm_history"][0].content


def test_goal_judge_keeps_complete_goal_dialogue_beyond_recent_32(monkeypatch):
    import agent_loop
    from agent_messages import AssistantMessage, ToolMessage, UserMessage

    state = {
        "work_messages": [],
        "_goal_judge_current_dialogue": [],
        "final_response": "",
    }
    for index in range(40):
        if index % 2 == 0:
            role = "user"
            content = f"user-message-{index}"
            message = UserMessage(content=content)
            kind = "question" if index == 0 else "followup"
        else:
            role = "assistant"
            content = f"assistant-message-{index}"
            message = AssistantMessage(content=content)
            kind = "response"
        goal_runtime._capture_goal_judge_dialogue(state, role, content, kind=kind)
        state["work_messages"].append(message)
        state["work_messages"].append(
            ToolMessage(content=f"tool-evidence-{index}", tool_call_id=f"tool-{index}")
        )

    evidence = goal_runtime._goal_judge_evidence(state)

    assert "user-message-0" in evidence["goal_dialogue"]
    assert "assistant-message-39" in evidence["goal_dialogue"]
    assert evidence["goal_dialogue"].count("message-") == 40
    assert "tool-evidence-39" in evidence["recent_evidence"]
    assert "tool-evidence-8" in evidence["recent_evidence"]
    assert evidence["recent_evidence"].count("tool-evidence-") == 32
    assert "tool-evidence-7" not in evidence["recent_evidence"]
    assert "tool-evidence-0" not in evidence["recent_evidence"]
    assert "assistant-message-39" not in evidence["recent_evidence"]


def test_goal_judge_prompt_does_not_clip_goal_dialogue(monkeypatch):
    from agent_goal_judge import build_judge_prompt

    goal_dialogue = "GOAL-DIALOGUE-START\n" + ("x" * 5000) + "\nGOAL-DIALOGUE-END"
    recent_evidence = "AUXILIARY-START\n" + ("y" * 5000) + "\nAUXILIARY-END"
    monkeypatch.setenv("GOAL_JUDGE_EVIDENCE_MAX_CHARS", "2000")

    prompt = build_judge_prompt(
        {
            "id": "g1",
            "objective": "Verify the complete current dialogue",
            "completion_requested_at": "2026-08-12T00:00:00Z",
        },
        {
            "goal_dialogue": goal_dialogue,
            "recent_evidence": recent_evidence,
        },
    )

    assert "GOAL-DIALOGUE-START" in prompt
    assert "GOAL-DIALOGUE-END" in prompt
    assert "AUXILIARY-START" not in prompt
    assert "AUXILIARY-END" in prompt


def test_tool_review_context_keeps_all_followups_last_10_assistant_entries_and_args(monkeypatch):
    import agent_loop

    class Event:
        def __init__(self, seq, event_type, run_id, payload):
            self.seq = seq
            self.type = event_type
            self.run_id = run_id
            self.payload = payload

    events = [
        Event(1, "user_turn_committed", "run-1", {
            "content": "transformed question",
            "ui_content": "initial question",
            "ui_type": "user",
        }),
    ]
    seq = 2
    for index in range(6):
        events.append(Event(seq, "model_assistant", "run-1", {
            "content": f"response-{index}",
            "additional_kwargs": {"reasoning_content": f"reasoning-{index}"},
        }))
        seq += 1
        events.append(Event(seq, "user_turn_committed", "run-1", {
            "content": f"<user_followup>followup-{index}</user_followup>",
            "ui_content": f"followup-{index}",
            "ui_type": "user_steer",
        }))
        seq += 1
    events.append(Event(seq, "user_turn_committed", "run-1", {
        "content": "same-followup",
        "ui_content": "same-followup",
        "ui_type": "user_steer",
    }))
    events.append(Event(seq + 1, "user_turn_committed", "run-1", {
        "content": "same-followup",
        "ui_content": "same-followup",
        "ui_type": "user_steer",
    }))

    class EventLog:
        @staticmethod
        def iter_events(session_id):
            assert session_id == "s1"
            return iter(events)

    class Ops:
        event_log = EventLog()

    monkeypatch.setattr(agent_loop, "_runtime_v2_is_primary", lambda: True)
    monkeypatch.setattr(agent_loop, "_runtime_v2_react_history_ops", lambda: Ops())
    arguments = {
        "command": "Remove-Item -LiteralPath D:/outside/file.txt",
        "options": {"recursive": False, "force": True},
    }

    context = goal_runtime._build_tool_review_context(
        {"session_id": "s1", "_submitted_user_input": "wrong fallback"},
        arguments,
    )
    arguments["options"]["force"] = False

    assert context["initial_user_question"] == "initial question"
    assert context["user_followups"] == [
        *[f"followup-{index}" for index in range(6)],
        "same-followup",
        "same-followup",
    ]
    assert context["assistant_context"] == [
        {"kind": kind, "content": f"{kind}-{index}"}
        for index in range(1, 6)
        for kind in ("reasoning", "response")
    ]
    assert context["tool_arguments"] == {
        "command": "Remove-Item -LiteralPath D:/outside/file.txt",
        "options": {"recursive": False, "force": True},
    }


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
    monkeypatch.setattr(goal_host, "publish_session_event", publish)

    response = asyncio.run(goal_host.control_goal(webui.session_manager, "s1", "resume", Request()))
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
    assert published[0][1]["type"] == "extension_state_changed"
    assert published[0][1]["plugin_id"] == "agent-goal"


def test_goal_edit_and_delete_routes_publish_session_scoped_state(monkeypatch):
    import agent_goal
    import webui

    calls = []
    published = []
    interrupts = []

    class Manager:
        @staticmethod
        def user_action(session_id, action, **kwargs):
            calls.append((session_id, action, kwargs))
            return {
                "id": "g1",
                "status": "active" if action == "edit" else "cancelled",
                "objective": kwargs.get("objective") or "Edited objective",
                "deleted": action == "delete",
            }

    class EditRequest:
        @staticmethod
        async def json():
            return {"objective": "Edited objective"}

    class DeleteRequest:
        @staticmethod
        async def json():
            return {}

    async def publish(session_id, event):
        published.append((session_id, event))

    monkeypatch.setattr(agent_goal, "manager_for", lambda _session_manager: Manager())
    monkeypatch.setattr(goal_host, "publish_session_event", publish)
    monkeypatch.setattr(
        webui.session_manager,
        "request_interrupt",
        lambda *args, **kwargs: interrupts.append((args, kwargs)),
    )

    edited = asyncio.run(goal_host.control_goal(webui.session_manager, "s1", "edit", EditRequest()))
    deleted = asyncio.run(goal_host.control_goal(webui.session_manager, "s1", "delete", DeleteRequest()))
    edited_body = json.loads(edited.body)
    deleted_body = json.loads(deleted.body)

    assert edited_body["goal"]["objective"] == "Edited objective"
    assert calls[0][2]["objective"] == "Edited objective"
    assert published[0][1]["action"] == "user_edit"
    assert deleted_body["goal"] is None
    assert published[1][0] == "s1"
    assert published[1][1]["action"] == "user_delete"
    assert interrupts == []


def test_goal_review_route_reopens_or_removes_completed_goal(monkeypatch):
    import agent_goal
    import webui

    calls = []
    published = []
    cleared = []

    class Manager:
        @staticmethod
        def review_completion(session_id, decision, **kwargs):
            calls.append((session_id, decision, kwargs))
            return {
                "id": "g1",
                "status": "active" if decision == "continue" else "completed",
                "objective": kwargs["objective"],
                "review_judge_result": kwargs["judge_result"],
                "deleted": decision == "approve",
            }

    class ContinueRequest:
        @staticmethod
        async def json():
            return {
                "decision": "continue",
                "objective": "Revised objective",
                "judge_result": "Verification is missing.",
                "additional_budget": 50,
            }

    class ApproveRequest:
        @staticmethod
        async def json():
            return {
                "decision": "approve",
                "objective": "Revised objective",
                "judge_result": "Verified by the reviewer.",
            }

    async def publish(session_id, event):
        published.append((session_id, event))

    monkeypatch.setattr(agent_goal, "manager_for", lambda _session_manager: Manager())
    monkeypatch.setattr(goal_host, "publish_session_event", publish)
    monkeypatch.setattr(
        webui.session_manager,
        "clear_interrupt",
        lambda session_id: cleared.append(session_id),
    )

    continued = asyncio.run(
        goal_host.control_goal(webui.session_manager, "s1", "review", ContinueRequest())
    )
    approved = asyncio.run(
        goal_host.control_goal(webui.session_manager, "s1", "review", ApproveRequest())
    )
    continued_body = json.loads(continued.body)
    approved_body = json.loads(approved.body)

    assert continued_body["goal"]["status"] == "active"
    assert calls[0][1] == "continue"
    assert calls[0][2]["additional_budget"] == 50
    assert cleared == ["s1"]
    assert published[0][1]["action"] == "user_review_continue"
    assert approved_body["goal"] is None
    assert published[1][1]["action"] == "user_review_approve"
