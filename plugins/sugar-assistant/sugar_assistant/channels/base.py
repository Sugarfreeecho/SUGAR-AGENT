"""Adapter 协议：每家 IM 只实现这 5 个方法 + 一张能力表。

Core 不允许出现 `if channel == "wechat"`；通道差异只能通过 `capabilities` 表达。
"""
from __future__ import annotations

from typing import Awaitable, Callable, Protocol

from ..models import Capabilities, Delivery, Inbound, SendResult

InboundSink = Callable[[Inbound], Awaitable[None]]


class ChannelAdapter(Protocol):
    id: str
    capabilities: Capabilities

    async def start(self, sink: InboundSink) -> None: ...
    async def stop(self) -> None: ...
    def send(self, delivery: Delivery) -> SendResult: ...
    def verify(self, delivery: Delivery) -> SendResult: ...
    def health(self) -> dict: ...


class AdapterError(RuntimeError):
    """通道层错误：带上通道名，便于 Core 直接写进审计。"""

    def __init__(self, channel: str, message: str) -> None:
        super().__init__(f"[{channel}] {message}")
        self.channel = channel
