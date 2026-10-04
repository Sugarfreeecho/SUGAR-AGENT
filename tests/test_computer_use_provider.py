from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import sys
import threading
import time
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from execution_services.jobs import ExecutionService
from execution_services.computer import ComputerUseManager


class Driver:
    def __init__(self, tools=None):
        self.tools = tools or [{"name": "get_screen_size", "inputSchema": {"type": "object"}}]
        self.closed = False
    async def list_tools_json(self):
        return json.dumps({"tools": self.tools})
    async def shutdown(self):
        self.closed = True
    async def call_tool(self, name, arguments_json):
        return SimpleNamespace(raw_json=json.dumps({"isError": True, "content": [
            {"type": "text", "text": "permission_denied"}]}), is_error=True)


def test_native_catalog_refusal_and_disable(monkeypatch):
    import host_tool_registry
    import security.runtime
    service = ExecutionService()
    manager = ComputerUseManager(service)
    driver = Driver()
    monkeypatch.setitem(sys.modules, "cua_driver", SimpleNamespace(CuaDriver=SimpleNamespace(create=lambda: driver)))
    monkeypatch.setattr(host_tool_registry, "host_tool_invokers", host_tool_registry.HostToolInvokerRegistry())
    monkeypatch.setattr(security.runtime, "session_permission_mode", lambda owner: "full_access")
    values = {"tool_name": "cua_driver_native__get_screen_size", "security_context": SimpleNamespace(mode="full_access"),
              "image_input_enabled": False, "model": "text-model"}
    context = SimpleNamespace(session_id="owner", service=values.__getitem__)
    async def run():
        try:
            result = await service.call(manager.configure, True, save=False)
            assert result["state"] == "ready"
            assert manager.catalog[0]["function"]["name"] == values["tool_name"]
            outcome = await manager.invoke(context, {})
            assert outcome.kind.value == "failed"
            assert "permission_denied" in outcome.content
            await service.call(manager.configure, False, save=False)
            assert driver.closed and manager.catalog == ()
            assert not host_tool_registry.host_tool_invokers.is_enabled(values["tool_name"])
        finally:
            await service.shutdown()
    asyncio.run(run())


def test_invalid_catalog_rolls_back_and_closes_native_runtime(monkeypatch):
    service = ExecutionService()
    manager = ComputerUseManager(service)
    driver = Driver([{"name": "same", "inputSchema": {"type": "object"}}] * 2)
    monkeypatch.setitem(sys.modules, "cua_driver", SimpleNamespace(CuaDriver=SimpleNamespace(create=lambda: driver)))
    async def run():
        try:
            result = await service.call(manager.configure, True, save=False)
            assert result["state"] == "error"
            assert "duplicate" in result["error"]
            assert manager.catalog == () and manager.names == {}
            assert driver.closed
        finally:
            await service.shutdown()
    asyncio.run(run())


def test_provider_replacement_waits_for_shutdown(monkeypatch):
    import host_tool_registry
    service = ExecutionService()
    manager = ComputerUseManager(service)
    order = []
    class Tracked(Driver):
        async def shutdown(self):
            order.append("shutdown-start")
            await asyncio.sleep(.05)
            order.append("shutdown-end")
    drivers = [Tracked(), Tracked()]
    def create():
        order.append("create")
        return drivers.pop(0)
    monkeypatch.setitem(sys.modules, "cua_driver", SimpleNamespace(CuaDriver=SimpleNamespace(create=create)))
    async def run():
        try:
            await service.call(manager.configure, True, save=False)
            before = host_tool_registry.host_tool_invokers.catalog_revision()[0]
            await service.call(manager.configure, True, save=False)
            assert order == ["create", "shutdown-start", "shutdown-end", "create"]
            assert host_tool_registry.host_tool_invokers.catalog_revision()[0] > before
            await service.call(manager.stop)
        finally:
            await service.shutdown()
    asyncio.run(run())


def test_mcp_provider_owns_catalog_and_releases_transport(monkeypatch):
    import agent_mcp
    import security.extensions
    service = ExecutionService()
    manager = ComputerUseManager(service)
    lifecycle = []
    class Server:
        _tools = [SimpleNamespace(model_dump=lambda: {"name": "click", "inputSchema": {"type": "object"}})]
        async def start(self):
            lifecycle.append("start")
        async def stop(self):
            lifecycle.append("stop")
        async def call_tool(self, name, arguments):
            return {"content": [{"type": "text", "text": name}]}
    async def run_here(coro):
        return await coro
    async def reserve(alias, value):
        lifecycle.append((alias, value))
    def connector(alias, cfg, *, register_tools):
        assert register_tools is False
        return Server()
    monkeypatch.setattr(agent_mcp, "_load_servers_dict_from_config", lambda: ({"cua-driver-mcp": {"command": "cua-driver"}}, None))
    monkeypatch.setattr(agent_mcp, "_make_stdio_connector", connector)
    monkeypatch.setattr(agent_mcp, "_run_on_mcp_loop", run_here)
    monkeypatch.setattr(agent_mcp, "reserve_server_for_host", reserve)
    monkeypatch.setattr(security.extensions, "mcp_registration_is_approved", lambda descriptor: True)
    async def run():
        try:
            result = await service.call(manager.configure, True, "mcp", save=False)
            assert result["state"] == "ready"
            assert manager.catalog[0]["function"]["name"] == "mcp__cua-driver-mcp__click"
            raw = await service.call(manager._raw_call, "mcp__cua-driver-mcp__click", {})
            assert raw["content"][0]["text"] == "click"
            await service.call(manager.stop)
            assert lifecycle == [("cua-driver-mcp", True), "start", "stop", ("cua-driver-mcp", False)]
        finally:
            await service.shutdown()
    asyncio.run(run())


def test_cancelled_native_startup_closes_created_driver(monkeypatch):
    service = ExecutionService()
    manager = ComputerUseManager(service)
    driver, creating = Driver(), threading.Event()
    def create():
        creating.set()
        time.sleep(.2)
        return driver
    monkeypatch.setitem(sys.modules, "cua_driver", SimpleNamespace(CuaDriver=SimpleNamespace(create=create)))
    async def run():
        try:
            configuring = asyncio.create_task(service.call(manager.configure, True, save=False))
            assert await asyncio.to_thread(creating.wait, 3)
            configuring.cancel()
            with pytest.raises(asyncio.CancelledError):
                await configuring
            await service.call(manager.stop)
            assert driver.closed and manager.catalog == ()
        finally:
            await service.shutdown()
    asyncio.run(run())


@pytest.mark.skipif(os.getenv("MYAGENT_CUA_SMOKE") != "1", reason="native SDK smoke is opt-in; no desktop input is sent")
def test_real_native_sdk_catalog_and_shutdown():
    service = ExecutionService()
    manager = ComputerUseManager(service)
    async def run():
        try:
            result = await service.call(manager.configure, True, save=False)
            assert result["state"] == "ready", result
            assert result["tool_count"] > 0
            await service.call(manager.stop)
        finally:
            await service.shutdown()
    asyncio.run(run())
