"""飞书通道：解析 + 配置 + 通道装配。

长连接不放宿主进程里，交给 `feishu_worker` 子进程（原因见该文件顶部注释）。
这里只保留纯函数（事件解析）与装配逻辑，方便单测。
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from typing import Any

from ..models import Capabilities, ChannelId, ConversationRef, Inbound, Principal

PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------- 配置
@dataclass
class FeishuSettings:
    enabled: bool = False
    app_id: str = ""
    app_secret: str = ""
    group_require_mention: bool = True
    session_scope: str = "chat"
    allowed_open_ids: frozenset[str] = frozenset()
    allowed_chat_ids: frozenset[str] = frozenset()

    @classmethod
    def from_env(cls) -> "FeishuSettings":
        def flag(name: str, default: bool) -> bool:
            raw = os.getenv(name)
            return default if raw is None else raw.strip().lower() in {"1", "true", "yes", "on"}

        def csv(name: str) -> frozenset[str]:
            return frozenset(x.strip() for x in os.getenv(name, "").split(",") if x.strip())

        return cls(
            enabled=flag("FEISHU_ENABLED", False),
            app_id=os.getenv("FEISHU_APP_ID", "").strip(),
            app_secret=os.getenv("FEISHU_APP_SECRET", "").strip(),
            group_require_mention=flag("FEISHU_GROUP_REQUIRE_MENTION", True),
            session_scope=(os.getenv("FEISHU_SESSION_SCOPE", "chat").strip() or "chat"),
            allowed_open_ids=csv("FEISHU_ALLOWED_OPEN_IDS"),
            allowed_chat_ids=csv("FEISHU_ALLOWED_CHAT_IDS"),
        )

    def validate(self) -> None:
        missing = [name for name, value in (("FEISHU_APP_ID", self.app_id), ("FEISHU_APP_SECRET", self.app_secret)) if not value]
        if missing:
            raise ValueError("飞书通道缺少配置：" + ", ".join(missing))


# ---------------------------------------------------------------- 事件解析（纯函数）
def _attr(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _text_of(raw: Any, message_type: str) -> str:
    payload = raw if isinstance(raw, dict) else {}
    if not payload:
        try:
            payload = json.loads(str(raw or "{}"))
        except (TypeError, json.JSONDecodeError):
            payload = {}
    if message_type == "text":
        return str(payload.get("text") or "").strip()
    if message_type == "post":
        locale = payload.get("zh_cn") or payload.get("en_us") or next(
            (v for v in payload.values() if isinstance(v, dict)), {}
        )
        lines: list[str] = []
        title = str((locale or {}).get("title") or "").strip()
        if title:
            lines.append(title)
        for row in (locale or {}).get("content") or []:
            parts = [
                str(item.get("text") or item.get("user_name") or "").strip()
                for item in (row if isinstance(row, list) else [])
                if isinstance(item, dict) and item.get("tag") in {"text", "a", "at"}
            ]
            joined = "".join(p for p in parts if p)
            if joined:
                lines.append(joined)
        return "\n".join(lines).strip()
    return ""


def parse_event(payload: Any) -> Inbound:
    """把飞书事件 JSON 变成统一 Inbound。字段口径与 feishu-transport 一致。"""
    event = _attr(payload, "event", payload)
    message = _attr(event, "message")
    sender = _attr(event, "sender")
    if message is None or sender is None:
        raise ValueError("事件里缺少 sender/message")
    sender_id = _attr(sender, "sender_id", {}) or {}
    message_type = str(_attr(message, "message_type", "") or "")
    text = _text_of(_attr(message, "content", ""), message_type)
    mentions = _attr(message, "mentions", []) or []
    for mention in mentions:
        key = str(_attr(mention, "key", "") or "")
        name = str(_attr(mention, "name", "") or "")
        if key:
            text = text.replace(key, " ")
        if name:
            text = text.replace(f"@{name}", " ")
    text = "\n".join(" ".join(line.split()) for line in text.splitlines()).strip()

    chat_id = str(_attr(message, "chat_id", "") or "")
    chat_type = str(_attr(message, "chat_type", "p2p") or "p2p")
    thread_id = str(_attr(message, "thread_id", "") or "") or None
    open_id = str(_attr(sender_id, "open_id", "") or "")
    union_id = str(_attr(sender_id, "union_id", "") or "")
    return Inbound(
        channel=ChannelId("feishu", "default"),
        conversation=ConversationRef(chat_id=chat_id, kind="group" if chat_type != "p2p" else "p2p", thread_id=thread_id),
        sender=Principal("feishu", union_id or open_id or str(_attr(sender, "sender_id", "") or "")),
        message_id=str(_attr(message, "message_id", "") or ""),
        text=text,
        reply_to=str(_attr(message, "parent_id", "") or "") or None,
        raw={"message_type": message_type, "mentions": bool(mentions),
             "sender_type": str(_attr(sender, "sender_type", "") or "")},
    )


CAPABILITIES = Capabilities(
    text=True, markdown=True,
    media_in=frozenset({"image", "file"}), media_out=frozenset(),
    threads=True, mentions=True, buttons=False, edit_message=False,
    proactive=True, group=True, quota="rate",
)


def build_channel(settings: FeishuSettings | None = None):
    """装配成子进程通道：连接与重连都在 worker 里，宿主只收发 JSON 行。"""
    from .sidecar import SidecarChannel, SidecarSpec

    settings = settings or FeishuSettings.from_env()
    env = {
        "PYTHONPATH": PLUGIN_ROOT,
        "FEISHU_APP_ID": settings.app_id,
        "FEISHU_APP_SECRET": settings.app_secret,
        "FEISHU_GROUP_REQUIRE_MENTION": "1" if settings.group_require_mention else "0",
    }
    return SidecarChannel(
        SidecarSpec(
            name="feishu",
            # 直接跑脚本而不是 -m：这台机器的 Python 不把 cwd 加进 sys.path，
            # `-m` 会报 ModuleNotFoundError；脚本模式由 worker 自己补路径。
            command=[sys.executable, "-u",
                     os.path.join(PLUGIN_ROOT, "sugar_assistant", "channels", "feishu_worker.py")],
            env=env,
            capabilities=CAPABILITIES,
            send_timeout=30.0,
        )
    )


def split_reply(text: str, limit: int = 3500) -> list[str]:
    """把长回复切成飞书能接受的多条：段落优先，超长段落硬切。"""
    body = str(text or "")
    if limit <= 0:
        limit = 3500
    if len(body) <= limit:
        return [body]
    chunks: list[str] = []
    buffer = ""
    for line in body.split("\n"):
        piece = line + "\n"
        if len(buffer) + len(piece) > limit and buffer:
            chunks.append(buffer.rstrip("\n"))
            buffer = ""
        while len(piece) > limit:
            chunks.append(piece[:limit])
            piece = piece[limit:]
        buffer += piece
    if buffer.strip():
        chunks.append(buffer.rstrip("\n"))
    return chunks or [body[:limit]]
