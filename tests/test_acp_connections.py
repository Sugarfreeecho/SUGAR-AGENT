"""Connection observability must reflect leases, ownership and actual execution."""
import asyncio
import json
import sys
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
from acp_bridge.connections import ConnectionRegistry, STALE_SECONDS, RETAIN_SECONDS, MAX_CONNECTIONS
from acp_bridge.backend import RuntimeBackend


def test_connection_lease_activity_disconnect_and_retention():
    now = [1000.0]
    registry = ConnectionRegistry(clock=lambda: now[0])
    registry.register("person", "c1", {"client": {"name": "DSH", "version": "1.4.0"}, "protocol_version": 1})
    registry.attach("person", "c1", "s1", "D:/Workspace", "Chat")
    activity = registry.snapshot()["connections"][0]["last_activity"]
    now[0] += 15
    registry.heartbeat("person", "c1", {"busy_session_ids": []})
    row = registry.snapshot()["connections"][0]
    assert row["last_activity"] == activity and row["last_seen"] != activity
    registry.heartbeat("person", "c1", {"busy_session_ids": ["s1"], "activity": "prompt"})
    assert registry.snapshot()["connections"][0]["busy"]
    now[0] += STALE_SECONDS + 1
    snapshot = registry.snapshot()
    assert snapshot["online_count"] == snapshot["session_count"] == 0
    assert snapshot["connections"][0]["status"] == "stale"
    assert not snapshot["connections"][0]["busy"]
    registry.heartbeat("person", "c1", {"busy_session_ids": [], "activity": "completed"})
    assert registry.snapshot()["online_count"] == 1
    registry.disconnect("person", "c1")
    row = registry.snapshot()["connections"][0]
    assert row["status"] == "disconnected" and not row["sessions"][0]["attached"]
    with pytest.raises(KeyError):
        registry.heartbeat("person", "c1", {})
    now[0] += RETAIN_SECONDS + 1
    assert registry.snapshot()["connections"] == []


def test_connection_identity_isolation_and_metadata_projection():
    registry = ConnectionRegistry()
    for owner in ("one", "two"):
        registry.register(owner, "same", {"client": {"name": "Editor\n\x00safe", "token": "secret"}, "protocol_version": 1})
    registry.attach("one", "same", "s1", "D:/One")
    with pytest.raises(ValueError):
        registry.heartbeat("two", "same", {"busy_session_ids": ["s1"]})
    registry.disconnect("two", "same")
    snapshot = registry.snapshot(owner="one")
    assert snapshot["online_count"] == snapshot["session_count"] == 1
    wire = json.dumps(snapshot)
    assert '"owner"' not in wire and "secret" not in wire and "token" not in wire
    assert snapshot["connections"][0]["client"]["name"] == "Editor safe"
    registry.detach("one", "same", "s1")
    assert registry.snapshot(owner="one")["session_count"] == 0


def test_registry_bound_and_invalid_telemetry():
    registry = ConnectionRegistry()
    for n in range(MAX_CONNECTIONS):
        registry.register("one", str(n), {"protocol_version": 1})
    with pytest.raises(ValueError):
        registry.register("one", "overflow", {"protocol_version": 1})
    registry.disconnect("one", "0")
    registry.register("one", "replacement", {"protocol_version": 1})
    assert len(registry.snapshot()["connections"]) == MAX_CONNECTIONS
    with pytest.raises(ValueError):
        registry.register("one", "bad", {"protocol_version": True})
    with pytest.raises(ValueError):
        registry.heartbeat("one", "replacement", {"prompt": "should not be recorded"})


def test_runtime_monitors_failed_prompt_and_disconnect_without_leaking_payloads():
    calls = []
    async def handler(request):
        body = json.loads(request.content) if request.content else None
        calls.append((request.url.path, request.method, body))
        assert request.headers["Authorization"] == "Bearer private-token"
        assert request.headers["X-MyAgent-ACP-Connection"]
        if request.url.path.endswith("/status"):
            return httpx.Response(200, json={"connection_monitoring": True})
        if request.url.path.endswith("/rpc"):
            return httpx.Response(403, json={"ok": False, "error": {"code": "denied", "message": "denied"}})
        return httpx.Response(200, json={"ok": True})
    async def scenario():
        client = httpx.AsyncClient(base_url="http://127.0.0.1", transport=httpx.MockTransport(handler))
        backend = RuntimeBackend("http://127.0.0.1", token="private-token", client=client)
        await backend.request("GET", "/api/acp/status")
        await backend.register_connection({"name": "DSH", "version": "1.4.0"}, 1)
        assert backend.monitor_task and not backend.monitor_task.done()
        with pytest.raises(Exception):
            async for _ in backend.events("s1", "r1", "private prompt"):
                pass
        assert backend.busy_sessions == set()
        task = backend.monitor_task
        await backend.close()
        assert task.done() and client.is_closed
    asyncio.run(scenario())
    telemetry = [(path, method, body) for path, method, body in calls if path.startswith("/api/acp/connections")]
    assert telemetry[0][2]["client"]["name"] == "DSH"
    heartbeats = [body for path, method, body in telemetry if path.endswith("heartbeat")]
    assert heartbeats[0] == {"busy_session_ids": ["s1"], "activity": "prompt"}
    assert heartbeats[-1] == {"busy_session_ids": [], "activity": "completed"}
    assert telemetry[-1][1] == "DELETE"
    assert "private" not in json.dumps(telemetry)


def test_runtime_old_host_needs_no_monitoring_routes():
    async def scenario():
        async def handler(request):
            assert request.url.path == "/api/acp/status"
            return httpx.Response(200, json={"protocol": "acp", "version": 1})
        backend = RuntimeBackend("http://127.0.0.1", token="test", client=httpx.AsyncClient(
            base_url="http://127.0.0.1", transport=httpx.MockTransport(handler)))
        await backend.request("GET", "/api/acp/status")
        await backend.register_connection({"name": "old-host"}, 1)
        await backend.close()
    asyncio.run(scenario())
