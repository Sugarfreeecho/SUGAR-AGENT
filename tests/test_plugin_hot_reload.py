"""``reload_plugin`` host tool: schema, registration and targeted reload."""
import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

TARGET = "demo.target"


def _plugin(plugin_id=TARGET, signature="v1", **extra):
    fields = dict(skills=(), hooks=(), mcp_servers={}, agents=(), prompts=())
    fields.update(extra)
    return SimpleNamespace(plugin_id=plugin_id, content_signature=signature, **fields)


def _install(monkeypatch, plugins, *, discovered=None, enabled=True, rows=None,
             context=(None, {}), changed=None, errors=()):
    """Stub the agent_extensions seams the reload path depends on."""

    import agent_extensions as ext
    import plugin_hot_reload

    events = []
    changed_ids = tuple(p.plugin_id for p in plugins) if changed is None else tuple(changed)
    discovered_ids = tuple(discovered if discovered is not None else (plugins or [_plugin()]))

    class _Manager:
        def discover(self):
            return tuple(discovered_ids)

        def reload_changed(self):
            events.append(("reload_changed", ()))
            return SimpleNamespace(
                changes=SimpleNamespace(
                    added=(), changed=changed_ids, removed=(),
                    to_dict=lambda: {"added": [], "changed": list(changed_ids),
                                     "removed": [], "has_changes": bool(changed_ids)},
                ),
                loaded=SimpleNamespace(plugins=tuple(plugins), errors=tuple(errors)),
            )

        def is_enabled(self, plugin_id):
            return enabled

        def loaded_signature(self, plugin_id):
            return "v1"

    def invalidate(*, plugin_id=None):
        events.append(("invalidate", plugin_id))

    async def background(*, loaded=None):
        events.append(("background", tuple(p.plugin_id for p in loaded.plugins)))
        return list(rows or [])

    monkeypatch.setattr(ext, "plugin_manager", _Manager)
    monkeypatch.setattr(ext, "invalidate_extension_caches", invalidate)
    monkeypatch.setattr(ext, "start_plugin_background_services", background)
    monkeypatch.setattr(plugin_hot_reload, "_web_context", lambda: context)
    return events


def test_tool_is_registered_and_declared():
    import builtin_host_tools  # noqa: F401 - registers built-in host tools
    import agent_tools
    import tool_search
    from host_tool_registry import host_tool_invokers

    assert host_tool_invokers.has("reload_plugin")
    assert host_tool_invokers.owner("reload_plugin") == "core.services"
    assert host_tool_invokers.is_enabled("reload_plugin")
    names = [row["function"]["name"] for row in agent_tools.OPENAI_TOOL_DEFINITIONS]
    assert "reload_plugin" in names
    assert "reload_plugin" in tool_search.RESIDENT_TOOLS


def test_unknown_plugin_is_rejected_before_any_invalidation(monkeypatch):
    import agent_extensions as ext
    import plugin_hot_reload

    monkeypatch.setattr(ext, "plugin_manager", lambda: SimpleNamespace(discover=lambda: ()))
    monkeypatch.setattr(
        ext, "invalidate_extension_caches",
        lambda **_: pytest.fail("unknown plugin must not invalidate caches"),
    )
    outcome = asyncio.run(plugin_hot_reload.invoke_reload_plugin(None, {"plugin_id": "missing-plugin"}))
    assert outcome.code == "unknown_plugin"
    assert outcome.kind.value == "failed"


def test_reload_is_targeted_and_reports_changes(monkeypatch):
    import plugin_hot_reload

    rows = [
        {"plugin_id": TARGET, "services": [{"name": "indexer", "status": "running"}]},
        {"plugin_id": "demo.other", "services": []},
    ]
    events = _install(monkeypatch, [_plugin()], rows=rows)
    payload = asyncio.run(plugin_hot_reload.reload_plugin(TARGET, reason="edited manifest"))

    assert ("invalidate", TARGET) in events
    assert ("background", (TARGET,)) in events
    assert payload["changed"] is True
    assert payload["enabled"] is True and payload["active"] is True
    assert payload["signature_before"] == "v1" and payload["signature_after"] == "v1"
    assert payload["background_services"] == [rows[0]]
    assert payload["routes_reinstalled"] is False
    assert any("FastAPI" in warning for warning in payload["warnings"])
    assert payload["errors"] == [] and payload["elapsed_ms"] >= 0


def test_unchanged_plugin_reports_no_change(monkeypatch):
    import plugin_hot_reload

    _install(monkeypatch, [_plugin()], changed=())
    payload = asyncio.run(plugin_hot_reload.reload_plugin(TARGET))
    assert payload["changed"] is False
    assert payload["changes"]["has_changes"] is False


def test_disabled_plugin_reports_inactive_without_starting_workers(monkeypatch):
    import plugin_hot_reload

    events = _install(monkeypatch, [], enabled=False, changed=())
    payload = asyncio.run(plugin_hot_reload.reload_plugin(TARGET))

    assert payload["active"] is False and payload["enabled"] is False
    assert ("background", ()) not in events
    assert payload["warnings"]


def test_load_errors_for_the_plugin_are_surfaced(monkeypatch):
    import plugin_hot_reload

    load_errors = [f"{TARGET}: manifest rejected", "other-plugin: unrelated"]
    _install(monkeypatch, [], errors=load_errors, changed=())
    payload = asyncio.run(plugin_hot_reload.reload_plugin(TARGET))
    assert payload["errors"] == [load_errors[0]]


def test_routes_are_reinstalled_and_mcp_refreshed(monkeypatch):
    import agent_mcp
    import plugin_hot_reload
    import plugins.host as host

    calls = []

    def install(app, plugins, context):
        calls.append(("install", app))

    async def start(plugins, context):
        calls.append(("start",))

    async def force_reload():
        calls.append(("mcp",))

    monkeypatch.setattr(host, "install_bundled_host_extensions", install)
    monkeypatch.setattr(host, "start_bundled_host_extensions", start)
    monkeypatch.setattr(agent_mcp, "force_reload", force_reload)
    app = object()
    _install(monkeypatch, [_plugin(mcp_servers={"docs": {"command": "node"}})],
             context=(app, {"app": "ctx"}))

    payload = asyncio.run(plugin_hot_reload.reload_plugin(TARGET))

    assert [call[0] for call in calls] == ["install", "start", "mcp"]
    assert calls[0][1] is app
    assert payload["routes_reinstalled"] is True and payload["mcp_refreshed"] is True
    assert payload["components"]["mcp_servers"] == 1


def test_host_reinstall_failure_is_a_warning_not_a_failure(monkeypatch):
    import plugin_hot_reload
    import plugins.host as host

    def install(app, plugins, context):
        raise RuntimeError("route conflict")

    monkeypatch.setattr(host, "install_bundled_host_extensions", install)
    _install(monkeypatch, [_plugin()], context=(object(), {}))

    payload = asyncio.run(plugin_hot_reload.reload_plugin(TARGET))
    assert payload["ok"] is True and payload["routes_reinstalled"] is False
    assert any("route conflict" in warning for warning in payload["warnings"])


def test_tool_result_is_json_payload(monkeypatch):
    import plugin_hot_reload

    _install(monkeypatch, [_plugin()])
    outcome = asyncio.run(plugin_hot_reload.invoke_reload_plugin(None, {"plugin_id": "Demo.Target"}))
    body = json.loads(outcome.content)
    assert body["ok"] is True and body["plugin_id"] == TARGET


def test_loaded_signature_reports_the_recorded_baseline(tmp_path):
    from plugins import PluginManager

    root = tmp_path / "demo-hot"
    (root / ".myagent-plugin").mkdir(parents=True)
    (root / ".myagent-plugin" / "plugin.json").write_text(
        json.dumps({"schema_version": 1, "name": "demo-hot", "version": "0.1.0"}),
        encoding="utf-8",
    )
    manager = PluginManager([tmp_path], tmp_path / "state.json")
    manager.enable("demo-hot")

    loaded = manager.load_enabled()
    current = next(plugin for plugin in loaded.plugins if plugin.plugin_id == "demo-hot")
    assert manager.loaded_signature("demo-hot") == current.content_signature

    skill = root / "skills" / "review" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: review\ndescription: demo\n---\n\nbody\n", encoding="utf-8")
    # discovery sees the new tree; the recorded baseline still describes the last load
    assert manager.loaded_signature("demo-hot") != manager.discover()[0].content_signature
