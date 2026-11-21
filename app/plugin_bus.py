"""宿主插件服务总线（方案 B 的正式形态）。

三件事：
  * 插件注册自己能提供的服务（如 browser）；
  * 插件在 manifest 的 permissions.services 里声明自己想调用的服务；
  * 调用时按「声明 + 方法白名单 + 调用方」三重校验，并记录审计。
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, Mapping

LOG = logging.getLogger("plugin_bus")

Handler = Callable[[str, str, Mapping[str, Any]], Awaitable[Any]]

_SERVICES: dict[str, dict[str, Any]] = {}
_DECLARED: dict[str, set[str]] = {}
_AUDIT: list[dict[str, Any]] = []


def reset() -> None:
    _SERVICES.clear()
    _DECLARED.clear()
    _AUDIT.clear()


def note_plugin(plugin_id: str, permissions: Mapping[str, Any] | None) -> None:
    """记录插件声明的服务权限；manifest 里的写法：permissions.services=[\"browser\"]。"""
    if not plugin_id:
        return
    raw = (permissions or {}).get("services") or []
    if isinstance(raw, str):
        raw = [raw]
    names = set()
    for item in raw:
        text = str(item or "").strip()
        if not text:
            continue
        names.add(text.split(".")[0])
    _DECLARED[str(plugin_id)] = names


def register(owner: str, name: str, handler: Handler, *, methods: set[str] | None = None) -> None:
    if not owner or not name or not callable(handler):
        raise ValueError("register 需要 owner/name/handler")
    _SERVICES[name] = {"owner": owner, "handler": handler, "methods": set(methods or ())}
    LOG.info("插件服务已注册：%s（owner=%s，方法=%s）", name, owner, sorted(methods or ()))


def unregister(owner: str, name: str) -> None:
    entry = _SERVICES.get(name)
    if entry and entry["owner"] == owner:
        _SERVICES.pop(name, None)


def available(name: str) -> bool:
    return name in _SERVICES


def allowed(caller: str, name: str) -> bool:
    return name in _DECLARED.get(str(caller), set())


async def call(caller: str, name: str, method: str, params: Mapping[str, Any] | None = None) -> Any:
    entry = _SERVICES.get(str(name))
    if entry is None:
        raise RuntimeError(f"服务 {name} 未注册")
    if not allowed(caller, name):
        raise PermissionError(f"插件 {caller} 未声明 {name} 权限")
    methods = entry["methods"]
    if methods and method not in methods:
        raise PermissionError(f"方法 {method} 不在 {name} 的白名单")
    _AUDIT.append({"caller": caller, "service": name, "method": method,
                   "params": {k: (str(v)[:60] if k != "text" else f"<{len(str(v))}字>")
                              for k, v in (params or {}).items()}})
    del _AUDIT[:-50]
    return await entry["handler"](caller, method, dict(params or {}))


def audit() -> list[dict[str, Any]]:
    return list(_AUDIT)


def call_in_loop(caller: str, name: str, method: str, params: Mapping[str, Any] | None = None):
    """在事件循环线程里排一个任务，返回 asyncio.Task；调用方自己决定是否等待。"""
    loop = asyncio.get_running_loop()
    return loop.create_task(call(caller, name, method, params))
