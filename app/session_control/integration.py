"""Small integration seams; application code keeps its existing domain owners."""
from __future__ import annotations

import copy
import asyncio
import time
from functools import wraps

from . import configuration as config

_application = None


def application():
    return _application


def install(app, dependencies, remote_config, callbacks):
    global _application
    from remote_control.store import RemoteControlStore
    from security.store import security_state_dir
    from .api import register_control
    import os
    from pathlib import Path
    state_dir = Path(os.environ["MYAGENT_SESSION_CONTROL_HOME"]) if os.getenv("MYAGENT_SESSION_CONTROL_HOME") else security_state_dir().parent / "session-control"
    _application = register_control(app, dependencies, state_dir,
                                    RemoteControlStore(remote_config.state_dir), callbacks=callbacks)
    config.configure_repository(_application.service.configs)
    return _application


def managed_turn(fn):
    @wraps(fn)
    async def run(state, *args, **kwargs):
        manager = fn.__globals__["session_manager"]
        sid = str(state.get("session_id") or "")
        turn = str(state.get("_runtime_v2_turn_id") or state.get("_change_review_turn_id") or state.get("_runtime_v2_run_id") or "")
        previous = state.get("_control_turn_key")
        if previous != turn or "_control_execution_config" not in state:
            try:
                meta = manager._load_metadata(sid) or {}
            except ValueError:
                if turn:
                    raise
                # Standalone in-memory ReAct callers have no persisted session yet.
                meta = {}
            saved = None
            app = _application
            if app is not None and app.service.manager is manager and turn:
                saved = app.store.get("runtime_configs", sid + ":" + turn)
            # The first controlled turn can have a temporary automation overlay.
            resolved = saved["config"] if saved else config.active_config(sid, meta) if previous is None else config.from_metadata(meta)
            state["_control_execution_config"] = copy.deepcopy(resolved)
            state["_control_turn_key"] = turn
            state["_control_tool_calls"] = 0
            state["_control_started_monotonic"] = time.monotonic()
            if app is not None and app.service.manager is manager and turn and not saved:
                record = {"config": resolved, "turn_id": turn, "run_id": state.get("_runtime_v2_run_id")}
                app.store.put("runtime_configs", sid + ":" + turn, record, expected=0)
                run_id = str(state.get("_runtime_v2_run_id") or "")
                if previous is None and run_id != turn and not app.store.get("runtime_configs", sid + ":" + run_id):
                    app.store.put("runtime_configs", sid + ":" + run_id, record, expected=0)
        with config.runtime_scope(sid, state["_control_execution_config"], config._authority_check.get()):
            timeout = state["_control_execution_config"].get("limits", {}).get("timeout_seconds")
            if timeout:
                remaining = max(.001, timeout - (time.monotonic() - state["_control_started_monotonic"]))
                return await asyncio.wait_for(fn(state, *args, **kwargs), remaining)
            return await fn(state, *args, **kwargs)
    return run


def redirect_allowed(url):
    current = config._active.get()
    if not current:
        return
    for binding in current[1]["tools"]["bindings"]:
        if config.ref_key(binding["tool_ref"]) == config._executing_tool.get() and binding["tool_ref"]["name"] in {"web_fetch", "web_download"}:
            for rule in binding.get("constraints", []):
                if rule["kind"] == "url":
                    config.validate_arguments({"url": url}, {"constraints": [{**rule, "pointer": "/url"}]}, __import__("pathlib").Path.cwd())


def consume_tool_budget(state):
    from .errors import ControlError
    limit = state.get("_control_execution_config", {}).get("limits", {}).get("max_tool_calls")
    count = state.get("_control_tool_calls", 0)
    if limit is not None and count >= limit:
        raise ControlError("tool_budget_exhausted", "Execution tool-call budget exhausted", status=403)
    state["_control_tool_calls"] = count + 1


def shell_background_allowed():
    current = config._active.get()
    if not current:
        return True
    for binding in current[1]["tools"]["bindings"]:
        if config.ref_key(binding["tool_ref"]) != config._executing_tool.get():
            continue
        if binding.get("fixed", {}).get("run_in_background") is False:
            return False
        for rule in binding.get("constraints", []):
            if rule["pointer"] == "/run_in_background" and rule["kind"] == "enum" and not any(value is True for value in rule["values"]):
                return False
    return True


def child_environment(env):
    """Bind CLI child calls to a task identity, never the user's saved credential."""
    from security.runtime import active_security_context
    ctx = active_security_context()
    if not ctx:
        return env
    value = dict(env)
    value["MYAGENT_CONTROL_TASK"] = "1"
    value.pop("MYAGENT_CONTROL_TOKEN", None)
    if _application is None:
        return value
    from .policy import Principal, validate_policy
    sid = ctx["session_id"]
    parent = config._principal_context.get()
    policy = parent.policy if parent is not None else validate_policy({}, workspace=str(ctx["workspace"]), current_session=sid)
    principal = Principal("agent:" + sid, "Agent CLI", False, policy,
                          parent_id=parent.parent_id or parent.id if parent else "",
                          parent_credential=(parent.parent_credential or parent.credential_id) if parent else "",
                          delegated_policies=parent.delegated_policies if parent else [],
                          source_ancestors=parent.source_ancestors if parent else [],
                          runtime_ceiling={k: v for k, v in config.active_config(sid).items() if k in {"tools", "limits", "read_only"}})
    value["MYAGENT_CONTROL_TOKEN"] = _application.identities.issue(principal, ttl=3600)
    return value


def summary_changed(manager, sid, fields):
    app = _application
    if app is None or app.service.manager is not manager:
        return
    changes = sorted(set(fields) & {"created", "deleted", "archived", "name", "work_dir"})
    if not changes:
        return
    from datetime import datetime, timezone
    from .store import digest
    row = next((dict(r) for r in manager.index if r.get("id") == sid), {})
    app.store.append_event({"specversion": "1.0", "source": "session-state/" + sid,
        "id": digest({"fields": changes, "summary": row}), "type": "session.lifecycle_changed", "subject": sid,
        "time": str(row.get("updated_at") or datetime.now(timezone.utc).isoformat()),
        "data": {"fields": changes, "summary": row}})


def session_stopped(manager, sid, reason):
    app = _application
    if app is None or app.service.manager is not manager or reason not in {"user", "user_button", "manual", "manual_stop", "stop_button", "remote_user", "control_stop", "user_stop", "session_deleted"}:
        return
    for op in app.store.operations(status="queued", session_id=sid, limit=1000):
        if op["method"] in {"session.send", "session.continue", "session.recover"}:
            app.store.update_operation(op["id"], expected="queued", status="cancelled", delivery="cancelled")
    for op in app.store.operations(status="running", session_id=sid, limit=1000):
        app.service.mark_cancelled(op)
