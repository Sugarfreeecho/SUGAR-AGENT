"""Render the real shell to catch text scaling, clipping and composer collisions."""
import base64
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api")
from tests.test_llm_stream_window_geometry import browser_page

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def typography_page(browser_page):
    page = browser_page
    styles = "\n".join((ROOT / path).read_text(encoding="utf-8") for path in (
        "frontend/src/styles/app.css", "frontend/src/styles/dock.css",
        "plugins/session-todo/web/session-panel.css",
        "plugins/agent-goal/web/session-panel.css", "plugins/change-review/web/change-review.css",
    ))
    shell = (ROOT / "frontend/src/shell-body.html").read_text(encoding="utf-8")
    layout = (ROOT / "frontend/src/app/modules/layout-panels.js").read_text(encoding="utf-8")
    page.set_content(f"<!doctype html><html><head><meta charset='utf-8'><style>{styles}</style></head><body>{shell}</body></html>")
    page.evaluate("""() => {
      document.querySelector('#sessions-list').innerHTML = `
        <div class="session-item active"><div class="session-item-head"><div class="session-item-main">
        <div class="session-item-title-row"><span class="session-name">中文会话 Mixed title</span></div>
        <div class="session-last-query">一条辅助说明，字号清晰而不抢眼。</div></div></div></div>`;
      document.querySelector('#breadcrumb-text').textContent = '排版与布局验证';
      document.querySelector('#model-profile-current').innerHTML = '<span class="composer-model-current-name">DeepSeek</span><span class="composer-model-current-effort">xhigh</span>';
      document.querySelector('#chat-stream').innerHTML = `
        <div class="msg-wrap msg-wrap--assistant msg-wrap--answer-frame">
          <div class="message assistant"><h2>阅读清晰的中文标题</h2>
          <p>中文与 English 混排内容保持自然的行距。<strong>重点内容</strong>应适度强调。</p>
          <pre><code>const greeting = '你好';</code></pre></div>
        </div>
        <div class="process-aggregate"><div class="process-aggregate-body">
          <div class="feed-item feed--tool"><div class="feed-row"><div class="feed-label">执行工具</div>
          <div class="feed-chunk"><div class="feed-chunk-scroller">第一行结果\n第二行结果</div></div></div></div>
        </div></div>`;
      const samples = document.createElement('div');
      samples.style.cssText = 'position:fixed;left:-10000px;top:0;width:260px';
      samples.innerHTML = `<div class="session-todo-panel-host">
        <div class="workspace-side-panel-title">任务计划</div>
        <div class="chat-todo-plan-stats">已完成 2 / 5</div>
        <div class="workspace-side-panel-item">这是一段需要自然换行的任务说明，确保文字放大后仍然完整显示。</div></div>
        <div class="pubar-narrow-popover" style="position:static;display:block"><div class="pubar-pane">
          <div class="change-review-head"><strong>文件改动</strong><span class="change-review-summary">3 个文件</span></div>
          <span class="change-review-path">src/component.js</span></div></div>`;
      document.body.append(samples);
    }""")
    page.add_script_tag(content=(
        layout[layout.index("function toggleTocPanel()"):layout.index("function updatePanelToggles()")]
        + layout[layout.index("var panelEdgeTabsObserver"):layout.index("var composerSideControlsObserver")]
        + layout[layout.index("var composerSideControlsObserver"):layout.index("initPanelAutoCollapse();")]
        + "\nglobalThis.MyAgentPubar={hasContent:()=>true};"
        + "\ninitComposerSideControlLayout();"
    ))
    yield page
    page.goto("about:blank")


@pytest.mark.parametrize("width,size,theme", [
    (1440, 16, "light"), (1280, 12, "purple"), (1280, 20, "dark"),
    (655, 16, "light"), (655, 20, "dark"), (390, 16, "purple"),
])
def test_shell_text_scales_without_composer_overlap(typography_page, width, size, theme):
    page = typography_page
    page.set_viewport_size({"width": width, "height": 800})
    page.evaluate("""({size,theme}) => {
      document.documentElement.style.fontSize = size + 'px';
      document.documentElement.className = 'theme-' + theme;
      scheduleComposerSideControlLayout();
    }""", {"size": size, "theme": theme})
    page.wait_for_function("document.querySelector('.panel').dataset.composerControlsOverlap !== undefined")
    # Wait through layout observers before measuring the final geometry.
    page.evaluate("() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")
    result = page.evaluate("""() => {
      const style = selector => {const s=getComputedStyle(document.querySelector(selector));return {
        size:parseFloat(s.fontSize),weight:s.fontWeight,line:parseFloat(s.lineHeight),family:s.fontFamily};};
      const rect = selector => {const r=document.querySelector(selector).getBoundingClientRect();return {
        left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:r.width};};
      return {body:style('.message.assistant'),code:style('.message.assistant pre code'),
        caption:style('.session-last-query'),title:style('#breadcrumb-text'),
        input:rect('.input-wrapper'),permission:rect('#permission-mode-trigger'),model:rect('#model-profile-trigger'),
        overflow:document.documentElement.scrollWidth>innerWidth,viewport:innerWidth};
    }""")
    assert result["body"]["size"] == pytest.approx(size)
    assert result["code"]["size"] == pytest.approx(size * 13 / 16)
    assert result["caption"]["size"] == pytest.approx(size * 12 / 16)
    assert result["title"]["weight"] == "700"
    assert "Segoe UI" in result["body"]["family"] and "Microsoft YaHei" in result["body"]["family"]
    assert not result["overflow"]
    for name in ("permission", "model"):
        r = result[name]
        assert r["width"] > 0 and r["left"] >= 0 and r["right"] <= width + 1
        assert r["top"] >= result["input"]["bottom"] or r["right"] <= result["input"]["left"] or r["left"] >= result["input"]["right"]
    assert result["permission"]["right"] <= result["model"]["left"] + 1 or result["permission"]["bottom"] <= result["model"]["top"]


def test_custom_panel_and_trace_type_is_preserved(typography_page):
    page = typography_page
    page.evaluate("document.documentElement.style.fontSize='16px'")
    result = page.evaluate("""() => {
      const style = selector => {const e=document.querySelector(selector),s=getComputedStyle(e);return {
        size:parseFloat(s.fontSize),weight:s.fontWeight,line:parseFloat(s.lineHeight),height:e.getBoundingClientRect().height};};
      return {plan:style('.workspace-side-panel-title'),review:style('.change-review-head strong'),
        planMeta:style('.chat-todo-plan-stats'),reviewMeta:style('.change-review-summary'),
        item:style('.workspace-side-panel-item'),trace:style('.feed-chunk-scroller'),label:style('.feed-label')};
    }""")
    for name in ("plan", "review"):
        assert result[name]["size"] == pytest.approx(9.92)
        assert result[name]["line"] == pytest.approx(12.896)
        assert result[name]["weight"] == "650"
    for name in ("planMeta", "reviewMeta"):
        assert result[name]["size"] == pytest.approx(8.96)
        assert result[name]["line"] == pytest.approx(11.648)
    assert result["item"]["height"] >= result["item"]["line"] * 2
    assert result["trace"]["size"] == pytest.approx(11.84) and result["trace"]["weight"] == "500"
    assert result["trace"]["line"] == pytest.approx(18.944)
    assert result["label"]["size"] == pytest.approx(11.04) and result["label"]["weight"] == "700"


@pytest.mark.parametrize("width,theme,size", [(1440, "light", 16), (2000, "dark", 20), (655, "purple", 16)])
def test_side_panes_fill_available_gutters_and_keep_narrow_width(typography_page, width, theme, size):
    page = typography_page
    page.set_viewport_size({"width": width, "height": 800})
    page.evaluate("""({theme,size}) => {
      document.documentElement.className='theme-'+theme;
      document.documentElement.style.fontSize=size+'px';
      syncComposerSideControlLayout();
      const todo=document.querySelector('#chat-todo-plan');
      todo.classList.add('is-open');
      todo.style.transition='none';
      todo.querySelector('.pubar-panes').innerHTML=`<div class="pubar-pane">
        <div class="change-review-head"><strong>改动审查</strong>
        <span class="change-review-summary"><span class="change-review-stat-added">+279</span>
        <span class="change-review-stat-removed">−0</span></span><button class="change-review-view">查看</button></div>
        <div class="workspace-side-panel-item">核对多行任务说明，确保内容自然换行且可以完整阅读。</div></div>`;
      const toc=document.querySelector('#chat-toc');
      toc.classList.add('is-open');
      toc.style.transition='none';
      toc.querySelector('nav').innerHTML='<a><span class="chat-toc-text">这是一条很长的历史记录，用来验证放大字体后的行高与截断。</span></a>';
      panelManualOverlapTodo=panelManualOverlapToc=innerWidth<=720;
      runPanelAutoCollapseCheck();
    }""", {"theme": theme, "size": size})
    result = page.evaluate("""() => {
      const pane = selector => {const e=document.querySelector(selector),s=getComputedStyle(e),r=e.getBoundingClientRect();return {
        width:r.width,right:r.right,color:s.backgroundColor};};
      const title=document.querySelector('#chat-todo-plan .change-review-head strong');
      const content=document.querySelector('.chat-stream > .msg-wrap').getBoundingClientRect();
      return {todo:{...pane('.chat-todo-plan-inner'),left:document.querySelector('#chat-todo-plan').getBoundingClientRect().left},
        toc:{...pane('.chat-toc-panel'),left:document.querySelector('#chat-toc').getBoundingClientRect().left},
        content:{left:content.left,right:content.right},
        stats:[...document.querySelectorAll('#chat-todo-plan .change-review-summary span')].map(e=>getComputedStyle(e).color),
        titleHeight:title.getBoundingClientRect().height,titleLine:parseFloat(getComputedStyle(title).lineHeight)};
    }""")
    for pane in (result["todo"], result["toc"]):
        if width <= 720:
            assert pane["width"] == pytest.approx(size * 7)
        else:
            assert pane["width"] > size * 9.5
        assert pane["right"] <= width
    if width > 720:
        assert 12 <= result["content"]["left"] - result["todo"]["right"] < 13.5
        assert 12 <= result["toc"]["left"] - result["content"]["right"] < 13.5
    if theme == "light":
        for color in result["stats"]:
            channels = [float(v) / 255 for v in color.removeprefix("rgb(").removesuffix(")").split(",")]
            linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in channels]
            luminance = sum(v * w for v, w in zip(linear, (.2126, .7152, .0722)))
            assert 1.05 / (luminance + .05) >= 4.5


def test_side_panes_resize_recover_and_respect_manual_collapse(typography_page):
    page = typography_page
    page.set_viewport_size({"width": 2000, "height": 800})
    page.evaluate("""() => {
      document.documentElement.style.fontSize='16px';
      syncComposerSideControlLayout();
      document.querySelector('#chat-toc-list').innerHTML='<a>历史记录</a>';
      document.querySelector('#chat-todo-plan').classList.add('is-open');
      document.querySelector('#chat-toc').classList.add('is-open');
      initPanelAutoCollapse();initPanelEdgeTabsLayout();runPanelAutoCollapseCheck();
    }""")
    for width in (2000, 1440, 1100, 655, 1440, 2000):
        page.set_viewport_size({"width": width, "height": 800})
        expected_open = width >= 1440
        page.wait_for_function("""open => {
          const a=document.querySelector('#chat-todo-plan'),b=document.querySelector('#chat-toc');
          if(a.classList.contains('is-open')!==open||b.classList.contains('is-open')!==open)return false;
          if(!open)return a.getBoundingClientRect().width<1&&b.getBoundingClientRect().width<1;
          const c=document.querySelector('.chat-stream > .msg-wrap').getBoundingClientRect();
          return Math.abs(c.left-a.getBoundingClientRect().right-12)<1.5
            && Math.abs(b.getBoundingClientRect().left-c.right-12)<1.5;
        }""", arg=expected_open)
        if expected_open:
            # A settled observer pass must not keep mutating the fitted widths.
            writes = page.evaluate("""() => {
              const stage=document.querySelector('.chat-stage');let writes=0;
              const observer=new MutationObserver(rows=>writes+=rows.length);
              observer.observe(stage,{attributes:true,attributeFilter:['style']});
              for(let i=0;i<5;i++)runPanelAutoCollapseCheck();
              return new Promise(resolve=>requestAnimationFrame(()=>{observer.disconnect();resolve(writes)}));
            }""")
            assert writes == 0
    page.evaluate("toggleTodoPlanPanel()")
    page.set_viewport_size({"width": 2200, "height": 800})
    page.wait_for_function("document.querySelector('#chat-todo-plan').getBoundingClientRect().width<1")
    assert page.evaluate("panelUserCollapsedTodo")
    assert not page.locator('#chat-todo-plan').evaluate("e=>e.classList.contains('is-open')")


@pytest.mark.parametrize("size", [12, 16, 20])
def test_change_review_row_matches_single_line_plan_without_clipping_text(typography_page, size):
    page = typography_page
    result = page.evaluate("""size => {
      document.documentElement.style.fontSize=size+'px';
      const host=document.querySelector('.pubar-narrow-popover .pubar-pane');
      host.innerHTML=`<article class="change-review-file"><div class="change-review-file-head">
        <button class="change-review-file-toggle"><span class="change-review-path">src/example.js</span>
        <span class="change-review-count">+12 −3</span></button></div></article>`;
      const button=host.querySelector('button');
      const path=host.querySelector('.change-review-path');
      const plan=document.createElement('li');plan.className='todo-plan-item workspace-side-panel-item';
      plan.innerHTML='<span class="todo-plan-status-tag"></span><span class="todo-plan-text">单行计划</span>';
      document.querySelector('.session-todo-panel-host').append(plan);
      const row=host.querySelector('article').getBoundingClientRect();
      return {height:row.height,planHeight:plan.getBoundingClientRect().height,
        before:getComputedStyle(button,'::before').content,
        pathSize:parseFloat(getComputedStyle(path).fontSize),
        text:[...button.children].map(e=>{const r=e.getBoundingClientRect();return {
          top:r.top,bottom:r.bottom,rowTop:row.top,rowBottom:row.bottom};})};
    }""", size)
    assert result["height"] == pytest.approx(result["planHeight"], abs=.05)
    assert result["before"] in ("none", "normal", '""')
    assert result["pathSize"] == pytest.approx(size * .68)
    for text in result["text"]:
        assert text["top"] > text["rowTop"] and text["bottom"] < text["rowBottom"]


def test_brand_header_small_text_and_final_card_frame_are_preserved(typography_page):
    page = typography_page
    page.evaluate("document.documentElement.style.fontSize='16px';document.documentElement.className='theme-light'")
    result = page.evaluate("""() => {
      const size=selector=>parseFloat(getComputedStyle(document.querySelector(selector)).fontSize);
      const card=getComputedStyle(document.querySelector('.msg-wrap--answer-frame .message.assistant'));
      return {tagline:size('.sidebar-brand-sub-line--zh'),subtitle:size('#breadcrumb-sub'),context:size('.ctx-wrap'),
        border:card.borderLeftWidth,borderColor:card.borderLeftColor,shadow:card.boxShadow};
    }""")
    assert result["tagline"] == pytest.approx(8.96)
    assert result["subtitle"] == pytest.approx(9.6)
    assert result["context"] == pytest.approx(8.82)
    assert result["border"] == "1px" and result["borderColor"] != "rgba(0, 0, 0, 0)"
    assert result["shadow"] != "none"


def test_session_renderers_use_one_tooltip_and_update_live_text(typography_page):
    page = typography_page
    hover = (ROOT / 'frontend/src/app/modules/toc-todo.js').read_text(encoding='utf-8')
    page.add_script_tag(content="""
      var uiHoverTooltipEl=null,hoverTooltipMoveScheduled=false,uiHoverTipScrollReconcileScheduled=false;
      var uiHoverTipTimer=null,uiHoverTipActiveEl=null,uiHoverTipLastEv=null;
      const UI_HOVER_TIP_DELAY_MS=20;
    """ + hover[:hover.index('function scheduleTocActiveUpdate()')])
    sources = {}
    for name, path in (
        ('plan', 'plugins/session-todo/web/session-panel.js'),
        ('goal', 'plugins/agent-goal/web/session-panel.js'),
        ('review', 'plugins/change-review/web/change-review.js'),
    ):
        source = (ROOT / path).read_text(encoding='utf-8')
        if name == 'review':
            source += '\nexport {renderFile,buildCard,setSummary};'
        sources[name] = 'data:text/javascript;base64,' + base64.b64encode(source.encode()).decode()
    page.evaluate("""async sources => {
      document.documentElement.style.fontSize='16px';
      const pane=document.createElement('section');pane.className='pubar-pane';
      document.querySelector('.pubar-panes').replaceChildren(pane);
      const side=document.querySelector('#chat-todo-plan');side.classList.add('is-open');
      side.style.cssText='left:16px;top:80px;transform:none;--todo-panel-width:280px;max-height:450px';
      const plan=await import(sources.plan),goal=await import(sources.goal),review=await import(sources.review);
      const planHost=document.createElement('div');pane.append(planHost);
      plan.renderSessionPanel({container:planHost,sessionId:'s',item:{pluginId:'plan',id:'plan',fields:[
        {label:'Completed',value:'0'},{label:'Total',value:'1'},
        {label:'Items',rows:[{values:['in_progress','完整的计划说明，即使页签曾经隐藏，也有统一浮窗。']}]}]}});
      const goalHost=document.createElement('div');pane.append(goalHost);
      window.cleanUpGoal=goal.renderSessionPanel({container:goalHost,sessionId:'s',
        item:{pluginId:'goal',id:'goal',fields:[{label:'Objective',value:'完整目标说明'}]},
        request:async()=>({ok:true,json:async()=>({goal:{objective:'完整目标说明',status:'active',
          used_tokens:1200,token_budget:10000,remaining_tokens:8800,elapsed_seconds:4}})})});
      const card=review.buildCard();pane.append(card);
      const row={path:'workspace/全部路径/一个完整的文件名.js',added:12,removed:3};
      review.setSummary(card.querySelector('.change-review-summary'),[row],[],true);
      card.querySelector('.change-review-list').append(review.renderFile(row,{onOpen:()=>window.reviewOpened=true}));
      initUiHoverTips(document);
    }""", sources)
    page.wait_for_function("document.querySelector('.chat-goal-stats-btn').getAttribute('data-ui-tip').includes('1200')")
    samples = [
        ('.todo-plan-text', '完整的计划说明，即使页签曾经隐藏，也有统一浮窗。'),
        ('.todo-plan-status-tag', '进行中'),
        ('.chat-goal-objective', '完整目标说明'),
        ('.change-review-path', 'workspace/全部路径/一个完整的文件名.js'),
    ]
    for selector, text in samples:
        page.locator('#chat-todo-plan ' + selector).hover()
        page.wait_for_function("text=>document.querySelector('#ui-hover-tooltip.is-visible')?.textContent===text", arg=text)
        assert page.locator('#ui-hover-tooltip').count() == 1
    assert page.locator('#chat-todo-plan [title]').count() == 0
    stats = page.locator('.chat-goal-stats-btn')
    stats.hover()
    page.wait_for_function("document.querySelector('#ui-hover-tooltip.is-visible')?.textContent.includes('1200')")
    previous = page.locator('#ui-hover-tooltip').text_content()
    page.wait_for_function("text=>document.querySelector('#ui-hover-tooltip.is-visible')?.textContent!==text", arg=previous)
    assert stats.get_attribute('title') is None
    assert '1200' in stats.get_attribute('data-ui-tip')
    page.locator('.change-review-file-toggle').click()
    assert page.evaluate('reviewOpened')
    page.evaluate('cleanUpGoal()')


@pytest.mark.parametrize('theme', ['light', 'dark', 'purple'])
def test_session_scrollbar_reveals_without_moving_content(typography_page, theme):
    page = typography_page
    page.evaluate("""theme => {
      document.documentElement.className='theme-'+theme;
      const side=document.querySelector('#chat-todo-plan');side.classList.add('is-open');
      side.style.cssText='left:16px;top:80px;transform:none;transition:none;--todo-panel-width:200px;height:200px';
      document.querySelector('.pubar-panes').innerHTML='<section class="pubar-pane">'
        + '<button>可聚焦的条目</button><div style="height:600px">滚动内容</div></section>';
    }""", theme)
    page.mouse.move(1, 1)

    def measure():
        return page.locator('.pubar-panes').evaluate("""e=>({
          color:getComputedStyle(e,'::-webkit-scrollbar-thumb').backgroundColor,
          left:e.firstElementChild.getBoundingClientRect().left,
          width:e.firstElementChild.getBoundingClientRect().width,
          overflow:e.scrollHeight>e.clientHeight})""")

    before = measure()
    assert before['overflow'] and before['color'] == 'rgba(0, 0, 0, 0)'
    page.locator('.pubar-panes').hover()
    revealed = measure()
    assert revealed['color'] != before['color']
    assert (revealed['left'], revealed['width']) == (before['left'], before['width'])
    page.mouse.move(1, 1)
    assert measure()['color'] == before['color']
    page.locator('.pubar-panes button').focus()
    assert measure()['color'] != before['color']
