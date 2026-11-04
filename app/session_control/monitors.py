"""One deadline/event scheduler; reference-counted acquisition and bounded dispatch."""
from __future__ import annotations

import asyncio
import hashlib
import heapq
import inspect
import itertools
import json
import logging
import time
from collections import Counter
from dataclasses import dataclass, field

from .errors import ControlError
from .resources import setting

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class MonitorKey:
    kind: str
    resource: str
    namespace: str
    options_digest: str = ""

    @classmethod
    def make(cls, kind, resource, *, namespace, options=None):
        if not all(isinstance(v, str) and v for v in (kind, resource, namespace)):
            raise ValueError("Monitor keys require kind, resource and an authorization namespace")
        digest = hashlib.sha256(json.dumps(options or {}, sort_keys=True, allow_nan=False).encode()).hexdigest()
        return cls(kind, resource, namespace, digest)


@dataclass
class Source:
    key: MonitorKey
    collect: object
    interval: float
    subscribers: dict = field(default_factory=dict)
    cleanup: object = None
    events: frozenset = frozenset()
    due: float = 0
    version: int = 0
    running: object = None
    dirty: bool = False
    failures: int = 0


class MonitorSubscription:
    def __init__(self, hub, source, owner):
        self.hub, self.source, self.key, self.owner = hub, source, source.key, owner
        self.closed = False

    def wake(self):
        if not self.done():
            self.hub.wake(self.key)

    async def close(self):
        if not self.closed:
            self.closed = True
            await self.hub.unsubscribe(self.key, self.owner, expected_source=self.source)

    def done(self):
        return self.closed or self.hub.sources.get(self.key) is not self.source or self.owner not in self.source.subscribers


class SharedMonitorHub:
    def __init__(self, resources, enabled=None):
        self.resources = resources
        self.enabled = enabled or (lambda _: True)
        self.limit = setting("MONITOR_CONCURRENCY", 4)
        self.per_namespace = min(self.limit, setting("MONITOR_PER_SOURCE", 2))
        self.namespace_sources = setting("MONITOR_SOURCES_PER_NAMESPACE", 32)
        self.source_limit = setting("MONITOR_SOURCES", 256)
        self.subscription_limit = setting("MONITOR_SUBSCRIPTIONS", 1024)
        self.sources, self.heap = {}, []
        self.event_sources = {}
        self.counter = itertools.count()
        self.loop = self.task = self.changed = None
        self.active = set()
        self.active_namespaces = Counter()
        self.closing = False
        self._listener = None
        self._inventories = {}
        self._revocations = set()

    async def start(self):
        if self.task and not self.task.done():
            return
        self.loop, self.changed, self.closing = asyncio.get_running_loop(), asyncio.Event(), False
        from session_event_bus import add_event_listener
        def listener(_sid, event):
            kind = event.get("type")
            if kind not in self.event_sources and kind != "lifecycle_changed":
                return
            def changed():
                if kind == "lifecycle_changed":
                    for entry in self._inventories.values():
                        entry["until"] = 0.
                for key in tuple(self.event_sources.get(kind, ())):
                    self.wake(key)
            if not self.loop.is_closed():
                try:
                    self.loop.call_soon_threadsafe(changed)
                except RuntimeError:
                    pass
        self._listener = listener
        add_event_listener(listener)
        self.task = asyncio.create_task(self._loop(), name="shared-monitor-hub")

    def subscribe(self, key, owner, collect, *, consume=None, interval=1., cleanup=None, events=(), immediate=True):
        if self.closing or not self.loop or self.loop is not asyncio.get_running_loop():
            raise ControlError("monitor_unavailable", "Register monitors on the running backend loop", status=503)
        if not owner or not callable(collect) or not .05 <= float(interval) <= 86400:
            raise ValueError("Invalid monitor owner, collector or interval")
        source = self.sources.get(key)
        count = sum(len(s.subscribers) for s in self.sources.values())
        if (not source and len(self.sources) >= self.source_limit) or (count >= self.subscription_limit and (not source or owner not in source.subscribers)):
            raise ControlError("monitor_full", "Monitor subscription budget is full", status=429)
        if not source and sum(k.namespace == key.namespace for k in self.sources) >= self.namespace_sources:
            raise ControlError("monitor_full", "This source namespace exhausted its monitor budget", status=429)
        if source and owner in source.subscribers:
            raise ControlError("monitor_conflict", "This owner already subscribed; close its old subscription first", status=409)
        if source and (source.interval != interval or source.events != frozenset(events)):
            raise ControlError("monitor_conflict", "Shared sources must use identical acquisition options", status=409)
        if source is None:
            source = Source(key, collect, float(interval), cleanup=cleanup, events=frozenset(events))
            self.sources[key] = source
            for kind in source.events:
                self.event_sources.setdefault(kind, set()).add(key)
            self._schedule(source, time.monotonic() + (0 if immediate else interval))
        source.subscribers[owner] = consume
        return MonitorSubscription(self, source, owner)

    def _schedule(self, source, when):
        source.due, source.version = when, source.version + 1
        heapq.heappush(self.heap, (when, next(self.counter), source.key, source.version))
        # Repeated pulses replace deadlines; cap obsolete heap entries too.
        if len(self.heap) > max(32, len(self.sources) * 4):
            self.heap = [(s.due, next(self.counter), s.key, s.version) for s in self.sources.values() if not s.running]
            heapq.heapify(self.heap)
        self.changed.set()

    def wake(self, key):
        if self.closing or not self.loop or self.loop.is_closed():
            return
        def pulse():
            source = self.sources.get(key)
            if source:
                if source.running:
                    source.dirty = True
                elif source.due > time.monotonic():
                    self._schedule(source, time.monotonic())
        try:
            self.loop.call_soon_threadsafe(pulse)
        except RuntimeError:
            pass

    async def _invoke(self, callback, owner, *args):
        if inspect.iscoroutinefunction(callback):
            return await callback(*args)
        value = await self.resources.io.run(owner, callback, *args)
        return await value if inspect.isawaitable(value) else value

    async def sessions(self, manager, *, include_archived=False):
        """Share one bounded, single-flight inventory read across domain monitors."""
        identity = str(manager.sessions_dir)
        entry = self._inventories.get(identity)
        now = time.monotonic()
        if entry is None or (entry["future"].done() and now >= entry["until"]):
            if entry is None and len(self._inventories) >= self.source_limit:
                raise ControlError("monitor_full", "Session inventory budget is full", status=429)
            future = asyncio.create_task(self.resources.io.run("@session-inventory", manager.list_sessions, include_archived=True))
            entry = self._inventories[identity] = {"future": future, "until": now + 5.}
        try:
            rows = await asyncio.shield(entry["future"])
        except Exception:
            entry["until"] = 0.
            raise
        return list(rows) if include_archived else [row for row in rows if not row.get("archived")]

    async def _poll(self, source):
        try:
            if not self.enabled(source.key.namespace):
                return
            value = await self._invoke(source.collect, source.key.namespace)
            for owner, consumer in tuple(source.subscribers.items()):
                if not self.enabled(source.key.namespace):
                    break
                if source.subscribers.get(owner) is not consumer or not consumer:
                    continue
                try:
                    await self._invoke(consumer, owner, value)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    log.exception("Monitor subscriber failed owner=%s", owner)
            source.failures = 0
        except asyncio.CancelledError:
            raise
        except Exception:
            source.failures += 1
            log.exception("Monitor collection failed kind=%s namespace=%s", source.key.kind, source.key.namespace)
        finally:
            source.running = None
            if not self.closing and self.sources.get(source.key) is source:
                delay = min(60., source.interval * 2 ** min(source.failures, 6)) if source.failures else source.interval
                self._schedule(source, time.monotonic() + (0 if source.dirty else delay))
                source.dirty = False
            if self.changed:
                self.changed.set()

    async def _loop(self):
        while not self.closing:
            self.changed.clear()
            now = time.monotonic()
            deferred = []
            while self.heap and len(self.active) < self.limit and self.heap[0][0] <= now:
                deadline = heapq.heappop(self.heap)
                _, _, key, version = deadline
                source = self.sources.get(key)
                if not source or source.version != version or source.running:
                    continue
                if self.active_namespaces[key.namespace] >= self.per_namespace:
                    deferred.append(deadline)
                    continue
                task = asyncio.create_task(self._poll(source), name="monitor:" + key.kind)
                source.running = task
                self.active.add(task)
                self.active_namespaces[key.namespace] += 1
                def finished(done, namespace=key.namespace):
                    self.active.discard(done)
                    self.active_namespaces[namespace] -= 1
                    if not self.active_namespaces[namespace]:
                        self.active_namespaces.pop(namespace)
                    self.changed.set()
                task.add_done_callback(finished)
            for deadline in deferred:
                heapq.heappush(self.heap, deadline)
            eligible = [when for when, _, key, version in self.heap if key in self.sources and
                        self.sources[key].version == version and self.active_namespaces[key.namespace] < self.per_namespace]
            delay = max(.01, min(eligible) - time.monotonic()) if eligible and len(self.active) < self.limit else 30.
            try:
                await asyncio.wait_for(self.changed.wait(), timeout=min(30., delay))
            except asyncio.TimeoutError:
                pass

    async def unsubscribe(self, key, owner, *, expected_source=None):
        source = self.sources.get(key)
        if not source or (expected_source is not None and source is not expected_source):
            return
        source.subscribers.pop(owner, None)
        if source.subscribers:
            return
        self.sources.pop(key, None)
        for kind in source.events:
            self.event_sources[kind].discard(key)
            if not self.event_sources[kind]:
                self.event_sources.pop(kind)
        if source.running and source.running is not asyncio.current_task():
            source.running.cancel()
            await asyncio.gather(source.running, return_exceptions=True)
        if source.cleanup:
            await self._invoke(source.cleanup, key.namespace)
        self.changed.set()

    def revoke_namespace(self, namespace):
        """Fence the current subscriptions; a later re-enable owns new sources."""
        if self.closing or not self.loop or self.loop.is_closed():
            return
        def schedule():
            captured = [(key, source, tuple(source.subscribers)) for key, source in self.sources.items()
                        if key.namespace == namespace]
            if not captured:
                return
            async def release():
                for key, source, owners in captured:
                    for owner in owners:
                        if self.sources.get(key) is source:
                            try:
                                await self.unsubscribe(key, owner, expected_source=source)
                            except Exception:
                                log.exception("Monitor cleanup failed namespace=%s", namespace)
            task = asyncio.create_task(release(), name="monitor-release:" + namespace)
            self._revocations.add(task)
            def completed(done):
                self._revocations.discard(done)
                if not done.cancelled() and (error := done.exception()):
                    log.error("Monitor release failed namespace=%s", namespace,
                              exc_info=(type(error), error, error.__traceback__))
            task.add_done_callback(completed)
        try:
            on_owner_loop = asyncio.get_running_loop() is self.loop
        except RuntimeError:
            on_owner_loop = False
        if on_owner_loop:
            # Capture the current generation before an idle subscription
            # can close and be replaced in the same event-loop turn.
            schedule()
        else:
            try:
                self.loop.call_soon_threadsafe(schedule)
            except RuntimeError:
                pass

    async def close(self):
        self.closing = True
        if self._listener:
            from session_event_bus import remove_event_listener
            remove_event_listener(self._listener)
            self._listener = None
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
        for source in tuple(self.sources.values()):
            for owner in tuple(source.subscribers):
                try:
                    await self.unsubscribe(source.key, owner)
                except Exception:
                    log.exception("Monitor cleanup failed namespace=%s", source.key.namespace)
        futures = [entry["future"] for entry in self._inventories.values()]
        for future in futures:
            future.cancel()
        if futures:
            await asyncio.gather(*futures, return_exceptions=True)
        self._inventories.clear()
        if self._revocations:
            await asyncio.gather(*self._revocations, return_exceptions=True)
        self.heap.clear()

    def snapshot(self):
        return {"sources": len(self.sources), "subscriptions": sum(len(s.subscribers) for s in self.sources.values()),
                "active": len(self.active), "concurrency": self.limit, "deadlines": len(self.heap),
                "shared_inventories": len(self._inventories)}
