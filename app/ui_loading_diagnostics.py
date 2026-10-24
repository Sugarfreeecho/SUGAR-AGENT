"""Small, correlated loading records. No message bodies, paths or exception text."""
from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import datetime, timezone
import json
import math
import queue
import re
import sys
import threading
import time
import uuid

from fastapi import Request
from fastapi.responses import JSONResponse

_queue = queue.Queue(maxsize=1024)
_writer_lock = threading.Lock()
_drop_lock = threading.Lock()
_writer_started = False
_dropped = 0
_ID = re.compile(r"[A-Za-z0-9_-]{1,80}\Z")
_PATH = re.compile(r"/sessions/([^/]+)/(history_snapshot|messages)\Z")
_PHASES = {"fetch", "headers", "body", "fallback", "hydrate", "images", "layout", "scroll", "complete", "setup",
           "worker_queue", "read_page", "count", "user_turns", "context_tokens", "todo_plan", "execution_recovery", "serialize"}


def safe_id(value):
    return value if isinstance(value, str) and _ID.fullmatch(value) else ""


def _write_records():
    while True:
        record = _queue.get()
        try:
            sys.stderr.write("ui_loading " + json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
            sys.stderr.flush()
        except Exception:
            pass  # Diagnostics never fail a page request.
        finally:
            _queue.task_done()


def emit_event(record):
    global _writer_started, _dropped
    if not _writer_started:
        with _writer_lock:
            if not _writer_started:
                threading.Thread(target=_write_records, name="ui-loading-log", daemon=True).start()
                _writer_started = True
    record = {"logged_at": datetime.now(timezone.utc).isoformat(), **record}
    with _drop_lock:
        if _dropped:
            record["dropped_records"] = _dropped
        try:
            _queue.put_nowait(record)
        except queue.Full:
            _dropped += 1
        else:
            _dropped = 0


def mark_phase(request, phase):
    if request is not None:
        trace = request.scope.get("state", {}).get("ui_loading_trace")
        if trace is not None:
            trace["phase"] = phase


class LoadingDiagnosticsMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "lifespan":
            # The production entrypoint replaces router.lifespan_context after
            # webui import. Observe ASGI startup so both entrypoints work.
            monitor = None

            async def lifecycle_send(message):
                nonlocal monitor
                if message["type"] == "lifespan.startup.complete":
                    monitor = asyncio.create_task(monitor_event_loop(), name="ui-loading-loop-lag")
                await send(message)

            try:
                return await self.app(scope, receive, lifecycle_send)
            finally:
                if monitor is not None:
                    monitor.cancel()
                    with suppress(asyncio.CancelledError):
                        await monitor
        path = scope.get("path", "")
        match = _PATH.fullmatch(path)
        if scope["type"] != "http" or not (match or path in {"/sessions", "/sessions/state", "/sessions/index/repair"}):
            return await self.app(scope, receive, send)
        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        request_id = safe_id(headers.get(b"x-request-id", b"").decode("ascii", "ignore")) or uuid.uuid4().hex
        load_id = safe_id(headers.get(b"x-ui-load-id", b"").decode("ascii", "ignore"))
        trace = {"request_id": request_id, "load_id": load_id, "session_id": safe_id(match[1]) if match else "",
                 "route": match[2] if match else path.removeprefix("/sessions").strip("/") or "list",
                 "phase": "setup"}
        scope.setdefault("state", {})["ui_loading_trace"] = trace
        started = time.perf_counter()
        headers_ms = None
        status_code, byte_count, disconnected, completed = 0, 0, False, False
        outcome, error_name = "incomplete", ""
        emit_event({"event": "server_start", **trace})

        async def read():
            nonlocal disconnected
            message = await receive()
            if message["type"] == "http.disconnect":
                disconnected = True
            return message

        async def write(message):
            nonlocal headers_ms, status_code, byte_count, completed
            if message["type"] == "http.response.start":
                headers_ms = round((time.perf_counter() - started) * 1000, 3)
                status_code = message["status"]
                message = {**message, "headers": [(key, value) for key, value in message.get("headers", [])
                           if key.lower() != b"x-request-id"] + [(b"x-request-id", request_id.encode("ascii"))]}
            elif message["type"] == "http.response.body":
                byte_count += len(message.get("body", b""))
            await send(message)
            if message["type"] == "http.response.body" and not message.get("more_body", False):
                completed = True

        try:
            await self.app(scope, read, write)
            outcome = "disconnected" if disconnected else "success" if completed and status_code < 400 else "http_error" if status_code >= 400 else "incomplete"
        except asyncio.CancelledError:
            outcome = "cancelled"
            raise
        except Exception as error:
            outcome, error_name = "exception", type(error).__name__
            raise
        finally:
            emit_event({"event": "server_end", **trace, "status": outcome, "error_name": error_name or trace.get("error_name", ""),
                        "status_code": status_code, "headers_ms": headers_ms, "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
                        "bytes": byte_count, "response_complete": completed, "disconnect_observed": disconnected})


def sanitize_client_record(raw):
    if (not isinstance(raw, dict) or not isinstance(raw.get("event"), str)
            or raw["event"] not in {"load_start", "load_end", "request_start", "request_end"}):
        return None
    out = {"event": "client_" + raw["event"]}
    for key in ("session_id", "request_id", "load_id", "error_name"):
        out[key] = safe_id(raw.get(key))
    for key, values in {
        "kind": {"history", "session_list"}, "phase": _PHASES,
        "status": {"success", "failed", "cancelled"},
        "reason": {"timeout", "cancelled", "network", "http", "json_parse", "invalid_payload", "render", "unknown"},
        "route": {"history_snapshot", "messages", "state", "list"},
    }.items():
        if isinstance(raw.get(key), str) and raw[key] in values:
            out[key] = raw[key]
    for key in ("elapsed_ms", "headers_ms", "body_ms", "timeout_ms", "status_code", "attempt", "queue_ms", "ttfb_ms", "network_body_ms", "after_network_ms", "server_ms", "fetch_ms", "fallback_ms", "hydrate_ms", "images_ms", "layout_ms", "scroll_ms"):
        value = raw.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and 0 <= value <= 86400000:
            out[key] = round(value, 3)
    if isinstance(raw.get("started_at"), str) and re.fullmatch(r"[0-9T:.+Z-]{10,40}", raw["started_at"]):
        out["started_at"] = raw["started_at"]
    return out


async def monitor_event_loop():
    # This clock includes stalls before ASGI can even receive a page request.
    # Healthy ticks do not produce records or inspect any session data.
    interval = 2.0
    while True:
        expected = time.perf_counter() + interval
        expected_at = datetime.now(timezone.utc).timestamp() + interval
        await asyncio.sleep(interval)
        lag_ms = (time.perf_counter() - expected) * 1000
        if lag_ms >= 500:
            emit_event({"event": "server_loop_lag", "lag_ms": round(lag_ms, 3),
                        "expected_at": datetime.fromtimestamp(expected_at, timezone.utc).isoformat(),
                        "interval_ms": int(interval * 1000)})


def register_loading_diagnostics(app):
    app.add_middleware(LoadingDiagnosticsMiddleware)

    @app.post("/api/ui-loading-diagnostics")
    async def client_records(request: Request):
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 32768:
                return JSONResponse({"ok": False}, status_code=413)
        try:
            records = json.loads(body).get("records")
        except (ValueError, AttributeError):
            return JSONResponse({"ok": False}, status_code=400)
        if not isinstance(records, list) or len(records) > 32:
            return JSONResponse({"ok": False}, status_code=400)
        for raw in records:
            record = sanitize_client_record(raw)
            if record:
                emit_event(record)
        return JSONResponse({"ok": True})
