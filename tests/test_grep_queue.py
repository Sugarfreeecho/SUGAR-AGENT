"""Bounded queue, default-pool isolation and cancellation race contracts."""
import asyncio
import contextvars
import json
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

import grep_runtime as runtime


@pytest.fixture
def pool(monkeypatch):
    executor = runtime._SearchExecutor(max_workers=1, capacity=2)
    monkeypatch.setattr(runtime, "_search_executor", lambda: executor)
    yield executor
    executor.shutdown()


def short_budget(monkeypatch, seconds=.08):
    constructor = runtime.SearchRun
    def create(**metadata):
        run = constructor(**metadata)
        run.timeout = seconds
        run.deadline = run.started + seconds
        return run
    monkeypatch.setattr(runtime, "SearchRun", create)


def traces(caplog):
    return [json.loads(row.message.split("grep_timing ", 1)[1])
            for row in caplog.records if "grep_timing " in row.message]


def test_default_executor_cannot_hold_up_grep(pool):
    entered, release = threading.Event(), threading.Event()
    def block():
        entered.set()
        release.wait(3)
    async def scenario():
        loop = asyncio.get_running_loop()
        loop.set_default_executor(ThreadPoolExecutor(max_workers=1))
        pending = loop.run_in_executor(None, block)
        assert entered.wait(1)
        try:
            assert await asyncio.wait_for(runtime.invoke(lambda: "hit", {}, {}), .5) == "hit"
            assert not release.is_set()
        finally:
            release.set()
            await pending
    asyncio.run(scenario())


def test_queued_deadline_returns_before_worker_available_and_never_runs(pool, monkeypatch, caplog):
    short_budget(monkeypatch)
    caplog.set_level("INFO", logger="agent_harness")
    entered, release = threading.Event(), threading.Event()
    called = []
    def block():
        entered.set()
        release.wait(3)
    blocked = pool._executor.submit(block)
    assert entered.wait(1)
    async def scenario():
        result = await asyncio.wait_for(runtime.invoke(lambda: called.append(True), {}, {}), .5)
        assert "timed out" in result and "incomplete" in result
        assert not release.is_set()
    try:
        asyncio.run(scenario())
    finally:
        release.set()
        blocked.result(1)
    pool._executor.submit(lambda: None).result(1)
    assert not called
    row = traces(caplog)[0]
    assert row["worker_queue_ms"] is None
    assert row["queue_outcome"] == "abandoned_before_start"
    assert row["stop_reason"] == "timeout"


def test_abandoned_placeholders_hold_capacity_until_dequeued(pool, monkeypatch, caplog):
    short_budget(monkeypatch, .035)
    caplog.set_level("INFO", logger="agent_harness")
    release = threading.Event()
    blocked = pool._executor.submit(lambda: release.wait(3))
    called = []
    async def scenario():
        # Two accepted placeholders fill the pool, the remaining ten must wait
        # for admission. Abandonment never releases a still-queued placeholder.
        for index in range(12):
            result = await runtime.invoke(lambda: called.append(True), {}, {"tool_call_id": str(index)})
            assert "timed out" in result
        assert pool._executor._work_queue.qsize() == 2
    try:
        asyncio.run(scenario())
    finally:
        release.set()
        blocked.result(1)
    pool._executor.submit(lambda: None).result(1)
    rows = traces(caplog)
    assert len(rows) == 12
    assert sum(row["admission_ms"] is not None for row in rows) == 2
    assert not called
    assert asyncio.run(runtime.invoke(lambda: "recovered", {}, {})) == "recovered"


def test_cancel_while_waiting_for_admission_does_not_submit(pool, caplog):
    caplog.set_level("INFO", logger="agent_harness")
    assert pool._slots.acquire(False) and pool._slots.acquire(False)
    called = []
    async def scenario():
        task = asyncio.create_task(runtime.invoke(lambda: called.append(True), {}, {}))
        await asyncio.sleep(.02)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, .5)
        assert pool._executor._work_queue.qsize() == 0
    try:
        asyncio.run(scenario())
    finally:
        pool._slots.release()
        pool._slots.release()
    assert not called and traces(caplog)[0]["admission_ms"] is None


@pytest.mark.parametrize("fails", [False, True])
def test_repeated_running_cancellation_waits_for_cleanup(pool, fails):
    entered, cleanup_allowed, cleaned = threading.Event(), threading.Event(), threading.Event()
    def worker():
        entered.set()
        assert runtime.current().cancel.wait(2)
        cleanup_allowed.wait(2)
        cleaned.set()
        if fails:
            raise ValueError("cleanup failed")
        return "settled"
    async def scenario():
        task = asyncio.create_task(runtime.invoke(worker, {}, {}))
        while not entered.is_set():
            await asyncio.sleep(.005)
        task.cancel()
        await asyncio.sleep(.02)
        task.cancel()
        await asyncio.sleep(.02)
        assert not task.done() and not cleaned.is_set()
        cleanup_allowed.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert cleaned.is_set()
    try:
        asyncio.run(scenario())
    finally:
        cleanup_allowed.set()


def test_running_timeout_stays_timeout_after_cancel_signal(pool, monkeypatch, caplog):
    short_budget(monkeypatch)
    caplog.set_level("INFO", logger="agent_harness")
    def worker():
        run = runtime.current()
        assert run.cancel.wait(2)
        run.check()
    result = asyncio.run(runtime.invoke(worker, {}, {}))
    assert "timed out" in result
    assert traces(caplog)[0]["stop_reason"] == "timeout"


def test_context_is_copied_and_exceptions_release_capacity(pool):
    marker = contextvars.ContextVar("test-search-context", default="outside")
    def read():
        return marker.get(), runtime.current().metadata["session_id"]
    async def scenario():
        async def one(name):
            marker.set(name)
            return await runtime.invoke(read, {}, {"session_id": name})
        assert await asyncio.gather(one("main"), one("child")) == [("main", "main"), ("child", "child")]
        def fail():
            raise ValueError("failed")
        with pytest.raises(ValueError, match="failed"):
            await runtime.invoke(fail, {}, {})
        assert await one("next") == ("next", "next")
    asyncio.run(scenario())
    assert marker.get() == "outside"


def test_submit_failure_releases_capacity_and_prevents_late_entry(pool, monkeypatch):
    called = []
    def broken(*args):
        raise RuntimeError("executor unavailable")
    monkeypatch.setattr(pool._executor, "submit", broken)
    with pytest.raises(RuntimeError, match="unavailable"):
        asyncio.run(runtime.invoke(lambda: called.append(True), {}, {}))
    assert pool._slots.acquire(False) and pool._slots.acquire(False)
    pool._slots.release()
    pool._slots.release()
    assert not called
