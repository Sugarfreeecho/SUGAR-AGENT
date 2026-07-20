"""Domain constants and payload validation for Agent Team."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Iterable


TEAM_STATUSES = frozenset({"active", "shutting_down", "stopped", "archived"})
MEMBER_STATES = frozenset(
    {"starting", "idle", "working", "waiting_permission", "stopping", "stopped", "failed"}
)
TASK_STATUSES = frozenset({"pending", "in_progress", "blocked", "completed", "cancelled"})
TASK_PRIORITIES = frozenset({"low", "normal", "high", "urgent"})
MESSAGE_STATUSES = frozenset({"queued", "delivering", "delivered", "consumed", "failed"})
TERMINAL_MEMBER_STATES = frozenset({"stopped", "failed"})
TERMINAL_TASK_STATUSES = frozenset({"completed", "cancelled"})


class AgentTeamError(RuntimeError):
    """Base error for Agent Team domain operations."""


class AgentTeamValidationError(AgentTeamError, ValueError):
    pass


class AgentTeamNotFoundError(AgentTeamError, LookupError):
    pass


class AgentTeamConflictError(AgentTeamError):
    pass


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def clean_text(value: Any, field: str, *, max_length: int, required: bool = True) -> str:
    text = str(value or "").strip()
    if required and not text:
        raise AgentTeamValidationError(f"{field} is required")
    if len(text) > max_length:
        raise AgentTeamValidationError(f"{field} exceeds {max_length} characters")
    return text


def clean_id(value: Any, field: str) -> str:
    text = clean_text(value, field, max_length=160)
    if any(part in text for part in ("/", "\\", "..")):
        raise AgentTeamValidationError(f"invalid {field}")
    return text


def choice(value: Any, field: str, allowed: Iterable[str], *, default: str | None = None) -> str:
    text = str(value if value is not None else default or "").strip().lower()
    allowed_set = frozenset(allowed)
    if text not in allowed_set:
        raise AgentTeamValidationError(f"invalid {field}: {text!r}")
    return text


@dataclass(frozen=True)
class TeamLimits:
    max_members: int = 4
    max_tasks: int = 1000
    max_messages: int = 2000
    max_permissions: int = 500
    max_message_chars: int = 32_000

    def __post_init__(self) -> None:
        if self.max_members < 1:
            raise AgentTeamValidationError("max_members must be positive")
        if self.max_tasks < 1:
            raise AgentTeamValidationError("max_tasks must be positive")
        if self.max_messages < 1:
            raise AgentTeamValidationError("max_messages must be positive")
        if self.max_permissions < 1:
            raise AgentTeamValidationError("max_permissions must be positive")
        if self.max_message_chars < 1:
            raise AgentTeamValidationError("max_message_chars must be positive")
