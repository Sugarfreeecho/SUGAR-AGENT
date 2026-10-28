"""Shared admission owner for HTTP, transports, workflows and plugin workers."""
from __future__ import annotations

import asyncio


class SessionExecutionCoordinator:
    def __init__(self, dependencies):
        self.dependencies = dependencies

    def reserve(self, session_id, run_id=""):
        return self.dependencies.reserve_start(session_id, run_id)

    def release(self, session_id, token=""):
        self.dependencies.release_start(session_id, token)

    async def reserve_async(self, session_id, run_id=""):
        return await asyncio.to_thread(self.reserve, session_id, run_id)
