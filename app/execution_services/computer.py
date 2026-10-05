"""One Cua provider slot, with transactional dynamic tool publication."""
from __future__ import annotations

import asyncio
import json
import os
import re
import threading
from copy import deepcopy

from tool_registry import ToolOutcome

GUIDANCE = (
    "Operate the host desktop. Discover the exact app/window and take a fresh window snapshot before acting. "
    "Use element_token from that snapshot or coordinates from its screenshot. New snapshots invalidate earlier tokens. "
    "Do not combine target with legacy pid/window_id. Prefer background delivery; refusal does not authorize a foreground retry. "
    "Verify the outcome from fresh state. After cancellation, observe before retrying: completed input is not rolled back. "
    "Other sessions may change the same desktop."
    " Computer Use calls preserve completed model-call order; even observation waits until the tool batch is complete. "
    " Read Cua structured status: verified:false is only delivery, not task success. "
    "Window actions accept optional _verify {expect, timeout_ms, stable_samples, include_screenshot}; "
    "it checks the same pid/window/session without replaying input, defaulting to no screenshot and a 1s wait. "
    "Prefer targeted query/tree-only snapshots or image-only snapshots instead of a full tree/image on every step. "
    "UIA evidence may be partial; an empty query does not prove absence. "
    "Screenshot attachments state the preview-to-driver coordinate mapping. Never scale by window_bounds or DPI again. "
    "Window max_dimension resizes only the host preview; driver coordinate space remains fixed. "
    "Replay dispatch counts do not prove semantic success, and legacy recordings without a coordinate contract are refused. "
    "Driver/UIA predicates and rendered pixels can disagree temporarily. For critical displayed values, combine _verify "
    "with a fresh screenshot (include_screenshot:true or a subsequent image-only observation) and inspect both. "
    "A satisfied predicate does not verify visual consistency; disagreement requires another observation, not another input. "
    "A named start_session does not revive implicit tools such as list_apps: use start_session({}) for those. "
    "Foreground input/bring_to_front can change focus and dismiss popups; obtain authorization and refresh afterward."
)
READ_TOOLS = {"get_desktop_state", "get_screen_size", "get_cursor_position", "list_windows",
              "get_window_state", "get_window_screenshot", "get_accessibility_tree", "get_agent_cursor_state",
              "list_apps", "verify_state", "get_session", "list_sessions", "get_session_state",
              "get_recording_state", "get_config", "health_report", "debug_window_info"}
WINDOW_ACTIONS = {"click", "double_click", "right_click", "drag", "type_text", "press_key",
                  "hotkey", "set_value", "scroll"}
_MANAGER = None
_LOCK = threading.Lock()


class ComputerUseManager:
    def __init__(self, service):
        self.service = service
        self.enabled = False
        self.provider = "native"
        self.server_alias = "cua-driver-mcp"
        self.driver = None
        self.server = None
        self.state = "disabled"
        self.error = ""
        self.catalog = ()
        self.names = {}
        self.pending = set()
        self.reserved_alias = ""
        self._gate = asyncio.Lock()
        self._call_gate = asyncio.Lock()
        self.allow_existing_profile = False
        self.output_schemas = {}
        self.window_images = {}
        from .computer_policy import RecordingEvidence
        self.recording = RecordingEvidence()

    def status(self):
        return {"enabled": self.enabled, "provider": self.provider,
                "server_alias": self.server_alias, "state": self.state, "error": self.error,
                "tool_count": len(self.catalog), "platform": os.name,
                "allow_existing_profile": self.allow_existing_profile,
                "recording_evidence": self.recording.summary()}

    def mcp_view(self):
        """Project the owned MCP connection/catalog into the settings inventory."""
        transport = self.server.connection_status() if self.server else {}
        connected = self.state == "ready" and bool(transport.get("connected"))
        enabled = connected and self._plugin_enabled()
        catalog, names = self.catalog, self.names
        return {
            "managed_by": "computer-use", "connected": connected,
            "discovered": bool(catalog), "tool_count": len(catalog),
            "error": self.error or transport.get("error", ""),
            "tools": [{"function_name": definition["function"]["name"],
                       "tool_name": names.get(definition["function"]["name"], definition["function"]["name"]),
                       "description": definition["function"].get("description", ""),
                       "enabled": enabled} for definition in catalog],
        }

    def settings(self):
        from security.runtime import security_store
        raw = security_store().get_text_setting("computer_use", "")
        if raw:
            try:
                value = json.loads(raw)
                if isinstance(value, dict):
                    return value
            except ValueError:
                pass
            self.error = "invalid persisted Computer Use settings"
            return {"enabled": False, "provider": "native"}
        return {"enabled": os.getenv("COMPUTER_USE_ENABLED", "0").lower() in {"1", "true", "yes"},
                "provider": os.getenv("COMPUTER_USE_PROVIDER", "native"),
                "server_alias": os.getenv("COMPUTER_USE_MCP_SERVER", "cua-driver-mcp")}

    async def configure(self, enabled, provider="native", server_alias="cua-driver-mcp", *, save=True,
                        allow_existing_profile=False):
        if not isinstance(provider, str) or provider not in {"native", "mcp"}:
            raise ValueError("computer provider must be native or mcp")
        if not isinstance(allow_existing_profile, bool):
            raise ValueError("allow_existing_profile must be a boolean")
        if allow_existing_profile and provider != "mcp":
            raise ValueError("existing-profile grant is supported only by the MCP provider")
        async with self._gate:
            await self._stop()
            self.provider, self.server_alias = provider, str(server_alias)
            self.enabled = bool(enabled)
            self.allow_existing_profile = allow_existing_profile
            self.error = ""
            if save:
                from security.runtime import security_store
                security_store().set_text_setting("computer_use", json.dumps({"enabled": self.enabled,
                    "provider": provider, "server_alias": self.server_alias,
                    "allow_existing_profile": self.allow_existing_profile}))
            if not enabled:
                return self.status()
            self.state = "starting"
            try:
                if provider == "native":
                    from cua_driver import CuaDriver
                    starter = asyncio.create_task(asyncio.to_thread(CuaDriver.create))
                    try:
                        self.driver = await asyncio.shield(starter)
                    except asyncio.CancelledError:
                        self.driver = await starter
                        raise
                    listed = await self.driver.list_tools_json()
                    tools = json.loads(listed)["tools"]
                else:
                    import agent_mcp
                    configs, error = agent_mcp._load_servers_dict_from_config()
                    cfg = (configs or {}).get(self.server_alias)
                    if not cfg:
                        raise ValueError(error or "selected Cua Driver MCP server is not configured")
                    if cfg.get("url"):
                        raise ValueError("Cua Driver MCP provider requires a local stdio server")
                    cfg = deepcopy(cfg)
                    if allow_existing_profile:
                        args = list(cfg.get("args") or [])
                        if "mcp" not in args:
                            raise ValueError("existing-profile grant requires a cua-driver mcp command")
                        if not any(args[index:index + 2] == ["--grant", "existing-profile"] for index in range(len(args))):
                            args += ["--grant", "existing-profile"]
                        cfg["args"] = args
                    from security.extensions import mcp_descriptor, mcp_registration_is_approved
                    if not mcp_registration_is_approved(mcp_descriptor(self.server_alias, cfg)):
                        raise PermissionError("approve this MCP server registration in MCP settings first" +
                                              ("; for existing-profile access, add --grant existing-profile to its configured args and approve that exact configuration, then save Computer Use again" if allow_existing_profile else ""))
                    self.reserved_alias = self.server_alias
                    await agent_mcp.reserve_server_for_host(self.server_alias, True, view=self.mcp_view)
                    self.server = agent_mcp._make_stdio_connector(self.server_alias, cfg, register_tools=False)
                    await agent_mcp._run_on_mcp_loop(self.server.start())
                    tools = [t.model_dump() for t in self.server._tools]
                definitions, names, output_schemas = [], {}, {}
                verify_schema = next((tool.get("inputSchema") for tool in tools if tool.get("name") == "verify_state"), None)
                prefix = "cua_driver_native__" if provider == "native" else "mcp__cua-driver-mcp__"
                from host_tool_registry import host_tool_invokers
                from tool_execution_policy import ToolExecutionPolicy
                for tool in tools:
                    original = str(tool.get("name") or "")
                    name = prefix + original
                    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", name) or name in names:
                        raise ValueError("invalid or duplicate Cua tool name: " + name)
                    if host_tool_invokers.has(name) and host_tool_invokers.owner(name) != "computer-use":
                        raise ValueError("Cua tool name collides with another host tool: " + name)
                    schema = deepcopy(tool.get("inputSchema"))
                    if not isinstance(schema, dict) or schema.get("type") != "object":
                        raise ValueError("invalid Cua tool inputSchema: " + name)
                    from jsonschema import Draft202012Validator
                    Draft202012Validator.check_schema(schema)
                    description = str(tool.get("description") or "")
                    output_schemas[original] = deepcopy(tool.get("outputSchema"))
                    if original == "get_window_state":
                        description += " MyAgent: max_dimension caps the returned preview only. Use coordinate_mapping or the attachment's preview-to-driver conversion; the driver's screenshot coordinate space stays at its configured size."
                    if original == "replay_trajectory":
                        description += " MyAgent requires a coordinate contract created by this host; old recordings and snapshot/zoom-token trajectories are refused before input. Replay counts are delivery, not task verification."
                    if original in WINDOW_ACTIONS and isinstance(verify_schema, dict):
                        verification = deepcopy(verify_schema)
                        verification["properties"] = {key: value for key, value in verification.get("properties", {}).items()
                                                      if key not in {"pid", "window_id", "session"}}
                        verification["required"] = [key for key in verification.get("required", []) if key in verification["properties"]]
                        verification["description"] = "Optional postcondition check of this exact window/session after one input. Default: timeout_ms=1000, no screenshot. Refusal, unknown or unsatisfied never retries input. Requires a window target with pid and window_id."
                        schema.setdefault("properties", {})["_verify"] = verification
                        Draft202012Validator.check_schema(schema)
                        description += " Host extension: _verify checks supplied verify_state predicates on the same window after delivery; input is sent once. verified:false alone is not proof of UI success."
                    names[name] = original
                    definitions.append({"type": "function", "function": {"name": name,
                        "description": description,
                        "parameters": schema}})
                # Validate the complete catalog before publishing any names.
                self.catalog, self.names, self.output_schemas = tuple(definitions), names, output_schemas
                for name, original in names.items():
                    host_tool_invokers.register(name, self.invoke, replace=True, owner="computer-use",
                        enabled=lambda name=name: self.state == "ready" and name in self.names and self._plugin_enabled(),
                        policy=ToolExecutionPolicy(effect="read" if original in READ_TOOLS else "external_write",
                            # Read snapshots/state must not overtake a preceding
                            # start/stop/input that cannot execute during streaming.
                            early_stream_safe=False, interruptibility="safe"))
                self.state = "ready"
                host_tool_invokers.notify_catalog_changed()
            except BaseException as exc:
                self.error = str(exc)
                await self._stop()
                self.state = "error"
                if isinstance(exc, asyncio.CancelledError):
                    raise
            return self.status()

    @staticmethod
    def _plugin_enabled():
        from plugins.host import bundled_host_plugin_enabled
        return bundled_host_plugin_enabled("computer-use")

    async def _stop(self):
        from host_tool_registry import host_tool_invokers
        host_tool_invokers.notify_catalog_changed()
        self.state = "closing"
        self.catalog, self.names = (), {}
        # Keep the provider reserved until admitted calls and shutdown settle.
        tasks = [t for t in self.pending if t is not asyncio.current_task()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        if self.driver:
            await self.driver.shutdown()
            self.driver = None
        if self.server:
            import agent_mcp
            await agent_mcp._run_on_mcp_loop(self.server.stop())
            self.server = None
        if self.reserved_alias:
            import agent_mcp
            await agent_mcp.reserve_server_for_host(self.reserved_alias, False)
            self.reserved_alias = ""
        self.state = "disabled"
        self.output_schemas = {}
        self.window_images.clear()
        from .computer_policy import RecordingEvidence
        self.recording = RecordingEvidence()

    async def stop(self):
        async with self._gate:
            await self._stop()

    async def _raw_call(self, name, arguments, *, admitted_mode=None):
        if self.state != "ready" or name not in self.names:
            raise RuntimeError("computer provider is unavailable")
        from jsonschema import Draft202012Validator
        definition = next(d for d in self.catalog if d["function"]["name"] == name)
        error = next(Draft202012Validator(definition["function"]["parameters"]).iter_errors(arguments), None)
        if error:
            raise ValueError(f"invalid {name} arguments at {'.'.join(map(str, error.absolute_path))}: {error.validator}")
        arguments = dict(arguments)
        verification = arguments.pop("_verify", None)
        verify_name = next((key for key, value in self.names.items() if value == "verify_state"), None)
        if verification is not None:
            if self.names[name] not in WINDOW_ACTIONS or "_verify" not in definition["function"]["parameters"].get("properties", {}):
                raise ValueError("_verify is supported only on declared window actions")
            target = arguments.get("target") or arguments
            if target.get("kind", arguments.get("scope", "window")) != "window" or not target.get("pid") or "window_id" not in target:
                raise ValueError("_verify requires an exact window target with pid and window_id; use verify_state separately for desktop actions")
            verification = {"timeout_ms": 1000, "include_screenshot": False, **verification,
                            "pid": target["pid"], "window_id": target["window_id"]}
            if "session" in arguments:
                verification["session"] = arguments["session"]
            verify_definition = next(d for d in self.catalog if d["function"]["name"] == verify_name)
            Draft202012Validator(verify_definition["function"]["parameters"]).validate(verification)
            if verification.get("timeout_ms") == 0:
                if verification.get("stable_samples", 1) > 1:
                    raise ValueError("_verify timeout_ms=0 requires stable_samples=1")
                verification["stable_samples"] = 1
        task = asyncio.current_task()
        self.pending.add(task)
        try:
            async with self._call_gate:
                if self.state != "ready" or name not in self.names:
                    raise RuntimeError("computer provider changed before invocation")
                if admitted_mode is not None:
                    from security.runtime import session_permission_mode
                    owner, mode = admitted_mode
                    if str(session_permission_mode(owner)) != mode:
                        raise PermissionError("permission mode changed while computer invocation was queued")
                from .computer_policy import (fixed_window_preview, repair_cursor_null_position, normalize_receipt,
                    failure, write_recording_manifest, record_window_mapping, validate_replay, replay_windows, window_geometry)
                from .computer_results import result_dict, structured_result
                original = self.names[name]
                owner = admitted_mode[0] if admitted_mode else None
                target = arguments.get("target") or arguments
                window_key = f"{target.get('pid')}:{target.get('window_id')}"
                if (original in {"start_recording", "stop_recording"} and self.recording.receipt
                    and self.recording.receipt.get("enabled") and self.recording.owner != owner):
                    return failure("recording_owned_by_other_agent", "Another Agent owns the active recording on this provider. No recording control was dispatched.")
                config = {}
                if original in {"start_recording", "replay_trajectory"} and "get_config" in self.names.values():
                    config_raw = result_dict(await self._call_driver("get_config", {}))
                    if not config_raw.get("isError"):
                        config = structured_result(config_raw)
                if original == "replay_trajectory":
                    refused = await asyncio.to_thread(validate_replay, arguments["dir"], config)
                    if refused:
                        return refused
                    windows = await asyncio.to_thread(replay_windows, arguments["dir"])
                    for key, expected in windows.items():
                        pid, window_id = map(int, key.split(":"))
                        observed = result_dict(await self._call_driver("get_window_state", {
                            "pid": pid, "window_id": window_id, "include_accessibility_tree": False}))
                        observed_data = structured_result(observed)
                        if (observed.get("isError") or observed_data.get("screenshot_error")
                            or (observed_data.get("screenshot_width"), observed_data.get("screenshot_height"))
                               != (expected.get("driver_width"), expected.get("driver_height"))
                            or (expected.get("window_geometry") and window_geometry(observed_data) != expected["window_geometry"])):
                            return failure("trajectory_window_geometry_changed", "A recorded window is missing or its image geometry changed. Re-record before replay. No action was dispatched.")
                recording_pixel_action = (original in WINDOW_ACTIONS and (self.recording.receipt or {}).get("enabled")
                    and any(key in arguments for key in ("x", "y", "from_x", "from_y", "to_x", "to_y")))
                if (recording_pixel_action and window_key not in self.window_images
                    and target.get("pid") and target.get("window_id") is not None
                    and target.get("kind", arguments.get("scope", "window")) == "window"):
                    # A restart/configuration change discards image evidence.
                    # Image-only inspection skips the UIA tree, so it does not
                    # invalidate element tokens; it restores the fixed image space.
                    observation_args = {"pid": target["pid"], "window_id": target["window_id"],
                                        "include_accessibility_tree": False, "include_screenshot": True}
                    if "session" in arguments:
                        observation_args["session"] = arguments["session"]
                    observed = fixed_window_preview(await self._call_driver("get_window_state", observation_args))
                    mapping = structured_result(observed).get("coordinate_mapping")
                    if not mapping:
                        return failure("recording_coordinate_observation_failed", "Cannot obtain the exact window's coordinate evidence before this recorded pixel input. No input was dispatched.", driver_state=structured_result(observed))
                    self.window_images[window_key] = mapping
                driver_arguments = dict(arguments)
                if original == "get_window_state":
                    driver_arguments.pop("max_dimension", None)
                if admitted_mode is not None:
                    from security.runtime import session_permission_mode
                    if str(session_permission_mode(owner)) != mode:
                        raise PermissionError("permission mode changed during computer preflight")
                raw = await self._call_driver(original, driver_arguments)
                if original == "get_window_state":
                    raw = fixed_window_preview(raw, arguments.get("max_dimension"))
                    mapping = structured_result(raw).get("coordinate_mapping")
                    if mapping:
                        self.window_images[window_key] = mapping
                if original == "get_agent_cursor_state":
                    raw = repair_cursor_null_position(raw, self.output_schemas.get(original))
                raw = self.recording.observe(normalize_receipt(raw, original) if original in {
                    "start_recording", "stop_recording", "get_recording_state"} else raw, original, owner)
                if original in {"set_config", "set_window_frame"}:
                    self.window_images.clear()
                if original == "start_recording" and not result_dict(raw).get("isError"):
                    directory = structured_result(raw).get("output_dir")
                    if directory:
                        try:
                            await asyncio.to_thread(write_recording_manifest, directory, config)
                        except (OSError, ValueError) as exc:
                            raw = result_dict(raw)
                            raw["structuredContent"] = {**structured_result(raw), "coordinate_contract_error": str(exc)}
                if (original in WINDOW_ACTIONS and self.recording.receipt and self.recording.receipt.get("enabled")
                    and window_key in self.window_images):
                    try:
                        await asyncio.to_thread(record_window_mapping, self.recording.receipt["output_dir"], window_key, self.window_images[window_key])
                    except (OSError, ValueError, KeyError) as exc:
                        raw = result_dict(raw)
                        raw["structuredContent"] = {**structured_result(raw), "coordinate_contract_error": str(exc)}
                elif original in WINDOW_ACTIONS and (self.recording.receipt or {}).get("enabled"):
                    raw = result_dict(raw)
                    raw["structuredContent"] = {**structured_result(raw), "coordinate_contract_error": "No fresh host window image mapping is available for " + window_key + "; take get_window_state with a screenshot before recording pixel actions."}
                if verification is not None:
                    from .computer_results import result_dict, structured_result
                    raw = result_dict(raw)
                    if not raw.get("isError"):
                        try:
                            checked = result_dict(await self._call_driver("verify_state", verification))
                        except Exception as exc:
                            checked = {"isError": True, "structuredContent": {"status": "unknown", "observation_error": str(exc)},
                                       "content": [{"type": "text", "text": "Postcondition observation failed after input; no input was retried: " + str(exc)}]}
                        evidence = structured_result(checked)
                        satisfied = not checked.get("isError") and evidence.get("status") == "satisfied" and evidence.get("stable") is True
                        if not satisfied and evidence.get("status") == "satisfied":
                            evidence = {**evidence, "driver_status": "satisfied", "status": "unknown"}
                        evidence = {**evidence, "evidence_scope": "driver_predicates", "visual_consistency": "not_checked"}
                        data = {**structured_result(raw), "host_verification": evidence or {"status": "unknown"}}
                        if not satisfied:
                            raw["isError"] = True
                            data["code"] = "postcondition_unsatisfied" if evidence.get("status") == "unsatisfied" else "postcondition_unknown"
                        raw["structuredContent"] = data
                        raw["content"] = list(raw.get("content") or []) + list(checked.get("content") or [])
                return normalize_receipt(raw, original)
        finally:
            self.pending.discard(task)

    async def _call_driver(self, original, arguments):
        if self.driver:
            result = await self.driver.call_tool(original, json.dumps(arguments, ensure_ascii=False))
            raw = json.loads(result.raw_json)
            if result.is_error:
                raw["isError"] = True
            return raw
        import agent_mcp
        return await agent_mcp._run_on_mcp_loop(self.server.call_tool(original, arguments))

    async def invoke(self, context, arguments):
        name = context.service("tool_name")
        from security.runtime import session_permission_mode
        if str(session_permission_mode(context.session_id)) != str(context.service("security_context").mode):
            raise PermissionError("permission mode changed before computer invocation")
        pending = self.service.call(self._raw_call, name, dict(arguments),
                                    admitted_mode=(context.session_id, str(context.service("security_context").mode)))
        awaiter = getattr(context, "services", {}).get("await_steerable")
        raw = await awaiter(pending, "computer_use") if awaiter else await pending
        from .computer_results import project_result, structured_result, image_source, result_dict
        original = name.split("__")[-1]
        data = structured_result(raw)
        from agent_mcp import format_call_tool_result
        content = format_call_tool_result(project_result(raw, original, arguments), image_enabled=context.service("image_input_enabled"),
                                          model=context.service("model"), image_source=image_source(original, arguments, data))
        metadata = {"computer_use": {"tool": original, "structuredContent": data}}
        failed = result_dict(raw).get("isError", False)
        return ToolOutcome.failed(str(data.get("code") or "computer_use_error"), "Cua Driver refused, failed or could not verify the action",
                                  content=content, metadata=metadata) if failed else ToolOutcome.completed(content, metadata=metadata)


def computer_manager(service=None):
    global _MANAGER
    with _LOCK:
        if _MANAGER is None:
            from .jobs import execution_service
            _MANAGER = ComputerUseManager(service or execution_service())
        return _MANAGER


def tool_contract(name):
    names = _MANAGER.names if _MANAGER is not None else {}
    original = names.get(name)
    if original is None:
        return None
    return {"effect": "read" if original in READ_TOOLS else "external_write", "declared": True}
