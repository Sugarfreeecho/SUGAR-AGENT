import asyncio
from pathlib import Path
import sys
import time
from types import SimpleNamespace

import pytest

APP = Path(__file__).resolve().parents[1] / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))


@pytest.fixture
def mcp(monkeypatch):
    import agent_mcp

    for key, value in {
        "_servers": {}, "_fname_to_tool": {}, "_defs_snapshot": [],
        "_tool_contracts": {}, "_tool_selections": {}, "_server_start_errors": {},
        "_server_config_signatures": {}, "_server_retry_state": {},
        "_server_registration_descriptors": {},
        "_plugin_mcp_content_signatures": {},
        "_host_reserved_servers": set(), "_loaded_signature": None,
        "_disabled_mcp_tools": set(), "_disabled_mcp_tools_loaded": True,
        "_tool_catalog_generation": 0, "_MCP_IMPORT_OK": True,
    }.items():
        monkeypatch.setattr(agent_mcp, key, value)
    monkeypatch.setattr(agent_mcp, "_enabled_flag", lambda: True)
    monkeypatch.setattr(agent_mcp, "schedule_mcp_startup_refresh", lambda: None)
    return agent_mcp


def publish(mcp, alias, stopped):
    async def stop():
        stopped.append(alias)
    mcp._servers[alias] = SimpleNamespace(stop=stop, connection_status=lambda: {"connected": True})
    mcp._register_tools_globally(alias, [SimpleNamespace(
        name="read", description="Read", inputSchema={"type": "object"},
    )])


def test_plugin_reload_retains_unrelated_published_connections(mcp):
    stopped = []
    for alias in ("demo.target/one", "demo.target/two", "demo.target-extra/keep", "standalone"):
        publish(mcp, alias, stopped)
        mcp._server_config_signatures[alias] = "fingerprint"
    keep = mcp._servers["standalone"]
    asyncio.run(mcp._reload_plugin_impl("demo.target"))
    assert set(stopped) == {"demo.target/one", "demo.target/two"}
    assert set(mcp._servers) == {"demo.target-extra/keep", "standalone"}
    assert mcp._servers["standalone"] is keep
    assert {pair[0] for pair in mcp._fname_to_tool.values()} == {"demo.target-extra/keep", "standalone"}
    assert mcp._loaded_signature is None


def test_catalog_read_never_awaits_discovery_and_filters_disabled(mcp, monkeypatch):
    async def forbidden():
        raise AssertionError("catalog readers must not start or await a connection")
    monkeypatch.setattr(mcp, "ensure_started", forbidden)
    publish(mcp, "good", [])
    publish(mcp, "disabled", [])
    mcp._disabled_mcp_tools.add("mcp_disabled_read")

    definitions = asyncio.run(mcp.get_published_tool_definitions())

    assert [row["function"]["name"] for row in definitions] == ["mcp_good_read"]
    monkeypatch.setattr(mcp, "_disabled_mcp_tools_loaded", False)
    monkeypatch.setattr(mcp, "_load_disabled_mcp_tools", lambda: set())
    assert asyncio.run(mcp.get_published_tool_definitions()) == []


def test_global_disable_hides_published_tools_and_refuses_existing_route(mcp, monkeypatch):
    publish(mcp, "good", [])
    monkeypatch.setattr(mcp, "_enabled_flag", lambda: False)
    assert asyncio.run(mcp.get_published_tool_definitions()) == []
    assert asyncio.run(mcp.get_tool_catalog_revision())[1] == "disabled"
    assert "disabled" in asyncio.run(mcp.invoke_tool_by_fname("mcp_good_read", {}))


def test_unreadable_enablement_state_refuses_previously_published_route(mcp, monkeypatch):
    publish(mcp, "good", [])
    revision = asyncio.run(mcp.get_tool_catalog_revision())
    monkeypatch.setattr(mcp, "_disabled_mcp_tools_loaded", False)
    monkeypatch.setattr(mcp, "_load_disabled_mcp_tools", lambda: set())
    assert asyncio.run(mcp.get_tool_catalog_revision()) != revision
    assert asyncio.run(mcp.get_published_tool_definitions()) == []
    assert "disabled" in asyncio.run(mcp.invoke_tool_by_fname("mcp_good_read", {}))


def test_revoked_trust_invalidates_catalog_and_call_without_waiting_for_reload(mcp, monkeypatch):
    approved = [True]
    publish(mcp, "good", [])
    mcp._server_registration_descriptors["good"] = {"extension_id": "good"}
    monkeypatch.setattr("security.extensions.extension_registration_approval_enabled", lambda: True)
    monkeypatch.setattr("security.extensions.mcp_registration_is_approved", lambda descriptor: approved[0])
    revision = asyncio.run(mcp.get_tool_catalog_revision())
    assert len(asyncio.run(mcp.get_published_tool_definitions())) == 1
    approved[0] = False
    assert asyncio.run(mcp.get_tool_catalog_revision()) != revision
    assert asyncio.run(mcp.get_published_tool_definitions()) == []
    assert "approval is required" in asyncio.run(mcp.invoke_tool_by_fname("mcp_good_read", {}))


def test_healthy_server_publishes_before_slow_sibling_finishes(mcp, monkeypatch):
    monkeypatch.setattr(mcp, "_compute_config_signature_cached", lambda: "config")
    monkeypatch.setattr(mcp, "_load_servers_dict_from_config", lambda: (
        {"slow": {"command": "slow"}, "good": {"command": "good"}}, None,
    ))

    async def scenario():
        release = asyncio.Event()
        healthy = asyncio.Event()

        async def start(alias, cfg):
            if alias == "slow":
                await release.wait()
            publish(mcp, alias, [])
            if alias == "good":
                healthy.set()
        monkeypatch.setattr(mcp, "_start_configured_server_unlocked", start)
        task = asyncio.create_task(mcp._ensure_started_impl())
        try:
            await asyncio.wait_for(healthy.wait(), timeout=1)
            assert not task.done()
            definitions = await mcp.get_published_tool_definitions()
            assert [row["function"]["name"] for row in definitions] == ["mcp_good_read"]
        finally:
            release.set()
            await task
    asyncio.run(mcp._run_on_mcp_loop(scenario()))


def test_signature_drift_restarts_only_changed_server(mcp, monkeypatch):
    signature = ["initial"]
    configs = {"a": {"command": "a"}, "b": {"command": "b"}}
    started, stopped = [], []
    monkeypatch.setattr(mcp, "_compute_config_signature_cached", lambda: signature[0])
    monkeypatch.setattr(mcp, "_load_servers_dict_from_config", lambda: (configs, None))

    async def start(alias, cfg):
        started.append(alias)
        publish(mcp, alias, stopped)
    monkeypatch.setattr(mcp, "_start_configured_server_unlocked", start)

    asyncio.run(mcp.ensure_started())
    generation = mcp._tool_catalog_generation
    signature[0] = "unrelated-plugin-edit"
    asyncio.run(mcp.ensure_started())
    assert started == ["a", "b"] and not stopped
    assert mcp._tool_catalog_generation == generation

    configs["a"] = {"command": "a-new"}
    signature[0] = "changed-a"
    asyncio.run(mcp.ensure_started())
    assert started == ["a", "b", "a"] and stopped == ["a"]
    del configs["b"]
    signature[0] = "removed-b"
    asyncio.run(mcp.ensure_started())
    assert stopped == ["a", "b"]
    assert [row["function"]["name"] for row in asyncio.run(mcp.get_published_tool_definitions())] == ["mcp_a_read"]


def test_failure_backoff_does_not_restart_healthy_servers(mcp, monkeypatch):
    started = []
    monkeypatch.setattr(mcp, "_compute_config_signature_cached", lambda: "config")
    monkeypatch.setattr(mcp, "_load_servers_dict_from_config", lambda: (
        {"good": {"command": "good"}, "bad": {"command": "bad"}}, None,
    ))

    async def start(alias, cfg):
        started.append(alias)
        if alias == "bad":
            raise RuntimeError("server unavailable")
        publish(mcp, alias, [])
    monkeypatch.setattr(mcp, "_start_configured_server_unlocked", start)

    asyncio.run(mcp.ensure_started())
    assert mcp._server_retry_state["bad"][0] == 1
    asyncio.run(mcp.ensure_started())
    assert started == ["good", "bad"]
    mcp._server_retry_state["bad"] = (1, time.monotonic() - 1)
    asyncio.run(mcp.ensure_started())
    assert started == ["good", "bad", "bad"]
    assert mcp._server_retry_state["bad"][0] == 2
    assert "server unavailable" in mcp._server_start_errors["bad"]


def test_plugin_code_change_restarts_its_own_server_only(mcp, monkeypatch):
    signature = ["initial"]
    started, stopped = [], []
    configs = {"example/service": {"command": "example"}, "other": {"command": "other"}}
    mcp._plugin_mcp_content_signatures["example"] = "code-v1"
    monkeypatch.setattr(mcp, "_compute_config_signature_cached", lambda: signature[0])
    monkeypatch.setattr(mcp, "_load_servers_dict_from_config", lambda: (configs, None))
    async def start(alias, cfg):
        started.append(alias)
        publish(mcp, alias, stopped)
    monkeypatch.setattr(mcp, "_start_configured_server_unlocked", start)
    asyncio.run(mcp.ensure_started())
    signature[0] = "example-code-changed"
    mcp._plugin_mcp_content_signatures["example"] = "code-v2"
    asyncio.run(mcp.ensure_started())
    assert started == ["example/service", "other", "example/service"]
    assert stopped == ["example/service"]
