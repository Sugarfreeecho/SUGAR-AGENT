"""Host-owned integration API. Plugins never start a Runtime or borrow UI state."""
from __future__ import annotations

import asyncio
import concurrent.futures
import copy
import dataclasses
import hashlib
import json
import uuid

from .errors import ControlError
from .policy import Principal, validate_policy
from .service import TERMINAL

RUNTIME_SOURCES = frozenset({"@runtime/subagents"})


def control_application():
    from .integration import application
    app = application()
    if app is None or app.service.closing:
        raise ControlError("control_unavailable", "The application session service is unavailable", status=503)
    return app


async def host_monitors():
    """Trusted adapters register on the single backend scheduler."""
    app = control_application()
    if app.service.loop and app.service.loop.is_running():
        await on_service_loop(app.service, app.service.start)
    else:
        await app.service.start()
    return app.service.monitors


def host_work_pool():
    return control_application().service.resources.business


async def on_service_loop(service, callback):
    loop = service.loop
    if loop is None or not loop.is_running():
        raise ControlError("control_unavailable", "Session service has not started", status=503)
    if loop is asyncio.get_running_loop():
        return await callback()
    future = asyncio.run_coroutine_threadsafe(callback(), loop)
    # Losing a channel connection must not cancel an accepted backend request.
    return await asyncio.shield(asyncio.wrap_future(future))


class ServiceProxy:
    """Compatible transport facade with all mutations on the application's loop."""
    durable_operations = True

    def __init__(self, service, *, source=None):
        self.service = service
        self.deps = service.deps
        self.source = source

    async def execute(self, principal, method, params, *, idempotency_key=""):
        if self.source:
            params = {**params, "_source": self.source}
            if self.source["id"] == "feishu-transport":
                from agent_harness import WORK_DIR
                normalized = self.service.principal(principal)
                principal = dataclasses.replace(normalized, policy=validate_policy(
                    {"capabilities": list(normalized.policy.get("capabilities", []))}, workspace=str(WORK_DIR)))
        return await on_service_loop(self.service, lambda: self.service.execute(
            principal, method, params, idempotency_key=idempotency_key))

    def subscribe(self, sid, *, replay_recent=True):
        return self.service.subscribe(sid, replay_recent=replay_recent)

    async def event_page(self, principal, operation_id, *, after=0):
        await self.execute(principal, "operation.get", {"id": operation_id})
        return await asyncio.to_thread(self.service.store.operation_events, operation_id, after)

    async def events(self, principal, operation_id, *, after=0):
        cursor = int(after)
        while True:
            result, _ = await self.execute(principal, "operation.get", {"id": operation_id})
            rows = await asyncio.to_thread(self.service.store.operation_events, operation_id, cursor)
            for row in rows:
                cursor = row["cursor"]
                yield row
            if result["status"] in TERMINAL:
                # The worker writes events before its terminal receipt.
                if rows:
                    continue
                yield {"cursor": cursor, "type": "operation.completed", "operation": result}
                return
            if not rows:
                yield {"cursor": cursor, "type": "operation.status", "operation": result}
            await asyncio.sleep(.2)


def transport_service(source_id=""):
    app = control_application()
    source = None
    if source_id:
        live = app.store.get("host_sources", source_id)
        if live is None or (not live["enabled"] and app.service.callbacks.get("source_enabled", lambda _: False)(source_id)):
            live = source_state(source_id, True, app=app)
        source = {"id": source_id, "epoch": live["epoch"]}
    return ServiceProxy(app.service, source=source)


def source_state(source_id, enabled, *, app=None):
    app = app or control_application()
    previous = app.store.get("host_sources", source_id)
    if previous and previous["enabled"] == bool(enabled):
        return previous
    return app.store.put("host_sources", source_id, {
        "enabled": bool(enabled), "epoch": (previous or {}).get("epoch", 0) + 1})


class HostSessionClient(ServiceProxy):
    """Only trusted host adapters construct identities and private source metadata."""
    def __init__(self, source_id, *, session_ids=(), workspace="", capabilities=(), app=None, runtime=False):
        self.app = app or control_application()
        super().__init__(self.app.service)
        self.source_id = str(source_id)
        if runtime and self.source_id not in RUNTIME_SOURCES:
            raise ControlError("forbidden", "Unregistered runtime source", status=403)
        source = self.app.store.get("host_sources", self.source_id)
        available = None if runtime else self.service.callbacks.get("source_enabled")
        if available is not None and not available(self.source_id):
            raise ControlError("source_disabled", "The calling plugin is disabled", status=403)
        if source is None:
            source = source_state(self.source_id, True, app=self.app)
        elif not source["enabled"] and available is not None:
            source = source_state(self.source_id, True, app=self.app)
        if not source["enabled"]:
            raise ControlError("source_disabled", "The calling plugin is disabled", status=403)
        self.source = {"id": self.source_id, "epoch": source["epoch"], "kind": "runtime" if runtime else "plugin"}
        if session_ids:
            policy = {"scope": "sessions", "session_ids": list(session_ids)}
        else:
            policy = {"scope": "workspace"}
        policy["capabilities"] = ["read", *capabilities]
        self.principal = Principal("host:" + self.source_id, self.source_id, False,
            validate_policy(policy, workspace=workspace), "host")
        from .configuration import _principal_context, _active
        parent, config = _principal_context.get(), _active.get()
        delegated = ([parent.policy] if parent and not parent.admin else []) + (parent.delegated_policies if parent else [])
        ancestors = list(parent.source_ancestors) if parent else []
        if self.source not in ancestors:
            ancestors.append(self.source)
        self.principal = dataclasses.replace(self.principal, delegated_policies=delegated, source_ancestors=ancestors,
            parent_id=(parent.parent_id or parent.id) if parent else "",
            parent_credential=(parent.parent_credential or parent.credential_id) if parent else "",
            runtime_ceiling={k: copy.deepcopy(v) for k, v in config[1].items() if k in {"tools", "limits", "read_only"}} if config else None)

    async def execute(self, principal, method, params, *, idempotency_key=""):
        return await super().execute(principal, method, {**params, "_source": self.source}, idempotency_key=idempotency_key)

    async def call(self, method, params=None, *, key=None, coalesce=False):
        params = {**copy.deepcopy(params or {}), "_source": self.source}
        if method in {"session.send", "session.continue", "session.recover"} and self.source_id in self.service.callbacks.get("source_before_run", {}):
            params["_source_lifecycle"] = True
        if coalesce:
            if method not in {"session.continue", "session.recover"}:
                raise ControlError("invalid_params", "Only continuation intents may be coalesced")
            params["_coalesce_key"] = self.source_id + ":" + method + ":" + params["session_id"]
        result, _ = await self.execute(self.principal, method, params, idempotency_key=key or str(uuid.uuid4()))
        return result

    def blocking(self, method, params=None, *, key=None, coalesce=False, timeout=30):
        try:
            if asyncio.get_running_loop() is self.service.loop:
                raise ControlError("blocking_on_service_loop", "Use await client.call() on the backend loop", status=409)
        except RuntimeError:
            pass
        loop = self.service.loop
        if loop is None or not loop.is_running():
            raise ControlError("control_unavailable", "Session service has not started", status=503)
        future = asyncio.run_coroutine_threadsafe(self.call(method, params, key=key, coalesce=coalesce), loop)
        try:
            return future.result(timeout)
        except concurrent.futures.TimeoutError as exc:
            raise ControlError("wait_timeout", "Admission may still complete; retry with the same key", status=408) from exc

    async def wait(self, operation_id):
        while True:
            try:
                return await self.call("operation.wait", {"id": operation_id, "timeout": 30})
            except ControlError as exc:
                if exc.code != "wait_timeout":
                    raise

    def observe(self, operation_id, *, after=0):
        return self.events(self.principal, operation_id, after=after)

    async def find(self, key):
        operation = await asyncio.to_thread(self.service.store.find_operation, self.principal.id, key)
        return await self.call("operation.get", {"id": operation["id"]}) if operation else None

    async def tool_override(self, session_id, allow=None, deny=None):
        catalog, _ = await self.execute(self.principal, "tool_catalog.list", {"session_id": session_id})
        def refs(names):
            result = []
            for name in names or []:
                matches = [r["tool_ref"] for r in catalog["tools"] if name in {
                    r["tool_ref"]["name"], r["definition"]["function"]["name"]}]
                if len(matches) != 1:
                    raise ControlError("tool_not_found", "Tool source is missing or ambiguous: " + name, status=409)
                result.append(matches[0])
            return result
        return {"tools": {"mode": "custom" if allow is not None else "inherit", "allow": refs(allow), "deny": refs(deny)}}

    async def run(self, session_id, message, *, key, budget=0, allow=None, deny=None,
                  context=None, on_event=None, should_stop=None, on_admitted=None):
        receipt = await self.find(key)
        if receipt is None:
            override = await self.tool_override(session_id, allow, deny) if allow is not None or deny else {}
            if budget:
                override["limits"] = {"timeout_seconds": float(budget)}
            receipt = await self.call("session.send", {"session_id": session_id, "message": message,
                "runtime_override": override, "_run_scope_context": context or {}}, key=key)
        if on_event:
            accepted = on_event({"type": "operation.accepted", **receipt})
            if asyncio.iscoroutine(accepted):
                await accepted
        if on_admitted:
            value = on_admitted(receipt)
            if asyncio.iscoroutine(value):
                await value
        async for event in self.observe(receipt["operation_id"]):
            if should_stop and should_stop():
                await self.call("operation.cancel", {"id": receipt["operation_id"]}, key=key + ":cancel")
            if event["type"] == "operation.completed":
                return event["operation"]
            if on_event:
                try:
                    value = on_event(event)
                    if asyncio.iscoroutine(value):
                        await value
                except BaseException:
                    await self.call("operation.cancel", {"id": receipt["operation_id"]}, key=stable_key("callback-cancel", key))
                    raise


def ensure_host_session(source_id, session_id, *, key, name, prompt, workspace, model_profile_id=""):
    client = host_client(source_id, workspace=workspace, capabilities=["session.create", "session.update", "session.config.update"])
    async def ensure():
        sid = session_id
        if sid:
            try:
                await client.call("session.get", {"session_id": sid})
            except ControlError as exc:
                if exc.status != 404:
                    raise
                sid = ""
        if not sid:
            created = await client.call("session.create", {"name": name, "work_dir": workspace,
                "model_profile_id": model_profile_id, "runtime_config": {"system_prompt": {"mode": "replace", "text": prompt}}}, key=stable_key("binding", [key, session_id]))
            return created["session_id"]
        current = await client.call("session.config.get", {"session_id": sid})
        desired = {"mode": "replace", "text": prompt}
        if current["config"]["system_prompt"] != desired:
            await client.call("session.config.update", {"session_id": sid, "expected_revision": current["revision"],
                "config": {**current["config"], "system_prompt": desired}}, key=stable_key("prompt", [sid, current["revision"], desired]))
        return sid
    loop = client.service.loop
    try:
        if asyncio.get_running_loop() is loop:
            raise ControlError("blocking_on_service_loop", "Session binding must run on a worker", status=409)
    except RuntimeError:
        pass
    if loop is None or not loop.is_running():
        raise ControlError("control_unavailable", "Session service has not started", status=503)
    return asyncio.run_coroutine_threadsafe(ensure(), loop).result(30)


def host_client(source_id, **kwargs):
    return HostSessionClient(source_id, **kwargs)


def register_source_lifecycle(source_id, *, before=None, after=None):
    service = control_application().service
    for name, callback in (("source_before_run", before), ("source_after_run", after)):
        registry = service.callbacks.setdefault(name, {})
        if callback is not None:
            registry[source_id] = callback


class HostRuntimeState:
    """Stable, read-only lifecycle queries for domain schedulers."""
    def __init__(self):
        self.service = control_application().service
        self.manager = self.service.manager

    def is_stopped(self, sid):
        return self.service.callbacks.get("manually_stopped", self.manager.is_interrupt_requested)(sid)

    def pending_human(self, sid):
        return self.service.callbacks.get("pending_human", lambda _: 0)(sid)

    def is_active(self, sid):
        return self.service.callbacks.get("has_local_activity", self.service.deps.is_stream_active)(sid)


def stable_key(prefix, value):
    return prefix + ":" + hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()
