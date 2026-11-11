"""Identity-based turn permissions.

权限只绑身份、不绑会话：每次工具调用或控制调用都按"当轮发言者"的身份现算，
会话元数据不再保存 tools / read_only 这类权限项。

四轴（各 1-4 档）：会话控制、工具集、作用域、访问目录。
"""
from __future__ import annotations

import threading
from dataclasses import dataclass

OWNER = "owner"
WHITELIST = "whitelist"
PRIVATE = "private"
GROUP = "group"
STRANGER = "stranger"

LEVELS = (OWNER, WHITELIST, PRIVATE, GROUP, STRANGER)

_ALIASES = {
    "owner": OWNER, "host": OWNER, "admin": OWNER, "机主": OWNER,
    "whitelist": WHITELIST, "allow": WHITELIST, "白名单": WHITELIST,
    "private": PRIVATE, "dm": PRIVATE, "small": PRIVATE, "私聊": PRIVATE, "小群": PRIVATE,
    "group": GROUP, "chat": GROUP, "群聊": GROUP,
    "stranger": STRANGER, "guest": STRANGER, "unknown": STRANGER, "陌生": STRANGER,
}


@dataclass(frozen=True)
class Axes:
    control: int
    tools: int
    scope: int
    directory: int

    def as_dict(self) -> dict[str, int]:
        return {"control": self.control, "tools": self.tools, "scope": self.scope, "directory": self.directory}


MATRIX: dict[str, Axes] = {
    OWNER: Axes(4, 4, 4, 4),
    WHITELIST: Axes(3, 3, 3, 3),
    PRIVATE: Axes(3, 3, 2, 2),
    GROUP: Axes(2, 2, 2, 2),
    STRANGER: Axes(1, 1, 1, 1),
}

# 2 档"只读工具"的允许面：只列真正不产生副作用的内置工具。
READ_TOOLS = frozenset({
    "read_file", "ls", "glob", "grep", "web_search", "web_fetch",
    "tool_search", "tool_describe", "show_user", "ask_user",
    "history_context", "scheduled_tasks", "agent_browser_get_context",
})

# 控制面方法 → 所需"会话控制"档；未列出的方法按 4 档处理（fail closed）。
CONTROL_LEVELS: dict[str, int] = {
    "session.list": 1, "session.get": 1, "session.history": 1, "session.search": 1,
    "session.attach": 1, "session.detach": 1, "session.config.get": 1,
    "session.config.preview": 1, "system.health": 1, "auth.status": 1,
    "tool_catalog.list": 1, "tool_catalog.describe": 1, "operation.get": 1,
    "session.send": 2, "session.send_batch": 2, "session.steer": 2,
    "session.steer.cancel": 2, "session.interrupt": 2, "session.notice": 2,
    "session.archive": 2, "operation.cancel": 2,
    "session.create": 3, "session.fork": 3, "session.update": 3, "session.delete": 3,
    "session.export": 3, "session.import": 3, "session.continue": 3, "session.recover": 3,
    "session.config.update": 4, "approval.resolve": 4, "approval.list": 4,
    "device.list": 4, "device.revoke": 4, "audit.list": 4, "operation.wait": 1,
}

_ACTORS: dict[str, dict] = {}
_LOCK = threading.RLock()


def normalize_level(value: object, *, default: str = STRANGER) -> str:
    raw = str(value or "").strip().lower()
    return _ALIASES.get(raw, default)


def axes_for(level: object) -> Axes:
    return MATRIX[normalize_level(level)]


def describe(level: object) -> dict:
    normalized = normalize_level(level)
    return {"level": normalized, **axes_for(normalized).as_dict()}


def resolve_level(
    *,
    admin: bool = False,
    channel: str = "",
    whitelisted: bool = False,
    whitelisted_group: bool = False,
    group_size: int | None = None,
    direct: bool = False,
) -> str:
    """把一次外来触发折算成用户身份。

    channel 为空表示本机入口（WebUI/桌面壳/本机 CLI/本机扩展），直接落机主。
    群成员数拿不到（None）时按"≥5"处理，不降级为私聊。
    """
    if admin:
        return OWNER
    if not str(channel or "").strip():
        return OWNER
    if whitelisted:
        return WHITELIST
    if whitelisted_group:
        return PRIVATE
    if direct:
        return PRIVATE
    if group_size is not None and int(group_size) < 5:
        return PRIVATE
    return GROUP


def actor_key(*, level: str, subject: str = "", channel: str = "") -> str:
    """同一身份 + 同一主体的连续提问才允许合并成一轮。"""
    return "|".join((normalize_level(level), str(channel or ""), str(subject or "")))


def set_turn_actor(session_id: str, *, level: object, subject: str = "", channel: str = "", label: str = "") -> dict:
    actor = {
        "level": normalize_level(level),
        "subject": str(subject or ""),
        "channel": str(channel or ""),
        "label": str(label or ""),
        "key": actor_key(level=level, subject=subject, channel=channel),
    }
    if str(session_id or "").strip():
        with _LOCK:
            _ACTORS[str(session_id)] = actor
    return actor


def get_turn_actor(session_id: str, *, default: str = OWNER) -> dict:
    """未登记的会话按机主处理：本机 UI 的历史路径没有身份，保持既有行为。"""
    with _LOCK:
        actor = _ACTORS.get(str(session_id or ""))
    if actor:
        return actor
    return {"level": default, "subject": "", "channel": "", "label": "", "key": actor_key(level=default)}


def clear_turn_actor(session_id: str) -> None:
    with _LOCK:
        _ACTORS.pop(str(session_id or ""), None)


def turn_level(session_id: str) -> str:
    return get_turn_actor(session_id)["level"]


def control_level(method: str, params: dict | None = None) -> int:
    """方法所需最低控制档。`session.delete` 的"仅限本人创建"由调用方追加判断。"""
    if method in CONTROL_LEVELS:
        return CONTROL_LEVELS[method]
    return 4


def control_allowed(level: object, method: str) -> bool:
    return axes_for(level).control >= control_level(method)


def tool_allowset(level: object, *, allow: list | None = None, deny: list | None = None) -> frozenset[str] | None:
    """返回允许的工具集合；None 表示不限制。"""
    axis = axes_for(level).tools
    deny_set = {str(name) for name in (deny or []) if str(name or "").strip()}
    if axis <= 1:
        return frozenset()
    if axis == 2:
        allowed = READ_TOOLS
    elif axis == 3:
        if allow:
            allowed = frozenset(str(name) for name in allow if str(name or "").strip())
        elif deny_set:
            return None  # 只有黑名单时由 deny 判断
        else:
            return None
    else:
        return None
    return allowed - deny_set


def tool_decision(
    tool_name: str,
    level: object,
    *,
    allow: list | None = None,
    deny: list | None = None,
) -> tuple[bool, str, list[str]]:
    """(是否允许, 规则标识, 当前身份可用工具清单)。清单用于拒绝回执。"""
    name = str(tool_name or "").strip()
    axis = axes_for(level).tools
    allowset = tool_allowset(level, allow=allow, deny=deny)
    deny_set = {str(item) for item in (deny or []) if str(item or "").strip()}
    if name in deny_set:
        return False, "identity.tool_denied.denylist", available_tools(level, allow=allow, deny=deny)
    if allowset is None:
        return True, "", available_tools(level, allow=allow, deny=deny)
    if name in allowset:
        return True, "", available_tools(level, allow=allow, deny=deny)
    rule = "identity.tool_denied.none" if axis <= 1 else (
        "identity.tool_denied.readonly" if axis == 2 else "identity.tool_denied.allowlist")
    return False, rule, available_tools(level, allow=allow, deny=deny)


def available_tools(level: object, *, allow: list | None = None, deny: list | None = None) -> list[str]:
    """拒绝回执里给出的可用工具清单：只列内置只读面 + 显式 allow。"""
    axis = axes_for(level).tools
    if axis <= 1:
        return []
    if axis == 2:
        base = set(READ_TOOLS)
    elif axis == 3:
        base = set(allow or READ_TOOLS)
    else:
        base = set(allow or READ_TOOLS)
    base -= {str(item) for item in (deny or []) if str(item or "").strip()}
    return sorted(base)


def denial_payload(tool_name: str, level: object, rule: str) -> dict:
    """给模型的拒绝回执：说明谁被拒、还能用什么。"""
    normalized = normalize_level(level)
    return {
        "error": "tool_denied_by_identity",
        "tool": str(tool_name or ""),
        "denied_by": normalized,
        "rule": rule,
        "axes": axes_for(normalized).as_dict(),
        "available_tools": available_tools(normalized),
        "hint": "该身份无权调用此工具；限制只作用于本轮，下一轮按新的发言者身份重新判定。"
                "如需提权，请让机主把发起者加入白名单或改用本机入口。",
    }
