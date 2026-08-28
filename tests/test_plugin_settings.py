import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


def _plugin(tmp_path, *, schema, permissions=None, source=None, ui=None):
    from plugins import load_plugin

    root = tmp_path / "settings-plugin"
    manifest = root / ".myagent-plugin" / "plugin.json"
    manifest.parent.mkdir(parents=True)
    payload = {
        "schema_version": 1,
        "id": "settings.demo",
        "name": "Settings Demo",
        "version": "1.0.0",
        "settings_schema": schema,
        "permissions": permissions or {},
    }
    if ui is not None:
        payload["capabilities"] = {"ui": ui}
    if source is not None:
        (root / "plugin.py").write_text(source, encoding="utf-8")
        payload["runtime"] = {"type": "python", "entrypoint": "./plugin.py"}
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    return load_plugin(root)


def _schema():
    return {
        "type": "object",
        "schema_version": 2,
        "title": "Demo settings",
        "required": ["enabled", "token"],
        "properties": {
            "enabled": {"type": "boolean", "title": "Enabled", "default": True},
            "mode": {"type": "string", "title": "Mode", "enum": ["safe", "fast"], "default": "safe"},
            "retries": {"type": "integer", "title": "Retries", "minimum": 0, "maximum": 5},
            "notes": {"type": "string", "format": "multiline", "title": "Notes", "maxLength": 40},
            "token": {"type": "string", "format": "secret", "secret_ref": "DEMO_TOKEN", "title": "Token"},
        },
    }


def test_settings_store_validates_defaults_updates_and_never_persists_secret(tmp_path):
    from plugins import PluginSettingsStore, public_plugin_settings

    plugin = _plugin(
        tmp_path,
        schema=_schema(),
        permissions={"secrets": ["DEMO_TOKEN"], "context": ["settings", "secrets"]},
    )
    path = tmp_path / "host-settings.json"
    store = PluginSettingsStore(path)

    assert store.values(plugin) == {"enabled": True, "mode": "safe"}
    assert store.update(plugin, {"mode": "fast", "retries": 3, "notes": "hello"}) == {
        "enabled": True,
        "mode": "fast",
        "retries": 3,
        "notes": "hello",
    }
    public = public_plugin_settings(
        plugin,
        store=store,
        environment={"DEMO_TOKEN": "actual-secret"},
    )
    encoded = json.dumps(public)
    stored = path.read_text(encoding="utf-8")
    assert public["valid"] is True
    assert public["schema_version"] == 2
    token = next(field for field in public["fields"] if field["id"] == "token")
    assert token["configured"] is True
    assert token["reference"] == "DEMO_TOKEN"
    assert "actual-secret" not in encoded
    assert "actual-secret" not in stored
    assert "DEMO_TOKEN" not in stored

    with pytest.raises(ValueError, match="allowed value"):
        store.update(plugin, {"mode": "turbo"})
    with pytest.raises(ValueError, match="manifest-owned"):
        store.update(plugin, {"token": "actual-secret"})
    with pytest.raises(ValueError, match="Unknown plugin setting"):
        store.update(plugin, {"other": True})


def test_secret_field_requires_manifest_permission(tmp_path):
    from plugins import PluginValidationError

    with pytest.raises(PluginValidationError, match="permissions.secrets"):
        _plugin(tmp_path, schema=_schema(), permissions={"context": ["secrets"]})


def test_settings_store_updates_are_atomic_under_concurrency(tmp_path):
    from plugins import PluginSettingsStore

    schema = _schema()
    schema["properties"].update(
        {f"value_{index}": {"type": "integer"} for index in range(12)}
    )
    plugin = _plugin(
        tmp_path,
        schema=schema,
        permissions={"secrets": ["DEMO_TOKEN"]},
    )
    store = PluginSettingsStore(tmp_path / "settings.json")

    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(lambda index: store.update(plugin, {f"value_{index}": index}), range(12)))

    values = store.values(plugin)
    assert all(values[f"value_{index}"] == index for index in range(12))
    assert not list((tmp_path).glob(".*.tmp"))


def test_runtime_injects_host_settings_and_resolved_secrets_without_argument_spoofing(
    tmp_path, monkeypatch
):
    from plugins import PluginRuntimeRegistry, PluginSettingsStore

    source = """
from dataclasses import asdict
from myagent_plugin_sdk import Plugin, current_tool_context

plugin = Plugin()

@plugin.tool(name="inspect", input_schema={"type": "object", "properties": {}})
def inspect():
    return asdict(current_tool_context())
""".lstrip()
    plugin = _plugin(
        tmp_path,
        schema=_schema(),
        permissions={"secrets": ["DEMO_TOKEN"], "context": ["settings", "secrets"]},
        source=source,
    )
    storage_root = tmp_path / "plugin-storage"
    PluginSettingsStore(storage_root / "_host" / "settings.json").update(
        plugin, {"mode": "fast", "retries": 4}
    )
    monkeypatch.setenv("DEMO_TOKEN", "resolved-secret")
    registry = PluginRuntimeRegistry(storage_root=storage_root)
    function_name = registry.tool_definitions([plugin])[0]["function"]["name"]

    result = registry.invoke(
        function_name,
        {},
        [plugin],
        context={
            "settings": {"mode": "spoofed"},
            "secrets": {"token": "spoofed"},
        },
    )
    registry.close()

    assert result["settings"] == {"enabled": True, "mode": "fast", "retries": 4}
    assert result["secrets"] == {"token": "resolved-secret"}


def test_runtime_does_not_inject_settings_without_explicit_context_permission(tmp_path):
    from plugins import PluginRuntimeRegistry, PluginSettingsStore

    source = """
from dataclasses import asdict
from myagent_plugin_sdk import Plugin, current_tool_context
plugin = Plugin()
@plugin.tool(name="inspect", input_schema={"type": "object", "properties": {}})
def inspect():
    return asdict(current_tool_context())
""".lstrip()
    plugin = _plugin(
        tmp_path,
        schema=_schema(),
        permissions={"secrets": ["DEMO_TOKEN"], "context": []},
        source=source,
    )
    storage_root = tmp_path / "plugin-storage"
    PluginSettingsStore(storage_root / "_host" / "settings.json").update(
        plugin, {"mode": "fast"}
    )
    registry = PluginRuntimeRegistry(storage_root=storage_root)
    function_name = registry.tool_definitions([plugin])[0]["function"]["name"]

    result = registry.invoke(function_name, {}, [plugin])
    registry.close()

    assert result["settings"] == {}
    assert result["secrets"] == {}


def test_settings_schema_automatically_contributes_a_host_form_without_plugin_web(tmp_path):
    from plugins import plugin_ui_contributions

    plugin = _plugin(
        tmp_path,
        schema=_schema(),
        permissions={"secrets": ["DEMO_TOKEN"]},
    )

    assert plugin_ui_contributions(plugin) == (
        {
            "id": "main",
            "plugin_id": "settings.demo",
            "slot": "settings.section",
            "title": "Demo settings",
            "label": "Save",
            "description": "",
            "order": 100,
            "target": "plugin-settings",
            "endpoint": "/api/plugins/settings.demo/settings",
        },
    )


def test_explicit_empty_settings_section_keeps_schema_without_rendering_host_form(tmp_path):
    from plugins import plugin_ui_contributions

    plugin = _plugin(
        tmp_path,
        schema=_schema(),
        permissions={"secrets": ["DEMO_TOKEN"]},
        ui={"settings.section": []},
    )

    assert plugin_ui_contributions(plugin) == ()


def test_agent_extensions_settings_api_uses_discovery_and_host_store(tmp_path, monkeypatch):
    import agent_extensions
    from plugins import PluginManager

    plugin = _plugin(
        tmp_path,
        schema=_schema(),
        permissions={"secrets": ["DEMO_TOKEN"], "context": ["settings", "secrets"]},
    )
    manager = PluginManager([plugin.root.parent], tmp_path / "plugin-state.json")
    storage_root = tmp_path / "storage"
    monkeypatch.setattr(agent_extensions, "plugin_manager", lambda: manager)
    monkeypatch.setenv("PLUGIN_STORAGE_DIR", str(storage_root))
    monkeypatch.setenv("PLUGINS_ENABLED", "1")
    monkeypatch.delenv("DEMO_TOKEN", raising=False)
    agent_extensions.invalidate_extension_caches()

    before = agent_extensions.plugin_settings_snapshot("settings.demo")
    after = agent_extensions.update_plugin_settings(
        "settings.demo", {"mode": "fast", "retries": 2}
    )

    assert before["settings"]["valid"] is False
    assert after["settings"]["fields"][1]["value"] == "fast"
    persisted = json.loads((storage_root / "_host" / "settings.json").read_text(encoding="utf-8"))
    assert persisted["plugins"]["settings.demo"]["values"] == {
        "mode": "fast",
        "retries": 2,
    }
