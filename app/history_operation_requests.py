"""Bounded single-flight receipts for retrying a branch HTTP request.

Receipts last ten minutes in this process; they are not durable across restart.
"""
import asyncio
from collections import OrderedDict
import time


class HistoryOperationRequests:
    def __init__(self, *, limit=128, ttl=600):
        self.limit, self.ttl = limit, ttl
        self.entries = OrderedDict()

    async def run(self, key, fingerprint, create):
        now = time.monotonic()
        for old_key, (_, task, completed) in list(self.entries.items()):
            if task.done() and completed is not None and now - completed >= self.ttl:
                self.entries.pop(old_key, None)
        if key in self.entries:
            previous, task, _ = self.entries[key]
            if previous != fingerprint:
                return {"ok": False, "error": "branch_request_conflict"}
            self.entries.move_to_end(key)
            # A completed receipt can also be read by a new test event loop.
            return task.result() if task.done() else await asyncio.shield(task)
        if len(self.entries) >= self.limit:
            evict = next((old for old, (_, task, _) in self.entries.items() if task.done()), None)
            if evict is None:
                return {"ok": False, "error": "branch_requests_busy"}
            self.entries.pop(evict)

        async def perform():
            try:
                result = await create()
            except BaseException:
                self.entries.pop(key, None)
                raise
            if (getattr(result, 'status_code', 200) >= 400
                    or (isinstance(result, dict) and result.get('ok') is False)):
                self.entries.pop(key, None)
            else:
                self.entries[key] = (fingerprint, asyncio.current_task(), time.monotonic())
            return result

        task = asyncio.create_task(perform(), name='branch-session-request')
        self.entries[key] = (fingerprint, task, None)
        # Retrieve errors even if the requesting browser has already left.
        task.add_done_callback(lambda done: None if done.cancelled() else done.exception())
        return await asyncio.shield(task)
