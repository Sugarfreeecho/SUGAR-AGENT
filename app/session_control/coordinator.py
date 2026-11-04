"""Shared admission owner for HTTP, transports, workflows and plugin workers."""
from __future__ import annotations

import asyncio
import threading


class SessionExecutionCoordinator:
    def __init__(self, dependencies):
        self.dependencies = dependencies

    def reserve(self, session_id, run_id=""):
        return self.dependencies.reserve_start(session_id, run_id)

    def release(self, session_id, token=""):
        self.dependencies.release_start(session_id, token)

    async def reserve_async(self, session_id, run_id="", *, pool=None):
        # Cancellation cannot stop a reservation already inside a file/host
        # lock. Transfer its token under a lock so shutdown cannot orphan it.
        lock, state = threading.Lock(), {"cancelled": False, "token": None}
        def reserve():
            token = self.reserve(session_id, run_id)
            with lock:
                cancelled = state["cancelled"]
                if not cancelled:
                    state["token"] = token
            if cancelled and token:
                self.release(session_id, token)
                return None
            return token
        try:
            if pool:
                return await pool.run("@reservation", reserve)
            return await asyncio.to_thread(reserve)
        except asyncio.CancelledError:
            with lock:
                state["cancelled"] = True
                token = state["token"]
            if token:
                self.release(session_id, token)
            raise
