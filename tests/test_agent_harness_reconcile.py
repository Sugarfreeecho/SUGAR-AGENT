import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


def _manager_with(**attrs):
    import agent_harness

    mgr = agent_harness.SessionManager.__new__(agent_harness.SessionManager)
    for name, value in attrs.items():
        setattr(mgr, name, value)
    return mgr


def test_reconcile_does_not_rebuild_when_llm_user_count_matches_ui():
    import agent_harness

    ui_events = [
        {"type": "user", "content": "u1"},
        {"type": "final", "content": "a1"},
        {"type": "user", "content": "u2"},
    ]
    llm_history = [
        {"type": "user", "content": "u1"},
        {
            "type": "assistant",
            "content": "",
            "tool_calls": [{"name": "search", "args": {}, "id": "call_1"}],
        },
        {"type": "tool", "content": "tool result", "tool_call_id": "call_1"},
        {"type": "assistant", "content": "a1", "metadata": {"is_final": True}},
        {"type": "user", "content": "u2"},
        {"type": "assistant", "content": "a2", "metadata": {"is_final": True}},
    ]
    saved_llm = []

    def fail_rebuild(*args, **kwargs):
        raise AssertionError("reconcile must not rebuild llm_history when user counts match")

    mgr = _manager_with(
        _load_ui_events=lambda sid: ui_events,
        _load_llm_history=lambda sid: llm_history,
        _load_work_messages=lambda sid: [],
        _save_llm_history=lambda sid, msgs: saved_llm.append(msgs),
        _save_work_messages=lambda sid, msgs: None,
        _rebuild_llm_work_from_ui=fail_rebuild,
        _observe_runtime_v2_history=lambda *args, **kwargs: None,
    )

    changed = agent_harness.SessionManager.reconcile_llm_work_to_ui_user_count(
        mgr,
        "s1",
        include_work=False,
    )

    assert changed is False
    assert saved_llm == []


def test_reconcile_trims_only_extra_tail_turn_and_preserves_tools():
    import agent_harness

    ui_events = [
        {"type": "user", "content": "u1"},
        {"type": "final", "content": "a1"},
        {"type": "user", "content": "u2"},
    ]
    llm_history = [
        {"type": "user", "content": "u1"},
        {
            "type": "assistant",
            "content": "",
            "tool_calls": [{"name": "search", "args": {}, "id": "call_1"}],
        },
        {"type": "tool", "content": "tool result", "tool_call_id": "call_1"},
        {"type": "assistant", "content": "a1", "metadata": {"is_final": True}},
        {"type": "user", "content": "u2"},
        {"type": "assistant", "content": "a2", "metadata": {"is_final": True}},
        {"type": "user", "content": "extra"},
        {"type": "system", "content": "New Agent Loop Start"},
    ]
    saved_llm = []
    observed = []

    mgr = _manager_with(
        _load_ui_events=lambda sid: ui_events,
        _load_llm_history=lambda sid: llm_history,
        _load_work_messages=lambda sid: [],
        _save_llm_history=lambda sid, msgs: saved_llm.append(msgs),
        _save_work_messages=lambda sid, msgs: None,
        _observe_runtime_v2_history=lambda *args, **kwargs: observed.append((args, kwargs)),
    )

    changed = agent_harness.SessionManager.reconcile_llm_work_to_ui_user_count(
        mgr,
        "s1",
        include_work=False,
    )

    assert changed is True
    assert len(saved_llm) == 1
    assert saved_llm[0] == llm_history[:6]
    assert any(m.get("type") == "tool" for m in saved_llm[0])
    assert observed == []


def test_legacy_rebuild_paths_do_not_replace_runtime_v2_model_history():
    source = (ROOT / "app" / "agent_harness.py").read_text(encoding="utf-8")
    forbidden_reasons = [
        "legacy_truncate",
        "legacy_branch",
        "legacy_repair",
        "legacy_reconcile",
        "legacy_tail_restored",
    ]
    for reason in forbidden_reasons:
        assert f'reason="{reason}"' not in source
