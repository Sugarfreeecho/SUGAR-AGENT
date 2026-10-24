"""Keep live card editors intact while pending requests are refreshed."""

import os
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def human_page():
    with playwright.sync_playwright() as runtime:
        browser = runtime.chromium.launch(
            headless=True, **({"channel": "msedge"} if os.name == "nt" else {})
        )
        page = browser.new_page()
        page.route("http://human-interaction.test/", lambda route: route.fulfill(
            content_type="text/html", body="""
            <style>.human-question-pane{display:none}.human-question-pane.is-active{display:block}
            .hidden{display:none}</style>
            <div id="chat-stream"><div class="process-aggregate"><div class="process-aggregate-body">
            <div class="feed-item feed--tool" data-tool-call-id="tool-1" data-execution-id="execution-1">
            <div class="human-interaction-tool-slot"></div></div></div></div></div>
            """
        ))
        page.goto("http://human-interaction.test/")
        page.add_script_tag(content="""
            var currentSessionId = 'parent', sessionsList = null;
            function normalizeSendableText(value) { return String(value || '').trim(); }
            function isInputSubmitShortcut(event) {
                return !event.isComposing && event.key === 'Enter' && (event.ctrlKey || event.metaKey);
            }
            var record = {
                kind: 'question', interaction_id: 'question-1', session_id: 'parent',
                status: 'pending', request_version: 1, request_digest: 'digest-1',
                tool_call_id: 'tool-1', execution_id: 'execution-1',
                questions: [{question_id: 'q1', header: '布局', question: '如何调整布局？',
                    options: [{option_id: 'o1', label: '按可用宽度', description: '自动调整'}]}]
            };
            var resolveRequests = 0, completeResolve;
            window.fetch = async function (url, init) {
                if (init && url.endsWith('/resolve')) {
                    resolveRequests++;
                    return new Promise(resolve => { completeResolve = () => resolve({
                        ok: true, json: async () => ({ok: true, interaction: {
                            ...record, status: 'resolved', answers: JSON.parse(init.body).answers
                        }})
                    }); });
                }
                return {ok: true, json: async () => JSON.parse(JSON.stringify(
                    url.includes('/approvals?')
                        ? {approvals: record.kind === 'approval' ? [record] : []}
                        : {interactions: record.kind === 'question' ? [record] : []}
                ))};
            };
        """)
        page.add_script_tag(content=(ROOT / "frontend/src/app/modules/human-interactions.js").read_text(
            encoding="utf-8"
        ))
        yield page
        browser.close()


@pytest.mark.parametrize("owner", ["parent", "child"])
def test_background_refresh_preserves_editor_focus_selection_and_draft(human_page, owner):
    page = human_page
    page.evaluate("""owner => {
        record.session_id = owner;
        renderHumanInteractionEvent(null, {...record, type: 'interaction_requested'}, 'parent');
    }""", owner)
    editor = page.locator(".human-other-input")
    editor.click()
    page.keyboard.insert_text("现在输入的答案")
    editor.evaluate("el => { window.originalEditor = el; el.setSelectionRange(2, 4, 'backward'); }")
    # SSE and snapshot serializers may order object fields differently.
    page.evaluate("record.questions = record.questions.map(q => Object.fromEntries(Object.entries(q).reverse()))")
    for _ in range(3):
        assert page.evaluate("refreshHumanInteractions('parent')")
        page.evaluate("renderHumanInteractionEvent(null, {...record, type: 'interaction_requested'}, 'parent')")
        assert editor.evaluate("el => el === originalEditor && document.activeElement === el")
        assert editor.evaluate("el => [el.selectionStart, el.selectionEnd, el.selectionDirection]") == [2, 4, "backward"]
    page.keyboard.insert_text("继续")
    assert editor.input_value() == "现在继续的答案"
    assert page.locator(".human-other-mark").is_checked()
    draft = page.evaluate("JSON.parse(sessionStorage.getItem(humanInteractionDraftKey(record.session_id, 'question-1', 1)))")
    assert draft["others"]["q1"] == "现在继续的答案"
    assert page.locator(".human-interaction-source").count() == (1 if owner == "child" else 0)


def test_background_refresh_does_not_interrupt_chinese_composition(human_page):
    page = human_page
    assert page.evaluate("refreshHumanInteractions('parent')")
    editor = page.locator(".human-other-input")
    editor.click()
    editor.evaluate("""el => {
        window.originalEditor = el; window.compositionEvents = [];
        for (const type of ['compositionstart', 'compositionend']) {
            el.addEventListener(type, event => compositionEvents.push(event.type));
        }
    }""")
    cdp = page.context.new_cdp_session(page)
    cdp.send("Input.imeSetComposition", {"text": "拼", "selectionStart": 1, "selectionEnd": 1})
    assert page.evaluate("refreshHumanInteractions('parent')")
    assert editor.evaluate("el => el === originalEditor && document.activeElement === el")
    assert page.evaluate("compositionEvents") == ["compositionstart"]
    cdp.send("Input.imeSetComposition", {"text": "拼音", "selectionStart": 2, "selectionEnd": 2})
    cdp.send("Input.insertText", {"text": "拼音输入"})
    assert editor.input_value() == "拼音输入"
    assert page.evaluate("compositionEvents") == ["compositionstart", "compositionend"]


def test_approval_refresh_and_analysis_preserve_rejection_editor(human_page):
    page = human_page
    page.evaluate("""() => {
        record = {kind: 'approval', approval_id: 'approval-1', session_id: 'parent',
            status: 'pending', request_version: 1, request_digest: 'approval-digest',
            tool_call_id: 'tool-1', execution_id: 'execution-1', title: '执行操作', tool: 'shell'};
    }""")
    assert page.evaluate("refreshHumanInteractions('parent')")
    page.locator(".human-deny-btn").click()
    editor = page.locator(".human-approval-rejection-input")
    page.keyboard.insert_text("请先保留原文件")
    editor.evaluate("el => { window.originalEditor = el; el.setSelectionRange(3, 3); }")
    assert page.evaluate("refreshHumanInteractions('parent')")
    page.evaluate("""() => {
        record.analysis = {recommendation: 'deny', risk: 'high', reason: '建议先检查文件'};
        renderHumanInteractionEvent(null, {...record, type: 'approval_analyzed'}, 'parent');
    }""")
    assert page.evaluate("refreshHumanInteractions('parent')")
    assert editor.evaluate("el => el === originalEditor && document.activeElement === el && el.selectionStart === 3")
    assert editor.input_value() == "请先保留原文件"
    assert page.locator(".human-approval-rejection-editor").is_visible()
    assert page.locator(".human-deny-btn").inner_text() == "确认拒绝"
    assert "建议拒绝" in page.locator(".human-approval-analysis").inner_text()


def test_refresh_preserves_submission_guard_and_resolved_card_is_readonly(human_page):
    page = human_page
    assert page.evaluate("refreshHumanInteractions('parent')")
    page.locator(".human-other-input").fill("保留当前布局")
    page.locator(".human-confirm-btn").click()
    assert page.evaluate("resolveRequests") == 1
    assert page.evaluate("refreshHumanInteractions('parent')")
    assert page.locator(".human-interaction-card").get_attribute("data-submitting") == "1"
    page.locator(".human-confirm-btn").click()
    assert page.evaluate("resolveRequests") == 1
    page.evaluate("completeResolve()")
    page.wait_for_selector('.human-interaction-card[data-status="resolved"]')
    assert page.locator(".human-other-input").is_disabled()
    assert page.locator(".human-other-input").input_value() == "保留当前布局"


def test_changed_request_rebuilds_card_and_uses_new_version_draft(human_page):
    page = human_page
    assert page.evaluate("refreshHumanInteractions('parent')")
    page.locator(".human-other-input").fill("旧版答案")
    page.evaluate("""() => {
        window.originalCard = document.querySelector('.human-interaction-card');
        record.request_version = 2;
        record.request_digest = 'digest-2';
        record.questions[0].question = '更新后的问题';
    }""")
    assert page.evaluate("refreshHumanInteractions('parent')")
    assert page.locator(".human-interaction-card").evaluate("el => el !== originalCard")
    assert page.locator(".human-question-text").inner_text() == "更新后的问题"
    assert page.locator(".human-other-input").input_value() == ""
    page.evaluate("""() => {
        window.originalCard = document.querySelector('.human-interaction-card');
        record.request_digest = 'corrected-digest';
        record.questions[0].question = '修正后的问题';
    }""")
    assert page.evaluate("refreshHumanInteractions('parent')")
    assert page.locator(".human-interaction-card").evaluate("el => el !== originalCard")
    assert page.locator(".human-question-text").inner_text() == "修正后的问题"


def test_question_image_loads_in_card_preserves_draft_and_opens_viewer(human_page):
    from io import BytesIO
    from PIL import Image
    output = BytesIO()
    Image.new("RGB", (200, 200), "white").save(output, "PNG")
    page = human_page
    page.route("**/interactions/question-1/images/q1/0", lambda route: route.fulfill(
        content_type="image/png", body=output.getvalue()))
    page.add_script_tag(content=(ROOT / "frontend/src/app/modules/workspace-media.js").read_text(encoding="utf-8"))
    page.evaluate("""() => {
        record.questions[0].images = [{alt: '登录二维码', caption: '<img src=x onerror=alert(1)>',
            attachment: {attachmentId: 'sha256:' + 'a'.repeat(64), mediaType: 'image/png', width: 200, height: 200}}];
        renderHumanInteractionEvent(null, {...record, type: 'interaction_requested'}, 'parent');
    }""")
    image = page.locator(".human-question-image")
    page.wait_for_function("document.querySelector('.human-question-image').naturalWidth === 200")
    assert image.get_attribute("src") == "/sessions/parent/interactions/question-1/images/q1/0"
    assert image.get_attribute("alt") == "登录二维码"
    assert page.locator(".human-question-image-caption").inner_text() == "<img src=x onerror=alert(1)>"
    assert page.locator(".human-question-image-caption img").count() == 0
    page.locator(".human-other-input").fill("扫码后请核实登录状态")
    image.evaluate("el => window.originalImage = el")
    assert page.evaluate("refreshHumanInteractions('parent')")
    assert image.evaluate("el => el === originalImage")
    assert page.locator(".human-other-input").input_value() == "扫码后请核实登录状态"
    page.locator(".human-question-image-trigger").click()
    assert page.locator(".attachment-image-viewer").get_attribute("open") is not None
    assert page.locator(".attachment-image-viewer img").get_attribute("alt") == "登录二维码"


def test_question_image_failure_can_retry_and_never_loads_raw_model_url(human_page):
    from io import BytesIO
    from PIL import Image
    output = BytesIO()
    Image.new("RGB", (60, 60), "white").save(output, "PNG")
    page = human_page
    attempts = []
    def serve(route):
        attempts.append(route.request.url)
        if len(attempts) == 1:
            route.fulfill(status=404, body="not found")
        else:
            route.fulfill(content_type="image/png", body=output.getvalue())
    page.route("**/images/q1/0*", serve)
    page.evaluate("""() => {
        record.questions[0].images = [{alt: '二维码', data_url: 'https://untrusted.test/track.png',
            attachment: {attachmentId: 'sha256:' + 'a'.repeat(64), mediaType: 'image/png'}},
            {data_url: 'javascript:alert(1)', alt: 'invalid'}];
        renderHumanInteractionEvent(null, {...record, type: 'interaction_requested'}, 'parent');
    }""")
    page.locator(".human-question-image-error").wait_for(state="visible")
    assert page.locator(".human-question-image").count() == 1
    assert "untrusted.test" not in page.locator(".human-question-image").get_attribute("src")
    page.locator(".human-question-image-retry").click()
    page.wait_for_function("document.querySelector('.human-question-image').naturalWidth === 60")
    assert page.locator(".human-question-image-error").is_hidden()
    assert len(attempts) == 2
