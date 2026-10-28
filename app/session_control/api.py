"""Authenticated HTTP transport, independent of the mobile remote-control flag."""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import math
import os
import secrets
import time
import uuid
from contextlib import closing
from itertools import islice
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from .errors import ControlError, envelope
from .policy import IdentityService, Principal
from .service import SessionControlService
from .store import ControlStore


class ControlApplication:
    def __init__(self, dependencies, state_dir, remote_store, *, callbacks=None):
        self.state_dir = Path(state_dir)
        self.store = ControlStore(self.state_dir / "control.sqlite3")
        self.identities = IdentityService(self.store, remote_store)
        self.service = SessionControlService(dependencies, self.store, self.identities, callbacks=callbacks)
        self.bootstrap = None
        self.auth_windows = {}
        self.hook_windows = {}
        self.archive_locks = {}
        self.router = APIRouter()
        self.router.add_api_route("/api/control/v1/rpc", self.rpc, methods=["POST"])
        self.router.add_api_route("/api/control/v1/events", self.events, methods=["GET"])
        self.router.add_api_route("/api/control/v1/operations/{operation_id}/events", self.operation_events, methods=["GET"])
        self.router.add_api_route("/api/control/v1/auth/claim", self.claim, methods=["POST"])
        self.router.add_api_route("/api/control/v1/auth/pairings", self.pairing, methods=["POST"])
        self.router.add_api_route("/api/control/v1/auth/logout", self.logout, methods=["POST"])
        self.router.add_api_route("/api/control/v1/archives", self.upload_archive, methods=["POST"])
        self.router.add_api_route("/api/control/v1/archives/{operation_id}", self.download_archive, methods=["GET"])
        self.router.add_api_route("/api/automation/v1/hooks/{source_id}", self.webhook, methods=["POST"])
        from .settings_api import register_settings_adapter
        register_settings_adapter(self)

    async def start(self):
        await asyncio.to_thread(self._bootstrap)
        await self.service.start()

    async def close(self):
        await self.service.close()

    def _bootstrap(self):
        self.state_dir.mkdir(parents=True, exist_ok=True)
        path = self.state_dir / "bootstrap.key"
        try:
            with path.open("x", encoding="utf-8") as handle:
                handle.write(secrets.token_urlsafe(48))
            if os.name != "nt":
                path.chmod(0o600)
        except FileExistsError:
            pass
        self.bootstrap = path.read_text(encoding="utf-8").strip()
        return self.bootstrap

    @staticmethod
    async def body(request, limit=1024 * 1024):
        data = bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data) > limit:
                raise ControlError("request_too_large", "Request body is too large", status=413)
        try:
            value = json.loads(data)
        except (ValueError, UnicodeDecodeError) as exc:
            raise ControlError("invalid_json", "Expected a JSON object") from exc
        if not isinstance(value, dict):
            raise ControlError("invalid_params", "Expected a JSON object")
        return value

    @staticmethod
    def token(request):
        header = request.headers.get("authorization", "")
        if not header.startswith("Bearer "):
            raise ControlError("unauthorized", "A Bearer credential is required", status=401)
        return header[7:].strip()

    def principal(self, request):
        return self.identities.authenticate(self.token(request))

    @staticmethod
    def error(exc, rid=""):
        if not isinstance(exc, ControlError):
            exc = ControlError("invalid_params" if isinstance(exc, (ValueError, TypeError, KeyError)) else "internal_error",
                               str(exc) if isinstance(exc, (ValueError, TypeError, KeyError)) else "The control operation failed", status=400 if isinstance(exc, (ValueError, TypeError, KeyError)) else 500)
        return JSONResponse(envelope(request_id=rid, error=exc), status_code=exc.status,
                            headers={"Cache-Control": "no-store"})

    async def rpc(self, request: Request):
        rid = ""
        try:
            principal = await asyncio.to_thread(self.principal, request)
            body = await self.body(request)
            rid = str(body.get("request_id") or uuid.uuid4())
            params = body.get("params", {})
            if not isinstance(params, dict) or any(k.startswith("_") for k in params):
                raise ControlError("invalid_params", "Reserved or invalid request parameters")
            method = str(body.get("method", ""))
            result, replay = await self.service.execute(principal, method, params, idempotency_key=body.get("idempotency_key", ""))
            if method not in {"system.health", "session.history", "session.list", "session.get"}:
                await asyncio.to_thread(self.identities.remote.audit, principal_id=principal.id, action=method,
                                        target=str(params.get("session_id") or params.get("id") or ""), outcome="replayed" if replay else "ok")
            return JSONResponse(envelope(result, request_id=rid, operation_id=result.get("operation_id")), headers={"Cache-Control": "no-store"})
        except Exception as exc:
            return self.error(exc, rid)

    async def claim(self, request: Request):
        try:
            host = request.client.host if request.client else ""
            now = time.monotonic()
            sample = self.auth_windows.get(host, (now, 0))
            sample = (now, 0) if now - sample[0] > 60 else sample
            self.auth_windows[host] = (sample[0], sample[1] + 1)
            if sample[1] >= 10:
                raise ControlError("rate_limited", "Too many authentication attempts", status=429)
            body = await self.body(request, 4096)
            if body.get("bootstrap_token"):
                from remote_control.gateway import _is_direct_loopback_request
                if not _is_direct_loopback_request(request):
                    raise ControlError("forbidden", "Bootstrap is direct-loopback only", status=403)
                key = self.bootstrap or await asyncio.to_thread(self._bootstrap)
                if not hmac.compare_digest(str(body["bootstrap_token"]), key):
                    raise ControlError("unauthorized", "Invalid bootstrap credential", status=401)
                principal = Principal("cli-" + str(uuid.uuid4()), str(body.get("name", "Local CLI")), True)
                token = self.identities.issue(principal, ttl=365 * 24 * 3600)
                return JSONResponse(envelope({"token": token, "principal": dataclasses_public(principal)}), headers={"Cache-Control": "no-store"})
            from remote_control.store import PairingCodeError
            try:
                issued = await asyncio.to_thread(self.identities.remote.consume_pairing, body.get("pairing_code", ""), device_name=body.get("name", "Session CLI"))
            except PairingCodeError as exc:
                raise ControlError("unauthorized", "Invalid or expired pairing code", status=401) from exc
            return JSONResponse(envelope({"token": issued["device_token"], "principal": {"id": issued["device_id"], "name": issued["device_name"], "scopes": issued["scopes"]}}), headers={"Cache-Control": "no-store"})
        except Exception as exc:
            return self.error(exc)

    async def operation_events(self, operation_id: str, request: Request):
        from .public import ServiceProxy
        try:
            principal = self.principal(request)
            await self.service.execute(principal, "operation.get", {"id": operation_id})
            cursor = max(0, int(request.query_params.get("cursor", "0")))
        except Exception as exc:
            return self.error(exc)
        async def stream():
            try:
                async for event in ServiceProxy(self.service).events(principal, operation_id, after=cursor):
                    self.identities.ensure_live(principal)
                    if await request.is_disconnected():
                        return
                    yield json.dumps(event, ensure_ascii=False) + "\n"
            except Exception as exc:
                yield json.dumps({"type": "error", "code": getattr(exc, "code", "stream_failed"), "content": str(exc)}) + "\n"
        return StreamingResponse(stream(), media_type="application/x-ndjson", headers={"Cache-Control": "no-store"})

    async def pairing(self, request: Request):
        try:
            principal = self.principal(request)
            if not principal.admin:
                raise ControlError("forbidden", "Administrator required", status=403)
            body = await self.body(request, 4096)
            result = self.identities.remote.create_pairing(label=body.get("name", "Session CLI"), scopes=body.get("scopes", ["read", "write"]))
            return JSONResponse(envelope(result), headers={"Cache-Control": "no-store"})
        except Exception as exc:
            return self.error(exc)

    async def logout(self, request: Request):
        try:
            token = self.token(request)
            self.identities.authenticate(token)
            self.identities.revoke(token)
            return JSONResponse(envelope({"logged_out": True}))
        except Exception as exc:
            return self.error(exc)

    async def events(self, request: Request):
        try:
            principal = self.principal(request)
            sid = request.query_params.get("session_id", "")
            self.service.authorize(principal, "session.attach", {"session_id": sid})
            requested_cursor = request.query_params.get("cursor")
            after = max(0, int(requested_cursor or 0))
            from runtime_v2.event_log import SessionEventLog
            events = SessionEventLog(self.service.manager.sessions_dir, self.service.manager._resolve_session_path)
            path = events.event_path(sid)
            def fingerprint():
                if not path.is_file():
                    return hashlib.sha256(b"").hexdigest()[:24]
                with path.open("rb") as handle:
                    return hashlib.sha256(handle.readline()).hexdigest()[:24]
            def snapshot():
                with events.session_transaction(sid):
                    tail = events.read_latest(sid, 1)
                    return (self.service.manager.get_ui_events_page(sid, limit=50),
                            fingerprint(), tail[-1].seq if tail else 0)
            def batch(cursor):
                with closing(events.iter_after_seq(sid, cursor)) as rows:
                    return list(islice(rows, 200))
            history, generation, highwater = await asyncio.to_thread(snapshot)
            requested_generation = request.query_params.get("generation")
            if requested_cursor is None:
                after = highwater
        except Exception as exc:
            return self.error(exc)
        async def stream():
            nonlocal after, generation
            if (requested_generation and requested_generation != generation) or after > highwater:
                yield json.dumps({"type": "gap", "reason": "history_generation_changed", "generation": generation, "cursor": highwater}) + "\n"
                after = highwater
            yield json.dumps({"type": "snapshot", "data": history, "generation": generation, "cursor": after}, ensure_ascii=False) + "\n"
            heartbeat = time.monotonic()
            while not await request.is_disconnected():
                try:
                    live_principal = self.principal(request)
                    self.service.authorize(live_principal, "session.attach", {"session_id": sid})
                    current_generation = await asyncio.to_thread(fingerprint)
                    if current_generation != generation:
                        history_now, generation, after = await asyncio.to_thread(snapshot)
                        yield json.dumps({"type": "gap", "reason": "history_generation_changed", "generation": generation, "cursor": after}) + "\n"
                        yield json.dumps({"type": "snapshot", "data": history_now, "generation": generation, "cursor": after}, ensure_ascii=False) + "\n"
                    rows = await asyncio.to_thread(batch, after)
                    for event in rows:
                        after = event.seq
                        # Model context, reasoning, and raw tool payloads are not transcript events.
                        if event.type in {"user_turn_committed", "assistant_final_committed", "message_user", "message_assistant_final", "run_started", "run_finished", "run_failed", "run_interrupted", "interaction_requested", "interaction_resolved"}:
                            payload = {k: v for k, v in event.payload.items() if k in {"ui_content", "content", "ui_type", "operation_id", "status", "reason", "turn_id"}}
                            yield json.dumps({"type": "event", "cursor": after, "generation": generation,
                                              "data": {"type": event.type, "run_id": event.run_id, "payload": payload}}, ensure_ascii=False) + "\n"
                    if time.monotonic() - heartbeat > 10:
                        heartbeat = time.monotonic()
                        yield json.dumps({"type": "heartbeat", "cursor": after, "generation": generation}) + "\n"
                except Exception as exc:
                    yield json.dumps({"type": "error", "error": {"code": getattr(exc, "code", "stream_failed"), "message": str(exc)}}) + "\n"
                    return
                await asyncio.sleep(.5)
        return StreamingResponse(stream(), media_type="application/x-ndjson", headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})

    async def upload_archive(self, request: Request):
        """A raw archive upload is staged locally; the normal admission owns import."""
        temporary = None
        try:
            principal = self.principal(request)
            self.service.authorize(principal, "session.import", {})
            if not principal.admin:
                raise ControlError("forbidden", "Archive import requires admin", status=403)
            key = request.headers.get("idempotency-key", "")
            if not key or len(key) > 200:
                raise ControlError("idempotency_key_required", "Idempotency-Key is required")
            staging = self.state_dir / "uploads"
            staging.mkdir(parents=True, exist_ok=True)
            temporary = staging / (str(uuid.uuid4()) + ".part")
            total, checksum = 0, hashlib.sha256()
            with temporary.open("xb") as handle:
                async for chunk in request.stream():
                    total += len(chunk)
                    if total > 256 * 1024 * 1024:
                        raise ControlError("request_too_large", "Archive exceeds 256 MiB", status=413)
                    checksum.update(chunk)
                    await asyncio.to_thread(handle.write, chunk)
            if not total:
                raise ControlError("invalid_params", "Archive is empty")
            identity = hashlib.sha256((principal.id + ":" + key + ":" + checksum.hexdigest()).encode()).hexdigest()
            archive = staging / (identity + ".zip")
            async with self.archive_locks.setdefault(identity, asyncio.Lock()):
                os.replace(temporary, archive)
                temporary = None
                try:
                    result, _ = await self.service.execute(principal, "session.import", {"source": str(archive), "kind": "zip"}, idempotency_key=key)
                finally:
                    archive.unlink(missing_ok=True)
            return JSONResponse(envelope(result, operation_id=result["operation_id"]), headers={"Cache-Control": "no-store"})
        except Exception as exc:
            return self.error(exc)
        finally:
            if temporary:
                temporary.unlink(missing_ok=True)

    async def download_archive(self, operation_id: str, request: Request):
        try:
            principal = self.principal(request)
            op = self.store.get_operation(operation_id)
            if not op or op["method"] != "session.export" or op["status"] != "succeeded":
                raise ControlError("not_found", "Completed export not found", status=404)
            self.service.authorize(principal, "session.export", {"session_id": op["session_id"]})
            if not principal.admin and principal.id != op["principal"]:
                raise ControlError("forbidden", "Export belongs to another identity", status=403)
            result = op["result"]
            path = Path(result["archive_path"])
            if not path.is_file():
                raise ControlError("not_found", "Export file expired; request a new export", status=404)
            return FileResponse(path, filename=result.get("filename", path.name), media_type="application/zip", headers={"Cache-Control": "no-store"})
        except Exception as exc:
            return self.error(exc)

    async def webhook(self, source_id: str, request: Request):
        try:
            source = self.store.get("sources", source_id)
            if not source or not source.get("enabled") or source.get("deleted"):
                raise ControlError("not_found", "Webhook source unavailable", status=404)
            now = time.time()
            window, count = self.hook_windows.get(source_id, (now, 0))
            if now - window > 60:
                window, count = now, 0
            self.hook_windows[source_id] = (window, count + 1)
            if count >= 60:
                raise ControlError("rate_limited", "Webhook rate limit exceeded", status=429)
            timestamp = request.headers.get("x-sugar-timestamp", "")
            eid = request.headers.get("x-sugar-event-id", "")
            signature = request.headers.get("x-sugar-signature", "")
            if not eid or len(eid) > 200 or not math.isfinite(float(timestamp)) or abs(now - float(timestamp)) > 300:
                raise ControlError("unauthorized", "Invalid event identity or timestamp", status=401)
            chunks = bytearray()
            async for chunk in request.stream():
                chunks.extend(chunk)
                if len(chunks) > 256 * 1024:
                    raise ControlError("request_too_large", "Webhook body exceeds 256 KiB", status=413)
            raw = bytes(chunks)
            expected = hmac.new(source["secret"].encode(), timestamp.encode() + b"\n" + eid.encode() + b"\n" + raw, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature.removeprefix("sha256="), expected):
                raise ControlError("unauthorized", "Webhook signature mismatch", status=401)
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                raise ControlError("invalid_json", "Webhook requires an object")
            event = {"specversion": "1.0", "source": "webhook/" + source_id, "id": eid,
                     "type": "webhook.received", "subject": source_id,
                     "time": datetime.fromtimestamp(float(timestamp), timezone.utc).isoformat(), "data": payload}
            cursor, duplicate = self.store.append_event(event, transport_time=True)
            await self.service.start()
            return JSONResponse(envelope({"accepted": True, "duplicate": duplicate, "cursor": cursor}), status_code=200 if duplicate else 202)
        except Exception as exc:
            return self.error(exc)


def dataclasses_public(p):
    return {"id": p.id, "name": p.name, "admin": p.admin, "policy": p.policy}


def register_control(app, dependencies, state_dir, remote_store, *, callbacks=None):
    application = ControlApplication(dependencies, state_dir, remote_store, callbacks=callbacks)
    app.include_router(application.router)
    return application
