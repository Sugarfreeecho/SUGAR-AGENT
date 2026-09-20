# -*- coding: utf-8 -*-
"""「新建对话」/ 会话切换后的胶囊新鲜度检查（用户 2026-09-20 反馈）。

场景（对已在运行的 8192 服务实机执行）：
  1) 打开带子代理的会话 → 标题栏胶囊可见（sanity）
  2) 点「新建对话」→ 进入草稿态：胶囊必须立即撤下（≤2s），且随后 ~5s
     观察窗内不得被 store 通知复活（旧 bug：胶囊残留、很久才消失）
  3) 切到无子代理的普通会话 → 胶囊保持隐藏（含通知观察窗）
  4) 切回子代理会话 → 胶囊恢复可见
  5) console 无错误

用法：python scripts/verify_capsule_new_session.py --base-url http://127.0.0.1:8192
退出码 0 = 全部通过；1 = 有检查未过（stdout 打印 JSON 记录）。
"""

from __future__ import annotations

import argparse
import base64
import json
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from subagent_ui_verify import Cdp, _browser_path, _free_port, _seed_subagents, _wait_eval  # noqa: E402

FIX_DIR = ROOT / "workspace" / "子代理样式块恢复"

CAPSULE_JS = (
    "(() => {"
    " const t = document.getElementById('subagent-catalog-trigger');"
    " if (!t) return { exists: false, visible: false, text: '' };"
    " const cs = getComputedStyle(t);"
    " const visible = !t.classList.contains('hidden') && cs.display !== 'none'"
    "   && t.getClientRects().length > 0;"
    " return { exists: true, visible: visible, hidden: t.classList.contains('hidden'),"
    "   text: String(t.textContent || '') };"
    "})()"
)


def _capsule(cdp: Cdp) -> dict:
    return cdp.evaluate(CAPSULE_JS) or {}


def _wait_capsule_state(cdp: Cdp, want_visible: bool, timeout: float, label: str):
    """等到胶囊的可见性变为 want_visible；返回 (ok, last_state, elapsed_ms)。"""
    start = time.monotonic()
    last: dict = {}
    while time.monotonic() - start < timeout:
        last = _capsule(cdp)
        if bool(last.get("visible")) == want_visible:
            return True, last, round((time.monotonic() - start) * 1000)
        time.sleep(0.1)
    return False, last, round((time.monotonic() - start) * 1000)


def _watch_hidden(cdp: Cdp, seconds: float, label: str):
    """观察窗内持续确认胶囊保持隐藏；返回 (ok, last_state)。"""
    end = time.monotonic() + seconds
    last: dict = {}
    while time.monotonic() < end:
        last = _capsule(cdp)
        if last.get("visible"):
            return False, last
        time.sleep(0.25)
    return True, last


def _click_sidebar(cdp: Cdp, name: str) -> bool:
    return bool(cdp.evaluate(
        "(() => { const items = Array.from(document.querySelectorAll('.session-item'));"
        " const hit = items.find(el => String(el.textContent || '').includes(" + json.dumps(name) + "));"
        " if (!hit) return false; (hit.querySelector('.session-name') || hit).click(); return true; })()"
    ))


def _wait_title(cdp: Cdp, name: str, timeout: float, label: str) -> None:
    expr = (
        "(() => { const t = document.getElementById('breadcrumb-text');"
        " return !!t && String(t.textContent || '').includes(" + json.dumps(name) + "); })()"
    )
    try:
        _wait_eval(cdp, expr, timeout=timeout, label=label)
    except RuntimeError:
        if not _click_sidebar(cdp, name):
            raise
        _wait_eval(cdp, expr, timeout=60, label=label + " (sidebar)")


def _shot(cdp: Cdp, tag: str):
    """截标题行区域（best-effort，失败返回 None）。"""
    try:
        rect = cdp.evaluate(
            "(() => { const r = document.querySelector('.breadcrumb-title-row').getBoundingClientRect();"
            " return { x: Math.max(0, r.x - 12), y: Math.max(0, r.y - 12),"
            "   width: r.width + 24, height: r.height + 24 }; })()"
        )
        if not rect or float(rect.get("width") or 0) <= 0:
            return None
        clip = {"x": rect["x"], "y": rect["y"], "width": rect["width"], "height": rect["height"], "scale": 2}
        data = cdp.call("Page.captureScreenshot", {"format": "png", "clip": clip}).get("data")
        out = FIX_DIR / f"capsule-{tag}-{time.strftime('%Y%m%d-%H%M%S')}.png"
        out.write_bytes(base64.b64decode(data))
        return str(out)
    except Exception:  # noqa: BLE001
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="New-session capsule freshness check")
    parser.add_argument("--base-url", default="http://127.0.0.1:8192")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    session_root = ROOT / "workspace" / "sessions"
    tag = uuid.uuid4().hex[:6]
    sub_name = "capsule sub " + tag
    plain_name = "capsule plain " + tag
    created: list[str] = []
    results: dict = {"checks": {}, "screenshots": []}
    profile_dir = Path(tempfile.mkdtemp(prefix="myagent-capsule-"))
    browser = None
    cdp = None
    exit_code = 1
    try:
        def new_session(name: str) -> str:
            resp = requests.post(base + "/sessions", timeout=90)
            resp.raise_for_status()
            sid = str(resp.json().get("session_id") or "")
            created.append(sid)
            requests.put(base + f"/sessions/{sid}/name", data={"name": name}, timeout=30)
            return sid

        sub_id = new_session(sub_name)
        new_session(plain_name)
        _seed_subagents(session_root / sub_id, 2)

        debug_port = _free_port()
        browser = subprocess.Popen(
            [str(_browser_path()), "--headless=new", f"--remote-debugging-port={debug_port}",
             "--remote-allow-origins=*", f"--user-data-dir={profile_dir}", "--disable-gpu",
             "--no-first-run", "--no-default-browser-check", "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        targets = None
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            try:
                targets = requests.get(f"http://127.0.0.1:{debug_port}/json/list", timeout=1).json()
                if targets:
                    break
            except Exception:  # noqa: BLE001
                time.sleep(0.2)
        page = next((t for t in (targets or []) if t.get("type") == "page"), None)
        if page is None:
            raise RuntimeError("no page target")
        cdp = Cdp(str(page["webSocketDebuggerUrl"]))
        cdp.call("Page.enable")
        cdp.call("Runtime.enable")
        cdp.call("Emulation.setDeviceMetricsOverride",
                 {"width": 1280, "height": 800, "deviceScaleFactor": 1, "mobile": False})
        cdp.call("Page.navigate", {"url": base + "/"})
        _wait_eval(cdp, "!!document.body", timeout=30, label="body")
        cdp.evaluate("(() => { localStorage.setItem('lastSessionId', " + json.dumps(sub_id) + "); return true; })()")
        cdp.call("Page.reload", {})
        _wait_eval(cdp, "!!document.getElementById('chat-stream')", timeout=60, label="shell")
        _wait_title(cdp, sub_name, 90, "subagents session title")

        # 1) sanity：子代理会话上胶囊可见
        ok1, state, _ = _wait_capsule_state(cdp, True, 60, "trigger visible")
        results["sub_trigger"] = state
        results["checks"]["1_trigger_on_subagents"] = bool(ok1 and "子代理" in str(state.get("text") or ""))
        shot = _shot(cdp, "sub-visible")
        if shot:
            results["screenshots"].append(shot)

        # 2) 新建对话 → 草稿态：胶囊必须立即撤下，并在观察窗内保持
        cdp.evaluate("(() => { const b = document.getElementById('new-session-btn');"
                     " if (!b) return false; b.click(); return true; })()")
        _wait_eval(cdp,
                   "(() => { const t = document.getElementById('breadcrumb-text');"
                   " return !!t && String(t.textContent || '').includes('未选择会话'); })()",
                   timeout=8, label="draft state")
        ok_hide, last_hide, hide_ms = _wait_capsule_state(cdp, False, 2.0, "draft hide")
        results["draft_hide"] = {"ok": ok_hide, "ms": hide_ms, "state": last_hide}
        if ok_hide:
            ok_watch, last_watch = _watch_hidden(cdp, 5.0, "draft")
        else:
            ok_watch, last_watch = False, last_hide
        results["draft_watch"] = {"ok": ok_watch, "state": last_watch}
        results["checks"]["2_draft_hides_capsule"] = bool(ok_hide and ok_watch)
        shot = _shot(cdp, "draft-clean")
        if shot:
            results["screenshots"].append(shot)

        # 3) 切到无子代理会话：胶囊保持隐藏
        if not _click_sidebar(cdp, plain_name):
            raise RuntimeError("plain session row not found in sidebar")
        _wait_title(cdp, plain_name, 60, "plain session title")
        ok_hide2, last_hide2, hide2_ms = _wait_capsule_state(cdp, False, 3.0, "plain hide")
        if ok_hide2:
            ok_watch2, last_watch2 = _watch_hidden(cdp, 4.0, "plain")
        else:
            ok_watch2, last_watch2 = False, last_hide2
        results["plain_phase"] = {
            "hide": {"ok": ok_hide2, "ms": hide2_ms, "state": last_hide2},
            "watch": {"ok": ok_watch2, "state": last_watch2},
        }
        results["checks"]["3_plain_session_stays_clean"] = bool(ok_hide2 and ok_watch2)

        # 4) 切回子代理会话：胶囊恢复
        if not _click_sidebar(cdp, sub_name):
            raise RuntimeError("subagents session row not found in sidebar")
        _wait_title(cdp, sub_name, 60, "back to subagents session")
        ok4, state4, _ = _wait_capsule_state(cdp, True, 20, "trigger returns")
        results["return_trigger"] = state4
        results["checks"]["4_trigger_returns_on_reopen"] = bool(ok4)

        # 5) 无 console 错误
        time.sleep(0.3)
        results["console_errors"] = cdp.console_errors[:10]
        results["checks"]["5_no_console_errors"] = not cdp.console_errors
        exit_code = 0 if all(bool(v) for v in results["checks"].values()) else 1
    except Exception as exc:  # noqa: BLE001
        results["error"] = f"{type(exc).__name__}: {exc}"
        exit_code = 1
    finally:
        results["ok"] = exit_code == 0
        print(json.dumps(results, ensure_ascii=True, indent=2))
        if cdp is not None:
            try:
                cdp.close()
            except Exception:  # noqa: BLE001
                pass
        if browser is not None:
            browser.terminate()
            try:
                browser.wait(timeout=5)
            except subprocess.TimeoutExpired:
                browser.kill()
        shutil.rmtree(profile_dir, ignore_errors=True)
        for sid in created:
            try:
                requests.delete(base + f"/sessions/{sid}", timeout=15)
            except Exception:  # noqa: BLE001
                pass
            if sid:
                shutil.rmtree(session_root / sid, ignore_errors=True)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
