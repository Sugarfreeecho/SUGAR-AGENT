"""Browser setup mounts inside the real Settings shell using native controls."""
import json
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from tests.test_workflow_consoles_browser import consoles, browser_page

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def browser_settings(consoles):
    from plugins import load_plugin, plugin_ui_contributions
    c, page = consoles, consoles.page
    rows = list(plugin_ui_contributions(load_plugin(ROOT / 'plugins/browser-use')))
    rows += list(plugin_ui_contributions(load_plugin(ROOT / 'plugins/agent-goal')))
    state = dict(enabled=False, installed=False, devices=[], default='', calls=[], available=False)
    def send(route, data, status=200):
        route.fulfill(status=status, content_type='application/json', body=json.dumps(data))
    def catalog(route):
        send(route, {'ok': True, 'plugins': [{'id': 'browser-use', 'enabled': state['enabled']}],
                     'enabled': {'plugins': True}, 'ui_contributions': rows})
    page.route('**/api/extensions', catalog)
    page.route('**/api/plugins/catalog', catalog)
    def enable(route):
        state['enabled'] = True
        state['calls'].append('enable')
        send(route, {'ok': True})
    page.route('**/api/plugins/browser-use/enabled', enable)
    def api(route):
        path = urlsplit(route.request.url).path
        state['calls'].append(path)
        if not state['enabled'] and path.endswith(('/setup', '/status')):
            return send(route, {}, 404)
        if path.endswith('/setup'):
            return send(route, dict(plugin_enabled=True, node_available=True, runtime_installed=state['installed'],
                runtime_bundled=False, installation={'status': 'idle'}, extension_ready=True, download_ready=True,
                extension_directory='D:/SugarAgent/browser-extension/dist', version='0.6.10'))
        if path.endswith('/status'):
            return send(route, {'devices': state['devices'], 'default_browser': state['default']})
        if path.endswith('/setup/install'):
            state['installed'] = True
        if path.endswith('/pairings'):
            state['pair_name'] = route.request.post_data_json['name']
            return send(route, {'code': 'NATIVE-1234'})
        if path.endswith('/default'):
            state['default'] = route.request.post_data_json['browser_id']
        if path.endswith('/revoke'):
            state['devices'] = []
        send(route, {'ok': True})
    page.route('**/api/browser/v1/**', api)
    def lifecycle(route):
        path = urlsplit(route.request.url).path
        if path.endswith('/status'):
            return send(route, {'restart_available': True, 'ui_token': 'fixture-token'})
        if path.endswith('/decision'):
            state['calls'].append(route.request.post_data_json['decision'])
            return send(route, {'operation': {}})
        send(route, {'operation': {'restart_id': 'native-test', 'request_digest': 'fixture-digest',
                                 'impact': {'running_tasks': 2, 'background_jobs': 1}}})
    page.route('**/api/lifecycle/**', lifecycle)
    page.goto('http://127.0.0.1/settings?embedded=1#plugin:browser-use:browser')
    root = page.locator('.browser-settings')
    root.get_by_role('button', name='启用插件', exact=True).wait_for()
    yield c, page, root, state


def test_native_browser_settings_uses_host_cards_fonts_themes_and_single_scroll(browser_settings):
    c, page, root, state = browser_settings
    assert page.locator('#st-body iframe').count() == 0
    assert root.locator('.st-card').count() == 5
    assert root.locator('h1').count() == 0
    assert page.locator('link[href*="browser-use/style.css"]').count() == 0
    for theme in ('light', 'dark', 'purple'):
        page.evaluate("theme=>{document.documentElement.classList.remove('theme-light','theme-dark','theme-purple');document.documentElement.classList.add('theme-'+theme)}", theme)
        for size in (12, 16, 20):
            page.evaluate('size=>MyAgentSettings.applyStFontSize(size)', size)
            assert root.locator('.step-heading strong').first.evaluate('node=>getComputedStyle(node).fontSize') == root.evaluate('node=>getComputedStyle(node).fontSize')
            assert root.locator('#name').evaluate('node=>getComputedStyle(node).height') == '32px'
        assert root.evaluate("node=>{const card=node.querySelector('.st-card'),probe=document.createElement('i');probe.style.background='var(--st-card)';node.append(probe);const same=getComputedStyle(card).backgroundColor===getComputedStyle(probe).backgroundColor;probe.remove();return same}")
    page.evaluate('MyAgentSettings.applyStFontSize(14)')
    for width in (1100, 560, 390):
        page.set_viewport_size({'width': width, 'height': 900})
        assert root.evaluate('node=>node.scrollWidth<=node.clientWidth+1')
        assert page.locator('#st-body').evaluate('node=>node.scrollWidth<=node.clientWidth+1')
        assert root.evaluate('node=>getComputedStyle(node).overflowY') == 'visible'
    page.set_viewport_size({'width': 1000, 'height': 900})
    (ROOT / 'browser-extension/artifacts/settings').mkdir(parents=True, exist_ok=True)
    for theme in ('light', 'dark', 'purple'):
        page.evaluate("theme=>{document.documentElement.classList.remove('theme-light','theme-dark','theme-purple');document.documentElement.classList.add('theme-'+theme)}", theme)
        page.screenshot(path=str(ROOT / 'browser-extension/artifacts/settings' / ('native-' + theme + '.png')))


def test_native_browser_setup_keeps_actions_scoped_and_disposes_on_navigation(browser_settings):
    c, page, root, state = browser_settings
    page.clock.install()
    page.evaluate("()=>{const input=document.createElement('input');input.id='name';input.value='host-sentinel';input.hidden=true;document.body.prepend(input)}")
    root.get_by_role('button', name='启用插件', exact=True).click()
    root.get_by_role('button', name='安装运行组件', exact=True).click()
    root.get_by_text('Playwright 运行组件已安装', exact=True).wait_for()
    root.get_by_role('button', name='继续加载扩展 →', exact=True).click()
    root.get_by_role('button', name='Edge', exact=True).click()
    assert root.locator('#edge').get_attribute('aria-pressed') == 'true'
    assert 'is-on' in root.locator('#edge').get_attribute('class')
    assert root.locator('#browser-url').inner_text() == 'edge://extensions'
    root.get_by_role('button', name='已加载扩展，继续配对 →', exact=True).click()
    root.locator('#name').fill('原生设置浏览器')
    root.get_by_role('button', name='生成配对码', exact=True).click()
    root.get_by_text('NATIVE-1234', exact=True).wait_for()
    page.screenshot(path=str(ROOT / 'browser-extension/artifacts/settings/native-pairing.png'))
    assert state['pair_name'] == '原生设置浏览器'
    assert page.locator('body>#name').input_value() == 'host-sentinel'
    state['devices'] = [{'id': 'native-device', 'name': '原生设置浏览器', 'runtime': {'initialized': True}}]
    page.clock.fast_forward(3200)
    root.get_by_text('浏览器与 Agent 已连通', exact=True).wait_for()
    assert root.locator('#code-panel').is_hidden()
    default = root.get_by_role('button', name='设为默认', exact=True)
    assert 'st-btn' in default.get_attribute('class')
    default.click()
    assert state['default'] == 'native-device'
    root.get_by_role('button', name='撤销配对', exact=True).click()
    assert state['devices']
    root.locator('#revoke-dialog').get_by_role('button', name='取消', exact=True).click()
    root.locator('#step-service .step-heading').click()
    root.get_by_role('button', name='重启开发后端', exact=True).click()
    root.locator('#restart-dialog').wait_for()
    root.locator('#restart-dialog').get_by_role('button', name='取消', exact=True).click()
    page.wait_for_function("document.querySelector('.browser-settings #restart-dialog').open===false")
    page.locator('[data-act="nav"][data-id="plugin:agent-goal:main"]').click()
    root.wait_for(state='detached')
    before = state['calls'].count('/api/browser/v1/setup')
    page.clock.fast_forward(10000)
    assert state['calls'].count('/api/browser/v1/setup') == before
    assert 'allow_once' not in state['calls']
    for _ in range(2):
        page.locator('[data-act="nav"][data-id="plugin:browser-use:browser"]').click()
        root.get_by_text('扩展包 v0.6.10', exact=True).wait_for()
        assert root.locator('#code').inner_text() == ''
        assert root.locator('#name').input_value() == '我的浏览器'
        page.locator('[data-act="nav"][data-id="plugin:agent-goal:main"]').click()
        root.wait_for(state='detached')
