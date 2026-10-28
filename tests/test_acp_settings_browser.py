"""Exercise the shipped ACP page with deterministic API responses in Chromium."""
import json
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest
from tests.test_llm_stream_full_text_browser import browser_page

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "plugins/acp-agents/web"


@pytest.fixture
def acp_page(browser_page):
    page = browser_page
    state = SimpleNamespace(fail=False, reject=False, puts=[], polls=0, raw="{}", intents=[], jobs=[])
    data = {"online_count": 1, "session_count": 1, "launch": {"command": "python", "args": ["acp_stdio.py"], "env_refs": ["MYAGENT_CONTROL_TOKEN"]},
        "connections": [{"id": "client-1", "client": {"name": "<b>DSH</b>", "version": "1.4.0"}, "status": "online", "busy": True,
            "protocol_version": 1, "connected_at": "2026-10-28T00:00:00Z", "last_seen": "2026-10-28T00:01:00Z",
            "last_activity": "2026-10-28T00:00:30Z", "activity": "prompt", "sessions": [
                {"session_id": "s/1", "title": "Test chat", "cwd": "D:/Work", "attached": True, "busy": True}]}]}
    def route(route):
        path = urlsplit(route.request.url).path
        if path == "/host":
            route.fulfill(content_type="text/html", body='''<script>window.messages=[];window.addEventListener('message',e=>messages.push(e.data));</script>
                <iframe src="/plugins/acp-agents?embedded=1" style="width:100%;height:1800px;border:0"></iframe>''')
        elif path == "/plugins/acp-agents":
            route.fulfill(content_type="text/html", body=(WEB / "index.html").read_text(encoding="utf-8"))
        elif path.startswith("/plugin-assets/acp-agents/"):
            file = WEB / "assets" / path.rsplit("/", 1)[1]
            route.fulfill(content_type="text/css" if file.suffix == ".css" else "application/javascript", body=file.read_text(encoding="utf-8"))
        elif path == "/static/settings/settings.css":
            route.fulfill(content_type="text/css", body=(ROOT / "app/templates/static/settings/settings.css").read_text(encoding="utf-8"))
        elif path == "/api/acp/connections":
            state.polls += 1
            route.fulfill(status=503 if state.fail else 200, json={"detail": "Backend unavailable"} if state.fail else data)
        elif path == "/api/acp/targets":
            if route.request.method == "PUT":
                state.puts.append(route.request.post_data_json)
                if state.reject:
                    route.fulfill(status=422, json={"detail": "Invalid ACP target configuration"})
                    return
                state.raw = route.request.post_data_json["agents_json"]
            route.fulfill(json={"agents_json": state.raw, "target_ids": list(json.loads(state.raw))})
        elif path == "/api/acp/outbound":
            route.fulfill(json={"parents": [{"id": "source-1", "name": "My source conversation"}], "targets": ["codex"],
                "sessions": [{"agent": "codex", "session_id": "saved-remote-session", "title": "Previous work", "available": True, "connected": True}],
                "tasks": state.jobs, "next_cursors": {"codex": "next-page"}})
        elif path == "/api/acp/outbound/requests":
            body = route.request.post_data_json
            state.intents.append(body)
            if body["action"] == "task":
                state.jobs.append({"task_id": "task-1", "agent": "codex", "session_id": body["arguments"].get("session_id", "fresh-session"), "session_action": "resume", "status": "succeeded"})
            route.fulfill(json={"accepted": True, "origin": body["origin"], "operation_id": "operation-1"})
        elif path == "/api/acp/outbound/tasks/task-1":
            route.fulfill(json={"status": "succeeded", "output": "progress:final-result", "events": [{"seq": 1, "type": "message", "phase": "progress", "text": "progress:"}],
                "delivery": {"status": "accepted", "operation_id": "return-operation"}, "truncated": False})
        else:
            route.fulfill(status=404, body="")
    page.route("**/*", route)
    page.goto("http://127.0.0.1/plugins/acp-agents")
    page.wait_for_function("!document.getElementById('targets').disabled")
    yield page, state
    for frame in page.frames:
        frame.evaluate("document.getElementById('targets')?.setRangeText('{}',0,document.getElementById('targets').value.length)")
        frame.evaluate("document.getElementById('task-prompt')?.setRangeText('',0,document.getElementById('task-prompt').value.length)")
    page.unroute("**/*", route)


def test_connections_errors_refresh_and_draft_survival(acp_page):
    page, state = acp_page
    page.locator(".connection").wait_for()
    assert page.locator(".client-line strong").inner_text() == "<b>DSH</b> · 1.4.0"
    assert page.locator(".client-line b").count() == 0
    assert page.locator(".badge").inner_text() == "运行中"
    assert page.locator(".session a").get_attribute("href") == "/?session=s%2F1"
    assert "MYAGENT_CONTROL_TOKEN" in page.locator("#launch").input_value()
    draft = '{"dsh":{"command":"node"}}'
    page.locator("#targets").fill(draft)
    state.fail = True
    page.locator("#refresh").click()
    page.wait_for_function("!document.getElementById('connection-error').hidden")
    assert "状态可能已过期" in page.locator("#connection-error").inner_text()
    assert page.locator(".connection").count() == 1
    assert page.locator("#targets").input_value() == draft
    state.fail = False
    page.locator("#refresh").click()
    page.wait_for_function("document.getElementById('connection-error').hidden")
    assert page.locator("#targets").input_value() == draft


def test_outbound_validation_errors_and_save(acp_page):
    page, state = acp_page
    page.locator("#targets").fill("{")
    page.locator("#save").click()
    assert "JSON" in page.locator("#settings-error").inner_text()
    assert state.puts == []
    draft = '{"dsh":{"command":"node"}}'
    page.locator("#targets").fill(draft)
    state.reject = True
    page.locator("#save").click()
    page.wait_for_function("document.getElementById('settings-error').textContent.includes('Invalid ACP')")
    assert page.locator("#targets").input_value() == draft
    state.reject = False
    page.locator("#save").click()
    page.wait_for_function("document.getElementById('save').disabled && document.getElementById('settings-error').hidden")
    assert state.puts[-1] == {"agents_json": draft}
    assert page.locator("#draft-status").inner_text() == "已保存"


def test_embedded_context_resizing_and_mobile_layout(acp_page):
    page, _ = acp_page
    page.goto("http://127.0.0.1/host")
    frame = page.frame_locator("iframe")
    frame.locator(".connection").wait_for()
    page.evaluate("document.querySelector('iframe').contentWindow.postMessage({type:'myagent:plugin-settings-context',theme:'theme-dark',lang:'en',fontPx:18},location.origin)")
    page.wait_for_function("document.querySelector('iframe').contentDocument.documentElement.lang==='en'")
    assert frame.locator("html").get_attribute("class") == "theme-dark"
    assert frame.locator("#inbound-heading").inner_text() == "Connected clients · inbound"
    assert not frame.locator(".standalone").is_visible()
    frame.locator("#targets").fill('{"dsh":{"command":"node"}}')
    page.wait_for_function("messages.some(m=>m.type==='myagent:plugin-settings-dirty'&&m.dirty)")
    assert page.evaluate("messages.some(m=>m.type==='myagent:plugin-settings-resize'&&m.height>320)")
    page.set_viewport_size({"width": 390, "height": 800})
    assert frame.locator("html").evaluate("el=>el.scrollWidth <= el.clientWidth+1")
    frame.locator("#targets").fill("{}")
    page.set_viewport_size({"width": 1100, "height": 800})


def test_choose_remote_session_background_policy_and_progress(acp_page):
    page, state = acp_page
    page.locator('#source-session option[value="source-1"]').wait_for(state="attached")
    page.locator("#source-session").select_option("source-1")
    page.locator('#remote-session option[value="saved-remote-session"]').wait_for(state="attached")
    page.locator("#remote-list").click()
    page.wait_for_function("!document.getElementById('remote-list').disabled")
    assert state.intents[-1]["action"] == "list"
    page.locator("#remote-more").click()
    page.wait_for_function("!document.getElementById('remote-more').disabled")
    assert state.intents[-1]["arguments"]["cursor"] == "next-page"
    page.locator("#remote-session").select_option("saved-remote-session")
    page.locator("#task-prompt").fill("Continue the earlier task")
    page.locator("#task-notify").select_option("all")
    page.locator("#task-submit").click()
    page.locator(".task-row").wait_for()
    intent = state.intents[-1]
    assert intent["origin"] == "source-1" and intent["action"] == "task"
    assert intent["arguments"] == {"agent": "codex", "prompt": "Continue the earlier task", "background": True, "notify": "all", "session_id": "saved-remote-session"}
    assert intent["request_id"]
    page.locator(".task-row button").first.click()
    page.wait_for_function("!document.getElementById('task-detail').hidden")
    assert page.locator("#task-progress").inner_text() == "progress:"
    assert page.locator("#task-result").inner_text() == "progress:final-result"
    assert "accepted" in page.locator("#task-delivery").inner_text()
    page.locator("#remote-new").click()
    page.wait_for_function("!document.getElementById('remote-new').disabled")
    assert state.intents[-1]["action"] == "new" and "session_id" not in state.intents[-1]["arguments"]
