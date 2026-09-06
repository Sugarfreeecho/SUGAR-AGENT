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


def test_tool_registry_revalidate_runs_in_background(monkeypatch):
    import types

    import agent_loop

    fresh_registry = types.SimpleNamespace(
        definitions=lambda: [{"type": "function", "function": {"name": "fresh_tool"}}]
    )
    build_calls: list = []

    async def fake_build(session_id, session_meta=None, **_kwargs):
        build_calls.append(session_id)
        return fresh_registry

    monkeypatch.setattr(agent_loop, "build_combined_tool_registry_for_session", fake_build)

    stale_registry = types.SimpleNamespace(
        definitions=lambda: [{"type": "function", "function": {"name": "stale_tool"}}]
    )
    state = {
        "session_id": "session-1",
        "_combined_tool_registry_cache": {
            "revision": ("old",),
            "registry": stale_registry,
            "definitions": stale_registry.definitions(),
        },
    }

    async def driver():
        scheduled = agent_loop._schedule_tool_registry_revalidate(state, {}, ("new",))
        assert scheduled is True
        assert state["_tool_registry_revalidating"] is True
        # The stale cache must stay untouched until the background rebuild lands.
        assert state["_combined_tool_registry_cache"]["revision"] == ("old",)
        task = state.get("_tool_registry_revalidate_task")
        assert task is not None
        await task
        assert state["_combined_tool_registry_cache"]["revision"] == ("new",)
        assert state["_combined_tool_registry_cache"]["registry"] is fresh_registry
        assert "_tool_registry_revalidating" not in state

    asyncio.run(driver())
    assert build_calls == ["session-1"]

    # While a rebuild is already in flight, the helper must not schedule another.
    state["_tool_registry_revalidating"] = True
    assert agent_loop._schedule_tool_registry_revalidate(state, {}, ("newer",)) is True
    assert build_calls == ["session-1"]


def test_tool_registry_revalidate_swallows_build_failure(monkeypatch):
    import types

    import agent_loop

    stale_registry = types.SimpleNamespace(
        definitions=lambda: [{"type": "function", "function": {"name": "stale_tool"}}]
    )
    state = {
        "session_id": "session-1",
        "_combined_tool_registry_cache": {
            "revision": ("old",),
            "registry": stale_registry,
            "definitions": stale_registry.definitions(),
        },
    }

    async def failing_build(session_id, session_meta=None, **_kwargs):
        raise RuntimeError("mcp unavailable")

    monkeypatch.setattr(agent_loop, "build_combined_tool_registry_for_session", failing_build)

    async def driver():
        assert agent_loop._schedule_tool_registry_revalidate(state, {}, ("new",)) is True
        await state["_tool_registry_revalidate_task"]
        assert state["_combined_tool_registry_cache"]["revision"] == ("old",)
        assert "_tool_registry_revalidating" not in state

    asyncio.run(driver())


def test_host_invoker_restatement_keeps_revision_stable():
    from host_tool_registry import HostToolInvokerRegistry
    from tool_execution_policy import ToolExecutionPolicy

    registry = HostToolInvokerRegistry()

    def make_invoker():
        async def _invoke(_context):
            return None
        return _invoke

    policy = ToolExecutionPolicy(effect="control", interruptibility="cooperative")
    first = registry.register(
        "demo_tool",
        make_invoker(),
        replace=True,
        enabled=lambda: True,
        owner="demo",
        policy=policy,
    )
    gen_after_first = registry.catalog_revision()[0]
    assert gen_after_first >= 1

    for _ in range(5):
        registry.register(
            "demo_tool",
            make_invoker(),
            replace=True,
            enabled=lambda: True,
            owner="demo",
            policy=policy,
        )
    assert registry.catalog_revision()[0] == gen_after_first

    # A real change (different owner) must still bump the generation.
    registry.register(
        "demo_tool",
        make_invoker(),
        replace=True,
        enabled=lambda: True,
        owner="demo2",
        policy=policy,
    )
    assert registry.catalog_revision()[0] == gen_after_first + 1
    assert registry.resolve("demo_tool") is not None


def test_static_segments_revalidate_serves_stale_and_rebuilds(monkeypatch):
    import types

    import agent_loop

    monkeypatch.setattr(agent_loop, "build_static_system_segments", lambda *a, **k: ["seg-v2"])
    monkeypatch.setattr(agent_loop, "get_skills_catalog", lambda: "skills")
    monkeypatch.setattr(agent_loop, "build_env_static", lambda sid=None: "env")
    monkeypatch.setattr(
        agent_loop,
        "_build_static_segments_for_session",
        lambda sid, meta, lang: ("seg-v2",),
    )

    state = {"session_id": "session-1"}
    key = ("session-1", False, False)
    agent_loop._STATIC_SEGMENTS_PROCESS_CACHE.clear()
    agent_loop._STATIC_SEGMENTS_REBUILD_INFLIGHT.clear()

    # Cold build populates the cache with the current revision.
    segs = agent_loop._build_static_segments_for_session("session-1", {}, "zh-CN")
    agent_loop._STATIC_SEGMENTS_PROCESS_CACHE[key] = (("rev1",), segs)

    async def driver():
        # Revision drift: helper schedules a background rebuild; the caller
        # keeps serving the stale segments until the rebuild lands.
        agent_loop._schedule_static_segments_rebuild(
            state, {}, "zh-CN", ("rev2",), key
        )
        task = state.get("_static_segments_revalidate_task")
        assert task is not None
        await task
        assert agent_loop._STATIC_SEGMENTS_PROCESS_CACHE[key][0] == ("rev2",)
        assert agent_loop._STATIC_SEGMENTS_PROCESS_CACHE[key][1] == ("seg-v2",)

    asyncio.run(driver())

    # While a rebuild is in flight, no second one is scheduled for the key.
    agent_loop._STATIC_SEGMENTS_REBUILD_INFLIGHT.add(key)
    state2 = {"session_id": "session-1"}
    agent_loop._schedule_static_segments_rebuild(state2, {}, "zh-CN", ("rev3",), key)
    assert "_static_segments_revalidate_task" not in state2
    agent_loop._STATIC_SEGMENTS_REBUILD_INFLIGHT.clear()
    agent_loop._STATIC_SEGMENTS_PROCESS_CACHE.clear()


def test_static_segments_rebuild_failure_keeps_stale_entry(monkeypatch):
    import agent_loop

    def failing_build(*_args, **_kwargs):
        raise RuntimeError("disk busy")

    monkeypatch.setattr(
        agent_loop, "_build_static_segments_for_session", failing_build
    )

    state = {"session_id": "session-1"}
    key = ("session-1", False, False)
    agent_loop._STATIC_SEGMENTS_PROCESS_CACHE.clear()
    agent_loop._STATIC_SEGMENTS_REBUILD_INFLIGHT.clear()
    agent_loop._STATIC_SEGMENTS_PROCESS_CACHE[key] = (("rev1",), ("old",))

    async def driver():
        agent_loop._schedule_static_segments_rebuild(
            state, {}, "zh-CN", ("rev2",), key
        )
        await state["_static_segments_revalidate_task"]
        # The stale entry must remain untouched after a failed rebuild.
        assert agent_loop._STATIC_SEGMENTS_PROCESS_CACHE[key] == (("rev1",), ("old",))
        assert key not in agent_loop._STATIC_SEGMENTS_REBUILD_INFLIGHT

    asyncio.run(driver())
    agent_loop._STATIC_SEGMENTS_PROCESS_CACHE.clear()
