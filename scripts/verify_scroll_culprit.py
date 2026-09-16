"""Measure what makes the page horizontally scrollable, before/after removing
the catalog trigger, to isolate whether the title-bar capsule is the culprit.

Run: python scripts/verify_scroll_culprit.py --base-url http://127.0.0.1:8192
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


PROBE = r"""
(() => {
  const de = document.documentElement;
  const bar = document.querySelector('.dock-rightbar');
  const surface = bar ? bar.querySelector('.dock-surface') : null;
  const overflowers = [];
  document.querySelectorAll('body *').forEach(el => {
    const r = el.getBoundingClientRect();
    if (r.width > 0 && r.right > window.innerWidth + 1) {
      overflowers.push({
        id: (el.id || String(el.className || el.tagName)).slice(0, 50),
        right: Math.round(r.right),
        cls: el.classList.contains('is-collapsed') ? 'collapsed' : '',
      });
    }
  });
  const styleOf = (el) => el ? getComputedStyle(el) : null;
  const bodyStyle = styleOf(document.body);
  return {
    winW: window.innerWidth,
    htmlScrollW: de.scrollWidth,
    htmlClientW: de.clientWidth,
    bodyScrollW: document.body.scrollWidth,
    bodyClientW: document.body.clientWidth,
    bodyOverflowX: bodyStyle ? bodyStyle.overflowX : null,
    htmlOverflowX: styleOf(de) ? styleOf(de).overflowX : null,
    overflowCount: overflowers.length,
    overflowers: overflowers.slice(0, 10),
    canScrollRight: (() => {
      const before = window.scrollX;
      window.scrollTo(9999, window.scrollY);
      const after = window.scrollX;
      const maxX = after;
      window.scrollTo(before, window.scrollY);
      return { maxScrollX: maxX };
    })(),
  };
})()
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:8192")
    args = ap.parse_args()
    base = args.base_url.rstrip("/")

    created = requests.post(base + "/sessions", timeout=90)
    created.raise_for_status()
    sid = str(created.json().get("session_id") or "")
    name = "scrollcheck " + uuid.uuid4().hex[:6]
    requests.put(base + f"/sessions/{sid}/name", data={"name": name}, timeout=30)

    # seed a couple of subagents so the trigger shows (worst case for title overflow)
    subs = ROOT / "workspace" / "sessions" / sid / "subagents"
    subs.mkdir(parents=True, exist_ok=True)
    now = time.time()
    rows = [{
        "task_id": str(uuid.uuid4()), "description": "scroll probe child",
        "subagent_type": "explore", "status": "completed",
        "started_at": now - 60, "finished_at": now - 30,
        "created_at": now - 60, "updated_at": now - 30, "background": False, "depth": 1,
    }]
    (subs / "tasks.json").write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    for row in rows:
        d = subs / row["task_id"]
        d.mkdir(parents=True, exist_ok=True)
        (d / "metadata.json").write_text(json.dumps(row, ensure_ascii=False), encoding="utf-8")

    debug_port = _free_port()
    profile = Path(tempfile.mkdtemp(prefix="myagent-scrollcheck-"))
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
        time.sleep(3)

        out["with_trigger"] = cdp.ev(PROBE)

        # 移除触发器后复测
        out["after_trigger_removed"] = cdp.ev(r"""
            (() => {
              const t = document.getElementById('subagent-catalog-trigger');
              if (t && t.parentNode) t.parentNode.removeChild(t);
              return %s;
            })()
        """ % PROBE)

        # 移除整个右侧停靠面板后复测
        out["after_dock_removed"] = cdp.ev(r"""
            (() => {
              const bar = document.querySelector('.dock-rightbar');
              if (bar && bar.parentNode) bar.parentNode.removeChild(bar);
              return %s;
            })()
        """ % PROBE)

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
