"""Trusted lifecycle adapter for the bundled Goal workflow."""
from __future__ import annotations

import json
from typing import Any, Mapping

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from session_event_bus import publish_session_event


async def _invoke_goal(context, arguments: Mapping[str, Any]):
    from agent_goal import GoalError, manager_for
    from tool_registry import ToolOutcome

    tool_name = str(context.service("tool_name") or "")
    try:
        manager = manager_for(context.service("session_manager"))
        if tool_name == "create_goal":
            goal = manager.create(
                context.session_id,
                str(arguments.get("objective") or ""),
                arguments.get("token_budget"),
                actor="model",
                run_id=context.run_id,
            )
        elif tool_name == "get_goal":
            goal = manager.get(context.session_id)
        elif tool_name == "update_goal":
            goal = manager.update_status(
                context.session_id,
                str(arguments.get("status") or ""),
                str(arguments.get("reason") or ""),
                report_id=context.run_id,
                blocker_key=str(arguments.get("blocker_key") or ""),
                actor="model",
                run_id=context.run_id,
            )
        else:
            return ToolOutcome.failed("unknown_goal_operation", tool_name)
    except (GoalError, ValueError) as exc:
        return ToolOutcome.failed("goal_error", str(exc))

    if isinstance(goal, dict):
        await context.publish(
            {
                "type": "extension_state_changed",
                "plugin_id": "agent-goal",
                "namespace": "goal",
                "action": tool_name,
                "ephemeral": True,
            }
        )
    lifecycle_events: list[str] = []
    if tool_name == "create_goal":
        lifecycle_events.append("GoalCreated")
    elif tool_name == "update_goal" and isinstance(goal, dict):
        requested = str(arguments.get("status") or "").strip().lower()
        resulting = str(goal.get("status") or "").strip().lower()
        if requested == resulting == "completed":
            lifecycle_events.append("GoalCompleted")
        elif requested == resulting == "blocked":
            lifecycle_events.append("GoalBlocked")
    return ToolOutcome.completed(
        json.dumps({"goal": goal}, ensure_ascii=False),
        metadata={
            "lifecycle_events": lifecycle_events,
            "workflow_completion_requested": bool(
                tool_name == "update_goal"
                and isinstance(goal, dict)
                and goal.get("completion_judge_requested")
            ),
        },
    )


def _definition(name: str, description: str, properties: dict, required: list[str]):
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": False,
            },
        },
    }


def tool_definitions(context, plugin):
    from agent_goal import goal_enabled
    from host_tool_registry import host_tool_invokers

    enabled = lambda: bool(context["is_enabled"](plugin.plugin_id) and goal_enabled())
    for name in ("create_goal", "get_goal", "update_goal"):
        host_tool_invokers.register(
            name,
            _invoke_goal,
            replace=True,
            enabled=enabled,
            owner=plugin.plugin_id,
        )
    return [
        _definition(
            "create_goal",
            "Create one durable goal only when the user explicitly asks to start a goal. Set token_budget only when the user explicitly supplies one.",
            {
                "objective": {"type": "string", "description": "Concrete objective to pursue across continuation runs."},
                "token_budget": {"type": "integer", "minimum": 1, "description": "Optional user-specified total token budget."},
            },
            ["objective"],
        ),
        _definition(
            "get_goal",
            "Read the current goal, status, budgets, token and elapsed-time usage, and remaining token budget.",
            {},
            [],
        ),
        _definition(
            "update_goal",
            "Request independent Judge verification after the objective is actually achieved, or report a genuinely repeated blocker. Judge done moves the goal to human review; Judge continue keeps it active.",
            {
                "status": {"type": "string", "enum": ["completed", "blocked"]},
                "reason": {"type": "string", "description": "Concrete verification evidence, or the repeated blocker reason."},
                "blocker_key": {"type": "string", "description": "Stable identifier for the same blocker across runs."},
            },
            ["status"],
        ),
    ]


def install(app, context, plugin):
    from agent_goal import goal_enabled, manager_for

    session_manager = context["session_manager"]
    from workflow_extensions import SessionWorkflow, session_workflows

    session_workflows.register(
        SessionWorkflow(
            plugin_id="agent-goal",
            continuation_source="agent-goal",
            can_continue=lambda session_id: manager_for(session_manager).should_continue(session_id),
        ),
        replace=True,
    )
    router = APIRouter()

    @router.get("/sessions/{session_id}/goal")
    async def get_goal(session_id: str):
        try:
            from plugins.host import bundled_host_plugin_enabled

            if not bundled_host_plugin_enabled(plugin.plugin_id):
                return JSONResponse({"enabled": False, "goal": None}, status_code=404)
            enabled = goal_enabled()
            return JSONResponse(
                {"enabled": enabled, "goal": manager_for(session_manager).get(session_id) if enabled else None}
            )
        except Exception as exc:
            return JSONResponse({"enabled": False, "goal": None, "error": str(exc)}, status_code=503)

    @router.post("/sessions/{session_id}/goal/{action}")
    async def control_goal(session_id: str, action: str, request: Request):
        from plugins.host import bundled_host_plugin_enabled

        if not bundled_host_plugin_enabled(plugin.plugin_id):
            return JSONResponse({"ok": False, "error": "plugin disabled"}, status_code=404)
        return await _control_goal(session_manager, session_id, action, request)

    app.include_router(router)


async def _control_goal(session_manager, session_id: str, action: str, request: Request):
    from agent_goal import manager_for

    if action not in {"pause", "resume", "cancel", "edit", "delete", "review"}:
        return JSONResponse({"ok": False, "error": "unknown action"}, status_code=400)
    try:
        try:
            body = await request.json()
        except Exception:
            body = {}
        body = body if isinstance(body, dict) else {}
        manager = manager_for(session_manager)
        if action == "review":
            goal = manager.review_completion(
                session_id, str(body.get("decision") or ""),
                objective=str(body.get("objective") or ""),
                judge_result=str(body.get("judge_result") or body.get("feedback") or ""),
                additional_budget=body.get("additional_budget"), actor="user",
            )
        else:
            kwargs = {"additional_budget": body.get("additional_budget"),
                      "reason": str(body.get("reason") or ""), "actor": "user"}
            if action == "edit":
                kwargs["objective"] = body.get("objective")
            goal = manager.user_action(session_id, action, **kwargs)
        if action in {"pause", "cancel"}:
            session_manager.request_interrupt(session_id, reason=f"workflow_{action}")
        if action == "review" and str(body.get("decision") or "").strip().lower() == "continue":
            session_manager.clear_interrupt(session_id)
        public_goal = None if action == "delete" or goal.get("deleted") is True else goal
        event_action = (
            f"user_review_{str(body.get('decision') or '').strip().lower()}"
            if action == "review"
            else f"user_{action}"
        )
        await publish_session_event(session_id, {
            "type": "extension_state_changed", "plugin_id": "agent-goal",
            "namespace": "goal", "action": event_action, "ephemeral": True,
        })
        return JSONResponse({"ok": True, "goal": public_goal})
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=409)


# Stable plugin-owned seam for non-ASGI callers and tests.
control_goal = _control_goal


async def start(_context, _plugin):
    import importlib.util
    from pathlib import Path
    import webui

    path = Path(__file__).with_name("runner.py")
    spec = importlib.util.spec_from_file_location("myagent_agent_goal_runner", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    globals()["_runner"] = module
    await module.start(webui)


async def stop(_context, _plugin):
    module = globals().get("_runner")
    if module is not None:
        await module.stop()
