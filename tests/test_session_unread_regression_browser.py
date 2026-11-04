"""The sidebar failure dot cannot be resurrected by a late HTTP snapshot."""
import os
import re
from pathlib import Path

import pytest


playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]


def function_source(source, name):
    match = re.search(r"^(?:async )?function " + name + r"\([\s\S]*?^}", source, re.M)
    assert match, name
    return match.group(0)


def test_a_late_snapshot_cannot_restore_an_old_failure_dot():
    with playwright.sync_playwright() as runtime:
        try:
            browser = runtime.chromium.launch(
                headless=True, **({"channel": "msedge"} if os.name == "nt" else {})
            )
        except playwright.Error as error:
            pytest.skip(f"Local Chromium browser unavailable: {error}")
        page = browser.new_page()
        try:
            page.set_content('<div class="session-item"><span class="session-name">会话</span></div>')
            page.add_style_tag(path=str(ROOT / "frontend/src/styles/app.css"))
            page.add_style_tag(content=":root { --green-accent: #a6e3a1; --red-accent: #f38ba8; }")
            page.add_script_tag(content='''
                var currentSessionId = 'other';
                var sessionUnreadComplete = new Set();
                var sessionUnreadClearInFlight = {};
                function persistSessionUnread() {}
                function syncSessionListIndicatorClasses() {}
                function syncSessionDraftBadge() {}
                function syncSessionRowQuickActions() {}
                function bindUiHoverTip() {}
                function isSessionRunning() { return false; }
                function refreshSingleSessionRow() {}
                function updateIndicator() {
                    applySessionItemIndicators(document.querySelector('.session-item'), 's1');
                }
                window.fetch = async function () { return {ok: true, json: async () => ({cleared: true})}; };
            ''')
            page.add_script_tag(path=str(ROOT / "frontend/src/app/state/session-store.js"))
            page.add_script_tag(path=str(ROOT / "frontend/src/app/state/session-selectors.js"))
            shared = (ROOT / "frontend/src/app/modules/shared-state-and-dialogs.js").read_text(encoding="utf-8")
            for name in ("clearSessionUnreadState", "shouldSuppressSessionUnreadSnapshot", "markSessionResultComplete"):
                page.add_script_tag(content=function_source(shared, name))
            management = (ROOT / "frontend/src/app/modules/session-management.js").read_text(encoding="utf-8")
            page.add_script_tag(content=function_source(management, "applySessionItemIndicators"))
            page.evaluate("window.store = sessionStore")

            def row_state():
                return page.evaluate('''() => {
                    const row = document.querySelector('.session-item');
                    const dot = document.querySelector('.session-name');
                    return {
                        classes: row.getAttribute('class'),
                        color: getComputedStyle(dot, '::before').backgroundColor,
                    };
                }''')

            page.evaluate("store.upsert({id: 's1'}); markSessionResultComplete('s1', 'failed', 'old-run'); updateIndicator();")
            failed = row_state()
            assert failed["classes"] == "session-item is-unread-failed"
            assert failed["color"] == "rgb(243, 139, 168)"

            page.evaluate('''() => {
                window.oldRow = JSON.parse(JSON.stringify(store.get('s1')));
                markSessionResultComplete('s1', 'success', 'new-run');
                updateIndicator();
            }''')
            assert row_state() == {
                "classes": "session-item is-unread-result",
                "color": "rgb(166, 227, 161)",
            }

            # A full-list response generated before the retry finished.
            page.evaluate("store.applySnapshot([window.oldRow]); updateIndicator();")
            assert row_state() == {
                "classes": "session-item is-unread-result",
                "color": "rgb(166, 227, 161)",
            }

            # Reading the new result must survive the same late row.
            page.evaluate("(async () => { currentSessionId = 's1'; return await clearSessionUnreadState('s1'); })()")
            page.evaluate("currentSessionId = 'other'; store.applySnapshot([window.oldRow]); updateIndicator();")
            assert row_state() == {"classes": "session-item", "color": "rgba(0, 0, 0, 0)"}

            # A genuine new failure still owns the red dot.
            page.evaluate("markSessionResultComplete('s1', 'failed', 'newer-run'); updateIndicator();")
            assert row_state() == {
                "classes": "session-item is-unread-failed",
                "color": "rgb(243, 139, 168)",
            }

            # These HTTP runs have never appeared in this page's history. Only
            # the server generation establishes their age relative to live SSE.
            for index, (method, status) in enumerate([
                ("applySnapshot", "success"), ("applySnapshot", "failed"),
                ("upsert", "success"), ("upsert", "failed"),
            ]):
                order = 100 + index * 10
                page.evaluate('''({method, status, order}) => {
                    const id = 'live-' + order;
                    markSessionResultComplete('s1', status, id, order);
                    const old = {id:'s1', unread_result:true,
                        unread_result_status:status === 'success' ? 'failed' : 'success',
                        unread_result_run_id:'unseen-' + order, unread_result_run_order:order - 1};
                    store[method](method === 'applySnapshot' ? [old] : old);
                    updateIndicator();
                }''', {"method": method, "status": status, "order": order})
                expected = {
                    "classes": "session-item " + ("is-unread-result" if status == "success" else "is-unread-failed"),
                    "color": "rgb(166, 227, 161)" if status == "success" else "rgb(243, 139, 168)",
                }
                assert row_state() == expected
                page.evaluate('''({status, order}) => {
                    store.upsert({id:'s1', unread_result:true, unread_result_status:status,
                        unread_result_run_id:'live-' + order, unread_result_run_order:order});
                    updateIndicator();
                }''', {"status": status, "order": order})
                assert row_state() == expected
        finally:
            browser.close()
