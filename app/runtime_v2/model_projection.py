from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from .config import runtime_v2_enabled
from .history_ops import RuntimeHistoryOps
from .snapshot_store import SnapshotStore


class RuntimeModelProjection:
    """Read model-facing messages from the Runtime V2 snapshot."""

    def __init__(self, sessions_dir: str | Path):
        self.sessions_dir = Path(sessions_dir)
        self.snapshots = SnapshotStore(sessions_dir)

    def read_message_dicts(self, session_id: str) -> List[Dict[str, Any]]:
        if not runtime_v2_enabled():
            return []
        snapshot = self.snapshots.read(session_id)
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
        RuntimeHistoryOps(self.sessions_dir).replace_model_history(
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
        if self._messages_equal(projected, clean):
            return {
                "checked": True,
                "action": "none",
                "legacy_count": len(clean),
                "projected_count": len(projected),
                "written": 0,
            }
        RuntimeHistoryOps(self.sessions_dir).replace_model_history(
            session_id,
            clean,
            reason=reason,
        )
        return {
            "checked": True,
            "action": "replace",
            "legacy_count": len(clean),
            "projected_count": len(projected),
            "written": len(clean),
        }

    @classmethod
    def _messages_equal(cls, left: List[Dict[str, Any]], right: List[Dict[str, Any]]) -> bool:
        return [cls._message_signature(item) for item in left if isinstance(item, dict)] == [
            cls._message_signature(item) for item in right if isinstance(item, dict)
        ]

    @staticmethod
    def _message_signature(message: Dict[str, Any]) -> tuple[str, str, str]:
        msg_type = str(message.get("type") or message.get("role") or "")
        content = str(message.get("content") or "")
        tool_call_id = str(message.get("tool_call_id") or "")
        return msg_type, content, tool_call_id
