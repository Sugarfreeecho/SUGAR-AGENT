"""Host integration for Hooks, declarative resources, and Plugin API runtimes.

Executable plugin entrypoints are only loaded in isolated worker processes.
This module supplies one process-wide plugin registry plus one Hook manager per
asyncio event loop, so the main loop and its worker loop do not share loop-bound
locks.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shlex
import threading
import time
import weakref
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional, Tuple

from myagent_plugin_sdk import parse_deferred_result, strip_deferred_result

try:  # Production launches with app/ on sys.path; package imports use the fallback.
    from hooks import HookDispatchResult, HookManager, HookSource, hooks_enabled
    from plugins import (
        PluginLoadResult,
        PluginManager,
        PluginReloadResult,
        get_plugin_manager,
        get_plugin_runtime_registry,
        plugins_enabled,
    )
except ImportError:  # pragma: no cover - import style depends on the launcher
    from .hooks import HookDispatchResult, HookManager, HookSource, hooks_enabled
    from .plugins import (
        PluginLoadResult,
        PluginManager,
        PluginReloadResult,
        get_plugin_manager,
        get_plugin_runtime_registry,
        plugins_enabled,
    )

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 1.0
_lock = threading.RLock()
_plugin_cache: Optional[Tuple[float, tuple[Any, ...], PluginLoadResult]] = None
_extension_catalog_generation = 0
_hook_managers: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, tuple[str, HookManager]]" = (
    weakref.WeakKeyDictionary()
)


def _project_root() -> Path:
    from agent_harness import WORK_DIR

    return Path(WORK_DIR).expanduser().resolve()


def _bundled_plugins_root() -> Path:
    return Path(__file__).resolve().parents[1] / "plugins"


def _plugin_installer():
    """Keep lifecycle writes in a user/configured root, never bundled source."""

    try:
        from plugins import PluginInstaller
    except ImportError:  # pragma: no cover - package import style
        from .plugins import PluginInstaller

    discovery_dirs = tuple(plugin_manager().discovery_dirs)
    bundled = _bundled_plugins_root().resolve()
    writable = next(
        (
            path
            for path in reversed(discovery_dirs)
            if Path(path).expanduser().resolve() != bundled
        ),
        discovery_dirs[0],
    )
    return PluginInstaller(discovery_dirs, install_root=writable)


def _is_bundled_system_plugin(plugin: Any) -> bool:
    """Hide only host-shipped system plugins, never a user plugin by declaration alone."""
    if not bool(getattr(plugin, "system_builtin", False)):
        return False
    if str(getattr(plugin, "source_format", "") or "").strip() != "native":
        return False
    try:
        Path(plugin.root).resolve().relative_to(_bundled_plugins_root().resolve())
    except (OSError, RuntimeError, ValueError):
        return False
    return True


def hooks_config_path() -> Path:
    configured = str(os.getenv("HOOKS_PATH") or os.getenv("HOOKS_CONFIG_PATH") or "").strip()
    if configured:
        path = Path(configured).expanduser()
        return (path if path.is_absolute() else _project_root() / path).resolve()
    return (_project_root() / "hooks.json").resolve()


def plugin_manager() -> PluginManager:
    return get_plugin_manager()


def load_plugins(*, force: bool = False) -> PluginLoadResult:
    """Return enabled plugin resources with a short hot-path cache."""

    global _plugin_cache
    now = time.monotonic()
    manager = plugin_manager()
    cache_key = (
        id(manager),
        plugins_enabled(),
        tuple(str(path) for path in manager.discovery_dirs),
        str(manager.state.path),
    )
    with _lock:
        if (
            not force
            and _plugin_cache
            and _plugin_cache[1] == cache_key
            and now - _plugin_cache[0] <= _CACHE_TTL_SECONDS
        ):
            return _plugin_cache[2]
        loaded = manager.load_enabled()
        _plugin_cache = (now, cache_key, loaded)
        return loaded


def plugin_skill_directories() -> Mapping[str, Path]:
    return dict(load_plugins().skill_directories)


def plugin_mcp_servers() -> Mapping[str, Mapping[str, Any]]:
    return dict(load_plugins().mcp_servers)


def plugin_instruction_resources() -> Mapping[str, Tuple[str, Path]]:
    """Expose declarative Agent/Prompt files through the host instruction registry."""

    loaded = load_plugins()
    out: Dict[str, Tuple[str, Path]] = {}
    out.update(
        {str(name): ("agent", Path(path)) for name, path in loaded.agent_directories.items()}
    )
    out.update(
        {str(name): ("prompt", Path(path)) for name, path in loaded.prompt_directories.items()}
    )
    return out


async def plugin_tool_definitions() -> list[Dict[str, Any]]:
    """Describe tools registered by enabled Plugin API v1 runtimes."""

    loaded = load_plugins()
    registry = get_plugin_runtime_registry()
    definitions = await asyncio.to_thread(registry.tool_definitions, loaded.plugins)
    for error in registry.errors:
        logger.warning("Plugin runtime registration failed: %s", error)
    return definitions


def bundled_host_tool_definitions(
    *, session_meta: Optional[Mapping[str, Any]] = None
) -> list[Dict[str, Any]]:
    """Describe trusted bundled tools without exposing host trust to manifests."""

    from plugins.host import bundled_host_tool_definitions as describe

    return describe(load_plugins().plugins, session_meta=session_meta)


def activate_bundled_provider_extensions(registry: Any) -> None:
    from plugins.host import activate_bundled_provider_extensions as activate

    activate(load_plugins().plugins, registry)


def activate_bundled_search_provider_extensions(registry: Any) -> None:
    from plugins.host import activate_bundled_provider_extensions as activate

    activate(
        load_plugins().plugins,
        registry,
        registration_method="register_search_providers",
    )


async def plugin_tool_contracts() -> Dict[str, Dict[str, Any]]:
    """Return host-only execution contracts for the current plugin catalog."""

    registry = get_plugin_runtime_registry()
    return await asyncio.to_thread(registry.current_tool_contracts)


async def invoke_plugin_tool(
    function_name: str,
    arguments: Optional[Mapping[str, Any]] = None,
    *,
    work_dir: str = "",
    require_worktree_isolation: bool = False,
    session_id: str = "",
    run_id: str = "",
    cancellation_id: str = "",
    should_cancel: Optional[Callable[[], bool]] = None,
    publish_event: Optional[Callable[[Mapping[str, Any]], Any]] = None,
) -> Any:
    """Invoke one code-plugin tool through its worker process."""

    loaded = load_plugins(force=True)
    registry = get_plugin_runtime_registry()
    call_arguments = dict(arguments or {})
    # Session identity is host-owned metadata, never a model-controlled tool
    # argument. Strip legacy/spoofed values and pass the trusted value through
    # the worker's separate invocation context.
    for reserved_name in (
        "_session_id",
        "session_id",
        "run_id",
        "plugin_id",
        "workspace_root",
        "plugin_data_dir",
        "plugin_cache_dir",
        "plugin_temp_dir",
        "cancellation_id",
    ):
        call_arguments.pop(reserved_name, None)
    contract = await asyncio.to_thread(
        registry.tool_contract,
        function_name,
        loaded.plugins,
    )
    plugin_id = str(contract.get("plugin_id") or "").strip()
    plugin_definition = next(
        (
            plugin
            for plugin in loaded.plugins
            if str(getattr(plugin, "plugin_id", "") or "") == plugin_id
        ),
        None,
    )

    def _owned_session_state() -> Dict[str, Any]:
        """Read only this plugin's namespaces for the trusted session."""

        if not session_id or not plugin_id:
            return {}
        try:
            from agent_harness import session_manager
            from runtime_v2.event_log import SessionEventLog
            from runtime_v2.projector import RuntimeProjector
            from runtime_v2.snapshot_store import SnapshotStore

            root = session_manager.repository.sessions_dir
            resolver = getattr(session_manager, "_resolve_session_path", None)
            snapshot = SnapshotStore(root, path_resolver=resolver).read_consistent(
                str(session_id),
                SessionEventLog(root, path_resolver=resolver),
                RuntimeProjector(),
            )
            extensions = snapshot.get("extensions") if isinstance(snapshot, Mapping) else None
            state = extensions.get(plugin_id) if isinstance(extensions, Mapping) else None
            if not isinstance(state, Mapping):
                return {}
            return json.loads(json.dumps(state, ensure_ascii=False, allow_nan=False))
        except Exception:
            logger.debug(
                "Plugin session-state context unavailable for %s/%s",
                plugin_id,
                session_id,
                exc_info=True,
            )
            return {}

    async def _apply_host_actions(value: Any) -> Any:
        if not isinstance(value, Mapping) or "_host_actions" not in value:
            return value
        if plugin_definition is None:
            raise ValueError("Plugin host action owner could not be resolved")
        from plugin_host_services import execute_host_actions

        clean = dict(value)
        actions = clean.pop("_host_actions", None)
        results = execute_host_actions(
            plugin_definition,
            actions,
            trusted_session_id=str(session_id or "").strip(),
            trusted_run_id=str(run_id or "").strip(),
        )
        if results:
            clean["_host_action_results"] = results
        if publish_event is not None:
            for item in results:
                service = str(item.get("service") or "")
                event_state = item.get("state")
                if not isinstance(event_state, Mapping):
                    continue
                if service == "session_events.append":
                    event = {
                        "type": "extension_event",
                        "plugin_id": str(event_state.get("plugin_id") or plugin_id),
                        "event_name": str(event_state.get("event_name") or ""),
                        "data": event_state.get("data"),
                        "created_at": event_state.get("timestamp"),
                        "runtime_seq": event_state.get("seq"),
                        "_runtime_v2_committed": True,
                    }
                elif service in {
                    "session_state.compare_and_set",
                    "session_state.set_latest",
                    "session_state.patch",
                }:
                    event = {
                        "type": "extension_state_changed",
                        "plugin_id": str(item.get("plugin_id") or plugin_id),
                        "namespace": str(item.get("namespace") or "default"),
                        "revision": int(event_state.get("revision") or 0),
                        "_runtime_v2_committed": True,
                    }
                else:
                    continue
                try:
                    pending = publish_event(event)
                    if asyncio.iscoroutine(pending):
                        await pending
                except Exception:
                    logger.warning(
                        "Plugin extension event live publication failed for %s",
                        plugin_id,
                        exc_info=True,
                    )
        return clean
    if require_worktree_isolation:
        if not contract.get("declared") or not contract.get("effect"):
            raise ValueError(
                f"Plugin tool {function_name!r} is blocked in a managed worktree "
                "because it does not declare an effect/resource isolation contract."
            )
        effect = str(contract.get("effect") or "")
        if effect == "workspace_write":
            if not contract.get("worktree_compatible"):
                raise ValueError(
                    f"Plugin tool {function_name!r} declares workspace writes but "
                    "does not declare worktree compatibility."
                )
            root_argument = str(contract.get("workspace_root_argument") or "")
            if not root_argument:
                raise ValueError(
                    f"Plugin tool {function_name!r} requires a "
                    "workspace_root_argument for worktree isolation."
                )
            call_arguments[root_argument] = str(Path(work_dir).resolve())
        elif effect not in {"read", "external_write"}:
            raise ValueError(
                f"Plugin tool {function_name!r} has unsupported effect "
                f"{effect!r} for worktree isolation."
            )
        root = Path(work_dir).resolve()
        for argument_name in contract.get("path_arguments") or []:
            raw_path = str(call_arguments.get(argument_name) or "").strip()
            if not raw_path:
                continue
            candidate = Path(raw_path)
            candidate = (
                candidate.resolve()
                if candidate.is_absolute()
                else (root / candidate).resolve()
            )
            try:
                candidate.relative_to(root)
            except ValueError as exc:
                raise ValueError(
                    f"Plugin argument {argument_name!r} escapes the managed worktree."
                ) from exc
            call_arguments[argument_name] = str(candidate)
    trusted_context = {
        "session_id": str(session_id or ""),
        "run_id": str(run_id or ""),
        "workspace_root": str(work_dir or ""),
        "cancellation_id": str(cancellation_id or ""),
        "session_state": await asyncio.to_thread(_owned_session_state),
    }
    result = await asyncio.to_thread(
        registry.invoke,
        function_name,
        call_arguments,
        loaded.plugins,
        context=trusted_context,
    )
    spec = parse_deferred_result(result)
    if spec is None:
        return await _apply_host_actions(result)

    # The opaque token is bound to this exact tool call and trusted context.
    # A poll response may tune the next interval but cannot rotate the token or
    # extend the original deadline indefinitely.
    opaque_token = spec.token
    remaining_lifetime = max(
        0.0,
        min(spec.timeout_seconds, spec.expires_at - time.time()),
    )
    deadline = time.monotonic() + remaining_lifetime
    latest = result

    async def _cancel(reason: str) -> Any:
        try:
            cancelled = await asyncio.to_thread(
                registry.cancel_deferred,
                function_name,
                opaque_token,
                reason,
                loaded.plugins,
                context=trusted_context,
            )
        except Exception:
            logger.warning(
                "Deferred plugin cleanup failed for %s",
                function_name,
                exc_info=True,
            )
            cancelled = None
        if cancelled is not None:
            return await _apply_host_actions(strip_deferred_result(cancelled))
        fallback = strip_deferred_result(latest)
        if isinstance(fallback, Mapping):
            fallback = dict(fallback)
            # Pending host actions are not implicitly authorized by a timeout
            # fallback. A plugin must return them explicitly from its cancel
            # handler if cancellation itself requires a host-side action.
            fallback.pop("_host_actions", None)
            fallback["wait_for_opponent"] = False
            fallback["timeout" if reason == "timeout" else "cancelled"] = True
            fallback.setdefault(
                "msg",
                "Deferred plugin result timed out."
                if reason == "timeout"
                else "Deferred plugin result was cancelled.",
            )
            return fallback
        return {
            "ok": False,
            "timeout" if reason == "timeout" else "cancelled": True,
        }

    try:
        while True:
            try:
                cancellation_requested = bool(should_cancel and should_cancel())
            except Exception:
                logger.debug("Deferred cancellation check failed", exc_info=True)
                cancellation_requested = False
            if cancellation_requested:
                return await _cancel("cancelled")

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return await _cancel("timeout")
            wait_seconds = min(spec.poll_after_ms / 1000.0, remaining)
            # Keep cancellation responsive even when a plugin chooses a long
            # polling interval.
            waited = 0.0
            while waited < wait_seconds:
                interval = min(0.25, wait_seconds - waited)
                await asyncio.sleep(interval)
                waited += interval
                try:
                    if should_cancel and should_cancel():
                        return await _cancel("cancelled")
                except Exception:
                    logger.debug("Deferred cancellation check failed", exc_info=True)

            if time.monotonic() >= deadline:
                return await _cancel("timeout")

            latest = await asyncio.to_thread(
                registry.poll_deferred,
                function_name,
                opaque_token,
                loaded.plugins,
                context=trusted_context,
            )
            next_spec = parse_deferred_result(latest)
            if next_spec is None:
                return await _apply_host_actions(strip_deferred_result(latest))
            if next_spec.token != opaque_token:
                await _cancel("protocol_error")
                raise ValueError("Deferred plugin result attempted to rotate its token")
            spec = next_spec
    except asyncio.CancelledError:
        await _cancel("cancelled")
        raise


def get_plugin_tool_contract(function_name: str) -> Dict[str, Any]:
    loaded = load_plugins()
    return get_plugin_runtime_registry().tool_contract(
        function_name,
        loaded.plugins,
    )


def plugin_runtime_errors() -> tuple[str, ...]:
    return get_plugin_runtime_registry().errors


async def plugin_command_descriptions() -> list[Dict[str, Any]]:
    loaded = load_plugins()
    registry = get_plugin_runtime_registry()
    runtime_rows = await asyncio.to_thread(
        registry.command_descriptions,
        loaded.plugins,
    )
    return _plugin_command_catalog(loaded, runtime_rows)


async def start_plugin_background_services() -> list[Dict[str, Any]]:
    """Start manifest-declared services by activating their isolated workers."""

    loaded = load_plugins(force=True)
    return await asyncio.to_thread(
        get_plugin_runtime_registry().background_status,
        loaded.plugins,
    )


async def stop_plugin_runtime() -> None:
    """Stop workers, deferred leases, Web handlers, and background services."""

    from plugin_host_services import release_all_plugin_leases

    await asyncio.to_thread(release_all_plugin_leases)
    await asyncio.to_thread(
        get_plugin_runtime_registry().close,
        preserve_deferred=True,
    )


def _plugin_command_catalog(
    loaded: PluginLoadResult,
    runtime_rows: Optional[list[Dict[str, Any]]] = None,
) -> list[Dict[str, Any]]:
    rows = []
    signatures = {
        plugin.plugin_id: plugin.content_signature for plugin in loaded.plugins
    }
    for command in loaded.command_definitions.values():
        rows.append(
            {
                "plugin_id": command.plugin_id,
                "plugin_signature": signatures.get(command.plugin_id, ""),
                "name": command.name,
                "qualified_name": command.qualified_name,
                "description": command.description,
                "usage": command.usage,
                "kind": "declarative",
                "source_path": str(command.source_path) if command.source_path else None,
            }
        )
    if runtime_rows is None:
        runtime_rows = get_plugin_runtime_registry().command_descriptions(loaded.plugins)
    rows.extend({**row, "kind": "runtime"} for row in runtime_rows)
    return sorted(
        rows,
        key=lambda row: (
            str(row.get("qualified_name") or ""),
            str(row.get("kind") or ""),
        ),
    )


def _expand_declarative_command(template: str, arguments: str) -> str:
    expanded = str(template)
    raw_arguments = str(arguments or "")
    had_placeholder = "$ARGUMENTS" in expanded or "{{arguments}}" in expanded
    expanded = expanded.replace("$ARGUMENTS", raw_arguments)
    expanded = expanded.replace("{{arguments}}", raw_arguments)
    try:
        positional = shlex.split(raw_arguments, posix=os.name != "nt")
    except ValueError:
        positional = raw_arguments.split()
    for index in range(9, 0, -1):
        placeholder = f"${index}"
        if placeholder in expanded:
            had_placeholder = True
            value = positional[index - 1] if index <= len(positional) else ""
            expanded = expanded.replace(placeholder, value)
    if raw_arguments.strip() and not had_placeholder:
        expanded = f"{expanded.rstrip()}\n\nArguments: {raw_arguments.strip()}"
    return expanded


async def dispatch_plugin_command(
    user_input: str,
    context: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Expand a registered slash command into a prompt and optional context."""

    text = str(user_input or "")
    if not text.startswith("/") or text.startswith("//"):
        return {"matched": False}
    token, separator, arguments = text[1:].partition(" ")
    requested = token.strip()
    if not requested:
        return {"matched": False}

    loaded = load_plugins(force=True)
    registry = get_plugin_runtime_registry()
    runtime_rows = await asyncio.to_thread(
        registry.command_descriptions,
        loaded.plugins,
    )
    rows = _plugin_command_catalog(loaded, runtime_rows)
    local_counts: Dict[str, int] = {}
    for row in rows:
        local_name = str(row.get("name") or "")
        local_counts[local_name] = local_counts.get(local_name, 0) + 1
    matches = {
        str(row.get("qualified_name") or ""): row
        for row in rows
    }
    for row in rows:
        local_name = str(row.get("name") or "")
        if local_counts.get(local_name) == 1:
            matches.setdefault(local_name, row)
    selected = matches.get(requested)
    if selected is None:
        return {"matched": False}

    command_arguments = arguments if separator else ""
    if selected.get("kind") == "declarative":
        command = loaded.command_definitions.get(
            str(selected.get("qualified_name") or "")
        )
        if command is None:
            raise ValueError("Declarative plugin command changed before invocation")
        result = _expand_declarative_command(command.template, command_arguments)
    else:
        result = await asyncio.to_thread(
            registry.invoke_command,
            str(selected.get("plugin_id") or ""),
            str(selected.get("plugin_signature") or ""),
            str(selected.get("name") or ""),
            command_arguments,
            dict(context or {}),
            loaded.plugins,
        )
    if isinstance(result, str):
        prompt = result
        additional_context = ""
    elif isinstance(result, Mapping):
        prompt = result.get("prompt", result.get("user_input"))
        additional_context = str(result.get("additional_context") or "")
    else:
        raise ValueError("Plugin command must return a string or JSON object")
    if prompt is None or not str(prompt).strip():
        raise ValueError("Plugin command returned an empty prompt")
    return {
        "matched": True,
        "plugin_id": str(selected.get("plugin_id") or ""),
        "name": str(selected.get("name") or ""),
        "qualified_name": str(selected.get("qualified_name") or ""),
        "prompt": str(prompt),
        "additional_context": additional_context,
    }


def plugin_registry_signature() -> str:
    loaded = load_plugins()
    rows = [
        (
            plugin.plugin_id,
            plugin.content_signature,
            plugin_manager().is_enabled(plugin.plugin_id),
        )
        for plugin in loaded.plugins
    ]
    return json.dumps(
        {
            "enabled": loaded.globally_enabled,
            "plugins": rows,
            "errors": list(loaded.errors),
        },
        sort_keys=True,
        ensure_ascii=True,
    )


def extension_catalog_generation() -> int:
    """Return the revision bumped by supported plugin mutation paths."""
    with _lock:
        return int(_extension_catalog_generation)


def _bump_extension_catalog_generation() -> None:
    global _extension_catalog_generation
    _extension_catalog_generation += 1


def _plugin_hook_sources(loaded: PluginLoadResult) -> tuple[HookSource, ...]:
    roots = {plugin.plugin_id: plugin.root for plugin in loaded.plugins}
    out = []
    for resource in loaded.hook_sources:
        root = roots.get(resource.plugin_id, resource.path.parent)
        out.append(
            HookSource(
                source_id=f"plugin:{resource.plugin_id}:{resource.local_name}",
                root=Path(root).resolve(),
                config_path=Path(resource.path).resolve(),
                plugin_id=resource.plugin_id,
            )
        )
    return tuple(out)


def _path_signature(path: Path) -> str:
    try:
        stat = path.stat()
        return f"{path}:{stat.st_mtime_ns}:{stat.st_size}"
    except OSError:
        return f"{path}:missing"


def _hook_signature(
    loaded: PluginLoadResult,
    runtime_definitions: tuple[Any, ...] = (),
) -> str:
    hook_rows = [
        (resource.plugin_id, str(resource.path), _path_signature(Path(resource.path)))
        for resource in loaded.hook_sources
    ]
    return json.dumps(
        {
            "hooks_enabled": hooks_enabled(),
            "plugins_enabled": plugins_enabled(),
            "project": _path_signature(hooks_config_path()),
            "plugin_hooks": hook_rows,
            "runtime_hooks": [
                (
                    item.plugin_id,
                    item.plugin_signature,
                    item.event,
                    item.id,
                    item.matcher,
                    item.priority,
                )
                for item in runtime_definitions
            ],
        },
        sort_keys=True,
    )


def _runtime_hook_definitions(loaded: PluginLoadResult) -> tuple[Any, ...]:
    try:
        from plugins.host_hooks import runtime_hook_definitions
    except ImportError:  # pragma: no cover - package import style
        from .plugins.host_hooks import runtime_hook_definitions

    return runtime_hook_definitions(
        get_plugin_runtime_registry(),
        tuple(loaded.plugins),
    )


def hook_manager_for_current_loop(
    *,
    force: bool = False,
    runtime_definitions: Optional[tuple[Any, ...]] = None,
) -> HookManager:
    """Return a manager whose asyncio locks belong to the current loop."""

    loop = asyncio.get_running_loop()
    loaded = load_plugins(force=force)
    if runtime_definitions is None:
        runtime_definitions = _runtime_hook_definitions(loaded)
    signature = _hook_signature(loaded, runtime_definitions)
    with _lock:
        cached = _hook_managers.get(loop)
        if force or cached is None or cached[0] != signature:
            configured = str(os.getenv("HOOKS_PATH") or os.getenv("HOOKS_CONFIG_PATH") or "").strip()
            try:
                from plugins.host_hooks import PluginAwareHookExecutor
            except ImportError:  # pragma: no cover - package import style
                from .plugins.host_hooks import PluginAwareHookExecutor

            manager = HookManager(
                _project_root(),
                config_path=hooks_config_path() if configured else None,
                plugin_sources=_plugin_hook_sources(loaded) if plugins_enabled() else (),
                executor=PluginAwareHookExecutor(
                    _project_root(),
                    get_plugin_runtime_registry(),
                    lambda: tuple(load_plugins(force=True).plugins),
                ),
            )
            manager.extend_definitions(runtime_definitions)
            _hook_managers[loop] = (signature, manager)
            return manager
        return cached[1]


def hook_snapshot() -> Dict[str, Any]:
    """Build a synchronous management snapshot without retaining loop locks."""

    loaded = load_plugins()
    configured = str(os.getenv("HOOKS_PATH") or os.getenv("HOOKS_CONFIG_PATH") or "").strip()
    runtime_definitions = _runtime_hook_definitions(loaded)
    try:
        from plugins.host_hooks import PluginAwareHookExecutor
    except ImportError:  # pragma: no cover - package import style
        from .plugins.host_hooks import PluginAwareHookExecutor

    manager = HookManager(
        _project_root(),
        config_path=hooks_config_path() if configured else None,
        plugin_sources=_plugin_hook_sources(loaded) if plugins_enabled() else (),
        executor=PluginAwareHookExecutor(
            _project_root(),
            get_plugin_runtime_registry(),
            lambda: tuple(load_plugins(force=True).plugins),
        ),
    )
    manager.extend_definitions(runtime_definitions)
    definitions = []
    for item in manager.definitions:
        definitions.append(
            {
                "id": item.id,
                "event": item.event,
                "matcher": item.matcher,
                "source_id": item.source_id,
                "plugin_id": item.plugin_id,
                "failure_policy": item.failure_policy,
                "priority": item.priority,
                "timeout_seconds": item.command.timeout_seconds,
                "handler_type": item.handler_type,
            }
        )
    return {
        "enabled": manager.enabled,
        "path": str(hooks_config_path()),
        "definitions": definitions,
        "errors": list(manager.config_errors),
        "loaded_sources": list(manager.loaded_sources),
    }


def invalidate_extension_caches() -> None:
    global _plugin_cache
    with _lock:
        _plugin_cache = None
        _hook_managers.clear()
        _bump_extension_catalog_generation()
    try:
        from plugin_host_services import release_all_plugin_leases

        release_all_plugin_leases()
    except Exception:
        logger.debug("Plugin host-service lease cleanup failed", exc_info=True)
    try:
        from workflow_extensions import invalidate_bundled_workflow_callbacks

        invalidate_bundled_workflow_callbacks()
    except Exception:
        logger.debug("Workflow callback cache cleanup failed", exc_info=True)
    get_plugin_runtime_registry().invalidate()


def reload_extensions() -> PluginReloadResult:
    """Rediscover plugins and invalidate Hook/Skill/MCP integration caches."""

    global _plugin_cache
    with _lock:
        manager = plugin_manager()
        result = manager.reload_changed()
        cache_key = (
            id(manager),
            plugins_enabled(),
            tuple(str(path) for path in manager.discovery_dirs),
            str(manager.state.path),
        )
        _plugin_cache = (time.monotonic(), cache_key, result.loaded)
        _hook_managers.clear()
        _bump_extension_catalog_generation()
    get_plugin_runtime_registry().invalidate()
    try:
        from workflow_extensions import invalidate_bundled_workflow_callbacks

        invalidate_bundled_workflow_callbacks()
    except Exception:
        logger.debug("Workflow callback cache cleanup failed", exc_info=True)
    try:
        from agent_tools import invalidate_skills_cache

        invalidate_skills_cache()
    except Exception:
        logger.debug("Unable to invalidate the skill cache", exc_info=True)
    return result


def set_plugin_enabled(plugin_id: str, enabled: bool) -> Mapping[str, object]:
    state = plugin_manager().set_enabled(plugin_id, enabled)
    invalidate_extension_caches()
    try:
        from agent_tools import invalidate_skills_cache

        invalidate_skills_cache()
    except Exception:
        logger.debug("Unable to invalidate the skill cache", exc_info=True)
    return state


def _discovered_plugin(plugin_id: str):
    try:
        from plugins import PluginValidationError, normalize_namespace
    except ImportError:  # pragma: no cover - package import style
        from .plugins import PluginValidationError, normalize_namespace

    namespace = normalize_namespace(plugin_id)
    plugin = next(
        (item for item in plugin_manager().discover() if item.plugin_id == namespace),
        None,
    )
    if plugin is None:
        raise PluginValidationError(f"Unknown plugin: {plugin_id}")
    return plugin


def plugin_settings_snapshot(plugin_id: str) -> Dict[str, Any]:
    """Return a secret-free, host-renderable settings view for one plugin."""

    try:
        from plugins import public_plugin_settings
    except ImportError:  # pragma: no cover - package import style
        from .plugins import public_plugin_settings

    plugin = _discovered_plugin(plugin_id)
    settings = public_plugin_settings(plugin)
    if settings is None:
        raise ValueError(f"Plugin {plugin.plugin_id!r} has no settings schema")
    return {"ok": True, "settings": settings}


def update_plugin_settings(plugin_id: str, changes: Mapping[str, Any]) -> Dict[str, Any]:
    """Validate and atomically update non-secret plugin settings."""

    try:
        from plugins import PluginSettingsStore, public_plugin_settings
    except ImportError:  # pragma: no cover - package import style
        from .plugins import PluginSettingsStore, public_plugin_settings

    plugin = _discovered_plugin(plugin_id)
    store = PluginSettingsStore()
    store.update(plugin, changes)
    runtime = get_plugin_runtime_registry()
    # Settings are immutable per worker invocation. Restart workers so Web and
    # background capabilities also observe the new snapshot; deferred leases
    # remain bound and can resume against the replacement worker.
    runtime.invalidate(preserve_deferred=True)
    loaded = load_plugins(force=True)
    runtime.background_status(loaded.plugins)
    settings = public_plugin_settings(plugin, store=store)
    return {"ok": True, "settings": settings}


def install_plugin(
    source: str,
    *,
    replace: bool = False,
    ref: str = "",
    install_dependencies: bool = False,
) -> Dict[str, Any]:
    get_plugin_runtime_registry().invalidate()
    installer = _plugin_installer()
    result = installer.install(
        source,
        replace=replace,
        ref=ref,
        install_dependencies=install_dependencies,
    )
    invalidate_extension_caches()
    reload_extensions()
    return result


def uninstall_plugin(plugin_id: str) -> Dict[str, Any]:
    get_plugin_runtime_registry().invalidate()
    installer = _plugin_installer()
    result = installer.uninstall(plugin_id)
    invalidate_extension_caches()
    reload_extensions()
    return result


def install_plugin_dependencies(plugin_id: str) -> Dict[str, Any]:
    get_plugin_runtime_registry().invalidate()
    installer = _plugin_installer()
    result = installer.install_dependencies(plugin_id)
    invalidate_extension_caches()
    return result


def _runtime_v2_enabled() -> bool:
    return str(os.getenv("RUNTIME_VERSION", "2")).strip().lower() in {"2", "v2", "runtime_v2"}


def _history_ops(session_manager: Any):
    from runtime_v2 import runtime_v2_react_transaction_timeout_seconds
    from runtime_v2.history_ops import RuntimeHistoryOps

    return RuntimeHistoryOps(
        session_manager.sessions_dir,
        path_resolver=getattr(session_manager, "_resolve_session_path", None),
        transaction_timeout_seconds=runtime_v2_react_transaction_timeout_seconds(),
    )


def _audit_hook_result(
    session_manager: Any,
    session_id: str,
    run_id: str,
    result: HookDispatchResult,
) -> None:
    if not _runtime_v2_enabled() or not session_id or not result.enabled:
        return
    try:
        ops = _history_ops(session_manager)
        aggregate_id = f"dispatch:{result.event}"
        for item in result.results:
            event_type = "hook_finished"
            if item.outcome == "timed_out" or "timed out" in str(item.error).lower():
                event_type = "hook_timed_out"
            elif item.decision == "deny" or item.outcome == "blocked":
                event_type = "hook_blocked"
            elif not item.success:
                event_type = "hook_failed"
            ops.append_hook_event(
                session_id,
                event_type,
                {
                    "hook_id": item.hook_id,
                    "hook_event": item.event,
                    "plugin_id": item.plugin_id,
                    "source_id": item.source_id,
                    "success": item.success,
                    "outcome": item.outcome,
                    "decision": item.decision,
                    "reason": item.reason,
                    "error": item.error,
                    "duration_ms": item.duration_ms,
                    "exit_code": item.exit_code,
                    "failure_policy": item.failure_policy,
                },
                run_id=run_id or None,
            )
        if result.input_modified:
            ops.append_hook_event(
                session_id,
                "hook_input_modified",
                {
                    "hook_id": aggregate_id,
                    "hook_event": result.event,
                    "input_modified": True,
                },
                run_id=run_id or None,
            )
        ops.append_hook_event(
            session_id,
            "hook_finished",
            {
                "hook_id": aggregate_id,
                "hook_event": result.event,
                "status": "finished",
                "success": not result.blocked and not result.should_pause,
                "decision": result.decision,
                "duration_ms": result.duration_ms,
                "input_modified": result.input_modified,
            },
            run_id=run_id or None,
        )
    except Exception:
        logger.debug("Hook audit append failed", exc_info=True)


def _audit_hook_started(
    session_manager: Any,
    session_id: str,
    run_id: str,
    event: str,
) -> None:
    if not _runtime_v2_enabled() or not session_id or not hooks_enabled():
        return
    try:
        _history_ops(session_manager).append_hook_event(
            session_id,
            "hook_started",
            {
                "hook_id": f"dispatch:{event}",
                "hook_event": event,
                "status": "started",
            },
            run_id=run_id or None,
        )
    except Exception:
        logger.debug("Hook started audit append failed", exc_info=True)


def _audit_hook_dispatch_failure(
    session_manager: Any,
    session_id: str,
    run_id: str,
    event: str,
    error: str,
) -> None:
    if not _runtime_v2_enabled() or not session_id or not hooks_enabled():
        return
    try:
        _history_ops(session_manager).append_hook_event(
            session_id,
            "hook_failed",
            {
                "hook_id": f"dispatch:{event}",
                "hook_event": event,
                "status": "failed",
                "success": False,
                "error": str(error),
            },
            run_id=run_id or None,
        )
    except Exception:
        logger.debug("Hook failure audit append failed", exc_info=True)


async def dispatch_hook(
    event: str,
    payload: Optional[Mapping[str, Any]] = None,
    *,
    session_manager: Any = None,
    session_id: str = "",
    run_id: str = "",
) -> HookDispatchResult:
    loaded = load_plugins()
    runtime_definitions = await asyncio.to_thread(
        _runtime_hook_definitions,
        loaded,
    )
    manager = hook_manager_for_current_loop(
        runtime_definitions=runtime_definitions,
    )
    audit_enabled = bool(manager.enabled and manager.hooks_for(event))
    if session_manager is not None and audit_enabled:
        await asyncio.to_thread(
            _audit_hook_started,
            session_manager,
            str(session_id or ""),
            str(run_id or ""),
            event,
        )
    try:
        result = await manager.dispatch(event, payload or {})
    except Exception as exc:
        if session_manager is not None and audit_enabled:
            await asyncio.to_thread(
                _audit_hook_dispatch_failure,
                session_manager,
                str(session_id or ""),
                str(run_id or ""),
                event,
                str(exc),
            )
        raise
    if session_manager is not None and audit_enabled:
        await asyncio.to_thread(
            _audit_hook_result,
            session_manager,
            str(session_id or ""),
            str(run_id or ""),
            result,
        )
    return result


def audit_plugin_inventory(
    session_manager: Any,
    session_id: str,
    run_id: str = "",
    *,
    event_type: str = "plugin_state_changed",
) -> None:
    if not _runtime_v2_enabled() or not session_id:
        return
    try:
        ops = _history_ops(session_manager)
        manager = plugin_manager()
        report = manager.discover_report()
        loaded_ids = {plugin.plugin_id for plugin in load_plugins(force=True).plugins}
        snapshot = ops.snapshots.read(session_id)
        previous_plugins = snapshot.get("plugins") if isinstance(snapshot, dict) else {}
        if not isinstance(previous_plugins, dict):
            previous_plugins = {}
        seen_ids = set()
        for plugin in report.plugins:
            seen_ids.add(plugin.plugin_id)
            state = {
                "installed": True,
                "enabled": manager.is_enabled(plugin.plugin_id) and plugins_enabled(),
                "loaded": plugin.plugin_id in loaded_ids,
                "name": plugin.name,
                "version": plugin.version,
                "source_format": plugin.source_format,
                "compatibility": plugin.compatibility.status,
                "content_signature": plugin.content_signature,
            }
            previous = previous_plugins.get(plugin.plugin_id)
            previous = previous if isinstance(previous, dict) else {}
            tracked = {key: previous.get(key) for key in state}
            if tracked == state:
                continue
            actual_event_type = event_type
            if (
                event_type == "plugin_state_changed"
                and previous.get("content_signature")
                and previous.get("content_signature") != plugin.content_signature
            ):
                actual_event_type = "plugin_reloaded"
            ops.update_plugin_state(
                session_id,
                plugin.plugin_id,
                state,
                event_type=actual_event_type,
                run_id=run_id or None,
            )
        for removed_id in sorted(set(previous_plugins) - seen_ids):
            previous = previous_plugins.get(removed_id)
            if isinstance(previous, dict) and previous.get("installed") is False:
                continue
            ops.update_plugin_state(
                session_id,
                removed_id,
                {"installed": False, "enabled": False, "loaded": False},
                event_type=event_type,
                run_id=run_id or None,
            )
    except Exception:
        logger.debug("Plugin inventory audit failed", exc_info=True)


def extensions_snapshot() -> Dict[str, Any]:
    try:
        from plugins.ui import plugin_ui_contributions
    except ImportError:  # pragma: no cover - package import style
        from .plugins.ui import plugin_ui_contributions

    manager = plugin_manager()
    report = manager.discover_report()
    # Use the short hot-path cache instead of forcing a full plugin reload on
    # every settings/skill-popover snapshot; explicit reloads call force=True.
    loaded = load_plugins()
    loaded_ids = {plugin.plugin_id for plugin in loaded.plugins}
    runtime_registry = get_plugin_runtime_registry()
    runtime_command_rows = runtime_registry.command_descriptions(loaded.plugins)
    command_rows = _plugin_command_catalog(loaded, runtime_command_rows)
    plugin_rows = []
    ui_contributions = []
    for plugin in report.plugins:
        row = plugin.to_dict()
        row["configured_enabled"] = manager.is_enabled(plugin.plugin_id)
        row["enabled"] = row["configured_enabled"] and plugins_enabled()
        row["loaded"] = plugin.plugin_id in loaded_ids
        row["ui"] = []
        if row["loaded"]:
            row["ui"] = list(plugin_ui_contributions(plugin))
            ui_contributions.extend(row["ui"])
        if not _is_bundled_system_plugin(plugin):
            plugin_rows.append(row)
    ui_contributions.sort(
        key=lambda item: (
            0 if item.get("slot") == "navigation" else 100,
            int(item.get("order") or 0),
            str(item.get("label") or item.get("title") or "").casefold(),
            str(item.get("plugin_id") or ""),
            str(item.get("id") or ""),
        )
    )
    hook_data = hook_snapshot()
    return {
        "ok": True,
        "enabled": {"hooks": hooks_enabled(), "plugins": plugins_enabled()},
        "paths": {
            "hooks": hook_data["path"],
            "plugins": [str(path.resolve()) for path in manager.discovery_dirs],
            "plugin_state": str(manager.state.path.resolve()),
        },
        "plugins": plugin_rows,
        "ui_contributions": ui_contributions,
        "plugin_errors": list(report.errors) + list(loaded.errors),
        "plugin_warnings": list(report.warnings) + list(loaded.warnings),
        "plugin_runtime_errors": list(plugin_runtime_errors()),
        "plugin_runtime": runtime_registry.snapshot(),
        "plugin_commands": command_rows,
        "hooks": hook_data["definitions"],
        "hook_errors": hook_data["errors"],
        "hook_sources": hook_data["loaded_sources"],
    }


def plugin_session_ui_snapshot(
    session_ids: list[str] | tuple[str, ...],
    *,
    snapshot_reader: Callable[[str], Mapping[str, Any]],
) -> Dict[str, Any]:
    """Return field-whitelisted UI projections for loaded plugin state."""

    try:
        from plugins.ui import project_plugin_session_ui
    except ImportError:  # pragma: no cover - package import style
        from .plugins.ui import project_plugin_session_ui

    loaded = load_plugins()
    return {
        "ok": True,
        "sessions": project_plugin_session_ui(
            loaded.plugins,
            session_ids,
            snapshot_reader,
        ),
    }


def plugin_session_action(plugin_id: str, action_id: str) -> Optional[Dict[str, Any]]:
    """Resolve one enabled manifest-declared session action."""

    try:
        from plugins.ui import plugin_session_action_definition
    except ImportError:  # pragma: no cover - package import style
        from .plugins.ui import plugin_session_action_definition

    loaded = load_plugins()
    return plugin_session_action_definition(loaded.plugins, plugin_id, action_id)
