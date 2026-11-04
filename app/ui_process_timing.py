"""Attach measured process spans before live events are persisted and published."""
from __future__ import annotations

import time


class UiProcessTiming:
    def __init__(self, *, clock=time.time, monotonic=time.monotonic):
        self.clock, self.monotonic = clock, monotonic
        self.reasoning, self.tools = {}, {}

    def _start(self):
        return {"started_at": self.clock(), "tick": self.monotonic()}

    def _finish(self, span):
        if span is not None and "duration_ms" not in span:
            span["duration_ms"] = max(0, round((self.monotonic() - span["tick"]) * 1000))
            span["finished_at"] = self.clock()

    @staticmethod
    def _copy(event, span):
        if span:
            for key in ("started_at", "finished_at", "duration_ms"):
                if key in span:
                    event.setdefault(key, span[key])

    def annotate(self, event):
        if event.get("_subagent_forward"):
            return
        kind = event.get("type", "")
        # Consumed by ExecutionJournal before publication. Capture receipt time
        # here so persistence queue latency is not counted as model thinking.
        from runtime_v2.execution_journal import STREAM_TYPES
        if kind in STREAM_TYPES | {"llm_stream_aborted", "run_interrupted", "run_failed"}:
            event["_process_received_at"] = self.clock()
        phase = event.get("react_iter", event.get("step", event.get("iteration")))
        key = (event.get("run_id"), phase, event.get("stream_seq"))
        reason = self.reasoning.get(key)
        if kind == "llm_reasoning_delta":
            if reason is None:
                reason = self.reasoning[key] = self._start()
            self._copy(event, reason)
        if kind in {"llm_response_delta", "llm_response", "llm_reasoning", "llm_reasoning_end",
                    "tool_call_delta", "tool_pending", "tool_execution_state", "tool_call"}:
            self._finish(reason)
            if reason is not None and kind in STREAM_TYPES:
                event["_reasoning_timing"] = {key: reason[key] for key in
                    ("started_at", "finished_at", "duration_ms") if key in reason}
            if kind in {"llm_reasoning", "llm_reasoning_end"}:
                self._copy(event, reason)
        if kind in {"tool_pending", "tool_execution_state", "tool_call"}:
            tool_id = event.get("tool_call_id") or event.get("tool_id")
            if not tool_id:
                return
            tool_key = (event.get("run_id"), tool_id)
            span = self.tools.get(tool_key)
            status = event.get("execution_status") or event.get("status")
            # Waiting for admission/approval is distinct from actual execution.
            if kind != "tool_call" and (span is None or status == "running" and span.get("pending")):
                span = self.tools[tool_key] = self._start()
                span["pending"] = kind == "tool_pending"
            if kind == "tool_call" or isinstance(status, str) and status in {
                "completed", "failed", "timed_out", "interrupted", "cancelled", "blocked", "denied", "unknown",
            }:
                self._finish(span)
                structured = event.get("status")
                measured = event.get("duration_ms")
                if measured is None and isinstance(structured, dict):
                    measured = structured.get("duration_ms")
                if isinstance(measured, (int, float)) and measured >= 0:
                    event.setdefault("duration_ms", measured)
                    event.setdefault("finished_at", self.clock())
                    event.setdefault("started_at", event["finished_at"] - measured / 1000)
            self._copy(event, span)
        if kind in {"final", "run_finished", "run_failed", "run_interrupted"}:
            for span in (*self.reasoning.values(), *self.tools.values()):
                self._finish(span)
