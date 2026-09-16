"""Reproduce the live-stream layout regression and audit duplicates.

1. Boots the app against the local server, opens a seeded session with a user
   turn + reasoning + tool + final rows (mimicking a live transcript).
2. Simulates the streaming path by adding a NEW assistant row through the same
   DOM operations the app uses (smooth-follow attribute + row append) and
   measures geometry before/after.
3. Reports: horizontal overflow, row widths, text-align of rows, duplicate CSS
   rules for process-aggregate.

Run: python scripts/verify_stream_layout.py --base-url http://127.0.0.1:8192
"""

from __future__ import annotations

import argparse
import json
import os
import re
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
        self.errors: list[str] = []

    def call(self, method: str, params: dict | None = None) -> dict:
        cid = self.next_id
        self.next_id += 1
        self.ws.send(json.dumps({"id": cid, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") != cid:
                if msg.get("method") == "Runtime.exceptionThrown":
                    d = msg["params"].get("exceptionDetails") or {}
                    self.errors.append((str(d.get("text") or "") + " " + str(((d.get("exception") or {}).get("description")) or ""))[:240])
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
    raise RuntimeError(f"timeout {label}: {expr[:100]}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:8192")
    args = ap.parse_args()
    base = args.base_url.rstrip("/")

    # ---- 1) 静态 CSS 层面：重复规则检测 ----
    css = open(ROOT / "frontend" / "src" / "styles" / "app.css", encoding="utf-8").read()
    counts: dict[str, int] = {}
    for m in re.finditer(r'([^{}]*)\{([^{}]*)\}', css):
        lines = [ln.strip() for ln in m.group(1).split('\n') if ln.strip()]
        sel = lines[-1] if lines else ''
        if sel and not sel.startswith('@'):
            counts[sel] = counts.get(sel, 0) + 1
    dupes = {s: n for s, n in counts.items() if n > 1}
    print(f'[CSS] 重复选择器 {len(dupes)} 个')
    for s, n in list(dupes.items())[:20]:
        print(f'   x{n}  {s[:150]}')

    # ---- 2) 浏览器层面 ----
    created = requests.post(base + "/sessions", timeout=90)
    created.raise_for_status()
    sid = str(created.json().get("session_id") or "")
    name = "streamcheck " + uuid.uuid4().hex[:6]
    requests.put(base + f"/sessions/{sid}/name", data={"name": name}, timeout=30)
    print("session:", sid, name)

    debug_port = _free_port()
    profile = Path(tempfile.mkdtemp(prefix="myagent-streamcheck-"))
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
        cdp.ev("(() => { localStorage.setItem('lastSessionId', " + json.dumps(sid) + "); return true; })()")
        cdp.call("Page.reload", {})
        wait(cdp, "!!document.getElementById('chat-stream')", 60, "shell")
        _ = name
        time.sleep(3)

        # 基础几何 + 横向溢出
        out["baseline"] = cdp.ev(r"""
            (() => {
              const de = document.documentElement;
              return {
                docScrollWidth: de.scrollWidth,
                docClientWidth: de.clientWidth,
                horizOverflow: de.scrollWidth > de.clientWidth + 1,
                innerWidth: window.innerWidth,
                whichOverflows: (() => {
                  const bad = [];
                  document.querySelectorAll('*').forEach(el => {
                    const r = el.getBoundingClientRect();
                    if (r.width > 0 && (r.right > window.innerWidth + 2 || r.left < -2)) {
                      const id = el.id || el.className || el.tagName;
                      bad.push(String(id).slice(0, 60) + ' [' + Math.round(r.left) + ',' + Math.round(r.right) + ']');
                    }
                  });
                  return bad.slice(0, 12);
                })(),
              };
            })()
        """)

        # 注入一个"流式"助手行：使用应用相同的结构与类（模拟 live 输出路径）
        out["after_stream_sim"] = cdp.ev(r"""
            (() => {
              const stream = document.getElementById('chat-stream');
              if (!stream) return { error: 'no stream' };
              const wrap = document.createElement('div');
              wrap.className = 'msg-wrap msg-wrap--assistant msg-wrap--answer-frame';
              const msg = document.createElement('div');
              msg.className = 'message assistant';
              msg.textContent = '流式模拟输出 — 检查是否向两侧增长';
              wrap.appendChild(msg);
              stream.appendChild(wrap);
              const cs = getComputedStyle(wrap);
              const ms = getComputedStyle(msg);
              const r = wrap.getBoundingClientRect();
              const streamRect = stream.getBoundingClientRect();
              return {
                wrapWidth: Math.round(r.width),
                wrapLeft: Math.round(r.left),
                wrapRight: Math.round(r.right),
                streamWidth: Math.round(streamRect.width),
                wrapTextAlign: cs.textAlign,
                msgTextAlign: ms.textAlign,
                streamAlignItems: getComputedStyle(stream).alignItems,
                streamJustify: getComputedStyle(stream).justifyContent,
                colWidthVar: getComputedStyle(document.querySelector('.main-center')).getPropertyValue('--content-column-width').trim(),
                docScrollWidth: document.documentElement.scrollWidth,
                docClientWidth: document.documentElement.clientWidth,
                horizOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
              };
            })()
        """)

        # smooth-follow 属性模拟
        out["after_smooth_follow"] = cdp.ev(r"""
            (() => {
              const stream = document.getElementById('chat-stream');
              stream.setAttribute('data-smooth-follow-owned', '1');
              const wrap = stream.querySelector('.msg-wrap--assistant');
              if (!wrap) return { error: 'no wrap' };
              const r = wrap.getBoundingClientRect();
              const streamRect = stream.getBoundingClientRect();
              return {
                wrapWidth: Math.round(r.width),
                streamWidth: Math.round(streamRect.width),
                wrapLeft: Math.round(r.left), wrapRight: Math.round(r.right),
                streamAlignItems: getComputedStyle(stream).alignItems,
                docScrollWidth: document.documentElement.scrollWidth,
                docClientWidth: document.documentElement.clientWidth,
                horizOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
              };
            })()
        """)

        # 标题栏触发器对宽度的影响
        out["titlebar"] = cdp.ev(r"""
            (() => {
              const row = document.querySelector('.breadcrumb-title-row');
              const title = document.getElementById('breadcrumb-text');
              const trigger = document.getElementById('subagent-catalog-trigger');
              const box = (el) => { if (!el) return null; const r = el.getBoundingClientRect();
                return { left: Math.round(r.left), right: Math.round(r.right), width: Math.round(r.width) }; };
              return {
                row: box(row), title: box(title), trigger: box(trigger),
                triggerExists: !!trigger,
                rowScrollW: row ? row.scrollWidth : null,
                rowClientW: row ? row.clientWidth : null,
              };
            })()
        """)

        out["console_errors"] = cdp.errors[:10]
        out["dock_probe"] = cdp.ev(r"""
            (() => {
              const bar = document.querySelector('.dock-rightbar');
              const surface = document.querySelector('.dock-rightbar > .dock-surface');
              const info = (el) => {
                if (!el) return null;
                const r = el.getBoundingClientRect();
                const cs = getComputedStyle(el);
                return {
                  rect: { left: Math.round(r.left), right: Math.round(r.right), width: Math.round(r.width) },
                  position: cs.position, transform: cs.transform,
                  width: cs.width, overflow: cs.overflow, display: cs.display, visibility: cs.visibility,
                  parents: (() => {
                    const chain = [];
                    let p = el.parentElement;
                    for (let i = 0; i < 4 && p; i += 1) {
                      const pr = p.getBoundingClientRect();
                      const pcs = getComputedStyle(p);
                      chain.push({
                        tag: p.tagName + (p.id ? ('#' + p.id) : '') + (p.className ? ('.' + String(p.className).split(/\s+/).slice(0, 2).join('.')) : ''),
                        rect: { left: Math.round(pr.left), right: Math.round(pr.right), width: Math.round(pr.width) },
                        overflowX: pcs.overflowX, position: pcs.position,
                      });
                      p = p.parentElement;
                    }
                    return chain;
                  })(),
                };
              };
              return {
                barClass: bar ? String(bar.className) : null,
                bar: info(bar),
                surface: info(surface),
              };
            })()
        """)
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0
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
