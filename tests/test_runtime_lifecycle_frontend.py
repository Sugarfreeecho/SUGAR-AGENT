import os
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def page():
    with playwright.sync_playwright() as runtime:
        try:
            browser = runtime.chromium.launch(headless=True, **({"channel": "msedge"} if os.name == "nt" else {}))
        except playwright.Error as exc:
            pytest.skip(str(exc))
        page = browser.new_page(viewport={"width": 1100, "height": 800})
        page.goto("about:blank")
        page.set_content('<textarea id="message-input">尚未发送的草稿</textarea><button id="send-btn">发送</button><div id="slot"></div>')
        page.add_style_tag(path=str(ROOT / "frontend/src/styles/app.css"))
        page.add_script_tag(content='''
            var currentSessionId='session', drafts=[], messageInput=document.getElementById('message-input');
            function persistInputDraft(id,text){drafts.push([id,text]);}
            function getVisibleChatStream(){return document.getElementById('slot');}
            function humanInteractionToolSlot(){return document.getElementById('slot');}
            var fixtureOperation={restart_id:'restart',target_instance_id:'old',supervisor_id:'host',phase:'awaiting_confirmation',
                revision:1,created_at:Date.now()/1000,request_digest:'digest',session_id:'session',run_id:'run',tool_call_id:'tool',
                reason:'后端已修改，需要重启',change_summary:'会话恢复检查已完成',impact:{running_tasks:3,background_jobs:1,terminals:1}};
            var posts=0, mode='pending';
            window.fetch=async function(url,options){
                if(mode==='offline')throw new TypeError('offline');
                if(options&&options.method==='POST'){
                    posts++;
                    fixtureOperation={...fixtureOperation,phase:JSON.parse(options.body).decision==='deny'?'denied':'authorized',revision:2};
                    return {ok:true,json:async()=>({ok:true,operation:fixtureOperation})};
                }
                return {ok:true,json:async()=>({ok:true,ready:true,instance_id:'old',ui_token:'ui',operations:[fixtureOperation]})};
            };
        ''')
        page.add_script_tag(path=str(ROOT / "frontend/src/app/modules/runtime-lifecycle.js"))
        page.evaluate("runtimeLifecycle.uiToken='ui'; acceptRuntimeLifecycleOperation(fixtureOperation)")
        yield page
        browser.close()


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
    assert page.url == "about:blank"


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
