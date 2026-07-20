from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any


PROTOCOL_VERSION = 1


class ProtocolError(ValueError):
    def __init__(self, code: str, message: str, *, request_id: str = ""):
        super().__init__(message)
        self.code = code
        self.message = message
        self.request_id = request_id


@dataclass(frozen=True)
class RequestFrame:
    request_id: str
    method: str
    params: dict[str, Any]
    idempotency_key: str = ""


def parse_request(raw: str, *, max_frame_bytes: int) -> RequestFrame:
    if len(raw.encode("utf-8")) > max_frame_bytes:
        raise ProtocolError("frame_too_large", "request frame exceeds configured limit")
    try:
        frame = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ProtocolError("invalid_json", "request must be valid JSON") from exc
    if not isinstance(frame, dict):
        raise ProtocolError("invalid_frame", "request frame must be an object")
    request_id = str(frame.get("id") or "").strip()
    if frame.get("type") != "req":
        raise ProtocolError("invalid_frame", "frame type must be 'req'", request_id=request_id)
    if not request_id or len(request_id) > 128:
        raise ProtocolError("invalid_request_id", "request id is required and must be <= 128 characters")
    method = str(frame.get("method") or "").strip()
    if not method or len(method) > 128:
        raise ProtocolError("invalid_method", "method is required", request_id=request_id)
    params = frame.get("params", {})
    if not isinstance(params, dict):
        raise ProtocolError("invalid_params", "params must be an object", request_id=request_id)
    idem_key = str(frame.get("idempotency_key") or "").strip()
    if len(idem_key) > 200:
        raise ProtocolError("invalid_idempotency_key", "idempotency key is too long", request_id=request_id)
    return RequestFrame(request_id, method, params, idem_key)


def response_ok(request_id: str, result: Any, *, replayed: bool = False) -> dict[str, Any]:
    frame = {"v": PROTOCOL_VERSION, "type": "res", "id": request_id, "ok": True, "result": result}
    if replayed:
        frame["idempotency_replayed"] = True
    return frame


def response_error(request_id: str, code: str, message: str, details: Any = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return {
        "v": PROTOCOL_VERSION,
        "type": "res",
        "id": request_id,
        "ok": False,
        "error": error,
    }


def event_frame(event: str, payload: Any, *, session_id: str = "") -> dict[str, Any]:
    frame: dict[str, Any] = {
        "v": PROTOCOL_VERSION,
        "type": "event",
        "event": event,
        "event_id": str(uuid.uuid4()),
        "payload": payload,
    }
    if session_id:
        frame["session_id"] = session_id
    return frame
