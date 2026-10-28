"""Final delivery must stay live while awaited post-final writers settle."""
import asyncio
import threading
import time

import pytest

from tests.test_queued_followup_continuation import queued_runtime


@pytest.mark.parametrize('continuation', [False, True])
@pytest.mark.parametrize('stage', ['title', 'history'])
def test_final_can_cross_an_async_handoff_during_post_final_work(
        queued_runtime, monkeypatch, continuation, stage):
    agent, directory = queued_runtime
    import agent_harness
    from runtime_v2.event_log import SessionEventLog

    monkeypatch.setattr(agent_harness, 'warm_llm_connections_if_stale', lambda: None)
    monkeypatch.setattr(agent.session_manager, 'get_interrupt_reason', lambda *args: '', raising=False)
    sid = 'final-handoff'
    if continuation:
        agent._runtime_v2_react_history_ops().commit_user_turn(sid, 'question', run_id='old')
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    deadline_missed = []

    async def react(state, emit):
        state['final_response'] = 'answer'
        return state

    original_finish = agent.finish

    def blocked(state):
        entered.set()
        try:
            if not release.wait(0.5):
                deadline_missed.append(True)
            return original_finish(state) if stage == 'history' else False
        finally:
            finished.set()

    monkeypatch.setattr(agent, '_run_react_node_off_loop', react)
    monkeypatch.setattr(agent, 'schedule_session_title_generation' if stage == 'title' else 'finish', blocked)
    seen = []

    async def collect():
        stream = (agent.astream_events_continuation(sid, require_pending_subagents=False, run_id='run')
                  if continuation else agent.astream_events('question', session_id=sid, run_id='run'))
        try:
            async for event in stream:
                seen.append(event['type'])
                if event['type'] == 'final':
                    # Observer/wire code can require more than one scheduling hop.
                    # A single sleep(0) in the producer does not flush that path.
                    await asyncio.sleep(0)
                    await asyncio.sleep(0)
                    while not entered.is_set():
                        await asyncio.sleep(0.001)
                    facts = SessionEventLog(directory).read_all(sid)
                    assert any(e.type == 'assistant_final_committed' for e in facts)
                    assert not any(e.type == 'run_finished' for e in facts)
                    assert not finished.is_set(), 'post-final work blocked the event loop'
                    release.set()
        finally:
            release.set()
            await stream.aclose()

    asyncio.run(collect())
    assert not deadline_missed
    assert finished.is_set()
    assert seen.index('final') < seen.index('run_finished')


@pytest.mark.parametrize('cancel_count', [1, 2])
def test_post_final_cancel_waits_for_history_writer(monkeypatch, cancel_count):
    import agent_loop as agent

    entered, release = threading.Event(), threading.Event()
    writes = []

    def finish(state):
        entered.set()
        assert release.wait(2)
        writes.append('committed')
        state['final_printed'] = True
        return state

    monkeypatch.setattr(agent, 'schedule_session_title_generation', lambda state: False)
    monkeypatch.setattr(agent, 'finish', finish)

    async def scenario():
        state = {'session_id': 'cancel-final', '_runtime_v2_run_id': 'run'}
        task = asyncio.create_task(agent._finish_after_final_off_loop(state, {}))
        try:
            deadline = time.monotonic() + 2
            while not entered.is_set() and time.monotonic() < deadline:
                await asyncio.sleep(0.001)
            assert entered.is_set()
            for _ in range(cancel_count):
                task.cancel()
                await asyncio.sleep(0)
            assert not task.done()
            assert writes == []
            release.set()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert writes == ['committed']
            assert state['final_printed'] is True
        finally:
            release.set()
            if not task.done():
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    asyncio.run(scenario())
