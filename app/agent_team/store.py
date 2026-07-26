"""Atomic Runtime V2 persistence for the Agent Team control plane."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

try:
    from runtime_v2.event_log import SessionEventLog
    from runtime_v2.event_schema import RuntimeEvent
    from runtime_v2.projector import RuntimeProjector
    from runtime_v2.snapshot_store import SnapshotStore
except ImportError:  # package import: ``app.agent_team``
    from app.runtime_v2.event_log import SessionEventLog
    from app.runtime_v2.event_schema import RuntimeEvent
    from app.runtime_v2.projector import RuntimeProjector
    from app.runtime_v2.snapshot_store import SnapshotStore

from .config import require_agent_team_enabled


SnapshotGuard = Callable[[dict], None]


class RuntimeTeamStore:
    """Append Team events and update their root-session projection atomically."""

    def __init__(self, sessions_dir: str | Path, path_resolver=None):
        self.event_log = SessionEventLog(sessions_dir, path_resolver=path_resolver)
        self.snapshots = SnapshotStore(sessions_dir, path_resolver=path_resolver)
        self.projector = RuntimeProjector()

    def read_snapshot(self, session_id: str) -> dict:
        require_agent_team_enabled()
        return self.snapshots.read_consistent(session_id, self.event_log, self.projector)

    def append_event(
        self,
        session_id: str,
        event_type: str,
        payload: Optional[dict] = None,
        *,
        run_id: Optional[str] = None,
        guard: Optional[SnapshotGuard] = None,
    ) -> RuntimeEvent:
        require_agent_team_enabled()
        with self.event_log.session_transaction(session_id):
            snapshot = self.snapshots.read_for_update(session_id)
            next_seq = self.event_log.next_seq(session_id)
            if int(snapshot.get("last_seq") or 0) != next_seq - 1:
                snapshot = self.projector.project(self.event_log.read_all(session_id))
            if guard is not None:
                guard(snapshot)
            event = self.event_log._append_unlocked(
                session_id,
                event_type,
                payload=payload or {},
                run_id=run_id,
            )
            snapshot = self.projector.project_incremental(snapshot, event)
            self.snapshots.stamp_event_log(
                session_id,
                snapshot,
                self.event_log.event_path(session_id),
            )
            self.snapshots.write_checkpointed(session_id, snapshot)
        return event
