import json
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_valid_metadata_does_not_probe_every_possible_history_file(monkeypatch, tmp_path):
    from agent_harness import SessionManager

    def unexpected_probe(*_args):
        pytest.fail('normal indexed metadata must not scan history files to rule out an empty deletion remnant')

    manager = SessionManager.__new__(SessionManager)
    with monkeypatch.context() as scoped:
        scoped.setattr(manager, '_has_session_payload_files', unexpected_probe)
        assert manager._is_metadata_only_delete_remnant(tmp_path, {'name': 'valid'}) is False
        assert manager._is_metadata_only_delete_remnant(tmp_path, {'created_at': '2026-10-22'}) is False
    assert manager._is_metadata_only_delete_remnant(tmp_path, {}) is True
    (tmp_path/'events.jsonl').write_text('', encoding='utf8')
    assert manager._is_metadata_only_delete_remnant(tmp_path, {}) is False


def test_repair_reuses_unchanged_activity_scan_and_invalidates_on_log_changes(monkeypatch, tmp_path):
    import agent_harness
    monkeypatch.setattr(agent_harness.SessionManager, '_runtime_v2_primary', lambda _: True)
    sid = str(uuid.uuid4())
    directory = tmp_path/'sessions'/sid
    directory.mkdir(parents=True)
    (directory/'metadata.json').write_text(json.dumps({'name': 'valid', 'created_at': '2025-01-01T00:00:00Z'}), encoding='utf8')
    log = directory/'events.jsonl'
    log.write_text(json.dumps({'seq': 1, 'type': 'message_user', 'timestamp': '2026-01-01T00:00:00Z'})+'\n', encoding='utf8')
    manager = agent_harness.SessionManager(directory.parent, tmp_path/'sessions.json')
    original = agent_harness._session_log_activity_timestamp
    scans = []

    def scan(*args):
        scans.append(True)
        return original(*args)

    monkeypatch.setattr(agent_harness, '_session_log_activity_timestamp', scan)
    manager.refresh_sessions_index_from_disk()
    assert scans == [], 'an unchanged event log must not be decoded again on every refresh'
    log.write_text(json.dumps({'seq': 2, 'type': 'message_user', 'timestamp': '2027-01-01T00:00:00Z'})+'\n', encoding='utf8')
    manager.refresh_sessions_index_from_disk()
    assert scans == [True]
    assert manager.index[0]['updated_at'].startswith('2027-01-01')


def test_activity_scan_read_failure_is_not_cached(monkeypatch, tmp_path):
    import agent_harness
    monkeypatch.setattr(agent_harness.SessionManager, '_runtime_v2_primary', lambda _: True)
    directory = tmp_path/'sessions'/str(uuid.uuid4())
    directory.mkdir(parents=True)
    (directory/'metadata.json').write_text(json.dumps({'name': 'valid', 'created_at': '2025-01-01T00:00:00Z'}), encoding='utf8')
    (directory/'events.jsonl').write_text('{}\n', encoding='utf8')
    scans = []

    def failed_scan(_path, fallback):
        scans.append(True)
        return fallback

    monkeypatch.setattr(agent_harness, '_session_log_activity_timestamp', failed_scan)
    manager = agent_harness.SessionManager(directory.parent, tmp_path/'sessions.json')
    manager.refresh_sessions_index_from_disk()
    assert len(scans) == 2, 'a transient read failure must be rechecked on the next refresh'
    assert manager._index_activity_cache == {}


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
