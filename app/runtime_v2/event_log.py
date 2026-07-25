from __future__ import annotations

import ctypes
import errno
import json
import logging
import os
import threading
import time
import uuid
from contextlib import contextmanager
from collections import deque
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional

from .event_schema import RuntimeEvent
from .versions import SEQ_OFFSET_INDEX_VERSION


_SEQ_OFFSET_STRIDE = 32


logger = logging.getLogger(__name__)
_windows_unbiased_query = None
_windows_unbiased_query_ready = False
_windows_unbiased_query_guard = threading.Lock()


def _active_uptime_seconds() -> float:
    """Return an acquisition clock that excludes Windows system sleep."""
    global _windows_unbiased_query, _windows_unbiased_query_ready
    if os.name == "nt":
        try:
            if not _windows_unbiased_query_ready:
                with _windows_unbiased_query_guard:
                    if not _windows_unbiased_query_ready:
                        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
                        query = kernel32.QueryUnbiasedInterruptTime
                        query.argtypes = [ctypes.POINTER(ctypes.c_ulonglong)]
                        query.restype = ctypes.c_bool
                        _windows_unbiased_query = query
                        _windows_unbiased_query_ready = True
            value = ctypes.c_ulonglong()
            query = _windows_unbiased_query
            if callable(query) and query(ctypes.byref(value)):
                return float(value.value) / 10_000_000.0
        except Exception:
            _windows_unbiased_query_ready = True
    return time.monotonic()


class RuntimeEventLogCorruptionError(RuntimeError):
    """Raised when the append-only fact source contains an unreadable row."""

    def __init__(
        self,
        session_id: str,
        path: Path,
        *,
        line_number: Optional[int] = None,
        byte_offset: Optional[int] = None,
        detail: str = "invalid runtime event",
    ) -> None:
        location = f"line {line_number}" if line_number is not None else f"byte {byte_offset or 0}"
        super().__init__(
            f"Runtime V2 event log is corrupt for session {session_id!r} at {location}: {detail}. "
            "Run the explicit Runtime V2 repair service before continuing."
        )
        self.session_id = session_id
        self.path = path
        self.line_number = line_number
        self.byte_offset = byte_offset
        self.detail = detail


class RuntimeEventLogBusyError(TimeoutError):
    """Raised when a session transaction cannot acquire its lock in time."""

    def __init__(self, session_id: str, stage: str, timeout_seconds: float) -> None:
        super().__init__(
            f"Runtime V2 session {session_id!r} remained busy while waiting for "
            f"{stage} for {timeout_seconds:.3f}s"
        )
        self.session_id = session_id
        self.stage = stage
        self.timeout_seconds = timeout_seconds


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

    def seq_offset_index_path(self, session_id: str) -> Path:
        return self.session_dir(session_id) / "snapshots" / "seq_offset_index.json"

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
        start_offset = path.stat().st_size if path.exists() else 0
        with path.open("a", encoding="utf-8", newline="\n") as fh:
            fh.writelines(encoded)
            fh.flush()
        self._update_seq_cache(session_id, events[-1].seq)
        self._update_seq_offset_index_after_append(session_id, events, encoded, start_offset)
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
        start_offset = path.stat().st_size if path.exists() else 0
        encoded = json.dumps(event.to_dict(), ensure_ascii=False, separators=(",", ":")) + "\n"
        with path.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(encoded)
            fh.flush()
        self._update_seq_cache(session_id, event.seq)
        self._update_seq_offset_index_after_append(session_id, [event], [encoded], start_offset)
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
            start_offset = path.stat().st_size if path.exists() else 0
            encoded = json.dumps(event.to_dict(), ensure_ascii=False, separators=(",", ":")) + "\n"
            with path.open("a", encoding="utf-8", newline="\n") as fh:
                fh.write(encoded)
                fh.flush()
            self._update_seq_cache(event.session_id, event.seq)
            self._update_seq_offset_index_after_append(
                event.session_id, [event], [encoded], start_offset
            )
            return event

    def read_all(self, session_id: str) -> List[RuntimeEvent]:
        return list(self.iter_events(session_id))

    def read_after_seq(self, session_id: str, after_seq: int) -> List[RuntimeEvent]:
        after = int(after_seq)
        entries = self._read_or_build_seq_offset_index(session_id)
        offset = self._offset_at_or_before_seq(entries, after + 1)
        return [
            ev for ev in self._iter_events_from_offset(session_id, offset)
            if ev.seq > after
        ]

    def read_latest(self, session_id: str, limit: int) -> List[RuntimeEvent]:
        limit = max(0, int(limit))
        if limit <= 0:
            return []
        entries = self._read_or_build_seq_offset_index(session_id)
        entry_back = max(1, (limit + _SEQ_OFFSET_STRIDE - 1) // _SEQ_OFFSET_STRIDE + 1)
        offset = int(entries[-entry_back][1]) if len(entries) >= entry_back else 0
        rows = deque(maxlen=limit)
        for ev in self._iter_events_from_offset(session_id, offset):
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
        A partial first line is discarded when reading a suffix. Any malformed
        complete or trailing row is surfaced as corruption instead of silently
        deleting facts from the projection.
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
        base_offset = size - read_size
        relative_offset = 0
        for raw_line in data.splitlines(keepends=True):
            line = raw_line.strip()
            if not line:
                relative_offset += len(raw_line)
                continue
            try:
                rows.append(RuntimeEvent.from_dict(json.loads(line.decode("utf-8"))))
            except Exception as exc:
                raise RuntimeEventLogCorruptionError(
                    session_id,
                    path,
                    byte_offset=base_offset + relative_offset,
                    detail=str(exc),
                ) from exc
            relative_offset += len(raw_line)
        return list(rows), reached_start

    def read_before_seq(self, session_id: str, before_seq: int, limit: int) -> List[RuntimeEvent]:
        before = int(before_seq)
        limit = max(0, int(limit))
        if limit <= 0:
            return []
        entries = self._read_or_build_seq_offset_index(session_id)
        eligible = [entry for entry in entries if int(entry[0]) < before]
        entry_back = max(1, (limit + _SEQ_OFFSET_STRIDE - 1) // _SEQ_OFFSET_STRIDE + 1)
        offset = int(eligible[-entry_back][1]) if len(eligible) >= entry_back else 0
        rows = deque(maxlen=limit)
        for ev in self._iter_events_from_offset(session_id, offset):
            if ev.seq < before:
                rows.append(ev)
            else:
                break
        return list(rows)

    def iter_events(self, session_id: str) -> Iterable[RuntimeEvent]:
        yield from self._iter_events_from_offset(session_id, 0)

    def _iter_events_from_offset(self, session_id: str, offset: int) -> Iterable[RuntimeEvent]:
        path = self.event_path(session_id)
        if not path.exists():
            return
        with path.open("rb") as fh:
            fh.seek(max(0, int(offset)))
            for line_number, raw_line in enumerate(fh, 1):
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    yield RuntimeEvent.from_dict(json.loads(line.decode("utf-8")))
                except Exception as exc:
                    raise RuntimeEventLogCorruptionError(
                        session_id,
                        path,
                        line_number=line_number,
                        detail=str(exc),
                    ) from exc

    @staticmethod
    def _offset_at_or_before_seq(entries: List[List[int]], target_seq: int) -> int:
        offset = 0
        target = int(target_seq)
        for seq, candidate in entries:
            if int(seq) > target:
                break
            offset = int(candidate)
        return offset

    def _read_or_build_seq_offset_index(self, session_id: str) -> List[List[int]]:
        path = self.seq_offset_index_path(session_id)
        event_path = self.event_path(session_id)
        if not event_path.exists():
            return []
        try:
            with path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            entries = data.get("entries") if isinstance(data, dict) else None
            if (
                int(data.get("index_version") or 0) == SEQ_OFFSET_INDEX_VERSION
                and isinstance(entries, list)
                and self._seq_offset_entries_valid(event_path, entries)
            ):
                return [[int(row[0]), int(row[1])] for row in entries]
        except Exception:
            pass
        return self._build_seq_offset_index(session_id)

    @staticmethod
    def _seq_offset_entries_valid(event_path: Path, entries: List[object]) -> bool:
        if not entries:
            return event_path.stat().st_size == 0
        last_seq = -1
        last_offset = -1
        try:
            for raw in entries:
                if not isinstance(raw, list) or len(raw) != 2:
                    return False
                seq, offset = int(raw[0]), int(raw[1])
                if seq <= last_seq or offset <= last_offset:
                    return False
                last_seq, last_offset = seq, offset
            if last_offset >= event_path.stat().st_size:
                return False
            with event_path.open("rb") as fh:
                fh.seek(last_offset)
                row = RuntimeEvent.from_dict(json.loads(fh.readline().decode("utf-8")))
            return int(row.seq) == last_seq
        except Exception:
            return False

    def _build_seq_offset_index(self, session_id: str) -> List[List[int]]:
        event_path = self.event_path(session_id)
        if not event_path.exists():
            return []
        entries: List[List[int]] = []
        offset = 0
        with event_path.open("rb") as fh:
            for ordinal, raw_line in enumerate(fh):
                line = raw_line.strip()
                if line:
                    try:
                        event = RuntimeEvent.from_dict(json.loads(line.decode("utf-8")))
                    except Exception as exc:
                        raise RuntimeEventLogCorruptionError(
                            session_id,
                            event_path,
                            line_number=ordinal + 1,
                            detail=str(exc),
                        ) from exc
                    if ordinal % _SEQ_OFFSET_STRIDE == 0:
                        entries.append([int(event.seq), int(offset)])
                offset += len(raw_line)
        self._write_seq_offset_index(session_id, entries)
        return entries

    def _write_seq_offset_index(self, session_id: str, entries: List[List[int]]) -> None:
        path = self.seq_offset_index_path(session_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.{uuid.uuid4().hex}.tmp")
        try:
            with tmp.open("x", encoding="utf-8") as fh:
                json.dump(
                    {
                        "index_version": SEQ_OFFSET_INDEX_VERSION,
                        "stride": _SEQ_OFFSET_STRIDE,
                        "entries": entries,
                    },
                    fh,
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, path)
        finally:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass

    def _update_seq_offset_index_after_append(
        self,
        session_id: str,
        events: List[RuntimeEvent],
        encoded: List[str],
        start_offset: int,
    ) -> None:
        """Best-effort maintenance for a rebuildable sparse index.

        Index failure must never turn a successfully appended fact into an
        apparent failed transaction; readers will rebuild it lazily.
        """
        path = self.seq_offset_index_path(session_id)
        if not path.exists():
            return
        try:
            with path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            if int(data.get("index_version") or 0) != SEQ_OFFSET_INDEX_VERSION:
                path.unlink(missing_ok=True)
                return
            entries = [list(row) for row in data.get("entries") or []]
            offset = int(start_offset)
            for event, row in zip(events, encoded):
                if (int(event.seq) - 1) % _SEQ_OFFSET_STRIDE == 0:
                    if not entries or int(entries[-1][0]) < int(event.seq):
                        entries.append([int(event.seq), offset])
                offset += len(row.encode("utf-8"))
            self._write_seq_offset_index(session_id, entries)
        except Exception:
            try:
                path.unlink(missing_ok=True)
            except Exception:
                pass

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
            try:
                self.seq_offset_index_path(session_id).unlink(missing_ok=True)
            except Exception:
                pass
            return {
                "kept": len(kept),
                "dropped": dropped,
                "duplicates": duplicates,
                "non_monotonic": non_monotonic,
            }

    def _cache_scope_for(self, session_id: str) -> str:
        return os.path.normcase(os.path.abspath(str(self.event_path(session_id))))

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
        scope = os.path.normcase(os.path.abspath(str(self.session_dir(safe_id))))
        with self._global_locks_guard:
            lock = self._global_locks.get(scope)
            if lock is None:
                lock = threading.RLock()
                self._global_locks[scope] = lock
            return lock

    @contextmanager
    def session_transaction(
        self,
        session_id: str,
        timeout_seconds: Optional[float] = None,
    ):
        """Serialize a session commit in this process and across workers.

        Lock acquisition is bounded so a wedged worker cannot suspend the ReAct
        loop indefinitely when an online caller supplies a timeout. Maintenance,
        migration, and repair callers remain unbounded by default.
        """
        safe_id = self._validate_session_id(session_id)
        lock = self._lock_for(safe_id)
        timeout = self._transaction_timeout_seconds(timeout_seconds)
        started = _active_uptime_seconds()
        deadline = None if timeout is None else started + timeout
        acquired = self._acquire_thread_lock(
            lock,
            session_id=safe_id,
            deadline=deadline,
            started=started,
        )
        if not acquired:
            logger.warning(
                "runtime_v2_transaction_timeout session=%s stage=in_process_lock timeout_seconds=%.3f",
                safe_id,
                timeout or 0.0,
            )
            raise RuntimeEventLogBusyError(safe_id, "in-process session lock", timeout or 0.0)
        try:
            session_dir = self.session_dir(safe_id)
            session_dir.mkdir(parents=True, exist_ok=True)
            lock_path = session_dir / ".events.lock"
            with lock_path.open("a+b") as fh:
                self._lock_file(
                    fh,
                    session_id=safe_id,
                    deadline=deadline,
                    timeout_seconds=timeout,
                    started=started,
                )
                try:
                    yield
                finally:
                    self._unlock_file(fh)
        finally:
            lock.release()

    @staticmethod
    def _lock_file(
        fh,
        *,
        session_id: str = "",
        deadline: Optional[float] = None,
        timeout_seconds: Optional[float] = None,
        started: Optional[float] = None,
    ) -> None:
        if deadline is None:
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
            return

        if os.name == "nt":
            import msvcrt
            fh.seek(0, os.SEEK_END)
            if fh.tell() == 0:
                fh.write(b"0")
                fh.flush()
        while True:
            try:
                fh.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                return
            except OSError as exc:
                if exc.errno not in {errno.EACCES, errno.EAGAIN, errno.EDEADLK}:
                    raise
                now = _active_uptime_seconds()
                SessionEventLog._log_slow_lock_wait(
                    session_id,
                    "cross-worker file lock",
                    started if started is not None else now,
                    now,
                )
                remaining = deadline - now
                if remaining <= 0:
                    timeout = max(0.0, float(timeout_seconds or 0.0))
                    logger.warning(
                        "runtime_v2_transaction_timeout session=%s stage=file_lock timeout_seconds=%.3f",
                        session_id,
                        timeout,
                    )
                    raise RuntimeEventLogBusyError(session_id, "cross-worker file lock", timeout) from exc
                time.sleep(min(0.05, remaining))

    @staticmethod
    def _acquire_thread_lock(
        lock: threading.RLock,
        *,
        session_id: str,
        deadline: Optional[float],
        started: float,
    ) -> bool:
        if deadline is None:
            lock.acquire()
            return True
        while True:
            now = _active_uptime_seconds()
            remaining = deadline - now
            if remaining <= 0:
                return False
            if lock.acquire(timeout=min(0.25, remaining)):
                return True
            SessionEventLog._log_slow_lock_wait(
                session_id,
                "in-process session lock",
                started,
                _active_uptime_seconds(),
            )

    @staticmethod
    def _log_slow_lock_wait(session_id: str, stage: str, started: float, now: float) -> None:
        waited = max(0.0, now - started)
        try:
            warning_seconds = max(
                0.0,
                float(os.getenv("RUNTIME_V2_SLOW_LOCK_WARNING_SECONDS", "2")),
            )
        except (TypeError, ValueError):
            warning_seconds = 2.0
        if warning_seconds and waited >= warning_seconds:
            # Log on coarse warning intervals rather than every polling tick.
            previous_bucket = int(max(0.0, waited - 0.25) / warning_seconds)
            current_bucket = int(waited / warning_seconds)
            if current_bucket > previous_bucket:
                logger.warning(
                    "runtime_v2_slow_lock_wait session=%s stage=%s waited_seconds=%.3f",
                    session_id,
                    stage,
                    waited,
                )

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

    @staticmethod
    def _transaction_timeout_seconds(value: Optional[float]) -> Optional[float]:
        if value is None:
            return None
        try:
            timeout = float(value)
        except (TypeError, ValueError):
            return None
        if timeout <= 0:
            return None
        return timeout
