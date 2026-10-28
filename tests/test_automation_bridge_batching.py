"""Event bridge batching preserves crash/replay and event-cursor boundaries."""
import hashlib
import json
from types import SimpleNamespace

import pytest

from runtime_v2.versions import EVENT_SCHEMA_VERSION
from session_control.automation import AutomationService
from session_control.store import ControlStore


def fixture(tmp_path, kinds):
    session = tmp_path / 'sessions/s'
    session.mkdir(parents=True)
    rows = [dict(schema_version=EVENT_SCHEMA_VERSION, session_id='s', seq=i, type=kind,
                 run_id='r', timestamp='2026-10-26T00:00:00Z', payload={})
            for i, kind in enumerate(kinds, 1)]
    path = session / 'events.jsonl'
    path.write_text(''.join(json.dumps(row) + '\n' for row in rows), encoding='utf-8')
    manager = SimpleNamespace(sessions_dir=session.parent, _resolve_session_path=lambda sid: session.parent / sid)
    store = ControlStore(tmp_path / 'control.db')
    service = AutomationService(SimpleNamespace(manager=manager, store=store))
    return service, store, path


def test_trace_backfill_commits_once_per_batch_and_resumes_after_restart(tmp_path, monkeypatch):
    service, store, _ = fixture(tmp_path, ['execution_recorded'] * 1001)
    writes = []
    original = store.set_cursor
    def write(name, value):
        writes.append(value['seq'])
        return original(name, value)
    monkeypatch.setattr(store, 'set_cursor', write)
    assert service._bridge_session('s') is True
    assert writes == [500]
    # A new service instance reads only the unacknowledged suffix.
    resumed = AutomationService(service.control)
    assert resumed._bridge_session('s') is True
    assert resumed._bridge_session('s') is False
    assert resumed._bridge_session('s') is False
    assert writes == [500, 1000, 1001]
    assert store.cursor('runtime:s')['seq'] == 1001
    assert store.events() == []


@pytest.mark.parametrize('trailing_trace', [False, True])
def test_business_events_keep_atomic_cursors_and_no_redundant_tail_commit(tmp_path, monkeypatch, trailing_trace):
    kinds = ['execution_recorded', 'run_finished', 'execution_recorded', 'assistant_final_committed']
    if trailing_trace:
        kinds.append('execution_recorded')
    service, store, _ = fixture(tmp_path, kinds)
    cursors = []
    append = store.append_event
    write = store.set_cursor
    def event(value, **kwargs):
        cursors.append(('event', kwargs['cursor'][1]['seq']))
        return append(value, **kwargs)
    def tail(name, value):
        cursors.append(('tail', value['seq']))
        return write(name, value)
    monkeypatch.setattr(store, 'append_event', event)
    monkeypatch.setattr(store, 'set_cursor', tail)
    service._bridge_session('s')
    assert cursors == [('event', 2), ('event', 4)] + ([('tail', 5)] if trailing_trace else [])
    assert [row['type'] for row in store.events()] == ['run.ended', 'turn.completed']
    service._bridge_session('s')
    assert len(store.events()) == 2


def test_failed_business_event_cannot_acknowledge_later_facts(tmp_path, monkeypatch):
    service, store, _ = fixture(tmp_path, ['run_finished', 'execution_recorded', 'assistant_final_committed', 'execution_recorded'])
    original = store.append_event
    def fail_final(event, **kwargs):
        if event['type'] == 'turn.completed':
            raise OSError('simulated durable write failure')
        return original(event, **kwargs)
    monkeypatch.setattr(store, 'append_event', fail_final)
    with pytest.raises(OSError):
        service._bridge_session('s')
    assert store.cursor('runtime:s')['seq'] == 1
    monkeypatch.setattr(store, 'append_event', original)
    service._bridge_session('s')
    assert store.cursor('runtime:s')['seq'] == 4
    assert [row['type'] for row in store.events()] == ['run.ended', 'turn.completed']


def test_failed_tail_commit_replays_nonsemantic_suffix_safely(tmp_path, monkeypatch):
    service, store, _ = fixture(tmp_path, ['run_finished', 'execution_recorded', 'execution_recorded'])
    original = store.set_cursor
    monkeypatch.setattr(store, 'set_cursor', lambda *args: (_ for _ in ()).throw(OSError('commit failed')))
    with pytest.raises(OSError):
        service._bridge_session('s')
    assert store.cursor('runtime:s')['seq'] == 1
    monkeypatch.setattr(store, 'set_cursor', original)
    service._bridge_session('s')
    assert store.cursor('runtime:s')['seq'] == 3
    assert len(store.events()) == 1


def test_generation_gap_and_backfill_are_preserved(tmp_path):
    service, store, path = fixture(tmp_path, ['execution_recorded'] * 3)
    store.set_cursor('runtime:s', {'generation': 'previous-log', 'seq': 99})
    service._bridge_session('s')
    generation = hashlib.sha256(path.read_bytes().splitlines(keepends=True)[0]).hexdigest()[:24]
    assert store.cursor('runtime:s') == {'generation': generation, 'seq': 3}
    assert [event['type'] for event in store.events()] == ['history.gap']
