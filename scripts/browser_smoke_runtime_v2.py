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
    from runtime_v2 import RuntimeHistoryOps, RuntimeSubagentStore
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
    child_id = str(uuid.uuid4())
    subagents = RuntimeSubagentStore(ROOT / "workspace" / "sessions")
    subagents.upsert_task(session_id, child_id, {
        "description": "browser smoke child",
        "subagent_type": "explore",
        "status": "completed",
        "result_preview": "browser smoke child finished",
    })
    subagents.append_event(session_id, child_id, "model_user", {"content": "inspect smoke fixture"})
    subagents.append_event(
        session_id,
        child_id,
        "model_assistant",
        {"content": "browser smoke child finished", "metadata": {"is_final": True}},
    )

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
                serverItems: [],
                uploadCalls: 0,
                delayMessageCount: false,
                chatPosts: 0,
                branchStartedAt: 0,
                branchElapsedMs: 0,
                branchSessionId: '',
                branchRequestUrl: '',
                branchStatus: 0,
                branchPayload: '',
                measureReconnect: false,
                reconnectGets: 0,
                fakeChat: false,
                truncatePosts: 0,
                truncateStatus: 0,
                truncatePayload: ''
              };
              const nativeFetch = window.fetch.bind(window);
              window.fetch = function(input, init) {
                const url = String(typeof input === 'string' ? input : ((input && input.url) || ''));
                if (url.indexOf('/api/upload-chat-files') >= 0) {
                  smoke.uploadCalls += 1;
                  const body = init && init.body;
                  const files = body && typeof body.getAll === 'function' ? body.getAll('files') : [];
                  return Promise.resolve(new Response(JSON.stringify({
                    ok: true,
                    files: files.map((file, index) => ({
                      name: String(file && file.name || ('clipboard-' + index + '.bin')),
                      path: '/workspace/uploads/chat/smoke/' + String(file && file.name || ('clipboard-' + index + '.bin')),
                      rel: 'uploads/chat/smoke/' + String(file && file.name || ('clipboard-' + index + '.bin')),
                      size: Number(file && file.size || 0)
                    }))
                  }), {status: 200, headers: {'Content-Type': 'application/json'}}));
                }
                if (smoke.delayMessageCount && url.indexOf('/sessions/' + encodeURIComponent(sid) + '/messages/count') >= 0) {
                  return new Promise(resolve => setTimeout(() => resolve(new Response(
                    JSON.stringify({count: 16}),
                    {status: 200, headers: {'Content-Type': 'application/json'}}
                  )), 650));
                }
                if (/\/sessions\/[^/]+\/truncate(?:\?|$)/.test(url)
                    && String((init && init.method) || 'GET').toUpperCase() === 'POST') {
                  smoke.truncatePosts += 1;
                  return nativeFetch(input, init).then(response => {
                    smoke.truncateStatus = Number(response.status || 0);
                    response.clone().text().then(text => {
                      smoke.truncatePayload = String(text || '');
                    }).catch(() => {});
                    return response;
                  });
                }
                if (url.endsWith('/chat') && String((init && init.method) || 'GET').toUpperCase() === 'POST') {
                  smoke.chatPosts += 1;
                  if (smoke.fakeChat) {
                    return Promise.resolve(new Response('data: [DONE]\n\n', {
                      status: 200,
                      headers: {'Content-Type': 'text/event-stream; charset=utf-8'}
                    }));
                  }
                }
                if (smoke.measureReconnect
                    && url.endsWith('/sessions/' + encodeURIComponent(sid))
                    && String((init && init.method) || 'GET').toUpperCase() === 'GET') {
                  smoke.reconnectGets += 1;
                }
                if (/\/sessions\/[^/]+\/branch(?:\?|$)/.test(url)
                    && String((init && init.method) || 'GET').toUpperCase() === 'POST') {
                  smoke.branchStartedAt = performance.now();
                  smoke.branchRequestUrl = url;
                  return nativeFetch(input, init).then(response => {
                    smoke.branchElapsedMs = performance.now() - smoke.branchStartedAt;
                    smoke.branchStatus = Number(response.status || 0);
                    response.clone().text().then(text => {
                      smoke.branchPayload = String(text || '');
                      let payload = null;
                      try { payload = JSON.parse(smoke.branchPayload); } catch (_e) {}
                      smoke.branchSessionId = String((payload && payload.session_id) || '');
                    }).catch(() => {});
                    return response;
                  });
                }
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

              const NativeXMLHttpRequest = window.XMLHttpRequest;
              window.XMLHttpRequest = class SmokeXMLHttpRequest {
                constructor() {
                  this.upload = {};
                  this.status = 0;
                  this.responseText = '';
                  this.withCredentials = false;
                  this.timeout = 0;
                  this._native = null;
                  this._aborted = false;
                }
                open(method, url, async) {
                  this._method = method;
                  this._url = String(url || '');
                  this._async = async;
                  if (this._url.indexOf('/api/upload-chat-files') < 0) {
                    this._native = new NativeXMLHttpRequest();
                    this._native.open(method, url, async);
                  }
                }
                setRequestHeader(name, value) {
                  if (this._native) this._native.setRequestHeader(name, value);
                }
                send(body) {
                  if (this._native) {
                    this._native.withCredentials = this.withCredentials;
                    this._native.timeout = this.timeout;
                    ['onload', 'onerror', 'ontimeout', 'onabort'].forEach(name => {
                      this._native[name] = event => {
                        this.status = this._native.status;
                        this.responseText = this._native.responseText;
                        if (typeof this[name] === 'function') this[name](event);
                      };
                    });
                    this._native.send(body);
                    return;
                  }
                  smoke.uploadCalls += 1;
                  const files = body && typeof body.getAll === 'function' ? body.getAll('files') : [];
                  const total = files.reduce((sum, file) => sum + Number(file && file.size || 0), 0);
                  queueMicrotask(() => {
                    if (this._aborted) return;
                    if (typeof this.upload.onprogress === 'function') {
                      this.upload.onprogress({loaded: total, total, lengthComputable: true});
                    }
                    this.status = 200;
                    this.responseText = JSON.stringify({
                      ok: true,
                      files: files.map((file, index) => ({
                        name: String(file && file.name || ('clipboard-' + index + '.bin')),
                        path: '/workspace/uploads/chat/smoke/' + String(file && file.name || ('clipboard-' + index + '.bin')),
                        rel: 'uploads/chat/smoke/' + String(file && file.name || ('clipboard-' + index + '.bin')),
                        size: Number(file && file.size || 0)
                      }))
                    });
                    if (typeof this.onload === 'function') this.onload();
                  });
                }
                abort() {
                  this._aborted = true;
                  if (this._native) this._native.abort();
                  else if (typeof this.onabort === 'function') this.onabort();
                }
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
                      expireCount: sid => uiEventCountCache.cache.delete(sid),
                      clearStopSuppression: sid => clearSessionStreamStopSuppress(sid),
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
                      }),
                      interruptLayout: sid => {
                        const stream = getVisibleChatStream();
                        const ctx = newDomContext(stream);
                        ctx.runId = 'layout-run';
                        appendLog(ctx, 'old interrupted reasoning', 'llm-reasoning', sid, 1);
                        const oldGroup = ctx.currentProcessGroup;
                        prepareSteerProcessBoundary(ctx, 'interrupt', 'layout-client');
                        const steerRow = appendSteerProcessMessage(
                          sid, ctx, 'interrupt follow-up', 'layout-client', 'interrupt', true
                        );
                        steerRow.dataset.steerClientId = 'layout-client';
                        steerRow.dataset.steerId = 'layout-steer';
                        const committed = appendSteerProcessMessage(
                          sid, ctx, 'interrupt follow-up', 'layout-client', 'interrupt', false
                        );
                        upsertLlmFeedRow(ctx, 'replacement reasoning', 'llm-reasoning', sid, 1);
                        upsertLlmFeedRow(ctx, 'replacement response', 'llm-response', sid, 1);
                        const newGroup = ctx.currentProcessGroup;
                        prepareSteerProcessBoundary(ctx, 'interrupt', 'layout-client');
                        const groups = Array.from(stream.querySelectorAll('.process-aggregate'));
                        const rows = Array.from(newGroup.querySelectorAll('.feed-item')).map(row =>
                          String(row.dataset.logType || '')
                        );
                        return {
                          distinctGroups: oldGroup !== newGroup,
                          oldHasReplacement: String(oldGroup.textContent || '').includes('replacement reasoning'),
                          rows,
                          steerRows: newGroup.querySelectorAll('.feed-item[data-steer-operation-id="layout-client"]').length,
                          committedInPlace: committed === steerRow,
                          groupCount: groups.length
                        };
                      },
                      currentSessionId: () => String(currentSessionId || '')
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
        _wait_eval(cdp, "document.readyState === 'complete'", timeout=30)
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
        _wait_eval(cdp, "!document.getElementById('subagent-toggle-btn').classList.contains('hidden')")
        cdp.evaluate("document.getElementById('subagent-toggle-btn').click()")
        _wait_eval(
            cdp,
            f"!!document.querySelector('.subagent-grid-card[data-agent-id={json.dumps(child_id)}]')",
        )
        cdp.evaluate("""
            window.__runtimeV2SmokeState.reconnectGets = 0;
            window.__runtimeV2SmokeState.measureReconnect = true;
            window.dispatchEvent(new Event('online'));
        """)
        _wait_eval(cdp, "window.__runtimeV2SmokeState.reconnectGets >= 1")
        reconnect_gets = int(cdp.evaluate("window.__runtimeV2SmokeState.reconnectGets") or 0)
        cdp.evaluate("window.__runtimeV2SmokeState.measureReconnect = false")
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
        _wait_eval(cdp, "document.readyState === 'complete'", timeout=30)
        restored = _wait_eval(cdp, "document.querySelectorAll('.msg-wrap--user').length >= 5")
        if not restored:
            raise AssertionError("history did not recover after refresh")
        _wait_eval(cdp, "!!window.__runtimeV2SmokeHooks")

        paste_result = cdp.evaluate(r"""
            (() => {
              const input = document.getElementById('message-input');
              input.value = '';
              const transfer = new DataTransfer();
              transfer.items.add(new File(['clipboard text'], 'clipboard-note.txt', {type:'text/plain'}));
              transfer.items.add(new File([new Uint8Array([137,80,78,71])], 'clipboard-image.png', {type:'image/png'}));
              const event = new Event('paste', {bubbles:true, cancelable:true});
              Object.defineProperty(event, 'clipboardData', {value: transfer});
              input.dispatchEvent(event);
              return {defaultPrevented:event.defaultPrevented};
            })()
        """)
        _wait_eval(cdp, "window.__runtimeV2SmokeState.uploadCalls === 1")
        pasted_value = str(_wait_eval(cdp, """
            (() => {
              const value = document.getElementById('message-input').value;
              return value.includes('clipboard-note.txt') && value.includes('clipboard-image.png') ? value : '';
            })()
        """))
        if not paste_result.get("defaultPrevented") or not pasted_value:
            raise AssertionError(f"clipboard files were not converted to input paths: {paste_result} {pasted_value!r}")

        optimistic = cdp.evaluate(f"""
            (() => {{
              const sid = {json.dumps(session_id)};
              const input = document.getElementById('message-input');
              input.value = 'optimistic button smoke';
              input.dispatchEvent(new Event('input', {{bubbles:true}}));
              window.__runtimeV2SmokeHooks.expireCount(sid);
              window.__runtimeV2SmokeState.delayMessageCount = true;
              document.getElementById('send-btn').click();
              const button = document.getElementById('send-btn');
              return {{text:button.textContent, isStop:button.classList.contains('is-stop')}};
            }})()
        """)
        if not optimistic.get("isStop") or "停止" not in str(optimistic.get("text") or ""):
            raise AssertionError(f"send button did not update optimistically: {optimistic}")
        cdp.evaluate("document.getElementById('send-btn').click()")
        time.sleep(0.8)
        stopped_button = cdp.evaluate("document.getElementById('send-btn').textContent")
        chat_posts = int(cdp.evaluate("window.__runtimeV2SmokeState.chatPosts") or 0)
        if "发送" not in str(stopped_button or "") or chat_posts != 0:
            raise AssertionError(
                f"stopping optimistic preflight failed: button={stopped_button!r} chat_posts={chat_posts}"
            )
        cdp.evaluate(f"window.__runtimeV2SmokeHooks.clearStopSuppression({json.dumps(session_id)})")
        cdp.evaluate("document.getElementById('message-input').value = ''")

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

        # Exercise the real toolbar + confirmation + server branch route and
        # wait for the UI to switch to the materialized V2 branch.  This is the
        # user-visible path that previously timed out even though the branch
        # appeared later.
        branch_click = cdp.evaluate(r"""
            (() => {
              const buttons = Array.from(document.querySelectorAll('#chat-container [data-act="branch"]'));
              if (!buttons.length) return false;
              buttons[0].click();
              return true;
            })()
        """)
        if not branch_click:
            raise AssertionError("no visible branch toolbar button")
        _wait_eval(cdp, "document.getElementById('ui-modal-root').classList.contains('is-open')")
        cdp.evaluate("document.getElementById('ui-modal-ok').click()")
        try:
            branch_session_id = str(_wait_eval(
                cdp,
                "window.__runtimeV2SmokeState.branchSessionId || ''",
                timeout=12,
            ))
        except RuntimeError as exc:
            branch_debug = cdp.evaluate("({"
                "startedAt: window.__runtimeV2SmokeState.branchStartedAt,"
                "elapsedMs: window.__runtimeV2SmokeState.branchElapsedMs,"
                "requestUrl: window.__runtimeV2SmokeState.branchRequestUrl,"
                "status: window.__runtimeV2SmokeState.branchStatus,"
                "payload: window.__runtimeV2SmokeState.branchPayload,"
                "modalOpen: document.getElementById('ui-modal-root').classList.contains('is-open')"
                "})")
            raise AssertionError(f"browser branch did not return a session id: {branch_debug}") from exc
        _wait_eval(
            cdp,
            "window.__runtimeV2SmokeHooks.currentSessionId() === window.__runtimeV2SmokeState.branchSessionId",
            timeout=12,
        )
        _wait_eval(cdp, "document.querySelectorAll('.msg-wrap--user').length >= 1", timeout=12)
        branch_elapsed_ms = float(cdp.evaluate("window.__runtimeV2SmokeState.branchElapsedMs") or 0)
        if not branch_session_id or branch_elapsed_ms <= 0 or branch_elapsed_ms >= 10000:
            raise AssertionError(
                f"browser branch exceeded 10s or returned no session: id={branch_session_id!r} elapsed={branch_elapsed_ms:.1f}ms"
            )

        # Run the inline rewrite interaction through its real truncate and
        # optimistic-send pipeline.  The model stream itself is replaced by a
        # deterministic terminal SSE because this smoke must not require API
        # credentials; Runtime V2 history-op tests verify the persisted model
        # and token checkpoints independently.
        _wait_eval(
            cdp,
            "document.querySelectorAll('#chat-container [data-act=\"rewrite\"]').length > 0",
            timeout=12,
        )
        rewrite_opened = cdp.evaluate(r"""
            (() => {
              const buttons = Array.from(document.querySelectorAll('#chat-container [data-act="rewrite"]'));
              if (!buttons.length) return false;
              buttons[buttons.length - 1].click();
              return true;
            })()
        """)
        if not rewrite_opened:
            raise AssertionError("no visible rewrite toolbar button in branch")
        _wait_eval(cdp, "!!document.querySelector('.user-inline-rewrite-input')")
        rewrite_optimistic = cdp.evaluate(r"""
            (() => {
              window.__runtimeV2SmokeState.fakeChat = true;
              const input = document.querySelector('.user-inline-rewrite-input');
              input.value = 'rewritten browser smoke question';
              input.dispatchEvent(new Event('input', {bubbles:true}));
              document.querySelector('.user-inline-rewrite-btn--primary').click();
              const send = document.getElementById('send-btn');
              return {isStop:send.classList.contains('is-stop'), text:String(send.textContent || '')};
            })()
        """)
        if not rewrite_optimistic.get("isStop"):
            raise AssertionError(f"inline rewrite did not enter optimistic stop state in the click frame: {rewrite_optimistic}")
        _wait_eval(cdp, "window.__runtimeV2SmokeState.truncatePosts >= 1", timeout=12)
        _wait_eval(cdp, "window.__runtimeV2SmokeState.truncateStatus >= 1", timeout=12)
        truncate_result = cdp.evaluate("({status:window.__runtimeV2SmokeState.truncateStatus,payload:window.__runtimeV2SmokeState.truncatePayload})")
        if int((truncate_result or {}).get("status") or 0) != 200:
            raise AssertionError(f"browser rewrite truncate failed: {truncate_result}")
        try:
            _wait_eval(cdp, "window.__runtimeV2SmokeState.chatPosts >= 1", timeout=12)
        except RuntimeError as exc:
            rewrite_state = cdp.evaluate("({truncate:window.__runtimeV2SmokeState.truncatePayload,button:document.getElementById('send-btn').textContent,input:document.getElementById('message-input').value})")
            raise AssertionError(f"browser rewrite did not reach optimistic chat: {rewrite_state}") from exc
        _wait_eval(cdp, "!document.getElementById('send-btn').classList.contains('is-stop')", timeout=12)
        _wait_eval(cdp, """
            Array.from(document.querySelectorAll('.msg-wrap--user .message.user'))
              .some(node => String(node.innerText || '').includes('rewritten browser smoke question'))
        """, timeout=12)
        interrupt_layout = cdp.evaluate(
            "window.__runtimeV2SmokeHooks.interruptLayout(window.__runtimeV2SmokeHooks.currentSessionId())"
        )
        expected_interrupt_rows = ["user-steer", "llm-reasoning", "llm-response"]
        if (
            not interrupt_layout.get("distinctGroups")
            or interrupt_layout.get("oldHasReplacement")
            or interrupt_layout.get("rows") != expected_interrupt_rows
            or int(interrupt_layout.get("steerRows") or 0) != 1
            or not interrupt_layout.get("committedInPlace")
        ):
            raise AssertionError(f"interrupt steer process layout is misaligned: {interrupt_layout}")
        return {
            "ok": True,
            "runtime_version": active_runtime,
            "session_id": session_id,
            "rendered": loaded,
            "snapshot_timing": snapshot.get("timing"),
            "toc_scroll_before": before_scroll,
            "toc_scroll_after": after_toc_scroll,
            "refresh_recovered": True,
            "reconnect": {
                "session_refresh_requests": reconnect_gets,
            },
            "subagent": {
                "agent_id": child_id,
                "card_rendered": True,
            },
            "clipboard_paste": {
                "upload_calls": 1,
                "paths_inserted": 2,
            },
            "optimistic_send_button": {
                "immediate_stop_state": True,
                "preflight_stop_prevented_chat": True,
            },
            "followup_queue": {
                "queued_before_refresh": len(queued_before_refresh or []),
                "posts_before_click": posts_after_restore_and_finish,
                "posts_after_first_click": 1,
                "next_item_waited": True,
                "posts_after_second_click": 2,
            },
            "interrupt_steer_layout": interrupt_layout,
            "branch": {
                "session_id": branch_session_id,
                "elapsed_ms": round(branch_elapsed_ms, 1),
                "switched": True,
            },
            "rewrite": {
                "truncate_posts": 1,
                "optimistic_chat_posts": 1,
                "immediate_stop_state": True,
                "rendered": True,
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
        try:
            if 'branch_session_id' in locals() and branch_session_id:
                requests.delete(base_url + f"/sessions/{branch_session_id}", timeout=15)
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
