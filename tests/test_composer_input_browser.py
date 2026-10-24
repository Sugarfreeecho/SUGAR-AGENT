"""Composer sizing and selection must follow the displayed text after path rewrites."""
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api")
from tests.test_llm_stream_full_text_browser import browser_page, function_source

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def composer_page(browser_page):
    page = browser_page
    rendering = (ROOT / "frontend/src/app/modules/message-rendering.js").read_text(encoding="utf-8")
    styles = (ROOT / "frontend/src/styles/app.css").read_text(encoding="utf-8")
    page.set_content(
        f"<!doctype html><style>{styles}</style>"
        '<div id="composer" style="width:300px"><div class="input-wrapper">'
        '<textarea id="message-input" rows="1"></textarea></div></div>'
    )
    setup = r"""
      var messageInput = document.getElementById('message-input');
      var inputPathTokenMap = {}, inputPathRewriteGuard = false;
      var currentSessionId = 'composer', recentComposerQueuedFollowup = null;
      var liveAutoFollow = false, chatContainer = null;
      var savedDraft = '';
      var _inputKnownExtWinPathRe = null;
      function pathTokenToWorkspaceOpenRel(path) { return path.replace(/\\/g, '/'); }
      function persistInputDraft(sessionId, text) { savedDraft = text; }
    """
    ext_start = rendering.index("var LINKIFY_EXT_FRAGMENT = (")
    ext_end = rendering.index("\n);", ext_start) + 3
    setup += rendering[ext_start:ext_end]
    setup += (ROOT / "frontend/src/app/modules/input-actions.js").read_text(encoding="utf-8")
    setup += "\n".join(function_source(rendering, name) for name in (
        "trimTrailingPathPunct", "stripPathWrappingQuotes", "workspaceOpenDisplayLabel",
        "normalizeInputPathTokenIdentity", "uniqueInputPathDisplayLabel",
        "inputQuotedWindowsPathRegex", "inputKnownExtWindowsPathRegex", "inputSimpleWindowsPathRegex",
        "ensureInputPathChipHost", "inputPathHasStructuredAttachment", "refreshInputPathChips",
        "rewriteInputWorkspacePaths", "escapeRegExpLiteral", "quotePromptPath", "expandInputPathTokens",
        "autoResizeTextarea", "repinStreamScrollAfterComposerResize", "syncComposerInputState",
    ))
    setup += "\nmessageInput.addEventListener('input', syncComposerInputState);"
    page.add_script_tag(content=setup)
    return page


@pytest.mark.parametrize("width", [180, 300, 900])
@pytest.mark.parametrize("placeholder", [
    "说说你想做什么…（Enter 发送 · Shift/Ctrl/Cmd + Enter 换行）",
    "What would you like to do? (Enter to send · Shift/Ctrl/Cmd + Enter for a new line)",
    "Agent运行中，输入后续任务",
])
def test_empty_composer_keeps_one_line(composer_page, width, placeholder):
    result = composer_page.evaluate("""({width, placeholder}) => {
      document.getElementById('composer').style.width = width + 'px';
      messageInput.placeholder = '';
      autoResizeTextarea();
      const baseline = messageInput.getBoundingClientRect().height;
      messageInput.placeholder = placeholder;
      autoResizeTextarea();
      return {baseline, height: messageInput.getBoundingClientRect().height,
        scrollHeight: messageInput.scrollHeight, clientHeight: messageInput.clientHeight,
        inputWidth: messageInput.getBoundingClientRect().width};
    }""", {"width": width, "placeholder": placeholder})
    assert result["height"] <= result["baseline"] + 1
    assert result["scrollHeight"] <= result["clientHeight"] + 1
    assert result["inputWidth"] < width


def test_long_pasted_path_sizes_the_short_display_and_keeps_the_caret(composer_page):
    page = composer_page
    prefix, suffix = "请查看 ", " 这里是后面的说明"
    path = "D:\\work\\" + "very-long-folder\\" * 18 + "image.png"
    page.locator("#message-input").fill(prefix + suffix)
    page.evaluate("pos => messageInput.setSelectionRange(pos, pos)", len(prefix))
    # Browser insertion fires the same input listener as a native text paste.
    page.keyboard.insert_text('"' + path + '"')
    result = page.evaluate("""() => {
      const height = messageInput.getBoundingClientRect().height;
      const caret = messageInput.selectionStart;
      const value = messageInput.value;
      const expanded = expandInputPathTokens(value);
      const persisted = savedDraft;
      autoResizeTextarea();
      return {value, expanded, persisted, caret, height,
        expectedHeight: messageInput.getBoundingClientRect().height};
    }""")
    expected = prefix + "@image.png" + suffix
    assert result["value"] == result["persisted"] == expected
    assert result["expanded"] == prefix + '"' + path + '"' + suffix
    assert result["caret"] == len(prefix + "@image.png")
    assert result["height"] == result["expectedHeight"]
    page.keyboard.insert_text("继续")
    assert page.locator("#message-input").input_value() == prefix + "@image.png继续" + suffix


@pytest.mark.parametrize("selection", ["before", "between", "after", "across", "inside"])
@pytest.mark.parametrize("paths", [
    (r'"D:\work\folder with spaces\one.png"', r"D:\work\two.md"),
    (r'"D:\work\folder with spaces\one.png"', r'"D:\work\two.md"'),
    (r"D:\work\one.png", r"D:\work\two.md"),
    (r"D:\work\one.custom_ext", r"D:\work\two.other_ext"),
])
def test_path_rewrite_maps_both_selection_ends(composer_page, selection, paths):
    first, second = paths
    first_label = "@" + first.strip('"').rsplit("\\", 1)[-1]
    second_label = "@" + second.strip('"').rsplit("\\", 1)[-1]
    source = f"前文 {first} 中间 {second} 后文"
    expected = f"前文 {first_label} 中间 {second_label} 后文"
    spans = {
        "before": (1, 2, 1, 2),
        "between": (source.index("中间"), source.index("中间") + 2,
                    expected.index("中间"), expected.index("中间") + 2),
        "after": (source.index("后文"), len(source), expected.index("后文"), len(expected)),
        "across": (source.index(first), source.index(second) + len(second),
                   expected.index(first_label), expected.index(second_label) + len(second_label)),
        "inside": (source.index(first) + 6, source.index(first) + 6,
                   expected.index(first_label) + len(first_label),
                   expected.index(first_label) + len(first_label)),
    }
    start, end, expected_start, expected_end = spans[selection]
    result = composer_page.evaluate("""({source, start, end}) => {
      messageInput.value = source;
      messageInput.focus();
      messageInput.setSelectionRange(start, end, 'backward');
      const originalDirection = messageInput.selectionDirection;
      rewriteInputWorkspacePaths();
      return {value: messageInput.value, start: messageInput.selectionStart,
        end: messageInput.selectionEnd, direction: messageInput.selectionDirection, originalDirection};
    }""", {"source": source, "start": start, "end": end})
    assert result["value"] == expected
    assert (result["start"], result["end"]) == (expected_start, expected_end)
    assert result["direction"] == result["originalDirection"]


@pytest.mark.parametrize("inserted, displayed", [
    (r'"D:\work\screenshot.png"', "@screenshot.png"),
    (r"D:\work\report.md", "@report.md"),
    ("https://example.com/image.png", "https://example.com/image.png"),
    ("普通文本", "普通文本"),
])
def test_insertion_replaces_selection_and_typing_continues_there(composer_page, inserted, displayed):
    page = composer_page
    page.locator("#message-input").fill("前文 待替换 后文")
    page.evaluate("messageInput.setSelectionRange(3, 6)")
    page.keyboard.insert_text(inserted)
    page.keyboard.insert_text("继续")
    assert page.locator("#message-input").input_value() == f"前文 {displayed}继续 后文"


def test_real_multiline_text_still_grows_and_shrinks(composer_page):
    page = composer_page
    page.locator("#message-input").fill("短文本")
    baseline = page.locator("#message-input").bounding_box()["height"]
    page.locator("#message-input").fill("实际内容\n" * 80)
    height = page.locator("#message-input").bounding_box()["height"]
    assert baseline < height <= page.viewport_size["height"] * 0.5
    page.locator("#message-input").fill("")
    assert page.locator("#message-input").bounding_box()["height"] <= baseline + 1
