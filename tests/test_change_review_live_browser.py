"""Exercise live SSE -> actual execution renderer -> actual public sidebar."""
from pathlib import Path

import pytest

from tests.test_llm_stream_full_text_browser import browser_page, function_source, page as rendering_page

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def live_review_page(rendering_page):
    page = rendering_page
    errors = []
    def on_error(error):
        errors.append(str(error))
    page.on('pageerror', on_error)
    page.evaluate('''() => {
      const stream=ctx.stream;stream.id='chat-stream';stream.className='chat-stream';
      stream.dataset.sessionId=currentSessionId;
      const stage=document.createElement('div');stage.className='chat-stage';
      const panel=document.createElement('div');panel.className='panel-inner';
      stream.before(stage);stage.append(panel);panel.append(stream);
      stream.insertAdjacentHTML('afterbegin','<div class="msg-wrap--user" data-event-index="0">Question</div>');
      panel.insertAdjacentHTML('beforeend','<div class="composer-row"></div>');
      document.body.insertAdjacentHTML('afterbegin','<div id="sessions-list"><div class="session-item active" data-session-id="full-text"></div></div>');
      stage.insertAdjacentHTML('beforeend','<div id="chat-todo-plan" class="is-open"><div class="pubar-tabs"></div><div class="pubar-panes"></div></div>');
      window.sessionStore={shouldAcceptSseEvent:()=>true};
      window.consumeExtensionControlEvent=()=>false;
      window.readSseChunkWithIdleTimeout=reader=>reader.read();
      window.SSE_IDLE_TIMEOUT_MS=1000;
      window.refreshAggregateStatsSmart=()=>{};
      window.scheduleFinalVisibleAfterRunIfEnabled=()=>{};
    }''')
    sse = (ROOT / 'frontend/src/app/modules/sse-handling.js').read_text(encoding='utf-8')
    page.add_script_tag(content='\n'.join(function_source(sse, name) for name in (
        'shouldApplySseSeqFilter', 'sseSequenceScope', 'shouldSkipRecoveredEphemeralEvent',
        'consumeAgentSseResponseInner')))
    page.add_script_tag(content=(ROOT / 'frontend/src/app/modules/public-sidebar.js').read_text(encoding='utf-8'))
    page.add_style_tag(content=(ROOT / 'plugins/change-review/web/change-review.css').read_text(encoding='utf-8'))
    page.add_style_tag(content='.panel-inner{height:600px;overflow:auto}#chat-todo-plan{position:static;width:300px;opacity:1;transform:none}[hidden]{display:none!important}')
    source = (ROOT / 'plugins/change-review/web/change-review.js').read_text(encoding='utf-8')
    page.evaluate('''async source=>{
      window.applicationSessionId='full-text';
      window.MyAgentDock={sessionId:()=>applicationSessionId,
        surfaceKey:id=>id==='child-session'?'full-text':id};
      const url=URL.createObjectURL(new Blob([source],{type:'text/javascript'}));
      window.cleanupReview=await (await import(url)).installChatExtension({});
      // Production keeps currentSessionId inside the shared Function scope, not on window.
      window.currentSessionId=undefined;
      window.deliver=async events=>{
        const bytes=new TextEncoder().encode(events.map(event=>'data: '+JSON.stringify(event)+'\\n\\n').join(''));
        const response=new Response(new ReadableStream({start(controller){controller.enqueue(bytes);controller.close()}}),
          {headers:{'Content-Type':'text/event-stream'}});
        await consumeAgentSseResponseInner(response,ctx,applicationSessionId,1);
        await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
      };
    }''', source)
    yield page
    page.evaluate('cleanupReview()')
    page.remove_listener('pageerror', on_error)
    assert not errors, errors


def frame(seq, **fields):
    return {'type': 'execution_update', 'ephemeral': True, 'runtime_seq': seq, 'run_id': 'run-1',
            'update': {'execution_id': 'live-tool', 'kind': 'tool', 'tool_call_id': 'call-1',
                       'run_id': 'run-1', 'react_iter': 1, 'stream_seq': 1, **fields}}


def changed(revision=1):
    return {'path': 'src/live.py', 'snapshot_id': 'live-change', 'turn_id': 'turn-1',
            'revision': revision, 'added': revision * 3, 'removed': 1, 'diff': '-old\n+new'}


def test_live_completed_tool_opens_sidebar_without_refresh(live_review_page):
    page = live_review_page
    page.evaluate('events=>deliver(events)', [frame(1, status='generating', tool='write_file', arguments_raw='{}')])
    assert page.locator('[data-pubar-pane="changes"]').is_hidden()
    page.evaluate('events=>deliver(events)', [frame(2, status='completed', tool='write_file', args={}, result='ok',
                                                  ui_committed=True, ui={'changes': [changed()]})])
    assert page.locator('[data-pubar-pane="changes"]').is_visible()
    assert '+3' in page.locator('.change-review-card .change-review-summary').inner_text()
    page.evaluate('events=>deliver(events)', [frame(3, status='completed', ui={'changes': [changed(2)]})])
    assert '+6' in page.locator('.change-review-card .change-review-summary').inner_text()


def test_live_review_survives_active_sidebar_row_being_filtered_out(live_review_page):
    page = live_review_page
    # Collapsed/filtered session groups can omit the active row while its stream stays mounted.
    page.evaluate('document.querySelector("#sessions-list").replaceChildren()')
    page.evaluate('events=>deliver(events)', [frame(1, status='completed', tool='write_file', args={}, result='ok',
                                                  ui_committed=True, ui={'changes': [changed()]})])
    assert page.locator('[data-pubar-pane="changes"]').is_visible()


def test_live_review_uses_stream_owner_when_dock_api_is_unavailable(live_review_page):
    page = live_review_page
    page.evaluate('''() => {
      delete window.MyAgentDock;
      document.getElementById('sessions-list').replaceChildren();
    }''')
    page.evaluate('events=>deliver(events)', [frame(1, status='completed', tool='write_file', args={}, result='ok',
                                                  ui_committed=True, ui={'changes': [changed()]})])
    assert page.locator('[data-pubar-pane="changes"]').is_visible()


def test_live_review_follows_canonical_session_change_before_sidebar_rerenders(live_review_page):
    page = live_review_page
    page.evaluate('events=>deliver(events)', [frame(1, status='completed', tool='write_file', args={}, result='ok',
                                                  ui_committed=True, ui={'changes': [changed()]})])
    assert page.locator('[data-pubar-pane="changes"]').is_visible()
    page.evaluate('''async () => {
      applicationSessionId='second';
      document.dispatchEvent(new CustomEvent('myagent:session-change',{detail:{sessionId:'second'}}));
      ctx.stream.dataset.sessionId='second';
      const group=document.createElement('div');group.className='process-aggregate';
      group.innerHTML='<div id="body" class="process-aggregate-body"></div>';
      ctx.currentProcessGroup.replaceWith(group);ctx.currentProcessGroup=group;
      await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
    }''')
    assert page.locator('[data-pubar-pane="changes"]').is_hidden()
    second = frame(2, status='completed', tool='write_file', args={}, result='ok', ui_committed=True,
                   ui={'changes': [{**changed(2), 'path': 'second.py', 'snapshot_id': 'second'}]})
    second['update']['execution_id'] = 'second-execution'
    page.evaluate('events=>deliver(events)', [second])
    assert page.locator('[data-pubar-pane="changes"]').is_visible()
    assert page.locator('.change-review-card .change-review-file').count() == 1
    assert 'second.py' in page.locator('.change-review-card').inner_text()
    assert 'src/live.py' not in page.locator('.change-review-card').inner_text()


def test_live_review_clears_on_draft_session_without_waiting_for_sidebar(live_review_page):
    page = live_review_page
    page.evaluate('events=>deliver(events)', [frame(1, status='completed', tool='write_file', args={}, result='ok',
                                                  ui_committed=True, ui={'changes': [changed()]})])
    page.evaluate('''async () => {
      applicationSessionId=null;
      document.dispatchEvent(new CustomEvent('myagent:session-change',{detail:{sessionId:null}}));
      await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
    }''')
    assert page.locator('[data-pubar-pane="changes"]').is_hidden()
