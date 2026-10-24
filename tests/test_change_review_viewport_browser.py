"""Narrow review entries must not move their own viewport selection boundary."""
from pathlib import Path

import pytest

from tests.test_llm_stream_full_text_browser import browser_page

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def viewport_page(browser_page):
    page = browser_page.context.browser.new_page(viewport={'width': 700, 'height': 800})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.set_content('''<html lang="zh"><body>
      <main id="fixture">
        <div class="chat-stage">
          <aside id="chat-todo-plan"><div class="pubar-tabs"></div><div class="pubar-panes"></div></aside>
          <div id="chat-container" class="chat-container">
            <div id="chat-stream" class="chat-stream" data-session-id="session">
              <div class="msg-wrap--user" data-event-index="0">First question</div>
              <div class="process-aggregate" id="first"></div>
              <div class="msg-wrap--user" data-event-index="10">Second question</div>
              <div class="process-aggregate" id="second"></div>
            </div>
          </div>
        </div>
        <div class="panel"><div class="panel-inner">
          <div class="pubar-narrow-slot">
            <div id="pubar-narrow-strip" class="pubar-narrow-strip" hidden></div>
            <div id="pubar-narrow-popover" class="pubar-narrow-popover" hidden>
              <div class="pnp-title"></div><div class="pnp-body"></div>
            </div>
          </div>
          <div class="composer-row">Composer</div>
        </div></div>
      </main></body></html>''')
    for path in ['frontend/src/styles/app.css', 'plugins/change-review/web/change-review.css']:
        page.add_style_tag(content=(ROOT / path).read_text(encoding='utf-8'))
    page.add_style_tag(content='''
      #fixture {height:650px;width:420px;display:flex;flex-direction:column}
      #fixture .panel {flex:none;padding:0;width:100%;max-width:none}
      #fixture .panel-inner {width:100%;max-width:none}
      #fixture .composer-row {height:60px;flex:none}
      #chat-stream {padding:0;gap:0;display:block}
      #chat-container {scroll-behavior:auto}
      #chat-stream .msg-wrap--user {height:32px;margin:0;padding:0}
      #chat-stream .process-aggregate {height:500px;margin:0;padding:0}
      #chat-todo-plan {display:none}
      [hidden] {display:none!important}
    ''')
    page.evaluate("window.MyAgentDock={sessionId:()=> 'session'}")
    page.add_script_tag(content=(ROOT / 'frontend/src/app/modules/public-sidebar.js').read_text(encoding='utf-8'))
    page.evaluate('''async source=>{
      const url=URL.createObjectURL(new Blob([source],{type:'text/javascript'}));
      window.cleanupReview=await (await import(url)).installChatExtension({});
      window.recordChange=(id,index)=>{
        const aggregate=document.getElementById(id);
        const row=document.createElement('div');row.className='feed-item feed--tool';
        row._toolCallEvent={type:'tool_result',ui:{changes:[{path:id+'.py',snapshot_id:id,
          added:3,removed:1,diff:'-old\\n+new'}]}};
        aggregate.append(row);
        document.dispatchEvent(new CustomEvent('myagent:tool-call-rendered',{detail:{
          sessionId:'session',rootSessionId:'session',eventIndex:index,
          event:row._toolCallEvent,aggregate,row}}));
      };
      window.frames=async(count=12)=>{
        const samples=[];
        for(let i=0;i<count;i++){
          await new Promise(requestAnimationFrame);
          samples.push({visible:!document.getElementById('pubar-narrow-strip').hidden,
            top:document.getElementById('chat-container').scrollTop,
            height:document.getElementById('chat-container').clientHeight});
        }
        return samples;
      };
    }''', (ROOT / 'plugins/change-review/web/change-review.js').read_text(encoding='utf-8'))
    yield page
    page.evaluate('cleanupReview()')
    page.close()
    assert not errors, errors


@pytest.mark.parametrize('other_pane', [False, True])
def test_narrow_review_does_not_oscillate_at_turn_boundary(viewport_page, other_pane):
    page = viewport_page
    if other_pane:
        page.evaluate('''() => {
          const pane=MyAgentPubar.registerPane({id:'plan',label:'Plan',order:10});
          pane.setNarrow({label:'Plan',summary:'An independent status'});pane.setVisible(true);
        }''')
    page.evaluate('''async () => {
      recordChange('second',11);
      const scroller=document.getElementById('chat-container');
      scroller.scrollTop=scroller.scrollHeight;
      await frames();
    }''')
    # Scrolling up puts the next question just below the current viewport centre.
    # Hiding the review grows the viewport and used to select the next turn again.
    samples = page.evaluate('''async () => {
      const scroller=document.getElementById('chat-container');
      const next=document.querySelector('[data-event-index="10"]');
      scroller.scrollTop+=next.getBoundingClientRect().top
        -(scroller.getBoundingClientRect().top+scroller.clientHeight/2+4);
      return frames(24);
    }''')
    assert len({sample['height'] for sample in samples[5:]}) == 1, samples
    assert len({sample['top'] for sample in samples[5:]}) == 1, samples
    # Continuing up must reach the first, unchanged turn and hide its empty review.
    page.evaluate('document.getElementById("chat-container").scrollTop=0')
    page.locator('[data-pubar-narrow-item="changes"]').wait_for(state='hidden')
    page.evaluate('''() => {
      const scroller=document.getElementById('chat-container');scroller.scrollTop=scroller.scrollHeight;
    }''')
    page.locator('[data-pubar-narrow-item="changes"]').wait_for(state='visible')


def test_narrow_review_does_not_oscillate_at_historical_process_edge(viewport_page):
    page = viewport_page
    samples = page.evaluate('''async () => {
      const spacer=document.createElement('div');spacer.style.height='700px';
      document.getElementById('first').before(spacer);
      recordChange('first',1);
      const scroller=document.getElementById('chat-container');
      scroller.scrollTop=scroller.scrollHeight;
      await frames();
      scroller.scrollTop+=document.getElementById('first').getBoundingClientRect().top
        -scroller.getBoundingClientRect().bottom+4;
      return frames(24);
    }''')
    assert len({sample['height'] for sample in samples[5:]}) == 1, samples
    assert all(sample['visible'] for sample in samples[5:]), samples
    page.locator('[data-pubar-narrow-item="changes"]').wait_for(state='visible')
    # A stationary reader must not cause repeated DOM replacement/recomposition.
    result = page.evaluate('''async () => {
      const strip=document.getElementById('pubar-narrow-strip');
      const item=strip.firstElementChild;let mutations=0;
      const observer=new MutationObserver(records=>mutations+=records.length);
      observer.observe(strip,{attributes:true,subtree:true,childList:true,characterData:true});
      await frames(24);observer.disconnect();
      return {mutations,same:item===strip.firstElementChild};
    }''')
    assert result == {'mutations': 0, 'same': True}


def test_review_stays_stable_after_wide_narrow_transition(viewport_page):
    page = viewport_page
    page.evaluate('''async () => {
      recordChange('second',11);
      const scroller=document.getElementById('chat-container');
      scroller.scrollTop=scroller.scrollHeight;await frames();
      const next=document.querySelector('[data-event-index="10"]');
      scroller.scrollTop+=next.getBoundingClientRect().top
        -(scroller.getBoundingClientRect().top+scroller.clientHeight/2+4);
      await frames();
    }''')
    for wide in [True, False, True, False]:
        samples = page.evaluate('''async wide => {
          document.getElementById('chat-todo-plan').classList.toggle('is-open',wide);
          return frames(20);
        }''', wide)
        assert len({sample['height'] for sample in samples[5:]}) == 1, samples
        assert len({sample['top'] for sample in samples[5:]}) == 1, samples
        if wide:
            assert not any(sample['visible'] for sample in samples[5:]), samples
