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


__all__ = ["LLMRequestContext", "LLMRequestPurpose", "TransportEvent"]
