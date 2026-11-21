"""发送失败分类：把平台错误码翻译成可执行建议。

规则：状态只有三种，unknown 一律不重试。
"""
from __future__ import annotations

from typing import Literal

Status = Literal["sent", "unknown", "failed"]

# 码 → (状态, 建议)
_ERRORS: dict[str, tuple[Status, str]] = {
    "230002": ("failed", "机器人不在该会话，改用账户主身份或拉机器人进群"),
    "230013": ("failed", "目标不在应用可用范围，去开发者后台补可用范围"),
    "230020": ("failed", "触发限频，稍后再发"),
    "230027": ("failed", "外部会话受限；跨租户单聊请启用浏览器兜底"),
    "230038": ("failed", "跨租户单聊禁止走 API；启用浏览器兜底"),
    "230053": ("failed", "对方已停止接收机器人消息"),
    "230001": ("failed", "参数不合法，检查接收者 ID 与消息类型"),
}


def classify(detail: str) -> tuple[Status, str]:
    text = str(detail or "")
    for code, (status, hint) in _ERRORS.items():
        if code in text:
            return status, hint
    lowered = text.lower()
    if "timeout" in lowered or "timed out" in lowered or "unknown" in lowered:
        return "unknown", "结果未知，先回查再决定"
    return "failed", ""


def describe(detail: str) -> str:
    """给日志/控制台用的一行描述：原文 + 建议。"""
    status, hint = classify(detail)
    if not hint:
        return f"{status}: {detail}" if detail else status
    return f"{status}: {detail}｜建议：{hint}" if detail else f"{status}｜建议：{hint}"
