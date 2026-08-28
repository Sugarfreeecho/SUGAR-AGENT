"""Trusted host adapter for the bundled Agent Team workflow."""
from __future__ import annotations

import os
from typing import Any, Mapping


async def _invoke_team(context, arguments: Mapping[str, Any]):
    from agent_team.tools import execute_team_tool
    from tool_registry import ToolOutcome

    try:
        result = await context.service("await_steerable")(
            execute_team_tool(
                dict(arguments),
                session_id=context.session_id,
                session_meta=context.service("session_meta"),
                parent_key_context=context.state.get("key_context", ""),
                emit=context.services.get("raw_emit"),
                parent_run_id=context.run_id,
                parent_runtime_config=dict(
                    context.state.get("_last_prompt_runtime_config") or {}
                ),
            ),
            "tool_extension",
        )
    except Exception as exc:
        if context.service("should_propagate_exception")(exc):
            raise
        message = f"Agent Team error: {exc}"
        return ToolOutcome.failed("team_error", message, content=message)
    return ToolOutcome.completed(result)


def tool_definitions(context, plugin):
    from host_tool_registry import host_tool_invokers
    from tool_execution_policy import ToolExecutionPolicy

    enabled = lambda: bool(context["is_enabled"](plugin.plugin_id))
    host_tool_invokers.register(
        "team",
        _invoke_team,
        replace=True,
        enabled=enabled,
        owner=plugin.plugin_id,
        policy=ToolExecutionPolicy(effect="control", interruptibility="cooperative"),
    )
    meta = dict(context.get("session_meta") or {})
    if meta.get("is_subagent") and not meta.get("agent_team_member_id"):
        return []
    return [{
        "type": "function",
        "function": {
            "name": "team",
            "description": "Manage the optional durable Agent Team. The root agent leads; members may coordinate, claim work, and report results.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": [
                        "status", "create", "spawn_member", "dispatch", "remove_member",
                        "set_member_state", "create_task", "claim_task", "release_task",
                        "update_task", "send_message", "read_inbox", "consume_message",
                        "shutdown", "complete_shutdown", "archive", "auto_schedule"
                    ]},
                    "title": {"type": "string"}, "name": {"type": "string"},
                    "role": {"type": "string"}, "prompt": {"type": "string"},
                    "model_profile_id": {"type": "string"}, "readonly": {"type": "boolean"},
                    "member_id": {"type": "string"}, "task_id": {"type": "string"},
                    "description": {"type": "string"},
                    "priority": {"type": "string", "enum": ["low", "normal", "high", "urgent"]},
                    "depends_on": {"type": "array", "items": {"type": "string"}},
                    "status": {"type": "string", "enum": [
                        "starting", "idle", "working", "waiting_permission", "stopping",
                        "stopped", "failed", "pending", "in_progress", "blocked",
                        "completed", "cancelled"
                    ]},
                    "result": {"type": "string"}, "detail": {"type": "string"},
                    "reason": {"type": "string"},
                    "recipient_ids": {"type": "array", "items": {"type": "string"}},
                    "content": {"type": "string"}, "message_id": {"type": "string"},
                    "reply_to": {"type": "string"}, "include_consumed": {"type": "boolean"},
                    "run_in_background": {"type": "boolean"}
                },
                "required": ["action"],
                "additionalProperties": False
            }
        }
    }]


def _service(context):
    from agent_team.service import AgentTeamService

    manager = context["session_manager"]
    return AgentTeamService(
        manager.repository.sessions_dir,
        path_resolver=manager._resolve_session_path,
    )


def install(app, context, _plugin):
    from fastapi import APIRouter, Depends, HTTPException
    from agent_team.api import create_agent_team_router
    from plugins.host import bundled_host_plugin_enabled

    # Plugin enablement replaces the old duplicate feature toggle.
    os.environ["AGENT_TEAM_ENABLED"] = "1"
    manager = context["session_manager"]
    async def require_enabled():
        if not bundled_host_plugin_enabled(_plugin.plugin_id):
            raise HTTPException(status_code=404, detail="plugin disabled")

    guarded = APIRouter(dependencies=[Depends(require_enabled)])
    guarded.include_router(
        create_agent_team_router(
            lambda: _service(context),
            session_exists=lambda session_id: bool(manager.get_session_summary(session_id)),
        )
    )
    app.include_router(guarded)


async def start(_context, _plugin):
    from agent_team.tools import start_auto_scheduler

    await start_auto_scheduler()


async def stop(_context, _plugin):
    from agent_team.tools import stop_auto_scheduler

    await stop_auto_scheduler()
