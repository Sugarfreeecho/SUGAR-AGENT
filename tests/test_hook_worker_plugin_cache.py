import asyncio
import threading
import time
from types import SimpleNamespace

import pytest


def catalog(monkeypatch, tmp_path):
    import agent_extensions as ext

    stale = SimpleNamespace(plugins=(), hook_sources=(), version='stale')
    fresh = SimpleNamespace(plugins=(), hook_sources=(), version='fresh')
    manager = SimpleNamespace(discovery_dirs=(tmp_path,), state=SimpleNamespace(path=tmp_path/'state.json'))
    key = (id(manager), True, (str(tmp_path),), str(manager.state.path))
    monkeypatch.setattr(ext, 'plugin_manager', lambda: manager)
    monkeypatch.setattr(ext, 'plugins_enabled', lambda: True)
    monkeypatch.setattr(ext, '_extension_catalog_generation', 73)
    monkeypatch.setattr(ext, '_plugin_cache', (time.monotonic()-ext._CACHE_TTL_SECONDS-1, key, stale))
    monkeypatch.setattr(ext, '_swr_refresh_in_flight', False)
    monkeypatch.setattr(ext, '_SWR_REFRESH_TASKS', set())
    monkeypatch.setattr(ext, '_runtime_hook_definitions', lambda loaded: ())
    monkeypatch.setattr(ext, '_hook_manager_for_loop', lambda loop, **kwargs: kwargs['loaded'])
    return ext, manager, stale, fresh, key


async def entered(event):
    async def poll():
        while not event.is_set():
            await asyncio.sleep(.001)
    await asyncio.wait_for(poll(), 5)


def test_expired_hook_worker_catalog_returns_stale_while_one_scan_is_blocked(monkeypatch, tmp_path):
    ext, manager, stale, fresh, key = catalog(monkeypatch, tmp_path)
    scanning, release = threading.Event(), threading.Event()
    scans = []

    def load():
        scans.append(threading.get_ident())
        scanning.set()
        assert release.wait(5)
        return fresh
    manager.load_enabled = load

    async def run():
        loop = asyncio.get_running_loop()
        submit = loop.run_in_executor
        def checked_submit(*args, **kwargs):
            assert asyncio.get_running_loop() is loop
            return submit(*args, **kwargs)
        monkeypatch.setattr(loop, 'run_in_executor', checked_submit)
        try:
            rows = await asyncio.wait_for(asyncio.gather(
                *(ext._prepare_hook_dispatch_async() for _ in range(6))), 3)
            assert all(row[0] is stale for row in rows)
            await entered(scanning)
            assert len(scans) == 1
            assert ext._plugin_cache[2] is stale
        finally:
            release.set()
            if ext._SWR_REFRESH_TASKS:
                await asyncio.gather(*tuple(ext._SWR_REFRESH_TASKS))
        assert ext._plugin_cache[1:] == (key, fresh)
        assert ext._swr_refresh_in_flight is False
        assert (await ext._prepare_hook_dispatch_async())[0] is fresh
    asyncio.run(run())


def test_force_reload_waits_for_new_catalog_even_with_owner_loop(monkeypatch, tmp_path):
    ext, manager, stale, fresh, _ = catalog(monkeypatch, tmp_path)
    scanning, release = threading.Event(), threading.Event()
    def load():
        scanning.set()
        assert release.wait(5)
        return fresh
    manager.load_enabled = load

    async def run():
        loop = asyncio.get_running_loop()
        task = asyncio.create_task(asyncio.to_thread(ext.load_plugins, force=True, refresh_loop=loop))
        try:
            await entered(scanning)
            assert not task.done()
        finally:
            release.set()
        assert await task is fresh
        assert not ext._SWR_REFRESH_TASKS
    asyncio.run(run())


def test_invalidation_discards_refresh_queued_from_worker(monkeypatch, tmp_path):
    ext, manager, _, _, key = catalog(monkeypatch, tmp_path)
    callbacks = []
    loop = SimpleNamespace(is_closed=lambda: False, call_soon_threadsafe=lambda cb: callbacks.append(cb))
    manager.load_enabled = lambda: pytest.fail('invalidated refresh must not scan')
    with ext._lock:
        assert ext._schedule_plugin_cache_refresh(manager, key, loop=loop)
        ext._extension_catalog_generation += 1
    assert len(callbacks) == 1
    callbacks[0]()
    assert ext._swr_refresh_in_flight is False
    assert not ext._SWR_REFRESH_TASKS


@pytest.mark.parametrize('replacement', ['fresh', 'different_key'])
def test_queued_refresh_skips_catalog_already_replaced(monkeypatch, tmp_path, replacement):
    ext, manager, _, fresh, key = catalog(monkeypatch, tmp_path)
    callbacks = []
    loop = SimpleNamespace(is_closed=lambda: False, call_soon_threadsafe=lambda cb: callbacks.append(cb))
    manager.load_enabled = lambda: pytest.fail('superseded refresh must not scan')
    with ext._lock:
        assert ext._schedule_plugin_cache_refresh(manager, key, loop=loop)
        if replacement == 'fresh':
            ext._plugin_cache = (time.monotonic(), key, fresh)
        else:
            ext._plugin_cache = (time.monotonic()-ext._CACHE_TTL_SECONDS-1, ('new',), fresh)
    callbacks[0]()
    assert len(callbacks) == 1, 'obsolete callback must not enqueue another refresh'
    assert ext._swr_refresh_in_flight is False
    assert not ext._SWR_REFRESH_TASKS


@pytest.mark.parametrize('closed_owner', [False, True])
def test_sync_or_closed_loop_preserves_inline_refresh(monkeypatch, tmp_path, closed_owner):
    ext, manager, stale, fresh, _ = catalog(monkeypatch, tmp_path)
    scans = []
    def load():
        scans.append(True)
        return fresh
    manager.load_enabled = load
    loop = asyncio.new_event_loop() if closed_owner else None
    if loop is not None:
        loop.close()
    assert ext.load_plugins(refresh_loop=loop) is fresh
    assert scans == [True] and not ext._SWR_REFRESH_TASKS


def test_executor_submission_failure_does_not_leave_refresh_inflight(monkeypatch, tmp_path):
    ext, manager, _, _, key = catalog(monkeypatch, tmp_path)
    async def run():
        loop = asyncio.get_running_loop()
        def fail(*args):
            raise RuntimeError('executor unavailable')
        monkeypatch.setattr(loop, 'run_in_executor', fail)
        before = ext._swr_active_count
        with ext._lock, pytest.raises(RuntimeError, match='executor unavailable'):
            ext._schedule_plugin_cache_refresh(manager, key)
        assert ext._swr_refresh_in_flight is False
        assert ext._swr_active_count == before
    asyncio.run(run())
