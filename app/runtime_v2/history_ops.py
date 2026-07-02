from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional

from .event_log import SessionEventLog
from .event_schema import RuntimeEvent
from .projector import RuntimeProjector
from .snapshot_store import SnapshotStore


class RuntimeHistoryOps:
    """Append-only history operations for the V2 path.

    These operations do not rewrite events.jsonl. They append semantic events
    and let RuntimeProjector calculate the visible/model history.
    """

    def __init__(self, sessions_dir: str | Path):
        self.event_log = SessionEventLog(sessions_dir)
        self.projector = RuntimeProjector()
        self.snapshots = SnapshotStore(sessions_dir)

    def delete_message(self, session_id: str, target_seq: int, reason: str = "") -> RuntimeEvent:
        return self._append_and_snapshot(session_id, "message_deleted", {
            "target_seq": int(target_seq),
            "reason": reason,
        })

    def rewrite_message(self, session_id: str, target_seq: int, content: str, reason: str = "") -> RuntimeEvent:
        return self._append_and_snapshot(session_id, "message_rewritten", {
            "target_seq": int(target_seq),
            "content": content,
            "reason": reason,
        })

    def create_branch(self, session_id: str, source_session_id: str, branch_from_seq: int, name: str = "") -> RuntimeEvent:
        event = self._append_and_snapshot(session_id, "history_branch_created", {
            "source_session_id": source_session_id,
            "branch_from_seq": int(branch_from_seq),
            "name": name,
        })
        self._seed_branch_visible_history(session_id, source_session_id, int(branch_from_seq))
        return event

    def compact_history(
        self,
        session_id: str,
        *,
        summary: str,
        compacted_before_seq: int,
        reason: str = "",
    ) -> RuntimeEvent:
        return self._append_and_snapshot(session_id, "history_compacted", {
            "summary": summary,
            "compacted_before_seq": int(compacted_before_seq),
            "reason": reason,
        })

    def commit_context_summary(self, session_id: str, summary: str, source_seq: Optional[int] = None) -> RuntimeEvent:
        payload = {"summary": summary}
        if source_seq is not None:
            payload["source_seq"] = int(source_seq)
        return self._append_and_snapshot(session_id, "context_summary_committed", payload)

    def change_visible_range(self, session_id: str, *, from_seq: Optional[int] = None, to_seq: Optional[int] = None, reason: str = "") -> RuntimeEvent:
        payload = {"reason": reason}
        if from_seq is not None:
            payload["from_seq"] = int(from_seq)
        if to_seq is not None:
            payload["to_seq"] = int(to_seq)
        return self._append_and_snapshot(session_id, "visible_range_changed", payload)

    def truncate_ui_history(self, session_id: str, before_index: int, reason: str = "") -> RuntimeEvent:
        """Record a UI-index truncation without rewriting the Runtime V2 log."""
        return self._append_and_snapshot(session_id, "visible_range_changed", {
            "to_ui_index": max(0, int(before_index)),
            "reason": reason or "ui_truncate",
        })

    def truncate_visible_history_before_seq(
        self,
        session_id: str,
        *,
        target_seq: int,
        keep_to_seq: int = 0,
        reason: str = "",
    ) -> RuntimeEvent:
        """Hide visible history from ``target_seq`` onward without UI indexes."""
        return self._append_and_snapshot(session_id, "visible_range_changed", {
            "target_seq": int(target_seq),
            "to_seq": max(0, int(keep_to_seq)),
            "apply_model": True,
            "reason": reason or f"truncate_before_seq:{int(target_seq)}",
        })

    def change_model_window(self, session_id: str, *, from_seq: Optional[int] = None, to_seq: Optional[int] = None, reason: str = "") -> RuntimeEvent:
        payload = {"reason": reason}
        if from_seq is not None:
            payload["from_seq"] = int(from_seq)
        if to_seq is not None:
            payload["to_seq"] = int(to_seq)
        return self._append_and_snapshot(session_id, "model_window_changed", payload)

    def append_model_message(self, session_id: str, role: str, content: str = "", **payload) -> RuntimeEvent:
        role = str(role or "").strip()
        event_type_by_role = {
            "user": "model_user",
            "assistant": "model_assistant",
            "tool": "model_tool",
            "system": "model_system",
        }
        event_type = event_type_by_role.get(role)
        if not event_type:
            raise ValueError(f"unsupported model role: {role}")
        data = dict(payload or {})
        run_id = data.pop("run_id", None)
        data["role"] = role
        data["content"] = content
        return self._append_and_snapshot(session_id, event_type, data, run_id=run_id)

    def replace_model_history(self, session_id: str, messages: list[dict], reason: str = "") -> RuntimeEvent:
        return self._append_and_snapshot(session_id, "model_history_replaced", {
            "messages": list(messages or []),
            "reason": reason,
        })

    def observe_legacy_truncate(
        self,
        session_id: str,
        *,
        before_index: int,
        old_event_count: int,
        new_event_count: int,
        boundary_for_branch: bool = False,
    ) -> RuntimeEvent:
        return self._append_and_snapshot(session_id, "legacy_truncate_observed", {
            "before_index": int(before_index),
            "old_event_count": int(old_event_count),
            "new_event_count": int(new_event_count),
            "boundary_for_branch": bool(boundary_for_branch),
        })

    def observe_legacy_tail_restored(
        self,
        session_id: str,
        *,
        tail_count: int,
        merged_event_count: int,
    ) -> RuntimeEvent:
        return self._append_and_snapshot(session_id, "legacy_tail_restored_observed", {
            "tail_count": int(tail_count),
            "merged_event_count": int(merged_event_count),
        })

    def observe_legacy_branch(
        self,
        session_id: str,
        *,
        source_session_id: str,
        new_session_id: str,
        before_index: int,
        new_event_count: int,
        name: str = "",
    ) -> RuntimeEvent:
        return self._append_and_snapshot(session_id, "legacy_branch_observed", {
            "source_session_id": source_session_id,
            "new_session_id": new_session_id,
            "before_index": int(before_index),
            "new_event_count": int(new_event_count),
            "name": name,
        })

    def observe_legacy_subagent_deleted(
        self,
        session_id: str,
        *,
        child_session_id: str,
        descendant_count: int = 0,
    ) -> RuntimeEvent:
        return self._append_and_snapshot(session_id, "legacy_subagent_deleted_observed", {
            "child_session_id": child_session_id,
            "descendant_count": int(descendant_count),
        })

    def observe_legacy_virtual_subagent_deleted(
        self,
        session_id: str,
        *,
        task_id: str,
    ) -> RuntimeEvent:
        return self._append_and_snapshot(session_id, "legacy_virtual_subagent_deleted_observed", {
            "task_id": task_id,
        })

    def observe_legacy_compress(
        self,
        session_id: str,
        *,
        summary: str = "",
        source_seq: Optional[int] = None,
        reason: str = "",
    ) -> RuntimeEvent:
        payload = {
            "summary": summary,
            "reason": reason,
        }
        if source_seq is not None:
            payload["source_seq"] = int(source_seq)
        return self._append_and_snapshot(session_id, "legacy_compress_observed", payload)

    def _append_and_snapshot(self, session_id: str, event_type: str, payload: dict, run_id: Optional[str] = None) -> RuntimeEvent:
        event = self.event_log.append(session_id, event_type, payload=payload, run_id=run_id)
        snapshot = self.projector.project_incremental(self.snapshots.read(session_id), event)
        self.snapshots.write(session_id, snapshot)
        return event

    def _seed_branch_visible_history(self, session_id: str, source_session_id: str, branch_from_seq: int) -> int:
        if self._has_projectable_ui_events(session_id):
            return 0
        projected_count = self._seed_branch_from_projected_ui(session_id, source_session_id, int(branch_from_seq))
        if projected_count:
            return projected_count
        count = 0
        for source_event in self.event_log.iter_events(source_session_id):
            if int(source_event.seq) > int(branch_from_seq):
                break
            if not self._is_branch_seed_event(source_event):
                continue
            copied = self._append_and_snapshot(
                session_id,
                source_event.type,
                self._copy_blob_refs(source_session_id, session_id, dict(source_event.payload or {})),
                run_id=source_event.run_id,
            )
            count += 1 if copied is not None else 0
        return count

    def _seed_branch_from_projected_ui(self, session_id: str, source_session_id: str, branch_from_seq: int) -> int:
        try:
            from .mirror import RuntimeMirror
            from .ui_projection import RuntimeUiProjection

            projection = RuntimeUiProjection(self.event_log.root)
            end_index = projection.runtime_seq_to_ui_end_index(source_session_id, int(branch_from_seq))
            if end_index is None:
                return 0
            source_events = projection.read_ui_events(source_session_id)[:max(0, int(end_index))]
            if not source_events:
                return 0
            mirror = RuntimeMirror(self.event_log.root)
            count = 0
            for event in source_events:
                if not isinstance(event, dict):
                    continue
                seed = dict(event)
                seed.pop("runtime_seq", None)
                seed.pop("runtime_event_type", None)
                seed.pop("rewritten", None)
                seed.pop("rewritten_by_seq", None)
                seed.pop("session_id", None)
                mirrored = mirror.mirror_ui_event(session_id, seed)
                if mirrored is None:
                    mirrored = mirror.append(session_id, "legacy_ui_event", self._copy_blob_refs(source_session_id, session_id, seed))
                count += 1 if mirrored is not None else 0
            return count
        except Exception:
            return 0

    def _has_projectable_ui_events(self, session_id: str) -> bool:
        return any(self._is_branch_seed_event(event) for event in self.event_log.iter_events(session_id))

    def _copy_blob_refs(self, source_session_id: str, target_session_id: str, payload: dict) -> dict:
        source_dir = self.event_log.session_dir(source_session_id)
        target_dir = self.event_log.session_dir(target_session_id)
        copied = dict(payload or {})
        for value in copied.values():
            if not isinstance(value, dict):
                continue
            blob_ref = value.get("blob_ref")
            if not blob_ref:
                continue
            rel = Path(str(blob_ref))
            if rel.is_absolute() or ".." in rel.parts:
                continue
            source = source_dir / rel
            target = target_dir / rel
            try:
                if source.exists() and not target.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
            except Exception:
                continue
        return copied

    @staticmethod
    def _is_branch_seed_event(event: RuntimeEvent) -> bool:
        if event.type in {
            "message_user",
            "message_assistant_final",
            "tool_started",
            "tool_finished",
            "context_summary_committed",
            "todo_updated",
            "context_tokens",
            "legacy_ui_event",
        }:
            return True
        return event.type.startswith("subagent_")
