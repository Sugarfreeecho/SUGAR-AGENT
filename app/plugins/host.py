"""Trusted in-process adapters for bundled workflow plugins.

Ordinary plugins always run out of process. A plugin physically shipped under
the repository's bundled ``plugins`` directory may additionally declare a
small host adapter for FastAPI routers and lifecycle callbacks that need core
service facades. The location check is host policy; a manifest alone cannot
grant this trust level.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
import asyncio
import hashlib
import importlib.util
import inspect
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Mapping, Sequence

from .models import PluginDefinition
from .security import PluginSecurityError


_BUNDLED_ROOT = Path(__file__).resolve().parents[2] / "plugins"
_MODULES: dict[tuple[str, str], ModuleType] = {}
_INSTALLED: set[tuple[int, str, str]] = set()
_STARTED: list[tuple[PluginDefinition, ModuleType]] = []
_INSTALLED_ROUTES: dict[tuple[int, str], list[Any]] = {}
_LIFECYCLE_LOCK = asyncio.Lock()
_AVAILABILITY_SNAPSHOT: ContextVar[dict | None] = ContextVar("bundled_host_availability_snapshot", default=None)


@contextmanager
def bundled_host_availability_scope():
    """Use one live plugin-state read per catalog pass, never across requests."""
    token = _AVAILABILITY_SNAPSHOT.set({})
    try:
        yield
    finally:
        _AVAILABILITY_SNAPSHOT.reset(token)


def is_bundled_trusted_host_plugin(plugin: PluginDefinition) -> bool:
    """Return whether a native plugin is installed directly under ``plugins/``.

    The bundled directory is the host-controlled trust boundary.  Requiring the
    resolved root to be exactly ``plugins/<plugin id>`` prevents manifests from
    granting in-process trust to plugins discovered from user or nested paths,
    while allowing newly bundled plugin directories without a second allowlist.
    """

    if plugin.source_format != "native":
        return False
    try:
        bundled_root = _BUNDLED_ROOT.resolve(strict=True)
        root = plugin.root.resolve(strict=True)
        expected_root = (_BUNDLED_ROOT / plugin.plugin_id).resolve(strict=True)
        root.relative_to(bundled_root)
        return root.is_dir() and root == expected_root
    except (OSError, RuntimeError, ValueError):
        return False


def _host_entry(plugin: PluginDefinition) -> Path | None:
    manifest = getattr(plugin, "raw_manifest", None) or {}
    capabilities = manifest.get("capabilities") if isinstance(manifest, dict) else None
    raw = capabilities.get("trusted_host") if isinstance(capabilities, Mapping) else None
    if not isinstance(raw, Mapping):
        return None
    entry = str(raw.get("entry") or "").strip()
    if not entry:
        return None
    root = plugin.root.resolve()
    try:
        root.relative_to(_BUNDLED_ROOT.resolve())
    except ValueError as exc:
        raise PluginSecurityError(
            f"Plugin {plugin.plugin_id!r} requested trusted_host outside the bundled root"
        ) from exc
    if not is_bundled_trusted_host_plugin(plugin):
        raise PluginSecurityError(
            f"Plugin {plugin.plugin_id!r} is not installed at "
            f"plugins/{plugin.plugin_id} under the bundled root"
        )
    candidate = (root / entry).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise PluginSecurityError("trusted_host entry escapes the plugin root") from exc
    if candidate.suffix.lower() != ".py" or not candidate.is_file():
        raise PluginSecurityError("trusted_host entry must be an existing Python file")
    return candidate


def _module(plugin: PluginDefinition) -> ModuleType | None:
    entry = _host_entry(plugin)
    if entry is None:
        return None
    key = (plugin.plugin_id, plugin.content_signature)
    cached = _MODULES.get(key)
    if cached is not None:
        return cached
    digest = hashlib.sha256(f"{entry}:{plugin.content_signature}".encode()).hexdigest()[:16]
    name = f"myagent_bundled_host_{digest}"
    # Give each adapter its own package namespace so implementation modules
    # can stay inside the plugin without adding its directory to sys.path.
    spec = importlib.util.spec_from_file_location(
        name, entry, submodule_search_locations=[str(entry.parent)]
    )
    if spec is None or spec.loader is None:
        raise PluginSecurityError(f"Cannot load trusted host entry: {entry}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        for module_name in list(sys.modules):
            if module_name == name or module_name.startswith(name + "."):
                sys.modules.pop(module_name, None)
        raise
    _MODULES[key] = module
    return module


def bundled_host_plugin_enabled(plugin_id: str) -> bool:
    """Return live enablement for a bundled host extension."""

    try:
        from .manager import get_plugin_manager, plugins_enabled

        snapshot = _AVAILABILITY_SNAPSHOT.get()
        if snapshot is not None:
            if "plugins" not in snapshot:
                snapshot["enabled"] = plugins_enabled()
                snapshot["plugins"] = {}
            key = str(plugin_id or "")
            cached = snapshot["plugins"].get(key)
            if cached is None:
                # tier default + per-plugin environment override + persisted state
                try:
                    cached = get_plugin_manager().is_enabled(key)
                except Exception:
                    # One failed read disables this plugin for this catalog
                    # pass; retry on the next pass or actual invocation.
                    cached = False
                snapshot["plugins"][key] = bool(cached)
            return bool(snapshot["enabled"] and cached)
        manager = get_plugin_manager()
        return bool(plugins_enabled() and manager.is_enabled(str(plugin_id or "")))
    except Exception:
        return False


def bundled_host_tool_definitions(
    plugins: Sequence[PluginDefinition],
    *,
    session_meta: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Activate and describe tools owned by enabled bundled extensions.

    The callable is accepted only from a physically bundled, host-validated
    module. Ordinary manifests cannot register in-process invokers.
    """

    rows: list[dict[str, Any]] = []
    context = {
        "is_enabled": bundled_host_plugin_enabled,
        "session_meta": dict(session_meta or {}),
    }
    for plugin in plugins:
        module = _module(plugin)
        describe = getattr(module, "tool_definitions", None) if module is not None else None
        if not callable(describe):
            continue
        definitions = describe(dict(context), plugin)
        if not isinstance(definitions, (list, tuple)):
            raise PluginSecurityError("trusted host tool_definitions must return a list")
        for definition in definitions:
            if not isinstance(definition, Mapping):
                raise PluginSecurityError("trusted host tool definition must be an object")
            rows.append(dict(definition))
    return rows


def activate_bundled_provider_extensions(
    plugins: Sequence[PluginDefinition],
    registry: Any,
    *,
    registration_method: str = "register_providers",
) -> None:
    """Let only physically bundled host adapters register hot-path providers."""

    method = str(registration_method or "").strip()
    if method not in {"register_providers", "register_search_providers"}:
        raise PluginSecurityError("unsupported bundled provider registration method")
    for plugin in plugins:
        module = _module(plugin)
        register = getattr(module, method, None) if module is not None else None
        if callable(register):
            register(registry, plugin)


def install_bundled_host_extensions(
    app: Any,
    plugins: Sequence[PluginDefinition],
    context: Mapping[str, Any],
) -> None:
    """Install enabled bundled routers before the ASGI app starts."""

    for plugin in plugins:
        module = _module(plugin)
        install = getattr(module, "install", None) if module is not None else None
        key = (id(app), plugin.plugin_id, plugin.content_signature)
        if callable(install) and key not in _INSTALLED:
            import plugin_bus

            plugin_bus.note_plugin(plugin.plugin_id, plugin.permissions)
            _drop_installed_routes(app, plugin.plugin_id)
            before = len(app.routes)
            install(app, dict(context), plugin)
            _INSTALLED_ROUTES[(id(app), plugin.plugin_id)] = list(app.routes[before:])
            _INSTALLED.add(key)


async def start_bundled_host_extensions(
    plugins: Sequence[PluginDefinition],
    context: Mapping[str, Any],
) -> None:
    """Reconcile changed extensions without interrupting unchanged services."""

    async with _LIFECYCLE_LOCK:
        desired = []
        for plugin in plugins:
            module = _module(plugin)
            if callable(getattr(module, "start", None)):
                desired.append((plugin, module))
        desired_keys = {(plugin.plugin_id, plugin.content_signature) for plugin, _ in desired}
        for plugin, module in reversed(_STARTED):
            if (plugin.plugin_id, plugin.content_signature) not in desired_keys:
                await _stop_bundled_host_extension(plugin, module, context)
        started_keys = {(plugin.plugin_id, plugin.content_signature) for plugin, _ in _STARTED}
        for plugin, module in desired:
            key = (plugin.plugin_id, plugin.content_signature)
            if key in started_keys:
                continue
            import plugin_bus

            plugin_bus.note_plugin(plugin.plugin_id, plugin.permissions)
            value = module.start(dict(context), plugin)
            if inspect.isawaitable(value):
                await value
            # Track each successful start immediately so a later failure does
            # not orphan services or start them twice on the next refresh.
            _STARTED.append((plugin, module))
            started_keys.add(key)


async def _stop_bundled_host_extension(plugin, module, context) -> None:
    from session_control.integration import application
    control = application()
    if control is not None and control.service.manager is context.get("session_manager") and not control.service.closing:
        from plugin_host_services import release_plugin_leases
        release_plugin_leases(plugin.plugin_id)
    stop = getattr(module, "stop", None)
    if callable(stop):
        value = stop(dict(context), plugin)
        if inspect.isawaitable(value):
            await value
    _STARTED.remove((plugin, module))


async def stop_bundled_host_extension(plugin_id: str, context: Mapping[str, Any]) -> None:
    """Stop one plugin's host adapter even if its signature did not change."""

    async with _LIFECYCLE_LOCK:
        for plugin, module in reversed(list(_STARTED)):
            if plugin.plugin_id == plugin_id:
                await _stop_bundled_host_extension(plugin, module, context)


def forget_bundled_host_extension(plugin_id: str) -> None:
    """Drop cached adapter modules so the next start re-imports edited code."""

    for key in [k for k in _MODULES if k[0] == plugin_id]:
        module = _MODULES.pop(key, None)
        name = getattr(module, "__name__", "")
        if name:
            sys.modules.pop(name, None)
            for child in [n for n in sys.modules if n.startswith(name + ".")]:
                sys.modules.pop(child, None)


def forget_bundled_host_install(plugin_id: str) -> None:
    """Allow install() to run again for one plugin after a forced reload."""

    for key in [k for k in _INSTALLED if k[1] == plugin_id]:
        _INSTALLED.discard(key)


def _drop_installed_routes(app: Any, plugin_id: str) -> None:
    """Remove routes a previous install() added, so re-install replaces instead of stacking."""

    routes = _INSTALLED_ROUTES.pop((id(app), plugin_id), [])
    if not routes:
        return
    try:
        app.routes[:] = [route for route in app.routes if route not in routes]
    except Exception:
        for route in routes:
            try:
                app.routes.remove(route)
            except ValueError:
                pass


async def restart_bundled_host_extension(plugin, context: Mapping[str, Any], app: Any = None) -> None:
    """Force stop → re-import → install → start for one plugin, ignoring signatures."""

    await stop_bundled_host_extension(plugin.plugin_id, context)
    forget_bundled_host_extension(plugin.plugin_id)
    forget_bundled_host_install(plugin.plugin_id)
    module = _module(plugin)
    if module is None:
        return
    install = getattr(module, "install", None)
    if app is not None and callable(install):
        import plugin_bus

        plugin_bus.note_plugin(plugin.plugin_id, plugin.permissions)
        _drop_installed_routes(app, plugin.plugin_id)
        routes = getattr(app, "routes", None)
        before = len(routes) if routes is not None else 0
        install(app, dict(context), plugin)
        if routes is not None:
            _INSTALLED_ROUTES[(id(app), plugin.plugin_id)] = list(app.routes[before:])
        _INSTALLED.add((id(app), plugin.plugin_id, plugin.content_signature))
    start = getattr(module, "start", None)
    if callable(start):
        value = start(dict(context), plugin)
        if inspect.isawaitable(value):
            await value
        _STARTED.append((plugin, module))


async def stop_bundled_host_extensions(context: Mapping[str, Any]) -> None:
    async with _LIFECYCLE_LOCK:
        for plugin, module in reversed(_STARTED):
            await _stop_bundled_host_extension(plugin, module, context)


__all__ = [
    "is_bundled_trusted_host_plugin",
    "install_bundled_host_extensions",
    "bundled_host_plugin_enabled",
    "bundled_host_tool_definitions",
    "activate_bundled_provider_extensions",
    "start_bundled_host_extensions",
    "stop_bundled_host_extensions",
]
