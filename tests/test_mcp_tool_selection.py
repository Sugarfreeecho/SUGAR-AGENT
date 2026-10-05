from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from starlette.requests import Request

APP = Path(__file__).resolve().parents[1] / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))


@pytest.fixture
def mcp(monkeypatch, tmp_path):
    import agent_mcp
    monkeypatch.setattr(agent_mcp, "_fname_to_tool", {})
    monkeypatch.setattr(agent_mcp, "_defs_snapshot", [])
    monkeypatch.setattr(agent_mcp, "_tool_contracts", {})
    monkeypatch.setattr(agent_mcp, "_tool_selections", {})
    monkeypatch.setattr(agent_mcp, "_disabled_mcp_tools", set())
    monkeypatch.setattr(agent_mcp, "_disabled_mcp_tools_loaded", True)
    monkeypatch.setattr(agent_mcp, "_host_reserved_servers", set())
    monkeypatch.setattr(agent_mcp, "_MCP_TOOLS_STATE_PATH", tmp_path / "mcp_tools_state.json")
    return agent_mcp


def tool(name):
    return SimpleNamespace(name=name, description="tool " + name,
                           inputSchema={"type": "object", "properties": {}})


def test_selection_filters_registration_and_pin_uses_original_or_function_name(mcp):
    mcp._tool_selections["demo"] = mcp._parse_tool_selection({"tools": {
        "include": ["read", "mcp_demo_write"], "exclude": ["write"], "pin": ["read"]}})
    assert mcp._register_tools_globally("demo", [tool("read"), tool("write"), tool("unused")]) == 1
    assert set(mcp._fname_to_tool) == {"mcp_demo_read"}
    assert mcp.get_pinned_tool_names() == {"mcp_demo_read"}
    assert mcp.list_registered_tools()[0]["pinned"] is True
    mcp._tool_selections["demo"] = mcp._parse_tool_selection({"tools": {"pin": ["mcp_demo_write"]}})
    mcp._register_tools_globally("demo", [tool("write")])
    assert set(mcp._fname_to_tool) == {"mcp_demo_write"}
    assert mcp.get_pinned_tool_names() == {"mcp_demo_write"}
    mcp._register_tools_globally("demo", [])
    assert not mcp._defs_snapshot
    assert not mcp._fname_to_tool


@pytest.mark.parametrize("raw", [{"tools": []}, {"tools": {"include": "read"}},
    {"tools": {"pin": [True]}}, {"tools": {"exclude": [""]}}])
def test_invalid_selection_is_rejected(mcp, raw):
    with pytest.raises(ValueError):
        mcp._parse_tool_selection(raw)


def test_bulk_toggle_is_atomic_persisted_and_does_not_touch_other_servers(mcp, monkeypatch):
    mcp._register_tools_globally("demo", [tool("read"), tool("write")])
    mcp._register_tools_globally("other", [tool("read")])
    generation = mcp._tool_catalog_generation
    assert mcp.set_mcp_server_tools_enabled("demo", False)
    assert mcp._tool_catalog_generation == generation + 1
    state = json.loads(mcp._MCP_TOOLS_STATE_PATH.read_text())
    assert set(state["tools"]) == {"mcp_demo_read", "mcp_demo_write"}
    assert mcp.is_mcp_tool_enabled("mcp_other_read")
    assert not mcp.is_mcp_tool_enabled("mcp_demo_read")
    async def no_start():
        pass
    monkeypatch.setattr(mcp, "ensure_started", no_start)
    assert [d["function"]["name"] for d in asyncio.run(mcp.get_tool_definitions())] == ["mcp_other_read"]
    assert mcp.set_mcp_server_tools_enabled("demo", True)
    assert not json.loads(mcp._MCP_TOOLS_STATE_PATH.read_text())["tools"]
    assert not mcp.set_mcp_server_tools_enabled("missing", True)
    mcp._host_reserved_servers.add("demo")
    with pytest.raises(ValueError, match="Host-managed"):
        mcp.set_mcp_server_tools_enabled("demo", False)


def request(raw):
    async def receive():
        return {"type": "http.request", "body": json.dumps(raw).encode(), "more_body": False}
    return Request({"type": "http", "method": "POST", "path": "/", "headers": []}, receive)


def test_disclosure_config_api_validates_and_off_overrides_environment(tmp_path, monkeypatch):
    import webui
    import tool_search
    monkeypatch.setattr(tool_search, "CONFIG_PATH", tmp_path / "tool_search.json")
    monkeypatch.setattr(tool_search, "_config_cache", None)
    monkeypatch.setenv("MYAGENT_TOOL_SEARCH", "on")
    saved = asyncio.run(webui.set_tool_search_config_api(request({"enabled": "off"})))
    assert saved.status_code == 200
    loaded = json.loads(asyncio.run(webui.get_tool_search_config_api()).body)
    assert loaded["config"]["enabled"] == "off"
    assert loaded["environment_override"] == "on"
    invalid = asyncio.run(webui.set_tool_search_config_api(request({"threshold_pct": -1})))
    assert invalid.status_code == 400
    assert tool_search.load_config().enabled == "off"


def test_bulk_api_requires_boolean_and_blocks_host_managed_server(mcp):
    import webui
    mcp._register_tools_globally("demo", [tool("read")])
    assert asyncio.run(webui.set_mcp_server_tools_enabled_api("demo", request({"enabled": "false"}))).status_code == 400
    assert asyncio.run(webui.set_mcp_server_tools_enabled_api("demo", request({"enabled": False}))).status_code == 200
    assert asyncio.run(webui.set_mcp_server_tools_enabled_api("missing", request({"enabled": False}))).status_code == 404
    mcp._host_reserved_servers.add("demo")
    assert asyncio.run(webui.set_mcp_server_tools_enabled_api("demo", request({"enabled": False}))).status_code == 400
