from __future__ import annotations

from typing import Iterable, Optional

from .event_schema import RuntimeEvent


TERMINAL_RUN_TYPES = {
    "run_finished": "finished",
    "run_failed": "failed",
    "run_interrupted": "interrupted",
}


class RuntimeProjector:
    """Rebuild a session snapshot from Runtime V2 events."""

    def empty_snapshot(self) -> dict:
        return {
            "session_id": None,
            "last_seq": 0,
            "updated_at": None,
            "runs": {},
            "active_runs": [],
            "messages": [],
            "raw_model_messages": [],
            "visible_messages": [],
            "model_messages": [],
            "subagents": {},
            "context": {},
            "todo": None,
            "history_ops": [],
            "legacy_observations": [],
            "visible_range": {},
            "model_window": {},
            "operation_ids": [],
        }

    def project(self, events: Iterable[RuntimeEvent]) -> dict:
        snapshot = self.empty_snapshot()
        for event in events:
            self.apply(snapshot, event)
        self.finalize(snapshot)
        return snapshot

    def project_incremental(self, snapshot: dict, event: RuntimeEvent) -> dict:
        if not snapshot:
            snapshot = self.empty_snapshot()
        self._ensure_shape(snapshot)
        self.apply(snapshot, event)
        self.finalize(snapshot)
        return snapshot

    def finalize(self, snapshot: dict) -> dict:
        self._ensure_shape(snapshot)
        self._rebuild_projected_messages(snapshot)
        snapshot["active_runs"] = [
            run for run in snapshot["runs"].values()
            if run.get("status") not in {"finished", "failed", "interrupted"}
        ]
        return snapshot

    def _ensure_shape(self, snapshot: dict) -> None:
        defaults = self.empty_snapshot()
        for key, value in defaults.items():
            if key not in snapshot:
                snapshot[key] = value

    def apply(self, snapshot: dict, event: RuntimeEvent) -> dict:
        self._ensure_shape(snapshot)
        operation_id = str((event.payload or {}).get("operation_id") or "").strip()
        if operation_id and operation_id in set(snapshot.get("operation_ids") or []):
            snapshot["last_seq"] = max(int(snapshot.get("last_seq") or 0), event.seq)
            snapshot["updated_at"] = event.timestamp
            return snapshot
        if operation_id:
            ids = [str(x) for x in snapshot.get("operation_ids") or [] if str(x)]
            ids.append(operation_id)
            snapshot["operation_ids"] = ids[-256:]
        snapshot["session_id"] = snapshot.get("session_id") or event.session_id
        snapshot["last_seq"] = max(int(snapshot.get("last_seq") or 0), event.seq)
        snapshot["updated_at"] = event.timestamp
        event_type = event.type

        if event_type == "session_meta":
            snapshot["session"] = dict(event.payload or {})
        elif event_type == "message_user":
            self._append_message(snapshot, event, "user")
        elif event_type == "user_turn_committed":
            self._append_message(snapshot, event, "user")
            self._append_model_message(snapshot, event)
        elif event_type == "assistant_final_committed":
            self._append_message(snapshot, event, "assistant")
            self._append_model_message(snapshot, event)
        elif event_type in {"message_assistant_delta", "message_assistant_final"}:
            self._append_or_update_assistant(snapshot, event)
        elif event_type in {"model_user", "model_assistant", "model_tool", "model_system"}:
            self._append_model_message(snapshot, event)
        elif event_type == "model_history_replaced":
            self._replace_model_messages(snapshot, event)
        elif event_type == "run_started":
            self._upsert_run(snapshot, event, "running")
        elif event_type == "run_heartbeat":
            self._upsert_run(snapshot, event, "running", heartbeat_only=True)
        elif event_type in TERMINAL_RUN_TYPES:
            self._upsert_run(snapshot, event, TERMINAL_RUN_TYPES[event_type])
        elif event_type.startswith("subagent_"):
            self._apply_subagent(snapshot, event)
        elif event_type == "context_tokens":
            payload = dict(event.payload or {})
            payload["updated_at"] = event.timestamp
            payload["seq"] = event.seq
            snapshot["context"]["tokens"] = payload
        elif event_type == "todo_updated":
            payload = dict(event.payload or {}) if isinstance(event.payload, dict) else {}
            if "todo" in payload and isinstance(payload.get("todo"), dict):
                todo = dict(payload.get("todo") or {})
            else:
                todo = payload
            todo["updated_at"] = event.timestamp
            todo["seq"] = event.seq
            snapshot["todo"] = todo
            snapshot["context"]["todo"] = todo
        elif event_type in {
            "message_deleted",
            "message_rewritten",
            "history_branch_created",
            "history_compacted",
            "context_summary_committed",
            "visible_range_changed",
            "model_window_changed",
        }:
            self._apply_history_op(snapshot, event)
        elif event_type.startswith("legacy_") and event_type.endswith("_observed"):
            self._apply_legacy_observation(snapshot, event)
        return snapshot

    def _append_message(self, snapshot: dict, event: RuntimeEvent, role: str) -> None:
        snapshot["messages"].append({
            "seq": event.seq,
            "timestamp": event.timestamp,
            "role": role,
            "run_id": event.run_id,
            "payload": dict(event.payload or {}),
        })

    def _append_or_update_assistant(self, snapshot: dict, event: RuntimeEvent) -> None:
        if event.type == "message_assistant_final":
            self._append_message(snapshot, event, "assistant")
            return
        delta = str((event.payload or {}).get("delta") or "")
        if not delta:
            return
        last = snapshot["messages"][-1] if snapshot["messages"] else None
        if last and last.get("role") == "assistant" and last.get("run_id") == event.run_id and last.get("streaming"):
            last["payload"]["content"] = str(last["payload"].get("content") or "") + delta
            last["seq"] = event.seq
            last["timestamp"] = event.timestamp
        else:
            snapshot["messages"].append({
                "seq": event.seq,
                "timestamp": event.timestamp,
                "role": "assistant",
                "run_id": event.run_id,
                "streaming": True,
                "payload": {"content": delta},
            })

    def _append_model_message(self, snapshot: dict, event: RuntimeEvent) -> None:
        payload = dict(event.payload or {})
        role = str(payload.get("role") or "").strip()
        if not role:
            role = {
                "model_user": "user",
                "model_assistant": "assistant",
                "model_tool": "tool",
                "model_system": "system",
            }.get(event.type, "")
        if not role:
            return
        row = {
            "seq": event.seq,
            "timestamp": event.timestamp,
            "role": role,
            "run_id": event.run_id,
            "payload": payload,
        }
        row["payload"]["role"] = role
        snapshot["raw_model_messages"].append(row)

    def _replace_model_messages(self, snapshot: dict, event: RuntimeEvent) -> None:
        payload = dict(event.payload or {})
        messages = payload.get("messages")
        if not isinstance(messages, list):
            return
        rows = []
        for index, item in enumerate(messages):
            if not isinstance(item, dict):
                continue
            msg_type = str(item.get("type") or item.get("role") or "").strip()
            role = {
                "human": "user",
                "llm": "assistant",
                "ai": "assistant",
                "agent": "assistant",
            }.get(msg_type, msg_type)
            if role not in {"user", "assistant", "tool", "system"}:
                continue
            msg_payload = dict(item)
            msg_payload["role"] = role
            msg_payload["content"] = str(item.get("content") or "")
            rows.append({
                "seq": event.seq,
                "timestamp": event.timestamp,
                "role": role,
                "run_id": event.run_id,
                "payload": msg_payload,
                "replacement_index": index,
                "replaced_by_seq": event.seq,
            })
        # A replacement is the caller's canonical, already-reconciled model
        # context (compression, branch seeding, or a post-rewrite run).  Do
        # not apply an older visible-range operation a second time: its event
        # sequence cannot describe the individual rows in this new snapshot.
        snapshot["raw_model_messages"] = rows
        if "summary" in payload:
            snapshot["context"]["summary"] = {
                "summary": str(payload.get("summary") or ""),
                "source_seq": payload.get("source_seq"),
                "changed_at_seq": event.seq,
            }

    def _apply_history_op(self, snapshot: dict, event: RuntimeEvent) -> None:
        payload = dict(event.payload or {})
        row = {
            "seq": event.seq,
            "timestamp": event.timestamp,
            "type": event.type,
            "payload": payload,
        }
        snapshot["history_ops"].append(row)
        if event.type in {"message_deleted", "message_rewritten"}:
            self._apply_message_op_to_model(snapshot, event)
        if event.type == "visible_range_changed":
            snapshot["visible_range"] = {
                "from_seq": payload.get("from_seq"),
                "to_seq": payload.get("to_seq"),
                "changed_at_seq": event.seq,
                "reason": payload.get("reason") or "",
            }
            if payload.get("apply_model") or payload.get("reason") == "runtime_v2_truncate":
                self._truncate_snapshot_model_rows(snapshot, payload)
                snapshot["context"]["model_truncate"] = {
                    "changed_at_seq": event.seq,
                    "target_seq": payload.get("target_seq"),
                    "to_seq": payload.get("to_seq"),
                    "reason": payload.get("reason") or "",
                }
        elif event.type == "model_window_changed":
            snapshot["model_window"] = {
                "from_seq": payload.get("from_seq"),
                "to_seq": payload.get("to_seq"),
                "changed_at_seq": event.seq,
                "reason": payload.get("reason") or "",
            }
            self._truncate_snapshot_model_rows(snapshot, payload)
        elif event.type == "history_compacted":
            snapshot["context"]["history_compaction"] = {
                "summary": payload.get("summary") or "",
                "compacted_before_seq": payload.get("compacted_before_seq"),
                "changed_at_seq": event.seq,
                "reason": payload.get("reason") or "",
            }
        elif event.type == "context_summary_committed":
            snapshot["context"]["summary"] = {
                "summary": payload.get("summary") or "",
                "source_seq": payload.get("source_seq"),
                "changed_at_seq": event.seq,
            }

    def _apply_legacy_observation(self, snapshot: dict, event: RuntimeEvent) -> None:
        snapshot["legacy_observations"].append({
            "seq": event.seq,
            "timestamp": event.timestamp,
            "type": event.type,
            "payload": dict(event.payload or {}),
        })

    def _rebuild_projected_messages(self, snapshot: dict) -> None:
        deleted = set()
        rewrites = {}
        compacted_before_seq = None
        compaction = (snapshot.get("context") or {}).get("history_compaction") or {}
        if compaction.get("compacted_before_seq") is not None:
            try:
                compacted_before_seq = int(compaction.get("compacted_before_seq"))
            except (TypeError, ValueError):
                compacted_before_seq = None

        for op in snapshot.get("history_ops") or []:
            payload = op.get("payload") or {}
            if op.get("type") == "message_deleted":
                target = self._int_or_none(payload.get("target_seq"))
                if target is not None:
                    deleted.add(target)
            elif op.get("type") == "message_rewritten":
                target = self._int_or_none(payload.get("target_seq"))
                if target is not None:
                    rewrite = dict(payload)
                    rewrite["changed_at_seq"] = op.get("seq")
                    rewrites[target] = rewrite

        projected = []
        for message in snapshot.get("messages") or []:
            seq = self._int_or_none(message.get("seq"))
            if seq is None or seq in deleted:
                continue
            next_message = self._copy_message(message)
            rewrite = rewrites.get(seq)
            if rewrite is not None:
                next_message["payload"] = dict(next_message.get("payload") or {})
                next_message["payload"]["content"] = rewrite.get("content") or ""
                next_message["rewritten_by_seq"] = rewrite.get("changed_at_seq")
                next_message["rewritten"] = True
            projected.append(next_message)

        for op in snapshot.get("history_ops") or []:
            if op.get("type") != "visible_range_changed":
                continue
            payload = op.get("payload") or {}
            projected = self._truncate_rows(
                projected,
                payload,
                effective_before_seq=self._int_or_none(op.get("seq")),
            )

        raw_model_messages = snapshot.get("raw_model_messages") or []
        model_source = raw_model_messages if isinstance(raw_model_messages, list) else []
        context = snapshot.get("context")
        if not isinstance(context, dict):
            context = {}
            snapshot["context"] = context
        if model_source:
            context.pop("model_history_missing", None)
        elif projected:
            context["model_history_missing"] = {
                "reason": "raw_model_messages_absent",
                "visible_message_count": len(projected),
            }
        model_messages = []
        for message in model_source:
            seq = self._int_or_none(message.get("seq"))
            if seq is None:
                continue
            if compacted_before_seq is not None and seq < compacted_before_seq:
                continue
            model_messages.append(self._copy_message(message))

        if compacted_before_seq is not None and compaction.get("summary"):
            model_messages.insert(0, {
                "seq": compacted_before_seq,
                "role": "system",
                "payload": {
                    "content": str(compaction.get("summary") or ""),
                    "kind": "history_compaction",
                },
            })

        snapshot["visible_messages"] = projected
        snapshot["model_messages"] = model_messages

    def _upsert_run(self, snapshot: dict, event: RuntimeEvent, status: str, heartbeat_only: bool = False) -> None:
        run_id = self._event_run_id(event)
        if not run_id:
            return
        runs = snapshot["runs"]
        run = runs.get(run_id)
        terminal_statuses = {"finished", "failed", "interrupted"}
        if status == "running" and not heartbeat_only:
            for existing_id, existing in list(runs.items()):
                if existing_id == run_id or not isinstance(existing, dict):
                    continue
                if existing.get("session_id") != event.session_id:
                    continue
                if existing.get("status") in terminal_statuses:
                    continue
                existing["status"] = "interrupted"
                existing["finished_at"] = event.timestamp
                existing["heartbeat_at"] = event.timestamp
                existing["error"] = existing.get("error") or "superseded by a newer run"
        if not run:
            run = {
                "run_id": run_id,
                "session_id": event.session_id,
                "status": "running",
                "started_at": event.timestamp,
                "heartbeat_at": event.timestamp,
                "finished_at": None,
                "error": None,
                "started_seq": event.seq,
            }
            runs[run_id] = run
        if run.get("status") in terminal_statuses and status not in terminal_statuses:
            return
        run["heartbeat_at"] = event.timestamp
        run["heartbeat_seq"] = event.seq
        if not heartbeat_only:
            run["status"] = status
        if status in terminal_statuses:
            run["finished_at"] = event.timestamp
            run["finished_seq"] = event.seq
        if status == "failed":
            run["error"] = str((event.payload or {}).get("error") or "")

    def _apply_subagent(self, snapshot: dict, event: RuntimeEvent) -> None:
        payload = event.payload or {}
        agent_id = str(payload.get("agent_id") or payload.get("id") or "")
        if not agent_id:
            return
        state = snapshot["subagents"].get(agent_id) or {
            "agent_id": agent_id,
            "status": "running",
            "has_final": False,
            "result_consumed": False,
            "started_at": event.timestamp,
            "finished_at": None,
        }
        if event.type == "subagent_finished":
            state["status"] = "finished" if payload.get("has_final", True) else "failed"
            state["has_final"] = bool(payload.get("has_final", True))
            state["finished_at"] = event.timestamp
        elif event.type == "subagent_failed":
            state["status"] = "failed"
            state["finished_at"] = event.timestamp
        elif event.type == "subagent_result_consumed":
            state["result_consumed"] = True
        else:
            state["status"] = state.get("status") or "running"
        state.update({k: v for k, v in payload.items() if k not in {"status"}})
        snapshot["subagents"][agent_id] = state

    @staticmethod
    def _event_run_id(event: RuntimeEvent) -> Optional[str]:
        if event.run_id:
            return event.run_id
        payload = event.payload or {}
        run = payload.get("run")
        if isinstance(run, dict) and run.get("run_id"):
            return str(run.get("run_id"))
        if payload.get("run_id"):
            return str(payload.get("run_id"))
        return None

    @staticmethod
    def _int_or_none(value) -> Optional[int]:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _seq_in_range(cls, seq: int, range_payload: dict) -> bool:
        """Return True if a row with ``seq`` should be kept after applying ``range_payload``.

        The retain region is defined by optional boundaries:

        - ``from_seq``: lower bound (inclusive). Rows with ``seq < from_seq``
          are dropped.
        - ``to_seq``: upper bound (inclusive). Rows with ``seq > to_seq`` are
          dropped.
        - ``target_seq``: an audit anchor identifying the clicked UI event.
          It does not change the retained range.  ``to_seq`` is the sole
          inclusive upper boundary, so delete/rewrite/truncate all have the
          same prefix semantics in the UI and model projections.
        """
        if not range_payload:
            return True
        from_seq = cls._int_or_none(range_payload.get("from_seq"))
        to_seq = cls._int_or_none(range_payload.get("to_seq"))
        if from_seq is not None and seq < from_seq:
            return False
        if to_seq is not None and seq > to_seq:
            return False
        return True

    @classmethod
    def _snapshot_should_keep(cls, row: dict, payload: dict) -> bool:
        """Decide whether a ``model_history_replaced`` snapshot row is kept.

        Snapshot rows share one ``seq`` (the event seq) but represent history
        *up to* that event, marked by ``replaced_by_seq``. A rewrite/delete
        truncate with ``target_seq`` drops visible history at and after
        ``target_seq`` while keeping everything before it. A snapshot whose
        ``replaced_by_seq < target_seq`` contains only pre-target history and
        must be kept entirely — even though its event seq may numerically fall
        between ``to_seq`` and ``target_seq``, because the snapshot captures
        the full history at the moment *before* the truncated run started.
        """
        target_seq = cls._int_or_none(payload.get("target_seq"))
        replaced_by = cls._int_or_none(row.get("replaced_by_seq"))
        if target_seq is not None and replaced_by is not None and replaced_by < target_seq:
            return True
        judge_seq = replaced_by if replaced_by is not None else cls._int_or_none(row.get("seq"))
        return cls._seq_in_range(judge_seq, payload)

    def _truncate_snapshot_rows(self, snapshot: dict, payload: dict) -> None:
        snapshot["messages"] = self._truncate_rows(snapshot.get("messages") or [], payload)

    def _truncate_snapshot_model_rows(self, snapshot: dict, payload: dict) -> None:
        snapshot["raw_model_messages"] = self._truncate_rows(
            snapshot.get("raw_model_messages") or [],
            payload,
        )

    @classmethod
    def _truncate_rows(cls, rows: list, payload: dict, effective_before_seq: Optional[int] = None) -> list:
        if payload.get("to_ui_index") is not None:
            try:
                return list(rows or [])[:max(0, int(payload.get("to_ui_index")))]
            except (TypeError, ValueError):
                return list(rows or [])
        out = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            seq = cls._int_or_none(row.get("seq"))
            if seq is None:
                continue
            # A history operation is chronological, not a permanent global
            # filter. Rows appended after the operation must remain visible.
            if effective_before_seq is not None and seq > effective_before_seq:
                out.append(row)
                continue
            # model_history_replaced snapshot rows are judged as a whole by
            # their ``replaced_by_seq`` so a rewrite/delete truncate does not
            # erase pre-existing history (see ``_snapshot_should_keep``).
            if row.get("replaced_by_seq") is not None:
                if cls._snapshot_should_keep(row, payload):
                    out.append(row)
            elif cls._seq_in_range(seq, payload):
                out.append(row)
        return out

    def _apply_message_op_to_model(self, snapshot: dict, event: RuntimeEvent) -> None:
        """Keep standalone delete/rewrite operations aligned with model context.

        UI and model events have independent seq values, so correlate the
        targeted visible message by role/content and change the latest matching
        model row. Canonical truncate/replace callers still take precedence.
        """
        payload = dict(event.payload or {})
        target_seq = self._int_or_none(payload.get("target_seq"))
        if target_seq is None:
            return
        target = None
        for message in snapshot.get("messages") or []:
            if self._int_or_none((message or {}).get("seq")) == target_seq:
                target = message
                break
        if not isinstance(target, dict):
            return
        role = str(target.get("role") or "")
        content = str((target.get("payload") or {}).get("content") or "")
        rows = list(snapshot.get("raw_model_messages") or [])
        match_index = None
        for index in range(len(rows) - 1, -1, -1):
            row = rows[index]
            if not isinstance(row, dict) or str(row.get("role") or "") != role:
                continue
            if str((row.get("payload") or {}).get("content") or "") == content:
                match_index = index
                break
        if match_index is None:
            return
        if event.type == "message_deleted":
            rows.pop(match_index)
        else:
            changed = self._copy_message(rows[match_index])
            changed["payload"]["content"] = str(payload.get("content") or "")
            changed["rewritten_by_seq"] = event.seq
            rows[match_index] = changed
        snapshot["raw_model_messages"] = rows

    @staticmethod
    def _copy_message(message: dict) -> dict:
        copied = dict(message)
        copied["payload"] = dict(copied.get("payload") or {})
        return copied
