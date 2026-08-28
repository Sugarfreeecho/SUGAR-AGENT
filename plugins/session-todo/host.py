"""Trusted model-tool adapter for session-scoped Todo state."""
from __future__ import annotations

import json
from typing import Any, Mapping


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
    previous_items = list(manager._by_session.get(context.session_id, []))
    result = manager.update_for_session(context.session_id, normalized)
    context.state["_todo_rounds_since_update"] = 0
    items = list(manager._by_session.get(context.session_id, []))
    try:
        from session_todo_extension import write_todo_extension

        row = write_todo_extension(
            context.service("session_manager"), context.session_id, items,
            run_id=context.run_id, cleared=not items,
        )
    except Exception:
        manager._by_session[context.session_id] = previous_items
        raise
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
