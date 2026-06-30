import sys
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


def test_runtime_v2_persist_does_not_save_legacy_histories(monkeypatch):
    import agent_loop

    calls = []

    class _SessionManager:
        def update_session(self, *args, **kwargs):
            raise AssertionError("Runtime V2 persist must not write work_messages")

        def update_session_model_state(self, *args, **kwargs):
            raise AssertionError("Runtime V2 persist must not write legacy llm_history")

        def _save_llm_history(self, *args, **kwargs):
            raise AssertionError("Runtime V2 persist must not save legacy llm_history")

        def _save_work_messages(self, *args, **kwargs):
            raise AssertionError("Runtime V2 persist must not save legacy work_messages")

        def _save_key_context(self, *args, **kwargs):
            calls.append(("key_context", args, kwargs))

        def _save_dialogue_history(self, *args, **kwargs):
            calls.append(("dialogue", args, kwargs))

        def dialogue_dicts_from_ui_events_file(self, session_id):
            return []

    monkeypatch.setattr(agent_loop, "session_manager", _SessionManager())
    monkeypatch.setattr(agent_loop, "_runtime_v2_is_primary", lambda: True)

    agent_loop._persist_session_messages(
        {
            "session_id": "s1",
            "work_messages": [agent_loop.UserMessage(content="legacy")],
            "llm_history": [agent_loop.UserMessage(content="hello")],
            "key_context": "",
        }
    )

    assert [call[0] for call in calls] == ["key_context", "dialogue"]
    assert calls[0][1][0] == "s1"


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
