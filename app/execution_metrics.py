from __future__ import annotations

import atexit
import copy
import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional


_lock = threading.RLock()
_root: Optional[Path] = None
_path_resolver: Optional[Callable[[str], str | Path]] = None
_sessions: Dict[str, dict] = {}
_last_started_order_ns = 0
_MAX_RUNS = max(1, int(os.getenv("EXECUTION_DASHBOARD_MAX_RUNS", "100")))
_heartbeat_controls: set[tuple[str, str]] = set()
_heartbeat_thread: Optional[threading.Thread] = None
_heartbeat_wakeup = threading.Event()
_flush_timers: Dict[str, threading.Timer] = {}
_flush_io_locks: Dict[str, threading.Lock] = {}
_flush_failed_sessions: set[str] = set()
_FLUSH_DELAY_SEC = max(
    0.05,
    min(1.0, float(os.getenv("EXECUTION_METRICS_FLUSH_DELAY_MS", "200")) / 1000.0),
)
_SLOW_OPERATION_MS = 100
_timing_logger = logging.getLogger("agent_harness")
_HEARTBEAT_INTERVAL_SEC = max(
    2.0,
    float(os.getenv("AGENT_RUN_HEARTBEAT_INTERVAL_SECONDS", "15")),
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _next_started_order_ns() -> int:
    """Return a wall-clock-based, process-monotonic run ordering key."""
    global _last_started_order_ns
    value = time.time_ns()
    _last_started_order_ns = max(value, _last_started_order_ns + 1)
    return _last_started_order_ns


def _run_sort_key(run: dict) -> tuple[str, int]:
    try:
        order = int(run.get("started_order_ns") or 0)
    except (TypeError, ValueError):
        order = 0
    return str(run.get("started_at") or ""), order


def configure(
    root: Path,
    *,
    path_resolver: Optional[Callable[[str], str | Path]] = None,
) -> None:
    global _root, _path_resolver
    _root = Path(root)
    _path_resolver = path_resolver
    with _lock:
        _heartbeat_controls.clear()
        _heartbeat_wakeup.set()
    try:
        import runtime_observability

        runtime_observability.configure(_root, path_resolver=path_resolver)
    except Exception:
        pass


def _path(session_id: str) -> Optional[Path]:
    if _path_resolver is not None and session_id:
        try:
            return Path(_path_resolver(session_id)) / "execution_metrics.json"
        except Exception:
            pass
    return (_root / session_id / "execution_metrics.json") if _root is not None and session_id else None


def _load(session_id: str) -> dict:
    cached = _sessions.get(session_id)
    if cached is not None:
        return cached
    data = {"version": 1, "session_id": session_id, "runs": []}
    path = _path(session_id)
    if path and path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict) and isinstance(loaded.get("runs"), list):
                data = loaded
        except Exception:
            pass
    _sessions[session_id] = data
    return data


def _write_now(session_id: str, data: dict) -> None:
    path = _path(session_id)
    if path is None:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        os.replace(tmp, path)
    except Exception:
        pass


def _flush_io_lock(session_id: str) -> threading.Lock:
    with _lock:
        return _flush_io_locks.setdefault(session_id, threading.Lock())


def _flush_session(session_id: str, *, fired_timer: bool = False) -> None:
    """Copy under the metrics lock; serialize and write outside it.

    The per-session I/O lock keeps a slow older flush from overwriting a newer
    snapshot. A mutation made during the write schedules the following flush.
    """
    started = time.perf_counter()
    io_lock = _flush_io_lock(session_id)
    with io_lock:
        io_acquired = time.perf_counter()
        with _lock:
            acquired = time.perf_counter()
            timer = _flush_timers.get(session_id)
            if fired_timer and timer is not threading.current_thread():
                return
            timer = _flush_timers.pop(session_id, None)
            if timer is not None and timer is not threading.current_thread():
                timer.cancel()
            _flush_failed_sessions.discard(session_id)
            data = _sessions.get(session_id)
            snapshot_data = copy.deepcopy(data) if data is not None else None
        copied = time.perf_counter()
        if snapshot_data is not None:
            _write_now(session_id, snapshot_data)
        finished = time.perf_counter()
    io_wait_ms = int((io_acquired - started) * 1000)
    lock_wait_ms = int((acquired - io_acquired) * 1000)
    lock_held_ms = int((copied - acquired) * 1000)
    io_write_ms = int((finished - copied) * 1000)
    if max(io_wait_ms, lock_wait_ms, lock_held_ms, io_write_ms) >= _SLOW_OPERATION_MS:
        _timing_logger.info(
            "execution_metrics_timing op=%s session=%s io_wait_ms=%d lock_wait_ms=%d lock_held_ms=%d io_write_ms=%d",
            "timer_flush" if fired_timer else "sync_flush",
            session_id, io_wait_ms, lock_wait_ms, lock_held_ms, io_write_ms,
        )


def _flush_timer_fired(session_id: str) -> None:
    _flush_session(session_id, fired_timer=True)


def _save(session_id: str, data: dict, *, force: bool = False) -> None:
    """Mark metrics dirty and coalesce whole-file rewrites."""
    _sessions[session_id] = data
    if force:
        _flush_failed_sessions.add(session_id)
        return
    if session_id in _flush_timers:
        return
    timer = threading.Timer(_FLUSH_DELAY_SEC, _flush_timer_fired, args=(session_id,))
    timer.daemon = True
    _flush_timers[session_id] = timer
    try:
        timer.start()
    except RuntimeError:
        # The terminal flush remains durable; never perform slow I/O while the
        # caller owns the global metrics lock.
        _flush_timers.pop(session_id, None)
        _flush_failed_sessions.add(session_id)


def flush(session_id: Optional[str] = None) -> None:
    """Durably flush pending metrics, normally used at terminal boundaries."""
    if session_id is not None:
        _flush_session(str(session_id))
        return
    with _lock:
        pending = set(_flush_timers) | set(_flush_failed_sessions)
    for sid in pending:
        _flush_session(sid)


atexit.register(flush)


def _run(data: dict, run_id: str, create: bool = True) -> Optional[dict]:
    for row in reversed(data.get("runs", [])):
        if str(row.get("run_id") or "") == run_id:
            return row
    if not create:
        return None
    row = {
        "run_id": run_id,
        "status": "running",
        "started_at": _now(),
        "started_order_ns": _next_started_order_ns(),
        "requests": [],
    }
    data.setdefault("runs", []).append(row)
    data["runs"] = data["runs"][-_MAX_RUNS:]
    return row


def _request(run: dict, react_iter: int, create: bool = True) -> Optional[dict]:
    for row in run.get("requests", []):
        if int(row.get("react_iter") or 0) == int(react_iter):
            return row
    if not create:
        return None
    row = {
        "react_iter": int(react_iter),
        "status": "preparing",
        "started_at": _now(),
        "context": {},
        "usage": {},
        "phases": {},
        "tools": [],
    }
    run.setdefault("requests", []).append(row)
    return row


def start_run(
    session_id: str,
    run_id: str,
    mode: str = "chat",
    user_preview: str = "",
) -> None:
    with _lock:
        data = _load(session_id)
        run = _run(data, run_id)
        if not run.get("started_order_ns"):
            run["started_order_ns"] = _next_started_order_ns()
        run.update({
            "status": "running",
            "mode": mode,
            "started_at": run.get("started_at") or _now(),
            "user_preview": str(user_preview or run.get("user_preview") or "").strip(),
        })
        _save(session_id, data)
    try:
        import runtime_observability

        runtime_observability.start_run(
            session_id,
            run_id,
            kind=mode,
        )
    except Exception:
        pass
    key = (str(session_id), str(run_id))
    with _lock:
        _heartbeat_controls.add(key)
    _ensure_heartbeat_thread()


def _heartbeat_pump() -> None:
    """Pulse every active run from one process-level native thread."""

    while True:
        _heartbeat_wakeup.wait(_HEARTBEAT_INTERVAL_SEC)
        _heartbeat_wakeup.clear()
        with _lock:
            active = list(_heartbeat_controls)
        for session_id, run_id in active:
            heartbeat_run(session_id, run_id, "running")


def _ensure_heartbeat_thread() -> bool:
    global _heartbeat_thread
    with _lock:
        if _heartbeat_thread is not None and _heartbeat_thread.is_alive():
            return True
        thread = threading.Thread(
            target=_heartbeat_pump,
            name="run-heartbeat-shared",
            daemon=True,
        )
        try:
            thread.start()
        except RuntimeError:
            # The watchdog also consults the precise asyncio task registry, so
            # loss of this diagnostic heartbeat must degrade gracefully.
            _heartbeat_thread = None
            return False
        _heartbeat_thread = thread
        return True


def finish_run(session_id: str, run_id: str, status: str, *, reason: str = "") -> None:
    with _lock:
        _heartbeat_controls.discard((str(session_id), str(run_id)))
        _heartbeat_wakeup.set()
    with _lock:
        data = _load(session_id)
        run = _run(data, run_id, create=False)
        if run is not None:
            run["status"] = status
            run["finished_at"] = _now()
            try:
                _started = datetime.fromisoformat(
                    str(run.get("started_at") or "").replace("Z", "+00:00")
                )
                _finished = datetime.fromisoformat(
                    str(run.get("finished_at") or "").replace("Z", "+00:00")
                )
                run["wall_ms"] = max(0, int(round((_finished - _started).total_seconds() * 1000)))
            except Exception:
                pass
            _save(session_id, data, force=True)
    flush(session_id)
    try:
        import runtime_observability

        runtime_observability.finish_run(session_id, run_id, status, reason=reason)
    except Exception:
        pass


def heartbeat_run(session_id: str, run_id: str, stage: str = "") -> None:
    try:
        import runtime_observability

        runtime_observability.heartbeat_run(session_id, run_id, stage=stage)
    except Exception:
        pass


def record_request(session_id: str, run_id: str, react_iter: int, **fields: Any) -> None:
    started = time.perf_counter()
    with _lock:
        acquired = time.perf_counter()
        data = _load(session_id)
        req = _request(_run(data, run_id), react_iter)
        for key, value in fields.items():
            if value is not None:
                req[key] = value
        _save(session_id, data)
    finished = time.perf_counter()
    wait_ms = int((acquired - started) * 1000)
    held_ms = int((finished - acquired) * 1000)
    if max(wait_ms, held_ms) >= _SLOW_OPERATION_MS:
        _timing_logger.info(
            "execution_metrics_timing op=record_request session=%s react_iter=%d lock_wait_ms=%d lock_held_ms=%d",
            session_id, react_iter, wait_ms, held_ms,
        )


def record_run_fields(session_id: str, run_id: str, **fields: Any) -> None:
    """Attach run-level timing/accounting fields (startup, round gaps, etc.)."""
    with _lock:
        data = _load(session_id)
        run = _run(data, run_id, create=False)
        if run is None:
            return
        for key, value in fields.items():
            if value is not None:
                run[key] = value
        _save(session_id, data)


def record_phase(session_id: str, run_id: str, react_iter: int, phase: str, values: Dict[str, Any], **meta: Any) -> None:
    started = time.perf_counter()
    with _lock:
        acquired = time.perf_counter()
        data = _load(session_id)
        req = _request(_run(data, run_id), react_iter)
        row = dict(req.setdefault("phases", {}).get(phase) or {})
        row.update({k: v for k, v in meta.items() if v is not None})
        merged_events = dict(row.get("events") or {}) if isinstance(row.get("events"), dict) else {}
        merged_events.update(dict(values or {}))
        row["events"] = merged_events
        if "total_ms" not in row:
            row["total_ms"] = sum(int(v or 0) for v in values.values() if isinstance(v, (int, float)))
        explicit_total = meta.get("total_ms")
        if explicit_total is not None:
            row["total_ms"] = int(explicit_total)
        req["phases"][phase] = row
        _save(session_id, data)
    finished = time.perf_counter()
    wait_ms = int((acquired - started) * 1000)
    held_ms = int((finished - acquired) * 1000)
    if max(wait_ms, held_ms) >= _SLOW_OPERATION_MS:
        _timing_logger.info(
            "execution_metrics_timing op=record_phase session=%s react_iter=%d phase=%s lock_wait_ms=%d lock_held_ms=%d",
            session_id, react_iter, phase, wait_ms, held_ms,
        )


def record_stream_event(session_id: str, run_id: str, react_iter: int, event: Dict[str, Any]) -> None:
    with _lock:
        data = _load(session_id)
        req = _request(_run(data, run_id), react_iter)
        phase = req.setdefault("phases", {}).setdefault("llm_stream", {"events": []})
        events = phase.setdefault("events", [])
        step = str(event.get("step") or "")
        existing = next((x for x in events if str(x.get("step") or "") == step), None)
        clean = {str(k): v for k, v in event.items() if isinstance(v, (str, int, float, bool)) or v is None}
        if existing is None:
            events.append(clean)
        else:
            existing.update(clean)
        at_ms = int(event.get("ms_since_api_start") or 0)
        phase["total_ms"] = max(int(phase.get("total_ms") or 0), at_ms)
        if step == "first_delta":
            req["status"] = "streaming"
            req["first_token_ms"] = at_ms
        elif step in {"stream_exhausted", "turn_ready"}:
            req["status"] = "completed"
            req["duration_ms"] = at_ms
        _save(session_id, data)


def record_usage(
    session_id: str,
    run_id: str,
    react_iter: int,
    usage: Dict[str, Any],
) -> Optional[dict]:
    with _lock:
        data = _load(session_id)
        req = _request(_run(data, run_id), react_iter)
        req["usage"] = {str(k): v for k, v in (usage or {}).items() if isinstance(v, (str, int, float, bool)) or v is None}
        _save(session_id, data)
    try:
        import runtime_observability

        return runtime_observability.record_usage(
            session_id,
            run_id,
            usage,
        )
    except Exception:
        return None


def record_tool(
    session_id: str,
    run_id: str,
    react_iter: int,
    tool: str,
    duration_ms: int,
    failed: bool,
    *,
    file_changes: Optional[list[dict]] = None,
) -> None:
    with _lock:
        data = _load(session_id)
        req = _request(_run(data, run_id), react_iter)
        req.setdefault("tools", []).append({
            "tool": str(tool or "tool"),
            "duration_ms": max(0, int(duration_ms)),
            "failed": bool(failed),
        })
        _save(session_id, data)
    try:
        import runtime_observability

        runtime_observability.heartbeat_run(session_id, run_id, stage=f"tool:{tool}")
        if file_changes:
            runtime_observability.record_file_changes(
                session_id,
                run_id,
                file_changes,
                tool=tool,
            )
    except Exception:
        pass


def snapshot(session_id: str) -> dict:
    # A snapshot is also a durable boundary, but disk I/O must not hold the
    # process-wide metrics lock used by active ReAct rounds.
    flush(str(session_id))
    with _lock:
        data = json.loads(json.dumps(_load(session_id), ensure_ascii=False))
    try:
        import runtime_observability

        data["observability"] = runtime_observability.snapshot(session_id)
    except Exception:
        pass
    return data


def snapshot_all(session_names: Optional[Dict[str, str]] = None) -> dict:
    """Return persisted metrics for every session, including inactive ones."""
    names = session_names or {}
    with _lock:
        root = _root
    disk_rows = _scan_persisted_metrics(root)
    with _lock:
        cached_ids = list(_sessions)
    cached_rows = {}
    for sid in cached_ids:
        with _lock:
            data = _sessions.get(sid)
            if data is not None:
                cached_rows[sid] = copy.deepcopy(data)
    disk_rows.update(cached_rows)
    sessions = []
    for sid, data in disk_rows.items():
        if not data.get("runs"):
            continue
        row = data
        row["session_name"] = str(names.get(sid) or sid)
        try:
            import runtime_observability

            row["observability"] = runtime_observability.snapshot(sid)
        except Exception:
            pass
        sessions.append(row)
    sessions.sort(key=lambda row: _run_sort_key((row.get("runs") or [{}])[-1]), reverse=True)
    return {"version": 1, "sessions": sessions}


def _scan_persisted_metrics(root: Optional[Path]) -> Dict[str, dict]:
    """Read inactive sessions without blocking active metrics writers."""
    rows: Dict[str, dict] = {}
    if root is None or not root.exists():
        return rows
    for path in root.rglob("execution_metrics.json"):
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            sid = str(loaded.get("session_id") or "")
            if sid and isinstance(loaded.get("runs"), list):
                rows[sid] = loaded
        except (OSError, ValueError, TypeError, AttributeError):
            continue
    return rows


def list_sessions(session_names: Optional[Dict[str, str]] = None) -> dict:
    """Lightweight session index for the dashboard (no request/phase payload)."""
    names = session_names or {}
    with _lock:
        root = _root
    disk_rows = _scan_persisted_metrics(root)
    with _lock:
        disk_rows.update(_sessions)
        sessions = []
        for sid, data in disk_rows.items():
            runs = data.get("runs") or []
            if not runs:
                continue
            last = runs[-1]
            sessions.append({
                "session_id": sid,
                "session_name": str(names.get(sid) or sid),
                "run_count": len(runs),
                "last_started_at": str(last.get("started_at") or ""),
                "last_finished_at": str(last.get("finished_at") or ""),
                "status": str(last.get("status") or ""),
                "_last_started_order_ns": _run_sort_key(last)[1],
            })
    sessions.sort(
        key=lambda row: (row["last_started_at"], row["_last_started_order_ns"]),
        reverse=True,
    )
    for row in sessions:
        row.pop("_last_started_order_ns", None)
    return {"sessions": sessions}
