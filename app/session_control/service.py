"""One application service for CLI, transports and durable session admissions."""
from __future__ import annotations

import asyncio
import copy
import dataclasses
import json
import logging
import math
import os
import threading
import time
import uuid
from pathlib import Path

from .configuration import (ConfigRepository, apply_metadata, configure_repository, filter_registry,
                            from_metadata, ref_key, resolve_config, runtime_scope, tool_ref, validate_config)
from .errors import ControlError
from .policy import Principal, READ, check_session, validate_policy, workspace_key
from .store import digest

log = logging.getLogger(__name__)
TERMINAL = {"succeeded", "failed", "stopped", "interrupted", "unknown", "cancelled", "coalesced", "rejected"}


class SessionControlService:
    def __init__(self, dependencies, store, identities, *, callbacks=None):
        self.deps, self.store, self.identities = dependencies, store, identities
        self.manager = dependencies.session_manager
        self.configs = ConfigRepository(self.manager)
        from .coordinator import SessionExecutionCoordinator
        self.coordinator = SessionExecutionCoordinator(dependencies)
        self.callbacks = callbacks or {}
        self.loop = None
        self.task = None
        self.workers = {}
        self.cancellations = {}
        self.locks = {}
        self.closing = False
        self.engine = None
        self.legacy_scan_at = 0.
        self.created_at = time.time()
        from remote_control.service import SessionControlService as Legacy
        self.legacy = Legacy(dependencies, identities.remote)

    def required_scope(self, method):
        return self.legacy.required_scope(method)

    def authorize(self, principal, method, params):
        if os.getenv("MYAGENT_SESSION_CONTROL_ENABLED", "1").lower() in {"0", "false", "no"}:
            raise ControlError("control_disabled", "Session control is disabled by the host", status=403)
        self.identities.ensure_live(principal)
        if not principal.permits(method):
            raise ControlError("forbidden", "Capability is not granted: " + method, status=403)
        sid = params.get("session_id")
        needs_session = method.startswith("session.") and method not in {"session.list", "session.search", "session.create", "session.import", "session.send_batch"}
        if needs_session and not sid:
            raise ControlError("invalid_params", "session_id is required")
        if sid:
            if not isinstance(sid, str) or not self.manager.get_session_summary(sid):
                raise ControlError("session_not_found", "Session not found", status=404)
            check_session(principal, sid, self.manager)
        sources = [*principal.source_ancestors, *([params["_source"]] if params.get("_source") else [])]
        seen_sources = set()
        for source in sources:
            binding = (source["id"], source["epoch"], source.get("kind", "plugin"))
            if binding in seen_sources:
                continue
            seen_sources.add(binding)
            live = self.store.get("host_sources", source["id"])
            enabled = self.callbacks.get("source_enabled")
            if source.get("kind") == "runtime":
                from .public import RUNTIME_SOURCES
                if source["id"] not in RUNTIME_SOURCES:
                    raise ControlError("forbidden", "Unregistered runtime source", status=403)
                enabled = None
            if not live or not live["enabled"] or live["epoch"] != source["epoch"] or (enabled is not None and not enabled(source["id"])):
                raise ControlError("source_disabled", "Plugin authorization was revoked", status=403)
        if params.get("_automation_id"):
            task = self.store.get("automations", params["_automation_id"])
            if not task or task.get("deleted"):
                raise ControlError("authorization_revoked", "Automation was deleted", status=403)
            origin = Principal(**task["_principal"])
            self.authorize(origin, method, {"session_id": sid} if sid else {})
            if sid:
                check_session(Principal(task["owner"], policy=task["policy"]), sid, self.manager)
            if not Principal(task["owner"], policy=task["policy"]).permits(method):
                raise ControlError("authorization_revoked", "Automation capability was revoked", status=403)

    def principal(self, p):
        if isinstance(p, Principal):
            return p
        # Existing trusted transport adapters carry authenticated DevicePrincipal.
        caps = ["read"] if p.permits("read") else []
        if p.permits("write"):
            caps += ["session.create", "session.send", "session.steer", "session.interrupt"]
        if p.permits("approvals"):
            caps += ["approval.list", "approval.resolve"]
        return Principal(p.device_id, p.name, p.permits("admin"), {"scope": "all", "capabilities": caps}, p.credential_kind)

    async def execute(self, principal, method, params, *, idempotency_key=""):
        if method in {"approval.list", "approval.resolve", "device.list", "device.revoke", "audit.list"}:
            normalized = self.principal(principal)
            self.authorize(normalized, method, params)
            from remote_control.store import DevicePrincipal
            legacy_principal = DevicePrincipal(normalized.id, normalized.name,
                frozenset({self.legacy.required_scope(method)}), normalized.credential_kind)
            result, replayed = await self.legacy.execute(legacy_principal, method, params, idempotency_key=idempotency_key)
            if method == "approval.list":
                visible = []
                for row in result.get("approvals", []):
                    try:
                        check_session(normalized, row["session_id"], self.manager)
                    except ControlError:
                        continue
                    visible.append(row)
                result = {**result, "approvals": visible}
            return result, replayed
        principal = self.principal(principal)
        if not isinstance(params, dict):
            raise ControlError("invalid_params", "params must be an object")
        if len(json.dumps(params, ensure_ascii=False).encode()) > 1024 * 1024:
            raise ControlError("request_too_large", "Request exceeds 1 MiB", status=413)
        self.authorize(principal, method, params)
        if method == "session.send_batch":
            rows = params.get("requests")
            if not isinstance(rows, list) or not 1 <= len(rows) <= 8:
                raise ControlError("invalid_params", "Batch requires 1-8 requests")
            admissions = []
            for row in rows:
                if not isinstance(row, dict) or not isinstance(row.get("message"), str) or not row["message"].strip():
                    raise ControlError("invalid_params", "Each batch input requires a message")
                if set(row) - {"session_id", "message", "ui_message", "mode", "runtime_override"}:
                    raise ControlError("invalid_params", "Unsupported batch input fields")
                request = {**row, "_principal": dataclasses.asdict(principal)}
                if params.get("_source"):
                    request["_source"] = params["_source"]
                self.authorize(principal, "session.send", request)
                if request.get("mode", "queue") != "queue":
                    raise ControlError("invalid_params", "Batch inputs require queue mode")
                admissions.append(request)
            operations = await asyncio.to_thread(self.store.admit_many, principal.id, idempotency_key, admissions)
            await self.start()
            return {"accepted": True, "operations": [self.receipt(op) for op in operations]}, False
        if method == "session.send":
            if not isinstance(params.get("message"), str) or not params["message"].strip():
                raise ControlError("invalid_params", "message must be non-empty text")
            if params.get("mode", "queue") not in {"queue", "append", "interrupt"}:
                raise ControlError("invalid_params", "Invalid message mode")
            if params.get("mode", "queue") != "queue":
                self.authorize(principal, "session.steer", params)
                if params.get("mode") == "interrupt":
                    self.authorize(principal, "session.interrupt", params)
                if params.get("runtime_override"):
                    raise ControlError("invalid_params", "Runtime overrides require queue mode")
                if self.deps.is_stream_active(params["session_id"]):
                    method = "session.steer"
        if method == "session.steer" and params.get("mode") == "interrupt":
            self.authorize(principal, "session.interrupt", params)
        if method in READ:
            return await self._read(principal, method, params), False
        operation, replayed = await asyncio.to_thread(self.store.admit, principal.id, idempotency_key, method,
                                                      {**params, "_principal": dataclasses.asdict(principal)})
        if replayed:
            if operation["method"] not in {"session.send", "session.continue", "session.recover"} and operation["status"] in {"failed", "rejected"} and operation["error"]:
                raise ControlError(**operation["error"])
            return self.receipt(operation), True
        if method in {"session.send", "session.continue", "session.recover"}:
            await self.start()
            return self.receipt(operation), False
        if method == "automation.run":
            # fire() may create a session under the same identity. The operation
            # CAS owns this dispatch; holding the identity lock would deadlock
            # its nested session.create mutation.
            await self._apply(operation)
        else:
            async with self.locks.setdefault(principal.id, asyncio.Lock()):
                await self._apply(operation)
        return self.receipt(self.store.get_operation(operation["id"])), False

    @staticmethod
    def receipt(operation):
        return {**(operation.get("result") or {}), "operation_id": operation["id"],
                "execution_id": (operation.get("result") or {}).get("execution_id", operation["id"]), "accepted": operation["status"] not in {"failed", "rejected"},
                "status": operation["status"], "delivery_status": operation["delivery"],
                "created_at": operation["created"], "updated_at": operation["updated"],
                "session_id": operation["session_id"] or (operation.get("result") or {}).get("session_id", ""), "run_id": (operation.get("result") or {}).get("run_id", operation["run_id"]),
                "error": operation.get("error")}

    async def _read(self, principal, method, p):
        sid = p.get("session_id", "")
        if method == "system.health":
            return {"ok": True, "protocol_version": 1, "service": "session-control", "backend_owned": True,
                    "features": ["sessions", "configuration", "presets", "schedules", "events", "webhooks"]}
        if method == "auth.status":
            return {"principal": {"id": principal.id, "name": principal.name, "admin": principal.admin, "policy": principal.policy}}
        if method == "session.list":
            rows = await asyncio.to_thread(self.manager.list_sessions, include_archived=bool(p.get("include_archived")))
            allowed = []
            for row in rows:
                try:
                    check_session(principal, row["id"], self.manager)
                    allowed.append(row)
                except ControlError:
                    continue
            return {"sessions": allowed, "count": len(allowed)}
        if method == "session.get":
            summary = self.manager.get_session_summary(sid)
            if p.get("include_runtime"):
                from agent_harness import session_work_root
                meta = self.manager._load_metadata(sid)
                summary = {**summary, "work_dir": str(session_work_root(meta)),
                    "model_profile_id": meta.get("model_profile_id", ""), "reasoning_effort": meta.get("reasoning_effort", ""),
                    "stream_active": bool(self.deps.is_stream_active(sid))}
            return {"session": summary}
        if method == "session.history":
            limit = max(1, min(int(p.get("limit", 50)), 500))
            page = await asyncio.to_thread(self.manager.get_ui_events_page, sid, limit=limit,
                                           before_index=p.get("before_index"), turns=p.get("turns"))
            return {"session_id": sid, **page}
        if method == "session.search":
            return await asyncio.to_thread(self._search, principal, p)
        if method == "session.attach":
            return {"session": self.manager.get_session_summary(sid), "history": await self._read(principal, "session.history", p),
                    "cursor": self.store.cursor("event_highwater", 0)}
        if method == "session.detach":
            return {"detached": True, "session_id": sid}
        if method == "session.config.get":
            return self.configs.get(sid)
        if method == "session.config.preview":
            cfg = resolve_config(self.configs.get(sid)["config"], p.get("runtime_override"))
            registry = await self.catalog(sid, cfg)
            meta = self.manager._load_metadata(sid)
            with runtime_scope(sid, cfg):
                from agent_loop import _build_static_segments_for_session, compute_context_tokens_for_session, normalize_prompt_language
                segments = _build_static_segments_for_session(sid, apply_metadata(sid, meta), normalize_prompt_language(meta.get("prompt_language")))
                tokens = await asyncio.to_thread(compute_context_tokens_for_session, sid, registry.definitions())
            return {"config": cfg, "system_segments": list(segments), "tools": registry.definitions(),
                    "token_estimate": tokens, "config_digest": digest(cfg), "effective_from": "next_turn"}
        if method.startswith("tool_catalog."):
            cfg = self.configs.get(sid)["config"] if sid else validate_config({})
            registry = await self.catalog(sid, cfg, unfiltered=True)
            rows = [{"tool_ref": tool_ref(d), "schema_digest": digest(d.openai_definition()["function"].get("parameters", {})),
                     "definition": d.openai_definition(), "effect": d.effect, "available": d.executable}
                    for d in registry._descriptors.values()]
            if method.endswith("describe"):
                rows = [r for r in rows if r["tool_ref"] == p.get("tool_ref") or r["tool_ref"]["name"] == p.get("name")]
            return {"tools": rows}
        if method in {"operation.get", "operation.wait"}:
            oid = p.get("id") or p.get("operation_id")
            timeout = float(p.get("timeout", 30))
            if not math.isfinite(timeout) or timeout < 0:
                raise ControlError("invalid_params", "timeout must be a non-negative finite number")
            deadline = time.monotonic() + min(timeout, 300)
            while True:
                op = self.store.get_operation(oid)
                if not op:
                    raise ControlError("not_found", "Execution not found", status=404)
                if not principal.admin and op["principal"] != principal.id:
                    raise ControlError("forbidden", "Execution belongs to another caller", status=403)
                if op["session_id"]:
                    check_session(principal, op["session_id"], self.manager)
                if method.endswith("get") or op["status"] in TERMINAL:
                    value = self.receipt(op)
                    value["runtime_config"] = op.get("snapshot")
                    return value
                if time.monotonic() >= deadline:
                    raise ControlError("wait_timeout", "Wait expired; execution remains active", status=408,
                                       details=self.receipt(op))
                await asyncio.sleep(.1)
        if method == "automation.history":
            rows = self.store.operations(session_id=p.get("session_id"), automation_id=p.get("id"), limit=p.get("limit", 100), newest=True)
            visible = []
            for row in rows:
                if not principal.admin and row["principal"] != principal.id:
                    continue
                if p.get("id") and row["request"].get("_automation_id") != p["id"]:
                    continue
                try:
                    if row["session_id"]:
                        check_session(principal, row["session_id"], self.manager)
                except ControlError:
                    continue
                visible.append(self.receipt(row))
            return {"executions": visible}
        family = {"automation": "automations", "config_preset": "presets", "event_source": "sources"}.get(method.split(".")[0])
        if family:
            if method.endswith("list"):
                rows = self.store.list(family)
                return {"items": [self.public_document(r, family) for r in rows if not r.get("deleted")
                    and (principal.admin or r.get("owner") == principal.id)
                    and (family != "automations" or not p.get("kind_filter") or
                         (r["trigger"]["kind"] == "event") == (p["kind_filter"] == "event"))]}
            row = self.require_document(family, p.get("id"), principal)
            if method == "automation.test":
                from .scheduling import match_condition
                trigger = row["trigger"]
                event = p.get("event", {})
                matched = trigger["kind"] == "event" and event.get("type") in trigger["types"] and match_condition(trigger.get("condition"), event)
                return {"matched": matched, "target": row["target"], "action": row["action"], "runtime_override": row.get("runtime_override", {})}
            if method == "event_source.test":
                return {"enabled": row.get("enabled", True), "endpoint": "/api/automation/v1/hooks/" + row["id"], "executed": False}
            if family == "presets" and p.get("revision") is not None:
                row = self.store.get("preset_versions", row["id"] + ":" + str(p["revision"]))
                if not row:
                    raise ControlError("not_found", "Preset version not found", status=404)
            return self.public_document(row, family)
        raise ControlError("method_not_found", "Unknown method: " + method, status=404)

    @staticmethod
    def public_document(row, family):
        value = copy.deepcopy(row)
        for key in ("secret", "_principal", "credential"):
            value.pop(key, None)
        if family == "sources":
            value["endpoint"] = "/api/automation/v1/hooks/" + row["id"]
        return value

    def require_document(self, family, identity, principal):
        row = self.store.get(family, identity)
        if row is None:
            raise ControlError("not_found", "Object not found", status=404)
        if not principal.admin and row.get("owner") != principal.id:
            raise ControlError("forbidden", "Object belongs to another caller", status=403)
        return row

    async def catalog(self, sid, config=None, *, unfiltered=False):
        provider = self.callbacks.get("catalog")
        if not provider:
            from agent_loop import build_combined_tool_registry_for_session
            provider = build_combined_tool_registry_for_session
        meta = self.manager._load_metadata(sid) if sid else {}
        if unfiltered:
            meta = {**meta, "session_runtime_config": validate_config({})}
        with runtime_scope(sid, validate_config({}) if unfiltered else config or from_metadata(meta)):
            registry = await provider(sid, session_meta=meta, include_mcp=True)
        return registry if unfiltered else filter_registry(registry, config or from_metadata(meta))

    async def validate_bindings(self, sid, config):
        resolve_config(config)  # Detect incompatible constraint layers before saving.
        if config.get("model_profile_id"):
            import model_profiles
            from agent_harness import PROJECT_ROOT
            if not model_profiles.is_usable_profile(model_profiles.get_profile(PROJECT_ROOT, config["model_profile_id"])):
                raise ControlError("invalid_config", "Unknown model_profile_id")
        if config.get("reasoning_effort"):
            import model_profiles
            if config["reasoning_effort"] not in model_profiles.REASONING_EFFORTS:
                raise ControlError("invalid_config", "Invalid reasoning_effort")
        tools = config.get("tools", {})
        if not tools.get("allow") and not tools.get("deny") and not tools.get("bindings"):
            return config
        registry = await self.catalog(sid, unfiltered=True)
        present = {ref_key(tool_ref(d)): d for d in registry._descriptors.values()}
        optional = {ref_key(b["tool_ref"]) for b in tools.get("bindings", []) if b.get("required") is False}
        for ref in tools.get("allow", []) + tools.get("deny", []):
            if ref_key(ref) not in present and ref_key(ref) not in optional:
                raise ControlError("tool_not_found", "Unknown tool: " + ref["name"], status=409)
        bindings = tools.setdefault("bindings", [])
        bound = {ref_key(b["tool_ref"]) for b in bindings}
        for ref in tools.get("allow", []):
            if ref_key(ref) not in bound:
                bindings.append({"tool_ref": copy.deepcopy(ref), "required": True})
        from .configuration import validate_arguments
        for binding in tools.get("bindings", []):
            key = ref_key(binding["tool_ref"])
            if key in {ref_key(r) for r in tools.get("deny", [])} or (tools.get("mode") == "custom" and key not in {ref_key(r) for r in tools.get("allow", [])}):
                continue
            d = present.get(ref_key(binding["tool_ref"]))
            if d is None:
                if binding.get("required") is False:
                    continue
                raise ControlError("tool_not_found", "Unknown bound tool", status=409)
            schema = d.openai_definition()["function"].get("parameters", {})
            fingerprint = digest(schema)
            if binding.get("schema_digest") not in {None, fingerprint}:
                if binding.get("required") is False:
                    continue
                raise ControlError("schema_changed", "Tool schema changed", status=409)
            if config.get("read_only") and binding.get("required", True) and d.effect != "read":
                raise ControlError("invalid_config", "Required tool conflicts with read_only: " + d.execution_name)
            properties = schema.get("properties", {})
            from jsonschema import Draft202012Validator, ValidationError
            for field in set(binding.get("defaults", {})) | set(binding.get("fixed", {})):
                if field not in properties:
                    raise ControlError("invalid_config", "Bound parameter is absent from tool schema: " + field)
                for source in (binding.get("defaults", {}), binding.get("fixed", {})):
                    if field in source:
                        try:
                            Draft202012Validator(properties[field]).validate(source[field])
                        except ValidationError as exc:
                            raise ControlError("invalid_config", "Bound value has the wrong type: " + field) from exc
            for rule in binding.get("constraints", []):
                first = rule["pointer"].split("/")[1]
                if first not in properties:
                    raise ControlError("invalid_config", "Constrained parameter is absent from tool schema")
                if first not in schema.get("required", []) and "default" not in properties[first] and first not in binding.get("defaults", {}) and first not in binding.get("fixed", {}):
                    raise ControlError("unsupported_constraint", "Optional constrained parameters require an explicit default or fixed value")
                node = schema
                for segment in rule["pointer"][1:].split("/"):
                    segment = segment.replace("~1", "/").replace("~0", "~")
                    if node.get("type") == "array" and segment.isdigit():
                        node = node.get("items", {})
                    elif segment in node.get("properties", {}):
                        node = node["properties"][segment]
                    else:
                        raise ControlError("unsupported_constraint", "Parameter path is not declared by the tool schema")
                if rule["kind"] == "url":
                    # Remote/MCP implementations cannot attest to redirects.
                    if d.invocation_kind.value != "host" or d.owner != "core.tools" or d.execution_name not in {"web_fetch", "web_download"} or rule["pointer"] != "/url":
                        raise ControlError("unsupported_constraint", "URL semantics are not declared for this tool")
                if rule["kind"] == "path":
                    names = {"read_file": {"path", "file_path"}, "write_file": {"path", "file_path"},
                             "edit_file": {"path", "file_path"}, "delete_file": {"path", "file_path"},
                             "ls": {"path"}, "glob": {"path", "root"}, "grep": {"path"},
                             "run_shell": {"workdir", "working_dir"}, "terminal_open": {"cwd", "workdir"}}
                    trusted = (d.invocation_kind.value == "host" and d.owner == "core.tools") or (d.invocation_kind.value == "host_service" and d.owner == "execution-tools" and d.execution_name == "terminal_open")
                    if not trusted or rule["pointer"] != "/" + first or first not in names.get(d.execution_name, set()):
                        raise ControlError("unsupported_constraint", "Path semantics are not declared for this tool")
            binding["schema_digest"] = fingerprint
        return config

    async def _apply(self, operation):
        if not self.store.update_operation(operation["id"], expected="queued", status="applying"):
            return
        p = {k: v for k, v in operation["request"].items() if not k.startswith("_")}
        principal = Principal(**operation["request"]["_principal"])
        method, sid = operation["method"], operation["session_id"]
        try:
            self.authorize(principal, method, operation["request"])
            result = await self._mutate(principal, method, p, operation)
            self.store.update_operation(operation["id"], status="succeeded", delivery="committed", result=result,
                                        session_id=result.get("session_id", sid))
        except Exception as exc:
            error = exc if isinstance(exc, ControlError) else ControlError("invalid_params" if isinstance(exc, (ValueError, TypeError)) else "internal_error", str(exc))
            self.store.update_operation(operation["id"], status="failed", delivery="rejected",
                                        error={"code": error.code, "message": error.message, "status": error.status, "details": error.details})
            raise error

    async def _mutate(self, principal, method, p, operation):
        sid = p.get("session_id", "")
        if method == "session.create":
            if p.get("runtime_config") is not None:
                validate_config(p["runtime_config"])
            workspace = p.get("work_dir") or principal.policy.get("workspace")
            if not workspace:
                from agent_harness import WORK_DIR
                workspace = str(WORK_DIR)
            self.check_workspace(principal, workspace)
            target = str(uuid.uuid5(uuid.UUID(operation["id"]), "session"))
            if not self.manager.get_session_summary(target):
                if hasattr(self.manager, "create_session_with_id"):
                    await asyncio.to_thread(self.manager.create_session_with_id, target, work_dir=workspace,
                                            model_profile_id=p.get("model_profile_id", ""))
                else:
                    raise ControlError("unsupported_backend", "Backend lacks deterministic session creation", status=409)
            if p.get("name"):
                await asyncio.to_thread(self.manager.set_session_name, target, str(p["name"])[:160])
            if p.get("runtime_config"):
                cfg = validate_config(p["runtime_config"])
                await self.validate_bindings(target, cfg)
                current = self.configs.get(target)
                if current["config"] != cfg:
                    self.configs.update(target, cfg, current["revision"])
            return {"session_id": target, "session": self.manager.get_session_summary(target)}
        if method == "session.config.update":
            cfg = validate_config(p.get("config"))
            await self.validate_bindings(sid, cfg)
            if "expected_revision" not in p:
                raise ControlError("revision_required", "expected_revision is required", status=409)
            result = self.configs.update(sid, cfg, p["expected_revision"])
            return {**result, "effective_from": "next_turn"}
        if method == "session.fork":
            result = await asyncio.to_thread(self.manager.branch_session_at_event_index, sid, int(p.get("before_index", self.manager.get_ui_event_count(sid))),
                                            branch_after_seq=p.get("after_seq"))
            if not result or result.get("ok") is False:
                raise ControlError("fork_failed", "Unable to fork at this history position", status=409, details=result)
            child = result["session_id"]
            cfg = self.configs.get(sid)["config"]
            self.configs.update(child, cfg, self.configs.get(child)["revision"])
            return result
        if method == "session.update":
            if any(field in p for field in ("model_profile_id", "reasoning_effort")):
                self.authorize(principal, "session.config.update", p)
            unknown = set(p) - {"session_id", "name", "pinned", "todo", "work_dir", "model_profile_id", "reasoning_effort"}
            if unknown:
                raise ControlError("invalid_params", "Unsupported session fields")
            for key, func in (("name", self.manager.set_session_name), ("pinned", self.manager.set_session_pinned), ("todo", self.manager.set_session_todo)):
                if key in p:
                    await asyncio.to_thread(func, sid, p[key])
            if "work_dir" in p:
                if self.deps.is_stream_active(sid):
                    raise ControlError("session_busy", "Cannot change workspace during execution", status=409)
                self.check_workspace(principal, p["work_dir"])
                await asyncio.to_thread(self.manager.set_session_work_dir, sid, p["work_dir"])
            for key in ("model_profile_id", "reasoning_effort"):
                if key in p:
                    callback = self.callbacks.get(key)
                    if not callback:
                        raise ControlError("unsupported_backend", "Backend cannot update " + key, status=409)
                    await callback(sid, p[key])
            return {"session_id": sid, "session": self.manager.get_session_summary(sid)}
        if method in {"session.archive", "session.delete"}:
            if method == "session.delete" or p.get("archived", True):
                await self.stop_session(sid)
            if method.endswith("archive"):
                await asyncio.to_thread(self.manager.set_session_archived, sid, p.get("archived", True))
            else:
                await asyncio.to_thread(self.manager.delete_session, sid)
            return {"session_id": sid, "ok": True}
        if method == "session.interrupt":
            await self.stop_session(sid)
            return {"session_id": sid, "stopped": True}
        if method == "session.steer":
            from remote_control.service import SessionControlService as Legacy
            legacy = Legacy(self.deps, self.identities.remote)
            return await legacy._session_steer({**p, "client_id": operation["id"]})
        if method == "session.steer.cancel":
            original = self.store.get_operation(p.get("client_id"))
            if not original or original["session_id"] != sid or (not principal.admin and original["principal"] != principal.id):
                raise ControlError("forbidden", "Steer belongs to another caller", status=403)
            from agent_loop import remove_session_steer
            return remove_session_steer(sid, client_id=p["client_id"])
        if method == "session.notice":
            if not isinstance(p.get("message"), str) or not p["message"].strip():
                raise ControlError("invalid_params", "Notice requires text")
            from runtime_v2.event_log import SessionEventLog
            events = SessionEventLog(self.manager.sessions_dir, self.manager._resolve_session_path)
            with events.session_transaction(sid):
                receipt = self.store.receipt(sid, operation["id"])
                if not receipt:
                    event = events._append_unlocked(sid, "ui_event", {"type": "status", "content": p["message"],
                                                    "operation_id": operation["id"]})
                    self.store.receipt(sid, operation["id"], {"seq": event.seq})
            return {"session_id": sid, "notice_written": True}
        if method in {"session.export", "session.import"}:
            if not principal.admin:
                raise ControlError("forbidden", "Import/export requires an administrative identity", status=403)
            callback = self.callbacks.get(method)
            if not callback:
                raise ControlError("unsupported_backend", "Import/export adapter unavailable", status=409)
            return await asyncio.to_thread(callback, p)
        if method == "operation.cancel":
            target = self.store.get_operation(p.get("id") or p.get("operation_id"))
            if not target:
                raise ControlError("not_found", "Execution not found", status=404)
            if not principal.admin and target["principal"] != principal.id:
                raise ControlError("forbidden", "Execution belongs to another caller", status=403)
            if target["session_id"]:
                check_session(principal, target["session_id"], self.manager)
            if target["status"] == "queued":
                self.store.update_operation(target["id"], expected="queued", status="cancelled", delivery="cancelled")
            elif target["status"] not in TERMINAL:
                self.mark_cancelled(target)
                self.manager.request_interrupt(target["session_id"], target["run_id"], reason="control_cancel")
            return {"cancel_requested": True, "execution_id": target["id"]}
        if method.startswith("config_preset."):
            return await self._preset(principal, method.split(".")[1], p, operation)
        if method.startswith("automation.") or method.startswith("event_source."):
            if self.engine is None:
                from .automation import AutomationService
                self.engine = AutomationService(self)
            return await self.engine.mutate(principal, method, p, operation)
        if method == "auth.logout":
            self.identities.revoke(p.get("token", ""))
            return {"logged_out": True}
        raise ControlError("method_not_found", "Unknown method: " + method, status=404)

    def check_workspace(self, principal, workspace):
        for policy in principal.delegated_policies:
            self.check_workspace(Principal("delegation", policy=policy), workspace)
        if principal.admin or principal.policy.get("scope") == "all":
            return
        roots = principal.policy.get("workspaces", []) if principal.policy.get("scope") == "workspaces" else [principal.policy.get("workspace")]
        if workspace_key(workspace) not in roots:
            raise ControlError("scope_denied", "Workspace is outside caller scope", status=403)

    async def _preset(self, principal, action, p, op):
        identity = p.get("id") or str(uuid.uuid5(uuid.UUID(op["id"]), "preset"))
        if action == "delete":
            self.require_document("presets", identity, principal)
            return {"deleted": self.store.delete("presets", identity)}
        if action == "apply":
            self.authorize(principal, "session.config.update", p)
            row = self.require_document("presets", identity, principal)
            if p.get("revision") is not None:
                version = self.store.get("preset_versions", identity + ":" + str(p["revision"]))
                if not version:
                    raise ControlError("not_found", "Preset version not found", status=404)
                row = version
            sid = p["session_id"]
            await self.validate_bindings(sid, row["config"])
            return self.configs.update(sid, row["config"], p.get("expected_revision"))
        cfg = validate_config(p.get("config"))
        if action == "update":
            self.require_document("presets", identity, principal)
            if "expected_revision" not in p:
                raise ControlError("revision_required", "expected_revision is required", status=409)
        row = self.store.put("presets", identity, {"name": str(p.get("name", "Preset")), "owner": principal.id, "config": cfg},
                             expected=0 if action == "create" else p["expected_revision"])
        self.store.put("preset_versions", identity + ":" + str(row["revision"]), {"config": cfg, "owner": principal.id,
                       "name": row["name"], "preset_id": identity, "preset_revision": row["revision"]}, expected=0)
        return row

    def _search(self, principal, params):
        service = self.callbacks.get("search")
        if not service:
            raise ControlError("unsupported_backend", "Search adapter unavailable", status=409)
        ctx = service.prepare({"q": params.get("query", ""), "scope": params.get("scope", "all"),
                               "phase": params.get("phase", "all"), "include_tools": params.get("include_tools", False),
                               "cursor": params.get("cursor")})
        # Filter before indexing or extracting any unauthorized transcript.
        rows = ctx.get("sessions", [])
        visible = []
        for row in rows:
            try:
                check_session(principal, row["id"], self.manager)
                visible.append(row)
            except ControlError:
                continue
        ctx["sessions"] = visible
        return {"events": list(service.search(ctx, threading.Event()))}

    async def stop_session(self, sid):
        self.manager.request_interrupt(sid, reason="control_stop")
        for op in self.store.operations(session_id=sid, status="queued", limit=1000):
            if op["method"] in {"session.send", "session.continue", "session.recover"}:
                self.store.update_operation(op["id"], expected="queued", status="cancelled", delivery="cancelled")
        for op in self.store.operations(session_id=sid, status="running", limit=1000):
            self.mark_cancelled(op)
        from remote_control.service import SessionControlService as Legacy
        await Legacy(self.deps, self.identities.remote)._session_interrupt({"session_id": sid, "reason": "control_stop"})
        try:
            from execution_services.integration import stop_execution
            await stop_execution([sid, *self.manager.list_subagent_descendants(sid)], reason="control_stop")
        except ImportError:
            pass

    def mark_cancelled(self, operation):
        self.cancellations.setdefault(operation["id"], threading.Event()).set()
        self.store.update_operation(operation["id"], expected="running", status="cancelling")

    async def start(self):
        if self.task and not self.task.done():
            return
        self.loop = asyncio.get_running_loop()
        self.closing = False
        from .automation import AutomationService
        self.engine = self.engine or AutomationService(self)
        configure_repository(self.configs)
        for status in ("queued", "applying"):
            for op in self.store.operations(status=status, limit=1000):
                if op["created"] < self.created_at and op["method"] not in {"session.send", "session.continue", "session.recover"}:
                    self.store.update_operation(op["id"], expected=status, status="unknown",
                        error={"code": "process_interrupted", "message": "Mutation outcome is unknown; inspect its target before retrying"})
        # A process restart must reconcile started work rather than replay it.
        for op in self.store.operations(status="running", limit=1000) + self.store.operations(status="cancelling", limit=1000):
            if not self.deps.is_stream_active(op["session_id"]):
                self.store.update_operation(op["id"], status="unknown", error={"code": "process_interrupted", "message": "Inspect or recover the original run"})
        self.task = asyncio.create_task(self._loop(), name="session-control-scheduler")

    async def close(self):
        self.closing = True
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
            self.task = None
        for sid, (task, op) in list(self.workers.items()):
            self.mark_cancelled(op)
            self.manager.request_interrupt(sid, op["run_id"], reason="backend_shutdown")
        if self.workers:
            await asyncio.wait([x[0] for x in self.workers.values()], timeout=5)
        if self.engine and self.engine._listener:
            from session_event_bus import remove_event_listener
            remove_event_listener(self.engine._listener)
            self.engine._listener = None

    async def _loop(self):
        while not self.closing:
            try:
                for sid, (task, operation) in list(self.workers.items()):
                    if task.done():
                        try:
                            task.result()
                        except Exception:
                            log.exception("Control worker failed")
                        self.workers.pop(sid, None)
                        self.cancellations.pop(operation["id"], None)
                await self.engine.tick()
                await self.adopt_followups()
                for op in self.store.pending_heads():
                    sid = op["session_id"]
                    if sid not in self.workers:
                        await self._dispatch(op)
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("Session control scheduling failed")
            await asyncio.sleep(.5)

    async def _dispatch(self, op):
        sid = op["session_id"]
        p = op["request"]
        token = None
        retry = self.store.get("dispatch_retries", op["id"]) or {}
        if retry.get("next_at", 0) > time.time():
            return
        try:
            principal = Principal(**p["_principal"])
            self.authorize(principal, op["method"], p)
            if p.get("_source_lifecycle") and p.get("_source", {}).get("id") not in self.callbacks.get("source_before_run", {}):
                return  # Restored domain inputs wait for their lifecycle adapter.
            meta = await asyncio.to_thread(self.manager._load_metadata, sid)
            if meta.get("archived"):
                return
            pending = self.callbacks.get("pending_human", lambda _: 0)(sid)
            if pending or self.deps.is_stream_active(sid):
                return
            if p.get("_respect_stop") and self.callbacks.get("manually_stopped", lambda _: False)(sid):
                self.store.update_operation(op["id"], status="cancelled", delivery="cancelled")
                return
            if op["method"] != "session.send":
                from workflow_extensions import session_workflows
                job_notice = p.get("_source", {}).get("id") == "execution-tools" and p.get("_continuation_source") == "tool-jobs"
                child_notice = p.get("_source", {}).get("id") == "@runtime/subagents" and p.get("_source", {}).get("kind") == "runtime"
                if not (job_notice or child_notice) and not self.manager.can_continue_react_session(sid) and not session_workflows.continuation_source(sid):
                    raise ControlError("nothing_to_continue", "Session has no unfinished turn or active workflow", status=409)
            if self.engine:
                if await asyncio.to_thread(self.engine._bridge_session, sid):
                    return  # Finish this session's durable dedup index before delivery.
            if self.store.receipt(sid, p.get("_legacy_followup_id", op["id"])):
                self.store.update_operation(op["id"], status="unknown", delivery="committed",
                    error={"code": "already_committed", "message": "Original input is committed; recover its run instead of resending"})
                return
            cfg = op.get("snapshot") or resolve_config(from_metadata(meta), p.get("runtime_override"))
            if principal.runtime_ceiling:
                cfg = resolve_config(cfg, principal.runtime_ceiling)
            await self.validate_bindings(sid, cfg)
            if p.get("_automation_id") and self.callbacks.get("manually_stopped", lambda _: False)(sid):
                return
            token = await self.coordinator.reserve_async(sid, op["run_id"])
            if not token:
                return
            if p.get("_legacy_followup_id"):
                from agent_loop import transition_session_steer
                claimed = transition_session_steer(sid, p["_legacy_followup_id"], {"queued"}, "claimed",
                    claimed_by=op["run_id"], claimed_at=time.time(), replacement_run_id=op["run_id"])
                if not claimed.get("ok"):
                    self.coordinator.release(sid, token)
                    self.store.update_operation(op["id"], status="coalesced", delivery="coalesced")
                    return
            if not self.store.update_operation(op["id"], expected="queued", status="running", snapshot=cfg):
                self.coordinator.release(sid, token)
                return
            self.cancellations.setdefault(op["id"], threading.Event())
            self.workers[sid] = (asyncio.create_task(asyncio.to_thread(self._run, op, cfg, token)), op)
        except Exception as exc:
            if token:
                self.coordinator.release(sid, token)
            transient = isinstance(exc, (TimeoutError, ConnectionError)) or getattr(exc, "code", "") in {"backend_unavailable", "provider_unavailable", "catalog_unavailable"}
            attempts = retry.get("attempts", 0) + 1
            if transient and attempts <= 3:
                self.store.put("dispatch_retries", op["id"], {"attempts": attempts, "next_at": time.time() + 2 ** (attempts - 1),
                    "error": {"code": getattr(exc, "code", "temporary_dispatch_failure"), "message": str(exc)}})
                return
            self.store.update_operation(op["id"], status="failed", delivery="rejected",
                                        error={"code": getattr(exc, "code", "dispatch_failed"), "message": str(exc)})

    def _run(self, op, cfg, token):
        try:
            self._run_owned(op, cfg)
        except BaseException as exc:
            self.store.update_operation(op["id"], status="unknown", error={"code": "worker_interrupted", "message": str(exc)})
        finally:
            hook = self.callbacks.get("source_after_run", {}).get(op["request"].get("_source", {}).get("id"))
            if hook:
                try:
                    hook(op["session_id"], op["run_id"], self.store.get_operation(op["id"]))
                except Exception:
                    log.exception("Plugin result accounting failed")
            self.coordinator.release(op["session_id"], token)

    def _run_owned(self, op, cfg):
        sid, p = op["session_id"], op["request"]
        final, failure = None, None
        committed = False
        cancellation = self.cancellations.setdefault(op["id"], threading.Event())
        if cancellation.is_set():
            self.store.update_operation(op["id"], status="stopped")
            return
        def should_stop(s):
            return cancellation.is_set() or self.manager.is_interrupt_requested(s, op["run_id"])
        from runtime_v2.event_log import SessionEventLog
        events = SessionEventLog(self.manager.sessions_dir, self.manager._resolve_session_path)
        tail = events.read_latest(sid, 1)
        start_seq = tail[-1].seq if tail else 0
        turn_id = p.get("_legacy_followup_id", op["id"]) if op["method"] == "session.send" else op["run_id"]
        def committed_final():
            for event in events.iter_after_seq(sid, start_seq):
                if event.type == "assistant_final_committed" and event.run_id == op["run_id"] and event.payload.get("operation_id") == "final:" + turn_id:
                    return event.payload.get("ui_content", event.payload.get("content", ""))
            return None
        async def consume():
            nonlocal final, failure, committed
            if op["method"] == "session.send":
                generator = self.deps.astream_events(p["message"], session_id=sid, run_id=op["run_id"],
                    user_operation_id=p.get("_legacy_followup_id", op["id"]), ui_user_content=p.get("ui_message", p["message"]),
                    user_content=p.get("_legacy_user_content"),
                    should_stop=should_stop)
            else:
                generator = self.callbacks["continue"](sid, run_id=op["run_id"], require_pending_subagents=p.get("_require_pending_subagents", False),
                    continuation_source=p.get("_continuation_source", "session-control"), recovery_reason=p.get("_recovery_reason", "control_recovery" if op["method"].endswith("recover") else ""),
                    should_stop=should_stop)
            turn_complete = False
            async for event in generator:
                kind = event.get("type")
                if not turn_complete and kind in {"run_started", "user_steer", "llm_response", "tool_pending", "tool_call", "approval_requested", "tool_approval_required", "question_requested", "final", "error", "run_failed"}:
                    value = copy.deepcopy(event)
                    if kind == "final":
                        answer = committed_final()
                        if answer is None:
                            continue
                        value["content"] = answer
                        turn_complete = True
                    for field in ("content", "result"):
                        if kind not in {"final", "llm_response"} and isinstance(value.get(field), str):
                            value[field] = value[field][:64000]
                    value = json.loads(json.dumps(value, ensure_ascii=False, default=str))
                    if kind not in {"final", "llm_response"} and len(json.dumps(value, ensure_ascii=False).encode("utf-8")) > 256 * 1024:
                        value = {k: v for k, v in value.items() if k in {"type", "tool", "tool_call_id", "approval_id", "execution_status", "content"}}
                        value["result"] = "[Large tool payload omitted from operation transport]"
                    value["run_id"] = op["run_id"]
                    self.store.append_operation_event(op["id"], value)
                if kind in {"user", "user_turn_committed"}:
                    committed = True
                    self.store.update_operation(op["id"], delivery="committed")
                if kind in {"final", "assistant_final_committed"} and final is None:
                    final = event.get("content", event.get("payload", {}).get("content", ""))
                if kind in {"error", "run_failed"}:
                    failure = str(event.get("content") or event.get("error") or "Run failed")
        try:
            principal = Principal(**p["_principal"])
            def authority():
                if cancellation.is_set():
                    raise ControlError("execution_cancelled", "Execution was cancelled", status=403)
                self.authorize(principal, op["method"], p)
            self.manager.clear_interrupt(sid, op["run_id"])
            with runtime_scope(sid, cfg, authority, principal):
                from contextlib import ExitStack
                with ExitStack() as scopes:
                    if p.get("_run_scope_context"):
                        from agent_loop import set_run_tool_scope, clear_run_tool_scope
                        scope = set_run_tool_scope(sid, run_id=op["run_id"], context=p["_run_scope_context"])
                        scopes.callback(clear_run_tool_scope, sid, scope)
                    hook = self.callbacks.get("source_before_run", {}).get(p.get("_source", {}).get("id"))
                    if hook:
                        hook(sid, op["run_id"], {**p, "_operation_id": op["id"]})
                    asyncio.run(consume())
            # Only this operation's durable turn can complete its execution.
            final = committed_final()
            stopped = should_stop(sid)
            status = "succeeded" if final is not None else "stopped" if stopped else "failed" if failure else "unknown"
            self.store.update_operation(op["id"], status=status, result={"content": final, "turn_id": turn_id},
                                        error={"code": "run_failed", "message": failure} if failure and final is None else None)
        except BaseException as exc:
            final = committed_final()
            self.store.update_operation(op["id"], status="succeeded" if final is not None else "coalesced" if getattr(exc, "code", "") == "intent_obsolete" else "stopped" if cancellation.is_set() else "interrupted" if isinstance(exc, asyncio.CancelledError) else "failed",
                result={"content": final, "turn_id": turn_id}, error=None if final is not None else {"code": "run_failed", "message": str(exc)})

    async def adopt_followups(self):
        """Consume accepted browser followups even when the browser has left."""
        state = self.callbacks.get("followup_state")
        if not state or time.monotonic() < self.legacy_scan_at:
            return
        self.legacy_scan_at = time.monotonic() + 2
        from agent_loop import list_session_steers
        for session in self.manager.list_sessions(include_archived=False):
            sid = session["id"]
            if sid in self.workers:
                continue
            entries = [item for item in list_session_steers(sid).get("items", [])
                       if item.get("after_turn") and item.get("state") == "queued"]
            # The readiness callback can rebuild historical UI projections.
            # No queued followup means there is nothing to admit or recover.
            if not entries or await asyncio.to_thread(state, sid) != "ready":
                continue
            for item in entries:
                principal = Principal("webui:" + sid, "Accepted WebUI followup", False,
                    {"scope": "self", "current_session": sid, "capabilities": ["read", "session.send"]}, "webui")
                params = {"session_id": sid, "message": str(item.get("content") or ""),
                          "ui_message": item.get("ui_content", item.get("content", "")),
                          "_legacy_followup_id": item["id"], "_legacy_user_content": item.get("user_content")}
                await self.execute(principal, "session.send", params, idempotency_key="followup:" + item["id"])
                break

    def subscribe(self, sid, *, replay_recent=True):
        from session_event_bus import subscribe_session_events
        return subscribe_session_events(sid, replay_recent=replay_recent)
