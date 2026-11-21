"""假通道：第一个必须实现的 Adapter。

用它可以把 25 条一致性用例跑在真实逻辑上：不需要任何凭据、不需要网络，
但 Core 走的还是生产那条路（准入 → 幂等 → 会话 → 投递）。
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field

from ..models import Capabilities, Delivery, Inbound, SendOutcome, SendResult
from .base import InboundSink


@dataclass
class FakeChannel:
    id: str = "fake"
    capabilities: Capabilities = field(
        default_factory=lambda: Capabilities(
            text=True,
            markdown=True,
            media_in=frozenset({"image", "file"}),
            media_out=frozenset({"image", "file"}),
            threads=True,
            buttons=True,
            edit_message=True,
            proactive=True,
            group=True,
            quota="none",
        )
    )
    outbox: list[Delivery] = field(default_factory=list)
    sent_texts: list[str] = field(default_factory=list)
    failures: int = 0          # 接下来多少次 send 会失败
    unreachable: int = 0       # 接下来多少次 send 返回"不可达"
    verify_ok: bool = False    # verify 是否谎报成功（用来测回读兜底）
    started: bool = False
    _sink: InboundSink | None = None
    _seq: itertools.count = field(default_factory=lambda: itertools.count(1))

    async def start(self, sink: InboundSink) -> None:
        self._sink = sink
        self.started = True

    async def stop(self) -> None:
        self.started = False
        self._sink = None

    def send(self, delivery: Delivery) -> SendResult:
        if self.failures > 0:
            self.failures -= 1
            return SendResult(SendOutcome.UNREACHABLE, "注入失败")
        self.outbox.append(delivery)
        self.sent_texts.append(delivery.text)
        return SendResult(SendOutcome.ACKED)

    def verify(self, delivery: Delivery) -> SendResult:
        if self.verify_ok:
            return SendResult(SendOutcome.READBACK, "回读命中")
        return SendResult(SendOutcome.UNREACHABLE, "回读未命中")

    def health(self) -> dict:
        return {"channel": self.id, "started": self.started, "sent": len(self.outbox)}

    # ------------------------------------------------------------------ 测试助手
    def next_message_id(self) -> str:
        return f"fake-{next(self._seq)}"


def inbound(
    text: str,
    *,
    peer: str = "u-owner",
    chat: str = "c-1",
    kind: str = "p2p",
    channel: str = "fake",
    message_id: str | None = None,
    thread: str | None = None,
) -> Inbound:
    from ..models import ChannelId, ConversationRef, Principal

    return Inbound(
        channel=ChannelId(channel),
        conversation=ConversationRef(chat_id=chat, kind=kind, thread_id=thread),  # type: ignore[arg-type]
        sender=Principal(channel=channel, user_id=peer),
        message_id=message_id or f"m-{abs(hash((text, peer, chat))) % 10**8}",
        text=text,
    )
