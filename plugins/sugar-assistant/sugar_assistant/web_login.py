"""一次性扫码登录：弹出可见浏览器，登录成功后 profile 留在 data/browser-profile。

由控制台「浏览器兜底 → 扫码登录」触发；也可以在命令行运行：
    python -m sugar_assistant.web_login
"""
from __future__ import annotations

import json
import os
import time

from . import paths, web_sender

MARKER = "web-login.json"


def marker_path() -> str:
    return os.path.join(os.path.dirname(paths.config_path()), MARKER)


def main() -> int:
    from playwright.sync_api import sync_playwright

    cfg = web_sender.load_config()
    tenant = cfg["tenant"]
    if not tenant:
        print("未配置租户域名，先在控制台填写")
        return 2
    url = f"https://{tenant}/next/messenger/"
    os.makedirs(cfg["profile"], exist_ok=True)
    ok = False
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            cfg["profile"], channel="msedge", headless=False,
            viewport={"width": 1100, "height": 780})
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        for _ in range(120):  # 最长 10 分钟
            page.wait_for_timeout(5000)
            try:
                if page.url.startswith(f"https://{tenant}") and "/next/messenger" in page.url:
                    ok = True
                    break
            except Exception:
                pass
        ctx.close()
    with open(marker_path(), "w", encoding="utf-8") as fh:
        json.dump({"ok": ok, "at": int(time.time())}, fh)
    print("登录成功" if ok else "超时未登录")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
