import json
import shutil
import sys
import time
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


@pytest.fixture(autouse=True)
def _trust_extensions(monkeypatch):
    monkeypatch.setattr(
        "security.extensions.descriptor_is_trusted",
        lambda _descriptor: True,
    )


def _wait_until(predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.025)
    return bool(predicate())


def _make_python_service_plugin(root: Path, *, declared: bool = True) -> Path:
    plugin_root = root / "service-demo"
    manifest = {
        "schema_version": 1,
        "id": "background.demo",
        "name": "Background Demo",
        "version": "1.0.0",
        "runtime": {
            "type": "python",
            "entrypoint": "./plugin.py",
            "api_version": "1",
            "timeout_seconds": 5,
        },
    }
    if declared:
        manifest["capabilities"] = {"background_services": True}
    manifest_path = plugin_root / ".myagent-plugin" / "plugin.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    (plugin_root / "plugin.py").write_text(
        """
import json
from pathlib import Path
from myagent_plugin_sdk import Plugin, current_tool_context

plugin = Plugin()

@plugin.background_service(name="heartbeat", interval_seconds=0.05)
def heartbeat(context):
    data = Path(context["plugin_data_dir"])
    path = data / "heartbeat.json"
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        state = {"count": 0}
    state["count"] += 1
    path.write_text(json.dumps(state), encoding="utf-8")

@plugin.on_deactivate
def deactivate(context):
    Path(context["plugin_data_dir"], "deactivated.txt").write_text("yes", encoding="utf-8")
""".lstrip(),
        encoding="utf-8",
    )
    return plugin_root


def test_python_background_service_starts_reports_health_and_stops(tmp_path):
    from plugins import PluginRuntimeRegistry, load_plugin

    plugin = load_plugin(_make_python_service_plugin(tmp_path / "plugins"))
    storage_root = tmp_path / "storage"
    registry = PluginRuntimeRegistry(storage_root=storage_root)
    heartbeat = storage_root / "background.demo" / "data" / "heartbeat.json"
    deactivated = storage_root / "background.demo" / "data" / "deactivated.txt"

    statuses = registry.background_status([plugin])
    assert _wait_until(
        lambda: heartbeat.is_file()
        and json.loads(heartbeat.read_text(encoding="utf-8"))["count"] >= 2
    )
    statuses = registry.background_status([plugin])
    registry.close()
    count_after_close = json.loads(heartbeat.read_text(encoding="utf-8"))["count"]
    time.sleep(0.15)

    assert statuses[0]["plugin_id"] == "background.demo"
    assert statuses[0]["services"][0]["name"] == "heartbeat"
    assert statuses[0]["services"][0]["runs"] >= 1
    assert deactivated.read_text(encoding="utf-8") == "yes"
    assert json.loads(heartbeat.read_text(encoding="utf-8"))["count"] == count_after_close


def test_undeclared_background_service_never_starts(tmp_path):
    from plugins import PluginRuntimeRegistry, load_plugin

    plugin = load_plugin(
        _make_python_service_plugin(tmp_path / "plugins", declared=False)
    )
    storage_root = tmp_path / "storage"
    registry = PluginRuntimeRegistry(storage_root=storage_root)

    assert registry.tool_definitions([plugin]) == []
    time.sleep(0.1)
    errors = registry.errors
    registry.close()

    assert any("without declaring" in error for error in errors)
    assert not (
        storage_root / "background.demo" / "data" / "heartbeat.json"
    ).exists()


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is not installed")
def test_node_background_service_uses_same_lifecycle(tmp_path):
    from plugins import PluginRuntimeRegistry, load_plugin

    root = tmp_path / "node-service"
    manifest_path = root / ".myagent-plugin" / "plugin.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "id": "background.node",
                "name": "Background Node",
                "version": "1.0.0",
                "runtime": {
                    "type": "node",
                    "entrypoint": "./plugin.cjs",
                    "api_version": "1",
                    "timeout_seconds": 5,
                },
                "capabilities": {"background_services": True},
            }
        ),
        encoding="utf-8",
    )
    (root / "plugin.cjs").write_text(
        """
exports.setup = (plugin) => {
  plugin.registerBackgroundService(
    { name: "heartbeat", intervalSeconds: 0.05 },
    async () => {}
  );
};
""".lstrip(),
        encoding="utf-8",
    )
    plugin = load_plugin(root)
    registry = PluginRuntimeRegistry(storage_root=tmp_path / "storage")

    registry.background_status([plugin])
    assert _wait_until(
        lambda: registry.background_status([plugin])[0]["services"][0]["runs"] >= 1
    )
    status = registry.background_status([plugin])[0]["services"][0]
    registry.close()

    assert status["name"] == "heartbeat"
    assert status["runs"] >= 1
