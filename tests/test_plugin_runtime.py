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
def _trust_extensions_for_runtime_tests(monkeypatch):
    """These tests exercise runtime contracts, not the application trust UI."""
    monkeypatch.setattr(
        "security.extensions.descriptor_is_trusted",
        lambda _descriptor: True,
    )


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _make_python_plugin(
    discovery: Path,
    *,
    plugin_id: str = "demo.runtime",
    source: str | None = None,
    permissions: dict | None = None,
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
            **({"permissions": permissions} if permissions is not None else {}),
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


def test_application_registry_does_not_start_untrusted_plugin(tmp_path, monkeypatch):
    from plugins import PluginRuntimeRegistry, load_plugin

    plugin = load_plugin(_make_python_plugin(tmp_path))
    monkeypatch.setattr(
        "security.extensions.descriptor_is_trusted",
        lambda _descriptor: False,
    )
    monkeypatch.setenv("EXTENSION_REGISTRATION_APPROVAL_ENABLED", "1")
    registry = PluginRuntimeRegistry(enforce_trust=True)

    assert registry.tool_definitions([plugin]) == []
    assert registry.snapshot()["workers"][0]["running"] is False
    assert "not approved" in registry.errors[0]
    registry.close()


def test_application_registry_starts_untrusted_plugin_when_approval_is_disabled(
    tmp_path, monkeypatch
):
    from plugins import PluginRuntimeRegistry, load_plugin

    plugin = load_plugin(_make_python_plugin(tmp_path))
    monkeypatch.setattr(
        "security.extensions.descriptor_is_trusted",
        lambda _descriptor: False,
    )
    monkeypatch.setenv("EXTENSION_REGISTRATION_APPROVAL_ENABLED", "0")
    registry = PluginRuntimeRegistry(enforce_trust=True)

    definitions = registry.tool_definitions([plugin])
    assert len(definitions) == 1
    assert definitions[0]["function"]["name"] == "plugin_demo_runtime__greet"
    assert registry.errors == ()
    registry.close()


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


def test_worker_uses_one_event_loop_for_its_entire_lifecycle(tmp_path):
    from plugins import PluginRuntimeRegistry, load_plugin

    deactivation_state = tmp_path / "deactivation-state.json"
    source = """
import asyncio
import json
from pathlib import Path

from myagent_plugin_sdk import Plugin

plugin = Plugin()
state = {"activation_loop": None, "last_call_loop": None}
deactivation_state = Path(__DEACTIVATION_STATE__)

@plugin.on_activate
async def activate(context):
    state["activation_loop"] = asyncio.get_running_loop()

@plugin.tool(name="loop_state")
async def loop_state():
    current_loop = asyncio.get_running_loop()
    result = {
        "same_as_activation": current_loop is state["activation_loop"],
        "activation_loop_closed": state["activation_loop"].is_closed(),
        "same_as_previous_call": (
            None
            if state["last_call_loop"] is None
            else current_loop is state["last_call_loop"]
        ),
    }
    state["last_call_loop"] = current_loop
    return result

@plugin.on_deactivate
async def deactivate(context):
    current_loop = asyncio.get_running_loop()
    deactivation_state.write_text(
        json.dumps({
            "same_as_activation": current_loop is state["activation_loop"],
            "activation_loop_closed": state["activation_loop"].is_closed(),
        }),
        encoding="utf-8",
    )
""".lstrip().replace("__DEACTIVATION_STATE__", repr(str(deactivation_state)))
    plugin = load_plugin(_make_python_plugin(tmp_path, source=source))
    registry = PluginRuntimeRegistry()
    name = registry.tool_definitions([plugin])[0]["function"]["name"]

    first = registry.invoke(name, {}, [plugin])
    second = registry.invoke(name, {}, [plugin])
    registry.close()

    assert first == {
        "same_as_activation": True,
        "activation_loop_closed": False,
        "same_as_previous_call": None,
    }
    assert second == {
        "same_as_activation": True,
        "activation_loop_closed": False,
        "same_as_previous_call": True,
    }
    assert json.loads(deactivation_state.read_text(encoding="utf-8")) == {
        "same_as_activation": True,
        "activation_loop_closed": False,
    }


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


def test_plugin_tool_host_actions_use_trusted_session_scope(tmp_path, monkeypatch):
    import agent_extensions
    import agent_harness
    from plugins import PluginManager
    from runtime_v2 import SnapshotStore

    source = """
from myagent_plugin_sdk import Plugin

plugin = Plugin()

@plugin.tool(name="save", input_schema={"type": "object", "properties": {}})
def save():
    return {
        "ok": True,
        "_host_actions": [{
            "service": "session_state.compare_and_set",
            "namespace": "prefs",
            "expected_revision": 0,
            "value": {"theme": "dark"},
        }],
    }
""".lstrip()
    discovery = tmp_path / "plugins"
    _make_python_plugin(
        discovery,
        source=source,
        permissions={
            "services": ["session_state.compare_and_set"],
            "context": ["session_id"],
        },
    )
    sessions_dir = tmp_path / "sessions"
    (sessions_dir / "s1").mkdir(parents=True)

    class FakeSessionManager:
        pass

    FakeSessionManager.sessions_dir = sessions_dir
    FakeSessionManager._resolve_session_path = staticmethod(
        lambda session_id: sessions_dir / session_id
    )

    monkeypatch.setattr(agent_harness, "session_manager", FakeSessionManager())
    manager = PluginManager([discovery], tmp_path / "plugin-state.json")
    monkeypatch.setattr(agent_extensions, "plugin_manager", lambda: manager)
    monkeypatch.setenv("PLUGINS_ENABLED", "1")
    agent_extensions.invalidate_extension_caches()

    name = asyncio.run(agent_extensions.plugin_tool_definitions())[0]["function"]["name"]
    result = asyncio.run(
        agent_extensions.invoke_plugin_tool(name, {}, session_id="s1", run_id="run-1")
    )

    assert "_host_actions" not in result
    assert result["_host_action_results"][0]["state"]["revision"] == 1
    snapshot = SnapshotStore(sessions_dir).read("s1")
    assert snapshot["extensions"]["demo.runtime"]["prefs"]["value"] == {
        "theme": "dark"
    }


def test_plugin_extension_event_is_committed_once_and_published_live(tmp_path, monkeypatch):
    import agent_extensions
    import agent_harness
    from plugins import PluginManager
    from runtime_v2 import SessionEventLog
    from runtime_v2.ui_projection import RuntimeUiProjection

    source = """
from myagent_plugin_sdk import Plugin, with_host_actions

plugin = Plugin()

@plugin.tool(name="notify", input_schema={"type": "object", "properties": {}})
def notify():
    return with_host_actions(
        {"ok": True},
        [
            {
                "service": "session_state.set_latest",
                "namespace": "job",
                "value": {"status": "done"},
            },
            {
                "service": "session_events.append",
                "event_name": "job_changed",
                "data": {"status": "done"},
            },
        ],
    )
""".lstrip()
    discovery = tmp_path / "plugins"
    _make_python_plugin(
        discovery,
        source=source,
        permissions={
            "services": ["session_state.set_latest", "session_events.append"],
            "context": ["session_id"],
        },
    )
    sessions_dir = tmp_path / "sessions"
    (sessions_dir / "s1").mkdir(parents=True)

    class FakeSessionManager:
        pass

    FakeSessionManager.sessions_dir = sessions_dir
    FakeSessionManager._resolve_session_path = staticmethod(
        lambda session_id: sessions_dir / session_id
    )
    monkeypatch.setattr(agent_harness, "session_manager", FakeSessionManager())
    manager = PluginManager([discovery], tmp_path / "plugin-state.json")
    monkeypatch.setattr(agent_extensions, "plugin_manager", lambda: manager)
    monkeypatch.setenv("PLUGINS_ENABLED", "1")
    agent_extensions.invalidate_extension_caches()
    published = []

    async def publish(event):
        published.append(dict(event))

    name = asyncio.run(agent_extensions.plugin_tool_definitions())[0]["function"]["name"]
    result = asyncio.run(
        agent_extensions.invoke_plugin_tool(
            name,
            {},
            session_id="s1",
            run_id="run-1",
            publish_event=publish,
        )
    )

    assert result["ok"] is True
    assert "_host_actions" not in result
    assert published == [
        {
            "type": "extension_state_changed",
            "plugin_id": "demo.runtime",
            "namespace": "job",
            "revision": 1,
            "_runtime_v2_committed": True,
        },
        {
            "type": "extension_event",
            "plugin_id": "demo.runtime",
            "event_name": "job_changed",
            "data": {"status": "done"},
            "created_at": published[1]["created_at"],
            "runtime_seq": 2,
            "_runtime_v2_committed": True,
        }
    ]
    runtime_events = SessionEventLog(sessions_dir).read_all("s1")
    assert [event.type for event in runtime_events] == [
        "extension_state_changed",
        "extension_event",
    ]
    assert RuntimeUiProjection(sessions_dir).read_ui_events("s1")[0]["data"] == {
        "status": "done"
    }


def test_plugin_tool_receives_trusted_session_context_without_argument_injection(
    tmp_path,
    monkeypatch,
):
    import agent_extensions
    from plugins import PluginManager

    source = """
from myagent_plugin_sdk import Plugin, current_tool_context

plugin = Plugin()

@plugin.tool(
    name="whoami",
    input_schema={
        "type": "object",
        "properties": {"value": {"type": "string"}},
        "required": ["value"],
        "additionalProperties": False,
    },
)
def whoami(value):
    context = current_tool_context()
    return {
        "value": value,
        "session_id": context.session_id,
        "run_id": context.run_id,
        "workspace_root": context.workspace_root,
        "cancellation_id": context.cancellation_id,
    }
""".lstrip()
    discovery = tmp_path / "plugins"
    _make_python_plugin(
        discovery,
        source=source,
        permissions={
            "context": [
                "session_id",
                "run_id",
                "workspace_root",
                "cancellation_id",
            ]
        },
    )
    manager = PluginManager([discovery], tmp_path / "plugin-state.json")
    monkeypatch.setattr(agent_extensions, "plugin_manager", lambda: manager)
    monkeypatch.setenv("PLUGINS_ENABLED", "1")
    agent_extensions.invalidate_extension_caches()

    definition = asyncio.run(agent_extensions.plugin_tool_definitions())[0]
    name = definition["function"]["name"]
    assert "session_id" not in definition["function"]["parameters"]["properties"]

    result = asyncio.run(
        agent_extensions.invoke_plugin_tool(
            name,
            {
                "value": "ok",
                "_session_id": "spoofed-private",
                "session_id": "spoofed-public",
                "run_id": "spoofed-run",
                "workspace_root": "spoofed-workspace",
                "plugin_id": "spoofed-plugin",
                "plugin_data_dir": "spoofed-data",
                "plugin_cache_dir": "spoofed-cache",
                "plugin_temp_dir": "spoofed-temp",
                "cancellation_id": "spoofed-call",
            },
            session_id="trusted-session",
            run_id="trusted-run",
            work_dir=str(tmp_path / "trusted-workspace"),
            cancellation_id="trusted-call",
        )
    )

    assert result == {
        "value": "ok",
        "session_id": "trusted-session",
        "run_id": "trusted-run",
        "workspace_root": str((tmp_path / "trusted-workspace")),
        "cancellation_id": "trusted-call",
    }


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
    _make_python_plugin(
        discovery,
        source=source,
        permissions={"context": ["session_id"]},
    )
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

    assert "build_combined_tool_definitions_for_session(" in source
    assert '"plugin_tool_definitions", plugin_tool_definitions' in source
    assert "invoke_plugin_tool(" in source
    assert '"tool_plugin"' in source
    assert "dispatch_plugin_command(" in source
