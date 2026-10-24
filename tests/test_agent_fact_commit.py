import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar
import threading

import pytest

from agent_fact_commit import run_fact_commit
from agent_local_timing import LocalOperationTrace
from runtime_v2 import RuntimeHistoryOps


async def wait_event(event):
    async def poll():
        while not event.is_set():
            await asyncio.sleep(.001)
    await asyncio.wait_for(poll(), 5)


def test_real_facts_are_awaited_and_receipt_published_on_owner_loop(tmp_path,monkeypatch):
    entered, release = threading.Event(), threading.Event()
    owner = threading.get_ident()
    context = ContextVar('fact_commit_test')
    ops = RuntimeHistoryOps(tmp_path)
    trace = LocalOperationTrace('fact_commit_test')
    captured=[]
    monkeypatch.setattr(LocalOperationTrace,'log',lambda trace:captured.append(trace.snapshot()))
    order = []

    def write(state):
        assert state['session_id']=='s'
        assert threading.get_ident() != owner and context.get() == 'value'
        entered.set()
        assert release.wait(5)
        events = ops.append_model_tool_results('s', [{'tool_call_id':'t', 'content':'done'}], run_id='r')
        order.append('durable')
        return events

    def publish(events):
        assert threading.get_ident() == owner and events[0].type == 'model_tool'
        order.append('published')

    async def run():
        context.set('value')
        with trace.bind():
            pending = asyncio.create_task(run_fact_commit(write, {'session_id':'s','_runtime_v2_run_id':'r','_current_react_iter':2},on_committed=publish))
            try:
                await wait_event(entered)
                await asyncio.sleep(.06)
                assert not pending.done() and not order
                release.set()
                await pending
                order.append('next_api_allowed')
            finally:
                release.set()
                await asyncio.gather(pending, return_exceptions=True)
    asyncio.run(run())
    assert order == ['durable','published','next_api_allowed']
    assert [e.type for e in ops.event_log.read_all('s')] == ['model_tool']
    marks = next(row for row in captured if row['kind']=='fact_commit_await')
    assert (marks['session_id'],marks['run_id'],marks['react_iter'])==('s','r',2)
    assert marks['mark_threads']['fact_commit_resumed'] == owner
    assert marks['mark_threads']['fact_commit_worker_entered'] != owner


def test_inflight_cancellation_waits_for_fact_and_memory_receipt_even_if_cancelled_twice(tmp_path):
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    ops = RuntimeHistoryOps(tmp_path)
    order = []
    def write():
        entered.set()
        assert release.wait(5)
        try:
            return ops.append_model_tool_results('s', [{'tool_call_id':'t','content':'done'}])
        finally:
            order.append('durable')
            finished.set()
    def publish(events):
        assert finished.is_set() and events[0].payload['tool_call_id']=='t'
        order.append('published')
    async def run():
        pending = asyncio.create_task(run_fact_commit(write,on_committed=publish))
        try:
            await wait_event(entered)
            pending.cancel()
            await asyncio.sleep(0)
            pending.cancel()
            await asyncio.sleep(0)
            assert not pending.done() and not finished.is_set()
            release.set()
            with pytest.raises(asyncio.CancelledError):
                await pending
            order.append('cancel_propagated')
        finally:
            release.set()
            await asyncio.gather(pending,return_exceptions=True)
    asyncio.run(run())
    assert order == ['durable','published','cancel_propagated']
    assert len(ops.event_log.read_all('s'))==1


def test_queued_cancellation_keeps_already_selected_completed_tool_fact(tmp_path):
    entered, release = threading.Event(), threading.Event()
    calls=[]
    ops=RuntimeHistoryOps(tmp_path)
    def write():
        events=ops.append_model_tool_results('s',[{'tool_call_id':'completed','content':'done'}])
        calls.append('write')
        return events
    def occupy():
        entered.set()
        assert release.wait(5)
    async def run():
        loop=asyncio.get_running_loop()
        loop.set_default_executor(ThreadPoolExecutor(1))
        busy=loop.run_in_executor(None,occupy)
        await wait_event(entered)
        pending=asyncio.create_task(run_fact_commit(write,on_committed=lambda _:calls.append('receipt')))
        try:
            await asyncio.sleep(0)
            pending.cancel()
            await asyncio.sleep(0)
            assert not pending.done() and not calls
            release.set()
            with pytest.raises(asyncio.CancelledError):
                await pending
            calls.append('cancel_propagated')
        finally:
            release.set()
            await busy
    asyncio.run(run())
    assert calls==['write','receipt','cancel_propagated']
    assert ops.event_log.read_all('s')[0].payload['tool_call_id']=='completed'


def test_write_error_is_preserved_and_never_publishes_receipt():
    calls=[]
    def fail():
        raise OSError('fact write failed')
    async def run():
        with pytest.raises(OSError,match='fact write failed'):
            await run_fact_commit(fail,on_committed=lambda _:calls.append('receipt'))
    asyncio.run(run())
    assert not calls
