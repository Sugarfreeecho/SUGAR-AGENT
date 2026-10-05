"""Exercise state restoration against the actual UI modules in a real browser."""
import json
from pathlib import Path

from tests.test_llm_stream_window_geometry import browser_page

ROOT = Path(__file__).resolve().parents[1]


def load_module(page, name):
    page.add_script_tag(content=(ROOT / "frontend/src/app/modules" / name).read_text(encoding="utf-8"))


def test_catalog_hover_then_click_keeps_list_open(browser_page):
    page = browser_page
    page.set_content('<div id="title"></div><button id="outside">Outside</button>')
    page.evaluate("""() => {
      window.subagentCatalogStore = {
        getCatalog:()=>({entries:[{childId:'child',label:'Child',activity:'inactive'}]}),
        summarizeDescendants:()=>({total:1,running:0}), isCatalogOpen:()=>false,
        setCatalogOpen:()=>{}, isSubagentRead:()=>false,
      };
    }""")
    load_module(page, "subagent-catalog-ui.js")
    page.evaluate("subagentCatalogUi.renderTrigger(document.getElementById('title'),'session')")
    trigger = page.locator("#subagent-catalog-trigger")
    trigger.hover()
    page.wait_for_function("subagentCatalogUi.isMenuOpen()")
    trigger.click()
    assert page.locator("#subagent-catalog-menu").is_visible()
    trigger.click()
    assert page.locator("#subagent-catalog-menu").is_visible()
    page.locator("#outside").click()
    assert page.locator("#subagent-catalog-menu").is_hidden()
    trigger.click()
    assert page.locator("#subagent-catalog-menu").is_visible()
    page.locator("#subagent-catalog-menu").press("Escape")
    assert page.locator("#subagent-catalog-menu").is_hidden()


def test_change_diff_survives_live_updates_and_new_turn(browser_page):
    page = browser_page
    page.set_content('<div id="host"></div>')
    load_module(page, "dock/embedder/right-column.js")
    page.evaluate("""() => {
      window.currentSessionId = 'session';
      dockRightTrackScroll = () => {};
      dockRightReviewRunning = () => false;
      dockRightFetchJSON = async () => ({response:{ok:true}, data:{ok:true,
        user_turns:[{event_index:0,preview:'First'}],
        messages:{range_start:0,has_older:false,events:[
          {type:'user',content:'First'},
          {type:'tool_result',ui:{changes:[{path:'a.js',snapshot_id:'a',revision:1,
            added:1,removed:1,diff:'-old\\n+new'}]}}
        ]}}});
      document.getElementById('host').appendChild(dockRightChangesBody({id:'changes'}));
      window.send = (event,index) => document.dispatchEvent(new CustomEvent('myagent:ui-event',
        {detail:{sessionId:'session',event,eventIndex:index}}));
    }""")
    toggle = page.locator('[data-dock-snapshot-id="a"] .dock-change-toggle')
    toggle.click()
    diff = page.locator('[data-dock-snapshot-id="a"] .dock-change-diff')
    page.wait_for_function("document.querySelector('.dock-change-diff').textContent.includes('+new')")
    for event in [
        {"type": "run_started"},
        {"type": "tool_result", "ui": {"changes": [{"path": "b.js", "snapshot_id": "b", "added": 1, "removed": 0, "diff": "+second"}]}},
        {"type": "user", "content": "Second", "turn_id": "second-token"},
        {"type": "tool_result", "ui": {"changes": [{"path": "c.js", "snapshot_id": "c", "added": 1, "removed": 0, "diff": "+third"}]}},
    ]:
        page.evaluate("send(" + json.dumps(event) + ",10)")
        page.wait_for_function("document.querySelector('[data-dock-snapshot-id=a] .dock-change-diff').textContent.includes('+new')")
        assert toggle.get_attribute("aria-expanded") == "true"
        assert diff.inner_text() == "-old\n+new\n"
    assert page.locator('[data-dock-changes-scope="turn"]').input_value() == "0"
    assert page.locator('[data-dock-snapshot-id="c"]').count() == 0
    page.locator('[data-dock-changes-scope="turn"]').select_option("10")
    assert page.locator('[data-dock-snapshot-id="c"]').count() == 1
    assert page.locator('[data-dock-snapshot-id="a"]').count() == 0


def test_approval_analysis_finishes_after_session_switch_and_restores_card(browser_page):
    page = browser_page
    page.set_content('<div id="chat-stream"></div>')
    load_module(page, "human-interactions.js")
    page.evaluate("""() => {
      window.currentSessionId = 'first';
      syncHumanInteractionSessionSummary = () => {};
      updateHumanInteractionBanner = () => {};
      window.record = {kind:'approval',approval_id:'approval',status:'pending',session_id:'first'};
      document.getElementById('chat-stream').appendChild(createHumanApprovalCard(record,'first'));
      window.fetch = () => new Promise(resolve => { window.finishAnalysis = resolve; });
      window.analysisPromise = analyzeHumanApproval(document.querySelector('.human-approval-card'));
      window.currentSessionId = 'second';
      document.getElementById('chat-stream').replaceChildren();
      finishAnalysis({ok:true,json:async()=>({ok:true,approval:{...record,analysis:{
        recommendation:'deny',risk:'high',reason:'Review reason',available:true}}})});
    }""")
    page.evaluate("""async () => {await analysisPromise; currentSessionId='first';
      const saved=humanInteractionSessionState('first').approvals.approval;
      document.getElementById('chat-stream').appendChild(createHumanApprovalCard(saved,'first'));}""")
    assert page.locator(".human-approval-analysis").is_visible()
    assert "Review reason" in page.locator(".human-approval-analysis").inner_text()
    assert page.locator(".human-approval-card").get_attribute("data-rejection-reason-suggestion") == "Review reason"
    assert page.evaluate("""() => {
      const sid='first';
      applyHumanInteractionEvent(sid,{type:'approval_resolved',approval_id:'approval',decision:'allow_once'});
      const saved=applyHumanInteractionEvent(sid,{type:'approval_analyzed',approval_id:'approval',status:'pending',
        analysis:{recommendation:'deny',reason:'Late advice'}});
      return saved.status==='resolved' && saved.decision==='allow_once' && saved.analysis.reason==='Late advice';
    }""")
