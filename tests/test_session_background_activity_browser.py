import os
from pathlib import Path

import pytest


playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("field", ["background_jobs_running", "subagent_running"])
def test_background_dot_is_steady_yellow_and_returns_to_normal_after_completion(field):
    from tests.test_llm_stream_full_text_browser import function_source

    with playwright.sync_playwright() as runtime:
        try:
            browser = runtime.chromium.launch(headless=True, **({"channel": "msedge"} if os.name == "nt" else {}))
        except playwright.Error as exc:
            pytest.skip(str(exc))
        page = browser.new_page()
        try:
            page.set_content('<div class="session-item"><span class="session-name">后台会话</span></div>')
            page.add_style_tag(path=str(ROOT / "frontend/src/styles/app.css"))
            page.add_style_tag(content=":root { --amber-accent: #f9e2af; --green-accent: #a6e3a1; }")
            page.add_script_tag(content='''
                var currentSessionId='s1', sessionUnreadComplete=new Set(), runActive=false;
                var summary={id:'s1',unread_result:true,unread_result_status:'success'};
                var sessionStore={get:()=>summary,isRunFinalizing:()=>false};
                function isSessionRunning(){return runActive;}
                function syncSessionDraftBadge(){} function syncSessionRowQuickActions(){} function bindUiHoverTip(){}
                function updateIndicator(){applySessionItemIndicators(document.querySelector('.session-item'),'s1');}
            ''')
            page.add_script_tag(path=str(ROOT / "frontend/src/app/state/session-selectors.js"))
            source = (ROOT / "frontend/src/app/modules/session-management.js").read_text(encoding="utf-8")
            page.add_script_tag(content=function_source(source, "applySessionItemIndicators"))
            page.evaluate("field => {summary[field]=1; updateIndicator();}", field)
            for selected in ("s1", "other"):
                page.evaluate("sid => {currentSessionId=sid; updateIndicator();}", selected)
                style = page.locator(".session-name").evaluate('''element => {
                    const style=getComputedStyle(element,'::before');
                    return {color:style.backgroundColor, animation:style.animationName, opacity:style.opacity};
                }''')
                assert style == {"color": "rgb(249, 226, 175)", "animation": "none", "opacity": "1"}
                assert page.locator(".session-item").get_attribute("class") == "session-item is-background-running"
            page.evaluate("runActive=true; updateIndicator()")
            assert page.locator(".session-name").evaluate("el=>getComputedStyle(el,'::before').animationName") == "pulse-dot"
            page.evaluate("field => {summary[field]=0; runActive=false; updateIndicator();}", field)
            assert page.locator(".session-item").get_attribute("class") == "session-item is-unread-result"
            page.evaluate("summary.unread_result=false; updateIndicator()")
            assert page.locator(".session-item").get_attribute("class") == "session-item"
        finally:
            browser.close()
