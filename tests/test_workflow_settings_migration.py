"""Workflow consoles live in Settings and retain their session/lifecycle contract."""
from pathlib import Path

import pytest

from tests.test_details_pages_browser import details_page
from tests.test_workflow_consoles_browser import consoles, browser_page

ROOT = Path(__file__).resolve().parents[1]


def contributions(plugin_id):
    from app.plugins import load_plugin, plugin_ui_contributions
    return list(plugin_ui_contributions(load_plugin(ROOT / 'plugins' / plugin_id)))


@pytest.mark.parametrize('plugin_id', ['agent-goal', 'agent-team'])
def test_workflow_moves_from_details_to_settings(details_page, plugin_id):
    page, _, errors, _ = details_page
    rows = contributions(plugin_id)
    settings = next(row for row in rows if row['slot'] == 'settings.section')
    assert settings['target'] == 'renderer' and settings['renderer']['module'].startswith('/plugin-assets/' + plugin_id + '/')
    assert not any(row['slot'] in ('navigation', 'details.tab') for row in rows)
    # Begin with a retained tab from the old contribution, then refresh the catalog.
    page.evaluate('row => {MyAgentDock.syncPluginPages([row]); MyAgentDock.openPluginPage(row.plugin_id)}', {
        'slot': 'details.tab', 'plugin_id': plugin_id, 'id': 'main', 'title': 'Old console',
        'href': '/plugins/' + plugin_id, 'target': 'plugin-page', 'scope': 'session'})
    page.locator('.dock-plugin-page iframe').wait_for()
    page.evaluate('rows => MyAgentDock.syncPluginPages(rows)', rows)
    page.wait_for_function("document.querySelectorAll('.dock-plugin-page').length===0")
    assert page.evaluate('id => MyAgentDock.openPluginPage(id)', plugin_id) is True
    assert page.evaluate('window.settingsOpened') == 'plugin:' + plugin_id + ':main'
    page.evaluate("MyAgentDock.openDetailsTab('plugins')")
    assert page.locator('[data-dock-plugin-page^="' + plugin_id + ':"]').count() == 0
    # A saved tab can be restored after the first catalog snapshot, too.
    page.evaluate('id => { const sid=dockRightState.sessionId; const contentId="myagent-plugin://page/"+encodeURIComponent(JSON.stringify({pluginId:id,pageId:"main",sessionId:"s1"})); dockActionOpenContent(sid,{kind:"plugin-page",contentId,title:"Old saved console"},dockRightSeed(),null,DOCK_RIGHT_AREA); dockRightRender(); }', plugin_id)
    page.wait_for_function("!Object.values(MyAgentDock.detailsState().tabs).some(t=>t.kind==='plugin-page')")
    assert not errors, [str(error) for error in errors]


@pytest.mark.parametrize('plugin_id', ['agent-goal', 'agent-team'])
def test_settings_console_binds_switches_and_stops_polling(consoles, plugin_id):
    c, page = consoles, consoles.page
    page.clock.install()
    page.route('**/workflow-settings-host', lambda route: route.fulfill(content_type='text/html', body=f'''
      <style>html,body{{height:100%;margin:0}}iframe{{height:100%;width:100%;border:0}}</style>
      <iframe id="settings" src="/settings?embedded=1&session_id=s1#plugin:{plugin_id}:main"></iframe>'''))
    page.goto('http://127.0.0.1/workflow-settings-host')
    settings = page.frame_locator('#settings')
    console = settings.locator('.workflow-settings')
    console.locator('#create-card').wait_for()
    assert console.locator('#session').input_value() == 's1'
    assert console.locator('.wf-session-picker').is_visible()
    assert settings.locator('iframe').count() == 0
    assert console.locator('.st-card').count() > 0
    assert console.locator('#session').evaluate('el => el.ownerDocument === document')
    if plugin_id == 'agent-goal':
        console.locator('#new-objective').fill('从设置管理目标')
        console.get_by_role('button', name='创建并开始', exact=True).click()
        console.locator('#goal-view').wait_for()
    else:
        console.locator('#title').fill('从设置管理团队')
        console.get_by_role('button', name='创建团队', exact=True).click()
        console.locator('#team-view').wait_for()
    out = ROOT / '.analysis/workflow-consoles'
    out.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(out / (plugin_id + '-settings-native.png')), full_page=True)
    console.locator('#session').fill('s2')
    console.get_by_role('button', name='打开会话', exact=True).click()
    console.locator('#create-card').wait_for()
    # Theme/visibility updates must not undo the user's manual session choice.
    child = next(frame for frame in page.frames if '/settings?' in frame.url)
    child.evaluate("document.documentElement.className='theme-dark'")
    settings.locator('html.theme-dark').wait_for()
    assert console.locator('#session').input_value() == 's2'
    page.locator('#settings').evaluate("el => el.style.display='none'")
    page.wait_for_timeout(100)
    before = len(c.requests)
    page.clock.fast_forward(20000)
    assert len(c.requests) == before

    page.locator('#settings').evaluate("el => el.style.display='block'")
    page.wait_for_timeout(100)
    console.locator('#create-card').wait_for()
    page.clock.fast_forward(6000)
    assert len(c.requests) > before
    # Leaving the section removes its browsing context and all its polling.
    settings.locator('[data-act="nav"][data-id="general"]').click()
    console.locator('#workspace').wait_for(state='detached')
    page.wait_for_timeout(50)
    before = len(c.requests)
    page.clock.fast_forward(20000)
    assert len(c.requests) == before


def test_native_goal_forms_review_and_repeated_mounts(consoles):
    c, page = consoles, consoles.page
    page.goto('http://127.0.0.1/settings?session_id=s1#plugin:agent-goal:main')
    goal = page.locator('.workflow-goal')
    goal.locator('#new-objective').fill('原生设置验收目标')
    goal.get_by_role('button', name='创建并开始', exact=True).click()
    goal.locator('#goal-view').wait_for()
    goal.get_by_role('button', name='编辑目标', exact=True).click()
    goal.locator('#edit-objective').fill('验证原生表单与清理')
    goal.get_by_role('button', name='保存修改', exact=True).click()
    goal.locator('#edit-dialog').wait_for(state='hidden')
    goal.get_by_role('button', name='暂停目标', exact=True).click()
    goal.get_by_role('button', name='恢复目标', exact=True).click()
    goal.get_by_role('button', name='恢复执行', exact=True).click()
    goal.locator('#resume-dialog').wait_for(state='hidden')
    requested = c.goals.update_status('s1', 'completed', 'verified', report_id='native-review')
    c.goals.record_judge_result('s1', 'done', '等待验收', run_id='native-review', expected_completion_request_id=requested['completion_request_id'])
    goal.locator('#refresh').click()
    goal.locator('#review-card').wait_for()
    goal.locator('#feedback').fill('检查设置分区交互')
    goal.locator('#refresh').click()
    assert goal.locator('#feedback').input_value() == '检查设置分区交互'
    goal.get_by_role('button', name='保存审核', exact=True).click()
    page.wait_for_function("document.querySelector('.workflow-goal #notice').textContent==='审核内容已保存'")
    goal.get_by_role('button', name='确认验收', exact=True).click()
    goal.locator('#create-card').wait_for()
    # Import caching must not preserve the old controller's session/model state.
    for _ in range(2):
        page.locator('[data-act="nav"][data-id="plugin:agent-team:main"]').click()
        page.locator('.workflow-team #create-card').wait_for()
        page.locator('[data-act="nav"][data-id="plugin:agent-goal:main"]').click()
        goal.locator('#create-card').wait_for()
        assert goal.locator('#session').input_value() == 's1'
        assert goal.locator('#new-objective').input_value() == ''
    assert page.locator('#st-body iframe').count() == 0
    assert page.locator('.workflow-settings').count() == 1


def test_native_team_member_task_message_and_archive(consoles):
    c, page = consoles, consoles.page
    page.goto('http://127.0.0.1/settings?session_id=s1#plugin:agent-team:main')
    team = page.locator('.workflow-team')
    team.locator('#title').fill('原生团队')
    team.get_by_role('button', name='创建团队', exact=True).click()
    team.locator('#new-member').click()
    team.locator('#member-name').fill('Coder')
    team.locator('#member-role').fill('实现与验证')
    team.get_by_role('button', name='创建成员', exact=True).click()
    team.locator('#member-dialog').wait_for(state='hidden')
    team.locator('#new-task').click()
    team.locator('#task-title').fill('原生设置任务')
    team.get_by_role('button', name='创建任务', exact=True).click()
    team.locator('#task-dialog').wait_for(state='hidden')
    team.locator('#tasks').get_by_role('button', name='派发成员', exact=True).click()
    team.get_by_role('button', name='后台派发', exact=True).click()
    team.locator('#dispatch-dialog').wait_for(state='hidden')
    assert any(name == 'dispatch' for name, _ in c.calls)
    team.locator('#new-message').click()
    team.locator('#message-recipients').select_option('lead')
    team.locator('#message-content').fill('原生设置消息')
    team.locator('#message-form button.primary').click()
    team.locator('#message-dialog').wait_for(state='hidden')
    team.get_by_role('button', name='标为已读', exact=True).click()
    team.locator('#messages .badge[data-status=consumed]').first.wait_for()
    team.locator('#shutdown').click()
    team.locator('#complete-shutdown').click()
    team.locator('#archive').click()
    team.locator('#team-status .badge[data-status=archived]').wait_for()
    assert c.teams.read_team('s1')['status'] == 'archived'
