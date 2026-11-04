"""Model continuation uses the same durable resume transition as the play button."""
import asyncio
import importlib.util
import json
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]


def load_module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def goal_tool(tmp_path, monkeypatch):
    import agent_goal
    import host_tool_registry

    monkeypatch.setenv('GOAL_ENABLED', '1')
    monkeypatch.setenv('RUNTIME_VERSION', '2')
    manager = agent_goal.GoalManager(tmp_path)
    stopped, cleared, published = {'s1'}, [], []
    owner_thread = threading.get_ident()

    def clear_interrupt(sid):
        assert threading.get_ident() != owner_thread
        # Restart eligibility is published only after the durable Goal is active.
        assert manager.get(sid)['status'] == 'active'
        stopped.discard(sid)
        cleared.append(sid)

    sessions = SimpleNamespace(clear_interrupt=clear_interrupt)
    monkeypatch.setattr(agent_goal, 'manager_for', lambda _: manager)
    registry = host_tool_registry.HostToolInvokerRegistry()
    monkeypatch.setattr(host_tool_registry, 'host_tool_invokers', registry)
    host = load_module('goal_continue_host_test', 'plugins/agent-goal/host.py')
    definitions = host.tool_definitions({'is_enabled': lambda _: True}, SimpleNamespace(plugin_id='agent-goal'))
    runner = load_module('goal_continue_runner_test', 'plugins/agent-goal/runner.py')
    runner._host = SimpleNamespace(manager=sessions, is_stopped=lambda sid: sid in stopped,
                                   is_active=lambda _: False, pending_human=lambda _: 0)

    async def publish(event):
        published.append(dict(event))

    def invoke(arguments, run_id='resume-run'):
        context = host_tool_registry.HostToolInvocationContext(
            session_id='s1', run_id=run_id,
            state={'session_id': 's1', '_runtime_v2_run_id': run_id},
            services={'session_manager': sessions, 'tool_name': 'update_goal'}, emit_event=publish,
        )
        return asyncio.run(registry.invoke('update_goal', context, arguments))

    return SimpleNamespace(manager=manager, invoke=invoke, definitions=definitions, runner=runner,
                           stopped=stopped, cleared=cleared, published=published, root=tmp_path)


def block_goal(c, budget=None):
    created = c.manager.create('s1', 'Continue the original objective', token_budget=budget)
    c.manager.record_run('s1', 12, run_id='work-run', continuation=True)
    for index in range(3):
        c.manager.update_status('s1', 'blocked', 'Missing credential',
                                blocker_key='credential', report_id=f'blocked-{index}')
    assert c.manager.get('s1')['status'] == 'blocked'
    return created


def test_update_goal_advertises_continue_and_optional_budget(goal_tool):
    definition = next(row['function'] for row in goal_tool.definitions if row['function']['name'] == 'update_goal')
    parameters = definition['parameters']
    assert parameters['properties']['status']['enum'] == ['completed', 'blocked', 'continue']
    assert parameters['properties']['additional_budget']['minimum'] == 1
    assert parameters['required'] == ['status']


@pytest.mark.parametrize('status', ['blocked', 'paused'])
@pytest.mark.parametrize('budget', [None, 100])
def test_model_continue_preserves_work_and_makes_goal_runnable(goal_tool, status, budget):
    import agent_goal

    c = goal_tool
    original = block_goal(c, budget)
    if status == 'paused':
        c.manager.user_action('s1', 'resume')
        c.manager.user_action('s1', 'pause', reason='manual')
    before = c.manager.get('s1')
    assert c.runner._discover(['s1']) == []
    outcome = c.invoke({'status': 'continue', 'reason': 'User asked to continue; credential supplied'})
    assert outcome.kind.value == 'completed', outcome.message
    resumed = json.loads(outcome.content)['goal']
    assert resumed['status'] == 'active' and resumed['id'] == original['id']
    for field in ('objective', 'used_tokens', 'token_budget', 'run_count', 'continuation_count'):
        assert resumed[field] == before[field]
    assert resumed['blocked_streak'] == 0 and resumed['consecutive_failures'] == 0
    for field in ('blocked_reason', 'blocked_fingerprint', 'blocker_key', 'pause_reason', 'next_retry_at'):
        assert resumed[field] is None
    assert resumed['updated_by'] == 'model' and resumed['last_run_id'] == 'resume-run'
    assert c.cleared == ['s1'] and c.runner._discover(['s1']) == ['s1']
    assert c.published == [{'type': 'extension_state_changed', 'plugin_id': 'agent-goal',
                            'namespace': 'goal', 'action': 'update_goal', 'ephemeral': True}]
    assert not outcome.metadata['workflow_completion_requested']
    assert outcome.metadata['lifecycle_events'] == []
    assert agent_goal.GoalManager(c.root).get('s1')['status'] == 'active'
    # A new blocked audit needs three new reports after a restart.
    report = c.manager.update_status('s1', 'blocked', 'Missing credential',
                                     blocker_key='credential', report_id='new-blocked-run')
    assert report['status'] == 'active' and report['blocked_streak'] == 1


def test_continue_requires_budget_when_exhausted_then_applies_authorized_amount(goal_tool):
    c = goal_tool
    block_goal(c, budget=20)
    c.manager.record_usage('s1', 10, usage_id='final-call')
    before = c.manager.get('s1')
    outcome = c.invoke({'status': 'continue'})
    assert outcome.kind.value == 'failed' and 'additional_budget' in outcome.message
    assert c.manager.get('s1')['status'] == 'blocked' and c.stopped == {'s1'}
    assert c.cleared == [] and c.published == []
    outcome = c.invoke({'status': 'continue', 'additional_budget': 50})
    assert outcome.kind.value == 'completed', outcome.message
    resumed = c.manager.get('s1')
    assert resumed['used_tokens'] == before['used_tokens'] == 22
    assert resumed['token_budget'] == 70 and resumed['remaining_tokens'] == 48
    assert c.runner._discover(['s1']) == ['s1']


@pytest.mark.parametrize('budget', [0, -1, 'invalid'])
def test_invalid_additional_budget_does_not_resume_or_clear_stop(goal_tool, budget):
    c = goal_tool
    block_goal(c)
    outcome = c.invoke({'status': 'continue', 'additional_budget': budget})
    assert outcome.kind.value == 'failed'
    assert c.manager.get('s1')['status'] == 'blocked'
    assert c.cleared == [] and c.published == [] and c.stopped == {'s1'}


@pytest.mark.parametrize('status', ['missing', 'active', 'cancelled', 'completed'])
def test_continue_does_not_create_replace_or_reopen_other_goals(goal_tool, status):
    c = goal_tool
    if status != 'missing':
        c.manager.create('s1', 'Keep existing state')
        if status == 'cancelled':
            c.manager.user_action('s1', 'cancel')
        elif status == 'completed':
            requested = c.manager.update_status('s1', 'completed', 'Verified', report_id='done')
            c.manager.record_judge_result('s1', verdict='done', reason='Verified', run_id='judge',
                expected_completion_request_id=requested['completion_request_id'])
    before = c.manager.get('s1')
    outcome = c.invoke({'status': 'continue'})
    assert outcome.kind.value == 'failed'
    after = c.manager.get('s1')
    assert (after or {}).get('version') == (before or {}).get('version')
    assert (after or {}).get('status') == (before or {}).get('status')
    assert c.cleared == [] and c.published == []


@pytest.mark.parametrize('status', ['completed', 'blocked'])
def test_budget_is_not_silently_accepted_for_other_updates(goal_tool, status):
    c = goal_tool
    c.manager.create('s1', 'Existing goal')
    outcome = c.invoke({'status': status, 'reason': 'Evidence', 'additional_budget': 50})
    assert outcome.kind.value == 'failed' and 'only supported with status=continue' in outcome.message
    assert c.manager.get('s1')['completion_request_id'] is None
    assert c.cleared == [] and c.published == []


def test_completion_and_blocker_updates_keep_the_existing_judge_contract(goal_tool):
    c = goal_tool
    c.manager.create('s1', 'Existing goal')
    outcome = c.invoke({'status': 'blocked', 'reason': 'Missing credential'}, run_id='blocked-1')
    report = json.loads(outcome.content)['goal']
    assert report['status'] == 'active' and report['blocked_streak'] == 1
    outcome = c.invoke({'status': 'completed', 'reason': 'Verification evidence'}, run_id='done')
    requested = json.loads(outcome.content)['goal']
    assert requested['status'] == 'active' and requested['completion_judge_requested']
    assert outcome.metadata['workflow_completion_requested']
    assert c.cleared == []
