import json
import os
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from tests.test_llm_stream_full_text_browser import browser_page


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def bili_page(browser_page, tmp_path):
    page = browser_page.context.browser.new_page(viewport={"width": 1100, "height": 820})
    source = (ROOT / "plugins/sugar-bili-scroll/web/index.html").read_text(encoding="utf-8")
    rows = [{"id": "first", "name": "教程 <测试>", "enabled": True, "keywords": "DSH, 教程", "daily_quota": 5,
        "picked_today": 2, "remaining": 3, "rounds_today": 1, "last_round_at": "2026-10-23T08:49:43",
        "valley_windows": "12:00-14:00,18:00-09:00", "min_interval_minutes": 45, "busy": False}]
    errors, requests = [], []
    prompts = {kind: {"text": "默认完整提示词："+kind, "custom": False} for kind in ("duty", "dm", "reply")}
    page.on("pageerror", lambda error: errors.append(str(error)))

    def route(request_route):
        request = request_route.request
        path = urlsplit(request.url).path
        method = request.method
        if path == "/":
            request_route.fulfill(content_type="text/html", body=source)
            return
        data = {"ok": True}
        if path.endswith("/settings"):
            data["settings"] = {"plugin_id": "sugar-bili-scroll", "fields": [
                {"id": "inbound_reply", "type": "boolean", "title": "入站自动回复", "value": True}]}
            if method == "PATCH":
                requests.append(request.post_data_json)
        elif path.endswith("/system-prompts"):
            if method == "PUT":
                body = request.post_data_json
                requests.append(body)
                for kind, value in body["prompts"].items():
                    prompts[kind] = {"text": value or "默认完整提示词："+kind, "custom": bool(value)}
            data.update(mode="replace", prompts=prompts)
        elif path.endswith("/status"):
            data.update(in_window=True, picked_today=2, daily_quota=5, rounds_today=1, logged_in=True)
        elif path.endswith("/tasks") and method == "GET":
            data["items"] = rows
        elif path.endswith("/tasks") and method == "POST":
            body = request.post_data_json
            requests.append(body)
            rows.append({**body, "id": "new", "picked_today": 0, "remaining": body["daily_quota"], "rounds_today": 0})
        elif "/tasks/" in path and method == "PATCH":
            body = request.post_data_json
            requests.append(body)
            rows[0].update(body)
            rows[0]["remaining"] = max(0, body["daily_quota"]-rows[0]["picked_today"])
        elif path.endswith("/inbound"):
            data.update(enabled=True, channels="dm,at,reply", cooldown_minutes=1, max_per_hour=6, replied_last_hour=1,
                bootstrapped=True, whitelist=[{"uid": "100", "label": "好友"}], jobs=[{"key": "dm:200:1", "status": "unknown",
                "event": {"channel": "dm", "uid": "200", "text": "这条消息的发送结果需要核对"}, "error": "连接中断"}])
        elif path.endswith("/emotes"):
            data.update(items=[], count=0, bytes=0)
        elif path.endswith("/report"):
            data.update(exists=True, text="# 这条任务的日报\n### BV1aEnA6JECB")
        request_route.fulfill(content_type="application/json", body=json.dumps(data, ensure_ascii=False))

    page.route("**/*", route)
    page.goto("http://bili.test/")
    page.wait_for_selector('#task-card tr[data-id="first"]')
    yield page, rows, requests, tmp_path
    page.close()
    assert errors == []


def test_task_editor_statistics_and_scoped_report(bili_page):
    page, rows, requests, tmp_path = bili_page
    assert page.locator('#task-card tr[data-id="first"]').inner_text().find("2 / 5") >= 0
    assert page.locator('#task-card tr[data-id="first"] b').inner_text() == "教程 <测试>"
    assert page.locator('#in-jobs').inner_text().find("待核对") >= 0
    page.locator('button[data-act="edit"]').click()
    page.wait_for_selector('#task-editor[open]')
    assert page.locator('#task-editor [data-field-id="min_interval_minutes"]').input_value() == "45"
    screenshot_dir = Path(os.environ.get("SUGAR_BILI_SCREENSHOT_DIR", str(tmp_path)))
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(screenshot_dir / "editor.png"))
    page.locator('#task-editor [data-field-id="daily_quota"]').fill("0")
    page.locator('#task-editor [data-field-id="name"]').fill("已编辑任务")
    page.locator('#task-editor button[type="submit"]').click()
    page.wait_for_selector('#task-editor:not([open])', state="attached")
    assert requests[-1]["daily_quota"] == 0
    assert requests[-1]["name"] == "已编辑任务"
    page.locator('button[data-act="report"]').click()
    page.wait_for_function("document.getElementById('report-box').textContent.includes('这条任务的日报')")
    page.locator('#task-card').screenshot(path=str(screenshot_dir / "tasks.png"))


def test_task_form_is_usable_on_narrow_page(bili_page):
    page, rows, requests, _ = bili_page
    page.set_viewport_size({"width": 390, "height": 844})
    page.locator('#task-add').click()
    page.wait_for_selector('#task-editor[open]')
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
    box = page.locator('#task-editor').bounding_box()
    assert box["x"] >= 0 and box["x"]+box["width"] <= 390
    page.locator('#task-editor [data-field-id="name"]').fill("新任务")
    page.locator('#task-editor button[type="submit"]').click()
    page.wait_for_selector('#task-card tr[data-id="new"]')
    assert requests[-1]["daily_quota"] == 3


def test_global_settings_render_and_save_host_response(bili_page):
    page, _, requests, _ = bili_page
    switch = page.locator('#settings-form [data-field-id="inbound_reply"]')
    assert switch.input_value() == "true"
    switch.select_option("false")
    page.locator('#btn-save').click()
    page.wait_for_function("document.getElementById('save-hint').textContent.includes('已保存')")
    assert requests[-1] == {"values": {"inbound_reply": False}}


def test_full_system_prompt_editor_saves_and_restores_one_kind(bili_page):
    page, _, requests, _ = bili_page
    editor = page.locator('[data-prompt-kind="dm"]')
    editor.fill('你是专属聊天助手。\n普通 JSON {"a":1} 和 {{uid}} 保持完整。')
    page.locator('[data-prompt-save="dm"]').click()
    page.wait_for_function("document.getElementById('system-prompts-status').textContent.includes('已保存')")
    assert requests[-1] == {"prompts": {"dm": '你是专属聊天助手。\n普通 JSON {"a":1} 和 {{uid}} 保持完整。'}}
    assert '自定义' in page.locator('#system-prompts-form label').nth(1).inner_text()
    # Saving/resetting one template must preserve unsaved edits in another.
    page.locator('[data-prompt-kind="reply"]').fill('尚未保存的评论模板')
    page.locator('[data-prompt-reset="dm"]').click()
    page.wait_for_function("document.querySelector('[data-prompt-kind=dm]').value === '默认完整提示词：dm'")
    assert requests[-1] == {"prompts": {"dm": ""}}
    assert page.locator('[data-prompt-kind="reply"]').input_value() == '尚未保存的评论模板'
    if os.environ.get("SUGAR_BILI_SCREENSHOT_DIR"):
        target = Path(os.environ["SUGAR_BILI_SCREENSHOT_DIR"])
        target.mkdir(parents=True, exist_ok=True)
        page.locator('#system-prompts-form').screenshot(path=str(target / 'system-prompts.png'))


def test_expired_auth_is_shown_in_login_status(bili_page):
    page, _, _, _ = bili_page
    page.route("**/api/sugar-bili-scroll/status",lambda route:route.fulfill(content_type="application/json",
        body=json.dumps({"ok":True,"logged_in":False,"auth_expired":True,"picked_today":0,"daily_quota":1,"rounds_today":0})))
    page.reload()
    page.wait_for_function("document.getElementById('s-login').textContent.includes('凭证失效')")
    assert page.locator('#state-pill').inner_text() == '登录失效'


def test_account_uid_switch_logout_and_qr_cancel_controls(bili_page):
    page, _, _, _ = bili_page
    state = {'logged_in':True, 'has_credential':True, 'account_uid':'999'}
    actions = []
    def status(route):
        route.fulfill(content_type='application/json', body=json.dumps({'ok':True,'picked_today':0,'daily_quota':1,'rounds_today':0,**state}))
    def action(route):
        url = route.request.url
        actions.append(url)
        if '/login/start' in url:
            state.update(logged_in=False, has_credential=False, account_uid='')
            result = {'status':'qrcode_ready','qrcode_image':'data:image/png;base64,iVBORw0KGgo=','message':'请扫码'}
        elif '/login/cancel' in url:
            result = {'ok':True,'status':'cancelled','message':'已取消扫码'}
        else:
            state.update(logged_in=False, has_credential=False, account_uid='')
            result = {'ok':True,'status':'logged_out','message':'已退出登录'}
        route.fulfill(content_type='application/json', body=json.dumps(result))
    page.route('**/api/sugar-bili-scroll/status', status)
    page.route('**/api/sugar-bili-scroll/login/start*', action)
    page.route('**/api/sugar-bili-scroll/login/cancel', action)
    page.route('**/api/sugar-bili-scroll/logout', action)
    page.reload()
    page.wait_for_function("document.getElementById('s-login').textContent.includes('UID 999')")
    assert page.locator('#btn-login').inner_text() == '添加账号（扫码）'
    page.locator('#btn-login').click()
    page.wait_for_function("document.getElementById('qr-msg').textContent === '请扫码'")
    assert any('/login/start?force=true' in url for url in actions)
    page.locator('#btn-login-cancel').click()
    page.wait_for_function("!document.getElementById('qr-box').classList.contains('show') && !document.getElementById('btn-login').disabled")
    assert any(url.endswith('/login/cancel') for url in actions)
    state.update(logged_in=True, has_credential=True, account_uid='888')
    page.reload()
    page.wait_for_function("document.getElementById('s-login').textContent.includes('UID 888')")
    page.locator('#btn-logout').click()
    page.wait_for_function("document.getElementById('s-login').textContent === '未登录'")
    assert page.locator('#btn-logout').is_disabled()
    assert any(url.endswith('/logout') for url in actions)


def test_saved_accounts_can_be_activated_removed_and_reused_after_logout(bili_page):
    page, _, _, _ = bili_page
    state = {'uid':'999', 'saved':['999','888']}
    actions = []
    def route(request_route):
        path = urlsplit(request_route.request.url).path
        method = request_route.request.method
        if path.endswith('/status'):
            result = {'ok':True,'logged_in':bool(state['uid']),'has_credential':bool(state['uid']),
                      'account_uid':state['uid'],'picked_today':0,'daily_quota':1,'rounds_today':0}
        elif path.endswith('/accounts'):
            result = {'ok':True,'items':[{'uid':uid,'active':uid==state['uid'],'updated':0,'error':''} for uid in state['saved']]}
        elif path.endswith('/activate'):
            actions.append((method,path))
            state['uid'] = path.split('/')[-2]
            result = {'ok':True,'message':'已启用所选账号'}
        elif method == 'DELETE':
            actions.append((method,path))
            uid = path.split('/')[-1]
            state['saved'].remove(uid)
            if uid == state['uid']:state['uid']=''
            result = {'ok':True}
        else:
            actions.append((method,path))
            state['uid']=''
            result = {'ok':True,'message':'登录态已保留'}
        request_route.fulfill(content_type='application/json',body=json.dumps(result))
    page.route('**/api/sugar-bili-scroll/status',route)
    page.route('**/api/sugar-bili-scroll/accounts**',route)
    page.route('**/api/sugar-bili-scroll/logout',route)
    page.reload()
    page.wait_for_function("document.getElementById('account-select').options.length===2")
    assert page.locator('#btn-account-use').is_disabled()
    page.locator('#account-select').select_option('888')
    page.locator('#btn-account-use').click()
    page.wait_for_function("document.getElementById('s-login').textContent.includes('UID 888')")
    assert ('POST','/api/sugar-bili-scroll/accounts/888/activate') in actions
    page.locator('#account-select').select_option('999')
    page.locator('#btn-account-remove').click()
    page.wait_for_function("document.getElementById('account-select').options.length===1")
    assert ('DELETE','/api/sugar-bili-scroll/accounts/999') in actions
    page.locator('#btn-logout').click()
    page.wait_for_function("document.getElementById('s-login').textContent==='未登录'")
    assert page.locator('#account-select option').count()==1
    page.locator('#btn-account-use').click()
    page.wait_for_function("document.getElementById('s-login').textContent.includes('UID 888')")
    assert state['saved']==['888']
