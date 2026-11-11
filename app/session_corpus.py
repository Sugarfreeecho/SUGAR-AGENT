"""Shared text extraction for every search corpus.

Both the chat-visible index and the model-facing history tool derive their text
here, so a role, block list or think-tag rule can never drift between them.
"""
from __future__ import annotations

import json
import re
from typing import Any, Mapping

_THINK = re.compile(r"<think>[\s\S]*?(?:</think>|$)", re.I)
_THINK_CLOSE = re.compile(r"</think>", re.I)
_FENCE = re.compile(r"(```[\s\S]*?```|`[^`]*`)")


def text_of(value: Any) -> str:
    """Plain text of a message body: string, block list or nested payload."""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = [
            _content_text(block.get("text"))
            for block in value
            if isinstance(block, Mapping) and block.get("type") in {"text", "input_text", "output_text"}
        ]
        return "\n".join(part for part in parts if part)
    if isinstance(value, Mapping):
        for key in ("text", "content"):
            if isinstance(value.get(key), str):
                return value[key]
    if value in (None, "", {}, []):
        return ""
    return _content_text(value)


def _content_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError):
        return str(value or "")


def strip_think(text: str) -> str:
    """Drop reasoning blocks while keeping literal examples inside code."""
    pieces = _FENCE.split(text)
    return "".join(
        part if index % 2 else _THINK_CLOSE.sub("", _THINK.sub("", part))
        for index, part in enumerate(pieces)
    )


def ui_row_text(row: Mapping[str, Any], *, labelled: bool = True) -> str:
    """Render one UI row; ``labelled`` matches the model-facing corpus."""
    kind = str(row.get("type") or "")
    if kind in {"user", "user_steer"}:
        text = text_of(row.get("content")).strip()
        if not text:
            return ""
        return f"用户：{text}" if labelled else text
    if kind in {"final", "assistant_final", "assistant"}:
        text = strip_think(text_of(row.get("content"))).strip()
        if not text:
            return ""
        return f"助手：{text}" if labelled else text
    if kind in {"tool_call", "tool_result", "tool_finished", "tool_started"}:
        name = str(row.get("tool") or row.get("name") or "").strip()
        body = ""
        for key in ("result", "output", "stdout", "stderr", "content", "args", "arguments"):
            candidate = row.get(key)
            body = _content_text(candidate) if isinstance(candidate, (dict, list)) else text_of(candidate)
            if body.strip():
                break
        text = body.strip()
        if not text:
            return ""
        return f"工具结果（工具={name}）：{text}" if labelled else f"{name}\n{text}".strip()
    return ""
