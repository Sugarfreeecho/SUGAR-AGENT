"""Full LLM and tool text survives streaming, folding and history recovery."""
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


@pytest.fixture(scope="module")
def browser_page():
    with playwright.sync_playwright() as runtime:
        try:
            browser = runtime.chromium.launch(
                headless=True, **({"channel": "msedge"} if os.name == "nt" else {})
            )
        except playwright.Error as error:
            pytest.skip(f"Local Chromium browser unavailable: {error}")
        page = browser.new_page(viewport={"width": 1100, "height": 800})
        yield page
        browser.close()


@pytest.fixture
def page(browser_page):
    rendering = (ROOT / "frontend/src/app/modules/message-rendering.js").read_text(encoding="utf-8")
    scrolling = (ROOT / "frontend/src/app/modules/session-scroll-history.js").read_text(encoding="utf-8")
    i18n = (ROOT / "frontend/src/app/modules/i18n.js").read_text(encoding="utf-8")
    css = (ROOT / "frontend/src/styles/app.css").read_text(encoding="utf-8")
    browser_page.set_content(
        f"<style>{css}</style><style>.fixture{{width:800px}}"
        "#oracle{position:absolute;left:-10000px}</style>"
        "<div id='stream'><div class='fixture process-aggregate' id='subject'>"
        "<div class='process-aggregate-body' id='body'></div></div></div>"
        "<div class='fixture process-aggregate' id='oracle'><div class='process-aggregate-body'>"
        "<div class='feed-item feed--llm'><div class='feed-row'>"
        "<div class='feed-chunk is-streaming'><div class='feed-chunk-scroller' id='full'></div>"
        "</div></div></div></div></div>"
    )
    setup = """
      var currentSessionId='full-text',replayingMessages=false;
      var LOG_TRUNCATE_HEAD_LINES=100,LOG_TRUNCATE_TAIL_LINES=100;
      var LOG_TRUNCATE_HEAD_CHARS=12000,LOG_TRUNCATE_TAIL_CHARS=12000;
      var executionRecordsBySession=new Map();
      var executionRowsByStream=new WeakMap();
      var uiI18nRuntimeOriginal=new WeakMap(),uiLanguage='zh';
      function translateUiString(text){return text.replace('生成中...', 'Generating...');}
      window.__MYAGENT_FEATURES__={smoothStream:true};
      function isSmoothStreamActive(){return false;}
      function stripWelcome(){}
      function getProcessBody(){return document.getElementById('body');}
      function getExistingProcessBody(){return document.getElementById('body');}
      function ensureProcessAggregateState(){return {maxReactIter:1};}
      function reactGenerationForContext(ctx){return ctx.reactGeneration || 0;}
      function insertReactOrderedFeedRow(body,row,type,iter){
        if(iter!=null)row.dataset.reactIter=String(iter);body.append(row);
      }
      function bindFeedChunkScrollChain(){}
      function animateSmoothTraceRowInsertion(){}
      function finishStreamScrollIfFollow(){}
      function registerProcessAggregateRow(){}
      function unregisterProcessAggregateRow(){}
      function refreshAggregateStatsSmart(){}
      function refreshFeedChunkOverflow(){}
      function scheduleFeedChunkOverflowRefresh(){}
      function scrollContentAreaIfFollow(){}
      function followStreamProcessScroll(){}
      function bumpAggregateMaxReactIter(){}
      function mutateSmoothTraceRowHeight(row,mutation){mutation();}
      function registerMermaidLazy(){}
      function renderDurableAttachmentImages(){}
      function splitThinkTagsForUi(text){return {content:text};}
      function selectExecutionProcessGroup(){}
      function removeTemporaryStatus(){}
      function getFeedItemText(el){return el.querySelector('.feed-chunk-scroller').textContent;}
      function queryFeedChunksInCtx(ctx,selector){return ctx.currentProcessGroup.querySelectorAll(selector);}
      window.ctx={stream:document.getElementById('stream'),
        currentProcessGroup:document.getElementById('subject'),llm:{},runId:'run-1'};
    """
    setup += rendering[rendering.index("const TRACE_ROW ="):rendering.index("const envKeepLines")]
    setup += "\n".join(function_source(rendering, name) for name in (
        "trimSurroundingBlankLines", "truncateLogTextForUi", "createProcessFeedRow", "appendLog",
        "feedRowCollapseAriaLabel", "syncFeedRowCollapseButton", "toggleCollapsibleFeedRow",
        "autoCollapseLlmReasoningRow", "handleTraceChunkClick", "handleToolRowChunkClick",
        "handleLlmRowChunkClick", "bindFeedChunkInteraction", "finalizeActiveLlmReasoningRow",
        "upsertLlmFeedRow", "findExistingLlmFeedRow", "removeDuplicateLlmFeedRows",
        "invalidateExecutionRowIndex", "executionRowIndexForStream", "findIndexedExecutionRow",
        "updateExecutionRecord", "renderExecutionRecord", "renderExecutionEvent",
        "formatToolDraftLine", "writeToolCallLlmText", "formatToolPendingLine",
        "toolCallDraftKey", "ensureToolStreamRenderState", "rememberToolStreamRow",
        "discardPendingToolRowRender", "findToolCallRow", "findToolDraftRow", "scheduleToolRowRender",
        "deltaDedupeKey", "hasSeenStreamDelta", "appendToolCallDelta", "appendToolPendingRow",
        "preferredToolPendingCommandPreview",
        "setToolRowText", "formatToolCommandLine", "formatToolDoneLine", "upsertToolCallResult",
        "autoCollapseToolRowAfterResult", "rootSessionIdForRenderedNode",
    ))
    setup += "\n".join(function_source(i18n, name) for name in ("setUiRuntimeText", "getUiRuntimeText"))
    setup += "\n".join(function_source(scrolling, name) for name in (
        "writeLlmStreamText", "appendLlmRevealedText", "flushLlmDeltaText", "resetLlmState",
        "finalizeLlmStreamChunks", "discardLlmStreamChunks",
        "cancelExecutionLlmReveal", "queueExecutionLlmReveal", "flushExecutionLlmReveals", "scheduleLlmDeltaFlush",
        "queueToolCallLlmReveal",
    ))
    setup += """
      window.start=(type='llm-reasoning',text='',options={streaming:true,reactIter:1})=>{
        document.getElementById('body').replaceChildren();
        window.sc=createProcessFeedRow(ctx,type,text,options,currentSessionId);
        const clone=sc.closest('.feed-item').cloneNode(true);
        document.querySelector('#oracle .process-aggregate-body').replaceChildren(clone);
        window.full=clone.querySelector('.feed-chunk-scroller');full.id='full';
        return sc;
      };
      start();
      window.write=text=>{writeLlmStreamText(sc,text,'reasoning');full.textContent=trimSurroundingBlankLines(text);};
      window.heights=()=>({actual:sc.getBoundingClientRect().height,expected:full.getBoundingClientRect().height});
    """
    browser_page.add_script_tag(content=setup)
    yield browser_page
    browser_page.goto("about:blank")


def assert_equal_height(page):
    values = page.evaluate("heights()")
    assert abs(values["actual"] - values["expected"]) < 1.5


@pytest.mark.parametrize("kind", ["reasoning", "response"])
def test_live_execution_reveals_by_frame_then_preserves_complete_body(page, kind):
    page.add_script_tag(content=(ROOT / "frontend/src/app/modules/smooth-stream.js").read_text(encoding="utf-8"))
    result = page.evaluate("""async kind => {
      body.replaceChildren();ctx.llm={};
      const text=('正文😀 '.repeat(30)+'\\n').repeat(350)+'END';
      const event={type:'llm_'+kind+'_delta',execution_id:'live-'+kind,
        run_id:'run-1',react_iter:1,execution_runtime_seq:1,delta:text};
      renderExecutionEvent(ctx,event,currentSessionId);
      const sc=body.querySelector('.feed-chunk-scroller');
      const before=sc.textContent.length;
      await new Promise(requestAnimationFrame);
      const first=sc.textContent.length,node=sc.firstChild;
      renderExecutionEvent(ctx,event,currentSessionId);
      renderExecutionEvent(ctx,{...event,delta:' appended',execution_runtime_seq:2},currentSessionId);
      const afterArrival=sc.textContent.length;
      await new Promise(requestAnimationFrame);
      const second=sc.textContent.length,sameNode=node===sc.firstChild;
      renderExecutionEvent(ctx,{type:'llm_'+kind,execution_id:'live-'+kind,
        run_id:'run-1',react_iter:1,execution_runtime_seq:3,content:text+' completed'},currentSessionId);
      finalizeLlmStreamChunks(ctx);
      await new Promise(requestAnimationFrame);
      return {before,first,second,afterArrival,total:text.length,sameNode,
        complete:sc.textContent===text+' completed',rows:body.children.length,
        pending:ctx.llm.llmExecutionReveals.size,raf:ctx.llm.llmDeltaFlushRaf,
        childElements:sc.children.length};
    }""", kind)
    assert result["before"] == 0
    assert 0 < result["first"] < result["total"]
    assert result["first"] < result["second"] <= result["total"] + len(" appended")
    assert result["afterArrival"] == result["first"]
    assert result["sameNode"] and result["complete"]
    assert result["rows"] == 1 and result["childElements"] == 0
    assert result["pending"] == 0 and result["raf"] == 0


@pytest.mark.parametrize("route", ["execution", "legacy"])
def test_tool_model_fields_reveal_and_stop_when_execution_begins(page, route):
    page.add_script_tag(content=(ROOT / "frontend/src/app/modules/smooth-stream.js").read_text(encoding="utf-8"))
    result = page.evaluate("""async route => {
      body.replaceChildren();ctx.llm={};ctx._toolStreamRenderState=null;
      const args='{"content":"'+'工具😀'.repeat(500),name='write_file';
      const event={type:'tool_call_delta',execution_id:route==='execution'?'tool-live':undefined,
        id:'tool-call',name_delta:name,arguments_delta:args,run_id:'run-1',react_iter:1,
        execution_runtime_seq:1,delta_seq:1};
      const deliver=e=>route==='execution'?renderExecutionEvent(ctx,e,currentSessionId):appendToolCallDelta(ctx,e,currentSessionId);
      deliver(event);const sc=body.querySelector('.feed-chunk-scroller');
      const before=sc._llmToolArgs||'';
      await new Promise(requestAnimationFrame);
      const first=sc._llmToolArgs.length,node=sc.firstChild;
      deliver({...event,name_delta:'',arguments_delta:' tail',execution_runtime_seq:2,delta_seq:2});
      const afterArrival=sc._llmToolArgs.length;
      await new Promise(requestAnimationFrame);
      const sameNode=node===sc.firstChild,second=sc._llmToolArgs.length;
      uiLanguage='en';
      writeToolCallLlmText(sc,sc._llmToolName,sc._llmToolArgs);
      const localized=sc.textContent.endsWith('Generating...');uiLanguage='zh';
      const pending={type:'tool_pending',execution_id:event.execution_id,execution_runtime_seq:3,
        tool:name,tool_call_id:'tool-call',react_iter:1,run_id:'run-1',
        command_preview:'write_file(path="a.txt")',args:{path:'a.txt'}};
      if(route==='execution')renderExecutionEvent(ctx,pending,currentSessionId);
      else appendToolPendingRow(ctx,pending,currentSessionId);
      const executed=sc.textContent;
      await new Promise(requestAnimationFrame);
      return {before,first,afterArrival,second,total:args.length,sameNode,localized,
        executionImmediate:executed==='write_file(path="a.txt")\\n执行中...',
        runtimeSourceKept:getUiRuntimeText(sc)===executed,
        executionKept:sc.textContent===executed,pending:ctx.llm.llmExecutionReveals.size,
        raf:ctx.llm.llmDeltaFlushRaf,rows:body.children.length};
    }""", route)
    assert result["before"] == ""
    assert 0 < result["first"] < result["total"]
    assert result["afterArrival"] == result["first"]
    assert result["first"] < result["second"] <= result["total"] + len(" tail")
    assert result["sameNode"] and result["localized"]
    assert result["executionImmediate"] and result["executionKept"] and result["runtimeSourceKept"]
    assert result["pending"] == 0 and result["raf"] == 0 and result["rows"] == 1


@pytest.mark.parametrize("kind", ["reasoning", "response"])
@pytest.mark.parametrize("smooth", [False, True])
def test_execution_blank_lines_stay_trimmed_through_completion_and_next_reply(page, kind, smooth):
    page.add_script_tag(content=(ROOT / "frontend/src/app/modules/smooth-stream.js").read_text(encoding="utf-8"))
    result = page.evaluate("""async ({kind,smooth}) => {
      body.replaceChildren();ctx.llm={};window.__MYAGENT_FEATURES__.smoothStream=smooth;
      const expected='  第一行正文\\n\\n第二行正文',prefix='\\n \\t\\n',tail='\\n \\t\\n';
      const event={type:'llm_'+kind+'_delta',execution_id:'blank-lines-'+kind,
        run_id:'run-1',react_iter:1,execution_runtime_seq:1,delta:prefix+expected};
      const samples=[];
      const sample=()=>{
        // Compare the complete body even when reasoning automatically folds.
        sc.closest('.feed-item').classList.remove('is-collapsed');
        samples.push({text:sc.textContent,height:sc.getBoundingClientRect().height});
      };
      renderExecutionEvent(ctx,event,currentSessionId);flushLlmDeltaText(ctx);
      const sc=body.querySelector('.feed-chunk-scroller');sample();
      const node=sc.firstChild;
      renderExecutionEvent(ctx,{...event,delta:tail,execution_runtime_seq:2},currentSessionId);
      flushLlmDeltaText(ctx);sample();
      const raw=prefix+expected+tail;
      renderExecutionEvent(ctx,{type:'llm_'+kind,execution_id:event.execution_id,
        run_id:'run-1',react_iter:1,execution_runtime_seq:3,content:raw},currentSessionId);
      sample();
      await new Promise(requestAnimationFrame);sample();
      const rawPreserved=sc._llmRawText===raw
        && executionRecordsBySession.get(currentSessionId).get(event.execution_id).content===raw;
      finalizeLlmStreamChunks(ctx);sample();
      renderExecutionEvent(ctx,{...event,execution_id:'next-'+kind,react_iter:2,
        execution_runtime_seq:4,delta:'下一条回复'},currentSessionId);
      flushLlmDeltaText(ctx);sample();
      return {expected,samples,rawPreserved,sameNode:node===sc.firstChild};
    }""", {"kind": kind, "smooth": smooth})
    assert [sample["text"] for sample in result["samples"]] == [result["expected"]] * 6
    heights = [sample["height"] for sample in result["samples"]]
    assert max(heights) - min(heights) < 1.5
    assert result["rawPreserved"]
    if smooth:
        assert result["sameNode"]


@pytest.mark.parametrize("kind", ["reasoning", "response"])
@pytest.mark.parametrize("recovery", ["snapshot", "history"])
def test_execution_recovery_trims_blank_lines_without_losing_later_line_breaks(page, kind, recovery):
    result = page.evaluate("""({kind,recovery}) => {
      body.replaceChildren();ctx.llm={};replayingMessages=recovery==='history';
      const expected='  恢复的正文\\n\\n保留段落',raw='\\n \\t\\n'+expected+'\\n \\t\\n';
      const id='recovery-'+kind;
      const record=updateExecutionRecord(currentSessionId,{execution_id:id,kind,
        run_id:'run-1',react_iter:1,status:'generating',content:raw,last_runtime_seq:1});
      renderExecutionRecord(ctx,record,currentSessionId,{snapshot:recovery==='snapshot'});
      const sc=body.querySelector('.feed-chunk-scroller'),recovered=sc.textContent;
      replayingMessages=false;
      renderExecutionEvent(ctx,{type:'llm_'+kind+'_delta',execution_id:id,
        run_id:'run-1',react_iter:1,execution_runtime_seq:2,delta:'后续正文'},currentSessionId);
      flushLlmDeltaText(ctx);
      return {expected,recovered,continued:sc.textContent,
        rawPreserved:sc._llmRawText===raw+'后续正文'};
    }""", {"kind": kind, "recovery": recovery})
    assert result["recovered"] == result["expected"]
    assert result["continued"] == result["expected"] + "\n \t\n后续正文"
    assert result["rawPreserved"]


@pytest.mark.parametrize("kind", ["llm-reasoning", "llm-response"])
@pytest.mark.parametrize("shape", ["single", "multi"])
def test_stream_keeps_middle_and_grows_with_full_text(page, kind, shape):
    result = page.evaluate("""({kind,shape}) => {
      start(kind);
      const unit=shape==='single'?'正文😀 '.repeat(100):'正文😀 '.repeat(20)+'\\n';
      const text=unit.repeat(shape==='single'?90:300)+'END',samples=[];
      for(const size of [12000,24000,36000,text.length]) {
        write(text.slice(0,size));samples.push({text:sc.textContent===full.textContent,...heights()});
      }
      const node=sc.firstChild;write(text+' appended');
      return {samples,complete:sc.textContent===text+' appended',sameNode:node===sc.firstChild,
        children:sc.childNodes.length,placeholders:sc.querySelectorAll('*').length};
    }""", {"kind": kind, "shape": shape})
    assert all(sample["text"] and abs(sample["actual"] - sample["expected"]) < 1.5
               for sample in result["samples"])
    assert result["samples"][-1]["actual"] > result["samples"][1]["actual"]
    assert result["complete"] and result["sameNode"]
    assert result["children"] == 1 and result["placeholders"] == 0


def test_resize_hidden_updates_and_font_change_use_natural_layout(page):
    page.evaluate("write(('正文 word '.repeat(30)+'\\n').repeat(350))")
    assert_equal_height(page)
    for width in (450, 900):
        page.evaluate("width=>{subject.style.width=width+'px';oracle.style.width=width+'px';}", width)
        assert_equal_height(page)
    page.evaluate("subject.style.display='none';write(sc._llmRawText+'\\n'+'hidden '.repeat(5000))")
    page.evaluate("subject.style.display=''")
    assert_equal_height(page)
    page.evaluate("sc.style.fontSize='17px';full.style.fontSize='17px'")
    assert_equal_height(page)


@pytest.mark.parametrize("kind", ["llm-reasoning", "llm-response"])
def test_finalization_and_folding_keep_full_body(page, kind):
    result = page.evaluate("""kind => {
      start(kind);const text=('正文 '.repeat(40)+'\\n').repeat(400)+'END';write(text);
      const node=sc.firstChild;finalizeLlmStreamChunks(ctx);finalizeLlmStreamChunks(ctx);
      const row=sc.closest('.feed-item'),chunk=sc.closest('.feed-chunk');
      const collapsed=row.classList.contains('is-collapsed');
      if(kind==='llm-reasoning')row.querySelector('.feed-row-collapse').click();
      else chunk.dispatchEvent(new MouseEvent('click',{bubbles:true}));
      return {complete:sc.textContent===text,sameNode:node===sc.firstChild,collapsed,
        streaming:chunk.classList.contains('is-streaming'),expanded:!row.classList.contains('is-collapsed'),
        textHeight:sc.scrollHeight,visibleHeight:sc.clientHeight};
    }""", kind)
    assert result["complete"] and result["sameNode"] and not result["streaming"]
    assert result["collapsed"] == (kind == "llm-reasoning") and result["expanded"]
    if kind == "llm-response":
        assert result["textHeight"] <= result["visibleHeight"] + 1


@pytest.mark.parametrize("kind", ["llm-reasoning", "llm-response"])
def test_history_and_authoritative_snapshot_keep_full_body(page, kind):
    result = page.evaluate("""kind => {
      const text=('history '.repeat(30)+'\\n').repeat(400)+'END';
      replayingMessages=true;start(kind,text,{historyHydrate:true,reactIter:1});
      const historyComplete=sc.textContent===text;
      replayingMessages=false;ctx.llm={};
      upsertLlmFeedRow(ctx,text+' snapshot',kind,currentSessionId,1);
      const snapshotComplete=sc.textContent===text+' snapshot';
      writeLlmStreamText(sc,text+' replacement\\n',kind==='llm-response'?'response':'reasoning');
      appendLlmRevealedText(sc,'next',kind==='llm-response'?'response':'reasoning');
      return {historyComplete,snapshotComplete,appendComplete:sc.textContent===text+' replacement\\nnext'};
    }""", kind)
    assert all(result.values())


@pytest.mark.parametrize("kind", ["reasoning", "response"])
def test_execution_records_preserve_long_deltas_and_recovery(page, kind):
    result = page.evaluate("""kind => {
      const text=('record '.repeat(30)+'\\n').repeat(400)+'END',id='execution-'+kind;
      body.replaceChildren();
      renderExecutionRecord(ctx,updateExecutionRecord(currentSessionId,{execution_id:id,
        kind,status:'generating',content:text,last_runtime_seq:1}),currentSessionId);
      const row=body.firstElementChild;window.sc=row.querySelector('.feed-chunk-scroller');
      const initialComplete=sc.textContent===text;
      renderExecutionRecord(ctx,updateExecutionRecord(currentSessionId,{execution_id:id,
        kind,status:'generating',text_delta:' next',last_runtime_seq:2}),currentSessionId);
      const deltaComplete=sc.textContent===text+' next';
      renderExecutionRecord(ctx,updateExecutionRecord(currentSessionId,{execution_id:id,
        kind,status:'completed',content:text+' committed',last_runtime_seq:3}),currentSessionId);
      finalizeLlmStreamChunks(ctx);
      const terminalComplete=sc.textContent===text+' committed';
      body.replaceChildren();replayingMessages=true;
      renderExecutionRecord(ctx,executionRecordsBySession.get(currentSessionId).get(id),currentSessionId);
      return {initialComplete,deltaComplete,terminalComplete,
        recoveredComplete:body.querySelector('.feed-chunk-scroller').textContent===text+' committed'};
    }""", kind)
    assert all(result.values())


@pytest.mark.parametrize("shape", ["single", "multi"])
def test_long_tool_draft_output_completion_and_history_keep_full_text(page, shape):
    result = page.evaluate("""shape => {
      const text=shape==='single'?'工具😀中间正文 '.repeat(5000)
        :Array.from({length:450},(_,i)=>'工具第 '+i+' 行：保留中间正文😀').join('\\n');
      const args='{"content":"'+text+'"}';
      start('tool-call','',{reactIter:1});
      const row=sc.closest('.feed-item');row.dataset.toolCallId='long-tool';
      rememberToolStreamRow(ctx,row,'','long-tool');
      writeToolCallLlmText(sc,'write_file',args);
      const draftComplete=getUiRuntimeText(sc)===formatToolDraftLine('write_file',args);
      appendToolPendingRow(ctx,{tool:'run_shell',tool_call_id:'long-tool',
        args:{},command_preview:text,react_iter:1},currentSessionId);
      const pendingComplete=getUiRuntimeText(sc)===formatToolPendingLine('run_shell',{},text);
      setToolRowText(row,text+'\\n实时输出完成',ctx,currentSessionId);
      const outputComplete=getUiRuntimeText(sc)===text+'\\n实时输出完成';
      upsertToolCallResult(ctx,{tool:'run_shell',tool_call_id:'long-tool',
        args:{},command_preview:'echo full',result:text},currentSessionId);
      const expected=formatToolDoneLine('run_shell',{},text,'echo full');
      const completedComplete=getUiRuntimeText(sc)===expected;
      const collapsed=row.classList.contains('is-collapsed');
      row.querySelector('.feed-row-collapse').click();
      const expandedComplete=!row.classList.contains('is-collapsed')&&getUiRuntimeText(sc)===expected;
      replayingMessages=true;start('tool-call',expected,{historyHydrate:true,reactIter:1});
      return {draftComplete,pendingComplete,outputComplete,completedComplete,collapsed,expandedComplete,
        historyComplete:getUiRuntimeText(sc)===expected};
    }""", shape)
    assert all(result.values()), result


@pytest.mark.parametrize("shape", ["single", "multi"])
def test_long_tool_execution_deltas_and_recovery_keep_full_text(page, shape):
    result = page.evaluate("""shape => {
      const text=shape==='single'?'长工具正文😀 '.repeat(5000)+'END'
        :Array.from({length:450},(_,i)=>'output '+i+' 中间保留😀').join('\\n');
      const args='{"content":"'+text+'"}',id='long-tool-execution';
      body.replaceChildren();ctx.llm={};
      const render=update=>renderExecutionRecord(ctx,
        updateExecutionRecord(currentSessionId,{execution_id:id,kind:'tool',...update}),currentSessionId);
      render({tool:'write_file',status:'generating',arguments_raw:args,last_runtime_seq:1});
      const sc=body.querySelector('.feed-chunk-scroller');
      const draftComplete=getUiRuntimeText(sc)===formatToolDraftLine('write_file',args);
      render({status:'running',command_preview:'echo full',output_delta:text,last_runtime_seq:2});
      const outputComplete=getUiRuntimeText(sc).includes(text);
      render({output_delta:'\\n尾部增量',last_runtime_seq:3});
      const deltaComplete=getUiRuntimeText(sc).includes(text+'\\n尾部增量');
      render({status:'completed',result:text+'\\n完整结果',last_runtime_seq:4});
      const completed=getUiRuntimeText(sc);
      const completedComplete=completed.includes(text+'\\n完整结果');
      body.replaceChildren();replayingMessages=true;
      renderExecutionRecord(ctx,executionRecordsBySession.get(currentSessionId).get(id),currentSessionId);
      return {draftComplete,outputComplete,deltaComplete,completedComplete,
        recoveryComplete:getUiRuntimeText(body.querySelector('.feed-chunk-scroller'))===completed};
    }""", shape)
    assert all(result.values()), result


def test_scoped_abort_and_auxiliary_log_truncation_remain(page):
    result = page.evaluate("""() => {
      const text=('tool '.repeat(30)+'\\n').repeat(400)+'END';write(text);
      const row=sc.closest('.feed-item');
      discardLlmStreamChunks(ctx,{react_iter:2,run_id:'run-1'});
      const otherScopeKept=row.isConnected && sc.textContent===text;
      discardLlmStreamChunks(ctx,{react_iter:1,run_id:'run-1'});
      const removed=!row.isConnected;
      const types=['status','context-summary-reasoning'];
      const truncationKept=types.every(type=>{
        const node=createProcessFeedRow(ctx,type,text,{historyHydrate:true},currentSessionId);
        return node.textContent===truncateLogTextForUi(text) && node.textContent.length<text.length;
      });
      return {otherScopeKept,removed,truncationKept};
    }""")
    assert all(result.values())
