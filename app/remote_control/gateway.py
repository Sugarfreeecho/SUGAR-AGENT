from __future__ import annotations

import asyncio
import hmac
import ipaddress
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse

from .config import RemoteControlConfig
from .protocol import ProtocolError, event_frame, parse_request, response_error, response_ok
from .service import ControlDependencies, RemoteControlError, SessionControlService
from .store import DevicePrincipal, PairingCodeError, RemoteControlStore

_DEVICE_COOKIE = "sugaragent_remote_token"


def _is_loopback(host: str) -> bool:
    try:
        return ipaddress.ip_address(str(host or "").split("%", 1)[0]).is_loopback
    except ValueError:
        return str(host or "").lower() in {"localhost"}


def _is_direct_loopback_request(request: Request) -> bool:
    """Reject loopback-looking requests that actually arrived through a proxy."""
    if not _is_loopback(request.client.host if request.client else ""):
        return False
    forwarded_headers = {
        "forwarded",
        "x-forwarded-for",
        "x-forwarded-host",
        "x-forwarded-proto",
        "x-real-ip",
        "tailscale-user-login",
        "tailscale-user-name",
        "tailscale-user-profile-pic",
    }
    return not any(str(request.headers.get(name) or "").strip() for name in forwarded_headers)


def _origin_allowed(websocket: WebSocket, configured: tuple[str, ...]) -> bool:
    origin = str(websocket.headers.get("origin") or "").strip().rstrip("/")
    if not origin:
        # Native clients do not send Origin; authentication still applies.
        return True
    if origin in configured:
        return True
    try:
        parsed = urlsplit(origin)
        origin_host = (parsed.hostname or "").lower()
        request_host = str(websocket.headers.get("host") or "").split(":", 1)[0].lower()
        return bool(origin_host and hmac.compare_digest(origin_host, request_host))
    except Exception:
        return False


@dataclass
class _RateWindow:
    started_at: float
    count: int = 0


class _ConnectionRateLimiter:
    def __init__(self, limit: int = 120, window_seconds: float = 60.0):
        self.limit = limit
        self.window_seconds = window_seconds
        self.window = _RateWindow(time.monotonic())

    def consume(self) -> bool:
        now = time.monotonic()
        if now - self.window.started_at >= self.window_seconds:
            self.window = _RateWindow(now)
        self.window.count += 1
        return self.window.count <= self.limit


class RemoteControlGateway:
    def __init__(self, config: RemoteControlConfig, dependencies: ControlDependencies):
        self.config = config
        # Disabled means no listener capability and no runtime files created.
        self.store = RemoteControlStore(config.state_dir) if config.enabled else None
        self.service = (
            SessionControlService(
                dependencies,
                self.store,
                idempotency_ttl_seconds=config.idempotency_ttl_seconds,
            )
            if self.store is not None
            else None
        )
        self.router = APIRouter(prefix="/api/remote/v1", tags=["remote-control"])
        self.router.add_api_route("/status", self.status, methods=["GET"])
        self.router.add_api_route("/pairings", self.create_pairing, methods=["POST"])
        self.router.add_api_route("/claim", self.claim_pairing, methods=["POST"])
        self.router.add_api_route("/logout", self.logout, methods=["POST"])
        self.router.add_api_route("/devices", self.list_devices_local, methods=["GET"])
        self.router.add_api_route("/devices/{device_id}", self.revoke_device_local, methods=["DELETE"])
        self.router.add_api_route("/client", self.mobile_client, methods=["GET"])
        self.router.add_api_websocket_route("/ws", self.websocket)

    async def status(self) -> JSONResponse:
        return JSONResponse(
            {
                "enabled": self.config.enabled,
                "protocol_version": 1,
                "websocket_path": "/api/remote/v1/ws",
                "pairing_path": "/api/remote/v1/pairings",
                "claim_path": "/api/remote/v1/claim",
                "client_path": "/api/remote/v1/client",
            }
        )

    async def mobile_client(self) -> HTMLResponse:
        client_path = Path(__file__).resolve().parents[1] / "templates" / "remote_control.html"
        html = await asyncio.to_thread(client_path.read_text, encoding="utf-8")
        return HTMLResponse(
            html,
            headers={
                "Cache-Control": "no-store",
                "Content-Security-Policy": (
                    "default-src 'self'; connect-src 'self' ws: wss:; "
                    "img-src 'self' data:; style-src 'unsafe-inline'; script-src 'unsafe-inline'"
                ),
                "X-Frame-Options": "DENY",
                "Referrer-Policy": "no-referrer",
            },
        )

    async def create_pairing(self, request: Request) -> JSONResponse:
        if not self.config.enabled:
            return JSONResponse({"ok": False, "error": "remote control is disabled"}, status_code=404)
        assert self.store is not None
        client_host = request.client.host if request.client else ""
        if self.config.loopback_pairing_only and not _is_direct_loopback_request(request):
            return JSONResponse({"ok": False, "error": "pairing can only be started locally"}, status_code=403)
        try:
            body = await request.json()
        except Exception:
            body = {}
        try:
            pairing = await asyncio.to_thread(
                self.store.create_pairing,
                label=str(body.get("label") or "Mobile device"),
                scopes=body.get("scopes"),
                ttl_seconds=self.config.pairing_ttl_seconds,
            )
        except (TypeError, ValueError) as exc:
            return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
        await asyncio.to_thread(
            self.store.audit,
            principal_id="local",
            action="pairing.create",
            target=pairing["pairing_id"],
            details={"scopes": pairing["scopes"], "client_host": client_host},
        )
        return JSONResponse({"ok": True, **pairing})

    async def claim_pairing(self, request: Request) -> JSONResponse:
        """Exchange a one-time pairing code for an HttpOnly browser credential."""
        if not self.config.enabled:
            return JSONResponse({"ok": False, "error": "remote control is disabled"}, status_code=404)
        assert self.store is not None
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"ok": False, "error": "invalid json"}, status_code=400)
        try:
            issued = await asyncio.to_thread(
                self.store.consume_pairing,
                str(body.get("pairing_code") or ""),
                device_name=str(body.get("device_name") or "Mobile browser"),
            )
        except PairingCodeError:
            return JSONResponse({"ok": False, "error": "invalid or expired pairing code"}, status_code=401)
        response = JSONResponse(
            {
                "ok": True,
                "device": {
                    "device_id": issued["device_id"],
                    "name": issued["device_name"],
                    "scopes": issued["scopes"],
                },
            }
        )
        response.set_cookie(
            _DEVICE_COOKIE,
            issued["device_token"],
            httponly=True,
            # The browser client is intentionally HTTPS-only. Local HTTP is
            # used solely for desktop administration and pairing creation.
            secure=True,
            samesite="strict",
            path="/api/remote/v1",
            max_age=365 * 24 * 60 * 60,
        )
        await asyncio.to_thread(
            self.store.audit,
            principal_id=issued["device_id"],
            action="pairing.claim",
            details={"client_host": request.client.host if request.client else ""},
        )
        return response

    async def logout(self, request: Request) -> JSONResponse:
        response = JSONResponse({"ok": True})
        response.delete_cookie(_DEVICE_COOKIE, path="/api/remote/v1", samesite="strict")
        return response

    async def list_devices_local(self, request: Request) -> JSONResponse:
        if not self.config.enabled or self.store is None:
            return JSONResponse({"ok": False, "error": "remote control is disabled"}, status_code=404)
        if not _is_direct_loopback_request(request):
            return JSONResponse({"ok": False, "error": "device management is local-only"}, status_code=403)
        return JSONResponse({"ok": True, "devices": await asyncio.to_thread(self.store.list_devices)})

    async def revoke_device_local(self, device_id: str, request: Request) -> JSONResponse:
        if not self.config.enabled or self.store is None:
            return JSONResponse({"ok": False, "error": "remote control is disabled"}, status_code=404)
        if not _is_direct_loopback_request(request):
            return JSONResponse({"ok": False, "error": "device management is local-only"}, status_code=403)
        revoked = await asyncio.to_thread(self.store.revoke_device, device_id)
        await asyncio.to_thread(
            self.store.audit,
            principal_id="local",
            action="device.revoke",
            target=device_id,
            outcome="ok" if revoked else "not_found",
        )
        return JSONResponse({"ok": revoked, "device_id": device_id}, status_code=200 if revoked else 404)

    async def _authenticate(
        self, websocket: WebSocket, params: dict[str, Any]
    ) -> tuple[DevicePrincipal | None, dict[str, Any]]:
        token = str(
            params.get("device_token")
            or params.get("token")
            or websocket.cookies.get(_DEVICE_COOKIE)
            or ""
        ).strip()
        assert self.store is not None
        if token and self.config.bootstrap_token and hmac.compare_digest(
            token, self.config.bootstrap_token
        ):
            return (
                DevicePrincipal(
                    device_id="bootstrap",
                    name="Bootstrap administrator",
                    scopes=frozenset({"read", "write", "approvals", "admin"}),
                    credential_kind="bootstrap",
                ),
                {},
            )
        if token:
            principal = await asyncio.to_thread(self.store.authenticate_device, token)
            return principal, {}
        pairing_code = str(params.get("pairing_code") or "").strip()
        if pairing_code:
            try:
                issued = await asyncio.to_thread(
                    self.store.consume_pairing,
                    pairing_code,
                    device_name=str(params.get("device_name") or "Mobile device"),
                )
            except PairingCodeError:
                return None, {}
            principal = await asyncio.to_thread(
                self.store.authenticate_device, issued["device_token"]
            )
            return principal, issued
        return None, {}

    async def websocket(self, websocket: WebSocket) -> None:
        if not self.config.enabled:
            await websocket.close(code=4404, reason="remote control disabled")
            return
        assert self.store is not None and self.service is not None
        if not _origin_allowed(websocket, self.config.allowed_origins):
            await websocket.close(code=4403, reason="origin not allowed")
            return
        await websocket.accept()
        challenge = secrets.token_urlsafe(24)
        await websocket.send_json(
            event_frame(
                "connect.challenge",
                {"nonce": challenge, "protocol_version": 1, "auth_timeout_seconds": 15},
            )
        )
        credential_token = ""
        try:
            raw = await asyncio.wait_for(websocket.receive_text(), timeout=15.0)
            connect_frame = parse_request(raw, max_frame_bytes=self.config.max_frame_bytes)
            if connect_frame.method != "connect":
                await websocket.send_json(
                    response_error(connect_frame.request_id, "authentication_required", "first method must be connect")
                )
                await websocket.close(code=4401)
                return
            if not hmac.compare_digest(str(connect_frame.params.get("nonce") or ""), challenge):
                await websocket.send_json(
                    response_error(connect_frame.request_id, "invalid_challenge", "connect nonce does not match")
                )
                await websocket.close(code=4401)
                return
            principal, issued = await self._authenticate(websocket, connect_frame.params)
            if principal is None:
                await websocket.send_json(
                    response_error(connect_frame.request_id, "authentication_failed", "invalid credential or pairing code")
                )
                await websocket.close(code=4401)
                return
            credential_token = str(
                connect_frame.params.get("device_token")
                or connect_frame.params.get("token")
                or websocket.cookies.get(_DEVICE_COOKIE)
                or issued.get("device_token")
                or ""
            ).strip()
            await asyncio.to_thread(
                self.store.audit,
                principal_id=principal.device_id,
                action="connection.open",
                details={"credential_kind": principal.credential_kind},
            )
            await websocket.send_json(
                response_ok(
                    connect_frame.request_id,
                    {
                        "connected": True,
                        "device": {
                            "device_id": principal.device_id,
                            "name": principal.name,
                            "scopes": sorted(principal.scopes),
                        },
                        **issued,
                    },
                )
            )
        except (asyncio.TimeoutError, WebSocketDisconnect):
            await websocket.close(code=4401, reason="authentication timeout")
            return
        except ProtocolError as exc:
            await websocket.send_json(response_error(exc.request_id, exc.code, exc.message))
            await websocket.close(code=4400)
            return

        outbound: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue(
            maxsize=self.config.outbound_queue_size
        )
        subscriptions: dict[str, asyncio.Task] = {}
        limiter = _ConnectionRateLimiter()

        async def sender() -> None:
            while True:
                item = await outbound.get()
                if item is None:
                    return
                await websocket.send_json(item)

        async def forward_subscription(sid: str, after_seq: int = 0) -> None:
            try:
                async for event in self.service.subscribe(sid, replay_recent=True):
                    if event is None:
                        return
                    try:
                        event_seq = int(event.get("event_bus_seq") or event.get("seq") or 0)
                    except (TypeError, ValueError):
                        event_seq = 0
                    if after_seq and event_seq and event_seq <= after_seq:
                        continue
                    frame = event_frame("session.event", event, session_id=sid)
                    try:
                        outbound.put_nowait(frame)
                    except asyncio.QueueFull:
                        await websocket.close(code=4429, reason="outbound queue overflow")
                        return
            except asyncio.CancelledError:
                return

        sender_task = asyncio.create_task(sender())

        async def watch_revocation() -> None:
            if principal.credential_kind != "device":
                return
            try:
                while True:
                    await asyncio.sleep(10.0)
                    live = await asyncio.to_thread(self.store.authenticate_device, credential_token)
                    if live is None:
                        await websocket.close(code=4401, reason="device revoked")
                        return
            except (asyncio.CancelledError, RuntimeError):
                return

        revocation_task = asyncio.create_task(watch_revocation())
        try:
            while True:
                raw = await websocket.receive_text()
                if not limiter.consume():
                    await outbound.put(response_error("", "rate_limited", "too many requests"))
                    continue
                try:
                    frame = parse_request(raw, max_frame_bytes=self.config.max_frame_bytes)
                    if frame.method == "connect":
                        raise RemoteControlError("already_connected", "connection is already authenticated")
                    if frame.method in {"session.subscribe", "session.unsubscribe"}:
                        if not principal.permits("read"):
                            raise RemoteControlError("forbidden", "scope 'read' is required")
                        sid = str(frame.params.get("session_id") or "").strip()
                        if not sid or self.service.deps.session_manager.get_session_summary(sid) is None:
                            raise RemoteControlError("session_not_found", "session does not exist")
                        if frame.method == "session.subscribe":
                            if sid not in subscriptions:
                                try:
                                    after_seq = max(0, int(frame.params.get("after_seq") or 0))
                                except (TypeError, ValueError) as exc:
                                    raise RemoteControlError("invalid_params", "after_seq must be an integer") from exc
                                subscriptions[sid] = asyncio.create_task(forward_subscription(sid, after_seq))
                            result = {"subscribed": True, "session_id": sid, "after_seq": frame.params.get("after_seq") or 0}
                        else:
                            task = subscriptions.pop(sid, None)
                            if task:
                                task.cancel()
                            result = {"subscribed": False, "session_id": sid}
                        await outbound.put(response_ok(frame.request_id, result))
                        continue
                    result, replayed = await self.service.execute(
                        principal,
                        frame.method,
                        frame.params,
                        idempotency_key=frame.idempotency_key,
                    )
                    if frame.method not in {"system.health", "session.list", "session.get", "session.history"}:
                        await asyncio.to_thread(
                            self.store.audit,
                            principal_id=principal.device_id,
                            action=frame.method,
                            target=str(frame.params.get("session_id") or frame.params.get("device_id") or ""),
                            outcome="replayed" if replayed else "ok",
                        )
                    await outbound.put(response_ok(frame.request_id, result, replayed=replayed))
                except ProtocolError as exc:
                    await outbound.put(response_error(exc.request_id, exc.code, exc.message))
                except RemoteControlError as exc:
                    await asyncio.to_thread(
                        self.store.audit,
                        principal_id=principal.device_id,
                        action="request.denied",
                        outcome=exc.code,
                        details={"message": exc.message},
                    )
                    await outbound.put(response_error(frame.request_id, exc.code, exc.message, exc.details))
                except Exception:
                    request_id = frame.request_id if "frame" in locals() else ""
                    await outbound.put(response_error(request_id, "internal_error", "request failed"))
        except WebSocketDisconnect:
            pass
        finally:
            for task in subscriptions.values():
                task.cancel()
            await asyncio.gather(*subscriptions.values(), return_exceptions=True)
            try:
                outbound.put_nowait(None)
            except asyncio.QueueFull:
                sender_task.cancel()
            await asyncio.gather(sender_task, return_exceptions=True)
            revocation_task.cancel()
            await asyncio.gather(revocation_task, return_exceptions=True)
            await asyncio.to_thread(
                self.store.audit,
                principal_id=principal.device_id,
                action="connection.close",
            )


def create_remote_control_gateway(
    config: RemoteControlConfig, dependencies: ControlDependencies
) -> RemoteControlGateway:
    return RemoteControlGateway(config, dependencies)


def register_remote_control(
    app: Any,
    config: RemoteControlConfig,
    dependencies: ControlDependencies,
) -> RemoteControlGateway | None:
    """Mount Remote Control only when the startup feature flag is enabled.

    Keeping the disabled path free of routes and state-store creation makes
    ``MYAGENT_REMOTE_CONTROL_ENABLED`` a hard startup boundary rather than a
    per-request soft check. Changing the environment variable requires a
    process restart.
    """
    if not config.enabled:
        return None
    gateway = create_remote_control_gateway(config, dependencies)
    app.include_router(gateway.router)
    return gateway
