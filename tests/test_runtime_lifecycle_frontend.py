import os
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]


def install_runtime(page, operation=None, instance_id="old"):
    page.add_style_tag(path=str(ROOT / "frontend/src/styles/app.css"))
    page.add_script_tag(content='''
        var currentSessionId='session', drafts=[], messageInput=document.getElementById('message-input');
        function persistInputDraft(id,text){drafts.push([id,text]);}
        function getVisibleChatStream(){return document.getElementById('slot');}
        function humanInteractionToolSlot(){return document.getElementById('slot');}
        var fixtureOperation={restart_id:'restart',target_instance_id:'old',supervisor_id:'host',phase:'awaiting_confirmation',
            revision:1,created_at:Date.now()/1000,request_digest:'digest',session_id:'session',run_id:'run',tool_call_id:'tool',
            reason:'后端已修改，需要重启',change_summary:'会话恢复检查已完成',impact:{running_tasks:3,background_jobs:1,terminals:1}};
        var posts=0, mode='pending', fixtureInstanceId='old';
        window.fetch=async function(url,options){
            if(mode==='offline')throw new TypeError('offline');
            if(options&&options.method==='POST'){
                posts++;
                fixtureOperation={...fixtureOperation,phase:JSON.parse(options.body).decision==='deny'?'denied':'authorized',revision:2};
                return {ok:true,json:async()=>({ok:true,operation:fixtureOperation})};
            }
            return {ok:true,json:async()=>({ok:true,ready:true,instance_id:fixtureInstanceId,ui_token:'ui',operations:[fixtureOperation]})};
        };
    ''')
    if operation is not None:
        page.evaluate("value => fixtureOperation=value", operation)
    page.evaluate("value => fixtureInstanceId=value", instance_id)
    page.add_script_tag(path=str(ROOT / "frontend/src/app/modules/runtime-lifecycle.js"))


def reload_runtime(page, operation, instance_id="old"):
    page.reload()
    install_runtime(page, operation, instance_id)
    page.evaluate("initRuntimeLifecycle()")
    page.wait_for_function("!runtimeLifecycle.busy && runtimeLifecycle.instanceId === fixtureInstanceId")


@pytest.fixture(scope="module")
def lifecycle_browser():
    with playwright.sync_playwright() as runtime:
        try:
            browser = runtime.chromium.launch(headless=True, **({"channel": "msedge"} if os.name == "nt" else {}))
        except playwright.Error as exc:
            pytest.skip(str(exc))
        yield browser
        browser.close()


@pytest.fixture
def page(lifecycle_browser):
    page = lifecycle_browser.new_page(viewport={"width": 1100, "height": 800})
    page.route('http://lifecycle.test/**', lambda route: route.fulfill(content_type='text/html; charset=utf-8', body=
        '<textarea id="message-input">尚未发送的草稿</textarea><button id="send-btn">发送</button><div id="slot"></div>'))
    page.goto("http://lifecycle.test/")
    install_runtime(page)
    page.evaluate("runtimeLifecycle.uiToken='ui'; acceptRuntimeLifecycleOperation(fixtureOperation)")
    yield page
    page.close()


def test_confirmation_is_visible_and_denial_keeps_draft(page):
    panel = page.locator("#runtime-lifecycle-panel")
    assert "3 个运行任务" in panel.inner_text()
    assert page.locator("#slot .runtime-lifecycle-inline").count() == 1
    panel.get_by_role("button", name="暂不重启").click()
    assert "本次未重启" in panel.inner_text()
    assert page.locator("#message-input").input_value() == "尚未发送的草稿"
    assert page.evaluate("runtimeLifecycleIsBlocked()") is False


def test_confirmation_blocks_send_then_disconnection_retains_page_and_draft(page):
    page.locator("#runtime-lifecycle-panel").get_by_role("button", name="确认重启").click()
    assert page.evaluate("runtimeLifecycleIsBlocked()") is True
    assert page.evaluate("drafts.at(-1)[1]") == "尚未发送的草稿"
    page.evaluate("mode='offline'; refreshRuntimeLifecycle()")
    assert "正在等待服务重新连接" in page.locator("#runtime-lifecycle-panel").inner_text()
    assert page.locator("#message-input").input_value() == "尚未发送的草稿"
    assert page.url == "http://lifecycle.test/"


def test_old_status_cannot_reopen_a_completed_restart(page):
    page.evaluate("acceptRuntimeLifecycleOperation({...fixtureOperation,phase:'completed',revision:5})")
    page.evaluate("acceptRuntimeLifecycleOperation({...fixtureOperation,phase:'awaiting_confirmation',revision:1})")
    assert "服务已重启" in page.locator("#runtime-lifecycle-panel").inner_text()
    assert page.locator("#runtime-lifecycle-panel").get_by_role("button", name="确认重启").count() == 0


def test_wrong_new_instance_cannot_release_restart_block(page):
    page.evaluate('''async () => {
        acceptRuntimeLifecycleOperation({...fixtureOperation,phase:'starting',revision:2});
        runtimeLifecycle.instanceId='old';
        window.fetch=async()=>({ok:true,json:async()=>({ok:true,ready:true,instance_id:'other',
            operations:[{...fixtureOperation,phase:'completed',revision:3,expected_new_instance_id:'expected'}]})});
        await refreshRuntimeLifecycle();
    }''')
    assert page.evaluate("runtimeLifecycleIsBlocked()") is True
    assert page.evaluate("runtimeLifecycle.instanceId") == "old"


def test_global_and_inline_resume_choices_are_synchronized(page):
    page.locator("#slot input[type=checkbox]").uncheck()
    assert not page.locator("#runtime-lifecycle-panel input[type=checkbox]").is_checked()
    assert page.evaluate("runtimeLifecycle.resume") is False


def test_text_is_rendered_without_html_execution_and_panel_fits_viewport(page):
    page.evaluate("acceptRuntimeLifecycleOperation({...fixtureOperation,reason:'<img src=x onerror=alert(1)>',revision:2})")
    assert page.locator("#runtime-lifecycle-panel img").count() == 0
    rectangle = page.locator("#runtime-lifecycle-panel").bounding_box()
    assert rectangle["x"] >= 0 and rectangle["x"] + rectangle["width"] <= 1100


@pytest.mark.parametrize("phase", ["completed", "denied", "cancelled"])
def test_refresh_does_not_announce_a_previous_result_again(page, phase):
    operation = page.evaluate("phase => ({...fixtureOperation,phase,revision:5,expected_new_instance_id:'new'})", phase)
    page.evaluate("operation => acceptRuntimeLifecycleOperation(operation)", operation)
    assert page.locator('#runtime-lifecycle-panel').is_visible()
    reload_runtime(page, operation, 'new')
    assert page.locator('#runtime-lifecycle-panel').is_hidden()
    assert page.evaluate('runtimeLifecycleIsBlocked()') is False
    assert page.evaluate('posts') == 0
    page.evaluate('refreshRuntimeLifecycle()')
    assert page.locator('#runtime-lifecycle-panel').is_hidden()


@pytest.mark.parametrize("phase", ["completed", "denied", "cancelled"])
def test_a_new_page_does_not_announce_historical_status(page, phase):
    operation = page.evaluate("phase => ({...fixtureOperation,phase,revision:5,expected_new_instance_id:'new'})", phase)
    page.evaluate('sessionStorage.clear()')
    reload_runtime(page, operation, 'new')
    assert page.locator('#runtime-lifecycle-panel').is_hidden()
    assert page.evaluate('runtimeLifecycleIsBlocked()') is False
    assert page.evaluate('posts') == 0


def test_refresh_during_restart_still_shows_verified_completion_once(page):
    operation = page.evaluate("""() => {
        const starting={...fixtureOperation,phase:'starting',revision:3,expected_new_instance_id:'new'};
        acceptRuntimeLifecycleOperation(starting);
        return {...starting,phase:'completed',revision:5};
    }""")
    reload_runtime(page, operation, 'new')
    assert page.locator('#runtime-lifecycle-panel').is_visible()
    assert '服务已重启' in page.locator('#runtime-lifecycle-panel').inner_text()
    assert page.evaluate('runtimeLifecycleIsBlocked()') is False
    reload_runtime(page, operation, 'new')
    assert page.locator('#runtime-lifecycle-panel').is_hidden()


def test_refresh_preserves_a_pending_confirmation_without_submitting_it(page):
    operation = page.evaluate('fixtureOperation')
    reload_runtime(page, operation)
    assert page.locator('#runtime-lifecycle-panel').get_by_role('button', name='确认重启').is_visible()
    assert page.evaluate('posts') == 0


def test_dismissed_failure_stays_dismissed_after_refresh(page):
    operation = page.evaluate("({...fixtureOperation,phase:'failed',revision:5})")
    page.evaluate('operation => acceptRuntimeLifecycleOperation(operation)', operation)
    page.locator('#runtime-lifecycle-panel').get_by_role('button', name='收起').click()
    reload_runtime(page, operation)
    assert page.locator('#runtime-lifecycle-panel').is_hidden()
    assert page.evaluate('posts') == 0
    new_operation = {**operation, 'restart_id': 'new-request', 'created_at': operation['created_at'] + 1,
                     'phase': 'awaiting_confirmation', 'revision': 1}
    page.evaluate('operation => acceptRuntimeLifecycleOperation(operation)', new_operation)
    assert page.locator('#runtime-lifecycle-panel').get_by_role('button', name='确认重启').is_visible()


def test_old_completed_instance_does_not_break_observing_the_current_service(page):
    operation = page.evaluate("({...fixtureOperation,phase:'completed',revision:5,expected_new_instance_id:'previous-instance'})")
    page.evaluate('sessionStorage.clear()')
    reload_runtime(page, operation, 'current-instance')
    assert page.evaluate('runtimeLifecycle.instanceId') == 'current-instance'
    assert page.locator('#runtime-lifecycle-panel').count() == 0
    assert page.evaluate('runtimeLifecycleIsBlocked()') is False


@pytest.mark.parametrize('replay', ['history', 'render', 'replayed_recent', 'replayed_snapshot'])
def test_chat_history_and_sse_replay_cannot_reopen_lifecycle_ui(page, replay):
    from tests.test_llm_stream_full_text_browser import function_source
    page.reload()
    install_runtime(page)
    source = (ROOT / 'frontend/src/app/modules/event-dispatch.js').read_text(encoding='utf-8')
    page.add_script_tag(content=function_source(source, 'renderEvent'))
    page.evaluate("""replay => {
        const event={type:'lifecycle_changed',operation:fixtureOperation};
        const options={source:['history','render'].includes(replay)?replay:'sse'};
        if(replay.startsWith('replayed_')) event[replay]=true;
        renderEvent({},event,0,'session',options);
    }""", replay)
    assert page.evaluate('runtimeLifecycle.operation') is None
    assert page.locator('#runtime-lifecycle-panel').count() == 0
    page.evaluate("renderEvent({},{type:'lifecycle_changed',operation:fixtureOperation},0,'session',{source:'sse'})")
    assert page.locator('#runtime-lifecycle-panel').get_by_role('button', name='确认重启').is_visible()
