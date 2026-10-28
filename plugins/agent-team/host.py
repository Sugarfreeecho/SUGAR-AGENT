"""Trusted host adapter for the bundled Agent Team workflow."""
from __future__ import annotations

import asyncio
import json
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
                    "state": {"type": "string", "enum": ["starting", "idle", "working", "waiting_permission", "stopping", "stopped", "failed"]},
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


async def _runtime_action(context, session_id, data):
    from agent_team.models import AgentTeamError
    from agent_team.tools import execute_team_tool
    from agent_subagent import run_subagent_task, subagent_registry
    from session_event_bus import publish_session_event

    service = _service(context)
    action = data["action"]
    if action in {"interrupt_member", "recover_member"}:
        team = await asyncio.to_thread(service.read_team, session_id) or {}
        member_id = str(data.get("member_id") or "")
        member = (team.get("members") or {}).get(member_id)
        if not member or member.get("removed"):
            raise AgentTeamError("member not found")
        child_id = str(member.get("child_session_id") or "")
        if action == "interrupt_member":
            if not subagent_registry.is_running(child_id):
                return await asyncio.to_thread(service.set_member_state, session_id, member_id, "stopped", detail="no live member execution; stopped by operator")
            await asyncio.to_thread(service.set_member_state, session_id, member_id, "stopping", detail="operator requested interrupt")
            result = await run_subagent_task(tool_args={"action": "interrupt", "resume": child_id},
                parent_session_id=session_id, parent_key_context="", emit=None, parent_run_id="team_console")
            if str(result).startswith("Error:"):
                raise AgentTeamError(str(result))
            if not subagent_registry.is_running(child_id):
                await asyncio.to_thread(service.set_member_state, session_id, member_id, "stopped", detail="interrupted by operator")
            return {"result": result}
        if subagent_registry.is_running(child_id):
            raise AgentTeamError("member is still running; interrupt it before recovery")
        if member.get("state") not in {"failed", "stopped", "working", "starting", "stopping"}:
            raise AgentTeamError("member does not need recovery")
        if team.get("status") != "active":
            raise AgentTeamError("team is not active")
        return await asyncio.to_thread(service.set_member_state, session_id, member_id, "idle", detail="recovered by operator")

    args = {key: data[key] for key in ("action", "name", "role", "prompt", "model_profile_id", "readonly", "member_id", "task_id") if key in data}
    if action == "dispatch":
        args["run_in_background"] = True
    async def emit(event):
        await publish_session_event(session_id, event)
    result = await execute_team_tool(args, session_id=session_id, parent_run_id="team_console", emit=emit)
    await publish_session_event(session_id, {"type": "extension_state_changed", "plugin_id": "agent-team", "namespace": "team", "ephemeral": True})
    return json.loads(result).get("data")


def install(app, context, _plugin):
    from plugin_page_assets import install_plugin_page_assets
    install_plugin_page_assets(app)
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
            runtime_action=lambda session_id, data: _runtime_action(context, session_id, data),
        )
    )

    # 热重载：先摘掉上一轮注册的同名 APIRoute。include_router 会复制 route 对象，
    # 且 FastAPI 先注册先匹配，不摘掉旧处理器就会一直赢。
    from fastapi.routing import APIRoute

    stale_paths = {route.path for route in guarded.routes}
    app.router.routes[:] = [
        route for route in app.router.routes
        if not isinstance(route, APIRoute)
        or getattr(route, "path", "") not in stale_paths
    ]
    app.openapi_schema = None
    app.include_router(guarded)


async def start(_context, _plugin):
    from agent_team.tools import start_auto_scheduler

    await start_auto_scheduler()


async def stop(_context, _plugin):
    from agent_team.tools import stop_auto_scheduler

    await stop_auto_scheduler()
