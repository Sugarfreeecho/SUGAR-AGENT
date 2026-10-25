"""Refresh regressions reproduced with legacy parents and concurrent browsers."""
import ast
import asyncio
from pathlib import Path
import threading
import sys
from types import SimpleNamespace
from typing import Optional
import uuid

import pytest

ROOT = Path(__file__).resolve().parents[1]


def real_function(path, name, namespace):
    tree = ast.parse((ROOT / path).read_text(encoding='utf-8'))
    node = next(node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name)
    node.decorator_list = []
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), namespace)
    return namespace[name]


def test_legacy_parent_discovery_walks_only_session_directories(tmp_path, monkeypatch):
    namespace = {'Path': Path, 'Optional': Optional}
    scan = real_function('app/agent_harness.py', '_scan_nested_subagent_path', namespace)
    parent, child, grandchild, missing = [str(uuid.uuid4()) for _ in range(4)]
    nested = tmp_path / parent / 'subagents' / child / 'subagents' / grandchild
    nested.mkdir(parents=True)
    (tmp_path / parent / 'snapshots' / 'deep' / 'more').mkdir(parents=True)
    (tmp_path / '.runtime_v2_repair_backups' / parent / 'subagents' / missing).mkdir(parents=True)
    registered = []
    def valid(value):
        try: return str(uuid.UUID(value)) == value
        except ValueError: return False
    manager = SimpleNamespace(sessions_dir=tmp_path, _normalize_session_id=lambda value: str(uuid.UUID(value)),
                              _is_valid_session_id=valid, _register_subagent=lambda *args: registered.append(args))
    original = Path.iterdir
    def guarded(path):
        assert 'snapshots' not in path.parts and '.runtime_v2_repair_backups' not in path.parts
        return original(path)
    monkeypatch.setattr(Path, 'iterdir', guarded)
    monkeypatch.setattr(Path, 'rglob', lambda *args: pytest.fail('refresh must not recursively scan payload/backup files'))
    assert scan(manager, grandchild) == nested.resolve()
    assert registered == [(grandchild, child)]
    assert scan(manager, missing) is None
    later = tmp_path / parent / 'subagents' / missing
    later.mkdir()
    assert scan(manager, missing) == later.resolve(), 'external children remain discoverable after an earlier miss'


def test_async_state_readers_share_one_executor_build_and_survive_cancellation():
    entered, release = threading.Event(), threading.Event()
    calls = []
    def build(**_options):
        calls.append(True); entered.set()
        assert release.wait(3)
        return {'sessions': ['ready']}
    namespace = {'asyncio': asyncio, '_sessions_state_async_requests': {}, '_build_sessions_state_snapshot_cached': build}
    read = real_function('app/webui.py', '_sessions_state_payload_async', namespace)
    async def scenario():
        readers = [asyncio.create_task(read(False)) for _ in range(20)]
        try:
            while not entered.is_set(): await asyncio.sleep(0.001)
            readers[0].cancel()
            with pytest.raises(asyncio.CancelledError): await readers[0]
            release.set()
            results = await asyncio.gather(*readers[1:])
            assert all(result == {'sessions': ['ready']} for result in results)
            await asyncio.sleep(0)
            assert namespace['_sessions_state_async_requests'] == {}
        finally: release.set()
    asyncio.run(scenario())
    assert calls == [True], 'waiting browser requests must not consume individual executor workers'


@pytest.mark.parametrize('function,arguments', [('get_global_permissions', ()), ('get_session_permissions', ('s',))])
def test_slow_security_health_probe_keeps_http_event_loop_responsive(monkeypatch, function, arguments):
    entered, release = threading.Event(), threading.Event()
    def status(_sid):
        entered.set()
        assert release.wait(3)
        return {'mode': 'ask_for_approval'}
    monkeypatch.setitem(sys.modules, 'security', SimpleNamespace(security_status_for_session=status))
    namespace = {'asyncio': asyncio, 'JSONResponse': lambda content, **_: content}
    read = real_function('app/webui.py', function, namespace)
    async def scenario():
        request = asyncio.create_task(read(*arguments))
        try:
            await asyncio.wait_for(asyncio.to_thread(entered.wait), timeout=1)
            # Another coroutine (a list/static/status request) runs while the
            # native helper/permission store is still blocked in its worker.
            await asyncio.wait_for(asyncio.sleep(0), timeout=0.1)
            assert not request.done()
            release.set()
            assert (await request)['mode'] == 'ask_for_approval'
        finally: release.set()
    asyncio.run(scenario())


def test_sidebar_counts_exclude_archived_and_unrelated_descendants(monkeypatch):
    from session_activity import attach_background_work, background_work_snapshot

    counted = []
    index = {'visible-child': 'visible', 'nested': 'visible-child', 'archived-child': 'archived', 'orphan': 'missing'}
    service = SimpleNamespace(pending_counts_many=lambda ids: counted.append(set(ids)) or {
        sid: {'questions': 0, 'approvals': 0, 'total': 0} for sid in ids
    })
    monkeypatch.setitem(sys.modules, 'human_interaction', SimpleNamespace(get_human_interaction_service=lambda: service))
    monkeypatch.setitem(sys.modules, 'agent_subagent', SimpleNamespace(subagent_registry=SimpleNamespace(running_runs=lambda: {})))
    namespace = {
        'session_manager': SimpleNamespace(list_sessions=lambda **_: [{'id': 'visible'}], archived_session_count=lambda: 1,
                                           _load_subagent_index=lambda: index),
        '_cleanup_stale_active_chat': lambda: None,
        '_session_run_state_fields_light': lambda _: {'stream_active': False, 'run_active': False, 'run_started_at': None},
        'is_session_title_generation_pending': lambda _: False,
        'attach_background_work': attach_background_work,
        'background_work_snapshot': background_work_snapshot,
    }
    build = real_function('app/webui.py', '_build_sessions_state_snapshot', namespace)
    assert build()['sessions'][0]['pending_human_interactions']['total'] == 0
    assert counted == [{'visible', 'visible-child', 'nested'}]


def test_static_plugin_reads_reuse_catalog_but_recheck_enablement(monkeypatch, tmp_path):
    import agent_extensions
    import plugin_web_gateway as gateway
    plugin = SimpleNamespace(plugin_id='demo')
    enabled = [True]
    forces = []
    monkeypatch.setattr(gateway, 'load_plugins', lambda **options: forces.append(options['force']) or SimpleNamespace(plugins=[plugin]))
    monkeypatch.setattr(agent_extensions, 'plugin_manager', lambda: SimpleNamespace(is_enabled=lambda _: enabled[0]))
    monkeypatch.setattr(gateway, 'resolve_plugin_asset', lambda *_: tmp_path / 'app.js')
    gateway.plugin_asset('demo', 'app.js')
    gateway.plugin_asset('demo', 'style.css')
    assert forces == [False, False]
    enabled[0] = False
    with pytest.raises(gateway.PluginWebError): gateway._enabled_plugin('demo', refresh=False)
    gateway._enabled_plugin('demo')
    assert forces[-1] is True, 'executable API lookup retains its fresh-catalog contract'


def test_runtime_metadata_does_not_deepcopy_conversation_arrays(tmp_path, monkeypatch):
    from runtime_v2.snapshot_store import SnapshotStore
    class LargePayload:
        def __deepcopy__(self, memo):
            pytest.fail('status/recovery must not copy unrelated message/execution payloads')
    view = {'last_seq': 5, 'active_runs': [{'run_id': 'r'}], 'runs': {'r': {'status': 'running'}},
            'context': {'tokens': {'estimated': 10}}, 'extensions': {}, 'subagents': {},
            'ui_events': LargePayload(), 'model_messages': LargePayload(), 'executions': LargePayload()}
    monkeypatch.setattr(SnapshotStore, 'read_consistent_view', lambda *a, **k: view)
    monkeypatch.setattr(SnapshotStore, 'read_consistent', lambda *a, **k: pytest.fail('full snapshot copy'))
    namespace = {'session_manager': SimpleNamespace(repository=SimpleNamespace(sessions_dir=tmp_path),
                    _resolve_session_path=lambda sid: tmp_path / sid)}
    read = real_function('app/webui.py', '_runtime_v2_snapshot', namespace)
    result = read('s', fail_closed=True)
    assert result['last_seq'] == 5 and result['context']['tokens']['estimated'] == 10
    result['runs']['r']['status'] = 'changed locally'
    assert view['runs']['r']['status'] == 'running', 'metadata callers still receive independent values'


def test_plugin_ui_membership_does_not_build_decorated_summaries(monkeypatch):
    seen = []
    def project(ids, **_):
        seen.append(ids)
        return {'ok': True, 'sessions': {sid: {} for sid in ids}}
    monkeypatch.setitem(sys.modules, 'agent_extensions', SimpleNamespace(plugin_session_ui_snapshot=project))
    namespace = {'asyncio': asyncio, 'Request': object, 'JSONResponse': lambda content, **_: content,
                 '_runtime_v2_extensions_snapshot': lambda _: {},
                 'session_manager': SimpleNamespace(index=[{'id': 'a'}, {'id': 'archived', 'archived': True}],
                     get_session_summary=lambda _: pytest.fail('membership must not rebuild activity/history previews'))}
    route = real_function('app/webui.py', 'get_plugin_session_ui', namespace)
    async def body(): return {'session_ids': ['a', 'missing', 'a', 'archived']}
    result = asyncio.run(route(SimpleNamespace(json=body)))
    assert result['ok'] and seen == [['a', 'archived']]
