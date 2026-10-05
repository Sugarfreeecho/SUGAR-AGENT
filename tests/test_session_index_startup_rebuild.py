import json
import os
import sys
import time
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


def _append_jsonl(path: Path, rows) -> None:
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _event(seq: int, event_type: str, session_id: str, timestamp: str, payload=None) -> dict:
    return {
        "schema_version": 1,
        "seq": seq,
        "type": event_type,
        "session_id": session_id,
        "timestamp": timestamp,
        "payload": payload or {},
    }


def _panel_state_event(seq: int, session_id: str, timestamp: str) -> dict:
    return _event(
        seq,
        "extension_state_changed",
        session_id,
        timestamp,
        {"plugin_id": "execution-tools", "namespace": "panel", "revision": 1, "value": {"enabled": True}},
    )


def _plugin_inventory_event(seq: int, session_id: str, timestamp: str, event_type: str) -> dict:
    return _event(seq, event_type, session_id, timestamp, {"plugin_id": "change-review", "state": {"enabled": True}})


def test_control_event_append_does_not_refresh_session_activity(monkeypatch, tmp_path):
    """执行面板等控制事件不能被当成新的对话活动。

    回归：宿主每次启动都往每个会话的事件日志补写一次面板状态，日志 mtime 被当成活动
    时间后，侧栏所有会话被顶成「今天」并按启动顺序重排。
    """
    import agent_harness

    monkeypatch.setenv("REPAIR_SESSIONS_INDEX_ON_START", "0")
    session_id = str(uuid.uuid4())
    session_dir = tmp_path / session_id
    session_dir.mkdir()
    (session_dir / "metadata.json").write_text(
        json.dumps(
            {
                "id": session_id,
                "name": "老会话",
                "created_at": "2026-08-24T10:00:00Z",
                "updated_at": "2026-08-24T11:00:00Z",
            }
        ),
        encoding="utf-8",
    )
    log = session_dir / "events.jsonl"
    _append_jsonl(log, [_event(1, "run_finished", session_id, "2026-08-24T11:05:00.000Z")])
    _append_jsonl(log, [_panel_state_event(2, session_id, "2026-08-25T09:00:00.000Z")])
    _append_jsonl(log, [
        _plugin_inventory_event(3, session_id, "2026-08-25T10:00:00.000Z", "plugin_state_changed"),
        _plugin_inventory_event(4, session_id, "2026-08-25T11:00:00.000Z", "plugin_reloaded"),
    ])
    now = time.time()
    os.utime(log, (now, now))

    manager = agent_harness.SessionManager(tmp_path, tmp_path / "sessions.json")
    assert manager.get_session_summary(session_id)["updated_at"] == "2026-08-24T11:05:00Z"

    # 真正的对话活动仍然照常前移活动时间。
    _append_jsonl(log, [_event(5, "run_finished", session_id, "2026-08-27T08:00:00.000Z")])
    rebuilt = agent_harness.SessionManager(tmp_path, tmp_path / "sessions.json")
    assert rebuilt.get_session_summary(session_id)["updated_at"] == "2026-08-27T08:00:00Z"


def test_control_only_log_keeps_metadata_activity(monkeypatch, tmp_path):
    """只有控制类事件的日志不产生活动时间，保留 metadata 里已有的值。"""
    import agent_harness

    monkeypatch.setenv("REPAIR_SESSIONS_INDEX_ON_START", "0")
    session_id = str(uuid.uuid4())
    session_dir = tmp_path / session_id
    session_dir.mkdir()
    (session_dir / "metadata.json").write_text(
        json.dumps(
            {
                "id": session_id,
                "name": "只有控制事件",
                "created_at": "2026-08-24T10:00:00Z",
                "updated_at": "2026-08-24T11:00:00Z",
            }
        ),
        encoding="utf-8",
    )
    log = session_dir / "events.jsonl"
    _append_jsonl(log, [_panel_state_event(1, session_id, "2026-08-25T09:00:00.000Z")])
    now = time.time()
    os.utime(log, (now, now))

    manager = agent_harness.SessionManager(tmp_path, tmp_path / "sessions.json")
    row = manager.get_session_summary(session_id)
    assert row["updated_at"] == "2026-08-24T11:00:00Z"
    assert row["last_activity_at"] == "2026-08-24T11:00:00Z"
