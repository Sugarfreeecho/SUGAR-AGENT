"""Coalesced, bounded background checkpoints of the complete execution journal."""
from __future__ import annotations

import copy
import hashlib
import json
import logging
import os
import threading
import time
import uuid

from .derived_cache import estimate_bytes, seal_source, source_matches
from .versions import EXECUTION_RECOVERY_VERSION

logger = logging.getLogger(__name__)
STATE_FIELDS = ("seq", "records", "group", "turn", "revision", "last_final_seq", "ui_ids", "boundaries", "active_runs")


class RecoveryCheckpoint:
    _condition = threading.Condition()
    _pending: dict = {}
    _active: set = set()
    _cancelled: set = set()
    _workers = 0

    @staticmethod
    def path(journal, session_id):
        return journal.log.session_dir(session_id) / "snapshots" / "execution_recovery.chk"

    @classmethod
    def load(cls, journal, session_id):
        try:
            with cls.path(journal, session_id).open("rb") as fh:
                header = json.loads(fh.readline(16384))
                encoded = fh.read()
            if (not isinstance(header, dict) or header.get("version") != EXECUTION_RECOVERY_VERSION
                    or header.get("session_id") != session_id
                    or hashlib.sha256(encoded).hexdigest() != header.get("sha256")
                    or not source_matches(journal.log.event_path(session_id), header["source"], full=True)):
                return None
            state = json.loads(encoded)
            if (not isinstance(state, dict) or any(key not in state for key in STATE_FIELDS)
                    or not isinstance(state["records"], dict)
                    or not isinstance(state["ui_ids"], dict)
                    or not isinstance(state["active_runs"], dict)
                    or not isinstance(state["boundaries"], list)
                    or int(state["seq"]) != int(header["seq"])):
                return None
            if (any(not isinstance(state[key], str) for key in ("group", "turn"))
                    or any(not isinstance(state[key], int) or state[key] < 0
                           for key in ("seq", "revision", "last_final_seq"))
                    or any(not isinstance(row, dict) or row.get("execution_id") != identity
                           for identity, row in state["records"].items())):
                return None
            state["ui_ids"] = {int(key): value for key, value in state["ui_ids"].items()}
            state["boundaries"] = [(int(seq), kind) for seq, kind in state["boundaries"]]
            state["source"] = header["source"]
            state["offset"] = int(header["source"]["offset"])
            # The persisted signature belongs to the captured boundary, not to
            # newer facts that must still be replayed after loading it.
            state["signature"] = (header["source"]["mtime_ns"], header["source"]["size"])
            state["_checkpoint_seq"] = int(state["seq"])
            state["_checkpoint_time"] = time.monotonic()
            state["_estimated_bytes"] = estimate_bytes(state)
            state["_valid"] = True
            return state
        except (OSError, KeyError, TypeError, ValueError, OverflowError):
            return None

    @classmethod
    def schedule(cls, journal, session_id, state, *, force=False):
        seq = int(state["seq"])
        if not seq:
            return
        now = time.monotonic()
        if not force and (seq - int(state.get("_checkpoint_seq", 0)) < 512
                          and now - state.get("_checkpoint_time", 0) < 15):
            return
        key = str(cls.path(journal, session_id).resolve())
        with cls._condition:
            if key in cls._cancelled:
                return
            # Store one live state reference per session, not a multi-MB copy
            # for every queued update. The worker freezes it under its lock.
            if key not in cls._pending and len(cls._pending) >= 64:
                return
            if (key not in cls._pending and cls._pending
                    and sum(int(item[2].get("_estimated_bytes") or 0) for item in cls._pending.values())
                        + int(state.get("_estimated_bytes") or 0) > 64 * 1024 * 1024):
                return
            if (force and seq <= int(state.get("_checkpoint_seq") or 0)
                    and (key in cls._pending or key in cls._active)):
                return
            cls._pending[key] = (journal, session_id, state)
            state["_checkpoint_seq"] = seq
            state["_checkpoint_time"] = now
            if not cls._workers:
                worker = threading.Thread(target=cls._worker, name="execution-recovery-checkpoint", daemon=True)
                worker.start()
                cls._workers = 1
            cls._condition.notify_all()

    @classmethod
    def wait(cls, journal, session_id, timeout_seconds=5.0):
        key = str(cls.path(journal, session_id).resolve())
        deadline = time.monotonic() + max(0.0, timeout_seconds)
        with cls._condition:
            while key in cls._pending or key in cls._active:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                cls._condition.wait(remaining)
        return True

    @classmethod
    def cancel(cls, journal, session_id, timeout_seconds=0.5):
        key = str(cls.path(journal, session_id).resolve())
        with cls._condition:
            cls._cancelled.add(key)
            cls._pending.pop(key, None)
        with journal._guard:
            journal._cache.pop(str(journal.log.event_path(session_id).resolve()), None)
        return cls.wait(journal, session_id, timeout_seconds)

    @classmethod
    def _is_cancelled(cls, path):
        with cls._condition:
            return str(path.resolve()) in cls._cancelled

    @classmethod
    def _worker(cls):
        while True:
            with cls._condition:
                while not cls._pending:
                    cls._condition.wait()
                key = next(iter(cls._pending))
                journal, session_id, state = cls._pending.pop(key)
                cls._active.add(key)
            started = time.perf_counter()
            try:
                cls._write(journal, session_id, state)
                logger.info("execution_recovery_checkpoint session=%s ms=%s", session_id,
                            int((time.perf_counter() - started) * 1000))
            except Exception:
                logger.warning("execution_recovery_checkpoint_failed session=%s", session_id, exc_info=True)
            finally:
                with cls._condition:
                    cls._active.discard(key)
                    cls._condition.notify_all()

    @classmethod
    def _write(cls, journal, session_id, state):
        event_path = journal.log.event_path(session_id)
        path = cls.path(journal, session_id)
        with journal._session_lock(session_id):
            if (cls._is_cancelled(path) or not state.get("_valid")
                    or not source_matches(event_path, state.get("source") or {})):
                return
            frozen = copy.deepcopy({key: state[key] for key in STATE_FIELDS})
            source = dict(state["source"])
        # Hashing, encoding, flush and filesystem locks never hold the journal
        # or event transaction lock used by a generating session.
        source = seal_source(event_path, source)
        encoded = json.dumps(frozen, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        estimated_bytes = estimate_bytes(frozen)
        with journal._guard:
            state["_estimated_bytes"] = estimated_bytes
            journal._trim_cache_locked()
        header = {"version": EXECUTION_RECOVERY_VERSION, "session_id": session_id,
                  "seq": frozen["seq"], "source": source, "sha256": hashlib.sha256(encoded).hexdigest()}
        from .snapshot_store import SnapshotStore
        store = SnapshotStore(journal.log.root)
        # A distinct checkpoint-file lock also orders writers in other processes.
        with store._cross_process_checkpoint_lock(path, timeout_seconds=5.0):
            if cls._is_cancelled(path) or not source_matches(event_path, source):
                return
            try:
                with path.open("rb") as fh:
                    prior = json.loads(fh.readline(16384))
                if (isinstance(prior, dict) and prior.get("version") == EXECUTION_RECOVERY_VERSION
                        and int(prior.get("seq") or 0) > frozen["seq"]
                        and source_matches(event_path, prior["source"])):
                    return
            except (OSError, KeyError, TypeError, ValueError):
                pass
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
            try:
                with tmp.open("xb") as fh:
                    fh.write(json.dumps(header, separators=(",", ":")).encode("utf-8") + b"\n")
                    fh.write(encoded)
                    fh.flush()
                    os.fsync(fh.fileno())
                if not cls._is_cancelled(path) and source_matches(event_path, source):
                    tmp.replace(path)
            finally:
                tmp.unlink(missing_ok=True)
