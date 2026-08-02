"""
使用本仓库内 tokenizer.json（HuggingFace 格式）估算 token 数。

优先用 HuggingFace `tokenizers` 库（Rust 实现、**不依赖 PyTorch**），避免
`transformers.AutoTokenizer` 触发 torch 检测与长导入。

目录默认：<项目根>/tools/deepseek_v3_tokenizer
或通过环境变量 DEEPSEEK_TOKENIZER_DIR 指定。不可用时回退为「字符 / 4」。

另含「整包输入」token 估算（静态 system + key_context + 多轮对话），供 agent_loop /
agent_memory 与右上角占用一致；其中对 agent_harness / agent_tools 的引用在函数内延迟 import，
避免 agent_harness → agent_tokenizer → agent_harness 循环初始化。
"""

from __future__ import annotations

import logging
import hashlib
import os
import platform
import re
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from agent_messages import AssistantMessage, SystemMessage, ToolMessage, UserMessage

logger = logging.getLogger(__name__)

_TOKENIZER: Any = None
_LOAD_FAILED: bool = False
_FULL_INPUT_TOKEN_CACHE: Dict[Tuple[str, int, str, str, str], Tuple[float, int]] = {}
_FULL_INPUT_TOKEN_CACHE_LOCK = threading.Lock()
_FULL_INPUT_TOKEN_CACHE_TTL_SEC = 30.0
_FULL_INPUT_TOKEN_CACHE_MAX = 256
_PROMPT_USAGE_BASELINE_CACHE: Dict[str, Dict[str, Any]] = {}
_PROMPT_USAGE_EXACT_CACHE: Dict[Tuple[str, str], Tuple[float, int, str]] = {}
_PROMPT_USAGE_CACHE_LOCK = threading.Lock()
_PROMPT_USAGE_CACHE_TTL_SEC = 300.0
_PROMPT_USAGE_EXACT_CACHE_MAX = 256


def _token_cache_text_hash(text: Any) -> str:
    return hashlib.sha1(str(text or "").encode("utf-8", errors="ignore")).hexdigest()


def _full_input_token_cache_key(session_id: str, llm_history: List[Any], key_context: str) -> Tuple[str, int, str, str]:
    message_fingerprint = _messages_token_fingerprint_from_hashes(
        _messages_token_hashes(list(llm_history or []))
    )
    return (
        str(session_id or "").strip(),
        len(llm_history or []),
        _token_cache_text_hash(key_context or ""),
        message_fingerprint,
    )


def _message_token_cache_repr(msg: Any) -> Dict[str, Any]:
    additional_kwargs = getattr(msg, "additional_kwargs", None) or {}
    if not isinstance(additional_kwargs, dict):
        additional_kwargs = {}
    data: Dict[str, Any] = {
        "type": type(msg).__name__,
        "content": str(getattr(msg, "content", "") or ""),
    }
    tool_call_id = getattr(msg, "tool_call_id", "")
    if tool_call_id:
        data["tool_call_id"] = str(tool_call_id)
    name = getattr(msg, "name", "")
    if name:
        data["name"] = str(name)
    tool_calls = getattr(msg, "tool_calls", None) or additional_kwargs.get("tool_calls")
    if tool_calls:
        data["tool_calls"] = tool_calls
    return data


def _message_token_cache_hash(msg: Any) -> str:
    raw = json_dumps_stable(_message_token_cache_repr(msg))
    return hashlib.sha1(raw.encode("utf-8", errors="ignore")).hexdigest()


def json_dumps_stable(value: Any) -> str:
    import json

    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    except Exception:
        return str(value)


def _messages_token_fingerprint_from_hashes(hashes: List[str]) -> str:
    return hashlib.sha1("\n".join(hashes).encode("ascii", errors="ignore")).hexdigest()


def _messages_token_hashes(messages: List[Any]) -> List[str]:
    return [_message_token_cache_hash(m) for m in list(messages or [])]


def _evict_prompt_usage_exact_cache_locked(now: float) -> None:
    expired = [
        key
        for key, cached in _PROMPT_USAGE_EXACT_CACHE.items()
        if now - float(cached[0]) > _PROMPT_USAGE_CACHE_TTL_SEC
    ]
    for key in expired:
        _PROMPT_USAGE_EXACT_CACHE.pop(key, None)
    while len(_PROMPT_USAGE_EXACT_CACHE) > _PROMPT_USAGE_EXACT_CACHE_MAX:
        oldest = min(_PROMPT_USAGE_EXACT_CACHE.items(), key=lambda item: item[1][0])[0]
        _PROMPT_USAGE_EXACT_CACHE.pop(oldest, None)


def _is_loop_marker_text(text: str) -> bool:
    c = (text or "").strip()
    return c == "New Agent Loop Start" or c.startswith("Loop finished")


def _strip_tool_display_prefix(text: str) -> str:
    s = str(text or "")
    return re.sub(r"^(?:\U0001f527\s*)?Tool Call:\s*[^\n]*?->\s*", "", s, count=1)


def _default_tokenizer_dir() -> Path:
    env = (os.getenv("DEEPSEEK_TOKENIZER_DIR") or "").strip()
    if env:
        return Path(env)
    return Path(__file__).resolve().parent / "tools" / "deepseek_v3_tokenizer"


def _get_tokenizer() -> Optional[Any]:
    """返回 `tokenizers.Tokenizer` 实例，失败则 None（之后始终走字符/4）。"""
    global _TOKENIZER, _LOAD_FAILED
    if _LOAD_FAILED:
        return None
    if _TOKENIZER is not None:
        return _TOKENIZER
    d = _default_tokenizer_dir()
    path = d / "tokenizer.json"
    if not path.is_file():
        _LOAD_FAILED = True
        logger.info("未找到 DeepSeek 词表（缺 tokenizer.json），token 估算使用字符/4：%s", d)
        return None
    try:
        from tokenizers import Tokenizer  # type: ignore

        _TOKENIZER = Tokenizer.from_file(str(path))
        logger.info("已加载 tokenizer.json 用于 token 估算（tokenizers，无 PyTorch 依赖）：%s", path)
        return _TOKENIZER
    except Exception as e:
        _LOAD_FAILED = True
        logger.warning("加载 tokenizer.json 失败，回退字符/4：%s", e)
        return None


def _flatten_messages_for_count(messages: List[Any]) -> str:
    """与历史上 estimate_message 口径一致：汇总 content、tool_calls、reasoning。"""
    parts: List[str] = []
    for msg in messages:
        if isinstance(msg, SystemMessage) and _is_loop_marker_text(getattr(msg, "content", "")):
            continue
        if hasattr(msg, "content"):
            c = msg.content
            if isinstance(c, str):
                parts.append(_strip_tool_display_prefix(c) if isinstance(msg, ToolMessage) else c)
            elif c is not None:
                parts.append(str(c))
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            parts.append(str(msg.tool_calls))
        ak = getattr(msg, "additional_kwargs", None) or {}
        if isinstance(ak, dict) and ak.get("reasoning_content"):
            parts.append(str(ak["reasoning_content"]))
    return "\n\n".join(parts)


def _count_by_chars_4(s: str) -> int:
    if not s:
        return 0
    return max(0, len(s) // 4)


def count_text_tokens(text: str) -> int:
    s = text or ""
    tok = _get_tokenizer()
    if tok is None:
        return _count_by_chars_4(s)
    try:
        enc = tok.encode(s)
        return len(enc.ids)
    except Exception as e:
        logger.debug("encode 失败，回退字符/4：%s", e)
        return _count_by_chars_4(s)


def count_message_tokens(messages: List[Any]) -> int:
    return count_text_tokens(_flatten_messages_for_count(messages))


def record_prompt_tokens_for_messages(
    session_id: str,
    messages: List[Any],
    prompt_tokens: int,
) -> None:
    """Record provider-reported input tokens for an exact request package."""
    sid = str(session_id or "").strip()
    try:
        tokens = int(prompt_tokens or 0)
    except (TypeError, ValueError):
        tokens = 0
    if not sid or tokens <= 0:
        return
    from agent_harness import strip_reasoning_for_api_request

    stripped = strip_reasoning_for_api_request(list(messages or []))
    hashes = _messages_token_hashes(stripped)
    fingerprint = _messages_token_fingerprint_from_hashes(hashes)
    now = time.monotonic()
    with _PROMPT_USAGE_CACHE_LOCK:
        _PROMPT_USAGE_BASELINE_CACHE[sid] = {
            "ts": now,
            "hashes": hashes,
            "fingerprint": fingerprint,
            "count": len(hashes),
            "tokens": tokens,
            "messages": list(stripped),
        }
        _PROMPT_USAGE_EXACT_CACHE[(sid, fingerprint)] = (now, tokens, "provider_exact")
        _evict_prompt_usage_exact_cache_locked(now)


def estimate_full_input_tokens_for_messages(
    session_id: str,
    messages: List[Any],
    *,
    return_source: bool = False,
) -> Any:
    """
    Estimate tokens for the already-built API request package.

    Prefer exact provider usage from a previous identical request, then reuse a
    provider-reported prefix baseline and estimate only the appended suffix.
    """
    from agent_harness import estimate_tokens, strip_reasoning_for_api_request

    sid = str(session_id or "").strip()
    stripped = strip_reasoning_for_api_request(list(messages or []))
    hashes = _messages_token_hashes(stripped)
    fingerprint = _messages_token_fingerprint_from_hashes(hashes)
    now = time.monotonic()
    calibration = None
    with _PROMPT_USAGE_CACHE_LOCK:
        exact = _PROMPT_USAGE_EXACT_CACHE.get((sid, fingerprint)) if sid else None
        if exact and now - exact[0] <= _PROMPT_USAGE_CACHE_TTL_SEC:
            result = (int(exact[1]), str(exact[2] if len(exact) > 2 else "provider_exact"))
            return result if return_source else result[0]
        baseline = _PROMPT_USAGE_BASELINE_CACHE.get(sid) if sid else None
        if baseline and now - float(baseline.get("ts") or 0) > _PROMPT_USAGE_CACHE_TTL_SEC:
            _PROMPT_USAGE_BASELINE_CACHE.pop(sid, None)
            baseline = None
        if baseline:
            base_count = int(baseline.get("count") or 0)
            base_tokens = int(baseline.get("tokens") or 0)
            base_fingerprint = str(baseline.get("fingerprint") or "")
            if (
                base_count > 0
                and base_tokens > 0
                and base_count <= len(hashes)
                and _messages_token_fingerprint_from_hashes(hashes[:base_count]) == base_fingerprint
            ):
                suffix = stripped[base_count:]
                suffix_tokens = int(estimate_tokens(suffix)) if suffix else 0
                margin = max(8, len(suffix) * 4) if suffix else 0
                estimated = base_tokens + suffix_tokens + margin
                _PROMPT_USAGE_EXACT_CACHE[(sid, fingerprint)] = (now, estimated, "provider_prefix")
                _evict_prompt_usage_exact_cache_locked(now)
                result = (int(estimated), "provider_prefix")
                return result if return_source else result[0]
            base_hashes = list(baseline.get("hashes") or [])
            common = 0
            for left, right in zip(base_hashes, hashes):
                if left != right:
                    break
                common += 1
            changed_tail = (len(base_hashes) - common) + (len(hashes) - common)
            if (
                common > 0
                and common >= max(1, min(len(base_hashes), len(hashes)) // 2)
                and changed_tail <= 4
            ):
                calibration = dict(baseline)
    estimated = int(estimate_tokens(stripped))
    source = "local_estimate"
    if calibration:
        base_tokens = int(calibration.get("tokens") or 0)
        base_messages = list(calibration.get("messages") or [])
        base_local_tokens = int(estimate_tokens(base_messages)) if base_messages else 0
        if base_tokens > 0 and base_local_tokens > 0:
            estimated = max(0, int(round(estimated * (base_tokens / base_local_tokens))))
            source = "provider_calibrated"
    with _PROMPT_USAGE_CACHE_LOCK:
        if sid:
            _PROMPT_USAGE_EXACT_CACHE[(sid, fingerprint)] = (now, estimated, source)
            _evict_prompt_usage_exact_cache_locked(now)
    result = (estimated, source)
    return result if return_source else result[0]


def estimate_calculated_input_tokens_for_messages(messages: List[Any]) -> int:
    """Estimate an assembled API request locally, without provider-usage caches.

    This is deliberately the same pure-tokenizer path used by the history
    preview in context compression.  It is used by CONTEXT_TOKEN_MODE=calculated
    so the auto-compression trigger cannot disagree with that preview merely
    because a provider reported a different token count for an earlier request.
    """
    from agent_harness import estimate_tokens, strip_reasoning_for_api_request

    stripped = strip_reasoning_for_api_request(list(messages or []))
    return int(estimate_tokens(stripped))


# ==================== 整包输入 token（与主模型上送一致）====================


def inject_missing_tool_messages(messages: List[Any]) -> List[Any]:
    """
    含 tool_calls 的 assistant 后必须紧跟对应 id 的 tool 消息；缺则用占位 ToolMessage 补齐，避免 400。
    """
    result: List[Any] = []
    idx = 0
    n = len(messages)
    while idx < n:
        msg = messages[idx]
        result.append(msg)
        if isinstance(msg, AssistantMessage) and getattr(msg, "tool_calls", None):
            need_ids = [tc.get("id") for tc in msg.tool_calls if tc.get("id")]
            seen = set()
            idx += 1
            while idx < n and isinstance(messages[idx], ToolMessage):
                tm = messages[idx]
                tid = getattr(tm, "tool_call_id", None) or ""
                if tid:
                    seen.add(tid)
                result.append(tm)
                idx += 1
            for tid in need_ids:
                if tid and tid not in seen:
                    result.append(
                        ToolMessage(
                            content="[工具返回缺失：可能因会话中断或历史压缩未保留，此为占位。]",
                            tool_call_id=tid,
                        )
                    )
            continue
        idx += 1
    return result


def messages_for_openai_turns(llm_history: List[Any]) -> List[Any]:
    """
    从持久化 llm_history 中构造 API 多轮（user/assistant/tool），不含前置静态 system 链与 key_context system（由外部拼接）。
    压缩区在微压与全量保留之间，可为：
    - 新版：System「Conversation compacted」+ User「[压缩摘要]…」，均原样上送（user 不包一层 [系统上下文]）；
    - 旧版：System「【历史上下文已压缩/摘要区】…」仍原样上送。
    其它非以上 System（提醒等）转为带 [系统上下文] 前缀的 user，避免与专用 system 层混淆。
    """
    from agent_harness import (
        is_compress_summary_system_message,
        is_conversation_compress_boundary_system,
    )

    out: List[Any] = []
    skip_contents = {
        "New Agent Loop Start",
        "Loop finished",
    }
    for msg in llm_history:
        if isinstance(msg, UserMessage):
            out.append(msg)
        elif isinstance(msg, AssistantMessage):
            out.append(msg)
        elif isinstance(msg, ToolMessage):
            out.append(ToolMessage(content=_strip_tool_display_prefix(msg.content), tool_call_id=msg.tool_call_id))
        elif isinstance(msg, SystemMessage):
            c = (msg.content or "").strip()
            if c in skip_contents:
                continue
            if is_compress_summary_system_message(msg) or is_conversation_compress_boundary_system(msg):
                out.append(msg)
                continue
            out.append(UserMessage(content="[系统上下文]\n" + (msg.content or "")))
        else:
            out.append(UserMessage(content=str(getattr(msg, "content", ""))))
    return out


def build_env_static(session_id: Optional[str] = None) -> str:
    """Build the Environment block: calendar month, OS, paths, session storage (no live workspace listing)."""
    from agent_harness import PROJECT_ROOT as AGENT_PROJECT_ROOT, WORK_DIR, session_manager
    from agent_tools import describe_run_shell_executor_for_prompt

    sid = (session_id or "").strip()

    wdir = str(WORK_DIR.resolve())
    proj = str(AGENT_PROJECT_ROOT.resolve())

    session_lines = ""
    if sid:
        try:
            from runtime_v2 import runtime_v2_primary

            is_v2 = bool(runtime_v2_primary())
        except Exception:
            is_v2 = True
        sdir = session_manager._get_session_path(sid).resolve()
        try:
            v_session = "/" + str(sdir.relative_to(WORK_DIR.resolve())).replace("\\", "/")
        except ValueError:
            v_session = f"/sessions/{sid}"
        v_key = f"{v_session}/key_context.md"
        v_todo = f"{v_session}/todo_plan.md"
        session_lines = f"""
- **Session storage directory**: {sdir}
  - Virtual path from `WORK_DIR`: `{v_session}`. Use this virtual path with file tools when possible; OS-absolute paths are shown only for orientation.
  - Main files: `llm_history.json`, `dialogue_history.json` (user↔final from `ui_events`), `work_messages.json`, `ui_events.json`, `key_context.md`, `todo_plan.md`, `metadata.json`, plus related artifacts.
  - Read or grep this directory when in-context messages are insufficient and you need persisted history or the event stream.
  - Persistent key facts belong in `key_context.md`: `{v_key}`. Use `context_manage` with `mode=edit_key_context` to revise it.
  - Live todo state belongs in `todo_plan.md`: `{v_todo}`. Use `update_todo`, or `read_file` on `{v_todo}` when you need to inspect it.
  - Extra `key_context` system message: when non-empty, the server injects the rendered full `key_context.md` body; legacy sessions may strip an embedded `## Todo 计划` section."""
        if is_v2:
            session_lines = f"""
- **Session storage directory**: {sdir}
  - Runtime V2 canonical path from `WORK_DIR`: `{v_session}`.
  - Canonical facts and rebuildable state live in `events.jsonl`, `snapshots/latest.json`, metadata, indexes, and referenced blobs. Legacy `llm_history.json`, `ui_events.json`, `key_context.md`, and `todo_plan.md` may be absent or stale and must not be used as context authority.
  - The server injects the active model context and summary. Use `context_manage` for explicit compact/summary edits and `update_todo` for the live plan; do not directly edit Runtime V2 storage files.
  - Use the conversation history APIs/UI when older visible history is needed."""
    else:
        session_lines = "\n- **Session storage directory**: not set for this run."

    run_shell_executor_hint = describe_run_shell_executor_for_prompt()
    current_year_month = datetime.now().strftime("%Y-%m")

    text = f"""
## Environment
- **Calendar month (host local time)**: **{current_year_month}**
- **OS**: {platform.system()} | **Python**: {platform.python_version()}
{run_shell_executor_hint}
- **MCP extensions** (optional): With `mcp_servers.json` at the project root (or env `MCP_SERVERS_JSON`), or settings saved via **Advanced settings → MCP configuration**, each exact server configuration requires one human registration confirmation before it connects and exposes tools as `mcp_<server_alias>_<tool_name>`. Tool calls then follow the current global permission mode and central `allow/ask/deny` policy.
- **Agent project root** (`AGENT_PROJECT_ROOT`): {proj}
  - This is the agent application's own source tree and project-level config root, including files such as `app/agent_loop.py`, `app/agent_tools.py`, `app/agent_harness.py`, `app/agent_tokenizer.py`, `app/prompt.md`, and `mcp_servers.json`.
  - When the user asks about "your" features, mechanisms, configuration, tool behavior, prompt behavior, self-checks, or asks you to inspect/check yourself, first use this root to read the relevant code and infer the agent's actual behavior before answering.
- **Work root** (`WORK_DIR`): {wdir}
  - Virtual `/` maps to this directory. Relative paths and virtual paths like `/outputs/a.txt` resolve under `WORK_DIR`.
  - `write_file`, `web_download`, `delete_file` (soft-delete target: `WORK_DIR/.trash/`), and restricted `run_shell` write or run inside this tree unless the UI approves broader access.
  - `delete_file` refuses protected tool state under `sessions/`, `skills/`, `.trash/`, and their children.

## This conversation's storage{session_lines}
    """.strip()
    return text


def build_static_system_segments(
    skills_catalog: str,
    env_static: str,
    language: str = "zh-CN",
) -> List[str]:
    """
    静态 system 分段上送（不含 key_context、不含对话轮）。
    顺序兼顾可读性与前缀缓存：角色原则 → 工具清单 → 调用策略 → 技能目录 → 环境。
    """
    from agent_harness import load_prompt_template

    normalized_language = str(language or "zh-CN").strip().lower()
    is_english = normalized_language in {"en", "en-us", "en-gb", "english"}
    def load_for_language(name: str) -> str:
        return (
            load_prompt_template(name, "en")
            if is_english
            else load_prompt_template(name)
        )

    identity = load_for_language("system_identity").strip()
    contract = load_for_language("system_tool_contract").strip()
    skills_tpl = load_for_language("system_skills_intro").strip()
    skills_block = skills_tpl.format(skills_catalog=skills_catalog)
    identity_heading = "## Role and response principles" if is_english else "## 角色与回答原则"
    contract_heading = "## Tool-calling policy" if is_english else "## 工具调用策略"
    skills_heading = "## Skills catalog" if is_english else "## 技能目录"
    parts = [
        identity_heading + "\n\n" + identity,
        contract_heading + "\n\n" + contract,
        skills_heading + "\n\n" + skills_block,
        env_static.strip(),
    ]
    return [p for p in parts if p.strip()]


def estimate_full_input_tokens_for_llm_history(
    session_id: str,
    llm_history: List[Any],
    key_context: str,
    language: str = "zh-CN",
) -> int:
    """
    与 react_node 发往主模型前、`compute_context_tokens_for_session`（右上角）一致的整包 token：
    静态 system 多段 + key_context 注入 + 多轮 turn（含 tool 占位补齐），reasoning 剥除口径相同。
    """
    from agent_harness import (
        estimate_tokens,
        key_context_body_for_system_prompt,
        strip_reasoning_for_api_request,
    )
    from agent_tools import get_skills_catalog

    sid = str(session_id or "").strip()
    cache_key = (*_full_input_token_cache_key(sid, llm_history, key_context or ""), str(language or "zh-CN"))
    now = time.monotonic()
    with _FULL_INPUT_TOKEN_CACHE_LOCK:
        cached = _FULL_INPUT_TOKEN_CACHE.get(cache_key)
        if cached and now - cached[0] <= _FULL_INPUT_TOKEN_CACHE_TTL_SEC:
            return int(cached[1])
    skills_catalog = get_skills_catalog()
    env_static = build_env_static(sid if sid else None)
    kc_body = key_context_body_for_system_prompt(key_context or "")
    static_segments = build_static_system_segments(skills_catalog, env_static, language)
    turn_msgs = inject_missing_tool_messages(messages_for_openai_turns(llm_history))
    llm_messages: List[Any] = [SystemMessage(content=s) for s in static_segments]
    if kc_body:
        llm_messages.append(SystemMessage(content=kc_body))
    llm_messages.extend(turn_msgs)
    _for_est = strip_reasoning_for_api_request(llm_messages)
    estimated = int(estimate_tokens(_for_est))
    with _FULL_INPUT_TOKEN_CACHE_LOCK:
        if len(_FULL_INPUT_TOKEN_CACHE) >= _FULL_INPUT_TOKEN_CACHE_MAX:
            oldest = min(_FULL_INPUT_TOKEN_CACHE.items(), key=lambda item: item[1][0])[0]
            _FULL_INPUT_TOKEN_CACHE.pop(oldest, None)
        _FULL_INPUT_TOKEN_CACHE[cache_key] = (now, estimated)
    return estimated


def estimate_hybrid_input_tokens_for_llm_history(
    session_id: str,
    llm_history: List[Any],
    key_context: str,
    language: str = "zh-CN",
) -> Tuple[int, str]:
    """Estimate a persisted session using the same provider-calibrated path as a live request."""
    from agent_harness import key_context_body_for_system_prompt
    from agent_tools import get_skills_catalog

    sid = str(session_id or "").strip()
    skills_catalog = get_skills_catalog()
    env_static = build_env_static(sid if sid else None)
    kc_body = key_context_body_for_system_prompt(key_context or "")
    static_segments = build_static_system_segments(skills_catalog, env_static, language)
    turn_msgs = inject_missing_tool_messages(messages_for_openai_turns(llm_history))
    llm_messages: List[Any] = [SystemMessage(content=s) for s in static_segments]
    if kc_body:
        llm_messages.append(SystemMessage(content=kc_body))
    llm_messages.extend(turn_msgs)
    estimated, source = estimate_full_input_tokens_for_messages(
        sid,
        llm_messages,
        return_source=True,
    )
    return int(estimated), str(source)
