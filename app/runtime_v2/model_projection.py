from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .config import runtime_v2_enabled
from .event_log import SessionEventLog
from .history_ops import RuntimeHistoryOps
from .projector import RuntimeProjector
from .snapshot_store import SnapshotStore


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
        return self._read_message_dicts(session_id, None, set())

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
        all_events = list(self.event_log.iter_events(session_id))
        events = [
            event
            for event in all_events
            if through_seq is None or int(event.seq) <= int(through_seq)
        ]
        if through_seq is None:
            snapshot = self.snapshots.read_consistent(
                session_id,
                self.event_log,
                self.projector,
            )
        else:
            snapshot = self.projector.project(events)
        local = self._messages_from_snapshot(snapshot)
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
            return local
        materialized = any(
            event.type == "model_history_replaced" and int(event.seq) > int(reference.seq)
            for event in events
        )
        if materialized:
            return local
        payload = dict(reference.payload or {})
        source_id = str(payload.get("source_session_id") or "").strip()
        try:
            source_seq = int(payload.get("branch_from_seq") or 0)
        except (TypeError, ValueError):
            source_seq = 0
        if not source_id or source_seq <= 0:
            return local
        prefix = self._read_message_dicts(source_id, source_seq, seen)
        return [*prefix, *local]

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
