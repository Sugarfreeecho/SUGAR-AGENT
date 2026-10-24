"""The details column follows committed sessions, including unsent drafts."""
import pytest

from tests.test_details_pages_browser import ROOT, browser_page, details_page, plugin_frame
from tests.test_llm_stream_full_text_browser import function_source


@pytest.fixture
def draft_page(details_page):
    page, _calls, errors, _rows = details_page
    source = (ROOT / 'frontend/src/app/modules/session-management.js').read_text(encoding='utf-8')
    page.add_script_tag(content='''
      var switchSessionEpoch=0,messageLoadEpoch=0,replayingMessages=false;
      var NEW_SESSION_DRAFT_KEY='draft',messageInput=null;
      function ensurePrefetchedNewSession(){return Promise.resolve(null)}
      function cancelSmoothStreamFollowForSessionSwitch(){}
      function saveChatScrollForSession(){}
      function stashInputDraft(){}
      function prepareStashLeaving(){}
      function clearOptionalPanelsForSessionLoad(){}
      function clearTocForSessionLoad(){}
      function getVisibleChatStream(){return document.querySelector('.main')}
      function setWelcome(){}
      function restoreInputDraft(){}
      function updateSessionTitle(){}
      function syncSessionListIndicatorClasses(){}
      function setSendButtonState(){}
      function hideLoading(){}
    ''' + function_source(source, 'createNewSession'))
    yield page
    assert not errors, [str(error) for error in errors]


def test_new_draft_collapses_immediately_and_its_controls_work_before_sending(draft_page):
    page = draft_page
    page.evaluate("MyAgentDock.openDetailsTab('guide')")
    page.wait_for_function("!dockRightState.host.classList.contains('is-collapsed')")
    page.evaluate('createNewSession()')
    # A delayed sidebar redraw can still contain the old active row.
    page.evaluate("async()=>{document.querySelector('.session-item').classList.add('stale');await Promise.resolve()}")
    assert page.evaluate("currentSessionId===null && dockRightState.sessionId===DOCK_APP_SURFACE_KEY")
    assert page.evaluate("dockRightState.host.getAttribute('aria-hidden')") == 'true'
    assert not page.evaluate('MyAgentDock.detailsState().expanded')
    # Exercise the actual header collapse button without creating/sending a message.
    page.evaluate('MyAgentDock.openDetails()')
    page.locator('[data-dock-rightbar-collapse]').click()
    assert not page.evaluate('MyAgentDock.detailsState().expanded')
    page.evaluate('MyAgentDock.openDetails()')
    assert page.evaluate('MyAgentDock.detailsState().expanded')
    page.evaluate("MyAgentDock.openSession('s1')")
    assert page.evaluate('MyAgentDock.detailsState().expanded')
    assert page.locator('[data-dock-guide]').is_visible()


@pytest.mark.parametrize('enter_draft', [False, True])
def test_slow_switch_completion_cannot_replace_the_newer_session_or_draft(draft_page, enter_draft):
    page = draft_page
    page.evaluate("MyAgentDock.openDetailsTab('guide')")
    page.evaluate('''() => {
      window.switchGates={s2:new Promise(resolve=>window.finishSlowSwitch=resolve)};
      window.slowSwitch=MyAgentDock.openSession('s2');
    }''')
    # The column changes before s2's history finishes loading.
    assert page.evaluate("currentSessionId==='s2' && dockRightState.sessionId==='s2'")
    assert not page.evaluate('MyAgentDock.detailsState().expanded')
    page.evaluate("MyAgentDock.openSession('s3')")
    page.evaluate("MyAgentDock.openDetailsTab('guide')")
    if enter_draft:
        page.evaluate('createNewSession()')
    page.evaluate('async()=>{finishSlowSwitch();await slowSwitch}')
    if enter_draft:
        assert page.evaluate("currentSessionId===null && dockRightState.sessionId===DOCK_APP_SURFACE_KEY")
        assert not page.evaluate('MyAgentDock.detailsState().expanded')
    else:
        assert page.evaluate("currentSessionId==='s3' && dockRightState.sessionId==='s3'")
        assert page.evaluate('MyAgentDock.detailsState().expanded')
    page.evaluate("MyAgentDock.openSession('s3')")
    assert page.evaluate('MyAgentDock.detailsState().expanded')


def test_reused_tab_ids_release_the_previous_sessions_listeners(details_page):
    page, _calls, errors, _rows = details_page
    page.evaluate('''() => {
      window.historyRequests=[];
      dockRightFetchJSON=async url=>{
        historyRequests.push(url);
        const sid=url.split('/')[2];
        return {response:{ok:true},data:{ok:true,user_turns:[],messages:{
          range_start:0,has_older:false,events:[{type:'user',content:sid},{type:'tool_result',
            ui:{changes:[{path:sid+'.txt',snapshot_id:sid,added:1,removed:0,diff:'+'+sid}]}}]}}};
      };
      MyAgentDock.openDetailsTab('changes');
    }''')
    page.wait_for_selector('[data-dock-snapshot-id="s1"]')
    first_tab = page.evaluate("Object.values(MyAgentDock.detailsState().tabs)[0].id")
    page.evaluate('window.previousState=Object.values(dockRightState.tabState)[0]')
    for sid in ['s2', 's1', 's2', 's1']:
        page.evaluate('sid=>MyAgentDock.openSession(sid)', sid)
        page.evaluate("MyAgentDock.openDetailsTab('changes')")
        page.wait_for_selector(f'[data-dock-snapshot-id="{sid}"]')
        assert page.evaluate("Object.values(MyAgentDock.detailsState().tabs)[0].id") == first_tab
        assert page.locator('.dock-change').count() == 1
        assert page.locator('.dock-changes-list').get_attribute('data-dock-session') == sid
        assert page.evaluate('previousState.released')
        page.evaluate('window.previousState=Object.values(dockRightState.tabState)[0]')
    assert not errors, [str(error) for error in errors]


def test_workspace_request_cannot_reload_the_departing_tree_with_the_entering_session(details_page):
    page, _calls, errors, _rows = details_page
    page.evaluate('''() => {
      window.getWorkspaceRequestContext=()=>({session_id:currentSessionId});
      window.workspaceApiUrl=(url,params,context)=>url+'?'+new URLSearchParams({...context,...params});
      window.workspaceRequests=[];
      window.fetch=(url,options)=>new Promise(resolve=>workspaceRequests.push({url,signal:options.signal,
        finish(){const sid=new URL(url,location.href).searchParams.get('session_id');
          resolve({ok:true,json:async()=>({ok:true,root:'D:/'+sid,
            files:[{kind:'file',name:sid+'.txt',rel:sid+'.txt',path:'D:/'+sid+'/'+sid+'.txt'}]})});}}));
      MyAgentDock.openDetailsTab('files');
    }''')
    assert page.evaluate('workspaceRequests.length') == 1
    page.evaluate("MyAgentDock.openSession('s2')")
    assert page.evaluate('workspaceRequests[0].signal.aborted')
    assert page.evaluate('workspaceRequests.length') == 1, 'switching must not reload the departing tree'
    page.evaluate("MyAgentDock.openDetailsTab('files')")
    assert page.evaluate('workspaceRequests.length') == 2
    page.evaluate('workspaceRequests[1].finish();workspaceRequests[0].finish()')
    page.wait_for_selector('.dock-files-row[data-rel="s2.txt"]')
    assert page.locator('[data-dock-files-path]').inner_text() == 'D:/s2'
    assert page.locator('.dock-files-row[data-rel="s1.txt"]').count() == 0
    page.evaluate("MyAgentDock.openSession('s1')")
    page.evaluate('workspaceRequests[2].finish()')
    page.wait_for_selector('.dock-files-row[data-rel="s1.txt"]')
    assert page.locator('[data-dock-files-path]').inner_text() == 'D:/s1'
    assert not errors, [str(error) for error in errors]


def test_parent_and_child_share_the_column_and_retained_plugin_page(details_page):
    page, _calls, errors, _rows = details_page
    page.evaluate("MyAgentDock.openPluginPage('demo')")
    first = plugin_frame(page).evaluate('window.instance')
    page.evaluate("window.subagentCatalogStore={getAddress:id=>id==='child'?{parentSessionId:'s1'}:null}")
    page.evaluate("MyAgentDock.openSession('child')")
    assert page.evaluate("dockRightState.sessionId") == 's1'
    assert page.evaluate('MyAgentDock.detailsState().expanded')
    assert plugin_frame(page).evaluate('window.instance') == first
    page.evaluate("MyAgentDock.openSession('s2')")
    page.evaluate("MyAgentDock.openSession('s1')")
    assert plugin_frame(page).evaluate('window.instance') == first
    assert not errors, [str(error) for error in errors]
