import asyncio
import sys
import threading
import time
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from remote_control.config import RemoteControlConfig
from remote_control.gateway import (
    _is_direct_loopback_request,
    create_remote_control_gateway,
    register_remote_control,
)
from remote_control.protocol import ProtocolError, parse_request
from remote_control.service import ControlDependencies, RemoteControlError, SessionControlService
from remote_control.store import DevicePrincipal, IdempotencyConflict, PairingCodeError, RemoteControlStore


class _SessionManager:
    def __init__(self):
        self.sessions = {
            "s1": {
                "id": "s1",
                "name": "Remote test",
                "archived": False,
                "created_at": "2026-01-01T00:00:00",
            }
        }
        self.interrupts = []

    def list_sessions(self, include_archived=False):
        return [dict(row) for row in self.sessions.values() if include_archived or not row.get("archived")]

    def get_session_summary(self, session_id):
        row = self.sessions.get(session_id)
        return dict(row) if row else None

    def get_ui_events_page(self, session_id, **_kwargs):
        return {
            "events": [{"type": "user", "content": "hello"}],
            "total": 1,
            "range_start": 0,
            "range_end": 1,
            "has_older": False,
            "has_newer": False,
        }

    def get_or_create_session(self):
        sid = f"s{len(self.sessions) + 1}"
        metadata = {"name": "New session", "created_at": "2026-01-01T00:00:00"}
        self.sessions[sid] = {"id": sid, **metadata, "archived": False}
        return sid, [], [], [], "", metadata

    def set_session_name(self, session_id, name):
        self.sessions[session_id]["name"] = name

    def clear_interrupt(self, *_args, **_kwargs):
        return None

    def is_interrupt_requested(self, *_args, **_kwargs):
        return False

    def request_interrupt(self, session_id, run_id="", reason="user"):
        self.interrupts.append((session_id, run_id, reason))

    def mark_session_unread_result(self, *_args, **_kwargs):
        return None

    def list_subagent_descendants(self, _session_id):
        return []


async def _empty_stream(*_args, **_kwargs):
    if False:
        yield {}


def _dependencies(manager):
    reservations = set()

    def reserve(sid, token):
        if sid in reservations:
            return None
        reservations.add(sid)
        return token or "reserved"

    def release(sid, _token):
        reservations.discard(sid)

    return ControlDependencies(
        session_manager=manager,
        astream_events=_empty_stream,
        reserve_start=reserve,
        release_start=release,
        is_stream_active=lambda _sid: False,
    )


def test_store_pairing_device_auth_and_revoke(tmp_path):
    store = RemoteControlStore(tmp_path)
    pairing = store.create_pairing(label="Phone", scopes=["read", "write"], ttl_seconds=60)
    issued = store.consume_pairing(pairing["code"], device_name="My phone")

    principal = store.authenticate_device(issued["device_token"])
    assert principal is not None
    assert principal.name == "My phone"
    assert principal.scopes == frozenset({"read", "write"})

    with pytest.raises(PairingCodeError):
        store.consume_pairing(pairing["code"], device_name="Replay")

    assert store.revoke_device(issued["device_id"]) is True
    assert store.authenticate_device(issued["device_token"]) is None


def test_store_idempotency_is_durable_and_method_bound(tmp_path):
    store = RemoteControlStore(tmp_path)
    response = {"accepted": True, "run_id": "r1"}
    store.put_idempotent("d1", "key-1", "session.send", response, ttl_seconds=60)
    assert store.get_idempotent("d1", "key-1", "session.send") == response
    with pytest.raises(IdempotencyConflict):
        store.get_idempotent("d1", "key-1", "session.interrupt")


def test_protocol_rejects_invalid_frames():
    frame = parse_request(
        '{"type":"req","id":"1","method":"system.health","params":{}}',
        max_frame_bytes=4096,
    )
    assert frame.method == "system.health"
    with pytest.raises(ProtocolError, match="valid JSON"):
        parse_request("{", max_frame_bytes=4096)
    with pytest.raises(ProtocolError, match="must be 'req'"):
        parse_request('{"type":"event","id":"1","method":"x"}', max_frame_bytes=4096)


def test_service_enforces_scope_and_replays_idempotent_result(tmp_path):
    manager = _SessionManager()
    service = SessionControlService(_dependencies(manager), RemoteControlStore(tmp_path))
    principal = DevicePrincipal("device-1", "Phone", frozenset({"read", "write"}))

    async def scenario():
        first, replayed_first = await service.execute(
            principal, "session.create", {"name": "Created remotely"}, idempotency_key="create-1"
        )
        second, replayed_second = await service.execute(
            principal, "session.create", {"name": "Ignored retry"}, idempotency_key="create-1"
        )
        assert replayed_first is False
        assert replayed_second is True
        assert first == second
        with pytest.raises(RemoteControlError, match="approvals"):
            await service.execute(principal, "approval.list", {})

    asyncio.run(scenario())
    assert len(manager.sessions) == 2


def test_pending_approval_can_be_resolved_cross_thread():
    from tool_approval_gate import (
        list_pending_approvals,
        resolve_tool_approval,
        wait_tool_ui_approval_after_emit,
    )

    emitted = threading.Event()
    result = []

    async def emit():
        emitted.set()

    def worker():
        result.append(
            asyncio.run(
                wait_tool_ui_approval_after_emit(
                    "s1", "approval-1", emit, metadata={"title": "Allow command"}
                )
            )
        )

    thread = threading.Thread(target=worker)
    thread.start()
    assert emitted.wait(timeout=2)
    deadline = time.time() + 2
    while time.time() < deadline and not list_pending_approvals("s1"):
        time.sleep(0.01)
    assert list_pending_approvals("s1")[0]["title"] == "Allow command"
    assert resolve_tool_approval("s1", "approval-1", True) is True
    thread.join(timeout=2)
    assert result == [True]


def test_gateway_pair_connect_and_read_methods(tmp_path):
    config = RemoteControlConfig(
        enabled=True,
        state_dir=tmp_path,
        loopback_pairing_only=False,
    )
    manager = _SessionManager()
    gateway = create_remote_control_gateway(config, _dependencies(manager))
    app = FastAPI()
    app.include_router(gateway.router)

    with TestClient(app, base_url="https://testserver") as client:
        pairing_response = client.post(
            "/api/remote/v1/pairings",
            json={"label": "Test phone", "scopes": ["read", "write"]},
        )
        assert pairing_response.status_code == 200
        pairing = pairing_response.json()

        claimed = client.post(
            "/api/remote/v1/claim",
            json={"pairing_code": pairing["code"], "device_name": "Cookie phone"},
        )
        assert claimed.status_code == 200
        assert "httponly" in claimed.headers["set-cookie"].lower()

        second_pairing = client.post(
            "/api/remote/v1/pairings",
            json={"label": "Native client", "scopes": ["read", "write"]},
        ).json()

        cookie_token = client.cookies.get("sugaragent_remote_token")
        with client.websocket_connect(
            "/api/remote/v1/ws",
            headers={"cookie": f"sugaragent_remote_token={cookie_token}"},
        ) as cookie_ws:
            cookie_challenge = cookie_ws.receive_json()
            cookie_ws.send_json(
                {
                    "type": "req",
                    "id": "cookie-connect",
                    "method": "connect",
                    "params": {"nonce": cookie_challenge["payload"]["nonce"]},
                }
            )
            assert cookie_ws.receive_json()["ok"] is True

        client.cookies.clear()

        with client.websocket_connect("/api/remote/v1/ws") as ws:
            challenge = ws.receive_json()
            assert challenge["event"] == "connect.challenge"
            nonce = challenge["payload"]["nonce"]
            ws.send_json(
                {
                    "type": "req",
                    "id": "connect-1",
                    "method": "connect",
                    "params": {
                        "nonce": nonce,
                        "pairing_code": second_pairing["code"],
                        "device_name": "Test phone",
                    },
                }
            )
            connected = ws.receive_json()
            assert connected["ok"] is True
            assert connected["result"]["device_token"].startswith("rc1_")

            ws.send_json(
                {"type": "req", "id": "health", "method": "system.health", "params": {}}
            )
            assert ws.receive_json()["result"]["protocol_version"] == 1

            ws.send_json(
                {"type": "req", "id": "sessions", "method": "session.list", "params": {}}
            )
            sessions = ws.receive_json()
            assert sessions["result"]["sessions"][0]["id"] == "s1"

            ws.send_json(
                {
                    "type": "req",
                    "id": "create-no-key",
                    "method": "session.create",
                    "params": {},
                }
            )
            denied = ws.receive_json()
            assert denied["ok"] is False
            assert denied["error"]["code"] == "idempotency_key_required"


def test_gateway_is_disabled_by_default_contract(tmp_path):
    state_dir = tmp_path / "remote-state"
    config = RemoteControlConfig(enabled=False, state_dir=state_dir)
    app = FastAPI()
    gateway = register_remote_control(app, config, _dependencies(_SessionManager()))
    assert gateway is None
    assert not state_dir.exists()
    with TestClient(app) as client:
        assert client.get("/api/remote/v1/status").status_code == 404
        assert client.get("/api/remote/v1/client").status_code == 404
        assert client.post("/api/remote/v1/pairings", json={}).status_code == 404


def test_register_remote_control_mounts_routes_when_enabled(tmp_path):
    state_dir = tmp_path / "remote-state"
    config = RemoteControlConfig(enabled=True, state_dir=state_dir)
    app = FastAPI()
    gateway = register_remote_control(app, config, _dependencies(_SessionManager()))
    assert gateway is not None
    paths = {getattr(route, "path", "") for route in app.routes}
    assert "/api/remote/v1/status" in paths
    assert "/api/remote/v1/ws" in paths
    assert state_dir.exists()


def test_remote_control_enabled_environment_flag(monkeypatch, tmp_path):
    monkeypatch.delenv("MYAGENT_REMOTE_CONTROL_ENABLED", raising=False)
    assert RemoteControlConfig.from_env(tmp_path).enabled is False
    for value in ("1", "true", "YES", "on"):
        monkeypatch.setenv("MYAGENT_REMOTE_CONTROL_ENABLED", value)
        assert RemoteControlConfig.from_env(tmp_path).enabled is True
    for value in ("0", "false", "no", "off", "invalid"):
        monkeypatch.setenv("MYAGENT_REMOTE_CONTROL_ENABLED", value)
        assert RemoteControlConfig.from_env(tmp_path).enabled is False


def test_local_admin_detection_rejects_reverse_proxy_headers():
    from starlette.requests import Request

    def request_with(headers):
        encoded = [(key.lower().encode(), value.encode()) for key, value in headers.items()]
        return Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/api/remote/v1/pairings",
                "headers": encoded,
                "client": ("127.0.0.1", 50000),
                "server": ("127.0.0.1", 8192),
                "scheme": "http",
            }
        )

    assert _is_direct_loopback_request(request_with({})) is True
    assert _is_direct_loopback_request(request_with({"X-Forwarded-For": "100.64.0.2"})) is False
    assert _is_direct_loopback_request(request_with({"Tailscale-User-Login": "user@example.com"})) is False
