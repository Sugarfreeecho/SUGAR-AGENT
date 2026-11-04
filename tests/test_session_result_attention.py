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


def _start_runs(store, sid, *run_ids):
    for run_id in run_ids:
        store.clear_interrupt(sid, run_id)


def test_delayed_failure_for_an_older_run_cannot_overwrite_a_newer_success(manager):
    from agent_harness import SessionManager

    store, sid = manager
    _start_runs(store, sid, "run-old", "run-new")
    store.mark_session_unread_result(sid, status="failed", run_id="run-old")
    store.mark_session_unread_result(sid, status="success", run_id="run-new")
    assert store.get_session_summary(sid)["unread_result_status"] == "success"

    # The old run's terminal handler runs after the retry already succeeded.
    store.mark_session_unread_result(sid, status="failed", run_id="run-old")
    summary = store.get_session_summary(sid)
    assert summary["unread_result_status"] == "success"
    assert summary["unread_result_run_id"] == "run-new"
    assert store.clear_session_unread_result(sid, expected_run_id="run-new") is True

    restarted = SessionManager(store.sessions_dir, store.index_file)
    reloaded = restarted.get_session_summary(sid)
    assert reloaded["unread_result"] is False
    assert reloaded["unread_result_status"] == "success"


def test_delayed_success_for_an_older_run_cannot_clear_a_newer_failure(manager):
    store, sid = manager
    _start_runs(store, sid, "run-old", "run-new")
    store.mark_session_unread_result(sid, status="failed", run_id="run-new")
    store.mark_session_unread_result(sid, status="success", run_id="run-old")
    summary = store.get_session_summary(sid)
    assert summary["unread_result_status"] == "failed"
    assert summary["unread_result_run_id"] == "run-new"
    assert store.clear_session_unread_result(sid, expected_run_id="run-new") is False


def test_failure_of_a_newer_run_is_still_red(manager):
    store, sid = manager
    _start_runs(store, sid, "run-old", "run-newer")
    store.mark_session_unread_result(sid, status="success", run_id="run-old")
    store.mark_session_unread_result(sid, status="failed", run_id="run-newer")
    summary = store.get_session_summary(sid)
    assert summary["unread_result_status"] == "failed"
    assert summary["unread_result_run_id"] == "run-newer"


def test_a_delayed_old_failure_cannot_return_after_the_result_was_read(manager):
    from agent_harness import SessionManager

    store, sid = manager
    _start_runs(store, sid, "run-old", "run-new", "run-newer")
    store.mark_session_unread_result(sid, status="failed", run_id="run-old")
    store.mark_session_unread_result(sid, status="success", run_id="run-new")
    assert store.clear_session_unread_result(sid, expected_run_id="run-new") is True
    assert store.get_session_summary(sid)["unread_result"] is False

    store.mark_session_unread_result(sid, status="failed", run_id="run-old")
    summary = store.get_session_summary(sid)
    assert summary["unread_result"] is False
    assert summary["unread_result_status"] == "success"
    restarted = SessionManager(store.sessions_dir, store.index_file)
    assert restarted.get_session_summary(sid)["unread_result"] is False

    store.mark_session_unread_result(sid, status="failed", run_id="run-newer")
    assert store.get_session_summary(sid)["unread_result_status"] == "failed"


def test_runs_without_a_recorded_start_order_fail_open(manager):
    store, sid = manager
    # Runs that never registered a start order cannot be compared, so the
    # write is accepted instead of being guessed away.
    store.mark_session_unread_result(sid, status="success", run_id="unregistered-new")
    store.mark_session_unread_result(sid, status="failed", run_id="unregistered-old")
    assert store.get_session_summary(sid)["unread_result_status"] == "failed"


def test_result_generation_survives_history_trimming_reads_and_restart(manager):
    from agent_harness import SessionManager

    store, sid = manager
    _start_runs(store, sid, "first", "second")
    store.mark_session_unread_result(sid, status="success", run_id="second")
    assert store.get_session_summary(sid)["unread_result_run_order"] == 2
    assert store.get_run_start_order(sid, "second") == 2
    # Sliding a bounded history must never renumber a run already sent to clients.
    _start_runs(store, sid, *(f"next-{i}" for i in range(63)))
    assert store.get_run_start_order(sid, "second") == 2
    assert store.get_run_start_order(sid, "next-62") == 65
    assert store.clear_session_unread_result(sid, expected_run_id="second")
    restarted = SessionManager(store.sessions_dir, store.index_file)
    read = restarted.get_session_summary(sid)
    assert read["unread_result"] is False
    assert read["unread_result_run_order"] == 2
    assert read["unread_result_last_run_id"] == "second"
    restarted.mark_session_unread_result(sid, status="failed", run_id="next-62")
    assert restarted.get_session_summary(sid)["unread_result_run_order"] == 65
    restarted.mark_session_unread_result(sid, status="success", run_id="second")
    assert restarted.get_session_summary(sid)["unread_result_status"] == "failed"
    restarted.refresh_sessions_index_from_disk()
    assert restarted.get_session_summary(sid)["unread_result_run_order"] == 65


def test_terminal_signal_and_http_summaries_share_the_same_generation(manager, monkeypatch):
    import webui
    from session_state_signal import SessionStateSignal
    from starlette.testclient import TestClient

    store, sid = manager
    _start_runs(store, sid, "old", "new")
    store.mark_session_unread_result(sid, status="success", run_id="new")
    monkeypatch.setattr(webui, "session_manager", store)
    monkeypatch.setattr(webui, "_is_configured", lambda: True)
    signal = SessionStateSignal(webui._sessions_state_cache_generation)
    monkeypatch.setattr(webui, "_sessions_state_signal", signal)
    base = signal.revision
    event = {"type": "run_finished", "run_id": "new", "result_status": "success"}
    webui._on_session_lifecycle_event_invalidate_state(sid, event)
    assert event["result_run_order"] == 2
    assert signal.changes_since(base)["terminal_events"][0]["result_run_order"] == 2
    client = TestClient(webui.fastapi_app)
    for url in ("/sessions", "/sessions/state", f"/sessions/{sid}"):
        payload = client.get(url).json()
        rows = payload if isinstance(payload, list) else payload.get("sessions", [payload])
        row = next(row for row in rows if row.get("id") == sid)
        assert row["unread_result_run_order"] == event["result_run_order"]
    assert store.clear_session_unread_result(sid, expected_run_id="new")
    assert client.get(f"/sessions/{sid}").json()["unread_result_last_run_id"] == "new"
