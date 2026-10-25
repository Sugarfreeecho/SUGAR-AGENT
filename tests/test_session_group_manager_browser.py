from pathlib import Path
import re

import pytest

from tests.test_llm_stream_full_text_browser import browser_page

ROOT = Path(__file__).resolve().parents[1]


def function(source, name):
    return re.search(r'^(?:async )?function ' + name + r'\([\s\S]*?^}', source, re.M).group()


@pytest.fixture
def manager_page(browser_page):
    page = browser_page
    errors = []
    on_error = lambda error: errors.append(error)
    page.on('pageerror', on_error)
    css = (ROOT / 'frontend/src/styles/app.css').read_text(encoding='utf8')
    page.route('**/group-manager-fixture', lambda route: route.fulfill(content_type='text/html', body=f'<style>{css}</style>'
        '<style>body{display:block;padding:20px}.session-group{position:relative;width:280px;min-height:32px}.session-group-actions{width:auto;opacity:1;pointer-events:auto}</style>'
        '<div id="group-buttons"></div><div id="ui-modal-root" class="ui-modal-overlay"><div class="ui-modal">'
        '<p id="confirm-message"></p><button id="confirm-no">取消</button><button id="confirm-yes">确定</button></div></div>'))
    page.goto('http://127.0.0.1/group-manager-fixture')
    selectors = (ROOT / 'frontend/src/app/state/session-selectors.js').read_text(encoding='utf8')
    management = (ROOT / 'frontend/src/app/modules/session-management.js').read_text(encoding='utf8')
    module = (ROOT / 'frontend/src/app/modules/session-group-manager.js').read_text(encoding='utf8')
    setup = r'''
      var fixtureRows=Array.from({length:12},(_,i)=>({id:'session-'+i,name:'Session '+i,
        work_dir:'D:/source',effective_work_dir:'D:/source',work_dir_label:'source',last_activity_at:new Date().toISOString()}));
      var currentSessionId='session-0',draftBySession={},lastUserMessageBySession={},sessionUnreadComplete=new Set();
      var sessionStore={archivedLoaded:false,list:()=>fixtureRows,get:id=>fixtureRows.find(s=>s.id===id),
        markDeletedSession:id=>{fixtureRows=fixtureRows.filter(s=>s.id!==id)}};
      var SIDEBAR_ICON_SVG={plus:'+',dots:'…'},calls=[],confirmations=[],commits=[],switched=[],failures={};
      window.__WORK_DIR__='D:/default';
      function escapeHtml(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/"/g,'&quot;')}
      function bindUiHoverTip(){}
      function bindSidebarPopup(popup){popup.querySelector('[data-popup-trigger]').onclick=()=>popup.classList.toggle('is-open')}
      function setSidebarPopupOpen(popup,open){popup.classList.toggle('is-open',open)}
      function startNewSessionInDir(){}
      function copyWorkDirPath(){} function revealWorkDirInExplorer(){} function renameWorkDirGroup(){}
      function renderSessionListIfChanged(){} function persistSessionUnread(){}
      function scheduleTitleGenerationRefresh(){} function removeStoredInputDraft(){} function clearContextStateForSession(){}
      function discardCachedSessionStream(){} function isSessionRunning(){return false}
      function releaseDeletedSessionDock(){} function syncSessionWorkspaceUi(){}
      function beginSidebarMetadataMutation(){return 1}
      function commitSidebarMetadataMutation(token,payload){commits.push(payload)} function cancelSidebarMetadataMutation(){}
      function applyOptimisticSessionUpdate(id,patch){Object.assign(sessionStore.get(id),patch)}
      async function switchSession(id){switched.push(id);currentSessionId=id}
      async function createNewSession(){switched.push('new');currentSessionId=null}
      async function loadSessions(){}
      function listCreatedSessionWorkDirs(){return [{label:'target',path:'D:/target',absolutePath:'D:/target'}]}
      function normalizeWorkDirIdentity(p){return p.toLowerCase().split(String.fromCharCode(92)).join('/')}
      function workDirDisplayName(p){return p.split('/').pop()}
      async function pickNewSessionWorkDir(){return 'D:/picked'}
      async function fetchWithTimeout(url,options){
        calls.push({url,options});const id=url.split('/')[2];
        const status=failures[id]||200;
        const payload=status===200?{ok:true,status:'ok',session:{id,work_dir:'D:/target',effective_work_dir:'D:/target'},state_revision:calls.length}:{error:'fixture busy or protected'};
        return new Response(JSON.stringify(payload),{status});
      }
      function openUiModal(options){
        confirmations.push(options);
        const root=document.getElementById('ui-modal-root');root.classList.add('is-open');
        document.getElementById('confirm-message').textContent=options.message;
        return new Promise(resolve=>{
          document.getElementById('confirm-yes').onclick=()=>{root.classList.remove('is-open');document.body.style.overflow='';resolve(true)};
          document.getElementById('confirm-no').onclick=()=>{root.classList.remove('is-open');document.body.style.overflow='';resolve(false)};
        });
      }
    '''
    wiring = '''
      var workGroup=selectNormalSessionWorkDirGroups(fixtureRows)[0],timeGroup=selectNormalSessionTimeGroups(fixtureRows)[0];
      [workGroup,timeGroup].forEach(g=>{
        const host=document.createElement('div');host.className='session-group';host.dataset.fixtureGroup=g.isWorkDirGroup?'workdir':'time';
        host.appendChild(buildSessionGroupActions(g,g.tip||''));document.getElementById('group-buttons').appendChild(host);
      });
    '''
    page.add_script_tag(content=setup + selectors + module + function(management, 'buildSessionGroupActions')
                        + function(management, 'removeDeletedSessionFromUi') + wiring)
    assert not errors, [str(error) for error in errors]
    yield page
    page.unroute('**/group-manager-fixture')
    page.goto('about:blank')
    page.remove_listener('pageerror', on_error)


def open_manager(page, group='workdir'):
    host = page.locator(f'[data-fixture-group={group}]')
    host.hover()
    host.locator('[data-popup-trigger]').click()
    host.locator('[data-group-action=manage]').click()
    page.locator('.session-manager-dialog').wait_for()


def test_both_group_menus_manage_full_membership_and_filter_selection(manager_page):
    page = manager_page
    assert page.locator('[data-fixture-group=workdir] [data-group-action=rename]').count() == 1
    assert page.locator('[data-fixture-group=time] [data-group-action=rename]').count() == 0
    assert page.evaluate('sessionGroupSessionsVisible(workGroup).rows.length') == 5
    open_manager(page)
    assert page.locator('.session-manager-row').count() == 12
    page.locator('.session-manager-filter').fill('Session 11')
    assert page.locator('.session-manager-row').count() == 1
    page.locator('[data-manager-all]').check()
    page.locator('.session-manager-filter').fill('')
    assert page.locator('.session-manager-row input:checked').count() == 1
    assert page.locator('[data-manager-all]').evaluate('(el)=>el.indeterminate')
    page.locator('[data-manager-all]').check()
    assert page.locator('.session-manager-row input:checked').count() == 12
    page.keyboard.press('Escape')
    assert page.locator('.session-manager-dialog').count() == 0
    assert page.locator('[data-fixture-group=workdir] [data-popup-trigger]').evaluate('(el)=>el===document.activeElement')
    open_manager(page, 'time')
    assert page.locator('.session-manager-row').count() == 12


def test_move_partial_failure_keeps_failed_selected_and_updates_workspace(manager_page):
    page = manager_page
    open_manager(page)
    page.locator('[data-manager-all]').check()
    page.locator('select[aria-label="目标工作区"]').select_option('D:/target')
    page.evaluate('failures={"session-1":409,"session-2":422}')
    page.locator('[data-manager-move]').click()
    assert page.evaluate('calls.length') == 0
    # The existing confirmation remains above the management overlay.
    assert page.locator('#ui-modal-root').evaluate('(el)=>+getComputedStyle(el).zIndex') > page.locator('.session-manager-overlay').evaluate('(el)=>+getComputedStyle(el).zIndex')
    page.locator('#confirm-yes').click()
    page.wait_for_function('sessionGroupManager.busy===false && calls.length===12')
    assert page.evaluate('calls.every(c=>c.options.method==="PUT" && c.url.endsWith("/work-dir"))')
    assert page.locator('.session-manager-row input:checked').count() == 2
    assert page.locator('.session-manager-row-result.is-error').count() == 2
    assert '成功 10，失败 2' in page.locator('.session-manager-status').inner_text()
    assert page.evaluate('fixtureRows.filter(s=>s.work_dir==="D:/target").length') == 10
    assert page.evaluate('commits.length') == 1
    assert page.evaluate('document.body.style.overflow') == 'hidden'


def test_delete_confirmation_partial_failure_and_current_session_fallback(manager_page):
    page = manager_page
    open_manager(page, 'time')
    page.locator('[data-managed-session-id=session-0] input').check()
    page.locator('[data-managed-session-id=session-1] input').check()
    page.locator('[data-manager-delete]').click()
    page.locator('#confirm-no').click()
    assert page.evaluate('calls.length') == 0
    page.evaluate('failures={"session-1":500}')
    page.locator('[data-manager-delete]').click()
    page.locator('#confirm-yes').click()
    page.wait_for_function('sessionGroupManager.busy===false && calls.length===2')
    assert page.evaluate('calls.every(c=>c.options.method==="DELETE")')
    assert page.locator('[data-managed-session-id=session-0]').count() == 0
    assert page.locator('[data-managed-session-id=session-1] input').is_checked()
    assert page.evaluate('currentSessionId') == 'session-1'
    assert page.evaluate('switched.length') == 1
    assert page.evaluate('fixtureRows.length') == 11
    page.evaluate('failures={}')
    page.locator('[data-manager-delete]').click()
    page.locator('#confirm-yes').click()
    page.wait_for_function('sessionGroupManager.busy===false && calls.length===3')
    assert page.locator('[data-managed-session-id=session-1]').count() == 0


def test_pick_target_does_not_migrate_until_confirmed(manager_page):
    page = manager_page
    open_manager(page)
    page.locator('[data-manager-pick]').click()
    page.wait_for_function('document.querySelector(".session-manager-target select").value==="D:/picked"')
    assert page.evaluate('calls.length') == 0
    assert page.locator('[data-manager-move]').is_disabled()
