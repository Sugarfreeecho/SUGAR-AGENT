"""Data models and public constants for MyAgent's hook runtime."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Tuple


SUPPORTED_HOOK_EVENTS: Tuple[str, ...] = (
    "SessionStart",
    "SessionEnd",
    "UserPromptSubmit",
    "PreToolUse",
    "PostToolUse",
    "PostToolUseFailure",
    "Stop",
    "RunFailed",
    "SubagentStart",
    "SubagentStop",
    "PreCompact",
    "PostCompact",
    "GoalCreated",
    "GoalBeforeContinue",
    "GoalCompleted",
    "GoalBlocked",
)
SUPPORTED_HOOK_EVENT_SET = frozenset(SUPPORTED_HOOK_EVENTS)
HOOK_DECISIONS = frozenset({"allow", "deny", "ask", "pause", "continue"})
FAILURE_POLICIES = frozenset({"ignore", "warn", "block", "pause"})
_FALSE_VALUES = frozenset({"0", "false", "no", "off"})


def hooks_enabled(value: Optional[Any] = None) -> bool:
    """Return whether hooks are enabled; ``HOOKS_ENABLED`` defaults to on."""

    if value is None:
        value = os.getenv("HOOKS_ENABLED", "1")
    return str(value).strip().lower() not in _FALSE_VALUES


class HookError(RuntimeError):
    """Base class for hook failures."""


class HookConfigurationError(HookError, ValueError):
    """Raised for an invalid hooks.json document."""


class HookExecutionError(HookError):
    """Raised internally when a command hook cannot produce a valid result."""


@dataclass(frozen=True)
class HookSource:
    """A project or plugin-owned hook configuration source."""

    source_id: str
    root: Path
    config_path: Optional[Path] = None
    config: Optional[Mapping[str, Any]] = None
    plugin_id: Optional[str] = None


@dataclass(frozen=True)
class CommandSpec:
    command: Optional[str] = None
    windows_command: Optional[str] = None
    unix_command: Optional[str] = None
    cwd: Optional[str] = None
    timeout_seconds: float = 10.0
    env_allowlist: Tuple[str, ...] = ()
    env: Mapping[str, str] = field(default_factory=dict)
    max_output_bytes: int = 1024 * 1024

    def platform_command(self, *, is_windows: Optional[bool] = None) -> Optional[str]:
        if is_windows is None:
            is_windows = os.name == "nt"
        selected = self.windows_command if is_windows else self.unix_command
        return selected or self.command


@dataclass(frozen=True)
class HookDefinition:
    id: str
    event: str
    command: CommandSpec
    matcher: str = ""
    handler_type: str = "command"
    failure_policy: str = "warn"
    priority: int = 100
    source_id: str = "project"
    source_root: Path = Path(".")
    plugin_id: Optional[str] = None
    order: int = 0


@dataclass(frozen=True)
class HookLoadResult:
    definitions: Tuple[HookDefinition, ...] = ()
    errors: Tuple[str, ...] = ()
    loaded_sources: Tuple[str, ...] = ()


@dataclass(frozen=True)
class HookExecutionResult:
    hook_id: str
    event: str
    source_id: str
    plugin_id: Optional[str] = None
    success: bool = True
    outcome: str = "success"
    decision: str = "continue"
    reason: str = ""
    updated_input: Optional[Dict[str, Any]] = None
    additional_context: str = ""
    user_message: str = ""
    duration_ms: int = 0
    exit_code: Optional[int] = None
    stderr: str = ""
    error: str = ""
    failure_policy: str = "warn"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hook_id": self.hook_id,
            "event": self.event,
            "source_id": self.source_id,
            "plugin_id": self.plugin_id,
            "success": self.success,
            "outcome": self.outcome,
            "decision": self.decision,
            "reason": self.reason,
            "updated_input": self.updated_input,
            "additional_context": self.additional_context,
            "user_message": self.user_message,
            "duration_ms": self.duration_ms,
            "exit_code": self.exit_code,
            "stderr": self.stderr,
            "error": self.error,
            "failure_policy": self.failure_policy,
        }


@dataclass(frozen=True)
class HookDispatchResult:
    event: str
    enabled: bool = True
    skipped: bool = False
    skip_reason: str = ""
    decision: str = "continue"
    matched_hooks: int = 0
    executed_hooks: int = 0
    input_modified: bool = False
    original_input: Optional[Dict[str, Any]] = None
    updated_input: Optional[Dict[str, Any]] = None
    additional_context: str = ""
    user_messages: Tuple[str, ...] = ()
    warnings: Tuple[str, ...] = ()
    results: Tuple[HookExecutionResult, ...] = ()
    duration_ms: int = 0
    config_errors: Tuple[str, ...] = ()

    @property
    def continue_execution(self) -> bool:
        return self.decision in {"allow", "continue"}

    @property
    def requires_approval(self) -> bool:
        return self.decision == "ask"

    @property
    def should_pause(self) -> bool:
        return self.decision == "pause"

    @property
    def blocked(self) -> bool:
        return self.decision == "deny"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event": self.event,
            "enabled": self.enabled,
            "skipped": self.skipped,
            "skip_reason": self.skip_reason,
            "decision": self.decision,
            "continue_execution": self.continue_execution,
            "requires_approval": self.requires_approval,
            "should_pause": self.should_pause,
            "blocked": self.blocked,
            "matched_hooks": self.matched_hooks,
            "executed_hooks": self.executed_hooks,
            "input_modified": self.input_modified,
            "original_input": self.original_input,
            "updated_input": self.updated_input,
            "additional_context": self.additional_context,
            "user_messages": list(self.user_messages),
            "warnings": list(self.warnings),
            "results": [item.to_dict() for item in self.results],
            "duration_ms": self.duration_ms,
            "config_errors": list(self.config_errors),
        }
