import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))


@pytest.fixture
def manager(tmp_path):
    from agent_harness import SessionManager

    session_id = "19191919-1919-4191-8191-191919191919"
    sessions_dir = tmp_path / "sessions"
    session_dir = sessions_dir / session_id
    session_dir.mkdir(parents=True)
    metadata = {"id": session_id, "name": "attention"}
    (session_dir / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    index_file = tmp_path / "sessions.json"
    index_file.write_text(json.dumps({"sessions": [metadata]}), encoding="utf-8")
    return SessionManager(sessions_dir, index_file), session_id


def test_read_and_retry_preserve_failure_until_a_new_success(manager):
    from agent_harness import SessionManager

    store, sid = manager
    store.mark_session_unread_result(sid, status="failed", run_id="failed-run")
    assert store.clear_session_unread_result(sid, expected_run_id="failed-run") is False
    store._apply_appended_ui_event_side_effects(sid, {"type": "user", "content": "Retry"})
    restarted = SessionManager(store.sessions_dir, store.index_file)
    assert restarted.get_session_summary(sid)["unread_result_status"] == "failed"
    restarted.mark_session_unread_result(sid, status="success", run_id="failed-run")
    assert restarted.get_session_summary(sid)["unread_result_status"] == "failed"
    restarted.mark_session_unread_result(sid, status="success", run_id="retry-run")
    assert restarted.get_session_summary(sid)["unread_result_status"] == "success"
    assert restarted.clear_session_unread_result(sid, expected_run_id="failed-run") is False
    assert restarted.clear_session_unread_result(sid, expected_run_id="retry-run") is True
    assert restarted.get_session_summary(sid)["unread_result"] is False


def test_legacy_failure_without_run_id_can_be_resolved(manager):
    store, sid = manager
    store.mark_session_unread_result(sid, status="failed")
    store.mark_session_unread_result(sid, status="success", run_id="retry-run")
    assert store.get_session_summary(sid)["unread_result_status"] == "success"


def test_reopening_an_already_read_session_does_not_write_or_invalidate(manager, monkeypatch):
    store, sid = manager
    store.mark_session_unread_result(sid, status="success", run_id="done")
    changes = []
    store.add_session_state_listener(lambda changed_sid, fields: changes.append((changed_sid, fields)))
    assert store.clear_session_unread_result(sid, expected_run_id="done") is True
    assert changes == [(sid, frozenset({"unread_result"}))]
    changes.clear()

    def unexpected_write(*_args, **_kwargs):
        pytest.fail("reading an unchanged conversation must not rewrite metadata or the entire index")

    monkeypatch.setattr(store, "_save_metadata_unlocked", unexpected_write)
    monkeypatch.setattr(store, "_save_index", unexpected_write)
    for _ in range(3):
        assert store.clear_session_unread_result(sid) is True
    assert changes == []


@pytest.mark.parametrize("accounting", ["record_usage", "record_run"])
def test_budget_exhaustion_stays_failed_after_a_successful_round(manager, monkeypatch, accounting):
    import agent_goal
    import agent_loop

    store, sid = manager
    monkeypatch.setenv("GOAL_ENABLED", "1")
    monkeypatch.setenv("RUNTIME_VERSION", "2")
    monkeypatch.setattr(agent_loop, "session_manager", store)
    goals = agent_goal.manager_for(store)
    goals.create(sid, "Finish the task", token_budget=10)
    kwargs = {"usage_id": "call-1"} if accounting == "record_usage" else {}
    goal = getattr(goals, accounting)(sid, 10, run_id="run-1", **kwargs)
    assert goal["status"] == "paused"
    assert goal["pause_reason"] == "token_budget_exhausted"
    agent_loop._mark_run_terminal_unread(sid, "run_finished", "run-1")
    assert store.get_session_summary(sid)["unread_result_status"] == "failed"
    assert store.clear_session_unread_result(sid) is False
    goals.user_action(sid, "resume", additional_budget=100)
    agent_loop._mark_run_terminal_unread(sid, "run_finished", "run-2")
    assert store.get_session_summary(sid)["unread_result_status"] == "failed"
    goals.update_status(sid, "completed")
    goals.record_judge_result(sid, "done", "Verified", run_id="run-3:judge")
    agent_loop._mark_run_terminal_unread(sid, "run_finished", "run-3")
    assert store.get_session_summary(sid)["unread_result_status"] == "success"


@pytest.mark.parametrize("preview", ["失败问题已修复", "异常处理已验证", "Error: examples documented", "interrupt handling verified"])
def test_subagent_success_does_not_depend_on_response_keywords(manager, monkeypatch, preview):
    store, sid = manager
    monkeypatch.setattr(store, "_subagent_finish_from_parent_events", lambda *_: {"ok": True})
    monkeypatch.setattr(store, "_load_ui_events_for_active_runtime", lambda *_: [{"type": "final", "content": preview}])
    result = store._resolve_subagent_status(sid, "parent", {}, running=False, result_preview=preview)
    assert result == {"status": "completed", "ok": True, "error": ""}
    monkeypatch.setattr(store, "_subagent_finish_from_parent_events", lambda *_: {"ok": False, "error": "provider rejected"})
    result = store._resolve_subagent_status(sid, "parent", {}, running=False, result_preview="All done")
    assert result["status"] == "failed"
