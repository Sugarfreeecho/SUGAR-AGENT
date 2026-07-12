import json
from pathlib import Path

from app.runtime_v2 import RuntimeHistoryOps, RuntimeMirror, RuntimeModelProjection
from app.runtime_v2.migration import RuntimeV2MigrationService
from app.runtime_v2.ui_projection import RuntimeUiProjection


def test_migration_service_does_not_export_legacy_by_default(monkeypatch, tmp_path):
    monkeypatch.setenv("RUNTIME_VERSION", "2")
    mirror = RuntimeMirror(tmp_path)
    mirror.mirror_ui_event("s1", {"type": "user", "content": "visible"})
    RuntimeHistoryOps(tmp_path).replace_model_history(
        "s1",
        [
            {"type": "user", "content": "hello"},
            {"type": "assistant", "content": "answer"},
        ],
        reason="test",
    )
    saved_ui = []
    saved_model = []

    result = RuntimeV2MigrationService(tmp_path).sync_session(
        "s1",
        load_legacy_ui_events=lambda: [],
        save_legacy_ui_events=lambda events: saved_ui.append(events),
        load_legacy_model_messages=lambda: [{"type": "user", "content": "legacy"}],
        save_legacy_model_messages=lambda messages: saved_model.append(messages),
    )

    assert result["v1_from_v2"]["action"] == "skipped"
    assert result["model_v2_from_v1"]["action"] == "mismatch"
    assert result["model_v2_to_v1"]["action"] == "skipped"
    assert saved_ui == []
    assert saved_model == []


def test_migration_service_exports_v2_ui_and_model_projection_to_legacy_when_explicit(monkeypatch, tmp_path):
    monkeypatch.setenv("RUNTIME_VERSION", "2")
    mirror = RuntimeMirror(tmp_path)
    mirror.mirror_ui_event("s1", {"type": "user", "content": "visible"})
    RuntimeHistoryOps(tmp_path).replace_model_history(
        "s1",
        [
            {"type": "user", "content": "hello"},
            {"type": "assistant", "content": "answer"},
        ],
        reason="test",
    )
    saved_ui = []
    saved_model = []

    result = RuntimeV2MigrationService(tmp_path).sync_session(
        "s1",
        load_legacy_ui_events=lambda: [],
        save_legacy_ui_events=lambda events: saved_ui.append(events),
        load_legacy_model_messages=lambda: [{"type": "user", "content": "legacy"}],
        save_legacy_model_messages=lambda messages: saved_model.append(messages),
        export_legacy=True,
    )

    assert result["v2_from_v1"]["action"] == "none"
    assert result["model_v2_from_v1"]["action"] == "mismatch"
    assert result["v1_from_v2"]["action"] == "replace"
    assert result["v1_from_v2"]["written"] == 1
    assert len(saved_ui) == 1
    assert saved_ui[0][0]["type"] == "user"
    assert saved_ui[0][0]["content"] == "visible"
    assert saved_ui[0][0]["runtime_seq"] == 1
    assert result["model_v2_to_v1"]["action"] == "replace"
    assert saved_model == [[
        {"type": "user", "content": "hello"},
        {"type": "assistant", "content": "answer"},
    ]]


def test_migration_service_backfills_v2_from_legacy_only_when_explicit(monkeypatch, tmp_path):
    monkeypatch.setenv("RUNTIME_VERSION", "2")
    saved_ui = []
    saved_model = []

    result = RuntimeV2MigrationService(tmp_path).sync_session(
        "s1",
        load_legacy_ui_events=lambda: [{"type": "user", "content": "legacy"}],
        save_legacy_ui_events=lambda events: saved_ui.append(events),
        load_legacy_model_messages=lambda: [],
        save_legacy_model_messages=lambda messages: saved_model.append(messages),
    )

    events = RuntimeUiProjection(tmp_path).read_ui_events_fast("s1")
    model_messages = RuntimeModelProjection(tmp_path).read_message_dicts("s1")

    assert result["v2_from_v1"]["action"] == "backfill"
    assert result["model_v2_from_v1"]["action"] == "none"
    assert result["v1_from_v2"]["action"] == "skipped"
    assert result["model_v2_to_v1"]["action"] == "skipped"
    assert [event["content"] for event in events] == ["legacy"]
    assert model_messages == []
    assert saved_ui == []
    assert saved_model == []
    assert result["verification"]["verified"] is True
    manifest_path = Path(result["manifest_path"])
    assert manifest_path.name == "runtime_v2_migration.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["manifest_version"] == 1
    assert manifest["operation"] == "migrate"
    assert manifest["verification"]["ui"]["status"] == "match"
    assert len(manifest["verification"]["ui"]["source_sha256"]) == 64


def test_migration_service_does_not_replace_runtime_v2_ahead_with_legacy(monkeypatch, tmp_path):
    monkeypatch.setenv("RUNTIME_VERSION", "2")
    mirror = RuntimeMirror(tmp_path)
    mirror.mirror_ui_event("s1", {"type": "user", "content": "legacy prefix"})
    mirror.mirror_ui_event("s1", {"type": "final", "content": "runtime tail"})
    saved_ui = []
    saved_model = []

    result = RuntimeV2MigrationService(tmp_path).sync_session(
        "s1",
        load_legacy_ui_events=lambda: [{"type": "user", "content": "legacy prefix"}],
        save_legacy_ui_events=lambda events: saved_ui.append(events),
        load_legacy_model_messages=lambda: [],
        save_legacy_model_messages=lambda messages: saved_model.append(messages),
    )

    events = RuntimeUiProjection(tmp_path).read_ui_events_fast("s1")

    assert result["v2_from_v1"]["action"] == "v2_ahead"
    assert [event["content"] for event in events] == ["legacy prefix", "runtime tail"]
    assert saved_ui == []
    assert saved_model == []


def test_model_sync_does_not_replace_runtime_v2_ahead_with_legacy(monkeypatch, tmp_path):
    monkeypatch.setenv("RUNTIME_VERSION", "2")
    RuntimeHistoryOps(tmp_path).replace_model_history(
        "s1",
        [
            {"type": "user", "content": "legacy prefix"},
            {"type": "assistant", "content": "runtime tail"},
        ],
        reason="test",
    )
    projection = RuntimeModelProjection(tmp_path)

    result = projection.sync_from_legacy_if_needed(
        "s1",
        [{"type": "user", "content": "legacy prefix"}],
    )

    assert result["action"] == "v2_ahead"
    assert result["written"] == 0
    assert [message["content"] for message in projection.read_message_dicts("s1")] == [
        "legacy prefix",
        "runtime tail",
    ]


def test_model_sync_reports_legacy_ahead_as_mismatch_without_replacing(monkeypatch, tmp_path):
    monkeypatch.setenv("RUNTIME_VERSION", "2")
    RuntimeHistoryOps(tmp_path).replace_model_history(
        "s1",
        [{"type": "user", "content": "runtime prefix"}],
        reason="test",
    )
    projection = RuntimeModelProjection(tmp_path)

    result = projection.sync_from_legacy_if_needed(
        "s1",
        [
            {"type": "user", "content": "runtime prefix"},
            {"type": "assistant", "content": "legacy tail"},
        ],
    )

    assert result["action"] == "mismatch"
    assert result["written"] == 0
    assert [message["content"] for message in projection.read_message_dicts("s1")] == ["runtime prefix"]


def test_migration_manifest_marks_divergent_history_unverified(monkeypatch, tmp_path):
    monkeypatch.setenv("RUNTIME_VERSION", "2")
    RuntimeMirror(tmp_path).mirror_ui_event("s1", {"type": "user", "content": "runtime"})
    RuntimeHistoryOps(tmp_path).replace_model_history(
        "s1",
        [{"type": "user", "content": "runtime"}],
        reason="test",
    )

    result = RuntimeV2MigrationService(tmp_path).sync_session(
        "s1",
        load_legacy_ui_events=lambda: [{"type": "user", "content": "legacy"}],
        save_legacy_ui_events=None,
        load_legacy_model_messages=lambda: [{"type": "user", "content": "legacy"}],
        save_legacy_model_messages=None,
    )

    assert result["verification"]["verified"] is False
    assert result["verification"]["ui"]["status"] == "mismatch"
    assert result["verification"]["model"]["status"] == "mismatch"
