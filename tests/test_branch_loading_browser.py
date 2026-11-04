"""Delayed branch creation uses one request and keeps visible, recoverable UI."""
import os
from pathlib import Path

import pytest

playwright = pytest.importorskip('playwright.sync_api')
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def page():
    with playwright.sync_playwright() as runtime:
        browser = runtime.chromium.launch(headless=True, **({'channel': 'msedge'} if os.name == 'nt' else {}))
        page = browser.new_page(viewport={'width': 1000, 'height': 700})
        page.set_default_timeout(5000)
        css = (ROOT / 'frontend/src/styles/app.css').read_text(encoding='utf-8')
        page.set_content('<style>'+css+'</style><div style="max-width:760px;margin:60px auto">'
            '<div class="msg-wrap" id="wrap" data-event-index="3" data-runtime-seq="20" '
            'data-runtime-event-type="message_assistant_final"><div class="message">这是用于验证分支等待反馈的测试回答。</div>'
            '<div class="msg-toolbar"><button class="msg-tb" data-act="branch">分支</button></div></div></div>')
        page.locator('#wrap').hover()
        source = (ROOT / 'frontend/src/app/modules/message-rendering.js').read_text(encoding='utf-8')
        page.add_script_tag(content='''var currentSessionId='source',switchSessionEpoch=1,posts=[],modals=0,
            switches=[],alerts=[],stored=[],refreshes=0,resolveModal,resolveRequest,resolveSwitch;
            function openUiModal() {modals++;return new Promise(r=>resolveModal=r);}
            function historyOperationJson(url) {posts.push(url);return new Promise(r=>resolveRequest=r);}
            function switchSession(sid) {switches.push(sid);return new Promise(r=>resolveSwitch=r);}
            function showUiAlert(options) {alerts.push(options);}
            function describeServerSyncFailure(res) {return res.error;}
            function renderSessionListIfChanged() {}
            function discardCachedSessionStream() {}
            function loadSessions() {refreshes++;}
            function isSessionRunning() {return false;}
            var sessionStore={upsert:r=>stored.push(r)};
        ''' + source[source.index('var branchRequestsByAnchor'):source.index('function normalizeBranchFinalText(')]
            + source[source.index('function onMessageToolbarClick('):source.index('function attachMessageToolbar(')]
            + '''document.querySelector('[data-act="branch"]').onclick=()=>onMessageToolbarClick(wrap,'assistant','branch');''')
        yield page
        browser.close()


def begin(page):
    page.locator('[data-act="branch"]').click()
    assert page.locator('[data-act="branch"]').is_disabled()
    page.evaluate('resolveModal(true)')
    page.wait_for_function('posts.length===1')


@pytest.mark.parametrize('runtime_type', ['message_assistant_final', 'assistant_final_committed', 'ui_event'])
def test_delayed_creation_shows_feedback_and_blocks_reentry(page, runtime_type):
    page.evaluate('value => {wrap.dataset.runtimeEventType=value;}', runtime_type)
    begin(page)
    assert page.evaluate("posts[0].includes('after_seq=20')")
    page.evaluate("onMessageToolbarClick(wrap,'assistant','branch')")
    assert page.evaluate('posts.length') == 1
    assert page.evaluate('modals') == 1
    assert page.locator('.branch-operation-status').is_visible()
    assert '正在创建分支' in page.locator('.branch-operation-status').inner_text()
    page.wait_for_function("document.querySelector('.branch-operation-status').textContent.includes('1 s')")
    output = ROOT / '.analysis/branch-loading-20261030/feedback.png'
    output.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(output))
    page.evaluate("resolveRequest({ok:true,session_id:'new',session:{id:'new'}})")
    page.wait_for_function('switches.length===1')
    assert '正在加载会话' in page.locator('.branch-operation-status').inner_text()
    assert page.locator('[data-act="branch"]').is_disabled()
    page.evaluate('resolveSwitch(true)')
    page.wait_for_function('branchUiOperationsBySession.size===0')
    assert page.locator('.branch-operation-status').count() == 0


def test_existing_branch_is_reopened_after_failed_history_load(page):
    begin(page)
    page.evaluate("resolveRequest({ok:true,session_id:'new'})")
    page.wait_for_function('switches.length===1')
    page.evaluate('resolveSwitch(false)')
    page.wait_for_function('branchUiOperationsBySession.size===0')
    assert page.locator('[data-act="branch"]').inner_text() == '打开分支'
    page.locator('[data-act="branch"]').click()
    page.wait_for_function('switches.length===2')
    assert page.evaluate('posts.length') == page.evaluate('modals') == 1
    page.evaluate('resolveSwitch(true)')
    page.wait_for_function('branchUiOperationsBySession.size===0')


def test_timeout_retry_keeps_same_server_request_id(page):
    begin(page)
    page.evaluate("resolveRequest({ok:false,error:'request_timeout'})")
    page.wait_for_function('branchUiOperationsBySession.size===0')
    assert page.locator('.branch-operation-status.is-error').is_visible()
    assert page.locator('[data-act="branch"]').inner_text() == '继续检查'
    page.locator('[data-act="branch"]').click()
    page.wait_for_function('posts.length===2')
    assert page.evaluate('modals') == 1
    assert page.evaluate('posts[0]===posts[1]')
    page.evaluate("resolveRequest({ok:true,session_id:'new'})")
    page.wait_for_function('switches.length===1')
    page.evaluate('resolveSwitch(true)')
    page.wait_for_function('branchUiOperationsBySession.size===0')


def test_leaving_source_does_not_force_navigation_when_creation_finishes(page):
    begin(page)
    page.evaluate("currentSessionId='other';switchSessionEpoch++;resolveRequest({ok:true,session_id:'new'})")
    page.wait_for_function('branchUiOperationsBySession.size===0')
    assert page.evaluate('switches.length') == 0
    assert '可在会话列表打开' in page.locator('.branch-operation-status').inner_text()


def test_cancel_confirmation_unlocks_without_request(page):
    page.locator('[data-act="branch"]').click()
    page.evaluate('resolveModal(false)')
    page.wait_for_function('branchUiOperationsBySession.size===0')
    assert page.evaluate('posts.length') == 0
    assert page.locator('[data-act="branch"]').is_enabled()


def test_duplicate_helper_requests_are_coalesced(page):
    page.evaluate("() => { window.one=branchSessionOnServer(4,'source',20);window.two=branchSessionOnServer(4,'source',20); }")
    assert page.evaluate('posts.length') == 1
    page.evaluate("resolveRequest({ok:true,session_id:'new'})")
    assert page.evaluate('Promise.all([one,two]).then(rows=>rows.map(r=>r.session_id))') == ['new','new']
