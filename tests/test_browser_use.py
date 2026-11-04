"""Browser integration contracts with the real control store and Node runtime."""
import asyncio
import hashlib
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from plugins import load_plugin
from plugins.host import _module
from session_control.policy import Principal
from tests.test_session_control import composed  # reusable isolated runtime fixture

ROOT = Path(__file__).resolve().parents[1]


def test_browser_setup_checks_fixed_artifacts_and_rejects_cross_origin_actions(browser_host, monkeypatch):
    import importlib
    host, c = browser_host
    setup = importlib.import_module(host.__package__ + '.setup')
    opened = []
    monkeypatch.setattr(setup, 'reveal_extension', lambda: opened.append('fixed-extension-directory'))
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=c.app), base_url='http://127.0.0.1') as client:
            response = await client.get('/api/browser/v1/setup')
            assert response.status_code == 200
            assert response.json()['protocol'] == 1
            assert response.json()['extension_directory'] == str(ROOT / 'browser-extension' / 'dist')
            assert 'token' not in response.json()
            assert (await client.get('/api/browser/v1/setup', headers={'Origin': 'https://attacker.example'})).status_code == 403
            assert (await client.post('/api/browser/v1/setup/reveal', headers={'Origin': 'https://attacker.example'}, json={})).status_code == 403
            assert (await client.post('/api/browser/v1/setup/reveal', headers={'Origin': 'http://127.0.0.1'}, json={'path': 'C:/ignored'})).status_code == 200
            assert opened == ['fixed-extension-directory']
            package = await client.get('/api/browser/v1/setup/download')
            assert package.status_code == 200 and package.content.startswith(b'PK')
    asyncio.run(scenario())


def test_setup_installs_only_locked_runtime_with_a_filtered_environment(browser_host, monkeypatch, tmp_path):
    import importlib
    import os
    host, _ = browser_host
    setup = importlib.import_module(host.__package__ + '.setup')
    node = tmp_path / 'node.exe'
    npm = tmp_path / 'node_modules/npm/bin/npm-cli.js'
    npm.parent.mkdir(parents=True)
    npm.write_text('// test npm', encoding='utf-8')
    monkeypatch.setattr(setup.shutil, 'which', lambda name: str(node if name == 'node' else tmp_path / 'npm.cmd'))
    monkeypatch.setenv('OPENAI_API_KEY', 'never-inherit-this')
    calls = []
    class Process:
        returncode = 0
        async def communicate(self): return b'', b''
    async def spawn(*args, **kwargs): calls.append((args, kwargs)); return Process()
    monkeypatch.setattr(setup.asyncio, 'create_subprocess_exec', spawn)
    async def scenario():
        await setup.install_runtime()
        await setup._installation
        assert setup._install_state['status'] == 'succeeded'
        args, kwargs = calls[0]
        assert args[2:] == ('ci', '--omit=dev', '--no-audit', '--no-fund')
        assert kwargs['cwd'] == str(ROOT / 'plugins/browser-use/node')
        assert 'OPENAI_API_KEY' not in kwargs['env']
        assert kwargs['env']['PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD'] == '1'
    asyncio.run(scenario())


def test_disabled_browser_setup_is_discoverable_but_does_not_enable_runtime(monkeypatch, tmp_path):
    import agent_extensions
    import plugin_web_gateway as gateway
    import plugins
    from plugins.web import bundled_setup_page
    from tests.test_plugin_web_gateway import _make_web_plugin
    browser = load_plugin(ROOT / 'plugins/browser-use')
    user_root = _make_web_plugin(tmp_path / 'user-plugins')
    import json
    manifest_path = user_root / '.myagent-plugin/plugin.json'
    manifest = json.loads(manifest_path.read_text())
    manifest['capabilities']['web']['setup_when_disabled'] = True
    manifest['capabilities']['ui'] = {'settings.section': [{'id': 'native', 'target': 'renderer',
        'renderer': {'module': 'app.js'}}]}
    manifest_path.write_text(json.dumps(manifest))
    user = load_plugin(user_root)
    from plugins import plugin_ui_contributions
    assert not any(item.get('target') == 'renderer' for item in plugin_ui_contributions(user))
    assert bundled_setup_page(browser)
    assert not bundled_setup_page(user)
    def unavailable(*_args, **_kwargs): raise gateway.PluginWebError(404, 'disabled', 'Disabled')
    monkeypatch.setattr(gateway, '_enabled_plugin', unavailable)
    monkeypatch.setattr(plugins, 'get_plugin_manager', lambda: SimpleNamespace(discover=lambda: [browser, user]))
    assert gateway.plugin_page('browser-use') == ROOT / 'plugins/browser-use/web/index.html'
    assert gateway.plugin_asset('browser-use', 'app.js') == ROOT / 'plugins/browser-use/web/app.js'
    with pytest.raises(gateway.PluginWebError): gateway.plugin_page(user.plugin_id)
    with pytest.raises(gateway.PluginWebError): gateway.plugin_asset(user.plugin_id, 'app.js')
    report = SimpleNamespace(plugins=[browser], errors=[], warnings=[])
    manager = SimpleNamespace(discover_report=lambda: report, is_enabled=lambda _id: False)
    loaded = SimpleNamespace(plugins=[], errors=[], warnings=[])
    monkeypatch.setattr(agent_extensions, '_plugin_cache', None)
    snapshot = agent_extensions._plugin_catalog_data(manager, loaded)
    assert any(item['plugin_id'] == 'browser-use' for item in snapshot['ui_contributions'])
    assert all(item['slot'] == 'settings.section' for item in snapshot['ui_contributions'])
    section = next(item for item in snapshot['ui_contributions'] if item['plugin_id'] == 'browser-use')
    assert section['target'] == 'renderer' and '/browser-use/settings.js' in section['renderer']['module']
    assert not snapshot['plugins'][0]['enabled'] and not snapshot['plugins'][0]['loaded']


@pytest.fixture
def browser_host(composed, monkeypatch):
    import session_control.integration
    monkeypatch.setattr(session_control.integration, "_application", composed.control)
    plugin = load_plugin(ROOT / "plugins" / "browser-use")
    host = _module(plugin)
    manager = host.BrowserManager(SimpleNamespace(_loop=None))
    manager.enabled = lambda: True
    monkeypatch.setattr(host, "_manager", manager)
    host.install(composed.app, {"session_manager": composed.manager}, plugin)
    return host, composed


def test_pairing_reuses_identity_and_grants_trusted_schedules(browser_host):
    host, c = browser_host
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=c.app), base_url="http://127.0.0.1") as client:
            pairing = await client.post('/api/browser/v1/pairings', headers={"Origin": "http://127.0.0.1"}, json={"name": "Fixture"})
            assert pairing.status_code == 200, pairing.text
            code = pairing.json()["code"]
            denied = await client.post('/api/browser/v1/claim', headers={"Origin": "https://untrusted.test"}, json={"code": code})
            assert denied.status_code == 403
            claimed = await client.post('/api/browser/v1/claim', headers={"Origin": host.extension_origin()}, json={"code": code})
            assert claimed.status_code == 200, claimed.text
            token = claimed.json()["token"]
            principal = c.control.identities.authenticate(token)
            assert not principal.admin
            assert principal.permits("session.send")
            assert principal.permits("session.config.update")
            # Trusted pairing path: schedules work like the main window, while
            # admin-only surfaces stay closed.
            assert principal.permits("automation.create")
            assert principal.permits("automation.list")
            assert not principal.permits("device.revoke")
            replay = await client.post('/api/browser/v1/claim', headers={"Origin": host.extension_origin()}, json={"code": code})
            assert replay.status_code == 401
            response = await client.post('/api/control/v1/rpc', headers={"Authorization": "Bearer " + token},
                json={"method": "session.create", "params": {"name": "From extension", "work_dir": str(c.root)}, "idempotency_key": "browser-test-create"})
            assert response.status_code == 200, response.text
            sid = response.json()["data"]["session_id"]
            created = await client.post('/api/control/v1/rpc', headers={"Authorization": "Bearer " + token},
                json={"method": "automation.create", "params": {
                    "name": "Pairing schedule", "trigger": {"kind": "interval", "seconds": 3600},
                    "target": {"mode": "existing", "session_id": sid},
                    "policy": {"scope": "all", "capabilities": ["session.send"]},
                    "action": {"kind": "prompt", "text": "继续"}}, "idempotency_key": "browser-test-schedule"})
            assert created.status_code == 200, created.text
            task = created.json()["data"]
            assert task["owner"] == principal.id
            listed = await client.post('/api/control/v1/rpc', headers={"Authorization": "Bearer " + token},
                json={"method": "automation.list", "params": {}, "idempotency_key": "browser-test-list"})
            assert [row["id"] for row in listed.json()["data"]["items"]] == [task["id"]]
            assert (await client.post('/api/control/v1/rpc', headers={"Authorization": "Bearer " + token},
                json={"method": "automation.delete", "params": {"id": task["id"], "expected_revision": task["revision"]},
                      "idempotency_key": "browser-test-delete"})).status_code == 200
            revoked = await client.post('/api/browser/v1/devices/' + principal.id + '/revoke', headers={"Origin": "http://127.0.0.1"}, json={})
            assert revoked.status_code == 200, revoked.text
            with pytest.raises(Exception, match="revoked"):
                c.control.identities.ensure_live(principal)
    asyncio.run(scenario())


def test_general_remote_pairing_cannot_be_promoted_to_browser_identity(browser_host):
    host, c = browser_host
    general = c.control.identities.remote.create_pairing(scopes=["read"])
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=c.app), base_url="http://127.0.0.1") as client:
            response = await client.post('/api/browser/v1/claim', headers={"Origin": host.extension_origin()}, json={"code": general["code"]})
            assert response.status_code == 401
            forbidden = await client.post('/api/browser/v1/pairings', headers={"Origin": "http://different.test"}, json={})
            assert forbidden.status_code == 403
    asyncio.run(scenario())


def test_sidebar_workspaces_native_picker_and_plugin_inventory_use_scoped_identity(browser_host, monkeypatch, tmp_path):
    import agent_extensions
    import path_picker_util
    host, c = browser_host
    target = tmp_path / 'selected-workspace'
    target.mkdir()
    chosen = []
    def pick(kind, initial, multiple):
        chosen.append((kind, initial, multiple))
        return str(target)
    monkeypatch.setattr(path_picker_util, 'pick_native_path', pick)
    monkeypatch.setattr(agent_extensions, 'plugin_catalog_snapshot', lambda: {
        'plugins': [{'id': 'fixture', 'name': 'Fixture plugin', 'description': 'Read project data', 'enabled': True, 'loaded': True, 'secret': 'must-not-leak'}],
        'ui_contributions': [{'plugin_id': 'fixture', 'slot': 'settings.section', 'id': 'settings'}]})
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=c.app), base_url='http://127.0.0.1') as client:
            pairing = await client.post('/api/browser/v1/pairings', headers={'Origin': 'http://127.0.0.1'}, json={})
            claimed = await client.post('/api/browser/v1/claim', headers={'Origin': host.extension_origin()}, json={'code': pairing.json()['code']})
            auth = {'Authorization': 'Bearer ' + claimed.json()['token']}
            write = {**auth, 'Origin': host.extension_origin()}
            assert (await client.get('/api/browser/v1/workspaces')).status_code == 401
            result = await client.get('/api/browser/v1/workspaces', headers=auth)
            assert result.status_code == 200, result.text
            assert result.json()['default_work_dir'] == str(c.root)
            assert result.json()['workspaces'] == [{'path': str(c.root), 'name': c.root.name}]
            assert (await client.post('/api/browser/v1/workspaces/pick', headers=auth, json={})).status_code == 403
            picked = await client.post('/api/browser/v1/workspaces/pick', headers=write, json={'initial': str(c.root)})
            assert picked.json() == {'cancelled': False, 'path': str(target)}
            assert chosen == [('directory', str(c.root), False)]
            assert (await client.post('/api/browser/v1/workspaces/validate', headers=write, json={'path': 'relative'})).status_code == 422
            assert (await client.post('/api/browser/v1/workspaces/validate', headers=write, json={'path': str(target / 'missing')})).status_code == 422
            valid = await client.post('/api/browser/v1/workspaces/validate', headers=write, json={'path': str(target)})
            assert valid.json() == {'path': str(target.resolve())}
            monkeypatch.setattr(path_picker_util, 'pick_native_path', lambda *_args: None)
            cancelled = await client.post('/api/browser/v1/workspaces/pick', headers=write, json={})
            assert cancelled.json() == {'cancelled': True, 'path': ''}
            plugins = await client.get('/api/browser/v1/plugins', headers=auth)
            assert plugins.status_code == 200
            assert plugins.json()['plugins'][0]['settings_section'] == 'plugin:fixture:settings'
            assert 'secret' not in plugins.text and 'must-not-leak' not in plugins.text
            assert (await client.get('/api/browser/v1/plugins', headers={**auth, 'Origin': 'https://untrusted.test'})).status_code == 403
    asyncio.run(scenario())


def test_authenticated_extension_gets_may_omit_origin_but_writes_and_foreign_origins_cannot(browser_host, monkeypatch):
    import model_profiles
    host, c = browser_host
    monkeypatch.setattr(model_profiles, 'sorted_profiles', lambda _root: [])
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=c.app), base_url='http://127.0.0.1') as client:
            pairing = await client.post('/api/browser/v1/pairings', headers={'Origin': 'http://127.0.0.1'}, json={})
            claimed = await client.post('/api/browser/v1/claim', headers={'Origin': host.extension_origin()}, json={'code': pairing.json()['code']})
            auth = {'Authorization': 'Bearer ' + claimed.json()['token']}
            assert (await client.get('/api/browser/v1/models', headers=auth)).json() == {'profiles': []}
            assert (await client.get('/api/browser/v1/models')).status_code == 401
            assert (await client.get('/api/browser/v1/models', headers={**auth, 'Origin': 'https://untrusted.test'})).status_code == 403
            assert (await client.get('/api/browser/v1/models', headers={**auth, 'Origin': 'null'})).status_code == 403
            assert (await client.post('/api/browser/v1/approvals/analyze', headers=auth, json={})).status_code == 403
            principal = c.control.identities.authenticate(claimed.json()['token'])
            c.control.identities.remote.revoke_device(principal.id)
            assert (await client.get('/api/browser/v1/models', headers=auth)).status_code == 401
    asyncio.run(scenario())


def test_catalog_uses_upstream_definitions_and_security_effects(monkeypatch, tmp_path):
    import host_tool_contracts
    import host_tool_registry
    from security.runtime import classify_tool
    plugin = load_plugin(ROOT / "plugins" / "browser-use")
    host = _module(plugin)
    monkeypatch.setattr(host_tool_registry, "host_tool_invokers", host_tool_registry.HostToolInvokerRegistry())
    monkeypatch.setattr(host_tool_contracts, "_PROVIDERS", [])
    manager = host.BrowserManager(None)
    schema = {"type": "object", "properties": {"target": {"type": "string"}}, "required": ["target"]}
    manager.register_catalog([{"name": "browser_click", "inputSchema": schema},
        {"name": "browser_snapshot", "inputSchema": {"type": "object"}},
        {"name": "browser_get_context", "inputSchema": {"type": "object", "properties": {}}},
        {"name": "browser_file_upload", "inputSchema": {"type": "object"}},
        {"name": "browser_tabs", "inputSchema": {"type": "object"}}])
    assert manager.catalog[0]["function"]["parameters"] == schema
    assert classify_tool("browser_snapshot", {}, tmp_path).effect == "read"
    assert classify_tool("browser_get_context", {}, tmp_path).effect == "read"
    assert classify_tool("browser_click", {"target": "e3"}, tmp_path).effect == "external_write"
    assert classify_tool("browser_tabs", {"action": "list"}, tmp_path).effect == "read"
    assert classify_tool("browser_tabs", {"action": "close", "index": 0}, tmp_path).effect == "external_write"
    assert classify_tool("browser_file_upload", {"paths": [str(tmp_path / '.env')]}, tmp_path).effect == "credential"
    snapshot_write = classify_tool("browser_snapshot", {"filename": "page.md"}, tmp_path)
    normal_write = classify_tool("write_file", {"path": "page.md", "content": ""}, tmp_path)
    assert (snapshot_write.action, snapshot_write.effect, snapshot_write.resource) == (normal_write.action, normal_write.effect, normal_write.resource)


def test_real_node_runtime_catalog_and_shutdown(tmp_path):
    plugin = load_plugin(ROOT / "plugins" / "browser-use")
    host = _module(plugin)
    async def scenario():
        runtime = host.BrowserManager.__init__.__globals__["BrowserRuntime"]("fixture", host.extension_origin(), tmp_path)
        await runtime.start()
        process = runtime.process
        try:
            tools = await runtime.request("catalog")
            names = {tool["name"] for tool in tools}
            assert {"browser_get_context", "browser_click", "browser_snapshot", "browser_tabs"} <= names
            assert not {"browser_action", "browser_files", "browser_evaluate", "browser_run_code"} & names
            state = await runtime.request("status")
            assert state["port"] > 0 and not state["connected"]
        finally:
            await runtime.close()
        assert process.returncode == 0
    asyncio.run(scenario())


def test_message_attachment_ids_cannot_select_arbitrary_paths_or_other_owners(composed):
    from session_control.attachments import prepare_message_attachments
    from session_control.errors import ControlError
    principal = Principal('browser-caller')
    for value in ({}, None, '', [{'path': str(composed.root / 'private.txt')}], [{'id': 'missing'}]):
        with pytest.raises(ControlError):
            prepare_message_attachments(principal, {'message': 'read', 'attachments': value}, composed.store)
    path = composed.root / 'uploaded.txt'
    path.write_text('User-provided text', encoding='utf-8')
    composed.store.put('message_uploads', 'other-owner', {'owner': 'someone-else', 'path': str(path), 'name': path.name})
    with pytest.raises(ControlError, match='unavailable'):
        prepare_message_attachments(principal, {'message': 'read', 'attachments': [{'id': 'other-owner'}]}, composed.store)
    composed.store.put('message_uploads', 'owned-file', {'owner': principal.id, 'path': str(path), 'name': path.name})
    prepared = prepare_message_attachments(principal, {'message': 'read', 'attachments': [{'id': 'owned-file'}]}, composed.store)
    assert 'uploaded.txt' in __import__('json').dumps(prepared['_legacy_user_content'])


def test_extension_identity_matches_the_shipped_manifest():
    import base64
    import json
    manifest = json.loads((ROOT / 'browser-extension/public/manifest.json').read_text(encoding='utf-8'))
    fingerprint = hashlib.sha256(base64.b64decode(manifest['key'])).hexdigest()[:32]
    identity = ''.join(chr(ord('a') + int(char, 16)) for char in fingerprint)
    plugin = load_plugin(ROOT / 'plugins/browser-use')
    assert _module(plugin).extension_origin() == 'chrome-extension://' + identity


def test_shared_media_requires_identity_and_a_grant_or_history_reference(browser_host, monkeypatch, tmp_path):
    import attachments
    import attachments.registry
    host, c = browser_host
    sid, *_ = c.manager.get_or_create_session()
    image_id = 'a' * 64
    class Store:
        async def read_image(self, _ref): return SimpleNamespace(data=b'image-bytes')
        def ref_by_id(self, identity):
            if identity != image_id: raise ValueError('unknown')
            return {'attachmentId': identity, 'mediaType': 'image/png'}
    monkeypatch.setattr(attachments, 'get_attachment_store', lambda _root: Store())
    monkeypatch.setattr(attachments.registry, 'AttachmentRegistry', lambda _store: SimpleNamespace(allowed=lambda *_: False))
    original_read = c.control.service._read
    visible = []
    async def read(principal, method, params):
        if method == 'session.history': return {'events': visible, 'has_older': False}
        return await original_read(principal, method, params)
    monkeypatch.setattr(c.control.service, '_read', read)
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=c.app), base_url='http://127.0.0.1') as client:
            origin = {'Origin': host.extension_origin()}
            code = (await client.post('/api/browser/v1/pairings', headers={'Origin': 'http://127.0.0.1'}, json={})).json()['code']
            issued = (await client.post('/api/browser/v1/claim', headers=origin, json={'code': code})).json()
            path = '/api/browser/v1/media'
            params = {'session_id': sid, 'attachment_id': image_id}
            assert (await client.get(path, params=params, headers=origin)).status_code == 401
            headers = {**origin, 'Authorization': 'Bearer ' + issued['token']}
            assert (await client.get(path, params=params, headers=headers)).status_code == 404
            visible.append({'type': 'user', 'content': [{'type': 'image', 'attachment': {'attachmentId': image_id}}]})
            response = await client.get(path, params=params, headers=headers)
            assert response.status_code == 200 and response.content == b'image-bytes'
            assert response.headers['cache-control'] == 'no-store'
            c.control.identities.remote.revoke_device(issued['browser_id'])
            assert (await client.get(path, params=params, headers=headers)).status_code == 401
    asyncio.run(scenario())


def test_sidebar_permission_and_token_adapters_are_authenticated_scoped_and_confirmed(browser_host, monkeypatch):
    import sys
    import security
    from fastapi.responses import JSONResponse
    host, c = browser_host
    sid, *_ = c.manager.get_or_create_session()
    state = {"mode": "ask_for_approval"}
    calls = []
    def status(_sid):
        return {**state, "mode_scope": "global", "security_enabled": True,
                "available_modes": {key: True for key in ("ask_for_approval", "approve_for_me", "full_access")}}
    monkeypatch.setattr(security, "security_status_for_session", status)
    async def tokens(target):
        assert target == sid
        return JSONResponse({"ok": True, "estimated": 40960, "threshold": 128000, "breakdown": {"tools": 6000}})
    async def change(target, mode):
        calls.append((target, mode))
        state["mode"] = mode
        return status(target)
    monkeypatch.setitem(sys.modules, "webui", SimpleNamespace(get_session_context_tokens=tokens, _apply_session_permission_mode=change))
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=c.app), base_url='http://127.0.0.1') as client:
            code = (await client.post('/api/browser/v1/pairings', headers={'Origin': 'http://127.0.0.1'}, json={})).json()['code']
            issued = (await client.post('/api/browser/v1/claim', headers={'Origin': host.extension_origin()}, json={'code': code})).json()
            headers = {'Origin': host.extension_origin(), 'Authorization': 'Bearer ' + issued['token']}
            assert (await client.post('/api/browser/v1/session-state', json={'session_id': sid})).status_code == 403
            result = await client.post('/api/browser/v1/session-state', headers=headers, json={'session_id': sid})
            assert result.json()['context_tokens']['estimated'] == 40960
            assert result.json()['permissions']['can_change'] is True
            empty = await client.post('/api/browser/v1/session-state', headers=headers, json={})
            assert empty.json()['permissions']['can_change'] is False and empty.json()['context_tokens'] is None
            params = {'session_id': sid, 'mode': 'full_access'}
            assert (await client.post('/api/browser/v1/permissions', headers=headers, json=params)).status_code == 409
            assert calls == []
            result = await client.post('/api/browser/v1/permissions', headers=headers, json={**params, 'confirmed_full_access': True})
            assert result.json()['permissions']['mode'] == 'full_access' and calls == [(sid, 'full_access')]
            result = await client.post('/api/browser/v1/session-state', headers=headers, json={'session_id': sid})
            assert result.json()['permissions']['mode'] == 'full_access'
            principal = c.control.identities.authenticate(issued['token'])
            from dataclasses import replace
            scoped = replace(principal, policy={**principal.policy, 'scope': 'sessions', 'session_ids': [sid]})
            limited = c.control.identities.issue(scoped)
            result = await client.post('/api/browser/v1/permissions', headers={**headers, 'Authorization': 'Bearer ' + limited}, json={**params, 'confirmed_full_access': True})
            assert result.status_code == 403 and len(calls) == 1
    asyncio.run(scenario())


def test_sidebar_files_allow_workspace_and_actual_attachments_but_reject_unrelated_paths(browser_host, monkeypatch, tmp_path):
    import attachments
    host, c = browser_host
    sid, *_ = c.manager.get_or_create_session()
    # Session work_dir defaults to the composed fixture's isolated root.
    document = c.root / 'guide.md'
    document.write_bytes(b'# Hello\n\n**Markdown**')
    store = attachments.get_attachment_store(c.root)
    file_ref = store.save_file_sync('attached.md', b'# Stored attachment')
    outside = c.root.parent / (c.root.name + '-outside.txt')
    outside.write_text('private unrelated file', encoding='utf-8')
    visible = []
    original = c.control.service._read
    async def read(principal, method, params):
        if method == 'session.history': return {'events': visible, 'has_older': False}
        return await original(principal, method, params)
    monkeypatch.setattr(c.control.service, '_read', read)
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=c.app), base_url='http://127.0.0.1') as client:
            code = (await client.post('/api/browser/v1/pairings', headers={'Origin': 'http://127.0.0.1'}, json={})).json()['code']
            issued = (await client.post('/api/browser/v1/claim', headers={'Origin': host.extension_origin()}, json={'code': code})).json()
            auth = {'Authorization': 'Bearer ' + issued['token']}
            params = {'session_id': sid, 'rel': 'guide.md'}
            assert (await client.get('/api/browser/v1/files', params=params)).status_code == 401
            response = await client.get('/api/browser/v1/files', headers=auth, params=params)
            assert response.status_code == 200 and response.text == '# Hello\n\n**Markdown**'
            assert response.headers['x-file-name'] == 'guide.md'
            assert (await client.get('/api/browser/v1/files', headers=auth, params={**params, 'rel': str(outside)})).status_code == 403
            # Tool arguments are not attachment grants.
            visible.append({'type': 'tool_call', 'arguments': {'path': str(outside)}})
            assert (await client.get('/api/browser/v1/files', headers=auth, params={**params, 'rel': str(outside)})).status_code == 403
            visible.append({'type': 'user', 'content': [{'type': 'local_file', 'local_file': {'path': str(outside), 'name': outside.name}}]})
            response = await client.get('/api/browser/v1/files', headers=auth, params={**params, 'rel': str(outside)})
            assert response.status_code == 200
            assert (await client.get('/api/browser/v1/files', headers={**auth, 'Origin': 'https://foreign.test'}, params=params)).status_code == 403
            assert (await client.get('/api/browser/v1/files', headers=auth, params={'session_id': sid, 'attachment_id': 'f' * 64})).status_code == 404
            visible.append({'type': 'final', 'content': [{'type': 'file', 'attachment': file_ref}]})
            response = await client.get('/api/browser/v1/files', headers=auth, params={'session_id': sid, 'attachment_id': file_ref['attachmentId']})
            assert response.status_code == 200 and response.text == '# Stored attachment'
    asyncio.run(scenario())


def test_sidebar_directory_links_list_authorized_children_and_reject_parent_escape(browser_host):
    host,c=browser_host
    sid,*_=c.manager.get_or_create_session()
    folder=c.root/'workspace'/'zen-gate (旧)'
    folder.mkdir(parents=True)
    (folder/'说明 文档.md').write_text('# 本地文件',encoding='utf-8')
    (folder/'子目录').mkdir()
    outside=c.root.parent/(c.root.name+'-outside-folder')
    outside.mkdir()
    (outside/'private.txt').write_text('private',encoding='utf-8')
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=c.app),base_url='http://127.0.0.1') as client:
            code=(await client.post('/api/browser/v1/pairings',headers={'Origin':'http://127.0.0.1'},json={})).json()['code']
            issued=(await client.post('/api/browser/v1/claim',headers={'Origin':host.extension_origin()},json={'code':code})).json()
            auth={'Authorization':'Bearer '+issued['token']}
            params={'session_id':sid,'rel':str(folder)}
            assert (await client.get('/api/browser/v1/files',params=params)).status_code==401
            result=await client.get('/api/browser/v1/files',params=params,headers=auth)
            assert result.status_code==200
            assert result.headers['x-resource-type']=='directory'
            assert result.json()['entries']==[{'name':'子目录','type':'directory'},{'name':'说明 文档.md','type':'file'}]
            assert Path(result.json()['parent'])==folder.parent
            child=await client.get('/api/browser/v1/files',params={**params,'rel':str(folder/'说明 文档.md')},headers=auth)
            assert child.status_code==200 and child.text=='# 本地文件'
            root=await client.get('/api/browser/v1/files',params={**params,'rel':str(c.root)},headers=auth)
            assert root.json()['parent'] is None
            denied=await client.get('/api/browser/v1/files',params={**params,'rel':str(outside)},headers=auth)
            assert denied.status_code==403
            for index in range(205): (folder/f'entry-{index}.txt').touch()
            limited=await client.get('/api/browser/v1/files',params=params,headers=auth)
            assert limited.json()['truncated'] and len(limited.json()['entries'])==200
    asyncio.run(scenario())


def test_real_multipart_image_upload_reads_and_admits_the_same_stored_ref(browser_host, monkeypatch):
    import io
    from PIL import Image
    import webui
    import agent_harness
    import session_control.integration
    from session_control.attachments import prepare_message_attachments
    host, c = browser_host
    monkeypatch.setattr(session_control.integration, '_application', c.control)
    monkeypatch.setattr(webui, 'WORK_DIR', c.root)
    monkeypatch.setattr(agent_harness, 'WORK_DIR', c.root)
    sid, *_ = c.manager.get_or_create_session()
    image = io.BytesIO()
    Image.new('RGB', (3, 2), 'blue').save(image, format='PNG')
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=c.app), base_url='http://127.0.0.1') as client:
            code = (await client.post('/api/browser/v1/pairings', headers={'Origin': 'http://127.0.0.1'}, json={})).json()['code']
            origin = {'Origin': host.extension_origin()}
            issued = (await client.post('/api/browser/v1/claim', headers=origin, json={'code': code})).json()
            headers = {**origin, 'Authorization': 'Bearer ' + issued['token']}
            uploaded = await client.post('/api/browser/v1/uploads', params={'session_id': sid}, headers=headers,
                files=[('files', ('reference.png', image.getvalue(), 'image/png'))])
            assert uploaded.status_code == 200, uploaded.text
            item = uploaded.json()['files'][0]
            assert set(item) == {'id', 'name', 'size'}
            principal = c.control.identities.authenticate(issued['token'])
            prepared = prepare_message_attachments(principal, {'message': '查看图片', 'attachments': [{'id': item['id']}]}, c.control.store)
            ref = next(block['attachment'] for block in prepared['_legacy_user_content'] if block['type'] == 'image')
            response = await client.get('/api/browser/v1/media', params={'session_id': sid, 'attachment_id': ref['attachmentId']}, headers=headers)
            assert response.status_code == 200
            assert Image.open(io.BytesIO(response.content)).size == (3, 2)
    asyncio.run(scenario())


def test_extension_message_commits_to_shared_runtime_and_history(browser_host):
    host, c = browser_host
    async def scenario():
        await c.control.start()
        try:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=c.app), base_url='http://127.0.0.1') as client:
                pairing = await client.post('/api/browser/v1/pairings', headers={'Origin': 'http://127.0.0.1'}, json={})
                claim = await client.post('/api/browser/v1/claim', headers={'Origin': host.extension_origin()}, json={'code': pairing.json()['code']})
                headers = {'Authorization': 'Bearer ' + claim.json()['token']}
                async def call(method, params, key):
                    response = await client.post('/api/control/v1/rpc', headers=headers, json={'method': method, 'params': params, 'idempotency_key': key})
                    assert response.status_code == 200, response.text
                    return response.json()['data']
                created = await call('session.create', {'name': '扩展共享会话', 'work_dir': str(c.root)}, 'create')
                sid = created['session_id']
                sent = await call('session.send', {'session_id': sid, 'message': '来自扩展的消息'}, 'send')
                finished = await call('operation.wait', {'id': sent['operation_id'], 'timeout': 10}, 'wait')
                assert finished['status'] == 'succeeded'
                history = await call('session.history', {'session_id': sid, 'turns': 5}, 'history')
                import json
                assert any(event.get('type') == 'user' and '来自扩展的消息' in json.dumps(event.get('content'), ensure_ascii=False) for event in history['events']), json.dumps(history, ensure_ascii=True)
                from runtime_v2.ui_projection import RuntimeUiProjection
                main_ui_page = RuntimeUiProjection(c.manager.sessions_dir, path_resolver=c.manager._resolve_session_path).read_ui_page(sid, turns=5)
                assert history['events'] == main_ui_page['events']
                assert any(event.get('type') == 'final' and 'answer:来自扩展的消息' in json.dumps(event.get('content'), ensure_ascii=False) for event in main_ui_page['events'])
                assert c.manager.get_session_summary(sid)['name'] == '扩展共享会话'
        finally:
            await c.control.close()
    asyncio.run(scenario())


def test_websocket_subscription_ack_live_events_and_revocation(browser_host, monkeypatch):
    from starlette.testclient import TestClient
    from starlette.websockets import WebSocketDisconnect
    from session_event_bus import publish_session_event, close_session_stream
    host, c = browser_host
    async def pair():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=c.app), base_url='http://127.0.0.1') as client:
            code = (await client.post('/api/browser/v1/pairings', headers={'Origin': 'http://127.0.0.1'}, json={})).json()['code']
            return (await client.post('/api/browser/v1/claim', headers={'Origin': host.extension_origin()}, json={'code': code})).json()
    issued = asyncio.run(pair())
    sid, *_ = c.manager.get_or_create_session()
    class LocalService:
        async def call(self, fn, *args):
            return await fn(*args)
    async def ensure(_record):
        return SimpleNamespace(relay_url=lambda: 'ws://127.0.0.1:1/extension?token=fixture')
    monkeypatch.setattr(host, '_manager', SimpleNamespace(enabled=lambda: True, ensure=ensure, service=LocalService(), bindings={}))
    async def loopback_app(scope, receive, send):
        await c.app({**scope, 'client': ('127.0.0.1', 12345)}, receive, send)
    observers_before = len(c.manager._session_state_listeners)
    with TestClient(loopback_app) as client:
        with client.websocket_connect('/api/browser/v1/ws', headers={'Origin': host.extension_origin()}) as ws:
            ws.send_json({'type': 'hello', 'token': issued['token'], 'browser_id': issued['browser_id']})
            assert ws.receive_json()['type'] == 'ready'
            ws.send_json({'type': 'subscribe', 'session_id': 'missing-session'})
            missing = ws.receive_json()
            assert missing['type'] == 'session.error' and missing['session_id'] == 'missing-session'
            ws.send_json({'type': 'subscribe', 'session_id': sid})
            assert ws.receive_json() == {'type': 'subscribed', 'session_id': sid}
            initial = ws.receive_json()
            assert initial['type'] == 'session.metadata' and initial['session']['id'] == sid
            client.portal.call(publish_session_event, sid, {'type': 'llm_response_delta', 'delta': '实时正文', 'run_id': 'test-run', 'ephemeral': True})
            event = ws.receive_json()
            assert event['type'] == 'session.event' and event['event']['delta'] == '实时正文'
            assert event['event']['event_bus_epoch']
            for turn in ('second-run', 'third-run'):
                client.portal.call(close_session_stream, sid)
                client.portal.call(publish_session_event, sid, {'type':'llm_response_delta','run_id':turn,'delta':turn,'ephemeral':True})
                event = ws.receive_json()
                assert event['type']=='session.event' and event['event']['run_id']==turn
            client.portal.call(close_session_stream, sid)
            c.manager.set_session_name(sid, '回复结束后异步命名')
            metadata = ws.receive_json()
            assert metadata['type']=='session.metadata' and metadata['session']['name']=='回复结束后异步命名'
            client.portal.call(publish_session_event, sid, {'type':'permission_mode_changed','mode':'approve_for_me','ephemeral':True})
            assert ws.receive_json()['event']['mode']=='approve_for_me'
            c.control.identities.remote.revoke_device(issued['browser_id'])
            ws.send_json({'type': 'ping'})
            with pytest.raises(WebSocketDisconnect) as closed:
                ws.receive_json()
            assert closed.value.code == 4401
    assert len(c.manager._session_state_listeners) == observers_before


def test_websocket_restores_durable_tool_drafts_output_and_final_results(browser_host, monkeypatch):
    from starlette.testclient import TestClient
    from starlette.websockets import WebSocketDisconnect
    from runtime_v2.execution_journal import ExecutionJournal
    host, c = browser_host
    async def pair():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=c.app), base_url='http://127.0.0.1') as client:
            code = (await client.post('/api/browser/v1/pairings', headers={'Origin': 'http://127.0.0.1'}, json={})).json()['code']
            return (await client.post('/api/browser/v1/claim', headers={'Origin': host.extension_origin()}, json={'code': code})).json()
    issued = asyncio.run(pair())
    sid, *_ = c.manager.get_or_create_session()
    journal = ExecutionJournal(c.manager.sessions_dir, path_resolver=c.manager._resolve_session_path)
    base = {'run_id': 'stream-tools', 'react_iter': 1, 'stream_seq': 8, 'tool_call_index': 0, 'tool_call_id': 'a'}
    journal.record(sid, {**base, 'type': 'tool_call_delta', 'id': 'a', 'index': 0, 'name_delta': 'run_shell', 'arguments_delta': '{"command":"echo hi"}', 'delta_seq': 1})
    journal.record(sid, {**base, 'type': 'tool_pending', 'tool': 'run_shell', 'args': {'command': 'echo hi'}})
    journal.record(sid, {**base, 'type': 'tool_execution_state', 'status': 'running', 'started_at': 1000})
    journal.record(sid, {**base, 'type': 'tool_command_delta', 'delta': 'hi\n', 'raw_delta': 'hi\n', 'delta_seq': 1})
    class LocalService:
        async def call(self, fn, *args):
            return await fn(*args)
    async def ensure(_record):
        return SimpleNamespace(relay_url=lambda: 'ws://127.0.0.1:1/extension?token=fixture')
    monkeypatch.setattr(host, '_manager', SimpleNamespace(enabled=lambda: True, ensure=ensure, service=LocalService(), bindings={}))
    active = [True]
    monkeypatch.setattr(c.control.service.deps, 'is_stream_active', lambda _: active[0])
    async def loopback_app(scope, receive, send):
        await c.app({**scope, 'client': ('127.0.0.1', 12345)}, receive, send)
    with TestClient(loopback_app) as client:
        with client.websocket_connect('/api/browser/v1/ws', headers={'Origin': host.extension_origin()}) as ws:
            ws.send_json({'type': 'hello', 'token': issued['token'], 'browser_id': issued['browser_id']})
            assert ws.receive_json()['type'] == 'ready'
            def restore():
                ws.send_json({'type': 'subscribe', 'session_id': sid})
                assert ws.receive_json() == {'type': 'subscribed', 'session_id': sid}
                messages = [ws.receive_json(), ws.receive_json()]
                snapshot = next(item for item in messages if item['type'] == 'session.executions')
                assert snapshot['session_id'] == sid
                return snapshot['records'][0]
            row = restore()
            assert row['arguments_raw'] == '{"command":"echo hi"}'
            assert row['args'] == {'command': 'echo hi'}
            assert row['output'] == 'hi\n' and row['status'] == 'running'
            assert row['execution_started_at'] == 1000
            assert row['last_tool_command_delta_delta_seq'] == 1 and row['last_tool_call_delta_delta_seq'] == 1
            active[0] = False
            assert restore()['status'] == 'unknown'
            journal.record(sid, {**base, 'type': 'tool_call', 'tool': 'run_shell', 'args': {'command': 'echo hi'}, 'result': 'hi\n', 'status': {'ok': True, 'duration_ms': 120}})
            row = restore()
            assert row['status'] == 'completed' and row['result'] == 'hi\n'
            assert row['output'] == 'hi\n' and row['duration_ms'] == 120
            # Finish the server task before TestClient tears down its portal.
            # Otherwise the transport's cancel scope can race normal cleanup.
            c.control.identities.remote.revoke_device(issued['browser_id'])
            ws.send_json({'type': 'ping'})
            with pytest.raises(WebSocketDisconnect):
                ws.receive_json()


def test_websocket_sidebar_focus_is_scoped_authenticated_and_cleared_on_revoke(browser_host, monkeypatch):
    from starlette.testclient import TestClient
    from starlette.websockets import WebSocketDisconnect
    import webui
    host, c = browser_host
    monkeypatch.setattr(webui, '_ui_attention_surfaces', {})
    async def pair():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=c.app), base_url='http://127.0.0.1') as client:
            code = (await client.post('/api/browser/v1/pairings', headers={'Origin':'http://127.0.0.1'}, json={})).json()['code']
            return (await client.post('/api/browser/v1/claim', headers={'Origin':host.extension_origin()}, json={'code':code})).json()
    issued = asyncio.run(pair())
    class LocalService:
        async def call(self, fn, *args): return await fn(*args)
    async def ensure(_record): return SimpleNamespace(relay_url=lambda:'ws://127.0.0.1:1/extension?token=fixture')
    monkeypatch.setattr(host, '_manager', SimpleNamespace(enabled=lambda:True,ensure=ensure,service=LocalService(),bindings={}))
    async def loopback_app(scope, receive, send): await c.app({**scope,'client':('127.0.0.1',12345)},receive,send)
    with TestClient(loopback_app) as client:
        with client.websocket_connect('/api/browser/v1/ws', headers={'Origin':host.extension_origin()}) as ws:
            ws.send_json({'type':'hello','token':issued['token'],'browser_id':issued['browser_id']})
            assert ws.receive_json()['type']=='ready'
            def focus(identity, active):
                ws.send_json({'type':'ui.presence','id':identity,'active':active})
                ws.send_json({'type':'ping'})
                assert ws.receive_json()['type']=='pong'
            focus('panel-a',True)
            focus('panel-b',True)
            assert len(webui._ui_attention_surfaces)==2
            focus('panel-a',False)
            assert len(webui._ui_attention_surfaces)==1
            c.control.identities.remote.revoke_device(issued['browser_id'])
            ws.send_json({'type':'ui.presence','id':'panel-b','active':True})
            with pytest.raises(WebSocketDisconnect): ws.receive_json()
        assert webui._ui_attention_surfaces=={}


def test_persistent_session_subscription_survives_turn_close_without_changing_chat_stream():
    from session_event_bus import subscribe_session_events, publish_session_event, close_session_stream
    async def scenario():
        sid = 'persistent-turn-boundary-test'
        normal = subscribe_session_events(sid, replay_recent=False)
        persistent = subscribe_session_events(sid, replay_recent=False, persistent=True)
        first = asyncio.create_task(anext(normal)); lasting = asyncio.create_task(anext(persistent))
        await asyncio.sleep(0)
        await close_session_stream(sid)
        assert await first is None
        await publish_session_event(sid, {'type':'user','content':'第二轮','run_id':'two'})
        assert (await lasting)['run_id']=='two'
        next_event = asyncio.create_task(anext(persistent)); await asyncio.sleep(0)
        await close_session_stream(sid)
        await publish_session_event(sid, {'type':'permission_mode_changed','mode':'full_access','ephemeral':True})
        assert (await next_event)['mode']=='full_access'
        await normal.aclose(); await persistent.aclose()
    asyncio.run(scenario())


def test_queued_browser_call_rechecks_authorized_permission_mode(monkeypatch, tmp_path):
    import security.runtime
    host = _module(load_plugin(ROOT / 'plugins/browser-use'))
    mode = ['full_access']
    monkeypatch.setattr(security.runtime, 'session_permission_mode', lambda _: mode[0])
    async def scenario():
        started, release = asyncio.Event(), asyncio.Event()
        calls = []
        class Runtime:
            tool_gate = asyncio.Lock()
            async def request(self, method, params):
                calls.append((method, params['run_id'])); started.set(); await release.wait()
                return {'content': []}
        manager = host.BrowserManager(None)
        monkeypatch.setattr(manager, 'enabled', lambda: True)
        manager.default_browser = 'browser'
        manager.runtimes['browser'] = Runtime()
        def context(run):
            return SimpleNamespace(session_id=run, run_id=run, state={}, services={'security_workspace': tmp_path}, service=lambda _: 'browser_snapshot')
        first = asyncio.create_task(manager._call(context('first'), {}, 'full_access'))
        await started.wait()
        second = asyncio.create_task(manager._call(context('second'), {}, 'full_access'))
        await asyncio.sleep(0)
        mode[0] = 'request_approval'
        release.set()
        await first
        with pytest.raises(PermissionError, match='queued'):
            await second
        assert calls == [('call', 'first')]
    asyncio.run(scenario())


def test_default_browser_changes_only_apply_to_the_next_run(monkeypatch, tmp_path):
    import security.runtime
    host = _module(load_plugin(ROOT / 'plugins/browser-use'))
    monkeypatch.setattr(security.runtime, 'session_permission_mode', lambda _: 'full_access')
    async def scenario():
        called = []
        class Runtime:
            def __init__(self, name): self.name, self.tool_gate = name, asyncio.Lock()
            async def request(self, _method, _params): called.append(self.name); return {'content': []}
        manager = host.BrowserManager(None)
        monkeypatch.setattr(manager, 'enabled', lambda: True)
        manager.runtimes = {'a': Runtime('a'), 'b': Runtime('b')}
        manager.default_browser = 'a'
        def context(run):
            return SimpleNamespace(session_id='same-session', run_id=run, state={}, services={'security_workspace': tmp_path}, service=lambda _: 'browser_snapshot')
        await manager._call(context('run-one'), {}, 'full_access')
        manager.default_browser = 'b'
        await manager._call(context('run-one'), {}, 'full_access')
        await manager._call(context('run-two'), {}, 'full_access')
        assert called == ['a', 'a', 'b']
    asyncio.run(scenario())
