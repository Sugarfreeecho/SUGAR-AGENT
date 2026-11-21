"""会话映射：把「哪个对话」映到「宿主里的哪个 session」。

三条硬规则：
  1. 主键用 `channel:account:chat[:thread]`，不用标题、不用人名；
  2. 会话本体在宿主，这里只存映射 —— 删掉映射不会丢对话；
  3. **会话配置只存名字/目录这类中性项**：权限按当轮身份现算，绝不写进会话
     （手册：`tools` / `read_only` 不进会话配置）。
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Protocol

# 会话归属固定为插件自身：bot/user 切换不改变归属，否则宿主判 another identity 而重建会话
OWNER_SUBJECT = "sugar-assistant:owner"

from .models import Inbound
from .storage import JsonStore


class HostPort(Protocol):
    """宿主能力的唯一入口；测试里可以整体替换。"""

    def create_session(self, *, title: str, subject: str = "", system_prompt: str = "",
                       shared: bool = False, work_dir: str = "", model_profile_id: str = "") -> str: ...
    def submit(self, session_id: str, text: str, *, op_id: str, actor: dict | None = None) -> None: ...
    def rename_session(self, session_id: str, title: str) -> None: ...
    def list_sessions(self) -> list[dict]: ...
    def interrupt(self, session_id: str) -> None: ...


@dataclass
class Binding:
    key: str
    session_id: str
    title: str
    principal: str
    created_at: float
    last_used: float
    kind: str = "p2p"
    chat_name: str = ""

    def to_json(self) -> dict:
        return {
            "session_id": self.session_id,
            "title": self.title,
            "principal": self.principal,
            "created_at": self.created_at,
            "last_used": self.last_used,
            "kind": self.kind,
            "chat_name": self.chat_name,
        }


class SessionMap:
    def __init__(self, store: JsonStore, host: HostPort, *, scope: str = "chat") -> None:
        self._store = store
        self._host = host
        self.scope = scope if scope in {"chat", "thread", "user"} else "chat"
        self.defaults: dict = {}

    # ------------------------------------------------------------------ 键
    def key_for(self, inbound: Inbound) -> str:
        channel = inbound.channel.channel
        account = inbound.channel.account
        # 飞书同一个 chat 无论用机器人还是本人身份收发，都必须是同一个对话、同一个会话
        if channel == "feishu" and account in {"user", "bot"}:
            account = "default"
        base = f"{channel}:{account}"
        if self.scope == "user":
            return f"{base}:user:{inbound.sender.user_id}"
        if self.scope == "thread" and inbound.conversation.thread_id:
            return f"{base}:{inbound.conversation.chat_id}#{inbound.conversation.thread_id}"
        return f"{base}:{inbound.conversation.chat_id}"

    # ------------------------------------------------------------------ 读
    def get(self, key: str) -> Binding | None:
        raw = (self._store.read().get("sessions") or {}).get(key)
        if not isinstance(raw, dict) or not raw.get("session_id"):
            return None
        return Binding(
            key=key,
            session_id=str(raw["session_id"]),
            title=str(raw.get("title") or ""),
            principal=str(raw.get("principal") or ""),
            created_at=float(raw.get("created_at") or 0),
            last_used=float(raw.get("last_used") or 0),
            kind=str(raw.get("kind") or "p2p"),
            chat_name=str(raw.get("chat_name") or ""),
        )

    def session_for_conversation(self, key: str) -> str | None:
        binding = self.get(key)
        return binding.session_id if binding else None

    def find_by_chat(self, chat_id: str) -> "Binding | None":
        """按 chat_id 找绑定（key 形如 channel:default:chat_id）。"""
        for key in (self._store.read().get("sessions") or {}):
            if str(key).endswith(f":{chat_id}"):
                return self.get(str(key))
        return None

    def conversations_for_session(self, session_id: str) -> list[str]:
        sessions = self._store.read().get("sessions") or {}
        return [key for key, raw in sessions.items() if isinstance(raw, dict) and raw.get("session_id") == session_id]

    def kind_of(self, key: str) -> str:
        binding = self.get(key)
        return binding.kind if binding else ""

    def current_conversation(self, session_id: str) -> str | None:
        """只返回**当前**绑定这条会话的那个对话（多对一时取最近使用的）。"""
        keys = self.conversations_for_session(session_id)
        if not keys:
            return None
        return max(keys, key=lambda k: self.get(k).last_used if self.get(k) else 0)

    # ------------------------------------------------------------------ 写
    def resolve(self, inbound: Inbound, *, title: str, system_prompt: str = "") -> tuple[Binding, bool]:
        """返回 (绑定, 是否新建)。新建时只给标题，不带任何权限项。"""
        key = self.key_for(inbound)
        existing = self.get(key)
        now = time.time()
        if existing is not None:
            if not self._host_session_alive(existing.session_id):
                binding = self._create(key, title or existing.title, inbound, now, system_prompt)
                return binding, True
            name = _chat_name(inbound)
            new_title = existing.title
            # runtime 传来的规范标题（小Sugar私聊 / 小Sugar群聊-尾号）优先，旧标题纠正
            if title and title.startswith("小Sugar") and title != existing.title:
                new_title = title
                rename = getattr(self._host, "rename_session", None)
                if callable(rename):
                    try:
                        rename(existing.session_id, title)
                    except Exception:
                        pass
            if (name and name != existing.chat_name) or new_title != existing.title:
                self._write(key, Binding(existing.key, existing.session_id, new_title,
                                         existing.principal, existing.created_at, now,
                                         existing.kind, name or existing.chat_name))
                existing = self.get(key) or existing
            self._touch(key, now)
            return existing, False
        binding = self._create(key, title, inbound, now, system_prompt)
        return binding, True

    def bind(self, key: str, session_id: str, *, title: str, principal: str) -> Binding:
        now = time.time()
        binding = Binding(key, session_id, title, principal, now, now)
        self._write(key, binding)
        return binding

    def drop(self, key: str) -> None:
        def mutate(data):
            sessions = data.setdefault("sessions", {})
            sessions.pop(key, None)
            return data

        self._store.update(mutate)

    # ------------------------------------------------------------------ 内部
    def _create(self, key: str, title: str, inbound: Inbound, now: float, system_prompt: str = "") -> Binding:
        resolved_title = (title or inbound.text or "新对话").strip()[:24] or "新对话"
        workspace = (self.defaults.get("workspace") or {})
        model = (self.defaults.get("model") or {})
        session_id = self._host.create_session(title=resolved_title, subject=OWNER_SUBJECT,
                                               system_prompt=system_prompt,
                                               shared=inbound.conversation.kind == "group",
                                               work_dir=str(workspace.get("path") or "") if workspace.get("mode") == "manual" else "",
                                               model_profile_id=str(model.get("profile_id") or "") if model.get("mode") == "manual" else "")
        binding = Binding(key, session_id, resolved_title, inbound.sender.key(), now, now,
                          inbound.conversation.kind, _chat_name(inbound))
        self._write(key, binding)
        return binding

    def _write(self, key: str, binding: Binding) -> None:
        def mutate(data):
            data.setdefault("sessions", {})[key] = binding.to_json()
            return data

        self._store.update(mutate)

    def _touch(self, key: str, now: float) -> None:
        def mutate(data):
            raw = (data.get("sessions") or {}).get(key)
            if isinstance(raw, dict):
                raw["last_used"] = now
            return data

        self._store.update(mutate)

    def _host_session_alive(self, session_id: str) -> bool:
        try:
            sessions = self._host.list_sessions()
        except Exception:
            return True  # 查不到不等于死了：宁可沿用，也不要每轮重建会话
        if not sessions:
            return True
        for item in sessions:
            if str(item.get("session_id") or item.get("id") or "") == session_id:
                return True
        return False


def _chat_name(inbound: Inbound) -> str:
    raw = inbound.raw
    if isinstance(raw, dict):
        return str(raw.get("chatName") or "")[:60]
    return ""
