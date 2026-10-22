from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from change_review_capture import ChangeReviewCapture


@pytest.mark.parametrize('stage', ['before', 'after'])
def test_failed_review_is_attached_without_changing_tool_result(stage):
    def callback(name, *args):
        if name == ('before_native_file_tool' if stage == 'before' else 'after_native_file_tool'):
            raise RuntimeError('probe')
        return SimpleNamespace(capture_id='capture', coverage='workspace')

    callbacks = SimpleNamespace(call=callback)
    state = {'session_id': 'session', '_runtime_v2_run_id': 'execution', '_change_review_turn_id': 'turn'}
    failed = ChangeReviewCapture(lambda: callbacks, state, 'run_shell', {}, 'first')
    token = failed.before()
    changes = failed.after(token, True)
    response = failed.attach({'result_for_llm': 'ok', 'ui': {'other': 'keep'}}, changes)
    assert response['result_for_llm'] == 'ok' and response['ui']['other'] == 'keep'
    status = response['ui']['change_review_status']
    assert (status['stage'], status['status'], status['reason']) == (stage, 'failed', 'probe')
    assert (status['run_id'], status['turn_id'], status['tool_call_id']) == ('execution', 'turn', 'first')
    # Another concurrent invocation sharing state must not inherit the failure.
    healthy = ChangeReviewCapture(lambda: SimpleNamespace(call=lambda *_: []), state, 'write_file', {}, 'second')
    healthy.after(SimpleNamespace(coverage='declared_paths'), True)
    assert healthy.attach({}, [])['ui']['change_review_status']['status'] == 'checked'
    assert failed.status['status'] == 'failed'


def test_absent_hook_does_not_invent_review_metadata():
    review = ChangeReviewCapture(lambda: SimpleNamespace(call=lambda *_: None), {}, 'read_file', {}, 'call')
    assert review.after(review.before(), True) == []
    assert review.attach({'result': 'ok'}, []) == {'result': 'ok'}


def test_batch_failure_is_visible_deduplicated_and_cleared_after_retry(monkeypatch):
    import agent_loop
    state = {'session_id': 'session', '_runtime_v2_run_id': 'execution', '_change_review_turn_id': 'turn',
             '_change_review_dirty': True}
    events = []

    def fail(*_):
        raise OSError('flush probe')

    async def push(_state, event, **_):
        events.append(event)

    registry = SimpleNamespace(call=fail)
    monkeypatch.setattr(agent_loop, '_state_run_has_write_fence', lambda _: True)
    monkeypatch.setattr(agent_loop, '_workflow_callbacks', lambda: registry)
    monkeypatch.setattr(agent_loop, '_push_stream_event', push)
    asyncio.run(agent_loop._flush_file_tool_reviews(state))
    asyncio.run(agent_loop._flush_file_tool_reviews(state))
    assert len(events) == 1 and events[0]['change_review_status']['status'] == 'failed'
    assert state['_change_review_dirty'], 'review work remains retryable'
    registry.call = lambda *_: []
    asyncio.run(agent_loop._flush_file_tool_reviews(state))
    assert len(events) == 2 and events[-1]['change_review_status']['status'] == 'checked'
    assert '_change_review_flush_failure' not in state
