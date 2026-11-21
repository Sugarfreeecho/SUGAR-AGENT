"""小Sugar助手的 CLI：给 agent 和人都能用的控制口。

权限档位沿用产品手册的「会话控制」轴（1–4），命令自己声明需要几档：

    1 只读        status / conversations / logs / persona show / person list / channel list
    2 可逆写      persona set / person add|remove / channel enable|disable
    3 不可逆      wechat login（会换掉登录态）
    4 全部        预留（改权限、清空状态）

本地命令行默认 4 档（本机 = 机主）；被 agent 通过 MCP 调用时，由 MCP 工具声明档位，
宿主再按当轮身份在执行层拒绝越档调用 —— 这里只做**第二道**校验，不替代宿主。

用法：
    python -m sugar_assistant.cli status --json
    python -m sugar_assistant.cli person add --name 阿鱼 --relation 主人
    python -m sugar_assistant.cli channel enable feishu
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from typing import Any

from .config import Config
from .console import ConsoleStore
from . import paths

PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_DIR = paths.data_dir()

# 命令 → 所需档位
COMMAND_LEVELS: dict[str, int] = {
    "status": 1,
    "conversations": 1,
    "logs": 1,
    "persona.show": 1,
    "person.list": 1,
    "channel.list": 1,
    "persona.set": 2,
    "person.add": 2,
    "person.remove": 2,
    "channel.enable": 2,
    "channel.disable": 2,
    "identity.show": 1,
    "identity.set": 2,
    "wechat.login": 3,
}


class PermissionDenied(RuntimeError):
    def __init__(self, command: str, need: int, have: int) -> None:
        super().__init__(f"{command} 需要 {need} 档，当前 {have} 档")
        self.command, self.need, self.have = command, need, have


def store() -> ConsoleStore:
    return ConsoleStore(STATE_DIR)


def require(command: str, actor_level: int) -> None:
    need = COMMAND_LEVELS.get(command, 4)
    if actor_level < need:
        raise PermissionDenied(command, need, actor_level)


# ---------------------------------------------------------------- 只读
def status() -> dict:
    config = Config.load()
    from . import identity as identity_mode

    sessions = _read_json(os.path.join(STATE_DIR, "sessions.json"), {}).get("sessions") or {}
    ops = _read_json(os.path.join(STATE_DIR, "ops.json"), {}).get("ops") or {}
    return {
        "plugin": "sugar-assistant",
        "config_enabled": config.enabled,
        "channels": [
            {"name": name, "enabled": cfg.enabled, "quota": cfg.quota,
             "allow": len(cfg.allow), "allow_groups": len(cfg.allow_groups)}
            for name, cfg in sorted(config.channels.items())
        ],
        "conversations": len(sessions),
        "ops": len(ops),
        "identity": identity_mode.current(),
        "wechat_logged_in": os.path.exists(os.path.join(STATE_DIR, "wechat-account.json")),
        "persona": store().persona().get("name") or "",
        "note": "实时连接状态由宿主进程维护；CLI 只能看到落盘状态",
    }


def conversations() -> list[dict]:
    raw = _read_json(os.path.join(STATE_DIR, "sessions.json"), {}).get("sessions") or {}
    items = [
        {"key": key, "session_id": value.get("session_id"), "title": value.get("title"),
         "principal": value.get("principal"), "last_used": value.get("last_used")}
        for key, value in raw.items() if isinstance(value, dict)
    ]
    items.sort(key=lambda item: item.get("last_used") or 0, reverse=True)
    return items


def logs(limit: int = 50) -> list[dict]:
    items = store().events(limit)
    items.reverse()
    return items


def history(session_id: str = "", limit: int = 50) -> list[dict]:
    """最近事件；给 session_id 时只看那个会话。日志不含消息正文。"""
    items = store().events(500)
    if session_id:
        items = [item for item in items if str(item.get("session_id") or "") == session_id]
    items.reverse()
    return items[:limit]


def person_lookup(name: str = "") -> list[dict]:
    items = store().persons()
    if not name:
        return items
    needle = name.strip().lower()
    return [
        item for item in items
        if needle in str(item.get("name") or "").lower()
        or needle in str(item.get("alias") or "").lower()
    ]


# ---------------------------------------------------------------- 写
def persona_set(name: str = "", tone: str = "", rules: str = "", prompt: str = "") -> dict:
    """兼容旧参数：拼成全局提示词；新代码直接用 prompt。"""
    current = store().persona()
    blocks = [str(prompt or current.get("prompt") or "").strip()]
    if name:
        blocks.append(f"你的身份：{name}")
    if tone:
        blocks.append(f"说话风格：{tone}")
    if rules:
        blocks.append("硬规则：\n" + "\n".join(f"- {line.strip('- ').strip()}"
                                              for line in rules.splitlines() if line.strip()))
    text = "\n\n".join(block for block in blocks if block)
    return store().save_persona({"prompt": text, "modes": current.get("modes") or {}})


def person_add(name: str, relation: str = "朋友", alias: str = "", note: str = "") -> dict:
    return store().add_person({"name": name, "relation": relation, "alias": alias, "note": note})


def person_remove(person_id: str) -> bool:
    return store().remove_person(person_id)


def channel_set(name: str, enabled: bool) -> dict:
    # 跟随 STATE_DIR，便于测试与迁到别处后仍写同一份配置
    path = os.path.join(STATE_DIR, "config.json")
    raw = _read_json(path, {})
    channels = raw.setdefault("channels", {})
    entry = channels.setdefault(name, {"enabled": False, "quota": "rate"})
    entry["enabled"] = bool(enabled)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(raw, fh, ensure_ascii=False, indent=2)
    store().log("cli_channel_set", channel=name, enabled=bool(enabled))
    return {"channel": name, "enabled": bool(enabled), "restart_required": True}


def wechat_login_start() -> dict:
    script = os.path.join(PLUGIN_ROOT, "sidecar", "wechat-login.mjs")
    creation = 0
    if sys.platform == "win32":
        creation = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    env = {**os.environ, "SUGAR_DATA_DIR": STATE_DIR}
    subprocess.Popen(["node", script], cwd=PLUGIN_ROOT, creationflags=creation, env=env,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    store().log("cli_wechat_login")
    return {"started": True, "hint": "在手机微信里扫码；成功后 state/wechat-account.json 会出现"}


# ---------------------------------------------------------------- 入口
def dispatch(args: argparse.Namespace, *, actor_level: int = 4) -> Any:
    command = args.command
    action = getattr(args, "action", None)
    if action:
        command = f"{command}.{action}"
    require(command, actor_level)

    if command == "status":
        return status()
    if command == "conversations":
        return conversations()
    if command == "logs":
        return logs(args.limit)
    if command == "persona.show":
        return store().persona()
    if command == "persona.set":
        return persona_set(args.name or "", args.tone or "", args.rules or "")
    if command == "person.list":
        return person_lookup(args.name or "")
    if command == "person.add":
        return person_add(args.name, args.relation or "朋友", args.alias or "", args.note or "")
    if command == "person.remove":
        return {"removed": person_remove(args.id)}
    if command == "channel.list":
        return status()["channels"]
    if command == "channel.enable":
        return channel_set(args.name, True)
    if command == "channel.disable":
        return channel_set(args.name, False)
    if command == "wechat.login":
        return wechat_login_start()
    if command == "identity.show":
        from . import identity as identity_mode

        return {"mode": identity_mode.current(), "chats": identity_mode.chats()}
    if command == "identity.set":
        from . import identity as identity_mode

        result = identity_mode.set_mode(args.mode, chats=getattr(args, "chat", None))
        if result.get("changed"):
            identity_mode.request_reload()
            result["reload"] = "requested"
        return result
    raise SystemExit(f"未知命令：{command}")


def build_parser() -> argparse.ArgumentParser:
    # --json / --level 放在子命令前后都能用：agent 拼命令时不该记顺序
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--level", type=int, default=argparse.SUPPRESS, help="调用方档位（1–4），默认 4=本机机主")
    common.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="输出 JSON")

    parser = argparse.ArgumentParser(prog="sugar-assistant", description="小Sugar助手 CLI")
    parser.add_argument("--level", type=int, default=4, help="调用方档位（1–4），默认 4=本机机主")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", parents=[common])
    sub.add_parser("conversations", parents=[common])
    p_logs = sub.add_parser("logs", parents=[common]); p_logs.add_argument("--limit", type=int, default=50)

    p_persona = sub.add_parser("persona", parents=[common]); p_persona.add_argument("action", choices=["show", "set"])
    p_persona.add_argument("--name"); p_persona.add_argument("--tone"); p_persona.add_argument("--rules")

    p_person = sub.add_parser("person", parents=[common]); p_person.add_argument("action", choices=["list", "add", "remove"])
    p_person.add_argument("--name"); p_person.add_argument("--alias"); p_person.add_argument("--relation")
    p_person.add_argument("--note"); p_person.add_argument("--id")

    p_channel = sub.add_parser("channel", parents=[common]); p_channel.add_argument("action", choices=["list", "enable", "disable"])
    p_channel.add_argument("name", nargs="?")

    p_wechat = sub.add_parser("wechat", parents=[common]); p_wechat.add_argument("action", choices=["login"])
    p_identity = sub.add_parser("identity", parents=[common])
    p_identity.add_argument("action", choices=["show", "set"])
    p_identity.add_argument("mode", nargs="?", choices=["bot", "user"])
    p_identity.add_argument("--chat", action="append", help="user 身份要轮询的 chat_id，可重复")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = dispatch(args, actor_level=args.level)
    except PermissionDenied as exc:
        print(json.dumps({"error": str(exc), "need": exc.need, "have": exc.have}, ensure_ascii=False))
        return 3
    except Exception as exc:  # 命令失败也要机器可读
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 1
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(_human(result))
    return 0


def _human(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return "\n".join(f"{key}: {val}" for key, val in value.items())
    if isinstance(value, list):
        if not value:
            return "（空）"
        if all(isinstance(item, dict) for item in value):
            keys = list(value[0].keys())
            lines = [" | ".join(keys)]
            for item in value:
                lines.append(" | ".join(str(item.get(key, "")) for key in keys))
            return "\n".join(lines)
        return "\n".join(str(item) for item in value)
    return str(value)


def _read_json(path: str, default):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return default


if __name__ == "__main__":
    raise SystemExit(main())
