import asyncio
import json
import sys
from pathlib import Path

from starlette.requests import Request


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


def test_mcp_config_signature_uses_short_cache(monkeypatch):
    import agent_mcp

    calls = {"signature": 0}
    now = {"value": 100.0}

    def compute():
        calls["signature"] += 1
        return f"sig-{calls['signature']}"

    monkeypatch.setattr(agent_mcp, "_signature_cache", None)
    monkeypatch.setattr(agent_mcp, "_compute_config_signature", compute)
    monkeypatch.setattr(agent_mcp.time, "monotonic", lambda: now["value"])

    assert agent_mcp._compute_config_signature_cached() == "sig-1"
    assert agent_mcp._compute_config_signature_cached() == "sig-1"
    assert calls["signature"] == 1

    now["value"] += agent_mcp._SIGNATURE_CACHE_TTL_SEC + 0.01
    assert agent_mcp._compute_config_signature_cached() == "sig-2"
    assert calls["signature"] == 2


def test_mcp_force_reload_clears_signature_cache(monkeypatch):
    import agent_mcp

    monkeypatch.setattr(agent_mcp, "_signature_cache", (100.0, "stale"))

    async def noop_shutdown():
        return None

    monkeypatch.setattr(agent_mcp, "_shutdown_servers_unlocked", noop_shutdown)

    asyncio.run(agent_mcp.force_reload())

    assert agent_mcp._signature_cache is None
    assert agent_mcp._loaded_signature is None


def test_unconfirmed_mcp_is_not_connected(monkeypatch):
    import agent_mcp

    calls = []
    monkeypatch.setattr(agent_mcp, "_MCP_IMPORT_OK", True)
    monkeypatch.setattr(agent_mcp, "_loaded_signature", None)
    monkeypatch.setattr(agent_mcp, "_compute_config_signature_cached", lambda: "pending")
    monkeypatch.setattr(
        agent_mcp,
        "_load_servers_dict_from_config",
        lambda: ({"demo": {"transport": "stdio", "command": "demo-server"}}, None),
    )
    monkeypatch.setattr(
        "security.extensions.mcp_registration_is_approved",
        lambda _descriptor: False,
    )
    monkeypatch.setattr(
        agent_mcp,
        "_make_stdio_connector",
        lambda *_args, **_kwargs: calls.append("connected"),
    )

    asyncio.run(agent_mcp.ensure_started())

    assert calls == []
    assert "demo" not in agent_mcp._servers


def test_confirmed_mcp_is_connected(monkeypatch):
    import agent_mcp

    calls = []

    class FakeServer:
        transport_label = "stdio"

        async def start(self):
            calls.append("started")

        async def stop(self):
            calls.append("stopped")

    monkeypatch.setattr(agent_mcp, "_MCP_IMPORT_OK", True)
    monkeypatch.setattr(agent_mcp, "_loaded_signature", None)
    monkeypatch.setattr(agent_mcp, "_compute_config_signature_cached", lambda: "confirmed")
    monkeypatch.setattr(
        agent_mcp,
        "_load_servers_dict_from_config",
        lambda: ({"demo": {"transport": "stdio", "command": "demo-server"}}, None),
    )
    monkeypatch.setattr(
        "security.extensions.mcp_registration_is_approved",
        lambda _descriptor: True,
    )
    monkeypatch.setattr(agent_mcp, "_make_stdio_connector", lambda *_args, **_kwargs: FakeServer())

    asyncio.run(agent_mcp.ensure_started())

    assert calls == ["started"]
    assert "demo" in agent_mcp._servers

    asyncio.run(agent_mcp.force_reload())


def _json_request(payload):
    body = json.dumps(payload).encode("utf-8")

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    return Request(
        {"type": "http", "method": "POST", "path": "/", "headers": []},
        receive,
    )


def test_mcp_registration_endpoint_starts_only_after_approval(monkeypatch):
    import security.extensions as extensions
    import security.runtime as security_runtime
    import webui

    calls = []

    class FakeStore:
        def audit(self, **kwargs):
            calls.append(("audit", kwargs["outcome"]))

    async def force_reload():
        calls.append("reload")

    async def ensure_started():
        calls.append("start")

    monkeypatch.setattr(
        extensions,
        "decide_current_mcp_registration",
        lambda extension_id, config_digest, approved: {
            "extension_id": extension_id,
            "config_digest": config_digest,
            "runtime": "stdio",
            "registration_status": "registered" if approved else "rejected",
        },
    )
    monkeypatch.setattr(security_runtime, "security_store", lambda: FakeStore())
    monkeypatch.setattr(webui.agent_mcp, "force_reload", force_reload)
    monkeypatch.setattr(webui.agent_mcp, "ensure_started", ensure_started)

    response = asyncio.run(
        webui.decide_mcp_registration(
            "demo",
            _json_request({"approved": True, "config_digest": "digest"}),
        )
    )

    assert response.status_code == 200
    assert json.loads(response.body)["registration"]["registration_status"] == "registered"
    assert calls == [("audit", "allow"), "reload", "start"]


def test_mcp_registration_endpoint_rejects_non_boolean_decision():
    import webui

    response = asyncio.run(
        webui.decide_mcp_registration(
            "demo",
            _json_request({"approved": "false", "config_digest": "digest"}),
        )
    )

    assert response.status_code == 422
