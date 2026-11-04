"""Trusted lifecycle adapter for the bundled Goal workflow."""
from __future__ import annotations

import asyncio
import json
from functools import partial
from typing import Any, Mapping

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from session_event_bus import publish_session_event


async def _invoke_goal(context, arguments: Mapping[str, Any]):
    from agent_goal import GoalError, manager_for, model_goal_view
    from agent_fact_commit import run_fact_commit
    from tool_registry import ToolOutcome

    tool_name = str(context.service("tool_name") or "")
    continuing = tool_name == "update_goal" and str(arguments.get("status") or "").strip().lower() == "continue"
    try:
        session_manager = context.service("session_manager")
        manager = manager_for(session_manager)
        if tool_name == "create_goal":
            operation = partial(manager.create,
                context.session_id,
                str(arguments.get("objective") or ""),
                arguments.get("token_budget"),
                actor="model",
                run_id=context.run_id,
            )
        elif tool_name == "get_goal":
            operation = partial(manager.get, context.session_id)
        elif tool_name == "update_goal":
            if continuing:
                operation = partial(manager.user_action,
                    context.session_id, "resume",
                    additional_budget=arguments.get("additional_budget"),
                    reason=str(arguments.get("reason") or ""),
                    actor="model", run_id=context.run_id,
                )
            else:
                if arguments.get("additional_budget") is not None:
                    raise GoalError("additional_budget is only supported with status=continue.")
                operation = partial(manager.update_status,
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
        goal = await run_fact_commit(operation, trace_state=context.state)
        if continuing:
            await asyncio.to_thread(session_manager.clear_interrupt, context.session_id)
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
        # The model gets the projected view; metadata below still reads the
        # durable record (completion_judge_requested is host-only).
        json.dumps({"goal": model_goal_view(goal)}, ensure_ascii=False),
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
            "Use status=continue to resume an existing paused or blocked goal, like the play button, when the user asks to resume or a reported blocker has been resolved. Respect user-requested pauses; resume a manually paused goal only when the user asks. Supply additional_budget only when explicitly authorized by the user. Use completed to request independent Judge verification after the objective is achieved, or blocked to report a genuinely repeated blocker. Judge done moves the goal to human review; Judge continue keeps it active.",
            {
                "status": {"type": "string", "enum": ["completed", "blocked", "continue"]},
                "reason": {"type": "string", "description": "Concrete verification evidence, repeated blocker reason, or why the goal can now continue."},
                "blocker_key": {"type": "string", "description": "Stable identifier for the same blocker across runs."},
                "additional_budget": {"type": "integer", "minimum": 1, "description": "Only for status=continue: optional user-authorized extra token budget; required if the existing budget is exhausted."},
            },
            ["status"],
        ),
    ]


def install(app, context, plugin):
    from plugin_page_assets import install_plugin_page_assets
    install_plugin_page_assets(app)
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

    async def read_goal(session_id: str, *, progress_only=False):
        try:
            from plugins.host import bundled_host_plugin_enabled

            if not bundled_host_plugin_enabled(plugin.plugin_id):
                return JSONResponse({"enabled": False, "goal": None}, status_code=404)
            enabled = goal_enabled()
            if not await asyncio.to_thread(session_manager.get_session_summary, session_id):
                return JSONResponse({"error": "session not found"}, status_code=404)
            goal = await asyncio.to_thread(manager_for(session_manager).get, session_id) if enabled else None
            runner = globals().get('_runner')
            if runner and hasattr(runner, 'progress_snapshot'):
                progress = await asyncio.to_thread(runner.progress_snapshot, session_id, goal)
            else:
                phase = (goal or {}).get('status')
                if phase == 'active':
                    phase = 'running' if goal.get('current_run_id') else 'waiting'
                progress = {'phase': phase, 'label': '正在执行' if phase == 'running' else '等待下一轮', 'since': None}
            body = {'enabled': enabled, 'goal_id': (goal or {}).get('id'),
                    'status': (goal or {}).get('status'), 'continuation': progress}
            if not progress_only:
                body['goal'] = goal
            return JSONResponse(body, headers={"Cache-Control": "no-store"})
        except Exception as exc:
            return JSONResponse({"enabled": False, "goal": None, "error": str(exc)}, status_code=503)

    @router.get("/sessions/{session_id}/goal")
    async def get_goal(session_id: str):
        return await read_goal(session_id)

    @router.get("/sessions/{session_id}/goal/progress")
    async def get_goal_progress(session_id: str):
        return await read_goal(session_id, progress_only=True)

    @router.post("/sessions/{session_id}/goal/{action}")
    async def control_goal(session_id: str, action: str, request: Request):
        from plugins.host import bundled_host_plugin_enabled

        if not bundled_host_plugin_enabled(plugin.plugin_id):
            return JSONResponse({"ok": False, "error": "plugin disabled"}, status_code=404)
        if not await asyncio.to_thread(session_manager.get_session_summary, session_id):
            return JSONResponse({"ok": False, "error": "session not found"}, status_code=404)
        return await _control_goal(session_manager, session_id, action, request)

    # 热重载：先摘掉上一轮注册的同名 APIRoute。include_router 会复制 route 对象，
    # 且 FastAPI 先注册先匹配，不摘掉旧处理器就会一直赢。
    from fastapi.routing import APIRoute

    stale_paths = {route.path for route in router.routes}
    app.router.routes[:] = [
        route for route in app.router.routes
        if not isinstance(route, APIRoute)
        or getattr(route, "path", "") not in stale_paths
    ]
    app.openapi_schema = None
    app.include_router(router)


async def _control_goal(session_manager, session_id: str, action: str, request: Request):
    from agent_goal import manager_for
    from agent_fact_commit import run_fact_commit

    if action not in {"create", "pause", "resume", "cancel", "edit", "delete", "review"}:
        return JSONResponse({"ok": False, "error": "unknown action"}, status_code=400)
    try:
        try:
            body = await request.json()
        except Exception:
            body = {}
        body = body if isinstance(body, dict) else {}
        manager = manager_for(session_manager)
        expected = {"expected_goal_id": str(body["expected_goal_id"])} if body.get("expected_goal_id") else {}
        if action == "create":
            operation = partial(manager.create, session_id, str(body.get("objective") or ""),
                                body.get("token_budget"), actor="user")
        elif action == "review":
            operation = partial(manager.review_completion,
                session_id, str(body.get("decision") or ""),
                objective=str(body.get("objective") or ""),
                judge_result=str(body.get("judge_result") or body.get("feedback") or ""),
                additional_budget=body.get("additional_budget"), actor="user",
                **expected,
            )
        else:
            kwargs = {"additional_budget": body.get("additional_budget"),
                      "reason": str(body.get("reason") or ""), "actor": "user"}
            kwargs.update(expected)
            if action == "edit":
                kwargs["objective"] = body.get("objective")
            operation = partial(manager.user_action, session_id, action, **kwargs)
        goal = await run_fact_commit(operation)
        # Pausing disables future Goal checks/continuations; the current run
        # keeps working. Cancelling retains its explicit stop behavior.
        if action == "cancel":
            session_manager.request_interrupt(session_id, reason=f"workflow_{action}")
        if action in {"create", "resume"} or (action == "review" and str(body.get("decision") or "").strip().lower() == "continue"):
            await asyncio.to_thread(session_manager.clear_interrupt, session_id)
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

    path = Path(__file__).with_name("runner.py")
    spec = importlib.util.spec_from_file_location("myagent_agent_goal_runner", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    globals()["_runner"] = module
    await module.start()


async def stop(_context, _plugin):
    module = globals().get("_runner")
    if module is not None:
        await module.stop()
