import json
from pathlib import Path

from app.plugin_availability import diagnosis_prompt, plugin_availability
from app.plugins import PluginManager


def _plugin(root: Path, **extra) -> Path:
    manifest = {
        "schema_version": 1,
        "id": "check-demo",
        "name": "Check Demo",
        "version": "1.0.0",
        "description": "Availability demo",
        **extra,
    }
    path = root / ".myagent-plugin" / "plugin.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    return root


def _manager(tmp_path: Path) -> PluginManager:
    return PluginManager([tmp_path], tmp_path / "state.json")


def test_ready_when_every_static_check_passes(tmp_path):
    root = _plugin(tmp_path / "demo")
    (root / "web").mkdir()
    (root / "web" / "index.html").write_text("<html></html>", encoding="utf-8")
    manifest = json.loads((root / ".myagent-plugin" / "plugin.json").read_text(encoding="utf-8"))
    manifest["capabilities"] = {"web": {"entry": "web/index.html"}}
    (root / ".myagent-plugin" / "plugin.json").write_text(json.dumps(manifest), encoding="utf-8")

    plugin = _manager(tmp_path).discover()[0]
    report = plugin_availability(plugin, manager=_manager(tmp_path))

    assert report["state"] == "ready"
    assert report["enabled"] is True
    assert all(item["ok"] for item in report["checks"])


def test_disabled_plugin_is_unavailable(tmp_path):
    _plugin(tmp_path / "demo")
    manager = _manager(tmp_path)
    plugin = manager.discover()[0]
    manager.disable("check-demo")

    report = plugin_availability(plugin, manager=manager)

    assert report["state"] == "unavailable"
    assert report["enabled"] is False
    assert any(item["id"] == "enabled" and item["fatal"] for item in report["checks"])


def test_missing_requirement_degrades_without_blocking(tmp_path):
    root = _plugin(tmp_path / "demo")
    (root / "requirements.txt").write_text(
        "definitely-missing-dist-xyz>=1.0\n# comment\n", encoding="utf-8"
    )

    plugin = _manager(tmp_path).discover()[0]
    report = plugin_availability(plugin, manager=_manager(tmp_path))

    assert report["state"] == "degraded"
    dependency = next(item for item in report["checks"] if item["id"] == "dependencies")
    assert dependency["ok"] is False
    assert "definitely-missing-dist-xyz" in dependency["detail"]


def test_missing_web_entry_degrades(tmp_path):
    root = _plugin(tmp_path / "demo")
    manifest = json.loads((root / ".myagent-plugin" / "plugin.json").read_text(encoding="utf-8"))
    manifest["capabilities"] = {"web": {"entry": "web/index.html"}}
    (root / ".myagent-plugin" / "plugin.json").write_text(json.dumps(manifest), encoding="utf-8")

    plugin = _manager(tmp_path).discover()[0]
    report = plugin_availability(plugin, manager=_manager(tmp_path))

    assert report["state"] == "degraded"
    web = next(item for item in report["checks"] if item["id"] == "web")
    assert web["ok"] is False


def test_diagnosis_prompt_carries_report_and_guardrails(tmp_path):
    _plugin(tmp_path / "demo")
    plugin = _manager(tmp_path).discover()[0]
    report = plugin_availability(plugin, manager=_manager(tmp_path))

    prompt = diagnosis_prompt(plugin, report)

    assert "check-demo" in prompt
    assert "自动检查结果" in prompt
    assert "不要修改插件源码" in prompt
