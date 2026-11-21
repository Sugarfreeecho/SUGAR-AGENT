"""通用命令层：/new /list /use /whoami /stop。

放在 Core 的原因很实际：这三件事每家 Adapter 都要，复制三遍必然长歪。
命令解析必须是纯函数，好测；副作用交给 runtime 注入的 callbacks。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

CommandKind = Literal["reply", "new", "use", "stop", "whoami", "list", "models", "model",
                      "dir", "history", "identity", "rename", "help"]

HELP = (
    "/new [标题]　开一个新对话\n"
    "/list　列出最近的对话\n"
    "/use N　切到第 N 个\n"
    "/whoami　看自己的身份与角色\n"
    "/stop　中止当前这一轮\n"
    "/history [N]　看最近 N 条消息\n"
    "/model [序号|id]　看/切模型\n"
    "/dir [路径]　看/切工作目录\n"
    "/identity [bot|user]　看/切发送身份\n"
    "/rename 名称　给当前会话改名\n"
    "/help　看这份说明"
)


@dataclass(frozen=True)
class Command:
    kind: CommandKind
    arg: str = ""


def parse_command(text: str) -> Command | None:
    # 中文输入法常打出全角斜杠，先归一化
    raw = (text or "").strip().replace("／", "/")
    if raw.startswith("。"):
        raw = raw[1:].lstrip()
    if not raw.startswith("/"):
        return None
    head, _, rest = raw.partition(" ")
    name = head[1:].strip().lower()
    rest = rest.strip()
    if name in {"help", ""}:
        return Command("help")
    if name == "new":
        return Command("new", rest)
    if name == "list":
        return Command("list")
    if name in {"use", "switch"}:
        return Command("use", rest)
    if name in {"stop", "cancel", "interrupt"}:
        return Command("stop")
    if name in {"whoami", "me"}:
        return Command("whoami")
    if name == "models":
        return Command("models")
    if name == "model":
        return Command("model", rest)
    if name == "dir":
        return Command("dir", rest)
    if name in {"history", "hist"}:
        return Command("history", rest)
    if name in {"identity", "id"}:
        return Command("identity", rest)
    if name in {"rename", "title"}:
        return Command("rename", rest)
    return Command("help")
