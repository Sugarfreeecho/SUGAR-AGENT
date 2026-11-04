"""Payload-free local spans shared by UI delivery and finalization workers."""
from __future__ import annotations

from contextlib import contextmanager, nullcontext
from contextvars import ContextVar
from functools import wraps
import inspect
import json
import logging
import os
import threading
import time

_current = ContextVar("local_operation_trace", default=None)
_logger = logging.getLogger("agent_harness")

TIMING_MODE = os.getenv("AGENT_LOG_TIMING", "summary").strip().lower()
if TIMING_MODE not in {"summary", "detail", "off"}:
    TIMING_MODE = "summary"
# 逐事件触发的 kind：单条没有诊断价值，summary 模式只按 run 聚合。
# 其余 kind（round_entry / model_commit 等）每轮或每次提交一条，保留逐条记录。
SUMMARY_KINDS = frozenset({"event_delivery"})
SUMMARY_SLOW_MS = max(0, int(os.getenv("AGENT_LOG_TIMING_SLOW_MS", "500") or 500))
_AGG_SAMPLE_CAP = 256
_AGG_FLUSH_AT = 1000
_agg_lock = threading.Lock()
_agg_rows = {}
_agg_total = 0


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

    def finish(self, *, slow_ms=None):
        """按 AGENT_LOG_TIMING 逐条、聚合或静默；慢操作始终单独留痕。"""
        if TIMING_MODE == "off":
            return
        elapsed_ms = (time.perf_counter() - self.started) * 1000
        kind = self.metadata.get("kind") or ""
        if TIMING_MODE == "summary" and kind in SUMMARY_KINDS:
            _record_summary(self, elapsed_ms)
            threshold = SUMMARY_SLOW_MS if slow_ms is None else slow_ms
            if threshold <= 0 or elapsed_ms >= threshold:
                self.log()
            return
        if slow_ms is not None and elapsed_ms < slow_ms:
            return
        self.log()


def _p95(samples):
    if not samples:
        return 0.0
    ordered = sorted(samples)
    return ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]


def _record_summary(trace, elapsed_ms: float) -> None:
    global _agg_total
    key = (
        trace.metadata.get("kind") or "",
        trace.metadata.get("session_id") or "",
        trace.metadata.get("run_id") or "",
    )
    with _agg_lock:
        row = _agg_rows.get(key)
        if row is None:
            row = {"count": 0, "total_ms": 0.0, "max_ms": 0.0, "samples": []}
            _agg_rows[key] = row
        row["count"] += 1
        row["total_ms"] += elapsed_ms
        row["max_ms"] = max(row["max_ms"], elapsed_ms)
        if len(row["samples"]) < _AGG_SAMPLE_CAP:
            row["samples"].append(elapsed_ms)
        _agg_total += 1
        flush_now = _agg_total >= _AGG_FLUSH_AT
    if flush_now:
        flush_local_operation_summary()


def flush_local_operation_summary() -> None:
    """把累计的高频计时压成每 kind/run 一行；由 finish 或阈值触发。"""
    global _agg_total
    with _agg_lock:
        rows = list(_agg_rows.items())
        _agg_rows.clear()
        _agg_total = 0
    for (kind, session_id, run_id), row in rows:
        try:
            _logger.info(
                "local_operation_summary kind=%s session=%s run=%s count=%d "
                "total_ms=%.0f p95_ms=%.1f max_ms=%.1f",
                kind, session_id or "-", run_id or "-", row["count"],
                row["total_ms"], _p95(row["samples"]), row["max_ms"],
            )
        except Exception:
            pass


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
            trace.finish(slow_ms=slow_ms)

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
