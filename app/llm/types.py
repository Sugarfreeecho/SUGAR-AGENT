"""Provider-neutral request and stream contracts."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Mapping, Optional


class LLMRequestPurpose(str, Enum):
    MAIN = "main"
    GOAL_JUDGE = "goal_judge"
    TITLE = "title"
    SUMMARY = "summary"
    SECURITY_REVIEW = "security_review"
    DIAGNOSTIC = "diagnostic"


@dataclass(frozen=True)
class TransportEvent:
    """One provider-independent stream event."""

    kind: str
    text: str = ""
    index: int = 0
    tool_call_id: str = ""
    tool_name: str = ""
    arguments_delta: str = ""
    usage: Optional[Dict[str, int]] = None
    finish_reason: Optional[str] = None
    stop_reason: Optional[str] = None
    model: str = ""
    provider_data: Optional[Dict[str, Any]] = None

    @property
    def is_first_token(self) -> bool:
        if self.kind in {"content_delta", "reasoning_delta"}:
            return bool(self.text)
        if self.kind == "tool_call_delta":
            return bool(self.tool_call_id or self.tool_name or self.arguments_delta)
        return False


@dataclass(frozen=True)
class LLMRequestContext:
    """Local context identity that must not be inferred from chat messages."""

    session_id: str = ""
    lineage_id: str = ""
    history_generation: int = 0
    purpose: LLMRequestPurpose = LLMRequestPurpose.MAIN
    server_storage_allowed: bool = True
    responses_compaction: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_value(cls, value: Any) -> "LLMRequestContext":
        if isinstance(value, cls):
            return value
        raw: Mapping[str, Any] = value if isinstance(value, Mapping) else {}
        purpose_raw = str(raw.get("purpose") or LLMRequestPurpose.MAIN.value)
        try:
            purpose = LLMRequestPurpose(purpose_raw)
        except ValueError:
            purpose = LLMRequestPurpose.DIAGNOSTIC
        return cls(
            session_id=str(raw.get("session_id") or ""),
            lineage_id=str(raw.get("lineage_id") or ""),
            history_generation=int(raw.get("history_generation") or 0),
            purpose=purpose,
            server_storage_allowed=bool(raw.get("server_storage_allowed", True)),
            responses_compaction=dict(raw.get("responses_compaction") or {}),
        )

    def prompt_cache_key(self, *, issuer: str, model: str) -> str:
        scope = self.lineage_id or self.session_id
        if not scope:
            return ""
        stable = json.dumps(
            {
                "scope": scope,
                "purpose": self.purpose.value,
                "issuer": str(issuer or ""),
                "model": str(model or ""),
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return "myagent-session-" + hashlib.sha256(stable.encode("utf-8")).hexdigest()[:32]

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "lineage_id": self.lineage_id,
            "history_generation": self.history_generation,
            "purpose": self.purpose.value,
            "server_storage_allowed": self.server_storage_allowed,
            "responses_compaction": dict(self.responses_compaction),
        }


class HttpStreamTransportError(RuntimeError):
    """Transport failure that carries the provider's HTTP status.

    Both the raw-httpx Chat Completions path and the Anthropic Messages path
    raise this, so the retry / model-fallback classifiers see one shape
    instead of guessing at SDK-specific attributes.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: Optional[int] = None,
        body: str = "",
        provider_code: str = "",
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body
        self.provider_code = provider_code


def response_status_code(exc: BaseException) -> Optional[int]:
    """HTTP status from an SDK error or the httpx response it wraps.

    ``httpx.HTTPStatusError`` keeps the code on ``.response.status_code`` and
    has no ``.status_code`` of its own, so reading only the exception demoted
    every raw-httpx 4xx (403/429/400) to "unknown error".
    """
    for value in (
        getattr(exc, "status_code", None),
        getattr(getattr(exc, "response", None), "status_code", None),
    ):
        try:
            status = int(value)
        except (TypeError, ValueError):
            continue
        if 100 <= status <= 599:
            return status
    return None


def safe_response_text(response: Any) -> str:
    """Return an httpx response body without touching an unread stream.

    ``getattr(response, "text")`` raises ``httpx.ResponseNotRead`` for a
    streaming response whose body was never consumed -- exactly the shape of a
    failed stream request. Letting that escape replaces the provider error being
    diagnosed, so an unread body reads as "".
    """
    if response is None:
        return ""
    try:
        if getattr(response, "is_stream_consumed", True) is False:
            return ""
        return str(getattr(response, "text", "") or "")
    except Exception:
        return ""


__all__ = [
    "HttpStreamTransportError",
    "LLMRequestContext",
    "LLMRequestPurpose",
    "TransportEvent",
    "response_status_code",
    "safe_response_text",
]
