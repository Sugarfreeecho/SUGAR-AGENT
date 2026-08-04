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
