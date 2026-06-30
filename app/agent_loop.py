"""
agent_loop — ReAct 主循环与 SSE 事件源。

流程（单轮用户消息）
------------------
1. `astream_events` 构建 state，顺序执行 `react_node` → `validate_final` → `finish`。
2. `react_node`：在 token 阈值内循环调用 `chat.completions`（带 tools），解析正文/思考/ tool_calls；
   按策略执行工具，结果写回 `llm_history`；通过 `emit` 将 `llm_reasoning`（先）/ `llm_response` / `tool_call` 等推入队列。
3. `validate_final`：验证事件（PASS）；`finish`：落盘、生成 `final` 事件。
"""

import json
import os
import queue
import re
import time
import asyncio
import uuid
import threading
from datetime import datetime
import inspect
from typing import TypedDict, List, Dict, Any, AsyncGenerator, Callable, Optional

from agent_harness import (
    executor_client,
    executor_model,
    EXECUTOR_TEMPERATURE,
    EXECUTOR_EXTRA_BODY,
    MAX_OUTPUT_TOKENS,
    executor_text_and_usage,
    load_prompt_template,
    session_manager,
    logger,
    MAX_REACT_ITER,
    SUBAGENT_MAX_REACT_ITER,
    _serialize_message,
    _message_to_dict,
    _dict_to_message,
    setup_logging,
    executor_http_client,
    key_context_body_for_system_prompt,
    todo_manager,
    CONTEXT_WINDOW,
    CONTEXT_EMERGENCY_SHRINK_MAX_RETRIES,
    REPEAT_DETECTION_THRESHOLD_SUMMARY,
    REPEAT_DETECTION_THRESHOLD_ERROR,
    COLOR_WHITE,
    COLOR_BLUE,
    COLOR_YELLOW,
    COLOR_RESET,
    apply_final_dedup_to_messages,
    derive_dialogue_from_assistant_history,
    LOG_TRUNCATE_KEEP_CHARS,
    LLM_CONTEXT_TRUNCATE_KEEP_CHARS,
    truncate_head_tail,
    truncate_tool_result_for_llm,
    MAX_PARALLEL_TOOLS,
    strip_reasoning_for_api_request,
    resolve_executor_config_for_session,
    EXECUTOR_REASONING_EFFORT,
    UserMessage,
    AssistantMessage,
    SystemMessage,
    ToolMessage,
    COMPACT_TRUNCATED_BOUNDARY_SYSTEM_EXACT,
)
from agent_memory import (
    auto_length_strategy_status_line,
    compress_tail_fallback,
    context_will_attempt_compress,
    run_context_policy,
    run_edit_key_context_instruction,
)
from agent_openai import (
    chat_completion,
    extract_usage_dict,
    parse_assistant_message,
    run_chat_completion_stream_worker,
)
from agent_reasoning import build_assistant_additional_kwargs
from agent_tools import (
    tools,
    get_skills_catalog,
    OPENAI_TOOL_DEFINITIONS,
    _compose_shell_command,
    AGENT_DEFAULT_WRITE_FILENAME,
    delete_file,
    safe_work_path,
    set_run_shell_interrupt_check,
    clear_run_shell_interrupt_check,
    redact_sensitive_tool_obj,
    redact_sensitive_tool_text,
)
from agent_tokenizer import (
    estimate_full_input_tokens_for_messages,
    estimate_full_input_tokens_for_llm_history,
    record_prompt_tokens_for_messages,
    inject_missing_tool_messages,
    messages_for_openai_turns,
    build_env_static,
    build_static_system_segments,
)
import agent_mcp
from agent_subagent_events import should_persist_ui_event
from session_event_bus import close_session_stream, prune_session_ephemeral, publish_session_event
from tool_approval_gate import new_approval_id, wait_tool_ui_approval_after_emit

EXECUTOR_STREAM = os.getenv("EXECUTOR_STREAM", "true").lower() in ("1", "true", "yes")

_STEER_LOCK = threading.Lock()
_STEER_QUEUES: Dict[str, List[Dict[str, Any]]] = {}
_STEER_RUN_LOCK = threading.Lock()
_ACTIVE_STEER_RUNS: Dict[str, Any] = {}
_CONTEXT_POLICY_LOCKS_LOCK = threading.Lock()
_CONTEXT_POLICY_LOCKS: Dict[str, threading.Lock] = {}


class _SteerRestartRequested(Exception):
    """Raised inside the active ReAct run when a user steer should restart the turn."""


class _SteerRunControl:
    def __init__(self, session_id: str, run_id: str):
        self.session_id = str(session_id or "").strip()
        self.run_id = str(run_id or "").strip()
        self.abort_event = threading.Event()
        self.reason = ""
        self.created_at = time.time()

    def abort(self, reason: str = "steer") -> None:
        self.reason = str(reason or "steer")
        self.abort_event.set()

    def reset(self) -> None:
        self.reason = ""
        self.abort_event.clear()

    def is_aborted(self) -> bool:
        return self.abort_event.is_set()


def _register_steer_run_control(session_id: str, run_id: str) -> _SteerRunControl:
    control = _SteerRunControl(session_id, run_id)
    sid = control.session_id
    if sid:
        with _STEER_RUN_LOCK:
            _ACTIVE_STEER_RUNS[sid] = control
    return control


def _clear_steer_run_control(session_id: str, control: _SteerRunControl) -> None:
    sid = str(session_id or "").strip()
    if not sid:
        return
    with _STEER_RUN_LOCK:
        if _ACTIVE_STEER_RUNS.get(sid) is control:
            _ACTIVE_STEER_RUNS.pop(sid, None)


def abort_session_steer_run(session_id: str, reason: str = "steer") -> bool:
    sid = str(session_id or "").strip()
    if not sid:
        return False
    with _STEER_RUN_LOCK:
        control = _ACTIVE_STEER_RUNS.get(sid)
    if not control:
        return False
    try:
        control.abort(reason)
        return True
    except Exception:
        logger.debug("abort steer run failed: session_id=%s", sid, exc_info=True)
        return False


def _context_policy_lock_for_session(session_id: str) -> threading.Lock:
    sid = str(session_id or "").strip()
    with _CONTEXT_POLICY_LOCKS_LOCK:
        lock = _CONTEXT_POLICY_LOCKS.get(sid)
        if lock is None:
            lock = threading.Lock()
            _CONTEXT_POLICY_LOCKS[sid] = lock
        return lock


def _run_context_policy_serialized(
    llm_history: List,
    key_context: str,
    session_id: str,
    *,
    force_user_compact: bool,
    hint_sink: Optional[Callable[[Any], None]] = None,
):
    lock = _context_policy_lock_for_session(session_id)
    with lock:
        return run_context_policy(
            llm_history,
            key_context,
            session_id,
            force_user_compact=force_user_compact,
            hint_sink=hint_sink,
        )


def _wait_context_policy_idle(session_id: str) -> None:
    lock = _context_policy_lock_for_session(session_id)
    lock.acquire()
    lock.release()


def enqueue_session_steer(session_id: str, content: str, client_id: str = "") -> Dict[str, Any]:
    sid = str(session_id or "").strip()
    text = str(content or "").strip()
    if not sid:
        return {"ok": False, "error": "missing session_id"}
    if not text:
        return {"ok": False, "error": "empty message"}
    item = {
        "id": str(uuid.uuid4()),
        "content": text,
        "client_id": str(client_id or "").strip(),
        "created_at": time.time(),
    }
    with _STEER_LOCK:
        q = _STEER_QUEUES.setdefault(sid, [])
        q.append(item)
        depth = len(q)
    return {"ok": True, "item": item, "queued": depth}


def remove_session_steer(session_id: str, steer_id: str = "", client_id: str = "") -> Dict[str, Any]:
    sid = str(session_id or "").strip()
    target_id = str(steer_id or "").strip()
    target_client = str(client_id or "").strip()
    if not sid:
        return {"ok": False, "error": "missing session_id"}
    if not target_id and not target_client:
        return {"ok": False, "error": "missing steer id"}
    with _STEER_LOCK:
        q = list(_STEER_QUEUES.get(sid) or [])
        keep: List[Dict[str, Any]] = []
        removed: Optional[Dict[str, Any]] = None
        for item in q:
            same_id = target_id and str(item.get("id") or "") == target_id
            same_client = target_client and str(item.get("client_id") or "") == target_client
            if removed is None and (same_id or same_client):
                removed = item
                continue
            keep.append(item)
        if removed is None:
            return {"ok": False, "error": "steer not pending"}
        if keep:
            _STEER_QUEUES[sid] = keep
        else:
            _STEER_QUEUES.pop(sid, None)
    return {"ok": True, "item": removed, "queued": len(keep)}


def _pop_session_steers(session_id: str) -> List[Dict[str, Any]]:
    sid = str(session_id or "").strip()
    if not sid:
        return []
    with _STEER_LOCK:
        items = list(_STEER_QUEUES.get(sid) or [])
        _STEER_QUEUES.pop(sid, None)
    return items


def _has_session_steers(session_id: str) -> bool:
    sid = str(session_id or "").strip()
    if not sid:
        return False
    with _STEER_LOCK:
        return bool(_STEER_QUEUES.get(sid))


def _is_followup_interrupt(session_id: str) -> bool:
    try:
        return session_manager.get_interrupt_reason(session_id) == "followup"
    except Exception:
        return False

# ---------------------------------------------------------------------------
# 压缩兜底（agent_memory：compress_tail_fallback）
# ---------------------------------------------------------------------------


def _compress_history_fallback_kind(nl: Optional[List[Any]]) -> str:
    """非空表示走了截尾兜底：llm 首条为 COMPACT_TRUNCATED_BOUNDARY 或旧版中文截尾通知。"""
    if not nl:
        return ""
    m0 = nl[0]
    if not isinstance(m0, SystemMessage):
        return ""
    c = str(m0.content or "").strip()
    if c == COMPACT_TRUNCATED_BOUNDARY_SYSTEM_EXACT.strip():
        return "truncated"
    if any(
        s in c
        for s in (
            "上下文摘要异常",
            "上下文压缩异常",
            "已达最大轮次",
            "Conversation truncated",
        )
    ):
        return "truncated"
    return ""

# ---------------------------------------------------------------------------
# 工具调用：OpenAI 返回的是参数字典，必须 **kwargs 传入 Python 函数
# ---------------------------------------------------------------------------


def _filter_kwargs_for_callable(func: Callable[..., Any], kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """只传入可调用对象签名中接受的形参，避免模型多传键导致 TypeError。若带 **kwargs 则原样传递。"""
    if not isinstance(kwargs, dict):
        return {}
    try:
        sig = inspect.signature(func)
        if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
            return dict(kwargs)
        accept = {
            p.name
            for p in sig.parameters.values()
            if p.kind
            in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
        }
        return {k: v for k, v in kwargs.items() if k in accept}
    except (TypeError, ValueError):
        return dict(kwargs)


# ============================================================
# 定时器：检测 reasoning/content 停止后发送"正在思考中..."
# ============================================================
async def _thinking_timer(emit, state, delay=8):
    """等待 delay 秒后，发送'正在思考中...'状态"""
    await asyncio.sleep(delay)
    if emit:
        await _push_stream_event(state, {"type": "status", "content": "正在思考中...", "ephemeral": True}, emit=emit)
        await asyncio.sleep(0)


async def _invoke_plain_tool(tool_func: Callable[..., Any], tool_args: Any) -> Any:
    """
    使用 OpenAI 返回的参数字典调用纯 Python 工具。
    必须 ** 解包，不能用 func(tool_args) 把整包 dict 当作第一个位置参数（否则会引发各类 'dict' has no attribute ...）。
    """
    if not isinstance(tool_args, dict):
        tool_args = {}
    ka = _filter_kwargs_for_callable(tool_func, tool_args)
    if inspect.iscoroutinefunction(tool_func):
        return await tool_func(**ka)
    return await asyncio.to_thread(lambda: tool_func(**ka))


# ---------------------------------------------------------------------------
# 图状态：llm_history 为唯一完整多轮；运行中 dialogue 由 llm derive（与模型侧主链一致）；dialogue_history.json 落盘来自 ui_events（完整用户可见主链）。
# ---------------------------------------------------------------------------
class State(TypedDict):
    dialogue: List                                    # 由 llm_history 派生的主对话（用户 + 对用户的最终助手）
    work_messages: List                               # 原始工作消息（全量，与前端/落盘 work_messages 一致）
    llm_history: List                                 # LLM 上下文历史（可压缩，已持久化）
    user_input: str                                  # 当前用户输入
    final_response: str                               # 最终响应
    stream_events: List[Dict[str, Any]]               # 流式事件队列
    final_printed: bool                               # 是否已输出最终结果
    session_id: str                                   # 会话 ID
    llm_calls: List[Dict[str, Any]]                   # 记录所有 LLM 调用
    key_context: str                                 # 持久化关键信息块（与 key_context.md 同步）
    # 重复检测状态（持久化）
    repeat_count: int                                 # 连续重复次数
    last_response_content: str                        # 上一次响应内容
    last_tool_calls_signature: str                    # 上一次工具调用签名
    reminder_inserted: bool                           # 是否已插入提醒


def _truncate_xml_content_blocks(xml_text: str, keep_chars: int) -> str:
    """
    仅截断 XML 文本内每个 <content>...</content> 块的内容，
    不对整段 XML 做整体截断。
    """
    if not isinstance(xml_text, str):
        xml_text = str(xml_text)

    pattern = re.compile(r"(<content>)(.*?)(</content>)", re.DOTALL)

    def _repl(match: re.Match) -> str:
        start_tag, inner_text, end_tag = match.groups()
        return f"{start_tag}{truncate_head_tail(inner_text, keep_chars)}{end_tag}"

    return pattern.sub(_repl, xml_text)


tools_dict = {k: v for k, v in tools.items()}

# 只读工具允许并发；存在副作用的工具默认串行执行。
# activate_skill 仅读取 SKILL.md/目录列表，不修改工作区，可并行。
READ_ONLY_TOOLS = {"read_file", "ls", "list_dir", "glob", "grep", "web_search", "web_fetch", "activate_skill"}
READ_ONLY_TOOL_VIRTUAL_LINE_CHARS = 1000


def _wrap_read_only_tool_output_lines(text: Any, max_chars: int = READ_ONLY_TOOL_VIRTUAL_LINE_CHARS) -> str:
    raw = redact_sensitive_tool_text(text)
    limit = max(1, int(max_chars or READ_ONLY_TOOL_VIRTUAL_LINE_CHARS))
    out: List[str] = []
    for line in raw.splitlines(keepends=True):
        newline = ""
        if line.endswith("\r\n"):
            body = line[:-2]
            newline = "\r\n"
        elif line.endswith("\n") or line.endswith("\r"):
            body = line[:-1]
            newline = line[-1]
        else:
            body = line
        if body == "":
            out.append(line)
            continue
        for i in range(0, len(body), limit):
            chunk = body[i : i + limit]
            if i + limit < len(body):
                chunk += "\n"
            else:
                chunk += newline
            out.append(chunk)
    return "".join(out) if out else raw


def compute_context_tokens_for_session(session_id: str) -> Dict[str, Any]:
    """
    与 react_node 中发往模型前的整包输入 token 估算一致；不依赖前端缓存。

    不含仅在循环中途临时插入的系统条目不包含在内（与稳定快照相比误差通常很小）。
    """
    sid = str(session_id or "").strip()
    if not sid:
        return {"ok": False, "error": "invalid session_id"}
    if _runtime_v2_is_primary():
        llm_history_dicts = _load_runtime_v2_model_history_dicts(sid)
        key_context = _load_runtime_v2_context_summary(sid)
    else:
        try:
            _sid, _dialogue, _wm, llm_history_dicts, key_context, _md = session_manager.get_or_create_session(sid)
        except Exception as e:
            return {"ok": False, "error": str(e)}

    llm_history = [_dict_to_message(m) for m in llm_history_dicts]
    full_input_est = estimate_full_input_tokens_for_llm_history(
        sid,
        llm_history,
        key_context or "",
    )
    _client, active_model, _max_out, active_context_window = resolve_executor_config_for_session(
        sid
    )
    return {
        "ok": True,
        "estimated": int(full_input_est),
        "threshold": int(active_context_window),
        "model": active_model,
        "source": "runtime_v2_projection" if _runtime_v2_is_primary() else "legacy_history",
    }

# ==================== 辅助函数：实时持久化 ====================
def _persist_session_messages(state: State) -> None:
    """work / llm / key_context 落盘；dialogue 由 llm 派生，dialogue_history 由 ui_events 派生。"""
    state["dialogue"] = derive_dialogue_from_assistant_history(state["llm_history"])
    if _runtime_v2_is_primary():
        sid = state["session_id"]
        if hasattr(session_manager, "_save_key_context"):
            session_manager._save_key_context(sid, state.get("key_context", ""))
        if hasattr(session_manager, "_save_dialogue_history"):
            session_manager._save_dialogue_history(
                sid,
                session_manager.dialogue_dicts_from_ui_events_file(sid),
            )
        return
    _materialize_lazy_work_messages(state)
    session_manager.update_session(
        state["session_id"],
        [_message_to_dict(m) for m in state["work_messages"]],
        [_message_to_dict(m) for m in state["llm_history"]],
        state.get("key_context", ""),
        dialogue_history=session_manager.dialogue_dicts_from_ui_events_file(state["session_id"]),
    )


def _persist_state(state: State):
    """实时保存当前会话的所有状态到磁盘。"""
    try:
        _persist_session_messages(state)
    except Exception as e:
        logger.warning(f"实时持久化失败: {e}")


def _assistant_tool_call_ids(msg: Any) -> List[str]:
    if not isinstance(msg, AssistantMessage):
        return []
    tool_calls = getattr(msg, "tool_calls", None)
    if not isinstance(tool_calls, list) or not tool_calls:
        return []
    ids: List[str] = []
    for idx, tc in enumerate(tool_calls):
        if isinstance(tc, dict):
            raw = tc.get("id") or tc.get("tool_call_id") or ""
        else:
            raw = getattr(tc, "id", "") or getattr(tc, "tool_call_id", "") or ""
        tid = str(raw or "").strip()
        ids.append(tid or f"__missing_tool_call_id_{idx}")
    return ids


def _first_unclosed_tool_call_index(messages: List[Any]) -> Optional[int]:
    i = 0
    n = len(messages)
    while i < n:
        ids = _assistant_tool_call_ids(messages[i])
        if not ids:
            i += 1
            continue
        required = set(ids)
        seen: List[str] = []
        j = i + 1
        while j < n and isinstance(messages[j], ToolMessage):
            seen.append(str(getattr(messages[j], "tool_call_id", "") or "").strip())
            j += 1
        if len(seen) < len(ids) or not required.issubset(set(seen)):
            return i
        i = j
    return None


def _truncate_unclosed_tool_call_tail(messages: List[Any]) -> tuple[List[Any], Optional[int]]:
    idx = _first_unclosed_tool_call_index(list(messages or []))
    if idx is None:
        return list(messages or []), None
    return list(messages or [])[:idx], idx


def _sanitize_loaded_histories_for_new_run(
    session_id: str,
    work_messages: List[Any],
    llm_history: List[Any],
    key_context: str,
    reason: str,
) -> tuple[List[Any], List[Any]]:
    clean_llm, llm_cut = _truncate_unclosed_tool_call_tail(llm_history)
    clean_work, work_cut = _truncate_unclosed_tool_call_tail(work_messages)
    if llm_cut is None and work_cut is None:
        return work_messages, llm_history
    state: State = {
        "session_id": session_id,
        "work_messages": clean_work,
        "llm_history": clean_llm,
        "key_context": key_context or "",
        "dialogue": derive_dialogue_from_assistant_history(clean_llm),
    }
    logger.warning(
        "Sanitized unclosed tool_call tail before run: session=%s reason=%s llm_cut=%s work_cut=%s",
        session_id,
        reason,
        llm_cut,
        work_cut,
    )
    _persist_state_with_model_replace(state, clean_llm, reason)
    return clean_work, clean_llm


def _load_runtime_v2_model_history_dicts(session_id: str) -> List[Dict[str, Any]]:
    try:
        from runtime_v2 import RuntimeModelProjection

        return RuntimeModelProjection(session_manager.sessions_dir).read_message_dicts(session_id)
    except Exception as exc:
        logger.debug("Runtime V2 model projection read failed: %s", exc)
        return []


def _load_runtime_v2_context_summary(session_id: str) -> str:
    try:
        from runtime_v2 import SnapshotStore

        snapshot = SnapshotStore(session_manager.sessions_dir).read(session_id)
        context = snapshot.get("context") if isinstance(snapshot, dict) else {}
        summary = context.get("summary") if isinstance(context, dict) else {}
        if isinstance(summary, dict):
            return str(summary.get("summary") or "")
    except Exception as exc:
        logger.debug("Runtime V2 context summary read failed: %s", exc)
    return ""


def _load_key_context_for_run(session_id: str) -> str:
    if _runtime_v2_is_primary():
        return _load_runtime_v2_context_summary(session_id)
    key_context = session_manager._load_key_context(session_id)
    return session_manager.migrate_todo_plan_off_key_context(session_id, key_context)


def _load_model_history_dicts_v2_primary(session_id: str, *, reconcile_legacy: bool) -> List[Dict[str, Any]]:
    if _runtime_v2_is_primary():
        return _load_runtime_v2_model_history_dicts(session_id)
    if reconcile_legacy:
        session_manager.reconcile_llm_work_to_ui_user_count(session_id, include_work=False)
    return session_manager._load_llm_history(session_id)


def _load_work_history_dicts_for_run(session_id: str) -> List[Dict[str, Any]]:
    if _runtime_v2_is_primary():
        return []
    return session_manager._load_work_messages(session_id)


def _pre_api_timing_mark(timings: Dict[str, int], name: str, start: float) -> None:
    timings[name] = int(max(0.0, (time.perf_counter() - start) * 1000.0))


def _pre_api_timing_log(session_id: str, timings: Dict[str, int], **extra: Any) -> None:
    try:
        total = int(sum(int(v or 0) for v in timings.values()))
        parts = [f"{k}={int(v)}ms" for k, v in timings.items()]
        for k, v in extra.items():
            parts.append(f"{k}={v}")
        logger.info("pre_api_timing session=%s total=%sms %s", session_id, total, " ".join(parts))
    except Exception:
        logger.debug("pre_api_timing log failed", exc_info=True)


def _runtime_v2_append_model_message(state: State, msg: Any) -> None:
    sid = str(state.get("session_id") or "").strip()
    if not sid:
        return
    try:
        from runtime_v2 import RuntimeHistoryOps

        data = _message_to_dict(msg)
        msg_type = str(data.get("type") or "").strip()
        role = {
            "human": "user",
            "llm": "assistant",
            "ai": "assistant",
            "agent": "assistant",
        }.get(msg_type, msg_type)
        if role not in {"user", "assistant", "tool", "system"}:
            return
        payload = dict(data)
        content = str(payload.pop("content", "") or "")
        payload.pop("type", None)
        run_id = str(state.get("_runtime_v2_run_id") or "").strip()
        if run_id:
            payload["run_id"] = run_id
        RuntimeHistoryOps(session_manager.sessions_dir).append_model_message(
            sid,
            role,
            content,
            **payload,
        )
    except Exception as exc:
        logger.debug("Runtime V2 model append failed: %s", exc)


def _runtime_v2_replace_model_history(state: State, messages: List[Any], reason: str) -> None:
    sid = str(state.get("session_id") or "").strip()
    if not sid:
        return
    try:
        from runtime_v2 import RuntimeHistoryOps

        RuntimeHistoryOps(session_manager.sessions_dir).replace_model_history(
            sid,
            [_message_to_dict(m) for m in list(messages or [])],
            reason=reason,
        )
    except Exception as exc:
        logger.debug("Runtime V2 model replace failed: %s", exc)


def _runtime_v2_is_primary() -> bool:
    try:
        from runtime_v2 import runtime_v2_primary

        return runtime_v2_primary()
    except Exception:
        return True


def _persist_state_with_model_append(state: State, msg: Any) -> None:
    if _runtime_v2_is_primary():
        _runtime_v2_append_model_message(state, msg)
        _persist_state(state)
    else:
        _persist_state(state)
        _runtime_v2_append_model_message(state, msg)


def _persist_state_with_model_replace(state: State, messages: List[Any], reason: str) -> None:
    if _runtime_v2_is_primary():
        _runtime_v2_replace_model_history(state, messages, reason)
        _persist_state(state)
    else:
        _persist_state(state)
        _runtime_v2_replace_model_history(state, messages, reason)


def _persist_session_messages_with_model_replace(state: State, messages: List[Any], reason: str) -> None:
    if _runtime_v2_is_primary():
        _runtime_v2_replace_model_history(state, messages, reason)
        _persist_session_messages(state)
    else:
        _persist_session_messages(state)
        _runtime_v2_replace_model_history(state, messages, reason)


def _materialize_lazy_work_messages(state: State) -> None:
    if not state.pop("_lazy_prepend_work_messages", False):
        return
    sid = str(state.get("session_id") or "").strip()
    suffix = list(state.get("work_messages", []))
    if not sid:
        state["work_messages"] = suffix
        return
    try:
        prev = [_dict_to_message(m) for m in session_manager._load_work_messages(sid)]
    except Exception as e:
        logger.warning("lazy load work_messages failed: %s", e)
        prev = []
    if prev and suffix:
        try:
            p = prev[-1]
            s = suffix[0]
            if type(p) is type(s) and getattr(p, "content", None) == getattr(s, "content", None):
                suffix = suffix[1:]
        except Exception:
            pass
    state["work_messages"] = prev + suffix


async def _push_stream_event(
    state: State,
    event: Dict[str, Any],
    emit: Optional[Callable[[Dict[str, Any]], Any]] = None,
):
    """追加 stream_events；若提供 emit（async 可调用），则同步推给前端。"""
    state["stream_events"].append(event)
    if emit:
        try:
            r = emit(event)
            if inspect.isawaitable(r):
                await r
        except Exception:
            pass


def _set_model_switch_status_callback(
    client: Any,
    callback: Optional[Callable[[Dict[str, Any]], None]],
) -> None:
    setter = getattr(client, "set_status_callback", None)
    if not callable(setter):
        return
    try:
        setter(callback)
    except Exception:
        logger.debug("设置模型切换状态回调失败", exc_info=True)


def _should_suppress_model_switch_status(state: State, event: Dict[str, Any]) -> bool:
    if not isinstance(event, dict) or not event.get("model_switch"):
        return False
    if not event.get("network_error"):
        return False
    return int(state.get("_network_reconnect_attempts", 0) or 0) > 0


def _queue_get_with_timeout(q: queue.Queue, timeout: float):
    try:
        return q.get(timeout=timeout)
    except queue.Empty:
        return ("__timeout__", None)


def _discard_task_result(task: asyncio.Task) -> None:
    try:
        task.result()
    except asyncio.CancelledError:
        pass
    except Exception:
        logger.debug("background task finished after cancellation", exc_info=True)


async def _await_maybe(awaitable_or_value):
    if inspect.isawaitable(awaitable_or_value):
        return await awaitable_or_value
    return awaitable_or_value


async def _run_react_node_off_loop(
    state: State,
    emit: Optional[Callable[[Dict[str, Any]], Any]],
) -> State:
    if emit is None:
        return await asyncio.to_thread(lambda: asyncio.run(react_node(state, emit=None)))
    main_loop = asyncio.get_running_loop()

    async def bridged_emit(ev: Dict[str, Any]) -> None:
        fut = asyncio.run_coroutine_threadsafe(_await_maybe(emit(ev)), main_loop)
        await asyncio.wrap_future(fut)

    return await asyncio.to_thread(lambda: asyncio.run(react_node(state, emit=bridged_emit)))


def _steer_control_from_state(state: State) -> Optional[_SteerRunControl]:
    control = state.get("_steer_control") if isinstance(state, dict) else None
    if isinstance(control, _SteerRunControl):
        return control
    return None


def _steer_requested(state: State) -> bool:
    sid = str(state.get("session_id") or "").strip() if isinstance(state, dict) else ""
    control = _steer_control_from_state(state)
    return bool((control and control.is_aborted()) or _has_session_steers(sid))


def _reset_steer_control(state: State) -> None:
    control = _steer_control_from_state(state)
    if control:
        control.reset()
    if isinstance(state, dict):
        state.pop("_steer_abort_event_emitted", None)


async def _emit_steer_abort_event(
    state: State,
    emit: Optional[Callable[[Dict[str, Any]], Any]],
    stage: str,
) -> None:
    if not isinstance(state, dict):
        return
    if state.get("_steer_abort_event_emitted"):
        return
    state["_steer_abort_event_emitted"] = True
    event: Dict[str, Any] = {
        "type": "llm_stream_aborted",
        "reason": "user_steer",
        "stage": str(stage or "react"),
        "ephemeral": True,
    }
    react_iter = state.get("_current_react_iter")
    try:
        if react_iter is not None:
            event["react_iter"] = int(react_iter)
    except Exception:
        pass
    await _push_stream_event(
        state,
        event,
        emit=emit,
    )


async def _raise_if_steer_requested(
    state: State,
    emit: Optional[Callable[[Dict[str, Any]], Any]],
    stage: str,
) -> None:
    if not _steer_requested(state):
        return
    await _emit_steer_abort_event(state, emit, stage)
    raise _SteerRestartRequested()


async def _await_steerable(
    state: State,
    awaitable,
    emit: Optional[Callable[[Dict[str, Any]], Any]],
    stage: str,
    poll_sec: float = 0.05,
):
    try:
        await _raise_if_steer_requested(state, emit, stage)
    except _SteerRestartRequested:
        close_fn = getattr(awaitable, "close", None)
        if callable(close_fn):
            close_fn()
        raise
    task = asyncio.ensure_future(awaitable)
    try:
        while True:
            done, _ = await asyncio.wait({task}, timeout=poll_sec)
            if task in done:
                return task.result()
            await _raise_if_steer_requested(state, emit, stage)
    except _SteerRestartRequested:
        if not task.done():
            task.add_done_callback(_discard_task_result)
            task.cancel()
        raise


async def _await_retry_delay_or_interrupt(
    state: State,
    emit: Optional[Callable[[Dict[str, Any]], Any]],
    delay_sec: float,
) -> bool:
    """Return False when the current run should stop instead of retrying."""
    sid = str(state.get("session_id") or "").strip()
    deadline = time.monotonic() + max(0.0, float(delay_sec or 0.0))
    while time.monotonic() < deadline:
        await _raise_if_steer_requested(state, emit, "network_reconnect")
        if sid and session_manager.is_interrupt_requested(sid):
            return False
        await asyncio.sleep(min(0.25, max(0.0, deadline - time.monotonic())))
    return True


def _rollback_steer_partial_turn(state: State) -> None:
    marker = state.pop("_steer_rollback_marker", None) if isinstance(state, dict) else None
    if not isinstance(marker, dict):
        return
    try:
        llm_len = int(marker.get("llm_len"))
        work_len = int(marker.get("work_len"))
    except Exception:
        return
    llm_history = list(state.get("llm_history", []))
    work_messages = list(state.get("work_messages", []))
    if llm_len < 0 or work_len < 0:
        return
    if len(llm_history) >= llm_len:
        llm_history = llm_history[:llm_len]
    if len(work_messages) >= work_len:
        work_messages = work_messages[:work_len]
    state["llm_history"] = llm_history
    state["work_messages"] = work_messages
    state["dialogue"] = derive_dialogue_from_assistant_history(llm_history)
    _persist_state_with_model_replace(state, llm_history, "steer_restart_rollback")


async def _restart_react_after_steer(
    state: State,
    emit: Optional[Callable[[Dict[str, Any]], Any]],
) -> State:
    _rollback_steer_partial_turn(state)
    consumed = await _consume_steer_messages(state, emit=emit)
    _reset_steer_control(state)
    if consumed:
        state["final_result_retries"] = 0
        state["empty_final_retries"] = 0
        state["repeat_count"] = 0
        state["last_response_content"] = None
        state["last_tool_calls_signature"] = None
        state["reminder_inserted"] = False
    return await react_node(state, emit=emit)


async def _consume_steer_messages(
    state: State,
    emit: Optional[Callable[[Dict[str, Any]], Any]] = None,
) -> bool:
    sid = str(state.get("session_id") or "").strip()
    items = _pop_session_steers(sid)
    if not items:
        return False
    work_messages = list(state.get("work_messages", []))
    llm_history = list(state.get("llm_history", []))
    changed = False
    for item in items:
        text = str((item or {}).get("content") or "").strip()
        if not text:
            continue
        msg = UserMessage(content=text)
        work_messages.append(msg)
        llm_history.append(msg)
        state["user_input"] = text
        state["dialogue"] = derive_dialogue_from_assistant_history(llm_history)
        state["work_messages"] = work_messages
        state["llm_history"] = llm_history
        _persist_state_with_model_append(state, msg)
        await _push_stream_event(
            state,
            {
                "type": "user_steer",
                "content": text,
                "steer": True,
                "steer_id": str((item or {}).get("id") or ""),
                "client_id": str((item or {}).get("client_id") or ""),
            },
            emit=emit,
        )
        changed = True
    return changed


def _progress_hint_to_stream_event(item: Any) -> Dict[str, Any]:
    """将 agent_memory 进度回调转为 SSE 事件（裁剪 / 压缩摘要 / 要点分轨）。"""
    if isinstance(item, dict) and item.get("type"):
        return item
    if isinstance(item, str):
        item = {"content": item, "progress_kind": "trim"}
    kind = str((item or {}).get("progress_kind") or "trim")
    if item.get("persist_body") is not None:
        body_map = {
            "trim": "context_trim_body",
            "summary": "context_summary_body",
            "key": "key_context_body",
        }
        return {
            "type": body_map.get(kind, "context_summary_body"),
            "content": str(item.get("persist_body") or ""),
        }
    if item.get("stream_delta") is not None:
        delta_map = {
            "trim": "context_trim_delta",
            "summary": "context_summary_delta",
            "key": "key_context_delta",
        }
        return {
            "type": delta_map.get(kind, "context_summary_delta"),
            "delta": str(item.get("stream_delta") or ""),
            "ephemeral": True,
        }
    type_map = {
        "trim": "context_trim_progress",
        "summary": "context_summary_progress",
        "key": "key_context_progress",
    }
    return {
        "type": type_map.get(kind, "context_trim_progress"),
        "content": str((item or {}).get("content") or ""),
    }


async def _await_thread_with_sse_keepalive(
    factory,
    state: State,
    emit: Optional[Callable[[Dict[str, Any]], Any]],
    interval_sec: float = 12.0,
    *,
    thread_hint_queue: Optional[queue.Queue] = None,
):
    """
    在线程中运行无参 factory()；等待期间周期性推送 ephemeral keepalive，
    避免上下文压缩等长时间同步调用期间 SSE 无字节，被反向代理/浏览器判定掉线。
    若提供 thread_hint_queue，则在等待循环中即时 drain 并推送 status（压缩阶段进度）。
    """
    loop = asyncio.get_running_loop()
    task = asyncio.create_task(asyncio.to_thread(factory))
    last_keep = loop.time()
    try:
        while True:
            done, _ = await asyncio.wait({task}, timeout=0.05)
            await _raise_if_steer_requested(state, emit, "thread_wait")
            if thread_hint_queue is not None and emit:
                while True:
                    try:
                        item = thread_hint_queue.get_nowait()
                    except queue.Empty:
                        break
                    ev = _progress_hint_to_stream_event(item)
                    await _push_stream_event(state, ev, emit=emit)
                    await asyncio.sleep(0)
            if task in done:
                if thread_hint_queue is not None and emit:
                    while True:
                        try:
                            item = thread_hint_queue.get_nowait()
                        except queue.Empty:
                            break
                        ev = _progress_hint_to_stream_event(item)
                        await _push_stream_event(state, ev, emit=emit)
                        await asyncio.sleep(0)
                return task.result()
            now = loop.time()
            if emit and now - last_keep >= interval_sec:
                await _push_stream_event(
                    state,
                    {"type": "sse_keepalive", "ephemeral": True},
                    emit=emit,
                )
                last_keep = now
    finally:
        if not task.done():
            task.add_done_callback(_discard_task_result)
            task.cancel()


async def _await_context_policy_idle_for_session(
    state: State,
    emit: Optional[Callable[[Dict[str, Any]], Any]],
) -> None:
    sid = str(state.get("session_id") or "").strip()
    if not sid:
        return
    lock = _context_policy_lock_for_session(sid)
    if lock.acquire(blocking=False):
        lock.release()
        return
    await _push_stream_event(
        state,
        {
            "type": "status",
            "content": "检测到同会话仍有未结束的上下文压缩，等待其完成后再继续 ReAct。",
        },
        emit=emit,
    )
    await _await_thread_with_sse_keepalive(
        lambda: _wait_context_policy_idle(sid),
        state,
        emit,
        interval_sec=5.0,
    )


async def _emit_tool_pending_sse(
    emit: Optional[Callable],
    tool_name: str,
    tool_args: Any,
    tool_call_id: str,
    react_iter: int,
    tool_call_index: Optional[int] = None,
) -> None:
    """工具实际执行前推送占位（不落 ui_events），前端显示「xxx 工具执行中」。"""
    if not emit:
        return
    try:
        payload = {
            "type": "tool_pending",
            "ephemeral": True,
            "tool": redact_sensitive_tool_text(tool_name),
            "args": redact_sensitive_tool_obj(tool_args),
            "command_preview": _tool_command_preview(tool_name, tool_args),
            "tool_call_id": tool_call_id or "",
            "tool_call_index": tool_call_index,
            "react_iter": int(react_iter),
        }
        r = emit(payload)
        if inspect.isawaitable(r):
            await r
        await asyncio.sleep(0)
    except Exception:
        pass


async def _emit_tool_approval_required_sse(
    emit: Optional[Callable],
    session_id: str,
    approval_id: str,
    tool_name: str,
    title: str,
    message: str,
    subtitle: str = "",
) -> None:
    """浏览器须弹窗确认；ephemeral 不落盘。"""
    if not emit:
        return
    try:
        payload = {
            "type": "tool_approval_required",
            "ephemeral": True,
            "approval_id": approval_id,
            "session_id": session_id,
            "tool": redact_sensitive_tool_text(tool_name),
            "title": redact_sensitive_tool_text(title),
            "message": redact_sensitive_tool_text(message),
            "subtitle": redact_sensitive_tool_text(subtitle or ""),
        }
        r = emit(payload)
        if inspect.isawaitable(r):
            await r
        await asyncio.sleep(0)
    except Exception:
        pass


def _tool_ui_approval_enabled() -> bool:
    return os.getenv("TOOL_UI_APPROVAL", "1").strip().lower() not in ("0", "false", "no", "off")


def _run_shell_requires_ui_approval(tool_args: Any) -> bool:
    """仅当模型显式将 restrict_to_workspace 置为 false 时视为工作区外/放宽执行。"""
    return tool_args.get("restrict_to_workspace") is False


def _tool_ui_approval_spec(tool_name: str, tool_args: Any) -> Optional[Dict[str, str]]:
    if tool_name == "run_shell":
        if not _run_shell_requires_ui_approval(tool_args):
            return None
        cmd = _compose_shell_command(
            str(tool_args.get("command") or ""),
            tool_args.get("args"),
        )
        snippet = redact_sensitive_tool_text(truncate_head_tail((cmd or "").strip(), 400))
        if not snippet.strip():
            snippet = "（空命令）"
        return {
            "title": "确认放宽工作区的 Shell",
            "subtitle": "restrict_to_workspace=false：可能访问或影响工作区之外的路径。",
            "message": "将执行的大致命令如下，请确认是否允许：\n\n" + snippet,
            "brief": "run_shell（放宽工作区）：" + snippet[:160],
        }
    if tool_name == "web_download":
        url = redact_sensitive_tool_text(str(tool_args.get("url") or "").strip())
        fp = str(
            tool_args.get("path")
            or tool_args.get("target_directory")
            or tool_args.get("file_path")
            or ""
        ).strip()
        fp = redact_sensitive_tool_text(fp)
        return {
            "title": "确认网络下载",
            "subtitle": "将把远程文件写入工作区指定路径。",
            "message": "URL：\n" + url + "\n\n保存为（工作区内）：\n" + (fp or "（未指定）"),
            "brief": "web_download → " + url[:120],
        }
    return None


def _tool_command_preview(tool_name: str, tool_args: Any) -> str:
    def _j(v: Any) -> str:
        return json.dumps(v, ensure_ascii=False)

    def _fmt_pair(k: str, v: Any) -> str:
        if k in ("content", "contents") and isinstance(v, str) and len(v) > 240:
            v = f"<{len(v)} chars>"
        return f"{_j(k)}: {_j(v)}"

    def _ordered_pairs(args: Dict[str, Any]) -> List[str]:
        preferred = [
            "path", "target_directory", "file_path", "command", "args", "url",
            "start_line", "end_line", "pattern", "query", "search", "replace",
            "old_string", "new_string", "working_dir", "timeout", "temporary",
            "content", "contents",
        ]
        keys: List[str] = []
        for k in preferred:
            if k in args:
                keys.append(k)
        for k in sorted(args.keys()):
            if k not in keys:
                keys.append(k)
        return [_fmt_pair(k, args.get(k)) for k in keys]

    if tool_name == "run_shell":
        try:
            args = dict(tool_args or {})
            args["command"] = _compose_shell_command(
                str(args.get("command") or ""),
                args.get("args"),
            ).strip()
            args.pop("args", None)
            return redact_sensitive_tool_text(f"{tool_name}({', '.join(_ordered_pairs(args))})")
        except Exception:
            pass
    if isinstance(tool_args, dict):
        return redact_sensitive_tool_text(f"{tool_name}({', '.join(_ordered_pairs(tool_args))})")
    try:
        arg_text = _j(tool_args if tool_args is not None else {})
    except Exception:
        arg_text = str(tool_args)
    return redact_sensitive_tool_text(f"{tool_name}({arg_text})")


def _record_temporary_write_file(state: Dict[str, Any], tool_name: str, tool_args: Any, failed: bool) -> None:
    if failed or tool_name != "write_file" or not isinstance(tool_args, dict):
        return
    if not bool(tool_args.get("temporary")):
        return
    raw = (
        tool_args.get("path")
        or tool_args.get("target_directory")
        or tool_args.get("file_path")
        or ""
    )
    try:
        p = safe_work_path(str(raw)) if str(raw).strip() else safe_work_path(AGENT_DEFAULT_WRITE_FILENAME)
    except Exception as e:
        logger.warning("temporary write_file path cannot be registered: %s", e)
        return
    bucket = list(state.get("_temporary_write_files") or [])
    sp = str(p)
    if sp not in bucket:
        bucket.append(sp)
    state["_temporary_write_files"] = bucket


def _save_result_to_tempfile(
    result_str: str,
    tool_name: str,
    state: Dict[str, Any],
    preview_chars: int = 1500,
) -> str:
    """
    工具结果超过 LLM 上下文阈值时：
    1. 完整内容写入 .tool_results/tool_result_{ts}_{tool}.txt
    2. 注册到 _temporary_write_files 跟踪列表
    3. 返回替换后的 result_for_llm（预览 + 路径 + 提示）
    """
    try:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"tool_result_{ts}_{tool_name}.txt"
        temp_path = safe_work_path(f".tool_results/{filename}")
        temp_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path.write_text(result_str, encoding="utf-8")

        # 注册到临时文件跟踪列表，session 结束时自动清理
        bucket = list(state.get("_temporary_write_files") or [])
        sp = str(temp_path)
        if sp not in bucket:
            bucket.append(sp)
        state["_temporary_write_files"] = bucket

        # 用虚拟路径展示给模型（和 read_file 的输出格式一致）
        virtual_path = f"/.tool_results/{filename}"
        preview = result_str[:preview_chars]
        total_chars = len(result_str)

        if tool_name == "read_file":
            return (
                f"[系统提示：read_file 输出过大（{total_chars} chars），完整内容已保存到临时文件。\n"
                f"建议缩小行范围分段读取，如 read_file(path, start_line=X, end_line=Y)]\n"
                f"临时文件路径：{virtual_path}\n\n"
                f"预览（前 {preview_chars} 字符）：\n{preview}"
            )
        else:
            return (
                f"[系统提示：工具输出过大（{total_chars} chars），已保存到临时文件。\n"
                f"如需查看完整内容，请使用 read_file 读取该文件。]\n"
                f"文件路径：{virtual_path}\n\n"
                f"预览（前 {preview_chars} 字符）：\n{preview}"
            )
    except Exception as e:
        logger.warning("save_result_to_tempfile failed, falling back to head+tail: %s", e)
        return truncate_tool_result_for_llm(result_str, LLM_CONTEXT_TRUNCATE_KEEP_CHARS)


def _cleanup_temporary_write_files(state: Dict[str, Any]) -> List[str]:
    files = list(state.get("_temporary_write_files") or [])
    if not files:
        return []
    cleaned: List[str] = []
    remaining: List[str] = []
    for p in files:
        try:
            result = delete_file(path=p)
            if str(result).lower().startswith("error:") or str(result).lower().startswith("failed"):
                remaining.append(p)
                logger.warning("temporary write_file cleanup failed for %s: %s", p, result)
            else:
                cleaned.append(p)
        except Exception as e:
            remaining.append(p)
            logger.warning("temporary write_file cleanup exception for %s: %s", p, e)
    state["_temporary_write_files"] = remaining
    return cleaned


def _tool_result_user_denied_ui(tool_name: str, tool_args: Any, tool_id: str) -> Dict[str, Any]:
    result_str = "Error: User denied tool execution in UI (web confirmation)."
    result_for_log = truncate_head_tail(result_str, LOG_TRUNCATE_KEEP_CHARS)
    result_for_llm = truncate_tool_result_for_llm(result_str, LLM_CONTEXT_TRUNCATE_KEEP_CHARS)
    return {
        "type": "tool",
        "tool_name": redact_sensitive_tool_text(tool_name),
        "tool_args": redact_sensitive_tool_obj(tool_args),
        "tool_id": tool_id,
        "result": result_str,
        "tool_detail_log": result_for_log,
        "tool_detail_llm": result_for_llm,
        "tool_detail_ui": result_str,
        "result_for_log": result_for_log,
        "tool_failed": True,
    }


async def _emit_tool_call_sse(
    emit: Optional[Callable],
    res: Dict[str, Any],
    react_iter: int,
    state: Optional[Dict[str, Any]] = None,
) -> None:
    """
    将单个 tool 结果推入 SSE 队列。并行工具在各自完成时立即调用，不等到整批 gather 结束。
    调用方应在 res 上置 _sse_emitted = True 以免在后续统一处理里重复发。
    """
    if not emit or not isinstance(res, dict) or res.get("type") != "tool":
        return
    try:
        r = emit(
            {
                "type": "tool_call",
                "tool": redact_sensitive_tool_text(res["tool_name"]),
                "args": redact_sensitive_tool_obj(res["tool_args"]),
                "command_preview": _tool_command_preview(res["tool_name"], res["tool_args"]),
                "result": redact_sensitive_tool_text(res.get("result", "")),
                "tool_call_id": res.get("tool_id") or "",
                "tool_call_index": res.get("tool_call_index"),
                "react_iter": int(react_iter),
            }
        )
        if inspect.isawaitable(r):
            await r
        if state is not None:
            state["_react_ui_tool_count"] = int(state.get("_react_ui_tool_count", 0) or 0) + 1
            if emit:
                await _emit_live_metrics(state, emit)
        # 让事件循环把 chunk 刷到 ASGI/uvicorn，再跑后续工具
        await asyncio.sleep(0)
    except Exception:
        pass

async def _emit_live_metrics(state, emit):
    """Push live tool counts to frontend in real-time."""
    if not emit:
        return
    await _push_stream_event(
        state,
        {
            "type": "process_metrics",
            "tool_calls": int(state.get("_react_ui_tool_count", 0) or 0),
            "tool_failures": int(state.get("_react_ui_tool_fail_count", 0) or 0),
        },
        emit=emit,
    )


def _tool_result_indicates_failure(_tool_name: str, result: Any) -> bool:
    """
    工具未抛异常仍可能失败（与过程区可见的「错误输出」一致），例如：
    - run_shell：非零 Exit code、任意位置的 Error:（勿仅扫描前缀：stdout 很长时错误在末尾）
    - 各工具返回 JSON 含 \"error\" 字段
    """
    if result is None:
        return False
    if isinstance(result, dict):
        if result.get("error") is not None:
            return True
        if result.get("ok") is False:
            return True
    s = str(result).strip()
    if not s:
        return False
    # run_shell / 校验失败等多以 \"Error:\" 标明（可能在全文任意位置）
    if re.search(r"(?i)\berror\s*:", s):
        return True
    if "error executing command:" in s.lower():
        return True
    if "regex error:" in s.lower():
        return True
    if s.startswith("{") and '"error"' in s[:1200]:
        try:
            j = json.loads(s)
            if isinstance(j, dict) and j.get("error") is not None:
                return True
        except Exception:
            pass
    matches = list(re.finditer(r"(?mi)Exit code:\s*(-?\d+)", s))
    if matches:
        try:
            if int(matches[-1].group(1)) != 0:
                return True
        except ValueError:
            pass
    return False


# ==================== 节点函数 ====================
def _classify_api_error(exc: BaseException) -> dict:
    """将 LLM API 异常分类为结构化错误信息（错误码 + 中文描述 + 解决方案）。"""
    try:
        from openai import APIConnectionError, APITimeoutError, AuthenticationError, BadRequestError, InternalServerError, NotFoundError, PermissionDeniedError, RateLimitError, UnprocessableEntityError
    except ImportError:
        AuthenticationError = BadRequestError = InternalServerError = NotFoundError = PermissionDeniedError = RateLimitError = UnprocessableEntityError = type(None)

    msg = str(exc).lower()

    if isinstance(exc, (APIConnectionError, APITimeoutError)) or 'timeout' in msg or 'timed out' in msg or 'connection' in msg:
        return {"code": "NET", "title": "网络连接失败",
                "msg": "无法连接到 API 服务器。",
                "solution": "请检查网络连接、OPENAI_BASE_URL 是否正确、VPN/代理设置。",
                "retry": 0}
    if isinstance(exc, AuthenticationError):
        return {"code": "401", "title": "API 认证失败",
                "msg": "API Key 无效或已过期。",
                "solution": "请在 .env 中检查 OPENAI_API_KEY 是否正确。",
                "retry": 0}
    if isinstance(exc, PermissionDeniedError):
        return {"code": "403", "title": "访问被拒绝",
                "msg": "当前地区不支持或 API Key 被风控。",
                "solution": "请新建 API Key，或检查服务地区限制。",
                "retry": 0}
    if isinstance(exc, NotFoundError):
        return {"code": "404", "title": "模型或接口不可用",
                "msg": "请求的模型不支持当前能力（如图像输入）。",
                "solution": "请检查模型名称是否正确，或换一个支持该能力的模型。",
                "retry": 0}
    if isinstance(exc, RateLimitError) or ("rate" in msg and "limit" in msg):
        return {"code": "429", "title": "请求频率超限",
                "msg": "已重试 3 次，均因速率限制失败。",
                "solution": "请稍等片刻再试，或降低请求频率；Token Plan 用户可考虑升级套餐。",
                "retry": 3}
    if isinstance(exc, BadRequestError) or isinstance(exc, UnprocessableEntityError):
        return {"code": "400", "title": "请求参数错误",
                "msg": "请求体格式不符合 API 要求。",
                "solution": "请检查消息格式、必填字段、模型名称是否正确。",
                "retry": 0}
    if '421' in msg or 'content' in msg and ('moderation' in msg or 'flag' in msg or 'block' in msg):
        return {"code": "421", "title": "内容被拦截",
                "msg": "输入内容触发了安全审核。",
                "solution": "请避免敏感或违规内容，修改后重试。",
                "retry": 0}
    if isinstance(exc, InternalServerError) or "500" in msg or "502" in msg or "503" in msg:
        code = "502" if "502" in msg else ("503" if "503" in msg else "500")
        return {"code": code, "title": f"服务器错误（{code}）",
                "msg": "已重试 3 次，服务器仍返回错误。",
                "solution": "请稍后重试；若持续出现请联系 API 服务商。",
                "retry": 3}
    return {"code": "OTHER", "title": "LLM 调用异常",
            "msg": "发生未知错误。",
            "solution": "请先检查模型配置，或到 GitHub 提交 issue 反馈。",
            "retry": 0}


async def react_node(state: State, emit: Optional[Callable[[Dict[str, Any]], Any]] = None) -> State:
    """ReAct 循环执行，集成 todo、技能、压缩、重复检测，支持并行工具调用。"""
    # ========== 1. 初始化状态 ==========
    if "user_input" not in state:
        for msg in reversed(state["dialogue"]):
            if isinstance(msg, UserMessage):
                state["user_input"] = msg.content
                break
        else:
            state["user_input"] = ""
        logger.warning("user_input 缺失，已从对话记录中恢复")

    if not _runtime_v2_is_primary():
        _materialize_lazy_work_messages(state)
    work_messages = list(state["work_messages"])
    llm_history = list(state["llm_history"])

    # 添加循环开始标记（仅内部使用，不在前端实时打印）
    if not (llm_history and isinstance(llm_history[-1], SystemMessage) and llm_history[-1].content == "New Agent Loop Start"):
        start_msg = SystemMessage(content="New Agent Loop Start")
        llm_history.append(start_msg)
        state["llm_history"] = llm_history
        _persist_state_with_model_append(state, start_msg)


    # ========== 2. 循环变量初始化 ==========
    iter_count = 0
    tool_results = []
    final_content = ""
    llm_stream_seq = 0
    compress_attempts = 0
    final_result_retries = int(
        state.get("final_result_retries", state.get("empty_final_retries", 0)) or 0
    )
    final_result_retry_max = max(
        0,
        int(os.getenv("FINAL_RESULT_RETRY_MAX", os.getenv("FINAL_EMPTY_RETRY_MAX", "3"))),
    )

    # 重复检测状态
    repeat_count = state.get("repeat_count", 0)
    last_response_content = state.get("last_response_content", None)
    last_tool_calls_signature = state.get("last_tool_calls_signature", None)
    reminder_inserted = state.get("reminder_inserted", False)

    react_wall_start = time.monotonic()
    state["_react_ui_tool_count"] = 0
    state["_react_ui_tool_fail_count"] = 0

    session_meta = session_manager._load_metadata(state["session_id"]) or {}
    max_react_iter = MAX_REACT_ITER
    if isinstance(session_meta, dict) and session_meta.get("is_subagent"):
        max_react_iter = max(
            1,
            int(session_meta.get("subagent_max_iter") or SUBAGENT_MAX_REACT_ITER),
        )
    parent_session_id = str(
        state.get("_subagent_parent_session_id")
        or (session_meta.get("parent_session_id") if isinstance(session_meta, dict) else "")
        or ""
    ).strip()

    if not (isinstance(session_meta, dict) and session_meta.get("is_subagent")):
        pending_notes = session_manager.consume_pending_subagent_notifications(state["session_id"])
        if pending_notes:
            note = SystemMessage(
                content="[后台 Subagent 已完成]\n" + "\n".join(pending_notes)
            )
            llm_history.append(note)
            work_messages.append(note)
            state["llm_history"] = llm_history
            state["work_messages"] = work_messages
            _persist_state_with_model_append(state, note)

    try:
        while iter_count < max_react_iter:
            pre_api_timings: Dict[str, int] = dict(state.pop("_pre_run_timings", {}) or {})
            _t_pre_api = time.perf_counter()
            await _raise_if_steer_requested(state, emit, "react")
            if session_manager.is_interrupt_requested(state["session_id"]):
                if _is_followup_interrupt(state["session_id"]):
                    raise asyncio.CancelledError()
                final_content = "任务已由用户中断。"
                await _push_stream_event(state, {"type": "status", "content": "任务已由用户中断"}, emit=emit)
                break
            if parent_session_id and session_manager.is_interrupt_requested(parent_session_id):
                final_content = "任务已由用户中断（父会话）。"
                await _push_stream_event(
                    state,
                    {"type": "status", "content": "任务已由用户中断（父会话）"},
                    emit=emit,
                )
                break
            _pre_api_timing_mark(pre_api_timings, "early_interrupt_checks", _t_pre_api)
            _t_pre_api = time.perf_counter()
            await _await_context_policy_idle_for_session(state, emit)
            _pre_api_timing_mark(pre_api_timings, "context_policy_wait_prebuild", _t_pre_api)
            _t_pre_api = time.perf_counter()
            await _raise_if_steer_requested(state, emit, "react")
            iter_count += 1
            state["_current_react_iter"] = int(iter_count)

            # ---------- 2.2 构建 LLM 输入（静态 system 多段 + key_context，优化前缀缓存与维护） ----------
            skills_catalog = get_skills_catalog()
            env_static = build_env_static(state.get("session_id"))
            static_segments = build_static_system_segments(skills_catalog, env_static)
            if isinstance(session_meta, dict) and session_meta.get("is_subagent"):
                from agent_subagent import SUBAGENT_RUN_INSTRUCTION

                static_segments = [
                    "## Subagent 运行约束\n\n" + SUBAGENT_RUN_INSTRUCTION.strip(),
                    *static_segments,
                ]
            # key_context body（随压缩变化）
            kc_body = key_context_body_for_system_prompt(state.get("key_context", "") or "")

            turn_msgs = inject_missing_tool_messages(messages_for_openai_turns(llm_history))

            llm_messages: List[Any] = [SystemMessage(content=s) for s in static_segments]
            if kc_body:
                llm_messages.append(SystemMessage(content=kc_body))
            llm_messages.extend(turn_msgs)
            _pre_api_timing_mark(pre_api_timings, "build_messages", _t_pre_api)
            _t_pre_api = time.perf_counter()

            # 调试：仅记录多轮消息数量与首段截断（避免整段 XML 日志）
            logger.debug(
                "LLM 多轮 messages: count=%s, last_roles=%s",
                len(llm_messages),
                [type(m).__name__ for m in llm_messages[-5:]],
            )

            # ---------- 2.1 上下文压缩：单轨 + key_context
            full_input_est = estimate_full_input_tokens_for_messages(
                state["session_id"],
                llm_messages,
            )
            _pre_api_timing_mark(pre_api_timings, "token_estimate", _t_pre_api)
            _t_pre_api = time.perf_counter()
            iter_client, iter_model, iter_max_output_tokens, iter_context_window = resolve_executor_config_for_session(
                state["session_id"]
            )
            _pre_api_timing_mark(pre_api_timings, "resolve_model_config", _t_pre_api)
            if emit:
                await _push_stream_event(
                    state,
                    {
                        "type": "context_tokens",
                        "estimated": int(full_input_est),
                        "threshold": int(iter_context_window),
                        "model": iter_model,
                        "ephemeral": True,
                    },
                    emit=emit,
                )
            # 上一轮已成功压缩时本轮不再压：key 追加后 system 变长，若再压会反复套娃并刷爆状态行
            _skip_compress = state.pop("_compress_skip_next", False)
            # 仅按 token 策略自动压缩；是否主动压由模型调用 context_manage(compact) 决定
            if not _skip_compress:
                kcur = state.get("key_context", "") or ""
                sid = state["session_id"]
                if full_input_est > iter_context_window:
                    _t_pre_api = time.perf_counter()
                    if emit:
                        await _push_stream_event(
                            state,
                            {
                                "type": "status",
                                "content": "【自动·长度策略】正在进行上下文裁剪以控制 token（可能需数秒，请稍候）…",
                            },
                            emit=emit,
                        )
                        # 让出事件循环，避免同步压缩阻塞时「开始」提示迟迟刷不到界面
                        await asyncio.sleep(0)
                    _hint_q: queue.Queue = queue.Queue()

                    def _compress_hint_emit(item: Any) -> None:
                        _hint_q.put(_progress_hint_to_stream_event(item))

                    # 压缩内为同步 LLM 调用，放线程执行以免阻塞 SSE；hint_sink 实时灌入队列由上层 drain
                    nl, nk, chg, _, used_llm_summary, new_recap = await _await_thread_with_sse_keepalive(
                        lambda: _run_context_policy_serialized(
                            llm_history,
                            kcur,
                            sid,
                            force_user_compact=False,
                            hint_sink=_compress_hint_emit,
                        ),
                        state,
                        emit,
                        thread_hint_queue=_hint_q,
                    )
                    _pre_api_timing_mark(pre_api_timings, "context_policy_run", _t_pre_api)
                else:
                    nl, nk, chg, used_llm_summary, new_recap = llm_history, kcur, False, False, None
            else:
                nl, nk, chg = llm_history, (state.get("key_context", "") or ""), False
            if chg:
                state["llm_history"] = nl
                state["dialogue"] = derive_dialogue_from_assistant_history(nl)
                state["key_context"] = nk
                todo_manager.sync_session_from_key_context(state["session_id"], state.get("key_context", "") or "")
                llm_history = nl
                work_messages = state.get("work_messages", [])
                _fb_kind_wm = _compress_history_fallback_kind(nl)
                if _fb_kind_wm == "truncated":
                    _wm_compact_note = (
                        "[系统通知：上下文已截尾（Conversation truncated）；更早内容请查本会话目录。]"
                    )
                    _st_base = (
                        "【自动·长度策略】上下文已截尾（Conversation truncated），"
                        "保留约半窗 token 尾部；更早内容请查本会话目录。"
                    )
                elif used_llm_summary:
                    _wm_compact_note = "[系统通知：上下文已按策略完成裁剪与摘要]"
                    _st_base = "【自动·长度策略】已完成上下文裁剪与摘要以控制长度"
                else:
                    _wm_compact_note = "[系统通知：上下文已按策略完成裁剪]"
                    _st_base = "【自动·长度策略】已完成上下文裁剪以控制长度"
                work_messages.append(SystemMessage(content=_wm_compact_note))
                state["work_messages"] = work_messages
                _persist_state_with_model_replace(state, nl, "auto_context_policy")
                state["_compress_skip_next"] = True
                _st = auto_length_strategy_status_line(
                    _st_base,
                    session_id=state["session_id"],
                    llm_history=nl,
                    key_context=nk,
                )
                await _push_stream_event(
                    state,
                    {"type": "status", "content": _st},
                    emit=emit,
                )
                compress_attempts = 0
                continue
            if full_input_est > iter_context_window:
                compress_attempts += 1
                if compress_attempts > CONTEXT_EMERGENCY_SHRINK_MAX_RETRIES:
                    logger.warning(
                        "自动应急截断已重试 %s 次仍可能超过整包阈值；将直接请求主模型。可新建会话或调低环境变量 CONTEXT_WINDOW（当前 %s）",
                        CONTEXT_EMERGENCY_SHRINK_MAX_RETRIES,
                        iter_context_window,
                    )
                else:
                    old_tok = estimate_full_input_tokens_for_llm_history(
                        state["session_id"],
                        llm_history,
                        state.get("key_context", "") or "",
                    )
                    new_llm_history, did_shrink, _ = compress_tail_fallback(
                        llm_history, reason="emergency"
                    )
                    if did_shrink and estimate_full_input_tokens_for_llm_history(
                        state["session_id"],
                        new_llm_history,
                        state.get("key_context", "") or "",
                    ) < old_tok:
                        llm_history = new_llm_history
                        state["llm_history"] = llm_history
                        _persist_state_with_model_replace(state, new_llm_history, "emergency_truncate")
                        logger.info(
                            "已按 CONTEXT_COMPRESS_FAILURE_MAX_TOKENS（与压缩失败兜底同款）裁剪对话尾部并继续本步"
                        )
                        compress_attempts = 0
                        continue
            else:
                compress_attempts = 0

            combined_tools: List[Dict[str, Any]] = list(OPENAI_TOOL_DEFINITIONS)
            _t_pre_api = time.perf_counter()
            try:
                combined_tools.extend(
                    await _await_steerable(
                        state,
                        agent_mcp.get_tool_definitions(),
                        emit,
                        "tool_definitions",
                    )
                )
                _pre_api_timing_mark(pre_api_timings, "mcp_tool_definitions", _t_pre_api)
            except _SteerRestartRequested:
                raise
            except Exception as _mcp_ex:
                _pre_api_timing_mark(pre_api_timings, "mcp_tool_definitions", _t_pre_api)
                logger.warning("MCP 工具列表加载失败（忽略）: %s", _mcp_ex)
            _t_pre_api = time.perf_counter()
            try:
                from agent_subagent import filter_tools_for_session

                combined_tools = filter_tools_for_session(combined_tools, session_meta)
                _pre_api_timing_mark(pre_api_timings, "subagent_tool_filter", _t_pre_api)
            except Exception as _sub_ex:
                _pre_api_timing_mark(pre_api_timings, "subagent_tool_filter", _t_pre_api)
                logger.warning("subagent 工具过滤失败（忽略）: %s", _sub_ex)

            # ---------- 2.6 调用 LLM ----------
            _t_pre_api = time.perf_counter()
            await _await_context_policy_idle_for_session(state, emit)
            _pre_api_timing_mark(pre_api_timings, "context_policy_wait_pre_api", _t_pre_api)
            _t_pre_api = time.perf_counter()
            await _raise_if_steer_requested(state, emit, "react")
            if session_manager.is_interrupt_requested(state["session_id"]):
                if _is_followup_interrupt(state["session_id"]):
                    raise asyncio.CancelledError()
                final_content = "任务已由用户中断。"
                await _push_stream_event(state, {"type": "status", "content": "任务已由用户中断"}, emit=emit)
                break
            _pre_api_timing_mark(pre_api_timings, "final_interrupt_checks", _t_pre_api)
            _pre_api_timing_log(
                state["session_id"],
                pre_api_timings,
                react_iter=int(iter_count),
                messages=len(llm_messages),
                tools=len(combined_tools),
                estimated_tokens=int(full_input_est),
                model=iter_model,
            )
            # 通知前端：LLM 推理开始
            if emit:
                await _push_stream_event(state, {"type": "status", "content": "正在思考中...", "ephemeral": True}, emit=emit)
                await asyncio.sleep(0)
            llm_messages_to_send = strip_reasoning_for_api_request(llm_messages)
            llm_stream_seq += 1
            turn = None
            streamed_this_call = False
            early_tool_detected = False
            seen_tool_call_ids: set = set()
            # 定时器：检测 reasoning/content 停止
            thinking_timer_task = None
            api_resp: Any = None
            llm_call_usage: Optional[Dict[str, int]] = None
            llm_call_finish: Dict[str, Any] = {"finish_reason": None, "stop_reason": None}
            actual_response_model = ""
            steer_interrupted_this_call = False
            if EXECUTOR_STREAM and emit:
                t_llm_start = time.monotonic()
                sync_q: queue.Queue = queue.Queue()
                stream_abort_event = threading.Event()
                def _stream_model_switch_status(ev: Dict[str, Any]) -> None:
                    if not _should_suppress_model_switch_status(state, ev):
                        sync_q.put(("status", ev))

                _set_model_switch_status_callback(
                    iter_client,
                    _stream_model_switch_status,
                )
                stream_task = asyncio.create_task(
                    asyncio.to_thread(
                        run_chat_completion_stream_worker,
                        sync_q,
                        iter_client,
                        iter_model,
                        llm_messages_to_send,
                        tools=combined_tools,
                        temperature=EXECUTOR_TEMPERATURE,
                        max_tokens=iter_max_output_tokens,
                        extra_body=EXECUTOR_EXTRA_BODY,
                        parallel_tool_calls=True,
                        reasoning_effort=EXECUTOR_REASONING_EFFORT,
                        should_abort=stream_abort_event.is_set,
                    )
                )
                stream_error: Optional[BaseException] = None
                try:
                    while True:
                        if _steer_requested(state):
                            steer_interrupted_this_call = True
                            stream_abort_event.set()
                            await _emit_steer_abort_event(state, emit, "llm_stream")
                            break
                        item = await asyncio.to_thread(_queue_get_with_timeout, sync_q, 0.03)
                        if item and item[0] == "__timeout__":
                            continue
                        if item is None:
                            break
                        tag, payload = item[0], item[1]
                        if tag == "err":
                            stream_error = payload
                            continue
                        if tag == "status":
                            if isinstance(payload, dict):
                                status_event = dict(payload)
                            else:
                                status_event = {"type": "status", "content": str(payload or "")}
                            if status_event.get("content"):
                                await _push_stream_event(state, status_event, emit=emit)
                            continue
                        if tag == "usage":
                            llm_call_usage = payload
                            record_prompt_tokens_for_messages(
                                state["session_id"],
                                llm_messages_to_send,
                                int((payload or {}).get("prompt_tokens", 0) or 0),
                            )
                            actual_response_model = str((payload or {}).get("model") or actual_response_model or "").strip()
                            ch = int((payload or {}).get("prompt_cache_hit_tokens", 0) or 0)
                            cm = int((payload or {}).get("prompt_cache_miss_tokens", 0) or 0)
                            if ch + cm > 0:
                                logger.info(
                                    "流式缓存: hit=%s miss=%s 命中率=%.1f%%",
                                    ch, cm, ch / (ch + cm) * 100
                                )
                            if emit:
                                r = emit({
                                    "type": "cache_stats",
                                    "stream": True,
                                    "cache_hit": ch,
                                    "cache_miss": cm,
                                    "hit_rate": round(ch / (ch + cm) * 100, 1) if (ch + cm) > 0 else 0,
                                    "input_tokens": int((payload or {}).get("prompt_tokens", 0) or 0),
                                    "output_tokens": int((payload or {}).get("completion_tokens", 0) or 0),
                                    "threshold": int(iter_context_window),
                                    "tokens_per_sec": round(int((payload or {}).get("completion_tokens", 0) or 0) / max(0.001, time.monotonic() - t_llm_start), 1),
                                    "model": actual_response_model or iter_model,
                                })
                                await r
                                await asyncio.sleep(0)
                            continue
                        if tag == "finish" and isinstance(payload, dict):
                            actual_response_model = str(payload.get("model") or actual_response_model or "").strip()
                            llm_call_finish = {
                                "finish_reason": payload.get("finish_reason"),
                                "stop_reason": payload.get("stop_reason"),
                                "model": actual_response_model or None,
                            }
                            continue
                        if tag == "turn":
                            turn = payload
                            continue
                        if tag == "tool_call_delta" and payload:
                            # 取消定时器
                            if thinking_timer_task and not thinking_timer_task.done():
                                thinking_timer_task.cancel()
                            payload_dict = payload if isinstance(payload, dict) else {}
                            tool_delta_id = str(payload_dict.get("id", "") or "").strip()
                            if tool_delta_id and tool_delta_id not in seen_tool_call_ids:
                                seen_tool_call_ids.add(tool_delta_id)
                                early_tool_detected = True
                            if emit:
                                r = emit(
                                    {
                                        "type": "tool_call_delta",
                                        "ephemeral": True,
                                        "stream_seq": llm_stream_seq,
                                        "react_iter": iter_count,
                                        "index": payload_dict.get("index", 0),
                                        "id": payload_dict.get("id", ""),
                                        "name_delta": payload_dict.get("name_delta", ""),
                                        "arguments_delta": payload_dict.get("arguments_delta", ""),
                                    }
                                )
                                if inspect.isawaitable(r):
                                    await r
                                await asyncio.sleep(0)
                            streamed_this_call = True
                            continue
                        if tag == "reasoning" and payload:
                            # 启动/重置定时器
                            if thinking_timer_task and not thinking_timer_task.done():
                                thinking_timer_task.cancel()
                            thinking_timer_task = asyncio.create_task(_thinking_timer(emit, state))
                            r = emit(
                                {
                                    "type": "llm_reasoning_delta",
                                    "delta": payload,
                                    "react_iter": iter_count,
                                    "stream_seq": llm_stream_seq,
                                    "ephemeral": True,
                                }
                            )
                            if inspect.isawaitable(r):
                                await r
                            await asyncio.sleep(0)
                            streamed_this_call = True
                        elif tag == "content" and payload:
                            # 启动/重置定时器
                            if thinking_timer_task and not thinking_timer_task.done():
                                thinking_timer_task.cancel()
                            thinking_timer_task = asyncio.create_task(_thinking_timer(emit, state))
                            r = emit(
                                {
                                    "type": "llm_response_delta",
                                    "delta": payload,
                                    "react_iter": iter_count,
                                    "stream_seq": llm_stream_seq,
                                    "ephemeral": True,
                                }
                            )
                            if inspect.isawaitable(r):
                                await r
                            await asyncio.sleep(0)
                            streamed_this_call = True
                finally:
                    # 取消定时器
                    if thinking_timer_task and not thinking_timer_task.done():
                        thinking_timer_task.cancel()
                    try:
                        if steer_interrupted_this_call:
                            stream_abort_event.set()
                            stream_task.add_done_callback(_discard_task_result)
                            stream_task.cancel()
                        else:
                            await stream_task
                    except Exception:
                        pass
                    _set_model_switch_status_callback(iter_client, None)
                if steer_interrupted_this_call:
                    if await _consume_steer_messages(state, emit=emit):
                        _reset_steer_control(state)
                        llm_history = list(state["llm_history"])
                        work_messages = list(state["work_messages"])
                        final_result_retries = 0
                        state["final_result_retries"] = 0
                        state["empty_final_retries"] = 0
                        continue
                    _reset_steer_control(state)
                if stream_error is not None:
                    logger.warning("流式输出失败，降级为整段响应: %s", stream_error)
                    turn = None
                    streamed_this_call = False
                elif turn is None:
                    logger.warning("流式未完成（无 turn），降级为整段响应")
                    streamed_this_call = False

            if turn is None:
                model_switch_status_events: List[Dict[str, Any]] = []
                def _collect_model_switch_status(ev: Dict[str, Any]) -> None:
                    if not _should_suppress_model_switch_status(state, ev):
                        model_switch_status_events.append(dict(ev))

                _set_model_switch_status_callback(
                    iter_client,
                    _collect_model_switch_status,
                )
                try:
                    t_llm_fallback_start = time.monotonic()
                    api_resp = await _await_steerable(
                        state,
                        asyncio.to_thread(
                            lambda: chat_completion(
                                iter_client,
                                iter_model,
                                llm_messages_to_send,
                                tools=combined_tools,
                                temperature=EXECUTOR_TEMPERATURE,
                                max_tokens=iter_max_output_tokens,
                                extra_body=EXECUTOR_EXTRA_BODY,
                                parallel_tool_calls=True,
                                reasoning_effort=EXECUTOR_REASONING_EFFORT,
                            )
                        ),
                        emit,
                        "llm_request",
                    )
                    choice0 = api_resp.choices[0]
                    actual_response_model = str(getattr(api_resp, "model", None) or actual_response_model or "").strip()
                    turn = parse_assistant_message(choice0.message)
                    llm_call_finish = {
                        "finish_reason": getattr(choice0, "finish_reason", None),
                        "stop_reason": getattr(choice0, "stop_reason", None),
                        "model": actual_response_model or None,
                    }
                    if emit:
                        for _switch_ev in model_switch_status_events:
                            await _push_stream_event(state, _switch_ev, emit=emit)
                        model_switch_status_events.clear()
                    u = getattr(api_resp, "usage", None)
                    if u is not None and not llm_call_usage:
                        llm_call_usage = extract_usage_dict(u)
                        record_prompt_tokens_for_messages(
                            state["session_id"],
                            llm_messages_to_send,
                            int((llm_call_usage or {}).get("prompt_tokens", 0) or 0),
                        )
                        ch = llm_call_usage.get("prompt_cache_hit_tokens", 0)
                        cm = llm_call_usage.get("prompt_cache_miss_tokens", 0)
                        if ch + cm > 0:
                            logger.info(
                                "非流式缓存: hit=%s miss=%s 命中率=%.1f%%",
                                ch, cm, ch / (ch + cm) * 100
                            )
                        if emit:
                            await _push_stream_event(
                                state,
                                {
                                    "type": "cache_stats",
                                    "stream": False,
                                    "cache_hit": ch,
                                    "cache_miss": cm,
                                    "hit_rate": round(ch / (ch + cm) * 100, 1) if (ch + cm) > 0 else 0,
                                    "input_tokens": llm_call_usage.get("prompt_tokens", 0),
                                    "output_tokens": llm_call_usage.get("completion_tokens", 0),
                                    "threshold": int(iter_context_window),
                                    "tokens_per_sec": round(llm_call_usage.get("completion_tokens", 0) / max(0.001, time.monotonic() - t_llm_fallback_start), 1),
                                    "model": actual_response_model or iter_model,
                                },
                                emit=emit,
                            )
                except _SteerRestartRequested:
                    raise
                except Exception as _llm_exc:
                    if emit:
                        for _switch_ev in model_switch_status_events:
                            await _push_stream_event(state, _switch_ev, emit=emit)
                        model_switch_status_events.clear()
                    _cls = _classify_api_error(_llm_exc)
                    _err_detail = f"{type(_llm_exc).__name__}: {_llm_exc}"
                    logger.error("LLM 调用失败 [iter %s] %s %s: %s", iter_count, _cls["code"], _cls["title"], _err_detail)
                    if _cls.get("code") == "NET":
                        attempt = int(state.get("_network_reconnect_attempts", 0) or 0) + 1
                        state["_network_reconnect_attempts"] = attempt
                        delay = min(30.0, 2.0 * (2 ** min(attempt - 1, 4)))
                        if emit:
                            await _push_stream_event(
                                state,
                                {
                                    "type": "llm_stream_aborted",
                                    "reason": "network_reconnect",
                                    "react_iter": int(iter_count),
                                    "stream_seq": llm_stream_seq,
                                    "ephemeral": True,
                                },
                                emit=emit,
                            )
                            await _push_stream_event(
                                state,
                                {
                                    "type": "status",
                                    "content": f"网络连接失败，正在重连（第 {attempt} 次，{delay:g}s 后重试）...",
                                    "ephemeral": True,
                                },
                                emit=emit,
                            )
                        if not await _await_retry_delay_or_interrupt(state, emit, delay):
                            final_content = "任务已由用户中断。"
                            await _push_stream_event(
                                state,
                                {"type": "status", "content": "任务已由用户中断"},
                                emit=emit,
                            )
                            break
                        iter_count = max(0, iter_count - 1)
                        state["_current_react_iter"] = int(iter_count)
                        continue
                    state.pop("_network_reconnect_attempts", None)
                    if emit:
                        import json as _json
                        _err_data = {"c": _cls["code"], "t": _cls["title"], "m": _cls["msg"], "s": _cls["solution"], "d": _err_detail}
                        await _push_stream_event(
                            state,
                            {"type": "error", "content": "__ERR_CARD__" + _json.dumps(_err_data, ensure_ascii=False)},
                            emit=emit,
                        )
                    final_content = f"LLM 调用失败 [{_cls['code']}] {_cls['title']}：{_cls['msg']}\n{_cls['solution']}"
                    break
                finally:
                    _set_model_switch_status_callback(iter_client, None)
            state.pop("_network_reconnect_attempts", None)
            # 正文与思考严格分源
            response_text = turn.content or ""
            reasoning_text = (turn.reasoning_content or "").strip()
            response_log_text = truncate_head_tail(response_text, LOG_TRUNCATE_KEEP_CHARS)
            reasoning_log_text = truncate_head_tail(reasoning_text, LOG_TRUNCATE_KEEP_CHARS) if reasoning_text else ""

            if reasoning_text:
                logger.info(
                    f"LLM Reasoning (iter {iter_count}): "
                    f"{reasoning_log_text}"
                )
            logger.info(
                f"LLM Response (iter {iter_count}): "
                f"{response_log_text if (response_text or '').strip() else '(无正文)'}"
            )

            # 推送给前端：流式时已在 delta 中展示；非流式仍发整段事件（与持久化一致）
            if emit:
                if streamed_this_call:
                    sid = state["session_id"]
                    if (reasoning_text or "").strip():
                        session_manager.append_ui_event(
                            sid,
                            {
                                "type": "llm_reasoning",
                                "content": reasoning_text,
                                "react_iter": int(iter_count),
                            },
                        )
                        await prune_session_ephemeral(
                            sid,
                            types={"llm_reasoning_delta"},
                            react_iter=int(iter_count),
                        )
                    if (response_text or "").strip():
                        session_manager.append_ui_event(
                            sid,
                            {
                                "type": "llm_response",
                                "content": response_text,
                                "react_iter": int(iter_count),
                            },
                        )
                        await prune_session_ephemeral(
                            sid,
                            types={"llm_response_delta"},
                            react_iter=int(iter_count),
                        )
                else:
                    if (reasoning_text or "").strip():
                        r = emit(
                            {
                                "type": "llm_reasoning",
                                "content": reasoning_text,
                                "react_iter": int(iter_count),
                            }
                        )
                        if inspect.isawaitable(r):
                            await r
                        await asyncio.sleep(0)
                    if (response_text or "").strip():
                        r = emit(
                            {
                                "type": "llm_response",
                                "content": response_text,
                                "react_iter": int(iter_count),
                            }
                        )
                        if inspect.isawaitable(r):
                            await r
                        await asyncio.sleep(0)

            tool_calls_list = turn.tool_calls
            if not isinstance(tool_calls_list, list) or len(tool_calls_list) == 0:
                tool_calls_list = None
            if tool_calls_list is not None:
                state["_steer_rollback_marker"] = {
                    "llm_len": len(llm_history),
                    "work_len": len(work_messages),
                }
            else:
                state.pop("_steer_rollback_marker", None)

            # 将本轮助手输出写入历史（OpenAI 多轮：AssistantMessage，含 tool_calls）
            _ak = build_assistant_additional_kwargs(reasoning_text)
            _ai_kw: Dict[str, Any] = {
                "content": response_text if response_text is not None else "",
                "metadata": {"is_assistant_response": True},
                "additional_kwargs": _ak,
            }
            if tool_calls_list is not None:
                _ai_kw["tool_calls"] = tool_calls_list
            interim_msg = AssistantMessage(**_ai_kw)
            llm_history.append(interim_msg)
            work_messages.append(interim_msg)
            state["llm_history"] = llm_history
            state["work_messages"] = work_messages
            _persist_state_with_model_append(state, interim_msg)

            # 记录 LLM 调用详情（可选；与实际上送内容一致，已剥历史 reasoning）
            request_msgs = [_serialize_message(msg) for msg in llm_messages_to_send]
            call_record = {
                "model": actual_response_model or iter_model,
                "requested_model": iter_model,
                "request": request_msgs,
                "response": {
                    "content": response_text if response_text else None,
                    "reasoning_content": reasoning_text if reasoning_text else None,
                    "finish_reason": llm_call_finish.get("finish_reason"),
                    "stop_reason": llm_call_finish.get("stop_reason"),
                    "tool_calls": [
                        {
                            "name": tc["name"],
                            "args": tc["args"],
                            "id": tc.get("id", "")
                        } for tc in tool_calls_list
                    ] if tool_calls_list else None,
                },
                "usage": llm_call_usage,
            }
            state["llm_calls"].append(call_record)

            # ---------- 2.7 并行工具调用（须先于重复检测插入的系统消息，保证 assistant(tool_calls) 后紧跟 tool） ----------
            if tool_calls_list:
                # 定义单个工具的执行逻辑（异步）
                async def execute_one(tool_call):
                    tool_name = tool_call["name"]
                    tool_args = tool_call["args"]
                    tool_id = tool_call["id"]
                    tool_call_index = tool_call.get("index")
                    await _raise_if_steer_requested(state, emit, "tool")

                    # 工作区放宽 Shell / 网页下载：前端弹窗确认后才进入「执行中」占位
                    if emit and tool_name != "context_manage" and _tool_ui_approval_enabled():
                        spec = _tool_ui_approval_spec(tool_name, tool_args)
                        if spec is None and isinstance(tool_name, str) and tool_name.startswith("mcp_"):
                            await _await_steerable(
                                state,
                                agent_mcp.ensure_started(),
                                emit,
                                "tool_mcp_start",
                            )
                            spec = agent_mcp.ui_approval_spec_for_mcp_tool(tool_name, tool_args)
                        if spec:
                            appr_id = new_approval_id()

                            async def _emit_appr():
                                await _emit_tool_approval_required_sse(
                                    emit,
                                    state["session_id"],
                                    appr_id,
                                    tool_name,
                                    spec["title"],
                                    spec["message"],
                                    spec.get("subtitle") or "",
                                )

                            allowed = await _await_steerable(
                                state,
                                wait_tool_ui_approval_after_emit(
                                    state["session_id"], appr_id, _emit_appr
                                ),
                                emit,
                                "tool_approval",
                            )
                            brief = spec.get("brief") or tool_name
                            if allowed:
                                await _push_stream_event(
                                    state,
                                    {"type": "status", "content": "【安全确认】用户已允许：" + brief},
                                    emit=emit,
                                )
                            else:
                                await _push_stream_event(
                                    state,
                                    {
                                        "type": "status",
                                        "content": "【安全确认】用户已拒绝执行（已跳过）。 " + brief,
                                    },
                                    emit=emit,
                                )
                                return _tool_result_user_denied_ui(tool_name, tool_args, tool_id)

                    # 执行前占位（context_manage / task 已有独立 status，不重复推送）
                    await _raise_if_steer_requested(state, emit, "tool")
                    if emit and tool_name not in ("context_manage", "task"):
                        await _emit_tool_pending_sse(
                            emit,
                            tool_name,
                            tool_args,
                            tool_id or "",
                            iter_count,
                            int(tool_call_index) if tool_call_index is not None else None,
                        )

                    # 特殊处理：context_manage（mode=compact | edit_key_context）
                    if tool_name == "context_manage":
                        mode = str(tool_args.get("mode") or "compact").strip().lower()
                        if mode == "compact":
                            logger.info("手动 context_manage compact：单轨强制压缩")
                            if emit:
                                await _push_stream_event(
                                    state,
                                    {
                                        "type": "status",
                                        "content": "【context_manage·compact】正在进行上下文裁剪（可能需数秒，请稍候）…",
                                    },
                                    emit=emit,
                                )
                            _cq: queue.Queue = queue.Queue()

                            def _compact_hint_emit(item: Any) -> None:
                                _cq.put(_progress_hint_to_stream_event(item))

                            nl, nk, chg, _, used_llm_c, new_recap_c = await _await_thread_with_sse_keepalive(
                                lambda: _run_context_policy_serialized(
                                    llm_history,
                                    state.get("key_context", ""),
                                    state["session_id"],
                                    force_user_compact=True,
                                    hint_sink=_compact_hint_emit,
                                ),
                                state,
                                emit,
                                thread_hint_queue=_cq,
                            )
                            if chg:
                                state["llm_history"] = nl
                                state["dialogue"] = derive_dialogue_from_assistant_history(nl)
                                state["key_context"] = nk
                                todo_manager.sync_session_from_key_context(state["session_id"], "")
                                return {
                                    "type": "compact",
                                    "new_llm_history": nl,
                                    "new_recap": new_recap_c,
                                    "used_llm_summary": used_llm_c,
                                }
                            return {"type": "compact_noop"}
                        if mode == "edit_key_context":
                            instr = str(tool_args.get("edit_instruction") or "").strip()
                            if not instr:
                                return {
                                    "type": "tool",
                                    "tool_name": tool_name,
                                    "tool_args": tool_args,
                                    "tool_id": tool_id,
                                    "result": "edit_key_context 模式需要提供非空的 edit_instruction。",
                                    "tool_detail_log": "缺少 edit_instruction",
                                    "tool_detail_llm": "缺少 edit_instruction",
                                    "tool_detail_ui": "缺少 edit_instruction",
                                    "result_for_log": "缺少 edit_instruction",
                                    "tool_failed": True,
                                }
                            logger.info("context_manage edit_key_context")
                            _kq: queue.Queue = queue.Queue()

                            def _key_hint_emit(item: Any) -> None:
                                _kq.put(_progress_hint_to_stream_event(item))

                            nk, msg = await _await_thread_with_sse_keepalive(
                                lambda: run_edit_key_context_instruction(
                                    state["session_id"],
                                    instr,
                                    hint_sink=_key_hint_emit,
                                ),
                                state,
                                emit,
                                thread_hint_queue=_kq,
                            )
                            state["key_context"] = nk
                            _persist_state(state)
                            return {
                                "type": "tool",
                                "tool_name": tool_name,
                                "tool_args": tool_args,
                                "tool_id": tool_id,
                                "result": msg,
                                "tool_detail_log": truncate_head_tail(msg, LOG_TRUNCATE_KEEP_CHARS),
                                "tool_detail_llm": truncate_tool_result_for_llm(msg, LLM_CONTEXT_TRUNCATE_KEEP_CHARS),
                                "tool_detail_ui": msg,
                                "result_for_log": truncate_head_tail(msg, LOG_TRUNCATE_KEEP_CHARS),
                                "tool_failed": _tool_result_indicates_failure(tool_name, msg),
                            }
                        return {
                            "type": "tool",
                            "tool_name": tool_name,
                            "tool_args": tool_args,
                            "tool_id": tool_id,
                            "result": f"无效的 mode：{mode!r}；仅支持 compact、edit_key_context。",
                            "tool_detail_log": "无效 mode",
                            "tool_detail_llm": "无效 mode",
                            "tool_detail_ui": "无效 mode",
                            "result_for_log": "无效 mode",
                            "tool_failed": True,
                        }

                    # 特殊处理：update_todo — 写入 todo_plan.md
                    if tool_name == "update_todo":
                        todo_tool_failed = False
                        try:
                            # 兼容多种参数格式：items / todos，数组 / JSON字符串 / 单个dict
                            uitems = tool_args.get("items")
                            if uitems is None:
                                uitems = tool_args.get("todos")
                            from agent_tools import _normalize_todo_items
                            normalized, err_msg = _normalize_todo_items(uitems)
                            if err_msg:
                                result = err_msg
                                todo_tool_failed = True
                            else:
                                result = todo_manager.update_for_session(state["session_id"], normalized)
                            if emit:
                                titems = list(
                                    todo_manager._by_session.get(state["session_id"], [])
                                )
                                done_n = sum(
                                    1 for t in titems if t.get("status") == "completed"
                                )
                                await _push_stream_event(
                                    state,
                                    {
                                        "type": "todo_plan",
                                        "ephemeral": True,
                                        "has_plan": len(titems) > 0,
                                        "items": [
                                            {
                                                "id": t["id"],
                                                "text": t["text"],
                                                "status": t["status"],
                                            }
                                            for t in titems
                                        ],
                                        "done": done_n,
                                        "total": len(titems),
                                    },
                                    emit=emit,
                                )
                        except Exception as e:
                            result = f"待办更新失败：{e}"
                            todo_tool_failed = True
                        result_str = str(result)
                        result_for_log = truncate_head_tail(result_str, LOG_TRUNCATE_KEEP_CHARS)
                        _llm_limit = LLM_CONTEXT_TRUNCATE_KEEP_CHARS * 2
                        if len(result_str) > _llm_limit:
                            result_for_llm = _save_result_to_tempfile(result_str, tool_name, state)
                        else:
                            result_for_llm = truncate_tool_result_for_llm(result_str, LLM_CONTEXT_TRUNCATE_KEEP_CHARS)
                        return {
                            "type": "tool",
                            "tool_name": tool_name,
                            "tool_args": tool_args,
                            "tool_id": tool_id,
                            "result": result,
                            "tool_detail_log": result_for_log,
                            "tool_detail_llm": result_for_llm,
                            "tool_detail_ui": result_str,
                            "result_for_log": result_for_log,
                            "tool_failed": bool(
                                todo_tool_failed or _tool_result_indicates_failure(tool_name, result)
                            ),
                        }

                    # 特殊处理：task — 启动/续接 subagent
                    if tool_name == "task":
                        from agent_subagent import run_subagent_task

                        try:
                            result = await _await_steerable(
                                state,
                                run_subagent_task(
                                    tool_args=tool_args if isinstance(tool_args, dict) else {},
                                    parent_session_id=state["session_id"],
                                    parent_key_context=state.get("key_context", ""),
                                    emit=emit,
                                ),
                                emit,
                                "tool_task",
                            )
                        except _SteerRestartRequested:
                            raise
                        except Exception as e:
                            result = f"subagent 执行异常：{e}"
                        result_str = str(result)
                        result_for_log = truncate_head_tail(result_str, LOG_TRUNCATE_KEEP_CHARS)
                        _llm_limit = LLM_CONTEXT_TRUNCATE_KEEP_CHARS * 2
                        if len(result_str) > _llm_limit:
                            result_for_llm = _save_result_to_tempfile(result_str, tool_name, state)
                        else:
                            result_for_llm = truncate_tool_result_for_llm(
                                result_str, LLM_CONTEXT_TRUNCATE_KEEP_CHARS
                            )
                        return {
                            "type": "tool",
                            "tool_name": tool_name,
                            "tool_args": tool_args,
                            "tool_id": tool_id,
                            "result": result,
                            "tool_detail_log": result_for_log,
                            "tool_detail_llm": result_for_llm,
                            "tool_detail_ui": result_str,
                            "result_for_log": result_for_log,
                            "tool_failed": _tool_result_indicates_failure(tool_name, result),
                        }

                    # MCP 外部工具（配置见 mcp_servers.json / MCP_SERVERS_JSON）
                    if tool_name.startswith("mcp_"):
                        tool_failed = False
                        try:
                            result = await _await_steerable(
                                state,
                                agent_mcp.invoke_tool_by_fname(
                                    tool_name,
                                    tool_args if isinstance(tool_args, dict) else {},
                                ),
                                emit,
                                "tool_mcp",
                            )
                        except _SteerRestartRequested:
                            raise
                        except Exception as e:
                            result = f"MCP 调用异常：{e}"
                            tool_failed = True
                        result_str = str(result)
                        result_for_log = truncate_head_tail(result_str, LOG_TRUNCATE_KEEP_CHARS)
                        _llm_limit = LLM_CONTEXT_TRUNCATE_KEEP_CHARS * 2
                        if len(result_str) > _llm_limit:
                            result_for_llm = _save_result_to_tempfile(result_str, tool_name, state)
                        else:
                            result_for_llm = truncate_tool_result_for_llm(result_str, LLM_CONTEXT_TRUNCATE_KEEP_CHARS)
                        result_for_ui = result_str
                        tool_detail_log = result_for_log
                        tool_detail_llm = result_for_llm
                        tool_detail_ui = result_for_ui
                        tool_failed = tool_failed or _tool_result_indicates_failure(tool_name, result)
                        return {
                            "type": "tool",
                            "tool_name": tool_name,
                            "tool_args": tool_args,
                            "tool_id": tool_id,
                            "result": result,
                            "tool_detail_log": tool_detail_log,
                            "tool_detail_llm": tool_detail_llm,
                            "tool_detail_ui": tool_detail_ui,
                            "result_for_log": result_for_log,
                            "tool_failed": tool_failed,
                        }

                    # 普通工具
                    tool_func = tools_dict.get(tool_name)
                    tool_failed = False
                    if not tool_func:
                        result = f"未知工具：{tool_name}"
                        tool_failed = True
                    else:
                        try:
                            # 注入 interrupt 回调，让 run_shell 能感知 interrupt 并杀子进程
                            _sid = state.get("session_id", "") if isinstance(state, dict) else ""
                            if _sid and tool_name == "run_shell":
                                set_run_shell_interrupt_check(
                                    lambda: session_manager.is_interrupt_requested(_sid) or _steer_requested(state)
                                )
                            if hasattr(tool_func, "ainvoke"):
                                result = await _await_steerable(
                                    state,
                                    tool_func.ainvoke(tool_args),
                                    emit,
                                    "tool",
                                )
                            elif hasattr(tool_func, "invoke"):
                                result = await _await_steerable(
                                    state,
                                    asyncio.to_thread(lambda: tool_func.invoke(tool_args)),
                                    emit,
                                    "tool",
                                )
                            else:
                                result = await _await_steerable(
                                    state,
                                    _invoke_plain_tool(tool_func, tool_args),
                                    emit,
                                    "tool",
                                )
                        except _SteerRestartRequested:
                            raise
                        except Exception as e:
                            result = f"工具执行异常：{str(e)}"
                            tool_failed = True
                        finally:
                            clear_run_shell_interrupt_check()

                    # 截断结果（三路文本生成：日志用、LLM上下文用、UI用）
                    if tool_name in READ_ONLY_TOOLS:
                        result_str = _wrap_read_only_tool_output_lines(result)
                    else:
                        result_str = redact_sensitive_tool_text(result)
                    
                    # 1. 日志用（首尾保留LOG_TRUNCATE_KEEP_CHARS）
                    result_for_log = truncate_head_tail(result_str, LOG_TRUNCATE_KEEP_CHARS)
                    
                    # 2. LLM上下文用：activate_skill 完整返回不截断；其他工具超阈值则落盘替换，否则原有截断
                    if tool_name == "activate_skill":
                        result_for_llm = result_str
                    else:
                        _llm_limit = LLM_CONTEXT_TRUNCATE_KEEP_CHARS * 2
                        if len(result_str) > _llm_limit:
                            result_for_llm = _save_result_to_tempfile(result_str, tool_name, state)
                        else:
                            result_for_llm = truncate_tool_result_for_llm(result_str, LLM_CONTEXT_TRUNCATE_KEEP_CHARS)
                    
                    # 3. UI用：完整内容（不做截断，但可保留Shell的10000硬截断，后续可考虑移除）
                    result_for_ui = result_str  # 直接完整

                    tool_detail_log = result_for_log
                    tool_detail_llm = result_for_llm
                    tool_detail_ui = result_for_ui

                    tool_failed = tool_failed or _tool_result_indicates_failure(tool_name, result)

                    return {
                        "type": "tool",
                        "tool_name": redact_sensitive_tool_text(tool_name),
                        "tool_args": redact_sensitive_tool_obj(tool_args),
                        "tool_id": tool_id,
                        "tool_call_index": tool_call_index,
                        "result": result_str,
                        "tool_detail_log": tool_detail_log,
                        "tool_detail_llm": tool_detail_llm,
                        "tool_detail_ui": tool_detail_ui,
                        "result_for_log": result_for_log,
                        "tool_failed": tool_failed,
                    }

                def is_read_only_tool(tool_call: Dict[str, Any]) -> bool:
                    n = tool_call.get("name") or ""
                    if isinstance(n, str) and n.startswith("mcp_"):
                        return False
                    return n in READ_ONLY_TOOLS

                async def run_group(group_calls: List[Dict[str, Any]]) -> List[Any]:
                    """
                    并行执行一批只读工具；用 as_completed 使「每个工具一结束就发 tool_call」，
                    再按原 tool_calls 顺序组装返回值供后续写 llm_history（顺序与 OpenAI 要求一致）。
                    """
                    if not group_calls:
                        return []

                    async def run_one_with_tc(tc: Dict[str, Any]):
                        try:
                            r = await execute_one(tc)
                        except _SteerRestartRequested:
                            raise
                        except Exception as e:
                            r = e
                        return (tc, r)

                    tasks = [asyncio.create_task(run_one_with_tc(tc)) for tc in group_calls]
                    by_id: Dict[str, Any] = {}
                    try:
                        pending_tasks = set(tasks)
                        while pending_tasks:
                            done_tasks, pending_tasks = await asyncio.wait(
                                pending_tasks,
                                timeout=0.03,
                                return_when=asyncio.FIRST_COMPLETED,
                            )
                            if not done_tasks:
                                await _raise_if_steer_requested(state, emit, "tool")
                                continue
                            for done in done_tasks:
                                tc, r = await done
                                tid = (tc or {}).get("id", "")
                                if tid is not None:
                                    by_id[tid] = r
                                if (
                                    emit
                                    and isinstance(r, dict)
                                    and r.get("type") == "tool"
                                ):
                                    r["_sse_emitted"] = True
                                    await _emit_tool_call_sse(emit, r, iter_count, state)
                            await _raise_if_steer_requested(state, emit, "tool")
                    except _SteerRestartRequested:
                        for task in tasks:
                            if not task.done():
                                task.add_done_callback(_discard_task_result)
                                task.cancel()
                        raise
                    out: List[Any] = []
                    for tc in group_calls:
                        tid = tc.get("id", "")
                        if tid in by_id:
                            out.append(by_id[tid])
                    return out

                # 分类执行策略：
                # 1) 只读工具同组并行（带并发上限）
                # 2) 写操作工具逐个串行
                # 3) 保持原始 tool_calls 顺序边界（读组/写组分段）
                exec_results = []
                pending_read_only = []

                async def flush_read_only():
                    nonlocal pending_read_only, exec_results
                    while pending_read_only:
                        chunk = pending_read_only[:MAX_PARALLEL_TOOLS]
                        pending_read_only = pending_read_only[MAX_PARALLEL_TOOLS:]
                        chunk_results = await run_group(chunk)
                        exec_results.extend(chunk_results)

                for tool_call in tool_calls_list:
                    await _raise_if_steer_requested(state, emit, "tool")
                    if session_manager.is_interrupt_requested(state["session_id"]):
                        if _is_followup_interrupt(state["session_id"]):
                            raise asyncio.CancelledError()
                        break
                    if is_read_only_tool(tool_call):
                        pending_read_only.append(tool_call)
                        continue

                    # 写操作前先清空当前只读并行队列
                    await flush_read_only()
                    write_result = await execute_one(tool_call)
                    exec_results.append(write_result)

                # 末尾残留的只读工具并行执行
                await _raise_if_steer_requested(state, emit, "tool")
                await flush_read_only()

                # 处理每个工具的返回结果
                for res in exec_results:
                    await _raise_if_steer_requested(state, emit, "tool")
                    if isinstance(res, Exception):
                        logger.error(f"工具执行异常: {res}")
                        state["_react_ui_tool_fail_count"] = int(state.get("_react_ui_tool_fail_count", 0) or 0) + 1
                        await _emit_live_metrics(state, emit)
                        error_msg = ToolMessage(content=f"工具执行异常: {str(res)}", tool_call_id="unknown")
                        work_messages.append(error_msg)
                        llm_history.append(error_msg)
                        _runtime_v2_append_model_message(state, error_msg)
                        # 追加流式事件
                        await _push_stream_event(state, {"type": "error", "content": f"工具执行异常: {str(res)}"}, emit=emit)
                        continue
                    if res is None:
                        continue

                    if res.get("type") == "compact":
                        # 更新压缩后的历史
                        llm_history = res["new_llm_history"]
                        state["llm_history"] = llm_history
                        _fb_ck = _compress_history_fallback_kind(llm_history)
                        if _fb_ck == "truncated":
                            _compact_note = (
                                "[系统通知：上下文已截尾（Conversation truncated）；更早内容请查本会话目录。]"
                            )
                            _status = (
                                "【context_manage·compact】上下文已截尾（Conversation truncated），"
                                "保留约半窗 token 尾部。"
                            )
                        elif bool(res.get("used_llm_summary")):
                            _compact_note = "[系统通知：对话已摘要，关键信息已写入 key_context]"
                            _status = "【context_manage·compact】已完成上下文裁剪与摘要"
                        else:
                            _compact_note = "[系统通知：对话已摘要，关键信息已写入 key_context]"
                            _status = "【context_manage·compact】已完成上下文裁剪"
                        work_messages.append(SystemMessage(content=_compact_note))
                        state["work_messages"] = work_messages
                        _runtime_v2_replace_model_history(state, llm_history, "manual_context_manage")
                        await _push_stream_event(
                            state,
                            {"type": "status", "content": _status},
                            emit=emit,
                        )
                        continue

                    if res.get("type") == "compact_noop":
                        await _push_stream_event(
                            state,
                            {"type": "status", "content": "【context_manage·compact】当前上下文无需进一步裁剪或摘要"},
                            emit=emit,
                        )
                        continue

                    # 普通工具：添加到历史
                    # UI消息使用完整内容（tool_detail_ui），LLM消息使用截断内容（tool_detail_llm）
                    if res.get("type") == "tool":
                        res = redact_sensitive_tool_obj(res)

                    if res.get("tool_failed"):
                        state["_react_ui_tool_fail_count"] = int(state.get("_react_ui_tool_fail_count", 0) or 0) + 1
                        await _emit_live_metrics(state, emit)
                    _record_temporary_write_file(
                        state,
                        str(res.get("tool_name") or ""),
                        res.get("tool_args"),
                        bool(res.get("tool_failed")),
                    )
                    tool_msg_ui = ToolMessage(content=res["tool_detail_ui"], tool_call_id=res["tool_id"])
                    tool_msg_llm = ToolMessage(content=res["tool_detail_llm"], tool_call_id=res["tool_id"])
                    work_messages.append(tool_msg_ui)
                    llm_history.append(tool_msg_llm)
                    _runtime_v2_append_model_message(state, tool_msg_llm)
                    state["llm_history"] = llm_history
                    state["work_messages"] = work_messages

                    tool_results.append({
                        "tool": res["tool_name"],
                        "args": res["tool_args"],
                        "result": res["result"]
                    })
                    logger.info(f"工具调用: {res['tool_name']}({str(res['tool_args'])}) -> {res['result_for_log']}")

                    # 并行只读批已在 run_group 内发 SSE；单工具/写路径在此发
                    if emit and not (isinstance(res, dict) and res.get("_sse_emitted")):
                        r = emit({
                            "type": "tool_call",
                            "tool": redact_sensitive_tool_text(res["tool_name"]),
                            "args": redact_sensitive_tool_obj(res["tool_args"]),
                            "command_preview": _tool_command_preview(res["tool_name"], res["tool_args"]),
                            "result": redact_sensitive_tool_text(res["result"]),
                            "tool_call_id": res.get("tool_id") or "",
                            "tool_call_index": res.get("tool_call_index"),
                            "react_iter": int(iter_count),
                        })
                        if inspect.isawaitable(r):
                            await r
                        state["_react_ui_tool_count"] = int(state.get("_react_ui_tool_count", 0) or 0) + 1
                        await _emit_live_metrics(state, emit)
                        await asyncio.sleep(0)

                state["llm_history"] = llm_history
                state["work_messages"] = work_messages
                _persist_state(state)
                if await _consume_steer_messages(state, emit=emit):
                    state.pop("_steer_rollback_marker", None)
                    _reset_steer_control(state)
                    llm_history = list(state["llm_history"])
                    work_messages = list(state["work_messages"])
                    final_result_retries = 0
                    state["final_result_retries"] = 0
                    state["empty_final_retries"] = 0
                    continue
                state.pop("_steer_rollback_marker", None)

            # ---------- 2.8 重复检测（须在工具结果写入 llm_history 之后，避免 OpenAI 报 tool_calls 顺序错误） ----------
            # 文本重复检测只对比「正文」；思考单独存在于 reasoning 字段，不参与与 last_response 的混比
            current_content = (response_text or "").strip()
            # 仅调工具、assistant 正文为空时，多轮会得到 ""==""，不能算作「重复输出」
            is_text_repeat = bool(current_content) and (current_content == last_response_content)
            current_tool_calls = tool_calls_list if tool_calls_list else []
            current_tool_signature = None
            if current_tool_calls:
                signature_parts = []
                for tc in current_tool_calls:
                    tool_name = tc.get("name", "")
                    args = tc.get("args", {})
                    args_str = json.dumps(args, sort_keys=True)
                    signature_parts.append(f"{tool_name}:{args_str}")
                current_tool_signature = "|".join(signature_parts)
            is_tool_repeat = (current_tool_signature and last_tool_calls_signature and current_tool_signature == last_tool_calls_signature)

            if is_text_repeat or is_tool_repeat:
                repeat_count += 1
                logger.warning(f"检测到重复行为（{repeat_count}/{REPEAT_DETECTION_THRESHOLD_ERROR}）：文本重复={is_text_repeat}, 工具重复={is_tool_repeat}")
                if repeat_count >= REPEAT_DETECTION_THRESHOLD_SUMMARY and not reminder_inserted:
                    logger.info("重复输出达到摘要阈值，插入强制提醒")
                    if is_tool_repeat and current_tool_signature:
                        repeat_tool_info = f"重复调用工具: {current_tool_calls[0].get('name')}，参数: {current_tool_calls[0].get('args')}"
                    else:
                        repeat_tool_info = "重复输出相同内容"
                    reminder_msg = SystemMessage(
                        content=f"[系统强制提醒] 检测到连续重复行为（{repeat_count}次）。{repeat_tool_info}。请立即停止当前重复模式，回顾任务目标，采取以下措施之一：\n"
                                f"1. 如果任务已完成，请输出最终结果。\n"
                                f"2. 如果遇到障碍，请使用 `update_todo` 调整计划，并尝试不同的工具或方法。\n"
                                f"3. 如果无法继续，请输出一条错误说明。\n"
                                f"禁止继续重复相同的工具调用或输出。"
                    )
                    llm_history.append(reminder_msg)
                    work_messages.append(reminder_msg)
                    _runtime_v2_append_model_message(state, reminder_msg)
                    state["llm_history"] = llm_history
                    state["work_messages"] = work_messages
                    _persist_state(state)
                    reminder_inserted = True
                    state["reminder_inserted"] = True
                    await _push_stream_event(state, {"type": "status", "content": f"检测到连续重复行为（{repeat_count}次），已插入强制提醒"}, emit=emit)
                if repeat_count >= REPEAT_DETECTION_THRESHOLD_ERROR:
                    logger.error(f"重复行为超过阈值（{REPEAT_DETECTION_THRESHOLD_ERROR}次），终止循环")
                    _snippet = (response_text or "").strip() or (reasoning_text or "")[:200]
                    final_content = f"检测到连续重复行为，已终止任务。最近输出：{_snippet}"
                    state["repeat_count"] = 0
                    state["last_response_content"] = None
                    state["last_tool_calls_signature"] = None
                    state["reminder_inserted"] = False
                    break
            else:
                repeat_count = 0
                reminder_inserted = False
                last_response_content = current_content
                last_tool_calls_signature = current_tool_signature
                state["repeat_count"] = 0
                state["last_response_content"] = current_content
                state["last_tool_calls_signature"] = current_tool_signature
                state["reminder_inserted"] = False

            if not tool_calls_list:
                # 没有工具调用 → 终稿只取正文；仅有思考、无正文时由前端 llm_reasoning 展示，不当作最终回答文本
                if await _consume_steer_messages(state, emit=emit):
                    _reset_steer_control(state)
                    llm_history = list(state["llm_history"])
                    work_messages = list(state["work_messages"])
                    final_result_retries = 0
                    state["final_result_retries"] = 0
                    state["empty_final_retries"] = 0
                    continue
                final_content = (response_text or "").strip()
                if not final_content and final_result_retries < final_result_retry_max:
                    final_result_retries += 1
                    state["final_result_retries"] = final_result_retries
                    state["empty_final_retries"] = final_result_retries
                    _persist_state(state)
                    await _push_stream_event(
                        state,
                        {
                            "type": "status",
                            "content": f"模型未输出最终内容，正在重试（{final_result_retries}/{final_result_retry_max}）",
                        },
                        emit=emit,
                    )
                    continue
                state["final_result_retries"] = 0
                state["empty_final_retries"] = 0
                break

        else:
            # 达到最大迭代次数
            state["react_limit_reached"] = True
            final_content = "执行步骤达到最大迭代次数，可能陷入循环，请检查执行过程。您可以手动继续任务"

    except _SteerRestartRequested:
        return await _restart_react_after_steer(state, emit)
    finally:
        pass

    # 本回合 ReAct 统计：写入 ui_events，刷新页面后仍可显示耗时/轮数/工具次数
    dur_ms = int(max(0.0, (time.monotonic() - react_wall_start) * 1000.0))
    tool_n = int(state.pop("_react_ui_tool_count", 0) or 0)
    fail_n = int(state.pop("_react_ui_tool_fail_count", 0) or 0)
    if emit:
        await _push_stream_event(
            state,
            {
                "type": "process_metrics",
                "duration_ms": dur_ms,
                "react_loops": int(iter_count),
                "tool_calls": tool_n,
                "tool_failures": fail_n,
            },
            emit=emit,
        )

    # ========== 3. 循环结束，添加标记并保存（仅内部使用，不在前端实时打印） ==========
    # 兜底清理：若所有 todo 已完成但未显式清空，自动清空以释放前端面板
    if todo_manager.has_active_plan(state["session_id"]):
        _td_items = todo_manager._by_session.get(state["session_id"], [])
        if _td_items and all(t.get("status") == "completed" for t in _td_items):
            todo_manager._by_session[state["session_id"]] = []
            try:
                session_manager.save_todo_plan(state["session_id"], "")
            except Exception:
                pass
            _persist_state(state)
    if not (llm_history and isinstance(llm_history[-1], SystemMessage) and llm_history[-1].content == "Loop finished"):
        end_msg = SystemMessage(content="Loop finished")
        llm_history.append(end_msg)
        work_messages = list(state.get("work_messages", []))
        work_messages.append(end_msg)
        _runtime_v2_append_model_message(state, end_msg)
        state["llm_history"] = llm_history
        state["work_messages"] = work_messages
        _persist_state(state)

    state["final_response"] = final_content
    return state

def validate_final(state: State) -> State:
    """终稿已由 ReAct 产出；不再调用独立校验模型，仅推送 PASS 占位事件以保持 SSE/UI 兼容。"""
    if state.get("final_printed", False):
        return state
    cleaned = _cleanup_temporary_write_files(state)
    if cleaned:
        state["stream_events"].append(
            {
                "type": "status",
                "content": f"已清理临时文件 {len(cleaned)} 个（已移入 .trash）",
            }
        )
    state["stream_events"].append({"type": "validate_final", "result": "PASS", "reason": ""})
    _persist_state(state)
    return state


def finish(state: State) -> State:
    """最终处理：生成会话标题、保存会话、输出最终结果"""
    # 确保 user_input 存在
    if "user_input" not in state:
        for msg in reversed(state["dialogue"]):
            if isinstance(msg, UserMessage):
                state["user_input"] = msg.content
                break
        else:
            state["user_input"] = ""
        logger.warning("finish: user_input 缺失，已从对话记录中恢复")

    if state.get("final_printed", False):
        return state

    if not state.get("final_response"):
        state["final_response"] = "No result"

    state["stream_events"].append({"type": "final", "content": state["final_response"]})

    # 先尝试生成标题（executor 用量计入下方 Total，避免「仅 HTTP 日志」在流式下恒为 0）
    title_usage: Optional[Dict[str, int]] = None
    metadata = session_manager._load_metadata(state["session_id"])
    if metadata.get("name") == "新会话":
        first_user = None
        for m in state["dialogue"]:
            if isinstance(m, UserMessage):
                first_user = m.content
                break
        if first_user:
            try:
                title_template = load_prompt_template("title_generator")
                title_prompt = title_template.format(
                    first_user=first_user,
                    final_response=state.get("final_response") or "",
                )
                title, title_usage = executor_text_and_usage(title_prompt)
                title = title.strip()[:20] if title else ""
                if not title:
                    title = first_user[:15]
            except Exception as e:
                logger.warning(f"生成会话标题失败: {e}")
                title = first_user[:15]
                title_usage = None
            if title:
                session_manager.set_session_name(state["session_id"], title)

    # 记录 LLM 调用详情及 token 统计（以各轮 call 上记录的 usage 为准）
    total_input_tokens = 0
    total_output_tokens = 0
    if state.get("llm_calls"):
        logger.info("=== LLM Call Details ===")
        for call in state["llm_calls"]:
            usage = call.get("usage")
            if usage:
                total_input_tokens += int(usage.get("prompt_tokens", 0) or 0)
                total_output_tokens += int(usage.get("completion_tokens", 0) or 0)

            logger.info("Model: %s", redact_sensitive_tool_text(call.get("model")))
            logger.info(">>> Agent to LLM:")
            for msg in call["request"]:
                role = msg.get('role', 'unknown')
                content = msg.get('content', '')
                if role in ("user", "user&history"):
                    content = _truncate_xml_content_blocks(content, LOG_TRUNCATE_KEEP_CHARS)
                else:
                    content = truncate_head_tail(content, LOG_TRUNCATE_KEEP_CHARS)
                logger.info(f"{COLOR_WHITE}  {role}: {content}{COLOR_RESET}")

            logger.info("<<< LLM Response:")
            resp = call["response"]
            if resp.get("tool_calls"):
                tool_calls_text = truncate_head_tail(str(resp["tool_calls"]), LOG_TRUNCATE_KEEP_CHARS)
                logger.info(f"{COLOR_BLUE}  tool_calls: {tool_calls_text}{COLOR_RESET}")
            else:
                content = resp.get('content', '')
                content = truncate_head_tail(content, LOG_TRUNCATE_KEEP_CHARS)
                logger.info(f"{COLOR_YELLOW}  {content}{COLOR_RESET}")
            logger.info("<<Finish>>")
    else:
        logger.info("=== LLM Call Details ===")
        logger.info("(No LLM calls recorded)")

    if title_usage:
        ti = int(title_usage.get("prompt_tokens", 0) or 0)
        to = int(title_usage.get("completion_tokens", 0) or 0)
        total_input_tokens += ti
        total_output_tokens += to
        logger.info("Session title (executor) tokens: input=%s, output=%s", ti, to)

    if state.get("llm_calls") or title_usage:
        logger.info(
            f"Total tokens: input={total_input_tokens}, output={total_output_tokens}, total={total_input_tokens+total_output_tokens}"
        )

    # 终稿：与最后一条 is_assistant_response 同文则只保留一条，标 is_final 并去 is_assistant_response（无重复 agent/llm）
    fr = (state.get("final_response") or "").strip()
    llm2, need_llm = apply_final_dedup_to_messages(state["llm_history"], fr)
    state["llm_history"] = llm2
    _final_ai_kw: Dict[str, Any] = {
        "content": fr,
        "metadata": {"is_final": True},
        "additional_kwargs": build_assistant_additional_kwargs(""),
    }
    if need_llm:
        state["llm_history"].append(AssistantMessage(**_final_ai_kw))
    wm0 = list(state.get("work_messages", []))
    wm2, need_wm = apply_final_dedup_to_messages(wm0, fr)
    state["work_messages"] = wm2
    if need_wm:
        state["work_messages"].append(AssistantMessage(**_final_ai_kw))
    _persist_session_messages_with_model_replace(state, state["llm_history"], "finish")
    state["final_printed"] = True
    return state


# ==================== 流式执行辅助 ====================
async def astream_events(
    user_input: str,
    session_id: str = None,
    should_stop: Optional[Callable[[str], bool]] = None,
    run_id: Optional[str] = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    顺序执行 react_node → validate_final（无独立校验 LLM）→ finish，通过队列实时向前端推送事件。
    """
    executor_http_client.interactions.clear()

    sid_in = str(session_id or "").strip()
    if sid_in:
        try:
            from session_lifecycle import is_session_deleted

            if is_session_deleted(sid_in):
                raise ValueError(f"Session {sid_in} was deleted")
        except ValueError:
            raise
        except Exception:
            pass
        session_id = sid_in
        key_context = _load_key_context_for_run(session_id)
    else:
        session_id, _, _, _, key_context, _metadata = (
            session_manager.get_or_create_session(session_id)
        )
    setup_logging(user_input, session_id or "")
    pre_run_timings: Dict[str, int] = {}
    _t_pre = time.perf_counter()
    llm_history_dicts = _load_model_history_dicts_v2_primary(session_id, reconcile_legacy=True)
    _pre_api_timing_mark(pre_run_timings, "load_model_history", _t_pre)
    _t_pre = time.perf_counter()
    work_messages_dicts = _load_work_history_dicts_for_run(session_id)
    _pre_api_timing_mark(pre_run_timings, "load_work_messages", _t_pre)

    _t_pre = time.perf_counter()
    prev_work_messages = [_dict_to_message(m) for m in work_messages_dicts]
    prev_llm_history = [_dict_to_message(m) for m in llm_history_dicts]
    _pre_api_timing_mark(pre_run_timings, "decode_histories", _t_pre)
    _t_pre = time.perf_counter()
    prev_work_messages, prev_llm_history = _sanitize_loaded_histories_for_new_run(
        session_id,
        prev_work_messages,
        prev_llm_history,
        key_context,
        "sanitize_unclosed_tool_calls_before_chat",
    )
    _pre_api_timing_mark(pre_run_timings, "sanitize_histories", _t_pre)

    user_message = UserMessage(content=user_input)

    new_work_messages = prev_work_messages + [user_message]
    new_llm_history = prev_llm_history + [user_message]
    runtime_v2_run_id = str(run_id or "").strip() or str(uuid.uuid4())

    state: State = {
        "dialogue": derive_dialogue_from_assistant_history(new_llm_history),
        "work_messages": new_work_messages,
        "llm_history": new_llm_history,
        "user_input": user_input,
        "final_response": "",
        "stream_events": [],
        "final_printed": False,
        "session_id": session_id,
        "llm_calls": [],
        "key_context": key_context,
        "_runtime_v2_run_id": runtime_v2_run_id,
        "_pre_run_timings": pre_run_timings,
    }
    todo_manager.sync_session_from_key_context(session_id, key_context or "")
    session_manager.clear_interrupt(session_id, runtime_v2_run_id)
    steer_control = _register_steer_run_control(session_id, runtime_v2_run_id)
    state["_steer_control"] = steer_control

    queue: asyncio.Queue = asyncio.Queue()
    runtime_v2_terminal_mirrored = False

    def mirror_runtime_v2(event_type: str, payload: Optional[Dict[str, Any]] = None) -> None:
        nonlocal runtime_v2_terminal_mirrored
        if event_type in {"run_finished", "run_interrupted", "run_failed"}:
            if runtime_v2_terminal_mirrored:
                return
            runtime_v2_terminal_mirrored = True
        try:
            from runtime_v2.mirror import RuntimeMirror

            mirror = RuntimeMirror(session_manager.sessions_dir)
            if event_type == "run_started":
                mirror.mirror_run_started(session_id, runtime_v2_run_id, payload)
            elif event_type == "run_finished":
                mirror.mirror_run_finished(session_id, runtime_v2_run_id, payload)
            elif event_type == "run_interrupted":
                mirror.mirror_run_interrupted(session_id, runtime_v2_run_id, payload)
            elif event_type == "run_failed":
                mirror.mirror_run_failed(session_id, str((payload or {}).get("error") or "unknown error"), runtime_v2_run_id, payload)
        except Exception as mirror_error:
            logger.debug("Runtime V2 mirror run event failed: %s", mirror_error)

    async def emit(ev: Dict[str, Any]) -> None:
        # 与浏览器 SSE 一致；ephemeral（如 llm_*_delta）仅实时推送，不写入 ui_events
        # 子 agent 转发事件仅推 SSE，不写入父会话 ui_events
        if should_persist_ui_event(ev):
            session_manager.append_ui_event(session_id, ev)
        await publish_session_event(session_id, ev)
        await queue.put(ev)

    async def runner():
        nonlocal state
        completed = False
        terminal_event = {"type": "run_interrupted", "ephemeral": True}
        try:
            # 用户气泡由前端已画；此处只写入与流顺序一致的持久化，供刷新与 SSE 同源
            mirror_runtime_v2("run_started", {"mode": "chat"})
            _runtime_v2_append_model_message(state, user_message)
            await emit({"type": "run_started", "run_id": runtime_v2_run_id, "ephemeral": True})
            session_manager.append_ui_event(session_id, {"type": "user", "content": user_input})
            await emit({"type": "status", "content": "New Agent Loop Start"})
            state = await _run_react_node_off_loop(state, emit)
            await emit({"type": "status", "content": "Loop finished"})
            stream_event_count_after_react = len(state["stream_events"])
            state = validate_final(state)
            for evt in state["stream_events"][stream_event_count_after_react:]:
                if evt.get("type") in ("status", "validate_final", "final"):
                    await emit(evt)
            stream_event_count_after_validate = len(state["stream_events"])
            state = finish(state)
            for evt in state["stream_events"][stream_event_count_after_validate:]:
                if evt.get("type") in ("status", "validate_final", "final"):
                    await emit(evt)
            completed = True
        except asyncio.CancelledError:
            terminal_event = {"type": "run_interrupted", "run_id": runtime_v2_run_id, "ephemeral": True}
            mirror_runtime_v2("run_interrupted", {"reason": "cancelled"})
            session_manager.mark_session_unread_result(session_id, status="failed")
            raise
        except Exception as exc:
            terminal_event = {"type": "run_failed", "run_id": runtime_v2_run_id, "error": str(exc), "ephemeral": True}
            mirror_runtime_v2("run_failed", {"error": str(exc)})
            session_manager.mark_session_unread_result(session_id, status="failed")
            raise
        finally:
            _clear_steer_run_control(session_id, steer_control)
            if completed:
                mirror_runtime_v2("run_finished", {"mode": "chat"})
                terminal_event = {"type": "run_finished", "run_id": runtime_v2_run_id, "ephemeral": True}
            await emit(terminal_event)
            await close_session_stream(session_id)
            await queue.put(None)

    task = asyncio.create_task(runner())
    from session_lifecycle import register_run_task

    register_run_task(session_id, task)
    try:
        while True:
            if should_stop and should_stop(session_id):
                reason = session_manager.get_interrupt_reason(session_id) or "user"
                if reason == "followup":
                    mirror_runtime_v2("run_interrupted", {"reason": reason})
                    task.cancel()
                    break
                ev1 = {"type": "status", "content": "任务已由用户中断"}
                ev2 = {"type": "final", "content": "任务已由用户中断。"}
                mirror_runtime_v2("run_interrupted", {"reason": reason})
                session_manager.mark_session_unread_result(session_id, status="failed")
                session_manager.append_ui_event(session_id, ev1)
                session_manager.append_ui_event(session_id, ev2)
                yield ev1
                yield ev2
                task.cancel()
                break
            item = await queue.get()
            if item is None:
                break
            yield item
    finally:
        if not task.done():
            try:
                session_manager.request_interrupt(session_id, runtime_v2_run_id, reason="disconnect")
            except Exception:
                pass
            task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


async def astream_events_continuation(
    session_id: str,
    should_stop: Optional[Callable[[str], bool]] = None,
    require_pending_subagents: bool = True,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    后台 subagent 完成后续接父 Agent：不追加用户气泡与 ui_events user 事件，
    pending 结果在 react_node 内通过 consume_pending_subagent_notifications 注入。
    """
    executor_http_client.interactions.clear()

    sid = (session_id or "").strip()
    if not sid:
        return
    if require_pending_subagents and not session_manager.can_continue_after_subagents(sid):
        return

    session_id = sid
    key_context = _load_key_context_for_run(session_id)
    setup_logging("[subagent-continuation]", session_id)
    pre_run_timings: Dict[str, int] = {}
    _t_pre = time.perf_counter()
    runtime_v2_llm_history_dicts = _load_runtime_v2_model_history_dicts(session_id)
    if runtime_v2_llm_history_dicts:
        llm_history_dicts = runtime_v2_llm_history_dicts
    elif _runtime_v2_is_primary():
        logger.warning(
            "Runtime V2 continuation skipped because model projection is empty: session=%s",
            session_id,
        )
        return
    else:
        session_manager.reconcile_llm_work_to_ui_user_count(session_id)
        llm_history_dicts = _load_model_history_dicts_v2_primary(session_id, reconcile_legacy=False)
    _pre_api_timing_mark(pre_run_timings, "load_model_history", _t_pre)
    _t_pre = time.perf_counter()
    work_messages_dicts = _load_work_history_dicts_for_run(session_id)
    _pre_api_timing_mark(pre_run_timings, "load_work_messages", _t_pre)

    _t_pre = time.perf_counter()
    prev_work_messages = [_dict_to_message(m) for m in work_messages_dicts]
    prev_llm_history = [_dict_to_message(m) for m in llm_history_dicts]
    _pre_api_timing_mark(pre_run_timings, "decode_histories", _t_pre)
    _t_pre = time.perf_counter()
    prev_work_messages, prev_llm_history = _sanitize_loaded_histories_for_new_run(
        session_id,
        prev_work_messages,
        prev_llm_history,
        key_context,
        "sanitize_unclosed_tool_calls_before_continuation",
    )
    _pre_api_timing_mark(pre_run_timings, "sanitize_histories", _t_pre)

    user_input = ""
    for msg in reversed(prev_llm_history):
        if isinstance(msg, UserMessage):
            user_input = msg.content
            break

    runtime_v2_run_id = str(uuid.uuid4())

    state: State = {
        "dialogue": derive_dialogue_from_assistant_history(prev_llm_history),
        "work_messages": prev_work_messages,
        "llm_history": prev_llm_history,
        "user_input": user_input,
        "final_response": "",
        "stream_events": [],
        "final_printed": False,
        "session_id": session_id,
        "llm_calls": [],
        "key_context": key_context,
        "_runtime_v2_run_id": runtime_v2_run_id,
        "_pre_run_timings": pre_run_timings,
    }
    todo_manager.sync_session_from_key_context(session_id, key_context or "")
    session_manager.clear_interrupt(session_id)
    steer_control = _register_steer_run_control(session_id, runtime_v2_run_id)
    state["_steer_control"] = steer_control

    queue: asyncio.Queue = asyncio.Queue()
    runtime_v2_terminal_mirrored = False

    def mirror_runtime_v2(event_type: str, payload: Optional[Dict[str, Any]] = None) -> None:
        nonlocal runtime_v2_terminal_mirrored
        if event_type in {"run_finished", "run_interrupted", "run_failed"}:
            if runtime_v2_terminal_mirrored:
                return
            runtime_v2_terminal_mirrored = True
        try:
            from runtime_v2.mirror import RuntimeMirror

            mirror = RuntimeMirror(session_manager.sessions_dir)
            if event_type == "run_started":
                mirror.mirror_run_started(session_id, runtime_v2_run_id, payload)
            elif event_type == "run_finished":
                mirror.mirror_run_finished(session_id, runtime_v2_run_id, payload)
            elif event_type == "run_interrupted":
                mirror.mirror_run_interrupted(session_id, runtime_v2_run_id, payload)
            elif event_type == "run_failed":
                mirror.mirror_run_failed(session_id, str((payload or {}).get("error") or "unknown error"), runtime_v2_run_id, payload)
        except Exception as mirror_error:
            logger.debug("Runtime V2 mirror continuation run event failed: %s", mirror_error)

    async def emit(ev: Dict[str, Any]) -> None:
        if should_persist_ui_event(ev):
            session_manager.append_ui_event(session_id, ev)
        await publish_session_event(session_id, ev)
        await queue.put(ev)

    async def runner():
        nonlocal state
        completed = False
        terminal_event = {"type": "run_interrupted", "ephemeral": True}
        try:
            mirror_runtime_v2("run_started", {"mode": "continuation"})
            await emit({"type": "run_started", "ephemeral": True})
            await emit({"type": "status", "content": "Subagent Continuation Start"})
            state = await _run_react_node_off_loop(state, emit)
            await emit({"type": "status", "content": "Loop finished"})
            stream_event_count_after_react = len(state["stream_events"])
            state = validate_final(state)
            for evt in state["stream_events"][stream_event_count_after_react:]:
                if evt.get("type") in ("status", "validate_final", "final"):
                    await emit(evt)
            stream_event_count_after_validate = len(state["stream_events"])
            state = finish(state)
            for evt in state["stream_events"][stream_event_count_after_validate:]:
                if evt.get("type") in ("status", "validate_final", "final"):
                    await emit(evt)
            completed = True
        except asyncio.CancelledError:
            terminal_event = {"type": "run_interrupted", "ephemeral": True}
            mirror_runtime_v2("run_interrupted", {"reason": "cancelled"})
            session_manager.mark_session_unread_result(session_id, status="failed")
            raise
        except Exception as exc:
            terminal_event = {"type": "run_failed", "error": str(exc), "ephemeral": True}
            mirror_runtime_v2("run_failed", {"error": str(exc)})
            session_manager.mark_session_unread_result(session_id, status="failed")
            raise
        finally:
            _clear_steer_run_control(session_id, steer_control)
            if completed:
                mirror_runtime_v2("run_finished", {"mode": "continuation"})
                terminal_event = {"type": "run_finished", "ephemeral": True}
            await emit(terminal_event)
            await close_session_stream(session_id)
            await queue.put(None)

    task = asyncio.create_task(runner())
    from session_lifecycle import register_run_task

    register_run_task(session_id, task)
    try:
        while True:
            if should_stop and should_stop(session_id):
                reason = session_manager.get_interrupt_reason(session_id) or "user"
                if reason == "followup":
                    mirror_runtime_v2("run_interrupted", {"reason": reason})
                    task.cancel()
                    break
                ev1 = {"type": "status", "content": "任务已由用户中断"}
                ev2 = {"type": "final", "content": "任务已由用户中断。"}
                mirror_runtime_v2("run_interrupted", {"reason": reason})
                session_manager.mark_session_unread_result(session_id, status="failed")
                session_manager.append_ui_event(session_id, ev1)
                session_manager.append_ui_event(session_id, ev2)
                yield ev1
                yield ev2
                task.cancel()
                break
            item = await queue.get()
            if item is None:
                break
            yield item
    finally:
        if not task.done():
            try:
                session_manager.request_interrupt(session_id, runtime_v2_run_id, reason="disconnect")
            except Exception:
                pass
            task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
