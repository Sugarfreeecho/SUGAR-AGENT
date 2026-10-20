"""Isolate blocking LLM requests from the event loop's filesystem executor."""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import contextvars
import os
import threading


_guard = threading.Lock()
_executor: ThreadPoolExecutor | None = None


def _request_executor() -> ThreadPoolExecutor:
    global _executor
    with _guard:
        if _executor is None:
            _executor = ThreadPoolExecutor(
                max_workers=min(32, (os.cpu_count() or 1) + 4),
                thread_name_prefix="myagent-llm-request",
            )
        return _executor


async def run_request_worker(function, /, *args, trace=None, **kwargs):
    """Preserve to_thread context, cancellation and exceptions on a separate pool."""
    if trace is not None:
        trace.mark("worker_dispatch_entered")
    loop = asyncio.get_running_loop()
    context = contextvars.copy_context()
    executor = _request_executor()

    def call():
        if trace is not None:
            trace.mark("worker_entered")
        return function(*args, **kwargs)

    if trace is not None:
        trace.mark("worker_submitted")
    return await loop.run_in_executor(executor, context.run, call)


def shutdown_request_executor(*, wait=False) -> None:
    """Cancel queued requests at shutdown; active workers keep their caller's abort path."""
    global _executor
    with _guard:
        executor, _executor = _executor, None
    if executor is not None:
        executor.shutdown(wait=wait, cancel_futures=True)
