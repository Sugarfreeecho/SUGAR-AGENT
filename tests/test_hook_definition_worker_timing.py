import asyncio
from concurrent.futures import ThreadPoolExecutor
import threading
import time
from types import SimpleNamespace


def test_hook_definition_worker_span_excludes_executor_wait_and_keeps_result(monkeypatch):
    import agent_extensions
    import plugins.host_hooks as hooks
    from agent_local_timing import LocalOperationTrace, local_step

    entered, release = threading.Event(), threading.Event()
    result = (object(),)
    registry = object()
    monkeypatch.setattr(agent_extensions, 'get_plugin_runtime_registry', lambda: registry)
    def definitions(actual_registry, plugins):
        assert actual_registry is registry and plugins == ('plugin',)
        return result
    monkeypatch.setattr(hooks, 'runtime_hook_definitions', definitions)
    trace = LocalOperationTrace('hook_dispatch', session_id='s', run_id='r')

    def occupy():
        entered.set()
        assert release.wait(5)

    async def run():
        loop = asyncio.get_running_loop()
        loop.set_default_executor(ThreadPoolExecutor(1))
        occupied = asyncio.create_task(asyncio.to_thread(occupy))
        while not entered.is_set():
            await asyncio.sleep(0)
        with trace.bind():
            async def request():
                with local_step('hook_runtime_definitions'):
                    return await asyncio.to_thread(agent_extensions._runtime_hook_definitions,
                                                   SimpleNamespace(plugins=('plugin',)))
            pending = asyncio.create_task(request())
            try:
                await asyncio.sleep(.06)
                assert not pending.done()
                released_at = time.perf_counter()
                release.set()
                assert await pending is result
                await occupied
            finally:
                release.set()
        return released_at

    released_at = asyncio.run(run())
    spans = {span['name']: span for span in trace.snapshot()['spans']}
    outer, worker = spans['hook_runtime_definitions'], spans['hook_runtime_definitions_worker']
    assert outer['started'] < released_at <= worker['started'] <= worker['ended'] <= outer['ended']
    assert outer['elapsed_ms'] > worker['elapsed_ms']
