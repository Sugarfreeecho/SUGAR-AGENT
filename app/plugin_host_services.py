"""Permission-checked host services available to isolated plugin workers."""
from __future__ import annotations

import asyncio
import logging
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Sequence

from plugins.models import PluginDefinition


logger = logging.getLogger(__name__)
_reservation_lock = threading.RLock()
_session_reservations: Dict[str, str] = {}
_owner_runs: Dict[str, list[SessionRunRequest]] = {}
_session_run_grants: Dict[str, tuple[str, frozenset[str], float]] = {}
_TERMINAL_RUN_STATUSES = frozenset(
    {"completed", "failed", "cancelled", "interrupted", "stale"}
)


class PluginHostServiceError(RuntimeError):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = int(status)
        self.code = str(code)


@dataclass(frozen=True)
class SessionRunRequest:
    session_id: str
    prompt: str
    run_id: str


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


def _release_many(owner: str, session_ids: Sequence[str]) -> None:
    with _reservation_lock:
        for session_id in session_ids:
            if _session_reservations.get(session_id) == owner:
                _session_reservations.pop(session_id, None)
        if owner not in _session_reservations.values():
            _owner_runs.pop(owner, None)


def _run_session_background(
    owner: str,
    request: SessionRunRequest,
) -> None:
    from agent_harness import session_manager
    from agent_loop import astream_events

    async def run() -> None:
        async for _event in astream_events(
            request.prompt,
            session_id=request.session_id,
            should_stop=lambda sid: session_manager.is_interrupt_requested(sid),
            run_id=request.run_id,
        ):
            pass

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(run())
    except Exception:
        logger.exception(
            "Plugin-started session run failed: session=%s run=%s",
            request.session_id,
            request.run_id,
        )
    finally:
        try:
            loop.close()
        finally:
            _release_many(owner, [request.session_id])


def _sessions_run_many(
    plugin: PluginDefinition,
    action: Mapping[str, Any],
    *,
    authorized_session_ids: frozenset[str],
) -> Dict[str, Any]:
    from agent_harness import session_manager

    raw_sessions = action.get("sessions")
    if not isinstance(raw_sessions, list) or not 1 <= len(raw_sessions) <= 8:
        raise PluginHostServiceError(
            400,
            "invalid_service_request",
            "sessions.run_many requires 1-8 session requests",
        )
    owner = f"{plugin.plugin_id}:{uuid.uuid4().hex}"
    requests = []
    seen = set()
    for raw in raw_sessions:
        if not isinstance(raw, Mapping):
            raise PluginHostServiceError(400, "invalid_service_request", "Invalid session request")
        session_id = str(raw.get("session_id") or "").strip()
        prompt = str(raw.get("prompt") or "")
        if not session_id or session_id in seen or not prompt.strip() or len(prompt) > 50_000:
            raise PluginHostServiceError(400, "invalid_service_request", "Invalid session or prompt")
        if session_manager.get_session_summary(session_id) is None:
            raise PluginHostServiceError(404, "session_not_found", f"Session {session_id} was not found")
        seen.add(session_id)
        requests.append(
            SessionRunRequest(
                session_id=session_id,
                prompt=prompt,
                run_id=f"plugin-{plugin.plugin_id}-{uuid.uuid4().hex}",
            )
        )

    session_ids = [item.session_id for item in requests]
    if not authorized_session_ids:
        raise PluginHostServiceError(
            403,
            "session_run_grant_required",
            "sessions.run_many requires a host-issued session grant",
        )
    if frozenset(session_ids) != authorized_session_ids:
        raise PluginHostServiceError(
            403,
            "session_scope_denied",
            "The session grant does not match the requested sessions",
        )
    with _reservation_lock:
        busy = [
            session_id
            for session_id in session_ids
            if session_id in _session_reservations or _session_is_active(session_id)
        ]
        if busy:
            raise PluginHostServiceError(
                409,
                "session_busy",
                f"Session is already running: {busy[0]}",
            )
        for session_id in session_ids:
            _session_reservations[session_id] = owner
        _owner_runs[owner] = list(requests)

    threads = [
        threading.Thread(
            target=_run_session_background,
            args=(owner, request),
            name=f"plugin-session-{request.session_id[:12]}",
            daemon=True,
        )
        for request in requests
    ]
    started = []
    try:
        for thread in threads:
            thread.start()
            started.append(thread)
    except Exception as exc:
        _release_many(owner, session_ids)
        for request in requests[: len(started)]:
            try:
                session_manager.request_interrupt(
                    request.session_id,
                    request.run_id,
                    reason="plugin_start_rollback",
                )
            except Exception:
                logger.debug("Plugin session rollback interrupt failed", exc_info=True)
        raise PluginHostServiceError(
            503,
            "service_start_failed",
            "Could not start every reserved session",
        ) from exc
    return {
        "service": "sessions.run_many",
        "accepted": True,
        "session_ids": session_ids,
        "run_ids": [item.run_id for item in requests],
    }


def release_plugin_leases(plugin_id: str, *, cancel_runs: bool = True) -> int:
    """Release and optionally cancel every session run owned by one plugin."""

    namespace = str(plugin_id or "").strip()
    prefix = namespace + ":"
    with _reservation_lock:
        owners = {
            owner
            for owner in _session_reservations.values()
            if owner.startswith(prefix)
        }
        requests = [request for owner in owners for request in _owner_runs.get(owner, [])]
        for session_id, owner in list(_session_reservations.items()):
            if owner in owners:
                _session_reservations.pop(session_id, None)
        for owner in owners:
            _owner_runs.pop(owner, None)
    if cancel_runs and requests:
        from agent_harness import session_manager

        for request in requests:
            try:
                session_manager.request_interrupt(
                    request.session_id,
                    request.run_id,
                    reason="plugin_disabled",
                )
            except Exception:
                logger.debug("Plugin-owned run cancellation failed", exc_info=True)
    return len(requests)


def release_all_plugin_leases(*, cancel_runs: bool = True) -> int:
    with _reservation_lock:
        plugin_ids = {
            owner.split(":", 1)[0]
            for owner in _session_reservations.values()
            if ":" in owner
        }
    return sum(
        release_plugin_leases(plugin_id, cancel_runs=cancel_runs)
        for plugin_id in plugin_ids
    )


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
    for action in actions:
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
