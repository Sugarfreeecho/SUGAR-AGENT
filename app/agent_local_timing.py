"""Payload-free local spans shared by UI delivery and finalization workers."""
from __future__ import annotations

from contextlib import contextmanager, nullcontext
from contextvars import ContextVar
from functools import wraps
import inspect
import json
import logging
import threading
import time

_current = ContextVar("local_operation_trace", default=None)
_logger = logging.getLogger("agent_harness")


class LocalOperationTrace:
    def __init__(self, kind: str, *, session_id="", run_id="", react_iter=0, event_type="", queued_at=None):
        self.metadata = dict(kind=kind, session_id=session_id, run_id=run_id,
                             react_iter=react_iter, event_type=event_type)
        self.started = time.perf_counter()
        self.anchors = {"started": self.started}
        self.mark_threads = {}
        if queued_at is not None:
            self.anchors["queued"] = queued_at
        self.spans = []
        self.dropped_spans = 0
        self._lock = threading.Lock()

    @contextmanager
    def bind(self):
        token = _current.set(self)
        try:
            yield self
        finally:
            _current.reset(token)

    def mark(self, name):
        with self._lock:
            self.anchors.setdefault(name, time.perf_counter())
            self.mark_threads.setdefault(name, threading.get_ident())

    @contextmanager
    def step(self, name, *, min_ms=0):
        started, cpu = time.perf_counter(), time.thread_time()
        try:
            yield
        finally:
            ended = time.perf_counter()
            row = {"name": name, "started": started, "ended": ended,
                   "elapsed_ms": round((ended - started) * 1000, 3),
                   "thread_cpu_elapsed_ms": round((time.thread_time() - cpu) * 1000, 3)}
            if row["elapsed_ms"] >= min_ms:
                with self._lock:
                    if len(self.spans) < 64:
                        self.spans.append(row)
                    else:
                        self.dropped_spans += 1

    def snapshot(self):
        ended = time.perf_counter()
        with self._lock:
            anchors = dict(self.anchors)
            spans = list(self.spans)
            dropped = self.dropped_spans
            mark_threads = dict(self.mark_threads)
        return {**self.metadata, "clock": "perf_counter", "anchors": anchors,
                "ended": ended, "elapsed_ms": round((ended - self.started) * 1000, 3),
                "spans": spans, "dropped_spans": dropped, "mark_threads": mark_threads}

    def log(self):
        try:
            _logger.info("local_operation_timing %s", json.dumps(self.snapshot(), separators=(",", ":")))
        except Exception:
            pass  # Diagnostics must not change delivery or terminal outcomes.


def local_step(name, *, min_ms=0):
    trace = _current.get()
    return trace.step(name, min_ms=min_ms) if trace is not None else nullcontext()


def mark_local(name):
    trace = _current.get()
    if trace is not None:
        trace.mark(name)


def local_timed(name):
    def decorate(function):
        if inspect.iscoroutinefunction(function):
            @wraps(function)
            async def async_call(*args, **kwargs):
                trace = _current.get()
                if trace is None:
                    return await function(*args, **kwargs)
                with trace.step(name):
                    return await function(*args, **kwargs)
            return async_call
        @wraps(function)
        def sync_call(*args, **kwargs):
            trace = _current.get()
            if trace is None:
                return function(*args, **kwargs)
            with trace.step(name):
                return function(*args, **kwargs)
        return sync_call
    return decorate


def local_operation(name, *, slow_ms=None):
    """Trace lifecycle work, resolving run identity from positional or keyword state."""
    def decorate(function):
        signature = inspect.signature(function)
        def make_trace(args, kwargs):
            arguments = {**kwargs, **signature.bind_partial(*args, **kwargs).arguments}
            state = arguments.get("state") or {}
            return LocalOperationTrace(name,
                                        session_id=arguments.get("session_id") or state.get("session_id", ""),
                                        run_id=arguments.get("run_id") or state.get("_runtime_v2_run_id", ""),
                                        react_iter=state.get("_current_react_iter", 0),
                                        event_type=arguments.get("event", ""))

        def finish(trace):
            if slow_ms is None or (time.perf_counter() - trace.started) * 1000 >= slow_ms:
                trace.log()

        if not inspect.iscoroutinefunction(function):
            @wraps(function)
            def sync_call(*args, **kwargs):
                trace = make_trace(args, kwargs)
                with trace.bind():
                    try:
                        return function(*args, **kwargs)
                    finally:
                        finish(trace)
            return sync_call

        @wraps(function)
        async def call(*args, **kwargs):
            trace = make_trace(args, kwargs)
            with trace.bind():
                try:
                    return await function(*args, **kwargs)
                finally:
                    finish(trace)
        return call
    return decorate
