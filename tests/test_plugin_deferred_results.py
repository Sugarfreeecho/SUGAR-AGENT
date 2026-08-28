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
def _trust_extensions(monkeypatch):
    monkeypatch.setattr(
        "security.extensions.descriptor_is_trusted",
        lambda _descriptor: True,
    )


def _make_plugin(root: Path) -> Path:
    plugin_root = root / "deferred-demo"
    manifest_path = plugin_root / ".myagent-plugin" / "plugin.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "id": "deferred.demo",
                "name": "Deferred Demo",
                "version": "1.0.0",
                "runtime": {
                    "type": "python",
                    "entrypoint": "./plugin.py",
                    "api_version": "1",
                    "timeout_seconds": 5,
                },
                "permissions": {
                    "context": ["session_id", "cancellation_id"]
                },
            }
        ),
        encoding="utf-8",
    )
    (plugin_root / "plugin.py").write_text(
        """
import uuid
from myagent_plugin_sdk import Plugin, deferred_result

plugin = Plugin()
pending = {}

@plugin.tool(
    name="wait",
    input_schema={
        "type": "object",
        "properties": {"mode": {"type": "string"}},
        "additionalProperties": False,
    },
)
def wait(mode="complete"):
    token = uuid.uuid4().hex
    pending[token] = {"mode": mode, "polls": 0, "released": False}
    timeout = 0.15 if mode == "timeout" else 2
    return deferred_result(
        token,
        {"ok": True, "mode": mode},
        poll_after_ms=50,
        timeout_seconds=timeout,
    )

@plugin.tool(name="release")
def release():
    for item in pending.values():
        item["released"] = True
    return {"ok": True}

@plugin.on_deferred_poll
def poll(token, context):
    item = pending.get(token)
    if item is None:
        return {"ok": False, "error": "unknown token"}
    item["polls"] += 1
    if item["mode"] == "complete" and item["polls"] >= 2:
        pending.pop(token, None)
        return {"ok": True, "done": True, "polls": item["polls"]}
    if item["released"]:
        pending.pop(token, None)
        return {"ok": True, "released": True, "polls": item["polls"]}
    timeout = 0.15 if item["mode"] == "timeout" else 2
    return deferred_result(
        token,
        {"ok": True, "mode": item["mode"]},
        poll_after_ms=50,
        timeout_seconds=timeout,
    )

@plugin.on_deferred_cancel
def cancel(token, reason, context):
    item = pending.pop(token, None)
    return {
        "ok": False,
        "reason": reason,
        "existed": item is not None,
        "session_id": context.get("session_id"),
        "cancellation_id": context.get("cancellation_id"),
    }
""".lstrip(),
        encoding="utf-8",
    )
    return plugin_root


def _configure_agent_extensions(tmp_path, monkeypatch):
    import agent_extensions
    from plugins import PluginManager

    discovery = tmp_path / "plugins"
    _make_plugin(discovery)
    manager = PluginManager([discovery], tmp_path / "plugin-state.json")
    monkeypatch.setattr(agent_extensions, "plugin_manager", lambda: manager)
    monkeypatch.setenv("PLUGINS_ENABLED", "1")
    agent_extensions.invalidate_extension_caches()
    definitions = asyncio.run(agent_extensions.plugin_tool_definitions())
    names = {
        item["function"]["name"].rsplit("__", 1)[-1]: item["function"]["name"]
        for item in definitions
    }
    return agent_extensions, names


def test_deferred_result_completes_without_exposing_host_marker(tmp_path, monkeypatch):
    agent_extensions, names = _configure_agent_extensions(tmp_path, monkeypatch)

    result = asyncio.run(
        agent_extensions.invoke_plugin_tool(
            names["wait"],
            {"mode": "complete"},
            session_id="session-a",
            cancellation_id="call-a",
        )
    )

    assert result == {"ok": True, "done": True, "polls": 2}
    assert "_myagent_deferred" not in result


def test_deferred_wait_does_not_occupy_plugin_worker(tmp_path, monkeypatch):
    agent_extensions, names = _configure_agent_extensions(tmp_path, monkeypatch)

    async def scenario():
        waiting = asyncio.create_task(
            agent_extensions.invoke_plugin_tool(
                names["wait"],
                {"mode": "release"},
                session_id="session-a",
            )
        )
        await asyncio.sleep(0.08)
        released = await agent_extensions.invoke_plugin_tool(names["release"], {})
        return released, await asyncio.wait_for(waiting, timeout=1)

    released, result = asyncio.run(scenario())

    assert released == {"ok": True}
    assert result["released"] is True


def test_deferred_timeout_and_cancellation_call_plugin_cleanup(tmp_path, monkeypatch):
    agent_extensions, names = _configure_agent_extensions(tmp_path, monkeypatch)

    timed_out = asyncio.run(
        agent_extensions.invoke_plugin_tool(
            names["wait"],
            {"mode": "timeout"},
            session_id="session-timeout",
            cancellation_id="call-timeout",
        )
    )
    cancelled = asyncio.run(
        agent_extensions.invoke_plugin_tool(
            names["wait"],
            {"mode": "release"},
            session_id="session-cancel",
            cancellation_id="call-cancel",
            should_cancel=lambda: True,
        )
    )

    assert timed_out == {
        "ok": False,
        "reason": "timeout",
        "existed": True,
        "session_id": "session-timeout",
        "cancellation_id": "call-timeout",
    }
    assert cancelled == {
        "ok": False,
        "reason": "cancelled",
        "existed": True,
        "session_id": "session-cancel",
        "cancellation_id": "call-cancel",
    }


def test_registry_rejects_deferred_marker_without_registered_handler(tmp_path):
    from plugins import PluginRuntimeError, PluginRuntimeRegistry, load_plugin

    plugin_root = _make_plugin(tmp_path / "plugins")
    source_path = plugin_root / "plugin.py"
    source = source_path.read_text(encoding="utf-8").replace(
        "@plugin.on_deferred_poll\ndef poll(token, context):",
        "def poll(token, context):",
    )
    source_path.write_text(source, encoding="utf-8")
    plugin = load_plugin(plugin_root)
    registry = PluginRuntimeRegistry(storage_root=tmp_path / "storage")
    wait_name = next(
        item["function"]["name"]
        for item in registry.tool_definitions([plugin])
        if item["function"]["name"].endswith("__wait")
    )
    with pytest.raises(PluginRuntimeError, match="without registering"):
        registry.invoke(wait_name, {"mode": "complete"}, [plugin])
    registry.close()


def test_deferred_lease_is_bound_to_tool_identity_and_revoked_on_disable(tmp_path):
    from myagent_plugin_sdk import parse_deferred_result
    from plugins import PluginRuntimeError, PluginRuntimeRegistry, load_plugin

    plugin = load_plugin(_make_plugin(tmp_path / "plugins"))
    registry = PluginRuntimeRegistry(storage_root=tmp_path / "storage")
    names = {
        item["function"]["name"].rsplit("__", 1)[-1]: item["function"]["name"]
        for item in registry.tool_definitions([plugin])
    }
    owner = {"session_id": "owner", "cancellation_id": "call-owner"}
    raw = registry.invoke(
        names["wait"],
        {"mode": "release"},
        [plugin],
        context=owner,
    )
    token = parse_deferred_result(raw).token

    with pytest.raises(PluginRuntimeError, match="session_id"):
        registry.poll_deferred(
            names["wait"],
            token,
            [plugin],
            context={"session_id": "attacker", "cancellation_id": "call-owner"},
        )
    with pytest.raises(PluginRuntimeError, match="different tool"):
        registry.poll_deferred(
            names["release"],
            token,
            [plugin],
            context=owner,
        )
    assert registry.snapshot()["deferred_count"] == 1

    assert registry.tool_definitions([]) == []
    assert registry.snapshot()["deferred_count"] == 0


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is not installed")
def test_node_worker_supports_deferred_poll_protocol(tmp_path):
    from myagent_plugin_sdk import parse_deferred_result
    from plugins import PluginRuntimeRegistry, load_plugin

    root = tmp_path / "node-deferred"
    manifest_path = root / ".myagent-plugin" / "plugin.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "id": "deferred.node",
                "name": "Deferred Node",
                "version": "1.0.0",
                "runtime": {
                    "type": "node",
                    "entrypoint": "./plugin.cjs",
                    "api_version": "1",
                    "timeout_seconds": 5,
                },
                "permissions": {"context": ["session_id"]},
            }
        ),
        encoding="utf-8",
    )
    (root / "plugin.cjs").write_text(
        """
exports.setup = (plugin) => {
  const pending = new Map();
  plugin.registerTool({ name: "later" }, async (_args, context) => {
    const token = "node-token";
    pending.set(token, context.session_id);
    return {
      ok: true,
      _myagent_deferred: {
        token,
        poll_after_ms: 50,
        timeout_seconds: 2
      }
    };
  });
  plugin.onDeferredPoll(async (token, context) => {
    const owner = pending.get(token);
    pending.delete(token);
    return { ok: true, owner, caller: context.session_id };
  });
};
""".lstrip(),
        encoding="utf-8",
    )
    plugin = load_plugin(root)
    registry = PluginRuntimeRegistry(storage_root=tmp_path / "storage")
    name = registry.tool_definitions([plugin])[0]["function"]["name"]
    context = {"session_id": "node-session"}
    raw = registry.invoke(name, {}, [plugin], context=context)
    token = parse_deferred_result(raw).token

    result = registry.poll_deferred(name, token, [plugin], context=context)
    registry.close()

    assert result == {
        "ok": True,
        "owner": "node-session",
        "caller": "node-session",
    }
