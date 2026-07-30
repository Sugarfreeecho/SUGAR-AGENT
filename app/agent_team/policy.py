"""Execution policy for persistent Agent Team members."""

from __future__ import annotations

import asyncio
import os
import threading
from typing import Any

_WRITE_TOOLS_DEFAULT = {
    "write_file",
    "apply_patch",
    "edit_file",
    "delete_file",
    "run_shell",
    "web_download",
}
_workspace_locks: dict[str, threading.Lock] = {}
_workspace_locks_guard = threading.Lock()


def team_member_identity(session_meta: dict | None) -> tuple[str, str] | None:
    meta = session_meta if isinstance(session_meta, dict) else {}
    root_id = str(meta.get("agent_team_root_session_id") or "").strip()
    member_id = str(meta.get("agent_team_member_id") or "").strip()
    if not root_id or not member_id:
        return None
    return root_id, member_id


def workspace_write_lock(session_meta: dict | None, tool_name: str) -> threading.Lock | None:
    identity = team_member_identity(session_meta)
    name = str(tool_name or "")
    contract_write = False
    if name.startswith(("mcp_", "plugin_")):
        try:
            if name.startswith("mcp_"):
                from agent_mcp import get_tool_contract
            else:
                from agent_extensions import get_plugin_tool_contract as get_tool_contract

            contract_write = (
                str(get_tool_contract(name).get("effect") or "")
                == "workspace_write"
            )
        except Exception:
            contract_write = False
    if identity is None or (name not in _write_tool_names() and not contract_write):
        return None
    root_id, _ = identity
    with _workspace_locks_guard:
        lock = _workspace_locks.get(root_id)
        if lock is None:
            # A primitive Lock may be acquired in an asyncio worker thread and
            # released by the event-loop thread. RLock is owner-bound and would
            # deadlock under that cross-thread pattern.
            lock = threading.Lock()
            _workspace_locks[root_id] = lock
        return lock


async def acquire_workspace_write_lock(lock: threading.Lock) -> None:
    """Acquire a primitive lock without leaking it when the waiter is cancelled."""

    waiter = asyncio.create_task(asyncio.to_thread(lock.acquire))
    try:
        await asyncio.shield(waiter)
    except asyncio.CancelledError:
        # ``to_thread`` cannot cancel a running Lock.acquire. Wait until that
        # worker owns the lock, release its orphaned acquisition, then preserve
        # cancellation for the caller.
        acquired = await waiter
        if acquired:
            lock.release()
        raise


def _write_tool_names() -> set[str]:
    raw = str(os.getenv("AGENT_TEAM_SERIAL_WRITE_TOOLS", "") or "").strip()
    if not raw:
        return set(_WRITE_TOOLS_DEFAULT)
    return {part.strip() for part in raw.split(",") if part.strip()}
