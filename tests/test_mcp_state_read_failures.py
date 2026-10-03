"""Unreadable enablement state must remain retryable and must not be overwritten."""
import json
from pathlib import Path

import pytest


@pytest.fixture
def state(tmp_path, monkeypatch):
    import agent_mcp

    path = tmp_path / "mcp-state.json"
    path.write_text(json.dumps({"tools": {"mcp_demo_x": {"enabled": False}}}), encoding="utf-8")
    monkeypatch.setattr(agent_mcp, "_MCP_TOOLS_STATE_PATH", path)
    monkeypatch.setattr(agent_mcp, "_DEFAULT_MCP_TOOLS_STATE_PATH", path)
    monkeypatch.setattr(agent_mcp, "_LEGACY_MCP_TOOLS_STATE_PATH", tmp_path / "missing-legacy.json")
    monkeypatch.setattr(agent_mcp, "_disabled_mcp_tools_loaded", False)
    monkeypatch.setattr(agent_mcp, "_disabled_mcp_tools", {"remembered"})
    monkeypatch.setattr(agent_mcp, "_fname_to_tool", {"mcp_demo_x": ("demo", "x")})
    return agent_mcp, path


def test_transient_read_failure_retries_and_preserves_memory(state, monkeypatch):
    agent_mcp, path = state
    read = Path.read_text

    def failing_read(self, *args, **kwargs):
        if self == path:
            raise PermissionError("temporarily locked")
        return read(self, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "read_text", failing_read)
        assert agent_mcp._load_disabled_mcp_tools() == {"remembered"}
        assert not agent_mcp._disabled_mcp_tools_loaded
        assert not agent_mcp.is_mcp_tool_enabled("mcp_demo_x")
        assert not agent_mcp.is_mcp_tool_enabled("unknown_tool")
        with pytest.raises(OSError, match="refusing to overwrite"):
            agent_mcp.set_mcp_tool_enabled("mcp_demo_x", True)
    assert agent_mcp._load_disabled_mcp_tools() == {"mcp_demo_x"}
    assert agent_mcp._disabled_mcp_tools_loaded
    assert agent_mcp.is_mcp_tool_enabled("unknown_tool")
    assert json.loads(path.read_text())["tools"]["mcp_demo_x"]["enabled"] is False


@pytest.mark.parametrize("invalid", ["{broken", "[]", '{"tools": []}'])
def test_corrupt_state_is_not_overwritten_and_can_recover(state, invalid):
    agent_mcp, path = state
    path.write_text(invalid, encoding="utf-8")
    with pytest.raises(OSError, match="refusing to overwrite"):
        agent_mcp.set_mcp_tool_enabled("mcp_demo_x", True)
    assert path.read_text() == invalid
    assert not agent_mcp._disabled_mcp_tools_loaded
    path.write_text('{"tools":{"mcp_demo_x":{"enabled":false}}}', encoding="utf-8")
    assert agent_mcp._load_disabled_mcp_tools() == {"mcp_demo_x"}


def test_missing_state_is_a_healthy_default(state):
    agent_mcp, path = state
    path.unlink()
    assert agent_mcp._load_disabled_mcp_tools() == set()
    assert agent_mcp._disabled_mcp_tools_loaded
    assert agent_mcp.set_mcp_tool_enabled("mcp_demo_x", False)
