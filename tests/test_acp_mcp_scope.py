import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from acp_bridge import mcp


def test_session_mcp_mount_visibility_ownership_and_rollback(monkeypatch, tmp_path):
    import agent_mcp
    import host_tool_registry
    from host_tool_registry import HostToolInvocationContext, HostToolInvokerRegistry

    registry = HostToolInvokerRegistry()
    monkeypatch.setattr(host_tool_registry, "host_tool_invokers", registry)
    monkeypatch.setattr(mcp, "_groups", {})
    clients = []

    class Client:
        def __init__(self):
            self.tools = [SimpleNamespace(name="echo", description="Echo", inputSchema={"type": "object"})]
            self.closed = False
        async def close(self):
            self.closed = True
        async def call(self, name, arguments):
            return SimpleNamespace(isError=False, content=[])

    async def open_client(name, config):
        if Path(config["command"]).name == "invalid":
            raise RuntimeError("discovery failed")
        client = Client()
        clients.append(client)
        return client

    monkeypatch.setattr(agent_mcp, "open_session_mcp_client", open_client)
    server = {"name": "echo", "command": sys.executable, "args": [], "env": []}
    async def scenario():
        await mcp.mount("one", "owner-a", [server], str(tmp_path))
        assert len(mcp.definitions("one", lambda: True, "acp-agents")) == 1
        assert mcp.definitions("two", lambda: True, "acp-agents") == []
        tool = next(iter(mcp._groups["one"]["tools"]))
        context = HostToolInvocationContext(session_id="two", services={"tool_name": tool})
        with pytest.raises(PermissionError):
            await mcp.invoke(context, {})
        with pytest.raises(PermissionError):
            await mcp.unmount("one", "owner-b")
        assert not clients[0].closed
        await mcp.unmount("one", "owner-a")
        assert clients[0].closed
        with pytest.raises(RuntimeError):
            await mcp.mount("three", "owner-a", [server, dict(server, name="broken", command=str(tmp_path / "invalid"))], str(tmp_path))
        assert "three" not in mcp._groups
        assert clients[-1].closed
    asyncio.run(scenario())


def test_scoped_connector_does_not_register_global_tools(monkeypatch):
    import agent_mcp
    import security.extensions
    states = []

    class Server:
        _tools = ("echo",)
        async def start(self):
            states.append("started")
        async def stop(self):
            states.append("stopped")
        async def call_tool(self, name, arguments):
            return name

    async def same_loop(awaitable):
        return await awaitable
    def factory(alias, config, *, register_tools=True):
        assert register_tools is False
        return Server()

    monkeypatch.setattr(agent_mcp, "_run_on_mcp_loop", same_loop)
    monkeypatch.setattr(agent_mcp, "_make_stdio_connector", factory)
    monkeypatch.setattr(security.extensions, "mcp_registration_is_approved", lambda descriptor: True)
    async def scenario():
        client = await agent_mcp.open_session_mcp_client("test", {"transport": "stdio", "command": sys.executable})
        assert client.tools == ("echo",)
        assert await client.call("echo", {}) == "echo"
        await client.close()
        with pytest.raises(RuntimeError):
            await client.call("echo", {})
        await client.close()
    asyncio.run(scenario())
    assert states == ["started", "stopped"]


def test_detach_waits_for_inflight_mcp_startup_and_closes_late_client(monkeypatch, tmp_path):
    import agent_mcp
    monkeypatch.setattr(mcp, "_groups", {})
    async def scenario():
        started, release = asyncio.Event(), asyncio.Event()
        client = SimpleNamespace(tools=[], closed=False)
        async def close():
            client.closed = True
        client.close = close
        async def open_client(*args):
            started.set()
            await release.wait()
            return client
        monkeypatch.setattr(agent_mcp, "open_session_mcp_client", open_client)
        mounting = asyncio.create_task(mcp.mount("one", "owner", [
            {"name": "one", "command": sys.executable, "args": [], "env": []}], str(tmp_path)))
        await started.wait()
        detaching = asyncio.create_task(mcp.unmount("one", "owner"))
        await asyncio.sleep(0)
        assert not detaching.done()
        release.set()
        await detaching
        assert client.closed and "one" not in mcp._groups
        assert isinstance((await asyncio.gather(mounting, return_exceptions=True))[0], asyncio.CancelledError)
    asyncio.run(scenario())
