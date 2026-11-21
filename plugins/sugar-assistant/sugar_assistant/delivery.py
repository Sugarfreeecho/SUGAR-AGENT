"""出站投递：重试、三态确认、幂等键。

三条规则（对应设计稿 §6）：
  * 幂等键重试不变，重试只影响送达，不影响执行；
  * `unreachable` **不重试** —— 宁可让用户说"没收到"，也不要重复轰炸；
  * 先写后回：调用方必须先确认完成状态，再把"已收到"回给用户。
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Iterable, Protocol

from .models import Delivery, SendOutcome, SendResult


class Sender(Protocol):
    def send(self, delivery: Delivery) -> SendResult: ...
    def verify(self, delivery: Delivery) -> SendResult: ...


@dataclass
class PumpReport:
    sent: int = 0
    retried: int = 0
    unreachable: int = 0
    skipped: int = 0


class DeliveryQueue:
    def __init__(
        self,
        sender_for: Callable[[str], Sender],
        *,
        max_attempts: int = 3,
        backoff: Iterable[float] = (0.5, 2.0, 8.0),
        sleeper: Callable[[float], None] = time.sleep,
        readback: bool = True,
    ) -> None:
        self._sender_for = sender_for
        self.max_attempts = max(1, int(max_attempts))
        self.backoff = list(backoff) or [0.0]
        self._sleep = sleeper
        self.readback = readback
        self._queue: list[Delivery] = []
        self._acked: set[str] = set()

    # ------------------------------------------------------------------ 入队
    def enqueue(self, delivery: Delivery) -> Delivery:
        if delivery.idempotency_key and delivery.idempotency_key in self._acked:
            delivery.status = "acked"
            return delivery
        self._queue.append(delivery)
        return delivery

    @property
    def pending(self) -> list[Delivery]:
        return [d for d in self._queue if d.status == "queued"]

    # ------------------------------------------------------------------ 投递
    def pump(self, *, limit: int = 20) -> PumpReport:
        report = PumpReport()
        processed = 0
        while self._queue and processed < limit:
            delivery = self._queue.pop(0)
            processed += 1
            if delivery.status != "queued":
                continue
            if delivery.idempotency_key and delivery.idempotency_key in self._acked:
                delivery.status = "acked"
                report.skipped += 1
                continue
            sender = self._sender_for(delivery.channel.channel)
            self._attempt(sender, delivery, report)
        return report

    def _attempt(self, sender: Sender, delivery: Delivery, report: PumpReport) -> None:
        while delivery.attempts < self.max_attempts:
            delivery.attempts += 1
            try:
                result = sender.send(delivery)
            except Exception as exc:  # 网络异常也走同一条重试路径
                delivery.last_error = f"{type(exc).__name__}: {exc}"
                result = SendResult(SendOutcome.UNREACHABLE, delivery.last_error)

            if result.outcome in {SendOutcome.ACKED, SendOutcome.READBACK}:
                delivery.status = result.outcome.value
                if delivery.idempotency_key:
                    self._acked.add(delivery.idempotency_key)
                report.sent += 1
                return

            if result.outcome is SendOutcome.UNREACHABLE and self.readback:
                # 先回读确认，再决定要不要重试：有些平台失败其实已经送达
                try:
                    verified = sender.verify(delivery)
                except Exception:
                    verified = SendResult(SendOutcome.UNREACHABLE)
                if verified.outcome in {SendOutcome.ACKED, SendOutcome.READBACK}:
                    delivery.status = "readback"
                    if delivery.idempotency_key:
                        self._acked.add(delivery.idempotency_key)
                    report.sent += 1
                    return

            delivery.last_error = result.detail or "发送失败"
            if delivery.attempts >= self.max_attempts:
                break
            delay = self.backoff[min(delivery.attempts - 1, len(self.backoff) - 1)]
            report.retried += 1
            if delay:
                self._sleep(delay)

        # 用尽重试：标记为不可达，不再重投
        delivery.status = "unreachable"
        report.unreachable += 1

    # ------------------------------------------------------------------ 状态
    def stats(self) -> dict[str, int]:
        result: dict[str, int] = {}
        for delivery in self._queue:
            result[delivery.status] = result.get(delivery.status, 0) + 1
        return result
