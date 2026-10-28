"""Production settings assets in a browser, with isolated control API responses."""
import json
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest

from tests.test_llm_stream_full_text_browser import browser_page

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app/templates/static/settings"


@pytest.fixture
def schedules(browser_page):
    page = browser_page
    items, requests, executions = [], [], []
    state = SimpleNamespace(conflict=False)
    refs = [{"kind": "host", "owner": "core.tools", "name": name} for name in ("read_file", "write_file")]
    def route(route):
        path = urlsplit(route.request.url).path
        if path == "/settings":
            body = (ROOT / "app/templates/settings_center.html").read_text(encoding="utf-8").replace("__SETTINGS_ASSET_VERSION__", "test").replace(
                "__SETTINGS_BOOTSTRAP__", json.dumps({"section": "schedules", "workspace": "D:/Example", "sessionId": "s1"}))
            route.fulfill(content_type="text/html", body=body)
        elif path.startswith("/static/settings/"):
            file = STATIC / path.rsplit("/", 1)[1]
            route.fulfill(content_type="text/css" if file.suffix == ".css" else "application/javascript", body=file.read_text(encoding="utf-8"))
        elif path == "/api/settings/session-control":
            body = route.request.post_data_json
            requests.append(body)
            method, p = body["method"], body["params"]
            if method == "automation.list": result = {"items": items}
            elif method == "session.list": result = {"sessions": [{"id": "s1", "name": "Project chat"}]}
            elif method == "tool_catalog.list": result = {"tools": [{"tool_ref": ref} for ref in refs]}
            elif method in {"automation.create", "automation.update"}:
                if state.conflict:
                    route.fulfill(status=409, json={"ok": False, "error": {"code": "revision_conflict", "message": "配置已变化，请刷新后再保存"}})
                    return
                row = {**p, "id": p.get("id", "task-1"), "revision": p.get("expected_revision", 0) + 1, "next_run_at": 1903914000}
                items[:] = [old for old in items if old["id"] != row["id"]] + [row]
                result = row
            elif method in {"automation.pause", "automation.resume"}:
                row = next(row for row in items if row["id"] == p["id"])
                row.update(enabled=method.endswith("resume"), revision=row["revision"] + 1)
                result = row
            elif method == "automation.delete":
                items[:] = [row for row in items if row["id"] != p["id"]]
                result = {"deleted": True}
            elif method == "automation.run":
                executions.append({"operation_id": "op-1", "status": "queued", "session_id": "s1", "created_at": 1903914000})
                result = {"operation_id": "op-1", "execution_id": "op-1"}
            elif method == "automation.history": result = {"executions": executions}
            elif method == "operation.cancel": result = {"cancel_requested": True}
            else: result = {}
            route.fulfill(json={"schema_version": 1, "ok": True, "data": result})
        elif path == "/api/model_profiles":
            route.fulfill(json={"profiles": [{"id": "p1", "name": "Review model", "enabled": True}]})
        elif path.startswith("/api/"):
            route.fulfill(json={"ok": True, "items": [], "plugins": [], "ui_contributions": [], "groups": []})
        else:
            route.fulfill(status=200, content_type="application/javascript", body="")
    page.route("**/*", route)
    page.goto("http://127.0.0.1/settings#schedules")
    page.locator('[data-act="schedule-new"]').first.wait_for()
    yield SimpleNamespace(page=page, items=items, requests=requests, state=state)
    page.unroute("**/*", route)


def fill_basic(page):
    page.locator('[data-act="schedule-new"]').first.click()
    page.locator('[data-field="name"]').fill("Project review")
    page.locator('[data-field="instructions"]').fill("Review recent changes and summarize blockers.")


def test_task_create_edit_pause_run_history_and_delete(schedules):
    s, page = schedules, schedules.page
    assert page.locator('[data-act="nav"][data-id="schedules"]').inner_text() == "定时任务"
    fill_basic(page)
    page.locator('[data-field="repeat"]').select_option("weekly")
    page.locator('[data-weekday="5"]').check()
    page.locator('[data-field="time"]').fill("10:30")
    page.locator('[data-field="model"]').select_option("p1")
    page.locator('[data-field="prompt_mode"]').select_option("replace")
    page.locator('[data-field="system_text"]').fill("Review charter")
    page.locator('[data-field="tools_mode"]').select_option("custom")
    page.locator('[data-tool-ref]').first.check()
    page.locator('[data-key="read_only"]').click()
    page.locator('#st-dlg-ok').click()
    page.locator('#st-dialog').wait_for(state="hidden")
    page.locator('.st-schedule-item h3').wait_for()
    task = s.items[0]
    assert task["trigger"]["weekdays"] == [1, 5]
    assert task["trigger"]["time"] == "10:30"
    assert task["target"] == {"mode": "existing", "session_id": "s1"}
    assert task["runtime_override"]["tools"]["allow"][0]["name"] == "read_file"
    assert task["runtime_override"]["system_prompt"] == {"mode": "replace", "text": "Review charter"}
    assert task["runtime_override"]["read_only"] is True
    assert task["notification"] == "important"
    page.locator('[data-act="schedule-toggle"]').click()
    page.wait_for_function("document.querySelector('[data-act=schedule-toggle]')?.textContent==='启用'")
    page.locator('[data-act="schedule-run"]').click()
    page.locator('[data-act="schedule-history"]').click()
    page.locator('.st-schedule-run').wait_for()
    assert "排队中" in page.locator('.st-schedule-run').inner_text()
    page.locator('[data-act="schedule-cancel"]').click()
    page.locator('[data-act="cf-ok"]').click()
    page.locator('.st-schedule-run').wait_for(state="detached")
    page.locator('#st-dlg-ok').click()
    page.locator('[data-act="schedule-edit"]').click()
    assert page.locator('[data-field="system_text"]').input_value() == "Review charter"
    assert page.locator('[data-tool-ref]').first.is_checked()
    page.locator('[data-field="name"]').fill("Updated review")
    page.locator('#st-dlg-ok').click()
    page.locator('#st-dialog').wait_for(state="hidden")
    assert s.items[0]["revision"] > 1
    page.locator('[data-act="schedule-delete"]').click()
    page.locator('[data-act="cf-ok"]').click()
    page.locator('.st-schedule-empty').wait_for()
    assert not s.items


def test_new_chat_empty_tools_timezone_conflict_and_unsaved_guard(schedules):
    s, page = schedules, schedules.page
    fill_basic(page)
    page.locator('[data-key="new_chat"]').click()
    assert page.locator('[data-schedule-new]').is_visible()
    assert not page.locator('[data-schedule-existing]').is_visible()
    page.locator('[data-field="repeat"]').select_option("at")
    page.locator('[data-field="local_at"]').fill("2030-04-01T09:00")
    page.locator('[data-field="timezone"]').fill("Asia/Shanghai")
    page.locator('[data-field="tools_mode"]').select_option("custom")
    page.locator('#st-dlg-ok').click()
    page.locator('#st-dialog').wait_for(state="hidden")
    assert s.items[0]["target"] == {"mode": "new"}
    assert s.items[0]["runtime_override"]["tools"]["allow"] == []
    assert s.items[0]["trigger"]["local_at"] == "2030-04-01T09:00"
    page.locator('[data-act="schedule-edit"]').click()
    page.locator('[data-field="name"]').fill("Unsaved")
    s.state.conflict = True
    page.locator('#st-dlg-ok').click()
    page.locator('#st-schedule-error').wait_for(state="visible")
    assert "请刷新" in page.locator('#st-schedule-error').inner_text()
    assert page.locator('[data-field="name"]').input_value() == "Unsaved"
    assert page.locator('#st-dlg-ok').is_enabled()
    page.once('dialog', lambda dialog: dialog.dismiss())
    page.locator('[data-act="dlg-cancel"]').click()
    assert page.locator('#st-dialog').is_visible()
    page.once('dialog', lambda dialog: dialog.accept())
    page.locator('[data-act="dlg-cancel"]').click()
    page.locator('#st-dialog').wait_for(state="hidden")
    errors = []
    on_error = lambda error: errors.append(error)
    page.on('pageerror', on_error)
    page.evaluate("MyAgentSettings.openDialog({title:'Other settings',body:'<input class=st-input data-field=other>'})")
    page.locator('[data-field="other"]').fill('Different form')
    page.locator('[data-field="other"]').dispatch_event('change')
    assert not errors, 'closed schedule editors must release their listeners'
    page.remove_listener('pageerror', on_error)


@pytest.mark.parametrize("width,theme", [(1100, "deep-dark"), (390, "light")])
def test_schedule_editor_layout_and_visible_validation(schedules, width, theme):
    page = schedules.page
    page.set_viewport_size({"width": width, "height": 900})
    page.evaluate("value => localStorage.setItem('myagent-theme', value)", theme)
    page.reload()
    fill_basic(page)
    page.locator('[data-field="repeat"]').select_option('cron')
    page.locator('[data-field="cron"]').fill('0 9 * * 1-5')
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert page.evaluate("document.querySelector('#st-dlg-body').scrollWidth <= document.querySelector('#st-dlg-body').clientWidth + 1")
    output = ROOT / '.analysis/schedule-settings'
    output.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(output / ('desktop.png' if width > 600 else 'mobile.png')))
    page.locator('[data-key="new_chat"]').click()
    page.locator('[data-field="workspace"]').fill('')
    page.locator('#st-dlg-ok').click()
    page.locator('#st-schedule-error').wait_for(state='visible')
    assert "工作目录" in page.locator('#st-schedule-error').inner_text()
