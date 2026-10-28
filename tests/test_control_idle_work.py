"""An idle control plane must not replay UI history or fsync every fact."""
import asyncio
from datetime import datetime, timezone
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from session_control.automation import AutomationService
from session_control.service import SessionControlService
from session_control.store import ControlStore
from tests.test_session_control import composed, new_session, rpc, run_async


@pytest.mark.parametrize('tasks', [[], [{'enabled': False, 'trigger': {'kind': 'event'}}],
                                   [{'enabled': True, 'trigger': {'kind': 'interval'}}]])
def test_no_enabled_event_rules_advance_batch_in_one_transaction(tmp_path, monkeypatch, tasks):
    store = ControlStore(tmp_path / 'control.db')
    for i, task in enumerate(tasks):
        store.put('automations', str(i), task, expected=0)
    for i in range(20):
        store.append_event({'source': 'test', 'id': str(i), 'type': 'run.ended', 'data': {}})
    service = AutomationService(SimpleNamespace(store=store))
    calls = []
    original = store.transaction
    @contextmanager
    def counted():
        calls.append(1)
        with original() as conn:
            yield conn
    monkeypatch.setattr(store, 'transaction', counted)
    asyncio.run(service.consume_events())
    assert len(calls) == 4  # Read cursor, events, rules; commit both watermarks.
    assert store.cursor('rules') == store.cursor('event_highwater') == 20
    calls.clear()
    asyncio.run(service.consume_events())
    assert len(calls) == 2, 'an empty event suffix performs no cursor writes'


def test_bulk_cursor_failure_does_not_skip_events_and_replay_is_safe(tmp_path, monkeypatch):
    store = ControlStore(tmp_path / 'control.db')
    store.append_event({'source': 'test', 'id': 'one', 'type': 'run.ended', 'data': {}})
    service = AutomationService(SimpleNamespace(store=store))
    original = store.set_cursors
    monkeypatch.setattr(store, 'set_cursors', lambda _: (_ for _ in ()).throw(OSError('simulated crash')))
    with pytest.raises(OSError):
        asyncio.run(service.consume_events())
    assert store.cursor('rules', 0) == store.cursor('event_highwater', 0) == 0
    monkeypatch.setattr(store, 'set_cursors', original)
    asyncio.run(service.consume_events())
    assert store.cursor('rules') == store.cursor('event_highwater') == 1
    store.set_cursors({'rules': 1, 'event_highwater': 1})
    with pytest.raises(ValueError):
        store.set_cursors({'rules': 2, 'event_highwater': float('nan')})
    assert store.cursor('rules') == store.cursor('event_highwater') == 1


@run_async
async def test_rule_admission_is_not_duplicated_when_watermark_commit_is_replayed(composed, monkeypatch):
    c = composed
    sid = await new_session(c)
    created = await rpc(c, 'automation.create', {'name': 'event rule',
        'trigger': {'kind': 'event', 'types': ['job.completed']},
        'target': {'mode': 'existing', 'session_id': sid}, 'action': {'kind': 'prompt', 'text': 'inspect'}})
    assert created.status_code == 200
    task_id = created.json()['data']['id']
    await c.control.close()
    async def no_dispatch():
        pass
    monkeypatch.setattr(c.service, 'start', no_dispatch)
    last = max([row['cursor'] for row in c.store.events()] or [0])
    c.store.set_cursors({'rules': last, 'event_highwater': last})
    sequence, _ = c.store.append_event({'source': 'runtime/' + sid, 'id': 'one', 'subject': sid,
        'time': datetime.now(timezone.utc).isoformat(), 'type': 'job.completed', 'data': {}})
    original = c.store.set_cursors
    monkeypatch.setattr(c.store, 'set_cursors', lambda _: (_ for _ in ()).throw(OSError('commit failed after admission')))
    with pytest.raises(OSError):
        await c.service.engine.consume_events()
    assert c.store.cursor('rules') == last
    monkeypatch.setattr(c.store, 'set_cursors', original)
    await c.service.engine.consume_events()
    operations = [row for row in c.store.operations() if row['request'].get('_automation_id') == task_id]
    assert len(operations) == 1 and operations[0]['status'] == 'queued'
    assert c.store.cursor('rules') >= sequence


@pytest.mark.parametrize('items', [[], [{'id': 'x', 'state': 'queued', 'after_turn': False}],
                                   [{'id': 'x', 'state': 'sent', 'after_turn': True}]])
def test_empty_followup_queues_never_check_ui_readiness(monkeypatch, items):
    import agent_loop
    monkeypatch.setattr(agent_loop, 'list_session_steers', lambda sid: {'items': items})
    service = SimpleNamespace(callbacks={'followup_state': lambda sid: pytest.fail('idle queue hydrated history')},
        legacy_scan_at=0, workers={}, manager=SimpleNamespace(list_sessions=lambda **_: [{'id': 's'}]))
    asyncio.run(SessionControlService.adopt_followups(service))


@pytest.mark.parametrize('state', ['ready', 'recovering', 'paused'])
def test_queued_followups_still_require_ready_state_and_admit_once(monkeypatch, state):
    import agent_loop
    items = [dict(id='x', state='queued', after_turn=True, content='question', ui_content='visible', user_content='original'),
             dict(id='y', state='queued', after_turn=True, content='next')]
    monkeypatch.setattr(agent_loop, 'list_session_steers', lambda sid: {'items': items})
    checked, admitted = [], []
    async def execute(*args, **kwargs):
        admitted.append((args, kwargs))
    service = SimpleNamespace(callbacks={'followup_state': lambda sid: checked.append(sid) or state},
        legacy_scan_at=0, workers={}, manager=SimpleNamespace(list_sessions=lambda **_: [{'id': 's'}]), execute=execute)
    asyncio.run(SessionControlService.adopt_followups(service))
    assert checked == ['s']
    assert len(admitted) == (1 if state == 'ready' else 0)
    if admitted:
        args, kwargs = admitted[0]
        assert args[1] == 'session.send' and args[2]['_legacy_followup_id'] == 'x'
        assert args[2]['ui_message'] == 'visible' and args[2]['_legacy_user_content'] == 'original'
        assert kwargs['idempotency_key'] == 'followup:x'
