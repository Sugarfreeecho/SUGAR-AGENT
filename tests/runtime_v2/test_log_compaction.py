import tempfile

import pytest

from app.runtime_v2 import (
    RuntimeHistoryOps,
    RuntimeUiProjection,
    RuntimeV2LogCompactionError,
    RuntimeV2LogCompactionService,
)


def test_offline_log_compaction_preserves_model_and_ui_projection():
    with tempfile.TemporaryDirectory() as tmp:
        ops = RuntimeHistoryOps(tmp)
        ops.commit_user_turn("s1", "u", operation_id="u1")
        ops.commit_assistant_final("s1", "a", operation_id="a1")
        for _ in range(40):
            ops.replace_model_history(
                "s1",
                [{"type": "user", "content": "u"}, {"type": "assistant", "content": "a"}],
                reason="legacy_finish",
            )
        before_model = [row["payload"]["content"] for row in ops.snapshots.read("s1")["model_messages"]]
        before_ui = RuntimeUiProjection(tmp).read_ui_events("s1")

        result = RuntimeV2LogCompactionService(tmp).compact("s1", keep_backup=False)

        after = RuntimeHistoryOps(tmp).snapshots.read_consistent(
            "s1", RuntimeHistoryOps(tmp).event_log, RuntimeHistoryOps(tmp).projector
        )
        assert result["compacted"] is True
        assert result["events_after"] == 1
        assert result["bytes_after"] < result["bytes_before"]
        assert [row["payload"]["content"] for row in after["model_messages"]] == before_model
        assert RuntimeUiProjection(tmp).read_ui_events("s1") == before_ui
        RuntimeHistoryOps(tmp).commit_user_turn("s1", "next", operation_id="u2")
        assert [event["content"] for event in RuntimeUiProjection(tmp).read_ui_events("s1")] == [
            "u", "a", "next"
        ]


def test_log_compaction_rejects_active_session():
    with tempfile.TemporaryDirectory() as tmp:
        ops = RuntimeHistoryOps(tmp)
        ops._append_and_snapshot("s1", "run_started", {}, run_id="r1")
        with pytest.raises(RuntimeV2LogCompactionError, match="active run"):
            RuntimeV2LogCompactionService(tmp).compact("s1", keep_backup=False)
