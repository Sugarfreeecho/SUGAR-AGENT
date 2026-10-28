"""Load the migrated execution console, including its production terminal bundle."""
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit, parse_qs

import pytest

from tests.test_llm_stream_full_text_browser import browser_page

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def execution_console(browser_page):
    context = browser_page.context.browser.new_context(viewport={"width": 1000, "height": 800})
    page = context.new_page()
    calls, errors = [], []
    state = {"closed": False}
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.add_init_script('''
      window.streams=[];window.alerts=[];window.termInstances=[];
      window.alert=value=>alerts.push(String(value));
      Object.defineProperty(navigator,'clipboard',{value:{writeText:async value=>{window.copied=value},readText:async()=>"echo paste\\r"}});
      window.EventSource=class {
        constructor(url){this.url=url;this.closed=false;streams.push(this);
          setTimeout(()=>{if(!this.closed)this.onmessage?.({data:JSON.stringify({text:'terminal output\\r\\n',offset:16,status:'running'})})},30)}
        close(){this.closed=true}
      };
    ''')

    def route(route):
        request = route.request
        parsed = urlsplit(request.url)
        path = parsed.path
        body = request.post_data_json if request.post_data else None
        calls.append((request.method, path, body))
        if path == '/plugins/execution-tools':
            route.fulfill(content_type='text/html', body=(ROOT / 'plugins/execution-tools/web/index.html').read_text(encoding='utf-8'))
        elif path.startswith('/plugin-assets/execution-tools/'):
            file = ROOT / 'plugins/execution-tools/web' / path.rsplit('/', 1)[1]
            route.fulfill(content_type='text/css' if file.suffix == '.css' else 'application/javascript', body=file.read_text(encoding='utf-8'))
        elif path.startswith('/static/'):
            file = ROOT / 'app/templates/static' / path.rsplit('/', 1)[1]
            route.fulfill(content_type='text/css' if file.suffix == '.css' else 'application/javascript', body=file.read_text(encoding='utf-8'))
        elif path == '/assets/terminal-runtime.js':
            route.fulfill(content_type='application/javascript', body=(ROOT / 'app/templates/dist/assets/terminal-runtime.js').read_text(encoding='utf-8'))
        elif path == '/sessions': route.fulfill(json=[{"id": "s1", "name": "构建任务"}, {"id": "s2", "name": "另一个会话"}])
        elif path == '/api/computer-use': route.fulfill(json={"enabled": False, "provider": "native", "state": "disabled", "tool_count": 0, "mcp_servers": []})
        elif path == '/api/execution/capabilities': route.fulfill(json={"shells": [{"name": "Test shell", "path": "test-shell"}]})
        elif path.endswith('/jobs'): route.fulfill(json={"jobs": [{"id": "job1", "label": path.split('/')[2] + ':build', "status": "running"}]})
        elif path.endswith('/output'): route.fulfill(json={"text": "build output" if parse_qs(parsed.query).get('offset') == ['0'] else '', "offset": 12})
        elif path.endswith('/terminals'):
            user = {"id": "user1", "actor": "user", "name": "work", "status": "closed" if state['closed'] else "running"}
            route.fulfill(json=user if body is not None else {"user": [user], "model": [{"id": "model1", "actor": "model", "name": "agent", "status": "running"}]})
        elif path.endswith('/history'): route.fulfill(json={"text": "Agent terminal history"})
        elif path.endswith('/close'):
            state['closed'] = True
            route.fulfill(json={"ok": True})
        else: route.fulfill(json={"ok": True})

    page.route('**/*', route)
    page.goto('http://127.0.0.1/plugins/execution-tools?session=s1')
    page.get_by_text('[running] s1:build', exact=True).wait_for()
    page.evaluate('''() => {const Native=MyAgentTerminal.Terminal;
      MyAgentTerminal.Terminal=class extends Native{constructor(options){super(options);termInstances.push(this)}};
    }''')
    yield SimpleNamespace(page=page, calls=calls, state=state)
    context.close()
    assert errors == []


def test_execution_console_output_terminal_menu_and_visibility(execution_console):
    c, page = execution_console, execution_console.page
    page.get_by_role('button', name='输出', exact=True).click()
    page.get_by_text('build output', exact=True).wait_for()
    page.get_by_role('button', name='关闭视图').click()
    page.get_by_role('button', name='连接', exact=True).click()
    page.wait_for_function("termInstances[0].buffer.active.getLine(0).translateToString().includes('terminal output')")
    page.locator('.xterm-screen').click(button='right')
    page.get_by_role('menuitem', name='全选', exact=True).click()
    page.locator('.xterm-screen').click(button='right')
    page.get_by_role('menuitem', name='复制选中文本').click()
    assert 'terminal output' in page.evaluate('copied')
    page.evaluate("MyAgentPluginPage={visible:false};document.dispatchEvent(new CustomEvent('myagent:plugin-page-visibility',{detail:{visible:false}}))")
    assert page.evaluate('streams.every(stream=>stream.closed)')
    before = len(c.calls)
    page.wait_for_timeout(1100)
    assert len(c.calls) == before
    page.evaluate("MyAgentPluginPage.visible=true;document.dispatchEvent(new CustomEvent('myagent:plugin-page-visibility',{detail:{visible:true}}))")
    page.wait_for_function('streams.length===2')
    assert 'offset=16' in page.evaluate('streams[1].url')
    assert page.evaluate('termInstances.length') == 1
    page.get_by_role('button', name='关闭视图').click()
    assert page.evaluate('streams.every(stream=>stream.closed)')
    assert not any(path.endswith('/close') for _method, path, _body in c.calls)
    out = ROOT / '.analysis/workflow-consoles'
    out.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(out / 'execution-console.png'), full_page=True)
    assert page.evaluate('alerts') == []


def test_execution_console_creation_end_and_session_switch(execution_console):
    c, page = execution_console, execution_console.page
    page.get_by_role('button', name='新建用户终端').click()
    page.locator('.execution-dialog select').select_option('test-shell')
    page.locator('.execution-dialog input').fill('D:/test')
    page.get_by_role('button', name='创建', exact=True).click()
    page.wait_for_function('streams.length===1')
    assert any(path == '/sessions/s1/terminals' and body == {"shell": "test-shell", "cwd": "D:/test"} for _method, path, body in c.calls)
    page.locator('#session').fill('s2')
    # The modal protects its session; close the view before selecting another session.
    page.get_by_role('button', name='关闭视图').click()
    page.get_by_role('button', name='打开会话').click()
    page.get_by_text('[running] s2:build', exact=True).wait_for()
    assert page.evaluate('streams.every(stream=>stream.closed)')
    page.get_by_role('button', name='结束', exact=True).click()
    page.wait_for_function("document.querySelector('.execution-row')!==null")
    assert c.state['closed']
    assert any(path == '/sessions/s2/terminals/user1/close' for _method, path, _body in c.calls)
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
    assert page.evaluate('alerts') == []


def test_execution_console_opens_the_requested_model_terminal(execution_console):
    page = execution_console.page
    page.goto('http://127.0.0.1/plugins/execution-tools?session=s1&terminal_id=model1')
    page.get_by_text('Agent terminal history', exact=True).wait_for()
    assert page.get_by_role('dialog').is_visible()
    assert page.get_by_text('Agent 终端 · agent', exact=True).is_visible()
