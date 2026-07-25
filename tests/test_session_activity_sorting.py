import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


def test_runtime_v2_event_activity_moves_old_session_to_front(tmp_path):
    import agent_harness

    old_id = "11111111-1111-4111-8111-111111111111"
    new_id = "22222222-2222-4222-8222-222222222222"
    sessions_dir = tmp_path / "sessions"
    index_file = tmp_path / "sessions.json"
    sessions_dir.mkdir()

    rows = [
        {
            "id": new_id,
            "name": "newer",
            "created_at": "2026-07-10T00:00:00Z",
            "updated_at": "2026-07-10T00:00:00Z",
        },
        {
            "id": old_id,
            "name": "older",
            "created_at": "2026-07-09T00:00:00Z",
            "updated_at": "2026-07-09T00:00:00Z",
        },
    ]
    index_file.write_text(json.dumps({"sessions": rows}), encoding="utf-8")
    for sid in (old_id, new_id):
        (sessions_dir / sid).mkdir()

    event_path = sessions_dir / old_id / "events.jsonl"
    event_path.write_text('{"seq":1,"type":"message_user"}\n', encoding="utf-8")
    activity_ts = 1_800_000_000
    os.utime(event_path, (activity_ts, activity_ts))

    manager = agent_harness.SessionManager(sessions_dir, index_file)
    listed = manager.list_sessions()

    assert [row["id"] for row in listed] == [old_id, new_id]
    assert manager._iso_ts(listed[0]["last_activity_at"]) == activity_ts


def test_user_event_side_effect_persists_activity_for_refresh(tmp_path):
    import agent_harness

    old_id = "11111111-1111-4111-8111-111111111111"
    new_id = "22222222-2222-4222-8222-222222222222"
    sessions_dir = tmp_path / "sessions"
    index_file = tmp_path / "sessions.json"
    sessions_dir.mkdir()
    rows = [
        {"id": new_id, "name": "newer", "created_at": "2026-07-10T00:00:00Z", "updated_at": "2026-07-10T00:00:00Z"},
        {"id": old_id, "name": "older", "created_at": "2026-07-09T00:00:00Z", "updated_at": "2026-07-09T00:00:00Z"},
    ]
    index_file.write_text(json.dumps({"sessions": rows}), encoding="utf-8")
    for row in rows:
        session_dir = sessions_dir / row["id"]
        session_dir.mkdir()
        (session_dir / "metadata.json").write_text(json.dumps(row), encoding="utf-8")

    manager = agent_harness.SessionManager(sessions_dir, index_file)
    manager._apply_appended_ui_event_side_effects(old_id, {
        "type": "user",
        "content": "new question",
        "created_at": "2026-07-11T00:00:00Z",
    })

    reloaded = agent_harness.SessionManager(sessions_dir, index_file)
    # This fixture deliberately uses stable timestamps. Include archived rows so
    # the assertion remains about persisted activity ordering as wall time moves.
    rows_after_refresh = reloaded.list_sessions(include_archived=True)
    assert [row["id"] for row in rows_after_refresh] == [old_id, new_id]
    assert rows_after_refresh[0]["last_user_preview"] == "new question"
