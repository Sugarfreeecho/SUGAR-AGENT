import asyncio
import json
import sys
import threading
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


def test_mcp_async_work_stays_on_one_loop_across_temporary_caller_loops(monkeypatch):
    import agent_mcp

    calls = []
    signature = {"value": "first"}

    class RunningTask:
        @staticmethod
        def done():
            return False

    class FakeServer:
        transport_label = "stdio"
        _task = RunningTask()

        async def start(self):
            calls.append(("start", id(asyncio.get_running_loop())))
            agent_mcp._fname_to_tool["mcp_demo_ping"] = ("demo", "ping")

        async def stop(self):
            calls.append(("stop", id(asyncio.get_running_loop())))

        async def call_tool(self, _name, _arguments):
            calls.append(("call", id(asyncio.get_running_loop())))
            return None

    monkeypatch.setattr(agent_mcp, "_MCP_IMPORT_OK", True)
    monkeypatch.setattr(agent_mcp, "_loaded_signature", None)
    monkeypatch.setattr(
        agent_mcp,
        "_compute_config_signature_cached",
        lambda: signature["value"],
    )
    monkeypatch.setattr(
        agent_mcp,
        "_load_servers_dict_from_config",
        lambda: ({"demo": {"transport": "stdio", "command": "demo-server"}}, None),
    )
    monkeypatch.setattr(
        "security.extensions.mcp_registration_is_approved",
        lambda _descriptor: True,
    )
    monkeypatch.setattr(agent_mcp, "_make_stdio_connector", lambda *_args: FakeServer())

    def invoke_from_temporary_loop():
        return asyncio.run(agent_mcp.invoke_tool_by_fname("mcp_demo_ping", {}))

    for _ in range(3):
        thread = threading.Thread(target=invoke_from_temporary_loop)
        thread.start()
        thread.join(timeout=5)
        assert not thread.is_alive()

    asyncio.run(agent_mcp.force_reload())
    signature["value"] = "second"
    invoke_from_temporary_loop()

    loop_ids = {loop_id for _operation, loop_id in calls}
    assert loop_ids == {id(agent_mcp._get_mcp_loop())}
    assert [operation for operation, _loop_id in calls].count("call") == 4

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


def test_list_registered_tools_returns_sorted_snapshot(monkeypatch):
    import agent_mcp

    monkeypatch.setattr(
        agent_mcp,
        "_fname_to_tool",
        {
            "mcp_b_alpha": ("server-b", "alpha"),
            "mcp_a_beta": ("server-a", "beta"),
        },
    )
    monkeypatch.setattr(
        agent_mcp,
        "_defs_snapshot",
        [
            {
                "type": "function",
                "function": {
                    "name": "mcp_b_alpha",
                    "description": "[MCP server `server-b`] Alpha tool",
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "mcp_a_beta",
                    "description": "[MCP server `server-a`] Beta tool",
                },
            },
        ],
    )

    tools = agent_mcp.list_registered_tools()

    assert [t["server"] for t in tools] == ["server-a", "server-b"]
    assert tools[0] == {
        "function_name": "mcp_a_beta",
        "server": "server-a",
        "tool_name": "beta",
        "description": "[MCP server `server-a`] Beta tool",
        "enabled": True,
    }
    assert tools[1]["tool_name"] == "alpha"


def test_mcp_tools_endpoint_returns_registered_tools(monkeypatch):
    import webui

    async def ensure_started():
        return None

    def list_registered_tools():
        return [{"function_name": "mcp_demo_x", "server": "demo", "tool_name": "x"}]

    monkeypatch.setattr(webui.agent_mcp, "ensure_started", ensure_started)
    monkeypatch.setattr(webui.agent_mcp, "list_registered_tools", list_registered_tools)

    response = asyncio.run(webui.list_mcp_tools())

    assert response.status_code == 200
    body = json.loads(response.body)
    assert body["ok"] is True
    assert body["tools"] == [{"function_name": "mcp_demo_x", "server": "demo", "tool_name": "x"}]


def test_mcp_tool_enablement_persists_and_filters_definitions(monkeypatch, tmp_path):
    import agent_mcp

    async def ensure_started():
        return None

    monkeypatch.setattr(agent_mcp, "_MCP_TOOLS_STATE_PATH", tmp_path / "mcp_tools_state.json")
    monkeypatch.setattr(agent_mcp, "_disabled_mcp_tools_loaded", False)
    monkeypatch.setattr(agent_mcp, "_disabled_mcp_tools", set())
    monkeypatch.setattr(
        agent_mcp,
        "_fname_to_tool",
        {"mcp_demo_x": ("demo", "x")},
    )
    monkeypatch.setattr(
        agent_mcp,
        "_defs_snapshot",
        [
            {
                "type": "function",
                "function": {
                    "name": "mcp_demo_x",
                    "description": "[MCP server `demo`] X tool",
                },
            }
        ],
    )
    monkeypatch.setattr(agent_mcp, "ensure_started", ensure_started)

    assert agent_mcp.set_mcp_tool_enabled("mcp_demo_x", False) is True
    assert agent_mcp.is_mcp_tool_enabled("mcp_demo_x") is False
    assert asyncio.run(agent_mcp.get_tool_definitions()) == []
    tools = agent_mcp.list_registered_tools()
    assert tools[0]["function_name"] == "mcp_demo_x"
    assert tools[0]["enabled"] is False
    assert "disabled" in asyncio.run(
        agent_mcp.invoke_tool_by_fname("mcp_demo_x", {})
    )

    assert agent_mcp.set_mcp_tool_enabled("mcp_demo_x", True) is True
    assert agent_mcp.is_mcp_tool_enabled("mcp_demo_x") is True
    assert [d["function"]["name"] for d in asyncio.run(agent_mcp.get_tool_definitions())] == [
        "mcp_demo_x"
    ]
    assert agent_mcp.list_registered_tools()[0]["enabled"] is True


def test_mcp_tool_enablement_endpoint_rejects_unknown_and_non_boolean(monkeypatch):
    import webui

    response = asyncio.run(
        webui.set_mcp_tool_enabled_api(
            "mcp_unknown",
            _json_request({"enabled": True}),
        )
    )
    assert response.status_code == 404

    response = asyncio.run(
        webui.set_mcp_tool_enabled_api(
            "mcp_demo_x",
            _json_request({"enabled": "yes"}),
        )
    )
    assert response.status_code == 400
