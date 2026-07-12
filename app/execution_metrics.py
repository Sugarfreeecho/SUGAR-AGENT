from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


_lock = threading.RLock()
_root: Optional[Path] = None
_sessions: Dict[str, dict] = {}
_MAX_RUNS = max(1, int(os.getenv("EXECUTION_DASHBOARD_MAX_RUNS", "100")))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def configure(root: Path) -> None:
    global _root
    _root = Path(root)


def _path(session_id: str) -> Optional[Path]:
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


def start_run(session_id: str, run_id: str, mode: str = "chat", user_preview: str = "") -> None:
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


def finish_run(session_id: str, run_id: str, status: str) -> None:
    with _lock:
        data = _load(session_id)
        run = _run(data, run_id, create=False)
        if run is not None:
            run["status"] = status
            run["finished_at"] = _now()
            _save(session_id, data)


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


def record_usage(session_id: str, run_id: str, react_iter: int, usage: Dict[str, Any]) -> None:
    with _lock:
        data = _load(session_id)
        req = _request(_run(data, run_id), react_iter)
        req["usage"] = {str(k): v for k, v in (usage or {}).items() if isinstance(v, (str, int, float, bool)) or v is None}
        _save(session_id, data)


def record_tool(session_id: str, run_id: str, react_iter: int, tool: str, duration_ms: int, failed: bool) -> None:
    with _lock:
        data = _load(session_id)
        req = _request(_run(data, run_id), react_iter)
        req.setdefault("tools", []).append({
            "tool": str(tool or "tool"),
            "duration_ms": max(0, int(duration_ms)),
            "failed": bool(failed),
        })
        _save(session_id, data)


def snapshot(session_id: str) -> dict:
    with _lock:
        return json.loads(json.dumps(_load(session_id), ensure_ascii=False))


def snapshot_all(session_names: Optional[Dict[str, str]] = None) -> dict:
    """Return persisted metrics for every session, including inactive ones."""
    names = session_names or {}
    with _lock:
        session_ids = set(_sessions.keys())
        if _root is not None and _root.exists():
            for path in _root.glob("*/execution_metrics.json"):
                session_ids.add(path.parent.name)
        sessions = []
        for sid in session_ids:
            data = _load(sid)
            if not data.get("runs"):
                continue
            row = json.loads(json.dumps(data, ensure_ascii=False))
            row["session_name"] = str(names.get(sid) or sid)
            sessions.append(row)
        sessions.sort(
            key=lambda row: str(((row.get("runs") or [{}])[-1]).get("started_at") or ""),
            reverse=True,
        )
        return {"version": 1, "sessions": sessions}
