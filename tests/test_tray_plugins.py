import json
import sys
from pathlib import Path

from app.tray_plugins import (
    MAX_TRAY_ACTIONS,
    TrayGroup,
    discover_tray_actions,
    discover_tray_menu,
)
from app.tray_slot import parse_tray_rows


def _project(tmp_path: Path, *, plugin_id: str = "demo", tier: str = "extension",
             enabled=None, command=None, extra_plugins: int = 0) -> Path:
    """Build a throwaway project with one manifest-driven plugin."""

    app_dir = tmp_path / "app"
    (app_dir / "plugins").mkdir(parents=True)
    (app_dir / "plugins" / "tiers.json").write_text(
        json.dumps({"tiers": {tier: [plugin_id]}}), encoding="utf-8"
    )
    config_dir = tmp_path / ".config"
    config_dir.mkdir()
    if enabled is not None:
        (config_dir / "plugins-state.json").write_text(
            json.dumps({"plugins": {plugin_id: {"enabled": enabled}}}), encoding="utf-8"
        )

    def write_plugin(ident: str) -> None:
        root = tmp_path / "plugins" / ident
        (root / ".myagent-plugin").mkdir(parents=True)
        (root / "scripts").mkdir()
        (root / "scripts" / "run.ps1").write_text("# stub", encoding="utf-8")
        manifest = {
            "schema_version": 1,
            "id": ident,
            "name": f"Plugin {ident}",
            "version": "1.0.0",
            "capabilities": {
                "ui": {
                    "tray": [
                        {
                            "id": "main",
                            "label": f"Action {ident}",
                            "command": command or ["{python}", "scripts/run.ps1"],
                        }
                    ]
                }
            },
        }
        (root / ".myagent-plugin" / "plugin.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )

    write_plugin(plugin_id)
    for index in range(extra_plugins):
        write_plugin(f"extra{index}")
    return tmp_path


def test_expands_placeholders_and_contains_paths(tmp_path):
    project = _project(tmp_path)
    actions = discover_tray_actions(project, python_exe=sys.executable)

    assert len(actions) == 1
    action = actions[0]
    assert action.plugin_id == "demo"
    assert action.item_id == "main"
    assert action.label == "Action demo"
    assert action.argv[0] == sys.executable
    assert action.argv[1] == str((project / "plugins" / "demo" / "scripts" / "run.ps1").resolve())
    assert action.cwd == project / "plugins" / "demo"
    assert action.windowless is True


def test_standalone_plugin_stays_hidden_until_enabled(tmp_path):
    project = _project(tmp_path, tier="standalone")
    assert discover_tray_actions(project, python_exe=sys.executable) == []

    second = _project(tmp_path / "enabled", tier="standalone", enabled=True)
    assert len(discover_tray_actions(second, python_exe=sys.executable)) == 1


def test_state_disables_an_extension_plugin(tmp_path):
    project = _project(tmp_path, enabled=False)
    assert discover_tray_actions(project, python_exe=sys.executable) == []


def test_env_override_wins(tmp_path, monkeypatch):
    project = _project(tmp_path)
    monkeypatch.setenv("PLUGIN_DEMO_ENABLED", "0")
    assert discover_tray_actions(project, python_exe=sys.executable) == []
    monkeypatch.setenv("PLUGIN_DEMO_ENABLED", "1")
    assert len(discover_tray_actions(project, python_exe=sys.executable)) == 1


def test_rejects_path_that_escapes_the_plugin(tmp_path):
    project = _project(tmp_path, command=["{python}", "../evil.ps1"])
    assert discover_tray_actions(project, python_exe=sys.executable) == []


def test_skips_entry_when_interpreter_is_missing(tmp_path):
    project = _project(tmp_path)
    missing = str(tmp_path / "nope" / "python.exe")
    assert discover_tray_actions(project, python_exe=missing) == []


def test_action_count_is_capped(tmp_path):
    project = _project(tmp_path, extra_plugins=MAX_TRAY_ACTIONS + 3)
    assert len(discover_tray_actions(project, python_exe=sys.executable)) == MAX_TRAY_ACTIONS


def test_broken_manifest_does_not_raise(tmp_path):
    project = _project(tmp_path)
    (project / "plugins" / "demo" / ".myagent-plugin" / "plugin.json").write_text(
        "{not json", encoding="utf-8"
    )
    assert discover_tray_actions(project, python_exe=sys.executable) == []


def _group_plugin(tmp_path: Path, state_dir: Path, mode: str = "shield") -> Path:
    project = _project(tmp_path)
    manifest_path = project / "plugins" / "demo" / ".myagent-plugin" / "plugin.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["capabilities"]["ui"]["tray"] = [
        {
            "id": "power",
            "label": "Power",
            "items": [
                {
                    "id": "shield",
                    "label": "Shield",
                    "command": ["{python}", "scripts/run.ps1"],
                    "check": {"file": "{state}/mode.json", "key": "mode", "equals": "shield"},
                },
                {
                    "id": "awake",
                    "label": "Awake",
                    "command": ["{python}", "scripts/run.ps1"],
                    "check": {"file": "{state}/mode.json", "key": "mode", "equals": "awake"},
                },
            ],
        }
    ]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "mode.json").write_text(json.dumps({"mode": mode}), encoding="utf-8")
    return project


def test_group_becomes_submenu_with_checked_children(tmp_path):
    state_dir = tmp_path / "state"
    project = _group_plugin(tmp_path / "project", state_dir, mode="awake")
    entries = discover_tray_menu(
        project, python_exe=sys.executable, state_dir=state_dir
    )

    assert len(entries) == 1
    group = entries[0]
    assert isinstance(group, TrayGroup)
    assert group.label == "Power"
    assert [child.item_id for child in group.children] == ["shield", "awake"]
    assert [child.checked for child in group.children] == [False, True]


def test_checked_is_false_when_state_file_is_missing(tmp_path):
    state_dir = tmp_path / "state"
    project = _group_plugin(tmp_path / "project", state_dir, mode="shield")
    (state_dir / "mode.json").unlink()
    entries = discover_tray_menu(project, python_exe=sys.executable, state_dir=state_dir)
    assert [child.checked for child in entries[0].children] == [False, False]


def test_parser_reports_actionable_warnings():
    rows, warnings = parse_tray_rows(
        [
            {"id": "bad id", "label": "Bad", "command": ["{python}"]},
            {"id": "ok", "label": "Ok", "command": []},
            {"id": "group", "label": "Group", "items": [{"id": "x", "label": "X", "items": []}]},
        ]
    )
    assert rows == []
    assert any("id is invalid" in warning for warning in warnings)
    assert any("command must be" in warning for warning in warnings)
    assert any("nested tray groups" in warning for warning in warnings)


def test_parser_normalises_check_spec():
    rows, warnings = parse_tray_rows(
        [{
            "id": "shield",
            "label": "Shield",
            "command": ["{python}", "run.py"],
            "check": {"file": "{state}/x.json", "key": "mode", "equals": "shield"},
        }]
    )
    assert warnings == []
    assert rows[0]["check"] == {
        "file": "{state}/x.json",
        "key": "mode",
        "equals": "shield",
    }


def test_loader_surfaces_tray_warnings_and_ui_exposes_slot(tmp_path):
    from app.plugins import load_plugin, plugin_ui_contributions

    project = _group_plugin(tmp_path / "project", tmp_path / "state")
    plugin = load_plugin(project / "plugins" / "demo")
    contributions = plugin_ui_contributions(plugin)
    tray_slots = [row for row in contributions if row["slot"] == "tray"]
    assert tray_slots and tray_slots[0]["kind"] == "group"
    assert [item["label"] for item in tray_slots[0]["items"]] == ["Shield", "Awake"]
    assert plugin.compatibility.warnings == ()

    manifest_path = project / "plugins" / "demo" / ".myagent-plugin" / "plugin.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["capabilities"]["ui"]["tray"] = [{"id": "broken", "label": "Broken", "command": "nope"}]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    broken = load_plugin(project / "plugins" / "demo")
    assert any("command must be" in warning for warning in broken.compatibility.warnings)
