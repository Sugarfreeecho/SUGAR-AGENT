"""Execution policy for persistent Agent Team members."""

from __future__ import annotations

import asyncio
import json
import os
import threading
from typing import Any

from .config import agent_team_enabled
from .service import AgentTeamService


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


def authorize_member_tool(
    service: AgentTeamService,
    session_meta: dict | None,
    tool_name: str,
    tool_args: Any,
) -> tuple[bool, str]:
    """Consume one-shot approval for protected member tools.

    Ordinary workspace edits are serialized but remain usable. Destructive or
    external-write operations require an explicit Team permission event.
    """

    identity = team_member_identity(session_meta)
    if identity is None:
        return True, ""
    if not agent_team_enabled():
        return False, "Agent Team was disabled while this member was running; stop and return control to the lead."
    if not _requires_permission(tool_name, tool_args):
        return True, ""
    root_id, member_id = identity
    resource = _tool_resource(tool_name, tool_args)
    permission = service.consume_permission(
        root_id,
        member_id=member_id,
        action=str(tool_name or ""),
        resource=resource,
    )
    if permission is not None:
        return True, ""
    try:
        team = service.read_team(root_id) or {}
        member = (team.get("members") or {}).get(member_id) or {}
        if member.get("state") != "waiting_permission":
            service.set_member_state(
                root_id,
                member_id,
                "waiting_permission",
                detail=f"permission required for {tool_name}: {resource}",
            )
    except Exception:
        pass
    request_hint = {
        "action": "request_permission",
        "permission_action": str(tool_name or ""),
        "resource": resource,
        "detail": "Explain why this protected operation is required, then stop and hand control to the lead.",
    }
    return False, (
        "Agent Team permission required. Call team with "
        + json.dumps(request_hint, ensure_ascii=False)
        + ". The lead must allow it and redispatch this member before the protected tool can run."
    )


def _write_tool_names() -> set[str]:
    raw = str(os.getenv("AGENT_TEAM_SERIAL_WRITE_TOOLS", "") or "").strip()
    if not raw:
        return set(_WRITE_TOOLS_DEFAULT)
    return {part.strip() for part in raw.split(",") if part.strip()}


def _requires_permission(tool_name: str, tool_args: Any) -> bool:
    name = str(tool_name or "").strip()
    configured = str(
        os.getenv("AGENT_TEAM_PERMISSION_TOOLS", "delete_file,web_download") or ""
    )
    protected = {part.strip() for part in configured.split(",") if part.strip()}
    if name in protected:
        return True
    if name.startswith(("mcp_", "plugin_")):
        try:
            if name.startswith("mcp_"):
                from agent_mcp import get_tool_contract
            else:
                from agent_extensions import get_plugin_tool_contract as get_tool_contract

            if str(get_tool_contract(name).get("effect") or "") in {
                "workspace_write",
                "external_write",
            }:
                return True
        except Exception:
            pass
    if name == "run_shell" and isinstance(tool_args, dict):
        return tool_args.get("restrict_to_workspace") is False
    return False


def _tool_resource(tool_name: str, tool_args: Any) -> str:
    args = tool_args if isinstance(tool_args, dict) else {}
    name = str(tool_name or "")
    if name.startswith(("mcp_", "plugin_")):
        try:
            if name.startswith("mcp_"):
                from agent_mcp import get_tool_contract
            else:
                from agent_extensions import get_plugin_tool_contract as get_tool_contract

            keys = get_tool_contract(name).get("resource_arguments") or []
            if isinstance(keys, str):
                keys = [keys]
            declared = {
                str(key): args.get(str(key))
                for key in keys
                if str(key) and args.get(str(key)) not in (None, "")
            }
            if declared:
                return json.dumps(
                    declared,
                    ensure_ascii=False,
                    sort_keys=True,
                )[:4000]
        except Exception:
            pass
    for key in (
        "path",
        "url",
        "command",
        "cmd",
        "destination",
        "output_path",
    ):
        value = str(args.get(key) or "").strip()
        if value:
            return value[:4000]
    try:
        return json.dumps(args, ensure_ascii=False, sort_keys=True)[:4000]
    except Exception:
        return name
