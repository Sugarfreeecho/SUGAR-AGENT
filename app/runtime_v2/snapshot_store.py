from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, Optional


class SnapshotStore:
    """Rebuildable snapshot cache for faster refresh/debug reads."""

    def __init__(self, root: str | Path, path_resolver: Optional[Callable[[str], str | Path]] = None):
        self.root = Path(root)
        self._path_resolver = path_resolver

    def path(self, session_id: str) -> Path:
        safe_id = self._safe_id(session_id)
        if self._path_resolver is not None:
            return Path(self._path_resolver(safe_id)) / "snapshots" / "latest.json"
        return self.root / safe_id / "snapshots" / "latest.json"

    def read(self, session_id: str) -> Dict[str, Any]:
        path = self.path(session_id)
        if not path.exists():
            return {}
        try:
            with path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}

    def write(self, session_id: str, snapshot: Dict[str, Any]) -> None:
        path = self.path(session_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(snapshot, fh, ensure_ascii=False, indent=2)
        tmp.replace(path)

    def stamp_event_log(self, session_id: str, snapshot: Dict[str, Any], event_path: Path) -> Dict[str, Any]:
        """Attach an O(1) freshness signature to a rebuildable snapshot."""
        try:
            stat = event_path.stat()
            snapshot["_event_log"] = {
                "size": int(stat.st_size),
                "mtime_ns": int(stat.st_mtime_ns),
            }
        except OSError:
            snapshot.pop("_event_log", None)
        return snapshot

    def read_consistent(self, session_id: str, event_log=None, projector=None) -> Dict[str, Any]:
        """Read the fast cache, rebuilding only when its log signature is stale.

        The normal path performs one snapshot read and one stat. Full replay is
        reserved for crash recovery, old snapshots without signatures, or
        external log edits.
        """
        if event_log is None or projector is None:
            from .event_log import SessionEventLog
            from .projector import RuntimeProjector
            event_log = event_log or SessionEventLog(self.root, path_resolver=self._path_resolver)
            projector = projector or RuntimeProjector()
        snapshot = self.read(session_id)
        if self._signature_matches(snapshot, event_log.event_path(session_id)):
            return snapshot
        with event_log.session_transaction(session_id):
            snapshot = self.read(session_id)
            if self._signature_matches(snapshot, event_log.event_path(session_id)):
                return snapshot
            rebuilt = projector.project(event_log.read_all(session_id))
            self.stamp_event_log(session_id, rebuilt, event_log.event_path(session_id))
            self.write(session_id, rebuilt)
            return rebuilt

    @staticmethod
    def _signature_matches(snapshot: Dict[str, Any], event_path: Path) -> bool:
        if not isinstance(snapshot, dict) or not snapshot:
            return not event_path.exists()
        signature = snapshot.get("_event_log")
        if not isinstance(signature, dict):
            return False
        try:
            stat = event_path.stat()
        except OSError:
            return int(snapshot.get("last_seq") or 0) == 0
        return (
            int(signature.get("size") or -1) == int(stat.st_size)
            and int(signature.get("mtime_ns") or -1) == int(stat.st_mtime_ns)
        )

    @staticmethod
    def _safe_id(session_id: str) -> str:
        safe = str(session_id or "").strip()
        if not safe or any(part in safe for part in ("/", "\\", "..")):
            raise ValueError("invalid session_id")
        return safe
