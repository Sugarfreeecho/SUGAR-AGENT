import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar
from pathlib import Path
import sys
import threading

import pytest

APP = Path(__file__).resolve().parents[1] / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

import agent_request_executor as module
from agent_request_timing import RequestPreparationTrace, current_request_trace, request_timing_scope


@pytest.fixture
def request_pool(monkeypatch):
    pool = ThreadPoolExecutor(2, thread_name_prefix="request-executor-test")
    monkeypatch.setattr(module, "_executor", pool)
    try:
        yield pool
    finally:
        module.shutdown_request_executor(wait=True)


def test_request_runs_while_default_executor_is_occupied_and_keeps_context(request_pool):
    value = ContextVar("request_test_value", default=None)
    entered, release = threading.Event(), threading.Event()
    trace = RequestPreparationTrace("s", "r", 2)
    def block():
        entered.set()
        release.wait(3)
    async def scenario():
        loop = asyncio.get_running_loop()
        loop.set_default_executor(ThreadPoolExecutor(1))
        blocked = loop.run_in_executor(None, block)
        while not entered.is_set():
            await asyncio.sleep(0)
        try:
            value.set("request")
            with request_timing_scope(trace):
                result = await asyncio.wait_for(module.run_request_worker(
                    lambda: (value.get(), current_request_trace()), trace=trace), 1)
            assert result == ("request", trace)
            assert not release.is_set()
        finally:
            release.set()
            await blocked
    asyncio.run(scenario())
    anchors = trace.snapshot()["anchors"]
    assert anchors["worker_dispatch_entered"] <= anchors["worker_submitted"] <= anchors["worker_entered"]


def test_queued_cancellation_does_not_start_request(monkeypatch):
    pool = ThreadPoolExecutor(1)
    monkeypatch.setattr(module, "_executor", pool)
    entered, release = threading.Event(), threading.Event()
    calls = []
    def block():
        entered.set()
        release.wait(3)
    blocker = pool.submit(block)
    assert entered.wait(1)
    trace = RequestPreparationTrace("s", "queued", 1)
    async def scenario():
        task = asyncio.create_task(module.run_request_worker(lambda: calls.append("started"), trace=trace))
        while "worker_submitted" not in trace.snapshot()["anchors"]:
            await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        await asyncio.sleep(0)
        release.set()
        await asyncio.wrap_future(pool.submit(lambda: None))
    try:
        asyncio.run(scenario())
        assert not calls
        assert "worker_entered" not in trace.snapshot()["anchors"]
    finally:
        release.set()
        blocker.result(1)
        module.shutdown_request_executor(wait=True)


def test_running_cancellation_leaves_cooperative_abort_with_the_caller(request_pool):
    entered, abort, finished = threading.Event(), threading.Event(), threading.Event()
    def worker():
        entered.set()
        try:
            abort.wait(3)
        finally:
            finished.set()
    async def scenario():
        task = asyncio.create_task(module.run_request_worker(worker))
        while not entered.is_set():
            await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert not finished.is_set()
        abort.set()
    try:
        asyncio.run(scenario())
        assert finished.wait(1)
    finally:
        abort.set()


def test_worker_exception_propagates_unchanged(request_pool):
    error = ValueError("request failure")
    def fail():
        raise error
    async def scenario():
        with pytest.raises(ValueError) as caught:
            await module.run_request_worker(fail)
        assert caught.value is error
    asyncio.run(scenario())


def test_parallel_requests_do_not_share_context(request_pool):
    value = ContextVar("parallel_request_value")
    barrier = threading.Barrier(2)
    def worker():
        barrier.wait(timeout=2)
        return value.get(), current_request_trace().run_id
    async def one(index):
        value.set(index)
        trace = RequestPreparationTrace("s", f"r{index}", 1)
        with request_timing_scope(trace):
            return await module.run_request_worker(worker, trace=trace)
    async def scenario():
        assert await asyncio.gather(one(1), one(2)) == [(1, "r1"), (2, "r2")]
    asyncio.run(scenario())


def test_shutdown_cancels_queued_calls_and_allows_a_later_lifecycle(monkeypatch):
    pool = ThreadPoolExecutor(1)
    monkeypatch.setattr(module, "_executor", pool)
    release, entered = threading.Event(), threading.Event()
    def block():
        entered.set()
        release.wait(3)
    active = pool.submit(block)
    assert entered.wait(1)
    pending = pool.submit(lambda: pytest.fail("shutdown request started"))
    try:
        module.shutdown_request_executor()
        assert pending.cancelled()
        assert module._executor is None
        release.set()
        active.result(1)
        async def scenario():
            assert await module.run_request_worker(lambda: 42) == 42
        asyncio.run(scenario())
    finally:
        release.set()
        pool.shutdown(wait=True, cancel_futures=True)
        module.shutdown_request_executor(wait=True)
