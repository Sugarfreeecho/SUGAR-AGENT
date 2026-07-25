"""
agent_subagent — 子 Agent（task 工具）运行器。

子会话位于父会话目录 subagents/{child_id}/，支持 Cursor Task 对齐参数。
"""

from __future__ import annotations

import asyncio
import copy
import json
import shutil
import subprocess
import threading
import uuid
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from agent_harness import (
    SUBAGENT_BEST_OF_N,
    SUBAGENT_MAX_DEPTH,
    SUBAGENT_MAX_REACT_ITER,
    WORK_DIR,
    UserMessage,
    _dict_to_message,
    _message_to_dict,
    derive_dialogue_from_assistant_history,
    inherited_executor_selection,
    list_executor_model_profile_choices,
    logger,
    session_manager,
    todo_manager,
)
from agent_subagent_events import (
    should_forward_subagent_event_to_parent,
    should_persist_ui_event,
    tag_subagent_forward_event,
)

# 只读（含 web，explore 默认）
EXPLORE_TOOLS = frozenset(
    {"read_file", "ls", "list_dir", "glob", "grep", "web_search", "web_fetch", "activate_skill"}
)
# 严格只读（Ask 模式：无 web / MCP / 写 / shell）
STRICT_READONLY_TOOLS = frozenset(
    {"read_file", "ls", "list_dir", "glob", "grep", "activate_skill"}
)
GENERAL_TOOLS_EXCLUDE = frozenset({"update_todo", "context_manage", "ask_user"})

SUBAGENT_TYPES = frozenset(
    {"generalPurpose", "explore", "best-of-n-runner"}
)

SUBAGENT_TOOL_PROFILES: Dict[str, Dict[str, Any]] = {
    "generalPurpose": {
        "exclude": GENERAL_TOOLS_EXCLUDE,
    },
    "explore": {
        "allow": EXPLORE_TOOLS,
        "exclude_mcp": True,
    },
    "readonly": {
        "allow": STRICT_READONLY_TOOLS,
        "exclude_mcp": True,
    },
}

_TOOL_FILTER_CACHE_MAX = 64
_tool_filter_cache: "OrderedDict[tuple, tuple[tuple[Dict[str, Any], ...], tuple[Dict[str, Any], ...]]]" = OrderedDict()
_tool_filter_cache_lock = threading.Lock()

SUBAGENT_RUN_INSTRUCTION = (
    "你是隔离运行的 subagent。你只能依赖当前 subagent 的 system/key_context、"
    "父 Agent 本次下发的任务说明和附件；不要假设能看到父会话、用户原话或父 Agent 的工具结果。"
    "父 Agent 通常只消费你的最终输出，因此最终输出必须自包含。\n"
    "工作规则：\n"
    "1. 先识别目标、范围、约束、交付物和验收方式，只处理下发任务授权的范围。\n"
    "2. 先检查实际文件、数据或运行状态再下结论。分析任务保持只读；"
    "只有任务明确要求实施时才修改，并做与风险相称的验证。\n"
    "3. 不要向用户追问，也不要等待父 Agent 回复。非关键事实缺失时采用最小合理假设并明确标注；"
    "关键输入缺失时说明已检查内容、具体阻塞和所需信息。\n"
    "4. 最终输出按顺序给出：结果或结论、关键证据、修改文件与验证、假设/风险/未完成项。"
    "省略空项和过程性寒暄。"
)


def _runtime_v2_primary() -> bool:
    try:
        from runtime_v2 import runtime_v2_primary

        return bool(runtime_v2_primary())
    except Exception:
        return True


def _load_runtime_v2_context_summary(session_id: str) -> str:
    from runtime_v2 import SnapshotStore

    snapshot = SnapshotStore(
        session_manager.sessions_dir,
        path_resolver=getattr(session_manager, "_resolve_session_path", None),
    ).read_consistent(session_id)
    context = snapshot.get("context") if isinstance(snapshot, dict) else {}
    summary = context.get("summary") if isinstance(context, dict) else {}
    if isinstance(summary, dict):
        return str(summary.get("summary") or "")
    return ""


def _load_subagent_run_histories(child_id: str) -> tuple[List[Any], List[Any], str]:
    if _runtime_v2_primary():
        from runtime_v2 import RuntimeModelProjection

        llm_dicts = RuntimeModelProjection(
            session_manager.sessions_dir,
            path_resolver=getattr(session_manager, "_resolve_session_path", None),
        ).read_message_dicts(child_id)
        prev_llm = [_dict_to_message(m) for m in llm_dicts if isinstance(m, dict)]
        key_context = _load_runtime_v2_context_summary(child_id)
        return [], prev_llm, key_context

    _, _, work_dicts, llm_dicts, key_context, _meta = session_manager.get_or_create_session(child_id)
    return (
        [_dict_to_message(m) for m in work_dicts],
        [_dict_to_message(m) for m in llm_dicts],
        key_context,
    )


def _persist_subagent_run_state(child_id: str, state_out: Dict[str, Any]) -> None:
    key_context = str(state_out.get("key_context") or "")
    if _runtime_v2_primary():
        from runtime_v2 import (
            RuntimeHistoryOps,
            runtime_v2_react_transaction_timeout_seconds,
        )

        llm_history = [_message_to_dict(m) for m in state_out.get("llm_history", [])]
        ops = RuntimeHistoryOps(
            session_manager.sessions_dir,
            path_resolver=getattr(session_manager, "_resolve_session_path", None),
            transaction_timeout_seconds=runtime_v2_react_transaction_timeout_seconds(),
        )
        ops.replace_model_history(child_id, llm_history, reason="subagent_run_finished")
        if key_context.strip():
            ops.commit_context_summary(child_id, key_context)
        return
    work_messages = [_message_to_dict(m) for m in state_out.get("work_messages", [])]
    llm_history = [_message_to_dict(m) for m in state_out.get("llm_history", [])]
    session_manager.update_session(child_id, work_messages, llm_history, key_context)


def _save_initial_subagent_key_context(child_id: str, key_context: str) -> None:
    if not (key_context or "").strip():
        return
    if _runtime_v2_primary():
        from runtime_v2 import (
            RuntimeHistoryOps,
            runtime_v2_react_transaction_timeout_seconds,
        )

        RuntimeHistoryOps(
            session_manager.sessions_dir,
            path_resolver=getattr(session_manager, "_resolve_session_path", None),
            transaction_timeout_seconds=runtime_v2_react_transaction_timeout_seconds(),
        ).commit_context_summary(child_id, key_context)
        return
    session_manager.save_key_context(child_id, key_context)

_IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"})
_TEXT_SUFFIXES = frozenset(
    {".txt", ".md", ".json", ".py", ".js", ".ts", ".tsx", ".html", ".css", ".xml", ".yaml", ".yml", ".csv", ".log"}
)


class SubagentTaskRegistry:
    """跟踪后台 subagent asyncio 任务，支持 interrupt / 等待。"""

    def __init__(self) -> None:
        self._tasks: Dict[str, asyncio.Task] = {}
        self._run_ids: Dict[str, str] = {}
        self._parent_by_child: Dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def reserve(self, child_id: str, run_id: str, *, parent_session_id: str = "") -> bool:
        """Atomically reserve the single execution slot for a subagent."""
        async with self._lock:
            current_run_id = self._run_ids.get(child_id)
            current_task = self._tasks.get(child_id)
            if current_run_id and (current_task is None or not current_task.done()):
                return False
            self._run_ids[child_id] = run_id
            self._tasks.pop(child_id, None)
            pid = (parent_session_id or "").strip()
            if pid:
                self._parent_by_child[child_id] = pid
            return True

    async def attach(self, child_id: str, run_id: str, task: asyncio.Task) -> bool:
        """Attach a task to a reservation without replacing another run."""
        async with self._lock:
            if self._run_ids.get(child_id) != run_id:
                return False
            self._tasks[child_id] = task
            return True

    async def register(
        self,
        child_id: str,
        task: asyncio.Task,
        *,
        parent_session_id: str = "",
    ) -> bool:
        run_id = uuid.uuid4().hex
        if not await self.reserve(child_id, run_id, parent_session_id=parent_session_id):
            return False
        if not await self.attach(child_id, run_id, task):
            return False

        def _release_finished(_task: asyncio.Task) -> None:
            try:
                asyncio.get_running_loop().create_task(self.unregister(child_id, run_id))
            except RuntimeError:
                pass

        task.add_done_callback(_release_finished)
        return True

    async def unregister(self, child_id: str, run_id: str) -> bool:
        async with self._lock:
            if run_id and self._run_ids.get(child_id) != run_id:
                return False
            self._tasks.pop(child_id, None)
            self._run_ids.pop(child_id, None)
            self._parent_by_child.pop(child_id, None)
            return True

    def is_running(self, child_id: str) -> bool:
        if child_id in self._run_ids and child_id not in self._tasks:
            return True
        t = self._tasks.get(child_id)
        return t is not None and not t.done()

    async def cancel(self, child_id: str) -> bool:
        async with self._lock:
            t = self._tasks.get(child_id)
            run_id = self._run_ids.get(child_id, "")
        if t is None or t.done():
            return False
        session_manager.request_interrupt(child_id)
        t.cancel()
        try:
            await t
        except asyncio.CancelledError:
            pass
        except Exception:
            pass
        await self.unregister(child_id, run_id)
        return True

    async def cancel_for_parent(
        self,
        parent_session_id: str,
        *,
        also_ids: Optional[Set[str]] = None,
    ) -> None:
        pid = (parent_session_id or "").strip()
        extra = set(also_ids or ())
        async with self._lock:
            ids = [
                cid
                for cid in self._tasks
                if cid in extra or self._parent_by_child.get(cid) == pid
            ]
        for cid in ids:
            try:
                await self.cancel(cid)
            except Exception:
                pass

    async def wait(self, child_id: str, timeout: Optional[float] = None) -> Optional[Any]:
        async with self._lock:
            t = self._tasks.get(child_id)
        if t is None:
            return None
        try:
            if timeout is not None:
                return await asyncio.wait_for(asyncio.shield(t), timeout=timeout)
            return await t
        except asyncio.TimeoutError:
            return None
        except asyncio.CancelledError:
            return None


subagent_registry = SubagentTaskRegistry()


def _tool_name(defn: Dict[str, Any]) -> str:
    fn = (defn or {}).get("function") or {}
    return str(fn.get("name") or "")


def inject_task_model_profiles(
    tool_definitions: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Inject current registered profile IDs into a copy of the task schema."""
    choices = list_executor_model_profile_choices()
    profile_ids = [str(row.get("id") or "").strip() for row in choices]
    profile_ids = [value for value in profile_ids if value]
    if not profile_ids:
        return list(tool_definitions or [])

    details = []
    for row in choices:
        pid = str(row.get("id") or "").strip()
        if not pid:
            continue
        name = str(row.get("name") or pid).strip()
        model = str(row.get("model") or "").strip()
        capability = str(row.get("capability_description") or "").strip()
        details.append(
            f"- {pid}: {name} (model={model or 'unspecified'})"
            + (f" — {capability}" if capability else "")
        )

    out: List[Dict[str, Any]] = []
    for definition in tool_definitions or []:
        if _tool_name(definition) != "task":
            out.append(definition)
            continue
        task_definition = copy.deepcopy(definition)
        function = task_definition.get("function") or {}
        parameters = function.get("parameters") or {}
        properties = parameters.get("properties") or {}
        profile_property = properties.get("model_profile_id")
        if isinstance(profile_property, dict):
            base_description = str(profile_property.get("description") or "").split(
                "\n\nAvailable registered model profiles:", 1
            )[0]
            profile_property["description"] = (
                base_description
                + "\n\nAvailable registered model profiles:\n"
                + "\n".join(details)
                + "\nSelection rule: omit by default; for a specialized task choose the first configured profile "
                "whose capability description materially matches the task. Do not select merely because a profile exists."
            )
            profile_property["enum"] = profile_ids
            profile_property.pop("default", None)
        out.append(task_definition)
    return out


def filter_tools_for_session(
    tool_definitions: List[Dict[str, Any]],
    session_meta: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """按会话 metadata 过滤可供 LLM 使用的工具列表。"""
    meta = session_meta if isinstance(session_meta, dict) else {}
    if not meta.get("is_subagent"):
        depth = 0
    else:
        depth = max(1, int(meta.get("subagent_depth") or 1))
    stype = str(meta.get("subagent_type") or "generalPurpose").strip()
    readonly_strict = bool(meta.get("readonly_strict"))

    # Built-in and MCP definition dictionaries are immutable snapshots in the
    # agent loop.  Object identity therefore gives us a cheap, exact revision
    # key without serialising (potentially large) MCP JSON schemas every turn.
    source_definitions = tuple(tool_definitions or [])
    cache_key = (
        bool(meta.get("is_subagent")),
        str(meta.get("agent_team_member_id") or ""),
        depth,
        stype,
        readonly_strict,
        tuple(id(item) for item in source_definitions),
    )
    with _tool_filter_cache_lock:
        cached = _tool_filter_cache.get(cache_key)
        if cached is not None:
            _tool_filter_cache.move_to_end(cache_key)
            return list(cached[1])

    profile: Dict[str, Any] = {}
    if meta.get("is_subagent"):
        profile = SUBAGENT_TOOL_PROFILES.get(
            "readonly" if readonly_strict else stype,
            SUBAGENT_TOOL_PROFILES["generalPurpose"],
        )
    allowed = profile.get("allow")
    excluded = profile.get("exclude") or frozenset()
    exclude_mcp = bool(profile.get("exclude_mcp"))

    out: List[Dict[str, Any]] = []
    for defn in tool_definitions or []:
        name = _tool_name(defn)
        if not name:
            continue
        if name.startswith("mcp_"):
            if meta.get("is_subagent") and exclude_mcp:
                continue
            out.append(defn)
            continue
        if name == "task":
            if depth >= SUBAGENT_MAX_DEPTH or stype == "best-of-n-runner":
                continue
            out.append(defn)
            continue
        if name == "team" and meta.get("is_subagent") and not meta.get("agent_team_member_id"):
            continue
        if meta.get("is_subagent"):
            if allowed is not None and name not in allowed:
                continue
            if name in excluded:
                continue
        out.append(defn)
    with _tool_filter_cache_lock:
        # Keep the source tuple alive with the entry so Python cannot recycle
        # an excluded definition's id while the bounded cache entry exists.
        _tool_filter_cache[cache_key] = (source_definitions, tuple(out))
        _tool_filter_cache.move_to_end(cache_key)
        while len(_tool_filter_cache) > _TOOL_FILTER_CACHE_MAX:
            _tool_filter_cache.popitem(last=False)
    return out


def _resolve_attachment_path(raw: str) -> Optional[Path]:
    s = (raw or "").strip().strip('"').strip("'")
    if not s:
        return None
    p = Path(s)
    if not p.is_absolute():
        if s.startswith("/"):
            p = WORK_DIR / s.lstrip("/")
        else:
            p = WORK_DIR / s
    try:
        p = p.resolve()
        p.relative_to(WORK_DIR.resolve())
    except (ValueError, OSError):
        if not p.is_file():
            return None
    return p if p.is_file() else None


def load_file_attachments_block(paths: List[str]) -> str:
    """将附件路径读入 prompt 块（文本摘录；二进制仅元数据）。"""
    if not paths:
        return ""
    lines = ["### Attached files"]
    for raw in paths:
        p = _resolve_attachment_path(str(raw))
        if p is None:
            lines.append(f"- {raw!r}: (not found or outside WORK_DIR)")
            continue
        suffix = p.suffix.lower()
        if suffix in _IMAGE_SUFFIXES:
            try:
                size = p.stat().st_size
            except OSError:
                size = -1
            lines.append(
                f"- {p} [image, {size} bytes] — vision not enabled; path only."
            )
            continue
        if suffix in _TEXT_SUFFIXES or suffix == "":
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except Exception as e:
                lines.append(f"- {p}: read error: {e}")
                continue
            cap = 12000
            if len(text) > cap:
                text = text[:cap] + f"\n... [truncated, total {len(text)} chars]"
            lines.append(f"- {p}:\n```\n{text}\n```")
            continue
        try:
            size = p.stat().st_size
        except OSError:
            size = -1
        lines.append(f"- {p} [binary {suffix or 'unknown'}, {size} bytes] — not inlined.")
    return "\n".join(lines)


def build_subagent_user_message(
    *,
    prompt: str,
    description: str,
    subagent_type: str,
    is_resume: bool = False,
    readonly: bool = False,
    file_attachments: Optional[List[str]] = None,
    best_of_attempt: int = 0,
    best_of_total: int = 0,
) -> str:
    if readonly:
        access_mode = "严格只读（无写入、Shell、Web 或 MCP）"
    elif subagent_type == "explore":
        access_mode = "探索只读（可读文件和检索 Web，不可写入）"
    else:
        access_mode = "通用（仅在父 Agent 明确要求实施时修改）"
    parts = [
        f"## Subagent 任务：{description.strip() or '未命名'}",
        f"- 类型：`{subagent_type}`",
        f"- 权限模式：{access_mode}",
        f"- 会话模式：{'续接已有 subagent' if is_resume else '新任务'}",
    ]
    if best_of_total > 1 and best_of_attempt > 0:
        parts.append(
            f"- Best-of-N：尝试 **{best_of_attempt}/{best_of_total}**；"
            "采用真正不同的策略，不要只改写常规方案。"
        )
    if is_resume:
        parts.append("\n续接要求：沿用已验证的状态，只执行下面的追加指令；除非必要，不要重做已完成工作。")
    parts.append("\n### 父 Agent 指令\n")
    parts.append((prompt or "").strip())
    attach_block = load_file_attachments_block(list(file_attachments or []))
    if attach_block:
        parts.append("\n" + attach_block)
    parts.extend([
        "\n### 返回父 Agent\n",
        "最终回答必须独立可读，先给结果，再给关键证据；如有修改，列出文件和验证结果；"
        "如未完成，明确阻塞、已尝试内容和下一步。不要只汇报过程。",
    ])
    return "\n".join(parts)


def _get_subagent_final_result(child_id: str) -> str:
    try:
        if _runtime_v2_primary():
            from runtime_v2 import RuntimeUiProjection

            events = RuntimeUiProjection(
                session_manager.sessions_dir,
                path_resolver=getattr(session_manager, "_resolve_session_path", None),
            ).read_ui_events(child_id)
        else:
            events = session_manager._load_ui_events(child_id)
        for ev in reversed(events):
            if isinstance(ev, dict) and str(ev.get("type") or "") == "final":
                return str(ev.get("content") or "").strip()
    except Exception:
        pass
    return ""


def _running_checker(child_id: str) -> bool:
    return subagent_registry.is_running(child_id)


def _format_subagent_status_report(parent_session_id: str, resume_raw: str = "") -> str:
    flat = session_manager.list_subagents_flat(
        parent_session_id, running_checker=_running_checker
    )
    if resume_raw:
        child_id = session_manager.validate_subagent_resume(parent_session_id, resume_raw)
        if not child_id:
            return f"Error: 无法查询 subagent {resume_raw!r}（不存在或不属于当前会话）。"
        flat = [n for n in flat if n.get("id") == child_id]
        if not flat:
            return f"Error: subagent {resume_raw!r} 未找到。"
    if not flat:
        return "当前会话下没有 subagent。"
    running_n = sum(1 for n in flat if n.get("running"))
    completed_n = sum(1 for n in flat if n.get("status") == "completed")
    failed_n = sum(1 for n in flat if n.get("status") == "failed")
    interrupted_n = sum(1 for n in flat if n.get("status") == "interrupted")
    pending_n = sum(1 for n in flat if n.get("status") == "pending")
    lines = [
        f"Subagent 状态（共 {len(flat)} 个；运行中 {running_n}；"
        f"已完成 {completed_n}；失败 {failed_n}；中断 {interrupted_n}；待续 {pending_n}）",
        "",
    ]
    for n in flat:
        cid = str(n.get("id") or "")
        desc = str(n.get("description") or cid[:8])
        stype = str(n.get("subagent_type") or "")
        status = str(n.get("status") or ("running" if n.get("running") else "unknown"))
        ok = n.get("ok")
        err = str(n.get("error") or "").strip()
        preview = str(n.get("result_preview") or "").strip()
        lines.append(f"- **{cid}** [{stype}] {desc}")
        lines.append(f"  status={status}, running={bool(n.get('running'))}, ok={ok}")
        if err:
            lines.append(f"  error: {err[:400]}")
        if preview:
            lines.append(f"  preview: {preview[:240]}")
        lines.append("")
    lines.append(
        "提示：收集完整结果用 task(action='collect', resume=<ID>)；"
        "汇总全部结果用 task(action='collect')。"
    )
    return "\n".join(lines).rstrip()


async def _format_subagent_collect_result(parent_session_id: str, resume_raw: str = "") -> str:
    if resume_raw:
        child_id = session_manager.validate_subagent_resume(parent_session_id, resume_raw)
        if not child_id:
            return f"Error: 无法收集 subagent {resume_raw!r}（不存在或不属于当前会话）。"
        if subagent_registry.is_running(child_id):
            waited = await subagent_registry.wait(child_id)
            if subagent_registry.is_running(child_id):
                return (
                    f"Subagent {child_id} 仍在运行。"
                    f"请稍后 task(action='collect', resume={child_id!r}) 再试。"
                )
            if isinstance(waited, str) and waited.strip():
                return waited
        meta = session_manager._load_metadata(child_id)
        desc = str(
            meta.get("subagent_description") or meta.get("name") or child_id[:8]
        ).strip()
        stype = str(meta.get("subagent_type") or "").strip()
        body = _get_subagent_final_result(child_id)
        if not body:
            preview = ""
            for n in session_manager.list_subagents_flat(
                parent_session_id, running_checker=_running_checker
            ):
                if n.get("id") == child_id:
                    preview = str(n.get("result_preview") or "").strip()
                    break
            body = preview or "(无 final 输出；subagent 可能未完成或被中断)"
        session_manager.clear_pending_subagent_results_by_agent_ids(parent_session_id, [child_id])
        return _format_subagent_result(
            child_session_id=child_id,
            description=desc,
            subagent_type=stype,
            final_response=body,
            resumed=True,
        )

    flat = session_manager.list_subagents_flat(
        parent_session_id, running_checker=_running_checker
    )
    pending_rows = session_manager._load_pending_subagent_results(parent_session_id)
    if not flat and not pending_rows:
        return "当前会话下没有 subagent 结果可收集。"

    lines = [f"Subagent 结果汇总（共 {len(flat)} 个）", ""]
    for n in flat:
        cid = str(n.get("id") or "")
        desc = str(n.get("description") or cid[:8])
        status = str(n.get("status") or "")
        if n.get("running"):
            lines.append(f"### {cid} ({desc}) — **运行中**")
            lines.append(
                f"（尚未完成；用 task(action='status', resume={cid!r}) 查看状态，"
                f"完成后用 task(action='collect', resume={cid!r}) 收集结果。）"
            )
        else:
            body = _get_subagent_final_result(cid) or str(n.get("result_preview") or "").strip()
            if not body:
                body = str(n.get("error") or "(无输出)")
            lines.append(f"### {cid} ({desc}) — {status}")
            lines.append(body)
        lines.append("")

    unconsumed = [
        item
        for item in pending_rows
        if str(item.get("status") or "") == "completed"
        and str(item.get("result") or "").strip()
    ]
    if unconsumed:
        lines.append("---")
        lines.append("后台完成通知（尚未注入父对话）：")
        for item in unconsumed:
            aid = str(item.get("agent_id") or "")
            desc = str(item.get("description") or "")
            result = str(item.get("result") or "").strip()
            lines.append(f"- {aid} ({desc}): {result[:4000]}")
    read_ids = [str(n.get("id") or "").strip() for n in flat if not n.get("running")]
    read_ids.extend(str(item.get("agent_id") or "").strip() for item in unconsumed)
    session_manager.clear_pending_subagent_results_by_agent_ids(parent_session_id, read_ids)
    return "\n".join(lines).rstrip()


def _format_subagent_result(
    *,
    child_session_id: str,
    description: str,
    subagent_type: str,
    final_response: str,
    resumed: bool,
    status: str = "completed",
) -> str:
    if status == "running":
        return (
            f"Subagent running in background (ID: {child_session_id}, type: {subagent_type}, "
            f"description: {description}). "
            f"Use task(action='collect', resume={child_session_id!r}) to collect the result when finished, "
            f"or task(action='status') for overall status."
        )
    tag = "续接完成" if resumed else "完成"
    header = (
        f"Subagent {tag} (ID: {child_session_id}, type: {subagent_type}, "
        f"description: {description})"
    )
    body = (final_response or "").strip() or "(无正文输出)"
    return f"{header}\n\n{body}"


def _is_subagent_user_interrupt_final(text: str) -> bool:
    """react_node 因 interrupt 标志提前退出时的 final 文案。"""
    t = (text or "").strip()
    if not t:
        return False
    if t.startswith("任务已由用户中断"):
        return True
    return t in ("interrupted",)


def _git_worktree_add(run_dir: Path, attempt: int) -> Optional[Tuple[Path, str]]:
    """
    best-of-n：若 WORK_DIR 在 git 仓库内，为单次尝试创建 worktree。
    返回 (worktree_path, branch_name) 或 None。
    """
    run_dir.mkdir(parents=True, exist_ok=True)
    wt_path = run_dir / f"attempt_{attempt}_worktree"
    git_file = wt_path / ".git"
    if wt_path.exists() and git_file.exists():
        branch = f"subagent/best-of-restored-a{attempt}"
        return wt_path, branch
    try:
        git_root = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(WORK_DIR),
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if git_root.returncode != 0:
            return None
        branch = f"subagent/best-of-{uuid.uuid4().hex[:8]}-a{attempt}"
        r = subprocess.run(
            ["git", "worktree", "add", "-B", branch, str(wt_path), "HEAD"],
            cwd=str(WORK_DIR),
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if r.returncode != 0:
            logger.info("git worktree 跳过 attempt %s: %s", attempt, (r.stderr or r.stdout)[:200])
            return None
        logger.info("best-of-n worktree: %s branch=%s", wt_path, branch)
        return wt_path, branch
    except Exception as e:
        logger.debug("git worktree 不可用: %s", e)
        return None


def _git_worktree_remove(worktree_path: Path, branch: str = "") -> None:
    """移除 git worktree 及临时分支（忽略非致命错误）。"""
    wt = Path(worktree_path)
    branch_name = (branch or "").strip()
    git_cwd = str(WORK_DIR)
    if wt.is_dir() or wt.is_file():
        try:
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(wt)],
                cwd=git_cwd,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
        except Exception as e:
            logger.debug("git worktree remove 失败 %s: %s", wt, e)
        if wt.exists():
            try:
                shutil.rmtree(wt, ignore_errors=True)
            except Exception:
                pass
    if branch_name.startswith("subagent/"):
        try:
            subprocess.run(
                ["git", "branch", "-D", branch_name],
                cwd=git_cwd,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except Exception as e:
            logger.debug("git branch -D 失败 %s: %s", branch_name, e)


def _persist_worktree_meta(child_id: str, worktree_path: Path, branch: str) -> None:
    session_manager.patch_subagent_metadata(
        child_id,
        {
            "git_worktree_path": str(worktree_path),
            "git_worktree_branch": branch,
        },
    )


def cleanup_git_worktree_for_session(child_session_id: str) -> None:
    """按 subagent metadata 清理关联 git worktree。"""
    try:
        meta = session_manager._load_metadata(child_session_id)
    except Exception:
        return
    if not isinstance(meta, dict):
        return
    wt_raw = str(meta.get("git_worktree_path") or "").strip()
    branch = str(meta.get("git_worktree_branch") or "").strip()
    if not wt_raw:
        return
    _git_worktree_remove(Path(wt_raw), branch)
    session_manager.patch_subagent_metadata(
        child_session_id,
        {"git_worktree_path": "", "git_worktree_branch": ""},
    )


def cleanup_best_of_run_worktrees(parent_session_id: str, run_id: str) -> None:
    """清理某次 best-of-n 运行目录下全部 attempt worktree。"""
    if not run_id:
        return
    run_dir = (
        session_manager._get_session_path(parent_session_id)
        / "subagents"
        / "_best_of"
        / str(run_id)
    )
    if not run_dir.is_dir():
        return
    manifest = run_dir / "worktrees.json"
    entries: List[Dict[str, str]] = []
    if manifest.is_file():
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            if isinstance(data, list):
                entries = [x for x in data if isinstance(x, dict)]
        except Exception:
            entries = []
    for item in entries:
        _git_worktree_remove(
            Path(str(item.get("path") or "")),
            str(item.get("branch") or ""),
        )
    try:
        shutil.rmtree(run_dir, ignore_errors=True)
    except Exception:
        pass
    logger.info("已清理 best-of-n worktrees run_id=%s", run_id)


def _register_best_of_worktree(
    parent_session_id: str, run_id: str, attempt: int, wt_path: Path, branch: str
) -> None:
    run_dir = (
        session_manager._get_session_path(parent_session_id)
        / "subagents"
        / "_best_of"
        / str(run_id)
    )
    run_dir.mkdir(parents=True, exist_ok=True)
    manifest = run_dir / "worktrees.json"
    rows: List[Dict[str, str]] = []
    if manifest.is_file():
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            if isinstance(data, list):
                rows = [x for x in data if isinstance(x, dict)]
        except Exception:
            rows = []
    rows.append(
        {
            "attempt": str(attempt),
            "path": str(wt_path),
            "branch": branch,
            "child_hint": "",
        }
    )
    manifest.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")


async def _execute_subagent_run(
    *,
    child_id: str,
    parent_session_id: str,
    user_text: str,
    description: str,
    subagent_type: str,
    resumed: bool,
    parent_emit: Optional[Callable[[Dict[str, Any]], Any]] = None,
    run_in_background: bool = False,
    parent_run_id: str = "",
) -> str:
    """单次 subagent react_node 执行（可前台或后台）。"""
    subagent_run_id = uuid.uuid4().hex
    if not await subagent_registry.reserve(
        child_id,
        subagent_run_id,
        parent_session_id=parent_session_id,
    ):
        return (
            f"Subagent {child_id} is already running. "
            f"Use task(action='status', resume={child_id!r}) or "
            f"task(action='interrupt', resume={child_id!r})."
        )
    session_manager.clear_interrupt(child_id)

    prev_work, prev_llm, key_context = _load_subagent_run_histories(child_id)
    user_message = UserMessage(content=user_text)
    new_work = prev_work + [user_message]
    new_llm = prev_llm + [user_message]

    state: Dict[str, Any] = {
        "dialogue": derive_dialogue_from_assistant_history(new_llm),
        "work_messages": new_work,
        "llm_history": new_llm,
        "user_input": user_text,
        "final_response": "",
        "stream_events": [],
        "final_printed": False,
        "session_id": child_id,
        "llm_calls": [],
        "key_context": key_context,
        "_subagent_parent_session_id": parent_session_id,
        "_subagent_run_id": subagent_run_id,
        **({"_runtime_v2_parent_run_id": parent_run_id} if parent_run_id else {}),
    }
    todo_manager.sync_session_from_key_context(child_id, key_context or "")
    session_manager.append_ui_event(child_id, {"type": "user", "content": user_text})
    session_manager.upsert_subagent_task(
        parent_session_id,
        child_id,
        {
            "agent_id": child_id,
            "run_id": subagent_run_id,
            "parent_session_id": parent_session_id,
            "description": description,
            "subagent_type": subagent_type,
            "status": "running",
            "background": bool(run_in_background),
            "resumed": bool(resumed),
            "started_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    async def child_emit(ev: Dict[str, Any]) -> None:
        if should_persist_ui_event(ev, session_meta={"is_subagent": True}):
            session_manager.append_ui_event(child_id, ev)
        if parent_emit and should_forward_subagent_event_to_parent(ev):
            tagged = tag_subagent_forward_event(ev, agent_id=child_id)
            r = parent_emit(tagged)
            if hasattr(r, "__await__"):
                await r

    def _append_parent_pending_result(
        *,
        status: str,
        result: str = "",
        error: str = "",
        output_file: str = "",
        write_pending: bool = True,
    ) -> None:
        body = (result or "").strip()
        err = (error or "").strip()
        if not body and err:
            body = (
                f"Subagent {status} (ID: {child_id}, type: {subagent_type}, "
                f"description: {description})\n\nError: {err}"
            )
        if write_pending:
            session_manager.append_pending_subagent_result(
                parent_session_id,
                {
                    "agent_id": child_id,
                    "run_id": subagent_run_id,
                    "description": description,
                    "subagent_type": subagent_type,
                    "status": status,
                    "result": body,
                    "error": err,
                    "output_file": output_file,
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                    "parent_run_id": str(parent_run_id or "").strip(),
                },
            )
        session_manager.upsert_subagent_task(
            parent_session_id,
            child_id,
            {
                "status": status,
                "run_id": subagent_run_id,
                "result_preview": body[:500],
                "error": err,
                "output_file": output_file,
                "finished_at": datetime.now(timezone.utc).isoformat(),
            },
        )

    async def _run_core(*, background: bool = False, emit_start: bool = True) -> str:
        from agent_loop import react_node

        session_manager.clear_interrupt(child_id)

        if parent_emit and emit_start:
            r = parent_emit(
                {
                    "type": "subagent_start",
                    "agent_id": child_id,
                    "description": description,
                    "subagent_type": subagent_type,
                    "resumed": resumed,
                    "background": background,
                }
            )
            if hasattr(r, "__await__"):
                await r
        if parent_emit:
            r = parent_emit(
                {
                    "type": "user",
                    "content": user_text,
                    "agent_id": child_id,
                    "_subagent_forward": True,
                }
            )
            if hasattr(r, "__await__"):
                await r
        try:
            state_out = await react_node(state, emit=child_emit)
        except asyncio.CancelledError:
            session_manager.patch_subagent_metadata(
                child_id, {"subagent_ok": False, "subagent_error": "interrupted"}
            )
            output_file = session_manager.write_subagent_output(
                child_id,
                "Subagent interrupted.\n",
            )
            _append_parent_pending_result(
                status="interrupted",
                error="interrupted",
                output_file=output_file,
                write_pending=background,
            )
            if parent_emit:
                r = parent_emit(
                    {
                        "type": "subagent_finish",
                        "agent_id": child_id,
                        "description": description,
                        "ok": False,
                        "error": "interrupted",
                    }
                )
                if hasattr(r, "__await__"):
                    await r
            raise
        except Exception as e:
            logger.exception("subagent react_node 失败: %s", e)
            session_manager.patch_subagent_metadata(
                child_id, {"subagent_ok": False, "subagent_error": str(e)}
            )
            result_text = f"Error: subagent 执行异常：{e}"
            output_file = session_manager.write_subagent_output(child_id, result_text)
            _append_parent_pending_result(
                status="failed",
                result=result_text,
                error=str(e),
                output_file=output_file,
                write_pending=background,
            )
            if parent_emit:
                r = parent_emit(
                    {
                        "type": "subagent_finish",
                        "agent_id": child_id,
                        "description": description,
                        "ok": False,
                        "error": str(e),
                    }
                )
                if hasattr(r, "__await__"):
                    await r
            return result_text
        finally:
            cleanup_git_worktree_for_session(child_id)

        final_response = str(state_out.get("final_response") or "").strip()
        if final_response:
            session_manager.append_ui_event(child_id, {"type": "final", "content": final_response})
        _persist_subagent_run_state(child_id, state_out)
        interrupted = _is_subagent_user_interrupt_final(final_response)
        limit_reached = bool(state_out.get("react_limit_reached"))
        missing_final = not bool(final_response)
        pending_status = "interrupted" if interrupted else ("failed" if (limit_reached or missing_final) else "completed")
        subagent_error = "max_react_iter" if limit_reached else ("interrupted" if interrupted else ("missing_final" if missing_final else ""))
        result_text = _format_subagent_result(
            child_session_id=child_id,
            description=description,
            subagent_type=subagent_type,
            final_response=final_response,
            resumed=resumed,
            status=pending_status,
        )
        output_file = session_manager.write_subagent_output(child_id, result_text)
        _append_parent_pending_result(
            status=pending_status,
            result=result_text,
            error=subagent_error,
            output_file=output_file,
            write_pending=background,
        )
        if interrupted or limit_reached or missing_final:
            session_manager.patch_subagent_metadata(
                child_id, {"subagent_ok": False, "subagent_error": subagent_error}
            )
        else:
            session_manager.patch_subagent_metadata(
                child_id, {"subagent_ok": True, "subagent_error": ""}
            )
        if parent_emit:
            r = parent_emit(
                {
                    "type": "subagent_finish",
                    "agent_id": child_id,
                    "description": description,
                    "ok": not (interrupted or limit_reached or missing_final),
                    "subagent_type": subagent_type,
                    "result_preview": final_response[:500],
                    **({"error": subagent_error} if subagent_error else {}),
                }
            )
            if hasattr(r, "__await__"):
                await r
        return result_text

    async def _run_owned(*, background: bool, emit_start: bool) -> str:
        try:
            return await _run_core(background=background, emit_start=emit_start)
        finally:
            await subagent_registry.unregister(child_id, subagent_run_id)

    if run_in_background:
        if parent_emit:
            r = parent_emit(
                {
                    "type": "subagent_start",
                    "agent_id": child_id,
                    "description": description,
                    "subagent_type": subagent_type,
                    "resumed": resumed,
                    "background": True,
                }
            )
            if hasattr(r, "__await__"):
                await r
        task = asyncio.create_task(_run_owned(background=True, emit_start=False))
        if not await subagent_registry.attach(child_id, subagent_run_id, task):
            task.cancel()
            return f"Error: subagent {child_id} execution reservation was lost before start."

        async def _bg_done(t: asyncio.Task) -> None:
            try:
                await t
            except Exception:
                pass

        task.add_done_callback(lambda t: asyncio.create_task(_bg_done(t)))
        return _format_subagent_result(
            child_session_id=child_id,
            description=description,
            subagent_type=subagent_type,
            final_response="",
            resumed=resumed,
            status="running",
        )

    current_task = asyncio.current_task()
    if current_task is not None:
        if not await subagent_registry.attach(child_id, subagent_run_id, current_task):
            await subagent_registry.unregister(child_id, subagent_run_id)
            return f"Error: subagent {child_id} execution reservation was lost before start."
    return await _run_owned(background=False, emit_start=True)


async def _run_single_subagent(
    *,
    tool_args: Dict[str, Any],
    parent_session_id: str,
    parent_key_context: str = "",
    emit: Optional[Callable[[Dict[str, Any]], Any]] = None,
    best_of_run_id: str = "",
    best_of_attempt: int = 0,
    best_of_total: int = 0,
    parent_run_id: str = "",
) -> str:
    action = str(tool_args.get("action") or "").strip().lower()
    if action:
        if action not in {"start", "resume", "status", "collect", "interrupt"}:
            return "Error: task action must be start, resume, status, collect, or interrupt."
        resume_for_action = str(tool_args.get("resume") or "").strip()
        if action == "start" and resume_for_action:
            return "Error: task action=start must not include resume; use action=resume."
        if action in {"resume", "interrupt"} and not resume_for_action:
            return f"Error: task action={action} requires resume=<subagent id>."
        if action == "resume" and not str(tool_args.get("prompt") or "").strip():
            return (
                "Error: task action=resume requires a non-empty follow-up prompt. "
                "Use action=collect to read the existing result or action=status to inspect state."
            )
        requested_profile_id = str(tool_args.get("model_profile_id") or "").strip()
        creates_new_session = action == "start" or (
            action == "resume" and resume_for_action.lower() == "self"
        )
        if not creates_new_session and requested_profile_id:
            return (
                f"Error: task action={action} cannot change the model of an existing subagent; "
                "set model_profile_id only when creating a new subagent."
            )
        if action == "status":
            return _format_subagent_status_report(parent_session_id, resume_for_action)
        if action == "collect":
            return await _format_subagent_collect_result(parent_session_id, resume_for_action)
        if action == "interrupt":
            child_id = session_manager.validate_subagent_resume(parent_session_id, resume_for_action)
            if not child_id:
                return f"Error: cannot interrupt subagent {resume_for_action!r}; it does not exist or belongs to another session."
            if subagent_registry.is_running(child_id):
                await subagent_registry.cancel(child_id)
                session_manager.request_interrupt(child_id)
                return f"Subagent {child_id} interrupted."
            return f"Subagent {child_id} is not running."

    check_status = bool(tool_args.get("check_status"))
    collect_result = bool(tool_args.get("collect_result"))
    resume_raw = str(tool_args.get("resume") or "").strip()

    if check_status and collect_result:
        return "Error: check_status 与 collect_result 不能同时为 true。"
    if check_status:
        return _format_subagent_status_report(parent_session_id, resume_raw)
    if collect_result:
        return await _format_subagent_collect_result(parent_session_id, resume_raw)

    description = str(tool_args.get("description") or "").strip() or "subagent"
    prompt = str(tool_args.get("prompt") or "").strip()
    subagent_type = str(tool_args.get("subagent_type") or "generalPurpose").strip()
    readonly_strict = bool(tool_args.get("readonly"))
    run_in_background = bool(tool_args.get("run_in_background"))
    interrupt = bool(tool_args.get("interrupt"))
    model_profile_id = str(tool_args.get("model_profile_id") or "").strip()
    removed_model_override = str(tool_args.get("model") or "").strip()
    model_override = ""
    executor_llm_type_override = ""
    file_attachments = tool_args.get("file_attachments")
    if not isinstance(file_attachments, list):
        file_attachments = []

    if removed_model_override:
        return (
            "Error: task.model has been removed; register/select the model and pass "
            "model_profile_id instead."
        )
    if resume_raw and resume_raw.lower() != "self" and model_profile_id:
        return (
            "Error: an existing subagent keeps its original model; "
            "model_profile_id is only valid when creating a new subagent."
        )

    profile_choices = list_executor_model_profile_choices()
    valid_profile_ids = {
        str(row.get("id") or "").strip() for row in profile_choices
        if str(row.get("id") or "").strip()
    }
    if model_profile_id and model_profile_id not in valid_profile_ids:
        return (
            f"Error: unknown model_profile_id={model_profile_id!r}; "
            f"available IDs: {', '.join(sorted(valid_profile_ids)) or '(none)'}."
        )

    if not model_profile_id and (
        not resume_raw or resume_raw.lower() == "self"
    ):
        inherited = inherited_executor_selection(parent_session_id)
        model_profile_id = str(inherited.get("model_profile_id") or "").strip()
        model_override = str(inherited.get("executor_model") or "").strip()
        executor_llm_type_override = str(inherited.get("executor_llm_type") or "").strip()
        if model_profile_id not in valid_profile_ids:
            model_profile_id = str((profile_choices[0] if profile_choices else {}).get("id") or "").strip()

    if not prompt and not resume_raw:
        return (
            "Error: task 需要提供非空 prompt，或对已有 subagent 使用 resume，"
            "或使用 action=status / action=collect 查询状态与结果。"
        )

    if subagent_type not in SUBAGENT_TYPES:
        return (
            f"Error: 无效的 subagent_type={subagent_type!r}；"
            f"可选：{', '.join(sorted(SUBAGENT_TYPES))}。"
        )

    parent_depth = session_manager.get_session_subagent_depth(parent_session_id)
    if parent_depth + 1 > SUBAGENT_MAX_DEPTH and resume_raw.lower() != "self":
        return (
            f"Error: 已达 subagent 最大嵌套深度 {SUBAGENT_MAX_DEPTH}，"
            "请自行完成或拆分任务。"
        )

    resumed = False
    child_id: Optional[str] = None

    if resume_raw.lower() == "self":
        if not prompt:
            return "Error: resume=self 需要提供 prompt 作为 fork 后的新任务。"
        child_id = session_manager.fork_subagent_from_parent(
            parent_session_id,
            description,
            subagent_type,
            parent_depth + 1,
            model_profile_id=model_profile_id,
            executor_model=model_override,
            executor_llm_type=executor_llm_type_override,
            readonly_strict=readonly_strict,
        )
    elif resume_raw:
        child_id = session_manager.validate_subagent_resume(parent_session_id, resume_raw)
        if not child_id:
            return f"Error: 无法 resume subagent {resume_raw!r}（不存在或不属于当前会话）。"
        resumed = True
        if subagent_registry.is_running(child_id):
            if interrupt:
                await subagent_registry.cancel(child_id)
            else:
                waited = await subagent_registry.wait(child_id)
                if subagent_registry.is_running(child_id):
                    return (
                        f"Subagent {child_id} still running. "
                        f"Use task(action='status', resume={child_id!r}) or task(action='interrupt', resume={child_id!r})."
                    )
                if not prompt:
                    if isinstance(waited, str):
                        return waited
                    return (
                        f"Subagent {child_id} finished but returned no result. "
                        f"Use task(action='resume', resume={child_id!r}, prompt=...) to follow up."
                    )
            session_manager.clear_interrupt(child_id)
    else:
        child_id = session_manager.create_subagent_session(
            parent_session_id,
            description,
            subagent_type,
            parent_depth + 1,
            model_profile_id=model_profile_id,
            executor_model=model_override,
            executor_llm_type=executor_llm_type_override,
            readonly_strict=readonly_strict,
            best_of_run_id=best_of_run_id,
            best_of_attempt=best_of_attempt,
        )

        # 继承父 key_context 到子会话，使 subagent 在 SystemMessage 中自然获得上下文
        _save_initial_subagent_key_context(child_id, parent_key_context)

    assert child_id

    # best-of-n worktree hint in prompt
    worktree_note = ""
    if best_of_run_id and best_of_attempt > 0:
        run_dir = (
            session_manager._get_session_path(parent_session_id)
            / "subagents"
            / "_best_of"
            / best_of_run_id
        )
        wt_info = _git_worktree_add(run_dir, best_of_attempt)
        if wt_info is not None:
            wt_path, branch = wt_info
            _persist_worktree_meta(child_id, wt_path, branch)
            _register_best_of_worktree(
                parent_session_id, best_of_run_id, best_of_attempt, wt_path, branch
            )
            worktree_note = f"\n\nGit worktree（本尝试）: `{wt_path}` — 优先在此目录内修改/验证。"

    user_text = build_subagent_user_message(
        prompt=(prompt or "请继续并完成先前任务。") + worktree_note,
        description=description,
        subagent_type=subagent_type,
        is_resume=resumed,
        readonly=readonly_strict,
        file_attachments=[str(x) for x in file_attachments],
        best_of_attempt=best_of_attempt,
        best_of_total=best_of_total,
    )

    return await _execute_subagent_run(
        child_id=child_id,
        parent_session_id=parent_session_id,
        user_text=user_text,
        description=description,
        subagent_type=subagent_type,
        resumed=resumed,
        parent_emit=emit,
        run_in_background=run_in_background,
        parent_run_id=parent_run_id,
    )


async def _run_best_of_n(
    *,
    tool_args: Dict[str, Any],
    parent_session_id: str,
    parent_key_context: str = "",
    emit: Optional[Callable[[Dict[str, Any]], Any]] = None,
    parent_run_id: str = "",
) -> str:
    n = int(tool_args.get("n") or SUBAGENT_BEST_OF_N)
    n = max(2, min(8, n))
    run_id = uuid.uuid4().hex[:10]
    base_prompt = str(tool_args.get("prompt") or "").strip()
    if not base_prompt:
        return "Error: best-of-n-runner 需要非空 prompt。"

    run_in_background = bool(tool_args.get("run_in_background"))
    description = str(tool_args.get("description") or "best-of-n").strip()

    async def one_attempt(i: int) -> str:
        args = copy.deepcopy(tool_args)
        args["subagent_type"] = "generalPurpose"
        args["run_in_background"] = False
        args["description"] = f"{description} #{i + 1}"
        args["prompt"] = (
            f"{base_prompt}\n\n"
            f"[Best-of-{n} attempt {i + 1}/{n}: use a **distinct** strategy from other attempts.]"
        )
        return await _run_single_subagent(
            tool_args=args,
            parent_session_id=parent_session_id,
            parent_key_context=parent_key_context,
            emit=None,
            best_of_run_id=run_id,
            best_of_attempt=i + 1,
            best_of_total=n,
            parent_run_id=parent_run_id,
        )

    if run_in_background:
        session_manager.upsert_subagent_task(
            parent_session_id,
            run_id,
            {
                "agent_id": run_id,
                "parent_session_id": parent_session_id,
                "description": description,
                "subagent_type": "best-of-n-runner",
                "status": "running",
                "background": True,
                "started_at": datetime.now(timezone.utc).isoformat(),
            },
        )

        async def _bg_best_of() -> None:
            try:
                results = await asyncio.gather(
                    *[one_attempt(i) for i in range(n)],
                    return_exceptions=True,
                )
                combined = _format_best_of_results(run_id, description, results)
                output_file = session_manager.write_subagent_task_output(
                    parent_session_id,
                    run_id,
                    combined,
                )
                session_manager.upsert_subagent_task(
                    parent_session_id,
                    run_id,
                    {
                        "status": "completed",
                        "result_preview": combined[:500],
                        "output_file": output_file,
                        "finished_at": datetime.now(timezone.utc).isoformat(),
                        "parent_run_id": str(parent_run_id or "").strip(),
                    },
                )
                session_manager.append_pending_subagent_result(
                    parent_session_id,
                    {
                        "agent_id": run_id,
                        "description": description,
                        "subagent_type": "best-of-n-runner",
                        "status": "completed",
                        "result": combined,
                        "output_file": output_file,
                        "finished_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
                if emit:
                    r = emit(
                        {
                            "type": "subagent_finish",
                            "agent_id": run_id,
                            "description": description,
                            "ok": True,
                            "subagent_type": "best-of-n-runner",
                            "result_preview": combined[:500],
                        }
                    )
                    if hasattr(r, "__await__"):
                        await r
            except Exception as e:
                err = f"Error: best-of-n-runner 执行异常：{e}"
                output_file = session_manager.write_subagent_task_output(
                    parent_session_id,
                    run_id,
                    err,
                )
                session_manager.upsert_subagent_task(
                    parent_session_id,
                    run_id,
                    {
                        "status": "failed",
                        "error": str(e),
                        "result_preview": err[:500],
                        "output_file": output_file,
                        "finished_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
                session_manager.append_pending_subagent_result(
                    parent_session_id,
                    {
                        "agent_id": run_id,
                        "description": description,
                        "subagent_type": "best-of-n-runner",
                        "status": "failed",
                        "result": err,
                        "error": str(e),
                        "output_file": output_file,
                        "finished_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
                if emit:
                    r = emit(
                        {
                            "type": "subagent_finish",
                            "agent_id": run_id,
                            "description": description,
                            "ok": False,
                            "subagent_type": "best-of-n-runner",
                            "error": str(e),
                        }
                    )
                    if hasattr(r, "__await__"):
                        await r
            finally:
                cleanup_best_of_run_worktrees(parent_session_id, run_id)

        task = asyncio.create_task(_bg_best_of())
        await subagent_registry.register(run_id, task, parent_session_id=parent_session_id)
        return (
            f"Best-of-{n} subagents started in background (run_id: {run_id}, description: {description}). "
            f"Results will appear in pending notifications when all attempts finish."
        )

    if emit:
        r = emit(
            {
                "type": "subagent_start",
                "description": description,
                "subagent_type": "best-of-n-runner",
                "best_of_n": n,
                "run_id": run_id,
            }
        )
        if hasattr(r, "__await__"):
            await r

    try:
        results = await asyncio.gather(
            *[one_attempt(i) for i in range(n)],
            return_exceptions=True,
        )
        return _format_best_of_results(run_id, description, results)
    finally:
        cleanup_best_of_run_worktrees(parent_session_id, run_id)


def _format_best_of_results(run_id: str, description: str, results: List[Any]) -> str:
    lines = [
        f"Best-of-N complete (run_id: {run_id}, description: {description})",
        "",
    ]
    for i, res in enumerate(results):
        lines.append(f"### Attempt {i + 1}")
        if isinstance(res, Exception):
            lines.append(f"Error: {res}")
        else:
            lines.append(str(res))
        lines.append("")
    lines.append("---")
    lines.append("请综合以上尝试，选出最佳方案或合并结论。")
    return "\n".join(lines)


async def run_subagent_task(
    *,
    tool_args: Dict[str, Any],
    parent_session_id: str,
    parent_key_context: str = "",
    emit: Optional[Callable[[Dict[str, Any]], Any]] = None,
    parent_run_id: str = "",
) -> str:
    """task 工具入口。"""
    stype = str(tool_args.get("subagent_type") or "generalPurpose").strip()
    if stype == "best-of-n-runner":
        return await _run_best_of_n(
            tool_args=tool_args,
            parent_session_id=parent_session_id,
            parent_key_context=parent_key_context,
            emit=emit,
            parent_run_id=parent_run_id,
        )
    return await _run_single_subagent(
        tool_args=tool_args,
        parent_session_id=parent_session_id,
        parent_key_context=parent_key_context,
        emit=emit,
        parent_run_id=parent_run_id,
    )
