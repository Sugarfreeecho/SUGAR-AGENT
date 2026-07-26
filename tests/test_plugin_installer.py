import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _plugin_source(
    root: Path,
    *,
    plugin_id: str = "demo.install",
    version: str = "1.0.0",
    dependencies: dict | None = None,
) -> Path:
    manifest = {
        "schema_version": 1,
        "id": plugin_id,
        "name": "Installer Demo",
        "version": version,
        "runtime": {"type": "python", "entrypoint": "./plugin.py"},
    }
    if dependencies is not None:
        manifest["dependencies"] = dependencies
    _write_json(root / ".myagent-plugin" / "plugin.json", manifest)
    (root / "plugin.py").write_text(
        "from myagent_plugin_sdk import Plugin\nplugin = Plugin()\n",
        encoding="utf-8",
    )
    return root


def test_local_install_update_and_recoverable_uninstall(tmp_path):
    from plugins import PluginInstaller, discover_plugins

    discovery = tmp_path / "installed"
    source_v1 = _plugin_source(tmp_path / "source-v1")
    installer = PluginInstaller([discovery])

    installed = installer.install(source_v1)
    assert installed["action"] == "installed"
    assert installed["plugin"]["version"] == "1.0.0"
    assert (discovery / "demo.install" / "plugin.py").is_file()

    source_v2 = _plugin_source(tmp_path / "source-v2", version="2.0.0")
    updated = installer.install(source_v2, replace=True)
    assert updated["action"] == "updated"
    assert updated["previous_version"] == "1.0.0"
    assert updated["plugin"]["version"] == "2.0.0"
    assert Path(updated["backup_path"]).is_dir()

    removed = installer.uninstall("demo.install")
    assert removed["recoverable"] is True
    assert Path(removed["trash_path"]).is_dir()
    assert discover_plugins([discovery]).plugins == ()


def test_archive_install_finds_nested_plugin_root(tmp_path):
    from plugins import PluginInstaller

    source = _plugin_source(tmp_path / "package" / "nested")
    archive_base = tmp_path / "plugin-archive"
    archive = Path(
        shutil.make_archive(
            str(archive_base),
            "zip",
            root_dir=str(source.parent),
            base_dir=source.name,
        )
    )
    discovery = tmp_path / "installed"

    result = PluginInstaller([discovery]).install(archive)
    assert result["plugin"]["id"] == "demo.install"
    assert (discovery / "demo.install" / ".myagent-plugin" / "plugin.json").is_file()


def test_remote_git_source_uses_clone_runner(tmp_path, monkeypatch):
    from plugins import PluginInstaller

    template = _plugin_source(tmp_path / "template")
    calls = []

    def runner(command, cwd, timeout):
        command = list(command)
        calls.append(command)
        if "clone" in command:
            checkout = Path(command[-1])
            shutil.copytree(template, checkout)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(shutil, "which", lambda name: f"/mock/{name}")
    result = PluginInstaller([tmp_path / "installed"], runner=runner).install(
        "https://example.invalid/demo.git",
        ref="feature/plugin-v2",
    )

    assert result["action"] == "installed"
    assert any("clone" in command for command in calls)
    assert any(
        "fetch" in command and command[-1] == "feature/plugin-v2"
        for command in calls
    )
    assert any(
        "checkout" in command and command[-1] == "FETCH_HEAD"
        for command in calls
    )


def test_python_dependencies_use_plugin_local_venv_and_do_not_change_signature(tmp_path):
    from plugins import PluginInstaller, load_plugin

    source = _plugin_source(
        tmp_path / "source",
        dependencies={
            "python": {
                "requirements": "requirements.txt",
                "packages": ["demo-extra>=1"],
            }
        },
    )
    (source / "requirements.txt").write_text("demo-core>=1\n", encoding="utf-8")
    calls = []

    def runner(command, cwd, timeout):
        command = list(command)
        calls.append(command)
        if command[1:3] == ["-m", "venv"]:
            venv_root = Path(command[3])
            python_path = (
                venv_root / "Scripts" / "python.exe"
                if sys.platform == "win32"
                else venv_root / "bin" / "python"
            )
            python_path.parent.mkdir(parents=True, exist_ok=True)
            python_path.write_text("", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "", "")

    discovery = tmp_path / "installed"
    installer = PluginInstaller([discovery], runner=runner)
    installer.install(source)
    before = load_plugin(discovery / "demo.install").content_signature
    result = installer.install_dependencies("demo.install")
    after = load_plugin(discovery / "demo.install").content_signature

    assert [item["type"] for item in result["operations"]] == [
        "python_requirements",
        "python_packages",
    ]
    assert any(command[1:3] == ["-m", "venv"] for command in calls)
    assert any("-r" in command for command in calls)
    assert any("demo-extra>=1" in command for command in calls)
    assert before == after


def test_python_dependencies_can_disable_conventional_requirements(tmp_path):
    from plugins import PluginInstaller

    source = _plugin_source(
        tmp_path / "source",
        dependencies={"python": False},
    )
    (source / "requirements.txt").write_text("should-not-install\n", encoding="utf-8")
    calls = []

    def runner(command, cwd, timeout):
        calls.append(list(command))
        return subprocess.CompletedProcess(command, 0, "", "")

    installer = PluginInstaller([tmp_path / "installed"], runner=runner)
    installer.install(source)
    result = installer.install_dependencies("demo.install")

    assert result["operations"] == []
    assert calls == []


def test_unsatisfied_plugin_dependency_blocks_install(tmp_path):
    from plugins import PluginInstallError, PluginInstaller

    source = _plugin_source(
        tmp_path / "source",
        dependencies={"plugins": {"required.plugin": ">=1.0"}},
    )

    with pytest.raises(PluginInstallError, match="required.plugin"):
        PluginInstaller([tmp_path / "installed"]).install(source)


def test_webui_exposes_plugin_lifecycle_routes():
    source = (APP_DIR / "webui.py").read_text(encoding="utf-8")
    template = (APP_DIR / "templates" / "extensions_config.html").read_text(
        encoding="utf-8"
    )

    assert '@fastapi_app.post("/api/plugins/install")' in source
    assert '@fastapi_app.delete("/api/plugins/{plugin_id}")' in source
    assert '@fastapi_app.post("/api/plugins/{plugin_id}/dependencies")' in source
    assert 'id="install-source"' in template
    assert "install_dependencies" in template
    assert "class=\"deps\"" in template
    assert "class=\"remove danger\"" in template
