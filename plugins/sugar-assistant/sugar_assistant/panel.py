"""控制台接口的纯数据层：放在可热重载的模块里，改这里不需要重启宿主。"""
from __future__ import annotations

import os
import time
from typing import Any

from .config import Config


def status_payload(service: Any, console: Any, *, started_at: float = 0.0,
                   fallback_adapters: dict | None = None) -> dict:
    adapters = getattr(getattr(service, "runtime", None), "adapters", None) or fallback_adapters or {}
    config = Config.load()
    channels = []
    for name, cfg in sorted(config.channels.items()):
        adapter = adapters.get(name)
        health = {}
        if adapter is not None and hasattr(adapter, "health"):
            try:
                health = adapter.health()
            except Exception as exc:
                health = {"error": str(exc)}
        channels.append({"name": name, "enabled": cfg.enabled, "quota": cfg.quota,
                         "running": adapter is not None, "health": health})
    sessions: list[str] = []
    if service is not None:
        store = service.runtime.sessions._store.read()  # noqa: SLF001
        sessions = list((store.get("sessions") or {}).keys())
    return {
        "ok": True,
        "plugin": "sugar-assistant",
        "core": service is not None,
        "uptime": round(time.time() - float(started_at or time.time())),
        "channels": channels,
        "web": web_status(),
        "web_api": web_api_status(),
        "warnings": config_warnings(),
        "conversations": len(sessions),
        "persona": console.persona(),
    }


def web_api_status() -> dict:
    """Web 内部接口通道的就绪度：Cookie 与数字 chatId 映射缺一不可。"""
    try:
        from . import web_api
        cookies = web_api.load_cookies({})
        mapping = web_api.load_map()
        ready = bool(cookies.get("session")) and bool(mapping)
        return {"ready": ready, "cookies": len(cookies), "chats": len(mapping),
                "rate_limit": web_api.RATE_LIMIT, "sent_last_min": len(web_api._SENT),
                "last": web_api.load_state()}
    except Exception as exc:
        return {"ready": False, "cookies": 0, "chats": 0, "error": str(exc)}


def config_warnings() -> list[str]:
    """不可用组合在配置层先提示，别等运行时报错。"""
    from . import identity

    warns: list[str] = []
    web = web_status()
    mode = identity.current()
    if mode == "user" and not web.get("enabled") and not web_api_status().get("ready"):
        warns.append("当前是账户主身份，浏览器兜底与 Web 接口都不可用：外部单聊会发不出去")
    if web.get("enabled") and not web.get("available"):
        warns.append(f"浏览器兜底已启用但不可用：{web.get('reason') or '未知原因'}")
    if mode == "user" and not web_api_status().get("ready"):
        warns.append("Web 接口通道未就绪（缺 Cookie 或 chatId 映射），外部单聊将降级到 DOM")
    if mode == "user" and not web.get("enabled") and web_api_status().get("ready"):
        warns.append("仅 Web 接口可用：它只发文本，附件/图片需要浏览器兜底")
    return warns


def web_status() -> dict:
    """浏览器兜底通道的可用性：不启动浏览器，只看配置与 profile 是否存在。"""
    try:
        from . import web_sender
        config = web_sender.load_config()
        sender = web_sender.WebSender(config)
        available, reason = sender.available()
        return {
            "enabled": config["enabled"],
            "tenant": config["tenant"],
            "cdp_url": config.get("cdp_url", ""),
            "headless": config["headless"],
            "allow": config["allow"],
            "available": available,
            "reason": reason,
            "logged_in": os.path.exists(os.path.join(config["profile"], "Default", "Network", "Cookies")),
            "last": [
                {"chat": key[0], "status": value[1].status, "detail": value[1].detail,
                 "at": round(value[0])}
                for key, value in list(web_sender._RECENT.items())[-5:]  # noqa: SLF001
            ],
        }
    except Exception as exc:
        return {"enabled": False, "available": False, "reason": f"读取失败：{exc}", "last": []}


def conversations_payload(service: Any) -> dict:
    if service is None:
        return {"items": []}
    raw = service.runtime.sessions._store.read().get("sessions") or {}  # noqa: SLF001
    items = [
        {"key": key, "session_id": value.get("session_id"), "title": value.get("title"),
         "principal": value.get("principal"), "last_used": value.get("last_used"),
         "kind": value.get("kind") or "p2p",
         "chat_id": key.rsplit(":", 1)[-1] if key.count(":") >= 2 else "",
         "identity": "user" if ":user:" in key else "bot",
         "chat_name": value.get("chat_name") or ""}
        for key, value in raw.items() if isinstance(value, dict)
    ]
    items.sort(key=lambda item: item.get("last_used") or 0, reverse=True)
    return {"items": items[:50]}


def list_models() -> list[dict]:
    import json
    from pathlib import Path

    from . import paths

    path = Path(paths.PROJECT_ROOT) / ".config" / "model_profiles.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    items = raw if isinstance(raw, list) else (raw.get("profiles") or list(raw.values()))
    rows = []
    for item in items:
        if not isinstance(item, dict) or not item.get("id"):
            continue
        if item.get("enabled") is False:
            continue
        rows.append({"id": str(item["id"]), "name": str(item.get("name") or item.get("model") or item["id"])})
    return rows


def host_workspace() -> str:
    try:
        from agent_harness import WORK_DIR  # type: ignore

        return str(WORK_DIR)
    except Exception:
        return ""
