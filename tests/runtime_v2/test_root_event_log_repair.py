import json
from pathlib import Path

from app.runtime_v2 import (
    RuntimeModelProjection,
    RuntimeUiProjection,
    RuntimeV2RootEventLogRepairService,
)
from app.runtime_v2.snapshot_store import SnapshotStore
from scripts.repair_runtime_v2_root_event_logs import _root_session_ids


def _write_rows(root: Path, session_id: str, rows: list[dict | str]) -> Path:
    path = root / session_id / "events.jsonl"
    path.parent.mkdir(parents=True)
    encoded = []
    for row in rows:
        encoded.append(row if isinstance(row, str) else json.dumps(row, ensure_ascii=False))
    path.write_text("\n".join(encoded) + "\n", encoding="utf-8")
    return path


def _event(seq: int, event_type: str, session_id: str, payload: dict) -> dict:
    return {
        "seq": seq,
        "timestamp": f"2026-01-01T00:00:{seq:02d}.000Z",
        "type": event_type,
        "session_id": session_id,
        "run_id": None,
        "payload": payload,
    }


def test_root_log_cli_discovery_ignores_backup_like_directories(tmp_path):
    sid = "ae17918b-9f38-4d39-afa6-107f224b5cdb"
    _write_rows(tmp_path, sid, [_event(1, "message_user", sid, {"content": "live"})])
    _write_rows(
        tmp_path,
        sid + " 压缩备份",
        [_event(1, "message_user", sid, {"content": "backup"})],
    )

    assert _root_session_ids(tmp_path) == [sid]


def test_root_log_repair_dry_run_is_read_only_and_reports_stable_resequence(tmp_path):
    sid = "root-session"
    path = _write_rows(tmp_path, sid, [
        _event(1, "message_user", sid, {"content": "hello"}),
        "torn-json-tail}}",
        _event(1, "model_user", sid, {"role": "user", "content": "hello"}),
        _event(2, "message_assistant_final", sid, {"content": "answer"}),
    ])
    before = path.read_bytes()
    service = RuntimeV2RootEventLogRepairService(tmp_path)

    result = service.repair(sid, apply=False)

    assert result["action"] == "dry_run"
    assert result["applied"] is False
    assert result["malformed_lines"] == 1
    assert result["duplicate_sequences"] == 1
    assert result["non_monotonic_sequences"] == 1
    assert result["valid_events"] == 3
    assert result["resequence_required"] is True
    assert result["semantic_projection_verified"] is True
    assert path.read_bytes() == before
    assert not (tmp_path / sid / ".events.lock").exists()
    assert not (tmp_path / sid / ".runtime_v2_repair_backups").exists()


def test_root_log_repair_backs_up_resequences_rebuilds_and_is_idempotent(tmp_path):
    sid = "root-session"
    path = _write_rows(tmp_path, sid, [
        _event(1, "message_user", sid, {"content": "hello"}),
        "torn-json-tail}}",
        _event(1, "model_user", sid, {"role": "user", "content": "hello"}),
        _event(2, "message_assistant_final", sid, {"content": "answer"}),
    ])
    source = path.read_bytes()
    stale_index = tmp_path / sid / "snapshots" / "ui_projection_index.json"
    stale_index.parent.mkdir(parents=True)
    stale_index.write_text('{"stale":true}', encoding="utf-8")
    service = RuntimeV2RootEventLogRepairService(tmp_path)

    result = service.repair(sid, apply=True)

    assert result["action"] == "repaired"
    assert result["applied"] is True
    assert result["verified"] is True
    assert [row["seq"] for row in (
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
    )] == [1, 2, 3]
    assert [row["type"] for row in (
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
    )] == ["message_user", "model_user", "message_assistant_final"]
    manifest_path = Path(result["manifest_path"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "complete"
    assert manifest["source_sha256"] == result["source_sha256"]
    assert manifest["repaired_sha256"] == result["repaired_sha256"]
    assert (manifest_path.parent / "events.jsonl").read_bytes() == source
    assert not stale_index.exists()
    assert SnapshotStore(tmp_path).read(sid)["last_seq"] == 3
    assert [event["content"] for event in RuntimeUiProjection(tmp_path).read_ui_events(sid)] == [
        "hello",
        "answer",
    ]
    assert [message["content"] for message in RuntimeModelProjection(tmp_path).read_message_dicts(sid)] == [
        "hello",
    ]

    repaired = path.read_bytes()
    second = service.repair(sid, apply=True)
    assert second["action"] == "clean"
    assert second["applied"] is False
    assert path.read_bytes() == repaired


def test_root_log_repair_refuses_ambiguous_local_sequence_reference(tmp_path):
    sid = "root-session"
    path = _write_rows(tmp_path, sid, [
        _event(1, "message_user", sid, {"content": "hello"}),
        _event(1, "model_user", sid, {"role": "user", "content": "hello"}),
        _event(2, "message_deleted", sid, {"target_seq": 1}),
    ])
    before = path.read_bytes()

    result = RuntimeV2RootEventLogRepairService(tmp_path).repair(sid, apply=True)

    assert result["action"] == "refused"
    assert result["applied"] is False
    assert any("ambiguous" in conflict for conflict in result["conflicts"])
    assert path.read_bytes() == before
    assert not (tmp_path / sid / ".runtime_v2_repair_backups").exists()


def test_root_log_repair_translates_only_known_nested_checkpoint_references(tmp_path):
    sid = "root-session"
    path = _write_rows(tmp_path, sid, [
        _event(1, "message_user", sid, {"content": "hello"}),
        _event(1, "model_user", sid, {
            "role": "user",
            "content": "hello",
            "tool_calls": [{"args": {"seq": 2, "source_seq": 2}}],
        }),
        _event(2, "context_tokens", sid, {"estimated": 10}),
        _event(3, "visible_range_changed", sid, {
            "restore_history_compaction": {
                "summary": "summary",
                "compacted_before_seq": 2,
                "changed_at_seq": 2,
            },
        }),
    ])

    result = RuntimeV2RootEventLogRepairService(tmp_path).repair(sid, apply=True)

    assert result["action"] == "repaired"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    checkpoint = rows[-1]["payload"]["restore_history_compaction"]
    assert checkpoint["compacted_before_seq"] == 3
    assert checkpoint["changed_at_seq"] == 3
    assert rows[1]["payload"]["tool_calls"][0]["args"] == {"seq": 2, "source_seq": 2}


def test_root_log_repair_refuses_external_branch_reference_that_would_become_stale(tmp_path):
    sid = "root-session"
    _write_rows(tmp_path, sid, [
        _event(1, "message_user", sid, {"content": "hello"}),
        _event(1, "model_user", sid, {"role": "user", "content": "hello"}),
        _event(2, "message_assistant_final", sid, {"content": "answer"}),
    ])
    branch_id = "branch-session"
    _write_rows(tmp_path, branch_id, [
        _event(1, "history_branch_created", branch_id, {
            "source_session_id": sid,
            "branch_from_seq": 2,
        }),
    ])

    result = RuntimeV2RootEventLogRepairService(tmp_path).repair(sid, apply=False)

    assert result["action"] == "refused"
    assert any("would become stale" in conflict for conflict in result["conflicts"])


def test_root_log_repair_rolls_back_event_snapshot_and_index_on_verify_failure(tmp_path, monkeypatch):
    sid = "root-session"
    path = _write_rows(tmp_path, sid, [
        _event(1, "message_user", sid, {"content": "hello"}),
        _event(1, "model_user", sid, {"role": "user", "content": "hello"}),
    ])
    snapshot_path = tmp_path / sid / "snapshots" / "latest.json"
    snapshot_path.parent.mkdir(parents=True)
    snapshot_path.write_text('{"old_snapshot":true}', encoding="utf-8")
    index_path = tmp_path / sid / "snapshots" / "ui_projection_index.json"
    index_path.write_text('{"old_index":true}', encoding="utf-8")
    before_events = path.read_bytes()
    before_snapshot = snapshot_path.read_bytes()
    before_index = index_path.read_bytes()
    service = RuntimeV2RootEventLogRepairService(tmp_path)

    def fail_verify(*_args, **_kwargs):
        raise RuntimeError("injected verification failure")

    monkeypatch.setattr(service, "_verify_repaired_state", fail_verify)
    result = service.repair(sid, apply=True)

    assert result["action"] == "rolled_back"
    assert result["applied"] is False
    assert "injected verification failure" in result["error"]
    assert path.read_bytes() == before_events
    assert snapshot_path.read_bytes() == before_snapshot
    assert index_path.read_bytes() == before_index
    manifest = json.loads(Path(result["manifest_path"]).read_text(encoding="utf-8"))
    assert manifest["status"] == "rolled_back"
