"""输入框 @基名 胶囊：标签→真实路径映射不得在"发送"前丢失。

问题背景（本次修复）：输入框会把绝对路径改写成 `@基名` 胶囊标签，真实路径只存在
`inputPathTokenMap` 内存映射里。入队/发送时映射会被 `clearInputPathTokens()` 清空，
于是任何"把 display 文本（标签形式）当作正文回填/落盘"的链路都会在下次发送时真的
发出 `@文件名` —— 路径被吞。本文件把关键接线固定下来，防止回退。
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SSE = ROOT / "frontend/src/app/modules/sse-handling.js"
SCROLL = ROOT / "frontend/src/app/modules/session-scroll-history.js"
RENDERING = ROOT / "frontend/src/app/modules/message-rendering.js"


def _function_body(source: str, name: str) -> str:
    """按大括号配平取出 `function name(...) { ... }` 的函数体。"""
    start = source.index(f"function {name}(")
    depth = 0
    for index in range(source.index("{", start), len(source)):
        char = source[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise AssertionError(f"function {name} braces unbalanced")


def test_followup_withdraw_returns_sent_text_instead_of_display_label():
    sse = SSE.read_text(encoding="utf-8")
    body = _function_body(sse, "returnFollowupToInput")

    # 回填正文必须是「实际提交的原文」，否则标签→路径映射已清空时会发出 @文件名
    assert "const returned = String(item.text || item.display || '')" in body
    assert "const returned = String(item.display || item.text || '')" not in body
    # 回填后仍走胶囊重写（显示形态不变）并同步草稿
    assert "rewriteInputWorkspacePaths();" in body
    assert "persistInputDraft(sid, messageInput.value);" in body


def test_followup_steer_and_queued_chat_use_sent_text_not_display_label():
    sse = SSE.read_text(encoding="utf-8")

    assert "sendSteerMessage(\n            sid,\n            item.text," in sse
    assert (sse.count("message: item.text,")) >= 3
    assert "displayMessage: item.display || item.text," in sse
    # 显示用途与模型用途两路必须分开
    assert "formData.append('message', rawMessage);" in sse
    assert "formData.append('ui_message', uiBaseMessage);" in sse


def test_busy_fallback_restores_sent_text_and_rebuilds_path_chips():
    sse = SSE.read_text(encoding="utf-8")
    busy = sse.split("if (response.status === 409) {", 1)[1].split(
        "scheduleActiveSessionReconnect(runSessionId, { delayMs: 0, failure: true });", 1
    )[0]

    assert "messageInput.value = rawMessage;" in busy
    assert "rewriteInputWorkspacePaths();" in busy
    assert "messageInput.value = visibleMessage;" not in busy
    # 回填的是重写后的输入框文本（标签 + 映射一起落盘草稿）
    assert "persistInputDraft(runSessionId, messageInput.value);" in busy


def test_inline_rewrite_expands_path_labels_before_send():
    sse = SSE.read_text(encoding="utf-8")

    assert (
        "const rawMessage = options.fromQueue ? visibleMessage : expandInputPathTokens(visibleMessage);"
        in sse
    )
    assert (
        "const rawMessage = (options.fromQueue || options.fromInlineRewrite) "
        "? visibleMessage : expandInputPathTokens(visibleMessage);" not in sse
    )


def test_draft_persists_and_restores_path_token_map():
    scroll = SCROLL.read_text(encoding="utf-8")

    assert "function inputDraftPathTokenStorageKey(sessionId) {" in scroll
    assert "LS_INPUT_DRAFT_PREFIX + draftKey" in scroll

    restore = _function_body(scroll, "restoreInputDraft")
    restore_token = restore.index("restoreDraftPathTokens(sessionId, messageInput.value);")
    restore_rewrite = restore.index("rewriteInputWorkspacePaths();")
    # 必须先重建标签映射，再刷新胶囊，否则胶囊会被判为无效标签
    assert restore_token < restore_rewrite

    persist = _function_body(scroll, "persistInputDraft")
    assert "persistDraftPathTokens(sessionId, text);" in persist
    assert "localStorage.removeItem(inputDraftPathTokenStorageKey(sessionId));" in persist
    assert "syncSessionDraftBadges(sessionId);" in persist
    assert "renderSessionList" not in persist

    remove = _function_body(scroll, "removeStoredInputDraft")
    assert "localStorage.removeItem(inputDraftPathTokenStorageKey(sessionId));" in remove
    assert "syncSessionDraftBadges(sessionId);" in remove
    assert "renderSessionList" not in remove

    collect = _function_body(scroll, "collectDraftPathTokens")
    assert "source.indexOf(label) >= 0" in collect

    restore_tokens = _function_body(scroll, "restoreDraftPathTokens")
    assert "source.indexOf(label) < 0" in restore_tokens
    assert "inputPathTokenMap[label] = path;" in restore_tokens


def test_draft_path_tokens_are_session_scoped_and_identity_checked():
    scroll = SCROLL.read_text(encoding="utf-8")
    restore_tokens = _function_body(scroll, "restoreDraftPathTokens")

    # 会话级隔离：映射键由草稿键派生
    assert "return inputDraftStorageKey(sessionId) + '::path-tokens';" in scroll
    # 同名标签指向不同文件时不得覆盖既有映射
    assert "normalizeInputPathTokenIdentity(existing) !== normalizeInputPathTokenIdentity(path)" in restore_tokens


def test_input_path_chip_display_form_is_unchanged_in_rendering():
    rendering = RENDERING.read_text(encoding="utf-8")

    assert "function workspaceOpenDisplayLabel(original, wsRel) {" in rendering
    assert "if (name) return '@' + name;" in rendering
    assert "inputPathTokenMap[label] = stripPathWrappingQuotes(path);" in rendering
