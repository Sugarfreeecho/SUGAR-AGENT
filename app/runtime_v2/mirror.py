from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from .event_log import SessionEventLog
from .event_schema import RuntimeEvent
from .projector import RuntimeProjector
from .snapshot_store import SnapshotStore

logger = logging.getLogger(__name__)


class RuntimeMirror:
    """Synchronous compatibility bridge from legacy events to Runtime V2."""

    def __init__(self, sessions_dir: str | Path):
        self.sessions_dir = Path(sessions_dir)
        self.event_log = SessionEventLog(self.sessions_dir)
        self.projector = RuntimeProjector()
        self.snapshots = SnapshotStore(self.sessions_dir)

    def mirror_ui_event(self, session_id: str, event: Dict[str, Any]) -> Optional[RuntimeEvent]:
        mapped = self._map_ui_event(event)
        if not mapped:
            return None
        return self.append(session_id, mapped["type"], mapped.get("payload") or {}, run_id=mapped.get("run_id"))

    def mirror_run_started(self, session_id: str, run_id: Optional[str] = None, payload: Optional[dict] = None) -> Optional[RuntimeEvent]:
        return self.append(session_id, "run_started", payload or {}, run_id=run_id)

    def mirror_run_finished(self, session_id: str, run_id: Optional[str] = None, payload: Optional[dict] = None) -> Optional[RuntimeEvent]:
        return self.append(session_id, "run_finished", payload or {}, run_id=run_id)

    def mirror_run_failed(self, session_id: str, error: str, run_id: Optional[str] = None, payload: Optional[dict] = None) -> Optional[RuntimeEvent]:
        data = {"error": error}
        if payload:
            data.update(payload)
        return self.append(session_id, "run_failed", data, run_id=run_id)

    def mirror_run_interrupted(self, session_id: str, run_id: Optional[str] = None, payload: Optional[dict] = None) -> Optional[RuntimeEvent]:
        return self.append(session_id, "run_interrupted", payload or {}, run_id=run_id)

    def append(self, session_id: str, event_type: str, payload: Optional[dict] = None, run_id: Optional[str] = None) -> Optional[RuntimeEvent]:
        try:
            event = self.event_log.append(session_id, event_type, payload=payload or {}, run_id=run_id)
            self._refresh_snapshot(session_id)
            return event
        except Exception as exc:
            logger.debug("Runtime V2 mirror append failed for session %s: %s", session_id, exc)
            return None

    def _refresh_snapshot(self, session_id: str) -> None:
        try:
            snapshot = self.projector.project(self.event_log.read_all(session_id))
            self.snapshots.write(session_id, snapshot)
        except Exception as exc:
            logger.debug("Runtime V2 mirror snapshot failed for session %s: %s", session_id, exc)

    def _map_ui_event(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        event_type = str((event or {}).get("type") or "")
        if not event_type:
            return None
        if event_type == "user":
            return {"type": "message_user", "payload": {"content": event.get("content") or ""}}
        if event_type == "final":
            return {"type": "message_assistant_final", "payload": {"content": event.get("content") or ""}}
        if event_type == "context_tokens":
            return {"type": "context_tokens", "payload": dict(event)}
        if event_type == "todo_plan":
            return {"type": "todo_updated", "payload": dict(event)}
        if event_type in {"subagent_started", "subagent_progress", "subagent_finished", "subagent_failed", "subagent_result_consumed"}:
            return {"type": event_type, "payload": dict(event)}
        if event_type in {"tool_call", "tool_result"}:
            mapped_type = "tool_finished" if event_type == "tool_result" else "tool_started"
            return {"type": mapped_type, "payload": dict(event)}
        if event_type in {"status", "process_metrics", "cache_stats", "validate_final"}:
            return None
        return {"type": "legacy_ui_event", "payload": dict(event)}
