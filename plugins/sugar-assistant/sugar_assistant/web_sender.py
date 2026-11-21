"""浏览器兜底发送器（跨租户单聊唯一可用路径）。

设计见 docs/浏览器补发通道方案.md：
  * 只负责发送，不接收入；
  * 成功判定只认 lark-cli 只读回查，不信前端状态；
  * 串行、幂等、失败分类，不盲目重试。

用法（手工验证）：
    python -m sugar_assistant.web_sender --chat-name 王影 --text "你好"
"""
from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Optional

from . import paths

MESSENGER = "https://{tenant}/next/messenger/"
SELECTORS = {
    "search": 'input[placeholder*="搜索"], .search-input input',
    "composer": ".zone-container, [contenteditable='true']",
    "send": ".submit__button button",
    "header": ".chat-title, .header-title, [class*='chatHeader']",
    "file": "input[type=file]",
}


def _config_path() -> str:
    return os.path.join(os.path.dirname(paths.config_path()), "web.json")


def load_config() -> dict:
    try:
        # PowerShell 写出的 UTF-8 带 BOM，用 utf-8-sig 兼容两种来源
        with open(_config_path(), "r", encoding="utf-8-sig") as fh:
            raw = json.load(fh)
    except Exception:
        raw = {}
    return {
        "enabled": bool(raw.get("enabled", False)),
        "tenant": str(raw.get("tenant") or "").strip(),
        "profile": str(raw.get("profile") or os.path.join(os.path.dirname(paths.config_path()), "browser-profile")),
        "cdp_url": str(raw.get("cdp_url") or "").strip(),
        "headless": bool(raw.get("headless", True)),
        "timeout_ms": int(raw.get("timeout_ms", 15000)),
        "allow": [str(x) for x in (raw.get("allow") or [])],
    }


@dataclass
class SendResult:
    ok: bool
    status: str  # sent | unknown | failed
    detail: str = ""
    message_id: str = ""


def _cli(args: list[str], timeout: int = 120) -> str:
    exe = os.path.join(os.environ.get("APPDATA", ""), "npm", "lark-cli.cmd")
    if not os.path.exists(exe):
        exe = "lark-cli"
    result = subprocess.run([exe, *args], capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=timeout)
    return (result.stdout or "") + (result.stderr or "")


_SELF_ID = {"value": ""}
_LOCK = threading.Lock()
_RECENT: dict[tuple[str, str], tuple[float, "SendResult"]] = {}
IDEMPOTENT_WINDOW_SEC = 60.0


def self_open_id() -> str:
    if _SELF_ID["value"]:
        return _SELF_ID["value"]
    out = _cli(["auth", "status", "--json"])
    start = out.find("{")
    if start < 0:
        return ""
    try:
        data = json.loads(out[start:])
        _SELF_ID["value"] = str(((data.get("identities") or {}).get("user") or {}).get("openId") or "")
    except ValueError:
        return ""
    return _SELF_ID["value"]


def verify_sent(chat_id: str, text: str, since_ts: float) -> str:
    """回查最近消息，返回命中的 message_id；没有则空串。"""
    me = self_open_id()
    out = _cli(["im", "+chat-messages-list", "--as", "user", "--chat-id", chat_id,
                "--page-size", "5", "--order", "desc"])
    start = out.find("{")
    if start < 0:
        return ""
    try:
        data = json.loads(out[start:])
    except ValueError:
        return ""
    for item in (data.get("data") or {}).get("messages") or []:
        if str(item.get("content") or "").strip() != text.strip():
            continue
        sender = item.get("sender") or {}
        if me and str(sender.get("id") or "") != me:
            continue
        if not me and sender.get("sender_type") != "user":
            continue
        raw = str(item.get("create_time") or "")
        try:
            ts = time.mktime(time.strptime(raw, "%Y-%m-%d %H:%M")) if raw else 0
        except ValueError:
            ts = 0
        if ts and ts + 60 < since_ts:
            continue
        return str(item.get("message_id") or "")
    return ""


def verify_media(chat_id: str, since_ts: float,
                 kinds: tuple[str, ...] = ("image", "file", "media")) -> str:
    me = self_open_id()
    out = _cli(["im", "+chat-messages-list", "--as", "user", "--chat-id", chat_id,
                "--page-size", "5", "--order", "desc"])
    start = out.find("{")
    if start < 0:
        return ""
    try:
        data = json.loads(out[start:])
    except ValueError:
        return ""
    for item in (data.get("data") or {}).get("messages") or []:
        if str(item.get("msg_type") or "") not in kinds:
            continue
        sender = item.get("sender") or {}
        if me and str(sender.get("id") or "") != me:
            continue
        raw = str(item.get("create_time") or "")
        try:
            ts = time.mktime(time.strptime(raw, "%Y-%m-%d %H:%M")) if raw else 0
        except ValueError:
            ts = 0
        if ts and ts + 60 < since_ts:
            continue
        return str(item.get("message_id") or "")
    return ""


class WebSender:
    """一个进程内单例：一个浏览器上下文，串行发送。"""

    def __init__(self, config: Optional[dict] = None) -> None:
        self.cfg = config or load_config()
        self._ctx = None
        self._page = None

    # ---------------------------------------------------------------- 生命周期
    def available(self) -> tuple[bool, str]:
        if not self.cfg["enabled"]:
            return False, "web 通道未启用"
        if not self.cfg["tenant"]:
            return False, "未配置租户域名"
        try:
            import playwright  # noqa: F401
        except ImportError:
            return False, "未安装 playwright"
        if self.cfg.get("cdp_url"):
            import urllib.request
            try:
                with urllib.request.urlopen(self.cfg["cdp_url"].rstrip("/") + "/json/version", timeout=3) as resp:
                    if resp.status == 200:
                        return True, ""
            except Exception as exc:
                return False, f"CDP 端口不可用：{exc}"
        if not os.path.isdir(self.cfg["profile"]):
            return False, "浏览器 profile 不存在，需要先扫码登录"
        cookies = os.path.join(self.cfg["profile"], "Default", "Network", "Cookies")
        if not os.path.exists(cookies):
            return False, "浏览器 profile 里没有登录 Cookie，需要先扫码登录"
        return True, ""

    def _ensure_page(self):
        from playwright.sync_api import sync_playwright
        if self._page is not None:
            return self._page
        self._pw = sync_playwright().start()
        if self.cfg.get("cdp_url"):
            # 直接接管用户已登录的 Edge：不需要另建 profile，也不需要再扫码
            self._browser = self._pw.chromium.connect_over_cdp(self.cfg["cdp_url"])
            contexts = self._browser.contexts or []
            self._ctx = contexts[0] if contexts else self._browser.new_context()
            for page in self._ctx.pages:
                if "feishu.cn" in page.url:
                    self._page = page
                    break
            if self._page is None:
                self._page = self._ctx.new_page()
                self._page.goto(MESSENGER.format(tenant=self.cfg["tenant"]),
                                wait_until="domcontentloaded", timeout=60000)
            self._page.wait_for_timeout(3000)
            if "accounts.feishu.cn" in self._page.url:
                raise RuntimeError("登录态失效，需要重新登录")
            return self._page
        self._ctx = self._pw.chromium.launch_persistent_context(
            self.cfg["profile"], channel="msedge", headless=self.cfg["headless"],
            viewport={"width": 1280, "height": 820})
        self._page = self._ctx.pages[0] if self._ctx.pages else self._ctx.new_page()
        self._page.goto(MESSENGER.format(tenant=self.cfg["tenant"]),
                        wait_until="domcontentloaded", timeout=60000)
        self._page.wait_for_timeout(3000)
        if "accounts.feishu.cn" in self._page.url:
            raise RuntimeError("登录态失效，需要重新扫码")
        return self._page

    def close(self) -> None:
        try:
            if getattr(self, "_browser", None):
                # CDP 接管模式：只断开，绝不能关掉用户的浏览器
                self._pw.stop()
                return
            if self._ctx:
                self._ctx.close()
            if getattr(self, "_pw", None):
                self._pw.stop()
        finally:
            self._ctx = self._page = None
            self._browser = None

    # ---------------------------------------------------------------- 发送
    def send(self, chat_id: str, chat_name: str, text: str) -> SendResult:
        ok, why = self.available()
        if not ok:
            return SendResult(False, "failed", why)
        if self.cfg["allow"] and chat_name not in self.cfg["allow"]:
            return SendResult(False, "failed", f"{chat_name} 不在白名单")
        key = (chat_id, text.strip())
        with _LOCK:
            cached = _RECENT.get(key)
            if cached and time.time() - cached[0] < IDEMPOTENT_WINDOW_SEC:
                return cached[1]
            return self._send_locked(key, chat_id, chat_name, text)

    def _send_locked(self, key, chat_id: str, chat_name: str, text: str) -> SendResult:
        started = time.time()
        try:
            page = self._ensure_page()
        except Exception as exc:
            return SendResult(False, "failed", f"打开失败：{exc}")

        try:
            page.get_by_text(chat_name, exact=True).first.click(timeout=self.cfg["timeout_ms"])
            page.wait_for_timeout(1200)
            header = page.locator(SELECTORS["header"]).first
            title = header.inner_text(timeout=3000) if header.count() else ""
            if title and chat_name not in title:
                return SendResult(False, "failed", f"会话标题不符：{title}")

            box = page.locator(SELECTORS["composer"]).first
            box.click()
            box.fill(text)
            page.wait_for_timeout(200)
            if box.inner_text().strip() != text.strip():
                return SendResult(False, "failed", "输入框内容与待发文本不一致")

            page.locator(SELECTORS["send"]).first.click(timeout=self.cfg["timeout_ms"])
            page.wait_for_timeout(1500)
        except Exception as exc:
            return SendResult(False, "failed", f"DOM 操作失败：{exc}")

        message_id = verify_sent(chat_id, text, started)
        if message_id:
            result = SendResult(True, "sent", "", message_id)
        else:
            result = SendResult(False, "unknown", "已点击发送但回查不到，按未知处理，不重发")
        _RECENT[key] = (time.time(), result)
        return result

    def send_media(self, chat_id: str, chat_name: str, path: str, kind: str = "file") -> SendResult:
        ok, why = self.available()
        if not ok:
            return SendResult(False, "failed", why)
        if not os.path.exists(path):
            return SendResult(False, "failed", f"文件不存在：{path}")
        key = (chat_id, f"media:{os.path.basename(path)}")
        with _LOCK:
            cached = _RECENT.get(key)
            if cached and time.time() - cached[0] < IDEMPOTENT_WINDOW_SEC:
                return cached[1]
            started = time.time()
            try:
                page = self._ensure_page()
                page.get_by_text(chat_name, exact=True).first.click(timeout=self.cfg["timeout_ms"])
                page.wait_for_timeout(1200)
                page.locator(SELECTORS["file"]).last.set_input_files(path)
                page.wait_for_timeout(2500)
                send_btn = page.locator(SELECTORS["send"]).first
                if send_btn.count() and send_btn.is_enabled():
                    send_btn.click(timeout=self.cfg["timeout_ms"])
                    page.wait_for_timeout(2000)
            except Exception as exc:
                result = SendResult(False, "failed", f"附件上传失败：{exc}")
                _RECENT[key] = (time.time(), result)
                return result
            message_id = verify_media(chat_id, started)
            result = (SendResult(True, "sent", "", message_id) if message_id
                      else SendResult(False, "unknown", "已上传但回查不到，按未知处理"))
            _RECENT[key] = (time.time(), result)
            return result


def send_text(chat_id: str, chat_name: str, text: str) -> SendResult:
    sender = WebSender()
    try:
        return sender.send(chat_id, chat_name, text)
    finally:
        sender.close()


def send_file(chat_id: str, chat_name: str, path: str, kind: str = "file") -> SendResult:
    sender = WebSender()
    try:
        return sender.send_media(chat_id, chat_name, path, kind)
    finally:
        sender.close()


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="浏览器兜底发送")
    parser.add_argument("--chat-id", required=True)
    parser.add_argument("--chat-name", required=True)
    parser.add_argument("--text", default="")
    parser.add_argument("--file", default="")
    parser.add_argument("--kind", default="file")
    args = parser.parse_args()
    if args.file:
        result = send_file(args.chat_id, args.chat_name, args.file, args.kind)
    else:
        result = send_text(args.chat_id, args.chat_name, args.text)
    print(json.dumps(result.__dict__, ensure_ascii=False))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
