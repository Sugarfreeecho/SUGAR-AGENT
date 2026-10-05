"""Evidence/coordinate regressions from c5caf529; no desktop input is sent."""
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
from execution_services.computer import ComputerUseManager
from execution_services.computer_policy import (RecordingEvidence, fixed_window_preview,
    normalize_receipt, repair_cursor_null_position, validate_replay, write_recording_manifest,
    record_window_mapping)
from execution_services.computer_results import image_source, project_result
from execution_services.jobs import ExecutionService
from tests.test_computer_use_feedback import provider


def screenshot(width=800, height=1003):
    stream = BytesIO()
    Image.new("RGB", (width, height), "white").save(stream, format="PNG")
    return {"content": [{"type": "image", "data": base64.b64encode(stream.getvalue()).decode(), "mimeType": "image/png"}],
            "structuredContent": {"screenshot_width": width, "screenshot_height": height}}


def add_tool(manager, tool, properties):
    name = next(iter(manager.names)).rsplit("__", 1)[0] + "__" + tool
    manager.names[name] = tool
    manager.catalog += ({"function": {"name": name, "parameters": {"type": "object", "properties": properties, "additionalProperties": False}}},)
    return name


@pytest.mark.parametrize("backend", ["native", "mcp"])
def test_preview_size_changes_cannot_change_driver_click_coordinates(provider, monkeypatch, backend):
    service = ExecutionService()
    manager = ComputerUseManager(service)
    calls = []
    async def run():
        try:
            await manager.configure(True, backend, save=False)
            shot = add_tool(manager, "get_window_state", {"pid": {"type": "integer"}, "window_id": {"type": "integer"}, "max_dimension": {"type": "integer"}})
            click = next(key for key, value in manager.names.items() if value == "click")
            ratio = [1]
            async def driver(tool, args):
                calls.append((tool, dict(args)))
                if tool == "get_window_state":
                    # Emulate the upstream ratio registry: per-call small
                    # capture used to change the next click and replay point.
                    ratio[0] = 1003 / min(1003, args.get("max_dimension", 1568))
                    return screenshot()
                return {"content": [], "structuredContent": {"landed_x": args["x"] * ratio[0], "landed_y": args["y"] * ratio[0]}}
            monkeypatch.setattr(manager, "_call_driver", driver)
            points = []
            for maximum in (700, 1200, 900):
                observed = await manager._raw_call(shot, {"pid": 1, "window_id": 2, "max_dimension": maximum})
                mapping = observed["structuredContent"]["coordinate_mapping"]
                assert mapping["driver_width"] == 800 and mapping["driver_height"] == 1003
                assert max(mapping["preview_width"], mapping["preview_height"]) <= maximum
                result = await manager._raw_call(click, {"pid": 1, "window_id": 2, "x": 302, "y": 650})
                points.append(result["structuredContent"])
            assert points == [{"landed_x": 302, "landed_y": 650}] * 3
            assert all("max_dimension" not in args for tool, args in calls if tool == "get_window_state")
        finally:
            await manager.stop()
            await service.shutdown()
    asyncio.run(run())


def test_preview_attachment_maps_directly_to_fixed_driver_pixels():
    from attachments.messages_text import request_image_handle_text
    raw = fixed_window_preview(screenshot(), 700)
    ref = {"attachmentId": "image", "width": 558, "height": 700, "mediaType": "image/png",
           "source": image_source("get_window_state", {}, raw["structuredContent"])}
    hint = request_image_handle_text(ref, SimpleNamespace(width=279, height=350), "preview.png")
    assert "driver image 800x1003px" in hint
    assert "x*800/279" in hint and "y*1003/350" in hint


@pytest.mark.parametrize("union", [False, True])
@pytest.mark.parametrize("extra_invalid", [False, True])
def test_only_nullable_cursor_position_mismatch_is_recovered(extra_invalid, union):
    schema = {"type": "object", "properties": {"position": {"type": "object"}, "enabled": {"type": "boolean"}},
              "required": ["position", "enabled"], "additionalProperties": False}
    if union:
        schema = {"type": "object", "anyOf": [schema, {"type": "object", "anyOf": [
            {"required": ["refusal"]}, {"required": ["status"]}, {"required": ["code"]}]}]}
    value = {"position": None, "enabled": "bad" if extra_invalid else True}
    raw = {"isError": True, "structuredContent": {"code": "tool_output_invalid", "invalid_output": value}}
    repaired = repair_cursor_null_position(raw, schema)
    assert repaired["isError"] is extra_invalid
    if not extra_invalid:
        assert repaired["structuredContent"]["position"] is None
        assert repaired["structuredContent"]["host_compatibility"]["driver_error"] == raw["structuredContent"]


def test_recording_conflict_is_unknown_not_cached_fake_success():
    evidence = RecordingEvidence()
    start = {"structuredContent": {"enabled": True, "recording": True, "output_dir": "rec"}}
    evidence.observe(start, "start_recording", "owner")
    disabled = {"structuredContent": {"enabled": False, "recording": False}}
    unknown = evidence.observe(disabled, "get_recording_state", "owner")
    assert unknown["isError"] and unknown["structuredContent"]["code"] == "recording_state_conflict"
    assert unknown["structuredContent"]["recording"] is None
    assert unknown["structuredContent"]["driver_state"] == disabled["structuredContent"]
    assert evidence.observe(disabled, "get_recording_state", "other")["structuredContent"]["code"] == "recording_state_conflict"
    evidence.observe(disabled, "stop_recording", "owner")
    assert evidence.observe(disabled, "get_recording_state", "owner")["structuredContent"]["enabled"] is False


@pytest.mark.parametrize("changed", [{"enabled": False}, {"output_dir": "rec3"}, {"owner": "another-client"}, {"next_turn": 1}])
def test_live_recording_getter_checks_identity_and_counter_not_only_enabled(changed):
    evidence = RecordingEvidence()
    start = {"enabled": True, "recording": True, "output_dir": "rec4", "owner": "mcp-current", "next_turn": 1}
    evidence.observe({"structuredContent": start}, "start_recording", "owner")
    evidence.observe({"structuredContent": {}}, "click", "owner")
    live = {**start, "next_turn": 2, **changed}
    result = evidence.observe({"structuredContent": live}, "get_recording_state", "another-agent")
    assert result["isError"] and result["structuredContent"]["code"] == "recording_state_conflict"
    assert result["structuredContent"]["driver_state"] == live
    assert result["structuredContent"]["last_control_receipt"] == start


def test_stale_enabled_getter_after_stop_is_also_unknown():
    evidence = RecordingEvidence()
    evidence.observe({"structuredContent": {"enabled": False, "output_dir": None}}, "stop_recording", "owner")
    result = evidence.observe({"structuredContent": {"enabled": True, "output_dir": "old"}}, "get_recording_state", "owner")
    assert result["isError"] and result["structuredContent"]["mismatches"] == ["enabled"]


@pytest.mark.parametrize("tool", ["type_text", "press_key", "hotkey"])
def test_failed_delivery_is_explicit_without_retry(tool):
    raw = {"content": [], "structuredContent": {"effect": "unverifiable", "escalation": {"reason": "delivery_failed"}}}
    result = normalize_receipt(raw, tool)
    assert result["isError"] and result["structuredContent"]["code"] == "input_delivery_unconfirmed"
    verified = {**raw, "structuredContent": {**raw["structuredContent"], "host_verification": {"status": "satisfied", "stable": True}}}
    assert not normalize_receipt(verified, tool).get("isError")


def test_nested_browser_refusal_becomes_failed_outcome_and_shows_actionable_hint():
    raw = {"content": [], "structuredContent": {"status": "refused", "refusal": {"code": "browser_consent_required"}}}
    normalized = normalize_receipt(raw, "get_browser_state")
    assert normalized["isError"] and normalized["structuredContent"]["code"] == "browser_consent_required"
    text = project_result(normalized, "get_browser_state", {})["content"][0]["text"]
    assert "Allow access to signed-in browser profiles" in text


def test_unverified_menu_receipt_and_verified_predicate_are_not_confused():
    raw = {"content": [{"type": "text", "text": "✅ Shown menu"}], "structuredContent": {"effect": "unverifiable"}}
    text = "\n".join(part["text"] for part in project_result(raw, "right_click", {})["content"])
    assert "UNVERIFIED DRIVER RECEIPT" in text and "✅ Shown menu" not in text
    raw["structuredContent"]["host_verification"] = {"status": "satisfied", "stable": True}
    text = "\n".join(part["text"] for part in project_result(raw, "right_click", {})["content"])
    assert "POSTCONDITION: satisfied" in text and "DELIVERY ONLY:" not in text


def test_replay_rejects_legacy_and_changed_config_and_snapshot_tokens(tmp_path):
    config = {"max_image_dimension": 1568}
    assert validate_replay(tmp_path, config)["structuredContent"]["code"] == "trajectory_coordinate_contract_missing"
    write_recording_manifest(tmp_path, config)
    assert validate_replay(tmp_path, {"max_image_dimension": 900})["structuredContent"]["code"] == "trajectory_coordinate_contract_changed"
    turn = tmp_path / "turn-00001"
    turn.mkdir()
    (turn / "action.json").write_text(json.dumps({"tool": "click", "arguments": {"element_token": "stale:5"}}))
    assert validate_replay(tmp_path, config)["structuredContent"]["code"] == "trajectory_snapshot_context_stale"
    (turn / "action.json").write_text(json.dumps({"tool": "click", "arguments": {"pid": 1, "window_id": 2, "x": 5, "y": 5}}))
    assert validate_replay(tmp_path, config)["structuredContent"]["code"] == "trajectory_window_mapping_missing"
    record_window_mapping(tmp_path, "1:2", {"driver_width": 800, "driver_height": 1003})
    assert validate_replay(tmp_path, config) is None


def test_replay_handles_uncapped_images_and_rejects_geometry_mutations(tmp_path):
    config = {"max_image_dimension": 0}
    write_recording_manifest(tmp_path, config)
    assert validate_replay(tmp_path, config) is None
    mapping = {"driver_width": 800, "driver_height": 1003}
    record_window_mapping(tmp_path, "1:2", mapping)
    record_window_mapping(tmp_path, "1:2", {**mapping, "driver_height": 900})
    assert validate_replay(tmp_path, config)["structuredContent"]["code"] == "trajectory_window_geometry_changed"
    write_recording_manifest(tmp_path, config)
    record_window_mapping(tmp_path, "1:2", mapping)
    record_window_mapping(tmp_path, "1:3", mapping)
    assert validate_replay(tmp_path, config)["structuredContent"]["code"] == "trajectory_shared_pid_coordinates"
    write_recording_manifest(tmp_path, config)
    turn = tmp_path / "turn-00001"
    turn.mkdir()
    (turn / "action.json").write_text(json.dumps({"tool": "set_window_frame", "arguments": {}}))
    assert validate_replay(tmp_path, config)["structuredContent"]["code"] == "trajectory_coordinate_mutation"


@pytest.mark.parametrize("invalid", [[], {"windows": {}}, {"policy": "fixed_driver_image_v1", "max_image_dimension": 1568, "windows": {"bad": {}}}])
def test_invalid_replay_contract_is_refused_before_native_dispatch(tmp_path, invalid):
    from execution_services.computer_policy import RECORDING_MANIFEST
    (tmp_path / RECORDING_MANIFEST).write_text(json.dumps(invalid))
    assert validate_replay(tmp_path, {"max_image_dimension": 1568})["isError"]


@pytest.mark.parametrize("backend", ["native", "mcp"])
def test_recording_contract_and_control_ownership(provider, monkeypatch, tmp_path, backend):
    service = ExecutionService()
    manager = ComputerUseManager(service)
    calls = []
    async def run():
        try:
            await manager.configure(True, backend, save=False)
            start = add_tool(manager, "start_recording", {"dir": {"type": "string"}})
            stop = add_tool(manager, "stop_recording", {})
            state = add_tool(manager, "get_recording_state", {})
            add_tool(manager, "get_config", {})
            shot = add_tool(manager, "get_window_state", {"pid": {"type": "integer"}, "window_id": {"type": "integer"}})
            click = next(key for key, value in manager.names.items() if value == "click")
            async def driver(tool, args):
                calls.append(tool)
                if tool == "get_config":
                    return {"structuredContent": {"max_image_dimension": 1568}}
                if tool == "get_window_state":
                    return screenshot()
                if tool == "start_recording":
                    return {"structuredContent": {"enabled": True, "output_dir": str(tmp_path)}}
                if tool in {"stop_recording", "get_recording_state"}:
                    return {"structuredContent": {"enabled": False}}
                return {"structuredContent": {"effect": "unverifiable"}}
            monkeypatch.setattr(manager, "_call_driver", driver)
            await manager._raw_call(start, {"dir": str(tmp_path)}, admitted_mode=("owner", "full_access"))
            await manager._raw_call(shot, {"pid": 1, "window_id": 2}, admitted_mode=("owner", "full_access"))
            await manager._raw_call(click, {"pid": 1, "window_id": 2, "x": 5, "y": 5}, admitted_mode=("owner", "full_access"))
            assert validate_replay(tmp_path, {"max_image_dimension": 1568}) is None
            before = list(calls)
            rejected = await manager._raw_call(stop, {}, admitted_mode=("other", "full_access"))
            assert rejected["structuredContent"]["code"] == "recording_owned_by_other_agent" and calls == before
            unknown = await manager._raw_call(state, {}, admitted_mode=("owner", "full_access"))
            assert unknown["structuredContent"]["code"] == "recording_state_conflict"
            await manager._raw_call(stop, {}, admitted_mode=("owner", "full_access"))
            assert not (await manager._raw_call(state, {}, admitted_mode=("owner", "full_access"))).get("isError")
        finally:
            await manager.stop()
            await service.shutdown()
    asyncio.run(run())


def test_permission_is_rechecked_after_readonly_preflight(provider, monkeypatch):
    import security.runtime
    service = ExecutionService()
    manager = ComputerUseManager(service)
    mode = ["full_access"]
    calls = []
    monkeypatch.setattr(security.runtime, "session_permission_mode", lambda owner: mode[0])
    async def run():
        try:
            await manager.configure(True, save=False)
            start = add_tool(manager, "start_recording", {"dir": {"type": "string"}})
            add_tool(manager, "get_config", {})
            async def driver(tool, args):
                calls.append(tool)
                mode[0] = "restricted"
                return {"structuredContent": {"max_image_dimension": 1568}}
            monkeypatch.setattr(manager, "_call_driver", driver)
            with pytest.raises(PermissionError, match="during computer preflight"):
                await manager._raw_call(start, {"dir": "unused"}, admitted_mode=("owner", "full_access"))
            assert calls == ["get_config"]
        finally:
            await manager.stop()
            await service.shutdown()
    asyncio.run(run())


def test_replay_checks_geometry_before_dispatch(provider, monkeypatch, tmp_path):
    service = ExecutionService()
    manager = ComputerUseManager(service)
    calls = []
    config = {"max_image_dimension": 1568}
    write_recording_manifest(tmp_path, config)
    record_window_mapping(tmp_path, "1:2", {"driver_width": 800, "driver_height": 1003})
    async def run():
        try:
            await manager.configure(True, save=False)
            replay = add_tool(manager, "replay_trajectory", {"dir": {"type": "string"}})
            add_tool(manager, "get_config", {})
            async def driver(tool, args):
                calls.append(tool)
                return {"structuredContent": config} if tool == "get_config" else screenshot(800, 900)
            monkeypatch.setattr(manager, "_call_driver", driver)
            refused = await manager._raw_call(replay, {"dir": str(tmp_path)})
            assert refused["structuredContent"]["code"] == "trajectory_window_geometry_changed"
            assert calls == ["get_config", "get_window_state"]
        finally:
            await manager.stop()
            await service.shutdown()
    asyncio.run(run())


@pytest.mark.parametrize("capture_failed", [False, True])
def test_real_mcp_payload_shape_tracks_receipt_and_maps_cross_agent_actions(provider, monkeypatch, tmp_path, capture_failed):
    from mcp.types import CallToolResult, TextContent
    from host_tool_registry import HostToolInvocationContext
    service = ExecutionService()
    manager = ComputerUseManager(service)
    calls = []
    async def run():
        try:
            await manager.configure(True, "mcp", save=False)
            start = add_tool(manager, "start_recording", {"output_dir": {"type": "string"}})
            state = add_tool(manager, "get_recording_state", {})
            shot = add_tool(manager, "get_window_state", {"pid": {"type": "integer"}, "window_id": {"type": "integer"}})
            add_tool(manager, "get_config", {})
            click = next(key for key, value in manager.names.items() if value == "click")
            control = {"enabled": True, "recording": True, "output_dir": str(tmp_path), "owner": "mcp-test-client",
                       "next_turn": 1, "video_active": False, "last_error": None, "last_video_path": None}
            async def driver(tool, args):
                calls.append(tool)
                if tool == "get_window_state":
                    assert args["include_accessibility_tree"] is False and args["include_screenshot"] is True
                    if capture_failed:
                        return {"isError": True, "structuredContent": {"screenshot_error": "window minimized"}}
                    return screenshot()
                data = {"max_image_dimension": 1568} if tool == "get_config" else (
                    control if tool == "start_recording" else {**control, "output_dir": "previous-recording"} if tool == "get_recording_state" else {"effect": "unverifiable"})
                return CallToolResult(content=[TextContent(type="text", text="driver receipt")], structuredContent=data, isError=False)
            monkeypatch.setattr(manager, "_call_driver", driver)
            async def invoke(name, args, owner="owner"):
                context = HostToolInvocationContext(session_id=owner, services={"tool_name": name,
                    "security_context": SimpleNamespace(mode="full_access"), "image_input_enabled": False, "model": "text"})
                return await manager.invoke(context, args)
            outcome = await invoke(start, {"output_dir": str(tmp_path)})
            assert outcome.metadata["computer_use"]["structuredContent"]["host_recording_evidence"]["control_tracked"]
            assert manager.status()["recording_evidence"]["acknowledged_enabled"] is True
            clicked = await invoke(click, {"pid": 8620, "window_id": 23333100, "x": 302, "y": 650}, "other-agent")
            contract = json.loads((tmp_path / "myagent-coordinate-contract.json").read_text())
            if capture_failed:
                assert calls == ["get_config", "start_recording", "get_window_state"]
                assert clicked.code == "recording_coordinate_observation_failed" and not contract["windows"]
            else:
                assert calls == ["get_config", "start_recording", "get_window_state", "click"]
                assert "8620:23333100" in contract["windows"]
            assert (await invoke(state, {})).code == "recording_state_conflict"
        finally:
            await manager.stop()
            await service.shutdown()
    asyncio.run(run())


@pytest.mark.parametrize("backend", ["native", "mcp"])
def test_cua_reads_cannot_overtake_control_or_input_during_streaming(provider, backend):
    import host_tool_registry
    service = ExecutionService()
    manager = ComputerUseManager(service)
    async def run():
        try:
            await manager.configure(True, backend, save=False)
            for name, original in manager.names.items():
                policy = host_tool_registry.host_tool_invokers.policy(name)
                assert policy.parallel_safe is False
                assert policy.early_stream_safe is False
                assert policy.effect == ("external_write" if original == "click" else "read")
        finally:
            await manager.stop()
            await service.shutdown()
    asyncio.run(run())


def test_satisfied_driver_predicate_never_claims_screenshot_consistency(provider, monkeypatch):
    service = ExecutionService()
    manager = ComputerUseManager(service)
    calls = []
    async def run():
        try:
            await manager.configure(True, save=False)
            click = next(key for key, value in manager.names.items() if value == "click")
            async def driver(tool, args):
                calls.append(tool)
                if tool == "click":
                    return {"structuredContent": {"effect": "unverifiable"}}
                assert args["include_screenshot"] is True
                return {**screenshot(), "structuredContent": {"status": "satisfied", "stable": True}}
            monkeypatch.setattr(manager, "_call_driver", driver)
            result = await manager._raw_call(click, {"pid": 1, "window_id": 2, "x": 5, "y": 5,
                "_verify": {"expect": [{"element": {"selector": {"label_contains": "7"}, "exists": True}}], "include_screenshot": True}})
            assert not result.get("isError") and calls == ["click", "verify_state"]
            assert result["structuredContent"]["host_verification"]["visual_consistency"] == "not_checked"
            projected = project_result(result, "click", {})
            assert "VISUAL CONSISTENCY NOT CHECKED" in projected["content"][0]["text"]
            assert any(part["type"] == "image" for part in projected["content"])
        finally:
            await manager.stop()
            await service.shutdown()
    asyncio.run(run())
