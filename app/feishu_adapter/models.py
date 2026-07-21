from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FeishuInboundMessage:
    message_id: str
    chat_id: str
    chat_type: str
    sender_open_id: str
    sender_union_id: str
    sender_type: str
    message_type: str
    text: str
    thread_id: str = ""
    parent_id: str = ""
    root_id: str = ""
    mentioned: bool = False

    @property
    def is_group(self) -> bool:
        return self.chat_type != "p2p"

    def conversation_key(self, session_scope: str = "chat") -> str:
        if not self.is_group:
            identity = self.sender_union_id or self.sender_open_id
            return f"p2p:{identity}"
        if session_scope == "thread" and self.thread_id:
            return f"thread:{self.thread_id}"
        return f"chat:{self.chat_id}"


def _attr(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _parse_text_content(raw_content: Any, message_type: str) -> str:
    if isinstance(raw_content, dict):
        payload = raw_content
    else:
        try:
            payload = json.loads(str(raw_content or "{}"))
        except (TypeError, json.JSONDecodeError):
            payload = {}
    if message_type == "text":
        return str(payload.get("text") or "").strip()
    if message_type == "post":
        # Keep a conservative plain-text fallback for rich posts. Media is a
        # later capability and should never be silently represented as a path.
        locale = payload.get("zh_cn") or payload.get("en_us") or next(
            (value for value in payload.values() if isinstance(value, dict)), {}
        )
        lines = []
        title = str((locale or {}).get("title") or "").strip()
        if title:
            lines.append(title)
        for row in (locale or {}).get("content") or []:
            parts = []
            for item in row if isinstance(row, list) else []:
                if isinstance(item, dict) and item.get("tag") in {"text", "a", "at"}:
                    text = str(item.get("text") or item.get("user_name") or "").strip()
                    if text:
                        parts.append(text)
            if parts:
                lines.append("".join(parts))
        return "\n".join(lines).strip()
    return ""


def parse_message_event(data: Any) -> FeishuInboundMessage:
    event = _attr(data, "event", data)
    message = _attr(event, "message")
    sender = _attr(event, "sender")
    if message is None or sender is None:
        raise ValueError("event does not contain sender and message")
    sender_id = _attr(sender, "sender_id", {})
    message_type = str(_attr(message, "message_type", "") or "").strip()
    raw_content = _attr(message, "content", "")
    mentions = _attr(message, "mentions", []) or []
    text = _parse_text_content(raw_content, message_type)
    mentioned = bool(mentions)
    for mention in mentions:
        key = str(_attr(mention, "key", "") or "").strip()
        name = str(_attr(mention, "name", "") or "").strip()
        if key:
            text = text.replace(key, " ")
        if name:
            text = text.replace(f"@{name}", " ")
    text = " ".join(text.split()) if "\n" not in text else "\n".join(
        " ".join(line.split()) for line in text.splitlines()
    ).strip()
    return FeishuInboundMessage(
        message_id=str(_attr(message, "message_id", "") or "").strip(),
        chat_id=str(_attr(message, "chat_id", "") or "").strip(),
        chat_type=str(_attr(message, "chat_type", "p2p") or "p2p").strip(),
        sender_open_id=str(_attr(sender_id, "open_id", "") or "").strip(),
        sender_union_id=str(_attr(sender_id, "union_id", "") or "").strip(),
        sender_type=str(_attr(sender, "sender_type", "user") or "user").strip(),
        message_type=message_type,
        text=text,
        thread_id=str(_attr(message, "thread_id", "") or "").strip(),
        parent_id=str(_attr(message, "parent_id", "") or "").strip(),
        root_id=str(_attr(message, "root_id", "") or "").strip(),
        mentioned=mentioned,
    )
