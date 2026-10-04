"""Trusted tool and UI adapter; the service owns execution lifetimes."""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import uuid

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from execution_services import execution_service
from execution_services.terminals import terminal_manager
from tool_registry import ToolOutcome

_SCHEMAS = {}


def _definition(name, description, properties, required=()):
    return {"type": "function", "function": {"name": name, "description": description,
        "parameters": {"type": "object", "properties": properties,
                       "required": list(required), "additionalProperties": False}}}


async def _invoke(context, arguments):
    from security.runtime import execution_scope
    from agent_tools import tool_work_dir_override, _resolve_shell_working_dir, _agent_self_protection_reason
    service = execution_service(context.service("session_manager"))
    name = context.service("tool_name")
    from jsonschema import Draft202012Validator
    error = next(Draft202012Validator(_SCHEMAS[name]).iter_errors(dict(arguments)), None)
    if error:
        raise ValueError(f"invalid {name} arguments at {'.'.join(map(str, error.absolute_path))}: {error.validator}")
    owner = context.session_id
    workspace = context.service("security_workspace")
    mode = str(context.service("security_context").mode)
    from security.runtime import session_permission_mode
    if str(session_permission_mode(owner)) != mode:
        raise PermissionError("permission mode changed before execution; authorize again")
    if context.service("run_interrupt_check")():
        raise asyncio.CancelledError()
    with execution_scope(session_id=owner, context=context.service("security_context"),
        request=context.service("security_request"), decision=context.service("security_decision"),
        workspace=workspace), tool_work_dir_override(workspace):
        if name == "job_list":
            result = await service.call(service.list_jobs, owner)
        elif name == "job_output":
            result = await service.call(service.output, owner, arguments["job_id"],
                bool(arguments.get("wait")), arguments.get("timeout_ms", 30000))
        elif name == "job_kill":
            result = await service.call(service.kill, owner, arguments["job_id"], arguments.get("reason", ""))
        else:
            terminals = terminal_manager(service)
            identifier = str(arguments.get("sessionId") or "")
            if name == "terminal_open":
                if arguments.get("type") != "shell":
                    raise ValueError("only terminal backend type 'shell' is registered")
                # Interactive PTYs cannot inherit the one-command egress helper
                # ticket. Fail explicitly rather than silently bypass its boundary.
                from security import egress_helper_enabled
                if egress_helper_enabled() and mode != "full_access":
                    raise PermissionError("interactive PTY is unavailable with the enabled egress helper; use run_shell")
                cwd = str(_resolve_shell_working_dir(arguments.get("cwd"), workspace))
                result = await service.call(terminals.open, owner, name=str(arguments.get("name") or ""),
                    cwd=cwd, permission_mode=mode)
            elif name == "terminal_send":
                reason = _agent_self_protection_reason(str(arguments.get("text") or ""))
                if reason:
                    raise PermissionError("Agent self-protection: " + reason)
                result = await service.call(terminals.send, owner, identifier,
                    str(arguments["text"]), bool(arguments.get("submit", True)), bool(arguments.get("run_in_background")))
            elif name == "terminal_read":
                result = await service.call(terminals.read, owner, identifier,
                    arguments.get("offset", 0), arguments.get("count", 500))
            elif name == "terminal_signal":
                result = await service.call(terminals.signal, owner, identifier, arguments["signal"])
            elif name == "terminal_close":
                result = await service.call(terminals.close, owner, identifier)
            elif name == "terminal_list":
                result = await service.call(terminals.list, owner)
            else:
                raise ValueError("unknown execution tool")
    return ToolOutcome.completed(json.dumps(result, ensure_ascii=False))


def tool_definitions(context, plugin):
    from host_tool_registry import host_tool_invokers
    from tool_execution_policy import ToolExecutionPolicy
    string = {"type": "string"}
    session = {"sessionId": string}
    definitions = [
        _definition("job_output", "Read new job output. wait=true waits for completion; timeout leaves the job running.",
            {"job_id": string, "wait": {"type": "boolean"}, "timeout_ms": {"type": "integer", "minimum": 1}}, ["job_id"]),
        _definition("job_list", "List your background jobs and their current states.", {}),
        _definition("job_kill", "Request cancellation of your background job.", {"job_id": string, "reason": string}, ["job_id"]),
        _definition("terminal_open", "Create an owner-isolated persistent PTY. Prefer run_shell for one-shot commands; keep terminals for persistent shell/REPL state.",
            {"type": {"type": "string", "enum": ["shell"]}, "name": string, "cwd": string}, ["type"]),
        _definition("terminal_send", "Send UTF-8 input to a persistent terminal. Enter is submitted by default. Background mode returns a jobId. inferred_idle or timeout does not prove command exit.",
            {**session, "text": string, "submit": {"type": "boolean"}, "run_in_background": {"type": "boolean"}}, ["sessionId", "text"]),
        _definition("terminal_read", "Read retained terminal output without sending input. offset is newest-relative lines; count defaults to 500.",
            {**session, "offset": {"type": "integer", "minimum": 0}, "count": {"type": "integer", "minimum": 1}}, ["sessionId"]),
        _definition("terminal_signal", "Signal the current foreground task. Shell-targeted SIGKILL is refused; use terminal_close. Unsupported platform signals fail explicitly.",
            {**session, "signal": {"type": "string", "enum": ["SIGINT", "SIGTERM", "SIGKILL", "SIGTSTP", "SIGHUP"]}}, ["sessionId", "signal"]),
        _definition("terminal_close", "Close your persistent terminal and terminate its process tree.", session, ["sessionId"]),
        _definition("terminal_list", "List your persistent terminals. User-operated terminals are separate and unavailable to model tools.", {}),
    ]
    for definition in definitions:
        name = definition["function"]["name"]
        _SCHEMAS[name] = definition["function"]["parameters"]
        read = name in {"job_output", "job_list", "terminal_read", "terminal_list"}
        host_tool_invokers.register(name, _invoke, replace=True, owner=plugin.plugin_id,
            enabled=lambda: context["is_enabled"](plugin.plugin_id),
            policy=ToolExecutionPolicy(effect="read" if read else "external_write",
                parallel_safe=read, early_stream_safe=read,
                interruptibility="safe" if read else "non_interruptible"))
    return definitions


def install(app, context, plugin):
    manager = context["session_manager"]
    router = APIRouter()

    def checked(session_id):
        from plugins.host import bundled_host_plugin_enabled
        if not bundled_host_plugin_enabled(plugin.plugin_id):
            raise HTTPException(404, "execution-tools is disabled")
        path = manager._resolve_session_path(session_id)
        if not path.is_dir():
            raise HTTPException(404, "session not found")
        return execution_service(manager)

    async def body(request):
        from plugin_web_gateway import validate_plugin_write_origin, PluginWebError
        try:
            validate_plugin_write_origin(request.method, origin=request.headers.get("origin", ""),
                scheme=request.url.scheme, host=request.headers.get("host", ""),
                fetch_site=request.headers.get("sec-fetch-site", ""), require_origin=True)
        except PluginWebError as exc:
            raise HTTPException(exc.status, str(exc)) from exc
        if int(request.headers.get("content-length", 0) or 0) > 256 * 1024:
            raise HTTPException(413, "terminal request too large")
        raw = await request.body()
        if len(raw) > 256 * 1024:
            raise HTTPException(413, "terminal request too large")
        try:
            value = json.loads(raw)
        except ValueError as exc:
            raise HTTPException(400, "invalid JSON") from exc
        if not isinstance(value, dict):
            raise HTTPException(422, "expected a JSON object")
        return value

    @router.get("/sessions/{session_id}/jobs")
    async def jobs(session_id: str):
        service = checked(session_id)
        return {"jobs": await service.call(service.list_jobs, session_id)}

    @router.get("/sessions/{session_id}/jobs/{job_id}/output")
    async def output(session_id: str, job_id: str, offset: int = 0):
        service = checked(session_id)
        try:
            return await service.call(service.output, session_id, job_id, offset=offset)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc

    @router.post("/sessions/{session_id}/jobs/{job_id}/kill")
    async def kill(session_id: str, job_id: str, request: Request):
        data = await body(request)
        service = checked(session_id)
        try:
            return await service.call(service.kill, session_id, job_id, str(data.get("reason") or "user cancellation"))
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc

    @router.get("/sessions/{session_id}/terminals")
    async def terminals(session_id: str):
        service = checked(session_id)
        tm = terminal_manager(service)
        return {"user": await service.call(tm.list, session_id, actor="user"),
                "model": await service.call(tm.list, session_id)}

    @router.post("/sessions/{session_id}/terminals")
    async def open_terminal(session_id: str, request: Request):
        data = await body(request)
        service = checked(session_id)
        tm = terminal_manager(service)
        from agent_tools import _resolve_shell_working_dir, active_tool_work_dir
        meta = manager._load_metadata_unlocked(session_id) or {}
        from pathlib import Path
        root = Path(meta.get("subagent_work_dir") or meta.get("git_worktree_path") or active_tool_work_dir())
        try:
            return await service.call(tm.open, session_id, actor="user",
                name=str(data.get("name") or "shell"),
                cwd=str(_resolve_shell_working_dir(data.get("cwd"), root)), shell=str(data.get("shell") or ""))
        except (ValueError, RuntimeError, ImportError) as exc:
            raise HTTPException(422, str(exc)) from exc

    @router.get("/sessions/{session_id}/terminals/{terminal_id}/history")
    async def history(session_id: str, terminal_id: str, actor: str = "user"):
        service = checked(session_id)
        tm = terminal_manager(service)
        try:
            return await service.call(tm.history, session_id, terminal_id, actor=actor)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc

    @router.post("/sessions/{session_id}/terminals/{terminal_id}/{action}")
    async def control(session_id: str, terminal_id: str, action: str, request: Request):
        data = await body(request)
        service = checked(session_id)
        tm = terminal_manager(service)
        try:
            if action == "input":
                await service.call(tm.input, session_id, terminal_id, str(data.get("text") or ""), str(data.get("connection") or ""))
            elif action == "resize":
                await service.call(tm.resize, session_id, terminal_id, data.get("rows", 40), data.get("cols", 160), str(data.get("connection") or ""))
            elif action == "close":
                await service.call(tm.close, session_id, terminal_id, actor="user")
            else:
                raise HTTPException(404, "unknown terminal action")
        except PermissionError as exc:
            raise HTTPException(409, str(exc)) from exc
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(422, str(exc)) from exc
        return {"ok": True}

    @router.get("/sessions/{session_id}/terminals/{terminal_id}/events")
    async def events(session_id: str, terminal_id: str, request: Request, offset: int = 0, connection: str = ""):
        service = checked(session_id)
        tm = terminal_manager(service)
        connection = connection or uuid.uuid4().hex
        try:
            initial = await service.call(tm.stream, session_id, terminal_id, offset, connection, claim=True)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc
        async def generate():
            current = initial
            cursor = offset
            while not await request.is_disconnected():
                if current["text"] or current["truncated"] or cursor == offset or current["status"] != "running":
                    yield "data: " + json.dumps({**current, "connection": connection}, ensure_ascii=False) + "\n\n"
                else:
                    yield ": keepalive\n\n"
                cursor = current["offset"]
                if current["status"] != "running":
                    break
                await asyncio.sleep(.15)
                current = await service.call(tm.stream, session_id, terminal_id, cursor, connection)
        return StreamingResponse(generate(), media_type="text/event-stream", headers={"Cache-Control": "no-store"})

    @router.get("/api/execution/capabilities")
    async def capabilities():
        candidates = ["pwsh", "powershell", "cmd", "bash"] if os.name == "nt" else ["bash", "sh", "zsh", "fish"]
        return {"shells": [{"name": name, "path": shutil.which(name)} for name in candidates if shutil.which(name)],
                "userTerminalPrivileges": "system_user", "maxTerminals": 8}

    app.include_router(router)


async def start(context, plugin):
    from execution_services.notifications import start_runner
    service = execution_service(context["session_manager"])
    service.start()
    async def enabled():
        service.closed_owners.clear()
    await service.call(enabled)
    await start_runner(service)


async def stop(context, plugin):
    from execution_services.notifications import stop_runner
    await stop_runner()
    service = execution_service(context["session_manager"])
    async def clean():
        owners = {j.owner for j in service.jobs.values()}
        if service.terminals:
            owners.update(s.owner for s in service.terminals.sessions.values())
        for owner in owners:
            await service.stop_owner(owner, close_terminals=True, reason="execution_tools_disabled")
    await service.call(clean)
