"""飞书长连接工作进程：把 lark SDK 关在自己的进程里。

为什么单独起进程：
    lark 的 `ws.Client` 用一个**模块级全局事件循环**，且重连也在那个循环里。
    放在宿主进程里，热重载时新旧连接会抢同一个 loop，报
    "This event loop is already running"，而且旧连接还会继续重连。
    隔离成子进程后，重载 = 杀掉子进程再起一个，宿主进程不再被污染。

协议（与其他 sidecar 一致，一行一个 JSON）：
    输出  {"type":"ready"} / {"type":"inbound", peerId, chatId, groupId, messageId, text}
          {"type":"sent", id, ok, error?}
    输入  {"type":"send", id, to, text} / {"type":"stop"}
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading

PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PLUGIN_ROOT not in sys.path:
    sys.path.insert(0, PLUGIN_ROOT)

import lark_oapi as lark  # noqa: E402

from sugar_assistant.channels.feishu import FeishuSettings, parse_event, split_reply  # noqa: E402
from sugar_assistant.paths import data_dir  # noqa: E402
from sugar_assistant import identity as identity_mode  # noqa: E402


_recent_sent: dict[tuple[str, str], float] = {}


def _is_echo(chat_id: str, text: str) -> bool:
    """账户主身份发送后，飞书会把这条也推回来；按 (chat, text) 8 秒内去重，避免自问自答。"""
    import time as _time
    now = _time.time()
    for key, ts in list(_recent_sent.items()):
        if now - ts > 8:
            _recent_sent.pop(key, None)
    return _recent_sent.get((chat_id, (text or "").strip())) is not None


def _cli_path() -> str:
    import shutil
    cli = os.path.join(os.environ.get("APPDATA", ""), "npm", "lark-cli.cmd")
    return cli if os.path.exists(cli) else (shutil.which("lark-cli") or "")


def _cli_json(args: list[str], cwd: str | None = None, timeout: int = 60) -> dict:
    import json as _json
    cli = _cli_path()
    if not cli:
        raise RuntimeError("未找到 lark-cli")
    if cli.lower().endswith((".cmd", ".bat")):
        quoted = " ".join(f'"{a}"' if (" " in a or a.startswith("@")) else a for a in args)
        result = subprocess.run(f'"{cli}" {quoted}', shell=True, capture_output=True, text=True,
                                timeout=timeout, encoding="utf-8", errors="replace", cwd=cwd,
                                stdin=subprocess.DEVNULL)
    else:
        result = subprocess.run([cli, *args], capture_output=True, text=True, timeout=timeout,
                                encoding="utf-8", errors="replace", cwd=cwd,
                                stdin=subprocess.DEVNULL)
    try:
        out = result.stdout or ""
        start = out.find("{")
        return _json.loads(out[start:]) if start >= 0 else {}
    except ValueError:
        return {}


def _self_open_id() -> str:
    data = _cli_json(["auth", "status", "--json"])
    return str(((data.get("identities") or {}).get("user") or {}).get("openId") or "")


def _cli_run(args: list[str], cwd: str | None = None, timeout: int = 60):
    """统一的 lark-cli 调用：.cmd 走 shell 并加引号，避免含空格路径被拆开。"""
    cli = _cli_path()
    if not cli:
        raise RuntimeError("未找到 lark-cli")
    if cli.lower().endswith((".cmd", ".bat")):
        quoted = " ".join(f'"{a}"' if (" " in a or a.startswith("@")) else a for a in args)
        return subprocess.run(f'"{cli}" {quoted}', shell=True, capture_output=True, text=True,
                              timeout=timeout, encoding="utf-8", errors="replace", cwd=cwd,
                              stdin=subprocess.DEVNULL)
    return subprocess.run([cli, *args], capture_output=True, text=True, timeout=timeout,
                          encoding="utf-8", errors="replace", cwd=cwd, stdin=subprocess.DEVNULL)


def _discover_chats(keywords: list[str], limit: int = 40) -> list[str]:
    """飞书没有"列出我全部会话"的接口，用消息搜索按关键词反查 chat_id。"""
    found: list[str] = []
    for word in keywords:
        data = _cli_json(["im", "+messages-search", "--as", "user", "--query", word])
        for item in ((data.get("data") or {}).get("messages") or []):
            chat = str(item.get("chat_id") or "")
            if chat and chat not in found:
                found.append(chat)
        if len(found) >= limit:
            break
    return found


def is_service_sender(sender: dict) -> bool:
    """服务号/应用（如账号安全中心）只读不触发。"""
    return str((sender or {}).get("sender_type") or "") == "app" or bool((sender or {}).get("is_agent"))


def _poll_messages(chat_id: str, page_size: int = 10) -> list[dict]:
    import json as _json
    import tempfile
    params = {"container_id_type": "chat", "container_id": chat_id,
              "page_size": page_size, "sort_type": "ByCreateTimeDesc"}
    temp_dir = tempfile.gettempdir()
    name = f"sugar-poll-{chat_id[-8:]}.json"
    with open(os.path.join(temp_dir, name), "w", encoding="utf-8") as fh:
        fh.write(_json.dumps(params, ensure_ascii=False))
    data = _cli_json(["api", "GET", "/open-apis/im/v1/messages", "--as", "user", "--params", f"@{name}"],
                     cwd=temp_dir)
    return list(((data.get("data") or {}).get("items") or []))


def _send_as_user(chat_id: str, text: str) -> None:
    """账户主身份发送：走本机 lark-cli 的用户授权（账户主完整设计另做）。"""
    import shutil
    cli = os.path.join(os.environ.get("APPDATA", ""), "npm", "lark-cli.cmd")
    if not os.path.exists(cli):
        cli = shutil.which("lark-cli") or ""
    if not cli:
        raise RuntimeError("未找到 lark-cli，无法以账户主身份发送")
    # 不能用 --text：命令行参数在换行处会被截断（实测只剩第一行）。
    # 改走 open API，正文放 JSON 文件，换行不会被 shell 吞掉。
    import json as _json
    import tempfile
    temp_dir = tempfile.gettempdir()
    params_path = os.path.join(temp_dir, "sugar-user-send-params.json")
    data_path = os.path.join(temp_dir, "sugar-user-send-data.json")
    with open(params_path, "w", encoding="utf-8") as fh:
        fh.write(_json.dumps({"receive_id_type": "chat_id"}, ensure_ascii=False))
    with open(data_path, "w", encoding="utf-8") as fh:
        fh.write(_json.dumps({"receive_id": chat_id, "msg_type": "text",
                              "content": _json.dumps({"text": text}, ensure_ascii=False)},
                             ensure_ascii=False))
    result = _cli_run(["api", "POST", "/open-apis/im/v1/messages", "--as", "user",
                       "--params", "@sugar-user-send-params.json",
                       "--data", "@sugar-user-send-data.json"], cwd=temp_dir)
    import time as _time
    _recent_sent[(chat_id, (text or "").strip())] = _time.time()
    if result.returncode != 0 or '"ok": true' not in (result.stdout or ""):
        detail = (result.stdout or result.stderr or "")[:300]
        raise RuntimeError(f"账户主发送失败：{detail}")
    if not _readback_text(chat_id, text):
        raise RuntimeError("发送接口返回成功，但回查未见该消息")


def _readback_text(chat_id: str, text: str, timeout: float = 8.0) -> bool:
    """只读回查：轮询最近消息，确认刚发出的文本真的落在会话里。"""
    import time as _time
    needle = (text or "").strip()
    if not needle:
        return True
    deadline = _time.time() + timeout
    while _time.time() < deadline:
        try:
            for item in _poll_messages(chat_id, page_size=5):
                body = item.get("body") or {}
                try:
                    content = json.loads(body.get("content") or "{}")
                except ValueError:
                    continue
                if str(content.get("text") or "").strip() == needle:
                    return True
        except Exception:
            pass
        _time.sleep(1.5)
    return False

MAX_REPLY_CHARS = int(os.getenv("FEISHU_MAX_REPLY_CHARS", "3500") or 3500)
INBOUND_DIR = os.path.join(data_dir(), "inbound")
MAX_MEDIA_BYTES = 25 * 1024 * 1024


def _download_as_user(message_id: str, msg_type: str, content: dict) -> str:
    """user 模式下载附件：飞书没有用户级事件，轮询拿到 message_id 后用 CLI 取资源。"""
    import shutil
    import time as _time
    key = str(content.get("image_key") or content.get("file_key") or "")
    if not key:
        return ""
    os.makedirs(INBOUND_DIR, exist_ok=True)
    name = str(content.get("file_name") or "").strip()
    stem = name or f"{message_id}_{int(_time.time())}"
    stem = "".join(ch for ch in stem if ch not in '\\/:*?"<>|')[:80]
    out = os.path.join(INBOUND_DIR, stem)
    cli = os.path.join(os.environ.get("APPDATA", ""), "npm", "lark-cli.cmd")
    if not os.path.exists(cli):
        cli = shutil.which("lark-cli") or ""
    if not cli:
        return ""
    args = [cli, "im", "+messages-resources-download", "--as", "user",
            "--message-id", message_id, "--file-key", key,
            "--type", "image" if msg_type == "image" else "file",
            "--output", out]
    result = subprocess.run(args, capture_output=True, text=True, timeout=120,
                            encoding="utf-8", errors="replace")
    if result.returncode != 0 or '"ok": true' not in (result.stdout or ""):
        detail = (result.stdout or result.stderr or "")[:200]
        raise RuntimeError(f"附件下载失败：{detail}")
    try:
        data = json.loads((result.stdout or "").strip()[result.stdout.strip().find("{"):])
        path = str(((data.get("data") or {}).get("path") or "")).strip()
    except Exception:
        path = ""
    if path and os.path.exists(path):
        return path
    candidates = [p for p in os.listdir(INBOUND_DIR) if p.startswith(stem)]
    return os.path.join(INBOUND_DIR, sorted(candidates)[-1]) if candidates else out


_card_clicks: dict[tuple[str, str, str], float] = {}


def sticker_payload(chat_id: str, file_key: str) -> dict:
    """user-cli 发贴纸的请求体：msg_type=sticker + file_key。"""
    if not file_key:
        raise ValueError("缺少 sticker file_key")
    return {"receive_id": chat_id, "msg_type": "sticker",
            "content": json.dumps({"file_key": file_key})}


def remember_sticker(file_key: str) -> None:
    """记录收到过的贴纸 key，供后续发送复用（最多 50 个，去重）。"""
    if not file_key:
        return
    path = os.path.join(data_dir(), "stickers.json")
    try:
        with open(path, encoding="utf-8") as fh:
            items = json.load(fh)
        if not isinstance(items, list):
            items = []
    except Exception:
        items = []
    if file_key in items:
        items.remove(file_key)
    items.insert(0, file_key)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(items[:50], fh, ensure_ascii=False, indent=2)


def latest_sticker_key() -> str:
    path = os.path.join(data_dir(), "stickers.json")
    try:
        with open(path, encoding="utf-8") as fh:
            items = json.load(fh)
        return str(items[0]) if items else ""
    except Exception:
        return ""


def card_payload_10(card: dict) -> dict:
    """卡片 1.0 结构：header + elements（2.0 不支持 action 块）。"""
    sections = card.get("sections") or [{"body": card.get("body"),
                                         "options": card.get("options") or []}]
    elements: list[dict] = []
    for section in sections:
        elements.append({"tag": "markdown", "content": str(section.get("body") or "")})
        actions = [
            {
                "tag": "button",
                "text": {"tag": "plain_text", "content": str(opt.get("label") or opt.get("value"))},
                "type": "primary" if index == 0 else "default",
                "value": {"choice": str(opt.get("value"))},
            }
            for index, opt in enumerate(section.get("options") or [])
        ]
        if actions:
            elements.append({"tag": "action", "actions": actions})
    return {
        "config": {"wide_screen_mode": True},
        "header": {"title": {"tag": "plain_text", "content": str(card.get("title") or "小Sugar助手")}},
        "elements": elements,
    }


def send_card_as_user(to: str, card: dict) -> None:
    import tempfile
    payload = card_payload_10(card)
    temp_dir = tempfile.gettempdir()
    with open(os.path.join(temp_dir, "sugar-card-params.json"), "w", encoding="utf-8") as fh:
        json.dump({"receive_id_type": "chat_id"}, fh)
    with open(os.path.join(temp_dir, "sugar-card-data.json"), "w", encoding="utf-8") as fh:
        json.dump({"receive_id": to, "msg_type": "interactive",
                   "content": json.dumps(payload, ensure_ascii=False)}, fh, ensure_ascii=False)
    result = _cli_run(["api", "POST", "/open-apis/im/v1/messages", "--as", "user",
                       "--params", "@sugar-card-params.json",
                       "--data", "@sugar-card-data.json"], cwd=temp_dir)
    if result.returncode != 0 or '"ok": true' not in (result.stdout or ""):
        raise RuntimeError(f"卡片发送失败：{(result.stdout or result.stderr or '')[:200]}")


def send_sticker_as_user(chat_id: str, file_key: str = "") -> None:
    """用账户主身份发一张已有的贴纸（file_key 来自收到过的贴纸消息）。"""
    import tempfile
    file_key = file_key or latest_sticker_key()
    body = sticker_payload(chat_id, file_key)
    temp_dir = tempfile.gettempdir()
    with open(os.path.join(temp_dir, "sugar-sticker-params.json"), "w", encoding="utf-8") as fh:
        json.dump({"receive_id_type": "chat_id"}, fh)
    with open(os.path.join(temp_dir, "sugar-sticker-data.json"), "w", encoding="utf-8") as fh:
        json.dump(body, fh, ensure_ascii=False)
    result = _cli_run(["api", "POST", "/open-apis/im/v1/messages", "--as", "user",
                       "--params", "@sugar-sticker-params.json",
                       "--data", "@sugar-sticker-data.json"], cwd=temp_dir)
    if result.returncode != 0 or '"ok": true' not in (result.stdout or ""):
        raise RuntimeError(f"贴纸发送失败：{(result.stdout or result.stderr or '')[:200]}")


def _send_media_as_user(chat_id: str, path: str, kind: str) -> None:
    """user 身份发图片/文件：CLI 自带 --image/--file，上传与发送一步完成。"""
    import shutil
    cli = os.path.join(os.environ.get("APPDATA", ""), "npm", "lark-cli.cmd")
    if not os.path.exists(cli):
        cli = shutil.which("lark-cli") or ""
    if not cli:
        raise RuntimeError("未找到 lark-cli，无法以账户主身份发送附件")
    flag = "--image" if kind == "image" else "--file"
    result = subprocess.run([cli, "im", "+messages-send", "--as", "user",
                             "--chat-id", chat_id, flag, path],
                            capture_output=True, text=True, timeout=180,
                            encoding="utf-8", errors="replace")
    if result.returncode != 0 or '"ok": true' not in (result.stdout or ""):
        detail = (result.stdout or result.stderr or "")[:300]
        raise RuntimeError(f"账户主发送附件失败：{detail}")


def _bridge_send(chat_name: str, text: str) -> str:
    """经宿主浏览器桥发送（方案 B）：复用用户已登录的浏览器，不读 Cookie。"""
    import json as _json
    import urllib.request
    url = os.environ.get("SUGAR_BROWSER_BRIDGE_URL", "")
    token = os.environ.get("SUGAR_BROWSER_BRIDGE_TOKEN", "")
    tenant = os.environ.get("SUGAR_WEB_TENANT", "")
    if not (url and token and tenant):
        raise RuntimeError("浏览器桥未配置")
    payload = _json.dumps({"caller": "sugar-assistant", "method": "send_text",
                           "params": {"tenant": tenant, "chat_name": chat_name, "text": text}},
                          ensure_ascii=False).encode()
    request = urllib.request.Request(url, data=payload, method="POST",
                                     headers={"Content-Type": "application/json",
                                              "x-sugar-bridge": token})
    with urllib.request.urlopen(request, timeout=120) as resp:
        return resp.read().decode("utf-8", "replace")


def emit(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _message_content(data) -> dict:
    try:
        raw = data.event.message.content
        return json.loads(raw) if isinstance(raw, str) else (raw or {})
    except Exception:
        return {}


def download_media(data, message_id: str, message_type: str) -> str:
    """把图片/文件/语音/视频下载到 data/inbound，返回本地路径。"""
    from lark_oapi.api.im.v1 import GetMessageResourceRequest

    content = _message_content(data)
    key = str(content.get("image_key") or content.get("file_key") or "")
    if not key:
        return ""
    name = str(content.get("file_name") or "").strip()
    if not name:
        ext = {"image": ".jpg", "audio": ".opus", "video": ".mp4", "media": ".bin"}.get(message_type, ".bin")
        name = f"{message_id}{ext}"
    safe = "".join(ch for ch in name if ch not in '\\/:*?"<>|')[:80] or f"{message_id}.bin"
    os.makedirs(INBOUND_DIR, exist_ok=True)
    target = os.path.join(INBOUND_DIR, f"{message_id}-{safe}")
    request = (
        GetMessageResourceRequest.builder()
        .message_id(message_id)
        .file_key(key)
        .type("image" if message_type == "image" else "file")
        .build()
    )
    client = globals().get("_api")
    if client is None:
        raise RuntimeError("SDK 客户端未初始化")
    response = client.im.v1.message_resource.get(request)
    if response is None or not response.success() or response.file is None:
        raise RuntimeError(
            f"[{getattr(response, 'code', 'unknown')}] {getattr(response, 'msg', 'download failed')}"
        )
    payload = response.file.read()
    if len(payload) > MAX_MEDIA_BYTES:
        raise RuntimeError("附件超过 25MB，未下载")
    with open(target, "wb") as fh:
        fh.write(payload)
    return target


def main() -> int:
    settings = FeishuSettings.from_env()
    try:
        settings.validate()
    except ValueError as exc:
        emit({"type": "error", "error": str(exc)})
        return 2

    _ensure_single_instance()

    last_message: dict[str, str] = {}
    api = (
        lark.Client.builder()
        .app_id(settings.app_id)
        .app_secret(settings.app_secret)
        .log_level(lark.LogLevel.INFO)
        .build()
    )
    globals()["_api"] = api

    _chat_names: dict[str, str] = {}
    _self_cli_id = ""

    def _cli_json(args: list[str]) -> dict:
        import json as _json
        import shutil
        import subprocess
        cli = os.path.join(os.environ.get("APPDATA", ""), "npm", "lark-cli.cmd")
        if not os.path.exists(cli):
            cli = shutil.which("lark-cli") or "lark-cli"
        quoted = " ".join(f'"{a}"' if (" " in a or a.startswith("@")) else a for a in args)
        try:
            out = subprocess.run(f'"{cli}" {quoted}', shell=True, capture_output=True,
                                 encoding="utf-8", errors="replace", timeout=30).stdout
            start = out.find("{")
            return _json.loads(out[start:]) if start >= 0 else {}
        except Exception:
            return {}

    def _cli_self_id() -> str:
        nonlocal _self_cli_id
        if _self_cli_id:
            return _self_cli_id
        data = _cli_json(["auth", "status"])
        _self_cli_id = str(((data.get("identities") or {}).get("user") or {}).get("openId") or "")
        return _self_cli_id

    def _cli_p2p_name(chat_id: str) -> str:
        data = _cli_json(["im", "+chat-members-list", "--as", "user", "--chat-id", chat_id,
                          "--page-size", "20"], timeout=8)
        me = _cli_self_id()
        for item in ((data.get("data") or {}).get("users") or []):
            member_id = str(item.get("member_id") or "")
            if member_id and member_id != me:
                return str(item.get("name") or "")
        return ""

    def _cli_sender_name(chat_id: str) -> str:
        """服务号/机器人会话成员接口只返回自己，改用最近一条非本人消息的发送者名。"""
        data = _cli_json(["im", "+chat-messages-list", "--as", "user", "--chat-id", chat_id,
                          "--page-size", "5", "--order", "desc"], timeout=8)
        me = _cli_self_id()
        for msg in ((data.get("data") or {}).get("messages") or []):
            sender = msg.get("sender") or {}
            open_id = str(sender.get("id") or "")
            name = str(sender.get("name") or "")
            if name and open_id != me and sender.get("sender_type") != "user":
                return name
        return ""

    def chat_name(chat_id: str, kind: str = "group") -> str:
        """对话名：群用群名；单聊用对方的名字。事件里不带，查一次接口并缓存。"""
        if chat_id in _chat_names:
            return _chat_names[chat_id]
        name = ""
        if identity_mode.current() == "user":
            # user 模式里机器人可能不在群/单聊中，SDK 查询会长时间重试并卡住轮询；
            # 名字优先从本地会话表取，取不到再走 CLI 短超时。
            try:
                with open(os.path.join(data_dir(), "sessions.json"), encoding="utf-8") as fh:
                    store = json.load(fh).get("sessions") or {}
                for key, item in store.items():
                    if key.endswith(chat_id):
                        name = str(item.get("chat_name") or "")
                        break
            except Exception:
                name = ""
        try:
            if name:
                pass
            elif kind == "group":
                from lark_oapi.api.im.v1 import GetChatRequest
                response = api.im.v1.chat.get(GetChatRequest.builder().chat_id(chat_id).build())
                if response is not None and response.success():
                    name = str((response.data or {}).name or "")
            elif identity_mode.current() != "user":
                # user 模式下机器人不在跨租户单聊里，SDK 查成员会长时间重试并卡住轮询
                from lark_oapi.api.im.v1 import GetChatMembersRequest
                request = (GetChatMembersRequest.builder().chat_id(chat_id)
                           .member_id_type("open_id").page_size(20).build())
                response = api.im.v1.chat_members.get(request)
                if response is not None and response.success():
                    me = _self_open_id()
                    for item in (getattr(response.data, "items", None) or []):
                        member_id = str(getattr(item, "member_id", "") or "")
                        if member_id and member_id != me:
                            name = str(getattr(item, "name", "") or "")
                            break
        except Exception:
            name = ""
        if not name and kind != "group":
            name = _cli_p2p_name(chat_id)
        if not name and kind != "group":
            name = _cli_sender_name(chat_id)
        _chat_names[chat_id] = name
        return name

    def on_event(data) -> None:
        try:
            if identity_mode.current() == "user":
                return  # user 模式只走轮询，机器人这条连接不再接活
            inbound = parse_event(data)
            if str((inbound.raw or {}).get("sender_type") or "") == "app":
                return  # 服务号/应用消息不触发
        except Exception as exc:  # 单条坏事件不该带走整个连接
            emit({"type": "error", "error": f"parse: {exc}"})
            return
        if not inbound.message_id or not inbound.text:
            kind = str((inbound.raw or {}).get("message_type") or "")
            if not inbound.message_id:
                return
            emit({"type": "recv", "messageId": inbound.message_id,
                  "chars": len(inbound.text or ""), "chatId": inbound.conversation.chat_id,
                  "ts": int(__import__("time").time() * 1000)})
            if kind and kind not in {"text", "post"}:
                # 图片/语音/视频/文件：下载到本地，把路径交给 agent，由它用文件工具处理
                label = {"image": "图片", "audio": "语音", "video": "视频", "media": "文件", "file": "文件"}.get(kind, kind)
                try:
                    path = download_media(data, inbound.message_id, kind)
                    text = f"[{label}] 已保存到本地：{path}" if path else f"[收到一条 {label} 消息，但取不到文件]"
                except Exception as exc:
                    text = f"[收到一条 {label} 消息，下载失败：{exc}]"
                emit({
                    "type": "inbound",
                    "peerId": inbound.sender.user_id,
                    "chatId": inbound.conversation.chat_id,
                    "groupId": "",
                    "messageId": inbound.message_id,
                    "text": text,
                })
            return
        if _is_echo(inbound.conversation.chat_id, inbound.text):
            return
        if inbound.conversation.kind == "group" and settings.group_require_mention:
            if not (inbound.raw or {}).get("mentions"):
                return
        last_message[inbound.conversation.chat_id] = inbound.message_id
        emit({
            "type": "inbound",
            "peerId": inbound.sender.user_id,
            "chatId": inbound.conversation.chat_id,
            "groupId": inbound.conversation.chat_id if inbound.conversation.kind == "group" else "",
            "messageId": inbound.message_id,
            "text": inbound.text,
            "chatName": chat_name(inbound.conversation.chat_id,
                                  "group" if inbound.conversation.kind == "group" else "p2p"),
        })

    def send_text(to: str, text: str, message_id: str) -> None:
        from lark_oapi.api.im.v1 import (CreateMessageRequest, CreateMessageRequestBody,
                                         ReplyMessageRequest, ReplyMessageRequestBody)
        import uuid

        if identity_mode.current() == "user":
            # 不静默换通道：user 模式发不出去就明确失败，由上层决定是否提示/改走 web。
            try:
                _send_as_user(to, text)
            except Exception as exc:
                detail = str(exc)
                if "230038" in detail or "230027" in detail:
                    try:
                        _bridge_send(chat_name(to, "p2p"), text)
                        emit({"type": "sent", "via": "browser-bridge"})
                        return
                    except Exception as bridge_exc:
                        detail = f"{detail}；浏览器桥失败：{bridge_exc}"
                    try:
                        from sugar_assistant import web_sender
                        result = web_sender.send_text(to, chat_name(to, "p2p"), text)
                    except Exception as web_exc:
                        result = None
                        detail = f"{detail}；web 兜底异常：{web_exc}"
                    if result is not None and result.ok:
                        emit({"type": "sent", "via": "web", "messageId": result.message_id})
                        return
                    if result is not None:
                        detail = f"{detail}；web 兜底{result.status}：{result.detail}"
                emit({"type": "error", "error": f"账户主发送失败：{detail}"})
                raise
            return

        if not message_id:
            # 重启后没有"上一条消息"可回复，改用主动发送（chat_id）
            body = (CreateMessageRequestBody.builder()
                    .receive_id(to).msg_type("text")
                    .content(json.dumps({"text": text}, ensure_ascii=False))
                    .uuid(uuid.uuid4().hex).build())
            request = CreateMessageRequest.builder().receive_id_type("chat_id").request_body(body).build()
            response = api.im.v1.message.create(request)
            if response is None or not response.success():
                raise RuntimeError(f"[{getattr(response, 'code', 'unknown')}] "
                                   f"{getattr(response, 'msg', 'create failed')}")
            return

        body = (
            ReplyMessageRequestBody.builder()
            .content(json.dumps({"text": text}, ensure_ascii=False))
            .msg_type("text")
            .uuid(uuid.uuid4().hex)
            .build()
        )
        request = ReplyMessageRequest.builder().message_id(message_id).request_body(body).build()
        response = api.im.v1.message.reply(request)
        if response is None or not response.success():
            raise RuntimeError(
                f"[{getattr(response, 'code', 'unknown')}] {getattr(response, 'msg', 'reply failed')}"
            )

    def send_card(to: str, card: dict, message_id: str) -> None:
        from lark_oapi.api.im.v1 import ReplyMessageRequest, ReplyMessageRequestBody
        import uuid

        if identity_mode.current() == "user":
            # 用户身份也能发 interactive（实测 22:58），不再降级成文字
            send_card_as_user(to, card)
            return

        sections = card.get("sections") or [{"body": card.get("body"), "options": card.get("options") or []}]
        elements: list[dict] = []
        for section in sections:
            elements.append({"tag": "markdown", "content": str(section.get("body") or "")})
            elements.append({"tag": "action", "actions": [
                {
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": str(opt.get("label") or opt.get("value"))},
                    "type": "primary" if index == 0 else "default",
                    "value": {"choice": str(opt.get("value"))},
                }
                for index, opt in enumerate(section.get("options") or [])
            ]})
        # 卡片 1.0：schema 2.0 不接受 action 块（错误 200861），按钮只能放在 1.0 的 elements 里
        payload = {
            "config": {"wide_screen_mode": True},
            "header": {"title": {"tag": "plain_text", "content": str(card.get("title") or "小Sugar助手")}},
            "elements": elements,
        }
        content = json.dumps(payload, ensure_ascii=False)
        if not message_id:
            from lark_oapi.api.im.v1 import CreateMessageRequest, CreateMessageRequestBody
            create_body = (CreateMessageRequestBody.builder()
                           .receive_id(to).msg_type("interactive").content(content)
                           .uuid(uuid.uuid4().hex).build())
            response = api.im.v1.message.create(
                CreateMessageRequest.builder().receive_id_type("chat_id").request_body(create_body).build())
            if response is None or not response.success():
                raise RuntimeError(f"[{getattr(response, 'code', 'unknown')}] "
                                   f"{getattr(response, 'msg', 'card create failed')}")
            return
        body = (
            ReplyMessageRequestBody.builder()
            .content(content)
            .msg_type("interactive")
            .uuid(uuid.uuid4().hex)
            .build()
        )
        request = ReplyMessageRequest.builder().message_id(message_id).request_body(body).build()
        response = api.im.v1.message.reply(request)
        if response is None or not response.success():
            raise RuntimeError(
                f"[{getattr(response, 'code', 'unknown')}] {getattr(response, 'msg', 'card failed')}"
            )

    def send_media(to: str, path: str, kind: str = "file") -> None:
        """发图片/文件。user 走 CLI；bot 先上传拿 key 再发。"""
        import os as _os
        import uuid as _uuid
        if not _os.path.exists(path):
            raise RuntimeError(f"附件不存在：{path}")
        if kind == "sticker":
            if identity_mode.current() == "user":
                raise RuntimeError("账户主身份暂不支持表情包")
            from lark_oapi.api.im.v1 import (CreateImageRequest, CreateImageRequestBody,
                                             CreateMessageRequest, CreateMessageRequestBody)
            with open(path, "rb") as fh:
                req = (CreateImageRequest.builder()
                       .request_body(CreateImageRequestBody.builder()
                                     .image_type("message").image(fh).build()).build())
            resp = api.im.v1.image.create(req)
            if resp is None or not resp.success():
                raise RuntimeError(f"[{getattr(resp, 'code', 'unknown')}] 上传表情失败")
            body = (CreateMessageRequestBody.builder()
                    .receive_id(to).msg_type("sticker")
                    .content(json.dumps({"file_key": resp.data.image_key}))
                    .uuid(_uuid.uuid4().hex).build())
            resp = api.im.v1.message.create(
                CreateMessageRequest.builder().receive_id_type("chat_id").request_body(body).build())
            if resp is None or not resp.success():
                raise RuntimeError(f"[{getattr(resp, 'code', 'unknown')}] 发送表情失败")
            return
        if identity_mode.current() == "user":
            try:
                _send_media_as_user(to, path, kind)
            except Exception as exc:
                detail = str(exc)
                if "230038" in detail or "230027" in detail:
                    from sugar_assistant import web_sender
                    result = web_sender.send_file(to, chat_name(to, "p2p"), path, kind)
                    if result.ok:
                        emit({"type": "sent", "via": "web", "messageId": result.message_id})
                        return
                    raise RuntimeError(f"{detail}；web 兜底{result.status}：{result.detail}")
                raise
            return
        from lark_oapi.api.im.v1 import (CreateImageRequest, CreateImageRequestBody,
                                         CreateFileRequest, CreateFileRequestBody,
                                         CreateMessageRequest, CreateMessageRequestBody)
        if kind == "image":
            with open(path, "rb") as fh:
                req = (CreateImageRequest.builder()
                       .request_body(CreateImageRequestBody.builder()
                                     .image_type("message").image(fh).build()).build())
            resp = api.im.v1.image.create(req)
            if resp is None or not resp.success():
                raise RuntimeError(f"[{getattr(resp, 'code', 'unknown')}] 上传图片失败")
            payload, msg_type = {"image_key": resp.data.image_key}, "image"
        else:
            with open(path, "rb") as fh:
                req = (CreateFileRequest.builder()
                       .request_body(CreateFileRequestBody.builder()
                                     .file_type("stream")
                                     .file_name(_os.path.basename(path))
                                     .file(fh).build()).build())
            resp = api.im.v1.file.create(req)
            if resp is None or not resp.success():
                raise RuntimeError(f"[{getattr(resp, 'code', 'unknown')}] 上传文件失败")
            payload, msg_type = {"file_key": resp.data.file_key}, "file"
        body = (CreateMessageRequestBody.builder()
                .receive_id(to).msg_type(msg_type)
                .content(json.dumps(payload, ensure_ascii=False))
                .uuid(_uuid.uuid4().hex).build())
        resp = api.im.v1.message.create(
            CreateMessageRequest.builder().receive_id_type("chat_id").request_body(body).build())
        if resp is None or not resp.success():
            raise RuntimeError(f"[{getattr(resp, 'code', 'unknown')}] 发送 {msg_type} 失败")

    def on_card_action(data) -> None:
        """卡片按钮点击：当成用户回了一个数字。"""
        try:
            event = data.event
            action = event.action
            value = action.value if isinstance(action.value, dict) else {}
            choice = str(value.get("choice") or "").strip()
            operator = str((event.operator.open_id if event.operator else "") or "")
            context = event.context or {}
            chat_id = str(getattr(context, "open_chat_id", "") or "") or operator
            message_id = str(getattr(context, "open_message_id", "") or f"card-{chat_id}")
            # 同一次点击可能被重复投递（长连接重连/客户端重试），按 (卡片, 选项, 操作者) 去重
            import time as _time
            dedupe_key = (message_id, choice, operator)
            now = _time.time()
            seen = _card_clicks.setdefault(dedupe_key, 0.0)
            if now - seen < 120:
                return {"toast": {"type": "info", "content": "已处理过该选项"}}
            _card_clicks[dedupe_key] = now
            for key, ts in list(_card_clicks.items()):
                if now - ts > 600:
                    _card_clicks.pop(key, None)
            if not choice:
                return {"toast": {"type": "info", "content": "没有可提交的选项"}}
            emit({
                "type": "inbound",
                "peerId": operator or chat_id,
                "chatId": chat_id,
                "groupId": "",
                "messageId": f"{message_id}:{choice}:{int(__import__('time').time() * 1000)}",
                "text": choice,
                "chatName": chat_name(chat_id),
            })
            return {"toast": {"type": "success", "content": f"已选择：{choice}"}}
        except Exception as exc:
            emit({"type": "error", "error": f"card action: {exc}"})
            return {"toast": {"type": "error", "content": "提交失败，请重试"}}

    def stdin_loop() -> None:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                command = json.loads(line)
            except json.JSONDecodeError:
                continue
            if command.get("type") == "stop":
                os._exit(0)
            if command.get("type") == "send":
                chat = str(command.get("to") or "")
                message_id = last_message.get(chat, "")
                # message_id 为空时 send_text 会用 chat_id 主动发送（重启后没有"上一条"）
                try:
                    media = command.get("media") or {}
                    if media.get("path"):
                        send_media(chat, str(media["path"]), str(media.get("kind") or "file"))
                        emit({"type": "sent", "id": command.get("id"), "ok": True,
                              "status": "sent", "media": True})
                        continue
                    text = str(command.get("text") or "")
                    import time as _time
                    _t0 = _time.perf_counter()
                    chunks = 0
                    for chunk in split_reply(text, MAX_REPLY_CHARS):
                        send_text(chat, chunk, message_id)
                        chunks += 1
                    emit({"type": "sent", "id": command.get("id"), "ok": True, "status": "sent",
                          "apiMs": round((_time.perf_counter() - _t0) * 1000), "chunks": chunks})
                except Exception as exc:
                    detail = str(exc)
                    try:
                        from sugar_assistant.results import describe as _describe
                        detail = _describe(detail)
                    except Exception:
                        pass
                    status = "unknown" if detail.startswith("unknown") else "failed"
                    emit({"type": "sent", "id": command.get("id"), "ok": False,
                          "status": status, "error": detail})
            if command.get("type") == "card":
                chat = str(command.get("to") or "")
                message_id = last_message.get(chat, "")
                try:
                    send_card(chat, command.get("card") or {}, message_id)
                    emit({"type": "sent", "id": command.get("id"), "ok": True, "status": "sent"})
                except Exception as exc:
                    emit({"type": "sent", "id": command.get("id"), "ok": False,
                          "status": "failed", "error": str(exc)})

    def guarded_stdin() -> None:
        stdin_loop()
        # 宿主进程没了（stdin 关闭）：立刻退出，避免孤儿长连接继续抢消息
        os._exit(0)

    threading.Thread(target=guarded_stdin, name="feishu-stdin", daemon=True).start()

    def poll_loop() -> None:
        """user 身份：飞书没有用户级事件推送，只能轮询指定会话。"""
        import time as _time
        seen: set[str] = set()
        primed: set[str] = set()
        self_id = ""
        started = _time.time()
        probes = ["的", "我", "你", "在"]
        probe_at = started + 30  # 先把已有会话跑起来，发现新会话稍后再做
        tick = 0
        while True:
            try:
                if identity_mode.current() != "user":
                    _time.sleep(3)
                    continue
                if not self_id:
                    self_id = _self_open_id()
                now = _time.time()
                if now - probe_at > 60:
                    probe_at = now
                    extra = [c for c in _discover_chats(probes) if c not in identity_mode.chats()]
                    for chat in extra:
                        identity_mode.add_chat(chat)
                all_chats = identity_mode.chats()
                # 轮询要省着用：每轮只查 2 个会话，轮转覆盖，避免 8 个会话每轮 12 秒
                batch = all_chats[(tick * 2) % len(all_chats):][:2] if all_chats else []
                tick += 1
                for chat in batch:
                    items = _poll_messages(chat)
                    emit({"type": "poll", "chat": chat[-8:], "items": len(items)})
                    if chat not in primed:
                        primed.add(chat)
                        for item in items:
                            # 只把「10 分钟以前」的旧消息标已读；刚发来的要处理，
                            # 否则重启一次就会吞掉上一轮没来得及回的消息。
                            if int(item.get("create_time") or 0) / 1000 < started - 600:
                                seen.add(str(item.get("message_id") or ""))
                        # 不 continue：启动后到达的消息要照常处理
                    for item in items:
                        mid = str(item.get("message_id") or "")
                        if not mid or mid in seen:
                            continue
                        seen.add(mid)
                        sender = item.get("sender") or {}
                        if is_service_sender(sender):
                            continue  # 服务号/应用消息只读不触发，避免登录通知之类拉起会话
                        # 机器人发的消息也当作"对方"处理：user 模式下机器人连接已停用，
                        # 回复又是本人身份发出（会被 self 过滤），不会形成回环。
                        body = item.get("body") or {}
                        try:
                            content = json.loads(body.get("content") or "{}")
                        except ValueError:
                            content = {}
                        if item.get("msg_type") == "sticker":
                            remember_sticker(str(content.get("file_key") or ""))
                            continue  # 贴纸只记录 key，不触发会话
                        if item.get("chat_type") == "group":
                            mentions = [str(((m.get("id") or {}).get("open_id") or "")) for m in (item.get("mentions") or [])]
                            if self_id and self_id not in mentions:
                                continue  # 群里只有 @ 我才响应，避免刷屏
                        text = str(content.get("text") or "").strip()
                        if str(sender.get("id") or "") == self_id and not text.startswith("/"):
                            continue  # 自己发的不回，避免自问自答；但允许用 / 命令切回 bot
                        if not text:
                            kind = str(item.get("msg_type") or "")
                            if kind == "interactive":
                                raw = str(body.get("content") or content or "")
                                title = ""
                                marker = 'title="'
                                pos = raw.find(marker)
                                if pos >= 0:
                                    title = raw[pos + len(marker):].split('"', 1)[0]
                                text = f"[卡片] {title}".strip() or "[卡片]"
                                emit({"type": "card", "messageId": mid, "title": title[:80]})
                            label = {"image": "图片", "audio": "语音", "video": "视频",
                                     "media": "文件", "file": "文件"}.get(kind)
                            if not text and not label:
                                continue
                            if label and not text:
                                try:
                                    path = _download_as_user(mid, kind, content)
                                    text = (f"[{label}] 已保存到本地：{path}" if path
                                            else f"[收到一条 {label} 消息，但取不到文件]")
                                except Exception as exc:
                                    text = f"[收到一条 {label} 消息，下载失败：{exc}]"
                                emit({"type": "media", "messageId": mid, "kind": kind, "chars": len(text)})
                        emit({"type": "inbound", "peerId": str(sender.get("id") or chat),
                              "chatId": chat, "groupId": chat if item.get("chat_type") == "group" else "",
                              "messageId": mid, "text": text,
                              "chatName": chat_name(chat, "group" if item.get("chat_type") == "group" else "p2p"),
                              "self": str(sender.get("id") or "") == self_id})
            except Exception as exc:
                emit({"type": "error", "error": f"poll: {exc}"})
            _time.sleep(4)

    # 常驻：轮询线程自己看当前模式，切 user 立刻开始收，切 bot 自动空转，
    # 不必等插件重载（重载只是顺手清待发队列）。
    threading.Thread(target=poll_loop, name="feishu-user-poll", daemon=True).start()

    handler = (
        lark.EventDispatcherHandler.builder("", "")
        .register_p2_im_message_receive_v1(on_event)
        .register_p2_card_action_trigger(on_card_action)
        .build()
    )
    ws = lark.ws.Client(
        settings.app_id, settings.app_secret,
        event_handler=handler, log_level=lark.LogLevel.INFO,
    )
    emit({"type": "ready"})
    try:
        ws.start()  # 阻塞直到删除/断线
    except Exception as exc:
        emit({"type": "error", "error": f"ws: {exc}"})
        return 1
    return 0


def _ensure_single_instance() -> None:
    """杀掉残留的 feishu_worker：两个长连接同时在线会让消息随机落到旧进程。"""
    pid_file = os.path.join(data_dir(), "feishu-worker.pid")
    try:
        if os.path.exists(pid_file):
            old = int(io_read(pid_file) or 0)
            if old and old != os.getpid():
                subprocess.run(["taskkill", "/F", "/PID", str(old)],
                               capture_output=True, text=True, timeout=10)
    except Exception:
        pass
    try:
        with open(pid_file, "w", encoding="utf-8") as fh:
            fh.write(str(os.getpid()))
    except OSError:
        pass



def io_read(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError:
        return ""


if __name__ == "__main__":
    raise SystemExit(main())
