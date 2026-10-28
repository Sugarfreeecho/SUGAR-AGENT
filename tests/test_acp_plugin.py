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
    import acp_bridge.connections as connections
    from session_control.api import register_control
    from session_control.policy import Principal
    from remote_control.store import RemoteControlStore
    import session_control.integration as integration

    module = host_module()
    plugin = SimpleNamespace(plugin_id="acp-agents")
    monkeypatch.setattr(plugins.host, "bundled_host_plugin_enabled", lambda name: True)
    monkeypatch.setattr(connections, "registry", connections.ConnectionRegistry())
    calls = []
    async def mount(sid, owner, servers, cwd):
        calls.append((sid, owner, servers, cwd))
    async def unmount(sid, owner):
        if owner != "person:owner":
            raise PermissionError("wrong owner")
    monkeypatch.setattr(mcp, "mount", mount)
    monkeypatch.setattr(mcp, "unmount", unmount)
    path = tmp_path / "one"
    path.mkdir()
    manager = SimpleNamespace(_resolve_session_path=lambda sid: tmp_path / sid,
                              get_session_summary=lambda sid: {"id": sid} if (tmp_path / sid).is_dir() else None,
                              _load_metadata=lambda sid: {"id": sid, "work_dir": str(tmp_path)})
    app = FastAPI()
    control = register_control(app, SimpleNamespace(session_manager=manager), tmp_path / "control", RemoteControlStore(tmp_path / "remote"))
    monkeypatch.setattr(integration, "_application", control)
    token = control.identities.issue(Principal("person", admin=True))
    other_token = control.identities.issue(Principal("other", policy={"scope": "all", "capabilities": ["read"]}))
    module.install(app, {"session_manager": manager}, plugin)
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1") as client:
            assert (await client.get("/api/acp/status")).status_code == 200
            assert (await client.post("/api/acp/mcp/one", json={"servers": []})).status_code == 403
            headers = {"Origin": "http://127.0.0.1", "X-MyAgent-ACP-Connection": "owner", "Authorization": "Bearer " + token}
            assert (await client.post("/api/acp/connections", json={"protocol_version": 1})).status_code == 403
            assert (await client.post("/api/acp/connections", headers={"Origin": "http://127.0.0.1", "X-MyAgent-ACP-Connection": "owner"}, json={"protocol_version": 1})).status_code == 401
            assert (await client.post("/api/acp/connections", headers=headers, json={"protocol_version": 1, "client": {"name": "DSH"}})).status_code == 200
            assert (await client.post("/api/acp/mcp/one", headers={"Origin": "http://127.0.0.1", "X-MyAgent-ACP-Connection": "owner"}, json={"servers": []})).status_code == 401
            assert (await client.post("/api/acp/mcp/missing", headers=headers, json={"servers": []})).status_code == 404
            assert (await client.post("/api/acp/mcp/one", headers=headers, json={"servers": []})).status_code == 200
            assert calls[0][:3] == ("one", "person:owner", [])
            snapshot = (await client.get("/api/acp/connections")).json()
            assert snapshot["online_count"] == snapshot["session_count"] == 1
            assert snapshot["connections"][0]["client"]["name"] == "DSH"
            assert snapshot["launch"]["env_refs"] == ["MYAGENT_CONTROL_TOKEN"]
            assert token not in json.dumps(snapshot)
            assert (await client.get("/api/acp/connections", headers={"Authorization": "Bearer " + other_token})).json()["connections"] == []
            assert (await client.get("/api/acp/connections", headers={"Origin": "https://foreign.example"})).status_code == 403
            assert (await client.get("/api/acp/connections", headers={"Sec-Fetch-Site": "cross-site"})).status_code == 403
            assert (await client.post("/api/acp/connections/heartbeat", headers=headers, json={"busy_session_ids": ["missing"]})).status_code == 422
            assert (await client.post("/api/acp/connections/heartbeat", headers=headers, json={"busy_session_ids": ["one"], "activity": "prompt"})).status_code == 200
            assert (await client.get("/api/acp/connections")).json()["connections"][0]["busy"]
            foreign = dict(headers, Authorization="Bearer " + other_token)
            assert (await client.post("/api/acp/connections/heartbeat", headers=foreign, json={})).status_code == 404
            assert (await client.delete("/api/acp/connections", headers=foreign)).status_code == 200
            assert (await client.get("/api/acp/connections")).json()["online_count"] == 1
            assert (await client.delete("/api/acp/mcp/one", headers=dict(headers, **{"X-MyAgent-ACP-Connection": "other"}))).status_code == 403
            assert (await client.delete("/api/acp/mcp/one", headers=headers)).status_code == 200
            assert (await client.get("/api/acp/connections")).json()["session_count"] == 0
            assert (await client.delete("/api/acp/connections", headers=headers)).status_code == 200
            assert (await client.get("/api/acp/connections")).json()["connections"][0]["status"] == "disconnected"
    asyncio.run(scenario())


def test_embedded_page_and_outbound_settings_validation(monkeypatch):
    import plugins.host
    from plugins import load_plugin, plugin_ui_contributions
    import agent_extensions

    plugin = load_plugin(ROOT / "plugins/acp-agents")
    row = next(row for row in plugin_ui_contributions(plugin) if row["slot"] == "settings.section")
    assert row["id"] == "main" and row["embedded"] and row["href"] == "/plugins/acp-agents"
    monkeypatch.setattr(plugins.host, "bundled_host_plugin_enabled", lambda name: True)
    calls = []
    monkeypatch.setattr(agent_extensions, "update_plugin_settings", lambda pid, values: calls.append((pid, values)))
    app = FastAPI()
    host_module().install(app, {"session_manager": SimpleNamespace()}, plugin)
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1") as client:
            headers = {"Origin": "http://127.0.0.1"}
            assert (await client.put("/api/acp/targets", json={"agents_json": "{}"})).status_code == 403
            for raw in ("{", "[]", '{"bad":{"command":"node","env":{"TOKEN":"secret"}}}'):
                assert (await client.put("/api/acp/targets", headers=headers, json={"agents_json": raw})).status_code == 422
            assert calls == []
            raw = '{"dsh":{"command":"node","args":["dsh.js","--profile","acp"]}}'
            response = await client.put("/api/acp/targets", headers=headers, json={"agents_json": raw})
            assert response.status_code == 200 and response.json()["target_ids"] == ["dsh"]
            assert calls == [("acp-agents", {"agents_json": raw})]
    asyncio.run(scenario())


def test_outbound_tool_catalog_requires_configured_targets_and_is_gated(monkeypatch):
    from host_tool_registry import HostToolInvokerRegistry
    import host_tool_registry
    from acp_bridge.client import parse_targets

    module = host_module()
    plugin = SimpleNamespace(plugin_id="acp-agents")
    monkeypatch.setattr(host_tool_registry, "host_tool_invokers", HostToolInvokerRegistry())
    monkeypatch.setattr(module, "_targets", lambda plugin: {})
    assert {row["function"]["name"] for row in module.tool_definitions({"is_enabled": lambda name: True}, plugin)} == {"acp_agents", "acp_tasks", "acp_task_get", "acp_task_cancel"}
    targets = parse_targets('{"dsh":{"command":"node","args":["dsh.js","--profile","acp"]}}')
    monkeypatch.setattr(module, "_targets", lambda plugin: targets)
    rows = module.tool_definitions({"is_enabled": lambda name: True}, plugin)
    task = next(row["function"] for row in rows if row["function"]["name"] == "acp_task")
    assert task["parameters"]["properties"]["agent"]["enum"] == ["dsh"]
    assert set(task["parameters"]["properties"]) == {"agent", "prompt", "session_id", "background", "notify"}
    assert {row["function"]["name"] for row in rows} >= {"acp_sessions", "acp_session_new", "acp_session_close", "acp_task_get", "acp_task_cancel", "acp_tasks"}
    assert "recipient" not in task["parameters"]["properties"]
    assert host_tool_registry.host_tool_invokers.policy("acp_task").effect == "external_write"
    assert module.tool_definitions({"is_enabled": lambda name: False}, plugin) == []


def test_outbound_ui_queues_one_scoped_tool_and_rejects_recipient_override(monkeypatch, tmp_path):
    import plugins.host
    import acp_bridge.outbound as outbound
    from acp_bridge.client import parse_targets

    module = host_module()
    monkeypatch.setattr(plugins.host, "bundled_host_plugin_enabled", lambda name: True)
    monkeypatch.setattr(module, "_targets", lambda plugin: parse_targets('{"codex":{"command":"node"}}'))
    monkeypatch.setattr(outbound, "capture_route", lambda origin, parent=None: {"bound_origin": origin})
    calls = []
    class Client:
        async def tool_override(self, origin, allow):
            assert origin == "source" and allow == ["acp_task"]
            return {"tools": {"mode": "custom", "allow": allow}}
        async def call(self, method, params, key):
            calls.append((method, params, key))
            return {"operation_id": "accepted-operation"}
    monkeypatch.setattr(outbound, "route_client", lambda route: Client())
    manager = SimpleNamespace(get_session_summary=lambda sid: {"id": sid} if sid == "source" else None,
        _load_metadata=lambda sid: {"id": sid, "work_dir": str(tmp_path)})
    app = FastAPI()
    module.install(app, {"session_manager": manager}, SimpleNamespace(plugin_id="acp-agents"))
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1") as client:
            payload = {"origin": "source", "action": "task", "arguments": {"agent": "codex", "prompt": "test", "session_id": "saved", "background": True, "notify": "all"}, "request_id": "same-request-id"}
            assert (await client.post("/api/acp/outbound/requests", json=payload)).status_code == 403
            headers = {"Origin": "http://127.0.0.1"}
            bad = {**payload, "arguments": {**payload["arguments"], "recipient": "another-session"}}
            assert (await client.post("/api/acp/outbound/requests", headers=headers, json=bad)).status_code == 422
            assert calls == []
            response = await client.post("/api/acp/outbound/requests", headers=headers, json=payload)
            assert response.status_code == 200 and response.json()["operation_id"] == "accepted-operation"
            assert calls[0][0] == "session.send" and calls[0][1]["session_id"] == "source"
            assert calls[0][1]["runtime_override"]["limits"]["max_tool_calls"] == 1
            assert calls[0][2] == "acp-ui:same-request-id"
            assert '"session_id": "saved"' in calls[0][1]["message"]
    asyncio.run(scenario())


def test_only_readonly_catalog_query_reconnects_after_transport_loss(tmp_path):
    from acp_bridge.client import AgentTarget
    module = host_module()
    target = AgentTarget("codex", "node")
    key = module._catalog_key("source", target, str(tmp_path))
    calls, closed = [], []
    class Peer:
        busy = set()
        async def close(self):
            closed.append(True)
    class Service:
        peers = {("source", key[2], key[3], "authority"): Peer()}
        async def sessions(self, *args, **kwargs):
            calls.append(kwargs)
            if len(calls) == 1:
                raise ConnectionError("dead transport")
            return {"sessions": [], "next_cursor": "next-page"}
    async def scenario():
        result = await module._session_action(Service(), "source", target, str(tmp_path), {}, cursor="same-page")
        assert result["next_cursor"] == "next-page" and len(calls) == 2 and closed
        assert all(call["cursor"] == "same-page" for call in calls)
        calls.clear()
        with pytest.raises(ConnectionError):
            await module._session_action(Service(), "source", target, str(tmp_path), {}, new=True)
        assert len(calls) == 1
    asyncio.run(scenario())
