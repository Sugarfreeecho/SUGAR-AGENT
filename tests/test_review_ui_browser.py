"""Review regressions exercised with real DOM and page lifecycles."""
from pathlib import Path

from tests.test_llm_stream_full_text_browser import browser_page
from tests.test_details_pages_browser import details_page, plugin_frame

ROOT = Path(__file__).resolve().parents[1]


def test_usage_fold_state_survives_rerender_and_request_labels_are_text(browser_page):
    page = browser_page
    page.set_content('<html><body><div id="detail"></div></body></html>')
    page.evaluate("""() => {
      window.MyAgentSettings={t:(zh,en)=>en,esc:value=>String(value).replace(/[&<>"']/g,
        c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))};
    }""")
    page.add_script_tag(content=(ROOT / 'app/templates/static/settings/usage_detail.js').read_text(encoding='utf-8'))
    page.evaluate("""() => {
      window.payload={sessions:[{session_id:'s1',runs:[{run_id:'r1',requests:[{
        react_iter:'<img id="injected">',model:'a&b',started_at:'2026-10-25T00:00:00Z',
        phases:{pre_api:{total_ms:10,events:{prepare:10}}},usage:{prompt_tokens:2,completion_tokens:3}
      }]}]}]};
      window.draw=()=>MyAgentUsageDetail.render(document.getElementById('detail'),payload,{sessionId:'s1'});
      window.cleanup=draw();
    }""")
    fold = page.locator('details[data-open-key="total|pre_api"]')
    fold.locator('summary').click()
    assert fold.evaluate('node=>node.open')
    page.evaluate('() => {cleanup();cleanup=draw();}')
    assert fold.evaluate('node=>node.open')
    page.locator('[data-ud="scope"]').select_option('r1|<img id="injected">')
    assert page.locator('#injected').count() == 0
    assert 'a&b' in page.locator('#detail').inner_text()


def test_deleted_session_pages_release_without_disturbing_other_sessions(details_page):
    page, _calls, errors, _rows = details_page
    page.evaluate("MyAgentDock.openPluginPage('demo')")
    plugin_frame(page)
    page.evaluate("MyAgentDock.openSession('s2');MyAgentDock.openPluginPage('demo')")
    second = plugin_frame(page, 's2').evaluate('window.instance')
    page.evaluate("dockRightPageHost.releaseSession('s1');dockForgetSession('s1')")
    assert page.evaluate("[...dockRightPageHost.records.values()].every(r=>r.surfaceId!=='s1')")
    assert page.evaluate("!dockSurfaceExists('s1',DOCK_RIGHT_AREA)")
    assert plugin_frame(page, 's2').evaluate('window.instance') == second
    assert not errors, [str(error) for error in errors]


def test_workspace_metadata_cache_evicts_old_entries_and_keeps_recent_hits(browser_page):
    page = browser_page
    page.add_script_tag(content=(ROOT / 'frontend/src/app/modules/workspace-media.js').read_text(encoding='utf-8'))
    result = page.evaluate("""() => {
      for(let i=0;i<2048;i++)workspaceImageMetadataCache.set('image-'+i,{width:i});
      workspaceImageMetadataCache.get('image-0');
      workspaceImageMetadataCache.set('new',{width:10});
      return {size:workspaceImageMetadataCache.size,recent:workspaceImageMetadataCache.has('image-0'),
        oldest:workspaceImageMetadataCache.has('image-1')};
    }""")
    assert result == {'size': 2048, 'recent': True, 'oldest': False}
