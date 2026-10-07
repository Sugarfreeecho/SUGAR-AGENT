"""Cua compatibility and evidence policy; never retries or invents UI success."""
from __future__ import annotations

import base64
from copy import deepcopy
from io import BytesIO
import json
import os
from pathlib import Path
import re

from .computer_results import result_dict, structured_result

COORDINATE_POLICY = "fixed_driver_image_v1"
RECORDING_MANIFEST = "myagent-coordinate-contract.json"
POLICY_REVISION = "recording-evidence-v2"


def window_geometry(data):
    bounds = data.get("window_bounds") or {}
    return {key: bounds[key] for key in ("width", "height") if key in bounds}


def failure(code, message, **evidence):
    return {"isError": True, "content": [{"type": "text", "text": message}],
            "structuredContent": {"code": code, **evidence}}


def fixed_window_preview(raw, maximum=None):
    """Resize only the returned preview, leaving the driver's capture ratio fixed."""
    from PIL import Image
    result = deepcopy(result_dict(raw))
    data = structured_result(result)
    if result.get("isError"):
        return result
    blocks = result.get("content") or []
    for index, part in enumerate(blocks):
        part = part if isinstance(part, dict) else part.model_dump(exclude_none=True)
        if part.get("type") != "image":
            continue
        with Image.open(BytesIO(base64.b64decode(part["data"]))) as source:
            width, height = source.size
            preview = source.copy()
        if maximum and max(preview.size) > maximum:
            preview.thumbnail((maximum, maximum), Image.Resampling.LANCZOS)
            stream = BytesIO()
            preview.save(stream, format="PNG")
            blocks[index] = {**part, "data": base64.b64encode(stream.getvalue()).decode("ascii"), "mimeType": "image/png"}
        data = {**data, "screenshot_width": preview.width, "screenshot_height": preview.height,
                "coordinate_mapping": {"policy": COORDINATE_POLICY, "driver_width": width, "driver_height": height,
                    "preview_width": preview.width, "preview_height": preview.height,
                    "window_geometry": window_geometry(data),
                    "preview_to_driver_x": width / preview.width, "preview_to_driver_y": height / preview.height}}
        result["structuredContent"] = data
        break
    return result


def repair_cursor_null_position(raw, output_schema):
    """Repair only the upstream read-only nullable-position contract mismatch."""
    from jsonschema import Draft202012Validator
    result = result_dict(raw)
    data = structured_result(result)
    value = data.get("invalid_output")
    if (not result.get("isError") or data.get("code") != "tool_output_invalid"
        or not isinstance(value, dict) or "position" not in value or value["position"] is not None
        or not isinstance(output_schema, dict)):
        return result
    if Draft202012Validator(output_schema).is_valid(value):
        return result
    schema = deepcopy(output_schema)
    # Published MCP schemas wrap the success payload and refusal payload in
    # anyOf. Validate the ENTIRE corrected union; removing the outer validation
    # error would also hide unrelated invalid fields in its success branch.
    branches = [schema, *schema.get("anyOf", [])]
    patched = False
    for branch in branches:
        if not isinstance(branch, dict):
            continue
        properties = branch.get("properties", {})
        position = properties.get("position", {})
        if (position.get("type") == "object" and "position" in branch.get("required", [])
            and properties.get("enabled", {}).get("type") == "boolean"):
            properties["position"] = {"anyOf": [position, {"type": "null"}]}
            patched = True
    if not patched or not Draft202012Validator(schema).is_valid(value):
        return result
    return {**result, "isError": False,
            "content": [{"type": "text", "text": "Read cursor state; position is unknown until the cursor first moves. Applied the validated upstream nullable-position compatibility fix."}],
            "structuredContent": {**value, "host_compatibility": {"fix": "nullable_cursor_position", "driver_error": data}}}


def normalize_receipt(raw, tool):
    result = result_dict(raw)
    data = structured_result(result)
    refusal = data.get("refusal") or data.get("error")
    if data.get("status") == "refused" or data.get("effect") == "refused":
        result = {**result, "isError": True,
                  "structuredContent": {**data, "code": data.get("code") or (refusal.get("code") if isinstance(refusal, dict) else None) or "computer_use_refused"}}
    escalation = data.get("escalation") or {}
    if (tool in {"type_text", "press_key", "hotkey"} and not result.get("isError")
        and escalation.get("reason") == "delivery_failed"
        and (data.get("host_verification") or {}).get("status") != "satisfied"):
        result = {**result, "isError": True,
                  "structuredContent": {**data, "code": "input_delivery_unconfirmed", "execution_state": "unknown"},
                  "content": list(result.get("content") or []) + [{"type": "text", "text": "The driver reports delivery_failed. Input effect is unconfirmed; no retry or foreground fallback was performed. Observe before deciding the next action."}]}
    return result


class RecordingEvidence:
    def __init__(self):
        self.receipt = None
        self.owner = None
        self.minimum_next_turn = 1

    def summary(self):
        return {"policy_revision": POLICY_REVISION, "control_tracked": self.receipt is not None,
                "acknowledged_enabled": (self.receipt or {}).get("enabled"),
                "output_dir": (self.receipt or {}).get("output_dir"), "agent_owner": self.owner,
                "minimum_next_turn": self.minimum_next_turn,
                "live_state_verified": False}

    @staticmethod
    def _path(value):
        if not isinstance(value, str):
            return value
        if value.startswith("\\\\?\\"):
            value = value[4:]
        return os.path.normcase(os.path.normpath(value))

    def observe(self, raw, tool, owner):
        result = result_dict(raw)
        data = structured_result(result)
        if not result.get("isError") and tool in {"start_recording", "stop_recording"}:
            self.receipt, self.owner = deepcopy(data), owner
            self.minimum_next_turn = data.get("next_turn", 1)
        if tool in {"click", "double_click", "right_click", "drag", "type_text", "press_key", "hotkey", "set_value", "scroll"} and (self.receipt or {}).get("enabled"):
            self.minimum_next_turn += 1
        if tool == "get_recording_state" and self.receipt and not result.get("isError"):
            mismatches = []
            if data.get("enabled") != self.receipt.get("enabled"):
                mismatches.append("enabled")
            if data.get("enabled") is True and self.receipt.get("enabled") is True:
                if self._path(data.get("output_dir")) != self._path(self.receipt.get("output_dir")):
                    mismatches.append("output_dir")
                if data.get("owner") != self.receipt.get("owner"):
                    mismatches.append("driver_owner")
                if type(data.get("next_turn")) is int and data["next_turn"] < self.minimum_next_turn:
                    mismatches.append("next_turn")
            if mismatches:
                # A cached acknowledgement is not proof the remote recorder is
                # still active. Keep both receipts and report uncertainty.
                return failure("recording_state_conflict", "The live recording getter conflicts with the last control acknowledgement or subsequent recorded actions (" + ", ".join(mismatches) + "). Recording state is UNKNOWN; inspect artifacts or explicitly stop_recording. No recording action was retried.",
                    recording=None, enabled=None, live_state_verified=False, mismatches=mismatches,
                    driver_state=data, last_control_receipt=self.receipt, host_recording_evidence=self.summary())
        if tool in {"start_recording", "stop_recording", "get_recording_state"}:
            result = {**result, "structuredContent": {**data, "host_recording_evidence": self.summary()}}
        return result


def write_recording_manifest(directory, config):
    path = Path(directory) / RECORDING_MANIFEST
    path.write_text(json.dumps({"policy": COORDINATE_POLICY, "max_image_dimension": config.get("max_image_dimension"), "windows": {}}, indent=2), encoding="utf-8")


def record_window_mapping(directory, key, mapping):
    path = Path(directory) / RECORDING_MANIFEST
    contract = json.loads(path.read_text(encoding="utf-8"))
    previous = contract["windows"].get(key)
    if previous and any(previous.get(field) != mapping.get(field) for field in ("driver_width", "driver_height", "window_geometry")):
        contract["geometry_changed"] = True
    contract["windows"][key] = mapping
    path.write_text(json.dumps(contract, indent=2), encoding="utf-8")


def validate_replay(directory, config):
    """Do not dispatch a legacy trajectory whose pixel space cannot be proven."""
    root = Path(directory)
    try:
        contract = json.loads((root / RECORDING_MANIFEST).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return failure("trajectory_coordinate_contract_missing", "No SugarAgent coordinate contract accompanies this recording. Legacy screenshot-scaled coordinates can drift; re-record through this host before replay. No action was dispatched.")
    if not isinstance(contract, dict) or not isinstance(contract.get("windows"), dict):
        return failure("trajectory_coordinate_contract_invalid", "The coordinate contract has an invalid structure. No action was dispatched.")
    maximum = config.get("max_image_dimension")
    if (contract.get("policy") != COORDINATE_POLICY or type(maximum) is not int or maximum < 0
        or contract.get("max_image_dimension") != config.get("max_image_dimension")):
        return failure("trajectory_coordinate_contract_changed", "The recording's driver image configuration differs from the current provider. Re-record before replay. No action was dispatched.")
    if contract.get("geometry_changed"):
        return failure("trajectory_window_geometry_changed", "Window geometry changed during recording. Re-record a stable window before replay. No action was dispatched.")
    pids = set()
    for key, mapping in contract["windows"].items():
        if (not re.fullmatch(r"[1-9][0-9]*:[0-9]+", key) or not isinstance(mapping, dict)
            or any(type(mapping.get(field)) is not int or mapping[field] <= 0 for field in ("driver_width", "driver_height"))):
            return failure("trajectory_coordinate_contract_invalid", "Invalid exact-window mapping in the coordinate contract. No action was dispatched.")
        pid = key.split(":")[0]
        if pid in pids:
            return failure("trajectory_shared_pid_coordinates", "The driver shares its screenshot scaling registry across windows with one PID. Split this recording by exact window before replay. No action was dispatched.")
        pids.add(pid)
    # Snapshot tokens and zoom contexts cannot survive recording/replay. The
    # native replay tool otherwise counts successful dispatch as task success.
    for turn in sorted(path for path in root.glob("turn-*") if path.is_dir()):
        try:
            action = json.loads((turn / "action.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return failure("trajectory_action_invalid", "Cannot validate a recorded action. No replay was dispatched.")
        if not isinstance(action, dict) or not isinstance(action.get("arguments"), dict) or not isinstance(action.get("tool"), str):
            return failure("trajectory_action_invalid", "Invalid recorded tool/arguments. No replay was dispatched.")
        args = action["arguments"]
        if action["tool"] in {"set_config", "set_window_frame", "replay_trajectory"}:
            return failure("trajectory_coordinate_mutation", "The trajectory changes coordinate configuration or geometry during replay. Perform those operations explicitly, then record a stable window. No action was dispatched.")
        if any(key in args for key in ("element_token", "element_index", "snapshot_id")) or args.get("from_zoom"):
            return failure("trajectory_snapshot_context_stale", "The trajectory contains snapshot/zoom-bound actions. Refresh the target and perform semantic actions explicitly; stale tokens cannot be replayed. No action was dispatched.")
        if any(key in args for key in ("x", "y", "from_x", "from_y", "to_x", "to_y")):
            target = args.get("target") or args
            if not isinstance(target, dict) or target.get("kind", args.get("scope", "window")) != "window":
                return failure("trajectory_window_mapping_missing", "Desktop pixel trajectories have no window coordinate evidence. No action was dispatched.")
            key = f"{target.get('pid')}:{target.get('window_id')}"
            if key not in contract.get("windows", {}):
                return failure("trajectory_window_mapping_missing", "A recorded pixel action has no exact-window coordinate evidence (desktop trajectories are not supported). No replay was dispatched.")
    return None


def replay_windows(directory):
    return json.loads((Path(directory) / RECORDING_MANIFEST).read_text(encoding="utf-8")).get("windows", {})
