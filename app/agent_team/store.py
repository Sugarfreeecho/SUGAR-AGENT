"""Atomic extension-state persistence for the Agent Team workflow."""

from __future__ import annotations

from pathlib import Path
import copy
from typing import Callable, Optional

try:
    from runtime_v2.event_log import SessionEventLog
    from runtime_v2.event_schema import RuntimeEvent, now_iso
    from runtime_v2.extension_state import SessionExtensionStateStore
    from runtime_v2.projector import RuntimeProjector
    from runtime_v2.snapshot_store import SnapshotStore
except ImportError:  # package import: ``app.agent_team``
    from app.runtime_v2.event_log import SessionEventLog
    from app.runtime_v2.event_schema import RuntimeEvent, now_iso
    from app.runtime_v2.extension_state import SessionExtensionStateStore
    from app.runtime_v2.projector import RuntimeProjector
    from app.runtime_v2.snapshot_store import SnapshotStore

from .config import require_agent_team_enabled
from .projection import apply_team_event


SnapshotGuard = Callable[[dict], None]


class RuntimeTeamStore:
    """Persist Team state without adding Team vocabulary to Runtime V2."""

    def __init__(self, sessions_dir: str | Path, path_resolver=None):
        self.event_log = SessionEventLog(sessions_dir, path_resolver=path_resolver)
        self.snapshots = SnapshotStore(sessions_dir, path_resolver=path_resolver)
        self.projector = RuntimeProjector()
        self.extensions = SessionExtensionStateStore(
            sessions_dir,
            path_resolver=path_resolver,
            # Team tools receive a host-derived root id. Keeping the legacy
            # create-on-first-write behavior also supports recovery/tests.
            require_existing_session=False,
        )

    def read_snapshot(self, session_id: str) -> dict:
        require_agent_team_enabled()
        snapshot = self.snapshots.read_consistent(session_id, self.event_log, self.projector)
        extensions = snapshot.get("extensions") if isinstance(snapshot, dict) else {}
        plugin = extensions.get("agent-team") if isinstance(extensions, dict) else {}
        row = plugin.get("team") if isinstance(plugin, dict) else {}
        value = row.get("value") if isinstance(row, dict) else None
        result = dict(snapshot)
        result["team"] = copy.deepcopy(value) if isinstance(value, dict) else None
        return result

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
        def mutate(current):
            facade = {"team": copy.deepcopy(current) if isinstance(current, dict) else None}
            if guard is not None:
                guard(facade)
            current_seq = int(current.get("seq") or 0) if isinstance(current, dict) else 0
            updated = apply_team_event(
                current,
                event_type,
                payload,
                timestamp=now_iso(),
                seq=current_seq + 1,
            )
            return event_type, updated, updated

        event, _value = self.extensions.mutate(
            session_id,
            "agent-team",
            "team",
            mutate,
            run_id=str(run_id or ""),
        )
        assert isinstance(event, RuntimeEvent)
        return event
