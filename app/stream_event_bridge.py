"""Ordered UI delivery without a cross-loop round trip for every model delta."""
from __future__ import annotations

import asyncio
import concurrent.futures
import inspect
import logging
import threading
import time
from collections import deque
from typing import Any, Callable


_DELTA_FIELDS = {
    "llm_reasoning_delta": ("delta",),
    "llm_response_delta": ("delta",),
    "tool_call_delta": ("name_delta", "arguments_delta"),
}
_IDENTITY_FIELDS = (
    "type", "session_id", "run_id", "react_iter", "stream_seq",
    "index", "tool_call_index", "id", "tool_call_id",
)
_logger = logging.getLogger(__name__)


class StreamEventBridge:
    """One main-loop drain; non-delta sends are ordered acknowledgements.

    Only explicitly ephemeral model deltas return after enqueueing. Durable
    commits remain with the caller. Completion, pruning and interrupt events
    wait for all preceding deltas, preventing late drafts after a terminal row.
    """

    def __init__(self, loop: asyncio.AbstractEventLoop, emit: Callable):
        self._loop = loop
        self._emit = emit
        self._lock = threading.Lock()
        self._pending = deque()
        self._draining = False
        self._timings = {}

    @staticmethod
    def is_queued_delta(event: dict) -> bool:
        return bool(event.get("ephemeral") and event.get("type") in _DELTA_FIELDS)

    def _enqueue(self, event: dict | None, acknowledgement=None) -> None:
        schedule = False
        with self._lock:
            previous = self._pending[-1] if self._pending else None
            if (
                acknowledgement is None and previous is not None
                and previous[1] is None and previous[0] is not None
                and all(previous[0].get(key) == event.get(key) for key in _IDENTITY_FIELDS)
            ):
                fields = _DELTA_FIELDS[event["type"]]
                merged = dict(event)
                for field in fields:
                    merged[field] = str(previous[0].get(field) or "") + str(event.get(field) or "")
                self._pending[-1] = (merged, None, previous[2])
            else:
                self._pending.append((dict(event) if event is not None else None, acknowledgement, time.perf_counter()))
            if not self._draining:
                self._draining = True
                schedule = True
        if schedule:
            try:
                self._loop.call_soon_threadsafe(self._start_drain)
            except RuntimeError as exc:
                self._fail_pending(exc)
                raise

    def _fail_pending(self, error: BaseException) -> None:
        with self._lock:
            pending = list(self._pending)
            self._pending.clear()
            self._draining = False
        for _, acknowledgement, _ in pending:
            if acknowledgement is not None and not acknowledgement.done():
                acknowledgement.set_exception(error)

    def _start_drain(self) -> None:
        self._loop.create_task(self._drain())

    async def _drain(self) -> None:
        try:
            while True:
                with self._lock:
                    if not self._pending:
                        self._draining = False
                        return
                    event, acknowledgement, enqueued_at = self._pending.popleft()
                started = time.perf_counter()
                cpu_started = time.thread_time()
                try:
                    if event is not None:
                        result = self._emit(event)
                        if inspect.isawaitable(result):
                            await result
                except asyncio.CancelledError as exc:
                    if acknowledgement is not None and not acknowledgement.done():
                        acknowledgement.set_exception(exc)
                    raise
                except Exception as exc:
                    if acknowledgement is not None and not acknowledgement.done():
                        acknowledgement.set_exception(exc)
                    else:
                        _logger.debug("queued stream delta delivery failed", exc_info=True)
                else:
                    if acknowledgement is not None and not acknowledgement.done():
                        acknowledgement.set_result(None)
                finally:
                    if event is not None:
                        elapsed_ms = int((time.perf_counter() - started) * 1000)
                        cpu_ms = int((time.thread_time() - cpu_started) * 1000)
                        queue_age_ms = int((started - enqueued_at) * 1000)
                        iteration = int(event.get("react_iter") or 0)
                        with self._lock:
                            timing = self._timings.setdefault(iteration, {
                                "main_emit_total_ms": 0, "main_emit_max_ms": 0,
                                "main_emit_cpu_ms": 0, "queue_age_max_ms": 0,
                                "main_emit_calls": 0,
                            })
                            timing["main_emit_total_ms"] += elapsed_ms
                            timing["main_emit_max_ms"] = max(timing["main_emit_max_ms"], elapsed_ms)
                            timing["main_emit_cpu_ms"] += cpu_ms
                            timing["queue_age_max_ms"] = max(timing["queue_age_max_ms"], queue_age_ms)
                            timing["main_emit_calls"] += 1
                        if max(elapsed_ms, queue_age_ms) >= 100:
                            _logger.info(
                                "stream_event_delivery_detail session=%s react_iter=%d type=%s queue_age_ms=%d emit_ms=%d thread_cpu_ms=%d",
                                event.get("session_id", ""), iteration, event.get("type"),
                                queue_age_ms, elapsed_ms, cpu_ms,
                            )
                # Let HTTP and interruption callbacks run during a backlog.
                await asyncio.sleep(0)
        except BaseException as exc:
            self._fail_pending(exc)
            raise

    async def send(self, event: dict) -> None:
        if self.is_queued_delta(event):
            self._enqueue(event)
            return
        acknowledgement = concurrent.futures.Future()
        self._enqueue(event, acknowledgement)
        await asyncio.wrap_future(acknowledgement)

    async def flush(self) -> None:
        acknowledgement = concurrent.futures.Future()
        self._enqueue(None, acknowledgement)
        await asyncio.wrap_future(acknowledgement)

    def snapshot(self, iteration: int) -> dict:
        with self._lock:
            timing = dict(self._timings.get(iteration) or {})
            timing["pending_events"] = sum(
                1 for event, _, _ in self._pending
                if event is not None and int(event.get("react_iter") or 0) == iteration
            )
        return timing
