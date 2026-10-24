import asyncio

import pytest

import session_authorized_dirs as directories


def test_once_authorization_expires_without_persisting(monkeypatch, tmp_path):
    workspace, external = tmp_path / "workspace", tmp_path / "external"
    monkeypatch.setattr(directories, "_get_persisted_authorized_dirs", lambda *_: [workspace])
    with directories.tool_directory_authorization_scope("session"):
        directories.authorize_dir_for_current_tool("session", str(external))
        assert directories.get_authorized_dirs_for_session("session", workspace) == [workspace, external]
        assert directories.get_authorized_dirs_for_session("other", workspace) == [workspace]
    assert directories.get_authorized_dirs_for_session("session", workspace) == [workspace]


def test_once_authorization_does_not_leak_between_parallel_tools(monkeypatch, tmp_path):
    monkeypatch.setattr(directories, "_get_persisted_authorized_dirs", lambda *_: [tmp_path])
    async def scenario():
        ready, done = asyncio.Event(), asyncio.Event()
        async def approved_tool():
            with directories.tool_directory_authorization_scope("session"):
                directories.authorize_dir_for_current_tool("session", str(tmp_path / "external"))
                ready.set()
                await done.wait()
                assert tmp_path / "external" in directories.get_authorized_dirs_for_session("session", tmp_path)
        async def other_tool():
            await ready.wait()
            with directories.tool_directory_authorization_scope("session"):
                assert directories.get_authorized_dirs_for_session("session", tmp_path) == [tmp_path]
            done.set()
        await asyncio.gather(approved_tool(), other_tool())
    asyncio.run(scenario())


def test_once_authorization_resets_on_exception(monkeypatch, tmp_path):
    monkeypatch.setattr(directories, "_get_persisted_authorized_dirs", lambda *_: [tmp_path])
    with pytest.raises(ValueError):
        with directories.tool_directory_authorization_scope("session"):
            directories.authorize_dir_for_current_tool("session", str(tmp_path / "external"))
            raise ValueError("cancelled")
    assert directories.get_authorized_dirs_for_session("session", tmp_path) == [tmp_path]
    with pytest.raises(RuntimeError):
        directories.authorize_dir_for_current_tool("session", str(tmp_path / "external"))


def test_child_task_cannot_keep_authorization_after_tool_returns(monkeypatch, tmp_path):
    monkeypatch.setattr(directories, "_get_persisted_authorized_dirs", lambda *_: [tmp_path])
    async def scenario():
        proceed = asyncio.Event()
        async def copied_context():
            await proceed.wait()
            return directories.get_authorized_dirs_for_session("session", tmp_path)
        with directories.tool_directory_authorization_scope("session"):
            directories.authorize_dir_for_current_tool("session", str(tmp_path / "external"))
            task = asyncio.create_task(copied_context())
        proceed.set()
        assert await task == [tmp_path]
    asyncio.run(scenario())
