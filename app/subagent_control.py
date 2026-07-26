"""Durable control-plane helpers for ordinary task subagents.

This module deliberately stays independent from Agent Team enablement.  A task
subagent may use the same one-shot approval semantics even when Agent Team is
disabled: an exact (child, tool, resource) request is persisted under the
parent session, the parent resolves it, and the next matching invocation
consumes the approval once.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from agent_harness import session_manager


_DEFAULT_PROTECTED_TOOLS = "run_shell,delete_file,web_download"
_TERMINAL_PERMISSION_STATES = frozenset({"consumed", "denied"})
_EXTERNAL_WRITE_VERBS = frozenset(
    {
        "create",
        "update",
        "edit",
        "delete",
        "remove",
        "send",
        "post",
        "write",
        "upload",
        "move",
        "share",
        "resolve",
        "reply",
        "publish",
        "deploy",
    }
)


def _parent_subagents_dir(parent_session_id: str) -> Path:
    return Path(session_manager._get_session_path(parent_session_id)) / "subagents"


def _permissions_path(parent_session_id: str) -> Path:
    return _parent_subagents_dir(parent_session_id) / "permissions.json"


@contextmanager
def _permission_transaction(parent_session_id: str):
    root = _parent_subagents_dir(parent_session_id)
    root.mkdir(parents=True, exist_ok=True)
    lock_path = root / ".permissions.lock"
    with lock_path.open("a+b") as fh:
        if os.name == "nt":
            import msvcrt

            fh.seek(0, os.SEEK_END)
            if fh.tell() == 0:
                fh.write(b"0")
                fh.flush()
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if os.name == "nt":
                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def _load_rows(parent_session_id: str) -> List[Dict[str, Any]]:
    path = _permissions_path(parent_session_id)
    try:
        raw = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []
    except Exception:
        raw = []
    return [dict(item) for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []


def _save_rows(parent_session_id: str, rows: Iterable[Dict[str, Any]]) -> None:
    path = _permissions_path(parent_session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    trimmed = sorted(
        (dict(item) for item in rows if isinstance(item, dict)),
        key=lambda item: float(item.get("created_at") or 0.0),
    )[-1000:]
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(trimmed, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)


def _configured_patterns() -> List[str]:
    raw = str(os.getenv("SUBAGENT_PERMISSION_TOOLS", _DEFAULT_PROTECTED_TOOLS) or "")
    return [part.strip() for part in raw.split(",") if part.strip()]


def subagent_tool_requires_permission(tool_name: str, tool_args: Any) -> bool:
    """Return whether an ordinary subagent tool call needs parent approval."""

    name = str(tool_name or "").strip()
    if not name:
        return False
    if any(fnmatch.fnmatchcase(name, pattern) for pattern in _configured_patterns()):
        return True
    protect_external = str(
        os.getenv("SUBAGENT_PROTECT_EXTERNAL_WRITES", "1") or "1"
    ).strip().lower() not in {"0", "false", "no", "off"}
    if protect_external and (name.startswith("mcp_") or name.startswith("plugin_")):
        try:
            if name.startswith("mcp_"):
                from agent_mcp import get_tool_contract
            else:
                from agent_extensions import get_plugin_tool_contract as get_tool_contract

            effect = str(get_tool_contract(name).get("effect") or "")
            if effect in {"workspace_write", "external_write"}:
                return True
        except Exception:
            pass
        tokens = {
            token
            for token in name.lower().replace("-", "_").split("_")
            if token
        }
        return bool(tokens & _EXTERNAL_WRITE_VERBS)
    return False


def tool_permission_resource(tool_name: str, tool_args: Any) -> str:
    args = tool_args if isinstance(tool_args, dict) else {}
    if str(tool_name or "").startswith(("mcp_", "plugin_")):
        try:
            if str(tool_name or "").startswith("mcp_"):
                from agent_mcp import get_tool_contract
            else:
                from agent_extensions import get_plugin_tool_contract as get_tool_contract

            keys = get_tool_contract(tool_name).get("resource_arguments") or []
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
        "workdir",
    ):
        value = str(args.get(key) or "").strip()
        if value:
            return value[:4000]
    try:
        return json.dumps(args, ensure_ascii=False, sort_keys=True)[:4000]
    except Exception:
        return str(tool_name or "")[:4000]


def _signature(child_id: str, action: str, resource: str) -> str:
    raw = json.dumps(
        [str(child_id), str(action), str(resource)],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _new_request(
    *,
    child_id: str,
    action: str,
    resource: str,
    detail: str,
) -> Dict[str, Any]:
    now = time.time()
    return {
        "permission_id": f"subperm_{uuid.uuid4().hex}",
        "child_id": child_id,
        "action": action,
        "resource": resource,
        "detail": str(detail or "")[:8000],
        "signature": _signature(child_id, action, resource),
        "state": "pending",
        "created_at": now,
        "updated_at": now,
    }


def authorize_subagent_tool(
    session_meta: Optional[Dict[str, Any]],
    tool_name: str,
    tool_args: Any,
) -> Tuple[bool, str]:
    """Consume one matching approval or create a durable permission request."""

    meta = session_meta if isinstance(session_meta, dict) else {}
    if not meta.get("is_subagent") or meta.get("agent_team_member_id"):
        return True, ""
    if not subagent_tool_requires_permission(tool_name, tool_args):
        return True, ""

    parent_id = str(meta.get("parent_session_id") or "").strip()
    child_id = str(meta.get("session_id") or meta.get("id") or "").strip()
    if not child_id:
        # The canonical child ID is not stored in older metadata. Resolve it
        # from the session path field injected by the caller when available.
        child_id = str(meta.get("_active_session_id") or "").strip()
    if not parent_id or not child_id:
        return False, "Subagent permission denied: missing parent/child identity."

    action = str(tool_name or "").strip()
    resource = tool_permission_resource(action, tool_args)
    signature = _signature(child_id, action, resource)
    request: Optional[Dict[str, Any]] = None
    with _permission_transaction(parent_id):
        rows = _load_rows(parent_id)
        for item in reversed(rows):
            if str(item.get("signature") or "") != signature:
                continue
            state = str(item.get("state") or "pending")
            if state == "allowed":
                item["state"] = "consumed"
                item["consumed_at"] = time.time()
                item["updated_at"] = item["consumed_at"]
                _save_rows(parent_id, rows)
                return True, ""
            if state == "pending":
                request = item
                break
            if state == "denied":
                request = item
                break
        if request is None or str(request.get("state") or "") == "consumed":
            request = _new_request(
                child_id=child_id,
                action=action,
                resource=resource,
                detail="Ordinary subagent requested a protected tool operation.",
            )
            rows.append(request)
            _save_rows(parent_id, rows)

    permission_id = str(request.get("permission_id") or "")
    if str(request.get("state") or "") == "denied":
        return False, (
            f"Subagent permission denied by parent: {action} on {resource!r} "
            f"(permission_id={permission_id})."
        )
    return False, (
        "Subagent parent approval required. The exact operation was not executed. "
        f"permission_id={permission_id}; action={action}; resource={resource!r}. "
        "The parent may call task(action='resolve_permission', "
        f"resume={child_id!r}, permission_id={permission_id!r}, decision='allowed') "
        "and then steer or resume this same subagent to retry."
    )


def list_subagent_permissions(
    parent_session_id: str,
    *,
    child_id: str = "",
    include_terminal: bool = False,
) -> List[Dict[str, Any]]:
    with _permission_transaction(parent_session_id):
        rows = _load_rows(parent_session_id)
    target = str(child_id or "").strip()
    if target:
        rows = [item for item in rows if str(item.get("child_id") or "") == target]
    if not include_terminal:
        rows = [
            item
            for item in rows
            if str(item.get("state") or "pending") not in _TERMINAL_PERMISSION_STATES
        ]
    rows.sort(key=lambda item: float(item.get("created_at") or 0.0))
    return rows


def resolve_subagent_permission(
    parent_session_id: str,
    child_id: str,
    permission_id: str,
    decision: str,
    *,
    reason: str = "",
) -> Dict[str, Any]:
    target_child = str(child_id or "").strip()
    target_permission = str(permission_id or "").strip()
    resolution = str(decision or "").strip().lower()
    if resolution not in {"allowed", "denied"}:
        raise ValueError("decision must be allowed or denied")
    with _permission_transaction(parent_session_id):
        rows = _load_rows(parent_session_id)
        for item in rows:
            if str(item.get("permission_id") or "") != target_permission:
                continue
            if str(item.get("child_id") or "") != target_child:
                raise ValueError("permission does not belong to this subagent")
            current = str(item.get("state") or "pending")
            if current not in {"pending", resolution}:
                raise ValueError(f"permission is already {current}")
            if current == resolution:
                return dict(item)
            item["state"] = resolution
            item["reason"] = str(reason or "")[:4000]
            item["resolved_at"] = time.time()
            item["updated_at"] = item["resolved_at"]
            _save_rows(parent_session_id, rows)
            return dict(item)
    raise ValueError("permission not found")


def format_subagent_permissions(rows: Iterable[Dict[str, Any]]) -> str:
    items = [dict(item) for item in rows if isinstance(item, dict)]
    if not items:
        return "没有匹配的 subagent 权限请求。"
    lines = [f"Subagent 权限请求（{len(items)} 条）", ""]
    for item in items:
        lines.append(
            "- {permission_id} child={child_id} state={state} action={action}".format(
                permission_id=item.get("permission_id"),
                child_id=item.get("child_id"),
                state=item.get("state"),
                action=item.get("action"),
            )
        )
        resource = str(item.get("resource") or "").strip()
        if resource:
            lines.append(f"  resource: {resource[:1000]}")
    return "\n".join(lines)
