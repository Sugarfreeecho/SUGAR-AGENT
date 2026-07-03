from __future__ import annotations

import re
from typing import List


_THINK_BLOCK_RE = re.compile(r"<think\b[^>]*>([\s\S]*?)</think\s*>", re.IGNORECASE)
_THINK_OPEN_TO_END_RE = re.compile(r"<think\b[^>]*>[\s\S]*$", re.IGNORECASE)
_THINK_CLOSE_TAG_RE = re.compile(r"</think\s*>", re.IGNORECASE)


def extract_think_blocks(text: str) -> List[str]:
    s = str(text or "")
    blocks = [m.group(1).strip() for m in _THINK_BLOCK_RE.finditer(s) if m.group(1).strip()]
    last_open = None
    for m in re.finditer(r"<think\b[^>]*>", s, re.IGNORECASE):
        last_open = m
    if last_open is not None:
        tail = s[last_open.end() :]
        if not _THINK_CLOSE_TAG_RE.search(tail) and tail.strip():
            blocks.append(tail.strip())
    return blocks


def strip_think_blocks(text: str) -> str:
    s = str(text or "")
    s = _THINK_BLOCK_RE.sub("", s)
    s = _THINK_OPEN_TO_END_RE.sub("", s)
    s = _THINK_CLOSE_TAG_RE.sub("", s)
    return s.strip()


def _head_tail(text: str, keep_each_side: int) -> str:
    s = str(text or "").strip()
    k = max(0, int(keep_each_side))
    if not s or k <= 0 or len(s) <= 2 * k:
        return s
    omitted = len(s) - 2 * k
    return f"{s[:k]}\n...已省略 {omitted} 字符...\n{s[-k:]}"


def think_excerpt(text: str, keep_each_side: int = 800) -> str:
    parts = [_head_tail(block, keep_each_side) for block in extract_think_blocks(text)]
    parts = [p for p in parts if p]
    return "\n\n".join(parts).strip()


def content_with_think_excerpt(text: str, keep_each_side: int = 800) -> str:
    content = strip_think_blocks(text)
    excerpt = think_excerpt(text, keep_each_side=keep_each_side)
    if excerpt:
        return (("[思考/推理摘录]\n" + excerpt + "\n\n") + content).strip()
    return content
