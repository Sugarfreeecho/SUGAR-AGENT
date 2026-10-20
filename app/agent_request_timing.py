"""Monotonic local request spans, carried across worker and hedge threads."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
import threading
import time
from typing import Optional


_current: ContextVar[Optional["RequestPreparationTrace"]] = ContextVar("request_preparation_trace", default=None)


class RequestPreparationTrace:
    """Record first endpoints per logical request without writing on the send path."""

    def __init__(self, session_id: str, run_id: str, react_iter: int, *,
                 previous_tool_iter: Optional[int] = None, anchors: Optional[dict] = None):
        self.session_id = session_id
        self.run_id = run_id
        self.react_iter = int(react_iter)
        self.previous_tool_iter = previous_tool_iter
        self._anchors = {str(key): float(value) for key, value in (anchors or {}).items() if value is not None}
        self._lock = threading.Lock()

    def mark(self, name: str, at: Optional[float] = None) -> None:
        value = time.perf_counter() if at is None else float(at)
        with self._lock:
            previous = self._anchors.get(name)
            if previous is None or value < previous:
                self._anchors[name] = value

    def snapshot(self) -> dict:
        with self._lock:
            anchors = dict(self._anchors)
        result = {
            "session_id": self.session_id, "run_id": self.run_id,
            "react_iter": self.react_iter, "previous_tool_iter": self.previous_tool_iter,
            "clock": "perf_counter", "anchors": anchors,
            "tool_return_boundary": "execute_one_core_return_before_workspace_audit",
            "http_send_observed": "http_send_entered" in anchors,
        }
        spans = {
            "tool_return_to_http_send_ms": ("tool_returned", "http_send_entered"),
            "tool_return_to_headers_ms": ("tool_returned", "http_headers_started"),
            "tool_return_to_body_ms": ("tool_returned", "http_body_started"),
            "local_ready_to_http_send_ms": ("local_ready", "http_send_entered"),
            "tool_return_to_commit_ms": ("tool_returned", "tool_result_committed"),
            "preparation_to_http_send_ms": ("preparation_started", "http_send_entered"),
            "worker_queue_ms": ("worker_scheduled", "worker_entered"),
            "worker_schedule_to_dispatch_ms": ("worker_scheduled", "worker_dispatch_entered"),
            "worker_dispatch_to_submit_ms": ("worker_dispatch_entered", "worker_submitted"),
            "worker_executor_queue_ms": ("worker_submitted", "worker_entered"),
            "worker_to_http_send_ms": ("worker_entered", "http_send_entered"),
            "request_conversion_ms": ("request_conversion_started", "request_conversion_completed"),
            "wire_json_encode_ms": ("wire_json_encode_started", "wire_json_encode_completed"),
            "http_send_to_headers_ms": ("http_send_entered", "http_headers_started"),
        }
        for key, (start, end) in spans.items():
            if start in anchors and end in anchors and anchors[end] >= anchors[start]:
                result[key] = round((anchors[end] - anchors[start]) * 1000.0, 3)
        return result


def current_request_trace() -> Optional[RequestPreparationTrace]:
    return _current.get()


def new_request_trace(state: dict, react_iter: int, preparation_started: float, *,
                      previous_trace: Optional[RequestPreparationTrace] = None) -> RequestPreparationTrace:
    previous_tool_iter = state.get("_last_tool_returned_iter")
    tool_returned = (state.get("_last_tool_returned_perf")
                     if previous_tool_iter == int(react_iter) - 1 else None)
    session_id = state["session_id"]
    run_id = str(state.get("_runtime_v2_run_id") or "")
    previous_iter = previous_tool_iter if tool_returned is not None else None
    # The outer ReAct retry repeats the same logical iteration. Keep the first
    # actual send, just as the stream/non-stream fallback and hedges already do.
    # The caller owns one local reference; no locks/trace objects enter State.
    if (previous_trace is not None and previous_trace.session_id == session_id
            and previous_trace.run_id == run_id and previous_trace.react_iter == int(react_iter)
            and previous_trace.previous_tool_iter == previous_iter
            and previous_trace.snapshot()["anchors"].get("tool_returned") == tool_returned):
        return previous_trace
    return RequestPreparationTrace(
        session_id, run_id, int(react_iter),
        previous_tool_iter=previous_iter,
        anchors={
            "preparation_started": preparation_started,
            "worker_scheduled": time.perf_counter(),
            "tool_returned": tool_returned,
            "tool_result_committed": state.get("_last_tool_result_committed_perf") if tool_returned is not None else None,
            "local_ready": max(float(tool_returned), float(state.get("_last_model_worker_done_perf") or 0))
            if tool_returned is not None else None,
        },
    )


@contextmanager
def request_timing_scope(trace: RequestPreparationTrace):
    token = _current.set(trace)
    try:
        yield trace
    finally:
        _current.reset(token)
