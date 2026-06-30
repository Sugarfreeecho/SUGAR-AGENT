import sys
import asyncio
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


class _NoLegacySessionManager:
    def reconcile_llm_work_to_ui_user_count(self, *args, **kwargs):
        raise AssertionError("Runtime V2 projection reads must not reconcile legacy history")

    def _load_llm_history(self, session_id):
        raise AssertionError("Runtime V2 projection reads must not load legacy llm_history")

    def can_continue_after_subagents(self, session_id):
        return True

    def _load_key_context(self, session_id):
        raise AssertionError("Runtime V2 run setup must not load legacy key_context")

    def migrate_todo_plan_off_key_context(self, session_id, key_context):
        raise AssertionError("Runtime V2 run setup must not migrate legacy key_context")


def test_runtime_v2_model_history_prefers_projection(monkeypatch):
    import agent_loop

    monkeypatch.setattr(agent_loop, "session_manager", _NoLegacySessionManager())
    monkeypatch.setattr(agent_loop, "_load_runtime_v2_model_history_dicts", lambda _sid: [
        {"type": "user", "content": "hello"},
    ])

    messages = agent_loop._load_model_history_dicts_v2_primary("s1", reconcile_legacy=True)

    assert messages == [{"type": "user", "content": "hello"}]


def test_runtime_v2_model_history_empty_projection_does_not_fallback_legacy(monkeypatch):
    import agent_loop

    monkeypatch.setattr(agent_loop, "session_manager", _NoLegacySessionManager())
    monkeypatch.setattr(agent_loop, "_runtime_v2_is_primary", lambda: True)
    monkeypatch.setattr(agent_loop, "_load_runtime_v2_model_history_dicts", lambda _sid: [])

    messages = agent_loop._load_model_history_dicts_v2_primary("s1", reconcile_legacy=True)

    assert messages == []


def test_runtime_v1_model_history_keeps_legacy_fallback(monkeypatch):
    import agent_loop

    calls = []

    class _SessionManager:
        def reconcile_llm_work_to_ui_user_count(self, session_id, include_work=False):
            calls.append(("reconcile", session_id, include_work))

        def _load_llm_history(self, session_id):
            calls.append(("load", session_id))
            return [{"type": "user", "content": "legacy"}]

    monkeypatch.setattr(agent_loop, "session_manager", _SessionManager())
    monkeypatch.setattr(agent_loop, "_runtime_v2_is_primary", lambda: False)

    messages = agent_loop._load_model_history_dicts_v2_primary("s1", reconcile_legacy=True)

    assert messages == [{"type": "user", "content": "legacy"}]
    assert calls == [("reconcile", "s1", False), ("load", "s1")]


def test_runtime_v2_context_token_compute_uses_projection_not_legacy(monkeypatch):
    import agent_loop

    captured = {}

    class _SessionManager:
        sessions_dir = Path("unused")

        def get_or_create_session(self, session_id):
            raise AssertionError("Runtime V2 context token compute must not read legacy session history")

    def fake_estimate(session_id, messages, key_context):
        captured["session_id"] = session_id
        captured["messages"] = messages
        captured["key_context"] = key_context
        return 123

    monkeypatch.setattr(agent_loop, "session_manager", _SessionManager())
    monkeypatch.setattr(agent_loop, "_runtime_v2_is_primary", lambda: True)
    monkeypatch.setattr(agent_loop, "_load_runtime_v2_model_history_dicts", lambda _sid: [
        {"type": "user", "content": "hello"},
    ])
    monkeypatch.setattr(agent_loop, "_load_runtime_v2_context_summary", lambda _sid: "summary")
    monkeypatch.setattr(agent_loop, "estimate_full_input_tokens_for_llm_history", fake_estimate)
    monkeypatch.setattr(agent_loop, "resolve_executor_config_for_session", lambda _sid: (None, "m", 1024, 4096))

    result = agent_loop.compute_context_tokens_for_session("s1")

    assert result == {
        "ok": True,
        "estimated": 123,
        "threshold": 4096,
        "model": "m",
        "source": "runtime_v2_projection",
    }
    assert captured["session_id"] == "s1"
    assert captured["messages"][0].content == "hello"
    assert captured["key_context"] == "summary"


def test_runtime_v2_run_key_context_uses_snapshot_not_legacy(monkeypatch):
    import agent_loop

    monkeypatch.setattr(agent_loop, "session_manager", _NoLegacySessionManager())
    monkeypatch.setattr(agent_loop, "_runtime_v2_is_primary", lambda: True)
    monkeypatch.setattr(agent_loop, "_load_runtime_v2_context_summary", lambda _sid: "summary")

    assert agent_loop._load_key_context_for_run("s1") == "summary"


def test_runtime_v1_run_key_context_keeps_legacy_migration(monkeypatch):
    import agent_loop

    calls = []

    class _SessionManager:
        def _load_key_context(self, session_id):
            calls.append(("load", session_id))
            return "legacy"

        def migrate_todo_plan_off_key_context(self, session_id, key_context):
            calls.append(("migrate", session_id, key_context))
            return "migrated"

    monkeypatch.setattr(agent_loop, "session_manager", _SessionManager())
    monkeypatch.setattr(agent_loop, "_runtime_v2_is_primary", lambda: False)

    assert agent_loop._load_key_context_for_run("s1") == "migrated"
    assert calls == [("load", "s1"), ("migrate", "s1", "legacy")]


def test_agent_loop_does_not_auto_backfill_v2_model_history_from_legacy():
    source = (APP_DIR / "agent_loop.py").read_text(encoding="utf-8")

    assert "legacy_model_sync_on_read" not in source
    assert "legacy_model_sync_on_continuation" not in source
    assert ".ensure_backfilled_from_legacy(" not in source
    assert ".sync_from_legacy_if_needed(" not in source


def test_runtime_v2_run_does_not_load_work_messages(monkeypatch):
    import agent_loop

    class _SessionManager:
        def _load_work_messages(self, session_id):
            raise AssertionError("Runtime V2 run setup must not load work_messages")

    monkeypatch.setattr(agent_loop, "session_manager", _SessionManager())
    monkeypatch.setattr(agent_loop, "_runtime_v2_is_primary", lambda: True)

    assert agent_loop._load_work_history_dicts_for_run("s1") == []


def test_runtime_v2_todo_sync_uses_snapshot_not_legacy(monkeypatch, tmp_path):
    import agent_harness
    from runtime_v2 import RuntimeMirror

    monkeypatch.setenv("RUNTIME_VERSION", "2")
    RuntimeMirror(tmp_path).mirror_ui_event(
        "s1",
        {
            "type": "todo_plan",
            "items": [{"id": "1", "text": "from snapshot", "status": "in_progress"}],
            "has_plan": True,
            "done": 0,
            "total": 1,
        },
    )

    class _SessionManager:
        sessions_dir = tmp_path

        def load_todo_plan(self, session_id):
            raise AssertionError("Runtime V2 todo sync must not read legacy todo_plan.md")

    monkeypatch.setattr(agent_harness, "session_manager", _SessionManager())

    manager = agent_harness.TodoManager()
    manager.sync_session_from_key_context("s1", "")

    assert manager._by_session["s1"] == [
        {"id": "1", "text": "from snapshot", "status": "in_progress"}
    ]


def test_runtime_v2_todo_update_does_not_write_legacy_file(monkeypatch, tmp_path):
    import agent_harness

    monkeypatch.setenv("RUNTIME_VERSION", "2")

    class _SessionManager:
        sessions_dir = tmp_path

        def save_todo_plan(self, *args, **kwargs):
            raise AssertionError("Runtime V2 todo update must not write legacy todo_plan.md")

    monkeypatch.setattr(agent_harness, "session_manager", _SessionManager())

    manager = agent_harness.TodoManager()
    result = manager.update_for_session(
        "s1",
        [{"id": "1", "text": "keep in runtime snapshot", "status": "pending"}],
    )

    assert "keep in runtime snapshot" in result
    assert manager._by_session["s1"] == [
        {"id": "1", "text": "keep in runtime snapshot", "status": "pending"}
    ]


def test_runtime_v2_persist_does_not_save_legacy_histories(monkeypatch, tmp_path):
    import agent_loop
    from runtime_v2 import SnapshotStore

    class _SessionManager:
        sessions_dir = None

        def update_session(self, *args, **kwargs):
            raise AssertionError("Runtime V2 persist must not write work_messages")

        def update_session_model_state(self, *args, **kwargs):
            raise AssertionError("Runtime V2 persist must not write legacy llm_history")

        def _save_llm_history(self, *args, **kwargs):
            raise AssertionError("Runtime V2 persist must not save legacy llm_history")

        def _save_work_messages(self, *args, **kwargs):
            raise AssertionError("Runtime V2 persist must not save legacy work_messages")

        def _save_key_context(self, *args, **kwargs):
            raise AssertionError("Runtime V2 persist must not save legacy key_context")

        def _save_dialogue_history(self, *args, **kwargs):
            raise AssertionError("Runtime V2 persist must not save legacy dialogue_history")

        def dialogue_dicts_from_ui_events_file(self, session_id):
            raise AssertionError("Runtime V2 persist must not read legacy ui_events for dialogue_history")

    manager = _SessionManager()
    manager.sessions_dir = tmp_path
    monkeypatch.setattr(agent_loop, "session_manager", manager)
    monkeypatch.setattr(agent_loop, "_runtime_v2_is_primary", lambda: True)

    agent_loop._persist_session_messages(
        {
            "session_id": "s1",
            "work_messages": [agent_loop.UserMessage(content="legacy")],
            "llm_history": [agent_loop.UserMessage(content="hello")],
            "key_context": "runtime v2 context",
        }
    )

    snapshot = SnapshotStore(tmp_path).read("s1")
    summary = snapshot.get("context", {}).get("summary", {})
    assert summary.get("summary") == "runtime v2 context"

    event_log_path = tmp_path / "s1" / "events.jsonl"
    before_events = event_log_path.read_text(encoding="utf-8")
    agent_loop._persist_session_messages(
        {
            "session_id": "s1",
            "work_messages": [agent_loop.UserMessage(content="legacy")],
            "llm_history": [agent_loop.UserMessage(content="hello")],
            "key_context": "runtime v2 context",
        }
    )
    after_events = event_log_path.read_text(encoding="utf-8")
    assert after_events == before_events


def test_runtime_v2_continuation_empty_projection_does_not_reconcile(monkeypatch):
    import agent_loop

    monkeypatch.setattr(agent_loop, "session_manager", _NoLegacySessionManager())
    monkeypatch.setattr(agent_loop, "_runtime_v2_is_primary", lambda: True)
    monkeypatch.setattr(agent_loop, "_load_runtime_v2_model_history_dicts", lambda _sid: [])
    monkeypatch.setattr(agent_loop, "setup_logging", lambda *args, **kwargs: None)

    async def collect():
        out = []
        async for ev in agent_loop.astream_events_continuation(
            "s1",
            require_pending_subagents=False,
        ):
            out.append(ev)
        return out

    import asyncio

    assert asyncio.run(collect()) == []


def test_finish_uses_title_generator_for_new_session(monkeypatch):
    import agent_loop

    names = []
    calls = []

    class _SessionManager:
        def _load_metadata(self, session_id):
            return {"name": "新会话"}

        def set_session_name(self, session_id, title):
            names.append((session_id, title))

    def fake_executor_text_and_usage(prompt):
        calls.append((prompt, list(state["stream_events"])))
        return "model title", {"prompt_tokens": 3, "completion_tokens": 2}

    monkeypatch.setattr(agent_loop, "session_manager", _SessionManager())
    monkeypatch.setattr(agent_loop, "load_prompt_template", lambda name: "Q:{first_user}\nA:{final_response}")
    monkeypatch.setattr(agent_loop, "executor_text_and_usage", fake_executor_text_and_usage)
    monkeypatch.setattr(agent_loop, "_persist_session_messages_with_model_replace", lambda *args, **kwargs: None)

    state = {
        "session_id": "s1",
        "dialogue": [agent_loop.UserMessage(content="hello world from user")],
        "work_messages": [],
        "llm_history": [],
        "stream_events": [],
        "final_response": "done",
        "final_printed": False,
        "llm_calls": [],
    }

    out = agent_loop.finish(state)

    assert out["final_printed"] is True
    assert out["stream_events"][-1] == {"type": "final", "content": "done"}
    assert calls == [("Q:hello world from user\nA:done", [{"type": "final", "content": "done"}])]
    assert names == [("s1", "model title")]


def test_finish_does_not_duplicate_prepared_final_event(monkeypatch):
    import agent_loop

    names = []

    class _SessionManager:
        def _load_metadata(self, session_id):
            return {"name": "新会话"}

        def set_session_name(self, session_id, title):
            names.append((session_id, title))

    monkeypatch.setattr(agent_loop, "session_manager", _SessionManager())
    monkeypatch.setattr(agent_loop, "load_prompt_template", lambda name: "{first_user} {final_response}")
    monkeypatch.setattr(agent_loop, "executor_text_and_usage", lambda prompt: ("model title", None))
    monkeypatch.setattr(agent_loop, "_persist_session_messages_with_model_replace", lambda *args, **kwargs: None)

    state = {
        "session_id": "s1",
        "dialogue": [agent_loop.UserMessage(content="hello")],
        "work_messages": [],
        "llm_history": [],
        "stream_events": [],
        "final_response": "done",
        "final_printed": False,
        "llm_calls": [],
    }

    agent_loop.prepare_final_event(state)
    assert state["stream_events"] == [{"type": "final", "content": "done"}]

    out = agent_loop.finish(state)

    assert out["final_printed"] is True
    assert out["stream_events"] == [{"type": "final", "content": "done"}]
    assert names == [("s1", "model title")]


def test_astream_emits_final_before_title_generation(monkeypatch, tmp_path):
    import agent_loop

    seen = []
    title_call_seen = []

    class _SessionManager:
        sessions_dir = tmp_path

        def clear_interrupt(self, *args, **kwargs):
            pass

        def append_ui_event(self, *args, **kwargs):
            pass

        def _load_metadata(self, session_id):
            return {"name": "新会话"}

        def set_session_name(self, *args, **kwargs):
            pass

        def mark_session_unread_result(self, *args, **kwargs):
            pass

    async def fake_run_react(state, emit):
        out = dict(state)
        out["final_response"] = "done"
        return out

    def fake_executor_text_and_usage(prompt):
        title_call_seen.append(list(seen))
        return "model title", None

    monkeypatch.setattr(agent_loop, "session_manager", _SessionManager())
    monkeypatch.setattr(agent_loop, "_load_key_context_for_run", lambda session_id: "")
    monkeypatch.setattr(agent_loop, "_load_model_history_dicts_v2_primary", lambda session_id, reconcile_legacy=True: [])
    monkeypatch.setattr(agent_loop, "_load_work_history_dicts_for_run", lambda session_id: [])
    monkeypatch.setattr(agent_loop, "_sanitize_loaded_histories_for_new_run", lambda sid, work, llm, key, reason: (work, llm))
    monkeypatch.setattr(agent_loop.todo_manager, "sync_session_from_key_context", lambda *args, **kwargs: None)
    monkeypatch.setattr(agent_loop, "setup_logging", lambda *args, **kwargs: None)
    monkeypatch.setattr(agent_loop, "_runtime_v2_append_model_message", lambda *args, **kwargs: None)
    monkeypatch.setattr(agent_loop, "_persist_state", lambda *args, **kwargs: None)
    monkeypatch.setattr(agent_loop, "_persist_session_messages_with_model_replace", lambda *args, **kwargs: None)
    monkeypatch.setattr(agent_loop, "_run_react_node_off_loop", fake_run_react)
    monkeypatch.setattr(agent_loop, "load_prompt_template", lambda name: "{first_user} {final_response}")
    monkeypatch.setattr(agent_loop, "executor_text_and_usage", fake_executor_text_and_usage)

    async def collect():
        async for ev in agent_loop.astream_events("hello", session_id="s-final-first"):
            seen.append(ev)

    asyncio.run(collect())

    assert title_call_seen, "title generation should still run for new sessions"
    assert any(ev.get("type") == "final" and ev.get("content") == "done" for ev in title_call_seen[0])
