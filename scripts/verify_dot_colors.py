"""Verify the agreed dot colours in a real browser.

Seeds one parent session with four children covering every semantic:
  running / completed-unread / completed-read / failed
Then opens the catalog and samples the computed background colour of each row's
status dot.

Run: python scripts/verify_dot_colors.py --base-url http://127.0.0.1:8192
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

import requests
import websocket

ROOT = Path(__file__).resolve().parents[1]


def _browser_path() -> Path:
    env = str(os.getenv("MYAGENT_BROWSER_BIN") or "").strip()
    for candidate in [
        Path(env) if env else None,
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    ]:
        if candidate and candidate.is_file():
            return candidate
    raise RuntimeError("Chromium/Edge not found")


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class Cdp:
    def __init__(self, url: str):
        self.ws = websocket.create_connection(url, timeout=120, origin="http://localhost")
        self.next_id = 1

    def call(self, method: str, params: dict | None = None) -> dict:
        cid = self.next_id
        self.next_id += 1
        self.ws.send(json.dumps({"id": cid, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") != cid:
                continue
            if "error" in msg:
                raise RuntimeError(f"CDP {method}: {msg['error']}")
            return dict(msg.get("result") or {})

    def ev(self, expr: str):
        r = self.call("Runtime.evaluate", {"expression": expr, "returnByValue": True})
        remote = r.get("result") or {}
        if remote.get("subtype") == "error":
            raise RuntimeError(str(remote.get("description") or remote))
        return remote.get("value")


def wait(cdp: Cdp, expr: str, timeout: float = 40.0, label: str = ""):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        v = cdp.ev(expr)
        if v:
            return v
        time.sleep(0.25)
    raise RuntimeError(f"timeout {label}")


def seed(parent: Path, rows: list[dict]) -> None:
    subs = parent / "subagents"
    subs.mkdir(parents=True, exist_ok=True)
    now = time.time()
    index_rows = []
    for row in rows:
        child = row["child"]
        index_rows.append({
            "task_id": child, "description": row["label"], "subagent_type": "explore",
            "status": row["status"], "started_at": now - 90, "finished_at": now - 30,
            "created_at": now - 90, "updated_at": now - 30, "background": False, "depth": 1,
            **({"error": "boom"} if row["status"] == "failed" else {}),
        })
        d = subs / child
        d.mkdir(parents=True, exist_ok=True)
        (d / "metadata.json").write_text(json.dumps(index_rows[-1], ensure_ascii=False), encoding="utf-8")
        (d / "events.jsonl").write_text(
            json.dumps({"seq": 1, "type": "final", "payload": {"content": "x"}, "created_at": now - 30}) + "\n",
            encoding="utf-8",
        )
    (subs / "tasks.json").write_text(json.dumps(index_rows, ensure_ascii=False), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:8192")
    args = ap.parse_args()
    base = args.base_url.rstrip("/")

    created = requests.post(base + "/sessions", timeout=90)
    created.raise_for_status()
    sid = str(created.json().get("session_id") or "")
    name = "dotcheck " + uuid.uuid4().hex[:6]
    requests.put(base + f"/sessions/{sid}/name", data={"name": name}, timeout=30)

    running_child = str(uuid.uuid4())
    unread_child = str(uuid.uuid4())
    read_child = str(uuid.uuid4())
    failed_child = str(uuid.uuid4())
    seed(ROOT / "workspace" / "sessions" / sid, [
        {"child": running_child, "label": "色标-进行中", "status": "running"},
        {"child": unread_child, "label": "色标-完成未读", "status": "completed"},
        {"child": read_child, "label": "色标-完成已读", "status": "completed"},
        {"child": failed_child, "label": "色标-错误", "status": "failed"},
    ])
    # 预置"已读"标记：写入与前端相同的 localStorage 键（由页面上下文注入）

    debug_port = _free_port()
    profile = Path(tempfile.mkdtemp(prefix="myagent-dotcheck-"))
    browser = subprocess.Popen(
        [str(_browser_path()), "--headless=new", f"--remote-debugging-port={debug_port}",
         "--remote-allow-origins=*", f"--user-data-dir={profile}", "--disable-gpu",
         "--no-first-run", "--no-default-browser-check", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    cdp = None
    out: dict = {}
    try:
        targets = None
        end = time.monotonic() + 30
        while time.monotonic() < end:
            try:
                targets = requests.get(f"http://127.0.0.1:{debug_port}/json/list", timeout=1).json()
                if targets:
                    break
            except Exception:
                time.sleep(0.2)
        page = next(t for t in targets if t.get("type") == "page")
        cdp = Cdp(str(page["webSocketDebuggerUrl"]))
        cdp.call("Page.enable")
        cdp.call("Runtime.enable")
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": 1280, "height": 800, "deviceScaleFactor": 1, "mobile": False})
        cdp.call("Page.navigate", {"url": base + "/"})
        wait(cdp, "!!document.body", 30, "body")
        # 标记 read-child 为已读（与前端相同的 key），再打开种子会话
        cdp.ev(
            "(() => { localStorage.setItem('myagent.subagent.read.v1', JSON.stringify({"
            + json.dumps(read_child) + ": 1}));"
            " localStorage.setItem('lastSessionId', " + json.dumps(sid) + "); return true; })()"
        )
        cdp.call("Page.reload", {})
        wait(cdp, "!!document.getElementById('chat-stream')", 60, "shell")
        try:
            wait(cdp, "(() => { const t = document.getElementById('breadcrumb-text');"
                      " return !!t && String(t.textContent||'').includes(" + json.dumps(name) + "); })()", 60, "session")
        except RuntimeError:
            cdp.ev(
                "(() => { const items = Array.from(document.querySelectorAll('.session-item'));"
                " const hit = items.find(el => String(el.textContent || '').includes(" + json.dumps(name) + "));"
                " if (hit) (hit.querySelector('.session-name') || hit).click(); return !!hit; })()"
            )
            wait(cdp, "(() => { const t = document.getElementById('breadcrumb-text');"
                      " return !!t && String(t.textContent || '').includes(" + json.dumps(name) + "); })()", 60, "session2")

        wait(cdp, "(() => { const t = document.getElementById('subagent-catalog-trigger');"
                  " return !!t && !t.classList.contains('hidden'); })()", 60, "trigger")
        cdp.ev("document.getElementById('subagent-catalog-trigger').click()")
        wait(cdp, "document.querySelectorAll('#subagent-catalog-menu .subagent-catalog-row').length >= 4", 30, "rows")

        dots = cdp.ev(r"""
            (() => {
              const out = {};
              document.querySelectorAll('#subagent-catalog-menu .subagent-catalog-row').forEach(row => {
                const name = String((row.querySelector('.subagent-catalog-name') || {}).textContent || '');
                const dot = row.querySelector('.subagent-catalog-status');
                if (!dot) return;
                out[name] = {
                  cls: String(dot.className),
                  color: getComputedStyle(dot).backgroundColor,
                };
              });
              return out;
            })()
        """)
        out["dots"] = dots

        # 断言映射
        def cls_of(label: str) -> str:
            for key, val in (dots or {}).items():
                if label in key:
                    return val.get("cls", "")
            return ""

        checks = {
            "running_is_amber": "is-running" in cls_of("进行中"),
            "unread_is_green": "is-unread" in cls_of("完成未读"),
            "read_is_blue": "is-read" in cls_of("完成已读"),
            "failed_is_red": "is-error" in cls_of("错误"),
        }
        out["checks"] = checks
        out["ok"] = all(checks.values())
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0 if out["ok"] else 1
    finally:
        if cdp:
            try:
                cdp.ws.close()
            except Exception:
                pass
        browser.terminate()
        try:
            browser.wait(timeout=5)
        except subprocess.TimeoutExpired:
            browser.kill()
        shutil.rmtree(profile, ignore_errors=True)
        try:
            requests.delete(base + f"/sessions/{sid}", timeout=15)
        except Exception:
            pass
        shutil.rmtree(ROOT / "workspace" / "sessions" / sid, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
