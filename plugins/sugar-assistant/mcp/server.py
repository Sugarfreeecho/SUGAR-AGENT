"""小Sugar助手 MCP 工具：把常用查询/操作注入 agent。

只做两件事：读插件自己落盘的状态、调已经存在的 CLI 函数。
**权限第一道在宿主**（四轴工具集，越档调用直接拒绝）；这里是第二道，
按 `SUGAR_ACTOR_LEVEL`（默认 4=本机机主）再挡一次明显的越档。

工具档位（沿用手册「会话控制」轴）：
    1 只读   sugar_status / sugar_channels / sugar_conversations / sugar_history
             / sugar_person_lookup / sugar_persona_show
    2 可逆写 sugar_persona_set / sugar_person_add / sugar_person_remove / sugar_channel_set
    3 不可逆 sugar_wechat_login
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mcp.server.fastmcp import FastMCP  # noqa: E402

from sugar_assistant import cli  # noqa: E402

mcp = FastMCP("sugar-assistant")


def _level() -> int:
    try:
        return max(1, min(4, int(os.getenv("SUGAR_ACTOR_LEVEL", "4"))))
    except ValueError:
        return 4


def _guard(command: str) -> dict | None:
    try:
        cli.require(command, _level())
    except cli.PermissionDenied as exc:
        return {"ok": False, "error": str(exc), "need_level": exc.need, "have_level": exc.have}
    return None


@mcp.tool()
def sugar_status() -> dict:
    """桥接状态：Core 是否配置启用、三个通道的开关与配额、会话数、微信是否已登录。需要 1 档（只读）。"""
    return {"ok": True, **cli.status()}


@mcp.tool()
def sugar_channels() -> dict:
    """通道清单：名字、是否启用、配额模型、白名单数量。需要 1 档。"""
    return {"ok": True, "items": cli.status()["channels"]}


@mcp.tool()
def sugar_conversations() -> dict:
    """对话映射：通道里的哪个对话对应宿主哪个会话（不含聊天正文）。需要 1 档。"""
    return {"ok": True, "items": cli.conversations()}


@mcp.tool()
def sugar_history(session_id: str = "", limit: int = 20) -> dict:
    """最近运行事件（准入/起一轮/投递/失败）；给 session_id 时只看那个会话。不含消息正文。需要 1 档。"""
    denied = _guard("logs")
    if denied:
        return denied
    return {"ok": True, "items": cli.history(session_id, max(1, min(100, limit)))}


@mcp.tool()
def sugar_person_lookup(name: str = "") -> dict:
    """查人物卡片：按名字或别名模糊匹配；不传 name 返回全部。需要 1 档。"""
    denied = _guard("person.list")
    if denied:
        return denied
    return {"ok": True, "items": cli.person_lookup(name)}


@mcp.tool()
def sugar_persona_show() -> dict:
    """当前人设：名字、说话风格、硬规则。需要 1 档。"""
    denied = _guard("persona.show")
    if denied:
        return denied
    return {"ok": True, **cli.store().persona()}


@mcp.tool()
def sugar_persona_set(name: str = "", tone: str = "", rules: str = "") -> dict:
    """修改人设（留空的字段保持不变）。需要 2 档（可逆写）。"""
    denied = _guard("persona.set")
    if denied:
        return denied
    return {"ok": True, **cli.persona_set(name, tone, rules)}


@mcp.tool()
def sugar_person_add(name: str, relation: str = "朋友", alias: str = "", note: str = "") -> dict:
    """新增人物卡片。需要 2 档。"""
    denied = _guard("person.add")
    if denied:
        return denied
    try:
        return {"ok": True, **cli.person_add(name, relation, alias, note)}
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}


@mcp.tool()
def sugar_person_remove(person_id: str) -> dict:
    """按 id 删除人物卡片。需要 2 档。"""
    denied = _guard("person.remove")
    if denied:
        return denied
    return {"ok": True, "removed": cli.person_remove(person_id)}


@mcp.tool()
def sugar_channel_set(name: str, enabled: bool) -> dict:
    """开关某个通道（feishu/wechat/qq）；写 config.json，重启宿主后生效。需要 2 档。"""
    denied = _guard("channel.enable")
    if denied:
        return denied
    return {"ok": True, **cli.channel_set(name, enabled)}


@mcp.tool()
def sugar_wechat_login() -> dict:
    """启动微信扫码登录（会另起 sidecar/wechat-login.mjs）。需要 3 档（不可逆）。"""
    denied = _guard("wechat.login")
    if denied:
        return denied
    return {"ok": True, **cli.wechat_login_start()}


if __name__ == "__main__":
    mcp.run()
