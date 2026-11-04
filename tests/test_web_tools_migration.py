"""Exercise web-tool migration through the real executor and stored policies."""
from __future__ import annotations

import ast
import asyncio
import copy
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from host_tool_registry import host_tool_invokers
from plugins import load_plugin
import plugins.host as plugin_host
from security.models import DecisionOutcome, PERMISSION_PRESETS, PermissionMode, SecurityDecision
from security.runtime import active_security_context, classify_tool
from session_control.configuration import (
    constrain_call, filter_registry, from_metadata, ref_key, resolve_config,
    runtime_scope, tool_ref, validate_config,
)
from session_control.errors import ControlError
from session_control.service import SessionControlService
from session_control.store import digest
from tool_registry import ToolRegistry


@pytest.fixture
def web_plugin():
    plugin = load_plugin(ROOT / "plugins/web-search-providers")
    module = plugin_host._module(plugin)
    definitions = module.tool_definitions({"is_enabled": lambda _: True}, plugin)

    def registry():
        value = ToolRegistry()
        for definition in definitions:
            name = definition["function"]["name"]
            value.register_definition(
                definition, invocation_kind="host_service", owner=plugin.plugin_id,
                invoker_id=name, effect=host_tool_invokers.effect(name),
            )
        return value

    return SimpleNamespace(web=module.web_tools, registry=registry)


@pytest.fixture
def download_executor(web_plugin, monkeypatch, tmp_path):
    import agent_loop as agent
    import agent_tools

    default = tmp_path / "default"
    default.mkdir()
    monkeypatch.setattr(agent_tools, "WORK_DIR", default)
    monkeypatch.setattr(web_plugin.web, "_url_safe_for_fetch", lambda _: (True, ""))

    class Response:
        status_code = 200
        headers = {"content-type": "application/octet-stream", "content-length": "5"}

        def __init__(self, url):
            self.url = url

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

        def raise_for_status(self):
            pass

        async def aiter_bytes(self):
            # Concurrent invocations must retain their own ContextVars.
            await asyncio.sleep(0)
            yield b"hello"

    class Client:
        def __init__(self, **_):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

        def stream(self, _method, url):
            return Response(url)

    monkeypatch.setattr(web_plugin.web.httpx, "AsyncClient", Client)
    # Match test_tool_naming: use the production execution closure without a
    # model request. Only network authorization and HTTP responses are faked.
    tree = ast.parse((ROOT / "app/agent_loop.py").read_text(encoding="utf-8"))
    core = next(n for n in ast.walk(tree)
                if isinstance(n, ast.AsyncFunctionDef) and n.name == "_execute_one_core")

    async def noop(*_, **__):
        pass

    async def execute(workspace, arguments, mode=PermissionMode.FULL_ACCESS):
        def authorize(**kwargs):
            request = classify_tool(kwargs["tool_name"], kwargs["arguments"], kwargs["workspace"])
            decision = SecurityDecision(DecisionOutcome.ALLOW, "Approved network request",
                                        "test.approved", request.digest(1))
            return request, decision, PERMISSION_PRESETS[mode]

        scope = dict(vars(agent))
        scope.update(
            tool_registry=web_plugin.registry(), llm_stream_seq=1,
            state={"session_id": "download-test"},
            session_meta={"work_dir": str(workspace)}, iter_count=1,
            iter_model="offline-test", emit=None, tool_calls_list=[],
            iter_context_window=100000, _run_context_policy_serialized={}, llm_history=[],
            iter_client=SimpleNamespace(current_candidate=lambda: {"input_modalities": ["text"]}),
            _runtime_v2_is_primary=lambda: False,
            authorize_tool=authorize, _raise_if_steer_requested=noop, _push_stream_event=noop,
            _workflow_callbacks=lambda: SimpleNamespace(call=lambda *_: None),
            _tool_result_details_for_views=lambda value, *_: (value, value, value),
        )
        exec(compile(ast.Module(body=[core], type_ignores=[]),
                     str(ROOT / "app/agent_loop.py"), "exec"), scope)
        result = await scope["_execute_one_core"]({
            "id": "download-call", "name": "web_download", "args": arguments,
        })
        assert active_security_context() is None
        assert agent_tools.active_tool_work_dir() == default.resolve()
        return result

    return SimpleNamespace(execute=execute, default=default)


@pytest.mark.parametrize("path_argument", [None, "path", "target_directory", "file_path"])
def test_download_uses_session_directory(download_executor, tmp_path, path_argument):
    session = tmp_path / "session"
    session.mkdir()
    original = download_executor.default / "file.bin"
    original.write_bytes(b"keep")
    arguments = {"url": "https://example.test/file.bin"}
    if path_argument:
        arguments[path_argument] = "file.bin"

    result = asyncio.run(download_executor.execute(session, arguments))

    assert result["tool_failed"] is False, result["result"]
    assert (session / "file.bin").read_bytes() == b"hello"
    assert original.read_bytes() == b"keep"


@pytest.mark.parametrize("mode", [PermissionMode.FULL_ACCESS, PermissionMode.ASK_FOR_APPROVAL])
def test_download_accepts_session_absolute_path(download_executor, tmp_path, mode):
    session = tmp_path / "session"
    session.mkdir()
    target = session / "file.bin"

    result = asyncio.run(download_executor.execute(session, {
        "url": "https://example.test/file.bin", "path": str(target),
    }, mode))

    assert result["tool_failed"] is False, result["result"]
    assert target.read_bytes() == b"hello"


@pytest.mark.parametrize("path", [".env", ".git/config"])
def test_restricted_download_preserves_protected_files(download_executor, path):
    target = download_executor.default / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"original")

    result = asyncio.run(download_executor.execute(download_executor.default, {
        "url": "https://example.test/file.bin", "path": path,
    }, PermissionMode.ASK_FOR_APPROVAL))

    assert result["tool_failed"] is True
    assert "Security-sensitive path is protected" in result["result"]
    assert target.read_bytes() == b"original"


def test_concurrent_downloads_keep_separate_workspaces(download_executor, tmp_path):
    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    second.mkdir()

    async def run():
        return await asyncio.gather(*(
            download_executor.execute(root, {"url": "https://example.test/file.bin"})
            for root in (first, second)
        ))

    assert all(not r["tool_failed"] for r in asyncio.run(run()))
    assert (first / "file.bin").read_bytes() == (second / "file.bin").read_bytes() == b"hello"
    assert not (download_executor.default / "file.bin").exists()


def legacy_ref(name):
    return {"kind": "host", "owner": "core.tools", "name": name}


@pytest.mark.parametrize("name", ["web_fetch", "web_download"])
def test_persisted_web_tool_deny_still_blocks(web_plugin, tmp_path, name):
    raw = {"tools": {"deny": [legacy_ref(name)]}}
    original = copy.deepcopy(raw)
    config = from_metadata({"session_runtime_config": raw})
    descriptor = web_plugin.registry().require(name)

    assert raw == original
    assert config["tools"]["deny"] == [tool_ref(descriptor)]
    assert name not in filter_registry(web_plugin.registry(), config).names()
    # Old runtime snapshots can reach the comparison without being revalidated.
    config["tools"]["deny"] = [legacy_ref(name)]
    assert name not in filter_registry(web_plugin.registry(), config).names()
    with runtime_scope("test", config), pytest.raises(ControlError, match="not allowed"):
        constrain_call("test", descriptor, {"url": "https://allowed.example/"}, tmp_path)


@pytest.mark.parametrize("name", ["web_fetch", "web_download"])
@pytest.mark.parametrize("required", [True, False])
def test_legacy_url_binding_applies_to_calls_and_redirects(web_plugin, tmp_path, name, required):
    from session_control.integration import redirect_allowed

    descriptor = web_plugin.registry().require(name)
    fingerprint = digest(descriptor.openai_definition()["function"]["parameters"])
    config = from_metadata({"session_runtime_config": {"tools": {"bindings": [{
        "tool_ref": legacy_ref(name), "schema_digest": fingerprint, "required": required,
        "constraints": [{"kind": "url", "pointer": "/url", "hosts": ["allowed.example"]}],
    }]}}})
    assert config["tools"]["bindings"][0]["schema_digest"] == fingerprint
    # Also exercise unrevised snapshots used during recovery.
    config["tools"]["bindings"][0]["tool_ref"] = legacy_ref(name)
    registry = filter_registry(web_plugin.registry(), config)
    assert name in registry.names()
    with runtime_scope("test", config):
        constrain_call("test", descriptor, {"url": "https://allowed.example/"}, tmp_path)
        redirect_allowed("https://allowed.example/next")
        with pytest.raises(ControlError, match="url constraint"):
            redirect_allowed("https://outside.example/")
        with pytest.raises(ControlError, match="url constraint"):
            constrain_call("test", descriptor, {"url": "https://outside.example/"}, tmp_path)


@pytest.mark.parametrize("name", ["web_fetch", "web_download"])
def test_old_allow_and_new_runtime_ceiling_intersect(web_plugin, name):
    current = tool_ref(web_plugin.registry().require(name))
    base = {"tools": {"mode": "custom", "allow": [legacy_ref(name)]}}
    ceiling = {"tools": {"mode": "custom", "allow": [current]}}
    config = resolve_config(base, ceiling)

    assert config["tools"]["allow"] == [current]
    assert filter_registry(web_plugin.registry(), config).names() == {name}
    config = resolve_config(config, {"tools": {"deny": [legacy_ref(name)]}})
    assert filter_registry(web_plugin.registry(), config).names() == set()


def test_legacy_binding_validation_and_missing_plugin_fail_closed(web_plugin):
    descriptor = web_plugin.registry().require("web_fetch")
    config = from_metadata({"session_runtime_config": {"tools": {"bindings": [{
        "tool_ref": legacy_ref("web_fetch"), "required": True,
        "schema_digest": digest(descriptor.openai_definition()["function"]["parameters"]),
        "constraints": [{"kind": "url", "pointer": "/url", "hosts": ["allowed.example"]}],
    }]}}})

    async def catalog(*_, **__):
        return web_plugin.registry()

    validated = asyncio.run(SessionControlService.validate_bindings(
        SimpleNamespace(catalog=catalog), "test", config))
    assert validated["tools"]["bindings"][0]["tool_ref"] == tool_ref(descriptor)
    with pytest.raises(ControlError, match="Required tool is missing"):
        filter_registry(ToolRegistry(), validated)
    validated["tools"]["bindings"][0]["schema_digest"] = "different-schema"
    with pytest.raises(ControlError, match="schema changed"):
        filter_registry(web_plugin.registry(), validated)


@pytest.mark.parametrize("ref", [
    {"kind": "host", "owner": "another-plugin", "name": "web_fetch"},
    {"kind": "mcp", "owner": "core.tools", "name": "web_fetch"},
    {"kind": "host", "owner": "core.tools", "name": "read_file"},
])
def test_migration_preserves_unrelated_source_identities(ref):
    config = validate_config({"tools": {"deny": [ref]}})
    assert config["tools"]["deny"] == [ref]
    assert ref_key(ref) == (ref["kind"], ref["owner"], ref["name"])
