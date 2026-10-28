"""Exercise production capsule modules with real DOM, styles and owned-job routes."""
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
import time

import pytest

from tests.test_llm_stream_full_text_browser import browser_page, function_source
from tests.test_details_pages_browser import details_page

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def capsule(browser_page):
    context = browser_page.context.browser.new_context(viewport={"width": 1100, "height": 800})
    page = context.new_page()
    calls, errors = [], []
    state = SimpleNamespace(jobs=[
        {"id": "root-job", "label": "npm run build", "kind": "process", "status": "running",
         "owner_session_id": "root", "owner_label": "Build conversation", "started_at": time.time() - 83},
        {"id": "child-job", "label": "pytest tests/", "kind": "pty-send", "status": "running",
         "owner_session_id": "child", "owner_label": "测试检查", "terminal_id": "model-terminal", "started_at": time.time() - 32},
    ], fail_jobs=False, fail_kill=False, outputs={"root-job": "building\n", "child-job": "testing\n"})
    page.on('pageerror', lambda error: errors.append(str(error)))

    def route(route):
        request = route.request
        parsed = urlsplit(request.url)
        path, query = parsed.path, parse_qs(parsed.query)
        calls.append((request.method, path, query))
        if path == '/capsule-test':
            route.fulfill(content_type='text/html', body='''<!doctype html><html lang="zh-CN" class="theme-dark"><head><meta charset="utf-8"></head><body>
              <header class="titlebar"><div class="breadcrumb"><div class="breadcrumb-title-row">
                <span id="breadcrumb-text">构建与测试验证</span><div class="breadcrumb-activities"></div>
                <div id="breadcrumb-session-actions" class="breadcrumb-session-actions"><button class="session-more-btn">⋯</button></div>
              </div><span id="breadcrumb-sub"></span></div><div class="titlebar-right">32k / 128k</div></header>
              <main style="padding:40px"><p>当前会话的执行过程</p><textarea id="message-input" aria-label="输入消息"></textarea></main>
            </body></html>''')
        elif path.endswith('/jobs'):
            if state.fail_jobs:
                route.fulfill(status=503, json={"detail": "offline"})
            else:
                owner = path.split('/')[2]
                owners = {"root", "child"} if owner == 'root' else {owner}
                route.fulfill(json={"jobs": [dict(job) for job in state.jobs
                    if job['owner_session_id'] in owners and job['status'] in ('running', 'stopping')]})
        elif path.endswith('/output') or path.endswith('/kill'):
            owner, identifier = path.split('/')[2], path.split('/')[4]
            job = next((job for job in state.jobs if job['id'] == identifier and job['owner_session_id'] == owner), None)
            if not job:
                route.fulfill(status=404, json={"detail": "wrong owner"})
            elif path.endswith('/kill'):
                if state.fail_kill:
                    route.fulfill(status=409, json={"detail": "cannot stop"})
                else:
                    job['status'] = 'stopping'
                    route.fulfill(json={"job": dict(job), "outcome": "cancellation-requested"})
            else:
                output = state.outputs[identifier]
                offset = int(query.get('offset', ['0'])[0])
                route.fulfill(json={"text": output[offset:], "offset": len(output), "job": dict(job)})
        elif path.endswith('/subagents'):
            owner = path.split('/')[2]
            route.fulfill(json={"subagents": [{"id": "child", "parent_id": "root", "name": "测试检查",
                "subagent_type": "generalPurpose", "running": True, "status": "running", "depth": 1,
                "source": "runtime_v2"}] if owner == 'root' else []})
        else:
            route.fulfill(json={"estimated": 2300, "threshold": 128000})

    page.route('**/*', route)
    page.goto('http://127.0.0.1/capsule-test')
    page.add_style_tag(path=str(ROOT / 'frontend/src/styles/app.css'))
    page.add_script_tag(content='''
      var currentSessionId='root', clockNow=Date.now(), refreshTasks=[], openedConsoles=[], pageHidden=false;
      Object.defineProperty(document,'hidden',{configurable:true,get:()=>pageHidden});
      Date.now=()=>clockNow;
      var sessionStore={currentSessionId:'root',get:id=>({id,name:'构建与测试验证'})};
      function registerSidebarRefreshTask(key,ms,run,options){refreshTasks.push({run,...options});}
      function advance(ms){clockNow+=ms;refreshTasks.forEach(task=>{if(!document.hidden||task.runWhenHidden)task.run();});}
      function initUiHoverTips(){} function setContextTokenLabel(){} function syncTitlebarSessionMenu(){}
      function buildSessionWorkspaceSubtitle(){return 'D:/workspace · 当前会话';}
      function selectCurrentSession(){return sessionStore.get(currentSessionId);}
      function localizeSessionPlaceholderName(value){return value;}
      async function switchSession(id){currentSessionId=id;sessionStore.currentSessionId=id;
        document.dispatchEvent(new CustomEvent('myagent:session-change',{detail:{sessionId:id}}));
        updateSessionTitle();return true;}
      window.MyAgentDock={openPluginPage:(id,options)=>{openedConsoles.push({id,...options});return true;}};
    ''')
    for file in ('state/subagent-catalog-store.js', 'state/subagent-addressing.js', 'modules/titlebar-activity.js',
                 'modules/subagent-catalog-ui.js', 'state/background-task-store.js', 'modules/background-task-ui.js'):
        page.add_script_tag(path=str(ROOT / 'frontend/src/app' / file))
    rendering = (ROOT / 'frontend/src/app/modules/message-rendering.js').read_text(encoding='utf-8')
    page.add_script_tag(content='\n'.join(function_source(rendering, name)
        for name in ('updateSessionTitle', 'renderSubagentAddressedTitle')))
    page.evaluate('subagentCatalogUi.bindStore(); backgroundTaskUi.bind(); updateSessionTitle();')
    page.locator('#background-task-trigger').wait_for()
    page.locator('#subagent-catalog-trigger').wait_for()
    yield SimpleNamespace(page=page, state=state, calls=calls)
    context.close()
    assert errors == []


def open_menu(page):
    # DOM click avoids mouse hover implicitly opening the popover first.
    page.locator('#background-task-trigger').dispatch_event('click')
    page.locator('#background-task-menu').wait_for()


def test_layout_order_narrow_themes_and_ending_all_work(capsule):
    c, page = capsule, capsule.page
    assert page.locator('.breadcrumb-activities').evaluate('el=>[...el.children].map(x=>x.id)') == [
        'subagent-catalog-trigger', 'background-task-trigger']
    assert page.locator('#background-task-trigger').inner_text() == '后台任务 2'
    sizes = page.locator('.breadcrumb-activities').evaluate('''el=>[...el.children].map(x=>{
      const s=getComputedStyle(x);return [s.height,s.fontSize,s.borderRadius]})''')
    assert sizes[0] == sizes[1]
    widths = page.locator('.breadcrumb-activities').evaluate('el=>[...el.children].map(x=>x.getBoundingClientRect().width)')
    page.locator('#breadcrumb-text').evaluate("el=>el.textContent='很长的会话标题'.repeat(40)")
    assert page.locator('.breadcrumb-activities').evaluate('el=>[...el.children].map(x=>x.getBoundingClientRect().width)') == widths
    page.locator('#breadcrumb-text').evaluate("el=>el.textContent='构建与测试验证'")
    open_menu(page)
    assert page.locator('.background-task-row').count() == 2
    assert '子代理：测试检查' in page.locator('.background-task-row').nth(1).inner_text()
    page.evaluate("document.documentElement.className='theme-light'")
    output = ROOT / '.analysis/background-task-capsule'
    output.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(output / 'light.png'))
    page.evaluate("document.documentElement.className='theme-dark'")
    page.screenshot(path=str(output / 'dark.png'))
    page.set_viewport_size({"width": 390, "height": 844})
    page.wait_for_timeout(60)
    bounds = page.evaluate('''()=>{
      const title=document.querySelector('#breadcrumb-text').getBoundingClientRect();
      const group=document.querySelector('.breadcrumb-activities').getBoundingClientRect();
      const menu=document.querySelector('#background-task-menu').getBoundingClientRect();
      return {wrapped:group.top>=title.bottom,left:menu.left,right:menu.right,overflow:document.documentElement.scrollWidth>innerWidth};}''')
    assert bounds['wrapped'] and bounds['left'] >= 16 and bounds['right'] <= 374 and not bounds['overflow']
    page.screenshot(path=str(output / 'narrow.png'))
    for job in c.state.jobs:
        job['status'] = 'stopping'
    page.evaluate('backgroundTaskStore.refresh()')
    assert '停止中' in page.locator('#background-task-trigger').inner_text()
    assert page.locator('#background-task-trigger .subagent-catalog-dot').evaluate("el=>getComputedStyle(el).animationName") == 'none'
    for job in c.state.jobs:
        job['status'] = 'completed'
    page.evaluate('backgroundTaskStore.refresh()')
    assert page.locator('#background-task-trigger').count() == 0
    assert page.locator('#background-task-menu').is_visible()
    assert page.get_by_text('当前无活动任务', exact=True).is_visible()
    page.keyboard.press('Escape')
    assert page.locator('#background-task-menu').is_hidden()


def test_hover_pinning_keyboard_and_subagent_navigation(capsule):
    page = capsule.page
    page.locator('#message-input').focus()
    page.locator('#background-task-trigger').hover()
    page.locator('#background-task-menu').wait_for()
    assert page.locator('#message-input').evaluate('el=>el===document.activeElement')
    page.locator('#background-task-trigger').click()
    page.mouse.move(900, 700)
    page.wait_for_timeout(180)
    assert page.locator('#background-task-menu').is_visible()
    page.locator('#background-task-trigger').click()
    assert page.locator('#background-task-menu').is_hidden()
    page.locator('#background-task-trigger').press('ArrowDown')
    assert page.locator('.background-task-row button').first.evaluate('el=>el===document.activeElement')
    page.keyboard.press('Escape')
    assert page.locator('#background-task-trigger').evaluate('el=>el===document.activeElement')
    open_menu(page)
    page.locator('#subagent-catalog-trigger').hover()
    page.locator('#subagent-catalog-menu').wait_for()
    assert page.locator('#background-task-menu').is_hidden()
    page.locator('.subagent-catalog-row').click()
    page.wait_for_function("currentSessionId==='child' && backgroundTaskStore.snapshot().jobs.length===1")
    assert page.locator('#background-task-trigger').inner_text() == '后台任务 1'
    assert page.locator('[data-addressing-back]').is_visible()
    assert page.evaluate("subagentCatalogStore.isSubagentRead('child')")
    page.locator('[data-addressing-back]').click()
    page.wait_for_function("currentSessionId==='root' && backgroundTaskStore.snapshot().jobs.length===2")


def test_logs_keep_scroll_and_final_result_and_open_corresponding_terminal(capsule):
    c, page = capsule, capsule.page
    c.state.outputs['child-job'] = ''.join(f'line {i}\n' for i in range(180))
    open_menu(page)
    page.locator('.background-task-row').nth(1).get_by_role('button', name='日志', exact=True).click()
    page.wait_for_function("document.querySelector('.background-task-output').textContent.includes('line 179')")
    assert any(path == '/sessions/child/jobs/child-job/output' for _, path, _ in c.calls)
    pre = page.locator('.background-task-output')
    pre.evaluate('el=>el.scrollTop=40')
    before = pre.evaluate('el=>el.scrollTop')
    c.state.outputs['child-job'] += 'new line\n'
    page.evaluate('advance(1000)')
    page.wait_for_function("document.querySelector('.background-task-output').textContent.includes('new line')")
    assert pre.evaluate('el=>el.scrollTop') == before
    assert page.locator('.background-task-terminal-note').is_visible()
    c.state.jobs[1].update(status='completed', command_state='unknown', finished_at=time.time())
    c.state.jobs[0].update(status='completed', finished_at=time.time())
    page.evaluate('advance(1000)')
    page.wait_for_function("document.querySelector('.background-task-log > .background-task-meta').textContent.includes('命令状态未知')")
    assert '命令执行成功' not in page.locator('.background-task-log > .background-task-meta').inner_text()
    assert 'line 179' in pre.inner_text()
    page.wait_for_function('backgroundTaskStore.snapshot().jobs.length===0')
    assert page.locator('#background-task-trigger').count() == 0
    assert page.locator('#background-task-menu').is_visible()
    page.get_by_role('button', name='查看对应终端').click()
    assert page.evaluate('openedConsoles') == [{"id": "execution-tools", "sessionId": "child", "terminalId": "model-terminal"}]


def test_failure_retry_stop_owner_and_switch_cleanup(capsule):
    c, page = capsule, capsule.page
    open_menu(page)
    c.state.fail_jobs = True
    page.evaluate('backgroundTaskStore.refresh()')
    assert '更新失败' in page.locator('#background-task-trigger').inner_text()
    assert page.locator('.background-task-row').count() == 2
    c.state.fail_jobs = False
    page.get_by_role('button', name='重试', exact=True).click()
    page.wait_for_function("backgroundTaskStore.snapshot().error===''")
    c.state.fail_kill = True
    child = page.locator('.background-task-row').nth(1)
    child.get_by_role('button', name='停止', exact=True).click()
    child.get_by_text('cannot stop', exact=True).wait_for()
    c.state.fail_kill = False
    child.get_by_role('button', name='停止', exact=True).click()
    page.wait_for_function("backgroundTaskStore.snapshot().jobs[1].status==='stopping'")
    assert child.get_by_role('button', name='停止', exact=True).is_disabled()
    assert any(method == 'POST' and path == '/sessions/child/jobs/child-job/kill' for method, path, _ in c.calls)
    assert c.state.jobs[0]['status'] == 'running'
    page.evaluate("switchSession('empty')")
    page.wait_for_function("backgroundTaskStore.snapshot().sessionId==='empty' && !backgroundTaskStore.snapshot().loading")
    assert page.locator('#background-task-trigger').count() == 0
    assert page.locator('#background-task-menu').is_hidden()
    assert page.locator('#subagent-catalog-trigger').count() == 0
    c.state.jobs.append({"id": "solo-job", "label": "independent job", "status": "running", "kind": "process",
                         "owner_session_id": "solo", "owner_label": "Solo", "started_at": time.time()})
    page.evaluate("switchSession('solo')")
    page.wait_for_function("backgroundTaskStore.snapshot().sessionId==='solo' && backgroundTaskStore.snapshot().jobs.length===1")
    assert page.locator('.breadcrumb-activities').evaluate('el=>[...el.children].map(x=>x.id)') == ['background-task-trigger']
    page.evaluate("switchSession('')")
    assert page.locator('.breadcrumb-activities').inner_text() == ''


def test_shared_clock_cadence_visibility_and_reduced_motion(capsule):
    c, page = capsule, capsule.page

    def job_reads():
        return sum(path.endswith('/jobs') for _, path, _ in c.calls)

    before = job_reads()
    page.evaluate('advance(1000)')
    page.wait_for_timeout(50)
    assert job_reads() == before
    page.evaluate('advance(3000)')
    page.wait_for_function('!backgroundTaskStore.snapshot().loading')
    assert job_reads() == before + 1
    open_menu(page)
    page.wait_for_function('!backgroundTaskStore.snapshot().loading')
    before = job_reads()
    page.evaluate('advance(1000)')
    page.wait_for_function('!backgroundTaskStore.snapshot().loading')
    assert job_reads() == before + 1
    page.evaluate("pageHidden=true;document.dispatchEvent(new Event('visibilitychange'));advance(10000)")
    page.wait_for_timeout(50)
    assert job_reads() == before + 1
    page.evaluate("pageHidden=false;document.dispatchEvent(new Event('visibilitychange'))")
    page.wait_for_function('!backgroundTaskStore.snapshot().loading')
    assert job_reads() == before + 2
    page.emulate_media(reduced_motion='reduce')
    assert page.locator('#background-task-trigger .subagent-catalog-dot').evaluate("el=>getComputedStyle(el).animationName") == 'none'


def test_corresponding_terminal_dock_entry_keeps_the_job_owner(details_page):
    page, _calls, errors, rows = details_page
    definition = {**rows[0], "plugin_id": "execution-tools", "href": "/plugins/execution-tools"}
    page.evaluate('rows=>MyAgentDock.syncPluginPages(rows)', [definition])
    assert page.evaluate("MyAgentDock.openPluginPage('execution-tools',{sessionId:'child',terminalId:'model-terminal'})")
    page.wait_for_function("[...document.querySelectorAll('.dock-plugin-page iframe')].some(frame=>frame.contentWindow.bound==='child')")
    frame = page.locator('.dock-plugin-page iframe')
    assert 'terminal_id=model-terminal' in frame.get_attribute('src')
    assert page.evaluate('currentSessionId') == 's1'
    assert not errors, [str(error) for error in errors]
