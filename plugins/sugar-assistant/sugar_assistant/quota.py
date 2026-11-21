"""配额模型：把「微信 10 条窗口」抽成通用能力。

三种实现共用一张表：
    none      不限
    window10  每个 context token 一个窗口（微信），第 8 条预警
    rate      滑动窗口（飞书 / QQ 主动消息），按分钟计数
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Charge:
    used: int
    limit: int
    warn: bool
    exhausted: bool
    hint: str = ""


class QuotaModel:
    kind: Literal["none", "window10", "rate"] = "none"

    def charge(self, conversation_key: str, token: str | None = None) -> Charge:
        raise NotImplementedError

    def reset(self, conversation_key: str | None = None) -> None:
        raise NotImplementedError


class NoQuota(QuotaModel):
    kind = "none"

    def charge(self, conversation_key: str, token: str | None = None) -> Charge:
        return Charge(used=0, limit=0, warn=False, exhausted=False)

    def reset(self, conversation_key: str | None = None) -> None:
        return None


class WindowQuota(QuotaModel):
    """按 token 切换窗口。微信侧：连续主动推送 10 条，第 8 条提醒续期。"""

    kind = "window10"

    def __init__(self, limit: int = 10, warn_at: int | None = None) -> None:
        self.limit = max(1, int(limit))
        self.warn_at = warn_at if warn_at is not None else max(1, self.limit - 2)
        self._state: dict[str, dict] = {}

    def charge(self, conversation_key: str, token: str | None = None) -> Charge:
        entry = self._state.setdefault(conversation_key, {"token": token, "used": 0, "warned": False})
        if token is not None and token != entry.get("token"):
            entry.update(token=token, used=0, warned=False)
        entry["used"] = int(entry.get("used", 0)) + 1
        used = entry["used"]
        warn = False
        if used >= self.warn_at and not entry.get("warned"):
            entry["warned"] = True
            warn = True
        exhausted = used >= self.limit
        hint = "通道快用完了，回我一句就能续期。" if exhausted else ""
        return Charge(used=used, limit=self.limit, warn=warn, exhausted=exhausted, hint=hint)

    def reset(self, conversation_key: str | None = None) -> None:
        if conversation_key is None:
            self._state.clear()
        else:
            self._state.pop(conversation_key, None)


class RateQuota(QuotaModel):
    """滑动窗口：一分钟内最多 per_minute 条，超了就不让 Core 继续推。"""

    kind = "rate"

    def __init__(self, per_minute: int = 30, window_seconds: float = 60.0, now=time.monotonic) -> None:
        self.per_minute = max(1, int(per_minute))
        self.window = float(window_seconds)
        self._now = now
        self._state: dict[str, list[float]] = {}

    def charge(self, conversation_key: str, token: str | None = None) -> Charge:
        now = self._now()
        stamps = [t for t in self._state.get(conversation_key, []) if now - t < self.window]
        stamps.append(now)
        self._state[conversation_key] = stamps
        used = len(stamps)
        warn = used >= max(1, self.per_minute - 2)
        exhausted = used > self.per_minute
        return Charge(used=used, limit=self.per_minute, warn=warn, exhausted=exhausted)

    def reset(self, conversation_key: str | None = None) -> None:
        if conversation_key is None:
            self._state.clear()
        else:
            self._state.pop(conversation_key, None)


def quota_for(kind: str, **options) -> QuotaModel:
    if kind == "window10":
        return WindowQuota(**options)
    if kind == "rate":
        return RateQuota(**options)
    return NoQuota()
