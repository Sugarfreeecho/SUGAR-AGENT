"""Explicit budgets for acquisition, orchestration and model execution."""
from __future__ import annotations

import asyncio
import contextvars
import os
import threading
from collections import Counter, deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from .errors import ControlError


def setting(name, default):
    value = int(os.getenv("MYAGENT_" + name, str(default)))
    if value < 1:
        raise ValueError("MYAGENT_" + name + " must be positive")
    return value


@dataclass(frozen=True)
class QueueLimits:
    total: int = 1024
    source: int = 256
    session: int = 64
    task: int = 64

    @classmethod
    def environment(cls):
        return cls(*(setting("CONTROL_QUEUE_" + name.upper(), default) for name, default in
                     (("total", 1024), ("source", 256), ("session", 64), ("task", 64))))


SOURCE_SQL = """CASE WHEN json_extract(request,'$._source.id') IS NOT NULL
    THEN 'host:' || json_extract(request,'$._source.id')
    WHEN json_extract(request,'$._automation_id') IS NOT NULL THEN 'automation:' || principal
    ELSE 'caller:' || principal END"""


def source_key(operation):
    p = operation.get("request", {})
    if (p.get("_source") or {}).get("id"):
        return "host:" + p["_source"]["id"]
    return ("automation:" if p.get("_automation_id") else "caller:") + operation["principal"]


class BoundedWorkPool:
    """Bound submitted work, not merely threads; cancellation retains running slots."""
    def __init__(self, name, workers, pending=0, per_owner=None, on_complete=None):
        self.name, self.workers, self.capacity = name, workers, workers + pending
        self.per_owner = per_owner or self.capacity
        self.on_complete = on_complete
        self._executor = None
        self._lock = threading.Lock()
        self._owners = Counter()
        self._futures = set()
        self._future_owners = {}
        self.closed = False

    def available(self, owner=""):
        with self._lock:
            return not self.closed and len(self._futures) < self.capacity and self._owners[owner] < self.per_owner

    def try_submit(self, owner, function, *args, **kwargs):
        loop, context = asyncio.get_running_loop(), contextvars.copy_context()
        with self._lock:
            if self.closed or len(self._futures) >= self.capacity or self._owners[owner] >= self.per_owner:
                return None
            if self._executor is None:
                self._executor = ThreadPoolExecutor(max_workers=self.workers, thread_name_prefix=self.name)
            future = self._executor.submit(context.run, function, *args, **kwargs)
            self._futures.add(future)
            self._future_owners[future] = owner
            self._owners[owner] += 1
        def completed(done):
            with self._lock:
                self._futures.discard(done)
                self._future_owners.pop(done, None)
                self._owners[owner] -= 1
                if not self._owners[owner]:
                    self._owners.pop(owner, None)
            if self.on_complete and not loop.is_closed():
                try:
                    loop.call_soon_threadsafe(self.on_complete)
                except RuntimeError:
                    pass  # The loop can close between the check and this callback.
        future.add_done_callback(completed)
        return asyncio.wrap_future(future, loop=loop)

    async def run(self, owner, function, *args, **kwargs):
        future = self.try_submit(owner, function, *args, **kwargs)
        if future is None:
            raise ControlError("work_pool_full", "Worker budget is full; retry after existing work completes", status=429,
                               details={"pool": self.name, "retry_after": 1})
        try:
            return await asyncio.shield(future)
        except asyncio.CancelledError:
            def consume(done):
                if not done.cancelled():
                    done.exception()
            future.add_done_callback(consume)
            raise

    def cancel_owner(self, owner):
        with self._lock:
            futures = [future for future, source in self._future_owners.items() if source == owner]
        return sum(future.cancel() for future in futures)

    def close(self):
        with self._lock:
            self.closed = True
            executor = self._executor
        if executor:
            executor.shutdown(wait=False, cancel_futures=True)

    def snapshot(self):
        with self._lock:
            return {"workers": self.workers, "capacity": self.capacity, "outstanding": len(self._futures),
                    "per_owner": self.per_owner, "owners": dict(self._owners), "closed": self.closed}


class FairSources:
    """Round robin between durable source queues while retaining session FIFO heads."""
    def __init__(self):
        self.order = deque()

    def ordered(self, operations):
        groups = {}
        for op in operations:
            groups.setdefault(source_key(op), deque()).append(op)
        self.order = deque(key for key in self.order if key in groups)
        self.order.extend(key for key in groups if key not in self.order)
        order = deque(self.order)
        result = []
        while order:
            key = order.popleft()
            result.append(groups[key].popleft())
            if groups[key]:
                order.append(key)
        if self.order:
            self.order.rotate(-1)
        return result


class ControlResources:
    def __init__(self, on_complete=None):
        self.io = BoundedWorkPool("control-io", setting("MONITOR_IO_WORKERS", 4), setting("MONITOR_IO_PENDING", 16),
                                  setting("MONITOR_IO_PER_SOURCE", 2))
        self.business = BoundedWorkPool("control-business", setting("MONITOR_BUSINESS_WORKERS", 4),
                                      setting("MONITOR_BUSINESS_PENDING", 16), setting("MONITOR_BUSINESS_PER_SOURCE", 2))
        self.runtime = BoundedWorkPool("control-run", setting("CONTROL_RUN_WORKERS", 4), pending=0,
                                     per_owner=setting("CONTROL_RUN_PER_SOURCE", 2), on_complete=on_complete)
        self.per_task = setting("CONTROL_RUN_PER_TASK", 1)
        self.fair = FairSources()

    def close(self):
        for pool in (self.io, self.business, self.runtime):
            pool.close()

    def snapshot(self):
        return {name: getattr(self, name).snapshot() for name in ("io", "business", "runtime")}
