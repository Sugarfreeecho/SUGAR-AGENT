"""Metadata caching must coalesce work without crossing mutation boundaries."""
import asyncio
import json
import shutil
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from ui_metadata_cache import MetadataCache


def test_single_flight_isolated_values_and_retry():
    cache = MetadataCache()
    entered, release = threading.Event(), threading.Event()
    calls = []

    def build():
        calls.append(1)
        entered.set()
        assert release.wait(3)
        return {'rows': [1]}

    with ThreadPoolExecutor(max_workers=4) as pool:
        first = pool.submit(cache.get, ('v1',), build)
        assert entered.wait(2)
        others = [pool.submit(cache.get, ('v1',), build) for _ in range(3)]
        release.set()
        value = first.result(timeout=2)
        value['rows'].append(2)
        assert all(item.result(timeout=2) == {'rows': [1]} for item in others)
    assert calls == [1]
    with pytest.raises(ValueError):
        cache.get(('bad',), lambda: (_ for _ in ()).throw(ValueError('failed')))
    assert cache.get(('bad',), lambda: {'recovered': True}) == {'recovered': True}


def test_old_generation_cannot_replace_new_cache():
    cache = MetadataCache()
    entered, release = threading.Event(), threading.Event()

    def old():
        entered.set()
        assert release.wait(3)
        return {'version': 1}

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(cache.get, (1,), old)
        assert entered.wait(2)
        assert cache.get((2,), lambda: {'version': 2}) == {'version': 2}
        release.set()
        first.result(timeout=2)
    assert cache.get((2,), lambda: pytest.fail('obsolete builder evicted fresh data')) == {'version': 2}


def test_expired_metadata_rebuilds(monkeypatch):
    import ui_metadata_cache as module
    now = [1.0]
    monkeypatch.setattr(module, 'monotonic', lambda: now[0])
    cache = MetadataCache(ttl=10)
    cache.get((1,), lambda: {'version': 1})
    now[0] += 11
    assert cache.get((1,), lambda: {'version': 2}) == {'version': 2}


def test_expired_display_is_immediate_but_new_generation_is_fresh(monkeypatch):
    import ui_metadata_cache as module
    now = [1.0]
    monkeypatch.setattr(module, 'monotonic', lambda: now[0])
    cache = MetadataCache(ttl=10, stale_while_revalidate=True)
    cache.get((1,), lambda: {'version': 1})
    now[0] += 11
    entered, release = threading.Event(), threading.Event()
    def slow():
        entered.set()
        assert release.wait(3)
        return {'version': 2}
    try:
        assert cache.get((1,), slow) == {'version': 1}
        assert entered.wait(2)
        assert cache.get((1,), lambda: pytest.fail('duplicate refresh')) == {'version': 1}
        assert cache.get((2,), lambda: {'version': 3}) == {'version': 3}
    finally:
        release.set()


def test_mcp_display_does_not_wait_for_transport_startup(monkeypatch):
    import webui
    scheduled = []

    async def forbidden():
        pytest.fail('display endpoint waited for MCP startup')

    monkeypatch.setattr(webui.agent_mcp, 'ensure_started', forbidden)
    monkeypatch.setattr(webui.agent_mcp, 'schedule_mcp_startup_refresh', lambda: scheduled.append(True))
    monkeypatch.setattr(webui.agent_mcp, 'catalog_refresh_pending', lambda: True)
    monkeypatch.setattr(webui.agent_mcp, 'list_registered_tools', lambda: [])
    monkeypatch.setattr(webui.agent_mcp, 'list_configured_servers', lambda: [{'server': 'slow', 'connected': False}])
    data = json.loads(asyncio.run(webui.list_mcp_tools()).body)
    assert scheduled == [True]
    assert data['initializing'] is True
    assert data['servers'][0]['server'] == 'slow'


def test_extensions_snapshot_reuses_inventory_and_invalidates_on_generation(monkeypatch, tmp_path):
    import agent_extensions as ext
    from types import SimpleNamespace
    manager = SimpleNamespace(state=SimpleNamespace(path=tmp_path / 'plugins.json'))
    calls = []
    monkeypatch.setattr(ext, 'plugin_manager', lambda: manager)
    monkeypatch.setattr(ext, 'hooks_config_path', lambda: tmp_path / 'hooks.json')
    monkeypatch.setattr(ext, '_management_snapshot_cache', MetadataCache())
    monkeypatch.setattr(ext, '_build_extensions_snapshot', lambda: calls.append(1) or {'plugins': [{'enabled': True}]})
    first = ext.extensions_snapshot()
    first['plugins'].clear()
    assert ext.extensions_snapshot()['plugins'] == [{'enabled': True}]
    assert len(calls) == 1
    monkeypatch.setattr(ext, '_extension_catalog_generation', ext.extension_catalog_generation() + 1)
    ext.extensions_snapshot()
    assert len(calls) == 2


@pytest.mark.parametrize('name,marker', [
    ('catalog_cache_runtime.cjs', 'catalog cache and lazy picker runtime checks passed'),
    ('session_startup_loading_runtime.cjs', 'session startup prefetch and immediate cached restore checks passed'),
])
def test_frontend_metadata_and_loading_runtime(name, marker):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is required for the frontend runtime check')
    script = Path(__file__).resolve().parent / 'js' / name
    result = subprocess.run([node, str(script)], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
    assert marker in result.stdout, 'the asynchronous runtime check must finish'
