"""Trusted model-tool adapter for session-scoped Todo state."""
from __future__ import annotations

import json
import asyncio
import copy
import weakref
from typing import Any, Mapping


_update_locks = weakref.WeakKeyDictionary()


def _update_lock(manager, session_id):
    # Locks are owned by the invoking loop and live only while updates use them.
    locks = _update_locks.setdefault(asyncio.get_running_loop(), weakref.WeakValueDictionary())
    key = (id(manager), session_id)
    lock = locks.get(key)
    if lock is None:
        lock = locks[key] = asyncio.Lock()
    return lock


def _normalize(raw_items):
    if raw_items is None:
        return None, "missing required items"
    if isinstance(raw_items, str):
        try:
            raw_items = json.loads(raw_items)
        except (TypeError, ValueError) as exc:
            return None, f"invalid items JSON: {exc}"
    if isinstance(raw_items, Mapping):
        raw_items = [raw_items]
    if not isinstance(raw_items, list) or not raw_items:
        return None, "items must be a non-empty array"
    return raw_items, ""


async def _invoke_update_todo(context, arguments: Mapping[str, Any]):
    from tool_registry import ToolOutcome

    normalized, error = _normalize(arguments.get("items", arguments.get("todos")))
    if error:
        return ToolOutcome.failed("invalid_todo_items", error)
    manager = context.service("session_plan_store")
    from agent_fact_commit import run_fact_commit
    from session_todo_extension import write_todo_extension

    async with _update_lock(manager, context.session_id):
        # Validate/render using the same manager implementation, but stage its
        # session-local cache privately. Readers only see committed items.
        staged = copy.copy(manager)
        staged._by_session = {
            context.session_id: list(manager._by_session.get(context.session_id, []))
        }
        session_manager = context.service("session_manager")

        def write():
            result = staged.update_for_session(context.session_id, normalized)
            items = list(staged._by_session.get(context.session_id, []))
            row = write_todo_extension(
                session_manager, context.session_id, items,
                run_id=context.run_id, cleared=not items,
            )
            return result, items, row

        def committed(receipt):
            manager._by_session[context.session_id] = receipt[1]
            context.state["_todo_rounds_since_update"] = 0

        result, _items, row = await run_fact_commit(
            write, on_committed=committed, trace_state=context.state,
        )
    await context.publish({
        "type": "extension_state_changed", "plugin_id": "session-todo",
        "namespace": "plan", "revision": int(row.get("revision") or 0),
        "_runtime_v2_committed": True,
    })
    return ToolOutcome.completed(result)


def tool_definitions(context, plugin):
    from host_tool_registry import host_tool_invokers

    host_tool_invokers.register(
        "update_todo", _invoke_update_todo, replace=True,
        enabled=lambda: bool(context["is_enabled"](plugin.plugin_id)),
        owner=plugin.plugin_id,
    )
    return [{"type": "function", "function": {
        "name": "update_todo",
        "description": "Replace the active session plan. Multiple items may be in progress; the plan clears when all are completed.",
        "parameters": {"type": "object", "properties": {"items": {
            "type": "array", "items": {"type": "object", "properties": {
                "id": {"type": "string"}, "text": {"type": "string"},
                "status": {"type": "string", "enum": ["pending", "in_progress", "completed"]}
            }, "required": ["id", "text", "status"], "additionalProperties": False}
        }}, "required": ["items"], "additionalProperties": False}
    }}]
