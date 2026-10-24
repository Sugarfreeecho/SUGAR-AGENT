"""乐观用户气泡必须携带本轮图片附件引用。

回归背景：发送图片时前端先画用户气泡，但附件列表是在画完之后才算出来的，
且只用于 /chat 的 FormData。服务端本轮只持久化 user 事件、不在实时 SSE 回显，
于是图片卡片要等刷新/重连走历史回放才出现。本文件锁定 sendMessage 的接线顺序。
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SSE = ROOT / "frontend/src/app/modules/sse-handling.js"


def _function_body(source: str, name: str) -> str:
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


def test_send_message_collects_image_refs_before_drawing_the_optimistic_bubble():
    body = _function_body(SSE.read_text(encoding="utf-8"), "sendMessage")

    collect_at = body.index("const optimisticAttachments")
    append_at = body.index("appendMessage(runCtx, 'user', displayMessage")
    assert collect_at < append_at, "attachments must be known before the bubble is drawn"

    assert "const optimisticAttachments = attachmentsForRun" in body
    assert body.count("const rememberedAttachments") == 1
    assert body.count("const attachmentsForRun") == 1
    assert (
        "applySessionEvent({ type: 'user', content: displayMessage, created_at: userSentAt, attachments: optimisticAttachments }"
        in body
    )
    assert "attachments: optimisticAttachments," in body
    assert "optimisticSteerMode, true, optimisticAttachments" in body


def test_live_and_recovered_steer_rows_keep_their_attachment_refs():
    sse = SSE.read_text(encoding="utf-8")

    # 实时 user_steer 提交：服务端会带 attachments，提交乐观行时不能丢。
    assert "String(parsed.steer_mode || 'interrupt'), false,\n                            parsed.attachments || []" in sse
    # 重连后补建 steer 行：队列项里保存的附件引用要交给渲染器。
    assert "item.steerMode || (serverItem && serverItem.mode) || 'interrupt', false,\n            item.attachments || []" in sse
