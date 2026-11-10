"""Session favourites: persistence, listener notifications, and auto-archive opt-out."""

import json
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


FAVORITE_ID = "44444444-4444-4444-8444-444444444444"
NORMAL_ID = "55555555-5555-4555-8555-555555555555"


@contextmanager
def _manager_fixture():
    import agent_harness

    with tempfile.TemporaryDirectory(prefix="myagent-favorite-") as raw:
        root = Path(raw)
        rows = [
            {
                "id": FAVORITE_ID,
                "name": "old favourite candidate",
                "created_at": "2020-01-01T00:00:00Z",
                "updated_at": "2020-01-01T00:00:00Z",
            },
            {
                "id": NORMAL_ID,
                "name": "old normal session",
                "created_at": "2020-01-02T00:00:00Z",
                "updated_at": "2020-01-02T00:00:00Z",
            },
        ]
        sessions_dir = root / "sessions"
        sessions_dir.mkdir()
        for row in rows:
            session_dir = sessions_dir / row["id"]
            session_dir.mkdir()
            (session_dir / "metadata.json").write_text(json.dumps(row), encoding="utf-8")
        index_file = root / "sessions.json"
        index_file.write_text(json.dumps({"sessions": rows}), encoding="utf-8")
        yield agent_harness.SessionManager(sessions_dir, index_file), sessions_dir, index_file


def test_favorite_notifies_state_listeners_and_survives_reload():
    import agent_harness

    with _manager_fixture() as (manager, sessions_dir, index_file):
        changes = []
        manager.add_session_state_listener(
            lambda session_id, fields: changes.append((session_id, fields))
        )

        manager.set_session_favorite(FAVORITE_ID, True)

        assert changes == [(FAVORITE_ID, frozenset({"favorite"}))]
        summary = manager.get_session_summary(FAVORITE_ID)
        assert summary["favorite"] is True

        manager.refresh_sessions_index_from_disk()
        assert manager.get_session_summary(FAVORITE_ID)["favorite"] is True

        reloaded = agent_harness.SessionManager(sessions_dir, index_file)
        assert reloaded.get_session_summary(FAVORITE_ID)["favorite"] is True


def test_favorite_is_not_auto_archived():
    with _manager_fixture() as (manager, _sessions_dir, _index_file):
        manager.set_session_favorite(FAVORITE_ID, True)

        manager._auto_archive_stale_sessions()

        rows = {row["id"]: row for row in manager.list_sessions(include_archived=True)}
        assert rows[FAVORITE_ID]["favorite"] is True
        assert rows[FAVORITE_ID]["archived"] is False
        assert rows[NORMAL_ID]["archived"] is True


def test_favorite_toggle_keeps_activity_time():
    with _manager_fixture() as (manager, _sessions_dir, _index_file):
        before = manager.get_session_summary(FAVORITE_ID)["last_activity_at"]

        manager.set_session_favorite(FAVORITE_ID, True)

        after = manager.get_session_summary(FAVORITE_ID)["last_activity_at"]
        assert after == before


def test_favorite_endpoint_updates_sessions_state(monkeypatch):
    from starlette.testclient import TestClient
    import agent_harness
    import webui

    with tempfile.TemporaryDirectory(prefix="myagent-favorite-api-") as raw:
        root = Path(raw)
        sessions_dir = root / "sessions"
        sessions_dir.mkdir()
        manager = agent_harness.SessionManager(sessions_dir, root / "sessions.json")
        session_id, *_rest = manager.get_or_create_session()
        monkeypatch.setattr(webui, "session_manager", manager)
        monkeypatch.setattr(webui, "_is_configured", lambda: True)
        client = TestClient(webui.fastapi_app, client=("127.0.0.1", 50000))
        webui._invalidate_sessions_state_cache()

        response = client.put(f"/sessions/{session_id}/favorite", data={"favorite": "true"})

        assert response.status_code == 200
        rows = client.get("/sessions/state").json()["sessions"]
        assert next(row for row in rows if row["id"] == session_id)["favorite"] is True

        response = client.put(f"/sessions/{session_id}/favorite", data={"favorite": "false"})

        assert response.status_code == 200
        rows = client.get("/sessions/state").json()["sessions"]
        assert next(row for row in rows if row["id"] == session_id)["favorite"] is False
