"""统一消息模型：进站 Inbound、出站 Delivery、通道能力表。"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal

ChatKind = Literal["p2p", "group"]
DeliveryKind = Literal["progress", "final", "approval", "error", "prompt"]


@dataclass(frozen=True)
class ChannelId:
    """通道 + 账号。同一家 IM 可以并存多个 bot。"""

    channel: str
    account: str = "default"

    def __str__(self) -> str:
        return f"{self.channel}:{self.account}"


@dataclass(frozen=True)
class ConversationRef:
    chat_id: str
    kind: ChatKind = "p2p"
    thread_id: str | None = None

    def key(self) -> str:
        return f"{self.chat_id}#{self.thread_id}" if self.thread_id else self.chat_id


@dataclass(frozen=True)
class Principal:
    channel: str
    user_id: str
    display: str = ""

    def key(self) -> str:
        return f"{self.channel}:{self.user_id}"


@dataclass
class Attachment:
    kind: Literal["image", "file", "voice", "video"]
    path: str
    size: int = 0


@dataclass
class Inbound:
    channel: ChannelId
    conversation: ConversationRef
    sender: Principal
    message_id: str
    text: str = ""
    attachments: list[Attachment] = field(default_factory=list)
    reply_to: str | None = None
    received_at: float = field(default_factory=time.time)
    raw: Any = None

    def dedupe_key(self) -> str:
        """幂等键：同一通同一条消息必须落在这里，重投递也只会得到同一个 op。"""
        return f"{self.channel.channel}:{self.channel.account}:{self.message_id}"


class SendOutcome(str, Enum):
    ACKED = "acked"            # 平台说成功
    READBACK = "readback"      # 回读确认成功
    UNREACHABLE = "unreachable"  # 无法确认：不重试，交给用户反馈


@dataclass
class SendResult:
    outcome: SendOutcome = SendOutcome.ACKED
    detail: str = ""


@dataclass(frozen=True)
class Capabilities:
    """通道能力表。Core 只根据它降级，不允许写 if channel == "wechat"。"""

    text: bool = True
    markdown: bool = False
    media_in: frozenset[str] = frozenset()
    media_out: frozenset[str] = frozenset()
    threads: bool = False
    mentions: bool = False
    buttons: bool = False
    edit_message: bool = False
    proactive: bool = True
    group: bool = False
    quota: Literal["none", "window10", "rate"] = "none"


@dataclass
class Delivery:
    id: str
    channel: ChannelId
    conversation: ConversationRef
    kind: DeliveryKind = "final"
    text: str = ""
    attachments: list[Attachment] = field(default_factory=list)
    reply_to: str | None = None
    idempotency_key: str = ""
    meta: dict[str, Any] = field(default_factory=dict)
    attempts: int = 0
    status: str = "queued"  # queued | acked | readback | unreachable
    last_error: str = ""
