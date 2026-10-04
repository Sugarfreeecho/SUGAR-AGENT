"""One Cua provider slot, with transactional dynamic tool publication."""
from __future__ import annotations

import asyncio
import json
import os
import re
import threading

from tool_registry import ToolOutcome

GUIDANCE = (
    "Operate the host desktop. Discover the exact app/window and take a fresh window snapshot before acting. "
    "Use element_token from that snapshot or coordinates from its screenshot. New snapshots invalidate earlier tokens. "
    "Do not combine target with legacy pid/window_id. Prefer background delivery; refusal does not authorize a foreground retry. "
    "Verify the outcome from fresh state. After cancellation, observe before retrying: completed input is not rolled back. "
    "Other sessions may change the same desktop."
)
READ_TOOLS = {"get_desktop_state", "get_screen_size", "get_cursor_position", "list_windows",
              "get_window_state", "get_window_screenshot", "get_accessibility_tree", "get_agent_cursor_state"}
_MANAGER = None
_LOCK = threading.Lock()


class ComputerUseManager:
    def __init__(self, service):
        self.service = service
        self.enabled = False
        self.provider = "native"
        self.server_alias = "cua-driver-mcp"
        self.driver = None
        self.server = None
        self.state = "disabled"
        self.error = ""
        self.catalog = ()
        self.names = {}
        self.pending = set()
        self.reserved_alias = ""
        self._gate = asyncio.Lock()

    def status(self):
        return {"enabled": self.enabled, "provider": self.provider,
                "server_alias": self.server_alias, "state": self.state, "error": self.error,
                "tool_count": len(self.catalog), "platform": os.name}

    def settings(self):
        from security.runtime import security_store
        raw = security_store().get_text_setting("computer_use", "")
        if raw:
            try:
                value = json.loads(raw)
                if isinstance(value, dict):
                    return value
            except ValueError:
                pass
            self.error = "invalid persisted Computer Use settings"
            return {"enabled": False, "provider": "native"}
        return {"enabled": os.getenv("COMPUTER_USE_ENABLED", "0").lower() in {"1", "true", "yes"},
                "provider": os.getenv("COMPUTER_USE_PROVIDER", "native"),
                "server_alias": os.getenv("COMPUTER_USE_MCP_SERVER", "cua-driver-mcp")}

    async def configure(self, enabled, provider="native", server_alias="cua-driver-mcp", *, save=True):
        if not isinstance(provider, str) or provider not in {"native", "mcp"}:
            raise ValueError("computer provider must be native or mcp")
        async with self._gate:
            await self._stop()
            self.provider, self.server_alias = provider, str(server_alias)
            self.enabled = bool(enabled)
            self.error = ""
            if save:
                from security.runtime import security_store
                security_store().set_text_setting("computer_use", json.dumps({"enabled": self.enabled,
                    "provider": provider, "server_alias": self.server_alias}))
            if not enabled:
                return self.status()
            self.state = "starting"
            try:
                if provider == "native":
                    from cua_driver import CuaDriver
                    starter = asyncio.create_task(asyncio.to_thread(CuaDriver.create))
                    try:
                        self.driver = await asyncio.shield(starter)
                    except asyncio.CancelledError:
                        self.driver = await starter
                        raise
                    listed = await self.driver.list_tools_json()
                    tools = json.loads(listed)["tools"]
                else:
                    import agent_mcp
                    configs, error = agent_mcp._load_servers_dict_from_config()
                    cfg = (configs or {}).get(self.server_alias)
                    if not cfg:
                        raise ValueError(error or "selected Cua Driver MCP server is not configured")
                    if cfg.get("url"):
                        raise ValueError("Cua Driver MCP provider requires a local stdio server")
                    from security.extensions import mcp_descriptor, mcp_registration_is_approved
                    if not mcp_registration_is_approved(mcp_descriptor(self.server_alias, cfg)):
                        raise PermissionError("approve this MCP server registration in MCP settings first")
                    await agent_mcp.reserve_server_for_host(self.server_alias, True)
                    self.reserved_alias = self.server_alias
                    self.server = agent_mcp._make_stdio_connector(self.server_alias, cfg, register_tools=False)
                    await agent_mcp._run_on_mcp_loop(self.server.start())
                    tools = [t.model_dump() for t in self.server._tools]
                definitions, names = [], {}
                prefix = "cua_driver_native__" if provider == "native" else "mcp__cua-driver-mcp__"
                from host_tool_registry import host_tool_invokers
                from tool_execution_policy import ToolExecutionPolicy
                for tool in tools:
                    original = str(tool.get("name") or "")
                    name = prefix + original
                    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", name) or name in names:
                        raise ValueError("invalid or duplicate Cua tool name: " + name)
                    if host_tool_invokers.has(name) and host_tool_invokers.owner(name) != "computer-use":
                        raise ValueError("Cua tool name collides with another host tool: " + name)
                    schema = tool.get("inputSchema")
                    if not isinstance(schema, dict) or schema.get("type") != "object":
                        raise ValueError("invalid Cua tool inputSchema: " + name)
                    from jsonschema import Draft202012Validator
                    Draft202012Validator.check_schema(schema)
                    names[name] = original
                    definitions.append({"type": "function", "function": {"name": name,
                        "description": str(tool.get("description") or ""),
                        "parameters": schema}})
                # Validate the complete catalog before publishing any names.
                self.catalog, self.names = tuple(definitions), names
                for name, original in names.items():
                    host_tool_invokers.register(name, self.invoke, replace=True, owner="computer-use",
                        enabled=lambda name=name: self.state == "ready" and name in self.names and self._plugin_enabled(),
                        policy=ToolExecutionPolicy(effect="read" if original in READ_TOOLS else "external_write",
                            early_stream_safe=original in READ_TOOLS, interruptibility="safe"))
                self.state = "ready"
                host_tool_invokers.notify_catalog_changed()
            except BaseException as exc:
                self.error = str(exc)
                await self._stop()
                self.state = "error"
                if isinstance(exc, asyncio.CancelledError):
                    raise
            return self.status()

    @staticmethod
    def _plugin_enabled():
        from plugins.host import bundled_host_plugin_enabled
        return bundled_host_plugin_enabled("computer-use")

    async def _stop(self):
        from host_tool_registry import host_tool_invokers
        host_tool_invokers.notify_catalog_changed()
        self.state = "closing"
        self.catalog, self.names = (), {}
        # Keep the provider reserved until admitted calls and shutdown settle.
        tasks = [t for t in self.pending if t is not asyncio.current_task()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        if self.driver:
            await self.driver.shutdown()
            self.driver = None
        if self.server:
            import agent_mcp
            await agent_mcp._run_on_mcp_loop(self.server.stop())
            self.server = None
        if self.reserved_alias:
            import agent_mcp
            await agent_mcp.reserve_server_for_host(self.reserved_alias, False)
            self.reserved_alias = ""
        self.state = "disabled"

    async def stop(self):
        async with self._gate:
            await self._stop()

    async def _raw_call(self, name, arguments):
        if self.state != "ready" or name not in self.names:
            raise RuntimeError("computer provider is unavailable")
        from jsonschema import Draft202012Validator
        definition = next(d for d in self.catalog if d["function"]["name"] == name)
        error = next(Draft202012Validator(definition["function"]["parameters"]).iter_errors(arguments), None)
        if error:
            raise ValueError(f"invalid {name} arguments at {'.'.join(map(str, error.absolute_path))}: {error.validator}")
        task = asyncio.current_task()
        self.pending.add(task)
        try:
            if self.driver:
                result = await self.driver.call_tool(self.names[name], json.dumps(arguments, ensure_ascii=False))
                raw = json.loads(result.raw_json)
                if result.is_error:
                    raw["isError"] = True
                return raw
            import agent_mcp
            return await agent_mcp._run_on_mcp_loop(self.server.call_tool(self.names[name], arguments))
        finally:
            self.pending.discard(task)

    async def invoke(self, context, arguments):
        name = context.service("tool_name")
        from security.runtime import session_permission_mode
        if str(session_permission_mode(context.session_id)) != str(context.service("security_context").mode):
            raise PermissionError("permission mode changed before computer invocation")
        pending = self.service.call(self._raw_call, name, dict(arguments))
        awaiter = getattr(context, "services", {}).get("await_steerable")
        raw = await awaiter(pending, "computer_use") if awaiter else await pending
        from agent_mcp import format_call_tool_result
        content = format_call_tool_result(raw, image_enabled=context.service("image_input_enabled"),
                                          model=context.service("model"))
        failed = raw.get("isError", False) if isinstance(raw, dict) else getattr(raw, "isError", False)
        return ToolOutcome.failed("computer_use_error", "Cua Driver refused or failed the action", content=content) if failed else ToolOutcome.completed(content)


def computer_manager(service=None):
    global _MANAGER
    with _LOCK:
        if _MANAGER is None:
            from .jobs import execution_service
            _MANAGER = ComputerUseManager(service or execution_service())
        return _MANAGER


def tool_contract(name):
    names = _MANAGER.names if _MANAGER is not None else {}
    original = names.get(name)
    if original is None:
        return None
    return {"effect": "read" if original in READ_TOOLS else "external_write", "declared": True}
