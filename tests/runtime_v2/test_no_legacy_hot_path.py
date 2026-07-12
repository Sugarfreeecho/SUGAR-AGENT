import inspect
import sys
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[2] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))


def test_v1_ui_append_does_not_mirror_into_runtime_v2(monkeypatch):
    import agent_harness
    import runtime_v2

    saved = []
    monkeypatch.setattr(runtime_v2, "runtime_v2_primary", lambda: False)

    class _Manager:
        index = []

        def _load_ui_events(self, _session_id):
            return []

        def _save_ui_events(self, session_id, events):
            saved.append((session_id, list(events)))

        def _mirror_ui_event_to_runtime_v2(self, *_args, **_kwargs):
            raise AssertionError("V1 must not write Runtime V2")

        def _apply_appended_ui_event_side_effects(self, *_args, **_kwargs):
            pass

    agent_harness.SessionManager.append_ui_event(
        _Manager(),
        "v1-session",
        {"type": "user", "content": "hello"},
    )

    assert saved[0][0] == "v1-session"
    assert saved[0][1][0]["content"] == "hello"


def test_v1_model_persistence_does_not_write_runtime_v2(monkeypatch):
    import agent_loop

    persisted = []
    monkeypatch.setattr(agent_loop, "_runtime_v2_is_primary", lambda: False)
    monkeypatch.setattr(agent_loop, "_persist_state", lambda state: persisted.append(("state", state)))
    monkeypatch.setattr(
        agent_loop,
        "_persist_session_messages",
        lambda state: persisted.append(("session", state)),
    )
    monkeypatch.setattr(
        agent_loop,
        "_runtime_v2_append_model_message",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("V1 must not append V2 model rows")),
    )
    monkeypatch.setattr(
        agent_loop,
        "_runtime_v2_replace_model_history",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("V1 must not replace V2 model history")),
    )

    state = {"session_id": "v1-session"}
    agent_loop._persist_state_with_model_append(state, object())
    agent_loop._persist_state_with_model_replace(state, [], "test")
    agent_loop._persist_session_messages_with_model_replace(state, [], "test")

    assert [kind for kind, _state in persisted] == ["state", "state", "session"]


def test_v2_model_and_context_loaders_do_not_reference_legacy_reconcile():
    import agent_loop

    model_source = inspect.getsource(agent_loop._load_runtime_v2_model_history_dicts)
    context_source = inspect.getsource(agent_loop._load_runtime_v2_context_summary)
    assert "_load_llm_history" not in model_source
    assert "reconcile" not in model_source
    assert "_load_key_context" not in context_source


def test_chat_form_defaults_to_runtime_v2_protocol():
    import webui

    parameter = inspect.signature(webui.chat).parameters["stream_protocol"]
    assert getattr(parameter.default, "default", None) == "runtime_v2"


def test_v2_tail_restore_does_not_call_legacy_projection_api():
    import agent_harness

    source = inspect.getsource(agent_harness.SessionManager.append_ui_events_tail)
    v2_branch = source.split("if self._runtime_v2_primary():", 1)[1].split("return True", 1)[0]
    assert "replace_from_legacy" not in v2_branch
    assert "replace_from_ui_events" in v2_branch
