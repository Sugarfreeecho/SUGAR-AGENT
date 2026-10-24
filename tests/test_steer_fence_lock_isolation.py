from concurrent.futures import ThreadPoolExecutor
import json
import threading
from types import SimpleNamespace

import pytest


def configure(monkeypatch, tmp_path):
    import agent_loop as agent
    import run_ownership
    monkeypatch.setattr(agent, 'session_manager', SimpleNamespace(sessions_dir=tmp_path))
    monkeypatch.setattr(agent, '_ACTIVE_STEER_RUNS', {})
    monkeypatch.setattr(agent, '_STEER_FENCE_REGISTRATION_LOCKS', {})
    return agent, run_ownership


def test_other_session_can_check_and_abort_while_registration_io_is_blocked(monkeypatch, tmp_path):
    agent, ownership = configure(monkeypatch, tmp_path)
    live = agent._register_steer_run_control('live', 'old')
    state = {'session_id': 'live', '_steer_control': live}
    entered, release = threading.Event(), threading.Event()
    inspect = ownership.inspect_run_fence
    def slow(path):
        if path.parent.name == 'slow':
            entered.set()
            assert release.wait(5)
        return inspect(path)
    monkeypatch.setattr(ownership, 'inspect_run_fence', slow)
    with ThreadPoolExecutor(3) as pool:
        registering = pool.submit(agent._register_steer_run_control, 'slow', 'new')
        try:
            assert entered.wait(3)
            assert 'slow' not in agent._ACTIVE_STEER_RUNS
            assert pool.submit(agent._state_run_has_write_fence, state).result(2) is True
            assert pool.submit(agent.abort_session_steer_run, 'live').result(2) is True
            assert live.is_aborted()
        finally:
            release.set()
        assert registering.result(3).run_id == 'new'


def test_same_session_registrations_publish_in_disk_transaction_order(monkeypatch, tmp_path):
    agent, ownership = configure(monkeypatch, tmp_path)
    entered, release, second_attempt = threading.Event(), threading.Event(), threading.Event()
    counts = []
    inspect = ownership.inspect_run_fence
    class ObservedLock:
        def __init__(self):
            self.lock = threading.Lock()
        def __enter__(self):
            if entered.is_set():
                second_attempt.set()
            self.lock.acquire()
        def __exit__(self, *args):
            self.lock.release()
    agent._STEER_FENCE_REGISTRATION_LOCKS['s'] = ObservedLock()
    def slow(path):
        counts.append(True)
        if len(counts) == 1:
            entered.set()
            assert release.wait(5)
        return inspect(path)
    monkeypatch.setattr(ownership, 'inspect_run_fence', slow)
    with ThreadPoolExecutor(2) as pool:
        first = pool.submit(agent._register_steer_run_control, 's', 'first')
        try:
            assert entered.wait(3)
            second = pool.submit(agent._register_steer_run_control, 's', 'second')
            assert second_attempt.wait(3)
            assert len(counts) == 1 and not second.done()
        finally:
            release.set()
        old, current = first.result(3), second.result(3)
    data = json.loads((tmp_path/'s/active_run_fence.json').read_text(encoding='utf8'))
    assert data['token'] == current.fence_token
    assert agent._ACTIVE_STEER_RUNS['s'] is current
    assert not agent._state_run_has_write_fence({'session_id': 's', '_steer_control': old})
    assert agent._state_run_has_write_fence({'session_id': 's', '_steer_control': current})
    agent._clear_steer_run_control('s', old)
    assert (tmp_path/'s/active_run_fence.json').exists()


def test_failed_fence_replace_never_publishes_candidate(monkeypatch, tmp_path):
    from pathlib import Path
    agent, _ = configure(monkeypatch, tmp_path)
    old = agent._register_steer_run_control('s', 'old')
    replace = Path.replace
    def fail(self, target):
        if self.name == 'active_run_fence.json.tmp':
            raise OSError('replacement failed')
        return replace(self, target)
    monkeypatch.setattr(Path, 'replace', fail)
    with pytest.raises(OSError, match='replacement failed'):
        agent._register_steer_run_control('s', 'candidate')
    assert agent._ACTIVE_STEER_RUNS['s'] is old
    assert agent._state_run_has_write_fence({'session_id': 's', '_steer_control': old})


def test_clear_old_owner_during_registration_cannot_delete_new_fence(monkeypatch, tmp_path):
    agent, ownership = configure(monkeypatch, tmp_path)
    old = agent._register_steer_run_control('s', 'old')
    entered, release = threading.Event(), threading.Event()
    inspect = ownership.inspect_run_fence
    def slow(path):
        entered.set()
        assert release.wait(5)
        return inspect(path)
    monkeypatch.setattr(ownership, 'inspect_run_fence', slow)
    with ThreadPoolExecutor(2) as pool:
        registering = pool.submit(agent._register_steer_run_control, 's', 'new')
        try:
            assert entered.wait(3)
            clearing = pool.submit(agent._clear_steer_run_control, 's', old)
        finally:
            release.set()
        current = registering.result(3)
        clearing.result(3)
    assert agent._ACTIVE_STEER_RUNS['s'] is current
    data = json.loads((tmp_path/'s/active_run_fence.json').read_text(encoding='utf8'))
    assert data['token'] == current.fence_token
