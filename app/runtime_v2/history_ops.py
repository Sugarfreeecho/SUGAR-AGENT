from __future__ import annotations

import logging
import shutil
import time
from pathlib import Path
from typing import Optional

from .event_log import SessionEventLog
from .event_schema import RuntimeEvent
from .projector import RuntimeProjector
from .snapshot_store import SnapshotStore

logger = logging.getLogger(__name__)


def _rt2_step_ms(start: float, end: Optional[float] = None) -> int:
    if end is None:
        end = time.perf_counter()
    return int(max(0.0, (end - start) * 1000.0))


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
        t0 = time.perf_counter()
        branch_from_seq = int(branch_from_seq)
        ui_events = self._branch_ui_events(source_session_id, branch_from_seq)
        t_after_ui = time.perf_counter()
        source_checkpoint = self._source_snapshot_at_seq(source_session_id, branch_from_seq)
        model_messages = self._model_message_dicts_from_snapshot(source_checkpoint)
        source_context = source_checkpoint.get("context") if isinstance(source_checkpoint, dict) else {}
        source_summary = source_context.get("summary") if isinstance(source_context, dict) else {}
        source_summary_text = str(source_summary.get("summary") or "") if isinstance(source_summary, dict) else ""
        t_after_model = time.perf_counter()
        seed_rows = self._branch_ui_seed_rows(session_id, source_session_id, ui_events)
        t_after_map = time.perf_counter()

        with self.event_log.session_transaction(session_id):
            existing_events = self.event_log.read_all(session_id)
            snapshot = self.snapshots.read(session_id)
            if int(snapshot.get("last_seq") or 0) != max((int(ev.seq) for ev in existing_events), default=0):
                snapshot = self.projector.project(existing_events)
            has_ui = any(
                self._is_branch_seed_event(event) and not self._is_branch_runtime_metric_event(event)
                for event in existing_events
            )
            has_model = bool(snapshot.get("raw_model_messages") if isinstance(snapshot, dict) else None)
            rows = [{
                "type": "history_branch_created",
                "payload": {
                    "source_session_id": source_session_id,
                    "branch_from_seq": branch_from_seq,
                    "name": name,
                },
            }]
            if not has_ui:
                rows.extend(seed_rows)
            if not has_model and model_messages:
                rows.append({
                    "type": "model_history_replaced",
                    "payload": {
                        "messages": model_messages,
                        "reason": "branch_model_seed",
                        "summary": source_summary_text,
                    },
                })
            appended = self.event_log._append_many_unlocked(session_id, rows)
            if not appended:
                raise RuntimeError("branch batch append produced no events")
            if int(snapshot.get("last_seq") or 0) == int(appended[0].seq) - 1:
                if not snapshot:
                    snapshot = self.projector.empty_snapshot()
                for appended_event in appended:
                    self.projector.apply(snapshot, appended_event)
                self.projector.finalize(snapshot)
            else:
                snapshot = self.projector.project(self.event_log.read_all(session_id))
            self.snapshots.stamp_event_log(session_id, snapshot, self.event_log.event_path(session_id))
            self.snapshots.write(session_id, snapshot)
        self._seed_branch_subagent_details_bulk(session_id, ui_events)
        t_after_commit = time.perf_counter()
        logger.info(
            "rt2_branch_timing session=%s source=%s branch_from_seq=%s ui_events=%s model_messages=%s "
            "source_ui_ms=%s source_model_ms=%s map_ms=%s commit_ms=%s total_ms=%s",
            session_id,
            source_session_id,
            branch_from_seq,
            len(ui_events),
            len(model_messages),
            _rt2_step_ms(t0, t_after_ui),
            _rt2_step_ms(t_after_ui, t_after_model),
            _rt2_step_ms(t_after_model, t_after_map),
            _rt2_step_ms(t_after_map, t_after_commit),
            _rt2_step_ms(t0, t_after_commit),
        )
        return appended[0]

    def _branch_ui_events(self, source_session_id: str, branch_from_seq: int) -> list[dict]:
        from .ui_projection import RuntimeUiProjection

        projection = RuntimeUiProjection(self.event_log.root)
        return projection.read_ui_events_through_runtime_seq(source_session_id, branch_from_seq)

    def _branch_ui_seed_rows(
        self,
        session_id: str,
        source_session_id: str,
        source_events: list[dict],
    ) -> list[dict]:
        from .mirror import RuntimeMirror

        mirror = RuntimeMirror(self.event_log.root)
        rows: list[dict] = []
        for event in source_events:
            if not isinstance(event, dict):
                continue
            seed = dict(event)
            origin_session_id = str(
                seed.get("branch_source_session_id") or source_session_id
            ).strip()
            origin_runtime_seq = seed.get("branch_source_runtime_seq", seed.get("runtime_seq"))
            seed.pop("runtime_seq", None)
            seed.pop("runtime_event_type", None)
            seed.pop("rewritten", None)
            seed.pop("rewritten_by_seq", None)
            seed.pop("session_id", None)
            if self._is_projected_ui_runtime_metric(seed):
                continue
            mapped = mirror._map_ui_event(session_id, seed)
            if not mapped:
                mapped = {
                    "type": "legacy_ui_event",
                    "payload": self._copy_blob_refs(source_session_id, session_id, seed),
                }
            mapped_payload = dict(mapped.get("payload") or {})
            if origin_session_id and self.projector._int_or_none(origin_runtime_seq) is not None:
                mapped_payload["branch_source_session_id"] = origin_session_id
                mapped_payload["branch_source_runtime_seq"] = int(origin_runtime_seq)
            rows.append({
                "type": mapped["type"],
                "payload": mapped_payload,
                "run_id": mapped.get("run_id"),
            })
        return rows

    def _seed_branch_subagent_details_bulk(self, session_id: str, source_events: list[dict]) -> None:
        from .mirror import RuntimeMirror

        grouped: dict[str, list[dict]] = {}
        mirror = RuntimeMirror(self.event_log.root)
        allowed = {
            "subagent_started",
            "subagent_progress",
            "subagent_finished",
            "subagent_failed",
            "subagent_result_consumed",
        }
        for event in source_events:
            if not isinstance(event, dict):
                continue
            event_type = str(event.get("type") or "")
            if event_type not in allowed:
                continue
            agent_id = str(event.get("agent_id") or event.get("task_id") or event.get("id") or "").strip()
            if not agent_id:
                continue
            payload = mirror._externalize_large_text_payload(
                str(self.event_log.session_dir(session_id) / "subagents" / agent_id),
                dict(event),
            )
            grouped.setdefault(agent_id, []).append({"type": event_type, "payload": payload})
        if not grouped:
            return
        root = self.event_log.session_dir(session_id) / "subagents"
        for agent_id, rows in grouped.items():
            log = SessionEventLog(root)
            snapshots = SnapshotStore(root)
            with log.session_transaction(agent_id):
                appended = log._append_many_unlocked(agent_id, rows)
                child_snapshot = self.projector.empty_snapshot()
                for event in appended:
                    self.projector.apply(child_snapshot, event)
                self.projector.finalize(child_snapshot)
                snapshots.stamp_event_log(agent_id, child_snapshot, log.event_path(agent_id))
                snapshots.write(agent_id, child_snapshot)

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

    def update_todo(self, session_id: str, todo: dict) -> RuntimeEvent:
        return self._append_and_snapshot(session_id, "todo_updated", dict(todo or {}))

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
        payload = {
            "target_seq": int(target_seq),
            "to_seq": max(0, int(keep_to_seq)),
            "apply_model": True,
            "reason": reason or f"truncate_before_seq:{int(target_seq)}",
        }
        payload.update(
            self._restore_checkpoint_before_seq(
                session_id,
                int(target_seq),
                keep_to_seq=max(0, int(keep_to_seq)),
            )
        )
        return self._append_and_snapshot(session_id, "visible_range_changed", payload)

    def _restore_checkpoint_before_seq(self, session_id: str, target_seq: int, *, keep_to_seq: int) -> dict:
        """Capture the exact model context immediately before a rewritten turn.

        A stopped run may already have replaced/compressed model history and
        updated the context summary. Truncating only UI/model rows would leave
        that post-send summary behind, so the next rewritten run would start
        from a different token baseline. The checkpoint is stored on the
        append-only truncate event so replay restores the same context state.
        """
        checkpoint = self.projector.empty_snapshot()
        for event in self.event_log.iter_events(session_id):
            if int(event.seq) >= int(target_seq):
                break
            self.projector.apply(checkpoint, event)
        self.projector.finalize(checkpoint)
        context = checkpoint.get("context") if isinstance(checkpoint, dict) else {}
        if not isinstance(context, dict):
            context = {}
        summary = context.get("summary")
        if not isinstance(summary, dict):
            summary = {"summary": "", "source_seq": None, "changed_at_seq": None}
        history_compaction = context.get("history_compaction")
        if not isinstance(history_compaction, dict):
            history_compaction = None
        checkpoint_model_rows = self.projector._truncate_rows(
            list(checkpoint.get("raw_model_messages") or []),
            {"target_seq": int(target_seq), "to_seq": max(0, int(keep_to_seq))},
        )
        model_messages = [
            self._model_row_to_message_dict(row)
            for row in checkpoint_model_rows
            if isinstance(row, dict)
        ]
        return {
            "restore_model_messages": [item for item in model_messages if item],
            "restore_context_summary": dict(summary),
            "restore_history_compaction": dict(history_compaction) if history_compaction else None,
        }

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

    def commit_user_turn(
        self,
        session_id: str,
        content: str,
        *,
        ui_content: Optional[str] = None,
        ui_type: str = "user",
        operation_id: str = "",
        run_id: Optional[str] = None,
        model_payload: Optional[dict] = None,
    ) -> Optional[RuntimeEvent]:
        """Atomically commit the UI and model representations of one user turn."""
        op_id = str(operation_id or "").strip()
        with self.event_log.session_transaction(session_id):
            snapshot = self.snapshots.read(session_id)
            if int(snapshot.get("last_seq") or 0) != self.event_log.next_seq(session_id) - 1:
                snapshot = self.projector.project(self.event_log.read_all(session_id))
            if op_id and op_id in set(snapshot.get("operation_ids") or []):
                return None
            payload = dict(model_payload or {})
            payload.update({
                "role": "user",
                "content": str(content or ""),
                "ui_content": str(ui_content if ui_content is not None else content or ""),
                "ui_type": "user_steer" if ui_type == "user_steer" else "user",
            })
            if op_id:
                payload["operation_id"] = op_id
            event = self.event_log._append_unlocked(
                session_id,
                "user_turn_committed",
                payload=payload,
                run_id=run_id,
            )
            snapshot = self.projector.project_incremental(snapshot, event)
            self.snapshots.stamp_event_log(session_id, snapshot, self.event_log.event_path(session_id))
            self.snapshots.write(session_id, snapshot)
            return event

    def commit_assistant_final(
        self,
        session_id: str,
        content: str,
        *,
        operation_id: str = "",
        run_id: Optional[str] = None,
        model_payload: Optional[dict] = None,
    ) -> Optional[RuntimeEvent]:
        op_id = str(operation_id or "").strip()
        with self.event_log.session_transaction(session_id):
            snapshot = self.snapshots.read(session_id)
            if int(snapshot.get("last_seq") or 0) != self.event_log.next_seq(session_id) - 1:
                snapshot = self.projector.project(self.event_log.read_all(session_id))
            if op_id and op_id in set(snapshot.get("operation_ids") or []):
                return None
            payload = dict(model_payload or {})
            payload.update({"role": "assistant", "content": str(content or "")})
            if op_id:
                payload["operation_id"] = op_id
            event = self.event_log._append_unlocked(
                session_id,
                "assistant_final_committed",
                payload=payload,
                run_id=run_id,
            )
            snapshot = self.projector.project_incremental(snapshot, event)
            self.snapshots.stamp_event_log(session_id, snapshot, self.event_log.event_path(session_id))
            self.snapshots.write(session_id, snapshot)
            return event

    def replace_model_history(
        self,
        session_id: str,
        messages: list[dict],
        reason: str = "",
        *,
        summary: Optional[str] = None,
        source_seq: Optional[int] = None,
    ) -> RuntimeEvent:
        payload = {
            "messages": list(messages or []),
            "reason": reason,
        }
        if summary is not None:
            payload["summary"] = str(summary)
        if source_seq is not None:
            payload["source_seq"] = int(source_seq)
        return self._append_and_snapshot(session_id, "model_history_replaced", payload)

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
        t0 = time.perf_counter()
        with self.event_log.session_transaction(session_id):
            event = self.event_log._append_unlocked(session_id, event_type, payload=payload, run_id=run_id)
            t_after_append = time.perf_counter()
            snapshot = self.snapshots.read(session_id)
            if int(snapshot.get("last_seq") or 0) != int(event.seq) - 1:
                snapshot = self.projector.project(self.event_log.read_all(session_id))
            else:
                snapshot = self.projector.project_incremental(snapshot, event)
            t_after_project = time.perf_counter()
            self.snapshots.stamp_event_log(session_id, snapshot, self.event_log.event_path(session_id))
            self.snapshots.write(session_id, snapshot)
        t_after_write = time.perf_counter()
        logger.info(
            "rt2_append_and_snapshot session=%s event_type=%s run_id=%s "
            "step_append_ms=%s step_project_ms=%s step_snapshot_write_ms=%s total_ms=%s",
            session_id,
            event_type,
            str(run_id or ""),
            _rt2_step_ms(t0, t_after_append),
            _rt2_step_ms(t_after_append, t_after_project),
            _rt2_step_ms(t_after_project, t_after_write),
            _rt2_step_ms(t0, t_after_write),
        )
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
            if self._is_branch_runtime_metric_event(source_event):
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
                if self._is_projected_ui_runtime_metric(seed):
                    continue
                mirrored = mirror.mirror_ui_event(session_id, seed)
                if mirrored is None:
                    mirrored = mirror.append(session_id, "legacy_ui_event", self._copy_blob_refs(source_session_id, session_id, seed))
                count += 1 if mirrored is not None else 0
            return count
        except Exception:
            return 0

    def _seed_branch_model_history(self, session_id: str, source_session_id: str, branch_from_seq: int) -> int:
        if self._has_model_history(session_id):
            return 0
        messages = self._source_model_message_dicts_at_seq(source_session_id, int(branch_from_seq))
        if not messages:
            return 0
        self.replace_model_history(session_id, messages, reason="branch_model_seed")
        return len(messages)

    def _source_snapshot_at_seq(
        self,
        source_session_id: str,
        branch_from_seq: int,
        *,
        _seen: Optional[set[tuple[str, int]]] = None,
    ) -> dict:
        key = (str(source_session_id), int(branch_from_seq))
        seen = set(_seen or set())
        if key in seen:
            return self.projector.empty_snapshot()
        seen.add(key)
        origin = self._branch_origin_at_seq(source_session_id, int(branch_from_seq))
        if origin is not None and origin != key:
            return self._source_snapshot_at_seq(origin[0], origin[1], _seen=seen)
        events = []
        later_history_ops = []
        for source_event in self.event_log.iter_events(source_session_id):
            if int(source_event.seq) <= int(branch_from_seq):
                events.append(source_event)
            elif source_event.type in {"message_deleted", "message_rewritten"}:
                target = self.projector._int_or_none((source_event.payload or {}).get("target_seq"))
                if target is not None and target <= int(branch_from_seq):
                    later_history_ops.append(source_event)
        if not events:
            return self.projector.empty_snapshot()
        snapshot = self.projector.project(events)
        # A later semantic edit may target history before the branch anchor.
        # Apply those edits to the anchored snapshot without importing later
        # conversational turns, keeping UI/model branch seeds identical.
        for source_event in later_history_ops:
            self.projector.apply(snapshot, source_event)
        self.projector.finalize(snapshot)
        return snapshot

    def _source_model_message_dicts_at_seq(self, source_session_id: str, branch_from_seq: int) -> list[dict]:
        snapshot = self._source_snapshot_at_seq(source_session_id, branch_from_seq)
        return self._model_message_dicts_from_snapshot(snapshot)

    def _model_message_dicts_from_snapshot(self, snapshot: dict) -> list[dict]:
        rows = snapshot.get("model_messages") if isinstance(snapshot, dict) else None
        if not isinstance(rows, list):
            return []
        messages: list[dict] = []
        for row in rows:
            item = self._model_row_to_message_dict(row)
            if item:
                messages.append(item)
        return messages

    def _branch_origin_at_seq(self, source_session_id: str, branch_from_seq: int) -> Optional[tuple[str, int]]:
        branch_created = None
        branch_model_seed_seq = None
        target_event = None
        for event in self.event_log.iter_events(source_session_id):
            if int(event.seq) == int(branch_from_seq):
                target_event = event
            if event.type == "history_branch_created" and branch_created is None:
                branch_created = event
            if (
                event.type == "model_history_replaced"
                and str((event.payload or {}).get("reason") or "") == "branch_model_seed"
                and branch_model_seed_seq is None
            ):
                branch_model_seed_seq = int(event.seq)
        target_payload = dict(target_event.payload or {}) if target_event is not None else {}
        direct_session = str(target_payload.get("branch_source_session_id") or "").strip()
        direct_seq = self.projector._int_or_none(target_payload.get("branch_source_runtime_seq"))
        if direct_session and direct_seq is not None:
            return direct_session, int(direct_seq)
        if branch_created is None or branch_model_seed_seq is None or int(branch_from_seq) >= branch_model_seed_seq:
            return None
        parent_id = str((branch_created.payload or {}).get("source_session_id") or "").strip()
        parent_limit = self.projector._int_or_none((branch_created.payload or {}).get("branch_from_seq"))
        if not parent_id or parent_limit is None:
            return None
        try:
            from .ui_projection import RuntimeUiProjection

            projection = RuntimeUiProjection(self.event_log.root)
            child_events = [
                event for event in projection.read_ui_events_through_runtime_seq(source_session_id, int(branch_from_seq))
                if not self._is_projected_ui_runtime_metric(event)
            ]
            parent_events = [
                event for event in projection.read_ui_events_through_runtime_seq(parent_id, int(parent_limit))
                if not self._is_projected_ui_runtime_metric(event)
            ]
            if not child_events or len(child_events) > len(parent_events):
                return None
            mapped = parent_events[len(child_events) - 1]
            mapped_seq = self.projector._int_or_none(mapped.get("runtime_seq"))
            if mapped_seq is None:
                return None
            return parent_id, int(mapped_seq)
        except Exception:
            return None

    def _has_model_history(self, session_id: str) -> bool:
        snapshot = self.snapshots.read(session_id)
        rows = snapshot.get("raw_model_messages") if isinstance(snapshot, dict) else None
        return bool(rows)

    def _has_projectable_ui_events(self, session_id: str) -> bool:
        return any(
            self._is_branch_seed_event(event) and not self._is_branch_runtime_metric_event(event)
            for event in self.event_log.iter_events(session_id)
        )

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
    def _model_row_to_message_dict(row: dict) -> dict:
        if not isinstance(row, dict):
            return {}
        role = str(row.get("role") or "").strip()
        payload = row.get("payload")
        if not isinstance(payload, dict):
            payload = {}
        content = str(payload.get("content") or "")
        if role == "user":
            item = {"type": "user", "content": content}
            if isinstance(payload.get("metadata"), dict):
                item["metadata"] = dict(payload["metadata"])
            return item
        if role == "assistant":
            item = {"type": "assistant", "content": content}
            if isinstance(payload.get("tool_calls"), list):
                item["tool_calls"] = list(payload["tool_calls"])
            if isinstance(payload.get("metadata"), dict):
                item["metadata"] = dict(payload["metadata"])
            if isinstance(payload.get("additional_kwargs"), dict):
                item["additional_kwargs"] = dict(payload["additional_kwargs"])
            return item
        if role == "tool":
            return {
                "type": "tool",
                "content": content,
                "tool_call_id": str(payload.get("tool_call_id") or ""),
            }
        if role == "system":
            return {"type": "system", "content": content}
        return {}

    @classmethod
    def _is_branch_runtime_metric_event(cls, event: RuntimeEvent) -> bool:
        if event.type == "context_tokens":
            return True
        if event.type != "legacy_ui_event":
            return False
        return cls._is_projected_ui_runtime_metric(dict(event.payload or {}))

    @staticmethod
    def _is_projected_ui_runtime_metric(event: dict) -> bool:
        if not isinstance(event, dict):
            return False
        event_type = str(event.get("type") or "").strip()
        if event_type in {"cache_stats", "context_tokens"}:
            return True
        return False

    @staticmethod
    def _is_branch_seed_event(event: RuntimeEvent) -> bool:
        if event.type in {
            "message_user",
            "user_turn_committed",
            "assistant_final_committed",
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
