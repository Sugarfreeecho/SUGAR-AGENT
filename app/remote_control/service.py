from __future__ import annotations

import asyncio
import inspect
import os
import threading
import uuid
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Callable

from session_event_bus import publish_session_event, subscribe_session_events

from .store import DevicePrincipal, IdempotencyConflict, RemoteControlStore


class RemoteControlError(RuntimeError):
    def __init__(self, code: str, message: str, *, details: Any = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details


@dataclass(frozen=True)
class ControlDependencies:
    session_manager: Any
    astream_events: Callable[..., Any]
    reserve_start: Callable[[str, str], str | None]
    release_start: Callable[[str, str], None]
    is_stream_active: Callable[[str], bool]


class SessionControlService:
    """Application service shared by transport adapters such as WebSocket and Feishu."""

    METHOD_SCOPES = {
        "system.health": "read",
        "session.list": "read",
        "session.get": "read",
        "session.history": "read",
        "session.create": "write",
        "session.send": "write",
        "session.steer": "write",
        "session.interrupt": "write",
        "approval.list": "approvals",
        "approval.resolve": "approvals",
        "device.list": "admin",
        "device.revoke": "admin",
        "audit.list": "admin",
    }
    IDEMPOTENT_METHODS = frozenset(
        {"session.create", "session.send", "session.steer", "session.interrupt", "approval.resolve", "device.revoke"}
    )

    def __init__(
        self,
        dependencies: ControlDependencies,
        store: RemoteControlStore,
        *,
        idempotency_ttl_seconds: int = 86400,
    ):
        self.deps = dependencies
        self.store = store
        self.idempotency_ttl_seconds = idempotency_ttl_seconds
        self._idempotency_locks: dict[tuple[str, str], asyncio.Lock] = {}
        self._idempotency_locks_guard = threading.Lock()

    def required_scope(self, method: str) -> str:
        scope = self.METHOD_SCOPES.get(method)
        if not scope:
            raise RemoteControlError("method_not_found", f"unknown method: {method}")
        return scope

    def _lock_for(self, principal_id: str, key: str) -> asyncio.Lock:
        identity = (principal_id, key)
        with self._idempotency_locks_guard:
            lock = self._idempotency_locks.get(identity)
            if lock is None:
                lock = asyncio.Lock()
                self._idempotency_locks[identity] = lock
            return lock

    async def execute(
        self,
        principal: DevicePrincipal,
        method: str,
        params: dict[str, Any],
        *,
        idempotency_key: str = "",
    ) -> tuple[dict[str, Any], bool]:
        required = self.required_scope(method)
        if not principal.permits(required):
            raise RemoteControlError("forbidden", f"scope '{required}' is required")
        if method in self.IDEMPOTENT_METHODS and not idempotency_key:
            raise RemoteControlError("idempotency_key_required", "this method requires idempotency_key")

        if idempotency_key:
            lock = self._lock_for(principal.device_id, idempotency_key)
            async with lock:
                try:
                    cached = await asyncio.to_thread(
                        self.store.get_idempotent,
                        principal.device_id,
                        idempotency_key,
                        method,
                    )
                except IdempotencyConflict as exc:
                    raise RemoteControlError("idempotency_conflict", str(exc)) from exc
                if cached is not None:
                    return cached, True
                result = await self._execute_once(method, params)
                await asyncio.to_thread(
                    self.store.put_idempotent,
                    principal.device_id,
                    idempotency_key,
                    method,
                    result,
                    ttl_seconds=self.idempotency_ttl_seconds,
                )
                return result, False
        return await self._execute_once(method, params), False

    async def _execute_once(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        handlers = {
            "system.health": self._health,
            "session.list": self._session_list,
            "session.get": self._session_get,
            "session.history": self._session_history,
            "session.create": self._session_create,
            "session.send": self._session_send,
            "session.steer": self._session_steer,
            "session.interrupt": self._session_interrupt,
            "approval.list": self._approval_list,
            "approval.resolve": self._approval_resolve,
            "device.list": self._device_list,
            "device.revoke": self._device_revoke,
            "audit.list": self._audit_list,
        }
        handler = handlers[method]
        result = handler(params)
        if inspect.isawaitable(result):
            result = await result
        return result

    def _require_session(self, params: dict[str, Any]) -> str:
        sid = str(params.get("session_id") or "").strip()
        if not sid:
            raise RemoteControlError("invalid_params", "session_id is required")
        if self.deps.session_manager.get_session_summary(sid) is None:
            raise RemoteControlError("session_not_found", f"session does not exist: {sid}")
        return sid

    def _health(self, _params: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True, "protocol_version": 1, "service": "remote-control"}

    def _session_list(self, params: dict[str, Any]) -> dict[str, Any]:
        include_archived = bool(params.get("include_archived", False))
        rows = self.deps.session_manager.list_sessions(include_archived=include_archived)
        return {"sessions": rows}

    def _session_get(self, params: dict[str, Any]) -> dict[str, Any]:
        sid = self._require_session(params)
        return {"session": self.deps.session_manager.get_session_summary(sid)}

    def _session_history(self, params: dict[str, Any]) -> dict[str, Any]:
        sid = self._require_session(params)
        try:
            limit = max(1, min(int(params.get("limit", 200)), 1000))
            before_index = params.get("before_index")
            if before_index is not None:
                before_index = int(before_index)
            turns = params.get("turns")
            if turns is not None:
                turns = max(1, min(int(turns), 50))
        except (TypeError, ValueError) as exc:
            raise RemoteControlError("invalid_params", "history cursor values must be integers") from exc
        page = self.deps.session_manager.get_ui_events_page(
            sid, limit=limit, before_index=before_index, turns=turns
        )
        return {"session_id": sid, **page}

    def _session_create(self, params: dict[str, Any]) -> dict[str, Any]:
        sid, _dialogue, _work, _llm, _key_context, _metadata = (
            self.deps.session_manager.get_or_create_session()
        )
        requested_name = str(params.get("name") or "").strip()
        if requested_name:
            self.deps.session_manager.set_session_name(sid, requested_name[:160])
        return {"session_id": sid, "session": self.deps.session_manager.get_session_summary(sid)}

    async def _session_send(self, params: dict[str, Any]) -> dict[str, Any]:
        sid = self._require_session(params)
        message = str(params.get("message") or "").strip()
        if not message:
            raise RemoteControlError("invalid_params", "message is required")
        run_id = str(params.get("run_id") or "").strip() or str(uuid.uuid4())
        token = self.deps.reserve_start(sid, run_id)
        if not token:
            raise RemoteControlError("session_busy", "session already has an active run")
        self.deps.session_manager.clear_interrupt(sid, run_id)

        async def consume() -> None:
            try:
                async for _event in self.deps.astream_events(
                    message,
                    session_id=sid,
                    run_id=run_id,
                    should_stop=lambda session_id: self.deps.session_manager.is_interrupt_requested(
                        session_id, run_id
                    ),
                    ui_user_content=str(params.get("ui_message") or message),
                    prompt_language=str(params.get("ui_language") or ""),
                ):
                    pass
            except Exception as exc:
                await publish_session_event(
                    sid,
                    {"type": "error", "content": str(exc), "run_id": run_id, "ephemeral": True},
                )
            finally:
                self.deps.release_start(sid, token)

        def worker() -> None:
            asyncio.run(consume())

        threading.Thread(target=worker, name=f"remote-run-{sid}", daemon=True).start()
        return {"accepted": True, "session_id": sid, "run_id": run_id}

    async def _session_steer(self, params: dict[str, Any]) -> dict[str, Any]:
        sid = self._require_session(params)
        message = str(params.get("message") or "").strip()
        if not message:
            raise RemoteControlError("invalid_params", "message is required")
        if not self.deps.is_stream_active(sid):
            raise RemoteControlError("session_not_running", "session is not running")
        mode = str(params.get("mode") or os.getenv("MYAGENT_STEER_MODE", "append")).strip().lower()
        if mode not in {"append", "interrupt"}:
            raise RemoteControlError("invalid_params", "mode must be append or interrupt")
        client_id = str(params.get("client_id") or "").strip()
        if not client_id:
            raise RemoteControlError("invalid_params", "client_id is required")
        from agent_loop import abort_session_steer_run, enqueue_session_steer, transition_session_steer

        result = enqueue_session_steer(
            sid,
            message,
            client_id=client_id,
            ui_content=str(params.get("ui_message") or message),
            source_run_id=str(params.get("source_run_id") or ""),
            mode=mode,
        )
        if not result.get("ok"):
            raise RemoteControlError("steer_rejected", str(result.get("error") or "steer rejected"), details=result)
        item = result.get("item") if isinstance(result.get("item"), dict) else {}
        if mode == "append":
            return {**result, "aborted": False, "restart": False}
        aborted = abort_session_steer_run(sid, reason="steer")
        if aborted:
            transitioned = transition_session_steer(
                sid, str(item.get("id") or ""), {"queued"}, "interrupting"
            )
            if transitioned.get("ok"):
                result["item"] = transitioned.get("item")
        return {**result, "aborted": bool(aborted), "restart": False}

    async def _session_interrupt(self, params: dict[str, Any]) -> dict[str, Any]:
        sid = self._require_session(params)
        run_id = str(params.get("run_id") or "").strip()
        reason = str(params.get("reason") or "remote_user").strip() or "remote_user"
        self.deps.session_manager.request_interrupt(sid, run_id, reason=reason)
        self.deps.session_manager.mark_session_unread_result(sid, status="failed")
        try:
            from agent_subagent import subagent_registry
            from session_lifecycle import cancel_run_tasks

            descendants = self.deps.session_manager.list_subagent_descendants(sid)
            for child_sid in descendants:
                self.deps.session_manager.request_interrupt(child_sid, reason=reason)
            await subagent_registry.cancel_for_parent(sid, also_ids=set(descendants))
            await cancel_run_tasks([sid, *descendants])
        except Exception:
            pass
        await publish_session_event(
            sid,
            {"type": "run_interrupted", "run_id": run_id, "reason": reason, "ephemeral": True},
        )
        return {"ok": True, "session_id": sid, "run_id": run_id}

    def _approval_list(self, params: dict[str, Any]) -> dict[str, Any]:
        from tool_approval_gate import list_pending_approvals

        sid = str(params.get("session_id") or "").strip()
        return {"approvals": list_pending_approvals(sid or None)}

    def _approval_resolve(self, params: dict[str, Any]) -> dict[str, Any]:
        from tool_approval_gate import resolve_tool_approval

        sid = self._require_session(params)
        approval_id = str(params.get("approval_id") or "").strip()
        if not approval_id:
            raise RemoteControlError("invalid_params", "approval_id is required")
        matched = resolve_tool_approval(sid, approval_id, bool(params.get("approve")))
        if not matched:
            raise RemoteControlError("approval_not_pending", "approval is no longer pending")
        return {"ok": True, "session_id": sid, "approval_id": approval_id}

    def _device_list(self, _params: dict[str, Any]) -> dict[str, Any]:
        return {"devices": self.store.list_devices()}

    def _device_revoke(self, params: dict[str, Any]) -> dict[str, Any]:
        device_id = str(params.get("device_id") or "").strip()
        if not device_id:
            raise RemoteControlError("invalid_params", "device_id is required")
        return {"ok": self.store.revoke_device(device_id), "device_id": device_id}

    def _audit_list(self, params: dict[str, Any]) -> dict[str, Any]:
        return {"entries": self.store.list_audit(limit=int(params.get("limit", 100)))}

    def subscribe(self, session_id: str, *, replay_recent: bool = True) -> AsyncGenerator[dict, None]:
        return subscribe_session_events(session_id, replay_recent=replay_recent)
