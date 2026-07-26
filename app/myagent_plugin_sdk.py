"""Public Plugin API v1 used inside MyAgent Python plugin workers.

The SDK intentionally has no dependency on the MyAgent host runtime.  A plugin
may either expose a module-level ``plugin = Plugin()`` registry or define
``setup(plugin: Plugin)`` and register capabilities on the supplied registry.
"""
from __future__ import annotations

import inspect
import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, Mapping, Optional


PLUGIN_API_VERSION = "1"
_TOOL_NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_COMMAND_NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_HOOK_EVENTS = frozenset(
    {
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
    }
)
_FAILURE_POLICIES = frozenset({"ignore", "warn", "block", "pause"})
_TOOL_EFFECTS = frozenset({"", "read", "workspace_write", "external_write"})


class PluginApiError(ValueError):
    """Raised when a plugin registers an invalid or duplicate capability."""


@dataclass(frozen=True)
class ToolRegistration:
    name: str
    description: str
    input_schema: Mapping[str, Any]
    handler: Callable[..., Any]
    effect: str = ""
    resource_arguments: tuple[str, ...] = ()
    path_arguments: tuple[str, ...] = ()
    workspace_root_argument: str = ""
    worktree_compatible: bool = False

    def describe(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": dict(self.input_schema),
            "effect": self.effect,
            "resource_arguments": list(self.resource_arguments),
            "path_arguments": list(self.path_arguments),
            "workspace_root_argument": self.workspace_root_argument,
            "worktree_compatible": self.worktree_compatible,
        }


@dataclass(frozen=True)
class HookRegistration:
    id: str
    event: str
    matcher: str
    priority: int
    failure_policy: str
    handler: Callable[..., Any]

    def describe(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "event": self.event,
            "matcher": self.matcher,
            "priority": self.priority,
            "failure_policy": self.failure_policy,
        }


@dataclass(frozen=True)
class CommandRegistration:
    name: str
    description: str
    usage: str
    handler: Callable[..., Any]

    def describe(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "usage": self.usage,
        }


class Plugin:
    """Capability registry exposed to a Python plugin entrypoint."""

    api_version = PLUGIN_API_VERSION

    def __init__(self) -> None:
        self._tools: Dict[str, ToolRegistration] = {}
        self._hooks: Dict[str, HookRegistration] = {}
        self._commands: Dict[str, CommandRegistration] = {}
        self._activate_handlers: list[Callable[..., Any]] = []
        self._deactivate_handlers: list[Callable[..., Any]] = []

    @property
    def tools(self) -> Mapping[str, ToolRegistration]:
        return dict(self._tools)

    @property
    def hooks(self) -> Mapping[str, HookRegistration]:
        return dict(self._hooks)

    @property
    def commands(self) -> Mapping[str, CommandRegistration]:
        return dict(self._commands)

    def register_tool(
        self,
        name: str,
        handler: Callable[..., Any],
        *,
        description: str = "",
        input_schema: Optional[Mapping[str, Any]] = None,
        effect: str = "",
        resource_arguments: tuple[str, ...] | list[str] = (),
        path_arguments: tuple[str, ...] | list[str] = (),
        workspace_root_argument: str = "",
        worktree_compatible: bool = False,
    ) -> Callable[..., Any]:
        tool_name = str(name or "").strip()
        if not _TOOL_NAME_RE.fullmatch(tool_name):
            raise PluginApiError(
                "Tool name must use 1-64 ASCII letters, digits, underscores, or hyphens"
            )
        if tool_name in self._tools:
            raise PluginApiError(f"Duplicate plugin tool: {tool_name}")
        if not callable(handler):
            raise PluginApiError(f"Tool handler for {tool_name!r} must be callable")
        schema: Mapping[str, Any] = input_schema or {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        }
        if not isinstance(schema, Mapping) or schema.get("type", "object") != "object":
            raise PluginApiError(f"Tool input_schema for {tool_name!r} must be an object schema")
        normalized_effect = str(effect or "").strip().lower()
        if normalized_effect not in _TOOL_EFFECTS:
            raise PluginApiError(
                f"Unsupported tool effect for {tool_name!r}: {normalized_effect!r}"
            )
        resource_rows = (
            [resource_arguments]
            if isinstance(resource_arguments, str)
            else resource_arguments
        )
        path_rows = [path_arguments] if isinstance(path_arguments, str) else path_arguments
        resources = tuple(
            str(item).strip() for item in resource_rows if str(item).strip()
        )
        paths = tuple(str(item).strip() for item in path_rows if str(item).strip())
        root_argument = str(workspace_root_argument or "").strip()
        self._tools[tool_name] = ToolRegistration(
            name=tool_name,
            description=str(description or "").strip(),
            input_schema=dict(schema),
            handler=handler,
            effect=normalized_effect,
            resource_arguments=resources,
            path_arguments=paths,
            workspace_root_argument=root_argument,
            worktree_compatible=bool(worktree_compatible or root_argument),
        )
        return handler

    def tool(
        self,
        name: Optional[str] = None,
        *,
        description: str = "",
        input_schema: Optional[Mapping[str, Any]] = None,
        effect: str = "",
        resource_arguments: tuple[str, ...] | list[str] = (),
        path_arguments: tuple[str, ...] | list[str] = (),
        workspace_root_argument: str = "",
        worktree_compatible: bool = False,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Decorator form of :meth:`register_tool`."""

        def decorate(handler: Callable[..., Any]) -> Callable[..., Any]:
            self.register_tool(
                name or handler.__name__,
                handler,
                description=description or inspect.getdoc(handler) or "",
                input_schema=input_schema,
                effect=effect,
                resource_arguments=resource_arguments,
                path_arguments=path_arguments,
                workspace_root_argument=workspace_root_argument,
                worktree_compatible=worktree_compatible,
            )
            return handler

        return decorate

    def describe_tools(self) -> list[Dict[str, Any]]:
        return [
            registration.describe()
            for _name, registration in sorted(self._tools.items())
        ]

    def register_hook(
        self,
        event: str,
        handler: Callable[..., Any],
        *,
        hook_id: Optional[str] = None,
        matcher: str = "",
        priority: int = 100,
        failure_policy: str = "warn",
    ) -> Callable[..., Any]:
        event_name = str(event or "").strip()
        if event_name not in _HOOK_EVENTS:
            raise PluginApiError(f"Unsupported hook event: {event_name}")
        identifier = str(hook_id or getattr(handler, "__name__", "") or "").strip()
        if not _TOOL_NAME_RE.fullmatch(identifier):
            raise PluginApiError(
                "Hook id must use 1-64 ASCII letters, digits, underscores, or hyphens"
            )
        key = f"{event_name}:{identifier}"
        if key in self._hooks:
            raise PluginApiError(f"Duplicate plugin hook: {key}")
        policy = str(failure_policy or "warn").strip().lower()
        if policy not in _FAILURE_POLICIES:
            raise PluginApiError(f"Unsupported hook failure policy: {policy}")
        if not callable(handler):
            raise PluginApiError(f"Hook handler for {key!r} must be callable")
        self._hooks[key] = HookRegistration(
            id=identifier,
            event=event_name,
            matcher=str(matcher or ""),
            priority=int(priority),
            failure_policy=policy,
            handler=handler,
        )
        return handler

    def hook(
        self,
        event: str,
        *,
        hook_id: Optional[str] = None,
        matcher: str = "",
        priority: int = 100,
        failure_policy: str = "warn",
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorate(handler: Callable[..., Any]) -> Callable[..., Any]:
            self.register_hook(
                event,
                handler,
                hook_id=hook_id,
                matcher=matcher,
                priority=priority,
                failure_policy=failure_policy,
            )
            return handler

        return decorate

    def register_command(
        self,
        name: str,
        handler: Callable[..., Any],
        *,
        description: str = "",
        usage: str = "",
    ) -> Callable[..., Any]:
        command_name = str(name or "").strip()
        if not _COMMAND_NAME_RE.fullmatch(command_name):
            raise PluginApiError(
                "Command name must use 1-64 ASCII letters, digits, underscores, or hyphens"
            )
        if command_name in self._commands:
            raise PluginApiError(f"Duplicate plugin command: {command_name}")
        if not callable(handler):
            raise PluginApiError(f"Command handler for {command_name!r} must be callable")
        self._commands[command_name] = CommandRegistration(
            name=command_name,
            description=str(description or "").strip(),
            usage=str(usage or "").strip(),
            handler=handler,
        )
        return handler

    def command(
        self,
        name: Optional[str] = None,
        *,
        description: str = "",
        usage: str = "",
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorate(handler: Callable[..., Any]) -> Callable[..., Any]:
            self.register_command(
                name or handler.__name__,
                handler,
                description=description or inspect.getdoc(handler) or "",
                usage=usage,
            )
            return handler

        return decorate

    def on_activate(
        self, handler: Callable[..., Any]
    ) -> Callable[..., Any]:
        if not callable(handler):
            raise PluginApiError("Activation handler must be callable")
        self._activate_handlers.append(handler)
        return handler

    def on_deactivate(
        self, handler: Callable[..., Any]
    ) -> Callable[..., Any]:
        if not callable(handler):
            raise PluginApiError("Deactivation handler must be callable")
        self._deactivate_handlers.append(handler)
        return handler

    def describe_hooks(self) -> list[Dict[str, Any]]:
        return [
            registration.describe()
            for _key, registration in sorted(self._hooks.items())
        ]

    def describe_commands(self) -> list[Dict[str, Any]]:
        return [
            registration.describe()
            for _name, registration in sorted(self._commands.items())
        ]

    @staticmethod
    async def _await_result(value: Any) -> Any:
        return await value if inspect.isawaitable(value) else value

    async def invoke_tool(self, name: str, arguments: Optional[Mapping[str, Any]] = None) -> Any:
        registration = self._tools.get(str(name or ""))
        if registration is None:
            raise PluginApiError(f"Unknown plugin tool: {name}")
        kwargs = dict(arguments or {})
        return await self._await_result(registration.handler(**kwargs))

    async def invoke_hook(
        self,
        event: str,
        hook_id: str,
        payload: Optional[Mapping[str, Any]] = None,
    ) -> Any:
        registration = self._hooks.get(f"{event}:{hook_id}")
        if registration is None:
            raise PluginApiError(f"Unknown plugin hook: {event}:{hook_id}")
        return await self._await_result(registration.handler(dict(payload or {})))

    async def invoke_command(
        self,
        name: str,
        arguments: str = "",
        context: Optional[Mapping[str, Any]] = None,
    ) -> Any:
        registration = self._commands.get(str(name or ""))
        if registration is None:
            raise PluginApiError(f"Unknown plugin command: {name}")
        return await self._await_result(
            registration.handler(str(arguments or ""), dict(context or {}))
        )

    async def activate(self, context: Optional[Mapping[str, Any]] = None) -> None:
        for handler in self._activate_handlers:
            await self._await_result(handler(dict(context or {})))

    async def deactivate(self, context: Optional[Mapping[str, Any]] = None) -> None:
        for handler in reversed(self._deactivate_handlers):
            await self._await_result(handler(dict(context or {})))


__all__ = [
    "PLUGIN_API_VERSION",
    "CommandRegistration",
    "HookRegistration",
    "Plugin",
    "PluginApiError",
    "ToolRegistration",
]
