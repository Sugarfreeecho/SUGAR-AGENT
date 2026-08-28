import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


def _make_context_plugin(
    discovery: Path,
    source: str,
    *,
    permissions: dict | None = None,
) -> Path:
    root = discovery / "demo-runtime"
    manifest = {
        "schema_version": 1,
        "id": "demo.runtime",
        "name": "Runtime Demo",
        "version": "1.0.0",
        "runtime": {
            "type": "python",
            "entrypoint": "./plugin.py",
            "api_version": "1",
            "timeout_seconds": 5,
        },
        **({"permissions": permissions} if permissions is not None else {}),
    }
    manifest_path = root / ".myagent-plugin" / "plugin.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    (root / "plugin.py").write_text(source, encoding="utf-8")
    return root


def test_plugin_storage_layout_allocates_isolated_host_directories(tmp_path):
    from plugins.storage import plugin_storage_layout

    layout = plugin_storage_layout("Demo.Plugin", storage_root=tmp_path / "host")

    assert layout.plugin_id == "demo.plugin"
    assert layout.root == (tmp_path / "host" / "demo.plugin").resolve()
    assert layout.data_dir == layout.root / "data"
    assert layout.cache_dir == layout.root / "cache"
    assert layout.temp_dir == layout.root / "temp"
    assert all(path.is_dir() for path in (layout.data_dir, layout.cache_dir, layout.temp_dir))


def test_plugin_storage_layout_rejects_plugin_root_symlink_escape(tmp_path):
    from plugins.security import PluginSecurityError
    from plugins.storage import plugin_storage_layout

    storage_root = tmp_path / "host"
    outside = tmp_path / "outside"
    storage_root.mkdir()
    outside.mkdir()
    link = storage_root / "demo.plugin"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory symlinks are unavailable: {exc}")

    with pytest.raises(PluginSecurityError, match="escapes the configured root"):
        plugin_storage_layout("demo.plugin", storage_root=storage_root)


def test_runtime_rejects_internal_state_symlink_escape(tmp_path):
    from plugins import PluginRuntimeError, PluginRuntimeRegistry

    storage_root = tmp_path / "host"
    outside = tmp_path / "outside"
    storage_root.mkdir()
    outside.mkdir()
    link = storage_root / ".runtime"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory symlinks are unavailable: {exc}")

    with pytest.raises(PluginRuntimeError, match="escapes"):
        PluginRuntimeRegistry(storage_root=storage_root)


def test_runtime_context_is_host_owned_and_manifest_scoped(tmp_path):
    from plugins import PluginRuntimeRegistry, load_plugin

    source = """
from dataclasses import asdict
from myagent_plugin_sdk import Plugin, current_tool_context

plugin = Plugin()

@plugin.tool(name="context", input_schema={"type": "object", "additionalProperties": True})
def context(**arguments):
    return {"arguments": arguments, "context": asdict(current_tool_context())}
""".lstrip()

    plugin = load_plugin(
        _make_context_plugin(
            tmp_path / "plugins",
            source,
            permissions={"context": ["session_id", "run_id", "cancellation_id"]},
        )
    )
    storage_root = tmp_path / "runtime"
    registry = PluginRuntimeRegistry(
        storage_root=storage_root,
        workspace_root=tmp_path / "workspace",
    )
    name = registry.tool_definitions([plugin])[0]["function"]["name"]

    result = registry.invoke(
        name,
        {"plugin_id": "model-spoof", "plugin_data_dir": "model-spoof"},
        [plugin],
        context={
            "session_id": "trusted-session",
            "run_id": "trusted-run",
            "cancellation_id": "trusted-call",
            "plugin_id": "host-spoof",
            "plugin_data_dir": str(tmp_path / "outside"),
            "workspace_root": str(tmp_path / "not-declared"),
        },
    )
    registry.close()

    context = result["context"]
    assert result["arguments"] == {
        "plugin_id": "model-spoof",
        "plugin_data_dir": "model-spoof",
    }
    assert context["plugin_id"] == "demo.runtime"
    assert Path(context["plugin_data_dir"]) == storage_root.resolve() / "demo.runtime" / "data"
    assert Path(context["plugin_cache_dir"]) == storage_root.resolve() / "demo.runtime" / "cache"
    assert Path(context["plugin_temp_dir"]) == storage_root.resolve() / "demo.runtime" / "temp"
    assert context["session_id"] == "trusted-session"
    assert context["run_id"] == "trusted-run"
    assert context["cancellation_id"] == "trusted-call"
    assert context["workspace_root"] == ""


def test_runtime_withholds_undeclared_optional_context(tmp_path):
    from plugins import PluginRuntimeRegistry, load_plugin

    source = """
from dataclasses import asdict
from myagent_plugin_sdk import Plugin, current_tool_context

plugin = Plugin()

@plugin.tool(name="context")
def context():
    return asdict(current_tool_context())
""".lstrip()

    plugin = load_plugin(_make_context_plugin(tmp_path / "plugins", source))
    registry = PluginRuntimeRegistry(
        storage_root=tmp_path / "runtime",
        workspace_root=tmp_path / "workspace",
    )
    name = registry.tool_definitions([plugin])[0]["function"]["name"]
    result = registry.invoke(
        name,
        {},
        [plugin],
        context={
            "session_id": "secret-session",
            "run_id": "secret-run",
            "workspace_root": str(tmp_path / "workspace"),
            "cancellation_id": "secret-call",
        },
    )
    registry.close()

    assert result["plugin_id"] == "demo.runtime"
    assert result["plugin_data_dir"]
    assert result["session_id"] == ""
    assert result["run_id"] == ""
    assert result["workspace_root"] == ""
    assert result["cancellation_id"] == ""


def test_new_worker_lifecycle_clears_only_plugin_temp_directory(tmp_path):
    from plugins import PluginRuntimeRegistry, load_plugin

    source = """
from pathlib import Path
from myagent_plugin_sdk import Plugin, current_tool_context

plugin = Plugin()

@plugin.tool(name="write_runtime_files")
def write_runtime_files():
    context = current_tool_context()
    for raw, value in (
        (context.plugin_data_dir, "data"),
        (context.plugin_cache_dir, "cache"),
        (context.plugin_temp_dir, "temp"),
    ):
        Path(raw, "marker.txt").write_text(value, encoding="utf-8")
    return True
""".lstrip()

    plugin = load_plugin(_make_context_plugin(tmp_path / "plugins", source))
    storage_root = tmp_path / "runtime"
    first = PluginRuntimeRegistry(storage_root=storage_root)
    name = first.tool_definitions([plugin])[0]["function"]["name"]
    assert first.invoke(name, {}, [plugin]) is True
    first.close()

    plugin_root = storage_root.resolve() / "demo.runtime"
    assert (plugin_root / "data" / "marker.txt").is_file()
    assert (plugin_root / "cache" / "marker.txt").is_file()
    assert (plugin_root / "temp" / "marker.txt").is_file()

    second = PluginRuntimeRegistry(storage_root=storage_root)
    second.tool_definitions([plugin])
    second.close()

    assert (plugin_root / "data" / "marker.txt").is_file()
    assert (plugin_root / "cache" / "marker.txt").is_file()
    assert not (plugin_root / "temp" / "marker.txt").exists()
