from __future__ import annotations

import json
import os
import threading
from contextlib import contextmanager
from collections import deque
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional

from .event_schema import RuntimeEvent


class SessionEventLog:
    """Append-only per-session JSONL event log.

    The log is the V2 fact source. Metadata, snapshots, and indexes should be
    treated as rebuildable projections.
    """

    _global_locks: Dict[str, threading.RLock] = {}
    _global_locks_guard = threading.Lock()
    _seq_cache: Dict[str, tuple[int, int, int]] = {}
    _seq_cache_guard = threading.Lock()

    def __init__(self, root: os.PathLike[str] | str, path_resolver: Optional[Callable[[str], os.PathLike[str] | str]] = None):
        self.root = Path(root)
        self._path_resolver = path_resolver

    def session_dir(self, session_id: str) -> Path:
        safe_id = self._validate_session_id(session_id)
        if self._path_resolver is not None:
            return Path(self._path_resolver(safe_id))
        return self.root / safe_id

    def event_path(self, session_id: str) -> Path:
        return self.session_dir(session_id) / "events.jsonl"

    def append(self, session_id: str, event_type: str, payload: Optional[dict] = None, run_id: Optional[str] = None) -> RuntimeEvent:
        with self.session_transaction(session_id):
            return self._append_unlocked(session_id, event_type, payload=payload, run_id=run_id)

    def append_batch(self, session_id: str, rows: Iterable[dict]) -> List[RuntimeEvent]:
        """Append a related group while owning the same session/file lock."""
        with self.session_transaction(session_id):
            return self._append_many_unlocked(session_id, rows)

    def _append_many_unlocked(self, session_id: str, rows: Iterable[dict]) -> List[RuntimeEvent]:
        """Write a batch with one seq lookup and one file open.

        The caller must own ``session_transaction``. This is the hot path for
        branch materialization, where opening the log once is materially faster
        than thousands of individual appends.
        """
        clean = [row for row in rows if isinstance(row, dict) and str(row.get("type") or "").strip()]
        if not clean:
            return []
        next_seq = self.next_seq(session_id)
        events: List[RuntimeEvent] = []
        for offset, row in enumerate(clean):
            events.append(RuntimeEvent(
                seq=next_seq + offset,
                type=str(row.get("type") or "").strip(),
                session_id=session_id,
                run_id=str(row.get("run_id") or "").strip() or None,
                payload=dict(row.get("payload") or {}) if isinstance(row.get("payload"), dict) else {},
            ))
        path = self.event_path(session_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        encoded = [
            json.dumps(event.to_dict(), ensure_ascii=False, separators=(",", ":")) + "\n"
            for event in events
        ]
        with path.open("a", encoding="utf-8", newline="\n") as fh:
            fh.writelines(encoded)
            fh.flush()
        self._update_seq_cache(session_id, events[-1].seq)
        return events

    def _append_unlocked(self, session_id: str, event_type: str, payload: Optional[dict] = None, run_id: Optional[str] = None) -> RuntimeEvent:
        seq = self.next_seq(session_id)
        event = RuntimeEvent(
            seq=seq,
            type=event_type,
            session_id=session_id,
            run_id=run_id,
            payload=payload or {},
        )
        path = self.event_path(session_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(event.to_dict(), ensure_ascii=False, separators=(",", ":")))
            fh.write("\n")
            fh.flush()
        self._update_seq_cache(session_id, event.seq)
        return event

    def append_event(self, event: RuntimeEvent) -> RuntimeEvent:
        with self.session_transaction(event.session_id):
            expected = self.next_seq(event.session_id)
            if event.seq != expected:
                event = RuntimeEvent(
                    seq=expected,
                    type=event.type,
                    session_id=event.session_id,
                    timestamp=event.timestamp,
                    run_id=event.run_id,
                    payload=event.payload,
                )
            path = self.event_path(event.session_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8", newline="\n") as fh:
                fh.write(json.dumps(event.to_dict(), ensure_ascii=False, separators=(",", ":")))
                fh.write("\n")
                fh.flush()
            self._update_seq_cache(event.session_id, event.seq)
            return event

    def read_all(self, session_id: str) -> List[RuntimeEvent]:
        return list(self.iter_events(session_id))

    def read_after_seq(self, session_id: str, after_seq: int) -> List[RuntimeEvent]:
        return [ev for ev in self.iter_events(session_id) if ev.seq > after_seq]

    def read_latest(self, session_id: str, limit: int) -> List[RuntimeEvent]:
        limit = max(0, int(limit))
        if limit <= 0:
            return []
        rows = deque(maxlen=limit)
        for ev in self.iter_events(session_id):
            rows.append(ev)
        return list(rows)

    def read_tail_window(
        self,
        session_id: str,
        *,
        max_bytes: int = 1024 * 1024,
        max_events: int = 5000,
    ) -> tuple[List[RuntimeEvent], bool]:
        """Read a suffix of the JSONL log without scanning from the beginning.

        Returns ``(events, reached_start)`` with events in chronological order.
        Bad trailing lines are skipped so a partially written line cannot make a
        session unloadable.
        """
        max_bytes = max(4096, int(max_bytes))
        max_events = max(1, int(max_events))
        path = self.event_path(session_id)
        if not path.exists():
            return [], True
        size = path.stat().st_size
        if size <= 0:
            return [], True
        read_size = min(size, max_bytes)
        reached_start = read_size >= size
        with path.open("rb") as fh:
            fh.seek(size - read_size)
            data = fh.read(read_size)
        if not reached_start:
            first_newline = data.find(b"\n")
            if first_newline >= 0:
                data = data[first_newline + 1:]
            else:
                data = b""
        rows: deque[RuntimeEvent] = deque(maxlen=max_events)
        for raw_line in data.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            try:
                rows.append(RuntimeEvent.from_dict(json.loads(line.decode("utf-8"))))
            except Exception:
                continue
        return list(rows), reached_start

    def read_before_seq(self, session_id: str, before_seq: int, limit: int) -> List[RuntimeEvent]:
        before = int(before_seq)
        limit = max(0, int(limit))
        if limit <= 0:
            return []
        rows = deque(maxlen=limit)
        for ev in self.iter_events(session_id):
            if ev.seq < before:
                rows.append(ev)
        return list(rows)

    def iter_events(self, session_id: str) -> Iterable[RuntimeEvent]:
        path = self.event_path(session_id)
        if not path.exists():
            return
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield RuntimeEvent.from_dict(json.loads(line))
                except Exception:
                    continue

    def next_seq(self, session_id: str) -> int:
        cached = self._cached_last_seq(session_id)
        if cached is not None:
            return cached + 1
        path = self.event_path(session_id)
        if not path.exists():
            return 1
        last = self._read_last_seq_from_tail(path)
        self._update_seq_cache(session_id, last)
        return last + 1

    @staticmethod
    def _read_last_seq_from_tail(path: Path, chunk_size: int = 64 * 1024) -> int:
        """Return the newest valid sequence without scanning a long JSONL file."""
        try:
            with path.open("rb") as fh:
                fh.seek(0, os.SEEK_END)
                pos = fh.tell()
                pending = b""
                while pos > 0:
                    take = min(max(1024, int(chunk_size)), pos)
                    pos -= take
                    fh.seek(pos)
                    pending = fh.read(take) + pending
                    lines = pending.splitlines()
                    if pos > 0 and lines:
                        pending = lines.pop(0)
                    else:
                        pending = b""
                    for raw in reversed(lines):
                        if not raw.strip():
                            continue
                        try:
                            data = json.loads(raw.decode("utf-8"))
                            return max(0, int(data.get("seq") or 0))
                        except (UnicodeDecodeError, ValueError, TypeError, json.JSONDecodeError):
                            continue
                if pending.strip():
                    try:
                        data = json.loads(pending.decode("utf-8"))
                        return max(0, int(data.get("seq") or 0))
                    except (UnicodeDecodeError, ValueError, TypeError, json.JSONDecodeError):
                        pass
        except OSError:
            pass
        return 0

    def repair(self, session_id: str) -> Dict[str, int]:
        """Drop malformed lines without changing published sequence IDs.

        Sequence gaps are valid. Renumbering would invalidate history-operation
        targets, branch anchors and SSE cursors. Duplicate/non-monotonic IDs are
        reported for explicit migration instead of being guessed here.
        """
        with self.session_transaction(session_id):
            path = self.event_path(session_id)
            if not path.exists():
                return {"kept": 0, "dropped": 0, "duplicates": 0, "non_monotonic": 0}
            kept: List[RuntimeEvent] = []
            dropped = 0
            with path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    try:
                        ev = RuntimeEvent.from_dict(json.loads(line))
                    except Exception:
                        dropped += 1
                        continue
                    kept.append(ev)
            seqs = [int(ev.seq) for ev in kept]
            duplicates = len(seqs) - len(set(seqs))
            non_monotonic = sum(1 for i in range(1, len(seqs)) if seqs[i] <= seqs[i - 1])
            tmp = path.with_suffix(".jsonl.tmp")
            with tmp.open("w", encoding="utf-8", newline="\n") as fh:
                for ev in kept:
                    fh.write(json.dumps(ev.to_dict(), ensure_ascii=False, separators=(",", ":")))
                    fh.write("\n")
            tmp.replace(path)
            self._update_seq_cache(session_id, max(seqs, default=0))
            return {
                "kept": len(kept),
                "dropped": dropped,
                "duplicates": duplicates,
                "non_monotonic": non_monotonic,
            }

    def _cache_scope_for(self, session_id: str) -> str:
        try:
            return str(self.event_path(session_id).resolve())
        except Exception:
            return str(self.root.resolve()) + "::" + str(session_id or "")

    def _cached_last_seq(self, session_id: str) -> Optional[int]:
        path = self.event_path(session_id)
        if not path.exists():
            return None
        try:
            stat = path.stat()
        except OSError:
            return None
        scope = self._cache_scope_for(session_id)
        with self._seq_cache_guard:
            cached = self._seq_cache.get(scope)
        if not cached:
            return None
        mtime_ns, size, last = cached
        if mtime_ns == stat.st_mtime_ns and size == stat.st_size:
            return int(last)
        return None

    def _update_seq_cache(self, session_id: str, last_seq: int) -> None:
        path = self.event_path(session_id)
        try:
            stat = path.stat()
        except OSError:
            return
        scope = self._cache_scope_for(session_id)
        with self._seq_cache_guard:
            self._seq_cache[scope] = (int(stat.st_mtime_ns), int(stat.st_size), int(last_seq))

    def _lock_for(self, session_id: str) -> threading.RLock:
        safe_id = self._validate_session_id(session_id)
        try:
            scope = str(self.session_dir(safe_id).resolve())
        except Exception:
            scope = str(self.root.resolve()) + "::" + safe_id
        with self._global_locks_guard:
            lock = self._global_locks.get(scope)
            if lock is None:
                lock = threading.RLock()
                self._global_locks[scope] = lock
            return lock

    @contextmanager
    def session_transaction(self, session_id: str):
        """Serialize a session commit in this process and across workers."""
        safe_id = self._validate_session_id(session_id)
        lock = self._lock_for(safe_id)
        with lock:
            session_dir = self.session_dir(safe_id)
            session_dir.mkdir(parents=True, exist_ok=True)
            lock_path = session_dir / ".events.lock"
            with lock_path.open("a+b") as fh:
                self._lock_file(fh)
                try:
                    yield
                finally:
                    self._unlock_file(fh)

    @staticmethod
    def _lock_file(fh) -> None:
        if os.name == "nt":
            import msvcrt
            fh.seek(0, os.SEEK_END)
            if fh.tell() == 0:
                fh.write(b"0")
                fh.flush()
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_LOCK, 1)
            return
        import fcntl
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)

    @staticmethod
    def _unlock_file(fh) -> None:
        if os.name == "nt":
            import msvcrt
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
            return
        import fcntl
        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)

    @staticmethod
    def _validate_session_id(session_id: str) -> str:
        safe_id = str(session_id or "").strip()
        if not safe_id:
            raise ValueError("session_id is required")
        if any(part in safe_id for part in ("/", "\\", "..")):
            raise ValueError("session_id contains invalid path characters")
        return safe_id
