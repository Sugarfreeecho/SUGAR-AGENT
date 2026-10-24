"""Trusted host adapter for the bundled Thread Monitor plugin.

The plugin ships its sampler next to this file.  A trusted host adapter is used
instead of the out-of-process plugin runtime because the numbers we want - the
host process's OS threads - only exist inside this process.

Everything exposed here is read-only, except ``POST /reset`` which only clears
the monitor's own baseline/peak counters and never touches agent state.
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Optional

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse


# One fixed module name, deliberately not derived from the content signature.
# The host re-imports a bundled adapter whenever its files change, so a
# per-signature module name would leave the previous generation's sampler
# thread running - a monitoring tool that leaks a thread per edit.
_MODULE_NAME = "myagent_thread_monitor"
_SIGNATURE_ATTR = "__thread_monitor_signature__"


def _stop_instance(module: Optional[ModuleType]) -> None:
    if module is None:
        return
    monitor = getattr(module, "_instance", None)
    if monitor is None:
        return
    try:
        monitor.stop()
    except Exception:
        pass
    module._instance = None


def _monitor_module(plugin: Any) -> ModuleType:
    """Load ``monitor.py`` for the plugin's current content signature.

    An edited copy must not stay stale in ``sys.modules``, but the replacement
    must also not add a second ticker: the previous sampler is stopped before
    the new code is executed into the same module name.
    """

    signature = str(getattr(plugin, "content_signature", "") or "dev")
    cached = sys.modules.get(_MODULE_NAME)
    if cached is not None and getattr(cached, _SIGNATURE_ATTR, "") == signature:
        return cached
    _stop_instance(cached)
    path = Path(__file__).with_name("monitor.py")
    spec = importlib.util.spec_from_file_location(_MODULE_NAME, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load thread-monitor sampler")
    module = importlib.util.module_from_spec(spec)
    sys.modules[_MODULE_NAME] = module
    spec.loader.exec_module(module)
    setattr(module, _SIGNATURE_ATTR, signature)
    return module


def _monitor(plugin: Any):
    module = _monitor_module(plugin)
    monitor = getattr(module, "_instance", None)
    if monitor is None:
        monitor = module.ThreadMonitor()
        module._instance = monitor
    # Starting lazily keeps the API usable after the plugin is enabled without
    # requiring a restart; ``start()`` is idempotent.
    monitor.start()
    return monitor


def _disabled() -> JSONResponse:
    return JSONResponse(
        {"ok": False, "error": "plugin_disabled", "message": "Thread Monitor is disabled"},
        status_code=404,
    )


def install(app, context, plugin):
    router = APIRouter(prefix="/api/thread-monitor", tags=["thread-monitor"])

    @router.get("")
    async def read_snapshot(history: int = Query(60, ge=1, le=600)):
        from plugins.host import bundled_host_plugin_enabled

        if not bundled_host_plugin_enabled(plugin.plugin_id):
            return _disabled()
        monitor = _monitor(plugin)
        try:
            data = await asyncio.to_thread(monitor.snapshot, history=history)
        except Exception as exc:
            return JSONResponse(
                {"ok": False, "error": "sample_failed", "message": str(exc)}, status_code=500
            )
        return JSONResponse({"ok": True, "data": data})

    @router.post("/reset")
    async def reset_baseline():
        from plugins.host import bundled_host_plugin_enabled

        if not bundled_host_plugin_enabled(plugin.plugin_id):
            return _disabled()
        monitor = _monitor(plugin)
        try:
            data = await asyncio.to_thread(monitor.reset_baseline)
        except Exception as exc:
            return JSONResponse(
                {"ok": False, "error": "reset_failed", "message": str(exc)}, status_code=500
            )
        return JSONResponse({"ok": True, "data": data})

    app.include_router(router)


async def start(context, plugin) -> None:
    from plugins.host import bundled_host_plugin_enabled

    if not bundled_host_plugin_enabled(plugin.plugin_id):
        return
    try:
        _monitor(plugin)
    except Exception:
        # A sampler failure must never block app startup; the API retries lazily
        # and reports the error through the sample payload instead.
        pass


async def stop(context, plugin) -> None:
    _stop_instance(sys.modules.get(_MODULE_NAME))
