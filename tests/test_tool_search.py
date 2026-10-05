from __future__ import annotations

import ast
import asyncio
import json
import sys
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

import pytest

APP = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP)) if str(APP) not in sys.path else None

import tool_search
from tool_registry import ToolInvocationKind, ToolRegistry


def definition(name, description="Find browser tabs", properties=None):
    return {"type": "function", "function": {"name": name, "description": description,
        "parameters": {"type": "object", "properties": properties or {"url": {"type": "string"}}}}}


def catalog(count=100, **traits):
    registry = ToolRegistry()
    registry.register_definition(definition("read_file"), invocation_kind="host", owner="core.tools",
                                 effect="read", parallel_safe=True)
    for index in range(count):
        registry.register_definition(definition(f"mcp_browser_action_{index}", "Browser automation " * 80),
            invocation_kind="mcp", owner="mcp", **traits)
    return registry


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    monkeypatch.setattr(tool_search, "CONFIG_PATH", tmp_path / "tool_search.json")
    monkeypatch.setattr(tool_search, "_config_cache", None)
    monkeypatch.delenv("MYAGENT_TOOL_SEARCH", raising=False)


def test_config_hot_reload_off_delete_and_environment_rollback(monkeypatch):
    assert tool_search.load_config().enabled == "off"
    tool_search.save_config({"enabled": "on"})
    assert tool_search.load_config().enabled == "on"
    before = tool_search.config_revision()
    monkeypatch.setenv("MYAGENT_TOOL_SEARCH", "auto")
    assert tool_search.config_revision() != before
    assert tool_search.load_config().enabled == "auto"
    tool_search.save_config({"enabled": "off"})
    assert tool_search.load_config().enabled == "off"
    tool_search.CONFIG_PATH.unlink()
    assert tool_search.load_config().enabled == "off"


@pytest.mark.parametrize("raw", [{"enabled": "bad"}, {"threshold_pct": float("nan")},
    {"threshold_pct": 0}, {"threshold_tokens": True}, {"search_default_limit": 21},
    {"max_search_limit": 500}, {"defer_plugin_tools": "false"}, {"unknown": 1}])
def test_config_rejects_invalid_values_without_overwriting(raw):
    tool_search.save_config({"enabled": "on"})
    before = tool_search.CONFIG_PATH.read_bytes()
    with pytest.raises(ValueError):
        tool_search.save_config(raw)
    assert tool_search.CONFIG_PATH.read_bytes() == before


def test_auto_uses_schema_tokens_and_caps_large_context_threshold():
    config = tool_search.ToolSearchConfig(enabled="auto")
    assert not tool_search.should_activate(config, 0, 512_000)
    assert not tool_search.should_activate(config, 19_999, 512_000)
    assert tool_search.should_activate(config, 20_000, 512_000)
    assert tool_search.should_activate(config, 10_000, 100_000)
    assert not tool_search.should_activate(config, 9_999, 100_000)
    assert tool_search.should_activate(config, 20_000, None)


def test_100_mcp_tools_reduce_request_but_preserve_authorized_execution_and_pins():
    from agent_tokenizer import count_tool_definition_tokens, build_context_breakdown
    registry = catalog()
    before = count_tool_definition_tokens(registry.definitions())
    tool_search.assemble(registry, context_window=512_000, pinned_names={"mcp_browser_action_0"},
                         config=tool_search.ToolSearchConfig(enabled="on"))
    schemas = registry.definitions()
    assert {row["function"]["name"] for row in schemas} == {
        "read_file", "mcp_browser_action_0", *tool_search.BRIDGE_NAMES}
    assert registry.require("mcp_browser_action_99").executable
    assert registry.disclosure.names == {f"mcp_browser_action_{i}" for i in range(1, 100)}
    assert count_tool_definition_tokens(schemas) < before * .2
    breakdown = build_context_breakdown([], 2000, schemas)
    assert breakdown["deferred_tools_count"] == 99
    assert breakdown["saved_tools_tokens"] == before - breakdown["tools_tokens"]
    assert sum(breakdown[key] for key in ("system_tokens", "tools_tokens", "message_tokens")) == 2000
    assert len(json.loads(json.dumps(schemas))) == 5


def test_off_keeps_request_exact_and_bridge_name_conflict_is_not_shadowed():
    registry = catalog(2)
    before = json.dumps(registry.definitions())
    tool_search.assemble(registry, context_window=100, config=tool_search.ToolSearchConfig())
    assert json.dumps(registry.definitions()) == before
    assert registry.disclosure is None
    registry.register_definition(definition("tool_search"), invocation_kind="plugin", owner="external")
    tool_search.assemble(registry, context_window=100, config=tool_search.ToolSearchConfig(enabled="on"))
    assert registry.require("tool_search").owner == "external"
    assert registry.disclosure is None


def test_search_describe_call_scope_and_immutable_assistant_message():
    registry = catalog(2)
    tool_search.assemble(registry, context_window=100, config=tool_search.ToolSearchConfig(enabled="on"))
    disclosure = registry.disclosure
    assert len(disclosure.search({"query": "browser +automation"})["tools"]) == 2
    assert disclosure.search({"query": "+unknown"})["tools"] == []
    assert disclosure.search({"query": "select:mcp_browser_action_1,missing"})["total_matches"] == 1
    described = disclosure.describe({"name": "mcp_browser_action_1"})
    described["function"]["name"] = "tampered"
    assert disclosure.describe({"name": "mcp_browser_action_1"})["function"]["name"] == "mcp_browser_action_1"
    assistant_call = {"name": "tool_call", "args": {"name": "mcp_browser_action_1", "arguments": {"url": "local", "nested": {"value": 1}}},
                      "id": "call-1", "index": 0}
    before = json.dumps(assistant_call)
    execution = tool_search.resolve_call(registry, assistant_call)
    execution["args"]["url"] = "changed"
    execution["args"]["nested"]["value"] = 2
    assert json.dumps(assistant_call) == before
    assert execution["name"] == "mcp_browser_action_1"
    assert execution["id"] == assistant_call["id"]
    for target in ("read_file", "tool_call", "tool_search", "missing", 7, ""):
        with pytest.raises(ValueError):
            tool_search.resolve_call(registry, {"name": "tool_call", "args": {"name": target, "arguments": {}}})
        with pytest.raises(ValueError):
            disclosure.describe({"name": target})
    with pytest.raises(ValueError):
        tool_search.resolve_call(registry, {"name": "tool_call", "args": {"name": "mcp_browser_action_1", "arguments": "{}"}})


def test_computer_provider_is_deferred_by_owner_and_global_pins_are_respected():
    registry = catalog(1)
    registry.register_definition(definition("computer_click"), invocation_kind="host_service", owner="computer-use")
    registry.register_definition(definition("computer_state"), invocation_kind="host_service", owner="computer-use")
    registry.register_definition(definition("job_list"), invocation_kind="host_service", owner="execution-tools")
    tool_search.assemble(registry, context_window=100, config=tool_search.ToolSearchConfig.parse({
        "enabled": "on", "pinned_tools": ["computer_state"]}))
    assert registry.disclosure.names == {"mcp_browser_action_0", "computer_click"}
    visible = {row["function"]["name"] for row in registry.definitions()}
    assert {"job_list", "computer_state", "read_file"} <= visible


def test_bridge_policy_is_underlying_write_policy_and_search_invokers_are_scoped():
    import agent_loop
    import builtin_host_tools
    from host_tool_registry import HostToolInvocationContext, host_tool_invokers
    registry = catalog(1, effect="external_write", parallel_safe=False, interruptibility="non_interruptible")
    tool_search.assemble(registry, context_window=100, config=tool_search.ToolSearchConfig(enabled="on"))
    call = {"name": "tool_call", "args": {"name": "mcp_browser_action_0", "arguments": {}}}
    descriptor = tool_search.call_descriptor(registry, call)
    assert descriptor.parallel_safe is False
    assert agent_loop._tool_steer_policy("tool_call", descriptor) == {
        "interruptibility": "non_interruptible", "side_effect": "irreversible"}
    context = HostToolInvocationContext(session_id="test", services={"tool_registry": registry, "tool_name": "tool_search"})
    result = asyncio.run(host_tool_invokers.invoke("tool_search", context, {"query": "browser"}))
    assert json.loads(result.content)["tools"][0]["name"] == "mcp_browser_action_0"
    assert asyncio.run(host_tool_invokers.invoke("tool_call", context, call["args"])).code == "unresolved_tool_bridge"


def test_builder_discloses_only_filtered_scope_and_preserves_fork_targets(monkeypatch):
    import agent_loop
    import agent_extensions
    import agent_mcp
    import agent_subagent
    tool_search.save_config({"enabled": "on"})
    async def remote():
        return [definition("mcp_demo_read"), definition("mcp_demo_write")]
    async def empty():
        return []
    monkeypatch.setattr(agent_loop, "OPENAI_TOOL_DEFINITIONS", [definition("read_file")])
    monkeypatch.setattr(agent_extensions, "bundled_host_tool_definitions", lambda **kwargs: [])
    monkeypatch.setattr(agent_extensions, "plugin_tool_definitions", empty)
    monkeypatch.setattr(agent_mcp, "get_tool_definitions", remote)
    monkeypatch.setattr(agent_loop, "resolve_executor_config_for_session", lambda sid: (None, "test", 100, 512_000))
    registry = asyncio.run(agent_loop.build_combined_tool_registry_for_session("main", session_meta={}))
    assert registry.disclosure.names == {"mcp_demo_read", "mcp_demo_write"}
    snapshot = {"tools": registry.definitions(), "authorized_tools": [d.openai_definition()
                for d in registry.descriptors() if d.owner != "core.tool_search"]}
    fork = asyncio.run(agent_loop.build_combined_tool_registry_for_session("fork", session_meta={"fork_runtime_config": snapshot}))
    assert fork.disclosure.names == registry.disclosure.names
    child = asyncio.run(agent_loop.build_combined_tool_registry_for_session("child", session_meta={
        "is_subagent": True, "subagent_type": "explore", "fork_runtime_config": snapshot}))
    assert child.disclosure is None
    assert not any(d.invocation_kind is ToolInvocationKind.MCP for d in child.descriptors())
    cold = asyncio.run(agent_loop.build_combined_tool_registry_for_session("cold", session_meta={}, include_mcp=False))
    assert cold.disclosure is None
    def broken_filter(*args):
        raise OSError("profile unavailable")
    monkeypatch.setattr(agent_subagent, "filter_tools_for_session", broken_filter)
    with pytest.raises(RuntimeError, match="profile filtering"):
        asyncio.run(agent_loop.build_combined_tool_registry_for_session("failed", session_meta={}, include_mcp=False))


def test_registry_revision_tracks_model_window_profile_and_config(monkeypatch):
    import agent_loop
    import agent_mcp
    tool_search.save_config({"enabled": "auto"})
    window = {"value": 100_000}
    async def fixed_revision():
        return (1, "fixture", ())
    monkeypatch.setattr(agent_mcp, "get_tool_catalog_revision", fixed_revision)
    monkeypatch.setattr(agent_loop, "resolve_executor_config_for_session", lambda sid: (None, "test", 100, window["value"]))
    first = asyncio.run(agent_loop._combined_tool_registry_revision({}, "test"))
    window["value"] = 512_000
    second = asyncio.run(agent_loop._combined_tool_registry_revision({}, "test"))
    assert first != second
    profile = asyncio.run(agent_loop._combined_tool_registry_revision({"is_subagent": True, "subagent_type": "explore"}, "test"))
    assert profile != second
    tool_search.save_config({"enabled": "off"})
    assert asyncio.run(agent_loop._combined_tool_registry_revision({}, "test")) != second


def _execution_wrapper(namespace):
    # Execute the production Hook wrapper independently of the model/network
    # loop, with a controlled core executor. This tests ordering and history
    # isolation through the actual wrapper rather than a copied implementation.
    tree = ast.parse((APP / "agent_loop.py").read_text(encoding="utf-8"))
    node = next(node for node in ast.walk(tree) if isinstance(node, ast.AsyncFunctionDef) and node.name == "execute_one")
    exec(compile(ast.Module(body=[node], type_ignores=[]), "agent_loop.py", "exec"), namespace)
    return namespace["execute_one"]


def test_execution_unwrap_precedes_hooks_audit_and_core_preserves_history(monkeypatch):
    import agent_loop
    registry = catalog(1, effect="read", parallel_safe=True, interruptibility="safe")
    tool_search.assemble(registry, context_window=100, config=tool_search.ToolSearchConfig(enabled="on"))
    events = []
    async def hook(event, state, payload, emit):
        events.append((event, payload["tool_name"], payload["tool_input"]))
        return SimpleNamespace(updated_input=None, requires_approval=False, blocked=False,
                               should_pause=False, additional_context="")
    async def core(call):
        events.append(("execute", call["name"], call["args"]))
        return {"type": "tool", "tool_name": call["name"], "tool_id": call["id"], "tool_failed": False}
    namespace = dict(vars(agent_loop)) | {"state": {"session_id": "test"}, "llm_stream_seq": 1,
        "iter_count": 1, "tool_registry": registry, "session_meta": {}, "emit": None,
        "executable_tool_names": registry.names(executable_only=True), "workspace_audit_tail_by_root": {},
        "_dispatch_state_hook": hook, "_execute_one_core": core,
        "execution_metrics": SimpleNamespace(record_tool=lambda *args, **kwargs: None),
        "diff_workspace_states": lambda before, after: []}
    execute = _execution_wrapper(namespace)
    original = {"name": "tool_call", "args": {"name": "mcp_browser_action_0", "arguments": {"url": "hello"}}, "id": "pair-1"}
    before = json.dumps(original)
    result = asyncio.run(execute(original))
    assert [row[:2] for row in events] == [("PreToolUse", "mcp_browser_action_0"),
        ("execute", "mcp_browser_action_0"), ("PostToolUse", "mcp_browser_action_0")]
    assert all(row[2] == {"url": "hello"} for row in events)
    assert result["tool_id"] == "pair-1"
    assert result["bridge_call"]["target"] == "mcp_browser_action_0"
    assert json.dumps(original) == before
    events.clear()
    bad = asyncio.run(execute({"name": "tool_call", "args": {"name": "read_file", "arguments": {}}, "id": "bad"}))
    assert bad["tool_failed"]
    assert events == []


@pytest.mark.parametrize("approved", [False, True])
def test_mcp_bridge_uses_production_approval_and_invocation_pipeline(monkeypatch, approved):
    import agent_loop
    import agent_mcp
    from security.models import DecisionOutcome, PermissionMode, PERMISSION_PRESETS, SecurityDecision
    registry = catalog(1, effect="external_write")
    tool_search.assemble(registry, context_window=100, config=tool_search.ToolSearchConfig(enabled="on"))
    observations = []
    admitted = {"value": False}
    async def noop(*args, **kwargs):
        pass
    async def emit(event):
        observations.append(("event", event))
    async def push(state, event, emit=None):
        if emit:
            await emit(event)
    async def hook(event, state, payload, _emit):
        observations.append((event, payload["tool_name"]))
        return SimpleNamespace(updated_input=None, requires_approval=False, blocked=False,
                               should_pause=False, additional_context="")
    def authorize(**kwargs):
        observations.append(("authorize", kwargs["tool_name"], kwargs["arguments"]))
        outcome = DecisionOutcome.ALLOW if admitted["value"] else DecisionOutcome.ASK
        return SimpleNamespace(), SecurityDecision(outcome, "fixture", "test", "bound-digest"), PERMISSION_PRESETS[PermissionMode.ASK_FOR_APPROVAL]
    async def pending(_emit, name, *args):
        observations.append(("pending", name))
    async def approval_event(_emit, sid, aid, name, *args, **kwargs):
        observations.append(("approval_card", name))
    async def wait_approval(sid, aid, publish, **kwargs):
        await publish()
        observations.append(("approval_metadata", kwargs["metadata"]["tool"], kwargs["metadata"]["tool_call_id"]))
        admitted["value"] = approved
        return {"approved": approved, "decision": "allow_once" if approved else "deny"}
    async def awaiter(state, awaitable, *args, **kwargs):
        return await awaitable
    async def invoke(name, arguments, **kwargs):
        observations.append(("mcp_invoke", name, arguments))
        return "fixture success"
    monkeypatch.setattr(agent_mcp, "invoke_tool_by_fname", invoke)
    namespace = dict(vars(agent_loop)) | {"state": {"session_id": "fixture"}, "llm_stream_seq": 1,
        "iter_count": 1, "tool_registry": registry, "session_meta": {}, "emit": emit,
        "executable_tool_names": registry.names(executable_only=True), "workspace_audit_tail_by_root": {},
        "_dispatch_state_hook": hook, "_runtime_v2_is_primary": lambda: False,
        "_push_stream_event": push,
        "_raise_if_steer_requested": noop, "authorize_tool": authorize,
        "_build_tool_review_context": lambda *args: {}, "_tool_ui_approval_spec": lambda *args: None,
        "_security_approval_spec": lambda *args: {"title": "fixture", "message": "fixture"},
        "_emit_tool_pending_sse": pending, "_emit_tool_approval_required_sse": approval_event,
        "wait_tool_ui_approval_after_emit": wait_approval, "_await_steerable": awaiter,
        "_begin_change_review_capture": lambda *args, **kwargs: None,
        "_finish_change_review_capture": lambda *args: [],
        "capture_workspace_state": lambda *args: {}, "diff_workspace_states": lambda *args: [],
        "_tool_result_details_for_views": lambda result, *args: (result, result, result),
        "iter_client": SimpleNamespace(current_candidate=lambda: {"input_modalities": ["text"], "model": "test"}),
        "iter_model": "test", "execution_metrics": SimpleNamespace(record_tool=lambda *args, **kwargs: None)}
    tree = ast.parse((APP / "agent_loop.py").read_text(encoding="utf-8"))
    core = next(node for node in ast.walk(tree) if isinstance(node, ast.AsyncFunctionDef) and node.name == "_execute_one_core")
    exec(compile(ast.Module(body=[core], type_ignores=[]), "agent_loop.py", "exec"), namespace)
    execute = _execution_wrapper(namespace)
    original = {"name": "tool_call", "args": {"name": "mcp_browser_action_0", "arguments": {"url": "hello"}}, "id": "pair-approval"}
    result = asyncio.run(execute(original))
    assert ("approval_card", "mcp_browser_action_0") in observations
    assert ("approval_metadata", "mcp_browser_action_0", "pair-approval") in observations
    assert ("pending", "mcp_browser_action_0") in observations
    invocations = [row for row in observations if row[0] == "mcp_invoke"]
    assert invocations == ([("mcp_invoke", "mcp_browser_action_0", {"url": "hello"})] if approved else [])
    assert result["tool_failed"] is not approved
    assert original["name"] == "tool_call" and original["args"]["name"] == "mcp_browser_action_0"

    if approved:
        async def cancelled(*args, **kwargs):
            raise asyncio.CancelledError()
        monkeypatch.setattr(agent_mcp, "invoke_tool_by_fname", cancelled)
        with pytest.raises(asyncio.CancelledError):
            asyncio.run(execute(original))
