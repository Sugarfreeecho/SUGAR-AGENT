"""Session-scoped MCP mounts supplied by trusted ACP controllers."""
from __future__ import annotations

import asyncio
import hashlib
import threading
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import TypeAdapter
from acp.schema import HttpMcpServer, McpServerStdio


_groups = {}
_lock = threading.RLock()
_server_type = TypeAdapter(McpServerStdio | HttpMcpServer)


def resolve_servers(servers, cwd):
    if not isinstance(servers, list) or len(servers) > 32:
        raise ValueError("mcpServers must contain at most 32 declarations")
    configs, names = [], set()
    for raw in servers:
        if not isinstance(raw, dict) or ("type" in raw and raw["type"] != "http"):
            raise ValueError("only standard stdio and HTTP MCP transports are supported")
        server = _server_type.validate_python(raw)
        name = server.name.strip()
        if not name or name in names or any(ord(ch) < 32 for ch in name):
            raise ValueError("MCP server names must be nonempty and unique")
        names.add(name)
        if isinstance(server, McpServerStdio):
            if not Path(server.command).is_absolute():
                raise ValueError("MCP command must be absolute")
            entries = server.env
            config = {"transport": "stdio", "command": server.command, "args": server.args, "cwd": cwd}
            field = "env"
        else:
            if urlsplit(server.url).scheme not in {"http", "https"} or not urlsplit(server.url).hostname:
                raise ValueError("MCP HTTP URL must be absolute")
            entries = server.headers
            config = {"transport": "streamable-http", "url": server.url}
            field = "headers"
        values, identities = {}, set()
        for entry in entries:
            identity = entry.name.lower() if field == "headers" else entry.name
            if (not identity or identity in identities or "\x00" in entry.name + entry.value
                    or (field == "env" and "=" in entry.name)
                    or (field == "headers" and any(ch in entry.name + entry.value for ch in "\r\n"))):
                raise ValueError("invalid or duplicate MCP environment/header entry")
            identities.add(identity)
            values[entry.name] = entry.value
        config[field] = values
        configs.append((name, config))
    return configs


async def mount(session_id, owner, servers, cwd):
    from agent_mcp import open_session_mcp_client

    configs = resolve_servers(servers, cwd)
    group = {"owner": owner, "clients": [], "tools": {}, "ready": False,
             "mount_task": asyncio.current_task()}
    with _lock:
        if session_id in _groups:
            raise ValueError("session is already attached to an ACP connection")
        _groups[session_id] = group
    try:
        for name, config in configs:
            opening = asyncio.create_task(open_session_mcp_client(
                "acp_" + hashlib.sha256(name.encode()).hexdigest()[:16], config))
            try:
                client = await asyncio.shield(opening)
            except asyncio.CancelledError:
                # A cross-loop startup can finish after the HTTP request is
                # cancelled. Retain ownership until it settles, then close it.
                try:
                    client = await opening
                except Exception:
                    raise asyncio.CancelledError() from None
                await client.close()
                raise
            group["clients"].append(client)
            for tool in client.tools:
                digest = hashlib.sha256((name + "\0" + tool.name).encode()).hexdigest()[:20]
                public_name = "acp_mcp_" + digest
                group["tools"][public_name] = (client, tool)
        group["ready"] = True
        from host_tool_registry import host_tool_invokers
        host_tool_invokers.notify_catalog_changed()
    except BaseException:
        await unmount(session_id, owner)
        raise


async def unmount(session_id, owner):
    with _lock:
        group = _groups.get(session_id)
        if group is None:
            return
        if group["owner"] != owner:
            raise PermissionError("ACP connection does not own this session attachment")
        _groups.pop(session_id)
    mounting = group["mount_task"]
    if not group["ready"] and mounting is not asyncio.current_task() and not mounting.done():
        mounting.cancel()
        await asyncio.gather(mounting, return_exceptions=True)
    from host_tool_registry import host_tool_invokers
    host_tool_invokers.notify_catalog_changed()
    results = await asyncio.gather(*(client.close() for client in group["clients"]), return_exceptions=True)
    if any(isinstance(result, BaseException) for result in results):
        raise RuntimeError("session MCP teardown failed")


def definitions(session_id, enabled, plugin_id):
    from host_tool_registry import host_tool_invokers
    from tool_execution_policy import ToolExecutionPolicy

    with _lock:
        group = _groups.get(session_id)
        tools = dict(group["tools"]) if group and group["ready"] else {}
    rows = []
    for name, (_, tool) in tools.items():
        host_tool_invokers.register(name, invoke, replace=True, owner=plugin_id, enabled=enabled,
            policy=ToolExecutionPolicy(effect="external_write", early_stream_safe=False, interruptibility="cooperative"))
        rows.append({"type": "function", "function": {"name": name,
                     "description": tool.description or tool.name, "parameters": tool.inputSchema}})
    return rows


async def invoke(context, arguments):
    from agent_mcp import format_call_tool_result
    from tool_registry import ToolOutcome

    with _lock:
        group = _groups.get(context.session_id)
        entry = group["tools"].get(context.service("tool_name")) if group and group["ready"] else None
    if entry is None:
        raise PermissionError("MCP tool is not mounted in this session")
    client, tool = entry
    result = await context.service("await_steerable")(client.call(tool.name, dict(arguments)), "tool_extension")
    content = format_call_tool_result(result)
    if getattr(result, "isError", False):
        return ToolOutcome.failed("acp_mcp_error", "MCP tool failed", content=content)
    return ToolOutcome.completed(content)


async def shutdown():
    with _lock:
        groups = [(sid, group["owner"]) for sid, group in _groups.items()]
    results = await asyncio.gather(*(unmount(sid, owner) for sid, owner in groups), return_exceptions=True)
    if any(isinstance(result, BaseException) for result in results):
        raise RuntimeError("ACP MCP cleanup failed")
