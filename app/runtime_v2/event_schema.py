from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .versions import EVENT_SCHEMA_VERSION


CORE_EVENT_TYPES = {
    "session_meta",
    "message_user",
    "user_turn_committed",
    "assistant_final_committed",
    "message_assistant_delta",
    "message_assistant_final",
    "model_user",
    "model_assistant",
    "model_tool",
    "model_system",
    "model_history_replaced",
    "run_started",
    "run_heartbeat",
    "runtime_resumed",
    "run_finished",
    "run_failed",
    "run_interrupted",
    "tool_started",
    "tool_delta",
    "tool_finished",
    "tool_failed",
    "interaction_requested",
    "interaction_resolved",
    "interaction_cancelled",
    "interaction_expired",
    "approval_requested",
    "approval_resolved",
    "approval_cancelled",
    "approval_expired",
    "subagent_started",
    "subagent_progress",
    "subagent_finished",
    "subagent_failed",
    "subagent_result_consumed",
    "subagent_deleted",
    "team_created",
    "team_status_changed",
    "team_member_added",
    "team_member_updated",
    "team_member_state_changed",
    "team_member_removed",
    "team_task_created",
    "team_task_updated",
    "team_task_claimed",
    "team_task_released",
    "team_message_enqueued",
    "team_message_delivery_started",
    "team_message_delivered",
    "team_message_consumed",
    "team_message_delivery_failed",
    "team_permission_requested",
    "team_permission_resolved",
    "team_permission_consumed",
    "team_shutdown_requested",
    "team_shutdown_completed",
    "team_archived",
    "context_tokens",
    "context_summary_started",
    "context_summary_finished",
    "todo_updated",
    "goal_created",
    "goal_updated",
    "goal_usage_updated",
    "goal_completion_requested",
    "goal_judge_evaluated",
    "goal_review_saved",
    "goal_review_approved",
    "goal_review_reopened",
    "goal_continuation_started",
    "goal_paused",
    "goal_resumed",
    "goal_completed",
    "goal_blocked",
    "goal_cancelled",
    "hook_started",
    "hook_progress",
    "hook_finished",
    "hook_failed",
    "hook_blocked",
    "hook_timed_out",
    "hook_input_modified",
    "plugin_state_changed",
    "plugin_reloaded",
    "ui_event",
    "legacy_ui_event",
    "message_deleted",
    "message_rewritten",
    "history_branch_created",
    "history_compacted",
    "context_summary_committed",
    "visible_range_changed",
    "model_window_changed",
    "legacy_truncate_observed",
    "legacy_tail_restored_observed",
    "legacy_branch_observed",
    "legacy_subagent_deleted_observed",
    "legacy_virtual_subagent_deleted_observed",
    "legacy_compress_observed",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


@dataclass(frozen=True)
class RuntimeEvent:
    seq: int
    type: str
    session_id: str
    timestamp: str = field(default_factory=now_iso)
    run_id: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    schema_version: int = EVENT_SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "schema_version": int(self.schema_version),
            "seq": int(self.seq),
            "timestamp": self.timestamp,
            "type": self.type,
            "session_id": self.session_id,
            "payload": dict(self.payload or {}),
        }
        if self.run_id:
            data["run_id"] = self.run_id
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RuntimeEvent":
        if not isinstance(data, dict):
            raise ValueError("runtime event must be an object")
        schema_version = data.get("schema_version", EVENT_SCHEMA_VERSION)
        if not isinstance(schema_version, int) or schema_version <= 0:
            raise ValueError("runtime event schema_version must be a positive integer")
        if schema_version > EVENT_SCHEMA_VERSION:
            raise ValueError(
                f"runtime event schema_version {schema_version} is newer than supported "
                f"version {EVENT_SCHEMA_VERSION}"
            )
        seq = data.get("seq")
        if not isinstance(seq, int):
            raise ValueError("runtime event seq must be an integer")
        event_type = str(data.get("type") or "").strip()
        if not event_type:
            raise ValueError("runtime event type is required")
        session_id = str(data.get("session_id") or "").strip()
        if not session_id:
            raise ValueError("runtime event session_id is required")
        timestamp = str(data.get("timestamp") or now_iso())
        run_id_raw = data.get("run_id")
        run_id = str(run_id_raw).strip() if run_id_raw else None
        payload = data.get("payload")
        if payload is None:
            payload = {}
        if not isinstance(payload, dict):
            raise ValueError("runtime event payload must be an object")
        return cls(
            seq=seq,
            type=event_type,
            session_id=session_id,
            timestamp=timestamp,
            run_id=run_id,
            payload=payload,
            schema_version=schema_version,
        )
