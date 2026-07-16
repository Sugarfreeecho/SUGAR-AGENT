import json
from pathlib import Path

import pytest

from app.plugins import (
    PluginManager,
    PluginSecurityError,
    PluginStateError,
    PluginStateStore,
    PluginValidationError,
    discover_plugins,
    load_plugin,
    plugins_enabled,
)


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _make_native(root: Path, name: str = "quality-tools", **extra) -> Path:
    manifest = {
        "schema_version": 1,
        "name": name,
        "version": "1.2.3",
        "description": "Quality gates",
        **extra,
    }
    _write_json(root / ".myagent-plugin" / "plugin.json", manifest)
    return root


def _make_skill(root: Path, directory: str = "review", name: str = "review") -> Path:
    path = root / "skills" / directory / "SKILL.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"---\nname: {name}\ndescription: Review changes\n---\n\nDo the review.\n",
        encoding="utf-8",
    )
    return path


@pytest.mark.parametrize("value", ["0", "false", "FALSE", "no", "off", " Off "])
def test_plugins_environment_switch_defaults_on_and_accepts_false_values(monkeypatch, value):
    monkeypatch.delenv("PLUGINS_ENABLED", raising=False)
    assert plugins_enabled() is True
    monkeypatch.setenv("PLUGINS_ENABLED", value)
    assert plugins_enabled() is False


def test_native_manifest_loads_all_declarative_components_with_namespaces(tmp_path):
    plugin_root = tmp_path / "quality"
    _make_skill(plugin_root, name="code-review")
    hooks = plugin_root / "hooks" / "hooks.json"
    _write_json(hooks, {"version": 1, "hooks": {}})
    agents = plugin_root / "agents"
    agents.mkdir(parents=True)
    (agents / "reviewer.md").write_text("Review safely", encoding="utf-8")
    prompts = plugin_root / "prompts"
    prompts.mkdir(parents=True)
    (prompts / "finish.md").write_text("Finish", encoding="utf-8")
    mcp = plugin_root / "mcp" / "servers.json"
    _write_json(
        mcp,
        {
            "servers": {
                "lint server": {
                    "command": "python",
                    "args": ["${MYAGENT_PLUGIN_ROOT}/server.py"],
                    "cwd": "${MYAGENT_PLUGIN_ROOT}",
                }
            }
        },
    )
    (plugin_root / "server.py").write_text("raise AssertionError('must not import')\n", encoding="utf-8")
    _make_native(
        plugin_root,
        skills=["./skills"],
        hooks="./hooks/hooks.json",
        mcp_servers="./mcp/servers.json",
        agents=["./agents"],
        prompts=["./prompts"],
        permissions={"shell": True, "network": False},
    )

    manager = PluginManager([tmp_path], tmp_path / "state.json")
    loaded = manager.load_enabled()

    assert loaded.globally_enabled is True
    assert len(loaded.plugins) == 1
    plugin = loaded.plugins[0]
    assert plugin.source_format == "native"
    assert plugin.compatibility.status == "native"
    assert plugin.permissions == {"shell": True, "network": False}
    assert set(loaded.skill_directories) == {"quality-tools:code-review"}
    assert [item.qualified_name for item in loaded.hook_sources] == ["quality-tools:hooks"]
    assert set(loaded.mcp_servers) == {"quality-tools/lint-server"}
    assert loaded.mcp_servers["quality-tools/lint-server"]["cwd"] == str(plugin_root.resolve())
    assert str(plugin_root.resolve()) in loaded.mcp_servers["quality-tools/lint-server"]["args"][0]
    assert set(loaded.agent_directories) == {"quality-tools:reviewer"}
    assert set(loaded.prompt_directories) == {"quality-tools:finish"}
    assert len(plugin.content_signature) == 64


def test_claude_conventions_convert_to_unified_compatible_definition(tmp_path):
    plugin_root = tmp_path / "claude-quality"
    _write_json(
        plugin_root / ".claude-plugin" / "plugin.json",
        {
            "name": "Claude Quality",
            "version": "2.0.0",
            "author": {"name": "Example"},
        },
    )
    _make_skill(plugin_root, name="review")
    _write_json(plugin_root / "hooks" / "hooks.json", {"hooks": {}})
    _write_json(plugin_root / ".mcp.json", {"mcpServers": {"audit": {"command": "npx"}}})

    plugin = load_plugin(plugin_root)

    assert plugin.plugin_id == "claude-quality"
    assert plugin.source_format == "claude"
    assert plugin.compatibility.status == "compatible"
    assert plugin.compatibility.supported_components == ("skills", "hooks", "mcp_servers")
    assert set(plugin.mcp_servers) == {"claude-quality/audit"}


def test_explicit_id_is_the_stable_namespace_while_name_remains_display_metadata(tmp_path):
    plugin_root = tmp_path / "identity"
    _write_json(
        plugin_root / ".myagent-plugin" / "plugin.json",
        {"id": "org.example.quality", "name": "Quality Tools", "version": "1.0.0"},
    )
    _make_skill(plugin_root, name="review")

    plugin = load_plugin(plugin_root)

    assert plugin.plugin_id == "org.example.quality"
    assert plugin.name == "Quality Tools"
    assert set(plugin.components) == {"skills", "hooks", "mcp_servers", "agents", "prompts"}


def test_codex_plugin_reports_partial_when_supported_and_host_specific_parts_mix(tmp_path):
    plugin_root = tmp_path / "codex-plugin"
    _write_json(
        plugin_root / ".codex-plugin" / "plugin.json",
        {
            "name": "Codex Helper",
            "version": "1.0.0",
            "skills": ["./skills"],
            "apps": ["./apps/example"],
            "main": "plugin.py",
        },
    )
    _make_skill(plugin_root, name="helper")
    (plugin_root / "plugin.py").write_text("raise RuntimeError('never imported')\n", encoding="utf-8")

    plugin = load_plugin(plugin_root)

    assert plugin.source_format == "codex"
    assert plugin.compatibility.status == "partial"
    assert set(plugin.compatibility.unsupported_components) == {"apps", "main"}
    assert any("not loaded" in warning for warning in plugin.compatibility.warnings)


def test_plugin_with_only_host_entrypoint_is_reported_unsupported_and_not_loaded(tmp_path):
    plugin_root = tmp_path / "unsafe-only"
    _write_json(
        plugin_root / ".claude-plugin" / "plugin.json",
        {"name": "Unsafe only", "main": "plugin.py"},
    )
    (plugin_root / "plugin.py").write_text("raise RuntimeError('never imported')\n", encoding="utf-8")
    plugin = load_plugin(plugin_root)
    assert plugin.compatibility.status == "unsupported"

    loaded = PluginManager([tmp_path], tmp_path / "state.json").load_enabled()
    assert loaded.plugins == ()
    assert any("unsupported" in error for error in loaded.errors)


@pytest.mark.parametrize("declared", ["../outside", "skills/../outside"])
def test_manifest_component_path_traversal_is_rejected(tmp_path, declared):
    plugin_root = tmp_path / "bad"
    (tmp_path / "outside").mkdir()
    _make_native(plugin_root, skills=[declared])

    with pytest.raises(PluginSecurityError, match="traversal"):
        load_plugin(plugin_root)


def test_absolute_component_outside_plugin_root_is_rejected(tmp_path):
    plugin_root = tmp_path / "bad"
    outside = tmp_path / "outside"
    outside.mkdir()
    _make_native(plugin_root, skills=[str(outside.resolve())])

    with pytest.raises(PluginSecurityError, match="escapes"):
        load_plugin(plugin_root)


def test_symlink_escape_is_rejected_when_platform_allows_symlinks(tmp_path):
    plugin_root = tmp_path / "bad-link"
    outside = tmp_path / "outside"
    outside.mkdir()
    _make_skill(outside)
    plugin_root.mkdir(exist_ok=True)
    try:
        (plugin_root / "linked-skills").symlink_to(outside / "skills", target_is_directory=True)
    except OSError:
        pytest.skip("Creating symlinks is not permitted on this Windows host")
    _make_native(plugin_root, skills=["linked-skills"])

    with pytest.raises(PluginSecurityError, match="symlink|escapes"):
        load_plugin(plugin_root)


def test_mcp_working_directory_cannot_escape_plugin_root(tmp_path):
    plugin_root = tmp_path / "bad-mcp"
    _make_native(
        plugin_root,
        mcp_servers={"servers": {"bad": {"command": "python", "cwd": ".."}}},
    )

    with pytest.raises(PluginSecurityError, match="traversal"):
        load_plugin(plugin_root)


def test_discovery_isolates_invalid_plugin_and_keeps_healthy_plugin(tmp_path):
    healthy = tmp_path / "healthy"
    _make_native(healthy)
    _make_skill(healthy)
    invalid = tmp_path / "invalid"
    _make_native(invalid, skills=["../escape"])

    report = discover_plugins([tmp_path])

    assert [plugin.plugin_id for plugin in report.plugins] == ["quality-tools"]
    assert len(report.errors) == 1
    assert "traversal" in report.errors[0]


def test_duplicate_namespaces_are_deterministic_and_reported(tmp_path):
    first = tmp_path / "a-first"
    second = tmp_path / "z-second"
    _make_native(first, name="Same Name")
    _make_skill(first)
    _make_native(second, name="same-name")
    _make_skill(second)

    report = discover_plugins([tmp_path])

    assert len(report.plugins) == 1
    assert report.plugins[0].root == first.resolve()
    assert any("Duplicate plugin namespace" in warning for warning in report.warnings)


def test_enable_state_persists_as_atomic_json_and_controls_loading(tmp_path):
    plugin_root = tmp_path / "plugin"
    _make_native(plugin_root)
    _make_skill(plugin_root)
    state_path = tmp_path / "config" / "plugins-state.json"
    manager = PluginManager([tmp_path], state_path)

    assert len(manager.load_enabled().plugins) == 1
    manager.disable("quality-tools")
    assert manager.load_enabled().plugins == ()
    assert PluginManager([tmp_path], state_path).is_enabled("quality-tools") is False
    stored = json.loads(state_path.read_text(encoding="utf-8"))
    assert stored["version"] == 1
    assert stored["plugins"]["quality-tools"]["enabled"] is False
    assert not list(state_path.parent.glob("*.tmp"))


def test_corrupt_enable_state_fails_closed_without_loading_plugins(tmp_path):
    plugin_root = tmp_path / "plugin"
    _make_native(plugin_root)
    _make_skill(plugin_root)
    state_path = tmp_path / "state.json"
    state_path.write_text("not json", encoding="utf-8")

    loaded = PluginManager([tmp_path], state_path).load_enabled()

    assert loaded.plugins == ()
    assert any("Cannot read plugin state" in error for error in loaded.errors)


def test_state_store_rejects_non_boolean_state(tmp_path):
    path = tmp_path / "state.json"
    _write_json(path, {"version": 1, "plugins": {"demo": {"enabled": "yes"}}})
    with pytest.raises(PluginStateError, match="boolean"):
        PluginStateStore(path).read()


def test_global_switch_prevents_all_discovery_and_resource_loading(tmp_path, monkeypatch):
    plugin_root = tmp_path / "plugin"
    _make_native(plugin_root)
    _make_skill(plugin_root)
    monkeypatch.setenv("PLUGINS_ENABLED", "off")

    loaded = PluginManager([tmp_path], tmp_path / "state.json").load_enabled()

    assert loaded.globally_enabled is False
    assert loaded.plugins == ()
    assert loaded.skill_directories == {}


def test_content_signature_detects_changes_and_reload_updates_baseline(tmp_path):
    plugin_root = tmp_path / "plugin"
    _make_native(plugin_root)
    skill = _make_skill(plugin_root)
    manager = PluginManager([tmp_path], tmp_path / "state.json")
    first = manager.load_enabled()
    first_signature = first.plugins[0].content_signature

    skill.write_text(skill.read_text(encoding="utf-8") + "Changed.\n", encoding="utf-8")
    changes = manager.detect_changes()
    assert changes.changed == ("quality-tools",)
    reloaded = manager.reload_changed()
    assert reloaded.changes.changed == ("quality-tools",)
    assert reloaded.loaded.plugins[0].content_signature != first_signature
    assert manager.has_changes() is False


def test_hot_reload_reports_enable_disable_as_remove_and_add(tmp_path):
    plugin_root = tmp_path / "plugin"
    _make_native(plugin_root)
    _make_skill(plugin_root)
    manager = PluginManager([tmp_path], tmp_path / "state.json")
    manager.load_enabled()

    manager.disable("quality-tools")
    assert manager.detect_changes().removed == ("quality-tools",)
    manager.reload_changed()
    manager.enable("quality-tools")
    assert manager.detect_changes().added == ("quality-tools",)


def test_inline_mcp_and_declared_permission_list_are_normalized(tmp_path):
    plugin_root = tmp_path / "inline"
    _make_native(
        plugin_root,
        mcp_servers={"one": {"command": "node", "args": ["server.js"]}},
        permissions=["shell", "network"],
    )

    plugin = load_plugin(plugin_root)

    assert plugin.permissions == {"shell": True, "network": True}
    assert set(plugin.mcp_servers) == {"quality-tools/one"}


def test_every_declared_hook_source_survives_same_filename_collision(tmp_path):
    plugin_root = tmp_path / "many-hooks"
    first = plugin_root / "hooks" / "pre" / "hooks.json"
    second = plugin_root / "hooks" / "post" / "hooks.json"
    _write_json(first, {"hooks": {}})
    _write_json(second, {"hooks": {}})
    _make_native(
        plugin_root,
        hooks=["./hooks/pre/hooks.json", "./hooks/post/hooks.json"],
    )

    loaded = PluginManager([tmp_path], tmp_path / "state.json").load_enabled()

    assert [item.path for item in loaded.hook_sources] == [first.resolve(), second.resolve()]
    assert [item.qualified_name for item in loaded.hook_sources] == [
        "quality-tools:hooks",
        "quality-tools:hooks-2",
    ]
    assert all(item.plugin_root == plugin_root.resolve() for item in loaded.hook_sources)


def test_hook_source_specs_connect_directly_to_hook_manager(tmp_path):
    from app.hooks import load_hook_sources

    plugin_root = tmp_path / "hook-plugin"
    _write_json(
        plugin_root / "hooks" / "hooks.json",
        {
            "version": 1,
            "hooks": {
                "PreToolUse": [
                    {"id": "guard", "matcher": "run_shell", "command": "check-command"}
                ]
            },
        },
    )
    _make_native(plugin_root, hooks="./hooks/hooks.json")
    plugins = PluginManager([tmp_path], tmp_path / "state.json").load_enabled()

    hooks = load_hook_sources(
        tmp_path,
        include_project=False,
        plugin_sources=plugins.hook_source_specs,
    )

    assert len(hooks.definitions) == 1
    assert hooks.definitions[0].plugin_id == "quality-tools"
    assert hooks.definitions[0].source_root == plugin_root.resolve()
    assert hooks.definitions[0].source_id == "quality-tools:hooks"
