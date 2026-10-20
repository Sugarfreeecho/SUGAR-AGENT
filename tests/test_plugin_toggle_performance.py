"""A plugin toggle must retain unrelated workers and avoid repeated discovery."""
import asyncio
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))


def test_target_invalidation_preserves_other_bindings_leases_and_worker(tmp_path):
    from plugins.runtime import PluginRuntimeRegistry, RuntimeDeferredLease, RuntimeToolBinding

    registry = PluginRuntimeRegistry(storage_root=tmp_path)
    closed, cancelled = [], []
    for plugin_id in ("demo.target", "demo.keep"):
        key = (plugin_id, "v1")
        registry._workers[key] = SimpleNamespace(
            plugin=SimpleNamespace(permissions={}), trusted_context=lambda: {},
            close=lambda id=plugin_id: closed.append(id),
            request=lambda method, args, id=plugin_id: cancelled.append((id, method)),
        )
        registry._describe_cache[key] = {"tools": []}
        registry._tool_bindings[plugin_id] = RuntimeToolBinding(plugin_id, plugin_id, "read", "v1", {})
        registry._deferred_leases[(plugin_id, "token")] = RuntimeDeferredLease(
            plugin_id, plugin_id, "v1", "session", "run", "cancel", time.time() + 60)
    keep = registry._workers[("demo.keep", "v1")]
    try:
        registry.invalidate(plugin_id="demo.target")
        assert closed == ["demo.target"]
        assert cancelled == [("demo.target", "deferred.cancel")]
        assert registry._workers[("demo.keep", "v1")] is keep
        assert set(registry._describe_cache) == {("demo.keep", "v1")}
        assert set(registry._tool_bindings) == {"demo.keep"}
        assert set(registry._deferred_leases) == {("demo.keep", "token")}
    finally:
        registry.close()


def test_plugin_toggle_releases_only_its_own_runtime(monkeypatch):
    import agent_extensions as ext
    import plugin_host_services

    calls = []
    manager = SimpleNamespace(set_enabled=lambda id, enabled: {"enabled": enabled})
    registry = SimpleNamespace(invalidate=lambda **kwargs: calls.append(("runtime", kwargs)))
    monkeypatch.setattr(ext, "plugin_manager", lambda: manager)
    monkeypatch.setattr(ext, "get_plugin_runtime_registry", lambda: registry)
    monkeypatch.setattr(ext, "_drain_background_refreshes", lambda: pytest.fail("toggle waited for unrelated background refreshes"))
    monkeypatch.setattr(plugin_host_services, "release_plugin_leases", lambda id: calls.append(("leases", id)))
    monkeypatch.setattr(plugin_host_services, "release_all_plugin_leases", lambda: pytest.fail("released unrelated leases"))
    ext.set_plugin_enabled("demo.target", False)
    assert calls == [("leases", "demo.target"), ("runtime", {"plugin_id": "demo.target"})]


@pytest.mark.parametrize("kind", ["catalog", "hooks"])
def test_old_background_refresh_cannot_repopulate_invalidated_cache(monkeypatch, kind):
    import agent_extensions as ext
    import workflow_extensions
    import plugin_host_services

    started, release = threading.Event(), threading.Event()
    monkeypatch.setattr(ext, "_extension_catalog_generation", 0)
    monkeypatch.setattr(ext, "_plugin_cache", None)
    monkeypatch.setattr(ext, "_hook_managers", {})
    monkeypatch.setattr(ext, "_SWR_REFRESH_TASKS", set())
    monkeypatch.setattr(ext, "_swr_refresh_in_flight", False)
    monkeypatch.setattr(ext, "_hook_manager_rebuild_in_flight", False)
    monkeypatch.setattr(ext, "get_plugin_runtime_registry", lambda: SimpleNamespace(invalidate=lambda **_: None))
    monkeypatch.setattr(workflow_extensions, "invalidate_bundled_workflow_callbacks", lambda: None)
    monkeypatch.setattr(plugin_host_services, "release_plugin_leases", lambda _: None)

    def build(*args):
        started.set()
        assert release.wait(5)
        return object()

    monkeypatch.setattr(ext, "_build_hook_manager", build)

    async def run():
        loop = asyncio.get_running_loop()
        try:
            with ext._lock:
                if kind == "catalog":
                    assert ext._schedule_plugin_cache_refresh(SimpleNamespace(load_enabled=build), ("old",))
                else:
                    ext._schedule_hook_manager_rebuild(loop, "old", object(), ())
            assert await asyncio.to_thread(started.wait, 3)
            ext.invalidate_extension_caches(plugin_id="demo.target")
            assert not release.is_set(), "invalidation completes while the old rebuild remains blocked"
            release.set()
            await asyncio.gather(*ext._SWR_REFRESH_TASKS)
            assert ext._plugin_cache is None
            assert not ext._hook_managers
        finally:
            release.set()

    asyncio.run(run())


def test_lifecycle_refresh_scans_once_off_the_request_loop(monkeypatch):
    import agent_extensions as ext
    import plugins.host as host
    import webui
    import workflow_extensions

    loaded = SimpleNamespace(plugins=())
    scans, backgrounds = [], []
    caller_thread = threading.get_ident()

    def load(**kwargs):
        scans.append(threading.get_ident())
        return loaded

    async def no_hosts(*args):
        pass

    monkeypatch.setattr(ext, "load_plugins", load)
    monkeypatch.setattr(ext, "get_plugin_runtime_registry", lambda: SimpleNamespace(
        background_status=lambda plugins: backgrounds.append(plugins)))
    monkeypatch.setattr(host, "install_bundled_host_extensions", lambda *args: None)
    monkeypatch.setattr(host, "start_bundled_host_extensions", no_hosts)
    monkeypatch.setattr(workflow_extensions, "activate_bundled_workflow_callbacks", lambda *args, **kwargs: None)
    asyncio.run(webui.refresh_web_plugin_lifecycle())
    assert len(scans) == 1
    assert scans[0] != caller_thread
    assert backgrounds == [loaded.plugins]


def test_toggle_audit_reuses_inventory_and_reads_enablement_once(monkeypatch):
    import agent_extensions as ext

    writes, reads = [], []
    plugin = SimpleNamespace(plugin_id="demo.target", name="Demo", version="1", source_format="native",
                             compatibility=SimpleNamespace(status="native"), content_signature="v1")
    manager = SimpleNamespace(
        last_discovery=SimpleNamespace(plugins=[plugin]), last_load=SimpleNamespace(plugins=[]),
        state=SimpleNamespace(read=lambda: reads.append(1) or {"plugins": {"demo.target": {"enabled": False}}}),
        discover_report=lambda: pytest.fail("toggle audit rescanned plugin inventory"),
    )
    ops = SimpleNamespace(snapshots=SimpleNamespace(read=lambda _: {}),
                          update_plugin_state=lambda *args, **kwargs: writes.append(args))
    monkeypatch.setattr(ext, "plugin_manager", lambda: manager)
    monkeypatch.setattr(ext, "_runtime_v2_enabled", lambda: True)
    monkeypatch.setattr(ext, "_history_ops", lambda _: ops)
    monkeypatch.setattr(ext, "load_plugins", lambda **_: pytest.fail("toggle audit forced another load"))
    ext.audit_plugin_inventory(None, "session", reuse_catalog=True)
    assert reads == [1]
    assert len(writes) == 1
    assert writes[0][2]["enabled"] is False
    assert writes[0][2]["loaded"] is False


@pytest.mark.parametrize("has_mcp", [False, True])
def test_toggle_api_only_refreshes_its_mcp_and_reuses_audit_catalog(monkeypatch, has_mcp):
    import agent_extensions as ext
    import webui

    calls = []
    plugin = SimpleNamespace(plugin_id="demo.target", mcp_servers={"demo.target/read": {}} if has_mcp else {})
    monkeypatch.setattr(ext, "plugin_manager", lambda: SimpleNamespace(last_discovery=SimpleNamespace(plugins=[plugin])))
    monkeypatch.setattr(ext, "set_plugin_enabled", lambda id, enabled: {"enabled": enabled})
    monkeypatch.setattr(ext, "audit_plugin_inventory", lambda *args, **kwargs: calls.append(("audit", kwargs)))

    async def refresh():
        calls.append(("lifecycle", {}))

    async def reload_plugin(id):
        assert id == "demo.target"
        calls.append(("mcp", {}))

    async def forbidden():
        pytest.fail("toggling a plugin must not force-reload all MCP servers")

    async def request_json():
        return {"enabled": False, "session_id": "session"}

    monkeypatch.setattr(webui, "refresh_web_plugin_lifecycle", refresh)
    monkeypatch.setattr(webui.agent_mcp, "reload_plugin", reload_plugin)
    monkeypatch.setattr(webui.agent_mcp, "force_reload", forbidden)
    response = asyncio.run(webui.set_plugin_enabled_api("demo.target", SimpleNamespace(json=request_json)))
    assert response.status_code == 200, response.body
    assert calls == [("lifecycle", {})] + ([("mcp", {})] if has_mcp else []) + [("audit", {"reuse_catalog": True})]
    assert "plugin-total;dur=" in response.headers["server-timing"]


def test_plugin_toggle_frontend_pending_success_and_failure():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is required for the frontend runtime check")
    result = subprocess.run([node, str(ROOT / "tests/js/plugin_toggle_runtime.cjs")],
                            cwd=ROOT, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_loading_control_stays_visible_without_hover(theme):
    playwright = pytest.importorskip("playwright.sync_api")
    with playwright.sync_playwright() as runtime:
        try:
            browser = runtime.chromium.launch(headless=True, **({"channel": "msedge"} if os.name == "nt" else {}))
        except playwright.Error as error:
            pytest.skip(f"Local Chromium browser unavailable: {error}")
        try:
            page = browser.new_page(viewport={"width": 440, "height": 540})
            page.set_content(f'<html class="theme-{theme}"><body><div id="panel" class="skill-picker-popover is-open"><div class="skill-picker-list"></div></div></body></html>')
            page.add_style_tag(path=str(ROOT / "frontend/src/styles/app.css"))
            page.add_style_tag(content="body{display:block;padding:24px}#panel{position:relative;inset:auto;width:380px;max-height:none;transform:none}.skill-picker-list{max-height:none}")
            source = (ROOT / "frontend/src/app/modules/skill-picker.js").read_text(encoding="utf-8")
            page.add_script_tag(content="var currentSessionId='session';\n" + source.replace("\ninitSkillPicker();", "\n"))
            page.evaluate("""() => {
                extensionsCache = {enabled: {plugins: true}, plugins: [
                    {id:'web-search-providers', name:'Web Search', version:'1.0', enabled:true},
                    {id:'game-arena', name:'Game Arena', version:'1.0', enabled:false}
                ]};
                pluginToggleBusy['web-search-providers'] = {enabled:false, phase:'switching'};
                pluginToggleBusy['game-arena'] = {enabled:true, phase:'switching'};
                document.querySelector('.skill-picker-list').innerHTML = renderSkillPickerPluginsHtml();
            }""")
            for label in ("正在禁用…", "正在启用…"):
                assert page.get_by_role("status").filter(has_text=label).is_visible()
            for control in page.locator(".plugin-toggle-action").all():
                assert control.is_disabled()
                assert control.locator(".plugin-toggle-spinner").is_visible()
                assert control.evaluate("el => getComputedStyle(el.parentElement).opacity") == "1"
            output = ROOT / ".analysis/plugin-toggle"
            output.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(output / f"loading-{theme}.png"))
        finally:
            browser.close()
