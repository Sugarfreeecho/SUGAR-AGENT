"""Bili tools over MCP Streamable HTTP, hosted alongside the workflow scheduler."""
from __future__ import annotations

import asyncio
import ipaddress
import json

from mcp import types
from mcp.server import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.server.transport_security import TransportSecuritySettings
from starlette.responses import JSONResponse

ALIAS = "sugar-bili-scroll/bili"
PATH = "/api/sugar-bili-scroll/mcp"
STATE_KEY = "sugar_bili_scroll_mcp"


def build_server(host):
    server = Server("sugar-bili-scroll")
    rows = host.mcp_tool_rows()
    schemas = {row[0]["function"]["name"]: row for row in rows}

    @server.list_tools()
    async def list_tools():
        return [types.Tool(name=name, description=host._mcp_tool_text(definition["function"]["description"]),
            inputSchema=definition["function"]["parameters"],
            annotations=types.ToolAnnotations(readOnlyHint=effect == "read",
                destructiveHint=effect != "read", idempotentHint=effect == "read",
                openWorldHint=True))
            for name, (definition, _, effect) in schemas.items()]

    @server.call_tool()
    async def call_tool(name, arguments):
        from host_tool_registry import HostToolInvocationContext
        from mcp_host_context import consume
        from plugins.host import bundled_host_plugin_enabled
        from tool_registry import ToolOutcomeKind

        meta = server.request_context.meta
        meta = meta.model_dump(by_alias=True) if meta is not None else {}
        trusted = consume(meta, ALIAS, name, arguments)
        if name not in schemas:
            raise ValueError("Unknown B站 tool")
        if host._runtime.get("stopping") or not bundled_host_plugin_enabled(host.PLUGIN_ID):
            raise ValueError("B站插件已停用")
        context = HostToolInvocationContext(**trusted, services={"tool_name": name})
        outcome = await host._invoke(context, arguments)
        content = outcome.content
        if not isinstance(content, str):
            content = json.dumps(content, ensure_ascii=False)
        return types.CallToolResult(content=[types.TextContent(type="text", text=content)],
                                    isError=outcome.kind is ToolOutcomeKind.FAILED)

    return server


async def start(host):
    if host._runtime.get("mcp_task") and not host._runtime["mcp_task"].done():
        return
    ready, halt = asyncio.Event(), asyncio.Event()
    manager = StreamableHTTPSessionManager(build_server(host), stateless=True, json_response=True,
        security_settings=TransportSecuritySettings(enable_dns_rebinding_protection=True,
            allowed_hosts=["127.0.0.1:*", "localhost:*", "[::1]:*"],
            allowed_origins=["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"]))

    async def serve():
        async with manager.run():
            ready.set()
            await halt.wait()

    task = asyncio.create_task(serve(), name="sugar-bili-scroll-mcp")
    host._runtime.update(mcp_manager=manager, mcp_task=task, mcp_halt=halt)
    waiter = asyncio.create_task(ready.wait())
    try:
        done, _ = await asyncio.wait([task, waiter], return_when=asyncio.FIRST_COMPLETED)
        if task in done:
            await task
    finally:
        waiter.cancel()


async def stop(host):
    halt, task = host._runtime.get("mcp_halt"), host._runtime.get("mcp_task")
    if halt is not None:
        halt.set()
    if task is not None:
        await task
    for key in ("mcp_halt", "mcp_task", "mcp_manager"):
        host._runtime.pop(key, None)


def install(app, host):
    """A stable gateway follows the current adapter across enable/reload cycles."""
    previous = getattr(app.state, STATE_KEY, None)
    setattr(app.state, STATE_KEY, host)
    if previous is not None:
        return

    async def gateway(scope, receive, send):
        current = getattr(app.state, STATE_KEY)
        manager = current._runtime.get("mcp_manager")
        address = (scope.get("client") or ("",))[0]
        try:
            local = ipaddress.ip_address(address).is_loopback
        except ValueError:
            local = False
        if not local:
            await JSONResponse({"error": "MCP host endpoint requires loopback"}, status_code=403)(scope, receive, send)
        elif manager is None or current._runtime.get("stopping"):
            await JSONResponse({"error": "B站 MCP 未启动或已停用"}, status_code=503)(scope, receive, send)
        else:
            await manager.handle_request(scope, receive, send)

    app.mount(PATH, gateway, name="sugar-bili-scroll-mcp")
