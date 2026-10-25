"""Bundled ACP transport integration through existing host/service seams."""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, HTTPException, Request


def _targets(plugin):
    from plugins.settings import PluginSettingsStore
    from acp_bridge.client import parse_targets
    return parse_targets(PluginSettingsStore().values(plugin).get("agents_json", "{}"))


async def _invoke(context, arguments, plugin):
    from acp_bridge.client import run_target
    from tool_registry import ToolOutcome

    targets = _targets(plugin)
    name = context.service("tool_name")
    if name == "acp_agents":
        if arguments:
            raise ValueError("acp_agents accepts no arguments")
        return ToolOutcome.completed(json.dumps({"agents": list(targets)}, ensure_ascii=False))
    if set(arguments) != {"agent", "prompt"} or arguments.get("agent") not in targets:
        raise ValueError("acp_task requires a configured agent ID and a prompt")
    try:
        result = await context.service("await_steerable")(
            run_target(targets[arguments["agent"]], arguments["prompt"],
                       str(context.service("security_workspace"))), "tool_extension")
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        # Neither child stderr nor protocol/HTTP exception payloads become model content.
        return ToolOutcome.failed("acp_task_failed", "ACP delegation failed", content=json.dumps(
            {"error": "ACP delegation failed", "category": type(exc).__name__}))
    content = json.dumps(result, ensure_ascii=False)
    if result["stop_reason"] != "end_turn":
        return ToolOutcome.failed("acp_task_incomplete", "ACP child did not complete", content=content)
    return ToolOutcome.completed(content)


def tool_definitions(context, plugin):
    from host_tool_registry import host_tool_invokers
    from tool_execution_policy import ToolExecutionPolicy
    from acp_bridge.mcp import definitions

    enabled = lambda: bool(context["is_enabled"](plugin.plugin_id))
    if not enabled():
        return []
    rows = definitions(str(context.get("session_meta", {}).get("id") or ""), enabled, plugin.plugin_id)
    targets = _targets(plugin)
    if not targets:
        return rows
    async def invoke(call_context, arguments):
        return await _invoke(call_context, arguments, plugin)
    for name in ("acp_agents", "acp_task"):
        host_tool_invokers.register(name, invoke, replace=True, owner=plugin.plugin_id, enabled=enabled,
            policy=ToolExecutionPolicy(effect="read" if name == "acp_agents" else "external_write",
                                       early_stream_safe=False, interruptibility="cooperative"))
    rows.append({"type": "function", "function": {"name": "acp_agents",
        "description": "List configured external agents available for delegated tasks.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False}}})
    rows.append({"type": "function", "function": {"name": "acp_task",
        "description": "Delegate a standalone task to a configured external agent in the current workspace. The child receives only this task, runs its own tools and model, and returns its answer. Parent conversation and tool restrictions are not inherited.",
        "parameters": {"type": "object", "properties": {
            "agent": {"type": "string", "enum": list(targets)}, "prompt": {"type": "string", "minLength": 1, "maxLength": 200000}},
            "required": ["agent", "prompt"], "additionalProperties": False}}})
    return rows


def install(app, context, plugin):
    from acp_bridge import mcp

    router = APIRouter(prefix="/api/acp", tags=["ACP"])
    manager = context["session_manager"]

    def check(request):
        from plugins.host import bundled_host_plugin_enabled
        if not bundled_host_plugin_enabled(plugin.plugin_id):
            raise HTTPException(404, "ACP Agents plugin is disabled")
        if request.client and request.client.host not in {"127.0.0.1", "::1", "testclient"}:
            raise HTTPException(403, "ACP backend is loopback-only")
        return str(request.headers.get("X-MyAgent-ACP-Connection") or "")

    def write_origin(request):
        from plugin_web_gateway import PluginWebError, validate_plugin_write_origin
        try:
            validate_plugin_write_origin(request.method, origin=request.headers.get("origin", ""),
                scheme=request.url.scheme, host=request.headers.get("host", ""),
                fetch_site=request.headers.get("sec-fetch-site", ""), require_origin=True)
        except PluginWebError as exc:
            raise HTTPException(exc.status, exc.code) from exc

    @router.get("/status")
    async def status(request: Request):
        check(request)
        return {"protocol": "acp", "version": 1}

    @router.post("/mcp/{session_id}")
    async def mount(session_id: str, request: Request):
        owner = check(request)
        write_origin(request)
        if not owner or len(owner) > 128:
            raise HTTPException(400, "missing ACP connection identity")
        raw = await request.body()
        if len(raw) > 1024 * 1024:
            raise HTTPException(413, "MCP declarations are too large")
        try:
            payload = json.loads(raw)
            path = await asyncio.to_thread(manager._resolve_session_path, session_id)
            if not path.is_dir():
                raise HTTPException(404, "session not found")
            metadata = await asyncio.to_thread(manager._load_metadata, session_id)
            from agent_harness import session_work_dir
            cwd = str(session_work_dir(session_id, metadata))
            await mcp.mount(session_id, owner, payload["servers"], cwd)
        except (ValueError, KeyError, TypeError) as exc:
            raise HTTPException(422, "invalid session MCP declarations") from exc
        return {"ok": True}

    @router.delete("/mcp/{session_id}")
    async def unmount(session_id: str, request: Request):
        owner = check(request)
        write_origin(request)
        try:
            await mcp.unmount(session_id, owner)
        except PermissionError as exc:
            raise HTTPException(403, "ACP connection does not own this attachment") from exc
        return {"ok": True}

    app.include_router(router)


async def stop(context, plugin):
    from acp_bridge.mcp import shutdown
    await shutdown()
