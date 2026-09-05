"""Registration and invocation contract for host-provided model tools.

Host capabilities register here instead of adding tool-name branches to the
ReAct loop.  The loop remains responsible for authorization and Hooks; an
invoker receives only the trusted per-call context after those gates pass.
"""
from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Awaitable, Callable, Mapping, Optional

from tool_registry import ToolOutcome
from tool_execution_policy import ToolExecutionPolicy


HostToolInvoker = Callable[
    ["HostToolInvocationContext", Mapping[str, Any]],
    ToolOutcome | Awaitable[ToolOutcome],
]
BeforeHookResolver = Callable[[Mapping[str, Any]], tuple[str, ...]]
AvailabilityResolver = Callable[[], bool]


@dataclass(frozen=True)
class HostToolInvocationContext:
    """Trusted host-owned values that are never exposed as model arguments."""

    session_id: str
    run_id: str = ""
    tool_call_id: str = ""
    state: dict[str, Any] = field(default_factory=dict, repr=False)
    emit_event: Optional[Callable[[Mapping[str, Any]], Awaitable[None]]] = field(
        default=None, repr=False
    )
    services: Mapping[str, Any] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "session_id", str(self.session_id or "").strip())
        object.__setattr__(self, "run_id", str(self.run_id or "").strip())
        object.__setattr__(self, "tool_call_id", str(self.tool_call_id or "").strip())
        object.__setattr__(self, "services", MappingProxyType(dict(self.services or {})))
        if not self.session_id:
            raise ValueError("HostToolInvocationContext requires session_id")

    async def publish(self, event: Mapping[str, Any]) -> None:
        if self.emit_event is not None:
            await self.emit_event(dict(event))

    def service(self, name: str) -> Any:
        try:
            return self.services[name]
        except KeyError as exc:
            raise RuntimeError(f"Host tool service is unavailable: {name}") from exc


class HostToolInvokerRegistry:
    """Process-wide registry for host tool implementations."""

    def __init__(self) -> None:
        self._invokers: dict[str, HostToolInvoker] = {}
        self._owners: dict[str, str] = {}
        self._emit_pending: dict[str, bool] = {}
        self._before_hooks: dict[str, BeforeHookResolver] = {}
        self._effects: dict[str, str] = {}
        self._policies: dict[str, ToolExecutionPolicy] = {}
        self._availability: dict[str, AvailabilityResolver] = {}
        self._generation = 0

    def register(
        self,
        invoker_id: str,
        invoker: HostToolInvoker,
        *,
        replace: bool = False,
        emit_pending: bool = True,
        before_hooks: Optional[BeforeHookResolver] = None,
        effect: str = "control",
        policy: Optional[ToolExecutionPolicy] = None,
        enabled: Optional[AvailabilityResolver] = None,
        owner: str = "core.services",
    ) -> str:
        key = str(invoker_id or "").strip()
        if not key:
            raise ValueError("Host tool invoker_id cannot be empty")
        if not callable(invoker):
            raise TypeError("Host tool invoker must be callable")
        owner_str = str(owner or "core.services").strip()
        effect_str = str(effect or "").strip().lower()
        new_policy = policy or ToolExecutionPolicy(effect=effect_str)
        replacing = key in self._invokers
        if replacing and not replace:
            raise ValueError(f"Host tool invoker is already registered: {key}")
        if replacing and self._is_restatement(
            key,
            owner_str=owner_str,
            emit_pending=bool(emit_pending),
            effect_str=effect_str,
            policy=new_policy,
            has_before_hooks=before_hooks is not None,
        ):
            # Plugins re-declare their host tools on every catalog build.
            # A restatement refreshes the binding but must not bump the
            # generation, or every build invalidates the catalog for nothing.
            self._invokers[key] = invoker
            self._availability[key] = enabled or (lambda: True)
            return key
        self._invokers[key] = invoker
        self._owners[key] = owner_str
        self._emit_pending[key] = bool(emit_pending)
        self._effects[key] = effect_str
        self._policies[key] = new_policy
        self._availability[key] = enabled or (lambda: True)
        if before_hooks is not None:
            self._before_hooks[key] = before_hooks
        elif replacing:
            self._before_hooks.pop(key, None)
        self._generation += 1
        return key

    def _is_restatement(
        self,
        key: str,
        *,
        owner_str: str,
        emit_pending: bool,
        effect_str: str,
        policy: ToolExecutionPolicy,
        has_before_hooks: bool,
    ) -> bool:
        return (
            self._owners.get(key) == owner_str
            and self._emit_pending.get(key, True) == emit_pending
            and self._effects.get(key, "control") == effect_str
            and self._policies.get(key) == policy
            and (key in self._before_hooks) == has_before_hooks
        )

    def catalog_revision(self) -> tuple[int, tuple[tuple[str, bool], ...]]:
        """Return a cheap revision including dynamic availability switches."""
        availability = tuple(
            (name, self.is_enabled(name)) for name in sorted(self._invokers)
        )
        return self._generation, availability

    def resolve(self, invoker_id: str) -> Optional[HostToolInvoker]:
        return self._invokers.get(str(invoker_id or "").strip())

    def has(self, invoker_id: str) -> bool:
        return self.resolve(invoker_id) is not None

    def is_enabled(self, invoker_id: str) -> bool:
        resolver = self._availability.get(str(invoker_id or "").strip())
        if resolver is None:
            return False
        try:
            return bool(resolver())
        except Exception:
            return False

    def owner(self, invoker_id: str) -> str:
        return self._owners.get(str(invoker_id or "").strip(), "core.services")

    def emits_pending(self, invoker_id: str) -> bool:
        return self._emit_pending.get(str(invoker_id or "").strip(), True)

    def effect(self, invoker_id: str) -> str:
        return self._effects.get(str(invoker_id or "").strip(), "")

    def policy(self, invoker_id: str) -> ToolExecutionPolicy:
        return self._policies.get(
            str(invoker_id or "").strip(), ToolExecutionPolicy()
        )

    def before_hook_events(
        self, invoker_id: str, arguments: Mapping[str, Any]
    ) -> tuple[str, ...]:
        resolver = self._before_hooks.get(str(invoker_id or "").strip())
        if resolver is None:
            return ()
        return tuple(str(item) for item in resolver(dict(arguments or {})) if str(item))

    async def invoke(
        self,
        invoker_id: str,
        context: HostToolInvocationContext,
        arguments: Mapping[str, Any],
    ) -> ToolOutcome:
        invoker = self.resolve(invoker_id)
        if invoker is None:
            return ToolOutcome.failed(
                "host_invoker_unavailable",
                f"Host tool invoker is unavailable: {invoker_id}",
            )
        if not self.is_enabled(invoker_id):
            return ToolOutcome.failed(
                "host_invoker_disabled",
                f"Host tool invoker is disabled: {invoker_id}",
            )
        try:
            pending = invoker(context, dict(arguments or {}))
            outcome = await pending if inspect.isawaitable(pending) else pending
        except Exception as exc:
            should_propagate = context.services.get("should_propagate_exception")
            if callable(should_propagate) and should_propagate(exc):
                raise
            return ToolOutcome.failed("host_invocation_error", str(exc))
        if not isinstance(outcome, ToolOutcome):
            return ToolOutcome.failed(
                "invalid_host_outcome",
                f"Host tool invoker {invoker_id!r} returned an invalid outcome",
            )
        return outcome


host_tool_invokers = HostToolInvokerRegistry()


__all__ = [
    "HostToolInvocationContext",
    "HostToolInvoker",
    "HostToolInvokerRegistry",
    "host_tool_invokers",
]
