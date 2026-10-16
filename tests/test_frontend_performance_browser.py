"""Behavior and bounded-work checks for the UI performance changes."""
import os
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def page():
    with playwright.sync_playwright() as runtime:
        try:
            browser = runtime.chromium.launch(
                headless=True, **({"channel": "msedge"} if os.name == "nt" else {})
            )
        except playwright.Error as error:
            pytest.skip(f"Local Chromium browser unavailable: {error}")
        yield browser.new_page(viewport={"width": 1100, "height": 800})
        browser.close()


def test_process_height_updates_on_resize_without_work_on_scroll(page):
    source = (ROOT / "frontend/src/app/modules/message-rendering.js").read_text(encoding="utf-8")
    page.set_content(
        "<style>#chat-container{height:300px;overflow:auto;}"
        ".process-aggregate-body{max-height:min(72vh,41.6rem);overflow:auto;}</style>"
        "<div id='chat-container'><div class='process-aggregate' id='agg'>"
        "<div class='process-aggregate-body' id='body'><div style='height:2000px'></div>"
        "</div></div><div style='height:1000px'></div></div>"
    )
    page.add_script_tag(content=source[
        source.index("function applyProcessBodyViewportClamp("):
        source.index("function scheduleProcessAggregateHeightUi(")
    ])
    page.evaluate("ensureProcessViewportClampBinding();applyProcessBodyViewportClamp(agg)")
    page.wait_for_function("body.clientHeight===292")
    page.wait_for_function("processViewportClampHeight===300")
    page.evaluate("""() => {
      window.sweeps=0;window.styleWrites=0;
      const query=document.querySelectorAll.bind(document);
      document.querySelectorAll=selector=>{if(selector==='.process-aggregate')sweeps++;return query(selector);};
      new MutationObserver(rows=>{styleWrites+=rows.length;}).observe(body,{attributes:true,attributeFilter:['style']});
    }""")
    # Allow the initial ResizeObserver notification to finish before measuring scroll work.
    page.wait_for_timeout(50)
    page.evaluate("""() => {
      sweeps=0;styleWrites=0;
      for(let i=0;i<20;i++)applyProcessBodyViewportClamp(agg);
      const port=document.getElementById('chat-container');
      port.scrollTop=100;port.dispatchEvent(new Event('scroll'));
    }""")
    page.wait_for_timeout(50)
    assert page.evaluate("({sweeps,styleWrites})") == {"sweeps": 0, "styleWrites": 0}
    page.evaluate("document.getElementById('chat-container').style.height='200px'")
    page.wait_for_function("body.clientHeight===192")
    page.evaluate("document.getElementById('chat-container').style.height='1000px'")
    page.wait_for_function("body.clientHeight===576")  # Original 72vh limit still applies.


def test_viewed_turn_uses_bounded_geometry_reads_and_preserves_selection(page):
    source = (ROOT / "plugins/change-review/web/change-review.js").read_text(encoding="utf-8")
    page.set_content(
        "<style>#port{height:400px;overflow:auto;}"
        ".msg-wrap--user{height:30px}</style><div id='port'><div id='chat-stream'>"
        + "".join(f"<div class='msg-wrap--user' data-event-index='{i}'>turn {i}</div>" for i in range(4096))
        + "</div></div>"
    )
    page.add_script_tag(content=source.replace("export ", ""))
    result = page.evaluate("""() => {
      const port=document.getElementById('port'),users=document.querySelectorAll('.msg-wrap--user');
      const original=Element.prototype.getBoundingClientRect;
      const samples=[];
      for(const top of [0,20000,90000,port.scrollHeight]) {
        port.scrollTop=top;
        const rect=port.getBoundingClientRect(),pivot=rect.top+rect.height/2;
        const nearBottom=port.scrollTop+port.clientHeight>=port.scrollHeight-24;
        let expected=users[0];
        for(const user of users) {if(user.getBoundingClientRect().top<=pivot)expected=user;else break;}
        if(nearBottom)expected=users[users.length-1];
        let reads=0;
        Element.prototype.getBoundingClientRect=function(){
          if(this.classList.contains('msg-wrap--user'))reads++;return original.call(this);
        };
        const viewed=viewedTurnRange();
        Element.prototype.getBoundingClientRect=original;
        samples.push({correct:viewed.key===expected.dataset.eventIndex,reads,nearBottom});
      }
      return samples;
    }""")
    assert all(sample["correct"] and sample["reads"] <= 13 for sample in result)
    assert result[-1]["reads"] == 0 and result[-1]["nearBottom"]


def test_execution_updates_reuse_rows_across_history_and_context_changes(page):
    rendering = (ROOT / "frontend/src/app/modules/message-rendering.js").read_text(encoding="utf-8")
    history = (ROOT / "frontend/src/app/modules/session-scroll-history.js").read_text(encoding="utf-8")
    page.set_content("<div id='stream'><div class='process-aggregate' data-process-group-id='turn:1'>"
                     "<div class='process-aggregate-body'></div></div></div>")
    page.add_script_tag(content="""
        var replayingMessages=true;
        function reactGenerationForContext(){return 0;}
        function discardPendingToolRowRender(){}
        function removeTemporaryStatus(){}
        function refreshFeedChunkOverflow(){}
        function refreshAggregateStatsSmart(){}
        function refreshProcessAggregateStats(){}
        function unregisterProcessAggregateRow(){}
        function registerProcessAggregateRow(){}
        function trimSurroundingBlankLines(text){return text.trim();}
        function createProcessFeedRow(ctx,type,text){
            var group=ctx.currentProcessGroup;
            if(!group || !ctx.stream.contains(group)){
                group=document.createElement('div');group.className='process-aggregate';
                group.dataset.processGroupId='turn:1';
                group.innerHTML='<div class="process-aggregate-body"></div>';
                ctx.stream.appendChild(group);ctx.currentProcessGroup=group;
            }
            var row=document.createElement('div');row.className='feed-item';
            row.innerHTML='<div class="feed-chunk"><div class="feed-chunk-scroller"></div></div>';
            var sc=row.querySelector('.feed-chunk-scroller');sc.textContent=text;
            group.querySelector('.process-aggregate-body').appendChild(row);return sc;
        }
    """ + rendering[rendering.index("var executionRecordsBySession"):
                      rendering.index("function ensureProcessGroup")]
        + history[history.index("function emptyChatStreamKeepingStrip("):
                  history.index("function persistHistoryPagingToStream(")])
    result = page.evaluate("""() => {
        const stream=document.getElementById('stream'),body=stream.querySelector('.process-aggregate-body');
        for(let i=0;i<1000;i++){
            const row=document.createElement('div');row.className='feed-item';row.dataset.executionId='row-'+i;
            row.innerHTML='<div class="feed-chunk"><div class="feed-chunk-scroller">old</div></div>';
            body.appendChild(row);
        }
        const card=document.createElement('div');card.dataset.executionId='row-999';card.textContent='approval card';
        body.lastChild.appendChild(card);
        let scans=0;const query=stream.querySelectorAll.bind(stream);
        stream.querySelectorAll=selector=>{if(selector==='[data-execution-id]')scans++;return query(selector);};
        const context=root=>({stream:root,currentProcessGroup:root.querySelector('.process-aggregate')});
        const ctx=context(stream);
        function render(target,id,seq,text){renderExecutionRecord(target,{
            execution_id:id,kind:'reasoning',status:'completed',process_group_id:'turn:1',
            last_runtime_seq:seq,content:text},'s');}
        for(let i=1;i<=150;i++)render(ctx,'row-999',i,'updated '+i);
        render(context(stream),'row-999',151,'fresh context');
        const hotScans=scans;
        const original=body.lastChild;
        const reused=body.children.length===1000 && original.querySelector('.feed-chunk-scroller').textContent==='fresh context'
            && card.textContent==='approval card';
        stream.remove();render(ctx,'row-999',152,'detached stream');
        const detached=original.querySelector('.feed-chunk-scroller').textContent==='detached stream';
        document.body.appendChild(stream);
        original.remove();const recoveredRow=original.cloneNode(true);body.appendChild(recoveredRow);
        render(ctx,'row-999',153,'recreated');
        const replacement=body.lastChild;
        const recreated=replacement===recoveredRow && replacement!==original && replacement.dataset.executionId==='row-999'
            && body.children.length===1000;
        const other=document.createElement('div');document.body.appendChild(other);
        render(context(other),'row-999',1,'other session');
        const isolated=replacement.querySelector('.feed-chunk-scroller').textContent==='recreated';
        const frag=document.createDocumentFragment(),older=context(frag);
        render(older,'older-row',1,'older');
        stream.insertBefore(frag,stream.firstChild);invalidateExecutionRowIndex(stream);
        mergeAdjacentExecutionGroups(stream);
        render(ctx,'older-row',2,'older updated');render(ctx,'row-999',154,'after merge');
        const merged=stream.querySelectorAll('.process-aggregate').length===1
            && stream.querySelector('[data-execution-id="older-row"] .feed-chunk-scroller').textContent==='older updated'
            && replacement.querySelector('.feed-chunk-scroller').textContent==='after merge';
        const afterPrependScans=scans;
        emptyChatStreamKeepingStrip(stream);render(context(stream),'row-999',1,'reload');
        const reloaded=stream.querySelectorAll('.feed-item').length===1
            && stream.querySelector('.feed-chunk-scroller').textContent==='reload';
        return {hotScans,afterPrependScans,totalScans:scans,reused,detached,recreated,isolated,merged,reloaded};
    }""")
    assert result == {"hotScans": 1, "afterPrependScans": 3, "totalScans": 4,
                      "reused": True, "detached": True, "recreated": True,
                      "isolated": True, "merged": True, "reloaded": True}
