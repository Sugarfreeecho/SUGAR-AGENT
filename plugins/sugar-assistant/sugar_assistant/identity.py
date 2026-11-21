"""发送/接收身份开关：bot（助手账号） / user（用户自己的账号）。

bot：收发都走应用机器人（当前形态）。
user：收消息轮询用户账号可见的会话，回复也以用户身份发出；其余行为保持一致。
账户主的完整交互（代发范围、审批归属）后续单独设计。
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from .paths import data_dir

_MODES = {"bot", "user"}


def _path() -> Path:
    return Path(data_dir()) / "identity.json"


def _read() -> dict:
    try:
        return json.loads(_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def current() -> str:
    mode = str(_read().get("mode") or os.getenv("SUGAR_IDENTITY", "bot"))
    return mode if mode in _MODES else "bot"


def chats() -> list[str]:
    """user 身份需要轮询的会话（飞书没有"列出我全部会话"的接口，只能显式给）。"""
    return [str(item) for item in (_read().get("chats") or []) if str(item).strip()]


def set_mode(mode: str, *, chats: list[str] | None = None) -> dict:
    value = str(mode or "").strip().lower()
    if value not in _MODES:
        raise ValueError(f"identity 只能是 bot 或 user，收到：{mode}")
    payload = _read()
    previous = str(payload.get("mode") or "bot")
    payload["mode"] = value
    if chats is not None:
        payload["chats"] = [str(item).strip() for item in chats if str(item).strip()]
    _path().parent.mkdir(parents=True, exist_ok=True)
    _path().write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"mode": value, "chats": payload.get("chats") or [], "changed": previous != value}


def request_reload(delay: float = 1.5) -> None:
    """切换身份后重载插件：换掉接收端、清空旧模式的待发队列。

    只写文件不重载会留下"新模式发送 + 旧模式接收"的混合状态，之前的报错都出在这。
    """
    import threading
    import urllib.request

    def _fire() -> None:
        import time as _time
        _time.sleep(delay)
        url = os.getenv("SUGAR_RELOAD_URL", "http://127.0.0.1:8192/api/extensions/reload")
        try:
            request = urllib.request.Request(url, data=b"{}", method="POST",
                                             headers={"Content-Type": "application/json"})
            urllib.request.urlopen(request, timeout=30).read()
        except Exception:
            pass

    threading.Thread(target=_fire, name="sugar-identity-reload", daemon=True).start()


def add_chat(chat_id: str) -> bool:
    """自动发现的新会话写入列表；返回是否新增。"""
    value = str(chat_id or "").strip()
    if not value:
        return False
    payload = _read()
    chats = [str(item) for item in (payload.get("chats") or [])]
    if value in chats:
        return False
    chats.append(value)
    payload["chats"] = chats
    _path().parent.mkdir(parents=True, exist_ok=True)
    _path().write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return True
