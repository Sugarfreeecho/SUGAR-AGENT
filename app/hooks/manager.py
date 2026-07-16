"""Hook registry and event dispatcher."""
from __future__ import annotations

import asyncio
import contextvars
import threading
import time
import weakref
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .config import SourceLike, load_hook_sources
from .executor import CommandHookExecutor
from .matcher import hook_matches
from .models import (
    SUPPORTED_HOOK_EVENT_SET,
    HookDefinition,
    HookDispatchResult,
    HookExecutionResult,
    hooks_enabled,
)


_ACTIVE_DISPATCHES: contextvars.ContextVar[frozenset] = contextvars.ContextVar(
    "myagent_active_hook_dispatches",
    default=frozenset(),
)
_DECISION_STRENGTH = {"continue": 0, "allow": 1, "ask": 2, "pause": 3, "deny": 4}


class HookManager:
    """Load, register, and safely dispatch MyAgent hooks.

    Dispatches for the same event are serialized, while different event names
    may run concurrently. A context-local guard prevents a hook callback from
    recursively dispatching the same event and deadlocking itself.
    """

    def __init__(
        self,
        project_root: Any,
        *,
        config_path: Optional[Any] = None,
        plugin_sources: Optional[Sequence[SourceLike]] = None,
        plugin_hook_sources: Optional[Sequence[SourceLike]] = None,
        include_project: bool = True,
        enabled: Optional[bool] = None,
        strict_config: bool = False,
        executor: Optional[Any] = None,
        definitions: Optional[Iterable[HookDefinition]] = None,
    ) -> None:
        self.project_root = Path(project_root).expanduser().resolve()
        self.config_path = config_path
        self.include_project = bool(include_project)
        self._enabled_override = enabled
        self._strict_config = bool(strict_config)
        combined_sources = list(plugin_sources or ())
        combined_sources.extend(plugin_hook_sources or ())
        self._plugin_sources: Tuple[SourceLike, ...] = tuple(combined_sources)
        self.executor = executor or CommandHookExecutor(self.project_root)
        self._definitions: Tuple[HookDefinition, ...] = ()
        self._config_errors: Tuple[str, ...] = ()
        self._loaded_sources: Tuple[str, ...] = ()
        self._event_locks: "weakref.WeakKeyDictionary[Any, Dict[str, asyncio.Lock]]" = weakref.WeakKeyDictionary()
        self._lock_guard = threading.Lock()
        if definitions is None:
            self.reload()
        else:
            self.replace_definitions(definitions)

    @property
    def enabled(self) -> bool:
        return hooks_enabled() if self._enabled_override is None else bool(self._enabled_override)

    @property
    def definitions(self) -> Tuple[HookDefinition, ...]:
        return self._definitions

    @property
    def config_errors(self) -> Tuple[str, ...]:
        return self._config_errors

    @property
    def loaded_sources(self) -> Tuple[str, ...]:
        return self._loaded_sources

    def reload(self) -> Tuple[HookDefinition, ...]:
        loaded = load_hook_sources(
            self.project_root,
            config_path=self.config_path,
            plugin_sources=self._plugin_sources,
            include_project=self.include_project,
            strict=self._strict_config,
        )
        self._definitions = loaded.definitions
        self._config_errors = loaded.errors
        self._loaded_sources = loaded.loaded_sources
        return self._definitions

    def set_plugin_sources(self, sources: Sequence[SourceLike], *, reload: bool = True) -> None:
        self._plugin_sources = tuple(sources)
        if reload:
            self.reload()

    def replace_definitions(self, definitions: Iterable[HookDefinition]) -> None:
        checked: List[HookDefinition] = []
        for definition in definitions:
            if not isinstance(definition, HookDefinition):
                raise TypeError("definitions must contain HookDefinition instances")
            if definition.event not in SUPPORTED_HOOK_EVENT_SET:
                raise ValueError(f"Unsupported hook event: {definition.event}")
            checked.append(definition)
        checked.sort(key=lambda item: (item.priority, item.order, item.source_id, item.id))
        self._definitions = tuple(checked)
        self._config_errors = ()
        self._loaded_sources = tuple(dict.fromkeys(item.source_id for item in checked))

    def register(self, definition: HookDefinition) -> None:
        self.replace_definitions((*self._definitions, definition))

    def hooks_for(self, event: str) -> Tuple[HookDefinition, ...]:
        self._validate_event(event)
        return tuple(item for item in self._definitions if item.event == event)

    @staticmethod
    def _validate_event(event: str) -> None:
        if event not in SUPPORTED_HOOK_EVENT_SET:
            raise ValueError(f"Unsupported hook event {event!r}.")

    def _event_lock(self, event: str) -> asyncio.Lock:
        loop = asyncio.get_running_loop()
        with self._lock_guard:
            per_loop = self._event_locks.get(loop)
            if per_loop is None:
                per_loop = {}
                self._event_locks[loop] = per_loop
            lock = per_loop.get(event)
            if lock is None:
                lock = asyncio.Lock()
                per_loop[event] = lock
            return lock

    async def dispatch(
        self,
        event: str,
        payload: Optional[Mapping[str, Any]] = None,
    ) -> HookDispatchResult:
        """Run matching hooks and return their aggregate, structured decision."""

        self._validate_event(event)
        started = time.perf_counter()
        if not self.enabled:
            return HookDispatchResult(
                event=event,
                enabled=False,
                skipped=True,
                skip_reason="disabled",
                config_errors=self._config_errors,
            )
        active_key = (id(self), event)
        active = _ACTIVE_DISPATCHES.get()
        if active_key in active:
            return HookDispatchResult(
                event=event,
                skipped=True,
                skip_reason="reentrant",
                config_errors=self._config_errors,
            )
        token = _ACTIVE_DISPATCHES.set(active | {active_key})
        try:
            async with self._event_lock(event):
                return await self._dispatch_locked(event, payload or {}, started)
        finally:
            _ACTIVE_DISPATCHES.reset(token)

    async def _dispatch_locked(
        self,
        event: str,
        payload: Mapping[str, Any],
        started: float,
    ) -> HookDispatchResult:
        current_payload: Dict[str, Any] = dict(payload)
        current_payload["event"] = event
        current_payload.setdefault("project_root", str(self.project_root))
        raw_input = current_payload.get("tool_input")
        input_field = "tool_input"
        if not isinstance(raw_input, Mapping):
            raw_input = current_payload.get("input")
            input_field = "input"
        original_input = dict(raw_input) if isinstance(raw_input, Mapping) else None
        current_input = dict(original_input) if original_input is not None else None

        default_decision = "allow" if event == "PreToolUse" else "continue"
        decision = default_decision
        matched = 0
        executed = 0
        results: List[HookExecutionResult] = []
        warnings: List[str] = []
        contexts: List[str] = []
        messages: List[str] = []
        seen: set = set()
        definitions = self.hooks_for(event)
        for definition in definitions:
            unique_key = (definition.source_id, definition.plugin_id, definition.id)
            if unique_key in seen:
                warnings.append(f"Duplicate hook registration skipped: {definition.source_id}/{definition.id}")
                continue
            seen.add(unique_key)
            try:
                is_match = hook_matches(definition.matcher, current_payload)
            except Exception as exc:
                result = HookExecutionResult(
                    hook_id=definition.id,
                    event=event,
                    source_id=definition.source_id,
                    plugin_id=definition.plugin_id,
                    success=False,
                    outcome="failed",
                    error=f"Matcher failed: {exc}",
                    failure_policy=definition.failure_policy,
                )
                result, warning = self._apply_failure_policy(result)
                results.append(result)
                executed += 1
                if warning:
                    warnings.append(warning)
                decision = self._stronger_decision(decision, result.decision)
                if decision in {"deny", "pause"}:
                    break
                continue
            if not is_match:
                continue
            matched += 1
            call_payload = dict(current_payload)
            call_payload["hook"] = {
                "id": definition.id,
                "source_id": definition.source_id,
                "plugin_id": definition.plugin_id,
            }
            result = await self.executor.execute(definition, call_payload)
            executed += 1
            warning = ""
            if not result.success:
                result, warning = self._apply_failure_policy(result)
            results.append(result)
            if warning:
                warnings.append(warning)
            if result.updated_input is not None:
                current_input = dict(result.updated_input)
                current_payload[input_field] = current_input
                if input_field == "tool_input" and "input" in current_payload:
                    current_payload["input"] = current_input
            if result.additional_context:
                contexts.append(result.additional_context)
            if result.user_message:
                messages.append(result.user_message)
            decision = self._stronger_decision(decision, result.decision)
            if decision in {"deny", "pause"}:
                break

        return HookDispatchResult(
            event=event,
            enabled=True,
            decision=decision,
            matched_hooks=matched,
            executed_hooks=executed,
            input_modified=current_input != original_input,
            original_input=original_input,
            updated_input=current_input,
            additional_context="\n".join(contexts),
            user_messages=tuple(messages),
            warnings=tuple(warnings),
            results=tuple(results),
            duration_ms=int((time.perf_counter() - started) * 1000),
            config_errors=self._config_errors,
        )

    @staticmethod
    def _stronger_decision(current: str, candidate: str) -> str:
        return candidate if _DECISION_STRENGTH.get(candidate, 0) > _DECISION_STRENGTH.get(current, 0) else current

    @staticmethod
    def _apply_failure_policy(result: HookExecutionResult) -> Tuple[HookExecutionResult, str]:
        message = f"Hook {result.source_id}/{result.hook_id} failed: {result.error or result.outcome}"
        if result.failure_policy == "ignore":
            return replace(result, outcome="ignored", decision="continue"), ""
        if result.failure_policy == "block":
            return replace(result, outcome="blocked", decision="deny", reason=result.error), message
        if result.failure_policy == "pause":
            return replace(result, outcome="paused", decision="pause", reason=result.error), message
        return replace(result, outcome="warning", decision="continue"), message

    def dispatch_sync(
        self,
        event: str,
        payload: Optional[Mapping[str, Any]] = None,
    ) -> HookDispatchResult:
        """Synchronous convenience wrapper for non-async integration points."""

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.dispatch(event, payload))
        raise RuntimeError("dispatch_sync cannot be used from a running event loop; await dispatch instead.")
