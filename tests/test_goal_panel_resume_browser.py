"""Goal panel and composer strip resume blocked goals through the real API."""
import json

import pytest

from tests.test_workflow_consoles_browser import browser_page, consoles
from tests.test_workflow_consoles_browser import ROOT


def mount_panel(c, wait_for_load=True):
    goal = c.goals.get('s1')
    fields = [{'label': 'Objective', 'value': goal['objective']},
              {'label': 'Status', 'value': goal['status']}]
    sidebar = (ROOT / 'frontend/src/app/modules/public-sidebar.js').read_text(encoding='utf-8')
    def function_source(name):
        start = sidebar.index('function ' + name + '(')
        return sidebar[start:sidebar.index('\n}', start) + 2]
    narrow_source = sidebar[sidebar.index('var PUBAR_NARROW_ICONS ='):sidebar.index('function pubarNarrowIcon(')]
    narrow_source += '\n'.join(function_source(name) for name in (
        'pubarNarrowIcon', 'pubarNarrowConfigOf', 'pubarNarrowHasOpen', 'pubarBuildNarrowItem'))
    html = '''<link rel="stylesheet" href="/plugin-assets/agent-goal/session-panel.css">
      <style>#strip svg{width:16px;height:16px}</style>
      <div id="panel"></div><div id="strip"></div>
      <script>var pubarNarrowOpenId=null,pubarNarrowConfigs={};
        function pubarOpenNarrowPopover(){} NARROW_SOURCE
      </script>
      <script type="module">
        import {renderSessionPanel} from '/plugin-assets/agent-goal/session-panel.js';
        window.MyAgentPubar = {
          notifyActivity(){}, updateNarrowChip(id, text){
            const chip=document.querySelector('#strip .pni-chip'); if(chip)chip.textContent=text;
          },
          configureNarrow(id, config) {
            pubarNarrowConfigs[id] = config;
            document.getElementById('strip').replaceChildren(pubarBuildNarrowItem({id, label:'GOAL'}, config));
          }
        };
        const context = {
          container: document.getElementById('panel'), sessionId: 's1',
          item: {pluginId: 'agent-goal', id: 'current-goal', fields: FIELDS},
          request: async (url, options) => {
            const response = await fetch(url, options);
            const data = await response.json();
            if (options.method === 'GET') window.goalLoaded = true;
            return {ok: response.ok, status: response.status, json: async () => data};
          },
          notifyStateChanged(){}
        };
        window.cleanup = renderSessionPanel(context);
        window.remount = (sessionId='s1') => {
          cleanup({nextSessionId:sessionId});
          context.sessionId = sessionId;
          context.container.replaceChildren();
          window.cleanup = renderSessionPanel(context);
        };
      </script>'''.replace('FIELDS', json.dumps(fields, ensure_ascii=False)).replace('NARROW_SOURCE', narrow_source)
    c.page.route('**/goal-panel-test', lambda route: route.fulfill(content_type='text/html', body=html))
    c.page.goto('http://127.0.0.1/goal-panel-test')
    if wait_for_load:
        c.page.wait_for_function('window.goalLoaded === true')


def block_goal(c, token_budget=None):
    goal = c.goals.create('s1', '继续完成原来的目标', token_budget=token_budget)
    for index in range(3):
        c.goals.update_status('s1', 'blocked', '需要用户提供凭据', report_id=f'run-{index}')
    assert c.goals.get('s1')['status'] == 'blocked'
    return goal


def test_goal_progress_api_is_compact_and_uncached(consoles):
    c = consoles
    goal = c.goals.create('s1', 'Private objective excluded from progress')
    response = c.client.get('/sessions/s1/goal/progress')
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'no-store'
    assert response.json()['goal_id'] == goal['id']
    assert response.json()['continuation']['phase'] == 'waiting'
    assert 'goal' not in response.json()
    assert goal['objective'] not in response.text
    assert c.client.get('/sessions/missing/goal/progress').status_code == 404


def test_waiting_phases_are_visible_in_panel_and_strip_and_polling_stops_on_cleanup(consoles):
    import time
    c, page = consoles, consoles.page
    goal = c.goals.create('s1', 'Keep working')
    current, polls = {'phase': 'queued', 'label': '续跑已排队'}, []
    def progress(route):
        polls.append(route.request.url)
        route.fulfill(json={'goal_id': goal['id'], 'status': 'active', 'continuation': {
            **current, 'since': time.time() - 5}})
    page.route('**/sessions/s1/goal/progress', progress)
    mount_panel(c)
    for phase, label in [('queued', '续跑已排队'), ('preparing', '准备下一轮'), ('model_wait', '正在请求模型'), ('finishing', '本轮收尾')]:
        current.update(phase=phase, label=label)
        page.wait_for_function('(label) => document.querySelector(".chat-goal-status").textContent.includes(label)', arg=label)
        assert label in page.locator('#strip .pni-chip').inner_text()
        assert '·' in page.locator('.chat-goal-status').inner_text()
    current.update(phase='running', label='正在执行')
    page.wait_for_function('document.querySelector(".chat-goal-status").textContent.startsWith("进行中")')
    assert sum(method == 'GET' and path == '/sessions/s1/goal' for method, path in c.requests) == 1
    page.evaluate('cleanup()')
    count = len(polls)
    page.wait_for_timeout(2200)
    assert len(polls) == count


@pytest.mark.parametrize('entry', ['panel', 'strip'])
@pytest.mark.parametrize('exhausted', [False, True])
def test_blocked_goal_can_resume_from_both_entries(consoles, entry, exhausted):
    c, page = consoles, consoles.page
    original = block_goal(c, token_budget=100 if exhausted else None)
    if exhausted:
        c.goals.record_usage('s1', 100, usage_id='last-run:tokens')
    mount_panel(c)
    page.evaluate("""() => {
      window.budgetPrompts = 0;
      window.prompt = () => {budgetPrompts++; return '50';};
    }""")
    button = page.locator('#' + entry).get_by_role('button', name='继续 Goal', exact=True)
    assert button.is_visible()
    if entry == 'strip':
        assert button.locator('svg path').get_attribute('d') == 'm8 5 11 7-11 7Z'
    else:
        assert button.locator('.chat-goal-icon-play').get_attribute('hidden') is None
        assert button.locator('.chat-goal-icon-pause').get_attribute('hidden') is not None
    with page.expect_response(lambda response: response.url.endswith('/goal/resume')) as response:
        button.click()
    assert response.value.status == 200
    page.locator('#panel').get_by_role('button', name='暂停 Goal', exact=True).wait_for()
    resumed = c.goals.get('s1')
    assert resumed['id'] == original['id'] and resumed['objective'] == original['objective']
    assert resumed['status'] == 'active' and resumed['blocked_streak'] == 0
    assert resumed['blocked_reason'] is None and resumed['blocked_fingerprint'] is None
    assert resumed['remaining_tokens'] == (50 if exhausted else None)
    assert page.evaluate('budgetPrompts') == (1 if exhausted else 0)
    assert c.goals.should_continue('s1')
    assert ('resume', 's1') in c.calls
    # A user restart begins a fresh blocker audit rather than stopping after one report.
    report = c.goals.update_status('s1', 'blocked', '需要用户提供凭据', report_id='new-run')
    assert report['status'] == 'active' and report['blocked_streak'] == 1
    page.evaluate('cleanup()')


def test_cancelling_budget_prompt_leaves_blocked_goal_resumable(consoles):
    c, page = consoles, consoles.page
    block_goal(c, token_budget=100)
    c.goals.record_usage('s1', 100, usage_id='last-run:tokens')
    mount_panel(c)
    page.evaluate("""() => {
      window.budgetPrompts = 0;
      window.prompt = () => {budgetPrompts++; return null;};
    }""")
    page.locator('#panel').get_by_role('button', name='继续 Goal', exact=True).click()
    assert page.evaluate('budgetPrompts') == 1
    assert not any(method == 'POST' and path.endswith('/goal/resume') for method, path in c.requests)
    assert c.goals.get('s1')['status'] == 'blocked'
    assert page.locator('#panel').get_by_role('button', name='继续 Goal', exact=True).is_enabled()
    page.evaluate('cleanup()')


@pytest.mark.parametrize('status,label,action', [
    ('active', '暂停 Goal', 'pause'), ('paused', '开始 Goal', 'resume'),
])
def test_existing_pause_and_start_actions_still_work(consoles, status, label, action):
    c, page = consoles, consoles.page
    c.goals.create('s1', 'Existing goal')
    if status == 'paused':
        c.goals.user_action('s1', 'pause')
    mount_panel(c)
    with page.expect_response(lambda response: response.url.endswith('/goal/' + action)):
        page.locator('#panel').get_by_role('button', name=label, exact=True).click()
    assert c.goals.get('s1')['status'] == ('paused' if action == 'pause' else 'active')
    if action == 'pause':
        assert ('interrupt', 's1') not in c.calls
        assert page.locator('.chat-goal-action-feedback').inner_text() == 'Goal 已暂停，当前任务继续执行'
    page.evaluate('cleanup()')


def test_cancelled_goal_does_not_offer_resume(consoles):
    c = consoles
    c.goals.create('s1', 'Cancelled goal')
    c.goals.user_action('s1', 'cancel')
    mount_panel(c)
    assert c.page.get_by_role('button', name='继续 Goal', exact=True).count() == 0
    assert c.page.get_by_role('button', name='开始 Goal', exact=True).count() == 0
    c.page.evaluate('cleanup()')


@pytest.mark.parametrize('entry', ['panel', 'strip'])
def test_resume_shows_immediate_feedback_through_panel_recreation(consoles, entry):
    c, page = consoles, consoles.page
    block_goal(c)
    pending = []
    page.route('**/sessions/s1/goal/resume', lambda route: pending.append(route))
    mount_panel(c)
    page.clock.install()
    page.locator('#' + entry).get_by_role('button', name='继续 Goal', exact=True).click()
    busy = page.locator('#panel').get_by_role('button', name='正在继续…', exact=True)
    assert busy.is_disabled() and busy.get_attribute('aria-busy') == 'true'
    assert busy.locator('.chat-goal-action-spinner').is_visible()
    assert page.locator('.chat-goal-action-feedback').inner_text() == '正在继续 Goal…'
    assert page.locator('#strip .pni-summary').inner_text() == '正在继续 Goal…'
    assert page.locator('#strip .pni-chip').inner_text() == '正在继续…'
    page.locator('#strip').get_by_role('button', name='正在继续…', exact=True).click()
    assert len(pending) == 1
    # An extension-state SSE update must not remove the in-flight feedback.
    page.evaluate('remount()')
    assert page.locator('#panel').get_by_role('button', name='正在继续…', exact=True).is_disabled()
    request = pending[0].request
    response = c.client.post('/sessions/s1/goal/resume', content=request.post_data,
                             headers={'Content-Type': 'application/json'})
    pending[0].fulfill(status=response.status_code, json=response.json())
    page.locator('#panel').get_by_role('button', name='暂停 Goal', exact=True).wait_for()
    assert page.locator('.chat-goal-action-feedback').inner_text() == 'Goal 已继续，自动续跑已启用'
    assert page.locator('#strip .pni-summary').inner_text() == 'Goal 已继续，自动续跑已启用'
    page.clock.fast_forward(5001)
    page.locator('.chat-goal-action-feedback').wait_for(state='hidden')
    assert page.locator('#strip .pni-summary').inner_text() == '继续完成原来的目标'
    page.evaluate('cleanup()')


def test_resume_failure_remains_visible_and_can_be_retried(consoles):
    c, page = consoles, consoles.page
    block_goal(c)
    pattern = '**/sessions/s1/goal/resume'
    def fail(route):
        route.fulfill(status=409, json={'error': '服务暂时不可用'})
    page.route(pattern, fail)
    mount_panel(c)
    page.locator('#strip').get_by_role('button', name='继续 Goal', exact=True).click()
    page.wait_for_function("document.querySelector('.chat-goal-action-feedback').dataset.kind === 'error'")
    assert page.locator('.chat-goal-action-feedback').inner_text() == '继续 Goal 失败：服务暂时不可用'
    assert page.locator('#strip .pni-summary').inner_text() == '继续 Goal 失败：服务暂时不可用'
    assert page.locator('#panel').get_by_role('button', name='继续 Goal', exact=True).is_enabled()
    assert c.goals.get('s1')['status'] == 'blocked'
    page.unroute(pattern, fail)
    page.locator('#strip').get_by_role('button', name='继续 Goal', exact=True).click()
    page.locator('#panel').get_by_role('button', name='暂停 Goal', exact=True).wait_for()
    assert page.locator('.chat-goal-action-feedback').get_attribute('data-kind') == 'success'
    page.evaluate('cleanup()')


def test_resume_timeout_clears_busy_state_without_claiming_success(consoles):
    c, page = consoles, consoles.page
    block_goal(c)
    pending = []
    page.route('**/sessions/s1/goal/resume', lambda route: pending.append(route))
    mount_panel(c)
    page.clock.install()
    page.locator('#panel').get_by_role('button', name='继续 Goal', exact=True).click()
    page.clock.fast_forward(15001)
    page.wait_for_function("document.querySelector('.chat-goal-action-feedback').dataset.kind === 'error'")
    assert page.locator('.chat-goal-action-feedback').inner_text() == '请求等待超时，请刷新确认 Goal 状态后再重试。'
    assert page.locator('#panel').get_by_role('button', name='继续 Goal', exact=True).is_enabled()
    assert len(pending) == 1 and c.goals.get('s1')['status'] == 'blocked'
    page.evaluate('cleanup()')


def test_initial_goal_read_cannot_overwrite_resume_result(consoles):
    c, page = consoles, consoles.page
    block_goal(c)
    stale = c.goals.get('s1')
    held = []
    page.route('**/sessions/s1/goal', lambda route: held.append(route))
    mount_panel(c, wait_for_load=False)
    page.locator('#panel').get_by_role('button', name='继续 Goal', exact=True).click()
    page.locator('#panel').get_by_role('button', name='暂停 Goal', exact=True).wait_for()
    held[0].fulfill(json={'goal': stale})
    page.wait_for_function('window.goalLoaded === true')
    assert page.locator('#panel').get_by_role('button', name='暂停 Goal', exact=True).is_visible()
    assert page.locator('.chat-goal-action-feedback').get_attribute('data-kind') == 'success'
    page.evaluate('cleanup()')


def test_pending_response_does_not_write_feedback_into_another_session(consoles):
    c, page = consoles, consoles.page
    block_goal(c)
    c.goals.create('s2', '另一个会话的目标')
    pending = []
    page.route('**/sessions/s1/goal/resume', lambda route: pending.append(route))
    mount_panel(c)
    page.locator('#strip').get_by_role('button', name='继续 Goal', exact=True).click()
    page.evaluate("remount('s2')")
    page.wait_for_function("document.querySelector('.chat-goal-objective').textContent === '另一个会话的目标'")
    response = c.client.post('/sessions/s1/goal/resume', json={})
    pending[0].fulfill(status=response.status_code, json=response.json())
    page.wait_for_function("!document.querySelector('.chat-goal-icon-btn[aria-busy=true]')")
    assert page.locator('.chat-goal-action-feedback').is_hidden()
    assert page.locator('#strip .pni-summary').inner_text() == '另一个会话的目标'
    page.evaluate('cleanup()')
