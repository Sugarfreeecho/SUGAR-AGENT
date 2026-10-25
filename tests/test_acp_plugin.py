import asyncio
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))


def host_module():
    spec = importlib.util.spec_from_file_location("acp_test_host", ROOT / "plugins/acp-agents/host.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_inbound_mcp_routes_enforce_origin_session_and_owner(monkeypatch, tmp_path):
    import plugins.host
    from acp_bridge import mcp

    module = host_module()
    plugin = SimpleNamespace(plugin_id="acp-agents")
    monkeypatch.setattr(plugins.host, "bundled_host_plugin_enabled", lambda name: True)
    calls = []
    async def mount(sid, owner, servers, cwd):
        calls.append((sid, owner, servers, cwd))
    async def unmount(sid, owner):
        if owner != "owner":
            raise PermissionError("wrong owner")
    monkeypatch.setattr(mcp, "mount", mount)
    monkeypatch.setattr(mcp, "unmount", unmount)
    path = tmp_path / "one"
    path.mkdir()
    manager = SimpleNamespace(_resolve_session_path=lambda sid: tmp_path / sid,
                              _load_metadata=lambda sid: {"id": sid, "work_dir": str(tmp_path)})
    app = FastAPI()
    module.install(app, {"session_manager": manager}, plugin)
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1") as client:
            assert (await client.get("/api/acp/status")).status_code == 200
            assert (await client.post("/api/acp/mcp/one", json={"servers": []})).status_code == 403
            headers = {"Origin": "http://127.0.0.1", "X-MyAgent-ACP-Connection": "owner"}
            assert (await client.post("/api/acp/mcp/missing", headers=headers, json={"servers": []})).status_code == 404
            assert (await client.post("/api/acp/mcp/one", headers=headers, json={"servers": []})).status_code == 200
            assert calls[0][:3] == ("one", "owner", [])
            assert (await client.delete("/api/acp/mcp/one", headers=dict(headers, **{"X-MyAgent-ACP-Connection": "other"}))).status_code == 403
            assert (await client.delete("/api/acp/mcp/one", headers=headers)).status_code == 200
    asyncio.run(scenario())


def test_outbound_tool_catalog_requires_configured_targets_and_is_gated(monkeypatch):
    from host_tool_registry import HostToolInvokerRegistry
    import host_tool_registry
    from acp_bridge.client import parse_targets

    module = host_module()
    plugin = SimpleNamespace(plugin_id="acp-agents")
    monkeypatch.setattr(host_tool_registry, "host_tool_invokers", HostToolInvokerRegistry())
    monkeypatch.setattr(module, "_targets", lambda plugin: {})
    assert module.tool_definitions({"is_enabled": lambda name: True}, plugin) == []
    targets = parse_targets('{"dsh":{"command":"node","args":["dsh.js","--profile","acp"]}}')
    monkeypatch.setattr(module, "_targets", lambda plugin: targets)
    rows = module.tool_definitions({"is_enabled": lambda name: True}, plugin)
    task = next(row["function"] for row in rows if row["function"]["name"] == "acp_task")
    assert task["parameters"]["properties"]["agent"]["enum"] == ["dsh"]
    assert set(task["parameters"]["properties"]) == {"agent", "prompt"}
    assert host_tool_registry.host_tool_invokers.policy("acp_task").effect == "external_write"
    assert module.tool_definitions({"is_enabled": lambda name: False}, plugin) == []
