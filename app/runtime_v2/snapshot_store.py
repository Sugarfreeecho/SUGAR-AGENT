from __future__ import annotations

import json
import copy
import os
import threading
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from .versions import EVENT_SCHEMA_VERSION, PROJECTOR_VERSION


class SnapshotStore:
    """Rebuildable snapshot cache for faster refresh/debug reads."""

    _memory_cache: Dict[str, tuple[tuple[bool, int, int], Dict[str, Any]]] = {}
    _memory_cache_lock = threading.Lock()

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
        signature = self._file_signature(path)
        key = self._cache_key(path)
        with self._memory_cache_lock:
            cached = self._memory_cache.get(key)
            if cached and cached[0] == signature:
                return copy.deepcopy(cached[1])
        if not path.exists():
            return {}
        try:
            with path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception:
            return {}
        if not isinstance(data, dict):
            return {}
        with self._memory_cache_lock:
            self._memory_cache[key] = (signature, data)
        return copy.deepcopy(data)

    def read_for_update(self, session_id: str) -> Dict[str, Any]:
        """Return the published cache object for projector copy-on-write use."""
        path = self.path(session_id)
        signature = self._file_signature(path)
        key = self._cache_key(path)
        with self._memory_cache_lock:
            cached = self._memory_cache.get(key)
            if cached and cached[0] == signature:
                return cached[1]
        self.read(session_id)
        with self._memory_cache_lock:
            cached = self._memory_cache.get(key)
            return cached[1] if cached else {}

    def write(self, session_id: str, snapshot: Dict[str, Any]) -> None:
        path = self.path(session_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Keep the temporary basename shorter than ``latest.json``.  Nested
        # subagent paths can already be close to the Win32 path-length limit;
        # including pid/thread/full UUID here made otherwise valid snapshots
        # fail before the atomic replace.  Three random bytes are sufficient for
        # per-directory collision resistance and ``x`` preserves exclusivity.
        tmp = path.with_name(f".s-{uuid.uuid4().hex[:6]}")
        try:
            with tmp.open("x", encoding="utf-8") as fh:
                # Snapshots are machine-owned, rebuildable caches. Compact JSON
                # materially reduces hot-path serialization and atomic-replace I/O
                # for large sessions without changing their semantics.
                json.dump(snapshot, fh, ensure_ascii=False, separators=(",", ":"))
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, path)
        finally:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
        with self._memory_cache_lock:
            self._memory_cache[self._cache_key(path)] = (
                self._file_signature(path),
                snapshot,
            )

    def write_checkpointed(self, session_id: str, snapshot: Dict[str, Any]) -> bool:
        """Publish every projection in memory and checkpoint disk periodically.

        ``events.jsonl`` remains the durable fact source. On restart, at most
        ``RUNTIME_V2_SNAPSHOT_CHECKPOINT_EVENTS - 1`` events are incrementally
        replayed into the rebuildable snapshot cache.
        """
        path = self.path(session_id)
        key = self._cache_key(path)
        signature = self._file_signature(path)
        with self._memory_cache_lock:
            self._memory_cache[key] = (signature, snapshot)
        interval = max(1, int(os.getenv("RUNTIME_V2_SNAPSHOT_CHECKPOINT_EVENTS", "32")))
        last_seq = max(0, int(snapshot.get("last_seq") or 0))
        if not path.exists() or last_seq <= 1 or last_seq % interval == 0:
            self.write(session_id, snapshot)
            return True
        return False

    def stamp_event_log(self, session_id: str, snapshot: Dict[str, Any], event_path: Path) -> Dict[str, Any]:
        """Attach an O(1) freshness signature to a rebuildable snapshot."""
        snapshot["_projection"] = {
            "event_schema_version": EVENT_SCHEMA_VERSION,
            "projector_version": PROJECTOR_VERSION,
        }
        snapshot["projector_version"] = PROJECTOR_VERSION
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
            if self._projection_version_matches(snapshot):
                last_seq = max(0, int(snapshot.get("last_seq") or 0))
                pending = event_log.read_after_seq(session_id, last_seq)
                if pending and all(int(event.seq) > last_seq for event in pending):
                    rebuilt = snapshot
                    for event in pending:
                        rebuilt = projector.project_incremental(rebuilt, event)
                    self.stamp_event_log(
                        session_id, rebuilt, event_log.event_path(session_id)
                    )
                    self.write(session_id, rebuilt)
                    return rebuilt
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
        if not SnapshotStore._projection_version_matches(snapshot):
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
    def _projection_version_matches(snapshot: Dict[str, Any]) -> bool:
        if not isinstance(snapshot, dict) or not snapshot:
            return False
        projection = snapshot.get("_projection")
        if not isinstance(projection, dict):
            return False
        return (
            int(projection.get("event_schema_version") or 0) == EVENT_SCHEMA_VERSION
            and int(projection.get("projector_version") or 0) == PROJECTOR_VERSION
        )

    @staticmethod
    def _safe_id(session_id: str) -> str:
        safe = str(session_id or "").strip()
        if not safe or any(part in safe for part in ("/", "\\", "..")):
            raise ValueError("invalid session_id")
        return safe

    @staticmethod
    def _file_signature(path: Path) -> tuple[bool, int, int]:
        try:
            stat = path.stat()
            return True, int(stat.st_mtime_ns), int(stat.st_size)
        except OSError:
            return False, 0, 0

    @staticmethod
    def _cache_key(path: Path) -> str:
        try:
            return str(path.resolve())
        except Exception:
            return str(path)
