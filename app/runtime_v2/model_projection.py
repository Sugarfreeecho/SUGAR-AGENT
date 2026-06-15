from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from .snapshot_store import SnapshotStore


class RuntimeModelProjection:
    """Read model-facing messages from the Runtime V2 snapshot."""

    def __init__(self, sessions_dir: str | Path):
        self.snapshots = SnapshotStore(sessions_dir)

    def read_message_dicts(self, session_id: str) -> List[Dict[str, Any]]:
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

