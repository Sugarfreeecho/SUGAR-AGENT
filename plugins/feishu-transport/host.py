"""Trusted lifecycle adapter for the optional Feishu transport."""
from __future__ import annotations


async def start(context, _plugin):
    from remote_control.transports.feishu.config import FeishuConfig
    from remote_control.transports.feishu.runtime import FeishuRuntimeManager
    import webui

    runtime = FeishuRuntimeManager(
        FeishuConfig.from_env(context["project_root"]),
        webui._control_dependencies,
        shared_service=(
            webui._remote_control_gateway.service
            if webui._remote_control_gateway is not None
            else None
        ),
    )
    globals()["_runtime"] = runtime
    await __import__("asyncio").to_thread(runtime.start)


async def stop(_context, _plugin):
    runtime = globals().pop("_runtime", None)
    if runtime is not None:
        await __import__("asyncio").to_thread(runtime.stop)
