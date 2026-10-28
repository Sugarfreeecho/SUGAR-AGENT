"""Permission-checked host services available to isolated plugin workers."""
from __future__ import annotations

import logging
import threading
import time
import uuid
from typing import Any, Dict, Mapping, Sequence

from plugins.models import PluginDefinition


logger = logging.getLogger(__name__)
_reservation_lock = threading.RLock()
_session_run_grants: Dict[str, tuple[str, frozenset[str], float]] = {}
_TERMINAL_RUN_STATUSES = frozenset(
    {
        "completed",
        "finished",
        "failed",
        "cancelled",
        "interrupted",
        "orphaned",
        "stale",
    }
)


class PluginHostServiceError(RuntimeError):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = int(status)
        self.code = str(code)


def _declared_services(plugin: PluginDefinition) -> frozenset[str]:
    permissions = dict(plugin.permissions or {})
    raw = permissions.get("services")
    if isinstance(raw, Mapping):
        values = {str(key) for key, enabled in raw.items() if bool(enabled)}
    elif isinstance(raw, (list, tuple, set, frozenset)):
        values = {str(item) for item in raw}
    elif isinstance(raw, str):
        values = {raw}
    else:
        values = set()
    return frozenset(values)


def _session_is_active(session_id: str) -> bool:
    try:
        from runtime_observability import snapshot

        data = snapshot(session_id)
        runs = data.get("runs") if isinstance(data, dict) else None
        if isinstance(runs, list):
            return any(
                str((run or {}).get("status") or "").lower()
                not in _TERMINAL_RUN_STATUSES
                for run in runs
                if isinstance(run, dict)
            )
    except Exception:
        logger.debug("Plugin session activity check failed", exc_info=True)
    return False


def _sessions_run_many(
    plugin: PluginDefinition,
    action: Mapping[str, Any],
    *,
    authorized_session_ids: frozenset[str],
    request_key: str,
) -> Dict[str, Any]:
    from agent_harness import session_manager
    from session_control.public import host_client
    from session_control.errors import ControlError

    rows = action.get("sessions")
    if not isinstance(rows, list) or not 1 <= len(rows) <= 8:
        raise PluginHostServiceError(400, "invalid_service_request", "sessions.run_many requires 1-8 requests")
    requests, seen = [], set()
    for row in rows:
        if not isinstance(row, Mapping):
            raise PluginHostServiceError(400, "invalid_service_request", "Invalid session request")
        sid, prompt = str(row.get("session_id") or "").strip(), str(row.get("prompt") or "")
        if not sid or sid in seen or not prompt.strip() or len(prompt) > 50_000:
            raise PluginHostServiceError(400, "invalid_service_request", "Invalid session or prompt")
        if session_manager.get_session_summary(sid) is None:
            raise PluginHostServiceError(404, "session_not_found", "Session not found: " + sid)
        seen.add(sid)
        requests.append({"session_id": sid, "message": prompt, "mode": "queue"})
    if not authorized_session_ids:
        raise PluginHostServiceError(403, "session_run_grant_required", "A host-issued session grant is required")
    if frozenset(seen) != authorized_session_ids:
        raise PluginHostServiceError(403, "session_scope_denied", "Session grant does not match requested sessions")
    try:
        client = host_client(plugin.plugin_id, session_ids=sorted(seen),
            capabilities=["session.send", "session.send_batch", "operation.cancel"])
        result = client.blocking("session.send_batch", {"requests": requests}, key=request_key)
    except ControlError as exc:
        raise PluginHostServiceError(exc.status, exc.code, str(exc)) from exc
    operations = result["operations"]
    return {"service": "sessions.run_many", "accepted": True,
            "session_ids": [row["session_id"] for row in operations],
            "run_ids": [row["run_id"] for row in operations],
            "operation_ids": [row["operation_id"] for row in operations],
            "operations": operations}


def release_plugin_leases(plugin_id: str, *, cancel_runs: bool = True) -> int:
    from session_control.integration import application
    app = application()
    if app is None:
        return 0
    from session_control.public import source_state
    source_state(plugin_id, False, app=app)
    operations = app.store.source_operations(plugin_id)
    if cancel_runs:
        for operation in operations:
            if operation["status"] == "queued":
                app.store.update_operation(operation["id"], expected="queued", status="cancelled", delivery="cancelled")
            else:
                app.service.mark_cancelled(operation)
                app.service.manager.request_interrupt(operation["session_id"], operation["run_id"], reason="plugin_disabled")
    return len(operations)


def release_all_plugin_leases(*, cancel_runs: bool = True) -> int:
    from session_control.integration import application
    app = application()
    if app is None:
        return 0
    return sum(release_plugin_leases(row["id"], cancel_runs=cancel_runs)
               for row in app.store.list("host_sources")
               if not row["id"].startswith("@runtime/")
               if not app.service.callbacks.get("source_enabled", lambda _: False)(row["id"]))


def execute_host_actions(
    plugin: PluginDefinition,
    actions: Any,
    *,
    trusted_session_id: str = "",
    trusted_run_id: str = "",
    trusted_session_ids: Sequence[str] = (),
) -> list[Dict[str, Any]]:
    if actions is None:
        return []
    if not isinstance(actions, list) or len(actions) > 16:
        raise PluginHostServiceError(400, "invalid_host_actions", "Host actions must be a list")
    allowed = _declared_services(plugin)
    authorized_session_ids = frozenset(
        str(item or "").strip() for item in trusted_session_ids if str(item or "").strip()
    )
    if not authorized_session_ids and str(trusted_session_id or "").strip():
        authorized_session_ids = frozenset({str(trusted_session_id).strip()})
    results = []
    from session_control.public import stable_key
    for index, action in enumerate(actions):
        if not isinstance(action, Mapping):
            raise PluginHostServiceError(400, "invalid_host_action", "Host action must be an object")
        service = str(action.get("service") or "").strip()
        if service not in allowed:
            raise PluginHostServiceError(
                403,
                "service_permission_denied",
                f"Plugin is not authorized for host service {service!r}",
            )
        if service == "sessions.run_many":
            results.append(
                _sessions_run_many(
                    plugin,
                    action,
                    authorized_session_ids=authorized_session_ids,
                    request_key=stable_key("plugin-batch", [trusted_run_id or action.get("idempotency_key") or str(uuid.uuid4()), index, action]),
                )
            )
        elif service.startswith("session_state.") or service == "session_events.append":
            results.append(
                _session_extension_action(
                    plugin,
                    action,
                    trusted_session_id=str(trusted_session_id or "").strip(),
                    trusted_run_id=str(trusted_run_id or "").strip(),
                )
            )
        else:
            raise PluginHostServiceError(
                400,
                "unknown_host_service",
                f"Unknown host service {service!r}",
            )
    return results


def issue_session_run_grant(
    plugin: PluginDefinition,
    session_ids: Sequence[str],
    *,
    ttl_seconds: float = 60.0,
) -> Dict[str, Any]:
    """Mint a short-lived, one-use grant for an explicit session set."""

    from agent_harness import session_manager

    if "sessions.run_many" not in _declared_services(plugin):
        raise PluginHostServiceError(
            403,
            "service_permission_denied",
            "Plugin is not authorized for sessions.run_many",
        )
    normalized = []
    for raw in session_ids:
        session_id = str(raw or "").strip()
        if not session_id or session_id in normalized:
            continue
        normalized.append(session_id)
    if not 1 <= len(normalized) <= 8:
        raise PluginHostServiceError(
            400,
            "invalid_service_request",
            "A session run grant requires 1-8 distinct sessions",
        )
    for session_id in normalized:
        if session_manager.get_session_summary(session_id) is None:
            raise PluginHostServiceError(
                404,
                "session_not_found",
                f"Session {session_id} was not found",
            )
    token = uuid.uuid4().hex + uuid.uuid4().hex
    expires_at = time.monotonic() + max(5.0, min(300.0, float(ttl_seconds)))
    with _reservation_lock:
        now = time.monotonic()
        for expired_token, (_owner, _sessions, expiry) in list(_session_run_grants.items()):
            if expiry <= now:
                _session_run_grants.pop(expired_token, None)
        _session_run_grants[token] = (
            plugin.plugin_id,
            frozenset(normalized),
            expires_at,
        )
    return {
        "token": token,
        "plugin_id": plugin.plugin_id,
        "session_ids": normalized,
        "expires_in_seconds": int(max(1.0, expires_at - time.monotonic())),
    }


def consume_session_run_grant(
    plugin: PluginDefinition,
    token: str,
) -> frozenset[str]:
    """Consume one grant, rejecting replay, expiry, and cross-plugin use."""

    requested = str(token or "").strip()
    if not requested:
        raise PluginHostServiceError(
            403,
            "session_run_grant_required",
            "A session run grant is required",
        )
    with _reservation_lock:
        row = _session_run_grants.pop(requested, None)
    if row is None:
        raise PluginHostServiceError(
            403,
            "invalid_session_run_grant",
            "The session run grant is invalid or has already been used",
        )
    owner, session_ids, expires_at = row
    if owner != plugin.plugin_id or expires_at <= time.monotonic():
        raise PluginHostServiceError(
            403,
            "invalid_session_run_grant",
            "The session run grant is invalid or expired",
        )
    return session_ids


def _session_extension_action(
    plugin: PluginDefinition,
    action: Mapping[str, Any],
    *,
    trusted_session_id: str,
    trusted_run_id: str,
) -> Dict[str, Any]:
    from agent_harness import session_manager
    from runtime_v2 import (
        ExtensionStateConflict,
        ExtensionStateError,
        ExtensionStateNotFound,
        SessionExtensionStateStore,
    )

    requested_session = str(action.get("session_id") or "").strip()
    if not trusted_session_id:
        raise PluginHostServiceError(
            403,
            "trusted_session_required",
            "Session state services require a trusted tool-call session",
        )
    if requested_session and requested_session != trusted_session_id:
        raise PluginHostServiceError(
            403,
            "session_scope_denied",
            "A plugin cannot access a different session through this service",
        )
    service = str(action.get("service") or "").strip()
    namespace = str(action.get("namespace") or "default").strip()
    store = SessionExtensionStateStore(
        session_manager.sessions_dir,
        path_resolver=getattr(session_manager, "_resolve_session_path", None),
    )
    try:
        if service == "session_state.get":
            row = store.get(trusted_session_id, plugin.plugin_id, namespace)
        elif service == "session_state.compare_and_set":
            row = store.compare_and_set(
                trusted_session_id,
                plugin.plugin_id,
                namespace,
                expected_revision=int(action.get("expected_revision", -1)),
                value=action.get("value"),
                run_id=trusted_run_id,
            )
        elif service == "session_state.set_latest":
            row = store.set_latest(
                trusted_session_id,
                plugin.plugin_id,
                namespace,
                action.get("value"),
                run_id=trusted_run_id,
            )
        elif service == "session_state.patch":
            operations = action.get("operations")
            if not isinstance(operations, list) or len(operations) > 128:
                raise ExtensionStateError("operations must contain at most 128 patches")
            row = store.patch(
                trusted_session_id,
                plugin.plugin_id,
                namespace,
                expected_revision=int(action.get("expected_revision", -1)),
                operations=operations,
                run_id=trusted_run_id,
            )
        elif service == "session_events.append":
            row = store.append_event(
                trusted_session_id,
                plugin.plugin_id,
                str(action.get("event_name") or ""),
                action.get("data"),
                run_id=trusted_run_id,
            )
        else:
            raise PluginHostServiceError(
                400, "unknown_host_service", f"Unknown host service {service!r}"
            )
    except ExtensionStateConflict as exc:
        raise PluginHostServiceError(409, "revision_conflict", str(exc)) from exc
    except ExtensionStateNotFound as exc:
        raise PluginHostServiceError(404, "session_not_found", str(exc)) from exc
    except ExtensionStateError as exc:
        raise PluginHostServiceError(400, "invalid_service_request", str(exc)) from exc
    return {
        "service": service,
        "session_id": trusted_session_id,
        "plugin_id": plugin.plugin_id,
        "namespace": namespace,
        "state": row,
    }


__all__ = [
    "PluginHostServiceError",
    "consume_session_run_grant",
    "execute_host_actions",
    "issue_session_run_grant",
    "release_all_plugin_leases",
    "release_plugin_leases",
]
