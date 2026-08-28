"""Public Plugin API v1 used inside MyAgent Python plugin workers.

The SDK intentionally has no dependency on the MyAgent host runtime.  A plugin
may either expose a module-level ``plugin = Plugin()`` registry or define
``setup(plugin: Plugin)`` and register capabilities on the supplied registry.
"""
from __future__ import annotations

import asyncio
import copy
import inspect
import re
import time
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Mapping, Optional


PLUGIN_API_VERSION = "1"
DEFERRED_RESULT_KEY = "_myagent_deferred"
HOST_ACTIONS_KEY = "_host_actions"
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


class _ReadOnlyContextMapping(Mapping[str, Any]):
    """Immutable during a call, but compatible with dataclasses.asdict()."""

    def __init__(self, values: Optional[Mapping[str, Any]] = None) -> None:
        self._values = dict(values or {})

    def __getitem__(self, key: str) -> Any:
        return self._values[key]

    def __iter__(self):
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def __deepcopy__(self, memo):
        return copy.deepcopy(self._values, memo)


@dataclass(frozen=True)
class ToolCallContext:
    """Host-owned metadata for the currently executing plugin tool call."""

    session_id: str = ""
    run_id: str = ""
    plugin_id: str = ""
    workspace_root: str = ""
    plugin_data_dir: str = ""
    plugin_cache_dir: str = ""
    plugin_temp_dir: str = ""
    cancellation_id: str = ""
    session_state: Mapping[str, Any] = field(default_factory=dict)
    settings: Mapping[str, Any] = field(default_factory=dict)
    secrets: Mapping[str, str] = field(default_factory=dict)


_EMPTY_TOOL_CALL_CONTEXT = ToolCallContext()
_TOOL_CALL_CONTEXT: ContextVar[ToolCallContext] = ContextVar(
    "myagent_plugin_tool_call_context",
    default=_EMPTY_TOOL_CALL_CONTEXT,
)


def current_tool_context() -> ToolCallContext:
    """Return immutable host metadata for the current tool invocation."""

    return _TOOL_CALL_CONTEXT.get()


def _tool_call_context(value: Optional[Mapping[str, Any]]) -> ToolCallContext:
    raw = dict(value or {})

    def _freeze(item: Any) -> Any:
        if isinstance(item, Mapping):
            return _ReadOnlyContextMapping(
                {str(key): _freeze(child) for key, child in item.items()}
            )
        if isinstance(item, list):
            return tuple(_freeze(child) for child in item)
        return item

    raw_session_state = raw.get("session_state")
    return ToolCallContext(
        session_id=str(raw.get("session_id") or ""),
        run_id=str(raw.get("run_id") or ""),
        plugin_id=str(raw.get("plugin_id") or ""),
        workspace_root=str(raw.get("workspace_root") or ""),
        plugin_data_dir=str(raw.get("plugin_data_dir") or ""),
        plugin_cache_dir=str(raw.get("plugin_cache_dir") or ""),
        plugin_temp_dir=str(raw.get("plugin_temp_dir") or ""),
        cancellation_id=str(raw.get("cancellation_id") or ""),
        session_state=_freeze(raw_session_state)
        if isinstance(raw_session_state, Mapping)
        else _ReadOnlyContextMapping(),
        settings=dict(raw.get("settings") or {})
        if isinstance(raw.get("settings"), Mapping)
        else {},
        secrets={str(key): str(item) for key, item in dict(raw.get("secrets") or {}).items()}
        if isinstance(raw.get("secrets"), Mapping)
        else {},
    )


@dataclass(frozen=True)
class DeferredResultSpec:
    """Validated instructions for polling a deferred plugin tool result."""

    token: str
    poll_after_ms: int
    timeout_seconds: float
    expires_at: float


def deferred_result(
    token: str,
    result: Optional[Mapping[str, Any]] = None,
    *,
    poll_after_ms: int = 1000,
    timeout_seconds: float = 300,
) -> Dict[str, Any]:
    """Return a pending tool outcome without blocking the plugin worker."""

    opaque_token = str(token or "").strip()
    if not opaque_token or len(opaque_token) > 4096:
        raise PluginApiError("Deferred result token must contain 1-4096 characters")
    poll_ms = max(50, min(10_000, int(poll_after_ms)))
    timeout = max(0.1, min(3600.0, float(timeout_seconds)))
    expires_at = time.time() + timeout
    payload = dict(result or {})
    payload[DEFERRED_RESULT_KEY] = {
        "token": opaque_token,
        "poll_after_ms": poll_ms,
        "timeout_seconds": timeout,
        "expires_at": expires_at,
    }
    return payload


def parse_deferred_result(value: Any) -> Optional[DeferredResultSpec]:
    """Parse the reserved pending marker from a plugin result."""

    if not isinstance(value, Mapping) or DEFERRED_RESULT_KEY not in value:
        return None
    raw = value.get(DEFERRED_RESULT_KEY)
    if not isinstance(raw, Mapping):
        raise PluginApiError("Deferred result marker must be an object")
    token = str(raw.get("token") or "").strip()
    if not token or len(token) > 4096:
        raise PluginApiError("Deferred result token must contain 1-4096 characters")
    try:
        poll_after_ms = max(50, min(10_000, int(raw.get("poll_after_ms") or 1000)))
        timeout_seconds = max(
            0.1,
            min(3600.0, float(raw.get("timeout_seconds") or 300)),
        )
        expires_at = float(raw.get("expires_at") or (time.time() + timeout_seconds))
        if expires_at <= 0:
            raise ValueError("expires_at must be positive")
    except (TypeError, ValueError) as exc:
        raise PluginApiError("Deferred result timing values are invalid") from exc
    return DeferredResultSpec(token, poll_after_ms, timeout_seconds, expires_at)


def strip_deferred_result(value: Any) -> Any:
    """Remove host-private polling metadata before exposing a final result."""

    if not isinstance(value, Mapping):
        return value
    result = dict(value)
    result.pop(DEFERRED_RESULT_KEY, None)
    return result


def with_host_actions(
    result: Mapping[str, Any],
    actions: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...],
) -> Dict[str, Any]:
    """Attach permission-checked host actions to a structured tool result."""

    if not isinstance(result, Mapping):
        raise PluginApiError("Host actions require a mapping tool result")
    if not isinstance(actions, (list, tuple)) or len(actions) > 16:
        raise PluginApiError("Host actions must contain at most 16 entries")
    clean_actions = []
    for action in actions:
        if not isinstance(action, Mapping) or not str(action.get("service") or "").strip():
            raise PluginApiError("Each host action must declare a service")
        clean_actions.append(dict(action))
    output = dict(result)
    output[HOST_ACTIONS_KEY] = clean_actions
    return output


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


@dataclass(frozen=True)
class BackgroundServiceRegistration:
    name: str
    handler: Callable[..., Any]
    interval_seconds: float
    run_on_start: bool
    failure_policy: str

    def describe(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "interval_seconds": self.interval_seconds,
            "run_on_start": self.run_on_start,
            "failure_policy": self.failure_policy,
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
        self._deferred_poll_handler: Optional[Callable[..., Any]] = None
        self._deferred_cancel_handler: Optional[Callable[..., Any]] = None
        self._http_handler: Optional[Callable[..., Any]] = None
        self._background_services: Dict[str, BackgroundServiceRegistration] = {}
        self._background_tasks: Dict[str, asyncio.Task[Any]] = {}
        self._background_status: Dict[str, Dict[str, Any]] = {}

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

    def on_deferred_poll(
        self, handler: Callable[..., Any]
    ) -> Callable[..., Any]:
        """Register the plugin's short, non-blocking deferred poll handler."""

        if not callable(handler):
            raise PluginApiError("Deferred poll handler must be callable")
        if self._deferred_poll_handler is not None:
            raise PluginApiError("Only one deferred poll handler may be registered")
        self._deferred_poll_handler = handler
        return handler

    def on_deferred_cancel(
        self, handler: Callable[..., Any]
    ) -> Callable[..., Any]:
        """Register optional cleanup/finalization for timeout or cancellation."""

        if not callable(handler):
            raise PluginApiError("Deferred cancel handler must be callable")
        if self._deferred_cancel_handler is not None:
            raise PluginApiError("Only one deferred cancel handler may be registered")
        self._deferred_cancel_handler = handler
        return handler

    @property
    def supports_deferred_results(self) -> bool:
        return self._deferred_poll_handler is not None

    def on_http_request(
        self, handler: Callable[..., Any]
    ) -> Callable[..., Any]:
        """Register one isolated HTTP request handler for the plugin gateway."""

        if not callable(handler):
            raise PluginApiError("HTTP handler must be callable")
        if self._http_handler is not None:
            raise PluginApiError("Only one HTTP handler may be registered")
        self._http_handler = handler
        return handler

    @property
    def supports_http(self) -> bool:
        return self._http_handler is not None

    def register_background_service(
        self,
        name: str,
        handler: Callable[..., Any],
        *,
        interval_seconds: float = 60,
        run_on_start: bool = True,
        failure_policy: str = "restart",
    ) -> Callable[..., Any]:
        service_name = str(name or "").strip()
        if not _TOOL_NAME_RE.fullmatch(service_name):
            raise PluginApiError("Background service name is invalid")
        if service_name in self._background_services:
            raise PluginApiError(f"Duplicate background service: {service_name}")
        if not callable(handler):
            raise PluginApiError("Background service handler must be callable")
        policy = str(failure_policy or "restart").strip().lower()
        if policy not in {"restart", "stop"}:
            raise PluginApiError("Background service failure_policy must be restart or stop")
        registration = BackgroundServiceRegistration(
            name=service_name,
            handler=handler,
            interval_seconds=max(0.05, min(86_400.0, float(interval_seconds))),
            run_on_start=bool(run_on_start),
            failure_policy=policy,
        )
        self._background_services[service_name] = registration
        self._background_status[service_name] = {
            "name": service_name,
            "state": "registered",
            "runs": 0,
            "failures": 0,
            "last_error": "",
            "last_started_monotonic": 0.0,
            "last_finished_monotonic": 0.0,
        }
        return handler

    def background_service(
        self,
        name: Optional[str] = None,
        *,
        interval_seconds: float = 60,
        run_on_start: bool = True,
        failure_policy: str = "restart",
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorate(handler: Callable[..., Any]) -> Callable[..., Any]:
            self.register_background_service(
                name or handler.__name__,
                handler,
                interval_seconds=interval_seconds,
                run_on_start=run_on_start,
                failure_policy=failure_policy,
            )
            return handler

        return decorate

    def describe_background_services(self) -> list[Dict[str, Any]]:
        return [
            registration.describe()
            for _name, registration in sorted(self._background_services.items())
        ]

    async def _call_background_handler(
        self,
        registration: BackgroundServiceRegistration,
        context: Mapping[str, Any],
    ) -> Any:
        if inspect.iscoroutinefunction(registration.handler):
            return await registration.handler(dict(context))
        result = await asyncio.to_thread(registration.handler, dict(context))
        return await result if inspect.isawaitable(result) else result

    async def _run_background_service(
        self,
        registration: BackgroundServiceRegistration,
        context: Mapping[str, Any],
    ) -> None:
        status = self._background_status[registration.name]
        if not registration.run_on_start:
            await asyncio.sleep(registration.interval_seconds)
        while True:
            status["state"] = "running"
            status["last_started_monotonic"] = time.monotonic()
            try:
                await self._call_background_handler(registration, context)
                status["runs"] = int(status.get("runs") or 0) + 1
                status["last_error"] = ""
                status["state"] = "sleeping"
            except asyncio.CancelledError:
                status["state"] = "stopped"
                raise
            except Exception as exc:
                status["failures"] = int(status.get("failures") or 0) + 1
                status["last_error"] = f"{type(exc).__name__}: {exc}"[:2000]
                status["state"] = "failed"
                if registration.failure_policy == "stop":
                    return
            finally:
                status["last_finished_monotonic"] = time.monotonic()
            await asyncio.sleep(registration.interval_seconds)

    async def _start_background_services(self, context: Mapping[str, Any]) -> None:
        if not bool(context.get("background_services_enabled")):
            return
        for name, registration in self._background_services.items():
            task = self._background_tasks.get(name)
            if task is not None and not task.done():
                continue
            self._background_tasks[name] = asyncio.create_task(
                self._run_background_service(registration, dict(context)),
                name=f"plugin-service-{name}",
            )

    async def _stop_background_services(self) -> None:
        tasks = list(self._background_tasks.values())
        self._background_tasks.clear()
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def background_service_status(self) -> list[Dict[str, Any]]:
        return [dict(self._background_status[name]) for name in sorted(self._background_status)]

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

    async def invoke_tool(
        self,
        name: str,
        arguments: Optional[Mapping[str, Any]] = None,
        context: Optional[Mapping[str, Any]] = None,
    ) -> Any:
        registration = self._tools.get(str(name or ""))
        if registration is None:
            raise PluginApiError(f"Unknown plugin tool: {name}")
        kwargs = dict(arguments or {})
        token = _TOOL_CALL_CONTEXT.set(_tool_call_context(context))
        try:
            return await self._await_result(registration.handler(**kwargs))
        finally:
            _TOOL_CALL_CONTEXT.reset(token)

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

    async def poll_deferred(
        self,
        token: str,
        context: Optional[Mapping[str, Any]] = None,
    ) -> Any:
        handler = self._deferred_poll_handler
        if handler is None:
            raise PluginApiError("Plugin did not register a deferred poll handler")
        context_token = _TOOL_CALL_CONTEXT.set(_tool_call_context(context))
        try:
            return await self._await_result(
                handler(str(token or ""), dict(context or {}))
            )
        finally:
            _TOOL_CALL_CONTEXT.reset(context_token)

    async def cancel_deferred(
        self,
        token: str,
        reason: str,
        context: Optional[Mapping[str, Any]] = None,
    ) -> Any:
        handler = self._deferred_cancel_handler
        if handler is None:
            return None
        context_token = _TOOL_CALL_CONTEXT.set(_tool_call_context(context))
        try:
            return await self._await_result(
                handler(
                    str(token or ""),
                    str(reason or "cancelled"),
                    dict(context or {}),
                )
            )
        finally:
            _TOOL_CALL_CONTEXT.reset(context_token)

    async def handle_http(
        self,
        request: Mapping[str, Any],
        context: Optional[Mapping[str, Any]] = None,
    ) -> Any:
        handler = self._http_handler
        if handler is None:
            raise PluginApiError("Plugin did not register an HTTP handler")
        context_token = _TOOL_CALL_CONTEXT.set(_tool_call_context(context))
        try:
            return await self._await_result(
                handler(dict(request or {}), dict(context or {}))
            )
        finally:
            _TOOL_CALL_CONTEXT.reset(context_token)

    async def activate(self, context: Optional[Mapping[str, Any]] = None) -> None:
        activation_context = dict(context or {})
        for handler in self._activate_handlers:
            await self._await_result(handler(dict(activation_context)))
        await self._start_background_services(activation_context)

    async def deactivate(self, context: Optional[Mapping[str, Any]] = None) -> None:
        await self._stop_background_services()
        for handler in reversed(self._deactivate_handlers):
            await self._await_result(handler(dict(context or {})))


__all__ = [
    "DEFERRED_RESULT_KEY",
    "HOST_ACTIONS_KEY",
    "PLUGIN_API_VERSION",
    "BackgroundServiceRegistration",
    "CommandRegistration",
    "DeferredResultSpec",
    "HookRegistration",
    "Plugin",
    "PluginApiError",
    "ToolCallContext",
    "ToolRegistration",
    "current_tool_context",
    "deferred_result",
    "parse_deferred_result",
    "strip_deferred_result",
    "with_host_actions",
]
