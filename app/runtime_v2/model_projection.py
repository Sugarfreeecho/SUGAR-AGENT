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
