"""Trusted lifecycle adapter for the optional Feishu transport.

The transport implementation lives in this plugin (``feishu_transport/``), not
in the core application: with the plugin absent or disabled, the core never
imports ``lark_oapi`` or any Feishu code.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_PLUGIN_ROOT = Path(__file__).resolve().parent
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))

# The host module is re-executed when the plugin content signature changes;
# drop the transport package too so edited files are picked up.
for _name in [name for name in sys.modules
              if name == "feishu_transport" or name.startswith("feishu_transport.")]:
    del sys.modules[_name]

from feishu_transport.config import FeishuConfig  # noqa: E402
from feishu_transport.runtime import FeishuRuntimeManager  # noqa: E402
from remote_control.public import transport_context  # noqa: E402

if str(_PLUGIN_ROOT) in sys.path:
    sys.path.remove(str(_PLUGIN_ROOT))


async def start(context, _plugin):
    ctx = transport_context()
    runtime = FeishuRuntimeManager(
        FeishuConfig.from_env(context["project_root"]),
        ctx.dependencies,
        shared_service=ctx.gateway_service,
    )
    globals()["_runtime"] = runtime
    await asyncio.to_thread(runtime.start)


async def stop(_context, _plugin):
    runtime = globals().pop("_runtime", None)
    if runtime is not None:
        await asyncio.to_thread(runtime.stop)
