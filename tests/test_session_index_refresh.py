import json
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_refresh_button_waits_for_index_rebuild():
    result = subprocess.run(
        ["node", "--test", str(ROOT / "tests/js/session_refresh_runtime.cjs")],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("index_state", ["stale", "missing", "corrupt"])
def test_refresh_repairs_index_file_and_invalidates_warm_sidebar_cache(monkeypatch, tmp_path, index_state):
    import agent_harness
    import webui
    from starlette.testclient import TestClient

    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    index_file = tmp_path / "sessions.json"
    manager = agent_harness.SessionManager(sessions_dir, index_file)
    ghost_id, disk_id = str(uuid.uuid4()), str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    manager.index = [{"id": ghost_id, "name": "stale entry", "created_at": now, "updated_at": now}]
    manager._save_index()
    monkeypatch.setattr(webui, "session_manager", manager)
    monkeypatch.setattr(webui, "_is_configured", lambda: True)
    client = TestClient(webui.fastapi_app)
    webui._invalidate_sessions_state_cache()
    before = client.get("/sessions/state").json()
    assert [row["id"] for row in before["sessions"]] == [ghost_id]
    # A directory copied after startup is absent from both the index and cache.
    session = sessions_dir / disk_id
    session.mkdir()
    metadata = json.dumps({"name": "copied session", "created_at": now, "updated_at": now})
    (session / "metadata.json").write_text(metadata, encoding="utf-8")
    (session / "events.jsonl").write_text("", encoding="utf-8")
    if index_state == "missing":
        index_file.unlink()
    elif index_state == "corrupt":
        index_file.write_text("{broken", encoding="utf-8")

    response = client.post("/sessions/index/repair")
    assert response.status_code == 200
    result = response.json()
    assert result["ok"] is True
    assert result["session_count"] == 1
    assert result["state_revision"] > before["state_revision"]
    assert [row["id"] for row in manager.index] == [disk_id]
    persisted = json.loads(index_file.read_text(encoding="utf-8"))
    assert [row["id"] for row in persisted["sessions"]] == [disk_id]
    after = client.get("/sessions/state").json()
    assert [row["id"] for row in after["sessions"]] == [disk_id]
    assert after["state_revision"] >= result["state_revision"]
    assert (session / "metadata.json").read_text(encoding="utf-8") == metadata
    assert (session / "events.jsonl").read_bytes() == b""


def test_index_repair_error_is_reported_as_json(monkeypatch):
    import webui
    from starlette.testclient import TestClient

    def fail():
        raise PermissionError("Index is read-only")

    monkeypatch.setattr(webui.session_manager, "refresh_sessions_index_from_disk", fail)
    monkeypatch.setattr(webui, "_is_configured", lambda: True)
    response = TestClient(webui.fastapi_app).post("/sessions/index/repair")
    assert response.status_code == 500
    assert response.json()["ok"] is False
    assert "重建会话索引失败" in response.json()["error"]
