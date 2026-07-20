"""Host integration for declarative Hooks and Plugins.

This module is deliberately thin: plugin packages are parsed as data and are
never imported.  It supplies one process-wide plugin registry plus one Hook
manager per asyncio event loop, so the main loop and its worker loop do not
share loop-bound locks.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import time
import weakref
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Tuple

try:  # Production launches with app/ on sys.path; package imports use the fallback.
    from hooks import HookDispatchResult, HookManager, HookSource, hooks_enabled
    from plugins import (
        PluginLoadResult,
        PluginManager,
        PluginReloadResult,
        get_plugin_manager,
        plugins_enabled,
    )
except ImportError:  # pragma: no cover - import style depends on the launcher
    from .hooks import HookDispatchResult, HookManager, HookSource, hooks_enabled
    from .plugins import (
        PluginLoadResult,
        PluginManager,
        PluginReloadResult,
        get_plugin_manager,
        plugins_enabled,
    )

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 1.0
_lock = threading.RLock()
_plugin_cache: Optional[Tuple[float, tuple[Any, ...], PluginLoadResult]] = None
_hook_managers: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, tuple[str, HookManager]]" = (
    weakref.WeakKeyDictionary()
)


def _project_root() -> Path:
    from agent_harness import WORK_DIR

    return Path(WORK_DIR).expanduser().resolve()


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


def _hook_signature(loaded: PluginLoadResult) -> str:
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
        },
        sort_keys=True,
    )


def hook_manager_for_current_loop(*, force: bool = False) -> HookManager:
    """Return a manager whose asyncio locks belong to the current loop."""

    loop = asyncio.get_running_loop()
    loaded = load_plugins(force=force)
    signature = _hook_signature(loaded)
    with _lock:
        cached = _hook_managers.get(loop)
        if force or cached is None or cached[0] != signature:
            configured = str(os.getenv("HOOKS_PATH") or os.getenv("HOOKS_CONFIG_PATH") or "").strip()
            manager = HookManager(
                _project_root(),
                config_path=hooks_config_path() if configured else None,
                plugin_sources=_plugin_hook_sources(loaded) if plugins_enabled() else (),
            )
            _hook_managers[loop] = (signature, manager)
            return manager
        return cached[1]


def hook_snapshot() -> Dict[str, Any]:
    """Build a synchronous management snapshot without retaining loop locks."""

    loaded = load_plugins()
    configured = str(os.getenv("HOOKS_PATH") or os.getenv("HOOKS_CONFIG_PATH") or "").strip()
    manager = HookManager(
        _project_root(),
        config_path=hooks_config_path() if configured else None,
        plugin_sources=_plugin_hook_sources(loaded) if plugins_enabled() else (),
    )
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


def _runtime_v2_enabled() -> bool:
    return str(os.getenv("RUNTIME_VERSION", "2")).strip().lower() in {"2", "v2", "runtime_v2"}


def _history_ops(session_manager: Any):
    from runtime_v2.history_ops import RuntimeHistoryOps

    return RuntimeHistoryOps(
        session_manager.sessions_dir,
        path_resolver=getattr(session_manager, "_resolve_session_path", None),
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
    manager = hook_manager_for_current_loop()
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
    manager = plugin_manager()
    report = manager.discover_report()
    loaded = load_plugins(force=True)
    loaded_ids = {plugin.plugin_id for plugin in loaded.plugins}
    plugin_rows = []
    for plugin in report.plugins:
        row = plugin.to_dict()
        row["configured_enabled"] = manager.is_enabled(plugin.plugin_id)
        row["enabled"] = row["configured_enabled"] and plugins_enabled()
        row["loaded"] = plugin.plugin_id in loaded_ids
        plugin_rows.append(row)
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
        "plugin_errors": list(report.errors) + list(loaded.errors),
        "plugin_warnings": list(report.warnings) + list(loaded.warnings),
        "hooks": hook_data["definitions"],
        "hook_errors": hook_data["errors"],
        "hook_sources": hook_data["loaded_sources"],
    }
