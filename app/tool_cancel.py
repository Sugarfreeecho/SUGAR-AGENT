"""Cooperative cancellation for synchronous tools running in worker threads.

``asyncio.to_thread`` cannot be interrupted, and Python cannot kill a running
thread.  Read-only tools therefore get a per-call ``threading.Event``: the
awaiting coroutine sets it when the tool deadline expires, and the worker
checks it between directory scans and returns partial results instead of
burning a core until the process restarts.
"""
from __future__ import annotations

import contextvars
import threading
from typing import Optional

_CANCEL_EVENT: contextvars.ContextVar[Optional[threading.Event]] = contextvars.ContextVar(
    "tool_cancel_event", default=None
)


def set_cancel_event(event: Optional[threading.Event]):
    """Install ``event`` for the current context; returns a reset token."""
    return _CANCEL_EVENT.set(event)


def reset_cancel_event(token) -> None:
    _CANCEL_EVENT.reset(token)


def current_cancel_event() -> Optional[threading.Event]:
    return _CANCEL_EVENT.get()
