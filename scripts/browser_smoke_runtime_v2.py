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
from pathlib import Path
from typing import Any

import requests
import websocket


ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = ROOT / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _browser_path() -> Path:
    env = str(os.getenv("MYAGENT_BROWSER_BIN") or "").strip()
    candidates = [
        Path(env) if env else None,
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    ]
    for candidate in candidates:
        if candidate and candidate.is_file():
            return candidate
    raise RuntimeError("Chromium/Edge not found; set MYAGENT_BROWSER_BIN")


class Cdp:
    def __init__(self, url: str):
        self.ws = websocket.create_connection(url, timeout=10, origin="http://localhost")
        self.next_id = 1

    def close(self) -> None:
        self.ws.close()

    def call(self, method: str, params: dict | None = None) -> dict:
        call_id = self.next_id
        self.next_id += 1
        self.ws.send(json.dumps({"id": call_id, "method": method, "params": params or {}}))
        while True:
            message = json.loads(self.ws.recv())
            if message.get("id") != call_id:
                continue
            if "error" in message:
                raise RuntimeError(f"CDP {method} failed: {message['error']}")
            return dict(message.get("result") or {})

    def evaluate(self, expression: str, *, await_promise: bool = False) -> Any:
        result = self.call("Runtime.evaluate", {
            "expression": expression,
            "awaitPromise": bool(await_promise),
            "returnByValue": True,
        })
        remote = result.get("result") or {}
        if remote.get("subtype") == "error":
            raise RuntimeError(str(remote.get("description") or remote))
        return remote.get("value")


def _wait_json(url: str, timeout: float = 15.0) -> Any:
    deadline = time.monotonic() + timeout
    last_error = None
    while time.monotonic() < deadline:
        try:
            response = requests.get(url, timeout=1)
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            last_error = exc
            time.sleep(0.1)
    raise RuntimeError(f"timed out waiting for {url}: {last_error}")


def _wait_eval(cdp: Cdp, expression: str, timeout: float = 15.0) -> Any:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = cdp.evaluate(expression)
        if value:
            return value
        time.sleep(0.1)
    raise RuntimeError(f"browser condition timed out: {expression}")


def run(base_url: str) -> dict:
    from runtime_v2 import RuntimeHistoryOps
    from runtime_v2.config import runtime_version

    active_runtime = int(runtime_version())
    if active_runtime != 2:
        raise AssertionError(f"Runtime V2 required, got {active_runtime}")

    created = requests.post(base_url + "/sessions", timeout=10)
    created.raise_for_status()
    session_id = str(created.json().get("session_id") or "")
    if not session_id:
        raise AssertionError("session creation returned no id")

    ops = RuntimeHistoryOps(ROOT / "workspace" / "sessions")
    for index in range(1, 9):
        ops.commit_user_turn(session_id, f"browser smoke question {index} " + ("x" * 120))
        ops.commit_assistant_final(session_id, f"browser smoke answer {index} " + ("y" * 240))

    debug_port = _free_port()
    profile_dir = Path(tempfile.mkdtemp(prefix="myagent-browser-smoke-"))
    process = subprocess.Popen(
        [
            str(_browser_path()),
            "--headless=new",
            f"--remote-debugging-port={debug_port}",
            "--remote-allow-origins=*",
            f"--user-data-dir={profile_dir}",
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    cdp = None
    try:
        targets = _wait_json(f"http://127.0.0.1:{debug_port}/json/list")
        page = next(item for item in targets if item.get("type") == "page")
        cdp = Cdp(str(page["webSocketDebuggerUrl"]))
        cdp.call("Page.enable")
        cdp.call("Runtime.enable")
        cdp.call("Emulation.setDeviceMetricsOverride", {
            "width": 1100,
            "height": 420,
            "deviceScaleFactor": 1,
            "mobile": False,
        })
        # Instrument the real bundled UI at its Function() composition boundary.
        # This keeps the smoke browser-driven while exposing a very small test
        # surface for state that otherwise lives inside the generated closure.
        smoke_bootstrap = r"""
            (() => {
              const sid = __SESSION_ID__;
              localStorage.setItem('lastSessionId', sid);
              const smoke = window.__runtimeV2SmokeState = {
                steerPosts: 0,
                steerSeq: 0,
                serverItems: []
              };
              const nativeFetch = window.fetch.bind(window);
              window.fetch = function(input, init) {
                const url = String(typeof input === 'string' ? input : ((input && input.url) || ''));
                const target = '/sessions/' + encodeURIComponent(sid) + '/steer';
                if (url.indexOf(target) >= 0) {
                  const method = String((init && init.method) || (input && input.method) || 'GET').toUpperCase();
                  const suffix = url.slice(url.indexOf(target) + target.length);
                  const jsonResponse = (payload, status) => Promise.resolve(new Response(
                    JSON.stringify(payload),
                    {status: status || 200, headers: {'Content-Type': 'application/json'}}
                  ));
                  if (method === 'POST' && !suffix) {
                    smoke.steerPosts += 1;
                    smoke.steerSeq += 1;
                    let body = {};
                    try { body = JSON.parse(String((init && init.body) || '{}')); } catch (_e) {}
                    const item = {
                      id: 'browser-steer-' + String(smoke.steerSeq),
                      client_id: String(body.client_id || ''),
                      content: String(body.message || ''),
                      ui_content: String(body.ui_content || body.message || ''),
                      state: 'queued',
                      created_at: Date.now() / 1000
                    };
                    smoke.serverItems.push(item);
                    return jsonResponse({ok: true, restart: false, item});
                  }
                  if (method === 'DELETE') {
                    smoke.serverItems = [];
                    return jsonResponse({ok: true});
                  }
                  if (method === 'POST' && /\/recover(?:\?|$)/.test(suffix)) {
                    return jsonResponse({ok: true, item: smoke.serverItems[0] || null});
                  }
                  if (method === 'GET' && suffix) {
                    const id = decodeURIComponent(suffix.replace(/^\//, '').split('/')[0] || '');
                    const item = smoke.serverItems.find(x => String(x.id) === id) || null;
                    return jsonResponse({ok: true, item});
                  }
                  return jsonResponse({ok: true, items: smoke.serverItems.slice()});
                }
                return nativeFetch(input, init);
              };

              const NativeFunction = window.Function;
              function SmokeFunction(...args) {
                const last = args.length - 1;
                let body = last >= 0 ? String(args[last]) : '';
                if (body.indexOf('//# sourceURL=myagent-ui.js') >= 0) {
                  body = body.replace(
                    '//# sourceURL=myagent-ui.js',
                    `window.__runtimeV2SmokeHooks = {
                      queueSnapshot: sid => getFollowupQueue(sid).map(item => ({
                        id: String(item.id),
                        text: String(item.text || ''),
                        status: String(item.status || ''),
                        steerId: String(item.steerId || '')
                      })),
                      setFakeRun: sid => setSessionRunState(sid, {runId: 'browser-fake-run', ctx: {}}),
                      enqueueByEnter: text => {
                        messageInput.value = String(text || '');
                        messageInput.dispatchEvent(new KeyboardEvent('keydown', {
                          key: 'Enter', bubbles: true, cancelable: true
                        }));
                      },
                      finishFakeRun: sid => endRunForClient(
                        sid,
                        (getSessionRunState(sid) || {}).ctx || {},
                        {reconcileFinal: false, scroll: false}
                      ),
                      syncFollowups: sid => syncFollowupQueueFromServer(sid),
                      consumeSteer: (sid, steerId) => removeConsumedFollowupSteer(sid, {
                        steer: true, steer_id: steerId
                      })
                    };
                    //# sourceURL=myagent-ui.js`
                  );
                  args[last] = body;
                }
                return NativeFunction.apply(this, args);
              }
              Object.setPrototypeOf(SmokeFunction, NativeFunction);
              SmokeFunction.prototype = NativeFunction.prototype;
              window.Function = SmokeFunction;
            })();
        """.replace("__SESSION_ID__", json.dumps(session_id))
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": smoke_bootstrap})
        cdp.call("Page.navigate", {"url": base_url + "/"})
        _wait_eval(cdp, "document.readyState === 'complete'")
        loaded = _wait_eval(cdp, """
            (() => {
              const users = document.querySelectorAll('.msg-wrap--user').length;
              const finals = document.querySelectorAll('.message.assistant, .message.final').length;
              const toc = document.querySelectorAll('#chat-toc-list a[data-event-index]').length;
              return users >= 5 && toc >= 5 ? {users, finals, toc} : null;
            })()
        """, timeout=30)
        snapshot = cdp.evaluate(f"""
            fetch('/sessions/{session_id}/history_snapshot?turns=5')
              .then(r => r.json())
              .then(x => ({{ok:x.ok, source:x.source, count:x.count, timing:x.timing}}))
        """, await_promise=True)
        if not snapshot.get("ok") or snapshot.get("source") != "runtime_v2_snapshot":
            raise AssertionError(f"unexpected snapshot response: {snapshot}")
        before_metrics = cdp.evaluate("""
            (() => { const x=document.getElementById('chat-container'); return {
              scrollTop:x.scrollTop, scrollHeight:x.scrollHeight, clientHeight:x.clientHeight
            }; })()
        """)
        cdp.evaluate("document.querySelector('#chat-toc-list a[data-event-index]').click()")
        time.sleep(1.2)
        after_toc_scroll = cdp.evaluate("document.getElementById('chat-container').scrollTop")
        before_scroll = int(before_metrics.get("scrollTop") or 0)
        if int(before_metrics.get("scrollHeight") or 0) <= int(before_metrics.get("clientHeight") or 0):
            raise AssertionError(f"smoke fixture did not overflow chat viewport: {before_metrics}")
        if int(after_toc_scroll or 0) >= before_scroll:
            raise AssertionError("TOC click did not scroll toward the selected earlier turn")
        cdp.call("Page.reload", {"ignoreCache": False})
        _wait_eval(cdp, "document.readyState === 'complete'")
        restored = _wait_eval(cdp, "document.querySelectorAll('.msg-wrap--user').length >= 5")
        if not restored:
            raise AssertionError("history did not recover after refresh")
        _wait_eval(cdp, "!!window.__runtimeV2SmokeHooks")

        # A follow-up entered during an active run must remain pending across
        # timers, refresh/server sync and run completion.  Only the row's
        # explicit send-now button may POST the steer.
        cdp.evaluate(f"window.__runtimeV2SmokeHooks.setFakeRun({json.dumps(session_id)})")
        cdp.evaluate("window.__runtimeV2SmokeHooks.enqueueByEnter('queued follow-up one')")
        cdp.evaluate("window.__runtimeV2SmokeHooks.enqueueByEnter('queued follow-up two')")
        time.sleep(0.35)
        queued_before_refresh = cdp.evaluate(f"window.__runtimeV2SmokeHooks.queueSnapshot({json.dumps(session_id)})")
        posts_before_refresh = int(cdp.evaluate("window.__runtimeV2SmokeState.steerPosts") or 0)
        if len(queued_before_refresh or []) != 2 or posts_before_refresh != 0:
            raise AssertionError(
                f"follow-ups did not remain pending before refresh: queue={queued_before_refresh} posts={posts_before_refresh}"
            )

        cdp.call("Page.reload", {"ignoreCache": False})
        _wait_eval(cdp, "document.readyState === 'complete'")
        _wait_eval(cdp, "!!window.__runtimeV2SmokeHooks")
        _wait_eval(cdp, "document.querySelectorAll('#followup-queue-panel .followup-queue-row').length === 2")
        cdp.evaluate(
            f"window.__runtimeV2SmokeHooks.syncFollowups({json.dumps(session_id)})",
            await_promise=True,
        )
        cdp.evaluate(f"window.__runtimeV2SmokeHooks.setFakeRun({json.dumps(session_id)})")
        cdp.evaluate(f"window.__runtimeV2SmokeHooks.finishFakeRun({json.dumps(session_id)})")
        time.sleep(0.35)
        posts_after_restore_and_finish = int(cdp.evaluate("window.__runtimeV2SmokeState.steerPosts") or 0)
        if posts_after_restore_and_finish != 0:
            raise AssertionError(
                "refresh, sync or run completion consumed a pending follow-up without a click"
            )

        cdp.evaluate("document.querySelector('#followup-queue-panel .followup-queue-send').click()")
        _wait_eval(cdp, "window.__runtimeV2SmokeState.steerPosts === 1")
        first_steer_id = str(cdp.evaluate(
            "window.__runtimeV2SmokeState.serverItems[0] && window.__runtimeV2SmokeState.serverItems[0].id"
        ) or "")
        if not first_steer_id:
            raise AssertionError("send-now did not create the first steer")
        cdp.evaluate("window.__runtimeV2SmokeState.serverItems = []")
        cdp.evaluate(
            f"window.__runtimeV2SmokeHooks.consumeSteer({json.dumps(session_id)}, {json.dumps(first_steer_id)})"
        )
        _wait_eval(cdp, "document.querySelectorAll('#followup-queue-panel .followup-queue-row').length === 1")
        time.sleep(0.35)
        if int(cdp.evaluate("window.__runtimeV2SmokeState.steerPosts") or 0) != 1:
            raise AssertionError("consuming the first follow-up auto-sent the next pending item")
        cdp.evaluate("document.querySelector('#followup-queue-panel .followup-queue-send').click()")
        _wait_eval(cdp, "window.__runtimeV2SmokeState.steerPosts === 2")
        return {
            "ok": True,
            "runtime_version": active_runtime,
            "session_id": session_id,
            "rendered": loaded,
            "snapshot_timing": snapshot.get("timing"),
            "toc_scroll_before": before_scroll,
            "toc_scroll_after": after_toc_scroll,
            "refresh_recovered": True,
            "followup_queue": {
                "queued_before_refresh": len(queued_before_refresh or []),
                "posts_before_click": posts_after_restore_and_finish,
                "posts_after_first_click": 1,
                "next_item_waited": True,
                "posts_after_second_click": 2,
            },
        }
    finally:
        if cdp is not None:
            try:
                cdp.close()
            except Exception:
                pass
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        shutil.rmtree(profile_dir, ignore_errors=True)
        try:
            requests.delete(base_url + f"/sessions/{session_id}", timeout=15)
        except Exception:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Runtime V2 real-browser smoke test")
    parser.add_argument("--base-url", default="http://127.0.0.1:8192")
    args = parser.parse_args()
    result = run(args.base_url.rstrip("/"))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
