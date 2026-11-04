"""Model tools for the same durable schedules shown in native settings.

Only HostToolInvocationContext supplies identity, workspace and origin. Model
arguments cannot supply a policy, source, credential or administrator flag.
"""
from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime
from zoneinfo import ZoneInfo

from tool_registry import ToolOutcome

from . import configuration as config
from .errors import ControlError
from .policy import Principal, check_session, validate_policy
from .public import control_application, on_service_loop
from .scheduling import instant
from .settings_api import local_trigger


READ_ACTIONS = ("list", "get", "history")
WRITE_ACTIONS = ("create", "update", "pause", "resume", "run", "delete")
EXECUTION_CAPS = ("read", "session.create", "session.send")
CAPABILITIES = (*EXECUTION_CAPS, *("automation." + action for action in (*READ_ACTIONS, *WRITE_ACTIONS)))

TRIGGER_SCHEMA = {"type": "object", "properties": {
    "kind": {"type": "string", "enum": ["at", "after", "interval", "daily", "weekdays", "weekly", "monthly", "cron"]},
    "at": {"type": "string", "description": "One-shot ISO date/time with UTC offset, e.g. 2030-04-01T09:00:00+08:00."},
    "local_at": {"type": "string", "description": "One-shot local date/time, e.g. 2030-04-01T09:00; interpreted in time_zone."},
    "seconds": {"type": "number", "exclusiveMinimum": 0, "description": "after: delay; interval: fixed interval, at least 60 seconds."},
    "time": {"type": "string", "description": "Calendar time HH:MM; default 09:00."},
    "time_zone": {"type": "string", "description": "IANA timezone; default Asia/Shanghai."},
    "weekdays": {"type": "array", "minItems": 1, "items": {"type": "integer", "minimum": 1, "maximum": 7}, "description": "weekly: ISO weekdays, Monday=1, Sunday=7."},
    "days": {"type": "array", "minItems": 1, "items": {"type": "integer", "minimum": 1, "maximum": 31}, "description": "monthly: month days; nonexistent dates are skipped."},
    "expression": {"type": "string", "description": "Numeric five-field cron, e.g. 0 9 * * 1-5."},
}, "required": ["kind"], "additionalProperties": False}


def _definition(name, description, properties):
    return {"type": "function", "function": {"name": name, "description": description,
        "parameters": {"type": "object", "properties": properties, "required": ["action"], "additionalProperties": False}}}


TOOL_DEFINITIONS = [
    _definition("scheduled_tasks", "Query durable scheduled tasks (定时任务) created by this chat/caller: list, get details, or execution history. "
        "These are the same tasks shown in Settings > Scheduled tasks. Read a task's revision before modifying it with manage_scheduled_task.", {
        "action": {"type": "string", "enum": list(READ_ACTIONS)},
        "id": {"type": "string", "minLength": 1, "description": "Required for get/history; use the task ID returned by create/list."},
        "limit": {"type": "integer", "minimum": 1, "maximum": 100, "description": "Maximum history entries; default 20."},
    }),
    _definition("manage_scheduled_task", "Create or manage a backend-owned scheduled task (定时任务). Use when the user asks for a reminder, recurring work, or future agent action; "
        "do not create unsolicited schedules. Tasks appear in Settings > Scheduled tasks and survive closing chat. "
        "create requires name, instructions and trigger. Default target is this chat; new_chat creates a new chat each run in this workspace. "
        "update/pause/resume/delete require id and expected_revision from scheduled_tasks. run enqueues one manual execution without changing the normal schedule. "
        "Never report completion from an acceptance receipt. Runtime overrides cannot expand the caller's tools, budgets or authorization. "
        "After creation, show_user(kind='settings', section='schedules') can open the task page if useful.", {
        "action": {"type": "string", "enum": list(WRITE_ACTIONS)},
        "id": {"type": "string", "minLength": 1},
        "expected_revision": {"type": "integer", "minimum": 0},
        "name": {"type": "string", "minLength": 1, "maxLength": 160},
        "instructions": {"type": "string", "minLength": 1, "description": "Ordinary task input; not a system prompt."},
        "trigger": TRIGGER_SCHEMA,
        "session_id": {"type": "string", "minLength": 1, "description": "Optional existing target within the caller's scope; default current chat."},
        "new_chat": {"type": "boolean", "description": "Create a new chat on each run; no session_id together with true."},
        "enabled": {"type": "boolean", "description": "Default true; false saves a paused task."},
        "notification": {"type": "string", "enum": ["important", "always", "never"], "description": "Default important: failures, unknown results and required user action."},
        "misfire": {"type": "string", "enum": ["latest", "skip"], "description": "Recovery after downtime; default latest."},
        "max_runs": {"type": ["integer", "null"], "minimum": 1, "description": "Maximum planned runs, excluding manual runs; null means unlimited."},
        "end_at": {"type": ["string", "null"], "description": "Optional end time with explicit UTC offset; null removes it."},
        "runtime_override": {"type": "object", "description": "Optional existing session-control config: system_prompt, tools, model_profile_id, reasoning_effort, read_only, limits. Host validates all fields and retains the caller's execution ceiling."},
        "idempotency_key": {"type": "string", "minLength": 1, "maxLength": 200, "description": "Reuse this key and identical arguments after an uncertain response. Otherwise the host uses the trusted tool call ID."},
    }),
]


def _arguments(name, arguments):
    from jsonschema import Draft202012Validator, ValidationError
    schema = next(row["function"]["parameters"] for row in TOOL_DEFINITIONS if row["function"]["name"] == name)
    try:
        Draft202012Validator(schema).validate(arguments)
    except ValidationError as exc:
        raise ControlError("invalid_params", exc.message) from exc
    return copy.deepcopy(arguments)


def _actor(context, app, parent):
    manager = context.service("session_manager")
    if manager is not app.service.manager:
        raise ControlError("control_unavailable", "The current runtime belongs to a different backend", status=503)
    from agent_harness import session_work_root
    meta = manager._load_metadata(context.session_id)
    if not meta:
        raise ControlError("session_not_found", "Current session is unavailable", status=404)
    workspace = str(session_work_root(meta))
    policy = copy.deepcopy(parent.policy) if parent and not parent.admin else validate_policy({}, workspace=workspace, current_session=context.session_id)
    policy = validate_policy(policy, workspace=workspace, current_session=context.session_id)
    policy["capabilities"] = [method for method in CAPABILITIES if parent is None or parent.permits(method)]
    current = config.active_config(context.session_id, meta)
    if parent and parent.runtime_ceiling:
        current = config.resolve_config(current, parent.runtime_ceiling)
    ceiling = {key: copy.deepcopy(current[key]) for key in ("tools", "limits", "read_only") if key in current}
    actor = Principal(parent.id if parent else "agent-schedules:" + context.session_id, "Agent scheduled tasks", False,
        policy, "host", parent_id=(parent.parent_id or parent.id) if parent else "",
        parent_credential=(parent.parent_credential or parent.credential_id) if parent else "",
        delegated_policies=([parent.policy] if parent and not parent.admin else []) + (parent.delegated_policies if parent else []),
        source_ancestors=copy.deepcopy(parent.source_ancestors) if parent else [], runtime_ceiling=ceiling)
    check_session(actor, context.session_id, manager)
    return actor, workspace, current


def _check_task(app, actor, row):
    if row.get("deleted"):
        raise ControlError("not_found", "Scheduled task was deleted", status=404)
    if row["trigger"]["kind"] == "event":
        raise ControlError("invalid_schedule", "This tool manages time triggers only")
    target = row["target"]
    if target["mode"] == "existing":
        check_session(actor, target["session_id"], app.service.manager)
    else:
        app.service.check_workspace(actor, row["workspace"])


def _public_result(result):
    value = copy.deepcopy(result)
    if value.get("next_run_at"):
        zone = ZoneInfo(value.get("trigger", {}).get("time_zone", "Asia/Shanghai"))
        value["next_run_at_iso"] = datetime.fromtimestamp(value["next_run_at"], zone).isoformat()
    value["settings_section"] = "schedules"
    return value


async def _execute(context, arguments, *, read):
    name = "scheduled_tasks" if read else "manage_scheduled_task"
    args = _arguments(name, dict(arguments))
    action = args.pop("action")
    if action in {"get", "history", "update", "pause", "resume", "run", "delete"} and not args.get("id"):
        raise ControlError("invalid_params", "id is required")
    if action in {"update", "pause", "resume", "delete"} and "expected_revision" not in args:
        raise ControlError("revision_required", "Read the task and provide expected_revision", status=409)
    if action == "create" and (not all(args.get(key, "").strip() for key in ("name", "instructions")) or "trigger" not in args):
        raise ControlError("invalid_params", "create requires name, instructions and trigger")
    explicit_key = args.pop("idempotency_key", None)
    key = explicit_key or context.tool_call_id
    if not read and not key:
        raise ControlError("idempotency_key_required", "A trusted tool call ID or stable idempotency key is required")
    app, parent = control_application(), config._principal_context.get()
    authority = config._authority_check.get()
    if authority:
        authority()
    # Capture host context before crossing to the backend loop. Never read a
    # credential from model arguments or fall back to the settings admin.
    actor, workspace, current = _actor(context, app, parent)
    if not read and current.get("read_only"):
        raise ControlError("tool_scope_denied", "This execution is read-only", status=403)

    async def invoke():
        app.service.authorize(actor, "automation." + action, {})
        row = None
        if args.get("id"):
            row = app.service.require_document("automations", args["id"], actor)
            _check_task(app, actor, row)
        if read:
            params = {**args, "kind_filter": "schedule"} if action == "list" else args
            if action == "history":
                params.setdefault("limit", 20)
            result, _ = await app.service.execute(actor, "automation." + action, params)
            if action == "list":
                visible = []
                for item in result["items"]:
                    try:
                        _check_task(app, actor, item)
                    except ControlError:
                        continue
                    visible.append(_public_result(item))
                result["items"] = visible
            return _public_result(result)
        params = dict(args)
        if action in {"create", "update"}:
            if row and row["action"].get("kind", "prompt") != "prompt":
                raise ControlError("invalid_schedule", "Only prompt tasks can be edited with this tool")
            if "instructions" in params:
                params["action"] = {"kind": "prompt", "text": params.pop("instructions")}
            if "trigger" in params:
                params["trigger"] = local_trigger(params["trigger"])
                ZoneInfo(params["trigger"].get("time_zone", "Asia/Shanghai"))
            if "end_at" in params and params["end_at"] is not None:
                params["end_at"] = instant(params["end_at"])
            if "runtime_override" in params:
                config.resolve_config(current, params["runtime_override"])
            if action == "create" or "session_id" in params or "new_chat" in params:
                new_chat = params.pop("new_chat", False)
                sid = params.pop("session_id", context.session_id)
                if new_chat:
                    if "session_id" in args:
                        raise ControlError("invalid_target", "new_chat and session_id cannot be combined")
                    if actor.policy.get("scope") not in {"workspace", "workspaces", "all"}:
                        raise ControlError("scope_denied", "This caller cannot create independent target chats", status=403)
                    params["target"] = {"mode": "new"}
                    params["workspace"] = workspace
                else:
                    params["target"] = {"mode": "existing", "session_id": sid}
                # Validate nested targets even when execute() will replay a
                # previous admission rather than enter automation.mutate().
                if new_chat:
                    app.service.authorize(actor, "session.create", {})
                    app.service.check_workspace(actor, workspace)
                    if not actor.permits("session.send"):
                        raise ControlError("forbidden", "Scheduled execution requires session.send", status=403)
                else:
                    app.service.authorize(actor, "session.send", {"session_id": sid})
            policy = copy.deepcopy(actor.policy)
            policy["capabilities"] = [cap for cap in EXECUTION_CAPS if actor.permits(cap)]
            params["policy"] = policy
            if action == "create":
                params.setdefault("notification", "important")
                params.setdefault("misfire", "latest")
        elif set(params) - {"id", "expected_revision"}:
            raise ControlError("invalid_params", action + " accepts only id, expected_revision and idempotency_key")
        if action == "run":
            if row["action"].get("kind", "prompt") != "prompt":
                raise ControlError("invalid_schedule", "This tool can manually run prompt tasks only")
            if row["target"]["mode"] == "existing":
                app.service.authorize(actor, "session.send", {"session_id": row["target"]["session_id"]})
            else:
                app.service.authorize(actor, "session.create", {})
                if not actor.permits("session.send"):
                    raise ControlError("forbidden", "Manual execution requires session.send", status=403)
        origin = [context.session_id, "explicit", key] if explicit_key else [context.session_id, context.run_id, key]
        identity = "model-schedule:" + hashlib.sha256(json.dumps(origin).encode()).hexdigest()
        result, _ = await app.service.execute(actor, "automation." + action, params, idempotency_key=identity)
        return _public_result(result)

    return await on_service_loop(app.service, invoke)


async def invoke_scheduled_tasks(context, arguments):
    return await _outcome(context, arguments, read=True)


async def invoke_manage_scheduled_task(context, arguments):
    return await _outcome(context, arguments, read=False)


async def _outcome(context, arguments, *, read):
    try:
        result = await _execute(context, arguments, read=read)
        return ToolOutcome.completed(json.dumps(result, ensure_ascii=False))
    except ControlError as exc:
        return ToolOutcome.failed(exc.code, str(exc), content=json.dumps({"error": {
            "code": exc.code, "message": str(exc), "details": exc.details}}, ensure_ascii=False))
    except (ValueError, TypeError, KeyError) as exc:
        return ToolOutcome.failed("invalid_params", str(exc))
