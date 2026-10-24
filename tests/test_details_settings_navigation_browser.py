"""Settings page links delegate to the main sidebar and keep embedded configuration local."""
import json
import pytest

from tests.test_settings_center_browser import browser_page, settings_page


@pytest.fixture
def plugin_settings_page(settings_page):
    page, requests = settings_page
    row = {'slot': 'details.tab', 'plugin_id': 'demo', 'id': 'main', 'title': 'Demo page',
           'target': 'plugin-page', 'href': '/plugins/demo', 'scope': 'app'}
    def respond(route):
        route.fulfill(content_type='application/json', body=json.dumps({'ok': True,
            'plugins': [{'id': 'demo', 'name': 'Demo', 'loaded': True}],
            'ui_contributions': [row, {**row, 'slot': 'navigation', 'label': 'Demo page'}]}))
    page.route('**/api/extensions', respond)
    page.route('**/api/plugins/catalog', respond)
    def main_page(route):
        route.fulfill(content_type='text/html', body='<title>Main page</title>')
    page.route('**/?open_plugin=*', main_page)
    page.reload()
    page.locator('[data-env-key="FOO"]').wait_for()
    yield page, requests
    page.unroute('**/api/extensions', respond)
    page.unroute('**/api/plugins/catalog', respond)
    page.unroute('**/?open_plugin=*', main_page)


def test_standalone_settings_page_uses_a_main_page_deep_link(plugin_settings_page):
    page, _requests = plugin_settings_page
    page.evaluate("MyAgentSettings.showSection('plugins',{force:true})")
    link = page.locator('a[href="/plugins/demo"]')
    link.wait_for()
    with page.expect_navigation():
        link.click()
    assert page.url == 'http://settings.test/?open_plugin=demo'


def test_embedded_settings_opens_the_main_sidebar_and_rejects_other_senders(plugin_settings_page):
    page, _requests = plugin_settings_page
    page.goto('http://settings.test/host')
    page.evaluate("window.openedPlugins=[];window.MyAgentDock={openPluginPage:id=>openedPlugins.push(id)};openSettingsCenter('plugins')")
    page.frame_locator('#settings-center-frame').locator('a[href="/plugins/demo"]').wait_for()
    page.evaluate("window.postMessage({type:'myagent:settings-open-plugin',pluginId:'demo'},location.origin)")
    page.wait_for_timeout(50)
    assert page.evaluate('openedPlugins') == []
    page.frame_locator('#settings-center-frame').locator('a[href="/plugins/demo"]').click()
    page.wait_for_function("openedPlugins.length===1 && document.getElementById('settings-center-overlay').hidden")
    assert page.evaluate('openedPlugins') == ['demo']


def test_embedded_configuration_stays_in_settings(plugin_settings_page):
    page, _requests = plugin_settings_page
    page.goto('http://settings.test/host')
    page.evaluate("window.openedPlugins=[];window.MyAgentDock={openPluginPage:id=>openedPlugins.push(id)};openSettingsCenter('plugins')")
    frame = page.frame_locator('#settings-center-frame')
    frame.locator('a[href="/plugins/demo"]').wait_for()
    child = page.locator('#settings-center-frame').element_handle().content_frame()
    child.evaluate("""MyAgentSettings.syncPluginSections({ui_contributions:[{
      slot:'settings.section',plugin_id:'demo',id:'accounts',title:'Accounts',target:'plugin-page',
      href:'/plugins/demo',embedded:true}]})""")
    frame.locator('a[href="/plugins/demo"]').click()
    assert child.evaluate('MyAgentSettings.currentSection') == 'plugin:demo:accounts'
    assert page.evaluate('openedPlugins') == []
    assert not page.locator('#settings-center-overlay').is_hidden()


def test_unsaved_settings_can_cancel_a_plugin_page_open(plugin_settings_page):
    page, _requests = plugin_settings_page
    page.locator('[data-env-key="FOO"]').fill('unsaved')
    page.evaluate("const link=document.createElement('a');link.href='/plugins/demo';link.id='open-page';link.textContent='Open';document.body.append(link)")
    page.once('dialog', lambda dialog: dialog.dismiss())
    page.locator('#open-page').click()
    assert page.url.endswith('/settings#env')
    assert page.locator('[data-env-key="FOO"]').input_value() == 'unsaved'
