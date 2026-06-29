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


def test_runtime_v2_model_history_prefers_projection(monkeypatch):
    import agent_loop

    monkeypatch.setattr(agent_loop, "session_manager", _NoLegacySessionManager())
    monkeypatch.setattr(agent_loop, "_load_runtime_v2_model_history_dicts", lambda _sid: [
        {"type": "user", "content": "hello"},
    ])

    messages = agent_loop._load_model_history_dicts_v2_primary("s1", reconcile_legacy=True)

    assert messages == [{"type": "user", "content": "hello"}]


def test_runtime_v2_run_does_not_load_work_messages(monkeypatch):
    import agent_loop

    class _SessionManager:
        def _load_work_messages(self, session_id):
            raise AssertionError("Runtime V2 run setup must not load work_messages")

    monkeypatch.setattr(agent_loop, "session_manager", _SessionManager())
    monkeypatch.setattr(agent_loop, "_runtime_v2_is_primary", lambda: True)

    assert agent_loop._load_work_history_dicts_for_run("s1") == []


def test_runtime_v2_persist_does_not_save_work_messages(monkeypatch):
    import agent_loop

    calls = []

    class _SessionManager:
        def update_session(self, *args, **kwargs):
            raise AssertionError("Runtime V2 persist must not write work_messages")

        def update_session_model_state(self, *args, **kwargs):
            calls.append((args, kwargs))

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

    assert len(calls) == 1
    assert calls[0][0][0] == "s1"
