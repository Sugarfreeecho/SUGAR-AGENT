"""Await fact writes without blocking the event loop or abandoning a writer."""
from __future__ import annotations

import asyncio
import contextvars
import logging

from agent_local_timing import LocalOperationTrace, local_step, mark_local
import time

logger = logging.getLogger(__name__)


async def run_fact_commit(function, /, *args, on_committed=None, trace_state=None):
    """Keep the fact boundary awaited, including when cancellation arrives.

    A selected completed fact must settle even if cancellation arrives while
    it is queued. The original writer still checks its live ownership fence.
    A synchronous owner-loop callback publishes the successful memory receipt
    before cancellation propagates, just as an inline commit previously did.
    trace_state labels calls whose arguments do not start with a ReAct State.
    """
    state = trace_state if isinstance(trace_state, dict) else (args[0] if args and isinstance(args[0], dict) else {})
    trace = LocalOperationTrace(
        'fact_commit_await', session_id=state.get('session_id',''),
        run_id=state.get('_runtime_v2_run_id',''),
        react_iter=state.get('_current_react_iter',0),
    )
    with trace.bind():
        try:
            return await _run_fact_commit(function, *args, on_committed=on_committed)
        finally:
            if (time.perf_counter()-trace.started)*1000 >= 50:
                trace.log()


async def _run_fact_commit(function, /, *args, on_committed=None):
    loop = asyncio.get_running_loop()
    context = contextvars.copy_context()
    mark_local('fact_commit_submitted')

    def write():
        mark_local('fact_commit_worker_entered')
        try:
            return function(*args)
        finally:
            mark_local('fact_commit_worker_finished')

    # Use a future rather than a child Task: loop shutdown must not cancel the
    # wrapper task and report completion while its synchronous writer is alive.
    future = loop.run_in_executor(None, context.run, write)
    cancellation = None
    while True:
        try:
            result = await asyncio.shield(future)
            break
        except asyncio.CancelledError as exc:
            cancellation = cancellation or exc
            mark_local('fact_commit_cancel_requested')
            if future.done():
                try:
                    result = future.result()
                except asyncio.CancelledError:
                    raise cancellation
                except BaseException:
                    logger.exception('Fact commit failed while cancellation was pending')
                    raise cancellation
                break
        except BaseException:
            if cancellation is not None:
                logger.exception('Fact commit failed while cancellation was pending')
                raise cancellation
            raise
    mark_local('fact_commit_resumed')
    if on_committed is not None:
        with local_step('fact_commit_memory_receipt'):
            on_committed(result)
    if cancellation is not None:
        raise cancellation
    return result
