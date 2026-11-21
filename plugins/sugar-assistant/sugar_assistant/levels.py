"""身份四轴：权限只绑身份、不绑会话，每一轮单独判。

依据 `skills/sugar-agent-manual/references/09-session-permissions.md`：
    五类身份  owner / whitelist / private（私聊·小群·白名单群）/ group / stranger
    四轴档位  会话控制 · 工具集 · 作用域 · 访问目录（各 1–4）

三条必须遵守的执行规则（此前实现正好反了，已在此纠正）：
    1. 权限不落会话：`tools` / `read_only` 不写进会话配置，按当轮身份现算；
    2. 工具清单固定、越档在执行层拒绝：插件不裁剪工具定义，只声明身份；
    3. 同人合并、异人排队：同一身份继续说话走 steer，不同身份排队各自判档。
"""
from __future__ import annotations

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

# 群人数低于这个值按"小群"处理，与手册的 < 5 一致；拿不到人数一律按群聊。
SMALL_GROUP_MAX = 5


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


def normalize_level(value: object, *, default: str = STRANGER) -> str:
    text = str(value or "").strip().lower()
    return _ALIASES.get(text, default)


def axes_for(level: object) -> Axes:
    return MATRIX.get(normalize_level(level), MATRIX[STRANGER])


def classify(
    *,
    whitelisted: bool = False,
    is_private: bool = True,
    members: int | None = None,
    whitelisted_group: bool = False,
) -> str:
    """把「这是谁、在哪种会话里」判成五类身份之一。

    注意 owner 不在插件侧判定：宿主只允许 admin 主体声明 owner，
    插件自称 owner 会被降级为 stranger（见 session_control/service.py:_actor_fields）。
    """
    if whitelisted:
        return WHITELIST
    if is_private:
        return PRIVATE
    if whitelisted_group:
        return PRIVATE
    if members is not None and members < SMALL_GROUP_MAX:
        return PRIVATE
    if members is None or members >= SMALL_GROUP_MAX:
        return GROUP
    return STRANGER


def turn_actor(level: str, *, subject: str, channel: str, label: str = "") -> dict:
    """给宿主 `session.send` 的当轮身份（字段名以 _actor_fields 为准）。"""
    # 只带身份两项：`_source` 由宿主的 ServiceProxy 注入（它才带 epoch/kind，
    # 自己造的 _source 会因为缺 epoch 直接 KeyError）。
    actor = {"_level": normalize_level(level), "_subject": subject}
    if label:
        actor["_label"] = label
    return actor


new_actor = turn_actor  # Core 里的习惯叫法
