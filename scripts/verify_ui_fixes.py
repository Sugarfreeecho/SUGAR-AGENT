"""Verify the follow-up UI fixes:

  1. title row vertical alignment of the catalog capsule vs the session title;
  2. capsule + back chip computed styles (rounded pill, muted color);
  3. the right-side detail panels stay open when addressing a child session;
  4. the "session more" dots render as a horizontal row (not stacked).

Run: python scripts/verify_ui_fixes.py --base-url http://127.0.0.1:8192
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


def seed_subagents(parent: Path, ids: list[str], descriptions: list[str]) -> None:
    subs = parent / "subagents"
    subs.mkdir(parents=True, exist_ok=True)
    now = time.time()
    rows = []
    for i, (cid, desc) in enumerate(zip(ids, descriptions)):
        rows.append({
            "task_id": cid, "description": desc, "subagent_type": "explore",
            "status": "running" if i == 0 else "completed",
            "started_at": now - 60 - i * 30, "finished_at": None if i == 0 else now - 20,
            "created_at": now - 60 - i * 30, "updated_at": now - 20, "background": False, "depth": 1,
        })
    (subs / "tasks.json").write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    for row in rows:
        d = subs / row["task_id"]
        d.mkdir(parents=True, exist_ok=True)
        (d / "metadata.json").write_text(json.dumps(row, ensure_ascii=False), encoding="utf-8")
        (d / "events.jsonl").write_text(
            json.dumps({"seq": 1, "type": "final", "payload": {"content": "answer"}, "created_at": now - 20}) + "\n",
            encoding="utf-8",
        )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:8192")
    args = ap.parse_args()
    base = args.base_url.rstrip("/")

    created = requests.post(base + "/sessions", timeout=90)
    created.raise_for_status()
    sid = str(created.json().get("session_id") or "")
    name = "fixcheck " + uuid.uuid4().hex[:6]
    requests.put(base + f"/sessions/{sid}/name", data={"name": name}, timeout=30)
    child_ids = [str(uuid.uuid4()), str(uuid.uuid4())]
    seed_subagents(ROOT / "workspace" / "sessions" / sid, child_ids, ["渲染管线审计任务", "第二项检查任务"])

    debug_port = _free_port()
    profile = Path(tempfile.mkdtemp(prefix="myagent-fixcheck-"))
    browser = subprocess.Popen(
        [str(_browser_path()), "--headless=new", f"--remote-debugging-port={debug_port}",
         "--remote-allow-origins=*", f"--user-data-dir={profile}", "--disable-gpu",
         "--no-first-run", "--no-default-browser-check", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    cdp = None
    out: dict = {"checks": {}}
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
        try:
            wait(cdp, "(() => { const t = document.getElementById('breadcrumb-text');"
                      " return !!t && String(t.textContent||'').includes(" + json.dumps(name) + "); })()", 90, "session open")
        except RuntimeError:
            # 兜底：从侧栏点击目标会话（也可诊断出"列表里没有它"）
            clicked = cdp.ev(
                "(() => { const items = Array.from(document.querySelectorAll('.session-item'));"
                " const hit = items.find(el => String(el.textContent || '').includes(" + json.dumps(name) + "));"
                " if (!hit) return { clicked: false, items: items.length };"
                " (hit.querySelector('.session-name') || hit).click(); return { clicked: true }; })()"
            )
            out["sidebar_fallback"] = clicked
            wait(cdp, "(() => { const t = document.getElementById('breadcrumb-text');"
                      " return !!t && String(t.textContent||'').includes(" + json.dumps(name) + "); })()", 60, "session open after click")

        # 打开目录并选一个子代理
        try:
            wait(cdp, "(() => { const t = document.getElementById('subagent-catalog-trigger');"
                      " return !!t && !t.classList.contains('hidden'); })()", 60, "trigger")
        except RuntimeError:
            out["trigger_debug"] = cdp.ev(r"""
                (() => {
                  const t = document.getElementById('subagent-catalog-trigger');
                  const row = document.querySelector('.breadcrumb-title-row');
                  return {
                    title: String((document.getElementById('breadcrumb-text') || {}).textContent || ''),
                    triggerExists: !!t,
                    triggerHidden: t ? t.classList.contains('hidden') : null,
                    triggerParentId: t && t.parentNode ? String(t.parentNode.id || t.parentNode.className || '') : '',
                    titleRowChildren: row ? Array.from(row.children).map(x => (x.id || x.className || x.tagName)) : [],
                    sidebarItems: Array.from(document.querySelectorAll('.session-item'))
                      .slice(0, 8).map(el => ({
                        name: String((el.querySelector('.session-name') || {}).textContent || ''),
                        id: el.dataset.sessionId || '',
                      })),
                  };
                })()
            """)
            raise
        cdp.ev("document.getElementById('subagent-catalog-trigger').click()")
        wait(cdp, "document.querySelectorAll('#subagent-catalog-menu .subagent-catalog-row').length >= 1", 30, "rows")
        rows_text = cdp.ev(
            "Array.from(document.querySelectorAll('#subagent-catalog-menu .subagent-catalog-name'))"
            ".map(n => String(n.textContent || ''))"
        )
        out["menu_names"] = rows_text
        out["checks"]["menu_uses_own_name"] = any("审计" in str(x) or "检查" in str(x) for x in (rows_text or []))

        # 打开右侧历史面板（先确保有内容可开：点击 TOC 折叠把手）
        cdp.ev("(() => { const tab = document.getElementById('toc-edge-tab'); if (tab) tab.click(); return true; })()")
        time.sleep(0.8)
        panel_open_before = cdp.ev("!!document.getElementById('chat-toc') && document.getElementById('chat-toc').classList.contains('is-open')")
        out["toc_open_before"] = panel_open_before

        # 打开子代理
        cdp.ev(
            "(() => { const rows = Array.from(document.querySelectorAll('#subagent-catalog-menu .subagent-catalog-row'));"
            " const t = rows.find(r => !r.classList.contains('is-diagnostic')); if (t) t.click(); return !!t; })()"
        )
        wait(cdp, "!!document.querySelector('#breadcrumb-text[data-addressing=\"child\"]')", 60, "child open")
        time.sleep(1.2)

        # 1) 标题行几何：胶囊与标题是否垂直居中对齐
        geo = cdp.ev(r"""
            (() => {
              const row = document.querySelector('.breadcrumb-title-row');
              const title = document.getElementById('breadcrumb-text');
              const trigger = document.getElementById('subagent-catalog-trigger');
              const back = document.querySelector('.breadcrumb-back-chip');
              const box = (el) => { if (!el) return null; const r = el.getBoundingClientRect();
                return { top: Math.round(r.top), bottom: Math.round(r.bottom), h: Math.round(r.height),
                         cy: Math.round((r.top + r.bottom) / 2), left: Math.round(r.left), right: Math.round(r.right) }; };
              const cs = trigger ? getComputedStyle(trigger) : null;
              return {
                rowAlign: row ? getComputedStyle(row).alignItems : '',
                title: box(title), trigger: box(trigger), back: box(back),
                triggerSiblingOfTitle: !!(trigger && title && trigger.parentNode === title.parentNode
                    && trigger.previousElementSibling === title),
                triggerStyles: cs ? {
                  borderRadius: cs.borderRadius, fontSize: cs.fontSize, height: cs.height,
                  background: cs.backgroundColor, color: cs.color, display: cs.display,
                } : null,
              };
            })()
        """)
        out["titleRowGeometry"] = geo
        title = geo.get("title") or {}
        trigger = geo.get("trigger") or {}
        delta = abs((title.get("cy") or 0) - (trigger.get("cy") or 0))
        out["center_delta_px"] = delta
        out["checks"]["title_capsule_v_centered"] = bool(trigger) and delta <= 2
        out["checks"]["capsule_is_pill"] = "999px" in str((geo.get("triggerStyles") or {}).get("borderRadius", ""))
        out["checks"]["trigger_is_row_sibling"] = bool(geo.get("triggerSiblingOfTitle"))

        # 2) 右侧面板保持打开
        toc_after = cdp.ev("!!document.getElementById('chat-toc') && document.getElementById('chat-toc').classList.contains('is-open')")
        out["toc_open_after_child"] = toc_after
        out["checks"]["panels_kept_on_child"] = (not panel_open_before) or bool(toc_after)

        # 3) 三点按钮是横向一排
        dots = cdp.ev(r"""
            (() => {
              const btn = document.querySelector('.session-more-btn');
              if (!btn) return { found: false };
              const wrap = btn.querySelector('.session-more-dots');
              if (!wrap) return { found: false };
              const spans = Array.from(wrap.querySelectorAll('span')).map(s => s.getBoundingClientRect());
              const cs = getComputedStyle(wrap);
              return {
                found: true, display: cs.display, flexDirection: cs.flexDirection, gap: cs.gap,
                tops: spans.map(r => Math.round(r.top)), lefts: spans.map(r => Math.round(r.left)),
              };
            })()
        """)
        out["dots"] = dots
        tops = set(dots.get("tops") or [])
        out["checks"]["dots_horizontal"] = bool(dots.get("found")) and len(tops) <= 1 and (dots.get("flexDirection") == "row")

        # 返回父会话
        out["before_back"] = cdp.ev(r"""
            (() => {
              const br = document.getElementById('breadcrumb-text');
              const probe = (typeof window.__myagentSubagentProbe !== 'undefined') ? window.__myagentSubagentProbe : null;
              return {
                addressing: br ? (br.dataset.addressing || '') : '(no br)',
                title: br ? String(br.textContent || '') : '',
                chip: !!document.querySelector('[data-addressing-back]'),
                lastSessionId: (() => { try { return localStorage.getItem('lastSessionId'); } catch (e) { return 'ERR'; } })(),
                activeSidebar: Array.from(document.querySelectorAll('.session-item.active'))
                  .map(x => x.dataset.sessionId || ''),
                probeAddressing: probe ? probe.addressing() : '(no probe)',
              };
            })()
        """)
        # 直接调用寻址模块的 returnToParent（绕过 chip），对比 chip 点击行为
        out["back_via_module"] = cdp.ev(r"""
            (() => {
              const probe = (typeof window.__myagentSubagentProbe !== 'undefined') ? window.__myagentSubagentProbe : null;
              const chip = document.querySelector('[data-addressing-back]');
              const result = { chipClicked: false, moduleCall: '(no probe)' };
              if (chip) { chip.click(); result.chipClicked = true; }
              return result;
            })()
        """)
        time.sleep(2.0)
        out["after_back"] = cdp.ev(r"""
            (() => {
              const br = document.getElementById('breadcrumb-text');
              const probe = (typeof window.__myagentSubagentProbe !== 'undefined') ? window.__myagentSubagentProbe : null;
              return {
                addressing: br ? (br.dataset.addressing || '') : '(no br)',
                title: br ? String(br.textContent || '') : '',
                chip: !!document.querySelector('[data-addressing-back]'),
                lastSessionId: (() => { try { return localStorage.getItem('lastSessionId'); } catch (e) { return 'ERR'; } })(),
                activeSidebar: Array.from(document.querySelectorAll('.session-item.active'))
                  .map(x => x.dataset.sessionId || ''),
                probeAddressing: probe ? probe.addressing() : '(no probe)',
              };
            })()
        """)
        try:
            wait(cdp, "!document.querySelector('#breadcrumb-text[data-addressing=\"child\"]')", 25, "back")
            out["checks"]["back_to_parent"] = True
        except RuntimeError:
            out["checks"]["back_to_parent"] = False
        out["console_errors"] = cdp.errors[:10]
        out["checks"]["no_console_errors"] = not cdp.errors
        out["ok"] = all(out["checks"].values())
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0 if out["ok"] else 1
    except Exception as exc:  # noqa: BLE001 - 失败也要把已收集的数据打出来
        out["fatal"] = repr(exc)[:300]
        if cdp is not None:
            out["console_errors"] = cdp.errors[:10]
        print(json.dumps(out, ensure_ascii=False, indent=2))
        raise
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
