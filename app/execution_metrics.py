from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional


_lock = threading.RLock()
_root: Optional[Path] = None
_path_resolver: Optional[Callable[[str], str | Path]] = None
_sessions: Dict[str, dict] = {}
_MAX_RUNS = max(1, int(os.getenv("EXECUTION_DASHBOARD_MAX_RUNS", "100")))
_heartbeat_controls: Dict[tuple[str, str], threading.Event] = {}
_HEARTBEAT_INTERVAL_SEC = max(
    2.0,
    float(os.getenv("AGENT_RUN_HEARTBEAT_INTERVAL_SECONDS", "15")),
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def configure(
    root: Path,
    *,
    path_resolver: Optional[Callable[[str], str | Path]] = None,
) -> None:
    global _root, _path_resolver
    _root = Path(root)
    _path_resolver = path_resolver
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


def _save(session_id: str, data: dict) -> None:
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


def _run(data: dict, run_id: str, create: bool = True) -> Optional[dict]:
    for row in reversed(data.get("runs", [])):
        if str(row.get("run_id") or "") == run_id:
            return row
    if not create:
        return None
    row = {"run_id": run_id, "status": "running", "started_at": _now(), "requests": []}
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
        previous = _heartbeat_controls.pop(key, None)
        if previous is not None:
            previous.set()
        stop = threading.Event()
        _heartbeat_controls[key] = stop

    def _pulse() -> None:
        while not stop.wait(_HEARTBEAT_INTERVAL_SEC):
            heartbeat_run(session_id, run_id, "running")

    threading.Thread(
        target=_pulse,
        name=f"run-heartbeat-{str(run_id)[:12]}",
        daemon=True,
    ).start()


def finish_run(session_id: str, run_id: str, status: str) -> None:
    with _lock:
        stop = _heartbeat_controls.pop((str(session_id), str(run_id)), None)
    if stop is not None:
        stop.set()
    with _lock:
        data = _load(session_id)
        run = _run(data, run_id, create=False)
        if run is not None:
            run["status"] = status
            run["finished_at"] = _now()
            _save(session_id, data)
    try:
        import runtime_observability

        runtime_observability.finish_run(session_id, run_id, status)
    except Exception:
        pass


def heartbeat_run(session_id: str, run_id: str, stage: str = "") -> None:
    try:
        import runtime_observability

        runtime_observability.heartbeat_run(session_id, run_id, stage=stage)
    except Exception:
        pass


def record_request(session_id: str, run_id: str, react_iter: int, **fields: Any) -> None:
    with _lock:
        data = _load(session_id)
        req = _request(_run(data, run_id), react_iter)
        for key, value in fields.items():
            if value is not None:
                req[key] = value
        _save(session_id, data)


def record_phase(session_id: str, run_id: str, react_iter: int, phase: str, values: Dict[str, Any], **meta: Any) -> None:
    with _lock:
        data = _load(session_id)
        req = _request(_run(data, run_id), react_iter)
        row = dict(req.setdefault("phases", {}).get(phase) or {})
        row.update({k: v for k, v in meta.items() if v is not None})
        merged_events = dict(row.get("events") or {}) if isinstance(row.get("events"), dict) else {}
        merged_events.update(dict(values or {}))
        row["events"] = merged_events
        if "total_ms" not in row:
            row["total_ms"] = sum(int(v or 0) for v in values.values() if isinstance(v, (int, float)))
        req["phases"][phase] = row
        _save(session_id, data)


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
        session_ids = set(_sessions.keys())
        if _root is not None and _root.exists():
            for path in _root.rglob("execution_metrics.json"):
                try:
                    loaded = json.loads(path.read_text(encoding="utf-8"))
                    sid = str(loaded.get("session_id") or "")
                    if sid:
                        session_ids.add(sid)
                except (OSError, ValueError, TypeError):
                    continue
        sessions = []
        for sid in session_ids:
            data = _load(sid)
            if not data.get("runs"):
                continue
            row = json.loads(json.dumps(data, ensure_ascii=False))
            row["session_name"] = str(names.get(sid) or sid)
            try:
                import runtime_observability

                row["observability"] = runtime_observability.snapshot(sid)
            except Exception:
                pass
            sessions.append(row)
        sessions.sort(
            key=lambda row: str(((row.get("runs") or [{}])[-1]).get("started_at") or ""),
            reverse=True,
        )
        return {"version": 1, "sessions": sessions}
