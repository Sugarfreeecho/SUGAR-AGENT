"""Exercise compression SSE delivery against real feed rows and fold controls."""
import re
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api")
from tests.test_llm_stream_full_text_browser import browser_page

ROOT = Path(__file__).resolve().parents[1]


def function_source(source, name):
    match = re.search(r"^(?:async )?function " + name + r"\([\s\S]*?^}", source, re.M)
    assert match, name
    return match.group(0)


@pytest.fixture
def compression_page(browser_page):
    page = browser_page
    rendering = (ROOT / "frontend/src/app/modules/message-rendering.js").read_text(encoding="utf-8")
    sse = (ROOT / "frontend/src/app/modules/sse-handling.js").read_text(encoding="utf-8")
    dispatch = (ROOT / "frontend/src/app/modules/event-dispatch.js").read_text(encoding="utf-8")
    reducer = (ROOT / "frontend/src/app/state/session-event-reducer.js").read_text(encoding="utf-8")
    messages = (ROOT / "frontend/src/app/state/message-renderers.js").read_text(encoding="utf-8")
    css = (ROOT / "frontend/src/styles/app.css").read_text(encoding="utf-8")
    page.set_content("<style>" + css + "</style><div id='stream'>"
                     "<div class='process-aggregate'><div class='process-aggregate-body' id='body'></div></div></div>")
    setup = """
      var currentSessionId='compression',replayingMessages=false,SSE_IDLE_TIMEOUT_MS=1000;
      var LOG_TRUNCATE_HEAD_LINES=100,LOG_TRUNCATE_TAIL_LINES=100;
      var LOG_TRUNCATE_HEAD_CHARS=12000,LOG_TRUNCATE_TAIL_CHARS=12000;
      var streamHistoryRecoveryBySession=new Set(),sessionStore={shouldAcceptSseEvent:()=>true};
      window.recorded=[];
      function applyMessageEvent(sid,event,index){recorded.push(event);return {event,index};}
      function appendContextProgressForSession(){}
      function stripWelcome(){}
      function getProcessBody(){return document.getElementById('body');}
      function reactGenerationForContext(){return 0;}
      function insertReactOrderedFeedRow(body,row){body.append(row);}
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
      function mutateSmoothTraceRowHeight(row,mutation){mutation();}
      function registerMermaidLazy(){}
      function syncRenderContextRunScope(){}
      function renderPluginExtensionEvent(){return false;}
      function finalizeLlmStreamChunks(){}
      function discardLlmStreamChunks(){}
      function removeTemporaryStatus(){}
      function removeAbortedToolDraftRows(){}
      function appendLlmStreamDelta(){throw Error('compression used the main reasoning stream');}
      function scheduleFinalVisibleAfterRunIfEnabled(){}
      function consumeExtensionControlEvent(){return false;}
      function readSseChunkWithIdleTimeout(reader){return reader.read();}
      function getUiRuntimeText(sc){return sc.textContent;}
      function setUiRuntimeText(sc,text){sc.textContent=text;}
      window.ctx={stream:document.getElementById('stream'),progressScrollers:{},progressStream:{},
        currentProcessGroup:document.querySelector('.process-aggregate'),llm:{marker:'main'}};
    """
    setup += rendering[rendering.index("const TRACE_ROW ="):rendering.index("const envKeepLines")]
    rendering_functions = [
        "trimSurroundingBlankLines", "truncateLogTextForUi", "feedRowCollapseAriaLabel",
        "syncFeedRowCollapseButton", "toggleCollapsibleFeedRow", "autoCollapseLlmReasoningRow",
        "createProcessFeedRow", "handleTraceChunkClick", "handleToolRowChunkClick",
        "handleLlmRowChunkClick", "bindFeedChunkInteraction", "appendLog",
        "flushProgressDeltaText", "scheduleProgressDeltaFlush", "ensureProgressScroller",
        "appendProgressStreamDelta", "appendProgressLog", "applyProgressPersistedBody",
        "createCompressionReasoningScroller", "appendCompressionReasoningDelta", "finishCompressionReasoning",
        "finalizeProgressStreamForType", "finalizeProgressStreamChunks", "discardProgressStreamChunks",
    ]
    setup += "\n".join(function_source(rendering, name) for name in rendering_functions)
    setup += "\n".join(function_source(sse, name) for name in (
        "shouldApplySseSeqFilter", "sseSequenceScope", "shouldSkipRecoveredEphemeralEvent",
        "consumeAgentSseResponseInner"))
    setup += function_source(dispatch, "renderEvent")
    setup += function_source(messages, "renderMessageRecord")
    setup += function_source(reducer, "markUiEventStoreApplied") + function_source(reducer, "applySessionEvent")
    setup += """
      createProcessFeedRow(ctx,'llm-reasoning','主模型推理',{},currentSessionId);
      window.deliver=async(events)=>{
        let bytes=new TextEncoder().encode(events.map(event=>'data: '+JSON.stringify(event)+'\\n\\n').join(''));
        let response=new Response(new ReadableStream({start(controller){
          for(let i=0;i<bytes.length;i+=3)controller.enqueue(bytes.slice(i,i+3));controller.close();
        }}),{headers:{'Content-Type':'text/event-stream'}});
        await consumeAgentSseResponseInner(response,ctx,currentSessionId,0);
        await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
      };
    """
    page.add_script_tag(content=setup)
    yield page
    page.goto("about:blank")


def send(page, *events):
    page.evaluate("events=>deliver(events)", list(events))


def reasoning(text, **extra):
    return {"type": "context_summary_reasoning_delta", "ephemeral": True, "delta": text, **extra}


def test_live_reasoning_shares_summary_row_and_can_be_reopened(compression_page):
    page = compression_page
    text = "先整理\n<script>window.unwanted=true</script>\n再写摘要。"
    send(page, reasoning(text))
    row = page.locator('[data-log-type="context-summary"]')
    thought = row.locator('.context-summary-reasoning')
    assert row.count() == 1
    assert page.locator('[data-log-type="context-summary-reasoning"]').count() == 0
    assert row.locator('.feed-label').text_content() == "压缩"
    assert thought.locator('.feed-chunk-scroller').text_content() == text
    assert thought.get_attribute("open") is not None
    assert thought.locator('.feed-chunk').get_attribute("class").endswith("is-streaming")
    assert row.locator('script').count() == 0
    assert page.evaluate("recorded.length") == 0

    send(page, {"type": "context_summary_delta", "ephemeral": True, "delta": "<recap>draft"},
         {"type": "context_summary_progress", "ephemeral": True, "content": "still waiting"},
         {"type": "context_summary_reasoning_end", "ephemeral": True},
         {"type": "context_summary_body", "content": "最终摘要"})
    assert row.count() == 1
    assert thought.get_attribute("open") is None
    assert thought.get_attribute("data-compression-live") is None
    assert thought.locator('.feed-chunk-scroller').text_content() == text
    assert row.locator('.context-summary-content > .feed-chunk > .feed-chunk-scroller').text_content().strip() == "still waiting\n\n最终摘要"
    assert page.locator('[data-log-type="llm-reasoning"] .feed-chunk-scroller').text_content() == "主模型推理"
    assert page.evaluate("ctx.llm.marker") == "main"
    thought.locator('summary').click()
    assert thought.get_attribute("open") is not None


def test_reconnect_snapshot_replaces_preview_and_keeps_whitespace(compression_page):
    page = compression_page
    send(page, reasoning("prefix"))
    send(page, reasoning("prefix\n新增", replayed_snapshot=True), reasoning(" tail\n"))
    row = page.locator('[data-log-type="context-summary"]')
    assert row.count() == 1
    assert row.locator('.context-summary-reasoning .feed-chunk-scroller').text_content() == "prefix\n新增 tail\n"


def test_retry_stays_in_same_row_and_interrupt_discards_only_active_preview(compression_page):
    page = compression_page
    send(page, reasoning("first request"), {"type": "context_summary_reasoning_end", "ephemeral": True},
         reasoning("retry"))
    row = page.locator('[data-log-type="context-summary"]')
    thoughts = row.locator('.context-summary-reasoning')
    assert row.count() == 1
    assert thoughts.count() == 2
    assert thoughts.nth(1).get_attribute("open") is not None
    send(page, {"type": "llm_stream_aborted", "ephemeral": True, "cleanup_scope": "drafts_only"})
    assert row.count() == 1
    assert thoughts.count() == 1
    assert thoughts.first.locator('.feed-chunk-scroller').text_content() == "first request"
    assert page.evaluate("Object.keys(ctx.progressStream).length") == 0


def test_compression_progress_replaces_status_without_losing_summary(compression_page):
    page = compression_page
    send(page, *[{"type": "context_trim_progress", "content": text}
                 for text in ("准备裁剪", "正在微压", "裁剪完成")])
    trim = page.locator('[data-log-type="context-trim"] .feed-chunk-scroller')
    assert trim.count() == 1
    assert trim.text_content() == "裁剪完成"
    send(page, {"type": "context_summary_progress", "content": "正在生成摘要"},
         *[{"type": "context_summary_progress", "ephemeral": True, "content": "等待摘要"}] * 20)
    summary = page.locator('[data-log-type="context-summary"] .feed-chunk-scroller')
    assert summary.count() == 1
    assert summary.text_content() == "等待摘要"
    send(page, {"type": "context_summary_delta", "ephemeral": True, "delta": "draft"},
         {"type": "context_summary_progress", "content": "整理摘要"},
         {"type": "context_summary_delta", "ephemeral": True, "delta": " tail"})
    assert summary.text_content() == "整理摘要\n\ndraft tail"
    assert page.evaluate("!!ctx.progressStream['context-summary']") is True
    send(page, {"type": "context_summary_body", "content": "完整摘要"},
         {"type": "context_summary_progress", "content": "摘要完成"},
         {"type": "context_summary_progress", "content": "摘要完成"})
    assert summary.text_content() == "摘要完成\n\n完整摘要"
    assert page.evaluate("!!ctx.progressStream['context-summary']") is False
