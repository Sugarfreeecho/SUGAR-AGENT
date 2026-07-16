"""Public hook API for MyAgent.

Typical integration::

    manager = HookManager(project_root, plugin_sources=plugin_hook_sources)
    result = await manager.dispatch("PreToolUse", {
        "session_id": session_id,
        "tool_name": tool_name,
        "tool_input": tool_input,
    })
    if result.blocked:
        ...
"""
from .config import load_hook_definitions, load_hook_sources
from .executor import CommandHookExecutor, build_hook_environment
from .manager import HookManager
from .matcher import hook_match_value, hook_matches
from .models import (
    FAILURE_POLICIES,
    HOOK_DECISIONS,
    SUPPORTED_HOOK_EVENTS,
    CommandSpec,
    HookConfigurationError,
    HookDefinition,
    HookDispatchResult,
    HookError,
    HookExecutionError,
    HookExecutionResult,
    HookLoadResult,
    HookSource,
    hooks_enabled,
)


HookRegistry = HookManager

__all__ = [
    "FAILURE_POLICIES",
    "HOOK_DECISIONS",
    "SUPPORTED_HOOK_EVENTS",
    "CommandHookExecutor",
    "CommandSpec",
    "HookConfigurationError",
    "HookDefinition",
    "HookDispatchResult",
    "HookError",
    "HookExecutionError",
    "HookExecutionResult",
    "HookLoadResult",
    "HookManager",
    "HookRegistry",
    "HookSource",
    "build_hook_environment",
    "hook_match_value",
    "hook_matches",
    "hooks_enabled",
    "load_hook_definitions",
    "load_hook_sources",
]
