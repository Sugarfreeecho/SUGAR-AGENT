"""Exercise real Dock and plugin bridges with real iframe browsing contexts."""
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from tests.test_llm_stream_full_text_browser import browser_page, function_source

ROOT = Path(__file__).resolve().parents[1]
MODULES = ROOT / 'frontend/src/app/modules/dock'


@pytest.fixture
def details_page(browser_page, request):
    page = browser_page
    original_viewport = page.viewport_size
    resizing = getattr(request, 'param', None) == 'resizing'
    if resizing:
        page.set_viewport_size({'width': 1440, 'height': 900})
    calls = []
    errors = []
    def on_error(error):
        errors.append(error)
    page.on('pageerror', on_error)
    bridge = (ROOT / 'app/templates/static/plugin-page-bridge.js').read_text(encoding='utf-8')
    css = (ROOT / 'frontend/src/styles/dock.css').read_text(encoding='utf-8')
    plugin = '''<!doctype html><html><head><script src="/static/plugin-page-bridge.js"></script></head><body>
      <form id="select"><input id="session"><button>Open</button></form><input id="draft">
      <script>window.instance=crypto.randomUUID();window.bound='';
      document.getElementById('select').onsubmit=e=>{e.preventDefault();window.bound=document.getElementById('session').value};
      setInterval(()=>fetch('/tick'),40);</script></body></html>'''

    def route(request):
        path = urlsplit(request.request.url).path
        if path == '/':
            request.fulfill(content_type='text/html', body='<html lang="zh-CN"><body>'
                            '<div id="sessions-list" hidden><div class="session-item active" data-session-id="s1"></div></div>'
                            '<div class="app"><main class="main"></main></div></body></html>')
        elif path.startswith('/plugins/'):
            request.fulfill(content_type='text/html', body=plugin)
        elif path == '/static/plugin-page-bridge.js':
            request.fulfill(content_type='application/javascript', body=bridge)
        elif path == '/static/plugin-page.css':
            request.fulfill(content_type='text/css', body='')
        elif path == '/tick':
            calls.append(request.request.url)
            request.fulfill(body='ok')
        elif path in ['/one', '/two']:
            request.fulfill(content_type='text/html', body='<html><title>Browser</title><a href="/two">Next</a></html>')
        else:
            request.fulfill(status=404)

    page.route('**/*', route)
    page.goto('http://127.0.0.1:8192/')
    page.add_style_tag(content=css + '\nbody{margin:0}.app{display:flex;height:780px}.main{flex:1;min-width:0}')
    if resizing:
        page.evaluate("localStorage.removeItem('myagent-dock-rightbar-width')")
        page.add_style_tag(content='*{box-sizing:border-box}.app{width:100vw;overflow:hidden}#sidebar{width:220px;flex:none}')
        page.evaluate("""() => {
            const sidebar=document.createElement('aside'); sidebar.id='sidebar';
            document.querySelector('.app').prepend(sidebar);
        }""")
    source = '''var currentSessionId='s1',composerDraftRevision=0;
      var sessionStore={setCurrentSession(id){this.currentSessionId=id}};
      window.MyAgentIcons={svg:()=>'<svg></svg>'};
      function getActiveWorkDir(){return 'D:/fixture'}
      async function switchSession(id){
        setCurrentSessionState(id);
        if(window.switchGates?.[id])await window.switchGates[id];
        return true;
      }
      function openSettingsCenter(id){window.settingsOpened=id}
      function showUiAlert(data){window.lastAlert=data}
    '''
    source += function_source((ROOT / 'frontend/src/app/state/session-actions.js').read_text(
        encoding='utf-8'), 'setCurrentSessionState')
    for folder, names in [
        ('engine', ['types', 'tree', 'constraints', 'geometry', 'operations', 'planner', 'sequence', 'controller']),
        ('renderer', ['icons', 'gesture', 'measure', 'dock-surface', 'float-layer']),
        ('embedder', ['surface-store', 'tab-registry', 'page-host', 'browser-page', 'right-column']),
    ]:
        for name in names:
            source += '\n' + (MODULES / folder / (name + '.js')).read_text(encoding='utf-8')
    page.add_script_tag(content=source)
    rows = [{'slot': 'details.tab', 'id': 'main', 'plugin_id': 'demo', 'title': 'Demo',
             'href': '/plugins/demo', 'target': 'plugin-page', 'scope': 'session'}]
    page.evaluate('rows=>MyAgentDock.syncPluginPages(rows)', rows)
    yield page, calls, errors, rows
    page.unroute('**/*', route)
    page.remove_listener('pageerror', on_error)
    if resizing:
        page.set_viewport_size(original_viewport)


def plugin_frame(page, session='s1'):
    page.wait_for_function("sid=>[...document.querySelectorAll('.dock-plugin-page:not([hidden]) iframe')].some(f=>f.contentWindow.bound===sid)", arg=session)
    return next(frame for frame in page.frames if '/plugins/demo' in frame.url and frame.evaluate('window.bound') == session)


def test_plugin_context_deduplication_visibility_and_live_frame_retention(details_page):
    page, calls, errors, _rows = details_page
    assert page.evaluate("MyAgentDock.openPluginPage('demo')") is True
    frame = plugin_frame(page)
    identity = frame.evaluate('window.instance')
    frame.locator('#draft').fill('unsaved text')
    page.wait_for_function("document.querySelectorAll('.dock-plugin-page:not([hidden])').length===1")
    page.wait_for_timeout(130)
    assert calls
    page.evaluate("MyAgentDock.openPluginPage('demo')")
    assert page.locator('.dock-plugin-page').count() == 1
    page.evaluate("MyAgentDock.openDetailsTab('guide')")
    page.wait_for_timeout(450)
    count = len(calls)
    page.wait_for_timeout(140)
    assert len(calls) == count, 'hidden pages do not poll'
    page.evaluate("MyAgentDock.openPluginPage('demo')")
    frame = plugin_frame(page)
    assert frame.evaluate('window.instance') == identity
    assert frame.locator('#draft').input_value() == 'unsaved text'
    page.evaluate("MyAgentDock.closeDetails()")
    page.wait_for_timeout(380)
    page.evaluate("MyAgentDock.openPluginPage('demo')")
    assert plugin_frame(page).evaluate('window.instance') == identity
    assert not errors, [str(error) for error in errors]


def test_session_switch_float_and_disable_preserve_then_release_the_correct_page(details_page):
    page, _calls, errors, _rows = details_page
    page.evaluate("MyAgentDock.openPluginPage('demo')")
    first = plugin_frame(page).evaluate('window.instance')
    page.evaluate("MyAgentDock.openSession('s2')")
    page.evaluate("MyAgentDock.openPluginPage('demo')")
    second = plugin_frame(page, 's2').evaluate('window.instance')
    assert second != first
    page.evaluate("MyAgentDock.openSession('s1')")
    assert plugin_frame(page).evaluate('window.instance') == first
    page.evaluate('''() => {
      const state=MyAgentDock.detailsState();const tab=Object.values(state.tabs).find(t=>t.kind==='plugin-page');
      dockActionFloatTab(dockRightState.sessionId,tab.id,{x:200,y:100,width:400,height:350},dockRightSeed(),'right');dockRightRender();
    }''')
    page.wait_for_timeout(100)
    assert plugin_frame(page).evaluate('window.instance') == first
    page.evaluate("MyAgentDock.syncPluginPages([])")
    page.wait_for_function("document.querySelectorAll('.dock-plugin-page').length===0")
    assert not errors, [str(error) for error in errors]


def test_registered_renderer_browser_and_application_pages_work_without_a_session(details_page):
    page, _calls, errors, rows = details_page
    page.evaluate("currentSessionId='';MyAgentDock.syncPluginPages([])")
    app_rows = [{**rows[0], 'scope': 'app'}]
    page.evaluate('rows=>MyAgentDock.syncPluginPages(rows)', app_rows)
    assert page.evaluate("MyAgentDock.openPluginPage('demo')") is True
    page.evaluate('''() => {
      window.unregisterFixture=MyAgentDock.registerTabType({id:'fixture',kind:'fixture',title:'Fixture',
        body(){const el=document.createElement('div');el.id='registered-body';el.textContent='Registered';return el}});
      MyAgentDock.openTab('fixture');
    }''')
    assert page.locator('#registered-body').inner_text() == 'Registered'
    assert page.evaluate("MyAgentDock.openBrowser('javascript:alert(1)')") is False
    assert page.evaluate("MyAgentDock.openBrowser('http://localhost:8192/api/env')") is False
    assert page.evaluate("MyAgentDock.openBrowser('http://user:password@example.com')") is False
    assert page.evaluate("dockParseBrowserAddress('http://127.0.0.1:5173').href") == 'http://127.0.0.1:5173/'
    assert page.evaluate("MyAgentDock.openBrowser('https://browser.fixture.test/one')") is True
    page.wait_for_selector('.dock-browser-page:not([hidden]) iframe')
    page.frame_locator('.dock-browser-page:not([hidden]) iframe').locator('a').wait_for()
    browser = next(frame for frame in page.frames if frame.url.endswith('/one'))
    browser.wait_for_load_state('load')
    page.wait_for_function("document.querySelector('.dock-browser-page:not([hidden]) .dock-browser-placeholder').hidden")
    # The retained iframe follows the sidebar's animated seat. Wait until its
    # screen position settles so a click cannot land at the pre-expansion offset.
    page.wait_for_function("dockRightPageHost.frame === null")
    browser.locator('a').click()
    page.wait_for_function("document.querySelector('.dock-browser-page:not([hidden]) .dock-browser-notice').textContent.includes('当前地址不可读取')")
    assert page.locator('.dock-browser-page:not([hidden]) button[aria-label="在系统浏览器中打开"]').is_disabled()
    assert not errors, [str(error) for error in errors]


def test_plugin_content_update_releases_old_browsing_context(details_page):
    page, _calls, errors, rows = details_page
    page.evaluate('rows=>MyAgentDock.syncPluginPages(rows)', [{**rows[0], 'signature': 'version-one'}])
    page.evaluate("MyAgentDock.openPluginPage('demo')")
    first = plugin_frame(page).evaluate('window.instance')
    page.evaluate('rows=>MyAgentDock.syncPluginPages(rows)', [{**rows[0], 'signature': 'version-two'}])
    page.wait_for_function("document.querySelectorAll('.dock-plugin-page').length===0")
    page.evaluate("MyAgentDock.openPluginPage('demo')")
    assert plugin_frame(page).evaluate('window.instance') != first
    # A same-origin message from the wrong Window cannot close this page.
    page.evaluate("window.postMessage({version:1,type:'myagent:plugin-page-request',action:'close'},location.origin)")
    page.wait_for_timeout(50)
    assert page.locator('.dock-plugin-page').count() == 1
    plugin_frame(page).evaluate('MyAgentPluginPage.close()')
    page.wait_for_function("document.querySelectorAll('.dock-plugin-page').length===0")
    assert not errors, [str(error) for error in errors]
