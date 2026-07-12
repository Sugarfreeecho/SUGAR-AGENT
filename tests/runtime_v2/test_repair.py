import uuid
from pathlib import Path

from app.runtime_v2 import (
    RuntimeHistoryOps,
    RuntimeMirror,
    RuntimeModelProjection,
    RuntimeUiProjection,
    RuntimeV2SubagentRepairService,
)


def _split_fixture(tmp_path: Path):
    parent_id = str(uuid.uuid4())
    child_id = str(uuid.uuid4())
    canonical = tmp_path / parent_id / "subagents" / child_id
    canonical.mkdir(parents=True)

    def resolver(session_id: str) -> Path:
        return canonical if session_id == child_id else tmp_path / session_id

    nested_mirror = RuntimeMirror(tmp_path, path_resolver=resolver)
    user = nested_mirror.mirror_ui_event(
        child_id,
        {"type": "user", "content": "subagent task"},
    )
    nested_mirror.mirror_ui_event(
        child_id,
        {"type": "final", "content": "visible answer"},
    )
    ghost_ops = RuntimeHistoryOps(tmp_path)
    ghost_ops.append_model_message(child_id, "system", "subagent system")
    ghost_ops.append_model_message(child_id, "assistant", "model answer")
    return parent_id, child_id, resolver, user


def test_subagent_split_repair_dry_run_is_read_only(tmp_path):
    parent_id, child_id, resolver, _user = _split_fixture(tmp_path)
    service = RuntimeV2SubagentRepairService(tmp_path, path_resolver=resolver)
    canonical_path = resolver(child_id) / "events.jsonl"
    ghost_path = tmp_path / child_id / "events.jsonl"
    before_canonical = canonical_path.read_bytes()
    before_ghost = ghost_path.read_bytes()

    result = service.repair(parent_id, child_id, apply=False)

    assert result["action"] == "dry_run"
    assert result["applied"] is False
    assert result["synthesized_model_user_events"] == 1
    assert canonical_path.read_bytes() == before_canonical
    assert ghost_path.read_bytes() == before_ghost


def test_subagent_split_repair_merges_ui_model_context_and_archives_ghost(tmp_path):
    parent_id, child_id, resolver, _user = _split_fixture(tmp_path)
    service = RuntimeV2SubagentRepairService(tmp_path, path_resolver=resolver)
    canonical_before = RuntimeHistoryOps(
        tmp_path,
        path_resolver=resolver,
    ).event_log.read_all(child_id)

    result = service.repair(parent_id, child_id, apply=True)

    assert result["applied"] is True
    assert result["action"] == "repaired"
    assert Path(result["manifest_path"]).is_file()
    assert Path(result["ghost_archive_path"]).is_dir()
    assert not (tmp_path / child_id).exists()
    canonical_after = RuntimeHistoryOps(
        tmp_path,
        path_resolver=resolver,
    ).event_log.read_all(child_id)
    assert [event.to_dict() for event in canonical_after[: len(canonical_before)]] == [
        event.to_dict() for event in canonical_before
    ]
    assert [
        row["content"]
        for row in RuntimeModelProjection(
            tmp_path,
            path_resolver=resolver,
        ).read_message_dicts(child_id)
    ] == ["subagent task", "subagent system", "model answer"]
    assert [
        event["content"]
        for event in RuntimeUiProjection(
            tmp_path,
            path_resolver=resolver,
        ).read_ui_events(child_id)
        if event.get("type") in {"user", "final"}
    ] == ["subagent task", "visible answer"]

    second = service.repair(parent_id, child_id, apply=True)
    assert second["action"] == "no_split_brain"
    assert second["applied"] is False


def test_subagent_split_repair_never_rewrites_nested_tool_payload_sequence_fields(tmp_path):
    parent_id, child_id, resolver, _user = _split_fixture(tmp_path)
    RuntimeHistoryOps(tmp_path).append_model_message(
        child_id,
        "assistant",
        "tool request",
        tool_calls=[{
            "id": "call-1",
            "name": "example",
            "args": {"seq": 1, "source_seq": 1},
        }],
    )
    service = RuntimeV2SubagentRepairService(tmp_path, path_resolver=resolver)

    result = service.repair(parent_id, child_id, apply=True)
    model = RuntimeModelProjection(tmp_path, path_resolver=resolver).read_message_dicts(child_id)

    assert result["applied"] is True
    tool_request = next(item for item in model if item.get("content") == "tool request")
    args = tool_request["tool_calls"][0]["args"]
    assert args == {"seq": 1, "source_seq": 1}


def test_subagent_split_repair_refuses_malformed_or_non_model_ghost_facts(tmp_path):
    parent_id, child_id, resolver, _user = _split_fixture(tmp_path)
    ghost_path = tmp_path / child_id / "events.jsonl"
    with ghost_path.open("ab") as fh:
        fh.write(b"{broken-json\n")
    service = RuntimeV2SubagentRepairService(tmp_path, path_resolver=resolver)

    result = service.repair(parent_id, child_id, apply=True)

    assert result["applied"] is False
    assert result["action"] == "refused"
    assert result["ok"] is False
    assert any("malformed" in conflict for conflict in result["conflicts"])
    assert ghost_path.is_file()


def test_subagent_split_repair_pending_archive_is_not_reported_ok(tmp_path, monkeypatch):
    parent_id, child_id, resolver, _user = _split_fixture(tmp_path)
    service = RuntimeV2SubagentRepairService(tmp_path, path_resolver=resolver)

    def fail_archive(*_args, **_kwargs):
        raise OSError("archive unavailable")

    monkeypatch.setattr("app.runtime_v2.repair.shutil.move", fail_archive)
    result = service.repair(parent_id, child_id, apply=True)

    assert result["applied"] is True
    assert result["action"] == "committed_pending_archive"
    assert result["ok"] is False
    assert "archive unavailable" in result["ghost_archive_error"]
