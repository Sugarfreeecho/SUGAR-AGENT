from pathlib import Path
import sys
from unittest.mock import Mock
import os
import pytest

APP = Path(__file__).resolve().parents[1] / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))


def test_fact_transaction_reuses_resolution_and_next_transaction_revalidates(tmp_path, monkeypatch):
    from agent_harness import SessionManager
    from runtime_v2 import RuntimeHistoryOps
    manager = SessionManager(tmp_path / "sessions", tmp_path / "sessions/index.json")
    sid, *_ = manager.get_or_create_session()
    ops = RuntimeHistoryOps(manager.sessions_dir, path_resolver=manager._resolve_session_path)
    uncached = Mock(wraps=manager._resolve_session_path_uncached)
    monkeypatch.setattr(manager, "_resolve_session_path_uncached", uncached)
    with ops.event_log.session_transaction(sid):
        first = manager._resolve_session_path(sid)
        before = uncached.call_count
        for _ in range(10):
            assert manager._resolve_session_path(sid) == first
            ops.snapshots.path(sid)
        assert uncached.call_count == before
    assert manager._session_path_scope.get() is None
    before = uncached.call_count
    with ops.event_log.session_transaction(sid):
        assert manager._resolve_session_path(sid) == first
    assert uncached.call_count > before


def test_subagent_index_change_invalidates_paths_inside_scope(tmp_path):
    from agent_harness import SessionManager
    manager = SessionManager(tmp_path / "sessions", tmp_path / "sessions/index.json")
    parent, *_ = manager.get_or_create_session()
    child, *_ = manager.get_or_create_session()
    with manager._session_path_resolution_scope():
        flat = manager._resolve_session_path(child)
        manager._save_subagent_index({child: parent})
        nested = manager._resolve_session_path(child)
        assert nested != flat
        assert nested.parent.name == "subagents"
        assert nested.parent.parent.name == parent


def test_closed_scope_cannot_be_reused_by_copied_context(tmp_path):
    import contextvars
    from agent_harness import SessionManager
    manager = SessionManager(tmp_path / "sessions", tmp_path / "sessions/index.json")
    sid, *_ = manager.get_or_create_session()
    with manager._session_path_resolution_scope():
        manager._resolve_session_path(sid)
        copied = contextvars.copy_context()
    scope = copied.run(manager._session_path_scope.get)
    assert not scope["active"]
    assert scope["paths"] == {}


def test_replaced_directory_is_revalidated_inside_active_scope(tmp_path):
    from agent_harness import SessionManager
    manager = SessionManager(tmp_path / "sessions", tmp_path / "sessions/index.json")
    sid, *_ = manager.get_or_create_session()
    outside = tmp_path / "outside"
    outside.mkdir()
    with manager._session_path_resolution_scope():
        original = manager._resolve_session_path(sid)
        backup = tmp_path / "saved-session"
        assert original.resolve().is_relative_to(tmp_path.resolve())
        assert backup.resolve().is_relative_to(tmp_path.resolve())
        original.rename(backup)
        try:
            os.symlink(outside, original, target_is_directory=True)
        except OSError:
            pytest.skip("Directory symlinks unavailable")
        with pytest.raises(ValueError, match="Invalid session_id"):
            manager._resolve_session_path(sid)


def test_real_directory_replacement_invalidates_guard_without_symlink_privileges(tmp_path, monkeypatch):
    from agent_harness import SessionManager
    manager = SessionManager(tmp_path / "sessions", tmp_path / "sessions/index.json")
    sid, *_ = manager.get_or_create_session()
    uncached = Mock(wraps=manager._resolve_session_path_uncached)
    monkeypatch.setattr(manager, "_resolve_session_path_uncached", uncached)
    with manager._session_path_resolution_scope():
        original = manager._resolve_session_path(sid)
        count = uncached.call_count
        backup = tmp_path / "saved-session"
        assert original.resolve().is_relative_to(tmp_path.resolve())
        assert backup.resolve().is_relative_to(tmp_path.resolve())
        original.rename(backup)
        original.mkdir()
        assert manager._resolve_session_path(sid) == original
        assert uncached.call_count == count + 1
        with pytest.raises(ValueError, match="Cyclic"):
            manager._resolve_session_path(sid, _seen={sid})


def test_noncanonical_configured_root_does_not_cache_resolution(tmp_path, monkeypatch):
    from agent_harness import SessionManager
    manager = SessionManager(tmp_path / "sessions", tmp_path / "sessions/index.json")
    sid, *_ = manager.get_or_create_session()
    manager.sessions_dir = manager.sessions_dir / ".." / "sessions"
    uncached = Mock(wraps=manager._resolve_session_path_uncached)
    monkeypatch.setattr(manager, "_resolve_session_path_uncached", uncached)
    with manager._session_path_resolution_scope():
        first = manager._resolve_session_path(sid)
        count = uncached.call_count
        assert manager._resolve_session_path(sid) == first
        assert uncached.call_count == count + 1


def test_other_manager_index_update_invalidates_active_scope(tmp_path):
    from agent_harness import SessionManager
    root = tmp_path / "sessions"
    manager = SessionManager(root, root / "index.json")
    other = SessionManager(root, root / "index.json")
    parent, *_ = manager.get_or_create_session()
    child, *_ = manager.get_or_create_session()
    with manager._session_path_resolution_scope():
        flat = manager._resolve_session_path(child)
        other._save_subagent_index({child: parent})
        nested = manager._resolve_session_path(child)
        assert nested != flat
        assert nested.parent.parent.name == parent


def test_react_operation_reuses_guarded_paths_and_closes_scope(tmp_path, monkeypatch):
    import asyncio
    import agent_loop
    from agent_harness import SessionManager
    manager = SessionManager(tmp_path / "sessions", tmp_path / "sessions/index.json")
    sid, *_ = manager.get_or_create_session()
    monkeypatch.setattr(agent_loop, "session_manager", manager)
    uncached = Mock(wraps=manager._resolve_session_path_uncached)
    monkeypatch.setattr(manager, "_resolve_session_path_uncached", uncached)

    async def operation(state, emit=None):
        first = manager._resolve_session_path(sid)
        count = uncached.call_count
        await asyncio.sleep(0)
        assert manager._resolve_session_path(sid) == first
        assert uncached.call_count == count
        return state

    monkeypatch.setattr(agent_loop, "_react_node_once", operation)
    state = {"session_id": sid}
    assert asyncio.run(agent_loop.react_node(state)) is state
    assert manager._session_path_scope.get() is None
