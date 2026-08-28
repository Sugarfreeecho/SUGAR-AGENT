from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .config import runtime_v2_enabled
from .event_log import SessionEventLog
from .history_ops import RuntimeHistoryOps
from .projector import RuntimeProjector
from .snapshot_store import SnapshotStore


def strip_responses_continuation_from_message(message: Dict[str, Any]) -> Dict[str, Any]:
    """Copy a branch seed while retaining replay facts but no server anchor."""
    item = copy.deepcopy(dict(message or {}))

    def replay_only(state: Dict[str, Any]) -> Dict[str, Any]:
        replay_state = dict(state)
        for key in (
            "continuation_anchor",
            "response_id",
            "stateful_supported",
            "fallback_reason",
            "responses_mode",
            "full_replay_reason",
        ):
            replay_state.pop(key, None)
        replay_state["state_mode"] = "stateless"
        return replay_state

    top_level_state = item.get("_myagent_responses")
    if isinstance(top_level_state, dict):
        item["_myagent_responses"] = replay_only(top_level_state)
    additional = item.get("additional_kwargs")
    if not isinstance(additional, dict):
        return item
    state = additional.get("_myagent_responses")
    if not isinstance(state, dict):
        return item
    additional = dict(additional)
    additional["_myagent_responses"] = replay_only(state)
    item["additional_kwargs"] = additional
    return item


class RuntimeModelProjection:
    """Read model-facing messages from the Runtime V2 snapshot."""

    def __init__(
        self,
        sessions_dir: str | Path,
        path_resolver: Optional[Callable[[str], str | Path]] = None,
    ):
        self.sessions_dir = Path(sessions_dir)
        self._path_resolver = path_resolver
        self.snapshots = SnapshotStore(sessions_dir, path_resolver=path_resolver)
        self.event_log = SessionEventLog(sessions_dir, path_resolver=path_resolver)
        self.projector = RuntimeProjector()

    def read_message_dicts(self, session_id: str) -> List[Dict[str, Any]]:
        if not runtime_v2_enabled():
            return []
        return list(self.read_run_bootstrap(session_id).get("messages") or [])

    def read_run_bootstrap(self, session_id: str) -> Dict[str, Any]:
        """Read model history and run context from one snapshot view."""
        if not runtime_v2_enabled():
            return {
                "messages": [],
                "context_summary": "",
                "history_generation": 0,
            }
        snapshot = self.snapshots.read_consistent_view(
            session_id,
            self.event_log,
            self.projector,
        )
        messages = self._messages_with_snapshot_branch(
            snapshot,
            seen={(str(session_id), None)},
        )
        context = snapshot.get("context") if isinstance(snapshot, dict) else {}
        summary = context.get("summary") if isinstance(context, dict) else {}
        return {
            "messages": messages,
            "context_summary": (
                str(summary.get("summary") or "")
                if isinstance(summary, dict)
                else ""
            ),
            "history_generation": (
                int(snapshot.get("model_history_generation") or 0)
                if isinstance(snapshot, dict)
                else 0
            ),
        }

    def read_request_context(self, session_id: str) -> Dict[str, Any]:
        """Return deterministic transport identity derived from Runtime V2."""
        if not runtime_v2_enabled():
            return {
                "session_id": str(session_id or ""),
                "lineage_id": "",
                "history_generation": 0,
            }
        snapshot = self.snapshots.read_consistent_view(
            session_id,
            self.event_log,
            self.projector,
        )
        context = snapshot.get("context") if isinstance(snapshot, dict) else {}
        compaction_row = (
            context.get("responses_compaction") if isinstance(context, dict) else None
        )
        compaction = (
            compaction_row.get("checkpoint")
            if isinstance(compaction_row, dict)
            else {}
        )
        return {
            "session_id": str(session_id or ""),
            "lineage_id": str(
                (
                    context.get("responses_lineage_id")
                    if isinstance(context, dict)
                    else ""
                )
                or ""
            ),
            "history_generation": int(
                (
                    snapshot.get("model_history_generation")
                    if isinstance(snapshot, dict)
                    else 0
                )
                or 0
            ),
            "responses_compaction": copy.deepcopy(compaction)
            if isinstance(compaction, dict)
            else {},
        }

    def _read_message_dicts(
        self,
        session_id: str,
        through_seq: Optional[int],
        seen: set[tuple[str, Optional[int]]],
    ) -> List[Dict[str, Any]]:
        key = (str(session_id), through_seq)
        if key in seen:
            return []
        seen.add(key)
        if through_seq is None:
            snapshot = self.snapshots.read_consistent_view(
                session_id,
                self.event_log,
                self.projector,
            )
            return self._messages_with_snapshot_branch(snapshot, seen)
        events = [
            event
            for event in self.event_log.iter_events(session_id)
            if int(event.seq) <= int(through_seq)
        ]
        snapshot = self.projector.project(events)
        return self._messages_with_events_branch(snapshot, events, seen)

    def _messages_with_snapshot_branch(
        self,
        snapshot: Dict[str, Any],
        seen: set[tuple[str, Optional[int]]],
    ) -> List[Dict[str, Any]]:
        history_ops = (
            list(snapshot.get("history_ops") or [])
            if isinstance(snapshot, dict)
            else []
        )
        reference = next(
            (
                row
                for row in history_ops
                if isinstance(row, dict)
                and row.get("type") == "history_branch_created"
                and str((row.get("payload") or {}).get("reference_mode") or "")
                == "immutable_model_prefix"
            ),
            None,
        )
        if reference is None:
            return self._messages_from_snapshot(snapshot)
        reference_seq = int(reference.get("seq") or 0)
        materialized = any(
            isinstance(row, dict)
            and row.get("type") in {"model_history_replaced", "model_prefix_compacted"}
            and int(row.get("seq") or 0) > reference_seq
            for row in history_ops
        )
        return self._messages_with_branch_reference(
            snapshot,
            reference.get("payload") or {},
            materialized,
            seen,
        )

    def _messages_with_events_branch(
        self,
        snapshot: Dict[str, Any],
        events: List[Any],
        seen: set[tuple[str, Optional[int]]],
    ) -> List[Dict[str, Any]]:
        reference = next(
            (
                event
                for event in events
                if event.type == "history_branch_created"
                and str((event.payload or {}).get("reference_mode") or "")
                == "immutable_model_prefix"
            ),
            None,
        )
        if reference is None:
            return self._messages_from_snapshot(snapshot)
        materialized = any(
            event.type in {"model_history_replaced", "model_prefix_compacted"}
            and int(event.seq) > int(reference.seq)
            for event in events
        )
        return self._messages_with_branch_reference(
            snapshot,
            reference.payload or {},
            materialized,
            seen,
        )

    def _messages_with_branch_reference(
        self,
        snapshot: Dict[str, Any],
        reference_payload: Dict[str, Any],
        materialized: bool,
        seen: set[tuple[str, Optional[int]]],
    ) -> List[Dict[str, Any]]:
        local = self._messages_from_snapshot(snapshot)
        if materialized:
            return local
        payload = dict(reference_payload or {})
        source_id = str(payload.get("source_session_id") or "").strip()
        try:
            source_seq = int(payload.get("branch_from_seq") or 0)
        except (TypeError, ValueError):
            source_seq = 0
        if not source_id or source_seq <= 0:
            return local
        prefix = self._read_message_dicts(source_id, source_seq, seen)
        return [
            *(strip_responses_continuation_from_message(item) for item in prefix),
            *local,
        ]

    def _messages_from_snapshot(self, snapshot: dict) -> List[Dict[str, Any]]:
        rows = snapshot.get("model_messages") if isinstance(snapshot, dict) else None
        if not isinstance(rows, list):
            return []
        out: List[Dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            role = str(row.get("role") or "").strip()
            payload = row.get("payload")
            if not isinstance(payload, dict):
                payload = {}
            content = str(payload.get("content") or "")
            if role == "user":
                item: Dict[str, Any] = {"type": "user", "content": content}
                if isinstance(payload.get("metadata"), dict):
                    item["metadata"] = dict(payload["metadata"])
                out.append(item)
            elif role == "assistant":
                item = {"type": "assistant", "content": content}
                if isinstance(payload.get("tool_calls"), list):
                    item["tool_calls"] = list(payload["tool_calls"])
                if isinstance(payload.get("metadata"), dict):
                    item["metadata"] = dict(payload["metadata"])
                if isinstance(payload.get("additional_kwargs"), dict):
                    item["additional_kwargs"] = dict(payload["additional_kwargs"])
                out.append(item)
            elif role == "tool":
                out.append({
                    "type": "tool",
                    "content": content,
                    "tool_call_id": str(payload.get("tool_call_id") or ""),
                })
            elif role == "system":
                out.append({"type": "system", "content": content})
        return out

    def has_model_messages(self, session_id: str) -> bool:
        return bool(self.read_message_dicts(session_id))

    def ensure_backfilled_from_legacy(self, session_id: str, legacy_messages: List[Dict[str, Any]]) -> int:
        if not runtime_v2_enabled() or self.has_model_messages(session_id):
            return 0
        clean = [dict(item) for item in list(legacy_messages or []) if isinstance(item, dict)]
        if not clean:
            return 0
        RuntimeHistoryOps(
            self.sessions_dir,
            path_resolver=self._path_resolver,
        ).replace_model_history(
            session_id,
            clean,
            reason="legacy_model_backfill",
        )
        return len(clean)

    def sync_from_legacy_if_needed(self, session_id: str, legacy_messages: List[Dict[str, Any]], reason: str = "legacy_model_sync") -> dict:
        if not runtime_v2_enabled():
            return {"checked": True, "action": "disabled", "legacy_count": 0, "projected_count": 0, "written": 0}
        clean = [dict(item) for item in list(legacy_messages or []) if isinstance(item, dict)]
        projected = self.read_message_dicts(session_id)
        if not clean:
            return {
                "checked": True,
                "action": "none",
                "legacy_count": 0,
                "projected_count": len(projected),
                "written": 0,
            }
        if not projected:
            RuntimeHistoryOps(
                self.sessions_dir,
                path_resolver=self._path_resolver,
            ).replace_model_history(
                session_id,
                clean,
                reason=reason,
            )
            return {
                "checked": True,
                "action": "backfill",
                "legacy_count": len(clean),
                "projected_count": 0,
                "written": len(clean),
            }
        if self._messages_equal(projected, clean):
            return {
                "checked": True,
                "action": "none",
                "legacy_count": len(clean),
                "projected_count": len(projected),
                "written": 0,
            }
        if self._messages_prefix_match(clean, projected):
            return {
                "checked": True,
                "action": "v2_ahead",
                "legacy_count": len(clean),
                "projected_count": len(projected),
                "written": 0,
            }
        if self._messages_prefix_match(projected, clean):
            # A legacy-only tail is safe to adopt because the complete existing
            # V2 projection is an exact prefix.  RuntimeHistoryOps records one
            # replacement event, keeping the operation atomic and auditable.
            RuntimeHistoryOps(
                self.sessions_dir,
                path_resolver=self._path_resolver,
            ).replace_model_history(
                session_id,
                clean,
                reason=reason,
            )
            return {
                "checked": True,
                "action": "legacy_tail_backfill",
                "legacy_count": len(clean),
                "projected_count": len(projected),
                "written": len(clean) - len(projected),
            }
        return {
            "checked": True,
            "action": "mismatch",
            "legacy_count": len(clean),
            "projected_count": len(projected),
            "written": 0,
        }

    @classmethod
    def _messages_equal(cls, left: List[Dict[str, Any]], right: List[Dict[str, Any]]) -> bool:
        return [cls._message_signature(item) for item in left if isinstance(item, dict)] == [
            cls._message_signature(item) for item in right if isinstance(item, dict)
        ]

    @classmethod
    def _messages_prefix_match(cls, prefix: List[Dict[str, Any]], rows: List[Dict[str, Any]]) -> bool:
        prefix_sigs = [cls._message_signature(item) for item in prefix if isinstance(item, dict)]
        row_sigs = [cls._message_signature(item) for item in rows if isinstance(item, dict)]
        return len(prefix_sigs) <= len(row_sigs) and row_sigs[:len(prefix_sigs)] == prefix_sigs

    @staticmethod
    def _message_signature(message: Dict[str, Any]) -> tuple[str, str, str]:
        msg_type = str(message.get("type") or message.get("role") or "")
        content = str(message.get("content") or "")
        tool_call_id = str(message.get("tool_call_id") or "")
        return msg_type, content, tool_call_id
