"""Isolated stdin fixture exercising the production host invoker and service loop.

This is a test process, never an HTTP route or a production plugin entry point.
"""
import asyncio
import json
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'app'))
from plugins import load_plugin
from plugins.host import _module
from execution_services.jobs import ExecutionService
from host_tool_registry import HostToolInvocationContext
import security.runtime


async def main():
    host = _module(load_plugin(ROOT / 'plugins/browser-use'))
    service = ExecutionService()
    manager = host.BrowserManager(service)
    manager.enabled = lambda: True
    security.runtime.session_permission_mode = lambda _: 'full_access'
    runtime_type = host.BrowserManager.__init__.__globals__['BrowserRuntime']
    runtime = runtime_type('fixture', host.extension_origin(), Path(sys.argv[1]), on_catalog=manager.register_catalog)
    manager.runtimes['fixture'] = runtime
    manager.default_browser = 'fixture'
    try:
        await service.call(runtime.start)
        print(json.dumps({'relay_url': runtime.relay_url()}), flush=True)
        while line := await asyncio.to_thread(sys.stdin.readline):
            request = json.loads(line)
            try:
                print('Host dispatch: ' + request['tool'], file=sys.stderr, flush=True)
                context = HostToolInvocationContext(session_id='host-session', run_id='host-run', services={
                    'security_context': SimpleNamespace(mode='full_access'), 'tool_name': request['tool'],
                    'image_input_enabled': False, 'model': 'fixture', 'security_workspace': Path(sys.argv[1]),
                })
                result = await manager.invoke(context, request.get('arguments', {}))
                print('Host settled: ' + result.kind.value, file=sys.stderr, flush=True)
                print(json.dumps({'id': request['id'], 'kind': result.kind.value, 'content': result.content, 'message': result.message, 'metadata': dict(result.metadata)}, ensure_ascii=False), flush=True)
            except Exception as error:
                print(json.dumps({'id': request['id'], 'error': str(error)}), flush=True)
    finally:
        await service.call(manager.close)
        await service.shutdown()


asyncio.run(main())
