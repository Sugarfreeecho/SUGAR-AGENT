"""One-use host context tickets for in-process MCP servers.

Tickets travel in MCP request metadata, never in model-visible arguments.
The process-local store binds each ticket to one server/tool/argument digest;
an HTTP client cannot manufacture session or run authority.
"""
from __future__ import annotations

import hashlib
import json
import secrets
import threading
import time

META_KEY = "myagent/host-context"
TTL_SECONDS = 900.0
_lock = threading.Lock()
_tickets: dict[str, tuple] = {}


def _digest(arguments: dict) -> str:
    return hashlib.sha256(json.dumps(arguments, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def issue(alias: str, name: str, arguments: dict, *, session_id: str,
          run_id: str = "", tool_call_id: str = "") -> dict:
    if not str(session_id or "").strip():
        raise ValueError("MCP host context requires a session_id")
    now = time.monotonic()
    token = secrets.token_urlsafe(32)
    item = (now + TTL_SECONDS, alias, name, _digest(arguments),
            {"session_id": str(session_id), "run_id": str(run_id or ""),
             "tool_call_id": str(tool_call_id or "")})
    with _lock:
        for stale in [key for key, row in _tickets.items() if row[0] <= now]:
            _tickets.pop(stale, None)
        if len(_tickets) >= 4096:
            raise RuntimeError("Too many pending MCP host context tickets")
        _tickets[token] = item
    return {META_KEY: token}


def revoke(meta: dict) -> None:
    with _lock:
        _tickets.pop(meta.get(META_KEY), None)


def consume(meta: dict, alias: str, name: str, arguments: dict) -> dict:
    token = meta.get(META_KEY) if isinstance(meta, dict) else None
    if not isinstance(token, str):
        raise ValueError("Missing trusted MCP host context")
    with _lock:
        item = _tickets.pop(token, None)
    if (item is None or item[0] <= time.monotonic()
            or item[1:4] != (alias, name, _digest(arguments))):
        raise ValueError("Invalid or expired MCP host context")
    return dict(item[4])
