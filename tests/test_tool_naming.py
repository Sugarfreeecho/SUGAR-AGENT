from __future__ import annotations

import asyncio
import ast
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

APP = Path(__file__).resolve().parents[1] / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from tool_naming import ToolNameSource, allocate_tool_names
from tool_registry import DuplicateToolError, ToolInvocationKind, ToolRegistry


def definition(name):
    return {"type": "function", "function": {"name": name, "description": name,
            "parameters": {"type": "object", "properties": {}}}}


def test_unique_tools_use_local_names_and_keep_original_case():
    sources = [ToolNameSource("plugin_docs__FindPage", "FindPage", "docs"),
               ToolNameSource("mcp_weather_forecast", "forecast", server_name="weather")]
    assert allocate_tool_names(sources) == {
        "plugin_docs__FindPage": "FindPage", "mcp_weather_forecast": "forecast"}


def test_collisions_add_only_the_needed_plugin_and_server_prefixes():
    sources = [ToolNameSource("a", "search", "docs", "pages"),
               ToolNameSource("b", "search", "docs", "files"),
               ToolNameSource("c", "search", "mail", "inbox"),
               ToolNameSource("d", "search", server_name="web"),
               ToolNameSource("e", "read_file", "storage")]
    expected = {"a": "docs__pages__search", "b": "docs__files__search",
                "c": "mail__search", "d": "web__search", "e": "storage__read_file"}
    assert allocate_tool_names(sources, reserved={"read_file"}) == expected
    assert allocate_tool_names(reversed(sources), reserved={"read_file"}) == expected


def test_qualified_names_cannot_shadow_another_tools_local_name():
    sources = [ToolNameSource("a", "search", "docs"),
               ToolNameSource("b", "search", "mail"),
               ToolNameSource("c", "docs__search", "special")]
    names = allocate_tool_names(sources)
    assert len(set(names.values())) == 3
    assert names["a"].startswith("docs__search_")
    assert names["b"] == "mail__search"
    assert names["c"] == "special__docs__search"


def test_normalization_and_truncation_never_drop_distinct_tools():
    sources = [ToolNameSource("a", "lookup", "demo.one"),
               ToolNameSource("b", "lookup", "demo_one"),
               ToolNameSource("c", "x" * 180 + "a", "long"),
               ToolNameSource("d", "x" * 180 + "b", "long")]
    names = allocate_tool_names(sources)
    assert len(set(names.values())) == len(sources)
    assert all(re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", name) for name in names.values())
    assert names == allocate_tool_names(reversed(sources))


def test_renaming_preserves_execution_binding_and_is_atomic_on_conflict():
    registry = ToolRegistry()
    registry.register_definition(definition("plugin_demo__greet"),
        invocation_kind="plugin", owner="demo", effect="read", parallel_safe=True)
    registry.register_definition(definition("read_file"), invocation_kind="host", owner="core")
    registry.rename_tools({"plugin_demo__greet": "greet"})
    descriptor = registry.require("greet")
    assert descriptor.execution_name == "plugin_demo__greet"
    assert descriptor.effect == "read" and descriptor.parallel_safe
    assert descriptor.openai_definition()["function"]["name"] == "greet"
    assert registry.resolve("plugin_demo__greet") is None
    with pytest.raises(DuplicateToolError):
        registry.rename_tools({"greet": "read_file"})
    assert registry.require("greet") == descriptor


@pytest.fixture
def catalog(monkeypatch):
    import agent_extensions
    import agent_loop
    import agent_mcp
    import agent_subagent

    monkeypatch.setenv("MYAGENT_TOOL_SEARCH", "off")
    monkeypatch.setattr(agent_extensions, "load_plugins", lambda **_: type("Plugins", (), {"plugins": ()})())
    monkeypatch.setattr(agent_extensions, "bundled_host_tool_definitions", lambda **_: [])
    monkeypatch.setattr(agent_loop, "OPENAI_TOOL_DEFINITIONS", [definition("read_file")])
    monkeypatch.setattr(agent_loop, "tools_dict", {"read_file": lambda: None})
    monkeypatch.setattr(agent_subagent, "inject_task_model_profiles", lambda rows: rows)
    identities = {"mcp_docs_pages_search": ("docs/pages", "search"),
                  "mcp_docs_files_search": ("docs/files", "search"),
                  "mcp_weather_forecast": ("weather", "forecast")}
    monkeypatch.setattr(agent_mcp, "_fname_to_tool", identities)
    monkeypatch.setattr(agent_mcp, "get_pinned_tool_names", lambda: frozenset())
    contracts = {"plugin_mail__search": {"plugin_id": "mail", "local_name": "search", "effect": "read"},
                 "plugin_storage__read_file": {"plugin_id": "storage", "local_name": "read_file", "effect": "workspace_write"},
                 "plugin_demo__greet": {"plugin_id": "demo", "local_name": "greet", "effect": "read"}}

    async def mcp_definitions():
        return [definition(name) for name in identities]

    async def plugin_definitions():
        return [definition(name) for name in contracts]

    async def plugin_contracts():
        return contracts

    monkeypatch.setattr(agent_mcp, "get_published_tool_definitions", mcp_definitions)
    monkeypatch.setattr(agent_extensions, "plugin_tool_definitions", plugin_definitions)
    monkeypatch.setattr(agent_extensions, "plugin_tool_contracts", plugin_contracts)
    return agent_loop, agent_mcp, agent_extensions


def test_combined_catalog_keeps_all_colliding_tools_and_their_execution_sources(catalog):
    agent, mcp, extensions = catalog
    registry = asyncio.run(agent.build_combined_tool_registry_for_session("test", session_meta={}))
    assert registry.names() == {"read_file", "storage__read_file", "docs__pages__search",
                               "docs__files__search", "mail__search", "forecast", "greet"}
    assert registry.require("read_file").invocation_kind is ToolInvocationKind.HOST
    assert mcp.get_tool_identity(registry.require("forecast").execution_name) == ("weather", "forecast")
    assert registry.require("mail__search").execution_name == "plugin_mail__search"
    assert registry.require("mail__search").parallel_safe
    assert registry.require("storage__read_file").effect == "workspace_write"


def test_fork_snapshot_keeps_parent_names_and_filters_using_source_names(catalog, monkeypatch):
    agent, _, _ = catalog
    import agent_subagent
    parent = asyncio.run(agent.build_combined_tool_registry_for_session("parent", session_meta={}))
    inherited = [parent.require("docs__pages__search").openai_definition(),
                 parent.require("greet").openai_definition()]
    source_names = {name: parent.require(name).execution_name for name in ("docs__pages__search", "greet")}
    seen = []

    def profile_filter(rows, meta):
        seen.append([row["function"]["name"] for row in rows])
        return rows

    monkeypatch.setattr(agent_subagent, "filter_tools_for_session", profile_filter)
    child = asyncio.run(agent.build_combined_tool_registry_for_session("child", session_meta={
        "fork_runtime_config": {"authorized_tools": inherited, "tool_sources": source_names}}))
    assert child.names() == {"docs__pages__search", "greet"}
    assert seen[-1] == ["mcp_docs_pages_search", "plugin_demo__greet"]
    assert child.require("docs__pages__search").execution_name == "mcp_docs_pages_search"


def test_legacy_pins_keep_the_renamed_tool_resident(catalog):
    import tool_search
    agent, _, _ = catalog
    registry = asyncio.run(agent.build_combined_tool_registry_for_session("test", session_meta={}))
    tool_search.assemble(registry, context_window=10000,
        pinned_names={"mcp_weather_forecast"}, config=tool_search.ToolSearchConfig(enabled="on"))
    assert "forecast" in {row["function"]["name"] for row in registry.definitions()}
    call = tool_search.resolve_call(registry, {"id": "1", "name": "tool_call",
        "args": {"name": "greet", "arguments": {}}})
    assert registry.require(call["name"]).execution_name == "plugin_demo__greet"


@pytest.mark.parametrize("name,source,kind", [
    ("forecast", "mcp_weather_forecast", "mcp"),
    ("greet", "plugin_demo__greet", "plugin"),
])
def test_execution_authorizes_and_invokes_source_but_reports_model_name(
    catalog, monkeypatch, tmp_path, name, source, kind
):
    agent, mcp, extensions = catalog
    registry = asyncio.run(agent.build_combined_tool_registry_for_session("test", session_meta={}))
    # Exercise the production execution closure without starting a model run.
    tree = ast.parse((APP / "agent_loop.py").read_text(encoding="utf-8"))
    core = next(node for node in ast.walk(tree)
                if isinstance(node, ast.AsyncFunctionDef) and node.name == "_execute_one_core")
    calls = []

    def authorize(**kwargs):
        calls.append(("authorize", kwargs["tool_name"]))
        return None, SimpleNamespace(outcome=agent.DecisionOutcome.ALLOW), SimpleNamespace(mode=agent.PermissionMode.FULL_ACCESS)

    async def invoke(function_name, arguments, **kwargs):
        calls.append(("invoke", function_name))
        return {"value": 42}

    async def noop(*args, **kwargs):
        pass

    async def await_call(state, pending, *args):
        return await pending

    monkeypatch.setattr(mcp, "invoke_tool_by_fname", invoke)
    monkeypatch.setattr(extensions, "invoke_plugin_tool", invoke)
    scope = dict(vars(agent))
    scope.update(tool_registry=registry, llm_stream_seq=1, state={"session_id": "test"},
        session_meta={}, iter_count=1, iter_model="test-model", emit=None,
        iter_client=SimpleNamespace(current_candidate=lambda: {"input_modalities": ["text"]}),
        _runtime_v2_is_primary=lambda: False, session_work_root=lambda _: tmp_path,
        authorize_tool=authorize, _build_tool_review_context=lambda *_: {},
        _raise_if_steer_requested=noop, _push_stream_event=noop, _await_steerable=await_call,
        _workflow_callbacks=lambda: SimpleNamespace(call=lambda *_: None),
        _tool_result_details_for_views=lambda value, *_: (value, value, value))
    exec(compile(ast.Module(body=[core], type_ignores=[]), str(APP / "agent_loop.py"), "exec"), scope)
    result = asyncio.run(scope["_execute_one_core"]({"id": "call-1", "name": name, "args": {}}))
    assert calls == [("authorize", source), ("invoke", source)]
    assert result["tool_name"] == name and result["tool_failed"] is False
    assert registry.require(name).invocation_kind.value == kind
