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


def test_v2_model_projection_failure_is_not_converted_to_empty_history(monkeypatch):
    import agent_loop
    import runtime_v2

    class _BrokenProjection:
        def __init__(self, *_args, **_kwargs):
            pass

        def read_message_dicts(self, _session_id):
            raise OSError("projection unavailable")

    monkeypatch.setattr(runtime_v2, "RuntimeModelProjection", _BrokenProjection)
    try:
        agent_loop._load_runtime_v2_model_history_dicts("s1")
    except OSError as exc:
        assert "projection unavailable" in str(exc)
    else:
        raise AssertionError("V2 projection failures must abort the request")


def test_v2_context_projection_failure_is_not_converted_to_empty_summary(monkeypatch):
    import agent_loop
    import runtime_v2

    class _BrokenStore:
        def __init__(self, *_args, **_kwargs):
            pass

        def read_consistent(self, _session_id):
            raise OSError("context snapshot unavailable")

    monkeypatch.setattr(runtime_v2, "SnapshotStore", _BrokenStore)
    try:
        agent_loop._load_runtime_v2_context_summary("s1")
    except OSError as exc:
        assert "context snapshot unavailable" in str(exc)
    else:
        raise AssertionError("V2 context failures must abort the request")


def test_v2_state_persistence_failure_propagates(monkeypatch):
    import agent_loop

    monkeypatch.setattr(agent_loop, "_runtime_v2_is_primary", lambda: True)
    monkeypatch.setattr(
        agent_loop,
        "_persist_session_messages",
        lambda _state: (_ for _ in ()).throw(OSError("disk unavailable")),
    )
    try:
        agent_loop._persist_state({})
    except OSError as exc:
        assert "disk unavailable" in str(exc)
    else:
        raise AssertionError("V2 persistence failures must fail the run")


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


def test_direct_runtime_v2_model_helpers_are_defensive_noops_in_v1(monkeypatch):
    import agent_loop

    monkeypatch.setattr(agent_loop, "_runtime_v2_is_primary", lambda: False)
    state = {"session_id": "v1-session", "key_context": "legacy"}

    agent_loop._runtime_v2_append_model_message(state, {"type": "user", "content": "x"})
    agent_loop._runtime_v2_replace_model_history(state, [], "test")
    agent_loop._runtime_v2_commit_context_summary(state)


def test_v1_subagent_task_and_pending_paths_do_not_mirror_v2():
    import agent_harness

    calls = []

    class _Repository:
        def load_json_list(self, _path):
            return []

        def save_json_list(self, path, rows):
            calls.append(("legacy", path, rows))

    class _Manager:
        repository = _Repository()

        def _runtime_v2_primary(self):
            return False

        def _get_subagent_tasks_path(self, _sid):
            return "tasks.json"

        def _get_pending_subagent_results_path(self, _sid):
            return "pending.json"

        def _runtime_subagent_store(self):
            raise AssertionError("V1 must not construct the V2 subagent store")

        def _upsert_subagent_task_v1(self, parent, task, patch):
            return agent_harness.SessionManager._upsert_subagent_task_v1(
                self, parent, task, patch
            )

        def _load_ui_events_for_active_runtime(self, _sid):
            return []

        def _latest_final_index_without_later_user(self, _events):
            return -1

    manager = _Manager()
    agent_harness.SessionManager.upsert_subagent_task(manager, "parent", "task", {"status": "running"})
    agent_harness.SessionManager.append_pending_subagent_result(
        manager,
        "parent",
        {"task_id": "task", "status": "completed"},
    )

    assert [row[0] for row in calls] == ["legacy", "legacy"]


def test_normal_open_interrupt_and_continuation_are_runtime_isolated():
    import agent_loop
    import webui

    messages_source = inspect.getsource(webui.get_session_messages)
    interrupt_source = inspect.getsource(webui._interrupt_runtime_v2_active_runs)
    resume_source = inspect.getsource(webui._runtime_v2_auto_resume_pending)
    continuation_source = inspect.getsource(agent_loop.astream_events_continuation)

    assert "RUNTIME_SYNC_ON_MESSAGES_OPEN" not in messages_source
    assert "runtime_v2_primary" in interrupt_source
    assert "runtime_v2_primary" in resume_source
    v2_load_at = continuation_source.index("_load_runtime_v2_model_history_dicts")
    runtime_guard_at = continuation_source.index("if _runtime_v2_is_primary()")
    assert runtime_guard_at < v2_load_at


def test_normal_v2_ui_fallback_uses_native_event_type():
    import agent_harness

    source = inspect.getsource(agent_harness.SessionManager._mirror_ui_event_to_runtime_v2)
    assert 'mirror.append(session_id, "ui_event"' in source
    assert 'mirror.append(session_id, "legacy_ui_event"' not in source
