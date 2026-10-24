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


def test_hidden_history_skips_repeated_layout_until_revealed(page):
    source = (ROOT / 'frontend/src/app/modules/message-rendering.js').read_text(encoding='utf-8')
    page.set_content('''<div id="chat-container" style="height:300px;overflow:auto">
      <div class="chat-stream" id="stream" hidden><div class="process-aggregate" id="agg">
        <button class="process-aggregate-resize"></button><div class="process-aggregate-body"></div>
        <div class="feed-chunk" id="chunk"><div class="feed-chunk-scroller">payload</div></div>
      </div></div></div>''')
    page.add_script_tag(content=source[source.index('function measureFeedChunkOverflow('):source.index('var feedChunkOverflowQueue')])
    page.add_script_tag(content=source[source.index('function syncProcessAggregateHeightUi('):source.index('/* 可视高度变化才重算')])
    result = page.evaluate('''() => {
      let geometry=0,styles=0;
      window.feedChunkCollapsedMax=()=>{styles++;return 60;};
      const viewport=document.getElementById('chat-container');
      const measure=viewport.getBoundingClientRect.bind(viewport);
      viewport.getBoundingClientRect=()=>{geometry++;return measure();};
      for(let i=0;i<200;i++){syncProcessAggregateHeightUi(agg);measureFeedChunkOverflow(chunk);}
      const hidden={geometry,styles};
      document.getElementById('stream').hidden=false;
      syncProcessAggregateHeightUi(agg);measureFeedChunkOverflow(chunk);
      return {hidden,geometry,styles};
    }''')
    assert result == {'hidden': {'geometry': 0, 'styles': 0}, 'geometry': 1, 'styles': 1}


def test_session_title_cleanup_defers_geometry_and_coalesces_latest_rows(page):
    source = (ROOT/'frontend/src/app/state/session-renderers.js').read_text(encoding='utf8')
    start = source.index('var sessionNameNormalizationQueue')
    end = source.index('\n/**', start)
    page.set_content('<div id="list"></div>')
    page.add_script_tag(content='window.jobs=[];window.MyAgentUiTasks={afterPaint:work=>jobs.push(work)};'+source[start:end])
    result = page.evaluate('''() => {
      const root=document.getElementById('list');let reads=0;
      const add=(name,width)=>{
        const el=document.createElement('span');el.className='session-name';
        el.dataset.original=name;el.textContent=name;
        Object.defineProperty(el,'scrollWidth',{get:()=>{reads++;return width;}});
        Object.defineProperty(el,'clientWidth',{get:()=>{reads++;return 100;}});
        root.append(el);return el;
      };
      const ordinary=add('普通会话',300),long=add('需要截断（长标题）',300),short=add('短标题）',50);
      normalizeTruncatedSessionNames(root);normalizeTruncatedSessionNames(root);
      const immediate={reads,jobs:jobs.length,text:long.textContent};
      jobs.shift()();const first={reads,long:long.textContent,short:short.textContent,ordinary:ordinary.textContent};
      normalizeTruncatedSessionNames(root);root.replaceChildren();
      const latest=add('替换后的长标题）',300);normalizeTruncatedSessionNames(root);
      const coalesced=jobs.length;jobs.shift()();
      return {immediate,first,coalesced,latest:latest.textContent,original:latest.dataset.original};
    }''')
    assert result == {
        'immediate': {'reads': 0, 'jobs': 1, 'text': '需要截断（长标题）'},
        'first': {'reads': 4, 'long': '需要截断（长标题…', 'short': '短标题）', 'ordinary': '普通会话'},
        'coalesced': 1, 'latest': '替换后的长标题…', 'original': '替换后的长标题）',
    }


def test_chinese_mutations_skip_translation_and_language_toggles_still_restore(page):
    page.route('http://ui-language.test/**', lambda route: route.fulfill(
        content_type='text/html; charset=utf-8',
        body='<meta charset="utf-8"><body><div id="host"></div><div class="message">打开会话</div></body>'))
    page.goto('http://ui-language.test/')
    page.add_script_tag(content=(ROOT/'frontend/src/app/modules/i18n.js').read_text(encoding='utf8'))
    result = page.evaluate('''async () => {
      let scans=0;const translate=translateUiNode;
      translateUiNode=root=>{scans++;return translate(root);};
      const host=document.getElementById('host');
      host.innerHTML='<button id="first" title="打开会话">打开会话</button>';
      await new Promise(resolve=>setTimeout(resolve,0));
      const chineseScans=scans;
      applyUiLanguage('en',false);
      const english={text:first.textContent,title:first.title,content:document.querySelector('.message').textContent};
      host.insertAdjacentHTML('beforeend','<button id="second" title="打开会话">打开会话</button>');
      await new Promise(resolve=>setTimeout(resolve,0));
      const addedEnglish={text:second.textContent,title:second.title};
      applyUiLanguage('zh-CN',false);
      return {chineseScans,english,addedEnglish,restored:[first.textContent,first.title,second.textContent,second.title]};
    }''')
    assert result == {
        'chineseScans': 0,
        'english': {'text': 'Open session', 'title': 'Open session', 'content': '打开会话'},
        'addedEnglish': {'text': 'Open session', 'title': 'Open session'},
        'restored': ['打开会话'] * 4,
    }


def test_closed_session_menu_skips_layout_and_open_menu_remains_focusable(page):
    source = (ROOT/'frontend/src/app/modules/session-management.js').read_text(encoding='utf8')
    start = source.index('function buildSessionMoreMenuMarkup()')
    end = source.index('function findSessionForActions', start)
    page.set_content('<div class="session-item" id="row"></div>')
    page.add_style_tag(content=(ROOT/'frontend/src/styles/app.css').read_text(encoding='utf8'))
    page.add_script_tag(content=source[start:end])
    result = page.evaluate('''() => {
      document.getElementById('row').innerHTML=buildSessionMoreMenuMarkup();
      const wrap=document.querySelector('.session-more-wrap');
      const menu=wrap.querySelector('.session-more-menu');
      const closed=menu.getClientRects().length;
      wrap.classList.add('is-open');
      const item=menu.querySelector('.session-menu-rename');item.focus();
      const open={visible:menu.getBoundingClientRect().height>0,focused:document.activeElement===item};
      wrap.classList.remove('is-open');
      return {closed,open,closedAgain:menu.getClientRects().length};
    }''')
    assert result == {'closed': 0, 'open': {'visible': True, 'focused': True}, 'closedAgain': 0}


def test_paged_run_generations_do_not_insert_new_output_before_old_history(page):
    import re
    source = (ROOT/'frontend/src/app/modules/message-rendering.js').read_text(encoding='utf8')
    page.set_content('''<div id="body">
      <div id="older" class="feed-item" data-log-type="llm-reasoning" data-run-id="same-run"
        data-react-generation="2" data-react-iter="1" data-execution-first-seq="800"></div>
      <div id="current" class="feed-item" data-log-type="llm-reasoning" data-run-id="same-run"
        data-react-generation="0" data-react-iter="77" data-execution-first-seq="3090"></div>
      </div>''')
    names=['reactFeedPhase','appendProcessRowBeforePendingAppendSteer','appendMonotonicProcessRow','insertReactOrderedFeedRow']
    page.add_script_tag(content='\n'.join(
        re.search(r'^function '+name+r'\([\s\S]*?^}',source,re.M)[0] for name in names))
    result=page.evaluate('''() => {
      const body=document.getElementById('body');body._reactOrderTailKey=[2,1,0];
      const add=(id,seq,iter,generation,type='llm-reasoning')=>{
        const row=document.createElement('div');row.id=id;row.className='feed-item';
        Object.assign(row.dataset,{executionFirstSeq:String(seq),runId:'same-run',logType:type});
        insertReactOrderedFeedRow(body,row,type,iter,generation);
      };
      add('new',3200,78,0);
      const initial=Array.from(body.children,node=>node.id);
      add('late-old',900,2,2);
      add('tool',3210,78,0,'tool-call');
      add('response',3215,78,0,'llm-response');
      return {initial,final:Array.from(body.children,node=>node.id)};
    }''')
    assert result['initial']==['older','current','new']
    assert result['final']==['older','late-old','current','new','response','tool']


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


def test_streamed_stats_do_not_restyle_unrelated_history(page):
    styles = (ROOT / "frontend/src/styles/app.css").read_text(encoding="utf-8")
    rendering = (ROOT / "frontend/src/app/modules/message-rendering.js").read_text(encoding="utf-8")
    shell = (ROOT / "frontend/src/shell-body.html").read_text(encoding="utf-8")
    page.set_content(f"<style>{styles}\n*,:before,:after{{animation:none!important;transition:none!important}}</style>{shell}")
    page.evaluate("""() => {
      document.getElementById('chat-stream').innerHTML=
        '<div class="feed-item"><div class="feed-chunk-scroller">history</div></div>'.repeat(1000)
        + '<div id="stats"></div>';
    }""")
    page.add_script_tag(content=rendering[
        rendering.index("function renderProcessAggregateStats("):
        rendering.index("function refreshProcessAggregateStats(")
    ])
    page.evaluate("renderProcessAggregateStats(document.getElementById('stats'),'1 步','input=1')")
    page.evaluate("() => new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))")
    # Inspect actual style work rather than a machine-dependent duration/FPS limit.
    # Broad :has(...) descendant rules previously invalidated both chat ancestors
    # whenever streaming rebuilt the stats spans, revisiting all history nodes.
    cdp = page.context.new_cdp_session(page)
    events = []
    complete = []
    cdp.on("Tracing.dataCollected", lambda data: events.extend(data["value"]))
    cdp.on("Tracing.tracingComplete", lambda data: complete.append(True))
    cdp.send("Tracing.start", {
        "categories": "devtools.timeline,disabled-by-default-devtools.timeline.invalidationTracking",
        "transferMode": "ReportEvents",
    })
    try:
        page.evaluate("""async () => {
          for(let i=0;i<3;i++) {
            renderProcessAggregateStats(document.getElementById('stats'),(i+2)+' 步','input='+i);
            document.getElementById('stats').offsetHeight;
            await new Promise(resolve=>requestAnimationFrame(resolve));
          }
        }""")
    finally:
        cdp.send("Tracing.end")
        for _ in range(100):
            if complete:
                break
            page.wait_for_timeout(20)
        cdp.detach()
    assert complete, "Browser did not finish the style-work trace"
    resolved = [event for event in events if event["name"] == "StyleResolver::ResolveStyle"]
    assert resolved, "Browser did not report style resolution work"
    assert len(resolved) < 100, f"Stats updates resolved {len(resolved)} styles across unrelated history"
