# -*- coding: utf-8 -*-
"""多模态 content（list）不再让字符串辅助函数崩溃。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from agent_harness import (
    _message_content_text,
    derive_dialogue_from_assistant_history,
    is_assistant_message_micro_shrunk,
    is_compress_recap_user_message,
)
from agent_messages import AssistantMessage, UserMessage


def _multimodal_user(text: str = "这是什么") -> UserMessage:
    return UserMessage(
        content=[
            {"type": "text", "text": text},
            {"type": "local_file", "local_file": {"path": "x.png", "name": "x.png"}},
        ]
    )


def test_message_content_text_projects_multimodal_list():
    m = _multimodal_user("看看这张图")
    assert _message_content_text(m) == "看看这张图"


def test_compress_recap_check_does_not_crash_on_multimodal_user():
    m = _multimodal_user("这是普通图片消息")
    # 非压缩前情提要 -> False，且不抛 AttributeError
    assert is_compress_recap_user_message(m) is False


def test_micro_shrunk_check_does_not_crash_on_multimodal_assistant():
    m = AssistantMessage(
        content=[{"type": "text", "text": "【微压工作块】abc"}],
        metadata={},
    )
    assert is_assistant_message_micro_shrunk(m) is True


def test_derive_dialogue_accepts_multimodal_history():
    hist = [
        _multimodal_user("这是什么"),
        AssistantMessage(content="回答", metadata={"is_final": True}),
    ]
    out = derive_dialogue_from_assistant_history(hist)
    assert len(out) == 2
    assert isinstance(out[0], UserMessage)
