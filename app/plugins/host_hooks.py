"""Bridge Plugin API v1 hook registrations into the host HookManager."""
from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

try:
    from hooks import (
        FAILURE_POLICIES,
        HOOK_DECISIONS,
        SUPPORTED_HOOK_EVENTS,
        CommandHookExecutor,
        CommandSpec,
        HookDefinition,
        HookExecutionResult,
    )
except ImportError:  # pragma: no cover - package import style
    from ..hooks import (
        FAILURE_POLICIES,
        HOOK_DECISIONS,
        SUPPORTED_HOOK_EVENTS,
        CommandHookExecutor,
        CommandSpec,
        HookDefinition,
        HookExecutionResult,
    )

from .models import PluginDefinition
from .runtime import PluginRuntimeRegistry

SUPPORTED_HOOK_EVENT_SET = frozenset(SUPPORTED_HOOK_EVENTS)


def runtime_hook_definitions(
    registry: PluginRuntimeRegistry,
    plugins: Sequence[PluginDefinition],
) -> tuple[HookDefinition, ...]:
    """Convert runtime descriptions into ordinary ordered HookDefinitions."""

    roots = {plugin.plugin_id: plugin.root for plugin in plugins}
    definitions = []
    for order, row in enumerate(registry.hook_descriptions(plugins), start=1_000_000):
        event = str(row.get("event") or "")
        failure_policy = str(row.get("failure_policy") or "warn")
        if event not in SUPPORTED_HOOK_EVENT_SET:
            raise ValueError(
                f"Plugin {row.get('plugin_id')!r} registered unsupported hook event {event!r}"
            )
        if failure_policy not in FAILURE_POLICIES:
            raise ValueError(
                f"Plugin {row.get('plugin_id')!r} registered unsupported "
                f"failure policy {failure_policy!r}"
            )
        plugin_id = str(row.get("plugin_id") or "")
        definitions.append(
            HookDefinition(
                id=str(row.get("id") or ""),
                event=event,
                command=CommandSpec(
                    timeout_seconds=float(row.get("timeout_seconds") or 30)
                ),
                matcher=str(row.get("matcher") or ""),
                handler_type="plugin",
                failure_policy=failure_policy,
                priority=int(row.get("priority", 100)),
                source_id=f"plugin-runtime:{plugin_id}",
                source_root=Path(roots.get(plugin_id) or ".").resolve(),
                plugin_id=plugin_id,
                order=order,
                handler_ref=str(row.get("id") or ""),
                plugin_signature=str(row.get("plugin_signature") or ""),
            )
        )
    return tuple(definitions)


class PluginAwareHookExecutor:
    """Route declarative command hooks and code hooks through one dispatcher."""

    def __init__(
        self,
        project_root: Any,
        registry: PluginRuntimeRegistry,
        plugins_provider: Callable[[], Sequence[PluginDefinition]],
    ) -> None:
        self.command_executor = CommandHookExecutor(project_root)
        self.registry = registry
        self.plugins_provider = plugins_provider

    @staticmethod
    def _failure(
        definition: HookDefinition,
        started: float,
        error: str,
    ) -> HookExecutionResult:
        return HookExecutionResult(
            hook_id=definition.id,
            event=definition.event,
            source_id=definition.source_id,
            plugin_id=definition.plugin_id,
            success=False,
            outcome="failed",
            decision="continue",
            duration_ms=int((time.perf_counter() - started) * 1000),
            error=str(error),
            failure_policy=definition.failure_policy,
        )

    async def execute(
        self,
        definition: HookDefinition,
        payload: Mapping[str, Any],
    ) -> HookExecutionResult:
        if definition.handler_type != "plugin":
            return await self.command_executor.execute(definition, payload)
        started = time.perf_counter()
        try:
            result = await asyncio.to_thread(
                self.registry.invoke_hook,
                str(definition.plugin_id or ""),
                definition.plugin_signature,
                definition.event,
                definition.handler_ref or definition.id,
                dict(payload),
                tuple(self.plugins_provider()),
            )
            if result is None:
                result = {}
            if not isinstance(result, Mapping):
                raise ValueError("Plugin hook result must be a JSON object")
            decision = str(result.get("decision") or "continue").strip().lower()
            if decision not in HOOK_DECISIONS:
                raise ValueError(f"Plugin hook returned invalid decision: {decision}")
            updated = result.get("updated_input")
            if updated is not None and not isinstance(updated, Mapping):
                raise ValueError("Plugin hook updated_input must be an object")
            return HookExecutionResult(
                hook_id=definition.id,
                event=definition.event,
                source_id=definition.source_id,
                plugin_id=definition.plugin_id,
                success=True,
                outcome="success",
                decision=decision,
                reason=str(result.get("reason") or ""),
                updated_input=dict(updated) if isinstance(updated, Mapping) else None,
                additional_context=str(result.get("additional_context") or ""),
                user_message=str(result.get("user_message") or ""),
                duration_ms=int((time.perf_counter() - started) * 1000),
                failure_policy=definition.failure_policy,
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            return self._failure(definition, started, str(exc))


__all__ = ["PluginAwareHookExecutor", "runtime_hook_definitions"]
