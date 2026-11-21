"""准入与定档：先确认通道开着，再判身份，最后按四轴定档。

与手册一致的三点：
  * **不裁剪工具**：这里只产出身份与档位，工具由宿主在执行层按当轮身份拒绝；
  * **拒绝文案不列清单**：只说"本轮未执行"，具体能干什么让模型去问 `tool_status`；
  * **不做白名单以外的一刀切**：私聊按 private 档（3），群里按 group 档（2），
    只有身份确实无法判定时才是 stranger（1，等于没有工具）。
"""
from __future__ import annotations

from dataclasses import dataclass

from .levels import Axes, axes_for, classify, normalize_level
from .models import Inbound


@dataclass(frozen=True)
class Identity:
    level: str
    subject: str
    channel: str
    axes: Axes


@dataclass(frozen=True)
class Decision:
    ok: bool
    reason: str = ""
    identity: Identity | None = None

    @classmethod
    def deny(cls, reason: str) -> "Decision":
        return cls(ok=False, reason=reason)

    @property
    def level(self) -> str:
        return self.identity.level if self.identity else "stranger"

    @property
    def tools_axis(self) -> int:
        return self.identity.axes.tools if self.identity else 1


class Admission:
    def __init__(
        self,
        *,
        enabled_channels: set[str] | None = None,
        allowed_principals: set[str] | None = None,
        allowed_groups: set[str] | None = None,
        group_members: dict[str, int] | None = None,
        channel_of_principal: dict[str, str] | None = None,
    ) -> None:
        # None = 不过滤通道；空集合 = 一个都没开（必须拒绝，不能退化成全放开）
        self.enabled_channels = None if enabled_channels is None else set(enabled_channels)
        self.allowed_principals = set(allowed_principals or ())
        self.allowed_groups = set(allowed_groups or ())
        self.group_members = dict(group_members or {})
        self.channel_of_principal = dict(channel_of_principal or {})

    def check(self, inbound: Inbound) -> Decision:
        name = inbound.channel.channel
        if self.enabled_channels is not None and name not in self.enabled_channels:
            return Decision.deny(f"通道未启用：{name}")

        principal = inbound.sender.key()
        chat = inbound.conversation.chat_id
        is_private = inbound.conversation.kind == "p2p"
        level = classify(
            whitelisted=principal in self.allowed_principals or inbound.sender.user_id in self.allowed_principals,
            is_private=is_private,
            members=None if is_private else self.group_members.get(chat),
            whitelisted_group=(not is_private) and chat in self.allowed_groups,
        )
        identity = Identity(
            level=normalize_level(level),
            subject=principal,
            channel=name,
            axes=axes_for(level),
        )
        return Decision(ok=True, identity=identity)

    # ------------------------------------------------------------------ 文案
    @staticmethod
    def refusal_text(decision: Decision) -> str:
        """拒绝/降级文案：不列可用工具清单，只指向 tool_status。"""
        if decision.ok:
            return ""
        return f"这条消息没有处理：{decision.reason}。"
