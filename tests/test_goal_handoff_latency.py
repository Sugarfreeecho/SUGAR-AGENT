"""Handoffs stay responsive while inventory/event maintenance is busy."""
import asyncio
import threading
from types import SimpleNamespace

import pytest

from tests.test_session_control import composed, new_session, rpc, run_async
from tests.test_goal_runner import _load_plugin_module


@run_async
async def test_known_goal_is_admitted_before_a_slow_inventory_scan(monkeypatch):
    import agent_goal
    import session_control.public as public

    goal = _load_plugin_module('goal_priority_test', 'plugins/agent-goal/runner.py')
    inventory_started, release = asyncio.Event(), asyncio.Event()
    admissions = []
    async def inventory(*_args, **_kwargs):
        inventory_started.set()
        await release.wait()
        return [{'id': 'known'}, {'id': 'archived'}]
    async def run(_owner, function, *args):
        return function(*args)
    async def admit(sid, **_kwargs):
        admissions.append(sid)
    monkeypatch.setattr(agent_goal, 'active_goal_session_ids', lambda: ['known'])
    monkeypatch.setattr(public, 'control_application', lambda: SimpleNamespace(service=SimpleNamespace(
        monitors=SimpleNamespace(sessions=inventory), resources=SimpleNamespace(io=SimpleNamespace(run=run)))))
    goal._host = SimpleNamespace(manager=object(), is_active=lambda _: False)
    monkeypatch.setattr(goal, '_discover', lambda ids: [sid for sid in ids if sid == 'known'])
    monkeypatch.setattr(goal, '_continue', admit)
    task = asyncio.create_task(goal._tick())
    try:
        await asyncio.wait_for(inventory_started.wait(), 1)
        assert admissions == ['known'], 'Known Goal waited behind the full inventory scan'
    finally:
        release.set()
        await task


@pytest.mark.parametrize('method', ['session.send', 'session.continue'])
@pytest.mark.parametrize('backlog', [False, True])
@run_async
async def test_new_admission_does_not_wait_for_background_maintenance(composed, monkeypatch, method, backlog):
    from runtime_v2 import RuntimeHistoryOps

    c = composed
    sid = await new_session(c)
    monkeypatch.setattr(c.manager, 'can_continue_react_session', lambda _: True)
    await c.control.start()
    entered, release = asyncio.Event(), asyncio.Event()
    worker_started = threading.Event()
    async def maintenance():
        entered.set()
        await release.wait()
    monkeypatch.setattr(c.service.engine, 'tick', maintenance)
    original = c.service.deps.astream_events
    async def stream(message, **kwargs):
        worker_started.set()
        async for event in original(message, **kwargs):
            yield event
    monkeypatch.setattr(c.service.deps, 'astream_events', stream)
    async def continuation(session_id, **kwargs):
        worker_started.set()
        run_id = kwargs['run_id']
        RuntimeHistoryOps(c.manager.sessions_dir, path_resolver=c.manager._resolve_session_path).commit_assistant_final(
            session_id, 'finished', operation_id='final:' + run_id, run_id=run_id)
        yield {'type': 'final', 'content': 'finished'}
    c.service.callbacks['continue'] = continuation
    try:
        c.service.monitors.wake(c.service.monitor_key)
        await asyncio.wait_for(entered.wait(), 2)
        if backlog:
            from runtime_v2.event_log import SessionEventLog
            SessionEventLog(c.manager.sessions_dir, c.manager._resolve_session_path).append_batch(
                sid, [{'type': 'ui_event', 'payload': {'type': 'status', 'content': 'old'}} for _ in range(1001)])
        params = {'session_id': sid, **({'message': 'work'} if method == 'session.send' else {})}
        response = await rpc(c, method, params)
        assert response.status_code == 200, response.text
        assert await asyncio.to_thread(worker_started.wait, 1), 'Admission waited for the blocked background cycle'
        assert not release.is_set()
        operation_id = response.json()['operation_id']
        # The periodic and immediate paths must share admission ownership.
        await asyncio.gather(c.service._dispatch_pending(), c.service._dispatch_pending())
        done = await rpc(c, 'operation.wait', {'id': operation_id, 'timeout': 3})
        assert done.json()['data']['status'] == 'succeeded', done.text
        assert len([op for op in c.store.operations(session_id=sid) if op['method'] == method]) == 1
    finally:
        release.set()
        await c.control.close()


def test_progress_distinguishes_queue_prepare_model_wait_and_execution():
    goal = _load_plugin_module('goal_progress_test', 'plugins/agent-goal/runner.py')
    stopped = False
    goal._host = SimpleNamespace(is_stopped=lambda _: stopped, pending_human=lambda _: 0, is_active=lambda _: False)
    state = {'id': 'g1', 'status': 'active', 'current_run_id': 'r1'}
    goal._set_progress('s1', 'queued', run_id='r1')
    assert goal.progress_snapshot('s1', state)['phase'] == 'queued'
    goal._observe_progress('s1', {'type': 'run_started', 'run_id': 'r1'})
    assert goal.progress_snapshot('s1', state)['phase'] == 'preparing'
    goal._observe_progress('s1', {'type': 'status', 'content': '正在思考中...', 'run_id': 'r1'})
    assert goal.progress_snapshot('s1', state)['phase'] == 'model_wait'
    goal._observe_progress('s1', {'type': 'llm_response_delta', 'run_id': 'other'})
    assert goal.progress_snapshot('s1', state)['phase'] == 'model_wait'
    goal._observe_progress('s1', {'type': 'tool_pending', 'run_id': 'r1'})
    assert goal.progress_snapshot('s1', state)['phase'] == 'running'
    goal._observe_progress('s1', {'type': 'final', 'run_id': 'r1'})
    assert goal.progress_snapshot('s1', state)['phase'] == 'finishing'
    goal._observe_progress('s1', {'type': 'run_finished', 'run_id': 'r1'})
    assert goal.progress_snapshot('s1', state)['phase'] == 'finishing'
    state['current_run_id'] = None
    waiting = goal.progress_snapshot('s1', state)
    assert waiting['phase'] == 'waiting'
    goal._observe_progress('s1', {'type': 'run_finished', 'run_id': 'r1'})
    assert goal.progress_snapshot('s1', state)['since'] == waiting['since']
    stopped = True
    assert goal.progress_snapshot('s1', state)['phase'] == 'stopped'
    state['status'] = 'paused'
    assert goal.progress_snapshot('s1', state)['phase'] == 'paused'


def test_new_admission_ignores_late_events_from_the_previous_run():
    goal = _load_plugin_module('goal_progress_identity_test', 'plugins/agent-goal/runner.py')
    goal._set_progress('s1', 'finishing', run_id='old')
    goal._set_progress('s1', 'queued')
    goal._observe_progress('s1', {'type': 'run_finished', 'run_id': 'old'})
    assert goal._progress['s1']['phase'] == 'queued'


@pytest.mark.parametrize('rows', [[], [{'parent_run_id': 'other'}], [{'parent_run_id': 'r1', 'after_final_index': 3}]])
def test_finalization_without_unanchored_results_does_not_read_history(composed, monkeypatch, rows):
    manager = composed.manager
    monkeypatch.setattr(manager, '_load_pending_subagent_results', lambda _: rows)
    def unexpected(_sid):
        pytest.fail('Finalization loaded the entire UI history without any results to anchor')
    monkeypatch.setattr(manager, '_load_ui_events_for_active_runtime', unexpected)
    assert manager.anchor_pending_subagent_results_for_run('s1', 'r1') == 0


def test_finalization_still_anchors_matching_child_results(composed, monkeypatch):
    manager, saved = composed.manager, []
    rows = [{'parent_run_id': 'r1'}, {'parent_run_id': 'other'}]
    monkeypatch.setattr(manager, '_load_pending_subagent_results', lambda _: rows)
    monkeypatch.setattr(manager, '_load_ui_events_for_active_runtime', lambda _: [{'type': 'user'}, {'type': 'final'}])
    monkeypatch.setattr(manager, '_save_pending_subagent_results', lambda sid, value: saved.append(value))
    assert manager.anchor_pending_subagent_results_for_run('s1', 'r1') == 1
    assert saved[0][0]['after_final_index'] == 1
    assert saved[0][0]['delivery_scope'] == 'after_final'
    assert 'after_final_index' not in saved[0][1]


def test_parallel_bridge_consumers_advance_instead_of_replaying_the_same_batch(composed, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from runtime_v2.event_log import SessionEventLog
    from session_control.automation import AutomationService
    c, sid = composed, '69d44f47-6512-48ca-b14f-3ef97906f013'
    log = SessionEventLog(c.manager.sessions_dir, c.manager._resolve_session_path)
    log.append_batch(sid, [{'type': 'ui_event', 'payload': {'type': 'status'}} for _ in range(1001)])
    engine = AutomationService(c.service)
    entered, release, second_commit = threading.Event(), threading.Event(), threading.Event()
    original = c.store.set_cursor
    first_thread = []
    def set_cursor(name, value):
        if name == 'runtime:' + sid:
            if not first_thread:
                first_thread.append(threading.get_ident())
                entered.set()
                assert release.wait(3)
            elif threading.get_ident() != first_thread[0]:
                second_commit.set()
        return original(name, value)
    monkeypatch.setattr(c.store, 'set_cursor', set_cursor)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(engine._bridge_session, sid)
        try:
            assert entered.wait(2)
            second = pool.submit(engine._bridge_session, sid)
            second_commit.wait(.1)
        finally:
            release.set()
        assert first.result(3) and second.result(3)
    assert c.store.cursor('runtime:' + sid)['seq'] == 1000
