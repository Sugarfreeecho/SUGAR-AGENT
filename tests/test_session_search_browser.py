import json
from pathlib import Path
import re

import pytest

from tests.test_llm_stream_full_text_browser import browser_page

ROOT = Path(__file__).resolve().parents[1]
A = '11111111-1111-4111-8111-111111111111'
B = '22222222-2222-4222-8222-222222222222'


@pytest.fixture
def search_page(browser_page):
    page = browser_page
    html = (ROOT / 'frontend/index.html').read_text(encoding='utf8')
    shell = html[html.index('<div id="session-list-head"'):html.index('<div class="sidebar-runtime"')]
    css = (ROOT / 'frontend/src/styles/app.css').read_text(encoding='utf8')
    page.route('**/search-fixture', lambda route: route.fulfill(content_type='text/html', body=f'<style>{css}</style>'
        '<style>body{display:block}aside{width:300px;height:520px;display:flex;flex-direction:column}'
        '.sessions-list{overflow:auto;flex:1}#chat-stream{position:absolute;left:350px;top:100px}</style>'
        f'<aside>{shell}</aside><div id="chat-stream"><div data-event-index="1">answer</div></div>'))
    page.goto('http://127.0.0.1/search-fixture')
    source = (ROOT / 'frontend/src/app/modules/session-search.js').read_text(encoding='utf8')
    selectors = (ROOT / 'frontend/src/app/state/session-selectors.js').read_text(encoding='utf8')
    management = (ROOT / 'frontend/src/app/modules/session-management.js').read_text(encoding='utf8')
    expanded = re.search(r'^function setSessionSearchExpanded\([\s\S]*?^}', management, re.M).group()
    apply_filter = re.search(r'^function applySessionListSearch\([\s\S]*?^}', management, re.M).group()
    menu = re.search(r'^function buildSessionViewMenuMarkup\([\s\S]*?^}', management, re.M).group()
    mount = re.search(r'^\(function mountSessionListHeadOnce\([\s\S]*?^}\)\(\);', management, re.M).group()
    setup = f'''
      var sessionsList=document.getElementById('sessions-list'), currentSessionId=null;
      var fixtureRows=[{{id:'{A}',name:'needle local',archived:false,last_activity_at:new Date().toISOString()}},
        {{id:'{B}',name:'other local',archived:false,last_activity_at:new Date().toISOString()}}];
      var sessionStore={{list:()=>fixtureRows,archivedList:()=>[],get:id=>fixtureRows.find(s=>s.id===id),isDeletedSessionTombstoned:()=>false}};
      function renderSessionListIfChanged(){{
        if(sessionSearchState.dialog && sessionSearchState.q){{observeSessionSearchStore();renderSessionSearchResults()}}
        sessionsList.innerHTML=selectSessionSections().normalGroups.map(g=>'<div class="normal-group" data-group="'+g.key+'">'+g.sessions.map(s=>'<p class="normal-session">'+s.name+'</p>').join('')+'</div>').join('')
          +(getSessionListSearchQuery()?'':Array.from({{length:50}},(_,i)=>'<p>normal '+i+'</p>').join(''));
      }}
      var SIDEBAR_ICON_SVG={{check:'✓'}};
      function bindUiHoverTip(){{}}function mountSessionImportOnce(){{}}function syncSessionViewMenu(){{}}function syncSessionListHead(){{}}
      function bindSidebarPopup(popup){{popup.querySelector('[data-popup-trigger]').onclick=()=>popup.classList.toggle('is-open')}}
      function setSidebarPopupOpen(popup,value){{popup.classList.toggle('is-open',value)}}
      window.opened=[];window.alerts=[];window.jumps=[];
      async function switchSession(id){{currentSessionId=id;opened.push(id)}}
      async function scrollToUserTurnOrLoadOlder(i){{jumps.push(i)}}
      async function loadHistoryWindowAroundEventIndex(){{return true}}
      function getVisibleChatStream(){{return document.getElementById('chat-stream')}}
      async function showUiAlert(o){{alerts.push(o)}}
      var nativeFetch=window.fetch.bind(window);window.searchCalls=[];
      window.fetch=async function(url,opts){{
        if(url==='/sessions/search'){{
          searchCalls.push(JSON.parse(opts.body));
          return new Response(new ReadableStream({{start(controller){{window.searchStream=controller}}}}),{{headers:{{'Content-Type':'text/event-stream'}}}});
        }}
        if(url.includes('/search-hit'))return new Response(JSON.stringify({{ui_index:1,turn_index:0,content:'needle answer',archive:false}}));
        return nativeFetch(url,opts);
      }};
      window.sendSearch=function(name,data){{searchStream.enqueue(new TextEncoder().encode('event: '+name+'\\ndata: '+JSON.stringify(data)+'\\n\\n'))}};
    '''
    page.add_script_tag(content=setup + selectors + '\n' + source + '\n' + expanded + '\n' + apply_filter + '\n' + menu + '\n' + mount + '\nrenderSessionListIfChanged();')
    yield page
    page.unroute('**/search-fixture')
    page.goto('about:blank')


def emit(page, name, data):
    page.evaluate('([name,data])=>sendSearch(name,data)', [name, data])


def session(sid=A, archived=False):
    return dict(id=sid, name='needle archived' if archived else 'needle local', archived=archived, last_activity_at='2026-10-25')


def hit(ref='history:test:event:3', snippet='needle answer'):
    return dict(ref=ref, source='assistant', label='助手回复', snippet=snippet, highlights=[[0, 6]], source_version='version')


def finish(page, phase):
    emit(page, 'phase_done', dict(phase=phase, cursor=None, scanned=1, total=1))


def open_advanced(page):
    if not page.locator('#session-search-box').is_visible():
        page.locator('#session-search-btn').click()
    page.locator('#session-advanced-search-btn').click()
    page.locator('#session-advanced-search-input').wait_for()


def test_sidebar_keeps_local_filter_and_advanced_search_is_independent(search_page):
    page = search_page
    page.keyboard.press('Control+k')
    page.locator('#session-search-input').fill('needle')
    page.wait_for_timeout(350)
    assert page.evaluate('searchCalls.length') == 0
    assert page.locator('.normal-group').count() == 1
    assert page.locator('.normal-session').all_inner_texts() == ['needle local']
    page.locator('#chat-stream').click()
    assert page.locator('#session-search-box').is_visible()
    page.evaluate('window.sidebarBefore=sessionsList.innerHTML')
    open_advanced(page)
    assert page.locator('.session-manager-dialog.session-advanced-search-dialog').count() == 1
    assert page.locator('#session-advanced-search-input').input_value() == 'needle'
    assert page.locator('aside #session-search-scope').count() == 0
    page.locator('#session-advanced-search-input').fill('other')
    page.wait_for_function('searchCalls.length===1')
    assert page.evaluate('getSessionListSearchQuery()') == 'needle'
    assert page.evaluate('sessionsList.innerHTML===sidebarBefore')
    page.locator('[data-advanced-close]').click()
    assert page.locator('#session-search-input').input_value() == 'needle'
    page.locator('#session-search-clear').click()
    assert page.locator('#session-search-box').is_hidden()
    assert page.locator('.normal-session').count() == 2
    page.locator('#session-view-options [data-popup-trigger]').click()
    page.locator('[data-session-advanced-search]').click()
    assert page.locator('#session-advanced-search-input').is_visible()
    page.keyboard.press('Escape')
    assert page.locator('.session-advanced-search-dialog').count() == 0


def test_progressive_merge_keyboard_highlight_and_restore(search_page):
    page = search_page
    page.evaluate('sessionsList.scrollTop=180;window.originalScroll=sessionsList.scrollTop')
    page.evaluate('window.sidebarBefore=sessionsList.innerHTML')
    open_advanced(page)
    assert page.locator('#session-advanced-search-input').evaluate('(el)=>el===document.activeElement')
    page.locator('#session-advanced-search-input').fill('needle')
    # Immediate preview precedes debounce/network.
    assert page.locator('.session-search-result').count() == 1
    assert page.evaluate('searchCalls.length') == 0
    page.wait_for_function('searchCalls.length===1')
    assert page.evaluate('searchCalls[0].scope') == 'all'
    emit(page, 'upsert', dict(phase='metadata', session=session(), hits=[dict(source='title', label='标题', snippet='needle local', highlights=[[0, 6]])]))
    finish(page, 'metadata')
    page.evaluate('window.originalNode=document.querySelector(".session-search-result")')
    emit(page, 'upsert', dict(phase='active_content', session=session(), hits=[hit()], hit_cursor=None))
    finish(page, 'active_content')
    assert page.locator('.session-search-result').count() == 1
    assert page.evaluate('originalNode===document.querySelector(".session-search-result")')
    emit(page, 'upsert', dict(phase='archived_content', session=session(B, True), hits=[hit('archive-hit', '<img src=x onerror=alert(1)> needle')], hit_cursor=None))
    finish(page, 'archived_content')
    emit(page, 'done', {})
    page.evaluate('searchStream.close()')
    page.wait_for_function('document.querySelectorAll(".session-search-result").length===2')
    assert page.locator('.session-search-badge').inner_text() == '已归档'
    assert page.locator('.session-search-results img').count() == 0
    assert page.locator('.session-search-results mark').count() >= 2
    page.locator('.session-search-expand').first.click()
    assert page.locator('.session-search-hit').count() == 1
    page.locator('#session-advanced-search-input').focus()
    page.keyboard.press('ArrowDown')
    page.keyboard.press('Enter')
    page.wait_for_function('opened.length===1 && jumps.length===1')
    assert page.evaluate('opened[0]') == A
    assert page.evaluate('jumps[0]') == 0
    assert page.locator('.session-advanced-search-dialog').count() == 0
    assert page.evaluate('sessionsList.innerHTML===sidebarBefore')
    assert page.evaluate('sessionsList.scrollTop===originalScroll')
    page.locator('#session-search-input').focus()
    page.keyboard.press('Escape')
    assert page.locator('#session-search-box').is_hidden()
    assert page.evaluate('getSessionListSearchQuery()') == ''


def test_composition_scope_abort_and_failure_retry(search_page):
    page = search_page
    open_advanced(page)
    page.locator('#session-advanced-search-input').dispatch_event('compositionstart')
    page.locator('#session-advanced-search-input').fill('needle')
    page.wait_for_timeout(350)
    assert page.evaluate('searchCalls.length') == 0
    page.locator('#session-advanced-search-input').dispatch_event('compositionend')
    page.wait_for_function('searchCalls.length===1')
    page.evaluate('window.oldStream=searchStream')
    page.locator('#session-search-scope').select_option('archived')
    page.wait_for_function('searchCalls.length===2')
    assert page.evaluate('searchCalls[1].scope') == 'archived'
    # Old pending response must never repopulate the new query.
    page.evaluate(r'''() => {try {oldStream.enqueue(new TextEncoder().encode('event: upsert\ndata: '+JSON.stringify({phase:'metadata',session:{id:'stale',name:'stale'},hits:[]})+'\n\n'));oldStream.close()}catch(_){}}''')
    assert page.locator('[data-search-session-id=stale]').count() == 0
    emit(page, 'error', dict(phase='metadata', message='fixture failure'))
    finish(page, 'active_content')
    finish(page, 'archived_content')
    emit(page, 'done', {})
    page.evaluate('searchStream.close()')
    page.locator('.session-search-more').filter(has_text='重试').wait_for()
    assert page.locator('.session-search-empty').count() == 0
    page.locator('.session-search-more').filter(has_text='重试').click()
    page.wait_for_function('searchCalls.length===3')
    assert page.evaluate('searchCalls[2].phase') == 'metadata'
    page.locator('#session-advanced-search-input').fill('new')
    page.wait_for_function('searchCalls.length===4')
    finish(page, 'metadata'); finish(page, 'active_content'); finish(page, 'archived_content'); emit(page, 'done', {})
    page.evaluate('searchStream.close()')
    page.locator('.session-search-empty').wait_for()


def test_advanced_clear_and_close_cancel_only_advanced_requests(search_page):
    page = search_page
    open_advanced(page)
    page.locator('#session-advanced-search-input').fill('needle')
    page.wait_for_function('searchCalls.length===1')
    page.evaluate('window.oldStream=searchStream;window.sidebarBefore=sessionsList.innerHTML')
    page.locator('[data-advanced-clear]').click()
    assert page.locator('.session-advanced-search-dialog').is_visible()
    assert page.locator('#session-advanced-search-input').input_value() == ''
    assert page.locator('.session-search-result').count() == 0
    page.locator('#session-advanced-search-input').fill('new')
    page.wait_for_function('searchCalls.length===2')
    page.keyboard.press('Escape')
    page.evaluate(r'''() => {try {searchStream.enqueue(new TextEncoder().encode('event: upsert\ndata: '+JSON.stringify({phase:'metadata',session:{id:'late',name:'late'},hits:[]})+'\n\n'));searchStream.close()}catch(_){}}''')
    assert page.locator('.session-advanced-search-dialog').count() == 0
    assert page.locator('.session-search-result').count() == 0
    assert page.evaluate('sessionsList.innerHTML===sidebarBefore')
    assert page.locator('#session-advanced-search-btn').evaluate('(el)=>el===document.activeElement')
