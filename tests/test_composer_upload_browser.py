"""Upload completion must preserve live edits and belong to its original draft."""
import json
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api")
from tests.test_llm_stream_full_text_browser import browser_page, function_source

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def upload_page(browser_page):
    page = browser_page
    page.goto("about:blank")
    page.set_content(
        '<div class="composer-row"><div class="input-wrapper">'
        '<button id="pick"></button><textarea id="message-input"></textarea>'
        '</div></div><button id="other">Other</button>'
    )
    page.add_script_tag(content=r"""
      var messageInput = document.getElementById('message-input');
      var currentSessionId = 'A', composerDraftRevision = 0;
      var draftBySession = Object.create(null), inputPathTokenMap = Object.create(null);
      var NEW_SESSION_DRAFT_KEY = '__new_session_draft__';
      var LS_INPUT_DRAFT_PREFIX = 'myagent-input-draft-';
      var inputPathRewriteGuard = false, _inputKnownExtWinPathRe = null;
      var recentComposerQueuedFollowup = null, liveAutoFollow = false, chatContainer = null;
      var sessionStore = { setCurrentSession() {} };
      var stored = new Map();
      Object.defineProperty(window, 'localStorage', {configurable: true, value: {
        getItem: key => stored.get(key) || null,
        setItem: (key, value) => stored.set(key, String(value)),
        removeItem: key => stored.delete(key)
      }});
      window.fetch = async () => ({ok: true, json: async () => ({ok: true, files: []})});
      function pathTokenToWorkspaceOpenRel(path) { return path.replace(/\\/g, '/'); }
      function setSendButtonState() {}
      window.requests = [];
      window.errors = [];
      messageInput.addEventListener('myagent:file-paste-error', e => errors.push(e.detail));
      window.XMLHttpRequest = class {
        constructor() { this.upload = {}; requests.push(this); }
        open() {}
        send(form) { this.form = form; }
        abort() { this.aborted = true; this.onabort(); }
        progress(loaded, total) { this.upload.onprogress({loaded, total, lengthComputable: true}); }
        transferred() { this.upload.onload(); }
        respond(files, status = 200) {
          this.status = status;
          this.responseText = JSON.stringify({ok: status === 200, files, error: 'server error'});
          this.onload();
        }
      };
    """)
    rendering = (ROOT / "frontend/src/app/modules/message-rendering.js").read_text(encoding="utf-8")
    scrolling = (ROOT / "frontend/src/app/modules/session-scroll-history.js").read_text(encoding="utf-8")
    settings = (ROOT / "frontend/src/app/modules/settings.js").read_text(encoding="utf-8")
    actions = (ROOT / "frontend/src/app/state/session-actions.js").read_text(encoding="utf-8")
    ext_start = rendering.index("var LINKIFY_EXT_FRAGMENT = (")
    ext_end = rendering.index("\n);", ext_start) + 3
    setup = rendering[ext_start:ext_end]
    setup += (ROOT / "frontend/src/app/modules/input-actions.js").read_text(encoding="utf-8")
    setup += "\n".join(function_source(rendering, name) for name in (
        "trimTrailingPathPunct", "stripPathWrappingQuotes", "workspaceOpenDisplayLabel",
        "normalizeInputPathTokenIdentity", "uniqueInputPathDisplayLabel",
        "inputQuotedWindowsPathRegex", "inputKnownExtWindowsPathRegex", "inputSimpleWindowsPathRegex",
        "ensureInputPathChipHost", "inputPathHasStructuredAttachment", "refreshInputPathChips",
        "clearInputPathTokens", "removeInputPathToken", "removeInputPathTokenForPath",
        "rewriteInputWorkspacePaths", "escapeRegExpLiteral", "quotePromptPath", "expandInputPathTokens",
        "autoResizeTextarea", "repinStreamScrollAfterComposerResize", "syncComposerInputState",
    ))
    setup += "\n".join(function_source(scrolling, name) for name in (
        "stashInputDraft", "restoreInputDraft", "inputDraftStorageKey", "inputDraftPathTokenStorageKey",
        "collectDraftPathTokens", "persistDraftPathTokens", "restoreDraftPathTokens",
        "persistInputDraft", "readStoredInputDraft",
    ))
    setup += function_source(settings, "appendUploadedTextToDraft")
    setup += function_source(actions, "setCurrentSessionState")
    page.add_script_tag(content=setup)
    page.add_script_tag(path=str(ROOT / "frontend/src/vendor/myagent_path_picker.js"))
    page.add_script_tag(content="""
      MyAgentPathPicker.attachChatPicker(document.getElementById('pick'), messageInput,
        {appendUploadedText: appendUploadedTextToDraft});
      window.removeInputPathTokenForPath = removeInputPathTokenForPath;
      messageInput.addEventListener('input', syncComposerInputState);
      window.changeSession = function(sid) {
        stashInputDraft(currentSessionId);
        setCurrentSessionState(sid);
        restoreInputDraft(sid);
      };
      window.startUpload = function(name = 'image.png') {
        window.uploadDone = MyAgentPathPicker.startChatFileUpload(messageInput,
          [new File(['file-data'], name)]).then(() => 'ok', error => error.name);
      };
    """)
    return page


def uploaded(name="image.png", folder="A", image=True):
    item = {"name": name, "path": f"D:\\work\\{folder}\\{name}", "size": 20}
    if image:
        item["attachment"] = {"attachmentId": "sha256:" + "a" * 64, "bytes": 20}
    return item


def complete(page, index=0, item=None):
    page.evaluate("([index, item]) => requests[index].respond([item])", [index, item or uploaded()])
    page.wait_for_function("!messageInput.dataset.fileUploadBusy")


@pytest.mark.parametrize("name,image", [("image.png", True), ("report.md", False)])
def test_typing_and_selection_survive_upload_completion(upload_page, name, image):
    page = upload_page
    page.locator("textarea").fill("前文 后文")
    page.evaluate("name => startUpload(name)", name)
    page.locator("textarea").fill("前文 上传期间新输入 后文")
    page.evaluate("messageInput.setSelectionRange(3, 11, 'backward')")
    complete(page, item=uploaded(name=name, image=image))
    assert page.locator("textarea").input_value() == f"前文 上传期间新输入 后文 @{name}"
    assert page.evaluate("[messageInput.selectionStart, messageInput.selectionEnd]") == [3, 11]
    assert page.locator(".composer-attachment-card").count() == 1
    page.keyboard.insert_text("继续")
    assert f"@{name}" in page.locator("textarea").input_value()
    assert page.evaluate("MyAgentPathPicker.chatAttachments(messageInput).length") == 1
    assert uploaded(name=name)["path"] in page.evaluate("expandInputPathTokens(messageInput.value)")


def test_transfer_completion_has_a_processing_phase_and_clears_on_success(upload_page):
    page = upload_page
    page.evaluate("startUpload(); requests[0].progress(100, 100); requests[0].transferred()")
    assert page.locator(".chat-upload-status-label").inner_text() == "文件已传输，正在处理…"
    assert page.locator(".chat-upload-progress").get_attribute("aria-valuenow") is None
    assert page.locator(".chat-upload-progress-bar").evaluate("el => el.style.width") == "99%"
    complete(page)
    assert page.locator(".chat-upload-status").count() == 0
    assert page.locator(".input-wrapper").get_attribute("aria-busy") is None


def test_background_completion_updates_only_the_owner_and_preserves_path_tokens(upload_page):
    page = upload_page
    page.locator("textarea").fill(r'请查看 "D:\work\A\same.md"')
    page.evaluate("startUpload(); requests[0].progress(40, 100); changeSession('B')")
    assert page.locator(".chat-upload-status").count() == 0
    assert page.locator(".composer-attachment-card").count() == 0
    assert page.evaluate("messageInput.dataset.fileUploadBusy || ''") == ""
    page.locator("textarea").fill(r'另一个会话 "D:\work\B\same.md"')
    before = page.locator("textarea").input_value()
    page.locator("#other").focus()
    complete(page)
    assert page.locator("textarea").input_value() == before
    assert page.evaluate("document.activeElement.id") == "other"
    assert page.locator(".composer-attachment-card").count() == 0
    page.evaluate("changeSession('A')")
    assert page.locator(".composer-attachment-card").count() == 1
    expanded = page.evaluate("expandInputPathTokens(messageInput.value)")
    assert r"D:\work\A\same.md" in expanded
    assert r"D:\work\B\same.md" not in expanded
    assert uploaded()["path"] in expanded
    page.evaluate("changeSession('B')")
    assert page.locator(".composer-attachment-card").count() == 0
    assert r"D:\work\B\same.md" in page.evaluate("expandInputPathTokens(messageInput.value)")


def test_two_sessions_can_upload_and_finish_independently(upload_page):
    page = upload_page
    page.evaluate("startUpload(); requests[0].progress(37, 100); changeSession('B'); startUpload('report.md')")
    page.evaluate("requests[1].progress(72, 100); changeSession('A')")
    assert "37%" in page.locator(".chat-upload-status-label").inner_text()
    page.evaluate("requests[1].respond([{}])".format(json.dumps(uploaded("report.md", "B", False))))
    assert page.evaluate("messageInput.dataset.fileUploadBusy") == "1"
    assert "37%" in page.locator(".chat-upload-status-label").inner_text()
    complete(page)
    assert page.evaluate("MyAgentPathPicker.chatAttachments(messageInput)[0].name") == "image.png"
    page.evaluate("changeSession('B')")
    assert page.locator(".chat-upload-status").count() == 0
    assert page.locator(".composer-attachment-name").inner_text() == "report.md"
    assert "report.md" in page.locator("textarea").input_value()


def test_cancel_and_processing_timeout_release_the_composer_for_retry(upload_page):
    page = upload_page
    page.evaluate("startUpload()")
    page.locator(".chat-upload-cancel").click()
    page.wait_for_function("!messageInput.dataset.fileUploadBusy")
    assert page.evaluate("errors.length") == 0
    # Run the actual response-deadline callback without waiting sixty seconds.
    page.evaluate("""() => {
      window.savedSetTimeout = window.setTimeout;
      window.setTimeout = (callback, delay) => {
        if (delay === 60000) { window.responseDeadline = callback; return 123; }
        return savedSetTimeout(callback, delay);
      };
      startUpload(); requests[1].transferred(); responseDeadline();
      window.setTimeout = savedSetTimeout;
    }""")
    page.wait_for_function("!messageInput.dataset.fileUploadBusy")
    assert page.evaluate("errors[0].message") == "上传处理超时，请重试。"
    assert page.locator(".chat-upload-status").count() == 0
    page.evaluate("startUpload()")
    complete(page, 2)


@pytest.mark.parametrize("origin,destination", [(None, "B"), ("A", None)])
def test_unsaved_new_draft_is_also_isolated(upload_page, origin, destination):
    page = upload_page
    page.evaluate("sid => changeSession(sid)", origin)
    page.evaluate("startUpload()")
    page.evaluate("sid => changeSession(sid)", destination)
    page.locator("textarea").fill("当前会话内容")
    complete(page)
    assert page.locator("textarea").input_value() == "当前会话内容"
    assert page.locator(".composer-attachment-card").count() == 0
    page.evaluate("sid => changeSession(sid)", origin)
    assert page.locator(".composer-attachment-card").count() == 1
    assert uploaded()["path"] in page.evaluate("expandInputPathTokens(messageInput.value)")


def test_new_draft_materialization_moves_attachments_to_the_real_session(upload_page):
    page = upload_page
    page.evaluate("changeSession(null); startUpload()")
    complete(page)
    page.evaluate("""() => {
      MyAgentPathPicker.moveChatSession(messageInput, null, 'created');
      setCurrentSessionState('created');
    }""")
    assert page.evaluate("MyAgentPathPicker.chatAttachments(messageInput, 'created').length") == 1
    assert page.evaluate("MyAgentPathPicker.chatAttachments(messageInput, null).length") == 0
    assert page.locator(".composer-attachment-card").count() == 1


@pytest.mark.parametrize("failure", ["network", "timeout", "invalid", "server"])
def test_failed_upload_never_leaves_a_busy_status(upload_page, failure):
    page = upload_page
    page.evaluate("startUpload()")
    page.evaluate("""failure => {
      if (failure === 'network') requests[0].onerror();
      else if (failure === 'timeout') requests[0].ontimeout();
      else requests[0].respond([], failure === 'server' ? 500 : 200);
    }""", failure)
    page.wait_for_function("!messageInput.dataset.fileUploadBusy")
    assert page.locator(".chat-upload-status").count() == 0
    assert page.locator(".composer-attachment-card").count() == 0
    assert page.evaluate("errors.length") == 1
