"""A failed diagnostic flush remains pending and never rolls live state back."""
import errno
import json
import threading

import pytest


def test_sharing_failure_is_retried_with_latest_cached_usage(tmp_path,monkeypatch):
    import runtime_observability as obs
    obs.configure(tmp_path)
    obs.start_run('s','r')
    original = obs._write
    failed, succeeded = threading.Event(), threading.Event()
    exceptions = []
    monkeypatch.setattr(threading,'excepthook',exceptions.append)
    def write(sid,data):
        if not failed.is_set():
            failed.set()
            error = PermissionError('reader holds destination')
            error.winerror = 32
            raise error
        original(sid,data)
        succeeded.set()
    with monkeypatch.context() as patcher:
        patcher.setattr(obs,'_write',write)
        obs.record_usage('s','r',{'tokens':1})
        assert failed.wait(3)
        obs.record_usage('s','r',{'tokens':2})
        assert succeeded.wait(3)
        obs.flush('s')
    assert not exceptions
    assert json.loads(obs._path('s').read_text(encoding='utf8'))['runs'][0]['usage']['tokens']==3
    assert 's' not in obs._flush_failures


def test_thread_start_and_write_failure_remain_pending_for_scan_and_global_flush(tmp_path,monkeypatch):
    import runtime_observability as obs
    obs.configure(tmp_path)
    obs.start_run('s','r')
    def no_thread(*args):
        raise RuntimeError('no thread slots')
    def no_write(*args):
        raise OSError(errno.ENOSPC,'storage full')
    with monkeypatch.context() as patcher:
        patcher.setattr(threading.Timer,'start',no_thread)
        patcher.setattr(obs,'_write',no_write)
        obs.record_usage('s','r',{'tokens':7})
        assert 's' in obs._flush_failures and 's' not in obs._flush_timers
        assert obs.scan_stale_runs(90,live_checker=lambda *_:True)==[]
        assert obs._cache['s']['runs'][0]['usage']['tokens']==7
        with pytest.raises(OSError):
            obs.flush('s')
    obs.flush()
    assert not obs._flush_failures
    assert json.loads(obs._path('s').read_text(encoding='utf8'))['runs'][0]['usage']['tokens']==7


def test_permanent_background_failure_is_retained_without_retry_spin(tmp_path,monkeypatch):
    import runtime_observability as obs
    obs.configure(tmp_path)
    obs.start_run('s','r')
    failed = threading.Event()
    exceptions = []
    monkeypatch.setattr(threading,'excepthook',exceptions.append)
    def no_write(*args):
        failed.set()
        raise OSError(errno.ENOSPC,'storage full')
    with monkeypatch.context() as patcher:
        patcher.setattr(obs,'_write',no_write)
        obs.record_usage('s','r',{'tokens':5})
        assert failed.wait(3)
        with obs._lock:
            assert 's' in obs._flush_failures and 's' not in obs._flush_timers
        with pytest.raises(OSError):
            obs.flush()
    obs.flush()
    assert not exceptions and not obs._flush_failures


def test_cancelled_callback_cannot_take_new_configuration_timer(tmp_path,monkeypatch):
    import runtime_observability as obs
    monkeypatch.setattr(obs,'_FLUSH_DELAY_SEC',10)
    obs.configure(tmp_path/'old')
    obs.start_run('s','old')
    obs.record_usage('s','old',{'tokens':1})
    old_timer=obs._flush_timers['s']
    obs.configure(tmp_path/'new')
    obs.start_run('s','new')
    obs.record_usage('s','new',{'tokens':2})
    new_timer=obs._flush_timers['s']
    with monkeypatch.context() as patcher:
        patcher.setattr(threading,'current_thread',lambda:old_timer)
        obs._flush_timer_fired('s')
    assert obs._flush_timers['s'] is new_timer
    obs.flush()
    assert json.loads(obs._path('s').read_text(encoding='utf8'))['runs'][0]['run_id']=='new'
