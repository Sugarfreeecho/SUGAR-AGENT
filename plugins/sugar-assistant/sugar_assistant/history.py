"""拉取飞书会话最近历史，供新会话首轮参考。

user 身份下读取是允许的（发送才受跨租户限制），所以历史能读到。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess


def _cli() -> str:
    exe = os.path.join(os.environ.get("APPDATA", ""), "npm", "lark-cli.cmd")
    if os.path.exists(exe):
        return exe
    return shutil.which("lark-cli") or ""


def recent(chat_id: str, limit: int = 20) -> str:
    exe = _cli()
    if not exe:
        return ""
    try:
        result = subprocess.run([exe, "im", "+chat-messages-list", "--as", "user",
                                 "--chat-id", chat_id, "--page-size", str(limit),
                                 "--order", "desc"],
                                capture_output=True, text=True, encoding="utf-8",
                                errors="replace", timeout=60)
    except Exception:
        return ""
    out = result.stdout or ""
    start = out.find("{")
    if start < 0:
        return ""
    try:
        data = json.loads(out[start:])
    except ValueError:
        return ""
    rows = []
    for item in reversed((data.get("data") or {}).get("messages") or []):
        sender = (item.get("sender") or {}).get("name") or ""
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        rows.append(f"{sender}: {content}")
    return "\n".join(rows[-limit:])
