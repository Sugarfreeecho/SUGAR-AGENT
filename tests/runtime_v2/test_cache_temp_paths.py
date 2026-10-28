"""Valid public cache paths must not fail because an atomic temp is longer."""
import errno
import os
from pathlib import Path

import pytest

from runtime_v2.event_log import SessionEventLog
from runtime_v2.execution_journal import ExecutionJournal
from runtime_v2.recovery_checkpoint import RecoveryCheckpoint


def bounded_open(monkeypatch, root, limit):
    original=Path.open
    def open_path(path,*args,**kwargs):
        if path.is_relative_to(root) and len(str(path))>limit:
            raise FileNotFoundError(errno.ENOENT,'simulated legacy path limit',str(path))
        return original(path,*args,**kwargs)
    monkeypatch.setattr(Path,'open',open_path)


@pytest.fixture(params=['portable_limit','native_windows'])
def cache_root(request,tmp_path):
    if request.param=='portable_limit':
        return tmp_path,True
    if os.name!='nt':
        pytest.skip('native Win32 path-boundary coverage')
    # Public index/checkpoint paths remain below MAX_PATH; former long UUID
    # temporary names exceed it. Keep directory components below their limit.
    padding=220-len(str(tmp_path))-len('/s/snapshots')-1
    if padding<1 or padding>240:
        pytest.skip('pytest root leaves no room for the fixed Win32 fixture')
    root=tmp_path/('n'*padding)
    root.mkdir()
    assert len(str(root/'s/snapshots'))==220
    return root,False


def test_sparse_index_can_publish_and_reuse_at_valid_path_boundary(cache_root,monkeypatch):
    root,simulate=cache_root
    log=SessionEventLog(root)
    log.append_batch('s',[{'type':'message_user','payload':{'text':str(i)}} for i in range(70)])
    target=log.seq_offset_index_path('s')
    if simulate:
        bounded_open(monkeypatch,root,len(str(target)))
    assert [event.seq for event in log.read_after_seq('s',65)]==list(range(66,71))
    assert target.is_file()
    # Repeated reads must use the published derivative, rather than rebuild
    # full fact history after every failed temporary-file creation.
    monkeypatch.setattr(log,'_build_seq_offset_index',lambda *_:pytest.fail('rebuilt a valid sparse index'))
    assert [event.seq for event in log.read_latest('s',2)]==[69,70]
    log.append_batch('s',[{'type':'message_user','payload':{'text':'tail'}} for _ in range(30)])
    assert [event.seq for event in log.read_after_seq('s',95)]==[96,97,98,99,100]
    assert not [p for p in target.parent.iterdir() if p.name.startswith('.')]


def test_recovery_checkpoint_publishes_and_cold_recovers_at_valid_path_boundary(cache_root,monkeypatch):
    root,simulate=cache_root
    journal=ExecutionJournal(root)
    journal.record('s',{'type':'llm_reasoning_delta','run_id':'run','stream_seq':1,
                        'react_iter':1,'delta':'retained result','delta_seq':1})
    assert RecoveryCheckpoint.wait(journal,'s',5)
    with journal._session_lock('s'):
        state=journal._state('s')
    target=RecoveryCheckpoint.path(journal,'s')
    target.unlink(missing_ok=True)
    if simulate:
        bounded_open(monkeypatch,root,len(str(target)))
    RecoveryCheckpoint._write(journal,'s',state)
    checkpoint=RecoveryCheckpoint.load(journal,'s')
    assert checkpoint is not None and checkpoint['seq']==state['seq']
    with ExecutionJournal._guard:
        ExecutionJournal._cache.pop(str(journal.log.event_path('s').resolve()),None)
    diagnostics={}
    recovered=journal.read('s',diagnostics=diagnostics)
    assert diagnostics['source']=='checkpoint'
    assert recovered['execution_records'][0]['content']=='retained result'
    assert not [p for p in target.parent.iterdir() if p.name.startswith('.')]
