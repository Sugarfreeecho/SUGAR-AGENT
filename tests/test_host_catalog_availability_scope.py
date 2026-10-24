from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import Mock

APP = Path(__file__).resolve().parents[1] / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))


def test_catalog_reads_plugin_state_once_and_observes_next_pass_changes(monkeypatch):
    import plugins.host as host
    import plugins.manager as manager
    from host_tool_registry import HostToolInvokerRegistry

    state = {"version": 1, "plugins": {"example": {"enabled": True}}}
    read = Mock(side_effect=lambda: {"version": 1, "plugins": {key: dict(value) for key, value in state["plugins"].items()}})
    get_manager = Mock(return_value=SimpleNamespace(state=SimpleNamespace(read=read),
        is_enabled=lambda name: state["plugins"][name]["enabled"]))
    monkeypatch.setattr(manager, "get_plugin_manager", get_manager)
    monkeypatch.setattr(manager, "plugins_enabled", lambda: True)
    registry = HostToolInvokerRegistry()
    async def invoke(*args):
        return None
    for index in range(4):
        registry.register(f"example_{index}", invoke, enabled=lambda: host.bundled_host_plugin_enabled("example"))
    before = registry.catalog_revision()
    assert get_manager.call_count == read.call_count == 1
    state["plugins"]["example"]["enabled"] = False
    assert registry.catalog_revision() != before
    assert get_manager.call_count == read.call_count == 2
    assert not host.bundled_host_plugin_enabled("example")
    assert get_manager.call_count == 3


def test_unreadable_state_disables_every_binding_in_the_same_pass(monkeypatch):
    import plugins.host as host
    import plugins.manager as manager
    from host_tool_registry import HostToolInvokerRegistry

    read = Mock(side_effect=OSError("state unavailable"))
    monkeypatch.setattr(manager, "get_plugin_manager", lambda: SimpleNamespace(state=SimpleNamespace(read=read)))
    monkeypatch.setattr(manager, "plugins_enabled", lambda: True)
    registry = HostToolInvokerRegistry()
    async def invoke(*args):
        raise AssertionError("disabled tool executed")
    for index in range(4):
        registry.register(f"example_{index}", invoke, enabled=lambda: host.bundled_host_plugin_enabled("example"))
    revision = registry.catalog_revision()
    assert all(enabled is False for _, enabled in revision[1])
    assert read.call_count == 1


def test_host_builder_uses_one_snapshot_and_execution_checks_live_disable(monkeypatch):
    import asyncio
    import agent_extensions
    import agent_loop
    import plugins.host as host
    import plugins.manager as manager
    import session_workspace
    from host_tool_registry import HostToolInvokerRegistry

    state = {"plugins": {"example": {"enabled": True}}}
    read = Mock(side_effect=lambda: {"plugins": {"example": dict(state["plugins"]["example"])}})
    get_manager = Mock(return_value=SimpleNamespace(state=SimpleNamespace(read=read),
        is_enabled=lambda name: state["plugins"][name]["enabled"]))
    monkeypatch.setattr(manager, "get_plugin_manager", get_manager)
    monkeypatch.setattr(manager, "plugins_enabled", lambda: True)
    registry = HostToolInvokerRegistry()
    called = []
    async def invoke(*args):
        called.append(True)
    definitions = []
    for index in range(4):
        name = f"example_{index}"
        registry.register(name, invoke, enabled=lambda: host.bundled_host_plugin_enabled("example"))
        definitions.append({"type":"function", "function":{"name":name,"parameters":{"type":"object","properties":{}}}})
    monkeypatch.setattr(agent_loop, "host_tool_invokers", registry)
    monkeypatch.setattr(agent_loop, "OPENAI_TOOL_DEFINITIONS", definitions)
    monkeypatch.setattr(session_workspace, "workspace_tool_definitions", lambda: [])
    monkeypatch.setattr(agent_extensions, "bundled_host_tool_definitions", lambda **kwargs: [])
    rows, _ = agent_loop._build_host_tool_catalog({})
    assert len(rows) == 4 and read.call_count == get_manager.call_count == 1
    state["plugins"]["example"]["enabled"] = False
    asyncio.run(registry.invoke("example_0", SimpleNamespace(services={}), {}))
    assert not called
    rows, _ = agent_loop._build_host_tool_catalog({})
    assert not rows and read.call_count == 2


def test_host_catalog_work_does_not_block_the_builders_event_loop(monkeypatch):
    import asyncio
    import threading
    import agent_extensions
    import agent_loop
    import agent_mcp
    import agent_subagent

    entered, release = threading.Event(), threading.Event()
    catalog = SimpleNamespace(plugins=("catalog-from-owner-loop",))
    def loaded_on_owner_loop():
        assert asyncio.get_running_loop() is not None
        return catalog
    def blocking_host_pass(meta, loaded_plugins):
        assert loaded_plugins == catalog.plugins
        entered.set()
        assert release.wait(2), "event loop could not release the host pass"
        return [], {}
    async def empty(*args, **kwargs):
        return []
    async def contracts():
        return {}
    monkeypatch.setattr(agent_loop, "_build_host_tool_catalog", blocking_host_pass)
    monkeypatch.setattr(agent_extensions, "load_plugins", loaded_on_owner_loop)
    monkeypatch.setattr(agent_extensions, "plugin_tool_definitions", empty)
    monkeypatch.setattr(agent_extensions, "plugin_tool_contracts", contracts)
    monkeypatch.setattr(agent_mcp, "get_published_tool_definitions", empty)
    monkeypatch.setattr(agent_mcp, "get_pinned_tool_names", lambda: [])
    monkeypatch.setattr(agent_subagent, "filter_tools_for_session", lambda tools, meta: tools)
    monkeypatch.setattr(agent_subagent, "inject_task_model_profiles", lambda tools: tools)
    monkeypatch.setattr(agent_loop, "resolve_executor_config_for_session", lambda sid: (None,None,None,None))
    monkeypatch.setattr(agent_loop.tool_search, "assemble", lambda *args, **kwargs: None)
    async def scenario():
        task = asyncio.create_task(agent_loop.build_combined_tool_registry_for_session("s", session_meta={}))
        try:
            while not entered.is_set():
                await asyncio.sleep(0)
            assert not task.done()
            release.set()
            await task
        finally:
            release.set()
    asyncio.run(scenario())


def test_host_definition_facade_reuses_the_catalog_without_worker_refresh(monkeypatch):
    import agent_extensions
    import plugins.host as host

    plugins = (SimpleNamespace(plugin_id="example"),)
    def unexpected_reload():
        raise AssertionError("a worker must not reload a catalog supplied by its owner loop")
    seen = []
    monkeypatch.setattr(agent_extensions, "load_plugins", unexpected_reload)
    monkeypatch.setattr(host, "bundled_host_tool_definitions",
        lambda rows, **kwargs: seen.append((rows, kwargs)) or [])
    assert agent_extensions.bundled_host_tool_definitions(
        loaded_plugins=plugins, session_meta={"session": "s"}) == []
    assert seen == [(plugins, {"session_meta": {"session": "s"}})]
