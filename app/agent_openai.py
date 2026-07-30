"""
OpenAI Chat Completions 适配层。

负责把 agent_messages 中的消息转为 API 的 messages 列表，并解析 assistant 消息中的
content / tool_calls / reasoning_content。

主模型在思考开时由 harness 传 extra_body.thinking、reasoning_effort，并继续传 temperature；
messages_to_openai_params 对每条 assistant 均带上 reasoning_content（可空串），兼容 DeepSeek thinking 多轮。
"""

from __future__ import annotations

import base64
import hashlib
import html
import json
import logging
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from queue import Queue
from typing import Any, Callable, Dict, List, Optional, Tuple

from openai import OpenAI
from openai.types.chat import ChatCompletion

from agent_messages import AssistantMessage, SystemMessage, ToolMessage, UserMessage
from agent_think import strip_think_blocks

logger = logging.getLogger(__name__)

OPENAI_MAX_RETRIES = max(1, int(os.getenv("OPENAI_MAX_RETRIES", "3")))
OPENAI_RETRY_BASE_SEC = float(os.getenv("OPENAI_RETRY_BASE_SEC", "1.0"))


def _redact_runtime_log_text(value: Any) -> str:
    text = value if isinstance(value, str) else str(value)
    for key in ("OPENAI_API_KEY", "OPENAI_BASE_URL", "LOCAL_LLM_HOST"):
        val = os.getenv(key)
        if val:
            text = text.replace(val, "***")
    text = re.sub(r"https?://[^\s,;]+", "***", text)
    text = re.sub(r"(?i)(api[_-]?key|authorization|bearer)\s*[:=]\s*[^\s,;]+", r"\1=***", text)
    return text


def _masked_model_label(model: str) -> str:
    s = str(model or "").strip()
    return _redact_runtime_log_text(s) if s else "(empty)"


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


_MISSING = object()


def _get_attr_or_key(obj: Any, key: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)

    val = getattr(obj, key, _MISSING)
    if val is not _MISSING:
        return val

    for extra_name in ("model_extra", "__dict__"):
        extra = getattr(obj, extra_name, None)
        if isinstance(extra, dict) and key in extra:
            return extra.get(key, default)
    return default


def _get_nested_attr_or_key(obj: Any, *path: str) -> Any:
    cur = obj
    for k in path:
        cur = _get_attr_or_key(cur, k, _MISSING)
        if cur is _MISSING:
            return None
    return cur


def extract_usage_dict(usage_obj: Any) -> Dict[str, int]:
    """
    统一提取 usage 字段，兼容：
    - OpenAI 平铺字段：prompt_cache_hit_tokens / prompt_cache_miss_tokens
    - MiMo 嵌套字段：prompt_tokens_details.cached_tokens、completion_tokens_details.reasoning_tokens
    """
    prompt_tokens = _safe_int(_get_nested_attr_or_key(usage_obj, "prompt_tokens"))
    completion_tokens = _safe_int(_get_nested_attr_or_key(usage_obj, "completion_tokens"))
    total_tokens = _safe_int(_get_nested_attr_or_key(usage_obj, "total_tokens"))

    cache_hit_flat = _safe_int(_get_nested_attr_or_key(usage_obj, "prompt_cache_hit_tokens"))
    cache_miss_flat = _safe_int(_get_nested_attr_or_key(usage_obj, "prompt_cache_miss_tokens"))
    cached_tokens_nested = _safe_int(
        _get_nested_attr_or_key(usage_obj, "prompt_tokens_details", "cached_tokens")
    )
    prompt_cache_hit_tokens = cache_hit_flat if cache_hit_flat > 0 else cached_tokens_nested

    prompt_cache_miss_tokens = cache_miss_flat
    if prompt_cache_miss_tokens <= 0 and prompt_tokens > 0 and prompt_cache_hit_tokens >= 0:
        prompt_cache_miss_tokens = max(prompt_tokens - prompt_cache_hit_tokens, 0)

    reasoning_tokens = _safe_int(
        _get_nested_attr_or_key(usage_obj, "completion_tokens_details", "reasoning_tokens")
    )
    accepted_prediction_tokens = _safe_int(
        _get_nested_attr_or_key(
            usage_obj, "completion_tokens_details", "accepted_prediction_tokens"
        )
    )
    rejected_prediction_tokens = _safe_int(
        _get_nested_attr_or_key(
            usage_obj, "completion_tokens_details", "rejected_prediction_tokens"
        )
    )

    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "prompt_cache_hit_tokens": prompt_cache_hit_tokens,
        "prompt_cache_miss_tokens": prompt_cache_miss_tokens,
        "reasoning_tokens": reasoning_tokens,
        "accepted_prediction_tokens": accepted_prediction_tokens,
        "rejected_prediction_tokens": rejected_prediction_tokens,
    }


def _is_retriable_openai_error(exc: BaseException) -> bool:
    msg = str(exc).lower()
    if "timeout" in msg or "timed out" in msg:
        return True
    if "connection" in msg or "connect" in msg:
        return True
    if "rate" in msg and "limit" in msg:
        return True
    if "503" in msg or "502" in msg or "529" in msg:
        return True
    try:
        from openai import APIConnectionError, APITimeoutError, InternalServerError, RateLimitError

        return isinstance(exc, (APIConnectionError, APITimeoutError, RateLimitError, InternalServerError))
    except ImportError:
        return False


@dataclass
class AssistantTurn:
    """单次 chat.completions 中 assistant 消息的已解析结果。"""

    content: str
    tool_calls: Optional[List[Dict[str, Any]]]
    reasoning_content: Optional[str]
    reasoning_field: Optional[str] = None


_DSML_SEP = r"[|｜]"
_DSML_MARKER_RE = re.compile(
    rf"<\s*{_DSML_SEP}\s*DSML\s*{_DSML_SEP}\s*(?:tool_calls|invoke|parameter)\b",
    re.IGNORECASE,
)
_DSML_TOOL_CALLS_RE = re.compile(
    rf"<\s*{_DSML_SEP}\s*DSML\s*{_DSML_SEP}\s*tool_calls\b[^>]*>"
    rf"(?P<body>[\s\S]*?)"
    rf"</\s*{_DSML_SEP}\s*DSML\s*{_DSML_SEP}\s*tool_calls\s*>",
    re.IGNORECASE,
)
_DSML_INVOKE_RE = re.compile(
    rf"<\s*{_DSML_SEP}\s*DSML\s*{_DSML_SEP}\s*invoke\b(?P<attrs>[^>]*)>"
    rf"(?P<body>[\s\S]*?)"
    rf"</\s*{_DSML_SEP}\s*DSML\s*{_DSML_SEP}\s*invoke\s*>",
    re.IGNORECASE,
)
_DSML_PARAMETER_RE = re.compile(
    rf"<\s*{_DSML_SEP}\s*DSML\s*{_DSML_SEP}\s*parameter\b(?P<attrs>[^>]*)>"
    rf"(?P<body>[\s\S]*?)"
    rf"</\s*{_DSML_SEP}\s*DSML\s*{_DSML_SEP}\s*parameter\s*>",
    re.IGNORECASE,
)
_DSML_ATTR_RE = re.compile(
    r"""(?P<name>[A-Za-z_][\w.-]*)\s*=\s*(?:"(?P<double>[^"]*)"|'(?P<single>[^']*)')""",
    re.IGNORECASE,
)
_DSML_STREAM_PREFIXES = ("<｜DSML｜", "<|DSML|")
_NATIVE_BOUNDARY_TOKEN_RE = re.compile(
    r"<\s*[|｜]\s*(?:begin[▁_]of[▁_]sentence|end[▁_]of[▁_]sentence)\s*[|｜]\s*>",
    re.IGNORECASE,
)
_NATIVE_BOUNDARY_TOKENS = (
    "<｜begin▁of▁sentence｜>",
    "<｜end▁of▁sentence｜>",
    "<｜begin_of_sentence｜>",
    "<｜end_of_sentence｜>",
    "<|begin_of_sentence|>",
    "<|end_of_sentence|>",
)


def _attrs_dict(raw: str) -> Dict[str, str]:
    attrs: Dict[str, str] = {}
    for match in _DSML_ATTR_RE.finditer(str(raw or "")):
        value = match.group("double")
        if value is None:
            value = match.group("single") or ""
        attrs[str(match.group("name") or "").strip().lower()] = html.unescape(value)
    return attrs


def _strip_native_boundary_tokens(text: Optional[str]) -> str:
    return _NATIVE_BOUNDARY_TOKEN_RE.sub("", str(text or ""))


def _tool_schema_map(tools: Optional[List[Dict[str, Any]]]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for item in tools or []:
        if not isinstance(item, dict):
            continue
        fn = item.get("function") if isinstance(item.get("function"), dict) else item
        name = str((fn or {}).get("name") or "").strip()
        if name:
            out[name] = fn or {}
    return out


def _matches_schema_type(value: Any, schema: Dict[str, Any]) -> bool:
    expected = schema.get("type")
    if isinstance(expected, list):
        return any(_matches_schema_type(value, {**schema, "type": item}) for item in expected)
    if not expected:
        return True
    expected = str(expected).lower()
    if expected == "null":
        ok = value is None
    elif expected == "boolean":
        ok = isinstance(value, bool)
    elif expected == "integer":
        ok = isinstance(value, int) and not isinstance(value, bool)
    elif expected == "number":
        ok = isinstance(value, (int, float)) and not isinstance(value, bool)
    elif expected == "string":
        ok = isinstance(value, str)
    elif expected == "array":
        ok = isinstance(value, list)
    elif expected == "object":
        ok = isinstance(value, dict)
    else:
        ok = True
    if not ok:
        return False
    enum = schema.get("enum")
    return not isinstance(enum, list) or value in enum


def _is_in_fenced_code(text: str, position: int) -> bool:
    prefix = text[: max(0, int(position))]
    return (prefix.count("```") % 2 == 1) or (prefix.count("~~~") % 2 == 1)


def _parse_dsml_invokes(
    raw: str,
    tools: Optional[List[Dict[str, Any]]],
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    schema_map = _tool_schema_map(tools)
    if not schema_map:
        return [], "no tools were supplied for DSML validation"
    invoke_matches = list(_DSML_INVOKE_RE.finditer(raw))
    if not invoke_matches:
        return [], "DSML contains no complete invoke block"
    residue = _DSML_INVOKE_RE.sub("", raw)
    if residue.strip():
        return [], "unexpected text or an incomplete invoke exists inside DSML tool_calls"

    calls: List[Dict[str, Any]] = []
    for invoke in invoke_matches:
        invoke_attrs = _attrs_dict(invoke.group("attrs"))
        tool_name = str(invoke_attrs.get("name") or "").strip()
        fn_schema = schema_map.get(tool_name)
        if not tool_name or fn_schema is None:
            return [], f"unknown or missing DSML tool name: {tool_name or '(empty)'}"

        param_matches = list(_DSML_PARAMETER_RE.finditer(invoke.group("body")))
        param_residue = _DSML_PARAMETER_RE.sub("", invoke.group("body"))
        if param_residue.strip():
            return [], f"malformed parameter block for DSML tool {tool_name}"

        args: Dict[str, Any] = {}
        for param in param_matches:
            attrs = _attrs_dict(param.group("attrs"))
            param_name = str(attrs.get("name") or "").strip()
            if not param_name or param_name in args:
                return [], f"missing or duplicate DSML parameter for tool {tool_name}"
            raw_value = html.unescape(param.group("body"))
            is_string = str(attrs.get("string") or "").strip().lower() == "true"
            if is_string:
                value: Any = raw_value
            else:
                try:
                    value = json.loads(raw_value.strip())
                except (TypeError, ValueError, json.JSONDecodeError):
                    return [], f"invalid JSON value for DSML parameter {tool_name}.{param_name}"
            args[param_name] = value

        parameters = fn_schema.get("parameters")
        parameters = parameters if isinstance(parameters, dict) else {}
        properties = parameters.get("properties")
        properties = properties if isinstance(properties, dict) else {}
        unknown = [name for name in args if properties and name not in properties]
        if unknown:
            return [], f"unknown DSML parameter for tool {tool_name}: {unknown[0]}"
        required = parameters.get("required")
        required = required if isinstance(required, list) else []
        missing = [str(name) for name in required if str(name) not in args]
        if missing:
            return [], f"missing required DSML parameter for tool {tool_name}: {missing[0]}"
        for param_name, value in args.items():
            prop_schema = properties.get(param_name)
            if isinstance(prop_schema, dict) and not _matches_schema_type(value, prop_schema):
                return [], f"wrong DSML value type for {tool_name}.{param_name}"

        digest = hashlib.sha256(invoke.group(0).encode("utf-8")).hexdigest()[:20]
        calls.append(
            {
                "name": tool_name,
                "args": args,
                "id": f"call_dsml_{digest}",
            }
        )
    return calls, None


def _recover_dsml_from_text(
    text: Optional[str],
    tools: Optional[List[Dict[str, Any]]],
) -> Tuple[str, List[Dict[str, Any]], bool]:
    raw = str(text or "")
    markers = [
        match for match in _DSML_MARKER_RE.finditer(raw)
        if not _is_in_fenced_code(raw, match.start())
    ]
    if not markers:
        return raw, [], False

    outer = [
        match for match in _DSML_TOOL_CALLS_RE.finditer(raw)
        if not _is_in_fenced_code(raw, match.start())
    ]
    candidates: List[Tuple[re.Match[str], str]] = []
    if outer:
        candidates = [(match, match.group("body")) for match in outer]
    else:
        invokes = [
            match for match in _DSML_INVOKE_RE.finditer(raw)
            if not _is_in_fenced_code(raw, match.start())
        ]
        candidates = [(match, match.group(0)) for match in invokes]

    recovered: List[Dict[str, Any]] = []
    remove_ranges: List[Tuple[int, int]] = []
    parse_failed = False
    for match, body in candidates:
        calls, error = _parse_dsml_invokes(body, tools)
        if error:
            logger.warning("丢弃无法安全恢复的 DSML 工具调用: %s", error)
            parse_failed = True
            continue
        recovered.extend(calls)
        remove_ranges.append((match.start(), match.end()))

    uncovered_marker = any(
        not any(start <= marker.start() < end for start, end in remove_ranges)
        for marker in markers
    )
    tail_start = markers[0].start()
    tail_residue_parts: List[str] = []
    tail_cursor = tail_start
    for start, end in sorted(remove_ranges):
        if end <= tail_start:
            continue
        tail_residue_parts.append(raw[tail_cursor:start])
        tail_cursor = end
    tail_residue_parts.append(raw[tail_cursor:])
    non_protocol_tail = bool("".join(tail_residue_parts).strip())
    if not recovered or parse_failed or uncovered_marker or non_protocol_tail:
        # Never expose an executable-looking, malformed protocol fragment or
        # accept its conversational prefix as a final answer. Returning an empty
        # channel lets the normal empty-result path retry the model cleanly.
        return "", [], True

    cleaned_parts: List[str] = []
    cursor = 0
    for start, end in sorted(remove_ranges):
        cleaned_parts.append(raw[cursor:start])
        cursor = end
    cleaned_parts.append(raw[cursor:])
    cleaned = "".join(cleaned_parts).strip()
    return cleaned, recovered, True


def _repair_dsml_turn(
    content: str,
    reasoning: Optional[str],
    tools: Optional[List[Dict[str, Any]]],
    existing_calls: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[str, Optional[str], Optional[List[Dict[str, Any]]], List[Dict[str, Any]]]:
    clean_content, content_calls, _ = _recover_dsml_from_text(content, tools)
    clean_reasoning, reasoning_calls, _ = _recover_dsml_from_text(reasoning, tools)
    merged: List[Dict[str, Any]] = list(existing_calls or [])
    if merged:
        # A standard OpenAI tool_calls array is authoritative. Raw protocol text
        # may be a duplicate provider artifact; strip it, but never combine two
        # conflicting interpretations into one executable batch.
        return clean_content, clean_reasoning.strip() or None, merged, []
    added: List[Dict[str, Any]] = []
    signatures = {
        (
            str(call.get("name") or ""),
            json.dumps(call.get("args") or {}, ensure_ascii=False, sort_keys=True, default=str),
        )
        for call in merged
    }
    for call in content_calls + reasoning_calls:
        signature = (
            str(call.get("name") or ""),
            json.dumps(call.get("args") or {}, ensure_ascii=False, sort_keys=True, default=str),
        )
        if signature in signatures:
            continue
        signatures.add(signature)
        merged.append(call)
        added.append(call)
    return clean_content, clean_reasoning.strip() or None, merged or None, added


class _DsmlStreamFilter:
    """Hold native DSML protocol text until it can be validated at turn end."""

    def __init__(self, enabled: bool):
        self.enabled = bool(enabled)
        self.pending = ""
        self.blocked = False

    def feed(self, piece: str) -> str:
        if not self.enabled:
            return piece
        if self.blocked:
            return ""
        combined = self.pending + piece
        marker_positions = [
            combined.find(prefix)
            for prefix in _DSML_STREAM_PREFIXES
            if combined.find(prefix) >= 0
        ]
        marker = _DSML_MARKER_RE.search(combined)
        if marker:
            marker_positions.append(marker.start())
        if marker_positions:
            marker_start = min(marker_positions)
            self.blocked = True
            self.pending = combined[marker_start:]
            return combined[:marker_start]
        keep = 0
        for prefix in _DSML_STREAM_PREFIXES:
            limit = min(len(prefix) - 1, len(combined))
            for size in range(limit, 0, -1):
                if combined.endswith(prefix[:size]):
                    keep = max(keep, size)
                    break
        if keep:
            self.pending = combined[-keep:]
            return combined[:-keep]
        self.pending = ""
        return combined

    def finish(self) -> str:
        if not self.enabled or not self.blocked:
            tail = self.pending
            self.pending = ""
            return tail
        return ""


class _NativeBoundaryStreamFilter:
    """Remove leaked BOS/EOS tokens, including tokens split across chunks."""

    def __init__(self):
        self.pending = ""

    def feed(self, piece: str) -> str:
        combined = self.pending + str(piece or "")
        cleaned = _NATIVE_BOUNDARY_TOKEN_RE.sub("", combined)
        keep = 0
        for token in _NATIVE_BOUNDARY_TOKENS:
            limit = min(len(token) - 1, len(cleaned))
            for size in range(limit, 0, -1):
                if cleaned.endswith(token[:size]):
                    keep = max(keep, size)
                    break
        if keep:
            self.pending = cleaned[-keep:]
            return cleaned[:-keep]
        self.pending = ""
        return cleaned

    def finish(self) -> str:
        tail = _strip_native_boundary_tokens(self.pending)
        self.pending = ""
        return tail


def normalize_content_text(content: Any) -> str:
    """将 API 返回的 content（str / dict / 多模态 list）统一成纯文本。"""
    if content is None:
        return ""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, dict):
        if str(content.get("type") or "").strip().lower() in {"reasoning", "reasoning_content"}:
            return ""
        for key in ("text", "content", "message", "value", "output"):
            v = content.get(key)
            if isinstance(v, str) and v.strip():
                return v.strip()
            if isinstance(v, (list, dict)):
                inner = normalize_content_text(v)
                if inner:
                    return inner
        return ""
    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, str) and item.strip():
                parts.append(item.strip())
            elif isinstance(item, dict):
                if str(item.get("type") or "").strip().lower() in {"reasoning", "reasoning_content"}:
                    continue
                chunk = ""
                for key in (
                    "text",
                    "content",
                    "value",
                ):
                    v = item.get(key)
                    if isinstance(v, str) and v.strip():
                        chunk = v.strip()
                        break
                    if isinstance(v, (list, dict)):
                        inner = normalize_content_text(v)
                        if inner:
                            chunk = inner
                            break
                if chunk:
                    parts.append(chunk)
        return "\n".join(parts).strip()
    return str(content).strip()


def _normalize_content_text(content: Any) -> str:
    return normalize_content_text(content)


def _coerce_text_or_none(raw: Any) -> Optional[str]:
    if raw is None:
        return None
    if isinstance(raw, str):
        text = raw.strip()
        return text or None
    text = str(raw).strip()
    return text or None


def _extract_reasoning_from_content(value: Any) -> Tuple[Optional[str], Optional[str]]:
    if value is None or isinstance(value, str):
        return (None, None)
    if isinstance(value, dict):
        direct = _coerce_text_or_none(value.get("reasoning"))
        if direct:
            return (direct, "reasoning")
        nested = value.get("reasoning_content")
        if isinstance(nested, (dict, list)):
            return _extract_reasoning_from_content(nested)
        text = _coerce_text_or_none(nested)
        return (text, "reasoning_content") if text else (None, None)
    if isinstance(value, list):
        parts: List[str] = []
        field: Optional[str] = None
        for item in value:
            if not isinstance(item, dict):
                continue
            part_type = str(item.get("type") or "").strip().lower()
            if part_type in {"reasoning", "reasoning_content"}:
                text = (
                    _coerce_text_or_none(item.get("reasoning"))
                    or _coerce_text_or_none(item.get("reasoning_content"))
                    or _coerce_text_or_none(item.get("text"))
                    or _coerce_text_or_none(item.get("content"))
                )
                if text:
                    parts.append(text)
                    if field is None:
                        field = "reasoning_content" if part_type == "reasoning_content" else "reasoning"
                continue
            text = _coerce_text_or_none(item.get("reasoning"))
            if text:
                parts.append(text)
                if field is None:
                    field = "reasoning"
                continue
            text = _coerce_text_or_none(item.get("reasoning_content"))
            if text:
                parts.append(text)
                if field is None:
                    field = "reasoning_content"
        joined = "\n".join(parts).strip()
        return (joined or None, field if joined else None)
    return (None, None)


def _extract_reasoning_text_and_field(obj: Any) -> Tuple[Optional[str], Optional[str]]:
    text = _coerce_text_or_none(_get_nested_attr_or_key(obj, "reasoning_content"))
    if text:
        return (text, "reasoning_content")
    text = _coerce_text_or_none(_get_nested_attr_or_key(obj, "reasoning"))
    if text:
        return (text, "reasoning")
    return _extract_reasoning_from_content(_get_nested_attr_or_key(obj, "content"))


def _extract_reasoning_text(obj: Any) -> Optional[str]:
    """
    兼容不同供应商的思考字段命名：
    - reasoning_content（OpenAI/DeepSeek 常见）
    - reasoning（部分兼容端）
    """
    return _extract_reasoning_text_and_field(obj)[0]


def format_tool_calls_for_openai_api(tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    将内部 tool_calls（name/args/id）转为 OpenAI Chat Completions 要求的
    tool_calls 项（含 function.name 与 JSON 字符串 arguments）。
    """
    out: List[Dict[str, Any]] = []
    for tc in tool_calls:
        name = tc.get("name", "")
        args = tc.get("args", {}) or {}
        tid = tc.get("id", "") or ""
        try:
            arg_str = json.dumps(args, ensure_ascii=False) if args else "{}"
        except TypeError:
            arg_str = "{}"
        out.append(
            {
                "id": tid,
                "type": "function",
                "function": {"name": name, "arguments": arg_str},
            }
        )
    return out


_MEDIA_TOKEN_RE = re.compile(
    r'(?P<q>["\'])(?P<qp>.+?\.(?:png|jpe?g|gif|webp|bmp|mp3|wav|ogg|flac|m4a|aac|mp4|webm|mov|avi))(?P=q)|'
    r'(?P<up>(?:[A-Za-z]:[\\/]|/|\.{1,2}[\\/])[^\s<>"\']+?\.(?:png|jpe?g|gif|webp|bmp|mp3|wav|ogg|flac|m4a|aac|mp4|webm|mov|avi))',
    re.IGNORECASE,
)
_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
_AUDIO_EXTS = {".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac"}
_VIDEO_EXTS = {".mp4", ".webm", ".mov", ".avi"}
_IMAGE_MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
}
_AUDIO_MIME = {
    ".mp3": "mp3",
    ".wav": "wav",
    ".ogg": "ogg",
    ".flac": "flac",
    ".m4a": "m4a",
    ".aac": "aac",
}
_VIDEO_MIME = {
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".mov": "video/quicktime",
    ".avi": "video/x-msvideo",
}
_MAX_INLINE_MEDIA_BYTES = max(1, int(os.getenv("MULTIMODAL_INLINE_MAX_BYTES", str(10 * 1024 * 1024))))


def _expand_media_paths_in_text(text: str) -> Any:
    """将文本中的图片/音频/视频路径展开为多模态 content parts；无命中则返回原文本。"""
    src = str(text or "")
    matches = list(_MEDIA_TOKEN_RE.finditer(src))
    if not matches:
        return src
    parts: List[Dict[str, Any]] = []
    last = 0
    media_found = 0
    for m in matches:
        raw = m.group("qp") or m.group("up") or ""
        if m.start() > last:
            prefix = src[last:m.start()]
            if prefix:
                parts.append({"type": "text", "text": prefix})
        last = m.end()
        p = Path(raw).expanduser()
        if not p.exists() or not p.is_file():
            parts.append({"type": "text", "text": m.group(0)})
            continue
        ext = p.suffix.lower()
        try:
            size = p.stat().st_size
            if size > _MAX_INLINE_MEDIA_BYTES:
                parts.append({"type": "text", "text": f"{m.group(0)} [skipped: too large]"})
                continue
            b64 = base64.b64encode(p.read_bytes()).decode("ascii")
            if ext in _IMAGE_EXTS:
                mime = _IMAGE_MIME.get(ext, "image/png")
                parts.append({"type": "text", "text": m.group(0)})
                parts.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}})
                media_found += 1
            elif ext in _AUDIO_EXTS:
                fmt = _AUDIO_MIME.get(ext, ext.lstrip("."))
                parts.append({"type": "text", "text": m.group(0)})
                parts.append({"type": "input_audio", "input_audio": {"data": b64, "format": fmt}})
                media_found += 1
            elif ext in _VIDEO_EXTS:
                # 兼容端差异较大：统一以 image_url/video data URL 透传，失败时模型仍可读文本提示。
                mime = _VIDEO_MIME.get(ext, "video/mp4")
                parts.append({"type": "text", "text": m.group(0)})
                parts.append({"type": "video_url", "video_url": {"url": f"data:{mime};base64,{b64}"}})
                media_found += 1
            else:
                parts.append({"type": "text", "text": m.group(0)})
        except Exception:
            parts.append({"type": "text", "text": m.group(0)})
    if last < len(src):
        parts.append({"type": "text", "text": src[last:]})
    if media_found <= 0:
        return src
    merged: List[Dict[str, Any]] = []
    for part in parts:
        if part.get("type") == "text" and merged and merged[-1].get("type") == "text":
            merged[-1]["text"] = str(merged[-1].get("text", "")) + str(part.get("text", ""))
        else:
            merged.append(part)
    return merged


def _exception_search_text(exc: BaseException) -> str:
    """Collect provider error text without depending on one SDK exception shape."""
    values: List[Any] = [
        getattr(exc, "message", None),
        getattr(exc, "body", None),
        getattr(exc, "code", None),
        exc,
    ]
    response = getattr(exc, "response", None)
    if response is not None:
        values.extend(
            [
                getattr(response, "text", None),
                getattr(response, "reason_phrase", None),
            ]
        )
    parts: List[str] = []
    for value in values:
        if value is None:
            continue
        if isinstance(value, (dict, list, tuple)):
            try:
                text = json.dumps(value, ensure_ascii=False)
            except Exception:
                text = str(value)
        else:
            text = str(value)
        if text and text not in parts:
            parts.append(text)
    return " ".join(parts).lower()


def _is_media_input_error(exc: BaseException) -> bool:
    """Return True when a provider rejects media capability or media content parts."""
    msg = _exception_search_text(exc)
    media_kw = (
        "image input",
        "image inputs",
        "images",
        "image_url",
        "input_image",
        "vision",
        "audio input",
        "audio inputs",
        "input_audio",
        "video input",
        "video inputs",
        "video_url",
        "multimodal",
        "multi-modal",
        "图片",
        "图像",
        "音频",
        "视频",
        "多模态",
    )
    reason_kw = (
        "not supported",
        "does not support",
        "doesn't support",
        "do not support",
        "don't support",
        "unsupported",
        "not_support",
        "not available",
        "cannot process",
        "can't process",
        "cannot handle",
        "can't handle",
        "only supports text",
        "text-only",
        "text only",
        "not found",
        "no endpoint",
        "invalid content type",
        "unsupported content type",
        "unsupported_value",
        "不支持",
        "无法处理",
        "仅支持文本",
    )
    return any(keyword in msg for keyword in media_kw) and any(
        keyword in msg for keyword in reason_kw
    )


def _is_stream_options_error(exc: BaseException) -> bool:
    """Return True only when retrying without stream_options can help."""
    msg = _exception_search_text(exc)
    stream_kw = ("stream_options", "include_usage")
    reason_kw = (
        "not supported",
        "does not support",
        "doesn't support",
        "unsupported",
        "unknown",
        "unexpected",
        "unrecognized",
        "extra fields",
        "extra inputs",
        "extra_forbidden",
        "not allowed",
        "not permitted",
        "invalid",
    )
    return any(keyword in msg for keyword in stream_kw) and any(
        keyword in msg for keyword in reason_kw
    )


def _api_messages_have_media(api_messages: List[Dict[str, Any]]) -> bool:
    for message in api_messages:
        content = message.get("content")
        if not isinstance(content, list):
            continue
        if any(
            isinstance(part, dict)
            and part.get("type") in ("image_url", "video_url", "input_audio")
            for part in content
        ):
            return True
    return False


def _strip_media_from_api_messages(api_messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Replace image/audio/video content parts with placeholder text."""
    _MEDIA_PLACEHOLDER = "[该消息包含多媒体内容（图片/音频/视频），但当前模型不支持，已用此文本占位]"
    cleaned: List[Dict[str, Any]] = []
    for msg in api_messages:
        c = msg.get("content")
        if isinstance(c, list):
            has_media = any(isinstance(p, dict) and p.get("type") in ("image_url", "video_url", "input_audio") for p in c)
            text_parts = [p for p in c if isinstance(p, dict) and p.get("type") == "text"]
            if text_parts:
                combined = " ".join(str(p.get("text", "")) for p in text_parts).strip()
                if has_media:
                    combined = _MEDIA_PLACEHOLDER + " " + combined
                cleaned.append({**msg, "content": combined})
            elif has_media:
                cleaned.append({**msg, "content": _MEDIA_PLACEHOLDER})
            else:
                cleaned.append(msg)
        else:
            cleaned.append(msg)
    return cleaned


def _append_multimodal_fallback_instruction(
    api_messages: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    out = list(api_messages)
    out.append(
        {
            "role": "system",
            "content": (
                "[多模态回退提示] 当前模型不支持直接识别该多媒体内容。"
                "可使用 task 工具选择支持多模态输入的模型，调用 subagent 识别多媒体内容；"
                "若该能力不可用，请明确告知用户。"
            ),
        }
    )
    return out


def _serialized_messages_to_text_only(
    api_messages: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Strip serialized media while preserving adjacent local-path text."""
    if not _api_messages_have_media(api_messages):
        return api_messages
    return _append_multimodal_fallback_instruction(
        _strip_media_from_api_messages(api_messages)
    )


def _is_glm_model(model: str) -> bool:
    s = str(model or "").strip().lower()
    return s.startswith("glm-")


def messages_to_openai_params(
    messages: List[Any],
    *,
    expand_media_paths: bool = True,
) -> List[Dict[str, Any]]:
    """将 UserMessage / AssistantMessage / ToolMessage / SystemMessage 转为 API messages 列表。"""
    api_msgs: List[Dict[str, Any]] = []
    for m in messages:
        if isinstance(m, SystemMessage):
            api_msgs.append({"role": "system", "content": m.content or ""})
        elif isinstance(m, UserMessage):
            if isinstance(m.content, list):
                api_msgs.append({"role": "user", "content": m.content})
            elif isinstance(m.content, str):
                content = (
                    _expand_media_paths_in_text(m.content)
                    if expand_media_paths
                    else m.content
                )
                api_msgs.append({"role": "user", "content": content})
            else:
                api_msgs.append({"role": "user", "content": str(m.content)})
        elif isinstance(m, AssistantMessage):
            item: Dict[str, Any] = {"role": "assistant", "content": strip_think_blocks(m.content or "")}
            if m.tool_calls:
                item["tool_calls"] = format_tool_calls_for_openai_api(m.tool_calls)
            ak = getattr(m, "additional_kwargs", None) or {}
            rc = None
            rc_field = "reasoning_content"
            if isinstance(ak, dict):
                raw_field = str(ak.get("reasoning_field") or "").strip()
                if raw_field in {"reasoning", "reasoning_content"}:
                    rc_field = raw_field
                rc = ak.get("reasoning_content", None)
                if rc is None:
                    rc = ak.get("reasoning", None)
            if rc is not None:
                item[rc_field] = str(rc)
            api_msgs.append(item)
        elif isinstance(m, ToolMessage):
            api_msgs.append(
                {
                    "role": "tool",
                    "tool_call_id": m.tool_call_id or "",
                    "content": m.content if isinstance(m.content, str) else str(m.content),
                }
            )
        else:
            c = getattr(m, "content", str(m))
            api_msgs.append({"role": "user", "content": str(c)})
    return api_msgs


def _messages_to_text_only_params(messages: List[Any]) -> List[Dict[str, Any]]:
    """
    Rebuild a failed multimodal request from the original messages.

    String user messages keep their original local paths. Already-structured
    multimodal messages have no recoverable local path, so their media parts
    use the explicit placeholder instead.
    """
    fallback_messages = _strip_media_from_api_messages(
        messages_to_openai_params(messages, expand_media_paths=False)
    )
    return _append_multimodal_fallback_instruction(fallback_messages)


def _messages_have_media_input(messages: List[Any]) -> bool:
    for message in messages:
        if not isinstance(message, UserMessage):
            continue
        content = message.content
        if isinstance(content, list):
            if any(
                isinstance(part, dict)
                and part.get("type") in ("image_url", "video_url", "input_audio")
                for part in content
            ):
                return True
            continue
        if not isinstance(content, str):
            continue
        for match in _MEDIA_TOKEN_RE.finditer(content):
            raw = match.group("qp") or match.group("up") or ""
            path = Path(raw).expanduser()
            try:
                if (
                    path.is_file()
                    and path.suffix.lower() in (_IMAGE_EXTS | _AUDIO_EXTS | _VIDEO_EXTS)
                    and path.stat().st_size <= _MAX_INLINE_MEDIA_BYTES
                ):
                    return True
            except OSError:
                continue
    return False


def _client_multimodal_input_enabled(client: Any) -> bool:
    return bool(getattr(client, "_myagent_multimodal_input", False))


def _mark_client_multimodal_failed(client: Any, exc: BaseException) -> None:
    try:
        setattr(client, "_myagent_multimodal_input", False)
    except Exception:
        pass
    callback = getattr(client, "_myagent_mark_multimodal_failed", None)
    if callable(callback):
        try:
            callback(exc)
        except Exception:
            logger.warning("记录模型多模态能力失败", exc_info=True)


def _messages_to_params_for_client(
    client: Any,
    messages: List[Any],
) -> List[Dict[str, Any]]:
    has_media = _messages_have_media_input(messages)
    if has_media and not _client_multimodal_input_enabled(client):
        return _messages_to_text_only_params(messages)
    return messages_to_openai_params(
        messages,
        expand_media_paths=_client_multimodal_input_enabled(client),
    )


def parse_assistant_message(
    msg: Any,
    tools: Optional[List[Dict[str, Any]]] = None,
) -> AssistantTurn:
    """解析 chat.completions 返回的 assistant message（content、tool_calls、reasoning_content）。"""
    content = _normalize_content_text(_get_nested_attr_or_key(msg, "content"))
    reasoning, reasoning_field = _extract_reasoning_text_and_field(msg)
    content = _strip_native_boundary_tokens(content).strip()
    reasoning = _strip_native_boundary_tokens(reasoning).strip() or None

    raw_calls = _get_nested_attr_or_key(msg, "tool_calls")
    tool_calls: Optional[List[Dict[str, Any]]] = None
    if raw_calls:
        tool_calls = []
        for tc in raw_calls:
            fn = _get_nested_attr_or_key(tc, "function")
            name = _get_nested_attr_or_key(fn, "name") if fn else ""
            raw_args = _get_nested_attr_or_key(fn, "arguments") if fn else "{}"
            tid = _get_nested_attr_or_key(tc, "id") or ""
            try:
                args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
            except json.JSONDecodeError:
                logger.warning("工具参数 JSON 解析失败，使用空对象: %s", raw_args[:200])
                args = {}
            tool_calls.append({"name": name, "args": args, "id": tid})
    if tools is not None:
        content, reasoning, tool_calls, _ = _repair_dsml_turn(
            content,
            reasoning,
            tools,
            tool_calls,
        )
    return AssistantTurn(
        content=content,
        tool_calls=tool_calls,
        reasoning_content=reasoning,
        reasoning_field=reasoning_field,
    )


def chat_completion(
    client: OpenAI,
    model: str,
    messages: List[Any],
    *,
    tools: Optional[List[Dict[str, Any]]] = None,
    temperature: float,
    max_tokens: int,
    extra_body: Optional[Dict[str, Any]] = None,
    parallel_tool_calls: bool = True,
    reasoning_effort: Optional[str] = None,
    omit_temperature: bool = False,
) -> ChatCompletion:
    """封装 client.chat.completions.create，支持 tools、extra_body、reasoning_effort（如 DeepSeek 思考模式）。"""
    api_messages = _messages_to_params_for_client(client, messages)
    kwargs: Dict[str, Any] = dict(
        model=model,
        messages=api_messages,
        max_tokens=max_tokens,
        parallel_tool_calls=parallel_tool_calls,
    )
    if not omit_temperature:
        kwargs["temperature"] = temperature
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
    if extra_body and not _is_glm_model(model):
        kwargs["extra_body"] = extra_body
    if reasoning_effort and not _is_glm_model(model):
        kwargs["reasoning_effort"] = reasoning_effort

    last_exc: Optional[BaseException] = None
    media_fallback_done = False
    attempt = 0
    while attempt < OPENAI_MAX_RETRIES:
        t0 = time.monotonic()
        try:
            r = client.chat.completions.create(**kwargs)
            dt = time.monotonic() - t0
            u = getattr(r, "usage", None)
            if u:
                ud = extract_usage_dict(u)
                pt = ud.get("prompt_tokens", 0)
                ct = ud.get("completion_tokens", 0)
                prompt_cache_hit_tokens = ud.get("prompt_cache_hit_tokens", 0)
                prompt_cache_miss_tokens = ud.get("prompt_cache_miss_tokens", 0)
                cache_total = prompt_cache_hit_tokens + prompt_cache_miss_tokens
                hit_pct = (
                    prompt_cache_hit_tokens / cache_total * 100 if cache_total > 0 else None
                )
                extra = ""
                if hit_pct is not None:
                    extra = f" hit_rate={hit_pct:.1f}%"
                logger.info(
                    "chat.completions 成功 model=%s 耗时=%.2fs "
                    "prompt_tokens=%s completion_tokens=%s "
                    "prompt_cache_hit_tokens=%s prompt_cache_miss_tokens=%s%s",
                    _masked_model_label(model),
                    dt,
                    pt,
                    ct,
                    prompt_cache_hit_tokens,
                    prompt_cache_miss_tokens,
                    extra,
                )
            else:
                logger.info("chat.completions 成功 model=%s 耗时=%.2fs", _masked_model_label(model), dt)
            return r
        except Exception as e:
            last_exc = e
            dt = time.monotonic() - t0
            if _is_media_input_error(e) and not media_fallback_done:
                media_fallback_done = True
                _mark_client_multimodal_failed(client, e)
                logger.warning(
                    "模型 %s 不支持多媒体输入，去掉图片/音频/视频后重试: %s",
                    _masked_model_label(model),
                    _redact_runtime_log_text(e),
                )
                kwargs["messages"] = _messages_to_text_only_params(messages)
                continue
            if not _is_retriable_openai_error(e) or attempt >= OPENAI_MAX_RETRIES - 1:
                logger.warning(
                    "chat.completions 失败 model=%s 耗时=%.2fs: %s",
                    _masked_model_label(model),
                    dt,
                    _redact_runtime_log_text(e),
                )
                raise
            delay = OPENAI_RETRY_BASE_SEC * (2**attempt)
            logger.warning(
                "chat.completions 可重试错误 model=%s (%.2fs)：%s；%.1fs 后重试 %s/%s",
                _masked_model_label(model),
                dt,
                _redact_runtime_log_text(e),
                delay,
                attempt + 1,
                OPENAI_MAX_RETRIES,
            )
            time.sleep(delay)
            attempt += 1
    assert last_exc is not None
    raise last_exc


def _accumulate_tool_call_delta(
    tool_acc: Dict[int, Dict[str, str]],
    delta_tool_calls: Any,
) -> None:
    """合并流式 chunk 中的 tool_calls 片段（按 index）。"""
    if not delta_tool_calls:
        return
    for tc in delta_tool_calls:
        idx = getattr(tc, "index", None)
        if idx is None:
            idx = 0
        if idx not in tool_acc:
            tool_acc[idx] = {"id": "", "name": "", "arguments": ""}
        tid = getattr(tc, "id", None)
        if tid:
            tool_acc[idx]["id"] = str(tid)
        fn = getattr(tc, "function", None)
        if fn:
            name = getattr(fn, "name", None)
            if name:
                tool_acc[idx]["name"] = str(name)
            args = getattr(fn, "arguments", None)
            if args:
                tool_acc[idx]["arguments"] += str(args)


def _tool_call_delta_payloads(delta_tool_calls: Any) -> List[Dict[str, str]]:
    if not delta_tool_calls:
        return []
    out: List[Dict[str, str]] = []
    for tc in delta_tool_calls:
        idx = getattr(tc, "index", None)
        if idx is None:
            idx = 0
        payload: Dict[str, str] = {"index": int(idx)}
        tid = getattr(tc, "id", None)
        if tid:
            payload["id"] = str(tid)
        fn = getattr(tc, "function", None)
        if fn:
            name = getattr(fn, "name", None)
            if name:
                payload["name_delta"] = str(name)
            args = getattr(fn, "arguments", None)
            if args:
                payload["arguments_delta"] = str(args)
        if len(payload) > 1:
            out.append(payload)
    return out


def _tool_acc_to_parsed_list(tool_acc: Dict[int, Dict[str, str]]) -> Optional[List[Dict[str, Any]]]:
    if not tool_acc:
        return None
    tool_calls: List[Dict[str, Any]] = []
    for i in sorted(tool_acc.keys()):
        row = tool_acc[i]
        name = (row.get("name") or "").strip()
        tid = row.get("id") or ""
        raw_args = row.get("arguments") or "{}"
        try:
            args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
        except json.JSONDecodeError:
            logger.warning("流式工具参数 JSON 未完整或无效，使用空对象: %s", raw_args[:200])
            args = {}
        if not name and not args and not tid:
            continue
        tool_calls.append({"name": name, "args": args, "id": tid, "index": i})
    return tool_calls or None


def run_chat_completion_stream_worker(
    sync_q: "Queue[Optional[Tuple[str, Any]]]",
    client: OpenAI,
    model: str,
    messages: List[Any],
    *,
    tools: Optional[List[Dict[str, Any]]] = None,
    temperature: float,
    max_tokens: int,
    extra_body: Optional[Dict[str, Any]] = None,
    parallel_tool_calls: bool = True,
    reasoning_effort: Optional[str] = None,
    omit_temperature: bool = False,
    should_abort: Optional[Callable[[], bool]] = None,
    transport_observer: Optional[Any] = None,
) -> None:
    """
    在后台线程中跑 chat.completions(stream=True)。
    经 sync_q 投递：("reasoning", str)、("content", str)、("turn", AssistantTurn)；
    失败时 ("err", Exception)；最后一定放入 None。
    """
    api_t0 = time.perf_counter()

    def put_stream_timing(step: str, **extra: Any) -> None:
        try:
            payload: Dict[str, Any] = {
                "step": step,
                "ms_since_api_start": int(max(0.0, (time.perf_counter() - api_t0) * 1000.0)),
                "model": model,
            }
            payload.update(extra)
            sync_q.put(("stream_timing", payload))
        except Exception:
            pass

    try:
        api_messages = _messages_to_params_for_client(client, messages)
        kwargs: Dict[str, Any] = dict(
            model=model,
            messages=api_messages,
            max_tokens=max_tokens,
            parallel_tool_calls=parallel_tool_calls,
            stream=True,
        )
        if not omit_temperature:
            kwargs["temperature"] = temperature
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        if extra_body and not _is_glm_model(model):
            kwargs["extra_body"] = extra_body
        if reasoning_effort and not _is_glm_model(model):
            kwargs["reasoning_effort"] = reasoning_effort
        # include_usage 使末包返回 usage；部分兼容端会忽略或报错
        stream = None
        stream_iter = None
        first_stream_chunk = _MISSING

        def abort_requested() -> bool:
            if should_abort is None:
                return False
            try:
                return bool(should_abort())
            except Exception:
                return False

        def close_stream_quietly() -> None:
            close_fn = getattr(stream, "close", None)
            if callable(close_fn):
                try:
                    close_fn()
                except Exception:
                    pass

        media_fallback_done = False
        if transport_observer is not None:
            try:
                transport_observer.start_transport_trace()
            except Exception:
                pass
        put_stream_timing("request_serialized", messages=len(api_messages), tools=len(tools or []))
        put_stream_timing(
            "request_start",
            messages=len(api_messages),
            tools=len(tools or []),
            max_tokens=max_tokens,
        )
        attempt = 0
        while attempt < OPENAI_MAX_RETRIES:
            if abort_requested():
                put_stream_timing("aborted_before_create", attempt=attempt + 1)
                return
            try:
                put_stream_timing("create_attempt_start", attempt=attempt + 1)
                try:
                    stream = client.chat.completions.create(
                        **kwargs, stream_options={"include_usage": True}
                    )
                except Exception as e1:
                    if _is_media_input_error(e1) or not _is_stream_options_error(e1):
                        raise
                    logger.debug("流式 create 无 stream_options 或端点不支持: %s", _redact_runtime_log_text(e1))
                    stream = client.chat.completions.create(**kwargs)
                put_stream_timing("stream_created", attempt=attempt + 1)
                stream_iter = iter(stream)
                try:
                    first_stream_chunk = next(stream_iter)
                except StopIteration:
                    first_stream_chunk = _MISSING
                break
            except Exception as e:
                close_stream_quietly()
                if _is_media_input_error(e) and not media_fallback_done:
                    media_fallback_done = True
                    _mark_client_multimodal_failed(client, e)
                    logger.warning(
                        "流式: 模型 %s 不支持多媒体输入，去掉图片/音频/视频后重试: %s",
                        _masked_model_label(model),
                        _redact_runtime_log_text(e),
                    )
                    kwargs["messages"] = _messages_to_text_only_params(messages)
                    sync_q.put(("status", "[提示] 当前模型不支持多媒体输入，已保留文件路径并切换为纯文本模式"))
                    put_stream_timing("media_fallback_retry", attempt=attempt + 1)
                    continue
                if not _is_retriable_openai_error(e) or attempt >= OPENAI_MAX_RETRIES - 1:
                    put_stream_timing("create_failed", attempt=attempt + 1, error=type(e).__name__)
                    raise
                delay = OPENAI_RETRY_BASE_SEC * (2**attempt)
                logger.warning(
                    "流式 chat.completions 重试 %s/%s 等待 %.1fs: %s",
                    attempt + 1,
                    OPENAI_MAX_RETRIES,
                    delay,
                    _redact_runtime_log_text(e),
                )
                put_stream_timing("retry_sleep", attempt=attempt + 1, delay_ms=int(delay * 1000), error=type(e).__name__)
                time.sleep(delay)
                attempt += 1
        if stream is None:
            raise RuntimeError("stream 创建失败")
        reasoning_buf = ""
        reasoning_field: Optional[str] = None
        content_buf = ""
        tool_acc: Dict[int, Dict[str, str]] = {}
        content_boundary_filter = _NativeBoundaryStreamFilter()
        reasoning_boundary_filter = _NativeBoundaryStreamFilter()
        content_dsml_filter = _DsmlStreamFilter(enabled=bool(tools))
        reasoning_dsml_filter = _DsmlStreamFilter(enabled=bool(tools))
        last_usage: Optional[Dict[str, int]] = None
        actual_model = ""
        finish_meta: Dict[str, Any] = {"finish_reason": None, "stop_reason": None}
        first_chunk_seen = False
        first_delta_seen = False
        first_reasoning_seen = False
        first_content_seen = False
        first_tool_delta_seen = False
        transport_breakdown_emitted = False
        first_delta_at_ms: Optional[int] = None
        last_delta_at_ms: Optional[int] = None
        usage_chunk_at_ms: Optional[int] = None
        response_payload_bytes_estimated = 0
        chunk_count = 0

        def api_elapsed_ms() -> int:
            return int(max(0.0, (time.perf_counter() - api_t0) * 1000.0))

        def emit_transport_breakdown_once() -> None:
            nonlocal transport_breakdown_emitted
            if transport_breakdown_emitted or transport_observer is None:
                return
            transport_breakdown_emitted = True
            try:
                snapshot = transport_observer.snapshot_transport_trace()
                events = list(snapshot.get("events") or [])
                metrics = dict(snapshot.get("metrics") or {})
                starts: Dict[str, int] = {}
                phases: Dict[str, int] = {}
                for row in events:
                    event_name = str(row.get("event") or "")
                    at_ms = int(row.get("at_ms") or 0)
                    if event_name.endswith(".started"):
                        starts[event_name[:-8]] = at_ms
                    elif event_name.endswith(".complete"):
                        base = event_name[:-9]
                        if base in starts:
                            key = re.sub(r"[^a-zA-Z0-9]+", "_", base).strip("_") + "_ms"
                            phases[key] = max(0, at_ms - starts[base])
                put_stream_timing(
                    "transport_breakdown",
                    trace_elapsed_ms=int(snapshot.get("elapsed_ms") or 0),
                    request_bytes=int(metrics.get("request_bytes") or 0),
                    response_content_length=int(metrics.get("response_content_length") or 0),
                    **phases,
                )
            except Exception:
                pass
        def iter_stream_chunks():
            if first_stream_chunk is not _MISSING:
                yield first_stream_chunk
            if stream_iter is not None:
                yield from stream_iter

        for chunk in iter_stream_chunks():
            if abort_requested():
                close_stream_quietly()
                put_stream_timing("aborted_during_stream")
                return
            chunk_count += 1
            try:
                raw_chunk = chunk.model_dump(mode="json") if hasattr(chunk, "model_dump") else str(chunk)
                response_payload_bytes_estimated += len(
                    json.dumps(raw_chunk, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                )
            except Exception:
                pass
            if not first_chunk_seen:
                first_chunk_seen = True
                put_stream_timing("first_chunk", chunk_count=chunk_count)
            chunk_model = str(getattr(chunk, "model", None) or "").strip()
            if chunk_model:
                actual_model = chunk_model
            uo = getattr(chunk, "usage", None)
            if uo is not None:
                last_usage = extract_usage_dict(uo)
                usage_chunk_at_ms = api_elapsed_ms()
                put_stream_timing("usage_chunk", chunk_count=chunk_count)
            if not chunk.choices:
                continue
            choice0 = chunk.choices[0]
            fr = getattr(choice0, "finish_reason", None)
            sr = getattr(choice0, "stop_reason", None)
            if fr is not None:
                finish_meta["finish_reason"] = fr
            if sr is not None:
                finish_meta["stop_reason"] = sr
            delta = choice0.delta
            if not delta:
                continue
            rc, rc_field = _extract_reasoning_text_and_field(delta)
            if rc:
                piece = rc if isinstance(rc, str) else str(rc)
                last_delta_at_ms = api_elapsed_ms()
                reasoning_buf += piece
                visible_piece = reasoning_dsml_filter.feed(
                    reasoning_boundary_filter.feed(piece)
                )
                if reasoning_field is None and rc_field:
                    reasoning_field = rc_field
                if visible_piece and not first_delta_seen:
                    first_delta_seen = True
                    first_delta_at_ms = last_delta_at_ms
                    put_stream_timing("first_delta", delta_type="reasoning", chars=len(visible_piece), chunk_count=chunk_count)
                    emit_transport_breakdown_once()
                if visible_piece and not first_reasoning_seen:
                    first_reasoning_seen = True
                    put_stream_timing("first_reasoning_delta", chars=len(visible_piece), chunk_count=chunk_count)
                if visible_piece:
                    sync_q.put(("reasoning", visible_piece))
            ct = getattr(delta, "content", None)
            if ct:
                piece = ct if isinstance(ct, str) else str(ct)
                last_delta_at_ms = api_elapsed_ms()
                content_buf += piece
                visible_piece = content_dsml_filter.feed(
                    content_boundary_filter.feed(piece)
                )
                if visible_piece and not first_delta_seen:
                    first_delta_seen = True
                    first_delta_at_ms = last_delta_at_ms
                    put_stream_timing("first_delta", delta_type="content", chars=len(visible_piece), chunk_count=chunk_count)
                    emit_transport_breakdown_once()
                if visible_piece and not first_content_seen:
                    first_content_seen = True
                    put_stream_timing("first_content_delta", chars=len(visible_piece), chunk_count=chunk_count)
                if visible_piece:
                    sync_q.put(("content", visible_piece))
            delta_tool_calls = getattr(delta, "tool_calls", None)
            for payload in _tool_call_delta_payloads(delta_tool_calls):
                last_delta_at_ms = api_elapsed_ms()
                if not first_delta_seen:
                    first_delta_seen = True
                    first_delta_at_ms = last_delta_at_ms
                    put_stream_timing("first_delta", delta_type="tool_call", chunk_count=chunk_count)
                    emit_transport_breakdown_once()
                if not first_tool_delta_seen:
                    first_tool_delta_seen = True
                    put_stream_timing("first_tool_call_delta", chunk_count=chunk_count)
                sync_q.put(("tool_call_delta", payload))
            _accumulate_tool_call_delta(tool_acc, delta_tool_calls)
        put_stream_timing("stream_exhausted", chunk_count=chunk_count)
        if transport_observer is not None:
            try:
                final_transport = transport_observer.snapshot_transport_trace()
                transport_metrics = dict(final_transport.get("metrics") or {})
                put_stream_timing(
                    "transport_final",
                    trace_elapsed_ms=int(final_transport.get("elapsed_ms") or 0),
                    request_bytes=int(transport_metrics.get("request_bytes") or 0),
                    response_content_length=int(transport_metrics.get("response_content_length") or 0),
                    response_payload_bytes_estimated=int(response_payload_bytes_estimated),
                )
            except Exception:
                pass
        if abort_requested():
            close_stream_quietly()
            put_stream_timing("aborted_after_stream")
            return
        reasoning_tail = reasoning_dsml_filter.feed(reasoning_boundary_filter.finish())
        reasoning_tail += reasoning_dsml_filter.finish()
        if reasoning_tail:
            sync_q.put(("reasoning", reasoning_tail))
        content_tail = content_dsml_filter.feed(content_boundary_filter.finish())
        content_tail += content_dsml_filter.finish()
        if content_tail:
            sync_q.put(("content", content_tail))
        tool_calls_list = _tool_acc_to_parsed_list(tool_acc)
        content_final, reasoning_final, tool_calls_list, recovered_dsml_calls = _repair_dsml_turn(
            _strip_native_boundary_tokens(content_buf),
            _strip_native_boundary_tokens(reasoning_buf).strip() or None,
            tools,
            tool_calls_list,
        )
        if recovered_dsml_calls:
            start_index = len(tool_acc)
            for offset, call in enumerate(recovered_dsml_calls):
                sync_q.put(
                    (
                        "tool_call_delta",
                        {
                            "index": start_index + offset,
                            "id": str(call.get("id") or ""),
                            "name_delta": str(call.get("name") or ""),
                            "arguments_delta": json.dumps(
                                call.get("args") or {},
                                ensure_ascii=False,
                                separators=(",", ":"),
                            ),
                        },
                    )
                )
            finish_meta["finish_reason"] = "tool_calls"
            logger.warning(
                "已从模型原始 DSML 文本安全恢复 %s 个工具调用 model=%s",
                len(recovered_dsml_calls),
                _masked_model_label(actual_model or model),
            )
        turn = AssistantTurn(
            content=content_final or "",
            tool_calls=tool_calls_list,
            reasoning_content=reasoning_final,
            reasoning_field=reasoning_field,
        )
        if last_usage:
            usage_payload: Dict[str, Any] = dict(last_usage)
            usage_end_ms = int(usage_chunk_at_ms if usage_chunk_at_ms is not None else api_elapsed_ms())
            first_ms = int(first_delta_at_ms or 0)
            last_ms = int(last_delta_at_ms if last_delta_at_ms is not None else first_ms)
            usage_payload["_timing"] = {
                "first_token_wait_ms": max(0, first_ms),
                "token_generation_ms": max(0, last_ms - first_ms),
                "usage_return_ms": max(0, usage_end_ms - last_ms),
                "measured_total_ms": max(0, usage_end_ms),
            }
            if actual_model:
                usage_payload["model"] = actual_model
            sync_q.put(("usage", usage_payload))
            logger.info(
                "chat.completions stream usage model=%s prompt_tokens=%s completion_tokens=%s "
                "prompt_cache_hit_tokens=%s prompt_cache_miss_tokens=%s",
                _masked_model_label(actual_model or model),
                last_usage.get("prompt_tokens", 0),
                last_usage.get("completion_tokens", 0),
                last_usage.get("prompt_cache_hit_tokens", 0),
                last_usage.get("prompt_cache_miss_tokens", 0),
            )
        if actual_model:
            finish_meta["model"] = actual_model
        sync_q.put(("finish", finish_meta))
        sync_q.put(("turn", turn))
        put_stream_timing(
            "turn_ready",
            chunk_count=chunk_count,
            reasoning_chars=len(reasoning_final or ""),
            content_chars=len(content_final or ""),
            tool_calls=len(tool_calls_list or []),
        )
    except Exception as e:
        put_stream_timing("stream_error", error=type(e).__name__)
        logger.warning("chat.completions 流式调用异常: %s", _redact_runtime_log_text(e))
        sync_q.put(("err", e))
    finally:
        if transport_observer is not None:
            try:
                transport_observer.finish_transport_trace()
            except Exception:
                pass
        sync_q.put(None)


def single_turn_text_completion(
    client: OpenAI,
    model: str,
    user_text: str,
    *,
    temperature: float,
    max_tokens: int,
) -> Tuple[str, Optional[Dict[str, int]]]:
    """单条 user 消息的非流式补全（会话标题、压缩摘要等）。返回 (文本, usage 或 None)。"""
    last_exc: Optional[BaseException] = None
    r = None
    for attempt in range(OPENAI_MAX_RETRIES):
        try:
            r = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": user_text}],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            break
        except Exception as e:
            last_exc = e
            if not _is_retriable_openai_error(e) or attempt >= OPENAI_MAX_RETRIES - 1:
                raise
            time.sleep(OPENAI_RETRY_BASE_SEC * (2**attempt))
    if r is None:
        assert last_exc is not None
        raise last_exc
    msg = r.choices[0].message
    text = _normalize_content_text(getattr(msg, "content", ""))
    usage: Optional[Dict[str, int]] = None
    u = getattr(r, "usage", None)
    if u is not None:
        usage = extract_usage_dict(u)
    return (text, usage)
