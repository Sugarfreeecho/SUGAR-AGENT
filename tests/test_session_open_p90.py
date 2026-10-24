"""Real emitter paths must leave their caller's loop free during UI writes."""
import ast
import asyncio
from pathlib import Path
import threading
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]


def emitter(method, manager, order):
    from agent_fact_commit import run_fact_commit
    from agent_subagent_events import should_persist_ui_event
    tree = ast.parse((ROOT/'app/agent_loop.py').read_text(encoding='utf8'))
    outer = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == method)
    node = next(n for n in outer.body if isinstance(n, ast.AsyncFunctionDef) and n.name == 'emit_event')
    node.returns = None
    node.args.args[0].annotation = None

    async def execution(_manager, _sid, event, **_):
        return event

    async def publish(_sid, event):
        order.append('publish')

    namespace = dict(asyncio=asyncio, session_id='s', runtime_v2_run_id='r',
        state={'session_id':'s','_runtime_v2_run_id':'r'}, session_manager=manager,
        runtime_lifecycle=SimpleNamespace(allows_stream_event=lambda _:True),
        persist_execution_event=execution, should_persist_ui_event=should_persist_ui_event,
        run_fact_commit=run_fact_commit, publish_session_event=publish,
        queue=asyncio.Queue(), consumer_attached=True)
    exec(compile(ast.Module(body=[node], type_ignores=[]), 'app/agent_loop.py', 'exec'), namespace)
    return namespace


@pytest.mark.parametrize('method',['astream_events','astream_events_continuation'])
@pytest.mark.parametrize('cancelled',[False,True])
def test_slow_progress_write_is_awaited_off_loop_before_publication(method, cancelled):
    entered, release = threading.Event(), threading.Event()
    owner, order = threading.get_ident(), []

    def append(sid, event):
        assert threading.get_ident() != owner, 'a slow progress write would block the emitter loop'
        assert sid == 's' and event['type'] == 'context_summary_progress'
        entered.set()
        assert release.wait(5)
        order.append('commit')

    ns = emitter(method, SimpleNamespace(append_ui_event=append), order)

    async def scenario():
        pending = asyncio.create_task(ns['emit_event']({'type':'context_summary_progress','phase':'start'}))
        try:
            async def entered_wait():
                while not entered.is_set():
                    if pending.done():
                        await pending
                    await asyncio.sleep(.001)
            await asyncio.wait_for(entered_wait(), 2)
            await asyncio.wait_for(asyncio.sleep(0), .1)
            assert not pending.done() and ns['queue'].empty() and not order
            if cancelled:
                pending.cancel()
                await asyncio.sleep(0)
                pending.cancel()
                await asyncio.sleep(0)
                assert not pending.done(), 'cancellation must not abandon an in-flight writer'
            release.set()
            if cancelled:
                with pytest.raises(asyncio.CancelledError):
                    await pending
                assert order == ['commit'] and ns['queue'].empty()
            else:
                await pending
                assert order == ['commit','publish']
                assert ns['queue'].get_nowait()['type'] == 'context_summary_progress'
        finally:
            release.set()
            await asyncio.gather(pending, return_exceptions=True)
    asyncio.run(scenario())


@pytest.mark.parametrize('method',['astream_events','astream_events_continuation'])
def test_failed_progress_write_is_not_published(method):
    order = []
    def fail(*_):
        raise OSError('write failed')
    ns = emitter(method, SimpleNamespace(append_ui_event=fail), order)
    async def scenario():
        with pytest.raises(OSError,match='write failed'):
            await ns['emit_event']({'type':'context_summary_progress'})
        assert not order and ns['queue'].empty()
    asyncio.run(scenario())
