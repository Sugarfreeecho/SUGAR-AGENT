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


@pytest.fixture(autouse=True)
def _trust_extensions_for_adapter_tests(monkeypatch):
    """Compatibility tests isolate adapters from the application trust gate."""
    monkeypatch.setattr(
        "security.extensions.descriptor_is_trusted",
        lambda _descriptor: True,
    )


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def test_claude_declarative_commands_expand_arguments(tmp_path, monkeypatch):
    import agent_extensions
    from plugins import PluginManager, load_plugin

    root = tmp_path / "plugins" / "claude-demo"
    _write_json(
        root / ".claude-plugin" / "plugin.json",
        {
            "name": "claude-demo",
            "version": "1.0.0",
            "commands": {
                "review": {
                    "content": "Review $ARGUMENTS carefully.",
                    "description": "Review a target.",
                    "argumentHint": "<path>",
                },
                "compare": {
                    "source": "./prompts/compare.md",
                    "description": "Compare two targets.",
                },
            },
        },
    )
    prompt = root / "prompts" / "compare.md"
    prompt.parent.mkdir(parents=True)
    prompt.write_text("Compare $1 with $2.", encoding="utf-8")
    conventional = root / "commands" / "explain.md"
    conventional.parent.mkdir(parents=True)
    conventional.write_text(
        "---\ndescription: Explain a target\nargument-hint: <path>\n---\n"
        "Explain {{arguments}}.",
        encoding="utf-8",
    )

    plugin = load_plugin(root)
    assert plugin.source_format == "claude"
    assert plugin.compatibility.status == "compatible"
    assert "commands" in plugin.compatibility.supported_components
    assert set(plugin.commands) == {
        "claude-demo:compare",
        "claude-demo:explain",
        "claude-demo:review",
    }

    manager = PluginManager([root.parent], tmp_path / "state.json")
    monkeypatch.setattr(agent_extensions, "plugin_manager", lambda: manager)
    monkeypatch.setenv("PLUGINS_ENABLED", "1")
    agent_extensions.invalidate_extension_caches()

    review = asyncio.run(
        agent_extensions.dispatch_plugin_command("/review app/agent_loop.py")
    )
    compare = asyncio.run(
        agent_extensions.dispatch_plugin_command("/claude-demo:compare old.py new.py")
    )
    explain = asyncio.run(
        agent_extensions.dispatch_plugin_command("/explain runtime.py")
    )

    assert review["prompt"] == "Review app/agent_loop.py carefully."
    assert compare["prompt"] == "Compare old.py with new.py."
    assert explain["prompt"] == "Explain runtime.py."


def _make_hermes_plugin(root: Path, *, kind: str = "standalone") -> Path:
    root.mkdir(parents=True)
    (root / "plugin.yaml").write_text(
        "\n".join(
            [
                "name: hermes-demo",
                "version: 1.2.0",
                "description: Hermes compatibility fixture",
                f"kind: {kind}",
                "provides_tools:",
                "  - hermes_echo",
                "provides_hooks:",
                "  - pre_tool_call",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "__init__.py").write_text(
        """
def register(ctx):
    schema = {
        "name": "hermes_echo",
        "description": "Echo through the Hermes adapter.",
        "parameters": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    }

    def echo(args):
        return {"echo": args["text"]}

    def pre_tool(tool_name="", args=None, **kwargs):
        if tool_name == "run_shell":
            return {"block": True, "reason": "blocked by hermes adapter"}

    def plan(raw_args):
        return f"Plan the following Hermes task: {raw_args}"

    ctx.register_tool("hermes_echo", "demo", schema, echo)
    ctx.register_hook("pre_tool_call", pre_tool)
    ctx.register_command("hermes-plan", plan, "Create a plan", "<task>")
""".lstrip(),
        encoding="utf-8",
    )
    return root


def test_hermes_standalone_adapter_registers_tool_hook_and_command(
    tmp_path, monkeypatch
):
    import agent_extensions
    from plugins import PluginManager, PluginRuntimeRegistry, load_plugin

    discovery = tmp_path / "plugins"
    root = _make_hermes_plugin(discovery / "hermes-demo")
    plugin = load_plugin(root)

    assert plugin.source_format == "hermes"
    assert plugin.runtime is not None
    assert plugin.runtime.adapter == "hermes"
    assert plugin.compatibility.status == "compatible"

    registry = PluginRuntimeRegistry()
    definitions = registry.tool_definitions([plugin])
    tool_name = definitions[0]["function"]["name"]
    assert registry.invoke(tool_name, {"text": "hello"}, [plugin]) == {"echo": "hello"}
    registry.close()

    manager = PluginManager([discovery], tmp_path / "state.json")
    monkeypatch.setattr(agent_extensions, "plugin_manager", lambda: manager)
    monkeypatch.setattr(agent_extensions, "_project_root", lambda: tmp_path)
    monkeypatch.setenv("PLUGINS_ENABLED", "1")
    monkeypatch.setenv("HOOKS_ENABLED", "1")
    agent_extensions.invalidate_extension_caches()

    hook = asyncio.run(
        agent_extensions.dispatch_hook(
            "PreToolUse",
            {
                "tool_name": "run_shell",
                "tool_input": {"command": "echo unsafe"},
            },
        )
    )
    command = asyncio.run(
        agent_extensions.dispatch_plugin_command("/hermes-plan ship adapter")
    )

    assert hook.blocked is True
    assert "blocked by hermes adapter" in hook.results[0].reason
    assert command["prompt"] == "Plan the following Hermes task: ship adapter"


def test_hermes_host_specific_plugin_kind_is_reported_unsupported(tmp_path):
    from plugins import load_plugin

    plugin = load_plugin(_make_hermes_plugin(tmp_path / "provider", kind="backend"))
    assert plugin.runtime is None
    assert plugin.compatibility.status == "unsupported"
    assert "runtime" in plugin.compatibility.unsupported_components
    assert any("host-specific provider APIs" in item for item in plugin.compatibility.warnings)


def _make_opencode_package(root: Path) -> Path:
    _write_json(
        root / "package.json",
        {
            "name": "opencode-demo",
            "version": "1.0.0",
            "description": "OpenCode compatibility fixture",
            "main": "./index.js",
            "keywords": ["opencode-plugin"],
            "peerDependencies": {"@opencode-ai/plugin": "^1.0.0"},
        },
    )
    (root / "index.js").write_text(
        """
exports.DemoPlugin = async () => ({
  tool: {
    echo: {
      description: "Echo from an OpenCode plugin.",
      args: { text: { type: "string" } },
      async execute(args) {
        return { echo: args.text };
      }
    }
  },
  "tool.execute.before": async (input, output) => {
    if (input.tool === "run_shell") output.args.command += " --checked";
  }
});
""".lstrip(),
        encoding="utf-8",
    )
    return root


def test_opencode_package_manifest_maps_to_partial_node_runtime(tmp_path):
    from plugins import discover_plugins, load_plugin

    root = _make_opencode_package(tmp_path / "opencode-demo")
    plugin = load_plugin(root)

    assert plugin.source_format == "opencode"
    assert plugin.runtime is not None
    assert plugin.runtime.runtime_type == "node"
    assert plugin.runtime.adapter == "opencode"
    assert plugin.dependencies == {"node": True}
    assert plugin.compatibility.status == "partial"
    assert "runtime" in plugin.compatibility.supported_components
    assert "opencode_host_context" in plugin.compatibility.unsupported_components
    assert discover_plugins([tmp_path]).plugins[0].plugin_id == "opencode-demo"


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is not installed")
def test_opencode_adapter_registers_tool_and_before_hook(tmp_path, monkeypatch):
    import agent_extensions
    from plugins import PluginManager, PluginRuntimeRegistry, load_plugin

    discovery = tmp_path / "plugins"
    plugin = load_plugin(_make_opencode_package(discovery / "opencode-demo"))
    registry = PluginRuntimeRegistry()
    definitions = registry.tool_definitions([plugin])
    name = definitions[0]["function"]["name"]
    assert registry.invoke(name, {"text": "hello"}, [plugin]) == {"echo": "hello"}
    registry.close()

    manager = PluginManager([discovery], tmp_path / "state.json")
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
    assert result.updated_input == {"command": "pytest --checked"}
