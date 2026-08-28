"""Structured Responses error classification and endpoint capability cache."""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, Mapping, Optional


CAPABILITY_SCHEMA_VERSION = 1


class ResponsesErrorKind(str, Enum):
    INVALID_PREVIOUS = "invalid_previous"
    UNSUPPORTED_STATE = "unsupported_state"
    INVALID_ENCRYPTED_REASONING = "invalid_encrypted_reasoning"
    UNSUPPORTED_ENCRYPTED_REASONING = "unsupported_encrypted_reasoning"
    UNSUPPORTED_COMPACT = "unsupported_compact"
    RATE_LIMIT = "rate_limit"
    TRANSIENT = "transient"
    OTHER = "other"


@dataclass(frozen=True)
class ResponsesErrorInfo:
    kind: ResponsesErrorKind
    status_code: int = 0
    param: str = ""
    code: str = ""
    error_type: str = ""
    message: str = ""


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _error_payload(exc: BaseException) -> Mapping[str, Any]:
    body = _mapping(getattr(exc, "body", None))
    if body:
        nested = _mapping(body.get("error"))
        return nested or body
    response = getattr(exc, "response", None)
    json_method = getattr(response, "json", None)
    if callable(json_method):
        try:
            body = _mapping(json_method())
        except Exception:
            body = {}
        nested = _mapping(body.get("error"))
        return nested or body
    return {}


def classify_responses_error(
    exc: BaseException,
    *,
    operation: str = "create",
) -> ResponsesErrorInfo:
    payload = _error_payload(exc)
    status_code = int(
        getattr(exc, "status_code", 0)
        or getattr(getattr(exc, "response", None), "status_code", 0)
        or 0
    )
    param = str(payload.get("param") or "").strip().lower()
    code = str(payload.get("code") or "").strip().lower()
    error_type = str(payload.get("type") or "").strip().lower()
    message = str(payload.get("message") or exc or "").strip()
    message_text = message.lower()
    text = " ".join((param, code, error_type, message_text))

    if status_code == 429:
        kind = ResponsesErrorKind.RATE_LIMIT
    elif status_code >= 500:
        kind = ResponsesErrorKind.TRANSIENT
    elif str(operation or "").lower() == "compact" and (
        status_code in {404, 405, 501}
        or any(
            marker in text
            for marker in (
                "unsupported",
                "not supported",
                "unknown endpoint",
                "has no attribute",
                "no such method",
            )
        )
    ):
        kind = ResponsesErrorKind.UNSUPPORTED_COMPACT
    elif any(
        marker in text
        for marker in (
            "previous_response_id",
            "previous response",
            "referenced response",
            "response reference",
        )
    ) and any(
        marker in text
        for marker in ("invalid", "not found", "expired", "deleted", "does not exist")
    ):
        kind = ResponsesErrorKind.INVALID_PREVIOUS
    elif "encrypted_content" in text and any(
        marker in message_text for marker in ("invalid", "decrypt", "issuer", "does not match")
    ):
        kind = ResponsesErrorKind.INVALID_ENCRYPTED_REASONING
    elif (
        param in {"include", "reasoning.encrypted_content"}
        or "reasoning.encrypted_content" in text
        or "encrypted_content" in text
    ) and any(
        marker in text
        for marker in (
            "unknown parameter",
            "unrecognized",
            "unsupported",
            "not supported",
            "extra fields not permitted",
        )
    ):
        kind = ResponsesErrorKind.UNSUPPORTED_ENCRYPTED_REASONING
    elif (
        param in {"store", "previous_response_id"}
        or "previous_response_id" in text
        or "parameter `store`" in text
        or "parameter 'store'" in text
        or "unknown parameter store" in text
    ) and any(
        marker in text
        for marker in (
            "unknown parameter",
            "unrecognized",
            "unsupported",
            "not supported",
            "extra fields not permitted",
        )
    ):
        kind = ResponsesErrorKind.UNSUPPORTED_STATE
    else:
        kind = ResponsesErrorKind.OTHER
    return ResponsesErrorInfo(
        kind=kind,
        status_code=status_code,
        param=param,
        code=code,
        error_type=error_type,
        message=message,
    )


@dataclass(frozen=True)
class ProviderCapabilities:
    issuer: str
    responses: Optional[bool] = None
    previous_response_id: Optional[bool] = None
    store: Optional[bool] = None
    encrypted_reasoning_replay: Optional[bool] = None
    compact: Optional[bool] = None
    websocket: Optional[bool] = None
    schema_version: int = CAPABILITY_SCHEMA_VERSION
    expires_at: float = 0.0

    def valid(self, now: Optional[float] = None) -> bool:
        return not self.expires_at or self.expires_at > float(now or time.time())


class ResponsesCapabilityCache:
    def __init__(self, *, ttl_seconds: float = 3600.0) -> None:
        self.ttl_seconds = max(1.0, float(ttl_seconds))
        self._lock = threading.RLock()
        self._values: dict[str, ProviderCapabilities] = {}

    def get(self, issuer: str) -> ProviderCapabilities:
        key = str(issuer or "")
        now = time.time()
        with self._lock:
            value = self._values.get(key)
            if value is None or not value.valid(now):
                value = ProviderCapabilities(
                    issuer=key,
                    expires_at=now + self.ttl_seconds,
                )
                self._values[key] = value
            return value

    def update(self, issuer: str, **changes: Optional[bool]) -> ProviderCapabilities:
        key = str(issuer or "")
        with self._lock:
            current = self.get(key)
            allowed = {
                "responses",
                "previous_response_id",
                "store",
                "encrypted_reasoning_replay",
                "compact",
                "websocket",
            }
            unknown = set(changes) - allowed
            if unknown:
                raise ValueError(f"unknown Responses capabilities: {sorted(unknown)}")
            value = replace(
                current,
                **changes,
                expires_at=time.time() + self.ttl_seconds,
            )
            self._values[key] = value
            return value

    def clear(self, issuer: str = "") -> None:
        with self._lock:
            if issuer:
                self._values.pop(str(issuer), None)
            else:
                self._values.clear()


responses_capability_cache = ResponsesCapabilityCache()


__all__ = [
    "CAPABILITY_SCHEMA_VERSION",
    "ProviderCapabilities",
    "ResponsesCapabilityCache",
    "ResponsesErrorInfo",
    "ResponsesErrorKind",
    "classify_responses_error",
    "responses_capability_cache",
]
