"""Exercise context actions, focus and stale targets in a real browser."""
import os
import json
import mimetypes
from pathlib import Path
from urllib.parse import urlsplit

import pytest

playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def context_browser():
    with playwright.sync_playwright() as runtime:
        browser = runtime.chromium.launch(headless=True, **({"channel": "msedge"} if os.name == "nt" else {}))
        yield browser
        browser.close()


@pytest.fixture
def page(context_browser):
    page = context_browser.new_page(viewport={"width": 1000, "height": 760})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.route("http://context.test/", lambda route: route.fulfill(status=200, content_type="text/html", body="<html></html>"))
    page.goto("http://context.test/")
    css = "\n".join((ROOT / f"frontend/src/styles/{name}.css").read_text(encoding="utf-8")
                    for name in ("app", "dock", "context-menus"))
    page.set_content(f'<!doctype html><html><head><base href="http://context.test/"><style>{css}</style></head><body></body></html>')
    page.add_script_tag(content="""
      var currentSessionId='active', uiLanguage='zh-CN', running=false;
      var actions=[], copied=[], feedback=[], messageRawMarkdown=new WeakMap();
      Object.defineProperty(navigator, 'clipboard', {value:{writeText:async text=>copied.push(text)}});
      function translateUiString(text){return text==='右键菜单'?'Context menu':text;}
      function showOpenFileFeedback(text){feedback.push(text);}
      function showUiAlert(error){throw new Error(error.message);}
      function closeAllSessionMenus(){}
      function closeAllMessageCopyPopovers(){}
      function isSessionRunning(){return running;}
      function findSessionForActions(id){return {id,name:'fixture',pinned:false};}
      function syncSessionMenuLabels(){}
      function switchSession(id){actions.push(['open',id]);}
      function getActiveWorkDir(){return 'D:\\\\Projects\\\\Workspace';}
      function dockRightRelPath(path){return path;}
      var DOCK_RIGHT_FILE_PREFIX='myagent-resource://file/';
      function dockRightOpenResource(address){actions.push(['preview',address]);}
      function getFeedItemText(row){return row.querySelector('.feed-chunk-scroller').textContent;}
      function toggleTocPanel(){actions.push(['toc']);}
      function toggleTodoPlanPanel(){actions.push(['todo']);}
      function scrollToBottom(){actions.push(['bottom']);}
      function createNewSession(){actions.push(['new']);}
      function startNewSessionInCurrentDir(){actions.push(['new-workspace']);}
      function loadSessions(){actions.push(['refresh']);}
      function applyMessageCopyOption(node,role,option){actions.push(['export',option]);}
      document.addEventListener('click',e=>{if(e.target.dataset.testAction)actions.push([e.target.dataset.testAction]);});
    """)
    rendering = (ROOT / "frontend/src/app/modules/message-rendering.js").read_text(encoding="utf-8")
    # The existing clipboard action is reused as-is, including its raw Markdown map.
    start = rendering.index("function copyMessageText(")
    end = rendering.index("function buildFinalExportFilename(")
    page.add_script_tag(content="function showCopyFeedback(){feedback.push('copied');}\n" + rendering[start:end])
    page.add_script_tag(content=(ROOT / "frontend/src/app/modules/context-menus.js").read_text(encoding="utf-8"))
    # File actions use the same session-aware URL builder as the application.
    page.add_script_tag(content=(ROOT / "frontend/src/app/config.js").read_text(encoding="utf-8").replace("export function", "function"))
    page.evaluate("value => {window.__WORK_DIR__=value; readRuntimeConfig(window)}", r"D:\Projects\Workspace")
    page.evaluate("() => new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))")
    yield page
    assert not errors, errors
    page.close()


def populate(page, html):
    page.evaluate("html => document.body.innerHTML=html", html)


def menu(page):
    return page.locator(".ui-context-menu")


def choose(page, label):
    menu(page).get_by_role("menuitem", name=label, exact=True).click()


def message(page):
    populate(page, '''<div class="msg-wrap msg-wrap--assistant"><div class="message assistant">Rendered answer</div>
      <div class="msg-toolbar"><button class="msg-tb" data-act="delete" data-test-action="delete">删除</button>
      <button class="msg-tb" data-act="branch" data-test-action="branch">分支</button></div></div>''')
    page.evaluate("messageRawMarkdown.set(document.querySelector('.msg-wrap'),'**Raw answer**')")


def test_session_context_does_not_select_background_session(page):
    populate(page, '''<div class="session-item" data-session-id="background">Background<div class="session-more-wrap">
      <div class="session-more-menu"><button data-test-action="rename">重命名</button>
      <button data-test-action="archive">归档会话</button><button data-test-action="delete">删除会话</button></div></div></div>''')
    page.locator(".session-item").click(button="right")
    assert page.evaluate("actions") == []
    choose(page, "重命名")
    assert page.evaluate("actions") == [["rename"]]
    page.locator(".session-item").click(button="right")
    choose(page, "复制会话 ID")
    assert page.evaluate("copied") == ["background"]


@pytest.mark.parametrize("theme", ["light", "dark", "purple"])
def test_open_sidebar_menu_children_remain_clickable_outside_row_hover(page, theme):
    populate(page, '''
      <div class="session-item" style="position:absolute;left:30px;top:60px;width:280px;height:50px">
        Session<div class="session-item-actions"><div class="session-more-wrap is-open">
          <button class="session-more-btn">More</button><div class="session-more-menu">
            <button id="legacy"><span>Legacy action</span></button></div></div></div></div>
      <div class="session-item" style="position:absolute;left:30px;top:260px;width:280px;height:50px">
        Session<div class="session-item-actions"><div class="sidebar-popup is-open">
          <button class="session-row-icon">More</button><div class="sidebar-popup-menu">
            <button id="popup"><span>Popup action</span></button></div></div></div></div>
      <div class="session-group" style="position:absolute;left:30px;top:460px;width:280px">
        <div class="session-group-head">Group<div class="session-group-actions">
          <div class="sidebar-popup session-group-popup is-open"><button class="session-row-icon">More</button>
            <div class="sidebar-popup-menu session-group-menu">
              <button id="group"><span>Group action</span></button></div></div></div></div></div>''')
    page.evaluate("""theme => {
      document.documentElement.className='theme-'+theme;
      for(const id of ['legacy','popup','group'])document.getElementById(id).addEventListener('click',()=>actions.push(id));
    }""", theme)
    page.mouse.move(900, 700)
    for name in ("legacy", "popup", "group"):
        target = page.locator(f"#{name} span")
        assert target.evaluate("e=>getComputedStyle(e).pointerEvents") == "auto"
        target.click()  # Normal browser hit testing, including the nested text node.
    assert page.evaluate("actions") == ["legacy", "popup", "group"]
    page.evaluate("""() => {
      document.activeElement.blur();
      document.querySelectorAll('.is-open').forEach(e=>e.classList.remove('is-open'));
    }""")
    page.mouse.move(900, 700)
    for name in ("legacy", "popup", "group"):
        page.locator(f"#{name} span").wait_for(state="hidden")


def test_answer_copy_uses_markdown_and_generation_disables_history_mutation(page):
    message(page)
    page.evaluate("running=true")
    page.locator(".message").click(button="right")
    assert menu(page).get_by_role("menuitem", name="删除本条及之后的对话").is_disabled()
    assert menu(page).get_by_role("menuitem", name="分支", exact=True).is_enabled()
    choose(page, "复制消息")
    assert page.evaluate("copied") == ["**Raw answer**"]
    page.locator(".message").click(button="right")
    choose(page, "导出文本")
    assert page.evaluate("actions") == [["export", "text"]]


def test_selection_copy_is_captured_before_menu_takes_focus(page):
    message(page)
    page.evaluate("""() => {const range=document.createRange();range.selectNodeContents(document.querySelector('.message'));
      const selection=getSelection();selection.removeAllRanges();selection.addRange(range);
      document.querySelector('.message').dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,cancelable:true,clientX:200,clientY:100}));} """)
    choose(page, "复制选中文本")
    assert page.evaluate("copied") == ["Rendered answer"]


def test_file_actions_use_relative_endpoint_and_exact_path(page):
    populate(page, '''<button class="dock-files-row" data-rel="folder/a.txt" title="D:\\Projects\\Workspace\\folder\\a.txt">a.txt</button>''')
    page.evaluate("document.querySelector('.dock-files-row').addEventListener('click',()=>dockRightOpenResource(DOCK_RIGHT_FILE_PREFIX+encodeURIComponent('folder/a.txt')))")
    requests = []
    page.route("**/api/open-workspace-*", lambda route: (requests.append(route.request.url),
               route.fulfill(status=200, content_type="application/json", body='{"ok":true}')))
    page.locator("button").click(button="right")
    choose(page, "复制路径")
    assert page.evaluate("copied[0]") == "D:\\Projects\\Workspace\\folder\\a.txt"
    page.locator(".dock-files-row").click(button="right")
    choose(page, "预览文件")
    assert page.evaluate("actions[0][1]") == "myagent-resource://file/folder%2Fa.txt"
    page.locator(".dock-files-row").click(button="right")
    choose(page, "打开文件目录")
    page.wait_for_function("feedback.includes('已打开文件目录')")
    assert requests == ["http://context.test/api/open-workspace-dir?session_id=active&rel=folder%2Fa.txt"]


def test_desktop_file_actions_use_native_bridge_without_background_open(page):
    populate(page, '<button class="dock-files-row" data-rel="folder/a.txt">a.txt</button>')
    requests = []
    page.route("**/api/open-workspace-*", lambda route: (requests.append(route.request.url),
               route.fulfill(status=500, content_type="application/json", body='{"ok":false}')))
    page.evaluate("""() => {
      window.nativeOpens = [];
      window.sugarAgentDesktop = {openLocalPath: async request => {
        nativeOpens.push(request); return {ok:true};
      }};
    }""")
    page.locator(".dock-files-row").click(button="right")
    choose(page, "打开文件目录")
    page.wait_for_function("feedback.includes('已打开文件目录')")
    assert page.evaluate("nativeOpens") == [{"session_id": "active", "rel": "folder/a.txt", "directory": True}]
    page.locator(".dock-files-row").click(button="right")
    choose(page, "在系统应用中打开")
    page.wait_for_function("nativeOpens.length===2")
    assert page.evaluate("nativeOpens[1].directory") is False
    assert requests == []


def test_document_and_change_actions_reuse_existing_buttons(page):
    populate(page, '''<div class="dock-doc" data-dock-file-rel="folder/a.md"><pre class="dock-doc-text"># Source</pre>
      <button class="dock-doc-refresh" data-test-action="doc-refresh">Refresh</button>
      <button class="dock-doc-source-toggle" data-test-action="source">查看源码</button></div>
      <article class="dock-change" data-dock-change-path="a.md"><span class="dock-change-name">a.md</span>
      <button class="dock-change-toggle" data-test-action="diff-toggle">Diff</button>
      <button class="dock-change-action" disabled>撤销</button></article>''')
    page.locator(".dock-doc-text").click(button="right")
    choose(page, "刷新文件")
    assert page.evaluate("actions") == [["doc-refresh"]]
    page.locator(".dock-doc-text").click(button="right")
    choose(page, "复制路径")
    assert page.evaluate("copied[0]") == "D:\\Projects\\Workspace\\folder\\a.md"
    page.locator(".dock-doc").evaluate("e=>e.remove()")
    page.locator(".dock-change-name").click(button="right")
    assert menu(page).get_by_role("menuitem", name="撤销", exact=True).is_disabled()
    assert menu(page).get_by_role("menuitem", name="复制差分").is_disabled()
    choose(page, "展开 / 折叠差分")
    assert page.evaluate("actions.at(-1)") == ["diff-toggle"]


def test_process_copy_includes_hidden_detail(page):
    populate(page, '''<div class="process-aggregate is-collapsed"><button class="process-aggregate-top">Execution</button>
      <div class="process-aggregate-body" hidden><div class="feed-item"><div class="feed-chunk-scroller">Hidden output</div></div></div></div>''')
    page.locator(".process-aggregate-top").click(button="right")
    assert menu(page).count()
    choose(page, "复制执行内容")
    assert page.evaluate("copied") == ["Hidden output"]


def test_keyboard_menu_skips_disabled_and_escape_does_not_close_outer_dialog(page):
    populate(page, '<button id="anchor">Anchor</button><section role="dialog">Outer</section>')
    page.evaluate("""() => {MyAgentContextMenu.bind(document.querySelector('#anchor'),()=>[
      {label:'First',action:()=>actions.push(['first'])}, {label:'Disabled',disabled:true,action:()=>actions.push(['bad'])},
      {label:'Last',action:()=>actions.push(['last'])}]);
      document.addEventListener('keydown', e=>{if(e.key==='Escape')actions.push(['outer-escape']);});}""")
    page.locator("#anchor").focus()
    page.keyboard.press("Shift+F10")
    assert page.evaluate("document.activeElement.textContent") == "First"
    page.keyboard.press("ArrowDown")
    assert page.evaluate("document.activeElement.textContent") == "Last"
    page.keyboard.press("Escape")
    assert menu(page).count() == 0
    assert page.evaluate("document.activeElement.id") == "anchor"
    assert page.evaluate("actions") == []


@pytest.mark.parametrize("theme,size,width,height", [("light", 16, 1000, 760), ("dark", 20, 360, 300), ("purple", 16, 600, 450)])
def test_menu_clamps_to_viewport_and_scrolls_when_tall(page, theme, size, width, height):
    page.set_viewport_size({"width": width, "height": height})
    page.evaluate("() => new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))")
    page.evaluate("""({theme,size})=>{document.documentElement.className='theme-'+theme;document.documentElement.style.fontSize=size+'px';
      MyAgentContextMenu.open({type:'contextmenu',clientX:innerWidth-1,clientY:innerHeight-1,preventDefault(){},stopPropagation(){}},
        Array.from({length:20},(_,i)=>({label:'Action '+i,action(){}})),document.body);}""", {"theme": theme, "size": size})
    result = menu(page).evaluate("e=>{const r=e.getBoundingClientRect();return {left:r.left,top:r.top,right:r.right,bottom:r.bottom,scroll:e.scrollHeight>e.clientHeight};}")
    assert 0 <= result["left"] < result["right"] <= width
    assert 0 <= result["top"] < result["bottom"] <= height
    if height == 300:
        assert result["scroll"]


@pytest.mark.parametrize("owner", ["message", "sidebar"])
def test_streaming_auto_scroll_keeps_menu_open_and_actions_work(page, owner):
    populate(page, '''<div class="session-item" data-session-id="background"
      style="position:fixed;left:0;top:0;width:220px">Background session</div>
      <div class="chat-container" id="chat-container"
      style="position:fixed;left:250px;top:180px;width:500px;height:160px;overflow:auto">
        <div style="height:600px">Earlier messages</div>
        <div class="msg-wrap msg-wrap--assistant"><div class="message assistant" style="white-space:pre-wrap">Streaming answer</div></div>
      </div>
      <div id="stream-log" style="position:fixed;left:250px;top:380px;width:500px;height:40px;overflow:auto">
        <pre id="stream-log-content" style="white-space:pre-wrap">Execution output</pre>
      </div>''')
    page.evaluate("""() => {
      running=true;
      document.querySelector('#chat-container').scrollTop=10000;
    }""")
    page.locator(".message" if owner == "message" else ".session-item").click(button="right")
    initial_scroll = page.locator("#chat-container").evaluate("e=>e.scrollTop")
    page.evaluate("""async () => {
      const chat=document.querySelector('#chat-container');
      const message=document.querySelector('.message');
      const log=document.querySelector('#stream-log');
      for (let i=0;i<25;i++) {
        message.textContent+='\\n流式输出 '+i;
        messageRawMarkdown.set(message.closest('.msg-wrap'),message.textContent);
        document.querySelector('#stream-log-content').textContent+='\\n执行输出 '+i;
        chat.scrollTop=chat.scrollHeight;
        log.scrollTop=log.scrollHeight;
        await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
        if (!document.querySelector('.ui-context-menu')) throw new Error('Streaming dismissed menu at token '+i);
      }
    }""")
    assert page.locator("#chat-container").evaluate("e=>e.scrollTop") > initial_scroll
    assert menu(page).is_visible()
    choose(page, "复制消息" if owner == "message" else "复制会话 ID")
    if owner == "message":
        assert "流式输出 24" in page.evaluate("copied[0]")
    else:
        assert page.evaluate("copied[0]") == "background"


def test_menu_dismisses_when_owner_detaches_or_user_scrolls(page):
    message(page)
    page.locator(".message").click(button="right")
    page.evaluate("document.querySelector('.msg-wrap').remove()")
    assert menu(page).count() == 0
    message(page)
    page.evaluate("""() => {const wrap=document.querySelector('.msg-wrap');wrap.style.cssText='height:40px;overflow:auto';
      wrap.querySelector('.message').style.height='200px';}""")
    page.locator(".message").click(button="right")
    bounds = page.locator(".message").bounding_box()
    page.mouse.move(bounds["x"] + 8, bounds["y"] + 8)
    page.mouse.wheel(0, 40)
    page.wait_for_function("!document.querySelector('.ui-context-menu')")
    assert menu(page).count() == 0


@pytest.mark.parametrize("input_type", ["touch", "keyboard", "pointer"])
def test_user_scroll_input_outside_menu_still_dismisses_it(page, input_type):
    message(page)
    page.locator(".message").click(button="right")
    if input_type == "touch":
        page.locator(".message").dispatch_event("touchmove")
    elif input_type == "keyboard":
        page.locator('.msg-tb[data-act="branch"]').focus()
        page.keyboard.press("PageDown")
    else:
        page.mouse.click(900, 700)  # Also covers the pointer press used to drag a scrollbar.
    assert menu(page).count() == 0


def test_scrolling_inside_menu_keeps_it_open(page):
    page.evaluate("""() => {
      MyAgentContextMenu.open({type:'contextmenu',clientX:20,clientY:20,preventDefault(){},stopPropagation(){}},
        Array.from({length:60},(_,i)=>({label:'Action '+i,action(){}})),document.body);
    }""")
    bounds = menu(page).bounding_box()
    page.mouse.move(bounds["x"] + 40, bounds["y"] + 50)
    page.mouse.wheel(0, 200)
    page.wait_for_function("document.querySelector('.ui-context-menu').scrollTop > 0")
    assert menu(page).is_visible()


def test_editable_fields_keep_native_menu_and_provider_can_override_xterm_textarea(page):
    populate(page, '<textarea id="composer">Draft</textarea><div id="terminal"><textarea id="xterm"></textarea></div>')
    assert page.evaluate("document.querySelector('#composer').dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,cancelable:true}))")
    assert menu(page).count() == 0
    page.evaluate("() => {MyAgentContextMenu.bind(document.querySelector('#terminal'),()=>[{label:'Paste terminal',action(){}}]);}")
    assert not page.evaluate("document.querySelector('#xterm').dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,cancelable:true}))")
    assert menu(page).get_by_role("menuitem", name="Paste terminal").is_visible()


def test_dock_context_menu_preserves_protected_tabs_and_offers_float(page):
    files = [f"dock/engine/{name}.js" for name in ("types", "tree", "constraints", "geometry", "operations", "planner", "sequence", "controller")]
    files += [f"dock/renderer/{name}.js" for name in ("gesture", "measure", "dock-surface", "float-layer")]
    source = "\n".join((ROOT / "frontend/src/app/modules" / file).read_text(encoding="utf-8") for file in files)
    page.add_script_tag(content=source + """
      var host=document.createElement('div');host.style.cssText='width:800px;height:500px';document.body.append(host);
      var state=dockCreateInitialState(dockCreateMinter(0),id=>({id,kind:'document',contentId:'a',title:'A'}));
      var pane=state.nodes[state.rootId], first=pane.activeTabId;
      state.expanded=true;
      for(const id of ['extra-b','extra-c']){state.tabs[id]={id,kind:'document',contentId:id,title:id};pane.tabs.push(id);}
      var view=new DockSurfaceView({root:host,renderTab:()=>document.createElement('div'),canCloseTab:id=>id!==first,
        intents:{duplicateTab:id=>actions.push(['duplicate',id]),closeTab:id=>actions.push(['close',id]),
          addTab:id=>actions.push(['add',id]),splitPane:id=>actions.push(['split',id]),floatTab:id=>actions.push(['float',id])}});
      view.mount();view.sync(state);view.splitBlock=()=>undefined;
    """)
    page.locator('[data-dock-tab="extra-b"]').click(button="right")
    choose(page, "关闭其他标签")
    assert page.evaluate("actions") == [["close", "extra-c"]]
    page.locator('[data-dock-tab="extra-b"]').focus()
    page.keyboard.press("Shift+F10")
    choose(page, "移至浮动窗口")
    assert page.evaluate("actions.at(-1)") == ["float", "extra-b"]
    page.evaluate("""() => {
      MyAgentContextMenu.close(false);
      const floated=dockReplay(state,dockPlanFloatTab(state,dockCreateMinter(100),'extra-b').ops);
      window.floats=new DockFloatLayerView({root:document.body,renderTab:()=>document.createElement('div'),
        intents:{unfloatPane:id=>actions.push(['dock',id]),closeTab:id=>actions.push(['close',id]),raiseFloat(){}}});
      floats.mount();floats.sync(floated);
    }""")
    page.locator(".dock-float-header").click(button="right")
    choose(page, "放回主区")
    assert page.evaluate("actions.at(-1)[0]") == "dock"


def test_user_terminal_menu_uses_real_xterm_copy_paste_and_cleanup(page):
    page.add_style_tag(path=str(ROOT / "plugins/execution-tools/web/session-panel.css"))
    page.add_style_tag(path=str(ROOT / "frontend/node_modules/@xterm/xterm/css/xterm.css"))
    page.add_script_tag(path=str(ROOT / "frontend/node_modules/@xterm/xterm/lib/xterm.js"))
    page.evaluate("""() => {
      globalThis.MyAgentTerminal={Terminal:class extends Terminal{
        constructor(options){super(options);window.activeTerminal=this;}
      },FitAddon:class{activate(){}fit(){}dispose(){}}};
      globalThis.EventSource=class {
        constructor(){queueMicrotask(()=>this.onmessage?.({data:JSON.stringify({status:'running',text:'Terminal output\\r\\n',offset:17})}));}
        close(){}
      };
      navigator.clipboard.readText=async ()=>'fixture input';
      crypto.randomUUID=()=> 'fixture-connection';
      const container=document.createElement('div');document.body.append(container);
      const user={actor:'user',id:'user-terminal',name:'Fixture',status:'running'};
      window.executionContext={container,sessionId:'active',request:async(url,options)=>{
        if(url.endsWith('/input'))actions.push(['input',JSON.parse(options.body).text]);
        return {ok:true,json:async()=>url.endsWith('/jobs')?{jobs:[]}:url.endsWith('/terminals')?{user:[user],model:[]}
          :url==='/api/computer-use'?{enabled:false,provider:'native',mcp_servers:[],tool_count:0,state:'disabled'}:{ok:true}};
      }};
    }""")
    source = (ROOT / "plugins/execution-tools/web/session-panel.js").read_text(encoding="utf-8")
    page.add_script_tag(content=source.replace("export function renderSessionPanel", "function renderSessionPanel")
                        + "\nwindow.disposeExecution=renderSessionPanel(executionContext);")
    page.locator(".execution-row").get_by_role("button", name="连接", exact=True).click()
    page.wait_for_function("window.activeTerminal && activeTerminal.buffer.active.getLine(0).translateToString().includes('Terminal output')")
    page.evaluate("activeTerminal.selectAll()")
    page.locator(".xterm-screen").click(button="right")
    choose(page, "复制选中文本")
    assert "Terminal output" in page.evaluate("copied[0]")
    page.locator(".xterm-screen").click(button="right")
    choose(page, "粘贴")
    page.wait_for_function("actions.some(item=>item[0]==='input')")
    assert page.evaluate("actions.find(item=>item[0]==='input')[1]") == "fixture input"
    page.locator(".xterm-screen").click(button="right")
    choose(page, "关闭视图")
    assert page.locator(".execution-dialog").count() == 0
    page.evaluate("disposeExecution({})")


def test_built_workbench_bootstraps_and_opens_existing_rename_dialog(context_browser):
    page = context_browser.new_page(viewport={"width": 1440, "height": 900})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    dist = ROOT / "app/templates/dist"
    session = {"id": "fixture", "name": "Fixture session", "work_dir": "D:/Fixture", "status": "completed",
               "created_at": "2026-10-11T00:00:00Z", "updated_at": "2026-10-11T00:00:00Z"}

    def route(request):
        path = urlsplit(request.request.url).path
        asset = dist / ("index.html" if path == "/" else path.lstrip("/"))
        if path == "/" or path.startswith("/assets/"):
            request.fulfill(status=200, content_type=mimetypes.guess_type(str(asset))[0] or "application/octet-stream", body=asset.read_bytes())
        else:
            payload = {"ok": True, "sessions": [session], "profiles": [], "events": [], "messages": [],
                       "items": [], "slots": [], "contributions": [], "pending": [], "mode": "ask_for_approval"}
            request.fulfill(status=200, content_type="application/json", body=json.dumps(payload))

    page.route("**/*", route)
    try:
        page.goto("http://workbench.test/")
        page.locator('.session-item[data-session-id="fixture"]').wait_for()
        page.locator('.session-item[data-session-id="fixture"]').click(button="right")
        choose(page, "重命名")
        page.locator("#ui-modal-input").wait_for(state="visible")
        assert page.locator("#ui-modal-input").input_value() == "Fixture session"
        page.locator("#ui-modal-cancel").click()
        assert not errors, errors
    finally:
        page.close()


def test_built_workbench_file_tree_text_and_html_assets_keep_custom_directory(context_browser):
    page = context_browser.new_page(viewport={"width": 1440, "height": 900})
    errors, requests = [], []
    page.on("pageerror", lambda error: errors.append(str(error)))
    dist = ROOT / "app/templates/dist"
    session = {"id": "fixture", "name": "Custom project", "work_dir": "D:/Custom Project",
               "effective_work_dir": "D:/Custom Project", "created_at": "2026-10-11T00:00:00Z"}
    def route(action):
        parsed = urlsplit(action.request.url)
        path = parsed.path
        if path == "/" or path.startswith("/assets/"):
            asset = dist / ("index.html" if path == "/" else path.lstrip("/"))
            action.fulfill(status=200, content_type=mimetypes.guess_type(str(asset))[0] or "application/octet-stream", body=asset.read_bytes())
            return
        requests.append(action.request.url)
        if "workspace-assets/" in path:
            action.fulfill(status=200, content_type="text/css" if path.endswith("style.css") else "text/html",
                           body="body {color: red}" if path.endswith("style.css") else '<link rel="stylesheet" href="style.css"><p>Custom HTML</p>')
            return
        payload = {"ok": True, "sessions": [session], "session": session, "session_id": "fixture",
                   "profiles": [], "events": [], "messages": {"events": [], "total": 0},
                   "items": [], "slots": [], "contributions": [], "pending": [], "mode": "ask_for_approval"}
        if path == "/api/workspace-files":
            payload.update(root=session["work_dir"], files=[{"name": name, "rel": name, "path": session["work_dir"] + "/" + name, "kind": "file"}
                                                          for name in ("same.txt", "page.html")])
        if path == "/api/workspace-file-text":
            payload.update(text="Custom project content", truncated=False)
        action.fulfill(status=200, content_type="application/json", body=json.dumps(payload))
    page.route("**/*", route)
    try:
        page.goto("http://workbench.test/")
        page.locator('.session-item[data-session-id="fixture"]').click()
        page.wait_for_function("window.MyAgentDock && MyAgentDock.sessionId() === 'fixture'")
        page.evaluate("MyAgentDock.openDetailsTab('files')")
        page.locator('.dock-files-path').filter(has_text="D:/Custom Project").wait_for()
        page.locator('.dock-files-row').filter(has_text="same.txt").click()
        page.locator('.dock-doc-text').filter(has_text="Custom project content").wait_for()
        with page.expect_response(lambda response: urlsplit(response.url).path.endswith("style.css"), timeout=5000):
            page.evaluate("MyAgentDock.openDetailsFile('page.html')")
        assert any("workspace-files?session_id=fixture" in url for url in requests)
        assert any("workspace-file-text?session_id=fixture&rel=D%3A%2FCustom+Project%2Fsame.txt" in url for url in requests)
        assert any("/api/sessions/fixture/workspace-assets/D%3A/Custom%20Project/style.css" in url for url in requests), requests
        assert not errors, errors
    finally:
        page.close()
