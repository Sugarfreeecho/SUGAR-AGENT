"""Regressions for modality-accurate media projection.

Covers the failure chain where one unsupported modality (a generic ``file``
part) downgraded every media part in the request, including images the model
declares support for.
"""
import base64
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


def _png(path: Path) -> Path:
    from PIL import Image

    Image.new("RGB", (8, 8)).save(path)
    return path


def _content_parts(message):
    content = message["content"]
    return content if isinstance(content, list) else [{"type": "text", "text": content}]


def test_stale_png_local_file_is_a_text_reference_not_a_file_part(tmp_path):
    import agent_openai
    from agent_messages import UserMessage

    missing = tmp_path / "gone.png"
    messages = [
        UserMessage(
            content=[
                {"type": "text", "text": "分析这张图"},
                {"type": "local_file", "local_file": {"path": str(missing)}},
            ]
        )
    ]

    wire = agent_openai.messages_to_openai_params(
        messages, image_enabled=True, language="zh"
    )

    kinds = {part.get("type") for part in _content_parts(wire[0])}
    assert "file" not in kinds
    assert {"image", "image_url"}.isdisjoint(kinds)
    assert agent_openai._api_messages_required_modalities(wire) == set()
    text = "".join(part.get("text", "") for part in _content_parts(wire[0]))
    assert str(missing) in text


def test_uppercase_png_with_surrounding_spaces_is_admitted_as_image(tmp_path):
    import agent_openai
    from agent_messages import UserMessage

    image_path = _png(tmp_path / "screen.PNG")
    messages = [
        UserMessage(
            content=[
                {"type": "text", "text": "看图"},
                {"type": "local_file", "local_file": {"path": f' "{image_path}" '}},
            ]
        )
    ]

    wire = agent_openai.messages_to_openai_params(messages, image_enabled=True)
    kinds = {part.get("type") for part in _content_parts(wire[0])}
    assert "image_url" in kinds
    assert "file" not in kinds
    assert agent_openai._api_messages_required_modalities(wire) == {"image"}


def test_plain_document_never_requires_file_modality(tmp_path):
    import agent_openai
    from agent_messages import UserMessage

    doc = tmp_path / "notes.txt"
    doc.write_text("hello", encoding="utf-8")
    messages = [
        UserMessage(
            content=[
                {"type": "text", "text": "读一下"},
                {"type": "local_file", "local_file": {"path": str(doc)}},
            ]
        )
    ]

    wire = agent_openai.messages_to_openai_params(messages, image_enabled=True)
    kinds = {part.get("type") for part in _content_parts(wire[0])}
    assert "file" not in kinds
    assert str(doc) in "".join(part.get("text", "") for part in _content_parts(wire[0]))


def _projected_mixed_request(tmp_path):
    """One readable image plus one inlined file part, after image projection."""
    from attachments.content import project_request_images

    image_path = _png(tmp_path / "shot.png")
    data = base64.b64encode(image_path.read_bytes()).decode("ascii")
    raw = [
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{data}"},
                },
                {"type": "text", "text": "对比这两份材料"},
                {
                    "type": "file",
                    "file": {
                        "filename": "spec.pdf",
                        "file_data": "data:application/pdf;base64,JVBERi0xLjQK",
                    },
                },
            ],
        }
    ]
    from attachments import get_attachment_store

    store = get_attachment_store()
    # Images are admitted through the store on the real path; here the data URL
    # is enough because projection only rewrites admitted references.
    return project_request_images(raw, store=store, image_enabled=False, language="zh"), raw


def test_missing_file_modality_keeps_supported_images():
    import agent_openai

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "看看这张图"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}},
                {
                    "type": "file",
                    "file": {"filename": "a.pdf", "file_data": "data:application/pdf;base64,JVBERi0="},
                },
            ],
        }
    ]

    projected = agent_openai._serialized_messages_to_text_only(
        messages, rejected={"file"}
    )
    user_message = next(m for m in projected if m.get("role") == "user")

    kinds = [part.get("type") for part in user_message["content"]]
    assert "image_url" in kinds
    assert "file" not in kinds
    text = "".join(part.get("text", "") for part in user_message["content"])
    assert "a.pdf" in text
    assert "application/pdf" in text
    assert any(
        "task" in str(message.get("content") or "")
        for message in projected
        if message.get("role") == "system"
    )


def test_image_placeholder_keeps_normalized_path():
    import json

    import agent_openai

    original = r"D:\tmp\shot.png"
    handle = (
        "[图片 sha256:" + "a" * 64 + "；请求预览 8x8px。"
        " 归一化副本（只读；可能已缩放或重新编码）："
        + json.dumps(original, ensure_ascii=False)
        + "（8x8px，image/png）。]"
    )
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": handle},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}},
            ],
        }
    ]

    projected = agent_openai._strip_media_from_api_messages(messages, {"image"})
    text = projected[0]["content"]

    assert isinstance(text, str)
    assert "sha256:" in text
    assert original in text
    assert "base64" not in text
    assert text.count("sha256:") == 1


def test_unknown_modality_keeps_supported_media_untouched():
    import agent_openai

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "hi"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}},
            ],
        }
    ]

    assert agent_openai._strip_media_from_api_messages(messages, {"file"})[0] is messages[0]


def test_codex_file_data_sniffing_maps_image_payloads():
    import agent_openai

    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "file",
                    "file": {"filename": "x.png", "file_data": "data:image/png;base64,AAAA"},
                }
            ],
        }
    ]

    assert agent_openai._api_messages_required_modalities(messages) == {"image"}
