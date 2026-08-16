# -*- coding: utf-8 -*-
"""媒体附件路径标注：多模态/纯文本两种文案 + 降级去重。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import agent_harness  # noqa: E402  (registers profiles)
from agent_messages import UserMessage  # noqa: E402
from agent_openai import (  # noqa: E402
    _annotate_local_media_paths,
    _messages_to_params_for_client,
    _text_only_media_part,
)

IMG = r"D:/AI/AI Agent/MyAgent Developer/workspace/uploads/chat/test_image.png"
VISION_LABEL = "[图片附件（图片已随消息附上，请直接查看描述，无需读取文件）]"
DELEGATE_LABEL = "[图片附件（如需要识图请委派给多模态子代理）]"


def _image_message(with_path_text: bool = True) -> UserMessage:
    parts = []
    if with_path_text:
        parts.append({"type": "text", "text": '"%s"这是啥' % IMG})
    parts.append({"type": "local_file", "local_file": {"path": IMG, "name": "test_image.png"}})
    return UserMessage(content=parts)


class _VisionClient:
    _myagent_input_modalities = ["text", "image", "video"]
    _myagent_multimodal_input = True


class _TextOnlyClient:
    _myagent_input_modalities = ["text"]


def test_annotate_vision_mode_keeps_path():
    out = _annotate_local_media_paths('"%s"这是啥' % IMG, mode="vision")
    assert VISION_LABEL in out
    assert IMG in out  # 路径保留


def test_annotate_text_only_mode_uses_delegate_label():
    out = _annotate_local_media_paths('"%s"这是啥' % IMG, mode="text_only")
    assert DELEGATE_LABEL in out
    assert IMG in out


def test_text_only_media_part_has_label_and_quoted_path():
    part = _text_only_media_part(IMG)
    assert part["type"] == "text"
    assert DELEGATE_LABEL in part["text"]
    assert '"%s"' % IMG in part["text"]


def test_multimodal_serialization_has_label_and_image_url():
    params = _messages_to_params_for_client(_VisionClient(), [_image_message()])
    user = [p for p in params if p.get("role") == "user"][0]
    texts = [p.get("text", "") for p in user["content"] if p.get("type") == "text"]
    assert any(VISION_LABEL in t and IMG in t for t in texts)
    assert any(p.get("type") == "image_url" for p in user["content"])


def test_text_only_serialization_no_duplicate_path():
    params = _messages_to_params_for_client(_TextOnlyClient(), [_image_message()])
    user = [p for p in params if p.get("role") == "user"][0]
    text = user["content"] if isinstance(user["content"], str) else "".join(
        p.get("text", "") for p in user["content"] if isinstance(p, dict)
    )
    assert DELEGATE_LABEL in text
    # 原文本已含路径 -> 不重复追加裸路径
    assert text.count(IMG) == 1


def test_text_only_serialization_appends_path_when_missing_from_text():
    params = _messages_to_params_for_client(_TextOnlyClient(), [_image_message(with_path_text=False)])
    user = [p for p in params if p.get("role") == "user"][0]
    text = user["content"] if isinstance(user["content"], str) else "".join(
        p.get("text", "") for p in user["content"] if isinstance(p, dict)
    )
    assert DELEGATE_LABEL in text
    assert IMG in text
