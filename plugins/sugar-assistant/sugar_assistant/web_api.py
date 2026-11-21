"""飞书 Web 内部接口（/im/gateway）发送通道。

协议来自实测：
  POST https://internal-api-lark-api.feishu.cn/im/gateway/
  x-command: 5，body 为 protobuf Packet{cmd=5, payload=PutMessageRequest}
  chatId 必须是数字 id，oc_ 开头的 open chat id 会被服务端拒绝。

Cookie 来自已登录的浏览器会话（调试浏览器或 CDP 端口）。
"""
from __future__ import annotations

import json
import os
import random
import time
import urllib.request
from collections import deque

GATEWAY = "https://internal-api-lark-api.feishu.cn/im/gateway/"
ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
BASE36 = "0123456789abcdefghijklmnopqrstuvwxyz"
_SENT: deque[float] = deque()
RATE_LIMIT = 20  # 每分钟最多 20 条，超出直接失败，由调用方降级
def data_dir(path: str = "") -> str:
    root = ""
    try:
        from . import paths
        root = paths.data_dir()
    except Exception:
        root = (os.environ.get("SUGAR_ASSISTANT_DATA")
                or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"))
    return os.path.join(root, path) if path else root


def _varint(n: int) -> bytes:
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        out.append(b | 0x80 if n else b)
        if not n:
            return bytes(out)


def _tag(field: int, wire: int) -> bytes:
    return _varint((field << 3) | wire)


def _str(field: int, value: str) -> bytes:
    raw = value.encode("utf-8")
    return _tag(field, 2) + _varint(len(raw)) + raw


def _int(field: int, value: int) -> bytes:
    return _tag(field, 0) + _varint(value)


def _msg(field: int, body: bytes) -> bytes:
    return _tag(field, 2) + _varint(len(body)) + body


def build_text_packet(text: str, chat_id: str, request_id: str, cid: str = "") -> bytes:
    """Packet(cmd=5) + PutMessageRequest(type=4, richText 单元素)。"""
    cid = cid or "".join(random.choice(ALPHABET) for _ in range(10))
    element = _int(1, 1) + _msg(3, _str(1, text))
    entry = _str(1, cid) + _msg(2, element)
    rich = _str(1, cid) + _str(2, text) + _msg(3, _msg(1, entry))
    content = _msg(14, rich)
    put = (_int(1, 4) + _msg(2, content) + _str(3, str(chat_id)) + _str(6, cid)
           + _int(7, 1) + _int(9, 1))
    return _int(2, 1) + _int(3, 5) + _msg(5, put) + _str(6, request_id)


def build_sticker_packet(file_key: str, chat_id: str, request_id: str, cid: str = "") -> bytes:
    """type=10(STICKER)，Content.fileKey。实测 23:39 发出 msg_type=sticker。"""
    cid = cid or "".join(random.choice(ALPHABET) for _ in range(10))
    content = _str(6, file_key)
    put = (_int(1, 10) + _msg(2, content) + _str(3, str(chat_id)) + _str(6, cid)
           + _int(7, 1) + _int(9, 1))
    return _int(2, 1) + _int(3, 5) + _msg(5, put) + _str(6, request_id)


def build_post_packet(text: str, chat_id: str, request_id: str, cid: str = "") -> bytes:
    """type=2(POST)：实测落地为富文本消息。"""
    cid = cid or "".join(random.choice(ALPHABET) for _ in range(10))
    content = _str(1, text)
    put = (_int(1, 2) + _msg(2, content) + _str(3, str(chat_id)) + _str(6, cid)
           + _int(7, 1) + _int(9, 1))
    return _int(2, 1) + _int(3, 5) + _msg(5, put) + _str(6, request_id)


def _headers(tenant: str, request_id: str) -> dict:
    return {
        "accept": "*/*",
        "content-type": "application/x-protobuf",
        "locale": "zh_CN",
        "origin": f"https://{tenant}",
        "referer": f"https://{tenant}/",
        "user-agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/157.0.0.0 Safari/537.36 Edg/157.0.0.0"),
        "x-appid": "161471",
        "x-command": "5",
        "x-command-version": "5.7.0",
        "x-lgw-os-type": "1",
        "x-lgw-terminal-type": "2",
        "x-request-id": request_id,
        "x-source": "web",
        "x-web-version": "3.9.32",
    }


def cookies_from_cdp(port: int = 9335) -> dict:
    """从调试浏览器的 CDP 端口取 Cookie（含 HttpOnly）。"""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}", timeout=8000)
            context = browser.contexts[0]
            return {c["name"]: c["value"] for c in context.cookies() if "feishu.cn" in c["domain"]}
    except Exception:
        return {}


def load_cookies(config: dict) -> dict:
    cached = {}
    path = config.get("cookies_path") or data_dir("web-cookies.json")
    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
        cached = raw if isinstance(raw, dict) else {c["name"]: c["value"] for c in raw}
    except Exception:
        cached = {}
    if config.get("cdp_url"):
        port = int(str(config["cdp_url"]).rstrip("/").rsplit(":", 1)[-1])
        fresh = cookies_from_cdp(port)
        if fresh:
            cached.update(fresh)
            try:
                with open(path, "w", encoding="utf-8") as fh:
                    json.dump(cached, fh, ensure_ascii=False)
            except Exception:
                pass
    return cached


def load_map() -> dict:
    try:
        with open(data_dir("webapi-chats.json"), encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def _save_state(result: dict, chat_id: str = "") -> None:
    try:
        path = data_dir("webapi-state.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"ts": time.time(), "chat_id": chat_id,
                       "status": result.get("status"), "detail": result.get("detail", "")[:200]},
                      fh, ensure_ascii=False)
    except Exception:
        pass


def load_state() -> dict:
    try:
        with open(data_dir("webapi-state.json"), encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def numeric_chat_id(chat_id: str, name: str = "") -> str:
    mapping = load_map()
    item = mapping.get(chat_id) or (mapping.get(name) if name else None)
    if isinstance(item, dict):
        return str(item.get("id") or "")
    return str(item or "")


def send_text(chat_id: str, text: str, name: str = "", config: dict | None = None) -> dict:
    """返回 {status: sent|failed, detail, message_id?}；不做重试，调用方决定降级。"""
    config = config or {}
    limit = int(config.get("api_rate_limit") or RATE_LIMIT)
    now = time.time()
    while _SENT and now - _SENT[0] > 60:
        _SENT.popleft()
    if len(_SENT) >= limit:
        result = {"status": "failed", "detail": f"webapi: 触发限流（{limit}/分钟）"}
        _save_state(result, chat_id)
        return result
    tenant = config.get("tenant") or "acneut3zrdux.feishu.cn"
    numeric = numeric_chat_id(chat_id, name)
    if not numeric:
        result = {"status": "failed", "detail": "webapi: 没有数字 chatId 映射"}
        _save_state(result, chat_id)
        return result
    cookies = load_cookies(config)
    if not cookies.get("session"):
        result = {"status": "failed", "detail": "webapi: 没有登录 Cookie"}
        _save_state(result, chat_id)
        return result
    request_id = "".join(random.choice(BASE36) for _ in range(10))
    body = build_text_packet(text, numeric, request_id)
    req = urllib.request.Request(GATEWAY, data=body, headers=_headers(tenant, request_id), method="POST")
    cookie_header = "; ".join(f"{k}={v}" for k, v in cookies.items())
    req.add_header("Cookie", cookie_header)
    started = time.time()
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            payload = resp.read()
            ok = resp.status == 200 and text.encode("utf-8") in payload
            result = {"status": "sent" if ok else "unknown", "detail": f"webapi: http {resp.status}",
                      "echo": ok, "elapsed": round(time.time() - started, 2)}
            if ok:
                _SENT.append(time.time())
            _save_state(result, chat_id)
            return result
    except Exception as exc:
        result = {"status": "failed", "detail": f"webapi: {exc}"}
        _save_state(result, chat_id)
        return result


def send_sticker(chat_id: str, file_key: str, name: str = "", config: dict | None = None) -> dict:
    """用 Web 网关发贴纸（type=10）。file_key 来自收到过的贴纸消息。"""
    config = config or {}
    numeric = numeric_chat_id(chat_id, name)
    if not numeric:
        return {"status": "failed", "detail": "webapi: 没有数字 chatId 映射"}
    if not file_key:
        return {"status": "failed", "detail": "webapi: 缺少 file_key"}
    cookies = load_cookies(config)
    if not cookies.get("session"):
        return {"status": "failed", "detail": "webapi: 没有登录 Cookie"}
    request_id = "".join(random.choice(BASE36) for _ in range(10))
    body = build_sticker_packet(file_key, numeric, request_id)
    req = urllib.request.Request(GATEWAY, data=body,
                                 headers=_headers(config.get("tenant") or "acneut3zrdux.feishu.cn",
                                                  request_id), method="POST")
    req.add_header("Cookie", "; ".join(f"{k}={v}" for k, v in cookies.items()))
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            payload = resp.read()
            ok = resp.status == 200 and file_key.encode() in payload
            result = {"status": "sent" if ok else "unknown", "detail": f"webapi: http {resp.status}"}
            _save_state(result, chat_id)
            return result
    except Exception as exc:
        result = {"status": "failed", "detail": f"webapi: {exc}"}
        _save_state(result, chat_id)
        return result


def send_post(chat_id: str, text: str, name: str = "", config: dict | None = None) -> dict:
    """用 Web 网关发富文本（type=2）。"""
    config = config or {}
    numeric = numeric_chat_id(chat_id, name)
    if not numeric:
        return {"status": "failed", "detail": "webapi: 没有数字 chatId 映射"}
    cookies = load_cookies(config)
    if not cookies.get("session"):
        return {"status": "failed", "detail": "webapi: 没有登录 Cookie"}
    request_id = "".join(random.choice(BASE36) for _ in range(10))
    body = build_post_packet(text, numeric, request_id)
    req = urllib.request.Request(GATEWAY, data=body,
                                 headers=_headers(config.get("tenant") or "acneut3zrdux.feishu.cn",
                                                  request_id), method="POST")
    req.add_header("Cookie", "; ".join(f"{k}={v}" for k, v in cookies.items()))
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            ok = resp.status == 200 and text.encode("utf-8") in resp.read()
            result = {"status": "sent" if ok else "unknown", "detail": f"webapi: http {resp.status}"}
            _save_state(result, chat_id)
            return result
    except Exception as exc:
        result = {"status": "failed", "detail": f"webapi: {exc}"}
        _save_state(result, chat_id)
        return result
