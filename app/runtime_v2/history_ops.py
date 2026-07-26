from __future__ import annotations

import logging
import shutil
import time
from pathlib import Path
from typing import Callable, Optional

from .event_log import SessionEventLog
from .event_schema import RuntimeEvent
from .projector import RuntimeProjector
from .snapshot_store import SnapshotStore

logger = logging.getLogger(__name__)


HOOK_EVENT_TYPES = {
    "hook_started",
    "hook_progress",
    "hook_finished",
    "hook_failed",
    "hook_blocked",
    "hook_timed_out",
    "hook_input_modified",
}

PLUGIN_EVENT_TYPES = {"plugin_state_changed", "plugin_reloaded"}

_GOAL_CHECKPOINT_INTERVAL = 64
_GOAL_APPEND_LIMITS = {
    "accounted_judge_run_ids": 512,
    "accounted_run_ids": 512,
    "accounted_usage_ids": 2048,
}


def _rt2_step_ms(start: float, end: Optional[float] = None) -> int:
    if end is None:
        end = time.perf_counter()
    return int(max(0.0, (end - start) * 1000.0))


class RuntimeHistoryOps:
    """Append-only history operations for the V2 path.

    These operations do not rewrite events.jsonl. They append semantic events
    and let RuntimeProjector calculate the visible/model history.
    """

    def __init__(
        self,
        sessions_dir: str | Path,
        path_resolver: Optional[Callable[[str], str | Path]] = None,
        transaction_timeout_seconds: Optional[float] = None,
    ):
        self._path_resolver = path_resolver
        self._transaction_timeout_seconds = transaction_timeout_seconds
        self.event_log = SessionEventLog(sessions_dir, path_resolver=path_resolver)
        self.projector = RuntimeProjector()
        self.snapshots = SnapshotStore(sessions_dir, path_resolver=path_resolver)

    def _session_transaction(self, session_id: str):
        return self.event_log.session_transaction(
            session_id,
            timeout_seconds=self._transaction_timeout_seconds,
        )

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
        source_tokens = source_context.get("tokens") if isinstance(source_context, dict) else None
        if not isinstance(source_tokens, dict):
            source_tokens = None
        source_todo = source_checkpoint.get("todo") if isinstance(source_checkpoint, dict) else None
        if not isinstance(source_todo, dict):
            source_todo = None
        t_after_model = time.perf_counter()
        seed_rows = self._branch_ui_seed_rows(session_id, source_session_id, ui_events)
        t_after_map = time.perf_counter()

        with self._session_transaction(session_id):
            existing_events = self.event_log.read_all(session_id)
            snapshot = self.snapshots.read(session_id)
            if int(snapshot.get("last_seq") or 0) != max((int(ev.seq) for ev in existing_events), default=0):
                snapshot = self.projector.project(existing_events)
            has_ui = any(
                self._is_branch_seed_event(event) and not self._is_branch_runtime_metric_event(event)
                for event in existing_events
            )
            has_model = bool(snapshot.get("raw_model_messages") if isinstance(snapshot, dict) else None)
            existing_context = snapshot.get("context") if isinstance(snapshot, dict) else None
            has_tokens = bool(existing_context.get("tokens")) if isinstance(existing_context, dict) else False
            has_todo = isinstance(snapshot.get("todo"), dict) if isinstance(snapshot, dict) else False
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
            if not has_tokens and source_tokens:
                token_payload = dict(source_tokens)
                token_payload.pop("seq", None)
                token_payload.pop("updated_at", None)
                token_payload["inherited_from_session_id"] = source_session_id
                token_payload["inherited_from_runtime_seq"] = branch_from_seq
                rows.append({
                    "type": "context_tokens",
                    "payload": token_payload,
                })
            if not has_todo and source_todo is not None:
                todo_payload = dict(source_todo)
                todo_payload.pop("seq", None)
                todo_payload.pop("updated_at", None)
                rows.append({
                    "type": "todo_updated",
                    "payload": todo_payload,
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

    def create_reference_branch(
        self,
        session_id: str,
        source_session_id: str,
        branch_from_seq: int,
        name: str = "",
    ) -> RuntimeEvent:
        """Create an immutable-prefix branch without materializing model history.

        RuntimeModelProjection resolves the source prefix at ``branch_from_seq``
        and appends this session's local tail.  A later model-history
        replacement materializes the effective history and detaches the
        reference, which keeps compaction/rewrite semantics straightforward.
        """
        reference = self._append_and_snapshot(
            session_id,
            "history_branch_created",
            {
                "source_session_id": str(source_session_id),
                "branch_from_seq": int(branch_from_seq),
                "name": str(name or ""),
                "reference_mode": "immutable_model_prefix",
            },
        )
        source = self._source_snapshot_at_seq(source_session_id, int(branch_from_seq))
        context = source.get("context") if isinstance(source, dict) else {}
        summary = context.get("summary") if isinstance(context, dict) else {}
        summary_text = (
            str(summary.get("summary") or "")
            if isinstance(summary, dict)
            else ""
        )
        if summary_text:
            self.commit_context_summary(
                session_id,
                summary_text,
                source_seq=(
                    summary.get("source_seq")
                    if isinstance(summary, dict)
                    and summary.get("source_seq") is not None
                    else branch_from_seq
                ),
            )
        tokens = context.get("tokens") if isinstance(context, dict) else None
        if isinstance(tokens, dict) and tokens:
            inherited_tokens = dict(tokens)
            inherited_tokens.pop("seq", None)
            inherited_tokens.pop("updated_at", None)
            inherited_tokens["inherited_from_session_id"] = source_session_id
            inherited_tokens["inherited_from_runtime_seq"] = int(branch_from_seq)
            self.checkpoint_context_tokens(session_id, inherited_tokens)
        todo = source.get("todo") if isinstance(source, dict) else None
        if isinstance(todo, dict):
            inherited_todo = dict(todo)
            inherited_todo.pop("seq", None)
            inherited_todo.pop("updated_at", None)
            self.update_todo(session_id, inherited_todo)
        return reference

    def _branch_ui_events(self, source_session_id: str, branch_from_seq: int) -> list[dict]:
        from .ui_projection import RuntimeUiProjection

        projection = RuntimeUiProjection(
            self.event_log.root,
            path_resolver=self._path_resolver,
        )
        return projection.read_ui_events_through_runtime_seq(source_session_id, branch_from_seq)

    def _branch_ui_seed_rows(
        self,
        session_id: str,
        source_session_id: str,
        source_events: list[dict],
    ) -> list[dict]:
        from .mirror import RuntimeMirror

        mirror = RuntimeMirror(
            self.event_log.root,
            path_resolver=self._path_resolver,
        )
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
                    "type": "ui_event",
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
        mirror = RuntimeMirror(
            self.event_log.root,
            path_resolver=self._path_resolver,
        )
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

    def checkpoint_context_tokens(self, session_id: str, tokens: dict) -> RuntimeEvent:
        """Persist the current request-size checkpoint after a context rewrite."""
        payload = dict(tokens or {})
        payload.pop("ephemeral", None)
        payload["stale"] = False
        return self._append_and_snapshot(session_id, "context_tokens", payload)

    def update_goal(self, session_id: str, goal: dict, event_type: str = "goal_updated") -> RuntimeEvent:
        if not str(event_type or "").startswith("goal_"):
            raise ValueError("goal event_type must start with goal_")
        return self._append_and_snapshot(session_id, str(event_type), dict(goal or {}))

    @staticmethod
    def _compact_goal_payload(current: Optional[dict], goal: dict) -> dict:
        """Encode frequent Goal accounting writes as replayable field deltas.

        The snapshot store still receives the complete projected Goal.  Full
        events are retained periodically so event-log recovery never needs to
        replay an unbounded chain of deltas.
        """

        previous = dict(current or {})
        persisted = dict(goal or {})
        version = max(0, int(persisted.get("version") or 0))
        if not previous or version % _GOAL_CHECKPOINT_INTERVAL == 0:
            return persisted

        changed: dict = {}
        appended: dict = {}
        removed = []
        for key in sorted(set(previous) | set(persisted)):
            if key == "seq" or previous.get(key) == persisted.get(key):
                continue
            if key not in persisted:
                removed.append(key)
                continue
            limit = _GOAL_APPEND_LIMITS.get(key)
            old_value = previous.get(key)
            new_value = persisted.get(key)
            if limit and isinstance(old_value, list) and isinstance(new_value, list):
                additions = new_value[-1:] if new_value else []
                if additions and (old_value + additions)[-limit:] == new_value:
                    appended[key] = additions
                    continue
            changed[key] = new_value

        payload = {
            "_goal_delta": True,
            "id": persisted.get("id"),
            "set": changed,
        }
        if appended:
            payload["append"] = appended
        if removed:
            payload["unset"] = removed
        return payload

    def mutate_goal(
        self,
        session_id: str,
        mutator: Callable[[Optional[dict]], tuple[str, dict, dict]],
        *,
        run_id: Optional[str] = None,
    ) -> tuple[Optional[RuntimeEvent], dict]:
        """Atomically read, mutate, append, and project one Goal state change."""

        with self._session_transaction(session_id):
            snapshot = self.snapshots.read(session_id)
            latest_seq = self.event_log.next_seq(session_id) - 1
            if int(snapshot.get("last_seq") or 0) != int(latest_seq):
                snapshot = self.projector.project(self.event_log.read_all(session_id))
            current = snapshot.get("goal") if isinstance(snapshot, dict) else None
            current_goal = dict(current) if isinstance(current, dict) else None
            event_type, persisted_goal, response_goal = mutator(current_goal)
            normalized_type = str(event_type or "").strip()
            if not normalized_type:
                return None, dict(response_goal or persisted_goal or current_goal or {})
            if not normalized_type.startswith("goal_"):
                raise ValueError("goal event_type must start with goal_")
            if not isinstance(persisted_goal, dict) or not persisted_goal.get("id"):
                raise ValueError("goal mutation must return a persisted goal with an id")
            event_payload = dict(persisted_goal)
            if normalized_type in {"goal_usage_updated", "goal_judge_evaluated"}:
                event_payload = self._compact_goal_payload(current_goal, persisted_goal)
            event = self.event_log._append_unlocked(
                session_id,
                normalized_type,
                payload=event_payload,
                run_id=run_id,
            )
            snapshot = self.projector.project_incremental(snapshot, event)
            self.snapshots.stamp_event_log(session_id, snapshot, self.event_log.event_path(session_id))
            self.snapshots.write(session_id, snapshot)
            return event, dict(response_goal or persisted_goal)

    def append_hook_event(
        self,
        session_id: str,
        event_type: str,
        payload: Optional[dict] = None,
        run_id: Optional[str] = None,
        **fields,
    ) -> RuntimeEvent:
        """Append a supported hook audit event and refresh the snapshot."""
        normalized_type = str(event_type or "").strip()
        if normalized_type not in HOOK_EVENT_TYPES:
            raise ValueError(f"unsupported hook event_type: {normalized_type}")
        data = dict(payload or {})
        data.update(fields)
        return self._append_and_snapshot(
            session_id,
            normalized_type,
            data,
            run_id=run_id,
        )

    def update_plugin_state(
        self,
        session_id: str,
        plugin_id: str,
        state=None,
        event_type: str = "plugin_state_changed",
        run_id: Optional[str] = None,
        **fields,
    ) -> RuntimeEvent:
        """Merge a plugin's latest state into the Runtime V2 projection."""
        normalized_type = str(event_type or "").strip()
        if normalized_type not in PLUGIN_EVENT_TYPES:
            raise ValueError(f"unsupported plugin event_type: {normalized_type}")
        normalized_id = str(plugin_id or "").strip()
        if not normalized_id:
            raise ValueError("plugin_id is required")
        data = dict(fields or {})
        data["plugin_id"] = normalized_id
        if state is not None:
            data["state"] = dict(state) if isinstance(state, dict) else state
        return self._append_and_snapshot(
            session_id,
            normalized_type,
            data,
            run_id=run_id,
        )

    def delete_subagent(
        self,
        session_id: str,
        agent_id: str,
        *,
        descendant_count: int = 0,
        virtual: bool = False,
    ) -> RuntimeEvent:
        return self._append_and_snapshot(session_id, "subagent_deleted", {
            "agent_id": str(agent_id or "").strip(),
            "descendant_count": max(0, int(descendant_count)),
            "virtual": bool(virtual),
        })

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
        context_tokens = context.get("tokens")
        if not isinstance(context_tokens, dict):
            context_tokens = None
        todo = checkpoint.get("todo") if isinstance(checkpoint, dict) else None
        if not isinstance(todo, dict):
            todo = None
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
            "restore_context_tokens": dict(context_tokens) if context_tokens else None,
            "restore_todo": dict(todo) if todo is not None else None,
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
        with self._session_transaction(session_id):
            snapshot = self.snapshots.read_for_update(session_id)
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
            self.snapshots.write_checkpointed(session_id, snapshot)
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
        with self._session_transaction(session_id):
            snapshot = self.snapshots.read_for_update(session_id)
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
            self.snapshots.write_checkpointed(session_id, snapshot)
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
        logger.info(
            "rt2_append_and_snapshot_started session=%s event_type=%s run_id=%s stage=wait_transaction",
            session_id,
            event_type,
            str(run_id or ""),
        )
        with self._session_transaction(session_id):
            logger.info(
                "rt2_append_and_snapshot_progress session=%s event_type=%s run_id=%s stage=transaction_acquired",
                session_id,
                event_type,
                str(run_id or ""),
            )
            event = self.event_log._append_unlocked(session_id, event_type, payload=payload, run_id=run_id)
            t_after_append = time.perf_counter()
            logger.info(
                "rt2_append_and_snapshot_progress session=%s event_type=%s run_id=%s stage=event_appended seq=%s",
                session_id,
                event_type,
                str(run_id or ""),
                event.seq,
            )
            snapshot = self.snapshots.read_for_update(session_id)
            if int(snapshot.get("last_seq") or 0) != int(event.seq) - 1:
                logger.info(
                    "rt2_append_and_snapshot_progress session=%s event_type=%s run_id=%s stage=full_projection_started",
                    session_id,
                    event_type,
                    str(run_id or ""),
                )
                snapshot = self.projector.project(self.event_log.read_all(session_id))
            else:
                snapshot = self.projector.project_incremental(snapshot, event)
            t_after_project = time.perf_counter()
            logger.info(
                "rt2_append_and_snapshot_progress session=%s event_type=%s run_id=%s stage=snapshot_write_started",
                session_id,
                event_type,
                str(run_id or ""),
            )
            self.snapshots.stamp_event_log(session_id, snapshot, self.event_log.event_path(session_id))
            self.snapshots.write_checkpointed(session_id, snapshot)
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
        logger.info(
            "rt2_append_and_snapshot_completed session=%s event_type=%s run_id=%s seq=%s",
            session_id,
            event_type,
            str(run_id or ""),
            event.seq,
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

            projection = RuntimeUiProjection(
                self.event_log.root,
                path_resolver=self._path_resolver,
            )
            end_index = projection.runtime_seq_to_ui_end_index(source_session_id, int(branch_from_seq))
            if end_index is None:
                return 0
            source_events = projection.read_ui_events(source_session_id)[:max(0, int(end_index))]
            if not source_events:
                return 0
            mirror = RuntimeMirror(
                self.event_log.root,
                path_resolver=self._path_resolver,
            )
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
                    mirrored = mirror.append(session_id, "ui_event", self._copy_blob_refs(source_session_id, session_id, seed))
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
            snapshot = self._source_snapshot_at_seq(origin[0], origin[1], _seen=seen)
            # A branch can rewrite/delete one of its inherited seed events.
            # The clicked seed retains its origin marker, so translate local
            # semantic edits back to the origin seq before producing another
            # branch checkpoint. Otherwise UI shows the edit while model
            # context silently reverts to the ancestor value.
            source_events = list(self.event_log.iter_events(source_session_id))
            by_seq = {int(event.seq): event for event in source_events}
            for local_op in source_events:
                if local_op.type not in {"message_deleted", "message_rewritten"}:
                    continue
                local_target = self.projector._int_or_none((local_op.payload or {}).get("target_seq"))
                if local_target is None or local_target > int(branch_from_seq):
                    continue
                target_event = by_seq.get(int(local_target))
                target_payload = dict(target_event.payload or {}) if target_event is not None else {}
                mapped_session = str(target_payload.get("branch_source_session_id") or "").strip()
                mapped_seq = self.projector._int_or_none(target_payload.get("branch_source_runtime_seq"))
                if mapped_session != origin[0] or mapped_seq is None or int(mapped_seq) > int(origin[1]):
                    continue
                translated_payload = dict(local_op.payload or {})
                translated_payload["target_seq"] = int(mapped_seq)
                self.projector.apply(snapshot, RuntimeEvent(
                    seq=int(local_op.seq),
                    type=local_op.type,
                    session_id=origin[0],
                    timestamp=local_op.timestamp,
                    run_id=local_op.run_id,
                    payload=translated_payload,
                ))
            self.projector.finalize(snapshot)
            return snapshot
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

            projection = RuntimeUiProjection(
                self.event_log.root,
                path_resolver=self._path_resolver,
            )
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
        if event.type not in {"ui_event", "legacy_ui_event"}:
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
            "ui_event",
            "legacy_ui_event",
        }:
            return True
        return event.type.startswith("subagent_")
