import json
import sys
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


def test_session_manager_rebuilds_existing_index_from_disk_on_start(monkeypatch, tmp_path):
    import agent_harness

    monkeypatch.setenv("REPAIR_SESSIONS_INDEX_ON_START", "0")
    stale_id = str(uuid.uuid4())
    disk_id = str(uuid.uuid4())
    index_file = tmp_path / "sessions.json"
    index_file.write_text(
        json.dumps({"sessions": [{"id": stale_id, "name": "stale index entry"}]}),
        encoding="utf-8",
    )
    session_dir = tmp_path / disk_id
    session_dir.mkdir()
    (session_dir / "metadata.json").write_text(
        json.dumps(
            {
                "id": disk_id,
                "name": "disk session",
                "created_at": "2026-08-24T10:00:00",
                "updated_at": "2026-08-24T11:00:00",
            }
        ),
        encoding="utf-8",
    )

    manager = agent_harness.SessionManager(tmp_path, index_file)

    assert [row["id"] for row in manager.index] == [disk_id]
    persisted = json.loads(index_file.read_text(encoding="utf-8"))
    assert [row["id"] for row in persisted["sessions"]] == [disk_id]
