import asyncio
from types import SimpleNamespace

import pytest


def definition(name):
    return {"type": "function", "function": {"name": name, "parameters": {"type": "object", "properties": {}}}}


def test_same_session_concurrent_runs_do_not_overwrite_each_others_scope():
    from agent_loop import set_run_tool_scope, run_tool_scope_for, clear_run_tool_scope

    async def scenario():
        ready = asyncio.Event()
        values = []

        async def worker(name):
            token = set_run_tool_scope("same-session", allow=[name], run_id=name)
            values.append(name)
            if len(values) == 2:
                ready.set()
            await ready.wait()
            assert run_tool_scope_for("same-session")["allow"] == [name]
            assert await asyncio.to_thread(lambda: run_tool_scope_for("same-session")["run_id"]) == name
            clear_run_tool_scope("same-session", token)
            assert run_tool_scope_for("same-session") == {}

        await asyncio.gather(worker("first"), worker("second"))

    asyncio.run(scenario())
    assert run_tool_scope_for("same-session") == {}


def test_empty_explicit_allowlist_removes_all_tools_including_bridges():
    from agent_subagent import filter_tools_for_session
    definitions = [definition(name) for name in ["run_shell", "bili_search", "tool_search", "tool_describe", "tool_call"]]
    assert filter_tools_for_session(definitions, {"tool_allowlist": [], "tool_allowlist_active": True}) == []
    assert len(filter_tools_for_session(definitions, {})) == len(definitions)


def test_nested_scope_restores_previous_scope_without_clearing_another_token():
    from agent_loop import set_run_tool_scope, run_tool_scope_for, clear_run_tool_scope
    first = set_run_tool_scope("s", allow=["bili_search"])
    second = set_run_tool_scope("s", allow=[])
    clear_run_tool_scope("s", first)
    assert run_tool_scope_for("s")["allow"] == []
    clear_run_tool_scope("s", second)
    assert run_tool_scope_for("s")["allow"] == ["bili_search"]
    clear_run_tool_scope("s", first)
    assert run_tool_scope_for("s") == {}


def test_registry_cannot_restore_filtered_tools_through_discovery(monkeypatch):
    import agent_loop
    import agent_extensions
    import agent_subagent
    import tool_search
    from tool_registry import ToolInvocationKind

    rows = [definition("run_shell"), definition("bili_search")]
    monkeypatch.setattr(agent_extensions, "load_plugins", lambda: SimpleNamespace(plugins=()))
    monkeypatch.setattr(agent_loop, "_build_host_tool_catalog", lambda *args: (rows, {
        "run_shell": (ToolInvocationKind.HOST, "core"), "bili_search": (ToolInvocationKind.HOST, "core")}))

    async def empty():
        return []

    async def contracts():
        return {}

    monkeypatch.setattr(agent_extensions, "plugin_tool_definitions", empty)
    monkeypatch.setattr(agent_extensions, "plugin_tool_contracts", contracts)
    monkeypatch.setattr(agent_subagent, "inject_task_model_profiles", lambda rows: rows)
    monkeypatch.setattr(tool_search, "load_config", lambda: tool_search.ToolSearchConfig(enabled="on"))
    token = agent_loop.set_run_tool_scope("s", allow=[])
    try:
        registry = asyncio.run(agent_loop.build_combined_tool_registry_for_session("s", session_meta={}, include_mcp=False))
        assert not registry.names() and not registry.definitions()
    finally:
        agent_loop.clear_run_tool_scope("s", token)


def test_scope_filter_failure_never_falls_back_to_full_tools(monkeypatch):
    import agent_loop
    import agent_extensions
    import agent_subagent
    import tool_search
    monkeypatch.setattr(agent_extensions, "load_plugins", lambda: SimpleNamespace(plugins=()))
    monkeypatch.setattr(agent_loop, "_build_host_tool_catalog", lambda *args: ([], {}))

    async def empty():
        return []

    async def contracts():
        return {}

    monkeypatch.setattr(agent_extensions, "plugin_tool_definitions", empty)
    monkeypatch.setattr(agent_extensions, "plugin_tool_contracts", contracts)
    monkeypatch.setattr(tool_search, "load_config", lambda: tool_search.ToolSearchConfig(enabled="off"))

    def broken(*args):
        raise ValueError("invalid filter")

    monkeypatch.setattr(agent_subagent, "filter_tools_for_session", broken)
    token = agent_loop.set_run_tool_scope("s", allow=[])
    try:
        with pytest.raises(RuntimeError, match="filtering"):
            asyncio.run(agent_loop.build_combined_tool_registry_for_session("s", session_meta={}, include_mcp=False))
    finally:
        agent_loop.clear_run_tool_scope("s", token)
