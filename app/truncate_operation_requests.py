"""Process-local, bounded receipts for asynchronous destructive history edits.

An HTTP disconnect must not replay a truncation. Unknown receipts (including
after a restart) are explicitly inconclusive, never treated as success.
"""
import asyncio
import json
import logging
import time
from collections import OrderedDict

logger = logging.getLogger(__name__)


class TruncateOperationRequests:
    def __init__(self, *, limit=256, ttl=1800):
        self.limit = limit
        self.ttl = ttl
        self.entries = OrderedDict()

    def _prune(self):
        now = time.monotonic()
        for key, entry in list(self.entries.items()):
            if entry["completed"] is not None and now - entry["completed"] >= self.ttl:
                self.entries.pop(key, None)

    def status(self, session_id, request_id):
        self._prune()
        entry = self.entries.get((session_id, request_id))
        if entry is None:
            return {"ok": False, "status": "unknown", "error": "truncate_result_unknown"}
        if entry["result"] is None:
            return {"ok": True, "status": "pending", "request_id": request_id}
        return dict(entry["result"], status="completed", request_id=request_id)

    def start(self, session_id, request_id, fingerprint, create):
        self._prune()
        key = (session_id, request_id)
        entry = self.entries.get(key)
        if entry is not None:
            if entry["fingerprint"] != fingerprint:
                return {"ok": False, "error": "truncate_request_conflict"}
            return self.status(*key)
        # Different tabs/IDs must not queue multiple destructive edits against
        # the same history while the outcome of the first one is pending.
        if any(sid == session_id and item["result"] is None
               for (sid, _), item in self.entries.items()):
            return {"ok": False, "error": "truncate_session_busy"}
        if len(self.entries) >= self.limit:
            evict = next((old for old, item in self.entries.items() if item["result"] is not None), None)
            if evict is None:
                return {"ok": False, "error": "truncate_requests_busy"}
            self.entries.pop(evict)
        entry = {"fingerprint": fingerprint, "result": None, "completed": None, "task": None}
        self.entries[key] = entry

        async def perform():
            try:
                response = await create()
                result = json.loads(response.body) if hasattr(response, "body") else dict(response)
                if not isinstance(result, dict):
                    raise ValueError("invalid truncation response")
                entry["result"] = result
            except asyncio.CancelledError:
                entry["result"] = {"ok": False, "error": "truncate_result_unknown"}
                raise
            except Exception:
                logger.exception("history truncation request failed: session=%s", session_id)
                entry["result"] = {"ok": False, "error": "truncate_result_unknown"}
            finally:
                entry["completed"] = time.monotonic()

        entry["task"] = asyncio.create_task(perform(), name="truncate-session-request")
        return self.status(*key)
