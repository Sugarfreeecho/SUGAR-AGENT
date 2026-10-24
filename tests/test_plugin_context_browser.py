from pathlib import Path

from tests.test_llm_stream_full_text_browser import browser_page, page, function_source


def test_context_disclosure_replay_deduplication_and_plain_text(browser_page):
    page = browser_page
    root = Path(__file__).resolve().parents[1]
    source = (root / 'frontend/src/app/modules/event-dispatch.js').read_text(encoding='utf-8')
    page.set_content('<html lang="zh-CN"><body><div id="stream"></div></body></html>')
    page.add_style_tag(content=(root / 'frontend/src/styles/app.css').read_text(encoding='utf-8'))
    page.add_script_tag(content='''function appendLog(ctx,text,type){
        const row=document.createElement('div');row.className='feed-item feed--'+type;
        row.innerHTML='<span class="feed-label"></span><div class="feed-chunk-scroller"></div>';
        ctx.stream.appendChild(row);return row.lastElementChild;
    }; window.ctx={stream:document.getElementById('stream')};'''
        + function_source(source, 'renderPluginContextInjection'))
    event = {'type':'context_injection','runtime_seq':42,'content':'<img src=x onerror=alert(1)>\nActual model text',
             'context': {'sections':[{'plugin_id':'demo','plugin_name':'资料插件','title':'<Current>',
                                      'stale':True,'truncated':True}], 'estimated_tokens':75}}
    page.evaluate('event=>{renderPluginContextInjection(ctx,event,"s");renderPluginContextInjection(ctx,event,"s")}', event)
    assert page.locator('.plugin-context-disclosure').count() == 1
    details = page.locator('.plugin-context-disclosure')
    assert details.locator('pre').is_hidden()
    assert details.locator('summary').inner_text().find('资料插件 · <Current>') >= 0
    details.locator('summary').click()
    assert details.locator('pre').inner_text() == event['content']
    assert details.locator('img').count() == 0
    assert '沿用上次状态' in details.locator('.plugin-context-notice').inner_text()
    assert '已截断' in details.locator('.plugin-context-notice').inner_text()
    page.evaluate('event=>renderPluginContextInjection(ctx,event,"s")',
                  {'type':'context_injection','runtime_seq':43,'content':'Cleared',
                   'context':{'cleared':True,'sections':[],'estimated_tokens':4}})
    assert page.locator('.plugin-context-disclosure').count() == 2
    assert '已清除' in page.locator('summary').last.inner_text()


def test_real_feed_row_has_one_disclosure_and_no_generic_text_fold(page):
    root = Path(__file__).resolve().parents[1]
    source = (root / 'frontend/src/app/modules/event-dispatch.js').read_text(encoding='utf-8')
    page.add_script_tag(content=function_source(source, 'renderPluginContextInjection'))
    page.evaluate(r"""() => {
      document.documentElement.lang='zh-CN';document.getElementById('body').replaceChildren();
      renderPluginContextInjection(ctx,{type:'context_injection',runtime_seq:44,
        content:'实际发送的资料\n'.repeat(100),
        context:{sections:[{plugin_name:'工作区资料',title:'项目约定'}],estimated_tokens:800}},'s');
    }""")
    row = page.locator('#body .feed--context-injection')
    assert row.count() == 1 and row.locator('.feed-label').count() == 0
    row.locator('summary').click()
    assert row.locator('pre').is_visible()
    assert row.bounding_box()['height'] > 100
    assert not row.locator('.feed-chunk').evaluate("el=>el.classList.contains('expanded')")
    row.locator('summary').click()
    assert row.locator('pre').is_hidden()
