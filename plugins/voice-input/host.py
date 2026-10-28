"""Bundled voice plugin: own HTTP routes and release providers on disable.

Hot reload: the host loads this adapter under a module name that already
carries the plugin content digest, so the ``speech_input`` package is named
after it. An edited copy therefore lands in a new package instead of being
reused from ``sys.modules``, and ``install()`` rebuilds the service (and its
routes) whenever the digest changes.
"""
import importlib.util
from pathlib import Path
import sys


_SERVICE_KEY = "voice_input_service"
_SIGNATURE_KEY = "voice_input_service_signature"
_ROUTE_PREFIX = "/api/speech"


def _package_name() -> str:
    """Per-adapter package name: a new digest never reuses old modules."""

    return __name__ + "_speech"


def _runtime():
    name = _package_name()
    if name not in sys.modules:
        root = Path(__file__).parent / "speech_input"
        spec = importlib.util.spec_from_file_location(
            name, root / "__init__.py", submodule_search_locations=[str(root)]
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    from importlib import import_module
    return import_module(name + ".api")


def _drop_routes(app) -> None:
    """Remove the previous cycle's /api/speech routes (APIRoute only)."""

    from fastapi.routing import APIRoute

    app.router.routes[:] = [
        route for route in app.router.routes
        if not isinstance(route, APIRoute)
        or (getattr(route, "path", "") != _ROUTE_PREFIX
            and not getattr(route, "path", "").startswith(_ROUTE_PREFIX + "/"))
    ]
    app.openapi_schema = None


def _register(app, context, plugin):
    from plugins.host import bundled_host_plugin_enabled

    service = _runtime().register_speech_api(
        app, context["work_dir"], lambda: getattr(app.state, "remote_control_gateway", None),
        enabled_resolver=lambda: bundled_host_plugin_enabled(plugin.plugin_id),
    )
    globals()["_service"] = service
    app.state.voice_input_service = service
    app.state.voice_input_service_signature = str(getattr(plugin, "content_signature", "") or "")
    return service


def install(app, context, plugin):
    signature = str(getattr(plugin, "content_signature", "") or "")
    current = getattr(app.state, _SERVICE_KEY, None)
    if current is not None and getattr(app.state, _SIGNATURE_KEY, "") == signature:
        return
    retired = globals().get("_service")
    _drop_routes(app)
    _register(app, context, plugin)
    if retired is not None and retired is not globals().get("_service"):
        # The lifecycle reconciler stops the retired adapter normally; this only
        # covers an in-place rebuild that had no matching stop().
        _close_quietly(retired)


def _close_quietly(service) -> None:
    import asyncio

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    loop.create_task(service.close())


async def start(context, plugin):
    service = globals().get("_service")
    if service is None:
        app = context.get("app") if hasattr(context, "get") else None
        if app is None:
            return
        service = _register(app, context, plugin)
    service._closed = False


async def stop(context, plugin):
    service = globals().get("_service")
    app = context.get("app") if hasattr(context, "get") else None
    if app is not None and getattr(app.state, _SERVICE_KEY, None) is service:
        app.state.voice_input_service = None
        app.state.voice_input_service_signature = ""
    if service is not None:
        await service.close()
