import json
import sys
import uuid
from pathlib import Path

import pytest


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


@pytest.mark.parametrize("runtime_v2_primary", [False, True])
def test_new_root_session_does_not_scan_nested_subagents(monkeypatch, tmp_path, runtime_v2_primary):
    import agent_harness

    manager = agent_harness.SessionManager(tmp_path, tmp_path / "sessions.json")
    monkeypatch.setattr(manager, "_runtime_v2_primary", lambda: runtime_v2_primary)

    def fail_scan(_session_id):
        raise AssertionError("new root session must not scan the sessions tree")

    monkeypatch.setattr(manager, "_scan_nested_subagent_path", fail_scan)
    session_id, _, _, _, _, metadata = manager.get_or_create_session()

    assert (tmp_path / session_id / "metadata.json").is_file()
    assert metadata["name"] == "新会话"
    if runtime_v2_primary:
        from runtime_v2.snapshot_store import SnapshotStore

        assert SnapshotStore(tmp_path, path_resolver=manager._resolve_session_path).wait_for_checkpoint(
            session_id, timeout_seconds=5
        )


@pytest.mark.parametrize("runtime_v2_primary", [False, True])
def test_prefetched_session_stays_hidden_until_first_user_turn(monkeypatch, tmp_path, runtime_v2_primary):
    import agent_harness

    manager = agent_harness.SessionManager(tmp_path, tmp_path / "sessions.json")
    monkeypatch.setattr(manager, "_runtime_v2_primary", lambda: runtime_v2_primary)
    notifications = []
    manager.add_session_state_listener(lambda sid, fields: notifications.append((sid, fields)))
    session_id, _, _, _, _, metadata = manager.get_or_create_session(draft=True)

    assert metadata["draft"] is True
    assert notifications == []
    assert manager.get_session_summary(session_id)["draft"] is True
    assert session_id not in {row["id"] for row in manager.list_sessions(include_archived=True)}

    manager._apply_appended_ui_event_side_effects(
        session_id, {"type": "user", "content": "first question"}
    )

    assert manager.get_session_summary(session_id).get("draft", False) is False
    assert notifications == [(session_id, frozenset({"draft"}))]
    assert session_id in {row["id"] for row in manager.list_sessions()}
    assert "draft" not in json.loads((tmp_path / session_id / "metadata.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("runtime_v2_primary", [False, True])
def test_rebuild_promotes_draft_with_committed_user_turn(monkeypatch, tmp_path, runtime_v2_primary):
    import agent_harness

    manager = agent_harness.SessionManager(tmp_path, tmp_path / "sessions.json")
    monkeypatch.setattr(manager, "_runtime_v2_primary", lambda: runtime_v2_primary)
    session_id, _, _, _, _, _ = manager.get_or_create_session(draft=True)

    # Simulate a process ending after the user fact was persisted but before
    # the separate metadata/index side effect removed the draft marker.
    if runtime_v2_primary:
        from runtime_v2.history_ops import RuntimeHistoryOps

        RuntimeHistoryOps(tmp_path, path_resolver=manager._resolve_session_path).commit_user_turn(
            session_id, "first question", ui_content="first question"
        )
    else:
        (tmp_path / session_id / "ui_events.json").write_text(
            json.dumps([{"type": "user", "content": "first question"}]), encoding="utf-8"
        )

    rebuilt = agent_harness.SessionManager(tmp_path, tmp_path / "sessions.json")

    assert session_id in {row["id"] for row in rebuilt.list_sessions()}
    assert rebuilt.get_session_summary(session_id)["last_user_preview"] == "first question"
    assert "draft" not in json.loads((tmp_path / session_id / "metadata.json").read_text(encoding="utf-8"))
