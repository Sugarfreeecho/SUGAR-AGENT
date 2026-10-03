"""Browser geometry regression checks against an independently rendered full-text oracle."""
import os
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]


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
    scrolling_path = Path(os.environ.get("UI_REVIEW_WINDOW_SOURCE", ROOT / "frontend/src/app/modules/session-scroll-history.js"))
    scrolling = scrolling_path.read_text(encoding="utf-8")
    rendering = (ROOT / "frontend/src/app/modules/message-rendering.js").read_text(encoding="utf-8")
    i18n = (ROOT / "frontend/src/app/modules/i18n.js").read_text(encoding="utf-8")
    css = (ROOT / "frontend/src/styles/app.css").read_text(encoding="utf-8")
    browser_page.set_content(
        f"<style>{css}</style>"
        "<style>.fixture{width:800px;}#oracle{position:absolute;left:-10000px;}</style>"
        "<div class='fixture process-aggregate' id='subject'><div class='process-aggregate-body'>"
        "<div class='feed-item feed--llm'><div class='feed-row'>"
        "<div class='feed-chunk is-streaming'><div class='feed-chunk-scroller' id='sc'></div>"
        "</div></div></div></div></div>"
        "<div class='fixture process-aggregate' id='oracle'><div class='process-aggregate-body'>"
        "<div class='feed-item feed--llm'><div class='feed-row'>"
        "<div class='feed-chunk is-streaming'><div class='feed-chunk-scroller' id='full'></div>"
        "</div></div></div></div></div>"
    )
    browser_page.add_script_tag(content=(
        "var LOG_TRUNCATE_HEAD_LINES=100,LOG_TRUNCATE_TAIL_LINES=100,"
        "LOG_TRUNCATE_HEAD_CHARS=12000,LOG_TRUNCATE_TAIL_CHARS=12000;"
        "var uiLanguage='zh-CN',UI_TRANSLATIONS_EN={},uiI18nRuntimeOriginal=new WeakMap();"
        + i18n[i18n.index("function translateUiString("):i18n.index("function translateUiNode(")]
        + i18n[i18n.index("function setUiRuntimeText("):i18n.index("function isUiRuntimeFinalText(")]
        + i18n[i18n.index("function translateRuntimeUiNodes("):i18n.index("function applyUiLanguage(")]
        + rendering[rendering.index("function trimSurroundingBlankLines("):rendering.index("function reactFeedPhase(")]
        + rendering[rendering.index("function endLlmStreamChunkProjection("):rendering.index("function finalizeActiveLlmReasoningRow(")]
        + scrolling[scrolling.index("function finalizeLlmStreamChunks("):scrolling.index("function writeLlmStreamText(")]
        + scrolling[scrolling.index("function writeLlmStreamText("):scrolling.index("function appendLlmRevealedText(")]
        + "\nfunction flushLlmDeltaText(){}function autoCollapseLlmReasoningRow(){}"
        "function scheduleFeedChunkOverflowRefresh(){}function refreshFeedChunkOverflow(){}"
        "function getFeedItemText(el){return el.textContent;}function reactGenerationForContext(){return 0;}"
        "function queryFeedChunksInCtx(ctx,sel){return ctx.currentProcessGroup.querySelectorAll(sel);}"
        + "\nwindow.sc=document.getElementById('sc');window.full=document.getElementById('full');"
        "window.write=(text)=>{writeLlmStreamText(sc,text,'reasoning');full.textContent=trimSurroundingBlankLines(text);};"
        "window.heights=()=>({actual:sc.getBoundingClientRect().height,expected:full.getBoundingClientRect().height});"
    ))
    yield browser_page


def assert_equal_height(page):
    page.wait_for_function("Math.abs(heights().actual-heights().expected)<1.5", timeout=5000)


def test_single_line_and_large_batch_keep_bounded_dom(page):
    result = page.evaluate("""() => {
      const samples=[];
      for(let n=10000;n<=150000;n+=10000) {
        write('x'.repeat(n));samples.push(sc.textContent.length);
      }
      const first={samples,tail:sc._llmWindow.tailNode.length,head:sc._llmWindow.headText.length};
      write('x'.repeat(300000));
      return {...first,bulk:sc.textContent.length,raw:sc._llmRawText.length,
        suffix:sc._llmRawText.endsWith(sc._llmWindow.tailNode.data)};
    }""")
    assert max(result["samples"]) < 42500
    assert result["head"] <= 12000
    assert result["tail"] <= 30000
    assert result["bulk"] < 42500
    assert result["raw"] == 300000 and result["suffix"]
    assert_equal_height(page)


def test_resize_and_visibility_remeasure_without_new_delta(page):
    page.evaluate("""() => {
      let raw='';
      for(let i=0;i<300;i++){raw+=(i?'\\n':'')+'row'+i+' '+ 'word '.repeat(35);write(raw);}
    }""")
    assert_equal_height(page)
    page.evaluate("subject.style.width='450px';oracle.style.width='450px'")
    assert_equal_height(page)
    page.evaluate("subject.style.width='900px';oracle.style.width='900px'")
    assert_equal_height(page)
    page.evaluate("""() => {
      subject.style.display='none';
      let raw=sc._llmRawText;
      for(let i=300;i<500;i++){raw+='\\nrow'+i+' '+ 'word '.repeat(35);write(raw);}
    }""")
    page.evaluate("subject.style.display=''")
    assert_equal_height(page)
    page.evaluate("sc.style.fontSize='17px';full.style.fontSize='17px'")
    assert_equal_height(page)
    page.evaluate("sc.closest('.feed-chunk').classList.add('expanded');full.closest('.feed-chunk').classList.add('expanded')")
    assert_equal_height(page)


def test_hidden_activation_rebuilds_and_finalization_releases_observer(page):
    page.evaluate("""() => {
      subject.style.display='none';
      write(Array.from({length:300},(_,i)=>'row'+i+' '+ 'word '.repeat(35)).join('\\n'));
    }""")
    page.evaluate("subject.style.display=''")
    assert_equal_height(page)
    result = page.evaluate("""() => {
      const win=sc._llmWindow;let disconnected=false;
      const disconnect=win.resizeObserver.disconnect.bind(win.resizeObserver);
      win.resizeObserver.disconnect=()=>{disconnected=true;disconnect();};
      collapseWindowedLlmText(sc);
      return {disconnected,window:!!sc._llmWindow,children:sc.childNodes.length,
        terminal:sc.textContent===truncateLogTextForUi(trimSurroundingBlankLines(sc._llmRawText))};
    }""")
    assert result == {"disconnected": True, "window": False, "children": 1, "terminal": True}


def test_real_finalization_projects_once_and_keeps_cached_node(page):
    result = page.evaluate("""() => {
      write('x'.repeat(80000));
      const ctx={currentProcessGroup:subject,llm:{}};
      const expected=truncateLogTextForUi(trimSurroundingBlankLines(sc._llmRawText));
      const truncate=truncateLogTextForUi;let projections=0;
      truncateLogTextForUi=text=>{projections++;return truncate(text);};
      finalizeLlmStreamChunks(ctx);
      const node=sc.firstChild;
      finalizeLlmStreamChunks(ctx);
      return {projections,terminal:sc.textContent===expected,window:!!sc._llmWindow,
        sameNode:node===sc.firstChild,cachedNode:sc._llmTextNode===sc.firstChild,
        cachedText:sc._llmRenderedText===sc.textContent};
    }""")
    assert result == {"projections": 1, "terminal": True, "window": False,
                      "sameNode": True, "cachedNode": True, "cachedText": True}


def test_scoped_abort_releases_observer_without_projection(page):
    result = page.evaluate("""() => {
      write('x'.repeat(80000));
      const row=sc.closest('.feed-item'),ctx={currentProcessGroup:subject,llm:{}};
      row.setAttribute('data-llm-live-row','1');row.setAttribute('data-react-iter','1');
      row.setAttribute('data-react-generation','0');row.setAttribute('data-run-id','run-1');
      const win=sc._llmWindow;let disconnected=false,projections=0;
      const disconnect=win.resizeObserver.disconnect.bind(win.resizeObserver);
      win.resizeObserver.disconnect=()=>{disconnected=true;disconnect();};
      const truncate=truncateLogTextForUi;
      truncateLogTextForUi=text=>{projections++;return truncate(text);};
      discardLlmStreamChunks(ctx,{react_iter:2,run_id:'run-1'});
      const otherScopeKept=row.isConnected && sc._llmWindow===win && !disconnected;
      discardLlmStreamChunks(ctx,{react_iter:1,run_id:'run-1'});
      return {otherScopeKept,disconnected,removed:!row.isConnected,
        window:!!sc._llmWindow,projections};
    }""")
    assert result == {"otherScopeKept": True, "disconnected": True,
                      "removed": True, "window": False, "projections": 0}


def test_character_eviction_reuses_layout_metrics(page):
    result = page.evaluate("""() => {
      write('x'.repeat(80000));
      const measure=llmStreamLayoutMetrics;let reads=0;
      llmStreamLayoutMetrics=scroller=>{reads++;return measure(scroller);};
      write(sc._llmRawText+'x'.repeat(113));
      return {reads,suffix:sc._llmRawText.endsWith(sc._llmWindow.tailNode.data)};
    }""")
    assert result == {"reads": 1, "suffix": True}
    assert_equal_height(page)


def test_large_measurement_yields_and_includes_streamed_append(page):
    result = page.evaluate("""() => {
      write(('word 中文 abc '.repeat(8)+'\\n').repeat(4000));
      const win=sc._llmWindow;
      window.measurementHeartbeat=false;
      setTimeout(()=>{window.measurementHeartbeat=!!win.layoutJob;},0);
      write(sc._llmRawText+'appended after measurement started\\n'.repeat(200));
      return {pending:!!win.layoutJob,tail:win.tailNode.length};
    }""")
    assert result["pending"] and result["tail"] <= 30000
    page.wait_for_function("window.measurementHeartbeat")
    assert_equal_height(page)
    assert page.evaluate("!sc._llmWindow.layoutJob && trimmedLlmStreamText(sc._llmRawText).endsWith(sc._llmWindow.tailNode.data)")


def test_pending_measurement_is_cancelled_on_resize_and_finalization(page):
    result = page.evaluate("""() => {
      write(('word 中文 abc '.repeat(8)+'\\n').repeat(4000));
      const job=sc._llmWindow.layoutJob;
      subject.style.width='450px';oracle.style.width='450px';
      refreshLlmStreamWindowGeometry(sc,false);
      const cancelled=!job.box.isConnected && sc._llmWindow.layoutJob!==job;
      const next=sc._llmWindow.layoutJob;
      collapseWindowedLlmText(sc);
      return {cancelled,released:!next.box.isConnected && !next.channel && !sc._llmWindow,
        terminal:sc.textContent===truncateLogTextForUi(trimSurroundingBlankLines(sc._llmRawText))};
    }""")
    assert result == {"cancelled": True, "released": True, "terminal": True}


def test_large_batch_shows_new_tail_before_background_measurement_finishes(page):
    result = page.evaluate("""() => {
      write('x'.repeat(80000));
      const text='x'.repeat(80000)+'new output '.repeat(30000)+'LATEST MARKER';
      write(text);
      return {pending:!!sc._llmWindow.layoutJob,latest:sc._llmWindow.tailNode.data.endsWith('LATEST MARKER'),
        chars:sc._llmWindow.tailNode.length,length:sc._llmWindow.textLength};
    }""")
    assert result["pending"] and result["latest"]
    assert result["chars"] <= 30000 and result["length"] == 410013
    assert_equal_height(page)


def test_million_character_layout_still_matches_full_text_oracle(page):
    page.evaluate("write(('word 中文 abc '.repeat(8)+'\\n').repeat(31000))")
    page.wait_for_function("!sc._llmWindow.layoutJob", timeout=15000)
    assert_equal_height(page)


def test_returning_to_measured_width_reuses_exact_geometry(page):
    page.evaluate("write(('word 中文 abc '.repeat(8)+'\\n').repeat(4000))")
    assert_equal_height(page)
    page.evaluate("subject.style.width='450px';oracle.style.width='450px'")
    assert_equal_height(page)
    result = page.evaluate("""() => {
      const create=createLlmStreamLayoutMeasurement;let measurements=0;
      createLlmStreamLayoutMeasurement=(...args)=>{measurements++;return create(...args);};
      subject.style.width='800px';oracle.style.width='800px';
      refreshLlmStreamWindowGeometry(sc,false);
      return {measurements,pending:!!sc._llmWindow.layoutJob};
    }""")
    assert result == {"measurements": 0, "pending": False}
    assert_equal_height(page)


def test_incremental_trim_preserves_indent_and_trailing_spaces(page):
    assert page.evaluate("""() => {
      const samples=['','  ','\\n \\n','  hello  ','\\n\\t\\n  hello  \\n  \\n',
        '\\r\\n  中🙂\\t\\n\\r\\n','a\\n \\n b  ','\\u00a0\\n x\\n\\u00a0'];
      return samples.every(text=>trimmedLlmStreamText(text)===trimSurroundingBlankLines(text));
    }""")


@pytest.mark.parametrize("multiline", [False, True], ids=["characters", "lines"])
def test_streaming_omission_note_follows_language_without_translating_output(page, multiline):
    result = page.evaluate("""multiline => {
      write(multiline ? Array.from({length:400},()=> '更早 99 轮对话').join('\\n')
        : '更早 99 轮对话'.repeat(10000));
      const win=sc._llmWindow,head=win.headEl.textContent,tail=win.tailNode.data;
      const chinese=win.noteEl.textContent;
      uiLanguage='en';translateRuntimeUiNodes(subject);
      const english=win.noteEl.textContent;
      write(sc._llmRawText+(multiline ? '\\n更早 99 轮对话' : '更早 99 轮对话'));
      const updateEnglish=win.noteEl.textContent;
      uiLanguage='zh-CN';translateRuntimeUiNodes(subject);
      return {chinese,english,updateEnglish,restored:win.noteEl.textContent,
        outputKept:win.headEl.textContent===head && sc._llmRawText.endsWith(win.tailNode.data)
          && !win.headEl.textContent.includes('Earlier') && !win.tailNode.data.includes('Earlier')};
    }""", multiline)
    assert "输出中" in result["chinese"] and "输出中" in result["restored"]
    assert "omitted (streaming)" in result["english"]
    assert "omitted (streaming)" in result["updateEnglish"]
    assert result["outputKept"] is True


def test_character_eviction_preserves_visible_visual_line_position(page):
    result = page.evaluate("""() => {
      write('x'.repeat(80000));
      let maxDrift=0;
      for(let i=0;i<40;i++) {
        const win=sc._llmWindow, index=win.tailNode.length-1000;
        const rawIndex=win.tailStart+index;
        const rect=(node,offset)=>{const r=document.createRange();r.setStart(node,offset);r.setEnd(node,offset+1);return r.getBoundingClientRect();};
        const before=rect(win.tailNode,index);
        write(sc._llmRawText+'x'.repeat(113));
        const next=sc._llmWindow;
        const after=rect(next.tailNode,rawIndex-next.tailStart);
        maxDrift=Math.max(maxDrift,Math.abs(after.top-before.top));
      }
      return {maxDrift,dom:sc.textContent.length};
    }""")
    assert result["maxDrift"] < 1.5
    assert result["dom"] < 42500
    assert_equal_height(page)


@pytest.mark.parametrize("text", [
    ("很长的思考段落🙂 e\u0301 word\t" * 8000),
    "\n".join("第" + str(i) + "行 " + "long text " * 100 for i in range(350)),
], ids=["mixed-single-line", "long-logical-lines"])
def test_mixed_text_large_batch_and_collapsed_row_restore(page, text):
    page.evaluate("write", text)
    assert_equal_height(page)
    bounds = page.evaluate("({head:sc._llmWindow.headText.length,tail:sc._llmWindow.tailNode.length})")
    assert bounds["head"] <= 12000 and bounds["tail"] <= 30000
    page.evaluate("sc.closest('.feed-item').classList.add('is-collapsed')")
    page.evaluate("write(sc._llmRawText+' appended🙂')")
    page.evaluate("sc.closest('.feed-item').classList.remove('is-collapsed')")
    assert_equal_height(page)
