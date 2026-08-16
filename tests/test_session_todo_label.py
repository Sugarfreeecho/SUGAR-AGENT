import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

SESSION_MANAGEMENT = ROOT / "frontend/src/app/modules/session-management.js"
APP_CSS = ROOT / "frontend/src/styles/app.css"
I18N = ROOT / "frontend/src/app/modules/i18n.js"
WEBUI = ROOT / "app/webui.py"


def test_session_todo_menu_badge_and_endpoint_are_wired():
    sessions = SESSION_MANAGEMENT.read_text(encoding="utf-8")
    css = APP_CSS.read_text(encoding="utf-8")
    i18n = I18N.read_text(encoding="utf-8")
    webui = WEBUI.read_text(encoding="utf-8")

    assert 'class="session-menu-todo"' in sessions
    assert "async function toggleSessionTodoFromMenu(sess)" in sessions
    assert "formData.append('todo', nextTodo ? 'true' : 'false')" in sessions
    assert "encodeURIComponent(sess.id) + '/todo'" in sessions
    assert 'class="session-todo-badge"' in sessions
    assert "s.todo ? 't' : ''" in sessions
    assert ".session-todo-badge" in css
    assert ".session-todo-badge[hidden] { display: none; }" in css
    assert "'设为待办': 'Mark as todo'" in i18n
    assert '@fastapi_app.put("/sessions/{session_id}/todo")' in webui
    assert "session_manager.set_session_todo(session_id, todo)" in webui


def test_session_todo_state_persists_in_metadata_and_index(tmp_path):
    import agent_harness

    session_id = "11111111-1111-4111-8111-111111111111"
    sessions_dir = tmp_path / "sessions"
    session_dir = sessions_dir / session_id
    session_dir.mkdir(parents=True)
    metadata = {
        "id": session_id,
        "name": "todo candidate",
        "created_at": "2026-08-15T00:00:00Z",
        "updated_at": "2026-08-15T00:00:00Z",
        "archived": False,
        "pinned": False,
    }
    (session_dir / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    index_file = tmp_path / "sessions.json"
    index_file.write_text(json.dumps({"sessions": [metadata]}), encoding="utf-8")

    manager = agent_harness.SessionManager(sessions_dir, index_file)
    assert manager.get_session_summary(session_id)["todo"] is False

    manager.set_session_todo(session_id, True)
    assert manager.get_session_summary(session_id)["todo"] is True
    assert json.loads((session_dir / "metadata.json").read_text(encoding="utf-8"))["todo"] is True

    reloaded = agent_harness.SessionManager(sessions_dir, index_file)
    assert reloaded.get_session_summary(session_id)["todo"] is True

    reloaded.set_session_todo(session_id, False)
    assert reloaded.get_session_summary(session_id)["todo"] is False
    assert json.loads((session_dir / "metadata.json").read_text(encoding="utf-8"))["todo"] is False
