"""Targeted hot reload for one plugin, exposed as the ``reload_plugin`` tool.

A plugin has four moving parts: its on-disk definition (manifest, skills,
hooks, MCP declarations), its isolated runtime workers, its bundled host
adapter (FastAPI routes and lifecycle callbacks), and any published MCP
connections. This module rebuilds those parts for one plugin and leaves every
other plugin's workers alone: the runtime registry is invalidated with a
``plugin_id`` filter, so only the reloaded plugin's workers are dropped.

What is deliberately *not* claimed here: Python modules already imported by a
plugin's trusted host adapter keep their old routes if that adapter's
``install()`` is not idempotent, in-flight calls to the plugin's worker fail
when its worker is replaced, and dependency installation is not part of a
reload.
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from typing import Any, Mapping

logger = logging.getLogger(__name__)

_LOCK: "asyncio.Lock | None" = None
_LOCK_LOOP: "asyncio.AbstractEventLoop | None" = None


def _reload_lock() -> asyncio.Lock:
    """Return one reload lock per running loop.

    ``asyncio.Lock`` binds to the loop that first awaits it, while tests and
    the desktop shell may create more than one loop in a single process.
    """

    global _LOCK, _LOCK_LOOP
    loop = asyncio.get_running_loop()
    if _LOCK is None or _LOCK_LOOP is not loop:
        _LOCK = asyncio.Lock()
        _LOCK_LOOP = loop
    return _LOCK


def _components(plugin: Any) -> dict[str, int]:
    """Report what the reloaded definition actually contributes.

    ``PluginDefinition.skills`` holds declared skill *roots*; the useful number
    is how many ``SKILL.md`` files those roots expose, so enumerate them and
    fall back to the root count when the loader cannot be consulted.
    """

    try:
        from plugins import skill_resources

        skills = len(skill_resources(plugin))
    except Exception:
        skills = len(getattr(plugin, "skills", ()) or ())
    return {
        "skills": skills,
        "hook_files": len(getattr(plugin, "hooks", ()) or ()),
        "mcp_servers": len(getattr(plugin, "mcp_servers", {}) or {}),
        "agent_roots": len(getattr(plugin, "agents", ()) or ()),
        "prompt_roots": len(getattr(plugin, "prompts", ()) or ()),
    }


def _web_context() -> tuple[Any, dict[str, Any]]:
    """Return the live ASGI app plus the context bundled host adapters expect."""

    webui = sys.modules.get("webui")
    app = getattr(webui, "fastapi_app", None) if webui is not None else None
    if app is None:
        return None, {}
    manager = getattr(webui, "session_manager", None)
    return app, {
        "session_manager": manager,
        "project_root": getattr(webui, "PROJECT_ROOT", None),
        "work_dir": getattr(webui, "WORK_DIR", None),
        "app": app,
    }


def _has_host_adapter(plugin: Any) -> bool:
    """Return whether the plugin declares a bundled trusted-host adapter."""

    manifest = getattr(plugin, "raw_manifest", None)
    capabilities = manifest.get("capabilities") if isinstance(manifest, Mapping) else None
    return isinstance(capabilities, Mapping) and isinstance(capabilities.get("trusted_host"), Mapping)


async def reload_plugin(plugin_id: str, *, reason: str = "") -> dict[str, Any]:
    """Reload one plugin's definition, workers, routes and MCP connections."""

    from agent_extensions import (
        invalidate_extension_caches,
        plugin_manager,
        start_plugin_background_services,
    )

    try:  # Production launches with app/ on sys.path; package imports use the fallback.
        from plugins import PluginValidationError, normalize_namespace
    except ImportError:  # pragma: no cover - import style depends on the launcher
        from .plugins import PluginValidationError, normalize_namespace

    started = time.monotonic()
    namespace = normalize_namespace(plugin_id)
    manager = plugin_manager()
    known = {plugin.plugin_id for plugin in manager.discover()}
    if namespace not in known:
        raise PluginValidationError(f"Unknown plugin: {plugin_id}")

    async with _reload_lock():
        # discover() always reflects the current tree; the recorded baseline is
        # the only honest "before" once files have already been edited.
        recorded = getattr(manager, "loaded_signature", None)
        signature_before = recorded(namespace) if callable(recorded) else ""
        # 签名缓存按 (目录指纹) 命中，编辑后同一秒内可能读到旧值；
        # 热重载必须看到磁盘现状，先清掉再重新计算。
        try:
            try:
                from plugins import security as plugin_security
            except ImportError:
                from .plugins import security as plugin_security
            with plugin_security._SIGNATURE_CACHE_LOCK:
                plugin_security._SIGNATURE_CACHE.clear()
            cache_path = plugin_security._signature_cache_path()
            if cache_path is not None:
                cache_path.unlink(missing_ok=True)
        except Exception:
            logger.debug("Plugin signature cache reset failed", exc_info=True)
        reloaded = await asyncio.to_thread(manager.reload_changed)
        changes = reloaded.changes
        loaded = reloaded.loaded
        # Targeted invalidation: only this plugin's workers, leases and catalog
        # entries are dropped; unrelated plugins keep their live workers.
        await asyncio.to_thread(invalidate_extension_caches, plugin_id=namespace)
        try:
            from agent_tools import invalidate_skills_cache

            await asyncio.to_thread(invalidate_skills_cache)
        except Exception:  # pragma: no cover - cache invalidation is best effort
            logger.debug("Skill cache invalidation failed during plugin reload", exc_info=True)

        active = next((plugin for plugin in loaded.plugins if plugin.plugin_id == namespace), None)
        warnings: list[str] = []
        services: list[dict[str, Any]] = []
        routes_reinstalled = False
        mcp_refreshed = False

        if active is not None:
            rows = await start_plugin_background_services(loaded=loaded)
            services = [dict(row) for row in rows if row.get("plugin_id") == namespace]
            app, context = _web_context()
            if app is not None:
                try:
                    from plugins.host import (
                        forget_bundled_host_extension,
                        install_bundled_host_extensions,
                        stop_bundled_host_extension,
                        start_bundled_host_extensions,
                    )

                    # 即使签名没变，也要停掉旧适配器并丢掉模块缓存，
                    # 否则插件里改的 Python 代码不会生效（只能重启宿主）。
                    await stop_bundled_host_extension(namespace, context)
                    forget_bundled_host_extension(namespace)
                    await asyncio.to_thread(
                        install_bundled_host_extensions, app, loaded.plugins, context
                    )
                    await start_bundled_host_extensions(loaded.plugins, context)
                    from plugins.host import restart_bundled_host_extension

                    await restart_bundled_host_extension(active, context, app)
                    routes_reinstalled = True
                except Exception as exc:
                    warnings.append("Host 路由/生命周期重装失败：" + str(exc))
                if routes_reinstalled and _has_host_adapter(active):
                    warnings.append(
                        "只有在插件 install() 自身去重时旧路由才会被替换；请按需核对 /api 路径"
                    )
            else:
                warnings.append("当前进程没有 FastAPI 应用，已跳过分发路由与生命周期回调")
            if getattr(active, "mcp_servers", None):
                try:
                    from agent_mcp import force_reload

                    await force_reload()
                    mcp_refreshed = True
                except Exception as exc:
                    warnings.append("MCP 重新发现失败：" + str(exc))
        else:
            warnings.append(
                "插件当前未启用或装载失败：已清理该插件缓存与 worker，但没有重新装载"
                if not manager.is_enabled(namespace)
                else "插件重新装载失败，请查看 errors"
            )

        errors = [str(error) for error in loaded.errors if namespace in str(error)]
        payload = {
            "ok": True,
            "plugin_id": namespace,
            "reason": str(reason or "").strip()[:500],
            "enabled": manager.is_enabled(namespace),
            "active": active is not None,
            "changed": namespace in (*changes.added, *changes.changed, *changes.removed),
            "signature_before": signature_before,
            "signature_after": getattr(active, "content_signature", ""),
            "changes": changes.to_dict(),
            "components": _components(active) if active is not None else {},
            "background_services": services,
            "routes_reinstalled": routes_reinstalled,
            "mcp_refreshed": mcp_refreshed,
            "errors": errors,
            "warnings": warnings,
            "elapsed_ms": int((time.monotonic() - started) * 1000),
        }
        return payload


async def invoke_reload_plugin(context, arguments):  # noqa: ARG001 - tool context is unused
    """Host invoker for the ``reload_plugin`` model tool."""

    from tool_registry import ToolOutcome

    args = arguments if isinstance(arguments, Mapping) else {}
    plugin_id = str(args.get("plugin_id") or "").strip()
    if not plugin_id:
        return ToolOutcome.failed("plugin_id_required", "请提供要热重载的插件 ID")
    try:
        from runtime_lifecycle import is_draining

        if is_draining():
            return ToolOutcome.failed("restart_in_progress", "服务正在重启，请等恢复后再热重载插件")
    except Exception:  # pragma: no cover - lifecycle module is optional in tests
        logger.debug("Lifecycle drain check unavailable", exc_info=True)
    try:
        payload = await reload_plugin(plugin_id, reason=str(args.get("reason") or ""))
    except Exception as exc:
        try:
            from plugins import PluginValidationError
        except ImportError:  # pragma: no cover - import style depends on the launcher
            from .plugins import PluginValidationError

        if isinstance(exc, PluginValidationError):
            return ToolOutcome.failed("unknown_plugin", str(exc))
        logger.exception("Plugin hot reload failed: %s", plugin_id)
        return ToolOutcome.failed("plugin_reload_failed", str(exc))
    return ToolOutcome.completed(json.dumps(payload, ensure_ascii=False))
