"""Settings inventory must stay independent of executable plugin work."""
import asyncio
import json
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

import agent_extensions as ext
from plugins import PluginManager
from plugins.runtime import PluginRuntimeRegistry
from ui_metadata_cache import MetadataCache


@pytest.fixture
def catalog(tmp_path, monkeypatch):
    root = tmp_path / 'plugins/demo'
    (root / '.myagent-plugin').mkdir(parents=True)
    (root / 'web').mkdir()
    (root / 'web/index.html').write_text('demo', encoding='utf-8')
    (root / '.myagent-plugin/plugin.json').write_text(json.dumps({
        'schema_version': 1, 'id': 'demo', 'name': 'Demo', 'version': '1.0.0',
        'capabilities': {
            'web': {'entry': 'web/index.html', 'assets': 'web'},
            'ui': {'settings.section': [{'id': 'main', 'title': 'Demo settings', 'target': 'plugin-page',
                                        'href': 'https://untrusted.invalid'}]},
        },
    }), encoding='utf-8')
    manager = PluginManager([root.parent], tmp_path / 'plugin-state.json')
    registry = PluginRuntimeRegistry(storage_root=tmp_path / 'runtime')
    monkeypatch.setenv('PLUGINS_ENABLED', '1')
    monkeypatch.setattr(ext, 'plugin_manager', lambda: manager)
    monkeypatch.setattr(ext, '_project_root', lambda: tmp_path)
    monkeypatch.setattr(ext, 'get_plugin_runtime_registry', lambda: registry)
    monkeypatch.setattr(ext, '_plugin_cache', None)
    monkeypatch.setattr(ext, '_management_snapshot_cache', MetadataCache())
    monkeypatch.setattr(ext, '_plugin_catalog_snapshot_cache', MetadataCache())
    ext.load_plugins(force=True)
    yield manager, registry
    registry.close()


def test_settings_catalog_completes_while_full_snapshot_waits_for_runtime(catalog, monkeypatch):
    _, registry = catalog
    entered = threading.Event()
    original = registry.command_descriptions
    def commands(*args):
        entered.set()
        return original(*args)
    monkeypatch.setattr(registry, 'command_descriptions', commands)
    with ThreadPoolExecutor(max_workers=2) as pool:
        # Model a plugin request holding the real registry lock. Only the full
        # diagnostics API is allowed to depend on that worker's completion.
        with registry._lock:
            full = pool.submit(ext.extensions_snapshot)
            assert entered.wait(3)
            light = pool.submit(ext.plugin_catalog_snapshot).result(timeout=3)
            assert not full.done()
            assert light['ui_contributions'][0]['href'] == '/plugins/demo'
        complete = full.result(timeout=3)
    for key in ('plugins', 'ui_contributions', 'plugin_errors', 'plugin_warnings'):
        assert light[key] == complete[key]
    assert 'hooks' not in light and 'plugin_runtime' not in light and 'plugin_commands' not in light
    assert 'hooks' in complete and 'plugin_runtime' in complete


def test_catalog_never_requests_runtime_or_hooks_and_does_not_leak_mutations(catalog, monkeypatch):
    monkeypatch.setattr(ext, 'get_plugin_runtime_registry', lambda: pytest.fail('settings started a worker'))
    monkeypatch.setattr(ext, 'hook_snapshot', lambda: pytest.fail('settings read hooks'))
    first = ext.plugin_catalog_snapshot()
    first['plugins'].clear()
    first['ui_contributions'].clear()
    again = ext.plugin_catalog_snapshot()
    assert len(again['plugins']) == 1 and len(again['ui_contributions']) == 1


def test_disabling_plugin_invalidates_catalog_and_removes_contributed_tabs(catalog):
    assert len(ext.plugin_catalog_snapshot()['ui_contributions']) == 1
    ext.set_plugin_enabled('demo', False)
    disabled = ext.plugin_catalog_snapshot()
    assert disabled['ui_contributions'] == []
    assert disabled['plugins'][0]['enabled'] is False
    assert disabled['plugins'][0]['loaded'] is False
    ext.set_plugin_enabled('demo', True)
    assert len(ext.plugin_catalog_snapshot()['ui_contributions']) == 1


def test_globally_disabled_plugins_remove_tabs(catalog, monkeypatch):
    assert ext.plugin_catalog_snapshot()['ui_contributions']
    monkeypatch.setenv('PLUGINS_ENABLED', '0')
    disabled = ext.plugin_catalog_snapshot()
    assert not disabled['ui_contributions']
    assert disabled['plugins'][0]['enabled'] is False


def test_catalog_route_runs_off_loop_and_exposes_queue_and_build_timing(monkeypatch):
    import webui
    entered, release = threading.Event(), threading.Event()
    threads = []
    def snapshot(**kwargs):
        threads.append(threading.get_ident())
        assert kwargs['refresh_loop'].is_running()
        entered.set()
        assert release.wait(3)
        return {'ok': True, 'plugins': [], 'ui_contributions': []}
    monkeypatch.setattr(ext, 'plugin_catalog_snapshot', snapshot)
    async def run():
        task = asyncio.create_task(webui.get_plugin_catalog())
        try:
            assert await asyncio.to_thread(entered.wait, 2)
            assert threads != [threading.get_ident()]
        finally:
            release.set()
        response = await task
        assert response.status_code == 200
        assert 'queue;dur=' in response.headers['server-timing']
        assert 'catalog;dur=' in response.headers['server-timing']
    asyncio.run(run())
