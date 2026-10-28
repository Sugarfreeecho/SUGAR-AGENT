import json
import sys
import threading
from dataclasses import replace
from pathlib import Path

import pytest
from tests.test_session_control import composed


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


def _plugin(tmp_path, services):
    from plugins import load_plugin

    root = tmp_path / "service-plugin"
    manifest_path = root / ".myagent-plugin" / "plugin.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "id": "service.demo",
                "name": "Service Demo",
                "version": "1.0.0",
            }
        ),
        encoding="utf-8",
    )
    plugin = load_plugin(root)
    return replace(plugin, permissions={"services": services})


@pytest.mark.parametrize(
    "status",
    [
        "completed",
        "finished",
        "failed",
        "cancelled",
        "interrupted",
        "orphaned",
        "stale",
    ],
)
def test_session_activity_check_accepts_every_terminal_runtime_status(
    monkeypatch, status
):
    import plugin_host_services as services
    import runtime_observability

    monkeypatch.setattr(
        runtime_observability,
        "snapshot",
        lambda _session_id: {"runs": [{"status": status}]},
    )

    assert services._session_is_active("session-finished") is False


def test_session_activity_check_rejects_a_running_runtime_status(monkeypatch):
    import plugin_host_services as services
    import runtime_observability

    monkeypatch.setattr(
        runtime_observability,
        "snapshot",
        lambda _session_id: {"runs": [{"status": "running"}]},
    )

    assert services._session_is_active("session-running") is True


def test_sessions_run_many_durably_queues_busy_sessions_and_revokes_only_plugin_inputs(composed, tmp_path, monkeypatch):
    import asyncio
    import agent_harness
    import plugin_host_services as services
    import session_control.integration as integration
    from tests.test_session_control import new_session
    c = composed
    monkeypatch.setattr(integration, "_application", c.control)
    monkeypatch.setattr(agent_harness, "session_manager", c.manager)
    plugin = _plugin(tmp_path, ["sessions.run_many"])
    async def scenario():
        one, two = await new_session(c), await new_session(c)
        c.active.update({one: "browser-one", two: "browser-two"})
        await c.control.start()
        action = [{"service": "sessions.run_many", "sessions": [
            {"session_id": one, "prompt": "one"}, {"session_id": two, "prompt": "two"}]}]
        first = await asyncio.to_thread(services.execute_host_actions, plugin, action,
            trusted_session_ids=(one, two), trusted_run_id="trigger-one")
        replay = await asyncio.to_thread(services.execute_host_actions, plugin, action,
            trusted_session_ids=(one, two), trusted_run_id="trigger-one")
        assert first[0]["accepted"] and len(first[0]["operation_ids"]) == 2
        assert replay[0]["operation_ids"] == first[0]["operation_ids"]
        second = await asyncio.to_thread(services.execute_host_actions, plugin, action,
            trusted_session_ids=(one, two), trusted_run_id="trigger-two")
        assert second[0]["operation_ids"] != first[0]["operation_ids"]
        assert all(c.store.get_operation(oid)["status"] == "queued"
                   for oid in first[0]["operation_ids"] + second[0]["operation_ids"])
        assert services.release_plugin_leases(plugin.plugin_id) == 4
        assert all(c.store.get_operation(oid)["status"] == "cancelled"
                   for oid in first[0]["operation_ids"] + second[0]["operation_ids"])
        assert c.active == {one: "browser-one", two: "browser-two"}
        c.active.clear()
        await c.control.close()
    asyncio.run(scenario())


def test_sessions_run_many_requires_an_exact_host_authorized_session_set(composed, tmp_path, monkeypatch):
    import asyncio
    import agent_harness
    import plugin_host_services as services
    import session_control.integration as integration
    from tests.test_session_control import new_session
    c = composed
    monkeypatch.setattr(integration, "_application", c.control)
    monkeypatch.setattr(agent_harness, "session_manager", c.manager)
    plugin = _plugin(tmp_path, ["sessions.run_many"])
    async def scenario():
        one, two = await new_session(c), await new_session(c)
        await c.control.start()
        action = [{"service": "sessions.run_many", "sessions": [
            {"session_id": one, "prompt": "one"}, {"session_id": two, "prompt": "two"}]}]
        with pytest.raises(services.PluginHostServiceError) as missing:
            services.execute_host_actions(plugin, action)
        assert missing.value.code == "session_run_grant_required"
        with pytest.raises(services.PluginHostServiceError) as mismatched:
            services.execute_host_actions(plugin, action, trusted_session_ids=(one,))
        assert mismatched.value.code == "session_scope_denied"
        assert not any(op["method"] == "session.send" for op in c.store.operations())
        result = await asyncio.to_thread(services.execute_host_actions, plugin, action, trusted_session_ids=(one, two))
        assert result[0]["accepted"]
        await c.control.close()
    asyncio.run(scenario())


def test_session_run_grant_is_plugin_bound_and_one_use(tmp_path, monkeypatch):
    import agent_harness
    import plugin_host_services as services

    class FakeSessionManager:
        @staticmethod
        def get_session_summary(session_id):
            return {"id": session_id} if session_id in {"s1", "s2"} else None

    monkeypatch.setattr(agent_harness, "session_manager", FakeSessionManager())
    services._session_run_grants.clear()
    plugin = _plugin(tmp_path, ["sessions.run_many"])
    other = replace(plugin, plugin_id="service.other", namespace="service.other")
    grant = services.issue_session_run_grant(plugin, ["s1", "s2"])

    with pytest.raises(services.PluginHostServiceError) as wrong_owner:
        services.consume_session_run_grant(other, grant["token"])
    assert wrong_owner.value.code == "invalid_session_run_grant"

    grant = services.issue_session_run_grant(plugin, ["s1", "s2"])
    assert services.consume_session_run_grant(plugin, grant["token"]) == frozenset(
        {"s1", "s2"}
    )
    with pytest.raises(services.PluginHostServiceError) as replay:
        services.consume_session_run_grant(plugin, grant["token"])
    assert replay.value.code == "invalid_session_run_grant"


def test_host_service_requires_explicit_manifest_permission(tmp_path):
    import plugin_host_services as services

    plugin = _plugin(tmp_path, [])

    with pytest.raises(services.PluginHostServiceError) as exc_info:
        services.execute_host_actions(
            plugin,
            [{"service": "sessions.run_many", "sessions": []}],
        )

    assert exc_info.value.status == 403
    assert exc_info.value.code == "service_permission_denied"


def test_session_state_services_are_scoped_to_trusted_tool_session(tmp_path, monkeypatch):
    import agent_harness
    import plugin_host_services as services

    class FakeSessionManager:
        sessions_dir = tmp_path

        @staticmethod
        def _resolve_session_path(session_id):
            return tmp_path / session_id

    (tmp_path / "s1").mkdir()
    (tmp_path / "s2").mkdir()
    monkeypatch.setattr(agent_harness, "session_manager", FakeSessionManager())
    plugin = _plugin(
        tmp_path,
        [
            "session_state.compare_and_set",
            "session_state.set_latest",
            "session_state.get",
            "session_state.patch",
        ],
    )

    created = services.execute_host_actions(
        plugin,
        [
            {
                "service": "session_state.compare_and_set",
                "namespace": "prefs",
                "expected_revision": 0,
                "value": {"enabled": False},
            }
        ],
        trusted_session_id="s1",
    )[0]
    assert created["state"]["revision"] == 1
    patched = services.execute_host_actions(
        plugin,
        [
            {
                "service": "session_state.patch",
                "namespace": "prefs",
                "expected_revision": 1,
                "operations": [
                    {"op": "replace", "path": "/enabled", "value": True}
                ],
            }
        ],
        trusted_session_id="s1",
    )[0]
    assert patched["state"]["value"] == {"enabled": True}
    latest = services.execute_host_actions(
        plugin,
        [
            {
                "service": "session_state.set_latest",
                "namespace": "prefs",
                "value": {"enabled": False, "source": "plugin"},
            }
        ],
        trusted_session_id="s1",
    )[0]
    assert latest["service"] == "session_state.set_latest"
    assert latest["plugin_id"] == "service.demo"
    assert latest["namespace"] == "prefs"
    assert latest["state"]["revision"] == 3
    assert latest["state"]["value"] == {"enabled": False, "source": "plugin"}

    with pytest.raises(services.PluginHostServiceError) as no_context:
        services.execute_host_actions(
            plugin,
            [{"service": "session_state.get", "namespace": "prefs"}],
        )
    assert no_context.value.code == "trusted_session_required"

    with pytest.raises(services.PluginHostServiceError) as wrong_session:
        services.execute_host_actions(
            plugin,
            [
                {
                    "service": "session_state.get",
                    "session_id": "s2",
                    "namespace": "prefs",
                }
            ],
            trusted_session_id="s1",
        )
    assert wrong_session.value.code == "session_scope_denied"
