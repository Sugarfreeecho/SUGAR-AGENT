"""Completed chats must not retain full model snapshots during recovery scans."""
from types import SimpleNamespace

from tests.test_refresh_loading_paths import real_function


def test_completed_visible_turn_skips_full_snapshot_and_recovery(monkeypatch):
    from workflow_extensions import session_workflows
    monkeypatch.setattr(session_workflows, 'continuation_source', lambda _: '')
    checked = []

    def forbidden(*_args, **_kwargs):
        raise AssertionError('a completed turn does not need a full runtime snapshot')

    namespace = {
        'session_manager': SimpleNamespace(can_continue_react_session=lambda sid: checked.append(sid) or False),
        '_has_local_worker_activity': lambda _: False,
        '_active_chat_by_session': {},
        '_react_run_fence_owner': lambda _: SimpleNamespace(status='absent'),
        '_runtime_v2_snapshot': forbidden,
        '_cleanup_orphan_runtime_v2_active_runs': forbidden,
        '_runtime_v2_auto_resume_pending': forbidden,
    }
    read = real_function('app/webui.py', '_is_recoverable_react_session', namespace)
    assert read('completed') is False
    assert checked == ['completed']


def test_live_or_unknown_owner_is_rejected_before_history_read(monkeypatch):
    from workflow_extensions import session_workflows
    monkeypatch.setattr(session_workflows, 'continuation_source', lambda _: '')
    for status in ('live', 'unknown'):
        namespace = {
            'session_manager': SimpleNamespace(can_continue_react_session=lambda _: (_ for _ in ()).throw(AssertionError('history read'))),
            '_has_local_worker_activity': lambda _: False,
            '_active_chat_by_session': {},
            '_react_run_fence_owner': lambda _: SimpleNamespace(status=status),
        }
        assert real_function('app/webui.py', '_is_recoverable_react_session', namespace)('foreign') is False
