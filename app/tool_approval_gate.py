"""
Web UI 对工作区放宽类工具的前端确认闸门（run_shell restrict_to_workspace=False、web_download）。

/chat SSE 在服务侧 await 此处，直到浏览器 POST /sessions/{id}/tool-approval，
或会话 interrupt、超时。
"""

from __future__ import annotations

import asyncio
import os
import threading
import time
import uuid
from typing import Any, Dict, Tuple

from agent_harness import session_manager

_PENDING: Dict[Tuple[str, str], asyncio.Future] = {}
_PENDING_META: Dict[Tuple[str, str], Dict[str, Any]] = {}
_PENDING_LOCK = threading.RLock()

_WAIT_SEC = float(os.getenv("TOOL_UI_APPROVAL_WAIT_SEC", "3600"))


def new_approval_id() -> str:
    return uuid.uuid4().hex


def reject_pending_approvals_for_sessions(session_ids) -> None:
    ids = {(s or "").strip() for s in session_ids if (s or "").strip()}
    if not ids:
        return
    for (sid, _aid), fut in list(_PENDING.items()):
        if sid in ids and not fut.done():
            try:
                fut.get_loop().call_soon_threadsafe(fut.set_result, False)
            except RuntimeError:
                pass


def list_pending_approvals(session_id: str | None = None) -> list[dict]:
    """Return reconnect-safe metadata for approvals currently waiting in this process."""
    sid_filter = str(session_id or "").strip()
    with _PENDING_LOCK:
        rows = []
        for (sid, aid), fut in list(_PENDING.items()):
            if fut.done() or (sid_filter and sid != sid_filter):
                continue
            meta = dict(_PENDING_META.get((sid, aid)) or {})
            rows.append({"session_id": sid, "approval_id": aid, **meta})
        return rows


def resolve_tool_approval(session_id: str, approval_id: str, approved: bool) -> bool:
    """由 HTTP 路由调用：释放等待中的 Future。"""
    sid = str(session_id or "").strip()
    aid = str(approval_id or "").strip()
    if not sid or not aid:
        return False
    with _PENDING_LOCK:
        fut = _PENDING.get((sid, aid))
    if not fut or fut.done():
        return False
    try:
        fut.get_loop().call_soon_threadsafe(fut.set_result, bool(approved))
    except RuntimeError:
        return False
    return True


async def _interrupt_poll_until_done(session_id: str, fut: asyncio.Future) -> None:
    try:
        while not fut.done():
            await asyncio.sleep(0.25)
            try:
                if session_manager.is_interrupt_requested(session_id):
                    if not fut.done():
                        fut.set_result(False)
                    return
            except Exception:
                pass
    except asyncio.CancelledError:
        return


async def wait_tool_ui_approval_after_emit(
    session_id: str,
    approval_id: str,
    emit_coro,
    metadata: Dict[str, Any] | None = None,
) -> bool:
    """先登记 Future，再执行 emit_coro（发送 SSE），避免客户端极快 POST 时未命中 pending。"""
    loop = asyncio.get_running_loop()
    fut: asyncio.Future = loop.create_future()
    key = (str(session_id or "").strip(), str(approval_id or "").strip())
    if not key[0] or not key[1]:
        return False
    with _PENDING_LOCK:
        _PENDING[key] = fut
        _PENDING_META[key] = {"created_at": time.time(), **dict(metadata or {})}
    poll = asyncio.create_task(_interrupt_poll_until_done(session_id, fut))
    try:
        await emit_coro()
        return await asyncio.wait_for(fut, timeout=max(30.0, _WAIT_SEC))
    except asyncio.TimeoutError:
        if not fut.done():
            fut.set_result(False)
        return False
    finally:
        poll.cancel()
        try:
            await poll
        except asyncio.CancelledError:
            pass
        with _PENDING_LOCK:
            _PENDING.pop(key, None)
            _PENDING_META.pop(key, None)
