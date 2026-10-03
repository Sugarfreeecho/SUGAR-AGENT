from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))


def test_plugin_legacy_user_dir_is_migrated_to_sugaragent(monkeypatch, tmp_path):
    import plugins.manager as plugin_manager

    monkeypatch.delenv("PLUGINS_DIRS", raising=False)
    monkeypatch.delenv("PLUGINS_DIR", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    if os.name == "nt":
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        target = tmp_path / "SugarAgent" / "plugins"
    else:
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
        target = tmp_path / "sugaragent" / "plugins"

    legacy = tmp_path / ".myagent" / "plugins"
    legacy.mkdir(parents=True)
    (legacy / "demo-plugin").mkdir()

    dirs = plugin_manager.default_discovery_dirs()

    assert target in dirs
    assert (target / "demo-plugin").is_dir()
    assert not legacy.exists()


def test_plugin_intermediate_home_plugins_dir_is_migrated(monkeypatch, tmp_path):
    import plugins.manager as plugin_manager

    monkeypatch.delenv("PLUGINS_DIRS", raising=False)
    monkeypatch.delenv("PLUGINS_DIR", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    if os.name == "nt":
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
        target = tmp_path / "local" / "SugarAgent" / "plugins"
    else:
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
        target = tmp_path / "state" / "sugaragent" / "plugins"

    legacy = tmp_path / ".sugaragent" / "plugins"
    legacy.mkdir(parents=True)
    (legacy / "demo-plugin").mkdir()

    dirs = plugin_manager.default_discovery_dirs()

    assert target in dirs
    assert (target / "demo-plugin").is_dir()
    assert not legacy.exists()


def test_plugin_legacy_state_file_is_migrated_to_sugaragent(tmp_path):
    from plugins.manager import _migrate_legacy_path

    legacy = tmp_path / ".myagent" / "plugins-state.json"
    legacy.parent.mkdir(parents=True)
    legacy.write_text('{"version": 1, "plugins": {}}', encoding="utf-8")

    new = tmp_path / ".sugaragent" / "plugins-state.json"
    result = _migrate_legacy_path(new, legacy)

    assert result == new
    assert new.is_file()
    assert not legacy.exists()


def test_remote_control_default_state_dir_uses_sugaragent(tmp_path, monkeypatch):
    from remote_control.config import RemoteControlConfig

    monkeypatch.delenv("MYAGENT_REMOTE_CONTROL_STATE_DIR", raising=False)
    legacy = tmp_path / ".myagent" / "remote-control"
    legacy.mkdir(parents=True)
    (legacy / "remote-control.sqlite3").write_text("db", encoding="utf-8")

    config = RemoteControlConfig.from_env(tmp_path)

    assert config.state_dir == tmp_path / ".sugaragent" / "remote-control"
    assert (config.state_dir / "remote-control.sqlite3").is_file()
    assert not legacy.exists()


def test_feishu_default_state_dir_uses_sugaragent(tmp_path, monkeypatch):
    from remote_control.transports.feishu.config import FeishuConfig

    monkeypatch.delenv("FEISHU_STATE_DIR", raising=False)
    legacy = tmp_path / ".myagent" / "feishu"
    legacy.mkdir(parents=True)
    (legacy / "feishu.sqlite3").write_text("db", encoding="utf-8")

    config = FeishuConfig.from_env(tmp_path)

    assert config.state_dir == tmp_path / ".sugaragent" / "feishu"
    assert (config.state_dir / "feishu.sqlite3").is_file()
    assert not legacy.exists()


def test_skill_state_file_is_migrated_to_sugaragent(monkeypatch, tmp_path):
    import agent_tools

    legacy = tmp_path / "skill_states.json"
    legacy.write_text(
        '{"version": 1, "skills": {"demo": {"enabled": false}}}',
        encoding="utf-8",
    )
    new = tmp_path / ".sugaragent" / "skill_states.json"

    monkeypatch.setattr(agent_tools, "SKILL_STATE_PATH", new)
    monkeypatch.setattr(agent_tools, "_DEFAULT_SKILL_STATE_PATH", new)
    monkeypatch.setattr(agent_tools, "_LEGACY_SKILL_STATE_PATH", legacy)

    assert agent_tools._load_skill_enabled_states() == {"demo": False}
    assert new.is_file()
    assert not legacy.exists()


def test_mcp_tools_state_file_is_migrated_to_sugaragent(monkeypatch, tmp_path):
    import agent_mcp

    legacy = tmp_path / "mcp_tools_state.json"
    legacy.write_text(
        '{"version": 1, "tools": {"mcp_demo_x": {"enabled": false}}}',
        encoding="utf-8",
    )
    new = tmp_path / ".sugaragent" / "mcp_tools_state.json"

    monkeypatch.setattr(agent_mcp, "_MCP_TOOLS_STATE_PATH", new)
    monkeypatch.setattr(agent_mcp, "_DEFAULT_MCP_TOOLS_STATE_PATH", new)
    monkeypatch.setattr(agent_mcp, "_LEGACY_MCP_TOOLS_STATE_PATH", legacy)
    monkeypatch.setattr(agent_mcp, "_disabled_mcp_tools_loaded", False)
    monkeypatch.setattr(agent_mcp, "_disabled_mcp_tools", set())

    assert agent_mcp._load_disabled_mcp_tools() == {"mcp_demo_x"}
    assert new.is_file()
    assert not legacy.exists()


def test_skill_migration_failure_keeps_disabled_states_on_read_and_write(monkeypatch, tmp_path):
    import agent_tools

    legacy = tmp_path / "skill_states.json"
    legacy.write_text('{"skills":{"demo":{"enabled":false}}}', encoding="utf-8")
    new = tmp_path / ".sugaragent" / "skill_states.json"
    monkeypatch.setattr(agent_tools, "SKILL_STATE_PATH", new)
    monkeypatch.setattr(agent_tools, "_DEFAULT_SKILL_STATE_PATH", new)
    monkeypatch.setattr(agent_tools, "_LEGACY_SKILL_STATE_PATH", legacy)

    def fail_move(*args):
        raise PermissionError("migration denied")

    monkeypatch.setattr(agent_tools.shutil, "move", fail_move)
    assert agent_tools._load_skill_enabled_states() == {"demo": False}
    assert legacy.is_file() and not new.exists()
    assert agent_tools.set_skill_enabled("other", False)
    assert agent_tools._load_skill_enabled_states() == {"demo": False, "other": False}


def test_skill_pending_migration_does_not_silently_ignore_unreadable_state(monkeypatch, tmp_path):
    import agent_tools

    legacy = tmp_path / "skill_states.json"
    legacy.write_text("invalid json", encoding="utf-8")
    new = tmp_path / ".sugaragent" / "skill_states.json"
    monkeypatch.setattr(agent_tools, "SKILL_STATE_PATH", new)
    monkeypatch.setattr(agent_tools, "_DEFAULT_SKILL_STATE_PATH", new)
    monkeypatch.setattr(agent_tools, "_LEGACY_SKILL_STATE_PATH", legacy)
    monkeypatch.setattr(agent_tools, "_migrate_legacy_state_path", lambda *args: None)
    with pytest.raises(ValueError):
        agent_tools._load_skill_enabled_states()
    assert not new.exists()


def test_default_state_paths_live_under_sugaragent():
    import agent_mcp
    import agent_tools

    assert agent_tools.SKILL_STATE_PATH == ROOT / ".sugaragent" / "skill_states.json"
    assert agent_mcp._MCP_TOOLS_STATE_PATH == ROOT / ".sugaragent" / "mcp_tools_state.json"
