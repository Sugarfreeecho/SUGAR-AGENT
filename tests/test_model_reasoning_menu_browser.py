"""Exercise the two-level composer menu with real browser focus and API writes."""
import json
from pathlib import Path
from urllib.parse import urlsplit

import pytest

playwright = pytest.importorskip("playwright.sync_api")
expect = playwright.expect

from tests.test_llm_stream_window_geometry import browser_page

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def model_menu_page(browser_page):
    page = browser_page
    source = (ROOT / "frontend/src/app/modules/model-profiles.js").read_text(encoding="utf-8")
    css = (ROOT / "frontend/src/styles/app.css").read_text(encoding="utf-8")
    profiles = [
        {"id": "p1", "name": "Fixture", "model": "first", "llm_type": "openai-responses", "reasoning_effort": "high"},
        {"id": "p2", "name": "Second model", "model": "second", "llm_type": "openai-responses", "reasoning_effort": "max"},
        {"id": "p3", "name": "Disabled model", "model": "third", "enabled": False},
    ]
    state = {"effort": "", "profile": "p1"}
    requests, pending = [], []
    html = """<!doctype html><html style="font-size:16px"><head><meta charset="utf-8"><style>""" + css + """</style>
      <style>#model-profile-control{position:fixed;top:auto;bottom:24px;right:24px;transform:none;width:220px;max-width:none}
      .titlebar{height:44px}#outside{margin:80px}</style></head><body>
      <div class="titlebar"></div><button id="outside">Outside</button>
      <div class="composer-model-bar" id="model-profile-control">
        <button type="button" class="composer-model-trigger" id="model-profile-trigger" aria-expanded="false">
          <span class="composer-model-v" id="model-profile-current"></span><span class="composer-model-caret"></span>
        </button><div class="composer-model-menu" id="model-profile-menu"></div>
      </div><script>localStorage.clear();var currentSessionId='',NEW_SESSION_DRAFT_KEY='draft',testLogs=[];
      function appendLogVisible(text){testLogs.push(text)}
      function selectContextTokens(){return null}function scheduleContextTokensAfterPaint(){}</script>
      <script src="/model.js"></script></body></html>"""

    def serve(route):
        request = route.request
        path = urlsplit(request.url).path
        if path == "/":
            route.fulfill(status=200, content_type="text/html", body=html)
        elif path == "/model.js":
            route.fulfill(status=200, content_type="application/javascript; charset=utf-8", body=source)
        else:
            body = json.loads(request.post_data) if request.post_data else None
            requests.append({"path": path, "method": request.method, "body": body})
            if path.endswith("/reasoning_effort") and request.method == "POST":
                pending.append(route)
                return
            if path.startswith("/api/model_profiles/") and path.endswith("/enabled"):
                next(p for p in profiles if p["id"] == path.split("/")[-2])["enabled"] = body["enabled"]
            data = {"ok": True, "profiles": profiles, "new_session_default_profile_id": "p1"} if path == "/api/model_profiles" else {
                "ok": True, "profile_id": state["profile"], "reasoning_effort": state["effort"]}
            route.fulfill(status=200, content_type="application/json", body=json.dumps(data))

    page.route("**/*", serve)
    page.goto("http://model.test/")
    expect(page.locator(".composer-model-current-name")).to_have_text("Fixture")
    yield page, requests, state, pending
    page.goto("about:blank")
    page.unroute("**/*", serve)


def test_draft_effort_uses_two_level_menu_and_updates_caption(model_menu_page):
    page, requests, _, _ = model_menu_page
    trigger = page.locator("#model-profile-trigger")
    trigger.click()
    expect(page.locator("#model-profile-menu [role=menuitem]")).to_have_count(2)
    expect(page.locator('[data-model-pane="effort"] .composer-model-cell-value')).to_have_text("high")
    page.locator('[data-model-pane="effort"]').click()
    expect(page.locator("#model-profile-menu select")).to_have_count(0)
    expect(page.locator("[data-reasoning-effort]")).to_have_text(["模型默认 · high", "low", "medium", "high", "xhigh", "max"])
    page.locator('[data-reasoning-effort="xhigh"]').click()
    expect(trigger).to_have_attribute("aria-expanded", "false")
    expect(trigger).to_be_focused()
    expect(page.locator(".composer-model-current-effort")).to_have_text("xhigh")
    assert page.evaluate("localStorage.getItem('myagent-new-session-reasoning-effort')") == "xhigh"
    trigger.click()
    page.locator('[data-model-pane="effort"]').click()
    expect(page.locator('[data-reasoning-effort="xhigh"]')).to_have_attribute("aria-checked", "true")
    expect(page.locator('[aria-checked="true"] .composer-model-check svg')).to_have_count(1)
    page.locator('[data-reasoning-effort=""]').click()
    expect(page.locator(".composer-model-current-effort")).to_have_text("high")
    assert not any(item["method"] == "POST" for item in requests)


def test_keyboard_drills_returns_and_restores_focus(model_menu_page):
    page, _, _, _ = model_menu_page
    trigger = page.locator("#model-profile-trigger")
    trigger.focus()
    page.keyboard.press("Enter")
    page.keyboard.press("ArrowDown")
    expect(page.locator('[data-model-pane="model"]')).to_be_focused()
    page.keyboard.press("ArrowDown")
    page.keyboard.press("Tab")
    expect(page.locator('[data-reasoning-effort=""]')).to_be_focused()
    page.keyboard.press("End")
    expect(page.locator('[data-reasoning-effort="max"]')).to_be_focused()
    page.keyboard.press("Enter")
    expect(page.locator(".composer-model-current-effort")).to_have_text("max")
    expect(trigger).to_be_focused()
    page.keyboard.press("Enter")
    page.keyboard.press("ArrowDown")
    page.keyboard.press("ArrowDown")
    page.keyboard.press("ArrowRight")
    expect(page.locator('[data-reasoning-effort="max"]')).to_be_focused()
    page.keyboard.press("Escape")
    expect(page.locator('[data-model-pane="effort"]')).to_be_focused()
    expect(trigger).to_have_attribute("aria-expanded", "true")
    page.keyboard.press("Escape")
    expect(trigger).to_be_focused()
    expect(trigger).to_have_attribute("aria-expanded", "false")


def test_session_save_waits_retries_and_commits(model_menu_page):
    page, requests, state, pending = model_menu_page
    page.evaluate("async()=>{currentSessionId='s1';await refreshModelProfileSelector('s1',{silent:true})}")
    trigger = page.locator("#model-profile-trigger")
    trigger.click()
    page.locator('[data-model-pane="effort"]').click()
    page.locator('[data-reasoning-effort="max"]').click()
    expect(page.locator("#model-profile-menu")).to_have_attribute("aria-busy", "true")
    expect(page.locator('[data-reasoning-effort="low"]')).to_be_disabled()
    expect(page.locator('[data-reasoning-effort="max"] .composer-model-pending')).to_have_count(1)
    assert page.evaluate("setCurrentSessionReasoningEffort('low')") is False
    assert len(pending) == 1
    pending[0].fulfill(status=500, content_type="application/json", body='{"ok":false,"error":"Retry later"}')
    expect(page.locator('[data-reasoning-effort="max"]')).to_be_enabled()
    expect(trigger).to_have_attribute("aria-expanded", "true")
    expect(page.locator(".composer-model-current-effort")).to_have_text("high")
    assert "Retry later" in page.evaluate("testLogs[0]")
    page.locator('[data-reasoning-effort="max"]').click()
    expect(page.locator("#model-profile-menu")).to_have_attribute("aria-busy", "true")
    state["effort"] = "max"
    pending[1].fulfill(status=200, content_type="application/json", body='{"ok":true}')
    expect(trigger).to_have_attribute("aria-expanded", "false")
    expect(trigger).to_be_focused()
    expect(page.locator(".composer-model-current-effort")).to_have_text("max")
    trigger.click()
    page.locator('[data-model-pane="effort"]').click()
    expect(page.locator('[data-reasoning-effort="max"]')).to_have_attribute("aria-checked", "true")
    assert [item["body"] for item in requests if item["method"] == "POST"] == [{"reasoning_effort": "max"}] * 2


def test_model_pane_keeps_switching_and_enabling(model_menu_page):
    page, _, _, _ = model_menu_page
    trigger = page.locator("#model-profile-trigger")
    trigger.click()
    page.locator('[data-model-pane="model"]').click()
    expect(page.locator('[data-profile-id="p3"]')).to_be_disabled()
    page.locator('[data-profile-id="p2"]').click()
    expect(page.locator(".composer-model-current-name")).to_have_text("Second model")
    expect(page.locator(".composer-model-current-effort")).to_have_text("max")
    expect(trigger).to_have_attribute("aria-expanded", "false")
    trigger.click()
    page.locator('[data-model-pane="model"]').click()
    page.locator('[data-toggle-profile-id="p3"]').click()
    expect(page.locator('[data-profile-id="p3"]')).to_be_enabled()
    expect(page.locator('[data-profile-id="p2"]')).to_have_attribute("aria-checked", "true")
    page.locator("#outside").click()
    expect(trigger).to_have_attribute("aria-expanded", "false")


@pytest.mark.parametrize("root_size", [12, 16, 20])
def test_menu_typography_matches_trigger_and_scales_with_ui(model_menu_page, root_size):
    page, _, _, _ = model_menu_page
    page.evaluate("px=>document.documentElement.style.fontSize=px+'px'", root_size)
    trigger = page.locator("#model-profile-trigger")
    trigger.click()
    family = page.locator("body").evaluate("el=>getComputedStyle(el).fontFamily")
    assert '"Segoe UI"' in family and '"Microsoft YaHei"' in family
    assert family.index('"Segoe UI"') < family.index('"Microsoft YaHei"')
    expected_size = root_size * 13 / 16

    def check(selector):
        styles = page.locator(selector).evaluate_all("""els=>els.map(el=>{
          const css=getComputedStyle(el);return {family:css.fontFamily,size:parseFloat(css.fontSize),
            line:parseFloat(css.lineHeight),height:el.getBoundingClientRect().height};
        })""")
        assert styles
        for style in styles:
            assert style["family"] == family
            assert style["size"] == pytest.approx(expected_size)
            assert style["line"] == pytest.approx(root_size * 20 / 16)
        return styles

    check(".composer-model-v, .composer-model-cell")
    assert page.locator("#outside").evaluate("el=>getComputedStyle(el).fontFamily") == family
    page.locator('[data-model-pane="model"]').click()
    check(".composer-model-option-name")
    trigger.click()
    trigger.click()
    page.locator('[data-model-pane="effort"]').click()
    for style in check(".composer-model-effort-option"):
        assert style["height"] >= root_size * 34 / 16


@pytest.mark.parametrize('overflow', [False, True])
def test_model_menu_gutters_remain_symmetric_when_list_scrolls(model_menu_page, overflow):
    page, _, _, _ = model_menu_page
    page.locator('#model-profile-trigger').click()
    page.locator('[data-model-pane="model"]').click()
    page.evaluate("""overflow => {
      const menu=document.querySelector('#model-profile-menu');menu.style.maxHeight='200px';
      if(overflow){const list=menu.querySelector('.composer-model-list');
        const row=list.querySelector('.composer-model-option-row');
        for(let i=0;i<30;i++)list.append(row.cloneNode(true));}
    }""", overflow)
    result = page.locator('#model-profile-menu').evaluate("""menu=>{
      const m=menu.getBoundingClientRect(),row=menu.querySelector('.composer-model-option-row').getBoundingClientRect();
      return {left:row.left-m.left,right:m.right-row.right,overflow:menu.scrollHeight>menu.clientHeight};
    }""")
    assert result['overflow'] is overflow
    assert result['left'] == pytest.approx(result['right'], abs=.2)
    assert 1 < result['left'] <= 8
