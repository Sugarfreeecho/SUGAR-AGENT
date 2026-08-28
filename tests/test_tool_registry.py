from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from tool_registry import (  # noqa: E402
    DuplicateToolError,
    ToolDescriptor,
    ToolInvocationKind,
    ToolOutcome,
    ToolRegistry,
    ToolRegistryError,
)
from host_tool_registry import (  # noqa: E402
    HostToolInvocationContext,
    HostToolInvokerRegistry,
)


def _definition(name: str, description: str = "demo") -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    }


def test_registry_preserves_order_and_definition_isolation():
    first = _definition("read_demo")
    registry = ToolRegistry()
    registry.register_definition(
        first,
        invocation_kind=ToolInvocationKind.HOST,
        owner="core.tools",
    )
    registry.register_definition(
        _definition("plugin_demo__run"),
        invocation_kind=ToolInvocationKind.PLUGIN,
        owner="demo",
    )

    first["function"]["description"] = "mutated outside"
    exported = registry.definitions()
    exported[0]["function"]["description"] = "mutated export"

    assert [item.name for item in registry.descriptors()] == [
        "read_demo",
        "plugin_demo__run",
    ]
    assert registry.require("read_demo").openai_definition()["function"][
        "description"
    ] == "demo"
    assert registry.names(executable_only=True) == {
        "read_demo",
        "plugin_demo__run",
    }


def test_registry_rejects_conflicting_tool_names_with_owner_diagnostics():
    registry = ToolRegistry()
    registry.register_definition(
        _definition("same_name"),
        invocation_kind="host",
        owner="core.tools",
    )

    with pytest.raises(DuplicateToolError) as exc_info:
        registry.register_definition(
            _definition("same_name"),
            invocation_kind="plugin",
            owner="third.party",
        )

    message = str(exc_info.value)
    assert "core.tools" in message
    assert "third.party" in message


def test_unavailable_descriptor_is_advertised_but_not_executable():
    registry = ToolRegistry()
    descriptor = registry.register_definition(
        _definition("inherited_missing"),
        invocation_kind=ToolInvocationKind.UNAVAILABLE,
        owner="inherited",
    )

    assert descriptor.executable is False
    assert registry.names() == {"inherited_missing"}
    assert registry.names(executable_only=True) == set()
    assert registry.definitions()[0]["function"]["name"] == "inherited_missing"

    with pytest.raises(ToolRegistryError):
        ToolDescriptor.from_openai_definition(
            _definition("bad"),
            invocation_kind=ToolInvocationKind.UNAVAILABLE,
            owner="inherited",
            executable=True,
        )


def test_descriptor_validates_model_definition_and_owner():
    with pytest.raises(ToolRegistryError, match="function.name"):
        ToolDescriptor.from_openai_definition(
            {"type": "function", "function": {}},
            invocation_kind="host",
            owner="core.tools",
        )
    with pytest.raises(ToolRegistryError, match="owner"):
        ToolDescriptor.from_openai_definition(
            _definition("demo"),
            invocation_kind="host",
            owner="",
        )


def test_tool_outcome_contract_covers_completed_failed_deferred_and_interaction():
    assert ToolOutcome.completed({"ok": True}).to_dict() == {
        "type": "completed",
        "content": {"ok": True},
    }
    assert ToolOutcome.failed(
        "permission_denied", "blocked", retryable=False
    ).to_dict() == {
        "type": "failed",
        "code": "permission_denied",
        "message": "blocked",
        "retryable": False,
    }
    assert ToolOutcome.deferred("opaque", 30).to_dict() == {
        "type": "deferred",
        "token": "opaque",
        "deadline_seconds": 30.0,
    }
    assert ToolOutcome.interaction("question-1").to_dict() == {
        "type": "interaction",
        "request_id": "question-1",
    }
    assert ToolOutcome.failed(
        "invalid", "bad input", content={"field": "name"}
    ).to_dict()["content"] == {"field": "name"}


def test_host_invoker_registry_normalizes_success_failure_and_exceptions():
    registry = HostToolInvokerRegistry()
    context = HostToolInvocationContext(session_id="session-1")

    async def successful(_context, arguments):
        return ToolOutcome.completed({"value": arguments["value"]})

    registry.register("success", successful)
    registry.register("invalid", lambda _context, _arguments: "not-an-outcome")
    registry.register("raises", lambda _context, _arguments: 1 / 0)

    assert asyncio.run(registry.invoke("success", context, {"value": 7})).content == {
        "value": 7
    }
    assert asyncio.run(registry.invoke("missing", context, {})).code == "host_invoker_unavailable"
    assert asyncio.run(registry.invoke("invalid", context, {})).code == "invalid_host_outcome"
    assert asyncio.run(registry.invoke("raises", context, {})).code == "host_invocation_error"


def test_host_invoker_rechecks_dynamic_enablement_at_call_time():
    registry = HostToolInvokerRegistry()
    context = HostToolInvocationContext(session_id="session-1")
    enabled = {"value": True}
    calls = []
    registry.register(
        "dynamic",
        lambda _context, _arguments: (
            calls.append("called") or ToolOutcome.completed({"ok": True})
        ),
        enabled=lambda: enabled["value"],
    )

    assert asyncio.run(registry.invoke("dynamic", context, {})).kind.value == "completed"
    enabled["value"] = False
    disabled = asyncio.run(registry.invoke("dynamic", context, {}))

    assert disabled.code == "host_invoker_disabled"
    assert calls == ["called"]


def test_builtin_todo_invoker_dual_writes_extension_state(tmp_path):
    import importlib.util
    from runtime_v2 import SnapshotStore

    path = ROOT / "plugins/session-todo/host.py"
    spec = importlib.util.spec_from_file_location("test_session_todo_host", path)
    todo_host = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(todo_host)

    class SessionManager:
        sessions_dir = tmp_path

    class TodoManager:
        def __init__(self):
            self._by_session = {}

        def update_for_session(self, session_id, items):
            self._by_session[session_id] = list(items)
            return "updated"

    (tmp_path / "s1").mkdir()
    events = []

    async def publish(event):
        events.append(dict(event))

    context = HostToolInvocationContext(
        session_id="s1",
        run_id="run-1",
        state={},
        emit_event=publish,
        services={
            "session_manager": SessionManager(),
            "session_plan_store": TodoManager(),
        },
    )
    outcome = asyncio.run(
        todo_host._invoke_update_todo(
            context,
            {"items": [{"id": "1", "text": "ship", "status": "pending"}]},
        )
    )

    assert outcome.content == "updated"
    assert events[-1] == {
        "type": "extension_state_changed",
        "plugin_id": "session-todo",
        "namespace": "plan",
        "revision": 1,
        "_runtime_v2_committed": True,
    }
    snapshot = SnapshotStore(tmp_path).read("s1")
    assert snapshot["extensions"]["session-todo"]["plan"]["value"]["items"] == [
        {"id": "1", "text": "ship", "status": "pending"}
    ]


@pytest.mark.parametrize(
    "factory",
    [
        lambda: ToolOutcome.failed("", "missing code"),
        lambda: ToolOutcome.deferred("", 30),
        lambda: ToolOutcome.deferred("opaque", 0),
        lambda: ToolOutcome.interaction(""),
    ],
)
def test_tool_outcome_rejects_incomplete_suspended_or_failed_states(factory):
    with pytest.raises(ToolRegistryError):
        factory()


def test_agent_catalog_records_tool_sources_without_name_prefixes(monkeypatch):
    import agent_extensions
    import agent_loop
    import agent_mcp
    import agent_subagent

    host = _definition("local_action")
    mcp = _definition("remote_action")
    plugin = _definition("business_action")

    async def mcp_definitions():
        return [mcp]

    async def plugin_definitions():
        return [plugin]

    async def plugin_contracts():
        return {"business_action": {"effect": "read"}}

    monkeypatch.setattr(agent_loop, "OPENAI_TOOL_DEFINITIONS", [host])
    monkeypatch.setattr(agent_loop, "tools_dict", {"local_action": lambda: None})
    monkeypatch.setattr(agent_extensions, "bundled_host_tool_definitions", lambda **_kwargs: [])
    monkeypatch.setattr(agent_mcp, "get_tool_definitions", mcp_definitions)
    monkeypatch.setattr(
        agent_extensions, "plugin_tool_definitions", plugin_definitions
    )
    monkeypatch.setattr(agent_extensions, "plugin_tool_contracts", plugin_contracts)
    monkeypatch.setattr(
        agent_subagent, "filter_tools_for_session", lambda rows, _meta: rows
    )
    monkeypatch.setattr(agent_subagent, "inject_task_model_profiles", lambda rows: rows)

    registry = asyncio.run(
        agent_loop.build_combined_tool_registry_for_session(
            "session-1", session_meta={}
        )
    )

    assert registry.require("local_action").invocation_kind is ToolInvocationKind.HOST
    assert registry.require("remote_action").invocation_kind is ToolInvocationKind.MCP
    assert (
        registry.require("business_action").invocation_kind
        is ToolInvocationKind.PLUGIN
    )
    assert registry.require("business_action").effect == "read"
    assert registry.require("business_action").parallel_safe is True
    assert registry.names(executable_only=True) == {
        "local_action",
        "remote_action",
        "business_action",
    }


def test_builtin_host_services_are_bound_to_registered_invokers(monkeypatch):
    import agent_extensions
    import agent_loop
    import agent_mcp
    import agent_subagent

    async def no_definitions():
        return []

    definitions = [_definition("ask_user")]
    monkeypatch.setattr(agent_loop, "OPENAI_TOOL_DEFINITIONS", definitions)
    monkeypatch.setattr(agent_mcp, "get_tool_definitions", no_definitions)
    monkeypatch.setattr(agent_extensions, "plugin_tool_definitions", no_definitions)
    monkeypatch.setattr(agent_subagent, "filter_tools_for_session", lambda rows, _meta: rows)
    monkeypatch.setattr(agent_subagent, "inject_task_model_profiles", lambda rows: rows)

    registry = asyncio.run(
        agent_loop.build_combined_tool_registry_for_session("session-1", session_meta={})
    )

    for name in ("create_goal", "update_todo", "ask_user"):
        descriptor = registry.require(name)
        assert descriptor.invocation_kind is ToolInvocationKind.HOST_SERVICE
        assert descriptor.invoker_id == name


def test_agent_catalog_marks_unknown_inherited_definition_unavailable(monkeypatch):
    import agent_extensions
    import agent_loop
    import agent_mcp
    import agent_subagent

    async def no_definitions():
        return []

    monkeypatch.setattr(agent_loop, "OPENAI_TOOL_DEFINITIONS", [])
    monkeypatch.setattr(agent_loop, "tools_dict", {})
    monkeypatch.setattr(agent_extensions, "bundled_host_tool_definitions", lambda **_kwargs: [])
    monkeypatch.setattr(agent_mcp, "get_tool_definitions", no_definitions)
    monkeypatch.setattr(agent_extensions, "plugin_tool_definitions", no_definitions)
    monkeypatch.setattr(
        agent_subagent, "filter_tools_for_session", lambda rows, _meta: rows
    )
    monkeypatch.setattr(agent_subagent, "inject_task_model_profiles", lambda rows: rows)

    registry = asyncio.run(
        agent_loop.build_combined_tool_registry_for_session(
            "child",
            session_meta={
                "fork_runtime_config": {"tools": [_definition("missing_parent_tool")]}
            },
        )
    )

    descriptor = registry.require("missing_parent_tool")
    assert descriptor.invocation_kind is ToolInvocationKind.UNAVAILABLE
    assert descriptor.executable is False


def test_agent_loop_dispatches_external_tools_by_registry_kind():
    source = (APP_DIR / "agent_loop.py").read_text(encoding="utf-8")

    assert "tool_registry = await build_combined_tool_registry_for_session(" in source
    assert "tool_registry.names(executable_only=True)" in source
    assert (
        "tool_descriptor.invocation_kind is ToolInvocationKind.MCP" in source
    )
    assert (
        "tool_descriptor.invocation_kind is ToolInvocationKind.PLUGIN" in source
    )
    assert 'if tool_name.startswith("mcp_"):' not in source
    assert 'if tool_name.startswith("plugin_"):' not in source
