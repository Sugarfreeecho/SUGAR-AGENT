"""Feedback regressions; fake desktop responses, never user desktop input."""
from __future__ import annotations

import asyncio
import base64
from io import BytesIO
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from execution_services.computer import ComputerUseManager, READ_TOOLS
from execution_services.computer_results import project_result
from execution_services.jobs import ExecutionService


def fixture_tools():
    window = {"pid": {"type": "integer", "minimum": 1}, "window_id": {"type": "integer"}, "session": {"type": "string"}}
    return [
        {"name": "click", "inputSchema": {"type": "object", "additionalProperties": False,
            "properties": {**window, "x": {"type": "number"}, "y": {"type": "number"}, "target": {"type": "object"}, "scope": {"type": "string"}}}},
        {"name": "verify_state", "inputSchema": {"type": "object", "additionalProperties": False,
            "properties": {**window, "expect": {"type": "array", "minItems": 1, "items": {"type": "object"}},
                           "timeout_ms": {"type": "integer", "minimum": 0, "maximum": 10000},
                           "stable_samples": {"type": "integer", "minimum": 1, "maximum": 5}, "include_screenshot": {"type": "boolean"}},
            "required": ["pid", "window_id", "expect"]}},
        {"name": "list_apps", "inputSchema": {"type": "object", "additionalProperties": False}},
    ]


@pytest.fixture
def provider(monkeypatch):
    import agent_mcp
    import host_tool_registry
    import security.runtime
    import security.extensions
    calls = []
    response = {"action_error": False, "status": "satisfied", "stable": True}

    async def call(name, arguments):
        calls.append((name, dict(arguments)))
        if name == "click":
            return {"isError": response["action_error"], "content": [{"type": "text", "text": "Posted click"}],
                    "structuredContent": {"path": "post_message", "verified": False, "effect": "unverifiable",
                                          **({"code": "background_unavailable"} if response["action_error"] else {})}}
        if name == "verify_state":
            if response.get("verify_error"):
                raise RuntimeError("observation transport lost")
            return {"content": [{"type": "text", "text": "verify_state: " + response["status"]}],
                    "structuredContent": {"status": response["status"], "stable": response["stable"]}}
        return {"isError": True, "content": [{"type": "text", "text": "this session has ended; call start_session explicitly to reuse its label"}],
                "structuredContent": {"code": "session_ended"}}

    class Driver:
        async def list_tools_json(self):
            return json.dumps({"tools": fixture_tools()})
        async def call_tool(self, name, arguments):
            raw = await call(name, json.loads(arguments))
            return SimpleNamespace(raw_json=json.dumps(raw), is_error=raw.get("isError", False))
        async def shutdown(self):
            pass

    launch_configs = []
    class Server:
        _tools = [SimpleNamespace(model_dump=lambda tool=tool: tool) for tool in fixture_tools()]
        async def start(self):
            pass
        async def stop(self):
            pass
        async def call_tool(self, name, arguments):
            return await call(name, arguments)
    configs = {"cua-driver-mcp": {"command": "cua-driver", "args": ["mcp"]}}
    def connector(alias, cfg, **kwargs):
        launch_configs.append(cfg)
        return Server()
    async def reserve(*args, **kwargs):
        pass
    async def run_here(coro):
        return await coro
    monkeypatch.setitem(sys.modules, "cua_driver", SimpleNamespace(CuaDriver=SimpleNamespace(create=Driver)))
    monkeypatch.setattr(agent_mcp, "_load_servers_dict_from_config", lambda: (configs, None))
    monkeypatch.setattr(agent_mcp, "_make_stdio_connector", connector)
    monkeypatch.setattr(agent_mcp, "_run_on_mcp_loop", run_here)
    monkeypatch.setattr(agent_mcp, "reserve_server_for_host", reserve)
    monkeypatch.setattr(security.extensions, "mcp_registration_is_approved", lambda descriptor: True)
    monkeypatch.setattr(security.runtime, "session_permission_mode", lambda owner: "full_access")
    monkeypatch.setattr(host_tool_registry, "host_tool_invokers", host_tool_registry.HostToolInvokerRegistry())
    return calls, response, launch_configs, configs


@pytest.mark.parametrize("backend", ["native", "mcp"])
@pytest.mark.parametrize("status,stable,expected", [("satisfied", True, "completed"), ("unsatisfied", False, "failed"), ("unknown", False, "failed"), ("satisfied", False, "failed")])
def test_one_action_followed_by_same_window_lightweight_verification(provider, backend, status, stable, expected):
    calls, response, _, _ = provider
    response.update(status=status, stable=stable)
    service = ExecutionService()
    manager = ComputerUseManager(service)
    async def run():
        try:
            assert (await service.call(manager.configure, True, backend, save=False))["state"] == "ready"
            name = next(key for key, tool in manager.names.items() if tool == "click")
            context = SimpleNamespace(session_id="owner", service={"tool_name": name,
                "security_context": SimpleNamespace(mode="full_access"), "image_input_enabled": False, "model": "text"}.__getitem__)
            outcome = await manager.invoke(context, {"target": {"kind": "window", "pid": 123, "window_id": 456}, "x": 1, "y": 2,
                "session": "work", "_verify": {"expect": [{"element": {"selector": {"label_contains": "Logs"}, "exists": True}}]}})
            assert outcome.kind.value == expected
            assert [name for name, _ in calls] == ["click", "verify_state"]
            assert "_verify" not in calls[0][1]
            assert calls[1][1]["pid"] == 123 and calls[1][1]["window_id"] == 456 and calls[1][1]["session"] == "work"
            assert calls[1][1]["include_screenshot"] is False and calls[1][1]["timeout_ms"] == 1000
            actual_status = "unknown" if status == "satisfied" and not stable else status
            assert outcome.metadata["computer_use"]["structuredContent"]["host_verification"]["status"] == actual_status
            assert "POSTCONDITION: " + actual_status in outcome.content
            if expected == "failed":
                assert outcome.code in {"postcondition_unsatisfied", "postcondition_unknown"}
        finally:
            await service.call(manager.stop)
            await service.shutdown()
    asyncio.run(run())


def test_refusal_and_ended_session_do_not_retry_or_start_session(provider):
    calls, response, _, _ = provider
    response["action_error"] = True
    service = ExecutionService()
    manager = ComputerUseManager(service)
    async def run():
        try:
            await service.call(manager.configure, True, save=False)
            for original, args in [("click", {"pid": 1, "window_id": 2, "_verify": {"expect": [{}]}}), ("list_apps", {})]:
                name = next(key for key, tool in manager.names.items() if tool == original)
                context = SimpleNamespace(session_id="owner", service={"tool_name": name,
                    "security_context": SimpleNamespace(mode="full_access"), "image_input_enabled": False, "model": "text"}.__getitem__)
                outcome = await manager.invoke(context, args)
                assert outcome.code == ("background_unavailable" if original == "click" else "session_ended")
                assert "foreground permission" in outcome.content if original == "click" else "WITHOUT a session label" in outcome.content
            assert [name for name, _ in calls] == ["click", "list_apps"]
        finally:
            await service.call(manager.stop)
            await service.shutdown()
    asyncio.run(run())


@pytest.mark.parametrize("backend", ["native", "mcp"])
def test_observation_exception_keeps_delivery_receipt_and_does_not_replay(provider, backend):
    calls, response, _, _ = provider
    response["verify_error"] = True
    service = ExecutionService()
    manager = ComputerUseManager(service)
    async def run():
        try:
            await service.call(manager.configure, True, backend, save=False)
            name = next(key for key, tool in manager.names.items() if tool == "click")
            context = SimpleNamespace(session_id="owner", service={"tool_name": name,
                "security_context": SimpleNamespace(mode="full_access"), "image_input_enabled": False, "model": "text"}.__getitem__)
            outcome = await manager.invoke(context, {"pid": 1, "window_id": 2, "_verify": {"expect": [{}]}})
            assert outcome.code == "postcondition_unknown"
            assert "Posted click" in outcome.content and "observation transport lost" in outcome.content
            assert "POSTCONDITION: unknown" in outcome.content
            assert [name for name, _ in calls] == ["click", "verify_state"]
        finally:
            await service.call(manager.stop)
            await service.shutdown()
    asyncio.run(run())


@pytest.mark.parametrize("arguments", [
    {"pid": 1, "window_id": 2, "_verify": {"expect": [], "timeout_ms": 0}},
    {"pid": 1, "window_id": 2, "_verify": {"expect": [{}], "timeout_ms": 0, "stable_samples": 2}},
    {"scope": "desktop", "_verify": {"expect": [{}]}},
    {"pid": 1, "window_id": 2, "_verify": {"expect": [{}], "pid": 3}},
])
def test_invalid_postcondition_never_sends_input(provider, arguments):
    calls, _, _, _ = provider
    service = ExecutionService()
    manager = ComputerUseManager(service)
    async def run():
        try:
            await service.call(manager.configure, True, save=False)
            name = next(key for key, tool in manager.names.items() if tool == "click")
            with pytest.raises(ValueError):
                await service.call(manager._raw_call, name, arguments)
            assert calls == []
        finally:
            await service.call(manager.stop)
            await service.shutdown()
    asyncio.run(run())


def test_mcp_profile_grant_is_opt_in_and_does_not_mutate_config(provider, monkeypatch):
    import security.extensions
    _, _, launched, configs = provider
    service = ExecutionService()
    manager = ComputerUseManager(service)
    async def run():
        try:
            await service.call(manager.configure, True, "mcp", save=False)
            assert launched[-1]["args"] == ["mcp"]
            await service.call(manager.configure, True, "mcp", save=False, allow_existing_profile=True)
            assert launched[-1]["args"] == ["mcp", "--grant", "existing-profile"]
            assert configs["cua-driver-mcp"]["args"] == ["mcp"]
            assert manager.status()["allow_existing_profile"] is True
            monkeypatch.setattr(security.extensions, "mcp_registration_is_approved", lambda descriptor: descriptor["config_digest"] == security.extensions.mcp_descriptor("cua-driver-mcp", configs["cua-driver-mcp"])["config_digest"])
            assert (await service.call(manager.configure, True, "mcp", save=False, allow_existing_profile=True))["state"] == "error"
            assert "exact configuration" in manager.error and len(launched) == 2
            with pytest.raises(ValueError):
                await service.call(manager.configure, True, "native", save=False, allow_existing_profile=True)
            with pytest.raises(ValueError):
                await service.call(manager.configure, True, "mcp", save=False, allow_existing_profile="true")
        finally:
            await service.call(manager.stop)
            await service.shutdown()
    asyncio.run(run())


def test_structured_elements_keep_tokens_indices_and_completeness_before_large_tree():
    tree = "[23] Button Export\n" * 2000
    raw = {"content": [{"type": "text", "text": "pid=1\n" + tree}], "structuredContent": {
        "snapshot_id": "snapshot", "elements_complete": False, "total_element_count": 400,
        "returned_element_count": 1, "elements": [{"element_index": 23, "element_token": "snapshot:23", "role": "Button", "label": "Export"}], "tree_markdown": tree}}
    projected = project_result(raw, "get_window_state", {})
    text = "\n".join(part["text"] for part in projected["content"])
    assert '"snapshot_id":"snapshot"' in text[:1000] and '"elements_complete":false' in text[:1000]
    assert '"element_index":23' in text and '"element_token":"snapshot:23"' in text
    assert "cannot prove absence" in text and len(text) < 2500
    assert raw["content"][0]["text"].endswith(tree)  # canonical data remains unchanged


def test_delivery_receipt_and_driver_failure_code_are_visible():
    raw = SimpleNamespace(model_dump=lambda **kw: {"content": [{"type": "text", "text": "Posted click"}],
        "structuredContent": {"verified": False, "effect": "unverifiable", "path": "post_message"}})
    text = project_result(raw, "click", {})["content"][0]["text"]
    assert "DELIVERY ONLY" in text and '"verified":false' in text
    hint = project_result({"isError": True, "content": [], "structuredContent": {"code": "browser_consent_required"}}, "get_browser_state", {})
    assert "Computer Use > MCP" in hint["content"][0]["text"]
    assert {"list_apps", "verify_state"} <= READ_TOOLS


def test_screenshot_mapping_accounts_for_store_and_request_resizes(tmp_path):
    from agent_mcp import format_call_tool_result
    from attachments.local import LocalAttachmentStore
    from attachments.types import ImageRequestPolicy
    from attachments.messages_text import request_image_handle_text
    store = LocalAttachmentStore(tmp_path, normalization_policy=ImageRequestPolicy(max_pixels=100 * 100))
    image = BytesIO()
    Image.new("RGB", (2560, 1504), "blue").save(image, format="PNG")
    content = format_call_tool_result({"content": [{"type": "image", "data": base64.b64encode(image.getvalue()).decode(), "mimeType": "image/png"}]},
        image_enabled=True, attachment_store=store, image_source={"kind": "computer_use", "coordinateSpace": "window_screenshot"})
    ref = content[0]["attachment"]
    assert ref["width"] < 2560 and ref["source"]["kind"] == "computer_use"
    version = store.read_request_image_sync(ref, ImageRequestPolicy(max_pixels=40 * 40))
    hint = request_image_handle_text(ref, version, store.image_host_path(ref))
    assert "driver image 2560x1504px" in hint
    assert f"x*2560/{version.width}" in hint and f"y*1504/{version.height}" in hint
    assert "DPI scaling again" in hint


def test_browser_screenshots_do_not_claim_native_window_coordinates():
    from attachments.messages_text import request_image_handle_text
    from execution_services.computer_results import image_source
    ref = {"attachmentId": "image", "width": 1600, "height": 900, "mediaType": "image/png",
           "source": image_source("get_browser_state", {})}
    text = request_image_handle_text(ref, SimpleNamespace(width=800, height=450), "preview.png")
    assert "use DOM refs" in text and "not native window coordinates" in text
    assert "x*1600/800" not in text


def test_input_and_postcondition_are_serialized_against_other_sessions(provider, monkeypatch):
    service = ExecutionService()
    manager = ComputerUseManager(service)
    async def run():
        try:
            await manager.configure(True, save=False)
            action_started, action_release = asyncio.Event(), asyncio.Event()
            check_started, check_release = asyncio.Event(), asyncio.Event()
            order = []
            async def call(original, arguments):
                order.append(original)
                if original == "click":
                    action_started.set()
                    await action_release.wait()
                    return {"content": [], "structuredContent": {"verified": False}}
                if original == "verify_state":
                    check_started.set()
                    await check_release.wait()
                    return {"content": [], "structuredContent": {"status": "satisfied", "stable": True}}
                return {"content": []}
            monkeypatch.setattr(manager, "_call_driver", call)
            names = {value: key for key, value in manager.names.items()}
            action = asyncio.create_task(manager._raw_call(names["click"], {"pid": 1, "window_id": 2, "_verify": {"expect": [{}]}}))
            await action_started.wait()
            other = asyncio.create_task(manager._raw_call(names["list_apps"], {}))
            await asyncio.sleep(0)
            action_release.set()
            await check_started.wait()
            assert order == ["click", "verify_state"] and not other.done()
            check_release.set()
            await asyncio.gather(action, other)
            assert order == ["click", "verify_state", "list_apps"]
            assert manager.pending == set()
        finally:
            await manager.stop()
            await service.shutdown()
    asyncio.run(run())


def test_provider_stop_cancels_admitted_and_queued_calls_without_replay(provider, monkeypatch):
    service = ExecutionService()
    manager = ComputerUseManager(service)
    async def run():
        try:
            await manager.configure(True, save=False)
            entered = asyncio.Event()
            calls = []
            async def call(original, arguments):
                calls.append(original)
                entered.set()
                await asyncio.Event().wait()
            monkeypatch.setattr(manager, "_call_driver", call)
            names = {value: key for key, value in manager.names.items()}
            action = asyncio.create_task(manager._raw_call(names["click"], {"pid": 1, "window_id": 2}))
            await entered.wait()
            queued = asyncio.create_task(manager._raw_call(names["list_apps"], {}))
            await asyncio.sleep(0)
            await manager.stop()
            settled = await asyncio.gather(action, queued, return_exceptions=True)
            assert all(isinstance(result, asyncio.CancelledError) for result in settled)
            assert calls == ["click"] and manager.pending == set() and manager.state == "disabled"
        finally:
            await service.shutdown()
    asyncio.run(run())


def test_queued_invocation_rechecks_permission_mode_before_input(provider, monkeypatch):
    import security.runtime
    service = ExecutionService()
    manager = ComputerUseManager(service)
    async def run():
        try:
            await manager.configure(True, save=False)
            original = next(key for key, tool in manager.names.items() if tool == "click")
            mode = ["full_access"]
            monkeypatch.setattr(security.runtime, "session_permission_mode", lambda owner: mode[0])
            await manager._call_gate.acquire()
            queued = asyncio.create_task(manager._raw_call(original, {"pid": 1, "window_id": 2}, admitted_mode=("owner", "full_access")))
            await asyncio.sleep(0)
            mode[0] = "read_only"
            manager._call_gate.release()
            with pytest.raises(PermissionError, match="queued"):
                await queued
            assert provider[0] == []
        finally:
            await manager.stop()
            await service.shutdown()
    asyncio.run(run())


def test_profile_setting_api_origin_validation_and_startup_restore(provider, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import execution_services.computer as computer
    import execution_services.jobs as jobs
    import plugins.host
    import security.runtime
    from plugins import load_plugin
    from plugins.host import _module
    saved = {}
    monkeypatch.setattr(security.runtime, "security_store", lambda: SimpleNamespace(
        set_text_setting=lambda key, value: saved.update({key: value}), get_text_setting=lambda key, default: saved.get(key, default)))
    service = ExecutionService()
    manager = ComputerUseManager(service)
    monkeypatch.setattr(computer, "_MANAGER", manager)
    monkeypatch.setattr(jobs, "_SERVICE", service)
    monkeypatch.setattr(plugins.host, "bundled_host_plugin_enabled", lambda name: True)
    plugin = load_plugin(Path(__file__).resolve().parents[1] / "plugins" / "computer-use")
    module = _module(plugin)
    app = FastAPI()
    module.install(app, {"session_manager": None}, plugin)
    headers = {"Origin": "http://testserver"}
    async def cleanup():
        await service.call(manager.stop)
        await service.shutdown()
    try:
        with TestClient(app) as client:
            assert client.post("/api/computer-use", json={"enabled": True, "provider": "mcp", "allow_existing_profile": True}).status_code == 403
            assert saved == {}
            assert client.post("/api/computer-use", headers=headers, json={"enabled": True, "provider": "mcp", "allow_existing_profile": "true"}).status_code == 422
            result = client.post("/api/computer-use", headers=headers, json={"enabled": True, "provider": "mcp", "allow_existing_profile": True})
            assert result.json()["state"] == "ready" and result.json()["allow_existing_profile"] is True
            assert json.loads(saved["computer_use"])["allow_existing_profile"] is True
            asyncio.run(service.call(manager.stop))
            asyncio.run(module.start({"session_manager": None}, plugin))
            assert client.get("/api/computer-use").json()["allow_existing_profile"] is True
            assert provider[2][-1]["args"] == ["mcp", "--grant", "existing-profile"]
    finally:
        asyncio.run(cleanup())
