import json
from pathlib import Path

import pytest

from app.runtime_v2 import RuntimeHistoryOps, RuntimeMirror, RuntimeModelProjection
from app.runtime_v2.migration import RuntimeV2MigrationService, RuntimeV2VerificationError
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
        load_legacy_model_messages=lambda: [
            {"type": "user", "content": "hello"},
            {"type": "assistant", "content": "answer"},
        ],
        save_legacy_model_messages=lambda messages: saved_model.append(messages),
    )

    assert result["v1_from_v2"]["action"] == "skipped"
    assert result["model_v2_from_v1"]["action"] == "none"
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
    legacy_ui = []
    legacy_model = [{"type": "user", "content": "legacy"}]

    def save_ui(events):
        saved_ui.append([dict(row) for row in events])
        legacy_ui[:] = [dict(row) for row in events]

    def save_model(messages):
        saved_model.append([dict(row) for row in messages])
        legacy_model[:] = [dict(row) for row in messages]

    result = RuntimeV2MigrationService(tmp_path).sync_session(
        "s1",
        load_legacy_ui_events=lambda: [dict(row) for row in legacy_ui],
        save_legacy_ui_events=save_ui,
        load_legacy_model_messages=lambda: [dict(row) for row in legacy_model],
        save_legacy_model_messages=save_model,
        export_legacy=True,
    )

    assert result["v2_from_v1"]["action"] == "skipped_export_mode"
    assert result["model_v2_from_v1"]["action"] == "skipped_export_mode"
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
    assert result["verification"]["verified"] is True


def test_explicit_export_replaces_equal_length_rewrite_and_shorter_history(monkeypatch, tmp_path):
    monkeypatch.setenv("RUNTIME_VERSION", "2")
    mirror = RuntimeMirror(tmp_path)
    mirror.mirror_ui_event("s1", {"type": "user", "content": "new"})
    RuntimeHistoryOps(tmp_path).replace_model_history(
        "s1",
        [{"type": "user", "content": "new model"}],
        reason="test",
    )
    saved_ui = []
    saved_model = []
    legacy_ui = [
        {"type": "user", "content": "old"},
        {"type": "final", "content": "old tail"},
    ]
    legacy_model = [
        {"type": "user", "content": "old model"},
        {"type": "assistant", "content": "old tail"},
    ]

    def save_ui(rows):
        saved_ui.append([dict(row) for row in rows])
        legacy_ui[:] = [dict(row) for row in rows]

    def save_model(rows):
        saved_model.append([dict(row) for row in rows])
        legacy_model[:] = [dict(row) for row in rows]

    result = RuntimeV2MigrationService(tmp_path).sync_session(
        "s1",
        load_legacy_ui_events=lambda: [dict(row) for row in legacy_ui],
        save_legacy_ui_events=save_ui,
        load_legacy_model_messages=lambda: [dict(row) for row in legacy_model],
        save_legacy_model_messages=save_model,
        export_legacy=True,
    )

    assert result["v1_from_v2"]["action"] == "replace"
    assert result["model_v2_to_v1"]["action"] == "replace"
    assert [row["content"] for row in saved_ui[0]] == ["new"]
    assert saved_model == [[{"type": "user", "content": "new model"}]]
    assert result["verification"]["verified"] is True


def test_explicit_export_can_clear_legacy_when_v2_is_empty(monkeypatch, tmp_path):
    monkeypatch.setenv("RUNTIME_VERSION", "2")
    saved_ui = []
    saved_model = []
    legacy_ui = [{"type": "user", "content": "old"}]
    legacy_model = [{"type": "user", "content": "old"}]

    def save_ui(rows):
        saved_ui.append([dict(row) for row in rows])
        legacy_ui[:] = [dict(row) for row in rows]

    def save_model(rows):
        saved_model.append([dict(row) for row in rows])
        legacy_model[:] = [dict(row) for row in rows]

    result = RuntimeV2MigrationService(tmp_path).sync_session(
        "s1",
        load_legacy_ui_events=lambda: [dict(row) for row in legacy_ui],
        save_legacy_ui_events=save_ui,
        load_legacy_model_messages=lambda: [dict(row) for row in legacy_model],
        save_legacy_model_messages=save_model,
        export_legacy=True,
    )

    assert saved_ui == [[]]
    assert saved_model == [[]]
    assert result["verification"]["verified"] is True


def test_migration_loader_failure_leaves_no_partial_v2_state(monkeypatch, tmp_path):
    monkeypatch.setenv("RUNTIME_VERSION", "2")

    def fail_model_load():
        raise RuntimeError("boom")

    try:
        RuntimeV2MigrationService(tmp_path).sync_session(
            "s1",
            load_legacy_ui_events=lambda: [{"type": "user", "content": "legacy"}],
            save_legacy_ui_events=None,
            load_legacy_model_messages=fail_model_load,
            save_legacy_model_messages=None,
        )
    except RuntimeError as exc:
        assert str(exc) == "boom"
    else:
        raise AssertionError("loader failure should propagate")

    assert not (tmp_path / "s1" / "events.jsonl").exists()
    assert not (tmp_path / "s1" / "runtime_v2_migration.json").exists()


def test_migration_rolls_back_v2_if_model_stage_fails(monkeypatch, tmp_path):
    monkeypatch.setenv("RUNTIME_VERSION", "2")
    original = RuntimeModelProjection.sync_from_legacy_if_needed

    def fail_model_sync(self, *args, **kwargs):
        raise RuntimeError("model stage failed")

    monkeypatch.setattr(RuntimeModelProjection, "sync_from_legacy_if_needed", fail_model_sync)
    try:
        RuntimeV2MigrationService(tmp_path).sync_session(
            "s1",
            load_legacy_ui_events=lambda: [{"type": "user", "content": "legacy"}],
            save_legacy_ui_events=None,
            load_legacy_model_messages=lambda: [],
            save_legacy_model_messages=None,
        )
    except RuntimeError as exc:
        assert str(exc) == "model stage failed"
    else:
        raise AssertionError("stage failure should propagate")
    finally:
        monkeypatch.setattr(RuntimeModelProjection, "sync_from_legacy_if_needed", original)

    assert not (tmp_path / "s1" / "events.jsonl").exists()
    assert RuntimeUiProjection(tmp_path).read_ui_events("s1") == []


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


def test_migration_verification_mismatch_rolls_back_partial_v2_write(monkeypatch, tmp_path):
    monkeypatch.setenv("RUNTIME_VERSION", "2")
    RuntimeHistoryOps(tmp_path).replace_model_history(
        "s1",
        [{"type": "user", "content": "runtime"}],
        reason="test",
    )
    original_events = (tmp_path / "s1" / "events.jsonl").read_bytes()

    with pytest.raises(RuntimeV2VerificationError) as exc_info:
        RuntimeV2MigrationService(tmp_path).sync_session(
            "s1",
            load_legacy_ui_events=lambda: [{"type": "user", "content": "legacy ui"}],
            save_legacy_ui_events=None,
            load_legacy_model_messages=lambda: [{"type": "user", "content": "legacy model"}],
            save_legacy_model_messages=None,
        )

    assert exc_info.value.verification["verified"] is False
    assert exc_info.value.verification["model"]["status"] == "mismatch"
    assert (tmp_path / "s1" / "events.jsonl").read_bytes() == original_events
    assert RuntimeUiProjection(tmp_path).read_ui_events_fast("s1") == []
    assert RuntimeModelProjection(tmp_path).read_message_dicts("s1") == [
        {"type": "user", "content": "runtime"}
    ]
    assert not (tmp_path / "s1" / "runtime_v2_migration.json").exists()


def test_export_verifies_persisted_readback_and_rolls_back_on_mismatch(monkeypatch, tmp_path):
    monkeypatch.setenv("RUNTIME_VERSION", "2")
    RuntimeMirror(tmp_path).mirror_ui_event("s1", {"type": "user", "content": "runtime ui"})
    RuntimeHistoryOps(tmp_path).replace_model_history(
        "s1",
        [{"type": "user", "content": "runtime model"}],
        reason="test",
    )
    legacy_ui = [{"type": "user", "content": "legacy ui"}]
    legacy_model = [{"type": "user", "content": "legacy model"}]
    model_saves: list[list[dict]] = []
    ui_loads = 0
    model_loads = 0

    def load_ui():
        nonlocal ui_loads
        ui_loads += 1
        return [dict(row) for row in legacy_ui]

    def save_ui(_rows):
        # Simulate a legacy saver that returns successfully without persisting.
        return None

    def load_model():
        nonlocal model_loads
        model_loads += 1
        return [dict(row) for row in legacy_model]

    def save_model(rows):
        legacy_model[:] = [dict(row) for row in rows]
        model_saves.append([dict(row) for row in rows])

    with pytest.raises(RuntimeV2VerificationError):
        RuntimeV2MigrationService(tmp_path).sync_session(
            "s1",
            load_legacy_ui_events=load_ui,
            save_legacy_ui_events=save_ui,
            load_legacy_model_messages=load_model,
            save_legacy_model_messages=save_model,
            export_legacy=True,
        )

    assert ui_loads == 2
    assert model_loads == 2
    assert legacy_ui == [{"type": "user", "content": "legacy ui"}]
    assert legacy_model == [{"type": "user", "content": "legacy model"}]
    assert [row[0]["content"] for row in model_saves] == ["runtime model", "legacy model"]
    assert not (tmp_path / "s1" / "runtime_v2_migration.json").exists()


def test_export_loader_failure_after_save_rolls_back_legacy(monkeypatch, tmp_path):
    monkeypatch.setenv("RUNTIME_VERSION", "2")
    RuntimeMirror(tmp_path).mirror_ui_event("s1", {"type": "user", "content": "runtime"})
    legacy_ui = [{"type": "user", "content": "legacy"}]
    load_count = 0

    def load_ui():
        nonlocal load_count
        load_count += 1
        if load_count > 1:
            raise RuntimeError("readback failed")
        return [dict(row) for row in legacy_ui]

    def save_ui(rows):
        legacy_ui[:] = [dict(row) for row in rows]

    with pytest.raises(RuntimeError, match="readback failed"):
        RuntimeV2MigrationService(tmp_path).sync_session(
            "s1",
            load_legacy_ui_events=load_ui,
            save_legacy_ui_events=save_ui,
            load_legacy_model_messages=lambda: [],
            save_legacy_model_messages=lambda _rows: None,
            export_legacy=True,
        )

    assert legacy_ui == [{"type": "user", "content": "legacy"}]
    assert not (tmp_path / "s1" / "runtime_v2_migration.json").exists()


def test_export_second_saver_failure_rolls_back_first_export(monkeypatch, tmp_path):
    monkeypatch.setenv("RUNTIME_VERSION", "2")
    RuntimeMirror(tmp_path).mirror_ui_event("s1", {"type": "user", "content": "runtime ui"})
    RuntimeHistoryOps(tmp_path).replace_model_history(
        "s1",
        [{"type": "user", "content": "runtime model"}],
        reason="test",
    )
    legacy_ui = [{"type": "user", "content": "legacy ui"}]
    legacy_model = [{"type": "user", "content": "legacy model"}]
    model_save_calls = 0

    def save_ui(rows):
        legacy_ui[:] = [dict(row) for row in rows]

    def save_model(rows):
        nonlocal model_save_calls
        model_save_calls += 1
        if model_save_calls == 1:
            raise RuntimeError("model save failed")
        legacy_model[:] = [dict(row) for row in rows]

    with pytest.raises(RuntimeError, match="model save failed"):
        RuntimeV2MigrationService(tmp_path).sync_session(
            "s1",
            load_legacy_ui_events=lambda: [dict(row) for row in legacy_ui],
            save_legacy_ui_events=save_ui,
            load_legacy_model_messages=lambda: [dict(row) for row in legacy_model],
            save_legacy_model_messages=save_model,
            export_legacy=True,
        )

    assert legacy_ui == [{"type": "user", "content": "legacy ui"}]
    assert legacy_model == [{"type": "user", "content": "legacy model"}]
    assert model_save_calls == 2
    assert not (tmp_path / "s1" / "runtime_v2_migration.json").exists()
