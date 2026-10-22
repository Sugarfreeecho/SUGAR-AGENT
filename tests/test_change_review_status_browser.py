"""Exercise the actual extension DOM, including empty/error-only events."""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_review_empty_failure_recovery_and_turn_isolation_in_browser():
    playwright = pytest.importorskip('playwright.sync_api')
    source = (ROOT / 'plugins/change-review/web/change-review.js').read_text(encoding='utf-8')
    css = (ROOT / 'plugins/change-review/web/change-review.css').read_text(encoding='utf-8')
    with playwright.sync_playwright() as runtime:
        options = {}
        if not Path(runtime.chromium.executable_path).is_file():
            if Path('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe').is_file():
                options['channel'] = 'msedge'
            else:
                pytest.skip('Chromium or Microsoft Edge is required for this browser check')
        browser = runtime.chromium.launch(headless=True, **options)
        page = browser.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.set_content('''<html lang="zh"><body>
          <div id="sessions-list"><div class="session-item active" data-session-id="session"></div></div>
          <div class="chat-stage"><div class="panel-inner"><div id="scroller" style="height:200px;overflow:auto">
            <div id="chat-stream" class="chat-stream" data-session-id="session">
              <div class="msg-wrap--user" data-event-index="0">Question</div>
              <div class="process-aggregate"></div>
            </div></div><div class="composer-row"></div></div></div>
          <div id="review"></div></body></html>''')
        page.add_style_tag(content=css)
        page.evaluate('''async source => {
            window.currentSessionId = 'session';
            window.MyAgentPubar = {registerPane() {return {
                host: document.getElementById('review'),
                setVisible(value) { document.getElementById('review').hidden = !value; },
                setCount() {}, setNarrow() {}, remove() {},
            };}};
            const blob = URL.createObjectURL(new Blob([source], {type:'text/javascript'}));
            window.reviewExtension = await import(blob);
            window.cleanupReview = await window.reviewExtension.installChatExtension({});
            window.sendReview = status => document.dispatchEvent(new CustomEvent('myagent:ui-event', {
                detail: {sessionId:'session', rootSessionId:'session', eventIndex:1,
                    event:{type:'file_changes_updated', changes:[], change_review_status:status}},
            }));
        }''', source)
        message = page.locator('#review .change-review-status')
        playwright.expect(page.locator('#review')).to_be_hidden()
        base = {'session_id': 'session', 'run_id': 'execution', 'turn_id': 'turn',
                'tool_call_id': 'call', 'stage': 'before', 'coverage': 'workspace'}
        page.evaluate('s => sendReview(s)', dict(base, status='failed', reason='probe <img src=x onerror=alert(1)>', at=10))
        playwright.expect(message).to_contain_text('改动审查未记录：probe <img')
        assert page.locator('#review img').count() == 0
        page.evaluate('s => sendReview(s)', dict(base, status='checked', at=9))
        playwright.expect(message).to_contain_text('probe')
        page.evaluate('s => sendReview(s)', dict(base, tool_call_id='other', status='checked', at=11))
        playwright.expect(message).to_contain_text('probe')
        page.evaluate('s => sendReview(s)', dict(base, stage='after', status='checked', at=12))
        playwright.expect(page.locator('#review')).to_be_hidden()
        page.evaluate('s => sendReview(s)', dict(base, status='checked', coverage='unavailable', at=13))
        playwright.expect(page.locator('#review')).to_be_hidden()
        page.evaluate('s => sendReview(s)', dict(base, status='failed', reason='old turn failure', at=14))
        playwright.expect(message).to_contain_text('old turn failure')
        page.evaluate('''() => {
            const stream = document.getElementById('chat-stream');
            stream.insertAdjacentHTML('beforeend', '<div style="height:400px"></div><div class="msg-wrap--user" data-event-index="10">Next question</div>');
            document.getElementById('scroller').scrollTop = 9999;
        }''')
        playwright.expect(page.locator('#review')).to_be_hidden()
        page.evaluate("document.getElementById('scroller').scrollTop = 0")
        playwright.expect(page.locator('#review')).to_be_visible()
        playwright.expect(message).to_contain_text('old turn failure')
        assert not errors
        page.evaluate('cleanupReview()')
        browser.close()
