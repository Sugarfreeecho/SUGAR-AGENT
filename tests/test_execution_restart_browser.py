"""Exercise restart ordering with production renderers and real DOM, without a server."""
import os
import re
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]


def function(source, name):
    match = re.search(r"^(?:async )?function " + name + r"\([\s\S]*?^}", source, re.M)
    if not match:
        raise AssertionError(f"Missing production function: {name}")
    return match.group(0)


@pytest.fixture
def page():
    with playwright.sync_playwright() as runtime:
        try:
            browser = runtime.chromium.launch(
                headless=True, **({"channel": "msedge"} if os.name == "nt" else {})
            )
        except playwright.Error as error:
            pytest.skip(f"Local Chromium browser unavailable: {error}")
        page = browser.new_page(viewport={"width": 600, "height": 800})
        rendering = (ROOT / "frontend/src/app/modules/message-rendering.js").read_text(encoding="utf-8")
        dispatch = (ROOT / "frontend/src/app/modules/event-dispatch.js").read_text(encoding="utf-8")
        css = (ROOT / "frontend/src/styles/app.css").read_text(encoding="utf-8")
        page.set_content(
            f"<style>{css}</style>"
            "<style>#stream{width:380px}.process-aggregate-body{display:block}</style>"
            "<div id='stream'><div class='process-aggregate' data-process-group-id='turn:1104'>"
            "<div class='process-aggregate-body'></div></div></div>"
        )
        helpers = "\n".join(function(rendering, name) for name in [
            "reactGenerationForContext", "reactFeedPhase", "appendProcessRowBeforePendingAppendSteer",
            "appendMonotonicProcessRow", "insertReactOrderedFeedRow", "createProcessFeedRow",
        ])
        scope = "\n".join(function(dispatch, name) for name in [
            "seedRenderContextRunGenerations", "syncRenderContextRunScope",
        ])
        records = rendering[rendering.index("var executionRecordsBySession"):rendering.index("function ensureProcessGroup")]
        page.add_script_tag(content="""
          var replayingMessages=false, follows=0, animations=0;
          var TRACE_ROW={
            'llm-reasoning':{c:'feed--llm',label:'思考'},
            'llm-response':{c:'feed--llm2',label:'回答'},
            'tool-call':{c:'feed--tool',label:'工具'},
            'log-entry':{c:'feed--log',label:'日志'}
          };
          function stripWelcome(){}
          function getProcessBody(ctx){return ctx.currentProcessGroup.querySelector('.process-aggregate-body');}
          function resetLlmState(ctx){ctx.llm={};}
          function trimSurroundingBlankLines(text){return String(text).trim();}
          function truncateLogTextForUi(text){return String(text);}
          function removeTemporaryStatus(){}
          function discardPendingToolRowRender(){}
          function bindFeedChunkInteraction(){}
          function bindFeedChunkScrollChain(){}
          function refreshFeedChunkOverflow(){}
          function scheduleFeedChunkOverflowRefresh(){}
          function refreshAggregateStatsSmart(){}
          function registerProcessAggregateRow(){}
          function unregisterProcessAggregateRow(){}
          function bumpAggregateMaxReactIter(){}
          function autoCollapseLlmReasoningRow(){}
          function toggleCollapsibleFeedRow(){}
          function updateProcessBrief(){}
          function animateSmoothTraceRowInsertion(){animations++;}
          function finishStreamScrollIfFollow(){follows++;}
          function scrollContentAreaIfFollow(){follows++;}
        """ + helpers + scope + records + """
          var ctx={stream:document.getElementById('stream'),
            currentProcessGroup:document.querySelector('.process-aggregate'),
            processGroupId:'turn:1104',runId:'before-restart',reactGeneration:0,llm:{}};
          createProcessFeedRow(ctx,'llm-reasoning','重启前的思考',{reactIter:171,streaming:true},'fixture');
          var live={execution_id:'after-restart:reasoning:1',run_id:'after-restart',
            process_group_id:'turn:1104',kind:'reasoning',status:'generating',react_iter:1,
            content:'恢复后的正文',first_runtime_seq:27194,last_runtime_seq:27194};
          var older={execution_id:'before-restart:reasoning:172',run_id:'before-restart',
            process_group_id:'turn:1104',kind:'reasoning',status:'generating',react_iter:172,
            content:'旧的部分思考',first_runtime_seq:27130,last_runtime_seq:27188};
          function order(){return Array.from(getProcessBody(ctx).children).map(row=>[
            row.dataset.runId,Number(row.dataset.reactIter),Number(row.dataset.reactGeneration)]);}
        """)
        yield page
        browser.close()


def test_new_run_stream_stays_at_tail_and_duplicate_frames_do_not_mutate(page):
    result = page.evaluate("""() => {
      renderExecutionRecord(ctx,live,'fixture');
      const row=ctx.stream.querySelector('[data-execution-id="'+live.execution_id+'"]');
      const before=follows;
      renderExecutionRecord(ctx,older,'fixture');
      const oldBackfillFollows=follows-before;
      const ordered=order();
      const ys=Array.from(getProcessBody(ctx).children).map(el=>el.getBoundingClientRect().top);
      let moved=false;
      for(let n=1;n<=100;n++) {
        renderExecutionRecord(ctx,{...live,last_runtime_seq:27194+n,content:'恢复后的正文'+n},'fixture');
        moved ||= getProcessBody(ctx).lastElementChild!==row;
      }
      const observer=new MutationObserver(()=>{});
      observer.observe(row,{subtree:true,childList:true,characterData:true,attributes:true});
      const followsBeforeDuplicate=follows;
      for(let n=0;n<100;n++) renderExecutionRecord(ctx,
        {...live,last_runtime_seq:27294,content:'恢复后的正文100'},'fixture');
      const duplicateMutations=observer.takeRecords().length;
      observer.disconnect();
      return {ordered,ys,moved,oldBackfillFollows,duplicateMutations,
        duplicateFollows:follows-followsBeforeDuplicate,
        text:row.querySelector('.feed-chunk-scroller').textContent,
        activeRun:ctx.runId,generation:ctx.reactGeneration};
    }""")
    assert result["ordered"] == [["before-restart", 171, 0], ["before-restart", 172, 0], ["after-restart", 1, 1]]
    assert result["ys"][0] < result["ys"][1] < result["ys"][2]
    assert result["moved"] is False
    assert result["oldBackfillFollows"] == result["duplicateMutations"] == result["duplicateFollows"] == 0
    assert result["text"] == "恢复后的正文100"
    assert result["activeRun"] == "after-restart" and result["generation"] == 1


def test_completed_historical_backfill_neither_follows_nor_animates(page):
    result = page.evaluate("""() => {
      renderExecutionRecord(ctx,live,'fixture');
      const before={follows,animations};
      renderExecutionRecord(ctx,{...older,status:'interrupted'},'fixture');
      return {follows:follows-before.follows,animations:animations-before.animations,order:order()};
    }""")
    assert result["follows"] == result["animations"] == 0
    assert result["order"][-1] == ["after-restart", 1, 1]
