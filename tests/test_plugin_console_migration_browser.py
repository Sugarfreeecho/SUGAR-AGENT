"""Former default sidebar panels live in retained per-plugin detail consoles."""
from pathlib import Path
import pytest

from tests.test_details_pages_browser import details_page
from tests.test_llm_stream_full_text_browser import browser_page

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('scope', ['session', 'app'])
def test_default_panels_move_into_plugin_console_and_keep_actions(details_page, scope):
    page, _calls, errors, rows = details_page
    state = {"value": "ready", "actions": []}
    page.evaluate('rows=>MyAgentDock.syncPluginPages(rows)', [{**rows[0], 'scope': scope}])

    def projection(route):
        route.fulfill(json={"ok": True, "sessions": {sid: {"badges": [], "panels": [
            {"plugin_id": "goal.fixture", "id": "current-goal", "title": "Goal", "group": {"id": "goal", "label": "目标"},
             "variant": "info", "fields": [{"label": "Objective", "value": "Keep goal", "format": "text"}]},
            {"plugin_id": "demo", "id": "status", "title": "Plugin state", "variant": "info",
             "fields": [{"label": "State", "value": state["value"] + ':' + sid, "format": "text"}],
             "actions": [{"id": "reset", "label": "更新状态", "variant": "neutral"}]},
            {"plugin_id": "execution-tools", "id": "execution", "title": "Execution", "group": {"id": "execution", "label": "执行"},
             "variant": "info", "fields": [{"label": "Legacy", "value": "execution", "format": "text"}]},
        ]} for sid in ("s1", "s2")}})

    def action(route):
        state["actions"].append(route.request.post_data_json)
        state["value"] = "updated <script>safe</script>"
        route.fulfill(json={"ok": True})

    page.route('**/api/extensions/session-ui', projection)
    page.route('**/api/extensions/session-action', action)
    page.route('**/fixture/plugin-ui.js', lambda route: route.fulfill(content_type='application/javascript', body=(ROOT / 'frontend/src/app/plugin-ui-slots.js').read_text(encoding='utf-8')))
    page.evaluate('''() => {
      const host=document.createElement('div');host.id='chat-todo-plan';host.hidden=true;
      host.innerHTML='<div class="pubar-tabs"></div><div class="pubar-panes"></div><div id="plugin-session-panels"></div>';
      document.body.append(host);
    }''')
    page.add_script_tag(content=(ROOT / 'frontend/src/app/modules/public-sidebar.js').read_text(encoding='utf-8'))
    page.evaluate('''async () => {
      window.panelUi=await import('/fixture/plugin-ui.js');
      window.MyAgentPluginSessionPanels={mount:panelUi.mountPluginConsoleSessionPanels};
      await panelUi.refreshPluginSessionUi(['s1']);
    }''')
    assert page.locator('[data-pubar-tab=plugins], [data-pubar-tab=execution]').count() == 0
    assert page.locator('[data-pubar-pane=goal] .plugin-session-panel').count() == 1
    assert page.locator('#plugin-session-panels .plugin-session-panel').count() == 0
    page.evaluate("MyAgentDock.openPluginPage('demo')")
    summary = page.locator('.dock-plugin-page:not([hidden]) .dock-plugin-session-state')
    summary.locator('summary').click()
    assert 'ready:s1' in summary.inner_text()
    summary.get_by_role('button', name='更新状态').click()
    summary.get_by_text('updated <script>safe</script>:s1', exact=True).wait_for()
    assert state['actions'] == [{"session_id": "s1", "plugin_id": "demo", "action_id": "reset", "inputs": {}}]
    assert summary.locator('script').count() == 0
    page.evaluate("MyAgentDock.openDetailsTab('guide')")
    page.wait_for_function("document.querySelector('.dock-plugin-page .plugin-console-session-panels').children.length===0")
    page.evaluate("MyAgentDock.openPluginPage('demo')")
    summary.get_by_text('updated <script>safe</script>:s1', exact=True).wait_for()
    page.evaluate('''async () => {
      await MyAgentDock.openSession('s2');MyAgentDock.openPluginPage('demo');
    }''')
    active = page.locator('.dock-plugin-page:not([hidden]) .dock-plugin-session-state')
    active.locator('summary').click()
    active.get_by_text('updated <script>safe</script>:s2', exact=True).wait_for()
    assert not errors, [str(error) for error in errors]


def test_ui_only_plugin_gets_detail_console_without_an_iframe(details_page):
    page, _calls, errors, _rows = details_page
    page.route('**/fixture/plugin-ui.js', lambda route: route.fulfill(content_type='application/javascript', body=(ROOT / 'frontend/src/app/plugin-ui-slots.js').read_text(encoding='utf-8')))
    page.route('**/api/extensions/session-ui', lambda route: route.fulfill(json={"ok": True, "sessions": {"s1": {"badges": [], "panels": [
        {"plugin_id": "bare", "id": "status", "title": "Bare state", "variant": "info", "fields": [{"label": "State", "value": "available", "format": "text"}]}
    ]}}}))
    page.evaluate('''async () => {
      window.panelUi=await import('/fixture/plugin-ui.js');
      window.MyAgentPluginSessionPanels={mount:panelUi.mountPluginConsoleSessionPanels};
      MyAgentDock.syncPluginPages([
        {slot:'settings.section',id:'settings',plugin_id:'bare',title:'Settings',href:'/plugins/bare',target:'plugin-page',embedded:true},
        {slot:'session.panel',id:'status',plugin_id:'bare',title:'Bare console'}]);
      MyAgentDock.openPluginPage('bare');
    }''')
    page.locator('.dock-plugin-page--projection').get_by_text('available', exact=True).wait_for()
    assert page.locator('.dock-plugin-page iframe').count() == 0
    assert page.locator('.dock-plugin-page--projection details').get_attribute('open') is not None
    page.evaluate('MyAgentDock.syncPluginPages([])')
    page.wait_for_function("document.querySelectorAll('.dock-plugin-page').length===0")
    assert not errors, [str(error) for error in errors]
