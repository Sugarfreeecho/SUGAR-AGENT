from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


APP = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP)) if str(APP) not in sys.path else None

import agent_mcp
from tool_registry import ToolOutcomeKind
from tool_result_status import tool_outcome_status


def server(monkeypatch, raw=None, error=None):
    async def call(_name, _arguments):
        if error is not None:
            raise error
        return raw

    monkeypatch.setattr(agent_mcp, "_fname_to_tool", {"demo": ("server", "action")})
    monkeypatch.setattr(agent_mcp, "_servers", {"server": SimpleNamespace(
        _task=SimpleNamespace(done=lambda: False), call_tool=call)})
    monkeypatch.setattr(agent_mcp, "_load_disabled_mcp_tools", lambda: set())
    # The loader stub must model a successful state read; production fails
    # closed until this flag is set. Never inherit the user's live state.
    monkeypatch.setattr(agent_mcp, "_disabled_mcp_tools_loaded", True)
    monkeypatch.setattr(agent_mcp, "_enabled_flag", lambda: True)
    monkeypatch.setattr(agent_mcp, "_unapproved_published_servers", lambda: frozenset())
    monkeypatch.setattr(agent_mcp, "get_tool_contract", lambda _: {})
    # Text-only results do not need the application's persistent image store.
    formatter = agent_mcp.format_call_tool_result
    monkeypatch.setattr(agent_mcp, "format_call_tool_result",
        lambda value, **kwargs: formatter(value, attachment_store=object(), **kwargs))


@pytest.mark.parametrize("is_error", [False, True])
@pytest.mark.parametrize("sdk_object", [False, True])
def test_protocol_flag_survives_content_formatting(monkeypatch, is_error, sdk_object):
    raw = {"isError": is_error, "content": [{"type": "text", "text": '{"error":false,"ok":true}'}]}
    server(monkeypatch, SimpleNamespace(**raw) if sdk_object else raw)
    outcome = asyncio.run(agent_mcp._invoke_tool_by_fname_impl("demo", {}, return_outcome=True))
    assert (outcome.kind is ToolOutcomeKind.FAILED) is is_error
    assert tool_outcome_status(outcome)["ok"] is not is_error
    assert tool_outcome_status(outcome)["source"] == "mcp_protocol"
    assert '{"error":false,"ok":true}' in outcome.content
    if is_error:
        assert outcome.code == "mcp_tool_error"
        assert "MCP tool returned an error." in outcome.content


def test_successful_mcp_result_can_contain_error_text(monkeypatch):
    server(monkeypatch, {"isError": False, "content": [{"type": "text", "text": "Error: this is documentation"}]})
    outcome = asyncio.run(agent_mcp._invoke_tool_by_fname_impl("demo", {}, return_outcome=True))
    assert outcome.kind is ToolOutcomeKind.COMPLETED
    assert outcome.content == "Error: this is documentation"
    # Existing callers retain the text API by default.
    assert asyncio.run(agent_mcp._invoke_tool_by_fname_impl("demo", {})) == outcome.content


def test_mcp_transport_failure_is_not_lost_as_plain_text(monkeypatch):
    server(monkeypatch, error=RuntimeError("connection lost"))
    outcome = asyncio.run(agent_mcp._invoke_tool_by_fname_impl("demo", {}, return_outcome=True))
    assert outcome.kind is ToolOutcomeKind.FAILED
    assert outcome.code == "mcp_invocation_error" and "connection lost" in outcome.content


def test_mcp_timeout_uses_exception_type_not_output_words(monkeypatch):
    server(monkeypatch, error=TimeoutError("waiting for server"))
    outcome = asyncio.run(agent_mcp._invoke_tool_by_fname_impl("demo", {}, return_outcome=True))
    assert outcome.kind is ToolOutcomeKind.FAILED
    assert outcome.code == "mcp_call_timed_out" and tool_outcome_status(outcome)["timed_out"]


@pytest.mark.parametrize("setup,code", [
    ("unknown", "mcp_unknown_tool"), ("disabled", "mcp_tool_disabled"),
    ("no_server", "mcp_server_unavailable"), ("no_contract", "mcp_isolation_contract_missing"),
    ("reconnect", "mcp_reconnect_error"),
])
def test_mcp_bridge_failures_have_explicit_outcomes(monkeypatch, setup, code):
    server(monkeypatch)
    if setup == "unknown":
        monkeypatch.setattr(agent_mcp, "_fname_to_tool", {})
    elif setup == "disabled":
        monkeypatch.setattr(agent_mcp, "_load_disabled_mcp_tools", lambda: {"demo"})
    elif setup == "no_server":
        monkeypatch.setattr(agent_mcp, "_servers", {})
    elif setup == "reconnect":
        async def restart():
            raise RuntimeError("reconnect failed")
        monkeypatch.setattr(agent_mcp, "_servers", {"server": SimpleNamespace(_task=None, _restart=restart)})
    outcome = asyncio.run(agent_mcp._invoke_tool_by_fname_impl("demo", {}, return_outcome=True,
        require_worktree_isolation=setup == "no_contract"))
    assert outcome.kind is ToolOutcomeKind.FAILED and outcome.code == code


def test_mcp_cancellation_propagates(monkeypatch):
    server(monkeypatch, error=asyncio.CancelledError())
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(agent_mcp._invoke_tool_by_fname_impl("demo", {}, return_outcome=True))
