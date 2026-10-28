"""Versioned instructions and source-bound tool parameter constraints."""
from __future__ import annotations

import copy
import json
import math
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from urllib.parse import urlsplit

from .errors import ControlError
from .store import digest

_active = ContextVar("session_control_runtime_config", default=None)
_repository = None
_catalog_provider = None
_authority_check = ContextVar("session_control_authority", default=None)
_principal_context = ContextVar("session_control_principal", default=None)
_executing_tool = ContextVar("session_control_executing_tool", default=None)


def configure_repository(repository, catalog_provider=None):
    global _repository, _catalog_provider
    _repository, _catalog_provider = repository, catalog_provider


def tool_ref(descriptor):
    return {"kind": descriptor.invocation_kind.value, "owner": descriptor.owner,
            "name": descriptor.execution_name}


def ref_key(ref):
    if not isinstance(ref, dict) or set(ref) != {"kind", "owner", "name"} or not all(isinstance(v, str) and v for v in ref.values()):
        raise ControlError("invalid_config", "Tool references require kind, owner and stable name")
    return (ref["kind"], ref["owner"], ref["name"])


def validate_config(raw, *, partial=False):
    from session_system_context import validate_system_context
    if not isinstance(raw, dict) or set(raw) - {"system_prompt", "tools", "model_profile_id", "reasoning_effort", "limits", "read_only"}:
        raise ControlError("invalid_config", "Unsupported runtime configuration fields")
    value = copy.deepcopy(raw)
    if "read_only" in value and type(value["read_only"]) is not bool:
        raise ControlError("invalid_config", "read_only must be boolean")
    if "limits" in value:
        limits = value["limits"]
        if not isinstance(limits, dict) or set(limits) - {"timeout_seconds", "max_tool_calls"}:
            raise ControlError("invalid_config", "Unsupported execution limits")
        if any(type(v) not in {int, float} or not math.isfinite(v) or v <= 0 for v in limits.values()):
            raise ControlError("invalid_config", "Execution limits must be positive finite numbers")
        if "max_tool_calls" in limits and type(limits["max_tool_calls"]) is not int:
            raise ControlError("invalid_config", "max_tool_calls must be an integer")
    if "system_prompt" in value:
        p = value["system_prompt"]
        if not isinstance(p, dict) or set(p) - {"mode", "text"}:
            raise ControlError("invalid_config", "Invalid system_prompt")
        mode = p.get("mode", "append")
        if mode == "default":
            mode, p = "append", {"text": ""}
        text, mode = validate_system_context(p.get("text", ""), mode)
        value["system_prompt"] = {"mode": mode, "text": text}
    elif not partial:
        value["system_prompt"] = {"mode": "append", "text": ""}
    for field in ("model_profile_id", "reasoning_effort"):
        if field in value and not isinstance(value[field], str):
            raise ControlError("invalid_config", field + " must be a string")
    tools = value.get("tools")
    if tools is None:
        if not partial:
            value["tools"] = {"mode": "inherit", "allow": [], "deny": [], "bindings": []}
        return value
    if not isinstance(tools, dict) or set(tools) - {"mode", "allow", "deny", "bindings"}:
        raise ControlError("invalid_config", "Invalid tools configuration")
    tools.setdefault("mode", "inherit")
    if tools["mode"] not in {"inherit", "custom"}:
        raise ControlError("invalid_config", "tools.mode must be inherit or custom")
    for field in ("allow", "deny"):
        tools.setdefault(field, [])
        if not isinstance(tools[field], list):
            raise ControlError("invalid_config", field + " must be an array")
        for ref in tools[field]:
            ref_key(ref)
    tools.setdefault("bindings", [])
    if not isinstance(tools["bindings"], list):
        raise ControlError("invalid_config", "bindings must be an array")
    seen = set()
    for b in tools["bindings"]:
        if not isinstance(b, dict) or set(b) - {"tool_ref", "schema_digest", "required", "defaults", "fixed", "constraints"}:
            raise ControlError("invalid_config", "Invalid tool binding")
        key = ref_key(b.get("tool_ref"))
        seen.add(key)
        if type(b.get("required", True)) is not bool:
            raise ControlError("invalid_config", "required must be boolean")
        for field in ("defaults", "fixed"):
            if not isinstance(b.get(field, {}), dict):
                raise ControlError("invalid_config", field + " must be an object")
        if not isinstance(b.get("constraints", []), list):
            raise ControlError("invalid_config", "constraints must be an array")
        for rule in b.get("constraints", []):
            if not isinstance(rule, dict) or set(rule) - {"pointer", "kind", "values", "min", "max", "roots", "hosts", "schemes", "ports"}:
                raise ControlError("invalid_config", "Invalid parameter rule")
            pointer_parts(rule.get("pointer"))
            if rule.get("kind") not in {"enum", "number", "length", "path", "url"}:
                raise ControlError("invalid_config", "Unsupported parameter rule")
            if rule["kind"] == "enum" and not isinstance(rule.get("values"), list):
                raise ControlError("invalid_config", "enum requires values")
            if rule["kind"] == "path" and (not isinstance(rule.get("roots"), list) or not rule["roots"]):
                raise ControlError("invalid_config", "path requires roots")
            if rule["kind"] == "path" and any(not isinstance(root, str) or (root != "$workspace" and not Path(root).expanduser().is_absolute()) for root in rule["roots"]):
                raise ControlError("invalid_config", "Path roots require absolute paths or $workspace")
            if rule["kind"] == "url" and (not isinstance(rule.get("hosts"), list) or not rule["hosts"]):
                raise ControlError("invalid_config", "url requires hosts")
            if rule["kind"] == "url":
                if any(not isinstance(host, str) or not host or any(x in host for x in ("/", "@", "*", ":")) for host in rule["hosts"]):
                    raise ControlError("invalid_config", "URL hosts require exact DNS names or IPv4 addresses")
                if not isinstance(rule.get("schemes", ["https"]), list) or not rule.get("schemes", ["https"]) or any(s not in {"https", "http"} for s in rule.get("schemes", ["https"])):
                    raise ControlError("invalid_config", "URL schemes must be http or https")
                if not isinstance(rule.get("ports", [443]), list) or not rule.get("ports", [443]) or any(type(p) is not int or not 1 <= p <= 65535 for p in rule.get("ports", [443])):
                    raise ControlError("invalid_config", "URL ports must be integers from 1 to 65535")
            for bound in ("min", "max"):
                if bound in rule and (type(rule[bound]) not in {int, float} or not math.isfinite(rule[bound])):
                    raise ControlError("invalid_config", "Bounds must be finite numbers")
            if "min" in rule and "max" in rule and rule["min"] > rule["max"]:
                raise ControlError("invalid_config", "Empty parameter range")
        for field, val in b.get("fixed", {}).items():
            candidate = {**b.get("defaults", {}), **b.get("fixed", {})}
            validate_arguments(candidate, b, Path.cwd(), semantic=False)
            break
    return value


def pointer_parts(pointer):
    if not isinstance(pointer, str) or not pointer.startswith("/") or pointer == "/":
        raise ControlError("invalid_config", "A non-empty JSON pointer is required")
    return [p.replace("~1", "/").replace("~0", "~") for p in pointer[1:].split("/")]


def pointer_get(args, pointer):
    value = args
    try:
        for part in pointer_parts(pointer):
            value = value[int(part)] if isinstance(value, list) else value[part]
        return value, True
    except (KeyError, IndexError, ValueError, TypeError):
        return None, False


def validate_arguments(args, binding, workspace, *, semantic=True):
    for rule in binding.get("constraints", []):
        value, exists = pointer_get(args, rule["pointer"])
        if not exists:
            continue
        kind = rule["kind"]
        valid = True
        if kind == "enum":
            valid = any(type(value) is type(x) and value == x for x in rule["values"])
        elif kind == "number":
            valid = type(value) in {int, float} and math.isfinite(value) and rule.get("min", -math.inf) <= value <= rule.get("max", math.inf)
        elif kind == "length":
            valid = isinstance(value, (str, list)) and rule.get("min", 0) <= len(value) <= rule.get("max", math.inf)
        elif kind == "path" and semantic:
            if not isinstance(value, str):
                valid = False
            else:
                from agent_tools import prepare_agent_workspace_path_literal
                literal = prepare_agent_workspace_path_literal(value)
                path = Path(literal).expanduser()
                if binding.get("tool_ref", {}).get("name") in {"run_shell", "terminal_open"}:
                    from agent_tools import _resolve_shell_working_dir
                    path = _resolve_shell_working_dir(value, workspace)
                else:
                    path = workspace.resolve() if literal in {"", "/"} else path.resolve() if path.is_absolute() else (workspace / literal.lstrip("/")).resolve()
                roots = [workspace if x == "$workspace" else Path(x).expanduser().resolve() for x in rule["roots"]]
                valid = any(path == root or root in path.parents for root in roots)
        elif kind == "url" and semantic:
            try:
                url = urlsplit(value)
                host = (url.hostname or "").encode("idna").decode("ascii").lower().rstrip(".")
                hosts = {h.encode("idna").decode("ascii").lower().rstrip(".") for h in rule["hosts"]}
                valid = not url.username and not url.password and host in hosts and url.scheme in rule.get("schemes", ["https"])
                valid = valid and (url.port or (443 if url.scheme == "https" else 80)) in rule.get("ports", [443])
            except (ValueError, TypeError, AttributeError):
                valid = False
        if not valid:
            raise ControlError("tool_constraint_denied", "Parameter violates " + kind + " constraint at " + rule["pointer"], status=403)


def from_metadata(meta):
    raw = meta.get("session_runtime_config")
    if isinstance(raw, dict):
        return validate_config(raw)
    return validate_config({"system_prompt": {"mode": meta.get("system_context_mode", "append"),
                                              "text": meta.get("system_context", "")}})


def resolve_config(base, override=None):
    value = validate_config(base)
    extra = validate_config(override or {}, partial=True)
    if "system_prompt" in extra:
        prompt = extra.pop("system_prompt")
        if prompt["mode"] == "append":
            value["system_prompt"]["text"] += "\n\n" + prompt["text"] if prompt["text"] else ""
        else:
            value["system_prompt"] = prompt
    if "tools" in extra:
        old, new = value["tools"], extra.pop("tools")
        if old["mode"] == "custom" and new["mode"] == "custom":
            allowed = {ref_key(r) for r in old["allow"]}
            new["allow"] = [r for r in new["allow"] if ref_key(r) in allowed]
        elif old["mode"] == "custom":
            new["mode"], new["allow"] = "custom", old["allow"]
        new["deny"] = old["deny"] + new["deny"]
        # Keep both layers: intersections are enforced by sequential validation.
        new["bindings"] = old["bindings"] + new["bindings"]
        value["tools"] = new
    if "limits" in extra:
        old_limits = value.get("limits", {})
        value["limits"] = {**old_limits, **{k: min(v, old_limits.get(k, v)) for k, v in extra.pop("limits").items()}}
    if "read_only" in extra:
        value["read_only"] = bool(value.get("read_only")) or extra.pop("read_only")
    value.update(extra)
    grouped = {}
    for binding in value["tools"]["bindings"]:
        grouped.setdefault(ref_key(binding["tool_ref"]), []).append(binding)
    for bindings in grouped.values():
        fixed, bounds, enums = {}, {}, {}
        for binding in bindings:
            for key, item in binding.get("fixed", {}).items():
                if key in fixed and (type(fixed[key]) is not type(item) or fixed[key] != item):
                    raise ControlError("config_conflict", "Conflicting fixed tool parameter: " + key, status=409)
                fixed[key] = item
            for rule in binding.get("constraints", []):
                identity = (rule["pointer"], rule["kind"])
                if rule["kind"] in {"number", "length"}:
                    low, high = bounds.get(identity, (-math.inf, math.inf))
                    bounds[identity] = (max(low, rule.get("min", -math.inf)), min(high, rule.get("max", math.inf)))
                    if bounds[identity][0] > bounds[identity][1]:
                        raise ControlError("config_conflict", "Tool parameter ranges do not intersect", status=409)
                if rule["kind"] == "enum":
                    options = [json.dumps(x, sort_keys=True) for x in rule["values"]]
                    enums[identity] = set(options) & enums.get(identity, set(options))
                    if not enums[identity]:
                        raise ControlError("config_conflict", "Tool parameter enums do not intersect", status=409)
        for binding in bindings:
            validate_arguments(fixed, binding, Path.cwd(), semantic=False)
    return value


@contextmanager
def runtime_scope(sid, config, authority=None, principal=None):
    token = _active.set((sid, copy.deepcopy(config)))
    guard = _authority_check.set(authority)
    actor = _principal_context.set(principal or _principal_context.get())
    try:
        yield
    finally:
        _authority_check.reset(guard)
        _principal_context.reset(actor)
        _active.reset(token)


def active_config(sid, meta=None):
    current = _active.get()
    if current and current[0] == sid:
        return current[1]
    return from_metadata(meta or {})


def apply_metadata(sid, meta):
    meta = dict(meta)
    cfg = active_config(sid, meta)
    p = cfg["system_prompt"]
    meta.update(system_context=p["text"], system_context_mode=p["mode"])
    meta["_resolved_control_config"] = cfg
    return meta


def filter_registry(registry, config):
    policy = config["tools"]
    if policy["mode"] == "inherit" and not policy["deny"] and not policy["bindings"] and not config.get("read_only"):
        return registry
    allow, deny = {ref_key(x) for x in policy["allow"]}, {ref_key(x) for x in policy["deny"]}
    removed = []
    descriptors = list(registry._descriptors.values())
    present = {ref_key(tool_ref(d)): d for d in descriptors}
    for binding in policy["bindings"]:
        key = ref_key(binding["tool_ref"])
        if key in deny or (policy["mode"] == "custom" and key not in allow):
            continue
        d = present.get(key)
        if d is None or not d.executable or (binding.get("schema_digest") and binding["schema_digest"] != digest(d.openai_definition()["function"].get("parameters", {}))):
            if binding.get("required", True):
                raise ControlError("required_tool_unavailable", "Required tool is missing or its schema changed: " + binding["tool_ref"]["name"], status=409)
            deny.add(ref_key(binding["tool_ref"]))
    for d in descriptors:
        key = ref_key(tool_ref(d))
        if key in deny or (policy["mode"] == "custom" and key not in allow) or (config.get("read_only") and d.effect != "read"):
            removed.append(d.name)
    for name in removed:
        registry._descriptors.pop(name, None)
    return registry


def constrain_call(sid, descriptor, args, workspace, *, inject=True):
    authority = _authority_check.get()
    if authority:
        authority()
    cfg = active_config(sid)
    policy = cfg["tools"]
    if hasattr(descriptor, "invocation_kind"):
        _executing_tool.set(ref_key(tool_ref(descriptor)))
    if cfg.get("read_only") and descriptor.effect != "read":
        raise ControlError("tool_scope_denied", "This execution is read-only", status=403)
    if policy["mode"] == "inherit" and not policy["deny"] and not policy["bindings"]:
        return args
    key = ref_key(tool_ref(descriptor))
    if key in {ref_key(x) for x in policy["deny"]} or (policy["mode"] == "custom" and key not in {ref_key(x) for x in policy["allow"]}):
        raise ControlError("tool_scope_denied", "Tool is not allowed by this execution", status=403)
    args = copy.deepcopy(args)
    bindings = [b for b in policy["bindings"] if ref_key(b["tool_ref"]) == key]
    for b in reversed(bindings):
        if inject:
            for name, value in b.get("defaults", {}).items():
                args.setdefault(name, copy.deepcopy(value))
    for b in bindings:
        for name, value in b.get("fixed", {}).items():
            if name not in args and not inject:
                raise ControlError("tool_constraint_denied", "Fixed parameter was removed: " + name, status=403)
            if name in args and (type(args[name]) is not type(value) or args[name] != value):
                raise ControlError("tool_constraint_denied", "Fixed parameter conflict: " + name, status=403)
            if inject:
                args[name] = copy.deepcopy(value)
    properties = descriptor.openai_definition()["function"].get("parameters", {}).get("properties", {})
    for binding in bindings:
        for rule in binding.get("constraints", []):
            root = pointer_parts(rule["pointer"])[0]
            if root not in args and "default" in properties.get(root, {}):
                args[root] = copy.deepcopy(properties[root]["default"])
    for b in bindings:
        validate_arguments(args, b, Path(workspace))
    if bindings:
        from jsonschema import Draft202012Validator, ValidationError
        try:
            Draft202012Validator(descriptor.openai_definition()["function"].get("parameters", {})).validate(args)
        except ValidationError as exc:
            raise ControlError("invalid_tool_arguments", "Bound arguments do not match the tool schema") from exc
    return args


class ConfigRepository:
    def __init__(self, manager):
        self.manager = manager

    def get(self, sid):
        meta = self.manager._load_metadata(sid)
        return {"session_id": sid, "revision": int(meta.get("runtime_config_revision", 0)),
                "config": from_metadata(meta)}

    def update(self, sid, raw, expected):
        config = validate_config(raw)
        manager = self.manager
        with manager._session_metadata_lock(sid):
            meta = manager._load_metadata_unlocked(sid)
            if not meta:
                raise ControlError("session_not_found", "Session not found", status=404)
            revision = int(meta.get("runtime_config_revision", 0))
            if expected != revision:
                raise ControlError("revision_conflict", "Reload configuration before saving", status=409, details={"revision": revision})
            meta["session_runtime_config"] = config
            meta["runtime_config_revision"] = revision + 1
            meta["system_context"] = config["system_prompt"]["text"]
            meta["system_context_mode"] = config["system_prompt"]["mode"]
            for field in ("model_profile_id", "reasoning_effort"):
                if field in config:
                    meta[field] = config[field]
            manager._save_metadata_unlocked(sid, meta)
        return self.get(sid)
