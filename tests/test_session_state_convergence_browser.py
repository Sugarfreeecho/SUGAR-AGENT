"""Exercise the assembled UI, real DOM and send/stream cleanup without an LLM."""
import json
import os
import re
from pathlib import Path
from urllib.parse import urlparse

import pytest

playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def browser():
    with playwright.sync_playwright() as runtime:
        instance = runtime.chromium.launch(headless=True, **({"channel": "msedge"} if os.name == "nt" else {}))
        yield instance
        instance.close()


@pytest.fixture
def ui(browser):
    page = browser.new_page()
    page.set_default_timeout(8000)
    state = {"fail_binding": False, "terminal": True, "requests": [], "errors": [], "failed": False}
    page.on("pageerror", lambda error: state["errors"].append(str(error)))
    sessions = [{"id": sid, "name": "Session " + sid, "created_at": "2026-10-27T00:00:00Z",
                 "work_dir": str(ROOT), "work_dir_available": True, "run_active": False,
                 "stream_active": False, "active_run": None, "archived": False,
                 "pending_human_interactions": {"total": 0}} for sid in ("a", "b")]
    profiles = {"ok": True, "profiles": [{"id": "p", "name": "Verified model", "model": "test-model",
                "enabled": True, "usable": True}], "new_session_default_profile_id": "p"}

    def respond(route):
        request = route.request
        path = urlparse(request.url).path
        state["requests"].append(path)
        if path.startswith("/assets/"):
            file = ROOT / "app/templates/dist" / path.lstrip("/")
            route.fulfill(path=str(file))
            return
        if path == "/":
            route.fulfill(path=str(ROOT / "app/templates/dist/index.html"), content_type="text/html")
            return
        if path == "/chat":
            form = request.post_data or ""
            match = re.search(r'name="client_run_id"\r\n\r\n([^\r\n]+)', form)
            assert match, form[:200]
            rid = match.group(1)
            events = [{"type": "run_started", "run_id": rid, "ephemeral": True},
                      {"type": "final", "run_id": rid, "content": "Completed in the background."}]
            if state["terminal"]:
                events.append({"type": "run_failed" if state["failed"] else "run_finished", "run_id": rid,
                               "error": "deque mutated during iteration" if state["failed"] else "", "ephemeral": True})
            if state["failed"]:
                events = [event for event in events if event["type"] != "final"]
            body = "".join("data: " + json.dumps(event) + "\n\n" for event in events) + "data: [DONE]\n\n"
            route.fulfill(content_type="text/event-stream", body=body)
            return
        if path == "/sessions/changes":
            route.abort()  # No wall-clock polling or live backend in this test.
            return
        if path == "/sessions/a/stream":
            rid = state.get("session_active_run", "")
            body = ("data: " + json.dumps({"type": "run_finished", "run_id": rid, "ephemeral": True}) + "\n\n") if rid else ""
            route.fulfill(content_type="text/event-stream", body=body + "data: [DONE]\n\n")
            return
        result = {"ok": True, "items": [], "plugins": [], "servers": [], "workers": [], "slots": []}
        if path == "/sessions/state":
            result = {"sessions": sessions, "active_runs": [], "state_revision": 1, "seq": 1, "archived_count": 0}
        elif path == "/sessions":
            result = sessions
        elif path == "/api/model_profiles":
            result = profiles
        elif path.endswith("/model_profile"):
            result = {"ok": False, "error": "temporary binding failure"} if state["fail_binding"] else {"ok": True, "profile_id": "p"}
        elif path in ("/sessions/a", "/sessions/b"):
            result = {**sessions[0 if path.endswith("/a") else 1], "queued_followup_state": "ready"}
            if path == "/sessions/a" and state.get("session_active_run"):
                result.update(run_active=True, stream_active=True, active_run={
                    "session_id": "a", "run_id": state["session_active_run"], "run_active": True, "runtime_v2": True})
        elif path.endswith("/history_snapshot"):
            result = {"events": [], "count": 0, "range_start": 0, "range_end": 0, "has_more": False,
                      "user_turns": [], "run_active": False, "stream_active": False, "source": "runtime_v2_snapshot"}
        elif path.endswith("/messages"):
            result = []
        elif path.endswith("/count"):
            result = {"count": 0}
        elif path.endswith("/user_turns"):
            result = {"turns": []}
        elif path.endswith("/interactions") or path.endswith("/approvals"):
            result = {"ok": True, "interactions": [], "approvals": []}
        elif path == "/api/runtime-status":
            result = {"ok": True, "status": "idle", "active_run_count": 0, "active_session_ids": []}
        route.fulfill(content_type="application/json", body=json.dumps(result))

    page.route("**/*", respond)
    # Export test-only entrypoints from the real assembled Function closure.
    # No lifecycle/rendering functions are stubbed or replaced.
    replacements = []
    baseline_dir = os.getenv("SESSION_STATE_BASELINE_DIR")
    if baseline_dir:
        for relative in ("frontend/src/app/modules/sse-handling.js", "frontend/src/app/modules/model-profiles.js",
                         "frontend/src/app/state/session-event-reducer.js"):
            replacements.append([(ROOT / relative).read_text(encoding="utf-8"),
                                 (Path(baseline_dir) / relative).read_text(encoding="utf-8")])
    page.add_init_script("const baselineReplacements=" + json.dumps(replacements) + ";" + """
        const OriginalFunction=window.Function;
        window.Function=function(...args){
            if(String(args.at(-1)).includes('//# sourceURL=myagent-ui.js')){
                args[args.length-1]=String(args.at(-1)).split(String.fromCharCode(13,10)).join(String.fromCharCode(10));
                for(const [current,previous] of baselineReplacements){
                    if(!args.at(-1).includes(current))throw new Error('Baseline source section not found');
                    args[args.length-1]=args.at(-1).replace(current,previous);
                }
                args[args.length-1]+=`\nwindow.__stateTest={
                  store:sessionStore, send:sendMessage, switchSession, setCurrentSessionState,
                  queue:getFollowupQueue, persist:persistFollowupQueue, render:renderFollowupQueue,
                  refreshModels:refreshModelProfileSelector,
                  async takeover(payload){
                    maybeTakeOverActiveRuntimeSession(payload);
                    await runtimeTakeoverBySession.a;
                  },
                  attachAgain(){return attachSessionEventStream('a',{skipInitialLoad:true,force:true,afterIndex:0});},
                  startDelayedAttach(){
                    sessionStore.applyActiveRunForSession('a',{session_id:'a',run_id:'delayed',run_active:true});
                    const previous=ensureLatestHistoryTailForLiveAppend;
                    ensureLatestHistoryTailForLiveAppend=()=>new Promise(resolve=>{window.__releaseAttach=resolve;});
                    window.__delayedAttach=attachSessionEventStream('a',{skipInitialLoad:true,force:true})
                      .finally(()=>{ensureLatestHistoryTailForLiveAppend=previous;});
                  },
                  finishOldRun(){
                    applySessionTerminalNotifications([{type:'run_finished',session_id:'a',run_id:'delayed'}]);
                  },
                  replayFailure(){
                    const ctx=newDomContext(getVisibleChatStream());ctx.runId='history-failure';
                    renderEvent(ctx,{type:'status',content:'Before failure'},0,'a');
                    renderEvent(ctx,{type:'run_failed',run_id:ctx.runId,error:'Persisted failure'},1,'a');
                  },
                  terminalWithPresentationFailure(){
                    const ctx=newDomContext(getVisibleChatStream());ctx.runId='presentation-fault';ctx.terminalSeen=true;
                    setSessionRunState('a',{ctx,runId:ctx.runId,controller:new AbortController()});
                    const previous=finalizeLlmStreamChunks;
                    try{
                      finalizeLlmStreamChunks=()=>{throw new Error('injected presentation fault');};
                      endRunForClient('a',ctx,{runId:ctx.runId,drainFollowup:false,syncFollowup:false});
                    }catch(error){}
                    finally{finalizeLlmStreamChunks=previous;}
                    return {run:!!sessionStore.getRun('a')};
                  },
                  beginReceiptStream(){
                    const ctx=newDomContext(getVisibleChatStream()); ctx.runId='adopted';
                    initRunFinalTracking(ctx);
                    setSessionRunState('a',{ctx,runId:'adopted',controller:new AbortController(),reattached:true});
                    let writer;
                    const response=new Response(new ReadableStream({start(c){writer=c;}}),
                        {headers:{'content-type':'text/event-stream'}});
                    window.__receiptWriter=writer;
                    window.__receiptPromise=consumeAgentSseResponse(response,ctx,'a',0);
                  }
                };`;
            }
            return OriginalFunction(...args);
        };
        window.__MYAGENT_FEATURES__={followupRestart:true};
        window.__WORK_DIR__='test-workspace';
    """)
    page.goto("http://127.0.0.1:8192/", wait_until="domcontentloaded")
    page.wait_for_function("!!window.__stateTest")
    page.evaluate("() => __stateTest.switchSession('a')")
    yield page, state
    page.close()


@pytest.mark.parametrize("terminal", [True, False], ids=["terminal", "lost-terminal"])
def test_background_send_releases_the_reader_and_finishes_cleanup(ui, terminal):
    page, state = ui
    state["terminal"] = terminal
    result = page.evaluate("""async () => {
        try {
            const sent=await __stateTest.send({sessionId:'a',message:'Background regression',
                onRunStarted(){__stateTest.setCurrentSessionState('b');}});
            return {sent,run:!!__stateTest.store.getRun('a')};
        }catch(error){return {error:String(error)};}
    }""")
    assert result == {"sent": True, "run": False}, result
    page.wait_for_function("__stateTest.store.get('a').run_active===false")
    page.evaluate("() => __stateTest.switchSession('a')")
    assert page.locator("#send-btn").inner_text().strip() != "停止"
    assert not any("ReferenceError" in error for error in state["errors"]), state["errors"]


@pytest.mark.parametrize("protocol", ["projected", "optimistic-skip"])
def test_adopted_followup_receipt_removes_the_queue_before_the_answer_finishes(ui, protocol):
    page, _ = ui
    page.evaluate("""protocol => {
      __stateTest.queue('a').push({id:'local',text:'Already being executed',steerId:'queued-op',
        serverQueued:true,awaitingRunEnd:true});
      __stateTest.persist('a');__stateTest.render('a');
      __stateTest.beginReceiptStream();
      const event=protocol==='projected'?{type:'user',content:'Already being executed',operation_id:'queued-op',run_id:'adopted'}:
        {protocol:'runtime_v2',seq:1,runtime_seq:1,session_id:'a',skip_ui:true,
          runtime_event:{type:'user_turn_committed',payload:{operation_id:'queued-op'}}};
      __receiptWriter.enqueue(new TextEncoder().encode('data: '+JSON.stringify(event)+'\\n\\n'));
    }""", protocol)
    page.wait_for_function("__stateTest.queue('a').length===0", timeout=3000)
    assert page.locator(".followup-queue-row").count() == 0
    page.evaluate("async () => {__receiptWriter.close();await __receiptPromise;}")


def test_model_refresh_failure_preserves_known_binding_and_recovers_on_focus(ui):
    page, state = ui
    assert page.evaluate("() => __stateTest.refreshModels('a')") is True
    label = page.locator("#model-profile-current").inner_text()
    state["fail_binding"] = True
    assert page.evaluate("() => __stateTest.refreshModels('a',{silent:true})") is False
    assert page.locator("#model-profile-current").inner_text() == label
    assert page.locator("[data-model-profile-retry]").is_enabled()
    state["fail_binding"] = False
    page.evaluate("() => window.dispatchEvent(new Event('focus'))")
    page.wait_for_function("!document.querySelector('#model-profile-trigger').hasAttribute('data-model-load-failed')")
    assert page.locator("#model-profile-current").inner_text() == label


def test_presentation_failure_cannot_keep_a_terminal_reader_alive(ui):
    page, _ = ui
    assert page.evaluate("() => __stateTest.terminalWithPresentationFailure()") == {"run": False}


def test_failed_run_explains_the_interruption_and_does_not_show_success(ui):
    page, state = ui
    state["failed"] = True
    assert page.evaluate("() => __stateTest.send({sessionId:'a',message:'Failure regression'})") is True
    assert page.locator(".process-aggregate.is-failed .process-aggregate-title").inner_text() == "执行失败"
    assert "deque mutated during iteration" in page.locator(".process-aggregate.is-failed").inner_text()
    assert page.locator(".process-aggregate.is-failed.is-running").count() == 0
    assert page.locator(".process-aggregate.is-failed.is-collapsed").count() == 0
    assert page.evaluate("() => !!__stateTest.store.getRun('a')") is False


def test_persisted_failure_remains_visible_after_history_replay(ui):
    page, _ = ui
    page.evaluate("() => __stateTest.replayFailure()")
    assert page.locator(".process-aggregate.is-failed .process-aggregate-title").inner_text() == "执行失败"
    assert "Persisted failure" in page.locator(".process-aggregate.is-failed").inner_text()


def test_delayed_failure_from_an_old_run_cannot_mark_the_new_run_failed(ui):
    page, _ = ui
    page.evaluate("""() => {
      __stateTest.beginReceiptStream();
      __receiptWriter.enqueue(new TextEncoder().encode('data: '+JSON.stringify({type:'run_failed',
        run_id:'older',error:'Old failure',ephemeral:true})+'\\n\\n'));
    }""")
    page.wait_for_function("__stateTest.store.isTerminalRun('a','older')")
    assert page.locator(".process-aggregate.is-failed").count() == 0
    assert page.evaluate("() => __stateTest.store.getRun('a').runId") == "adopted"
    page.evaluate("async () => {__receiptWriter.close();await __receiptPromise;}")


def test_delayed_runtime_heartbeat_cannot_reopen_a_terminal_session(ui):
    page, state = ui
    page.evaluate("() => __stateTest.store.markTerminalRun('a','ended')")
    page.evaluate("() => __stateTest.takeover({active_session_ids:['a']})")
    assert "/sessions/a/stream" not in state["requests"], "A stale heartbeat must not reopen an ended run"
    assert page.evaluate("() => !!__stateTest.store.getRun('a')") is False


def test_runtime_heartbeat_can_attach_a_genuinely_new_run(ui):
    page, state = ui
    state["session_active_run"] = "new-run"
    page.evaluate("() => __stateTest.store.markTerminalRun('a','ended')")
    page.evaluate("() => __stateTest.takeover({active_session_ids:['a']})")
    assert state["requests"].count("/sessions/a/stream") == 1


def test_terminal_during_history_catchup_cancels_the_pending_attachment(ui):
    page, state = ui
    page.evaluate("() => __stateTest.startDelayedAttach()")
    page.wait_for_function("typeof __releaseAttach==='function'")
    page.evaluate("() => __stateTest.finishOldRun()")
    page.evaluate("async () => {__releaseAttach(true);await __delayedAttach;}")
    assert "/sessions/a/stream" not in state["requests"], "Catch-up must recheck the terminal before claiming a local reader"
    assert page.evaluate("() => !!__stateTest.store.getRun('a')") is False


def test_parallel_attachment_cannot_create_a_second_reader(ui):
    page, state = ui
    page.evaluate("() => __stateTest.startDelayedAttach()")
    page.wait_for_function("typeof __releaseAttach==='function'")
    page.evaluate("() => __stateTest.attachAgain()")
    assert "/sessions/a/stream" not in state["requests"]
    page.evaluate("() => __stateTest.finishOldRun()")
    page.evaluate("async () => {__releaseAttach(true);await __delayedAttach;}")


def test_pending_attachment_cannot_overwrite_a_newer_reader(ui):
    page, state = ui
    page.evaluate("() => __stateTest.startDelayedAttach()")
    page.wait_for_function("typeof __releaseAttach==='function'")
    page.evaluate("() => __stateTest.beginReceiptStream()")
    page.evaluate("async () => {__releaseAttach(true);await __delayedAttach;}")
    assert "/sessions/a/stream" not in state["requests"]
    assert page.evaluate("() => __stateTest.store.getRun('a').runId") == "adopted"
    page.evaluate("async () => {__receiptWriter.close();await __receiptPromise;}")
