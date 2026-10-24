import asyncio
import threading
import time
from types import SimpleNamespace
import weakref

import pytest


def configure(monkeypatch, tmp_path):
    import agent_extensions as ext
    monkeypatch.setenv('HOOKS_ENABLED', '0')
    monkeypatch.setenv('PLUGINS_ENABLED', '0')
    monkeypatch.setenv('HOOKS_PATH', str(tmp_path/'hooks.json'))
    monkeypatch.setattr(ext, '_project_root', lambda: tmp_path)
    monkeypatch.setattr(ext, 'get_plugin_runtime_registry', lambda: object())
    monkeypatch.setattr(ext, '_hook_managers', weakref.WeakKeyDictionary())
    monkeypatch.setattr(ext, '_SWR_REFRESH_TASKS', set())
    monkeypatch.setattr(ext, '_hook_manager_rebuild_in_flight', False)
    monkeypatch.setattr(ext, '_runtime_hook_definitions', lambda loaded: ())
    loaded = SimpleNamespace(plugins=(), hook_sources=())
    monkeypatch.setattr(ext, 'load_plugins', lambda **kwargs: loaded)
    return ext, loaded


async def wait_event(event):
    async def poll():
        while not event.is_set():
            await asyncio.sleep(.001)
    await asyncio.wait_for(poll(), 5)


def test_hook_catalog_signature_and_cold_manager_leave_loop_free(monkeypatch, tmp_path):
    from agent_local_timing import LocalOperationTrace
    ext, loaded = configure(monkeypatch, tmp_path)
    owner = threading.get_ident()
    entered, release = threading.Event(), threading.Event()
    observed = []
    signature = ext._hook_signature

    def load(**kwargs):
        observed.append(('load', threading.get_ident()))
        assert threading.get_ident() != owner
        entered.set()
        assert release.wait(5)
        return loaded

    def get_signature(*args):
        observed.append(('signature', threading.get_ident()))
        assert threading.get_ident() != owner
        return signature(*args)

    original_manager = ext.HookManager
    def manager(*args, **kwargs):
        observed.append(('manager', threading.get_ident()))
        assert threading.get_ident() != owner
        return original_manager(*args, **kwargs)

    monkeypatch.setattr(ext, 'load_plugins', load)
    monkeypatch.setattr(ext, '_hook_signature', get_signature)
    monkeypatch.setattr(ext, 'HookManager', manager)
    trace = LocalOperationTrace('hook_dispatch', session_id='s', run_id='r')

    async def run():
        with trace.bind():
            pending = asyncio.create_task(ext.dispatch_hook('PreToolUse', {}))
            try:
                await wait_event(entered)
                # This coroutine can progress while catalog I/O is blocked.
                await asyncio.sleep(0)
                assert not pending.done()
                release.set()
                result = await pending
                assert result.enabled is False and result.skipped is True
                assert asyncio.get_running_loop() in ext._hook_managers
            finally:
                release.set()
                await asyncio.gather(pending, return_exceptions=True)
    asyncio.run(run())
    marks = trace.snapshot()
    assert {name for name, _ in observed} == {'load', 'signature', 'manager'}
    assert all(thread != owner for _, thread in observed)
    a, threads = marks['anchors'], marks['mark_threads']
    names = ['hook_prepare_submitted', 'hook_prepare_worker_entered',
             'hook_prepare_worker_finished', 'hook_prepare_resumed']
    assert [a[n] for n in names] == sorted(a[n] for n in names)
    assert threads[names[0]] == threads[names[-1]] == owner
    assert threads[names[1]] == threads[names[2]] != owner


def test_worker_stale_manager_rebuild_uses_original_loop_and_is_deduplicated(monkeypatch, tmp_path):
    ext, loaded = configure(monkeypatch, tmp_path)
    entered, release = threading.Event(), threading.Event()
    builds = []
    original_build = ext._build_hook_manager
    signature = ['old']
    monkeypatch.setattr(ext, '_hook_signature', lambda *args: signature[0])

    def rebuild(*args):
        builds.append(threading.get_ident())
        entered.set()
        assert release.wait(5)
        return original_build(*args)
    monkeypatch.setattr(ext, '_build_hook_manager', rebuild)

    async def run():
        loop = asyncio.get_running_loop()
        original_submit = loop.run_in_executor
        def submit(*args, **kwargs):
            assert asyncio.get_running_loop() is loop
            return original_submit(*args, **kwargs)
        monkeypatch.setattr(loop, 'run_in_executor', submit)
        first, *_ = await ext._prepare_hook_dispatch_async()
        signature[0] = 'new'
        try:
            old = await asyncio.gather(*(ext._prepare_hook_dispatch_async() for _ in range(6)))
            assert all(row[0] is first for row in old)
            await wait_event(entered)
            assert len(builds) == 1
        finally:
            release.set()
            if ext._SWR_REFRESH_TASKS:
                await asyncio.gather(*tuple(ext._SWR_REFRESH_TASKS))
        final, *_ = await ext._prepare_hook_dispatch_async()
        assert final is not first
        assert ext._hook_managers[loop] == ('new', final)
    asyncio.run(run())


def test_cancelled_preparation_does_not_dispatch_hook(monkeypatch, tmp_path):
    from agent_local_timing import LocalOperationTrace
    ext, loaded = configure(monkeypatch, tmp_path)
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    dispatched = []
    def load(**kwargs):
        entered.set()
        try:
            assert release.wait(5)
            return loaded
        finally:
            finished.set()
    monkeypatch.setattr(ext, 'load_plugins', load)
    original = ext.HookManager.dispatch
    async def dispatch(self, *args, **kwargs):
        dispatched.append(True)
        return await original(self, *args, **kwargs)
    monkeypatch.setattr(ext.HookManager, 'dispatch', dispatch)
    trace = LocalOperationTrace('hook_dispatch')
    async def run():
        with trace.bind():
            pending = asyncio.create_task(ext.dispatch_hook('PreToolUse', {}))
            try:
                await wait_event(entered)
                pending.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await pending
            finally:
                release.set()
                await wait_event(finished)
    asyncio.run(run())
    assert not dispatched
    a = trace.snapshot()['anchors']
    assert a['hook_prepare_resumed'] < a['hook_prepare_worker_finished']
