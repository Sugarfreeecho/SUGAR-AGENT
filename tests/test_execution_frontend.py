"""Exercise the execution panel with real xterm and a deterministic transport."""
import os
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def page():
    with playwright.sync_playwright() as runtime:
        try:
            browser = runtime.chromium.launch(headless=True,
                **({"channel": "msedge"} if os.name == "nt" else {}))
        except playwright.Error as error:
            pytest.skip(f"Local Chromium browser unavailable: {error}")
        page = browser.new_page(viewport={"width": 1100, "height": 800})
        page.route("https://execution.test/**", lambda route: route.fulfill(body="<div id='panel'></div>", content_type="text/html"))
        page.goto("https://execution.test/")
        page.add_style_tag(path=str(ROOT / "plugins/execution-tools/web/session-panel.css"))
        page.add_style_tag(path=str(ROOT / "frontend/node_modules/@xterm/xterm/css/xterm.css"))
        page.add_script_tag(path=str(ROOT / "frontend/node_modules/@xterm/xterm/lib/xterm.js"))
        page.add_script_tag(path=str(ROOT / "frontend/node_modules/@xterm/addon-fit/lib/addon-fit.js"))
        page.add_script_tag(content="""
          window.calls=[];window.streams=[];window.terminals=[];window.alerts=[];
          window.alert=text=>alerts.push(text);
          window.MyAgentTerminal={Terminal:class extends window.Terminal {
            constructor(options){super(options);terminals.push(this);}
          },FitAddon:window.FitAddon.FitAddon};
          window.job={id:'job-id',label:'build',status:'running'};
          window.user={id:'user-id',actor:'user',name:'work',status:'running'};
          window.model={id:'model-id',actor:'model',name:'agent',status:'running'};
          window.EventSource=class {
            constructor(url){this.url=url;this.closed=false;streams.push(this);
              setTimeout(()=>this.emit({text:'terminal output\\r\\n',offset:16,status:'running'}),20);}
            emit(value){if(!this.closed)this.onmessage?.({data:JSON.stringify(value)});}
            close(){this.closed=true;}
          };
          window.context={container:document.getElementById('panel'),sessionId:'owner',request:async(url,options)=>{
            const body=options.body?JSON.parse(options.body):null;calls.push({url,body});
            let result={};
            if(url==='/api/computer-use')result={enabled:false,provider:'native',state:'disabled',tool_count:0,mcp_servers:[]};
            else if(url==='/api/execution/capabilities')result={shells:[{name:'test shell',path:'/bin/bash'}]};
            else if(url.endsWith('/jobs'))result={jobs:[job]};
            else if(url.includes('/jobs/job-id/output'))result={text:url.endsWith('offset=0')?'job output':'',offset:10,job};
            else if(url.endsWith('/terminals')&&body)result=user;
            else if(url.endsWith('/terminals'))result={user:[user],model:[model]};
            else if(url.includes('/history'))result={text:'model history'};
            else if(url.endsWith('/close'))user.status='closed';
            return {ok:true,json:async()=>result};
          }};
        """)
        source = (ROOT / "plugins/execution-tools/web/session-panel.js").read_text(encoding="utf-8")
        page.add_script_tag(content=source.replace("export function renderSessionPanel", "function renderSessionPanel")
            + "\nwindow.cleanup=renderSessionPanel(context);")
        yield page
        page.evaluate("cleanup({nextSessionId:'other'})")
        browser.close()


def test_terminal_input_reconnect_tabs_and_view_cleanup(page):
    page.get_by_role("button", name="连接", exact=True).click()
    page.wait_for_function("streams.length===1 && calls.some(c=>c.url.endsWith('/resize'))")
    page.wait_for_function("terminals[0].buffer.active.getLine(0).translateToString().includes('terminal output')")
    page.evaluate("terminals[0].paste('echo test\\r')")
    page.wait_for_function("calls.some(c=>c.url.endsWith('/input'))")
    command = page.evaluate("calls.find(c=>c.url.endsWith('/input')).body")
    assert command["text"] == "echo test\r" and command["connection"]
    page.evaluate("streams[0].onerror()")
    page.wait_for_function("streams.length===2")
    assert "offset=16" in page.evaluate("streams[1].url")
    page.get_by_role("tab", name="Agent · agent", exact=True).click()
    assert page.evaluate("streams.every(s=>s.closed)")
    assert page.locator(".execution-output").inner_text() == "model history"
    assert not page.evaluate("calls.some(c=>c.url.endsWith('/close'))")
    page.get_by_role("tab", name="work", exact=True).click()
    page.wait_for_function("streams.length===3")
    assert page.evaluate("cleanup({nextSessionId:'owner'})") is False
    assert page.locator(".execution-dialog").count() == 1
    assert page.evaluate("cleanup({nextSessionId:'other'})") is True
    assert page.evaluate("streams.every(s=>s.closed)")
    assert page.locator(".execution-dialog").count() == 0
    assert not page.evaluate("calls.some(c=>c.url.endsWith('/close'))")


def test_computer_profile_grant_is_explicit_mcp_only(page):
    computer = page.locator('.execution-computer')
    computer.locator('summary').click()
    grant = computer.get_by_label('允许访问已登录浏览器（追加 MCP 授权）')
    assert not grant.is_visible()
    computer.locator('select').first.select_option('mcp')
    assert grant.is_visible() and not grant.is_checked()
    grant.check()
    computer.get_by_role('button', name='保存', exact=True).click()
    page.wait_for_function("calls.some(c=>c.url==='/api/computer-use' && c.body)")
    assert page.evaluate("calls.filter(c=>c.url==='/api/computer-use' && c.body).at(-1).body.allow_existing_profile") is True
    computer.locator('select').first.select_option('native')
    computer.get_by_role('button', name='保存', exact=True).click()
    page.wait_for_function("calls.filter(c=>c.url==='/api/computer-use' && c.body).length===2")
    assert page.evaluate("calls.filter(c=>c.url==='/api/computer-use' && c.body).at(-1).body.allow_existing_profile") is False


def test_create_terminal_job_output_and_explicit_end(page):
    page.get_by_role("button", name="输出", exact=True).click()
    assert page.locator(".execution-output").inner_text() == "job output"
    page.wait_for_function("calls.some(c=>c.url.endsWith('offset=10'))")
    page.get_by_role("button", name="关闭视图", exact=True).click()
    page.get_by_role("button", name="新建用户终端", exact=True).click()
    page.locator(".execution-dialog select").select_option("/bin/bash")
    page.locator(".execution-dialog input").fill("/workspace")
    page.get_by_role("button", name="创建", exact=True).click()
    page.wait_for_function("streams.length===1")
    assert page.evaluate("calls.find(c=>c.url.endsWith('/terminals')&&c.body).body") == {"shell": "/bin/bash", "cwd": "/workspace"}
    page.get_by_role("button", name="关闭视图", exact=True).click()
    assert page.evaluate("streams[0].closed")
    assert not page.evaluate("calls.some(c=>c.url.endsWith('/close'))")
    page.get_by_role("button", name="结束", exact=True).click()
    page.wait_for_function("calls.some(c=>c.url.endsWith('/close'))")
    assert page.evaluate("user.status") == "closed"
    assert page.evaluate("alerts") == []


def test_background_send_shows_unknown_command_state_and_links_terminal(page):
    page.evaluate("Object.assign(job,{kind:'pty-send',status:'completed',command_state:'unknown',terminal_id:'model-id'})")
    page.get_by_text('发送等待结束 · 命令状态未知', exact=False).wait_for()
    page.get_by_role('button', name='输出', exact=True).click()
    assert '命令状态未知' in page.locator('.execution-dialog .execution-status').first.inner_text()
    assert '命令后续输出请查看对应 Agent 终端' in page.locator('.execution-dialog').inner_text()
    page.get_by_role('button', name='查看对应终端', exact=True).click()
    assert page.locator('.execution-output').inner_text() == 'model history'
