"""Pausing the Goal disables later automation while the accepted run finishes."""
import asyncio
import importlib.util
import json
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.test_session_control import composed, new_session, rpc


ROOT = Path(__file__).resolve().parents[1]


def load_module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def goal_environment(tmp_path, monkeypatch):
    import agent_goal
    import agent_loop

    monkeypatch.setenv('GOAL_ENABLED', '1')
    monkeypatch.setenv('RUNTIME_VERSION', '2')
    manager = agent_goal.GoalManager(tmp_path / 'goals')
    monkeypatch.setattr(agent_goal, 'manager_for', lambda _: manager)
    host = load_module('goal_pause_host_test', 'plugins/agent-goal/host.py')
    runtime = load_module('goal_pause_runtime_test', 'plugins/agent-goal/runtime.py')
    runtime.initialize(agent_loop)
    runtime.goal_manager_for = lambda _: manager
    runtime._load_goal_judge_dialogue_for_goal = lambda *_: []
    runner = load_module('goal_pause_runner_test', 'plugins/agent-goal/runner.py')
    events = []

    async def publish(sid, event):
        events.append((sid, event))

    monkeypatch.setattr(host, 'publish_session_event', publish)
    return SimpleNamespace(manager=manager, host=host, runtime=runtime, runner=runner, events=events)


class EmptyRequest:
    async def json(self):
        return {}


@pytest.mark.parametrize('source', ['chat', 'goal'])
def test_pause_preserves_inflight_run_and_prevents_another(goal_environment, composed, monkeypatch, source):
    import session_control.integration as integration
    from runtime_v2 import RuntimeHistoryOps

    c, g = composed, goal_environment
    monkeypatch.setattr(integration, '_application', c.control)

    async def scenario():
        sid = await new_session(c)
        original = g.manager.create(sid, 'Finish the current task without another Goal run')
        monkeypatch.setattr(c.manager, 'can_continue_react_session', lambda _: True)
        g.runner._host = SimpleNamespace(manager=c.manager,
            is_active=lambda session_id: session_id in c.active,
            is_stopped=c.manager.is_interrupt_requested, pending_human=lambda _: 0)
        entered, release = threading.Event(), threading.Event()
        progress = []
        ops = RuntimeHistoryOps(c.manager.sessions_dir, path_resolver=c.manager._resolve_session_path)

        async def finish_current(session_id, run_id, turn_id=None):
            progress.append('started')
            entered.set()
            yield {'type': 'run_started'}
            assert await asyncio.to_thread(release.wait, 5)
            assert not c.manager.is_interrupt_requested(session_id, run_id)
            progress.append('finished')
            ops.commit_assistant_final(session_id, 'Current task finished',
                operation_id='final:' + (turn_id or run_id), run_id=run_id)
            g.manager.record_run(session_id, 7, continuation=source == 'goal',
                                  run_id=run_id, outcome='finished')
            yield {'type': 'final', 'content': 'Current task finished'}

        async def chat(message, *, session_id, run_id, user_operation_id='', **_kwargs):
            ops.commit_user_turn(session_id, message, operation_id=user_operation_id, run_id=run_id)
            async for event in finish_current(session_id, run_id, user_operation_id):
                yield event

        async def continuation(session_id, **kwargs):
            async for event in finish_current(session_id, kwargs['run_id']):
                yield event

        monkeypatch.setattr(c.service.deps, 'astream_events', chat)
        c.service.callbacks['continue'] = continuation
        task = None
        await c.control.start()
        try:
            if source == 'goal':
                task = asyncio.create_task(g.runner._continue(sid))
            else:
                response = await rpc(c, 'session.send', {'session_id': sid, 'message': 'Current task'})
                operation_id = response.json()['operation_id']
            assert await asyncio.to_thread(entered.wait, 3)
            run_id = c.active[sid]
            response = await g.host.control_goal(c.manager, sid, 'pause', EmptyRequest())
            assert response.status_code == 200, response.body
            paused = json.loads(response.body)['goal']
            assert paused['id'] == original['id'] and paused['status'] == 'paused'
            assert not c.manager.is_interrupt_requested(sid, run_id)
            assert c.active[sid] == run_id and progress == ['started']
            if source == 'goal':
                assert paused['current_run_id'] == run_id
            operation_count = len(c.store.operations(session_id=sid))
            await g.runner._continue(sid)
            assert len(c.store.operations(session_id=sid)) == operation_count
            release.set()
            if task is not None:
                await asyncio.wait_for(task, 3)
            else:
                done = await rpc(c, 'operation.wait', {'id': operation_id, 'timeout': 3})
                assert done.json()['data']['status'] == 'succeeded', done.text
            assert progress == ['started', 'finished']
            assert any(op['status'] == 'succeeded' for op in c.store.operations(session_id=sid))
            final_goal = g.manager.get(sid)
            assert final_goal['status'] == 'paused' and final_goal['pause_reason'] == 'manual'
            assert final_goal['used_tokens'] == 7 and final_goal['run_count'] == 1
            assert final_goal['current_run_id'] is None
            assert g.runner._discover([sid]) == []
            await g.runner._continue(sid)
            assert len(c.store.operations(session_id=sid)) == operation_count
        finally:
            release.set()
            if task is not None:
                await asyncio.gather(task, return_exceptions=True)
            await c.control.close()

    asyncio.run(scenario())


def test_paused_goal_skips_judge_context_and_continuation_hooks(goal_environment, monkeypatch):
    import agent_goal_judge

    g = goal_environment
    g.manager.create('s1', 'Pause checks')
    g.manager.update_status('s1', 'completed', 'Evidence', report_id='run')
    g.manager.user_action('s1', 'pause')

    def unexpected(*_args, **_kwargs):
        raise AssertionError('Paused Goal must not run checks or continuation hooks')

    monkeypatch.setattr(agent_goal_judge, 'evaluate_goal', unexpected)
    g.runtime._dispatch_state_hook = unexpected
    state = {'session_id': 's1', '_runtime_v2_run_id': 'run', 'work_messages': []}
    async def scenario():
        assert g.runtime._goal_continuation_message('s1') is None
        await g.runtime._before_continue(state)
        goal, applied = await g.runtime._run_pending_goal_judge(state)
        assert goal['status'] == 'paused' and applied is False
        assert state['work_messages'] == []
    asyncio.run(scenario())


def test_judge_already_inflight_cannot_override_manual_pause(goal_environment, monkeypatch):
    import agent_goal_judge

    g = goal_environment
    g.manager.create('s1', 'Pause during Judge')
    g.manager.update_status('s1', 'completed', 'Evidence', report_id='run')
    entered, release = threading.Event(), threading.Event()

    def evaluate(*_args):
        entered.set()
        assert release.wait(3)
        return {'verdict': 'done', 'reason': 'Accepted', 'usage': {}}

    monkeypatch.setattr(agent_goal_judge, 'evaluate_goal', evaluate)
    async def scenario():
        task = asyncio.create_task(g.runtime._run_pending_goal_judge(
            {'session_id': 's1', '_runtime_v2_run_id': 'run', 'work_messages': []}))
        try:
            assert await asyncio.to_thread(entered.wait, 2)
            g.manager.user_action('s1', 'pause')
            release.set()
            result, applied = await task
            assert result['status'] == 'paused' and applied is False
            assert result['judge_count'] == 0 and result['last_judge_verdict'] is None
        finally:
            release.set()
            await asyncio.gather(task, return_exceptions=True)
    asyncio.run(scenario())


def test_cancel_retains_its_explicit_interrupt(goal_environment):
    g = goal_environment
    g.manager.create('s1', 'Cancelled objective')
    interrupts = []
    sessions = SimpleNamespace(request_interrupt=lambda sid, **kwargs: interrupts.append((sid, kwargs)))
    response = asyncio.run(g.host.control_goal(sessions, 's1', 'cancel', EmptyRequest()))
    assert response.status_code == 200
    assert interrupts == [('s1', {'reason': 'workflow_cancel'})]
