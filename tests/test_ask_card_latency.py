import asyncio
import copy
import os
import threading

import pytest

from human_interaction import service as module


QUESTIONS = {'questions': [{'header': '选择', 'question': '选择哪一项？',
                            'options': [{'label': '甲', 'description': '甲方案'},
                                        {'label': '乙', 'description': '乙方案'}]}]}


@pytest.fixture
def service(tmp_path, monkeypatch):
    monkeypatch.setenv('ASK_USER_ENABLED', '1')
    monkeypatch.setenv('RUNTIME_V2_ASYNC_SNAPSHOT_CHECKPOINTS', 'false')
    result = module.HumanInteractionService(tmp_path, path_resolver=lambda sid: tmp_path/sid)
    monkeypatch.setattr(module, 'get_human_interaction_service', lambda: result)
    return result


def answer(record):
    q = record['questions'][0]
    return [{'question_id': q['question_id'], 'selected_option_ids': [q['options'][0]['option_id']]}]


def test_question_creation_reuses_validated_suffix_without_full_replay(service, monkeypatch):
    service.mirror.append('s', 'model_user', {'role': 'user', 'content': 'initial'}, raise_on_error=True)
    log = service.mirror.event_log
    for i in range(3):
        log.append('s', 'context_tokens', {'estimated': i})
    monkeypatch.setattr(log, 'read_all', lambda *_: pytest.fail('ordinary journal suffix must not replay the full log'))
    prepared = []
    original = service._snapshot_locked
    def counted(sid):
        prepared.append(sid)
        return original(sid)
    monkeypatch.setattr(service, '_snapshot_locked', counted)
    record = service.create_question('s', QUESTIONS)
    assert prepared == ['s']
    assert service.get('s', record['interaction_id'])['status'] == 'pending'
    assert service.pending_counts('s')['questions'] == 1
    snapshot = service.mirror.snapshots.read_consistent_view('s', log, service.mirror.projector)
    assert snapshot['last_seq'] == 5
    assert snapshot['raw_model_messages'][0]['payload']['content'] == 'initial'


@pytest.mark.parametrize('extra_fact', [False, True])
def test_replaced_event_source_rebuilds_before_question_validation(service, tmp_path, monkeypatch, extra_fact):
    service.mirror.append('s', 'model_user', {'role': 'user', 'content': 'old'}, raise_on_error=True)
    from runtime_v2 import SessionEventLog
    other = SessionEventLog(tmp_path/'other')
    other.append('s', 'model_user', {'role': 'user', 'content': 'replacement'})
    if extra_fact:
        other.append('s', 'context_tokens', {'estimated': 2})
    os.replace(other.event_path('s'), service.mirror.event_log.event_path('s'))
    reads = []
    original = service.mirror.event_log.read_all
    def read_all(sid):
        reads.append(sid)
        return original(sid)
    monkeypatch.setattr(service.mirror.event_log, 'read_all', read_all)
    service.create_question('s', QUESTIONS)
    snapshot = service.mirror.snapshots.read_consistent_view('s', service.mirror.event_log, service.mirror.projector)
    assert reads
    assert snapshot['raw_model_messages'][0]['payload']['content'] == 'replacement'


def test_get_and_list_copy_only_interaction_and_keep_nested_values_isolated(service, monkeypatch):
    class UnrelatedHistory:
        def __deepcopy__(self, memo):
            pytest.fail('get/list must not copy unrelated model or execution history')
    record = service.create_question('s', QUESTIONS)
    view = {'interactions': {record['interaction_id']: copy.deepcopy(record)},
            'raw_model_messages': [UnrelatedHistory()]}
    monkeypatch.setattr(service.mirror.snapshots, 'read_consistent_view', lambda *args: view)
    loaded = service.get('s', record['interaction_id'])
    loaded['questions'][0]['options'][0]['label'] = 'changed'
    listed = service.list('s')
    assert listed[0]['questions'][0]['options'][0]['label'] == '甲'
    listed[0]['questions'].clear()
    assert service.get('s', record['interaction_id'])['questions']


@pytest.mark.parametrize('bad_source', ['bad', ['bad'], None])
def test_invalid_snapshot_source_stamp_rebuilds_instead_of_trusting_seq(service, monkeypatch, bad_source):
    service.mirror.append('s', 'model_user', {'role': 'user', 'content': 'initial'}, raise_on_error=True)
    snapshot = service.mirror.snapshots.read_for_update('s')
    damaged = {**snapshot, '_event_log': bad_source}
    original_read = service.mirror.snapshots.read_for_update
    calls = []
    def read(sid):
        calls.append(sid)
        return damaged if len(calls) == 1 else original_read(sid)
    monkeypatch.setattr(service.mirror.snapshots, 'read_for_update', read)
    record = service.create_question('s', QUESTIONS)
    assert service.get('s', record['interaction_id'])['status'] == 'pending'
    assert calls == ['s']


def test_card_is_emitted_after_durable_creation_on_worker_and_waiter_on_owner_loop(service, monkeypatch):
    owner = threading.get_ident()
    threads = []
    original = service.create_question
    def create(*args, **kwargs):
        threads.append(threading.get_ident())
        return original(*args, **kwargs)
    monkeypatch.setattr(service, 'create_question', create)
    emitted = []
    async def emit(event):
        assert threading.get_ident() == owner
        assert module.has_registered_waiter('s', 'question', event['interaction_id'])
        assert any(e.type == 'interaction_requested' for e in service.mirror.event_log.read_all('s'))
        emitted.append(event)
        await asyncio.to_thread(service.resolve_question, 's', event['interaction_id'], answer(event))
    result = asyncio.run(module.wait_for_user_answers('s', QUESTIONS, run_id='r', react_iter=7, emit=emit))
    assert result['status'] == 'resolved'
    assert threads and all(t != owner for t in threads)
    assert len(emitted) == 1 and emitted[0]['react_iter'] == 7
    assert not module.has_registered_waiter('s', 'question', result['interaction_id'])


def test_answer_between_commit_and_waiter_registration_is_recovered(service, monkeypatch):
    original = service.create_question
    def create(*args, **kwargs):
        record = original(*args, **kwargs)
        service.resolve_question('s', record['interaction_id'], answer(record))
        return record
    monkeypatch.setattr(service, 'create_question', create)
    async def run():
        return await asyncio.wait_for(module.wait_for_user_answers('s', QUESTIONS), 3)
    assert asyncio.run(run())['status'] == 'resolved'


def test_cancel_during_question_creation_waits_and_cleans_up_without_card(service, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    original = service.create_question
    def create(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        return original(*args, **kwargs)
    monkeypatch.setattr(service, 'create_question', create)
    emitted = []
    async def emit(event):
        emitted.append(event)
    async def run():
        task = asyncio.create_task(module.wait_for_user_answers('s', QUESTIONS, emit=emit))
        try:
            while not entered.is_set():
                await asyncio.sleep(.001)
            task.cancel()
            task.cancel()
            await asyncio.sleep(.02)
            assert not task.done()
        finally:
            release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
    asyncio.run(run())
    records = service.list('s')
    assert len(records) == 1 and records[0]['status'] == 'cancelled'
    assert service.pending_counts('s')['questions'] == 0
    assert not emitted
    assert not module.has_registered_waiter('s', 'question', records[0]['interaction_id'])


def test_failed_question_commit_never_emits_or_registers_waiter(service, monkeypatch):
    before = dict(module._WAITERS)
    def fail(*args, **kwargs):
        raise OSError('append failed')
    monkeypatch.setattr(service.mirror.event_log, '_append_unlocked', fail)
    async def emit(event):
        pytest.fail('no card may be emitted after a failed append')
    with pytest.raises(OSError, match='append failed'):
        asyncio.run(module.wait_for_user_answers('s', QUESTIONS, emit=emit))
    assert module._WAITERS == before


def test_card_prepare_trace_finishes_before_human_answer(service, monkeypatch):
    traces = []
    monkeypatch.setattr(module.LocalOperationTrace, 'log', lambda trace: traces.append(trace.snapshot()))
    async def run():
        visible = asyncio.Event()
        records = []
        async def emit(event):
            records.append(event)
            visible.set()
        task = asyncio.create_task(module.wait_for_user_answers('s', QUESTIONS, run_id='r', react_iter=9, emit=emit))
        await asyncio.wait_for(visible.wait(), 3)
        assert not task.done()
        ready = next(row for row in traces if row['kind'] == 'ask_user_card_prepare')
        assert (ready['session_id'], ready['run_id'], ready['react_iter']) == ('s', 'r', 9)
        assert 'ask_question_card_emitted' in ready['anchors']
        assert any(span['name'] == 'ask_question_status_recheck' for span in ready['spans'])
        await asyncio.to_thread(service.resolve_question, 's', records[0]['interaction_id'], answer(records[0]))
        assert (await task)['status'] == 'resolved'
    asyncio.run(run())


def test_no_emitter_does_not_record_fake_card_delivery(service, monkeypatch):
    traces = []
    monkeypatch.setattr(module.LocalOperationTrace, 'log', lambda trace: traces.append(trace.snapshot()))
    result = asyncio.run(module.wait_for_user_answers('s', QUESTIONS, interrupt_check=lambda: True))
    assert result['status'] == 'cancelled'
    ready = next(row for row in traces if row['kind'] == 'ask_user_card_prepare')
    assert 'ask_question_card_emitted' not in ready['anchors']
