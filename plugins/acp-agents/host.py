"""Bundled ACP transport integration through existing host/service seams."""
from __future__ import annotations

import asyncio
import json
import re
import sys
import threading
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

# Opaque pagination hints are disposable UI state; session bindings/tasks stay durable.
_CATALOG_CURSORS = {}
_CATALOG_LOCK = threading.RLock()


def _catalog_key(origin, target, cwd):
    from acp_bridge.outbound import fingerprint, workspace_key
    return origin, target.name, fingerprint(target), workspace_key(cwd)


async def _session_action(service, origin, target, cwd, authority, *, cursor=None, new=False, close=None):
    try:
        return await service.sessions(origin, target, cwd, authority, cursor=cursor, new=new, close=close)
    except (ConnectionError, EOFError, BrokenPipeError):
        # Read-only catalog queries may reconnect once. Never repeat a create or prompt.
        if new or close:
            raise
        scope = _catalog_key(origin, target, cwd)
        keys = [key for key in service.peers if key[:3] == (origin, scope[2], scope[3])]
        if any(service.peers[key].busy for key in keys):
            raise  # Another prompt owns the transport; let its own cancellation finish.
        for key in keys:
            peer = service.peers.pop(key)
            await asyncio.wait_for(peer.close(), 12)
        return await service.sessions(origin, target, cwd, authority, cursor=cursor)


def _targets(plugin):
    from plugins.settings import PluginSettingsStore
    from acp_bridge.client import parse_targets
    return parse_targets(PluginSettingsStore().values(plugin).get("agents_json", "{}"))


async def _invoke(context, arguments, plugin):
    from acp_bridge.outbound import capture_route, on_host, service_for
    from tool_registry import ToolOutcome
    from jsonschema import Draft202012Validator

    targets = _targets(plugin)
    name = context.service("tool_name")
    if name == "acp_agents":
        if arguments:
            raise ValueError("acp_agents accepts no arguments")
        return ToolOutcome.completed(json.dumps({"agents": list(targets)}, ensure_ascii=False))
    definitions = _definitions(targets)
    schema = next(row["function"]["parameters"] for row in definitions if row["function"]["name"] == name)
    error = next(Draft202012Validator(schema).iter_errors(dict(arguments)), None)
    if error:
        raise ValueError("invalid ACP tool arguments: " + ".".join(map(str, error.absolute_path)))
    service = await service_for(context.service("session_manager"))
    origin = context.session_id
    cwd = str(context.service("security_workspace"))
    authority = capture_route(origin)
    try:
        if name == "acp_tasks":
            from acp_bridge.outbound import public_task
            result = {"tasks": [public_task(row, summary=True) for row in sorted(
                await asyncio.to_thread(service.store.rows, "tasks", origin), key=lambda row: row["created_at"], reverse=True)[:50]]}
        elif name in {"acp_task_get", "acp_task_cancel"}:
            if name == "acp_task_get":
                result = await on_host(lambda: service.get(origin, arguments["task_id"], arguments.get("after", 0)))
            else:
                result = await on_host(lambda: service.cancel(origin, arguments["task_id"]))
        elif name in {"acp_sessions", "acp_session_new", "acp_session_close"}:
            result = await context.service("await_steerable")(on_host(lambda: _session_action(service,
                origin, targets[arguments["agent"]], cwd, authority, cursor=arguments.get("cursor"),
                new=name == "acp_session_new", close=arguments.get("session_id") if name == "acp_session_close" else None)), "tool_extension")
            if name == "acp_sessions":
                key = _catalog_key(origin, targets[arguments["agent"]], cwd)
                with _CATALOG_LOCK:
                    if len(_CATALOG_CURSORS) >= 512 and key not in _CATALOG_CURSORS:
                        _CATALOG_CURSORS.pop(next(iter(_CATALOG_CURSORS)))
                    _CATALOG_CURSORS[key] = result.get("next_cursor")
        else:
            job = await on_host(lambda: service.submit(origin, targets[arguments["agent"]], cwd, authority,
                arguments["prompt"], session_id=arguments.get("session_id"), background=arguments.get("background", False),
                notify=arguments.get("notify", "final"), origin_run=context.run_id, tool_call_id=context.tool_call_id))
            if arguments.get("background", False):
                return ToolOutcome.completed(json.dumps(job, ensure_ascii=False))
            async def observe():
                cursor = 0
                while True:
                    value = await on_host(lambda: service.get(origin, job["task_id"], cursor))
                    for event in value.pop("events"):
                        cursor = event["seq"]
                        if event["type"] == "message":
                            await context.publish({"type": "status", "content": event["text"], "source": "acp-agents",
                                "task_id": job["task_id"], "phase": "progress", "ephemeral": True})
                    if value["status"] not in {"queued", "running"}:
                        return value
                    await asyncio.sleep(.25)
            try:
                result = await context.service("await_steerable")(observe(), "tool_extension")
            except asyncio.CancelledError:
                await asyncio.shield(on_host(lambda: service.cancel(origin, job["task_id"])))
                raise
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        # Neither child stderr nor protocol/HTTP exception payloads become model content.
        return ToolOutcome.failed("acp_task_failed", "ACP delegation failed", content=json.dumps(
            {"error": "ACP delegation failed", "category": type(exc).__name__}))
    content = json.dumps(result, ensure_ascii=False)
    if name == "acp_task" and result.get("status") != "succeeded":
        return ToolOutcome.failed("acp_task_incomplete", "ACP child did not complete", content=content)
    return ToolOutcome.completed(content)


def _definitions(targets):
    def definition(name, description, properties, required=()):
        return {"type": "function", "function": {"name": name, "description": description,
            "parameters": {"type": "object", "properties": properties, "required": list(required), "additionalProperties": False}}}
    agent = {"agent": {"type": "string", "enum": list(targets)}}
    session = {"session_id": {"type": "string", "minLength": 1, "maxLength": 512}}
    task = {"task_id": {"type": "string", "minLength": 1, "maxLength": 64}}
    return [
        definition("acp_agents", "List configured external ACP agent target IDs.", {}),
        definition("acp_sessions", "Query a configured agent's sessions in the current workspace and register them for explicit reuse. May launch its ACP adapter. Resume support depends on the peer.",
            {**agent, "cursor": {"type": "string", "maxLength": 4096}}, ["agent"]),
        definition("acp_session_new", "Explicitly create an external ACP session in the current workspace. Returns session_id for later acp_task calls; a live connection is retained.", agent, ["agent"]),
        definition("acp_session_close", "Release an external session connection without deleting its history. Cannot close a running prompt. Future reuse requires peer resume support.",
            {**agent, **session}, ["agent", "session_id"]),
        definition("acp_task", "Delegate a task to a configured ACP agent. Omit session_id to create a new session; supply a session ID from acp_sessions/acp_session_new to continue it. The child gets this task and workspace, not the parent transcript or tool restrictions. background=true returns task_id immediately; notify=final (default) sends the final result to this source conversation and wakes it, all also posts progress notices, none only stores results. Foreground calls return progress and final tool result without a duplicate callback. ACP v1 text chunks are progress; prompt completion determines the final result.",
            {**agent, **session, "prompt": {"type": "string", "minLength": 1, "maxLength": 200000},
             "background": {"type": "boolean"}, "notify": {"type": "string", "enum": ["final", "all", "none"]}}, ["agent", "prompt"]),
        definition("acp_tasks", "List ACP tasks belonging to this source conversation.", {}),
        definition("acp_task_get", "Read an ACP task's state, partial/final text and ordered progress events. after is an event cursor. Reading does not send another callback.",
            {**task, "after": {"type": "integer", "minimum": 0}}, ["task_id"]),
        definition("acp_task_cancel", "Cancel this conversation's ACP task, keeping its partial output and recorded outcome.", task, ["task_id"]),
    ]


def tool_definitions(context, plugin):
    from host_tool_registry import host_tool_invokers
    from tool_execution_policy import ToolExecutionPolicy
    from acp_bridge.mcp import definitions

    enabled = lambda: bool(context["is_enabled"](plugin.plugin_id))
    if not enabled():
        return []
    rows = definitions(str(context.get("session_meta", {}).get("id") or ""), enabled, plugin.plugin_id)
    targets = _targets(plugin)
    async def invoke(call_context, arguments):
        return await _invoke(call_context, arguments, plugin)
    definitions = [row for row in _definitions(targets) if targets or row["function"]["name"] in {"acp_agents", "acp_tasks", "acp_task_get", "acp_task_cancel"}]
    for definition in definitions:
        name = definition["function"]["name"]
        host_tool_invokers.register(name, invoke, replace=True, owner=plugin.plugin_id, enabled=enabled,
            policy=ToolExecutionPolicy(effect="read" if name in {"acp_agents", "acp_tasks", "acp_task_get"} else "external_write",
                                       early_stream_safe=False, interruptibility="cooperative"))
    return rows + definitions


def install(app, context, plugin):
    from acp_bridge import mcp
    from acp_bridge.connections import registry

    router = APIRouter(prefix="/api/acp", tags=["ACP"])
    manager = context["session_manager"]
    app.state.acp_route_signature = getattr(plugin, "content_signature", "")

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

    def authorize_session(request, sid, *, configure=False):
        from session_control.public import control_application
        from session_control.errors import ControlError
        try:
            control = control_application()
            principal = control.principal(request)
            control.service.authorize(principal, "session.mcp.configure" if configure else "session.attach", {"session_id": sid})
            return principal.id
        except ControlError as exc:
            raise HTTPException(exc.status, exc.code) from exc

    def principal(request):
        from session_control.public import control_application
        from session_control.errors import ControlError
        try:
            return control_application().principal(request)
        except ControlError as exc:
            raise HTTPException(exc.status, exc.code) from exc

    def local_view(request, *, admin=False):
        check(request)
        if request.headers.get("origin") or request.headers.get("sec-fetch-site"):
            from plugin_web_gateway import PluginWebError, validate_plugin_write_origin
            try:
                validate_plugin_write_origin("POST", origin=request.headers.get("origin", ""),
                    scheme=request.url.scheme, host=request.headers.get("host", ""),
                    fetch_site=request.headers.get("sec-fetch-site", ""))
            except PluginWebError as exc:
                raise HTTPException(exc.status, exc.code) from exc
        if request.headers.get("authorization"):
            caller = principal(request)
            if admin and not caller.admin:
                raise HTTPException(403, "ACP target settings require an administrator")
            return None if caller.admin else caller.id
        return None  # Same-origin local settings UI, like the host settings API.

    def connection_identity(request):
        connection_id = check(request)
        write_origin(request)
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", connection_id):
            raise HTTPException(400, "invalid ACP connection identity")
        return principal(request).id, connection_id

    async def small_json(request):
        raw = await request.body()
        if len(raw) > 64 * 1024:
            raise HTTPException(413, "ACP metadata is too large")
        try:
            return json.loads(raw)
        except ValueError as exc:
            raise HTTPException(422, "invalid JSON") from exc

    @router.get("/status")
    async def status(request: Request):
        check(request)
        return {"protocol": "acp", "version": 1, "connection_monitoring": True}

    @router.get("/connections")
    async def connections(request: Request):
        owner = local_view(request)
        snapshot = registry.snapshot(owner=owner)
        origin = str(request.base_url).rstrip("/")
        snapshot["launch"] = {"command": sys.executable,
            "args": [str(Path(__file__).resolve().parents[2] / "app" / "acp_stdio.py"), "--server-url", origin],
            "env_refs": ["MYAGENT_CONTROL_TOKEN"]}
        from fastapi.responses import JSONResponse
        return JSONResponse(snapshot, headers={"Cache-Control": "no-store"})

    @router.post("/connections")
    async def register_connection(request: Request):
        owner, connection_id = connection_identity(request)
        try:
            registry.register(owner, connection_id, await small_json(request))
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return {"ok": True}

    @router.post("/connections/heartbeat")
    async def heartbeat(request: Request):
        owner, connection_id = connection_identity(request)
        try:
            registry.heartbeat(owner, connection_id, await small_json(request))
        except KeyError as exc:
            raise HTTPException(404, "ACP connection is not registered") from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return {"ok": True}

    @router.delete("/connections")
    async def disconnect(request: Request):
        owner, connection_id = connection_identity(request)
        registry.disconnect(owner, connection_id)
        return {"ok": True}

    @router.get("/targets")
    async def targets(request: Request):
        local_view(request, admin=True)
        from plugins.settings import PluginSettingsStore
        return {"agents_json": PluginSettingsStore().values(plugin).get("agents_json", "{}")}

    @router.put("/targets")
    async def save_targets(request: Request):
        local_view(request, admin=True)
        write_origin(request)
        payload = await small_json(request)
        from acp_bridge.client import parse_targets
        from agent_extensions import update_plugin_settings
        try:
            if not isinstance(payload, dict) or set(payload) != {"agents_json"} or not isinstance(payload["agents_json"], str):
                raise ValueError("agents_json must be a JSON string")
            parsed = parse_targets(payload["agents_json"])
        except (ValueError, TypeError) as exc:
            raise HTTPException(422, "Invalid ACP target configuration: " + str(exc)) from exc
        await asyncio.to_thread(update_plugin_settings, plugin.plugin_id, {"agents_json": payload["agents_json"]})
        return {"ok": True, "agents_json": payload["agents_json"], "target_ids": list(parsed)}

    def source_context(request, origin):
        from agent_harness import session_work_dir
        from acp_bridge.outbound import capture_route
        if not isinstance(origin, str) or not origin or not manager.get_session_summary(origin):
            raise HTTPException(404, "source session not found")
        caller = principal(request) if request.headers.get("authorization") else None
        if caller:
            from session_control.public import control_application
            from session_control.errors import ControlError
            try:
                control_application().service.authorize(caller, "session.attach", {"session_id": origin})
            except ControlError as exc:
                raise HTTPException(exc.status, exc.code) from exc
        metadata = manager._load_metadata(origin)
        return str(session_work_dir(origin, metadata)), capture_route(origin, caller)

    @router.get("/outbound")
    async def outbound(request: Request, origin: str = ""):
        local_view(request)
        from acp_bridge.outbound import service_for, public_task, fingerprint, workspace_key
        sessions = await asyncio.to_thread(manager.list_sessions)
        parents = []
        for session in sessions:
            if session.get("is_subagent"):
                continue
            try:
                if request.headers.get("authorization"):
                    source_context(request, session["id"])
                parents.append({"id": session["id"], "name": str(session.get("name") or session["id"])[:200]})
            except HTTPException:
                continue
        targets = _targets(plugin)
        snapshot = {"parents": parents, "targets": list(targets), "tasks": [], "sessions": [], "next_cursors": {}}
        if origin:
            cwd, _ = source_context(request, origin)
            service = await service_for(manager)
            with _CATALOG_LOCK:
                snapshot["next_cursors"] = {name: _CATALOG_CURSORS.get(_catalog_key(origin, target, cwd)) for name, target in targets.items()}
            snapshot["tasks"] = [public_task(row, summary=True) for row in sorted(await asyncio.to_thread(service.store.rows, "tasks", origin),
                key=lambda row: row["created_at"], reverse=True)[:50]]
            for row in await asyncio.to_thread(service.store.rows, "sessions", origin):
                if row["cwd"] != workspace_key(cwd):
                    continue
                target = targets.get(row["agent"])
                snapshot["sessions"].append({key: value for key, value in row.items() if key != "fingerprint"})
                snapshot["sessions"][-1]["available"] = bool(target and row["fingerprint"] == fingerprint(target))
                snapshot["sessions"][-1]["connected"] = any(row["session_id"] in peer.active for key, peer in service.peers.items()
                    if key[:3] == (origin, row["fingerprint"], row["cwd"]))
        from fastapi.responses import JSONResponse
        return JSONResponse(snapshot, headers={"Cache-Control": "no-store"})

    @router.post("/outbound/requests")
    async def request_outbound(request: Request):
        local_view(request)
        write_origin(request)
        payload = await small_json(request)
        if not isinstance(payload, dict) or set(payload) - {"origin", "action", "arguments", "request_id"}:
            raise HTTPException(422, "invalid ACP request")
        origin, action = payload.get("origin"), payload.get("action")
        cwd, authority = source_context(request, origin)
        tool = {"list": "acp_sessions", "new": "acp_session_new", "close": "acp_session_close", "task": "acp_task"}.get(action)
        if tool is None or not isinstance(payload.get("arguments"), dict):
            raise HTTPException(422, "invalid ACP action")
        from jsonschema import Draft202012Validator
        schema = next(row["function"]["parameters"] for row in _definitions(_targets(plugin)) if row["function"]["name"] == tool)
        if next(Draft202012Validator(schema).iter_errors(payload["arguments"]), None):
            raise HTTPException(422, "invalid ACP action arguments")
        request_id = payload.get("request_id")
        if not isinstance(request_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,80}", request_id):
            raise HTTPException(422, "invalid request identity")
        from acp_bridge.outbound import route_client
        from session_control.errors import ControlError
        client = route_client(authority)
        try:
            override = await client.tool_override(origin, allow=[tool])
            override["limits"] = {"max_tool_calls": 1, "timeout_seconds": 3600}
            message = "请执行用户从 ACP 管理页指定的工具调用，然后报告结果。保持下面参数中的会话 ID 和回送策略，不添加其他任务：\n" + json.dumps(
                {"tool": tool, "arguments": payload["arguments"]}, ensure_ascii=False)
            receipt = await client.call("session.send", {"session_id": origin, "message": message,
                "runtime_override": override}, key="acp-ui:" + request_id)
        except ControlError as exc:
            raise HTTPException(exc.status, exc.code) from exc
        return {"accepted": True, "origin": origin, "operation_id": receipt["operation_id"]}

    @router.get("/outbound/tasks/{task_id}")
    async def outbound_task(task_id: str, request: Request, origin: str, after: int = 0):
        local_view(request)
        source_context(request, origin)
        from acp_bridge.outbound import service_for, on_host
        service = await service_for(manager)
        try:
            return await on_host(lambda: service.get(origin, task_id, max(0, after)))
        except PermissionError as exc:
            raise HTTPException(403, "task belongs to another source session") from exc
        except ValueError as exc:
            raise HTTPException(404, "task not found") from exc

    @router.post("/outbound/tasks/{task_id}/cancel")
    async def cancel_outbound(task_id: str, request: Request):
        local_view(request)
        write_origin(request)
        payload = await small_json(request)
        origin = payload.get("origin") if isinstance(payload, dict) else None
        source_context(request, origin)
        from acp_bridge.outbound import service_for, on_host
        service = await service_for(manager)
        try:
            return await on_host(lambda: service.cancel(origin, task_id))
        except PermissionError as exc:
            raise HTTPException(403, "task belongs to another source session") from exc
        except ValueError as exc:
            raise HTTPException(404, "task not found") from exc

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
            identity = authorize_session(request, session_id, configure=bool(payload.get("servers")))
            path = await asyncio.to_thread(manager._resolve_session_path, session_id)
            if not path.is_dir():
                raise HTTPException(404, "session not found")
            metadata = await asyncio.to_thread(manager._load_metadata, session_id)
            from agent_harness import session_work_dir
            cwd = str(session_work_dir(session_id, metadata))
            await mcp.mount(session_id, identity + ":" + owner, payload["servers"], cwd)
            try:
                registry.attach(identity, owner, session_id, cwd, metadata.get("name", ""))
            except BaseException:
                await mcp.unmount(session_id, identity + ":" + owner)
                raise
        except (ValueError, KeyError, TypeError) as exc:
            raise HTTPException(422, "invalid session MCP declarations") from exc
        return {"ok": True}

    @router.delete("/mcp/{session_id}")
    async def unmount(session_id: str, request: Request):
        owner = check(request)
        write_origin(request)
        identity = authorize_session(request, session_id)
        try:
            await mcp.unmount(session_id, identity + ":" + owner)
            registry.detach(identity, owner, session_id)
        except PermissionError as exc:
            raise HTTPException(403, "ACP connection does not own this attachment") from exc
        return {"ok": True}

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


async def stop(context, plugin):
    from plugins.host import bundled_host_plugin_enabled
    app = context.get("app")
    if (app is not None and bundled_host_plugin_enabled(plugin.plugin_id)
            and getattr(app.state, "acp_route_signature", None) != getattr(plugin, "content_signature", "")):
        return  # An installed replacement owns the same host service during hot reload.
    from acp_bridge.outbound import stop_services
    await stop_services()
    from acp_bridge.mcp import shutdown
    await shutdown()


async def start(context, plugin):
    from acp_bridge.outbound import service_for
    await service_for(context["session_manager"])
