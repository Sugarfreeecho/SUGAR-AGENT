from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from tests.test_details_pages_browser import details_page, browser_page
from tests.test_llm_stream_full_text_browser import function_source
from tests.test_settings_center_browser import settings_page

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def presentation_page(details_page):
    page, calls, errors, rows = details_page
    page.add_style_tag(content=(ROOT / "frontend/src/styles/app.css").read_text(encoding="utf-8"))
    page.evaluate("""() => {
        sessionStorage.removeItem('myagent-show-user-seen');
        const stream=document.createElement('section');stream.id='chat-stream';
        stream.innerHTML='<div id="presentation-slot"></div>';
        document.querySelector('.main').appendChild(stream);
        window.ctx={stream};
    }""")
    page.add_script_tag(content="""
      function humanInteractionToolSlot(){return document.getElementById('presentation-slot')}
      function applySessionEvent(){return {handled:false}}
      var executionRecordsBySession = new Map();
    """)
    page.add_script_tag(content=(ROOT / "frontend/src/app/modules/user-presentations.js").read_text(encoding="utf-8"))
    page.add_script_tag(content=function_source((ROOT / "frontend/src/app/modules/event-dispatch.js").read_text(encoding="utf-8"), "renderEvent"))
    page.add_script_tag(content=(ROOT / "frontend/src/app/state/message-renderers.js").read_text(encoding="utf-8"))
    page.evaluate("""() => {
        window.presentation={type:'show_user',session_id:'s1',tool_call_id:'call-1',
          presentation:{kind:'text',title:'实现过程',text:'内容尚未结束，Agent继续工作。',
            presentation_id:'a'.repeat(32),session_id:'s1'}};
    }""")
    return page, calls, errors, rows


def _render(page, source="sse"):
    page.evaluate("source => renderMessageRecord(ctx,{event:presentation,index:0,source},'s1')", source)


def test_live_show_opens_details_without_waiting_and_replay_does_not_reopen(presentation_page):
    page, _, errors, _ = presentation_page
    _render(page)
    assert page.locator('.show-user-plain').inner_text() == '内容尚未结束，Agent继续工作。'
    assert page.evaluate("MyAgentDock.detailsState().expanded")
    assert page.locator('.show-user-card').count() == 1
    page.evaluate('MyAgentDock.closeDetails()')
    _render(page)
    assert not page.evaluate("MyAgentDock.detailsState().expanded")
    assert page.locator('.show-user-card').count() == 1
    _render(page, 'history')
    assert not page.evaluate("MyAgentDock.detailsState().expanded")
    page.locator('.show-user-open').click()
    assert page.evaluate("MyAgentDock.detailsState().expanded")
    assert page.locator('[data-show-user-view]').count() == 1
    assert not errors, [str(e) for e in errors]


def test_history_stays_quiet_and_background_chat_does_not_steal_details(presentation_page):
    page, _, errors, _ = presentation_page
    _render(page, 'history')
    assert not page.evaluate("MyAgentDock.detailsState()?.expanded || false")
    page.evaluate("presentation.presentation.presentation_id='b'.repeat(32)")
    page.evaluate("currentSessionId='s2'")
    _render(page)
    assert not page.evaluate("MyAgentDock.detailsState()?.expanded || false")
    assert not errors, [str(e) for e in errors]


def test_plugin_console_reuses_live_plugin_frame_and_binds_source_chat(presentation_page):
    page, _, errors, _ = presentation_page
    page.evaluate("presentation.presentation={...presentation.presentation,kind:'plugin',plugin_id:'demo',page_id:'main'}")
    _render(page)
    page.wait_for_selector('.dock-plugin-page iframe')
    frame = next(frame for frame in page.frames if '/plugins/demo' in frame.url)
    frame.wait_for_function("window.bound==='s1'")
    identity = frame.evaluate('window.instance')
    frame.locator('#draft').fill('控制台未提交内容')
    page.locator('.show-user-open').click()
    assert page.locator('.dock-plugin-page').count() == 1
    assert frame.evaluate('window.instance') == identity
    assert frame.locator('#draft').input_value() == '控制台未提交内容'
    assert not errors, [str(e) for e in errors]


def test_webpage_uses_existing_browser_and_reopen_is_one_tab(presentation_page):
    page, _, errors, _ = presentation_page
    page.route('https://presentation.test/**', lambda route: route.fulfill(content_type='text/html', body='<h1>报告网页</h1>'))
    page.evaluate("presentation.presentation={...presentation.presentation,kind:'webpage',url:'https://presentation.test/report'}")
    _render(page)
    page.wait_for_selector('.dock-browser-page iframe')
    count = page.locator('.dock-browser-page').count()
    page.locator('.show-user-open').click()
    assert page.locator('.dock-browser-page').count() == count == 1
    assert page.locator('.dock-browser-page iframe').get_attribute('src') == 'https://presentation.test/report'
    assert not errors, [str(e) for e in errors]


def test_image_in_details_loads_and_text_is_not_html(presentation_page):
    page, _, errors, _ = presentation_page
    output = BytesIO()
    Image.new('RGB', (120, 120), 'white').save(output, 'PNG')
    page.route('**/presentations/*/image', lambda route: route.fulfill(content_type='image/png', body=output.getvalue()))
    page.evaluate("""() => {
        presentation.presentation={...presentation.presentation,kind:'image',image:{
          alt:'登录二维码',caption:'<img src=x onerror=alert(1)>',
          attachment:{attachmentId:'sha256:'+'a'.repeat(64),mediaType:'image/png'}}};
    }""")
    _render(page)
    page.wait_for_function("document.querySelector('.show-user-image').naturalWidth===120")
    assert page.locator('.show-user-image').get_attribute('alt') == '登录二维码'
    assert page.locator('.show-user-image-caption').inner_text() == '<img src=x onerror=alert(1)>'
    assert page.locator('.show-user-image-caption img').count() == 0
    assert not errors, [str(e) for e in errors]


def test_markdown_renders_structural_tokens_without_executable_html_or_images(presentation_page):
    page, _, errors, _ = presentation_page
    page.add_script_tag(content=(ROOT / 'frontend/node_modules/marked/lib/marked.umd.js').read_text(encoding='utf-8'))
    content = '## 结果\n\n**已完成** [危险链接](javascript:alert(1)) ![远程图片](https://track.test/image.png)\n\n<img src=x onerror=alert(1)>\n\n| 列 | 值 |\n|---|---|\n| 状态 | 成功 |'
    page.evaluate("text => {presentation.presentation={...presentation.presentation,format:'markdown',text}}", content)
    _render(page)
    assert page.locator('.show-user-document h2').inner_text() == '结果'
    assert page.locator('.show-user-document strong').inner_text() == '已完成'
    assert page.locator('.show-user-document img, .show-user-document script, .show-user-document a').count() == 0
    assert '<img src=x' in page.locator('.show-user-document').inner_text()
    assert page.locator('.show-user-document td').all_inner_texts() == ['状态', '成功']
    assert not errors, [str(e) for e in errors]


def test_image_failure_can_retry_in_details(presentation_page):
    page, _, errors, _ = presentation_page
    output = BytesIO()
    Image.new('RGB', (80, 80), 'white').save(output, 'PNG')
    attempts = []
    def serve(route):
        attempts.append(route.request.url)
        route.fulfill(status=404, body='missing') if len(attempts) == 1 else route.fulfill(content_type='image/png', body=output.getvalue())
    page.route('**/presentations/*/image*', serve)
    page.evaluate("presentation.presentation={...presentation.presentation,kind:'image',image:{alt:'图片',attachment:{attachmentId:'sha256:'+'a'.repeat(64)}}}")
    _render(page)
    page.locator('.show-user-image-error').wait_for(state='visible')
    page.locator('.show-user-view button').click()
    page.wait_for_function("document.querySelector('.show-user-image').naturalWidth===80")
    assert page.locator('.show-user-image-error').is_hidden()
    assert len(attempts) == 2
    assert not errors, [str(e) for e in errors]


def test_early_request_waits_for_dock_and_plugin_readiness(presentation_page):
    page, _, errors, rows = presentation_page
    page.evaluate("window.savedDock=MyAgentDock; window.MyAgentDock=undefined")
    _render(page)
    page.evaluate("document.dispatchEvent(new CustomEvent('myagent:plugin-ui-ready'))")
    assert page.evaluate('showUserPending.size') == 1
    page.evaluate("window.MyAgentDock=savedDock; document.dispatchEvent(new CustomEvent('myagent:dock-ready'))")
    assert page.locator('.show-user-plain').inner_text() == '内容尚未结束，Agent继续工作。'
    page.evaluate("MyAgentDock.syncPluginPages([]); presentation.presentation={...presentation.presentation,presentation_id:'c'.repeat(32),kind:'plugin',plugin_id:'demo',page_id:'main'}")
    _render(page)
    assert page.evaluate('showUserPending.size') == 1
    page.evaluate("rows=>{MyAgentDock.syncPluginPages(rows);document.dispatchEvent(new CustomEvent('myagent:plugin-ui-ready'))}", rows)
    page.wait_for_selector('.dock-plugin-page iframe')
    assert page.evaluate('showUserPending.size') == 0
    assert not errors, [str(e) for e in errors]


def test_top_notice_works_without_dock_and_is_safe_dismissible_and_replay_quiet(presentation_page):
    page, _, errors, _ = presentation_page
    page.evaluate("""() => {
        window.MyAgentDock=undefined;
        const input=document.createElement('input');input.id='composer-draft';document.body.append(input);input.focus();
        presentation.presentation={...presentation.presentation,kind:'notice',title:'准备完成',
          text:'<img src=x onerror=alert(1)>',level:'success',duration_ms:0};
    }""")
    _render(page)
    assert page.locator('.show-user-notice').get_attribute('data-level') == 'success'
    assert page.locator('.show-user-notice-text').inner_text() == '<img src=x onerror=alert(1)>'
    assert page.locator('.show-user-notice img').count() == 0
    assert page.evaluate("document.activeElement.id") == 'composer-draft'
    page.locator('.show-user-notice-close').click()
    _render(page)
    _render(page, 'history')
    assert page.locator('.show-user-notice').count() == 0
    page.locator('.show-user-open').click()
    assert page.locator('.show-user-notice').count() == 1
    page.locator('.show-user-notice-close').click()
    assert not errors, [str(e) for e in errors]


def test_notice_expires_after_reading_and_fits_a_narrow_screen(presentation_page):
    page, _, errors, _ = presentation_page
    viewport = page.viewport_size
    try:
        page.set_viewport_size({'width': 320, 'height': 800})
        page.evaluate("presentation.presentation={...presentation.presentation,kind:'notice',text:'页面可预览。',level:'warning',duration_ms:1000}")
        _render(page)
        box = page.locator('.show-user-notice').bounding_box()
        assert box['x'] >= 0 and box['x'] + box['width'] <= 320
        page.locator('.show-user-notice').hover()
        page.wait_for_timeout(1100)
        assert page.locator('.show-user-notice').is_visible()
        page.mouse.move(0, 790)
        page.locator('.show-user-notice').wait_for(state='detached', timeout=3000)
        assert not errors, [str(e) for e in errors]
    finally:
        page.set_viewport_size(viewport)


def test_history_and_background_notices_do_not_pop_up(presentation_page):
    page, _, errors, _ = presentation_page
    page.evaluate("presentation.presentation={...presentation.presentation,kind:'notice',text:'历史提示',duration_ms:0}")
    _render(page, 'history')
    assert page.locator('.show-user-card-text').inner_text() == '历史提示'
    assert page.locator('.show-user-notice').count() == 0
    page.evaluate("currentSessionId='s2';presentation.presentation.presentation_id='d'.repeat(32)")
    _render(page)
    assert page.locator('.show-user-notice').count() == 0
    assert not errors, [str(e) for e in errors]


def test_settings_request_works_without_dock_and_history_does_not_reopen(presentation_page):
    page, _, errors, _ = presentation_page
    page.evaluate("""() => {
        window.MyAgentDock=undefined;
        window.settingsCalls=[];
        openSettingsCenter=(section,options)=>{settingsCalls.push({section,options});return true};
        presentation.presentation={...presentation.presentation,kind:'settings',section:'models'};
    }""")
    _render(page)
    assert page.evaluate('settingsCalls') == [{'section': 'models', 'options': {'preserveUnsaved': True}}]
    _render(page, 'history')
    _render(page)
    assert page.evaluate('settingsCalls.length') == 1
    page.locator('.show-user-open').click()
    assert page.evaluate('settingsCalls.length') == 2
    assert not errors, [str(e) for e in errors]


def test_notification_rendering_updates_status_without_client_dispatch_or_resend(presentation_page):
    page, _, errors, _ = presentation_page
    page.evaluate("""() => {
        window.MyAgentDock=undefined;
        window.Notification=()=>{throw Error('Native notifications must be server-side')};
        presentation.presentation={...presentation.presentation,kind:'notification',text:'报告已完成。'};
    }""")
    _render(page)
    assert page.locator('.show-user-card').count() == 1
    page.evaluate("presentation.presentation.notification_status='requested'")
    _render(page)
    _render(page, 'history')
    assert page.locator('.show-user-card').count() == 1
    assert page.locator('.show-user-status').inner_text() == '已向系统请求通知。'
    assert page.locator('.show-user-open, .show-user-notice').count() == 0
    assert not errors, [str(e) for e in errors]


def test_show_user_settings_preserves_same_tab_and_guards_unsaved_changes(settings_page):
    page, requests = settings_page
    page.goto('http://settings.test/host')
    page.evaluate("openSettingsCenter('env')")
    frame = page.frame_locator('#settings-center-frame')
    frame.locator('[data-env-key="FOO"]').fill('unsaved form')
    page.add_script_tag(content=(ROOT / 'frontend/src/app/modules/user-presentations.js').read_text(encoding='utf-8'))
    page.evaluate("""() => {
        const stream=document.createElement('section');document.body.append(stream);window.ctx={stream};
        window.humanInteractionToolSlot=()=>stream;
        window.requestSettings=(section,id)=>renderShowUserEvent(ctx,{type:'show_user',
          presentation:{kind:'settings',title:'配置',section,presentation_id:id.repeat(32),session_id:'fixture'}},'fixture',{source:'sse'});
        requestSettings('env','a');
    }""")
    page.wait_for_timeout(100)
    assert frame.locator('[data-env-key="FOO"]').input_value() == 'unsaved form'
    page.once('dialog', lambda dialog: dialog.dismiss())
    page.evaluate("requestSettings('models','b')")
    page.wait_for_timeout(150)
    assert frame.locator('[data-env-key="FOO"]').input_value() == 'unsaved form'
    page.once('dialog', lambda dialog: dialog.accept())
    page.evaluate("requestSettings('models','c')")
    frame.locator('[data-act="model-add"]').wait_for()
    assert not [request for request in requests if request['method'] != 'GET']


def test_show_user_settings_guards_iframe_replacement_after_session_change(settings_page):
    page, _ = settings_page
    page.goto('http://settings.test/host')
    page.evaluate("openSettingsCenter('env')")
    frame = page.frame_locator('#settings-center-frame')
    frame.locator('[data-env-key="FOO"]').fill('keep across context change')
    original = page.locator('#settings-center-frame').get_attribute('src')
    page.once('dialog', lambda dialog: dialog.dismiss())
    page.evaluate("currentSessionId='other';openSettingsCenter('models',{preserveUnsaved:true})")
    page.wait_for_timeout(150)
    assert page.locator('#settings-center-frame').get_attribute('src') == original
    assert frame.locator('[data-env-key="FOO"]').input_value() == 'keep across context change'
    assert frame.locator('[data-env-key="FOO"]').is_visible()


def test_agent_reopen_does_not_restore_a_form_the_user_discarded(settings_page):
    page, _ = settings_page
    page.goto('http://settings.test/host')
    page.evaluate("openSettingsCenter('env')")
    frame = page.frame_locator('#settings-center-frame')
    frame.locator('[data-env-key="FOO"]').fill('discard this edit')
    page.once('dialog', lambda dialog: dialog.accept())
    page.evaluate('closeSettingsCenter()')
    page.wait_for_function("!window.__settingsCenterOpen")
    page.evaluate("openSettingsCenter('env',{preserveUnsaved:true})")
    page.wait_for_function("document.getElementById('settings-center-frame').contentDocument.querySelector('[data-env-key=FOO]')?.value==='original'")
    assert frame.locator('[data-env-key="FOO"]').input_value() == 'original'
