import asyncio
import json
import shutil
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _make_python_plugin(
    discovery: Path,
    *,
    plugin_id: str = "demo.runtime",
    source: str | None = None,
) -> Path:
    root = discovery / plugin_id.replace(".", "-")
    _write_json(
        root / ".myagent-plugin" / "plugin.json",
        {
            "schema_version": 1,
            "id": plugin_id,
            "name": "Runtime Demo",
            "version": "1.0.0",
            "runtime": {
                "type": "python",
                "entrypoint": "./plugin.py",
                "api_version": "1",
                "timeout_seconds": 5,
            },
        },
    )
    (root / "plugin.py").write_text(
        source
        or """
from myagent_plugin_sdk import Plugin

plugin = Plugin()

@plugin.tool(
    name="greet",
    description="Return a structured greeting.",
    input_schema={
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
        "additionalProperties": False,
    },
)
def greet(name):
    return {"message": f"hello {name}", "source": "plugin"}
""".lstrip(),
        encoding="utf-8",
    )
    return root


def test_native_manifest_v1_accepts_python_runtime(tmp_path):
    from plugins import load_plugin

    root = _make_python_plugin(tmp_path)
    plugin = load_plugin(root)

    assert plugin.runtime is not None
    assert plugin.runtime.runtime_type == "python"
    assert plugin.runtime.api_version == "1"
    assert plugin.runtime.entrypoint == (root / "plugin.py").resolve()
    assert plugin.compatibility.status == "native"
    assert "runtime" in plugin.compatibility.supported_components
    assert plugin.to_dict()["components"]["runtime"]["type"] == "python"


def test_python_worker_describes_and_invokes_registered_tool(tmp_path):
    from plugins import PluginRuntimeRegistry, load_plugin

    plugin = load_plugin(_make_python_plugin(tmp_path))
    registry = PluginRuntimeRegistry()

    definitions = registry.tool_definitions([plugin])
    assert len(definitions) == 1
    function = definitions[0]["function"]
    assert function["name"] == "plugin_demo_runtime__greet"
    assert function["description"] == "Return a structured greeting."
    assert function["parameters"]["required"] == ["name"]

    result = registry.invoke(function["name"], {"name": "Ada"}, [plugin])
    assert result == {"message": "hello Ada", "source": "plugin"}
    assert registry.errors == ()
    assert not (plugin.root / "__pycache__").exists()


def test_setup_function_and_async_handler_are_supported(tmp_path):
    from plugins import PluginRuntimeRegistry, load_plugin

    source = """
def setup(plugin):
    @plugin.tool(
        name="double",
        input_schema={
            "type": "object",
            "properties": {"value": {"type": "integer"}},
            "required": ["value"],
        },
    )
    async def double(value):
        return value * 2
""".lstrip()
    plugin = load_plugin(_make_python_plugin(tmp_path, source=source))
    registry = PluginRuntimeRegistry()
    definitions = registry.tool_definitions([plugin])

    result = registry.invoke(
        definitions[0]["function"]["name"],
        {"value": 21},
        [plugin],
    )
    assert result == 42


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is not installed")
def test_node_worker_describes_and_invokes_registered_tool(tmp_path):
    from plugins import PluginRuntimeRegistry, load_plugin

    root = tmp_path / "node-runtime"
    _write_json(
        root / ".myagent-plugin" / "plugin.json",
        {
            "schema_version": 1,
            "id": "demo.node",
            "name": "Node Runtime Demo",
            "version": "1.0.0",
            "runtime": {
                "type": "node",
                "entrypoint": "./plugin.cjs",
                "api_version": "1",
                "timeout_seconds": 5,
            },
        },
    )
    (root / "plugin.cjs").write_text(
        """
exports.setup = (plugin) => {
  plugin.registerTool(
    {
      name: "sum",
      description: "Add two numbers.",
      inputSchema: {
        type: "object",
        properties: {
          left: { type: "number" },
          right: { type: "number" }
        },
        required: ["left", "right"],
        additionalProperties: false
      }
    },
    async ({ left, right }) => ({ total: left + right })
  );
};
""".lstrip(),
        encoding="utf-8",
    )
    plugin = load_plugin(root)
    registry = PluginRuntimeRegistry()

    definitions = registry.tool_definitions([plugin])
    assert definitions[0]["function"]["name"] == "plugin_demo_node__sum"
    result = registry.invoke(
        definitions[0]["function"]["name"],
        {"left": 19, "right": 23},
        [plugin],
    )
    assert result == {"total": 42}


def test_broken_runtime_is_isolated_from_healthy_plugins(tmp_path):
    from plugins import PluginRuntimeRegistry, load_plugin

    good = load_plugin(_make_python_plugin(tmp_path, plugin_id="good.runtime"))
    broken = load_plugin(
        _make_python_plugin(
            tmp_path,
            plugin_id="broken.runtime",
            source="raise RuntimeError('broken on import')\n",
        )
    )
    registry = PluginRuntimeRegistry()

    definitions = registry.tool_definitions([broken, good])
    assert [item["function"]["name"] for item in definitions] == [
        "plugin_good_runtime__greet"
    ]
    assert len(registry.errors) == 1
    assert "broken on import" in registry.errors[0]


def test_runtime_registry_reloads_changed_plugin_signature(tmp_path):
    from plugins import PluginRuntimeRegistry, load_plugin

    root = _make_python_plugin(tmp_path)
    first = load_plugin(root)
    registry = PluginRuntimeRegistry()
    name = registry.tool_definitions([first])[0]["function"]["name"]
    assert registry.invoke(name, {"name": "Ada"}, [first])["message"] == "hello Ada"

    source_path = root / "plugin.py"
    source_path.write_text(
        source_path.read_text(encoding="utf-8").replace("hello {name}", "welcome {name}"),
        encoding="utf-8",
    )
    changed = load_plugin(root)
    assert changed.content_signature != first.content_signature
    assert registry.invoke(name, {"name": "Ada"}, [changed])["message"] == "welcome Ada"


def test_worker_is_persistent_and_activation_state_is_retained(tmp_path):
    from plugins import PluginRuntimeRegistry, load_plugin

    source = """
from myagent_plugin_sdk import Plugin

plugin = Plugin()
state = {"active": False, "calls": 0}

@plugin.on_activate
def activate(context):
    state["active"] = True

@plugin.tool(name="next_value")
def next_value():
    state["calls"] += 1
    return {"active": state["active"], "calls": state["calls"]}
""".lstrip()
    plugin = load_plugin(_make_python_plugin(tmp_path, source=source))
    registry = PluginRuntimeRegistry()
    name = registry.tool_definitions([plugin])[0]["function"]["name"]
    first_snapshot = registry.snapshot()

    assert registry.invoke(name, {}, [plugin]) == {"active": True, "calls": 1}
    assert registry.invoke(name, {}, [plugin]) == {"active": True, "calls": 2}
    second_snapshot = registry.snapshot()
    assert first_snapshot["workers"][0]["pid"] == second_snapshot["workers"][0]["pid"]
    assert second_snapshot["workers"][0]["running"] is True
    registry.close()
    assert registry.snapshot()["workers"] == []


def test_timed_out_worker_restarts_cleanly_for_next_call(tmp_path):
    from plugins import PluginRuntimeError, PluginRuntimeRegistry, load_plugin

    source = """
from myagent_plugin_sdk import Plugin
import time

plugin = Plugin()

@plugin.tool(
    name="maybe_slow",
    input_schema={
        "type": "object",
        "properties": {"slow": {"type": "boolean"}},
        "required": ["slow"],
    },
)
def maybe_slow(slow):
    if slow:
        time.sleep(2)
    return "ready"
""".lstrip()
    root = _make_python_plugin(tmp_path, source=source)
    manifest_path = root / ".myagent-plugin" / "plugin.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["runtime"]["timeout_seconds"] = 1
    _write_json(manifest_path, manifest)
    plugin = load_plugin(root)
    registry = PluginRuntimeRegistry()
    name = registry.tool_definitions([plugin])[0]["function"]["name"]

    with pytest.raises(PluginRuntimeError, match="timed out"):
        registry.invoke(name, {"slow": True}, [plugin])
    assert registry.invoke(name, {"slow": False}, [plugin]) == "ready"


def test_disabling_runtime_removes_previous_tool_binding(tmp_path):
    from plugins import PluginRuntimeError, PluginRuntimeRegistry, load_plugin

    plugin = load_plugin(_make_python_plugin(tmp_path))
    registry = PluginRuntimeRegistry()
    name = registry.tool_definitions([plugin])[0]["function"]["name"]

    assert registry.tool_definitions([]) == []
    with pytest.raises(PluginRuntimeError, match="Unknown or disabled"):
        registry.invoke(name, {"name": "Ada"}, [])


def test_agent_extensions_exposes_runtime_tools(tmp_path, monkeypatch):
    import agent_extensions
    from plugins import PluginManager

    discovery = tmp_path / "plugins"
    _make_python_plugin(discovery)
    manager = PluginManager([discovery], tmp_path / "plugin-state.json")
    monkeypatch.setattr(agent_extensions, "plugin_manager", lambda: manager)
    monkeypatch.setenv("PLUGINS_ENABLED", "1")
    agent_extensions.invalidate_extension_caches()

    definitions = asyncio.run(agent_extensions.plugin_tool_definitions())
    name = definitions[0]["function"]["name"]
    result = asyncio.run(agent_extensions.invoke_plugin_tool(name, {"name": "Lin"}))

    assert result["message"] == "hello Lin"


def test_plugin_workspace_write_contract_is_enforced(tmp_path, monkeypatch):
    import agent_extensions
    from plugins import PluginManager

    source = """
from myagent_plugin_sdk import Plugin

plugin = Plugin()

@plugin.tool(
    name="write",
    effect="workspace_write",
    resource_arguments=["path"],
    path_arguments=["path"],
    workspace_root_argument="workspace_root",
    worktree_compatible=True,
    input_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "workspace_root": {"type": "string"},
        },
        "required": ["path"],
    },
)
def write(path, workspace_root):
    return {"path": path, "workspace_root": workspace_root}
""".lstrip()
    discovery = tmp_path / "plugins"
    _make_python_plugin(discovery, source=source)
    manager = PluginManager([discovery], tmp_path / "plugin-state.json")
    monkeypatch.setattr(agent_extensions, "plugin_manager", lambda: manager)
    monkeypatch.setenv("PLUGINS_ENABLED", "1")
    agent_extensions.invalidate_extension_caches()
    worktree = tmp_path / "worktree"
    worktree.mkdir()

    definitions = asyncio.run(agent_extensions.plugin_tool_definitions())
    name = definitions[0]["function"]["name"]
    contract = agent_extensions.get_plugin_tool_contract(name)
    assert contract["effect"] == "workspace_write"
    result = asyncio.run(
        agent_extensions.invoke_plugin_tool(
            name,
            {"path": "nested/file.txt"},
            work_dir=str(worktree),
            require_worktree_isolation=True,
        )
    )
    assert result == {
        "path": str((worktree / "nested/file.txt").resolve()),
        "workspace_root": str(worktree.resolve()),
    }
    with pytest.raises(ValueError, match="escapes the managed worktree"):
        asyncio.run(
            agent_extensions.invoke_plugin_tool(
                name,
                {"path": str(tmp_path / "outside.txt")},
                work_dir=str(worktree),
                require_worktree_isolation=True,
            )
        )


def test_undeclared_plugin_tool_fails_closed_in_managed_worktree(
    tmp_path,
    monkeypatch,
):
    import agent_extensions
    from plugins import PluginManager

    discovery = tmp_path / "plugins"
    _make_python_plugin(discovery)
    manager = PluginManager([discovery], tmp_path / "plugin-state.json")
    monkeypatch.setattr(agent_extensions, "plugin_manager", lambda: manager)
    monkeypatch.setenv("PLUGINS_ENABLED", "1")
    agent_extensions.invalidate_extension_caches()

    name = asyncio.run(agent_extensions.plugin_tool_definitions())[0]["function"]["name"]
    with pytest.raises(ValueError, match="does not declare"):
        asyncio.run(
            agent_extensions.invoke_plugin_tool(
                name,
                {"name": "Lin"},
                work_dir=str(tmp_path),
                require_worktree_isolation=True,
            )
        )


def test_code_hook_joins_normal_hook_dispatch_chain(tmp_path, monkeypatch):
    import agent_extensions
    from plugins import PluginManager

    source = """
from myagent_plugin_sdk import Plugin

plugin = Plugin()

@plugin.hook(
    "PreToolUse",
    hook_id="rewrite-shell",
    matcher="^run_shell$",
    priority=5,
    failure_policy="block",
)
def rewrite(payload):
    updated = dict(payload["tool_input"])
    updated["command"] += " --safe"
    return {
        "decision": "allow",
        "updated_input": updated,
        "additional_context": "runtime hook executed",
    }
""".lstrip()
    discovery = tmp_path / "plugins"
    _make_python_plugin(discovery, source=source)
    manager = PluginManager([discovery], tmp_path / "plugin-state.json")
    monkeypatch.setattr(agent_extensions, "plugin_manager", lambda: manager)
    monkeypatch.setattr(agent_extensions, "_project_root", lambda: tmp_path)
    monkeypatch.setenv("PLUGINS_ENABLED", "1")
    monkeypatch.setenv("HOOKS_ENABLED", "1")
    agent_extensions.invalidate_extension_caches()

    result = asyncio.run(
        agent_extensions.dispatch_hook(
            "PreToolUse",
            {
                "tool_name": "run_shell",
                "tool_input": {"command": "pytest"},
            },
        )
    )

    assert result.decision == "allow"
    assert result.updated_input == {"command": "pytest --safe"}
    assert result.additional_context == "runtime hook executed"
    assert result.results[0].source_id == "plugin-runtime:demo.runtime"
    assert result.results[0].plugin_id == "demo.runtime"
    snapshot = agent_extensions.hook_snapshot()
    runtime_hook = next(row for row in snapshot["definitions"] if row["id"] == "rewrite-shell")
    assert runtime_hook["handler_type"] == "plugin"


def test_code_command_expands_slash_input(tmp_path, monkeypatch):
    import agent_extensions
    from plugins import PluginManager

    source = """
from myagent_plugin_sdk import Plugin

plugin = Plugin()

@plugin.command(
    name="review",
    description="Expand a review request.",
    usage="/review <path>",
)
def review(arguments, context):
    return {
        "prompt": f"Review {arguments.strip()} in session {context['session_id']}",
        "additional_context": "Generated by demo.runtime:review",
    }
""".lstrip()
    discovery = tmp_path / "plugins"
    _make_python_plugin(discovery, source=source)
    manager = PluginManager([discovery], tmp_path / "plugin-state.json")
    monkeypatch.setattr(agent_extensions, "plugin_manager", lambda: manager)
    monkeypatch.setenv("PLUGINS_ENABLED", "1")
    agent_extensions.invalidate_extension_caches()

    result = asyncio.run(
        agent_extensions.dispatch_plugin_command(
            "/review app",
            {"session_id": "s1"},
        )
    )
    qualified = asyncio.run(
        agent_extensions.dispatch_plugin_command(
            "/demo.runtime:review tests",
            {"session_id": "s2"},
        )
    )
    missing = asyncio.run(
        agent_extensions.dispatch_plugin_command("/missing", {"session_id": "s3"})
    )

    assert result["matched"] is True
    assert result["prompt"] == "Review app in session s1"
    assert result["additional_context"] == "Generated by demo.runtime:review"
    assert qualified["prompt"] == "Review tests in session s2"
    assert missing == {"matched": False}


def test_non_native_runtime_is_reported_unsupported(tmp_path):
    from plugins import load_plugin

    root = tmp_path / "foreign"
    _write_json(
        root / ".claude-plugin" / "plugin.json",
        {
            "name": "foreign-runtime",
            "runtime": {"type": "python", "entrypoint": "./plugin.py"},
        },
    )
    (root / "plugin.py").write_text("raise AssertionError('must not run')\n", encoding="utf-8")

    plugin = load_plugin(root)
    assert plugin.runtime is None
    assert plugin.compatibility.status == "unsupported"
    assert "runtime" in plugin.compatibility.unsupported_components


def test_agent_loop_wires_runtime_definitions_and_invocation():
    source = (APP_DIR / "agent_loop.py").read_text(encoding="utf-8")

    assert "plugin_tool_definitions()" in source
    assert "invoke_plugin_tool(" in source
    assert '"tool_plugin"' in source
    assert "dispatch_plugin_command(" in source
