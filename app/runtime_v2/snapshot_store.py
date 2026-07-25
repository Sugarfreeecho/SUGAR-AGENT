from __future__ import annotations

import copy
import json
import logging
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from .versions import EVENT_SCHEMA_VERSION, PROJECTOR_VERSION


logger = logging.getLogger(__name__)


class SnapshotStore:
    """Rebuildable snapshot cache for faster refresh/debug reads."""

    _memory_cache: Dict[str, tuple[tuple[bool, int, int], Dict[str, Any]]] = {}
    _memory_cache_lock = threading.Lock()
    _checkpoint_condition = threading.Condition(threading.Lock())
    _checkpoint_pending: Dict[str, tuple[Any, str, Dict[str, Any]]] = {}
    _checkpoint_running: set[str] = set()
    _disk_locks: Dict[str, threading.Lock] = {}
    _disk_locks_guard = threading.Lock()

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
            current = self._memory_cache.get(key)
            if current and self._snapshot_seq(current[1]) > self._snapshot_seq(data):
                # A deferred checkpoint may have advanced the in-memory
                # projection beyond the latest disk checkpoint.
                self._memory_cache[key] = (signature, current[1])
                data = current[1]
            else:
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
        key = self._cache_key(path)
        self._discard_pending_checkpoint(key, at_or_before_seq=self._snapshot_seq(snapshot))
        with self._disk_lock_for(key):
            self._write_file(path, snapshot)
        with self._memory_cache_lock:
            self._memory_cache[key] = (self._file_signature(path), snapshot)

    def _write_file(self, path: Path, snapshot: Dict[str, Any]) -> None:
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

    def write_checkpointed(self, session_id: str, snapshot: Dict[str, Any]) -> bool:
        """Publish in memory and schedule rebuildable disk checkpoints.

        ``events.jsonl`` remains the durable fact source. On restart, at most
        ``RUNTIME_V2_SNAPSHOT_CHECKPOINT_EVENTS - 1`` events are incrementally
        replayed into the rebuildable snapshot cache. Disk serialization and
        ``fsync`` run on a per-session daemon worker so they cannot suspend the
        ReAct hot path.
        """
        path = self.path(session_id)
        key = self._cache_key(path)
        signature = self._file_signature(path)
        with self._memory_cache_lock:
            self._memory_cache[key] = (signature, snapshot)
        interval = max(1, int(os.getenv("RUNTIME_V2_SNAPSHOT_CHECKPOINT_EVENTS", "32")))
        last_seq = max(0, int(snapshot.get("last_seq") or 0))
        async_enabled = str(
            os.getenv("RUNTIME_V2_ASYNC_SNAPSHOT_CHECKPOINTS", "true")
        ).strip().lower() not in {"0", "false", "no", "off"}
        with self._checkpoint_condition:
            checkpoint_in_flight = key in self._checkpoint_running or key in self._checkpoint_pending
        checkpoint_due = (
            (not path.exists() and not checkpoint_in_flight)
            or last_seq <= 1
            or last_seq % interval == 0
        )
        if checkpoint_due and async_enabled:
            self._schedule_checkpoint(session_id, snapshot)
            # Fast checkpoints normally finish within a few milliseconds. A
            # short grace avoids leaving open temp files behind when a request
            # immediately deletes a session, while a slow or wedged fsync is
            # still detached from the ReAct path after this bounded wait.
            try:
                grace_ms = max(
                    0.0,
                    float(os.getenv("RUNTIME_V2_SNAPSHOT_INLINE_GRACE_MS", "50")),
                )
            except (TypeError, ValueError):
                grace_ms = 50.0
            if grace_ms:
                self.wait_for_checkpoint(session_id, timeout_seconds=grace_ms / 1000.0)
            return True
        if checkpoint_due:
            self.write(session_id, snapshot)
            return True
        return False

    def wait_for_checkpoint(self, session_id: str, timeout_seconds: float = 5.0) -> bool:
        """Wait for this session's deferred checkpoint without waiting forever."""
        key = self._cache_key(self.path(session_id))
        deadline = time.monotonic() + max(0.0, float(timeout_seconds))
        with self._checkpoint_condition:
            while key in self._checkpoint_running or key in self._checkpoint_pending:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._checkpoint_condition.wait(timeout=remaining)
        return True

    def _schedule_checkpoint(self, session_id: str, snapshot: Dict[str, Any]) -> None:
        path = self.path(session_id)
        key = self._cache_key(path)
        with self._checkpoint_condition:
            pending = self._checkpoint_pending.get(key)
            if pending is None or self._snapshot_seq(snapshot) >= self._snapshot_seq(pending[2]):
                self._checkpoint_pending[key] = (self, str(session_id), snapshot)
            if key in self._checkpoint_running:
                self._checkpoint_condition.notify_all()
                return
            self._checkpoint_running.add(key)
            worker = threading.Thread(
                target=self._checkpoint_worker,
                args=(key,),
                name=f"runtime-v2-snapshot-{uuid.uuid4().hex[:6]}",
                daemon=True,
            )
            try:
                worker.start()
            except Exception:
                self._checkpoint_running.discard(key)
                self._checkpoint_pending.pop(key, None)
                self._checkpoint_condition.notify_all()
                logger.warning(
                    "runtime_v2_snapshot_worker_start_failed session=%s",
                    session_id,
                    exc_info=True,
                )

    @classmethod
    def _checkpoint_worker(cls, key: str) -> None:
        while True:
            with cls._checkpoint_condition:
                item = cls._checkpoint_pending.pop(key, None)
                if item is None:
                    cls._checkpoint_running.discard(key)
                    cls._checkpoint_condition.notify_all()
                    return
            store, session_id, snapshot = item
            started = time.perf_counter()
            try:
                store._write_background_checkpoint(session_id, snapshot)
                logger.info(
                    "runtime_v2_snapshot_checkpoint session=%s seq=%s ms=%s",
                    session_id,
                    cls._snapshot_seq(snapshot),
                    int((time.perf_counter() - started) * 1000),
                )
            except Exception:
                logger.warning(
                    "runtime_v2_snapshot_checkpoint_failed session=%s seq=%s",
                    session_id,
                    cls._snapshot_seq(snapshot),
                    exc_info=True,
                )

    def _write_background_checkpoint(self, session_id: str, snapshot: Dict[str, Any]) -> None:
        path = self.path(session_id)
        key = self._cache_key(path)
        with self._disk_lock_for(key):
            self._write_file(path, snapshot)
        signature = self._file_signature(path)
        with self._memory_cache_lock:
            current = self._memory_cache.get(key)
            if current and self._snapshot_seq(current[1]) > self._snapshot_seq(snapshot):
                self._memory_cache[key] = (signature, current[1])
            else:
                self._memory_cache[key] = (signature, snapshot)

    @classmethod
    def _discard_pending_checkpoint(cls, key: str, *, at_or_before_seq: int) -> None:
        with cls._checkpoint_condition:
            pending = cls._checkpoint_pending.get(key)
            if pending is not None and cls._snapshot_seq(pending[2]) <= int(at_or_before_seq):
                cls._checkpoint_pending.pop(key, None)
            cls._checkpoint_condition.notify_all()

    @classmethod
    def _disk_lock_for(cls, key: str) -> threading.Lock:
        with cls._disk_locks_guard:
            lock = cls._disk_locks.get(key)
            if lock is None:
                lock = threading.Lock()
                cls._disk_locks[key] = lock
            return lock

    @staticmethod
    def _snapshot_seq(snapshot: Dict[str, Any]) -> int:
        try:
            return max(0, int((snapshot or {}).get("last_seq") or 0))
        except (TypeError, ValueError, AttributeError):
            return 0

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
