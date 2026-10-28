"""Plugin migration must leave normal chat and core shutdown independent."""
import asyncio
from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from execution_services import integration, jobs
from plugins import load_plugin
from plugins.host import activate_bundled_provider_extensions, bundled_host_tool_definitions
from tests.computer_use_plugin import computer


def test_disabled_computer_plugin_does_not_break_normal_chat_prompt(monkeypatch):
    import plugins.host as host

    plugin = load_plugin(Path(__file__).resolve().parents[1] / "plugins" / "computer-use")
    monkeypatch.setattr(host, "bundled_host_plugin_enabled", lambda _: False)
    monkeypatch.setattr(integration, "_GUIDANCE_PROVIDERS", set())
    activate_bundled_provider_extensions([plugin], object())
    assert bundled_host_tool_definitions([plugin]) == []
    assert computer.GUIDANCE not in integration.prompt_guidance()
    assert "execution_services.computer" not in sys.modules

    service = jobs.ExecutionService()
    monkeypatch.setattr(computer, "_MANAGER", None)
    monkeypatch.setattr(jobs, "execution_service", lambda: service)
    assert computer.computer_manager().service is service


def test_plugin_registers_contracts_guidance_and_service_cleanup(monkeypatch, tmp_path):
    import host_tool_contracts
    import host_tool_registry
    import agent_tools
    from security.runtime import classify_tool

    closed = []

    class Driver:
        async def list_tools_json(self):
            return '{"tools":[{"name":"get_screen_size","inputSchema":{"type":"object"}},' \
                   '{"name":"click","inputSchema":{"type":"object"}}]}'

        async def shutdown(self):
            closed.append(True)

    monkeypatch.setitem(sys.modules, "cua_driver", SimpleNamespace(CuaDriver=SimpleNamespace(create=Driver)))
    monkeypatch.setattr(host_tool_registry, "host_tool_invokers", host_tool_registry.HostToolInvokerRegistry())
    monkeypatch.setattr(host_tool_contracts, "_PROVIDERS", [])
    monkeypatch.setattr(integration, "_GUIDANCE_PROVIDERS", set())
    monkeypatch.setattr(agent_tools, "_agent_protected_process_ids", lambda: {1234})
    service = jobs.ExecutionService()
    manager = computer.ComputerUseManager(service)
    monkeypatch.setattr(manager, "_plugin_enabled", lambda: True)

    async def scenario():
        try:
            assert (await service.call(manager.configure, True, save=False))["state"] == "ready"
            assert computer.GUIDANCE in integration.prompt_guidance()
            assert classify_tool("cua_driver_native__get_screen_size", {}, tmp_path).effect == "read"
            assert classify_tool("cua_driver_native__click", {"pid": 9999}, tmp_path).effect == "external_write"
            assert classify_tool("cua_driver_native__click", {"pid": 1234}, tmp_path).effect == "policy_change"
        finally:
            await service.shutdown()

        assert closed == [True]
        assert not host_tool_contracts.tool_contract("cua_driver_native__click")
        assert computer.GUIDANCE not in integration.prompt_guidance()
        assert not service._thread.is_alive()

    asyncio.run(scenario())
