"""Plugin-context preparation must preserve stale catalog refresh off loop."""
import asyncio
import threading
import time
from types import SimpleNamespace

import pytest

import agent_extensions as ext
import plugin_context


def catalog(monkeypatch, tmp_path, *, cold=False):
    loaded = SimpleNamespace(plugins=())
    manager = SimpleNamespace(discovery_dirs=(tmp_path,), state=SimpleNamespace(path=tmp_path/'state.json'))
    key = (id(manager), True, (str(tmp_path),), str(manager.state.path))
    monkeypatch.setattr(ext, 'plugin_manager', lambda: manager)
    monkeypatch.setattr(ext, 'plugins_enabled', lambda: True)
    monkeypatch.setattr(ext, '_extension_catalog_generation', 51)
    monkeypatch.setattr(ext, '_plugin_cache', None if cold else
                        (time.monotonic()-ext._CACHE_TTL_SECONDS-1, key, loaded))
    monkeypatch.setattr(ext, '_swr_refresh_in_flight', False)
    monkeypatch.setattr(ext, '_SWR_REFRESH_TASKS', set())
    return manager, loaded


async def prepare():
    # The once-per-run persisted clear check has already completed. No provider
    # is active; avoid coupling the queue regression to unrelated session IO.
    return await plugin_context.prepare_for_step(
        {'session_id':'child', '_plugin_context_checked_empty':True}, SimpleNamespace(), [],
        step=2, workspace_root='workspace', context_window=128000)


async def entered(event):
    while not event.is_set():
        await asyncio.sleep(.001)


def test_stale_context_catalog_returns_while_background_scan_is_blocked(monkeypatch, tmp_path):
    manager, loaded = catalog(monkeypatch, tmp_path)
    scanning, release = threading.Event(), threading.Event()
    scans = []
    def load():
        scans.append(threading.get_ident())
        scanning.set()
        assert release.wait(3)
        return loaded
    manager.load_enabled = load
    async def scenario():
        try:
            values = await asyncio.wait_for(asyncio.gather(*(prepare() for _ in range(4))), .5)
            assert values == [None]*4 and not release.is_set()
            await asyncio.wait_for(entered(scanning), 1)
            assert len(scans)==1
        finally:
            release.set()
            if ext._SWR_REFRESH_TASKS:
                await asyncio.gather(*tuple(ext._SWR_REFRESH_TASKS))
    asyncio.run(scenario())


def test_cold_context_catalog_still_waits_for_authoritative_load(monkeypatch, tmp_path):
    manager, loaded = catalog(monkeypatch, tmp_path, cold=True)
    scanning, release = threading.Event(), threading.Event()
    def load():
        scanning.set()
        assert release.wait(3)
        return loaded
    manager.load_enabled = load
    async def scenario():
        task = asyncio.create_task(prepare())
        try:
            await asyncio.wait_for(entered(scanning), 1)
            await asyncio.sleep(0)
            assert not task.done()
        finally:
            release.set()
        assert await task is None
    asyncio.run(scenario())


def test_context_revalidation_passes_owner_loop_and_drops_disabled_provider(monkeypatch, tmp_path):
    from runtime_v2.snapshot_store import SnapshotStore
    import plugins.runtime
    provider = SimpleNamespace(plugin_id='test', content_signature='one', raw_manifest={'capabilities':{'context':True}})
    calls = []
    def load(*, refresh_loop=None):
        calls.append(refresh_loop)
        return SimpleNamespace(plugins=(provider,) if len(calls)==1 else ())
    monkeypatch.setattr(ext, 'load_plugins', load)
    monkeypatch.setattr(SnapshotStore, 'read_consistent_view', lambda *a,**kw: {})
    monkeypatch.setattr(plugins.runtime, 'get_plugin_runtime_registry', lambda: object())
    async def collect(*args):
        return [dict(plugin_id='test',plugin_signature='one',id='current',title='Title',max_tokens=100,order=1)], \
               {('test','current'):{'value':{'text':'late data'}}}, {}
    monkeypatch.setattr(plugin_context, 'collect', collect)
    async def scenario():
        assert await plugin_context.prepare_for_step(
            {'session_id':'s'}, SimpleNamespace(sessions_dir=tmp_path), [], step=1,
            workspace_root=str(tmp_path), context_window=128000) is None
        assert calls == [asyncio.get_running_loop()]*2
    asyncio.run(scenario())
