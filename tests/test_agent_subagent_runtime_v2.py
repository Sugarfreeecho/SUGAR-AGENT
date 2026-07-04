import asyncio
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


def test_runtime_v2_subagent_run_uses_projection_not_legacy(monkeypatch, tmp_path):
    import agent_loop
    import agent_subagent
    from agent_harness import AssistantMessage
    from runtime_v2 import RuntimeMirror, RuntimeModelProjection

    monkeypatch.setenv("RUNTIME_VERSION", "2")

    class _SessionManager:
        sessions_dir = tmp_path

        def clear_interrupt(self, session_id):
            pass

        def get_or_create_session(self, session_id):
            raise AssertionError("Runtime V2 subagent run must not load legacy session histories")

        def update_session(self, *args, **kwargs):
            raise AssertionError("Runtime V2 subagent run must not save legacy session histories")

        def _load_ui_events(self, session_id):
            raise AssertionError("Runtime V2 subagent final reads must not load legacy ui_events")

        def append_ui_event(self, session_id, event):
            RuntimeMirror(tmp_path).mirror_ui_event(session_id, event)

        def upsert_subagent_task(self, *args, **kwargs):
            pass

        def append_pending_subagent_result(self, *args, **kwargs):
            pass

        def patch_subagent_metadata(self, *args, **kwargs):
            pass

        def write_subagent_output(self, child_session_id, text):
            return str(tmp_path / child_session_id / "output.md")

    async def fake_react_node(state, emit=None):
        final = AssistantMessage(content="done")
        final.metadata = {"is_final": True}
        out = dict(state)
        out["llm_history"] = list(state.get("llm_history") or []) + [final]
        out["work_messages"] = list(state.get("work_messages") or []) + [final]
        out["final_response"] = "done"
        out["key_context"] = "subagent context"
        return out

    monkeypatch.setattr(agent_subagent, "session_manager", _SessionManager())
    monkeypatch.setattr(agent_subagent.todo_manager, "sync_session_from_key_context", lambda *args, **kwargs: None)
    monkeypatch.setattr(agent_subagent, "cleanup_git_worktree_for_session", lambda *args, **kwargs: None)
    monkeypatch.setattr(agent_loop, "react_node", fake_react_node)

    result = asyncio.run(
        agent_subagent._execute_subagent_run(
            child_id="child",
            parent_session_id="parent",
            user_text="task",
            description="desc",
            subagent_type="generalPurpose",
            resumed=False,
        )
    )

    messages = RuntimeModelProjection(tmp_path).read_message_dicts("child")
    assert any(item.get("type") == "user" and "task" in item.get("content", "") for item in messages)
    assert any(item.get("type") == "assistant" and item.get("content") == "done" for item in messages)
    assert agent_subagent._get_subagent_final_result("child") == "done"
    assert "done" in result


def test_subagent_child_session_state_is_not_forwarded_to_parent(monkeypatch, tmp_path):
    import agent_loop
    import agent_subagent
    from agent_harness import AssistantMessage
    from runtime_v2 import RuntimeMirror

    monkeypatch.setenv("RUNTIME_VERSION", "2")
    persisted_events = []
    parent_events = []

    class _SessionManager:
        sessions_dir = tmp_path

        def clear_interrupt(self, session_id):
            pass

        def get_or_create_session(self, session_id):
            raise AssertionError("Runtime V2 subagent run must not load legacy session histories")

        def update_session(self, *args, **kwargs):
            raise AssertionError("Runtime V2 subagent run must not save legacy session histories")

        def append_ui_event(self, session_id, event):
            persisted_events.append((session_id, dict(event)))
            RuntimeMirror(tmp_path).mirror_ui_event(session_id, event)

        def upsert_subagent_task(self, *args, **kwargs):
            pass

        def append_pending_subagent_result(self, *args, **kwargs):
            pass

        def patch_subagent_metadata(self, *args, **kwargs):
            pass

        def write_subagent_output(self, child_session_id, text):
            return str(tmp_path / child_session_id / "output.md")

    async def fake_react_node(state, emit=None):
        if emit:
            await emit({"type": "todo_plan", "items": [{"id": "1", "text": "child todo"}]})
            await emit({"type": "context_tokens", "estimated": 123, "threshold": 1000})
            await emit({"type": "status", "content": "child working"})
        final = AssistantMessage(content="done")
        final.metadata = {"is_final": True}
        out = dict(state)
        out["llm_history"] = list(state.get("llm_history") or []) + [final]
        out["work_messages"] = list(state.get("work_messages") or []) + [final]
        out["final_response"] = "done"
        return out

    async def parent_emit(ev):
        parent_events.append(dict(ev))

    monkeypatch.setattr(agent_subagent, "session_manager", _SessionManager())
    monkeypatch.setattr(agent_subagent.todo_manager, "sync_session_from_key_context", lambda *args, **kwargs: None)
    monkeypatch.setattr(agent_subagent, "cleanup_git_worktree_for_session", lambda *args, **kwargs: None)
    monkeypatch.setattr(agent_loop, "react_node", fake_react_node)

    result = asyncio.run(
        agent_subagent._execute_subagent_run(
            child_id="child",
            parent_session_id="parent",
            user_text="task",
            description="desc",
            subagent_type="generalPurpose",
            resumed=False,
            parent_emit=parent_emit,
        )
    )

    persisted_types = [event.get("type") for sid, event in persisted_events if sid == "child"]
    parent_types = [event.get("type") for event in parent_events]

    assert "todo_plan" in persisted_types
    assert "context_tokens" in persisted_types
    assert "todo_plan" not in parent_types
    assert "context_tokens" not in parent_types
    assert any(event.get("type") == "status" and event.get("agent_id") == "child" for event in parent_events)
    assert any(event.get("type") == "subagent_finish" and event.get("agent_id") == "child" for event in parent_events)
    assert "done" in result
