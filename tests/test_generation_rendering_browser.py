"""Streaming work bounds and ordering using the actual execution renderer."""
import os
import re
from pathlib import Path

import pytest

playwright = pytest.importorskip('playwright.sync_api')
ROOT = Path(__file__).resolve().parents[1]


def function(source, name):
    return re.search(r'^(?:async )?function ' + name + r'\([\s\S]*?^}', source, re.M).group(0)


@pytest.fixture(scope='module')
def browser():
    with playwright.sync_playwright() as runtime:
        browser = runtime.chromium.launch(headless=True, **({'channel': 'msedge'} if os.name == 'nt' else {}))
        yield browser
        browser.close()


@pytest.fixture
def page(browser):
    page = browser.new_page()
    install_runtime(page)
    yield page
    page.close()


def install_runtime(page, rendering=None):
    rendering = rendering or (ROOT / 'frontend/src/app/modules/message-rendering.js').read_text(encoding='utf-8')
    interactions = (ROOT / 'frontend/src/app/modules/human-interactions.js').read_text(encoding='utf-8')
    page.set_content('<style>.session-offscreen-buffers{position:absolute;left:-9999px;width:1px;height:1px;overflow:hidden}</style>'
                     '<div id="visible"><div class="chat-stream" id="stream"></div></div>'
                     '<div id="offscreen" class="session-offscreen-buffers"></div>')
    page.add_script_tag(content='''
      var replayingMessages=false, currentSessionId='session', stats=0, follows=0;
      function reactGenerationForContext(ctx){return ctx.reactGeneration||0;}
      function discardPendingToolRowRender(){}
      function removeTemporaryStatus(){}
      function refreshFeedChunkOverflow(){}
      function refreshAggregateStatsSmart(){stats++;}
      function refreshProcessAggregateStats(){}
      function unregisterProcessAggregateRow(){}
      function registerProcessAggregateRow(){}
      function trimSurroundingBlankLines(text){return text.trim();}
      function rememberToolStreamRow(){}
      function findToolCallRow(ctx,id){return ctx.stream.querySelector('[data-tool-call-id="'+CSS.escape(id)+'"].feed-item');}
      function setUiRuntimeText(el,text){if(el.textContent!==text)el.textContent=text;}
      function formatToolDraftLine(name,args){return name+'('+args+')';}
      function writeToolCallLlmText(el,name,args){el.textContent=formatToolDraftLine(name,args);}
      function formatToolPendingLine(name,args,text){return text;}
      function isSmoothStreamActive(){return false;}
      function scrollContentAreaIfFollow(){follows++;}
      function getFeedItemText(row){return row.querySelector('.feed-chunk-scroller').textContent;}
      function createProcessFeedRow(ctx,type,text,options,sid,toolId){
        var group=ctx.currentProcessGroup;
        if(!group || !ctx.stream.contains(group)){
          group=document.createElement('div');group.className='process-aggregate';
          group.dataset.processGroupId=ctx.processGroupId||'turn:1';
          group.innerHTML='<div class="process-aggregate-body"></div>';
          ctx.stream.appendChild(group);ctx.currentProcessGroup=group;
        }
        var row=document.createElement('div');row.className='feed-item '+(type==='tool-call'?'feed--tool':'feed--llm');
        row.innerHTML='<div class="feed-chunk"><div class="feed-chunk-scroller"></div></div>';
        var sc=row.querySelector('.feed-chunk-scroller');sc.textContent=text;
        if(toolId)row.dataset.toolCallId=toolId;
        group.querySelector('.process-aggregate-body').appendChild(row);return sc;
      }
      function context(stream){return {stream:stream,llm:{},reactGeneration:0};}
      function deliver(ctx,id,seq,fields,opts){
        renderExecutionRecord(ctx,updateExecutionRecord('session',Object.assign({execution_id:id,
          process_group_id:'turn:1',kind:'response',status:'generating',last_runtime_seq:seq},fields)),
          'session',Object.assign({smoothText:true},opts));
      }
    ''' + rendering[rendering.index('var executionRecordsBySession'):rendering.index('function ensureProcessGroup')])
    page.add_script_tag(content='\n'.join(function(interactions, name) for name in (
        'humanInteractionToolRow', 'humanInteractionToolSlot', 'attachHumanInteractionCardsForToolCall',
        'attachAllHumanInteractionCards', 'removeEmptyHumanInteractionFallbackSlots')))
    page.evaluate("window.ctx=context(document.getElementById('stream'))")


def test_group_index_tracks_synchronous_structure_metadata_and_duplicate_boundaries(page):
    result = page.evaluate('''() => {
      const stream=ctx.stream;
      function group(id,run){const g=document.createElement('div');g.className='process-aggregate';
        g.dataset.processGroupId=id;g.dataset.processRunId=run;stream.appendChild(g);return g;}
      const first=group('turn:1','r'),last=group('turn:2','r');
      let scans=0;const query=stream.querySelectorAll.bind(stream);
      stream.querySelectorAll=s=>{if(s==='.process-aggregate')scans++;return query(s);};
      for(let i=0;i<1000;i++){
        first.classList.add('is-running');first.textContent='token '+i;
        if(findExecutionProcessGroup(stream,'turn:1','')!==first)throw Error('wrong group');
      }
      const stableScans=scans;
      const byRun=findExecutionProcessGroup(stream,'','r')===last;
      last.dataset.procEndedAt='123';
      const ended=findExecutionProcessGroup(stream,'','r')===first;
      const duplicate=group('turn:1','next');
      const newest=findExecutionProcessGroup(stream,'turn:1','')===duplicate;
      stream.insertBefore(duplicate,first);
      const prepended=findExecutionProcessGroup(stream,'turn:1','')===first;
      first.dataset.processGroupId='renamed';
      const renamed=findExecutionProcessGroup(stream,'renamed','')===first;
      first.classList.remove('process-aggregate');
      const removedClass=findExecutionProcessGroup(stream,'renamed','')===null;
      first.classList.add('process-aggregate');
      const addedClass=findExecutionProcessGroup(stream,'renamed','')===first;
      const replacement=first.cloneNode(true);first.replaceWith(replacement);
      const replaced=findExecutionProcessGroup(stream,'renamed','')===replacement;
      stream.textContent='';
      const cleared=findExecutionProcessGroup(stream,'turn:1','')===null;
      return {stableScans,byRun,ended,newest,prepended,renamed,removedClass,addedClass,replaced,cleared};
    }''')
    assert result == dict(stableScans=1, **{key: True for key in (
        'byRun','ended','newest','prepended','renamed','removedClass','addedClass','replaced','cleared')})


@pytest.mark.parametrize('kind', ['response', 'reasoning', 'tool'])
def test_background_deltas_coalesce_and_terminal_state_flushes_in_order(page, kind):
    result = page.evaluate('''kind => {
      ctx.stream.classList.add('is-offscreen');
      const fields={kind,tool_call_id:kind==='tool'?'tool':'',tool:'read',arguments_raw:'{}',content:'first'};
      deliver(ctx,'draft',1,fields);
      const row=ctx.stream.querySelector('.feed-item'),sc=row.querySelector('.feed-chunk-scroller');
      const initial=sc.textContent;stats=0;
      for(let i=2;i<=101;i++)deliver(ctx,'draft',i,Object.assign({},fields,{content:'delta '+i,arguments_raw:'args '+i}));
      const before={text:sc.textContent,stats,records:executionRecordsBySession.get('session').get('draft').last_runtime_seq};
      deliver(ctx,'draft',102,Object.assign({},fields,{status:'completed',content:'final',arguments_raw:'final args'}));
      const state=pendingExecutionRendersByStream.has(ctx.stream);
      return {initial,before,stats,state,status:row.dataset.executionStatus,seq:row.dataset.executionRenderedSeq,
        finalText:sc.textContent,rows:ctx.stream.querySelectorAll('.feed-item').length};
    }''', kind)
    assert result['before'] == {'text': result['initial'], 'stats': 0, 'records': 101}
    assert result['stats'] == 2 and result['state'] is False
    assert result['status'] == 'completed' and result['seq'] == '102' and result['rows'] == 1
    assert ('final args' if kind == 'tool' else 'final') in result['finalText']


@pytest.mark.parametrize('reused_node', [False, True])
def test_background_timer_restoration_and_eviction_do_not_lose_or_recreate_rows(page, reused_node):
    result = page.evaluate('''async reused => {
      ctx.stream.classList.add('is-offscreen');
      deliver(ctx,'a',1,{content:'first'});deliver(ctx,'a',2,{content:'timer latest'});
      await new Promise(resolve=>setTimeout(resolve,300));
      const timerLatest=ctx.stream.querySelector('.feed-chunk-scroller').textContent==='timer latest';
      deliver(ctx,'a',3,{content:'switch latest'});
      ctx.stream.classList.remove('is-offscreen');flushPendingExecutionRenders(ctx.stream);
      const switchLatest=ctx.stream.querySelector('.feed-chunk-scroller').textContent==='switch latest';
      ctx.stream.classList.add('is-offscreen');deliver(ctx,'a',4,{content:'obsolete'});
      if(reused)ctx.stream.querySelector('.feed-item').dataset.executionId='different execution';
      else ctx.stream.textContent='';
      flushPendingExecutionRenders(ctx.stream);
      const safe=reused?ctx.stream.querySelector('.feed-chunk-scroller').textContent==='switch latest':ctx.stream.children.length===0;
      return {timerLatest,switchLatest,safe,pending:pendingExecutionRendersByStream.has(ctx.stream)};
    }''', reused_node)
    assert result == dict(timerLatest=True, switchLatest=True, safe=True, pending=False)


def test_new_rows_snapshots_and_visible_deltas_are_immediate(page):
    result = page.evaluate('''() => {
      deliver(ctx,'visible',1,{content:'visible'});deliver(ctx,'visible',2,{content:'visible latest'});
      const visible=ctx.stream.querySelector('.feed-chunk-scroller').textContent==='visible latest';
      ctx.stream.classList.add('is-offscreen');
      deliver(ctx,'visible',3,{content:'queued'});
      deliver(ctx,'new',4,{content:'new row'});
      const order=Array.from(ctx.stream.querySelectorAll('.feed-chunk-scroller')).map(sc=>sc.textContent);
      deliver(ctx,'new',5,{content:'snapshot'},{snapshot:true});
      return {visible,order,last:ctx.stream.querySelectorAll('.feed-chunk-scroller')[1].textContent,
        pending:pendingExecutionRendersByStream.has(ctx.stream)};
    }''')
    assert result == dict(visible=True, order=['queued','new row'], last='snapshot', pending=False)


def test_background_tool_output_coalesces_without_delaying_start_or_failure(page):
    result = page.evaluate('''() => {
      ctx.stream.classList.add('is-offscreen');
      deliver(ctx,'tool',1,{kind:'tool',tool:'shell',tool_call_id:'call',status:'waiting_execution'});
      function output(seq,text){renderExecutionEvent(ctx,{type:'tool_command_delta',execution_id:'tool',
        execution_runtime_seq:seq,process_group_id:'turn:1',tool_call_id:'call',delta:text},'session');}
      output(2,'started');
      const row=ctx.stream.querySelector('.feed-item');
      const startedImmediately=row.dataset.executionStatus==='running'
        &&row.querySelector('.feed-chunk-scroller').textContent.includes('started');
      stats=0;
      for(let i=3;i<103;i++)output(i,' line'+i);
      const deferred=stats===0;
      renderExecutionEvent(ctx,{type:'tool_execution_state',execution_id:'tool',execution_runtime_seq:103,
        process_group_id:'turn:1',tool_call_id:'call',status:'failed'},'session');
      return {startedImmediately,deferred,stats,status:row.dataset.executionStatus,
        complete:row.querySelector('.feed-chunk-scroller').textContent.includes('line102'),
        pending:pendingExecutionRendersByStream.has(ctx.stream)};
    }''')
    assert result == dict(startedImmediately=True, deferred=True, stats=2, status='failed', complete=True, pending=False)


def test_tool_cards_attach_before_and_after_row_creation_without_per_delta_scans(page):
    result = page.evaluate('''() => {
      const card=document.createElement('div');card.className='human-interaction-card';
      card.dataset.toolCallId='call';ctx.stream.appendChild(card);
      deliver(ctx,'tool',1,{kind:'tool',tool_call_id:'call',tool:'read',arguments_raw:'{}'});
      const row=ctx.stream.querySelector('.feed-item');
      const before=row.contains(card);
      let scans=0;const query=ctx.stream.querySelectorAll.bind(ctx.stream);
      ctx.stream.querySelectorAll=s=>{if(s.includes('human-interaction'))scans++;return query(s);};
      for(let i=2;i<102;i++)deliver(ctx,'tool',i,{kind:'tool',tool_call_id:'call',arguments_raw:'arg '+i});
      const hotScans=scans;
      const late=card.cloneNode();humanInteractionToolSlot(ctx.stream,'call',late.dataset).appendChild(late);
      const after=row.contains(late);
      const replacement=row.cloneNode(true);row.replaceWith(replacement);
      attachAllHumanInteractionCards(ctx.stream);
      return {before,after,hotScans,cards:replacement.querySelectorAll('.human-interaction-card').length};
    }''')
    assert result == dict(before=True, after=True, hotScans=0, cards=2)


def test_late_tool_identity_attaches_approval_without_waiting_for_background_timer(page):
    result = page.evaluate('''() => {
      ctx.stream.classList.add('is-offscreen');
      deliver(ctx,'tool',1,{kind:'tool',tool:'read',arguments_raw:'{}'});
      const card=document.createElement('div');card.className='human-interaction-card';
      card.dataset.toolCallId='late-call';ctx.stream.appendChild(card);
      deliver(ctx,'tool',2,{kind:'tool',tool_call_id:'late-call',arguments_raw:'args'});
      return {attached:ctx.stream.querySelector('.feed-item').contains(card),
        pending:pendingExecutionRendersByStream.has(ctx.stream)};
    }''')
    assert result == dict(attached=True, pending=False)


@pytest.mark.parametrize('running', [True, False])
def test_real_session_restore_flushes_pending_text_before_return(page, running):
    scrolling = (ROOT / 'frontend/src/app/modules/session-scroll-history.js').read_text(encoding='utf-8')
    page.add_script_tag(content='''
      var offscreenRoot=document.getElementById('offscreen'),chatContainer=document.getElementById('visible');
      function getSessionRunState(){return {ctx:ctx};}
      function isCompleteLocalRunStream(){return true;}
      function getVisibleChatStream(){return document.getElementById('chat-stream');}
      function cssEscapeIdent(value){return CSS.escape(value);}
      function cacheOrderTouch(){}
      function restoreHistoryPagingFromStream(){return null;}
      function updateHistorySentinelVisibility(){}
      function bindExistingLogs(){}
    ''' + '\n'.join(function(scrolling, name) for name in ('restoreStreamForRunningSession','restoreCachedSessionStream')))
    result = page.evaluate('''running => {
      ctx.stream.classList.add('is-offscreen');ctx.stream.dataset.cacheSessionId='session';
      offscreenRoot.appendChild(ctx.stream);
      ctx.stream.dataset.sessionLoadOk='1';
      deliver(ctx,'a',1,{content:'first'});deliver(ctx,'a',2,{content:'latest'});
      const restored=running?restoreStreamForRunningSession('session'):restoreCachedSessionStream('session');
      return {restored,text:ctx.stream.querySelector('.feed-chunk-scroller').textContent,
        visible:ctx.stream.parentNode===chatContainer&&!ctx.stream.classList.contains('is-offscreen'),
        pending:pendingExecutionRendersByStream.has(ctx.stream)};
    }''', running)
    assert result == dict(restored=True, text='latest', visible=True, pending=False)


@pytest.mark.parametrize('boundary', ['finalizeLlmStreamChunks','discardLlmStreamChunks'])
def test_stream_terminal_cleanup_cancels_pending_background_work(page, boundary):
    scrolling = (ROOT / 'frontend/src/app/modules/session-scroll-history.js').read_text(encoding='utf-8')
    page.add_script_tag(content='''
      function flushLlmDeltaText(){}
      function queryFeedChunksInCtx(){return [];}
      function scheduleFeedChunkOverflowRefresh(){}
    ''' + '\n'.join(function(scrolling, name) for name in ('finalizeLlmStreamChunks','discardLlmStreamChunks')))
    result = page.evaluate('''boundary => {
      ctx.stream.classList.add('is-offscreen');
      deliver(ctx,'a',1,{content:'first'});deliver(ctx,'a',2,{content:'received before stop'});
      window[boundary](ctx,{});
      return {text:ctx.stream.querySelector('.feed-chunk-scroller').textContent,
        pending:pendingExecutionRendersByStream.has(ctx.stream)};
    }''', boundary)
    assert result == dict(text='received before stop', pending=False)
