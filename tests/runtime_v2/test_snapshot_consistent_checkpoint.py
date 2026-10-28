"""Consistent readers publish views without serializing generation on derived IO."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
import threading

import pytest

from runtime_v2 import RuntimeProjector, SessionEventLog, SnapshotStore


def seeded(root):
    log,store,projector=SessionEventLog(root),SnapshotStore(root),RuntimeProjector()
    log.append('s','message_user',{'content':'original'})
    snapshot=projector.project(log.read_all('s'))
    store.stamp_event_log('s',snapshot,log.event_path('s'))
    store.write('s',snapshot)
    return log,store,projector


def test_consistent_reader_and_generator_finish_while_checkpoint_fsync_is_blocked(tmp_path,monkeypatch):
    monkeypatch.setenv('RUNTIME_V2_ASYNC_SNAPSHOT_CHECKPOINTS','true')
    monkeypatch.setenv('RUNTIME_V2_SNAPSHOT_CHECKPOINT_EVENTS','1')
    log,store,projector=seeded(tmp_path)
    event=log.append('s','execution_recorded',{'execution_id':'draft','text_delta':'received'})
    entered,release=threading.Event(),threading.Event()
    original=store._write_file

    def blocked(path,snapshot):
        entered.set()
        assert release.wait(5)
        return original(path,snapshot)

    monkeypatch.setattr(store,'_write_file',blocked)
    with ThreadPoolExecutor(max_workers=2) as executor:
        future=executor.submit(store.read_consistent_view,'s',log,projector)
        try:
            assert entered.wait(2)
            view=future.result(timeout=2)
            assert view['last_seq']==event.seq
            assert view['executions']['draft']['content']=='received'
            following=executor.submit(log.append,'s','context_tokens',{'estimated':42}).result(timeout=2)
            # The view acknowledges its own boundary, not a later concurrent fact.
            assert view['last_seq']==following.seq-1
        finally:
            release.set()
            assert store.wait_for_checkpoint('s',timeout_seconds=5)
    assert log.read_all('s')[-1].seq==following.seq


def test_consistent_reader_uses_verified_suffix_without_sparse_index(tmp_path,monkeypatch):
    log,store,projector=seeded(tmp_path)
    for _ in range(70):
        log.append('s','execution_recorded',{'execution_id':'draft','text_delta':'字'})
    end=log.append('s','message_assistant_final',{'content':'done'})
    monkeypatch.setattr(log,'read_after_seq',lambda *a,**k:pytest.fail('reopened sparse index'))
    monkeypatch.setattr(log,'read_all',lambda *a,**k:pytest.fail('replayed old history'))
    result=store.read_consistent_view('s',log,projector)
    assert result['last_seq']==end.seq
    assert result['executions']['draft']['content']=='字'*70
    assert result['messages'][-1]['payload']['content']=='done'


@pytest.mark.parametrize('generation',['replacement','truncation'])
def test_changed_source_generation_rebuilds_instead_of_mixing_old_messages(tmp_path,generation):
    log,store,projector=seeded(tmp_path)
    path=log.event_path('s')
    event=log.read_all('s')[0].to_dict()
    event['payload']['content']='new source'
    data=json.dumps(event,ensure_ascii=False)+'\n'
    if generation=='replacement':
        replacement=path.with_name('replacement')
        replacement.write_text(data,encoding='utf-8')
        os.replace(replacement,path)
    else:
        path.write_text(data,encoding='utf-8')
    result=store.read_consistent_view('s',log,projector)
    assert result['messages'][0]['payload']['content']=='new source'
    assert result['last_seq']==1


def test_checkpoint_failure_keeps_latest_view_and_recovery_from_facts(tmp_path,monkeypatch):
    monkeypatch.setenv('RUNTIME_V2_ASYNC_SNAPSHOT_CHECKPOINTS','true')
    monkeypatch.setenv('RUNTIME_V2_SNAPSHOT_CHECKPOINT_EVENTS','1')
    log,store,projector=seeded(tmp_path)
    end=log.append('s','execution_recorded',{'execution_id':'draft','text_delta':'durable'})
    original=store._write_file
    def failed(*args):raise OSError('isolated checkpoint failure')
    monkeypatch.setattr(store,'_write_file',failed)
    view=store.read_consistent_view('s',log,projector)
    assert view['last_seq']==end.seq
    assert store.wait_for_checkpoint('s',timeout_seconds=5)
    assert store.read_consistent_view('s',log,projector)['executions']['draft']['content']=='durable'
    with store._memory_cache_lock:
        store._memory_cache.pop(store._cache_key(store.path('s')),None)
    monkeypatch.setattr(store,'_write_file',original)
    recovered=store.read_consistent_view('s',log,projector)
    assert recovered['last_seq']==end.seq
    assert recovered['executions']['draft']['content']=='durable'
    assert store.wait_for_checkpoint('s',timeout_seconds=5)


def test_explicit_synchronous_checkpoint_mode_remains_available(tmp_path,monkeypatch):
    monkeypatch.setenv('RUNTIME_V2_ASYNC_SNAPSHOT_CHECKPOINTS','false')
    monkeypatch.setenv('RUNTIME_V2_SNAPSHOT_CHECKPOINT_EVENTS','1')
    log,store,projector=seeded(tmp_path)
    end=log.append('s','context_tokens',{'estimated':42})
    result=store.read_consistent_view('s',log,projector)
    disk=json.loads(store.path('s').read_text(encoding='utf-8'))
    assert result['last_seq']==disk['last_seq']==end.seq
