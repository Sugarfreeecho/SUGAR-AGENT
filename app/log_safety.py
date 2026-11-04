"""日志 payload 策略：日志只记录可定位的元数据，不记录正文。

约定
----
- 日志中只允许出现：枚举值、路径、ID、数值、长度、哈希、错误类型。
- 模型正文 / 思考 / 工具参数值 / 工具结果 / 用户输入 / 系统提示词
  一律不得作为 ``record.msg`` 的参数写入。
- 需要正文时使用 :func:`preview`，只有 ``LOG_PAYLOAD_MODE=full`` 才返回内容。
- :class:`PayloadSafeFormatter` 是最后一道防线：超长或多行消息在格式化阶段
  强制压成单行摘要，避免遗漏的调用点把整段内容写进文件。

模式
----
``off``（默认）
    只写元数据；正文完全不出现。
``digest``
    元数据 + 每段正文首行 80 字符，用于"看一眼开头"的排障折中。
``full``
    恢复完整正文（受 ``LOG_PAYLOAD_PREVIEW_CHARS`` / ``LOG_TRUNCATE_KEEP_CHARS``
    限制），仅用于临时排障。
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from collections.abc import Mapping, Sequence
from typing import Any

_VALID_MODES = frozenset({"off", "digest", "full"})


def _read_mode() -> str:
    value = os.getenv("LOG_PAYLOAD_MODE", "off").strip().lower()
    return value if value in _VALID_MODES else "off"


def _read_int(name: str, default: int, minimum: int = 0) -> int:
    try:
        return max(minimum, int(str(os.getenv(name, str(default))).strip()))
    except (TypeError, ValueError):
        return default


MODE = _read_mode()
LINE_MAX = _read_int("LOG_LINE_MAX_CHARS", 2000, 400)
PREVIEW_CHARS = _read_int("LOG_PAYLOAD_PREVIEW_CHARS", 0)
DEFAULT_PREVIEW = _read_int("LOG_TRUNCATE_KEEP_CHARS", 200)

_TRUNCATE_MARK = "…[log truncated"
# 结构化计时行由本地计数器生成，不含 payload；放宽上限以免截断 JSON。
STRUCTURED_PREFIXES = ("local_operation_timing ", "local_request_timing ")
STRUCTURED_LINE_MAX = 32768


def payload_enabled() -> bool:
    """是否允许写正文（仅 full 模式）。"""
    return MODE == "full"


def _hash_bytes(raw: bytes) -> str:
    return hashlib.blake2b(raw, digest_size=6).hexdigest()


def digest(value: Any) -> str:
    """内容指纹：长度 + 12 位哈希，永不返回正文。"""
    if value is None:
        return "len=0 sha=-"
    if isinstance(value, (bytes, bytearray)):
        raw = bytes(value)
        return f"bytes={len(raw)} sha={_hash_bytes(raw)}"
    try:
        text = value if isinstance(value, str) else json.dumps(
            value,
            ensure_ascii=False,
            default=str,
            sort_keys=True,
            separators=(",", ":"),
        )
    except Exception:
        return "len=? sha=?"
    raw = text.encode("utf-8", "replace")
    return f"len={len(text)} sha={_hash_bytes(raw)}"


def shape(value: Any, *, depth: int = 2, max_keys: int = 12) -> str:
    """结构指纹：键名 + 类型 + 长度，不序列化字符串值。"""
    try:
        return _shape(value, depth, max_keys)
    except Exception:
        return type(value).__name__


def _shape(value: Any, depth: int, max_keys: int) -> str:
    if isinstance(value, Mapping):
        items = list(value.items())[:max_keys]
        inner = ", ".join(f"{key}:{_leaf(item, depth - 1)}" for key, item in items)
        extra = f", …+{len(value) - len(items)}" if len(value) > len(items) else ""
        return f"{{{inner}{extra}}}"
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return f"list({len(value)})"
    return _leaf(value, depth)


def _leaf(value: Any, depth: int) -> str:
    if isinstance(value, str):
        return f"str#{len(value)}"
    if value is None or isinstance(value, (bool, int, float)):
        return f"{type(value).__name__}={value!r}"[:32]
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return f"list({len(value)})"
    if isinstance(value, Mapping) and depth > 0:
        return _shape(value, depth, 12)
    return type(value).__name__


def preview(text: str, limit: int | None = None) -> str:
    """按模式返回正文摘要；off 永远返回空串。"""
    if not text or MODE == "off":
        return ""
    if MODE == "digest":
        stripped = text.strip()
        if not stripped:
            return ""
        first = stripped.splitlines()[0]
        return (first[:80] + "…") if len(first) > 80 else first
    cap = limit or PREVIEW_CHARS or DEFAULT_PREVIEW
    if cap <= 0:
        return ""
    return text if len(text) <= cap else text[:cap] + "…"


def error_text(exc: BaseException, limit: int = 300) -> str:
    """异常消息压成单行并限长，避免把回显的参数写进日志。"""
    try:
        text = str(exc)
    except Exception:
        text = type(exc).__name__
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit] + "…"


def clamp_log_text(text: str, *, has_traceback: bool = False, limit: int | None = None) -> str:
    """把一行日志压到上限内；异常堆栈保留首尾，便于定位根因。"""
    cap = limit or LINE_MAX
    if len(text) <= cap and (has_traceback or "\n" not in text):
        return text
    total = len(text)
    sha = _hash_bytes(text.encode("utf-8", "replace"))
    if has_traceback:
        head_len = max(0, cap - 420)
        head, tail = text[:head_len], text[-360:]
        return f"{head}\n…[log truncated total_chars={total} sha={sha}]…\n{tail}"
    flat = text.replace("\r", "").replace("\n", "\\n")
    if _TRUNCATE_MARK in flat:
        flat = flat[:cap]
        return f"{flat} …[log truncated total_chars={total} sha={sha}]"
    lines = text.count("\n") + 1
    return f"{flat[:cap]} …[log truncated total_chars={total} sha={sha} lines={lines}]"


class PayloadSafeFormatter(logging.Formatter):
    """格式化阶段兜底：单行上限 + 多行折叠 + 异常堆栈首尾保留。"""

    def format(self, record: logging.LogRecord) -> str:
        text = super().format(record)
        head = record.msg if isinstance(record.msg, str) else ""
        limit = STRUCTURED_LINE_MAX if head.startswith(STRUCTURED_PREFIXES) else LINE_MAX
        return clamp_log_text(text, has_traceback=bool(record.exc_info), limit=limit)
