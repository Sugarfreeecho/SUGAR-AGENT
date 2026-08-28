import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

SESSION_MANAGEMENT = ROOT / "frontend/src/app/modules/session-management.js"
TODO_GOAL = ROOT / "frontend/src/app/modules/toc-todo.js"
APP_CSS = ROOT / "frontend/src/styles/app.css"
I18N = ROOT / "frontend/src/app/modules/i18n.js"


def test_completed_goal_review_badge_is_rendered_and_refreshed():
    manifest = json.loads(
        (ROOT / "plugins/agent-goal/.myagent-plugin/plugin.json").read_text(encoding="utf-8")
    )
    assert manifest["capabilities"]["ui"]["session.badge"][0]["namespace"] == "goal"
    assert "goal_review_pending" not in SESSION_MANAGEMENT.read_text(encoding="utf-8")


def test_goal_completion_persists_pending_review_until_reviewed(tmp_path, monkeypatch):
    import agent_harness
    from agent_goal import manager_for

    monkeypatch.setenv("GOAL_ENABLED", "1")
    monkeypatch.setenv("RUNTIME_VERSION", "1")
    session_id = "22222222-2222-4222-8222-222222222222"
    sessions_dir = tmp_path / "sessions"
    session_dir = sessions_dir / session_id
    session_dir.mkdir(parents=True)
    metadata = {
        "id": session_id,
        "name": "goal review",
        "created_at": "2026-08-15T00:00:00Z",
        "updated_at": "2026-08-15T00:00:00Z",
    }
    (session_dir / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    index_file = tmp_path / "sessions.json"
    index_file.write_text(json.dumps({"sessions": [metadata]}), encoding="utf-8")
    session_manager = agent_harness.SessionManager(sessions_dir, index_file)
    goal_manager = manager_for(session_manager)

    goal_manager.create(session_id, "Finish and verify the task")
    goal_manager.update_status(session_id, "completed")
    assert session_manager.get_session_summary(session_id)["goal_review_pending"] is False

    completed = goal_manager.record_judge_result(
        session_id,
        "done",
        "All acceptance checks passed.",
        run_id="run-1:judge",
    )
    assert completed["status"] == "completed"
    assert completed["review_status"] == "pending"
    assert session_manager.get_session_summary(session_id)["goal_review_pending"] is True
    assert json.loads((session_dir / "metadata.json").read_text(encoding="utf-8"))[
        "goal_review_pending"
    ] is True

    goal_manager.review_completion(
        session_id,
        "approve",
        objective="Finish and verify the task",
        judge_result="Approved.",
    )
    assert session_manager.get_session_summary(session_id)["goal_review_pending"] is False
    assert json.loads((session_dir / "metadata.json").read_text(encoding="utf-8"))[
        "goal_review_pending"
    ] is False
