"""
agent_subagent_events — subagent/UI 事件持久化与转发口径。

这里集中处理“哪些事件属于当前 session 的可回放 UI 历史”，避免
agent_loop 与 agent_subagent 各自维护一份相似但不完全一致的过滤规则。
"""

from __future__ import annotations

from typing import Any, Dict, Optional


async def persist_execution_event(manager, session_id: str, event: Dict[str, Any]) -> Dict[str, Any]:
    """Persist execution updates before their live presentation, without model writes."""
    if event.get("_subagent_forward"):
        return event
    from runtime_v2.execution_journal import ExecutionJournal, STREAM_TYPES
    if event.get("type") not in STREAM_TYPES | {"llm_stream_aborted", "run_interrupted", "run_failed"}:
        return event
    from runtime_v2 import runtime_v2_primary
    if not runtime_v2_primary():
        return event
    import asyncio
    journal = ExecutionJournal(manager.sessions_dir, getattr(manager, "_resolve_session_path", None))
    return await asyncio.to_thread(journal.record, session_id, event)


SUBAGENT_PARENT_FORWARD_BLOCKED_TYPES = frozenset(
    {
        # Child-local session state. Forwarding these through the parent SSE stream
        # makes the frontend reducer apply them to the parent session before the
        # event is routed to the subagent card.
        "todo_plan",
        "context_tokens",
    }
)


def is_low_value_subagent_ui_event(ev: Dict[str, Any]) -> bool:
    """子会话 UI 不持久化空白/循环标记状态，避免卡片里出现噪声。"""
    if not isinstance(ev, dict):
        return False
    et = str(ev.get("type") or "")
    content = str(ev.get("content") or "").strip()
    if et == "status" and (
        not content
        or content == "New Agent Loop Start"
        or content == "Loop finished"
        or content in {"Subagent Continuation Start", "任务已恢复，流程重启"}
    ):
        return True
    if et in ("warning", "error") and not content:
        return True
    return False


def should_persist_ui_event(
    ev: Any,
    *,
    session_meta: Optional[Dict[str, Any]] = None,
    low_value_subagent_events: bool = False,
) -> bool:
    """是否把事件写入当前 session 的 ui_events。"""
    if not ev or not isinstance(ev, dict):
        return False
    if ev.get("_skip_persist"):
        return False
    if ev.get("ephemeral"):
        return False
    if ev.get("_subagent_forward"):
        return False
    meta = session_meta if isinstance(session_meta, dict) else {}
    if (
        low_value_subagent_events
        or bool(meta.get("is_subagent"))
    ) and is_low_value_subagent_ui_event(ev):
        return False
    return True


def should_forward_subagent_event_to_parent(ev: Any) -> bool:
    """Whether a child event belongs in the parent live stream."""
    if not ev or not isinstance(ev, dict):
        return False
    et = str(ev.get("type") or "")
    if et in SUBAGENT_PARENT_FORWARD_BLOCKED_TYPES:
        return False
    return True


def tag_subagent_forward_event(ev: Dict[str, Any], *, agent_id: str) -> Dict[str, Any]:
    """将子会话事件标记为向父级实时转发的事件。"""
    tagged = dict(ev)
    if not (tagged.get("_subagent_forward") and tagged.get("agent_id")):
        tagged["agent_id"] = agent_id
    tagged["_subagent_forward"] = True
    return tagged
