"""Execution traits for built-in tools and source-neutral descriptors."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolExecutionPolicy:
    effect: str = "write"
    parallel_safe: bool = False
    pressure_limited: bool = False
    interactive: bool = False
    early_stream_safe: bool = True
    interruptibility: str = "non_interruptible"


_LOCAL_READS = {"read_file", "ls", "list_dir", "glob", "grep", "activate_skill"}
_NETWORK_READS = {"web_search", "web_fetch"}


def builtin_tool_policy(name: str) -> ToolExecutionPolicy:
    key = str(name or "").strip()
    if key in _LOCAL_READS:
        return ToolExecutionPolicy(
            effect="read",
            parallel_safe=True,
            pressure_limited=True,
            interruptibility="safe",
        )
    if key in _NETWORK_READS:
        return ToolExecutionPolicy(
            effect="read",
            parallel_safe=True,
            interruptibility="safe",
        )
    return ToolExecutionPolicy()


def plugin_tool_policy(effect: str) -> ToolExecutionPolicy:
    normalized = str(effect or "").strip().lower()
    if normalized == "read":
        return ToolExecutionPolicy(
            effect="read",
            parallel_safe=True,
            interruptibility="safe",
        )
    if normalized in {"workspace_write", "external_write"}:
        return ToolExecutionPolicy(effect=normalized)
    return ToolExecutionPolicy()


__all__ = ["ToolExecutionPolicy", "builtin_tool_policy", "plugin_tool_policy"]
