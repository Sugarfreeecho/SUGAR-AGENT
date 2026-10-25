"""Use real settings/plugin code with isolated API fixtures in a local browser."""
import base64
import json
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from tests.test_llm_stream_full_text_browser import browser_page

ROOT = Path(__file__).resolve().parents[1]


def _day(offset: int) -> str:
    """以今天为基准算日期：热力图按自然周铺格子，写死日期会随时间掉出窗口。"""
    return (date.today() - timedelta(days=offset)).isoformat()


def test_hovered_picker_trigger_does_not_loop_or_detach_tabs(browser_page):
    page = browser_page
    source = (ROOT / 'frontend/src/app/modules/skill-picker.js').read_text(encoding='utf8')
    def route(request):
        if urlsplit(request.request.url).path == '/picker':
            request.fulfill(content_type='text/html', body='''
                <style>.composer-row{position:absolute;left:40px;top:100px}
                #skill-picker-btn{width:40px;height:40px}svg{pointer-events:auto}
                #skill-picker-popover{display:none;width:500px}
                #skill-picker-popover.is-open{display:block}</style>
                <div class="composer-row"><button id="skill-picker-btn"></button>
                <div id="skill-picker-popover"></div></div>
                <script>var currentSessionId='fixture',NEW_SESSION_DRAFT_KEY='draft';
                window.MyAgentResourceCache={get:async path=>({ok:true,skills:[{name:'alpha',enabled:true}],tools:[],servers:[]})};
                </script><script src="/picker.js"></script>''')
        elif urlsplit(request.request.url).path == '/picker.js':
            request.fulfill(content_type='application/javascript', body=source)
        else:
            request.fulfill(status=404)
    page.route('**/*', route)
    page.goto('http://127.0.0.1/picker')
    page.evaluate('''() => {
        window.triggerReplacements=0;
        new MutationObserver(list=>triggerReplacements+=list.length)
            .observe(document.querySelector('#skill-picker-btn'),{childList:true});
    }''')
    page.locator('#skill-picker-btn').click()
    page.locator('.skill-picker-option-name').wait_for(state='visible')
    # Keep the pointer over the child that reconciliation previously replaced.
    page.locator('#skill-picker-btn svg').hover()
    page.wait_for_timeout(150)
    replacements = page.evaluate('triggerReplacements')
    page.wait_for_timeout(400)
    assert page.evaluate('triggerReplacements') == replacements == 0
    page.locator('[data-skill-picker-tab="mcp"]').click(timeout=2000)
    assert page.locator('[data-skill-picker-tab="mcp"]').get_attribute('aria-selected') == 'true'
    page.add_script_tag(content=(ROOT / 'app/templates/static/settings/resource_cache.js').read_text(encoding='utf8'))
    blocked = page.evaluate('''() => {
      window.tabPhases=[];
      const render=renderSkillPicker;
      renderSkillPicker=function(...args){
        tabPhases.push('render');
        const end=performance.now()+80;while(performance.now()<end){}
        return render.apply(this,args);
      };
      requestAnimationFrame(()=>tabPhases.push('feedback-frame'));
      document.querySelector('[data-skill-picker-tab="hooks"]').click();
      const list=document.querySelector('.skill-picker-list');
      return list.inert && list.style.opacity==='0';
    }''')
    assert blocked, 'previous tab content cannot be clicked while its replacement is queued'
    page.wait_for_function("tabPhases.includes('render')")
    assert page.evaluate("tabPhases.indexOf('feedback-frame')<tabPhases.indexOf('render')")


@pytest.fixture
def settings_page(browser_page):
    page = browser_page
    requests = []
    static = ROOT / "app/templates/static/settings"
    profile = {"id": "p1", "name": "Fixture", "model": "fixture-model", "llm_type": "openai-responses",
               "base_url": "https://example.invalid/v1", "context_window": 8000, "max_output_tokens": 2000,
               "model_context_window": 16000, "api_key_set": True, "configured_input_modalities": ["text"]}
    responses = {
        "/api/env": {"groups": [{"title": "Fixture", "vars": [
            {"key": "FOO", "value": "original", "hint": "first", "has_value": True},
            {"key": "SECRET", "value": "", "hint": "second", "sensitive": True},
        ]}]},
        "/api/skills": {"skills": [{"name": "alpha", "description": "Read PDFs", "enabled": True},
                                    {"name": "beta", "description": "Other skill", "enabled": True}]},
        "/api/model_profiles": {"profiles": [profile]},
        "/api/model_profiles/probe": {"model": {"model_context_window": 32000, "probe_error": "HTTP 400: fixture detail"}},
        "/api/model_profiles/connectivity": {"probe": {
            "state": "available", "label": "可用", "ttft_ms": 321, "latency_ms": 987,
            "http_status": 200, "detail": "", "served_model": "fixture-model"}},
        "/api/usage-stats": {"data": {
            "ready": True, "generatedAt": "2026-10-21T10:00:00Z", "parsed": 2, "reused": 0,
            "totals": {"tokens": 1980, "input": 1800, "output": 180, "requests": 3, "sessions": 2,
                       "models": 2, "cacheHit": 8, "cacheMiss": 2, "reasoning": 0,
                       "ttftMs": 640, "ttftSamples": 3, "tokensPerSec": 152.2, "speedSamples": 3,
                       "lastAt": "2026-10-21T10:00:00Z"},
            "days": [
                {"day": _day(2), "input": 1000, "output": 10, "requests": 1},
                {"day": _day(1), "input": 10, "output": 100, "requests": 1},
                {"day": _day(0), "input": 790, "output": 70, "requests": 1},
            ],
            "models": [{"model": "model-a", "input": 1500, "output": 150, "requests": 2, "ttftMs": 640}],
            "modelsTotal": 2,
            "profiles": [{"model": "Fixture config", "input": 1500, "output": 150,
                          "requests": 2, "ttftMs": 640}],
            "profilesTotal": 1,
            "sessions": [{"id": "s1", "name": "Demo", "input": 1500, "output": 150,
                          "requests": 2, "lastAt": "2026-10-21T10:00:00Z"}],
            "sessionsTotal": 1,
        }},
        "/api/execution-metrics": {"data": {"sessions": [{
            "session_id": "s1", "session_name": "Demo",
            "runs": [{
                "run_id": "run-1", "status": "finished", "mode": "chat",
                "started_at": "2026-10-21T10:00:00.000Z", "wall_ms": 9000,
                "requests": [
                    {"react_iter": 1, "model": "model-a", "status": "ok",
                     "started_at": "2026-10-21T10:00:00.000Z", "duration_ms": 1200,
                     "first_token_ms": 300, "wall_ms": 1500,
                     "usage": {"prompt_tokens": 1000, "completion_tokens": 90, "model": "model-a"},
                     "context": {"estimated_tokens": 1000, "context_window": 128000},
                     "phases": {"pre_api": {"total_ms": 40, "events": {"estimate": 12}},
                                "llm_stream": {"total_ms": 1200, "events": []},
                                "first_token": {"total_ms": 300, "events": {"a": 300}},
                                "llm_output": {"total_ms": 900, "events": {}},
                                "tool_execution": {"total_ms": 500, "events": {}}},
                     "tools": [{"tool": "read_file", "duration_ms": 500, "failed": False}],
                     "network": {"request_bytes": 4096, "request_to_first_token_ms": 300}},
                    {"react_iter": 2, "model": "model-a", "status": "ok",
                     "started_at": "2026-10-21T10:00:20.000Z", "duration_ms": 800,
                     "first_token_ms": 200, "wall_ms": 900,
                     "usage": {"prompt_tokens": 500, "completion_tokens": 60, "model": "model-a"},
                     "context": {"estimated_tokens": 500, "context_window": 128000},
                     "phases": {"first_token": {"total_ms": 200, "events": {}},
                                "llm_output": {"total_ms": 600, "events": {}}},
                     "tools": [], "network": {"request_bytes": 2048}},
                ]}],
            "observability": {"runs": [{"run_id": "run-1", "status": "finished", "file_changes": []}]},
        }]}},
        "/api/mcp_config": {"text": "{}", "path": "fixture/mcp_servers.json"},
        "/api/tool_search/config": {"config": {"enabled": "on", "threshold_pct": 10,
            "threshold_tokens": 20000, "search_default_limit": 5, "max_search_limit": 20,
            "defer_plugin_tools": False}, "environment_override": ""},
    }

    def route(request):
        path = urlsplit(request.request.url).path
        if path == "/settings":
            html = (ROOT / "app/templates/settings_center.html").read_text(encoding="utf-8")
            html = html.replace("__SETTINGS_ASSET_VERSION__", "1").replace("__SETTINGS_BOOTSTRAP__", '{"section":"general","sessionId":"fixture"}')
            request.fulfill(status=200, content_type="text/html", body=html)
        elif path == "/host":
            request.fulfill(status=200, content_type="text/html", body='''
                <button id="sidebar-settings-btn">Settings</button>
                <div id="settings-center-overlay" hidden><iframe id="settings-center-frame"></iframe></div>
                <style>#settings-center-overlay{position:fixed;inset:0;padding:20px;background:#ddd}
                #settings-center-overlay[hidden]{display:none}iframe{width:100%;height:95%;border:0}</style>
                <script>var currentSessionId='fixture';</script><script src="/static/settings/resource_cache.js"></script><script src="/host-settings.js"></script>''')
        elif path == "/host-settings.js":
            request.fulfill(status=200, content_type="application/javascript",
                            body=(ROOT / "frontend/src/app/modules/settings.js").read_text(encoding="utf-8"))
        elif path == "/static/myagent_path_picker.js":
            request.fulfill(status=200, content_type="application/javascript",
                            body=(ROOT / "app/templates/static/myagent_path_picker.js").read_text(encoding="utf-8"))
        elif path.startswith("/static/settings/"):
            name = path.rsplit("/", 1)[1]
            request.fulfill(status=200, content_type="text/css" if name.endswith(".css") else "application/javascript",
                            body=(static / name).read_text(encoding="utf-8"))
        elif path.startswith("/api/"):
            requests.append({"path": path, "method": request.request.method, "body": request.request.post_data})
            request.fulfill(status=200, content_type="application/json", body=json.dumps({"ok": True, **responses.get(path, {})}))
        else:
            request.fulfill(status=404, body="")

    page.route("**/*", route)
    page.goto("about:blank")
    page.goto("http://settings.test/settings#env")
    page.locator('[data-env-key="FOO"]').wait_for()
    yield page, requests
    page.unroute("**/*", route)


def test_env_search_keeps_focus_and_unsaved_inputs_without_fetch(settings_page):
    page, requests = settings_page
    page.locator('[data-env-key="FOO"]').fill("unsaved edit")
    page.evaluate("window.originalInput=document.querySelector('[data-env-key=FOO]')")
    search = page.locator('[data-act="search"]')
    search.press_sequentially("SECRET", delay=180)
    page.wait_for_function("document.querySelector('[data-env-key=FOO]').closest('.st-row').hidden")
    assert search.input_value() == "SECRET"
    assert page.evaluate("document.activeElement.dataset.act") == "search"
    search.fill("")
    page.wait_for_function("!document.querySelector('[data-env-key=FOO]').closest('.st-row').hidden")
    assert page.locator('[data-env-key="FOO"]').input_value() == "unsaved edit"
    assert page.evaluate("originalInput===document.querySelector('[data-env-key=FOO]')")
    assert "有未保存" in page.locator("#st-dirty-msg").inner_text()
    assert len([request for request in requests if request["path"] == "/api/env"]) == 1


@pytest.mark.parametrize('outcome', ['same', 'changed', 'editing', 'failed'])
def test_optimistic_settings_preserve_visible_content_and_edits(settings_page, outcome):
    page, _ = settings_page
    page.evaluate("MyAgentSettings.showSection('models',{force:true,reuseCache:true})")
    page.locator('[data-act="model-add"]').wait_for()
    page.evaluate('''async () => {
      window.cachedCatalog=await MyAgentResourceCache.get('/api/model_profiles');
      window.originalCard=document.querySelector('#st-body .st-card');
      window.releaseRefresh=null;
      MyAgentResourceCache.get=()=>new Promise((resolve,reject)=>{releaseRefresh={resolve,reject};});
      window.refreshTask=MyAgentSettings.showSection('models',{force:true,reuseCache:true,optimistic:true});
    }''')
    assert page.evaluate("originalCard===document.querySelector('#st-body .st-card')")
    page.wait_for_function('!!window.releaseRefresh')
    if outcome == 'editing':
        page.locator('[data-act="model-add"]').click()
        page.locator('[data-field="model"]').fill('keep-my-edit')
    page.evaluate('''outcome => {
      if(outcome==='failed') releaseRefresh.reject(new Error('offline'));
      else releaseRefresh.resolve(outcome==='same' ? cachedCatalog : {ok:true,profiles:[]});
    }''', outcome)
    page.evaluate('refreshTask')
    if outcome in ('same', 'editing', 'failed'):
        assert page.evaluate("originalCard===document.querySelector('#st-body .st-card')")
    if outcome == 'changed':
        assert not page.evaluate("originalCard===document.querySelector('#st-body .st-card')")
    if outcome == 'editing':
        assert page.locator('[data-field="model"]').input_value() == 'keep-my-edit'
    if outcome == 'failed':
        assert '刷新失败' in page.locator('#st-toast').inner_text()


@pytest.fixture
def cpu_slowdown(browser_page, request):
    session = browser_page.context.new_cdp_session(browser_page)
    session.send('Emulation.setCPUThrottlingRate', {'rate': request.param})
    yield request.param
    session.send('Emulation.setCPUThrottlingRate', {'rate': 1})
    session.detach()


@pytest.mark.parametrize('cpu_slowdown', [1, 4], indirect=True)
def test_settings_feedback_precedes_expensive_open_and_close_work(settings_page, cpu_slowdown, record_property):
    page, _ = settings_page
    page.goto('http://settings.test/host')
    page.evaluate("myagentOpenSettings('models')")
    frame = page.frame_locator('#settings-center-frame')
    frame.locator('[data-act="model-add"]').wait_for()
    page.evaluate('myagentCloseSettings()')
    page.locator('#settings-center-overlay').wait_for(state='hidden')
    page.evaluate('''() => {
      window.phases=[];
      window.openStarted=performance.now();
      const settings=document.querySelector('#settings-center-frame').contentWindow.MyAgentSettings;
      const show=settings.showSection;
      settings.showSection=function(...args){
        phases.push('load');
        const end=performance.now()+80; while(performance.now()<end){}
        return show.apply(this,args);
      };
      requestAnimationFrame(()=>{window.openFrameMs=performance.now()-openStarted;phases.push(document.querySelector('#settings-center-overlay').hidden?'hidden':'open-frame')});
      myagentOpenSettings('models');
    }''')
    page.wait_for_function("phases.includes('load')")
    assert page.evaluate("phases.indexOf('open-frame')<phases.indexOf('load')")
    page.evaluate('''() => {
      window.closePhases=[];
      window.closeStarted=performance.now();
      window.restoreUiPreferences=()=>{
        closePhases.push('reconcile');
        const end=performance.now()+80; while(performance.now()<end){}
      };
      requestAnimationFrame(()=>{window.closeFrameMs=performance.now()-closeStarted;closePhases.push(document.querySelector('#settings-center-overlay').hidden?'closed-frame':'visible')});
      myagentCloseSettings();
    }''')
    page.wait_for_function("closePhases.includes('reconcile')")
    assert page.evaluate("closePhases.indexOf('closed-frame')<closePhases.indexOf('reconcile')")
    record_property('cpu_rate', cpu_slowdown)
    record_property('open_next_frame_ms', round(page.evaluate('openFrameMs'), 1))
    record_property('close_next_frame_ms', round(page.evaluate('closeFrameMs'), 1))


def test_closed_settings_cancels_deferred_mount_and_intent_preload_stays_hidden(settings_page):
    page, _ = settings_page
    page.goto('http://settings.test/host')
    page.evaluate("myagentOpenSettings('models');myagentCloseSettings()")
    page.wait_for_timeout(150)
    assert page.locator('#settings-center-frame').get_attribute('src') is None
    page.locator('#sidebar-settings-btn').hover()
    page.wait_for_function("!!document.querySelector('#settings-center-frame').getAttribute('src')")
    assert page.locator('#settings-center-overlay').is_hidden()
    page.evaluate("myagentOpenSettings('models')")
    page.frame_locator('#settings-center-frame').locator('[data-act="model-add"]').wait_for()


@pytest.mark.parametrize("close_with", ["mask", "escape"])
def test_nested_settings_dialog_closes_only_inner_layer(settings_page, close_with):
    page, requests = settings_page
    page.evaluate("""() => {
      window.saved = false;
      MyAgentSettings.openDialog({title:'Inner', body:'<input id="inner-input">',
        onOk:() => {window.saved=true;}});
    }""")
    page.locator("#inner-input").click()
    assert page.locator("#st-dialog").is_visible()
    page.evaluate("MyAgentSettings.askConfirm('Confirm',()=>{window.saved=true})")
    if close_with == "mask":
        page.locator("#st-confirm").click(position={"x": 4, "y": 4})
    else:
        page.keyboard.press("Escape")
    assert page.locator("#st-confirm").is_hidden()
    assert page.locator("#st-dialog").is_visible()
    if close_with == "mask":
        page.locator("#st-dialog").click(position={"x": 4, "y": 4})
    else:
        page.keyboard.press("Escape")
    assert page.locator("#st-dialog").is_hidden()
    assert page.locator("#st-body").is_visible()
    assert page.evaluate("!window.saved")


def test_mcp_managed_provider_shows_tools_without_registration_or_generic_toggles(settings_page):
    page, requests = settings_page
    _mock_json(page, "/api/mcp/tools", {
        "servers": [{"server": "cua-driver-mcp", "transport": "stdio", "connected": True,
                     "discovered": True, "tool_count": 2, "managed_by": "computer-use"}],
        "tools": [{"server": "cua-driver-mcp", "function_name": "mcp__cua-driver-mcp__" + name,
                   "tool_name": name, "enabled": True, "managed_by": "computer-use"}
                  for name in ("click", "list_windows")],
    })
    page.evaluate("MyAgentSettings.showSection('mcp',{force:true})")
    group = page.locator('[data-mcp-server="cua-driver-mcp"]')
    group.wait_for()
    text = group.inner_text()
    assert "已连接" in text and "2 个工具" in text and "由 Computer Use 管理" in text
    assert "mcp__cua-driver-mcp__click" in text and "mcp__cua-driver-mcp__list_windows" in text
    assert "未连接" not in text and "尚未注册" not in text
    assert group.locator('[data-act="mcp-register"]').count() == 0
    assert group.locator('[data-key^="mcp:"]').count() == 0
    assert not [request for request in requests if request["method"] == "POST"]


def test_mcp_composer_inventory_respects_provider_ownership(browser_page):
    page = browser_page
    source = (ROOT / "frontend/src/app/modules/skill-picker.js").read_text(encoding="utf-8")
    page.goto("about:blank")
    page.add_script_tag(content=source.rsplit("\ninitSkillPicker();", 1)[0])
    page.evaluate("""() => {
      mcpServersCache=[{server:'cua-driver-mcp',connected:true,discovered:true,managed_by:'computer-use'}];
      mcpToolsCache=[{server:'cua-driver-mcp',function_name:'mcp__cua-driver-mcp__click',
                     tool_name:'click',enabled:true,managed_by:'computer-use'}];
      document.body.innerHTML=renderSkillPickerMcpToolsHtml();
    }""")
    assert "由 Computer Use 管理" in page.locator("body").inner_text()
    assert "已启用 1 / 共 1 个工具" in page.locator("body").inner_text()
    assert "mcp__cua-driver-mcp__click" in page.locator("body").inner_text()
    assert page.locator(".mcp-tool-toggle,.mcp-server-register-btn").count() == 0

    page.evaluate("""() => {
      mcpServersCache[0].connected=false;mcpServersCache[0].discovered=false;mcpToolsCache=[];
      document.body.innerHTML=renderSkillPickerMcpToolsHtml();
    }""")
    assert "未连接" in page.locator("body").inner_text()
    assert page.locator(".mcp-server-register-btn").count() == 0

    page.evaluate("""() => {
      mcpServersCache=[{server:'ordinary',connected:false,discovered:false}];
      document.body.innerHTML=renderSkillPickerMcpToolsHtml();
    }""")
    assert page.locator('.mcp-server-register-btn[data-mcp-server="ordinary"]').count() == 1


def _mock_json(page, path, payload, method="GET"):
    def respond(route):
        if route.request.method != method:
            route.fallback()
            return
        route.fulfill(status=200, content_type="application/json", body=json.dumps({"ok": True, **payload}))
    page.route("**" + path, respond)


def test_chat_and_retained_settings_share_catalog_requests(settings_page):
    page, requests = settings_page
    page.goto('http://settings.test/host')
    page.evaluate("MyAgentResourceCache.get('/api/plugins/catalog')")
    page.evaluate("myagentOpenSettings('plugins')")
    frame = page.frame_locator('#settings-center-frame')
    frame.locator('#st-title').filter(has_text='插件').wait_for()
    def extension_reads():
        return sum(row['path'] == '/api/plugins/catalog' and row['method'] == 'GET' for row in requests)
    assert extension_reads() == 2  # One standalone fixture load, one shared host load.
    page.evaluate('myagentCloseSettings()')
    page.locator('#settings-center-overlay').wait_for(state='hidden')
    page.evaluate("myagentOpenSettings('plugins')")
    frame.locator('#st-title').filter(has_text='插件').wait_for()
    assert extension_reads() == 2
    frame.locator('body').evaluate("async () => { await MyAgentSettings.api('/api/plugins/demo/enabled', {method:'POST',body:{enabled:false}}); await MyAgentSettings.showSection('plugins',{force:true,reuseCache:true}); }")
    assert extension_reads() == 3, 'a successful mutation invalidates the shared catalog'
    frame.locator('body').evaluate("MyAgentSettings.showSection('hooks')")
    assert extension_reads() == 3, 'Hooks does not invalidate the plugin-only catalog'
    assert sum(row['path'] == '/api/extensions' for row in requests) == 1, 'only Hooks requests the runtime snapshot'


def test_plugin_tabs_and_list_render_while_full_extensions_request_is_blocked(settings_page):
    page, _ = settings_page
    held = []
    page.route('**/api/extensions', lambda route: held.append(route))
    contribution = {'slot': 'settings.section', 'plugin_id': 'demo', 'id': 'main', 'title': 'Fast demo',
                    'target': 'plugin-page', 'href': '/plugins/demo'}
    _mock_json(page, '/api/plugins/catalog', {'plugins': [{'id': 'demo', 'name': 'Demo', 'enabled': True}],
                                            'ui_contributions': [contribution]})
    # A diagnostic consumer is already waiting; settings must not share its
    # full-snapshot request or wait for it before installing navigation tabs.
    page.evaluate("() => { fetch('/api/extensions').then(() => { window.fullDone=true; }); }")
    try:
        page.evaluate("async () => { MyAgentResourceCache.invalidate(); await MyAgentSettings.loadPluginSections(); await MyAgentSettings.showSection('plugins'); }")
        page.locator('[data-act="nav"][data-id="plugin:demo:main"]').wait_for()
        page.locator('[data-key="plugin:demo"]').wait_for()
        assert len(held) == 1 and not page.evaluate('Boolean(window.fullDone)')
        assert page.evaluate("performance.getEntriesByName('settings.plugin-tabs').length") > 0
    finally:
        for route in held:
            route.fulfill(status=200, content_type='application/json', body='{"ok":true}')
        page.unroute('**/api/extensions')


def test_mcp_background_discovery_preserves_form_drafts(settings_page):
    page, _ = settings_page
    calls = []
    def respond(route):
        calls.append(True)
        payload = {'ok': True, 'initializing': len(calls) == 1, 'tools': [], 'servers': []}
        if len(calls) > 1:
            payload.update(tools=[{'function_name': 'mcp_alpha_read', 'server': 'alpha', 'tool_name': 'read'}],
                           servers=[{'server': 'alpha', 'connected': True, 'discovered': True}])
        route.fulfill(status=200, content_type='application/json', body=json.dumps(payload))
    page.route('**/api/mcp/tools', respond)
    page.evaluate("MyAgentSettings.showSection('mcp',{force:true})")
    page.locator('[data-field="mcp-cmd"]').fill('npx pending-draft')
    page.locator('[data-key="mcp:mcp_alpha_read"]').wait_for()
    assert page.locator('[data-field="mcp-cmd"]').input_value() == 'npx pending-draft'
    assert len(calls) == 2


def _three_profiles(page):
    profiles = [{"id": "p" + str(index), "name": "Profile " + str(index), "model": "fixture", "api_key_set": True,
                 "base_url": "https://example.invalid/v1", "llm_type": "openai-responses"} for index in range(1, 4)]
    _mock_json(page, "/api/model_profiles", {"profiles": profiles})
    page.evaluate("MyAgentSettings.showSection('models',{force:true})")
    page.locator('[data-profile-id="p3"]').wait_for()


def test_quick_sort_preserves_rows_focus_and_serializes_latest_order(settings_page):
    page, requests = settings_page
    _three_profiles(page)
    page.evaluate("""() => {
      window.originalRows=Array.from(document.querySelector('[data-profile-list]').children);
      window.sortRequests=[];
      const original=window.fetch;
      window.fetch=(url,options)=>url==='/api/model_profiles/reorder'
        ? new Promise(resolve=>sortRequests.push({ids:JSON.parse(options.body).ordered_ids,resolve})) : original(url,options);
    }""")
    handle = page.locator('[data-profile-id="p3"] .st-drag-handle')
    handle.evaluate("el=>{el.focus();for(let i=0;i<2;i++)el.dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowUp',bubbles:true}))}")
    page.wait_for_function("sortRequests.length===1")
    assert page.evaluate("sortRequests[0].ids") == ["p3", "p1", "p2"]
    assert page.evaluate("document.activeElement.closest('[data-profile-id]').dataset.profileId") == "p3"
    handle.press("ArrowDown")
    page.evaluate("sortRequests[0].resolve({ok:true,json:async()=>({ok:true})})")
    page.wait_for_function("sortRequests.length===2")
    assert page.evaluate("sortRequests[1].ids") == ["p1", "p3", "p2"]
    page.evaluate("sortRequests[1].resolve({ok:true,json:async()=>({ok:true})})")
    page.wait_for_function("!document.querySelector('[data-profile-list]').hasAttribute('aria-busy')")
    assert page.evaluate("originalRows.every(row=>row===document.querySelector('[data-profile-id='+row.dataset.profileId+']'))")
    assert page.locator('[data-profile-default]:visible').evaluate("el=>el.closest('[data-profile-id]').dataset.profileId") == "p1"
    assert not any(request["path"] == "/api/model_profiles" for request in requests), "sorting must not reload the list"


def test_drag_batches_geometry_and_cancel_restores_before_drag(settings_page):
    page, _ = settings_page
    _three_profiles(page)
    result = page.evaluate("""async () => {
      const list=document.querySelector('[data-profile-list]'), handle=list.lastElementChild.querySelector('.st-drag-handle');
      const original=Element.prototype.getBoundingClientRect;let reads=0;
      const y=list.getBoundingClientRect().top;
      Element.prototype.getBoundingClientRect=function(){reads++;return original.call(this)};
      handle.dispatchEvent(new DragEvent('dragstart',{bubbles:true,dataTransfer:new DataTransfer()}));
      for(let i=0;i<200;i++)list.dispatchEvent(new DragEvent('dragover',{bubbles:true,clientY:y,dataTransfer:new DataTransfer()}));
      await new Promise(requestAnimationFrame);
      const moved=Array.from(list.children).map(row=>row.dataset.profileId), batchedReads=reads;
      handle.dispatchEvent(new DragEvent('dragend',{bubbles:true}));
      Element.prototype.getBoundingClientRect=original;
      return {moved,reads:batchedReads,restored:Array.from(list.children).map(row=>row.dataset.profileId)};
    }""")
    assert result["moved"] == ["p3", "p1", "p2"]
    assert result["reads"] <= 12, "200 drag events should do at most one frame of geometry work"
    assert result["restored"] == ["p1", "p2", "p3"]


def test_model_form_shows_metadata_required_fields_and_fixed_efforts(settings_page):
    page, _ = settings_page
    page.evaluate("MyAgentSettings.showSection('models',{force:true})")
    page.locator('[data-act="model-edit"]').wait_for()
    page.evaluate("Object.assign(__lastProfiles[0],{capability_source:'automatic:models-table',capability_description:'Automatic content',headers:{'X-Example':'value'}})")
    page.locator('[data-act="model-edit"]').click()
    page.locator("#st-dlg-body details summary").click()
    assert page.locator('[data-field="capability_description"]').input_value() == "Automatic content"
    assert json.loads(page.locator('[data-field="headers_json"]').input_value()) == {"X-Example": "value"}
    assert page.locator('[data-field="thinking_mode"]').count() == 0
    assert page.locator('[data-field="reasoning_effort"] option').evaluate_all("options=>options.map(option=>option.value)") == ["low", "medium", "high", "xhigh", "max"]
    assert page.locator('[data-field="model"]').get_attribute("aria-required") == "true"
    assert page.locator('[data-field="api_key"]').get_attribute("aria-required") == "false"
    labels = page.locator("#st-dlg-body .st-label").all_text_contents()
    assert next(i for i, label in enumerate(labels) if "模型总窗口" in label) < next(i for i, label in enumerate(labels) if "上下文长度（压缩阈值）" in label)
    assert page.locator("#st-dlg-body").evaluate("el=>getComputedStyle(el).scrollbarGutter") == "stable"
    assert page.locator("#st-dlg-body").evaluate("el=>getComputedStyle(el,'::-webkit-scrollbar').width") == "5px"


def test_model_protocol_is_visible_explicit_and_saved(settings_page):
    page, requests = settings_page
    page.evaluate("MyAgentSettings.showSection('models',{force:true})")
    page.locator('[data-act="model-edit"]').click()
    selector = page.locator('[data-field="llm_type"]')
    assert selector.is_visible()
    assert selector.locator('option').evaluate_all("options=>options.map(option=>option.value)") == [
        "openai-completions", "openai-responses", "anthropic",
    ]
    assert selector.input_value() == "openai-responses"
    selector.select_option("anthropic")
    page.locator("#st-dlg-ok").click()
    page.locator("#st-dialog").wait_for(state="hidden")
    saved = json.loads(next(request["body"] for request in requests
                            if request["path"] == "/api/model_profiles" and request["method"] == "POST"))
    assert saved["llm_type"] == "anthropic"
    assert saved["base_url"] == "https://example.invalid/v1"


def test_auto_add_opens_model_dialog_with_ascend_and_huawei_defaults(settings_page):
    """欢迎页带 add=1 进来：模型页签渲染后自动弹「添加模型」，并预填华为 ascend 默认值。"""
    page, _ = settings_page

    def open_models_with_add(route):
        if urlsplit(route.request.url).path != "/settings":
            route.fallback()
            return
        html = (ROOT / "app/templates/settings_center.html").read_text(encoding="utf-8")
        html = html.replace("__SETTINGS_ASSET_VERSION__", "1").replace(
            "__SETTINGS_BOOTSTRAP__",
            '{"section":"models","sessionId":"fixture","autoAddModel":true}')
        route.fulfill(status=200, content_type="text/html", body=html)

    page.route("**/*", open_models_with_add)
    try:
        page.goto("http://settings.test/settings?section=models&add=1")
        page.locator("#st-dialog").wait_for(state="visible")
        assert page.locator('[data-field="base_url"]').input_value() == "http://models.ascend.huawei.com/v1"
        assert page.locator('[data-field="model"]').input_value() == ""
        assert page.locator('[data-field="llm_type"]').input_value() == "openai-completions"
        page.locator("#st-dlg-body details summary").click()
        assert page.locator('[data-field="model_context_window"]').input_value() == "200000"
        assert page.locator('[data-field="context_window"]').input_value() == "180000"
        assert page.locator('[data-field="max_output_tokens"]').input_value() == "20000"
    finally:
        page.unroute("**/*", open_models_with_add)


def test_model_connect_button_wraps_below_the_name_field_and_reports(settings_page):
    """控件列只有 220px：输入框独占一行，两个按钮换行到下一行，不能挤成几十像素。"""
    page, requests = settings_page
    page.evaluate("MyAgentSettings.showSection('models',{force:true})")
    page.locator('[data-act="model-edit"]').click()

    field = page.locator('[data-field="model"]').bounding_box()
    fetch = page.locator('[data-act="model-fetch"]').bounding_box()
    connect = page.locator('[data-act="model-connect"]').bounding_box()
    assert field["width"] > 150, "模型名输入框应占满控件列"
    assert connect["y"] >= field["y"] + field["height"], "按钮应换到输入框下一行"
    assert abs(connect["y"] - fetch["y"]) < 2, "两个按钮应同在一行"

    page.locator('[data-act="model-connect"]').click()
    page.locator('[data-model-test-status] .st-status').wait_for()
    status = page.locator('[data-model-test-status]').inner_text()
    assert "可用" in status and "321ms" in status
    sent = json.loads(next(request["body"] for request in requests
                           if request["path"] == "/api/model_profiles/connectivity"))
    assert sent["id"] == "p1"
    assert sent["model"] == "fixture-model"


def test_usage_section_totals_and_metric_toggle(settings_page):
    """用量页签：汇总数字、（总量/输出）切换，以及两张表都在。"""
    page, requests = settings_page
    page.evaluate("MyAgentSettings.showSection('usage',{force:true})")
    assert page.locator("#st-title").inner_text() == "用量统计"
    page.locator(".st-usage-sum .cell").first.wait_for()

    assert page.locator(".st-usage-sum .cell").count() == 5
    summary = page.locator(".st-usage-sum").inner_text()
    assert "1980" in summary and "180" in summary and "3" in summary
    assert "80%" in summary, "缓存命中率 8/(8+2)"

    page.locator('[data-act="usage-mode"][data-mode="output"]').click()
    assert page.locator('[data-act="usage-mode"][data-mode="output"]').get_attribute("class") == "on"

    assert page.locator(".st-usage-table").count() == 2
    assert "model-a" in page.locator(".st-usage-table").first.inner_text()


def test_usage_section_session_row_opens_the_execution_detail(settings_page):
    """点会话行进执行明细：汇总卡片、四张图、阶段累计，返回能回汇总。"""
    page, requests = settings_page
    page.evaluate("MyAgentSettings.showSection('usage',{force:true})")
    row = page.locator('tr[data-act="usage-session"]').first
    row.wait_for()
    row.click()

    page.locator(".st-ud-cards").first.wait_for(timeout=10000)
    body = page.locator("#st-body")
    text = body.inner_text()
    assert "次请求" in text and "Run 墙钟" in text
    assert page.locator(".st-ud-legend").count() == 4, "Token/阶段/工具/网络四张图"
    assert page.locator(".st-ud-chart svg polyline").count() >= 4
    assert page.locator(".st-ud-fold").count() == 7, "七个阶段累计"
    assert any(row["path"] == "/api/execution-metrics" for row in requests), "明细要按会话拉单会话快照"

    page.locator('[data-act="usage-back"]').click()
    page.locator(".st-usage-sum .cell").first.wait_for(timeout=10000)
    assert page.locator(".st-ud-cards").count() == 0
    assert page.locator("#st-title").inner_text() == "用量统计"


def test_usage_section_heatmap_switches_modes_and_shows_the_day(settings_page):
    """Token 活动栅格：按天铺 52 周格子，每周/累计切换，点格子出当天明细。"""
    page, requests = settings_page
    page.evaluate("MyAgentSettings.showSection('usage',{force:true})")
    page.locator(".st-heat-cell").first.wait_for()
    # 52 列 × 7 行，最后一列只铺到今天所在的位置（所以略少于 364）。
    assert page.locator(".st-heat-cell").count() >= 350, "近 52 周按天铺格子"
    assert page.locator(".st-heat-months span").count() >= 10

    page.locator('[data-act="usage-heat-mode"][data-mode="weekly"]').click()
    page.wait_for_timeout(60)
    # 每周只有 52 个点，用柱高而不是色阶，才能看出量级差异。
    assert page.locator(".st-week-bars i").count() == 52, "每周 52 根柱子"
    assert page.locator(".st-heat-cell").count() == 0
    heights = page.locator(".st-week-bars i").evaluate_all("els=>els.map(el=>el.style.height)")
    # fixture 的三天都在同一周：只有那一周最高，其余是 2% 的平底。
    assert heights.count("100%") == 1 and heights.count("2%") >= 45, "柱高来自每周合计"
    assert "on" in page.locator('[data-act="usage-heat-mode"][data-mode="weekly"]').get_attribute("class")
    page.locator(".st-week-bars i").last.click()
    page.wait_for_timeout(60)
    assert " ~ " in page.locator(".st-heat-day").inner_text(), "点柱子看当周区间"

    page.locator('[data-act="usage-heat-mode"][data-mode="cumulative"]').click()
    page.wait_for_timeout(60)
    assert page.locator(".st-heat-cell").count() >= 350

    page.locator('[data-act="usage-heat-mode"][data-mode="daily"]').click()
    page.wait_for_timeout(60)
    page.locator(".st-heat-cell.l1, .st-heat-cell.l2, .st-heat-cell.l3, .st-heat-cell.l4").last.click()
    page.wait_for_timeout(60)
    detail = page.locator(".st-heat-day").inner_text()
    assert "输入" in detail and "2026-" in detail


def test_usage_section_lists_all_sessions_with_search(settings_page):
    """会话表默认 30 行，可展开全部，也能按名字/ID 搜到没显示的那些。"""
    page, requests = settings_page
    sessions = [{"id": "s%02d" % index, "name": "Session %02d" % index, "input": 1000 - index,
                 "output": 10, "requests": 1, "lastAt": "2026-10-21T10:00:00Z"} for index in range(35)]
    payload = {"ok": True, "data": {
        "ready": True, "generatedAt": "2026-10-21T10:00:00Z", "parsed": 35, "reused": 0,
        "totals": {"tokens": 35000, "input": 35000, "output": 0, "requests": 35, "sessions": 35,
                   "models": 1, "cacheHit": 0, "cacheMiss": 0, "reasoning": 0},
        "days": [{"day": "2026-10-21", "input": 35000, "output": 0, "requests": 35}],
        "models": [{"model": "m", "input": 35000, "output": 0, "requests": 35}], "modelsTotal": 1,
        "sessions": sessions, "sessionsTotal": 35,
    }}
    page.route("**/api/usage-stats*", lambda route: route.fulfill(
        status=200, content_type="application/json", body=json.dumps(payload)))
    page.evaluate("MyAgentSettings.showSection('usage',{force:true})")
    page.locator('tr[data-act="usage-session"]').first.wait_for()
    visible = lambda: page.locator('tr[data-act="usage-session"]:visible').count()

    assert visible() == 30, "默认只显示前 30 个"
    page.locator('[data-act="usage-sessions-all"]').click()
    page.wait_for_timeout(80)
    assert visible() == 35, "点「全部」展开余下的会话"

    page.locator('[data-usage-session-search]').fill("s34")
    page.wait_for_timeout(80)
    assert visible() == 1
    assert page.locator('[data-usage-session-count]').inner_text() == "1 / 35"


def test_usage_section_sorts_sessions_by_header(settings_page):
    """点「请求/输入/输出/最近」表头排序：降序 → 升序 → 回到默认顺序。"""
    page, requests = settings_page
    def row(sid, name, input_tokens, requests_count, last):
        return {"id": sid, "name": name, "input": input_tokens, "output": 10,
                "requests": requests_count, "lastAt": last}
    sessions = [
        row("s2", "Echo", 300, 4, "2026-10-02T10:00:00Z"),
        row("s0", "Alpha", 100, 5, "2026-10-05T10:00:00Z"),
        row("s4", "Hotel", 400, 2, "2026-10-01T10:00:00Z"),
        row("s1", "Bravo", 500, 3, "2026-10-04T10:00:00Z"),
        row("s3", "Golf", 200, 1, "2026-10-03T10:00:00Z"),
    ]
    payload = {"ok": True, "data": {
        "ready": True, "generatedAt": "2026-10-21T10:00:00Z", "parsed": 5, "reused": 0,
        "totals": {"tokens": 1500, "input": 1500, "output": 50, "requests": 15, "sessions": 5,
                   "models": 1, "cacheHit": 0, "cacheMiss": 0, "reasoning": 0},
        "days": [{"day": "2026-10-21", "input": 1500, "output": 50, "requests": 15}],
        "models": [{"model": "m", "input": 1500, "output": 50, "requests": 15}], "modelsTotal": 1,
        "sessions": sessions, "sessionsTotal": 5,
    }}
    page.route("**/api/usage-stats*", lambda route: route.fulfill(
        status=200, content_type="application/json", body=json.dumps(payload)))
    page.evaluate("MyAgentSettings.showSection('usage',{force:true})")
    page.locator('tr[data-act="usage-session"]').first.wait_for()
    names = lambda: [text.split("\t")[0] for text in
                     page.locator('tr[data-act="usage-session"]:visible').all_inner_texts()]
    assert names()[0] == "Echo", "默认保持后端给的顺序"

    header = page.locator('th[data-act="usage-sort"][data-key="input"]')
    header.click()
    assert names()[0] == "Bravo" and "▼" in header.inner_text(), "第一下按输入降序"
    header.click()
    assert names()[0] == "Alpha" and "▲" in header.inner_text(), "再一下切升序"
    header.click()
    assert names()[0] == "Echo" and "▲" not in header.inner_text(), "第三下回到默认顺序"

    page.locator('th[data-act="usage-sort"][data-key="requests"]').click()
    assert names()[:2] == ["Alpha", "Echo"], "请求数降序：5 条在前"
    page.locator('th[data-act="usage-sort"][data-key="lastAt"]').click()
    assert names()[0] == "Alpha", "最近时间降序：10-05 最前"


def test_usage_section_models_card_shows_ttft_and_switches_to_profiles(settings_page):
    """按模型卡片：带平均首字、限高十行滚动、可切到按模型配置。"""
    page, requests = settings_page
    page.evaluate("MyAgentSettings.showSection('usage',{force:true})")
    scroll = page.locator(".st-usage-model-scroll")
    scroll.wait_for()

    head = scroll.locator("thead").inner_text()
    assert "平均首字" in head
    assert "640ms" in scroll.inner_text(), "首字延迟按毫秒/秒格式化"
    style = page.evaluate("""() => {
        const s = getComputedStyle(document.querySelector('.st-usage-model-scroll'));
        return {max: s.maxHeight, overflow: s.overflowY};
    }""")
    assert style == {"max": "380px", "overflow": "auto"}, "限高约十行，超出滚动"

    page.locator('[data-act="usage-model-mode"][data-mode="profile"]').click()
    page.wait_for_timeout(80)
    assert "模型配置" in scroll.locator("thead").inner_text()
    assert "Fixture config" in scroll.inner_text()
    assert "按当前模型配置归类" in page.locator("#st-body").inner_text()

    page.locator('[data-act="usage-model-mode"][data-mode="model"]').click()
    page.wait_for_timeout(80)
    assert "模型" in scroll.locator("thead").inner_text()


def test_usage_section_token_activity_merges_the_daily_bars(settings_page):
    """「每日 Token」被热力图吸收：不再有独立柱状图，量纲切换直接改格子深浅。"""
    page, requests = settings_page
    page.evaluate("MyAgentSettings.showSection('usage',{force:true})")
    page.locator(".st-heat-cell").first.wait_for()
    body = page.locator("#st-body").inner_text()
    assert "每日 Token" not in body, "旧的独立卡片已合并"
    assert page.locator(".st-usage-bars").count() == 0, "柱状图已被热力图取代"
    first = page.locator(".st-card").nth(0).inner_text()
    assert "Token 活动" in first and "平均首字" in first, "速度行仍在这个卡片里"

    peak_day = page.locator('.st-heat-cell[data-day="%s"]' % _day(2))
    assert "l4" in peak_day.get_attribute("class"), "总量模式下 10-19 那天最深"
    page.locator('[data-act="usage-mode"][data-mode="output"]').click()
    page.wait_for_timeout(80)
    assert "l1" in page.locator('.st-heat-cell[data-day="%s"]' % _day(2)).get_attribute("class"), \
        "切到输出后同一天变浅（当天的输出很少）"


def test_usage_section_mode_switch_keeps_the_card_height(settings_page):
    """每周换成柱状图后，卡片高度要和每日/累计一致，切模式不能跳。"""
    page, requests = settings_page
    page.evaluate("MyAgentSettings.showSection('usage',{force:true})")
    page.locator(".st-heat-cell").first.wait_for()

    height = lambda: round(page.locator(".st-card").nth(0).bounding_box()["height"])
    daily = height()
    page.locator('[data-act="usage-heat-mode"][data-mode="weekly"]').click()
    page.wait_for_timeout(80)
    weekly = height()
    assert "柱高" in page.locator(".st-heat-legend").inner_text(), "图例位置换成柱高说明"
    page.locator('[data-act="usage-heat-mode"][data-mode="cumulative"]').click()
    page.wait_for_timeout(80)
    cumulative = height()

    assert daily == weekly == cumulative, "三种模式高度必须一致"


def test_usage_section_polls_until_the_background_build_finishes(settings_page):
    """第一次打开只拿到 ready:false，前端要自己轮询到 ready 再画。"""
    page, requests = settings_page
    calls = {"count": 0}
    ready = {"ok": True, "data": {
        "ready": True, "generatedAt": "2026-10-21T10:00:00Z",
        "totals": {"tokens": 500, "input": 400, "output": 100, "requests": 2, "sessions": 1,
                   "models": 1, "cacheHit": 0, "cacheMiss": 0, "reasoning": 0},
        "days": [{"day": "2026-10-21", "input": 400, "output": 100, "requests": 2}],
        "models": [{"model": "late-model", "input": 400, "output": 100, "requests": 2}],
        "modelsTotal": 1,
        "sessions": [{"id": "s1", "name": "Demo", "input": 400, "output": 100, "requests": 2,
                      "lastAt": "2026-10-21T10:00:00Z"}],
        "sessionsTotal": 1,
    }}

    def usage_route(route):
        calls["count"] += 1
        body = {"ok": True, "data": {"ready": False}} if calls["count"] == 1 else ready
        route.fulfill(status=200, content_type="application/json", body=json.dumps(body))

    page.route("**/api/usage-stats*", usage_route)  # 后注册的路由优先，覆盖 fixture 的固定响应
    page.evaluate("MyAgentSettings.showSection('usage',{force:true})")
    page.locator(".st-hint").first.wait_for()
    assert "正在统计" in page.locator("#st-body").inner_text()

    page.locator(".st-usage-sum .cell").first.wait_for(timeout=10000)
    assert calls["count"] >= 2
    assert "late-model" in page.locator(".st-usage-table").first.inner_text()


def test_welcome_page_routes_immediate_setup_and_defers_to_main_ui(browser_page):
    """欢迎页只有两个按钮：立即配置落到模型页签并带自动弹窗标记，稍后配置记下选择再进主界面。"""
    page = browser_page
    skipped = []

    def route(request):
        path = urlsplit(request.request.url).path
        if path == "/setup":
            request.fulfill(status=200, content_type="text/html",
                            body=(ROOT / "app/templates/first_time_config.html").read_text(encoding="utf-8"))
        elif path == "/api/setup/skip":
            skipped.append(request.request.method)
            request.fulfill(status=200, content_type="application/json", body='{"ok": true}')
        elif path in {"/settings", "/"}:
            request.fulfill(status=200, content_type="text/html", body="<html><body>fixture</body></html>")
        else:
            request.fulfill(status=404, body="")

    page.route("**/*", route)
    try:
        page.goto("http://setup.test/setup")
        buttons = page.locator(".welcome-actions .btn")
        assert buttons.count() == 2
        assert buttons.nth(0).inner_text().strip() == "立即配置首个模型"
        assert buttons.nth(1).inner_text().strip() == "稍后配置"
        assert page.locator("#configForm, #llmProvider").count() == 0, "旧配置向导表单不应再出现"

        buttons.nth(0).click()
        page.wait_for_function(
            "location.pathname + location.search + location.hash === '/settings?section=models&add=1#models'")
        page.go_back()
        page.wait_for_function("location.pathname === '/setup'")
        assert skipped == [], "立即配置不该跳过配置门槛"

        page.locator(".welcome-actions .btn").nth(1).click()
        page.wait_for_function("location.pathname === '/'")
        assert skipped == ["POST"]
    finally:
        page.goto("about:blank")
        page.unroute("**/*", route)


def test_model_automatic_preview_and_manual_edit_are_not_overwritten(settings_page):
    page, requests = settings_page
    _mock_json(page, "/api/model_profiles/capabilities", {"capabilities": {"capability_description": "Generated description"}}, method="POST")
    page.evaluate("MyAgentSettings.showSection('models',{force:true})")
    page.locator('[data-act="model-edit"]').click()
    page.locator("#st-dlg-body details summary").click()
    page.locator('[data-field="model"]').fill("new-model")
    page.wait_for_function("document.querySelector('[data-field=capability_description]').value==='Generated description'")
    page.locator('[data-field="capability_description"]').fill("Manual description")
    page.locator('[data-field="model"]').fill("other-model")
    page.locator('[data-field="reasoning_effort"]').select_option("max")
    page.locator("#st-dlg-ok").click()
    page.locator("#st-dialog").wait_for(state="hidden")
    saved = json.loads(next(request["body"] for request in requests if request["path"] == "/api/model_profiles" and request["method"] == "POST"))
    assert saved["capability_description"] == "Manual description"
    assert saved["thinking_mode"] == "enabled" and saved["reasoning_effort"] == "max"
    assert saved["headers"] == {} and saved["extra_body_json"] == ""


def test_model_fetch_opens_its_own_filterable_menu(settings_page):
    """「从接口获取」把列表放进带筛选框的菜单：模型名称框里已有文字也不会筛掉列表。"""
    page, _ = settings_page
    posted = []
    models = [
        {"id": "alpha-model", "context_window": 32000},
        {"id": "beta-model", "context_window": 128000},
        {"id": "gamma-model"},
    ]

    def discover(route):
        posted.append(json.loads(route.request.post_data))
        route.fulfill(status=200, content_type="application/json",
                      body=json.dumps({"ok": True, "models": models}))

    page.route("**/api/model_profiles/discover", discover)
    page.evaluate("MyAgentSettings.showSection('models',{force:true})")
    page.locator('[data-act="model-edit"]').click()
    # 编辑已有模型：模型名称框里本来就填着模型名
    assert page.locator('[data-field="model"]').input_value() == "fixture-model"
    page.locator('[data-act="model-fetch"]').click()
    menu = page.locator(".st-model-menu")
    menu.wait_for()
    assert menu.locator(".st-model-option").count() == 3, "列表不该被模型名称框里的文字筛掉"
    # 筛选框长在菜单内部，且打开就聚焦
    assert page.evaluate("document.activeElement.hasAttribute('data-model-filter')")
    page.locator("[data-model-filter]").fill("beta")
    page.wait_for_function("document.querySelectorAll('.st-model-option').length === 1")
    menu.locator(".st-model-option").first.click()
    assert page.locator('[data-field="model"]').input_value() == "beta-model"
    assert page.locator(".st-model-menu").count() == 0
    # 编辑态把 profile_id 一起发出去，后端才能复用已存密钥（空 Key 会 401）
    assert posted and posted[0]["profile_id"] == "p1"
    assert posted[0]["api_key"] == ""
    page.unroute("**/api/model_profiles/discover", discover)


def test_dialog_survives_a_press_that_starts_inside_and_ends_on_the_mask(settings_page):
    """在窗口内按住、拖到遮罩上松开不该关窗；真正的遮罩点击照旧关闭。"""
    page, _ = settings_page
    page.evaluate("MyAgentSettings.showSection('models',{force:true})")
    page.locator('[data-act="model-edit"]').click()
    assert page.locator("#st-dialog").is_visible()

    body = page.locator("#st-dlg-body").bounding_box()
    page.mouse.move(body["x"] + 40, body["y"] + 20)
    page.mouse.down()
    page.mouse.move(6, 6, steps=8)
    page.mouse.up()
    assert page.locator("#st-dialog").is_visible(), "拖出窗口再松开不能关掉弹窗"

    page.mouse.click(6, 6)
    page.locator("#st-dialog").wait_for(state="hidden")


def test_skill_picker_updates_kind_after_source_switch(settings_page):
    page, requests = settings_page
    _mock_json(page, "/api/pick-path", {"path": "D:\\chosen\\example.zip"}, method="POST")
    page.evaluate("MyAgentSettings.showSection('skills',{force:true})")
    page.locator('[data-act="skill-add"]').click()
    # The source field is a batch textarea; the browse button carries the picker kind.
    browse = page.locator("#st-dlg-body [data-browse-kind]")
    assert browse.get_attribute("data-browse-kind") == "directory"
    page.locator('#st-dlg-body [data-val="zip"]').click()
    assert browse.get_attribute("data-browse-kind") == "file"
    browse.click()
    page.wait_for_function("document.querySelector('[data-field=source]').value.endsWith('example.zip')")
    page.locator("#st-dlg-ok").click()
    page.locator("#st-dialog").wait_for(state="hidden")
    saved = json.loads(next(request["body"] for request in requests if request["path"] == "/api/skills/install"))
    assert saved == {"source": "D:\\chosen\\example.zip", "kind": "zip"}


@pytest.mark.parametrize("section", ["skills", "plugins"])
def test_package_drop_uploads_actual_archive_contents(settings_page, section):
    page, _ = settings_page
    uploaded = []
    def receive(route):
        uploaded.append(route.request.post_data_buffer)
        route.fulfill(status=200, content_type="application/json", body='{"ok":true}')
    page.route("**/api/" + section + "/install-upload", receive)
    page.evaluate("section=>MyAgentSettings.showSection(section,{force:true})", section)
    if section == "skills":
        page.locator('[data-act="skill-add"]').click()
    page.locator('[data-package-kind="' + section + '"]').evaluate("""zone=>{
      const data=new DataTransfer();data.items.add(new File(['archive-content'],'example.zip',{type:'application/zip'}));
      zone.dispatchEvent(new DragEvent('drop',{bubbles:true,cancelable:true,dataTransfer:data}));
    }""")
    page.wait_for_function("document.getElementById('st-toast').textContent==='已安装'")
    assert len(uploaded) == 1
    assert b"archive-content" in uploaded[0] and b"example.zip" in uploaded[0]


def test_mcp_add_precedes_server_groups_and_tools_stay_in_their_group(settings_page):
    page, _ = settings_page
    _mock_json(page, "/api/mcp/tools", {"servers": [{"server": "alpha", "connected": True}, {"server": "beta", "connected": False}],
        "tools": [{"server": "alpha", "function_name": "alpha_one"}, {"server": "alpha", "function_name": "alpha_two"}, {"server": "beta", "function_name": "beta_one"}]})
    page.evaluate("MyAgentSettings.showSection('mcp',{force:true})")
    page.locator('[data-mcp-server="beta"]').wait_for()
    assert page.locator("#st-body .st-card .st-t").all_text_contents()[:3] == ["工具按需披露", "添加服务器", "已添加服务器"]
    assert page.locator('[data-mcp-server="alpha"] [data-key^="mcp:"]').count() == 2
    assert page.locator('[data-mcp-server="beta"] [data-key^="mcp:"]').count() == 1


def test_tool_disclosure_mode_and_group_controls_send_validated_settings(settings_page):
    page, requests = settings_page
    _mock_json(page, "/api/mcp/tools", {"servers": [{"server": "alpha", "connected": True}],
        "tools": [{"server": "alpha", "function_name": "mcp_alpha_read", "tool_name": "read"}]})
    _mock_json(page, "/api/mcp_config", {"text": json.dumps({"servers": {"alpha": {"command": "demo"}}}), "path": "fixture"})
    page.evaluate("MyAgentSettings.showSection('mcp',{force:true})")
    page.locator('[data-field="tool-search-mode"]').wait_for()
    page.locator('[data-field="tool-search-mode"]').select_option("auto")
    page.locator('[data-field="tool-search-pct"]').fill("5")
    page.locator('[data-field="tool-search-tokens"]').fill("10000")
    page.locator('[data-act="tool-search-save"]').click()
    page.wait_for_function("document.getElementById('st-toast').textContent.includes('已保存')")
    saved = next(row for row in requests if row["path"] == "/api/tool_search/config" and row["method"] == "POST")
    assert json.loads(saved["body"])["enabled"] == "auto"
    assert json.loads(saved["body"])["threshold_pct"] == 5
    assert json.loads(saved["body"])["threshold_tokens"] == 10000
    page.locator('[data-act="mcp-disable-group"]').click()
    page.wait_for_function("document.getElementById('st-toast').textContent==='已更新'")
    group = next(row for row in requests if row["path"] == "/api/mcp/servers/alpha/tools/enabled")
    assert json.loads(group["body"]) == {"enabled": False}
    page.locator('[data-act="mcp-pin"]').click()
    page.wait_for_function("document.getElementById('st-toast').textContent==='已更新常驻配置'")
    pin = next(row for row in requests if row["path"] == "/api/mcp_config" and row["method"] == "POST")
    assert json.loads(json.loads(pin["body"])["text"])["servers"]["alpha"]["tools"]["pin"] == ["mcp_alpha_read"]


def test_plugin_page_link_is_in_contributed_pages_card(settings_page):
    page, _ = settings_page
    _mock_json(page, "/api/plugins/catalog", {"plugins": [{"id": "demo", "name": "Demo", "loaded": True}],
        "ui_contributions": [{"slot": "navigation", "plugin_id": "demo", "id": "main", "label": "Demo page", "target": "plugin-page", "href": "/plugins/demo"}]})
    page.evaluate("MyAgentSettings.showSection('plugins',{force:true})")
    page.locator('[data-key="plugin:demo"]').wait_for()
    row = page.locator('[data-key="plugin:demo"]').locator("xpath=ancestor::div[contains(@class,'st-lrow')]")
    assert row.locator('a[href="/plugins/demo"]').count() == 0
    card = page.locator("#st-body .st-card").filter(has_text="插件页面与设置")
    assert card.locator('a[href="/plugins/demo"]').inner_text() == "打开"
    assert page.locator('a[href="/plugins/demo"]').count() == 1


def test_folder_drop_reads_every_directory_batch_and_preserves_relative_paths(settings_page):
    page, _ = settings_page
    uploads = []
    def receive(route):
        uploads.append(route.request.post_data_buffer)
        route.fulfill(status=200, content_type="application/json", body='{"ok":true}')
    page.route("**/api/skills/install-upload", receive)
    page.evaluate("MyAgentSettings.showSection('skills',{force:true})")
    page.locator('[data-act="skill-add"]').click()
    page.locator('[data-package-kind="skills"]').evaluate("""zone=>{
      const file=(name,text)=>({name,isFile:true,file:resolve=>resolve(new File([text],name))});
      const dir=(name,batches)=>({name,isDirectory:true,createReader:()=>{let index=0;return{readEntries:resolve=>resolve(batches[index++]||[])}}});
      const entry=dir('example',[[file('SKILL.md','skill-body')],[dir('assets',[[file('example.txt','asset-body')]])]]);
      const event=new DragEvent('drop',{bubbles:true,cancelable:true});
      Object.defineProperty(event,'dataTransfer',{value:{types:['Files'],items:[{kind:'file',webkitGetAsEntry:()=>entry}],files:[]}});
      zone.dispatchEvent(event);
    }""")
    page.wait_for_function("document.getElementById('st-toast').textContent==='已安装'")
    assert b'filename="example/SKILL.md"' in uploads[0]
    assert b'filename="example/assets/example.txt"' in uploads[0]
    assert b"skill-body" in uploads[0] and b"asset-body" in uploads[0]


def test_paths_show_defaults_without_persisting_untouched_values(settings_page):
    page, requests = settings_page
    paths = {"WORK_DIR": ["D:\\work"], "SKILLS_DIR": ["D:\\work\\skills"], "PLUGINS_DIR": ["D:\\plugins", "D:\\user-plugins"], "LOG_DIR": ["D:\\logs"]}
    _mock_json(page, "/api/env", {"groups": [], "effective_paths": paths})
    page.evaluate("MyAgentSettings.showSection('paths',{force:true})")
    assert page.locator('[data-path-key="WORK_DIR"]').input_value() == "D:\\work"
    assert "D:\\user-plugins" in page.locator("#st-body").inner_text()
    page.locator('[data-act="save"]').click()
    assert not any(request["method"] == "POST" for request in requests)
    page.locator('[data-path-key="LOG_DIR"]').fill("D:\\changed-logs")
    page.locator('[data-act="save"]').click()
    page.wait_for_function("document.getElementById('st-toast').textContent.includes('已保存')")
    body = json.loads(next(request["body"] for request in requests if request["method"] == "POST"))
    assert body == {"values": {"LOG_DIR": "D:\\changed-logs"}}


def test_security_uses_session_permissions_and_shared_option_labels(settings_page):
    page, requests = settings_page
    _mock_json(page, "/sessions/fixture/permissions", {"mode": "approve_for_me"})
    page.evaluate("MyAgentSettings.showSection('security',{force:true})")
    page.locator('[data-key="mode"][data-val="approve_for_me"]').wait_for()
    assert "is-on" in page.locator('[data-key="mode"][data-val="approve_for_me"]').get_attribute("class")
    assert page.locator('[data-key="mode"][data-val="full_access"]').inner_text() == "完全访问权限"
    assert not any(request["path"] == "/api/security/permissions" for request in requests)


def test_plugin_settings_section_registers_form_paths_saves_and_removes_on_reload(settings_page):
    page, requests = settings_page
    contribution = {"slot": "settings.section", "plugin_id": "demo", "id": "main", "title": "Demo <Settings>", "target": "plugin-settings", "endpoint": "/api/plugins/demo/settings"}
    _mock_json(page, "/api/plugins/demo/settings", {"settings": {"title": "Demo", "fields": [
        {"id": "folder", "type": "string", "format": "directory", "value": "D:\\data"},
        {"id": "enabled", "type": "boolean", "value": False},
        {"id": "token", "type": "string", "format": "secret", "configured": True},
    ]}})
    page.evaluate("item=>MyAgentSettings.syncPluginSections({ui_contributions:[item]})", contribution)
    assert page.locator('[data-id="plugin:demo:main"]').inner_text() == "Demo <Settings>"
    page.locator('[data-id="plugin:demo:main"]').click()
    page.locator('[data-field="folder"]').wait_for()
    assert page.locator("#st-body .path-browse-btn").count() == 1
    page.locator('[data-field="folder"]').fill("D:\\new-data")
    page.locator('[data-act="save"]').click()
    page.wait_for_function("document.getElementById('st-toast').textContent.includes('已保存')")
    body = json.loads(next(request["body"] for request in requests if request["path"] == "/api/plugins/demo/settings" and request["method"] == "PATCH"))
    assert body == {"values": {"folder": "D:\\new-data", "enabled": False}}
    page.evaluate("MyAgentSettings.syncPluginSections({ui_contributions:[]})")
    assert page.locator('[data-id="plugin:demo:main"]').count() == 0
    page.locator('[data-field="plugin-source"]').wait_for()


def test_skill_search_by_description_keeps_query_on_reload(settings_page):
    page, requests = settings_page
    page.evaluate("MyAgentSettings.showSection('skills',{force:true})")
    search = page.locator('[data-act="search"]')
    search.press_sequentially("pdf", delay=180)
    page.wait_for_function("document.querySelector('[data-key=\"skill:beta\"]').closest('.st-lrow').hidden")
    assert search.input_value() == "pdf"
    assert page.evaluate("document.activeElement.dataset.act") == "search"
    assert len([request for request in requests if request["path"] == "/api/skills"]) == 1
    page.evaluate("MyAgentSettings.reload()")
    assert page.locator('[data-act="search"]').input_value() == "pdf"
    assert page.locator('[data-key="skill:alpha"]').is_visible()
    assert not page.locator('[data-key="skill:beta"]').is_visible()


def test_legacy_fragment_and_slow_section_cannot_replace_current_view(settings_page):
    page, _ = settings_page
    page.goto("http://settings.test/settings#env?_=123")
    page.locator('[data-env-key="FOO"]').wait_for()
    result = page.evaluate("""async () => {
      MyAgentSettings.registerSection({id:'slow',zh:'Slow',load:()=>new Promise(resolve=>window.resolveSlow=resolve),
        render:()=>'<p id="stale-view">stale</p>'});
      const pending=MyAgentSettings.showSection('slow',{force:true});
      await MyAgentSettings.showSection('skills',{force:true});
      resolveSlow({});await pending;
      return {stale:!!document.getElementById('stale-view'),skill:!!document.querySelector('[data-key="skill:alpha"]')};
    }""")
    assert result == {"stale": False, "skill": True}


def test_advanced_model_options_save_and_probe_error_is_visible(settings_page):
    page, requests = settings_page
    page.evaluate("MyAgentSettings.showSection('models',{force:true})")
    page.locator('[data-act="model-edit"]').click()
    page.locator("#st-dlg-body details summary").click()
    page.locator('[data-field="responses_store_disabled"]').check()
    page.locator('[data-field="system_prompt_mode"]').select_option("merge")
    page.locator('[data-field="multimodal_mode"]').select_option("enabled")
    page.locator('[data-input-modality="image"]').check()
    page.locator('[data-field="capability_description"]').fill("Manual capabilities")
    page.locator('[data-act="model-probe"]').click()
    page.wait_for_function("document.querySelector('[data-model-probe-status]').textContent.includes('HTTP 400: fixture detail')")
    assert page.locator('[data-field="model_context_window"]').input_value() == "32000"
    page.locator("#st-dlg-ok").click()
    page.locator("#st-dialog").wait_for(state="hidden")
    payload = json.loads(next(request["body"] for request in requests
                              if request["path"] == "/api/model_profiles" and request["method"] == "POST"))
    assert payload["responses_store_disabled"] is True
    assert payload["system_prompt_mode"] == "merge" and payload["multimodal_mode"] == "enabled"
    assert payload["input_modalities"] == ["text", "image"]
    assert payload["capability_description"] == "Manual capabilities"
    assert payload["model_context_window"] == 32000


@pytest.mark.parametrize("group", ["servers", "mcpServers"])
def test_mcp_add_preserves_existing_servers_and_schema(settings_page, group):
    page, requests = settings_page
    page.evaluate("MyAgentSettings.showSection('mcp',{force:true})")
    page.locator('[data-field="mcp-url"]').wait_for()
    original = {"enabled": False, "custom": {"keep": True}, group: {
        "server-2": {"command": "existing", "args": ["keep"]}, "custom-server": {"url": "http://old/sse"}}}
    page.evaluate("text=>MyAgentSettings.__mcpText=text", json.dumps(original))
    page.locator('[data-field="mcp-url"]').fill("http://new/sse")
    with page.expect_response(lambda response: response.request.method == "POST" and response.url.endswith("/api/mcp_config")):
        page.locator('[data-act="mcp-add-url"]').click()
    payload = json.loads(next(request["body"] for request in requests
                              if request["path"] == "/api/mcp_config" and request["method"] == "POST"))
    expected = {**original, group: {**original[group], "server-1": {"url": "http://new/sse"}}}
    assert json.loads(payload["text"]) == expected


@pytest.mark.parametrize("raw,command,args", [
    (r'"C:\Program Files\nodejs\node.exe" "C:\My Tools\server.js" --root "D:\Shared Docs"',
     r"C:\Program Files\nodejs\node.exe", [r"C:\My Tools\server.js", "--root", r"D:\Shared Docs"]),
    ('npx.cmd -y fixture --label "two words" ""', "npx.cmd", ["-y", "fixture", "--label", "two words", ""]),
    (r'''node 'C:\My Tools\server.js' "say \"hello\"" "C:\data\\"''',
     "node", [r"C:\My Tools\server.js", 'say "hello"', "C:\\data\\"]),
])
def test_mcp_command_quotes_preserve_argv(settings_page, raw, command, args):
    page, requests = settings_page
    page.evaluate("MyAgentSettings.showSection('mcp',{force:true})")
    page.locator('[data-field="mcp-cmd"]').fill(raw)
    with page.expect_response(lambda response: response.request.method == "POST" and response.url.endswith("/api/mcp_config")):
        page.locator('[data-act="mcp-add-cmd"]').click()
    payload = json.loads(next(request["body"] for request in requests
                              if request["path"] == "/api/mcp_config" and request["method"] == "POST"))
    assert json.loads(payload["text"])["servers"]["server-1"] == {"command": command, "args": args}


@pytest.mark.parametrize("config,command", [("{", "node"), ("[]", "node"), ('{"servers":[]}', "node"), ("{}", 'node "unclosed')])
def test_mcp_invalid_config_or_command_is_not_saved(settings_page, config, command):
    page, requests = settings_page
    page.evaluate("MyAgentSettings.showSection('mcp',{force:true})")
    page.locator('[data-field="mcp-cmd"]').wait_for()
    page.evaluate("text=>MyAgentSettings.__mcpText=text", config)
    page.locator('[data-field="mcp-cmd"]').fill(command)
    page.locator('[data-act="mcp-add-cmd"]').click()
    assert not any(request["method"] == "POST" for request in requests)


@pytest.mark.parametrize("entry", ["back", "child-escape", "child-mask", "host-escape", "host-mask", "api"])
def test_unsaved_settings_guard_all_close_entries(settings_page, entry):
    page, _ = settings_page
    page.goto("http://settings.test/host")
    page.evaluate("myagentOpenSettings('env')")
    frame = page.frame_locator("#settings-center-frame")
    field = frame.locator('[data-env-key="FOO"]')
    field.fill("unsaved value")

    def close():
        if entry == "back":
            frame.locator("#st-back").click()
        elif entry == "child-escape":
            field.press("Escape")
        elif entry == "child-mask":
            frame.locator(".st-stage").evaluate("node=>node.click()")
        elif entry == "host-escape":
            page.evaluate("document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape'}))")
        elif entry == "host-mask":
            page.locator("#settings-center-overlay").evaluate("node=>node.click()")
        else:
            page.evaluate("myagentCloseSettings()")

    dialogs = []
    def reject(dialog):
        dialogs.append(dialog.message)
        dialog.dismiss()

    page.on("dialog", reject)
    try:
        close()
        assert len(dialogs) == 1 and "未保存" in dialogs[0]
        assert page.locator("#settings-center-overlay").is_visible()
        assert field.input_value() == "unsaved value"
    finally:
        page.remove_listener("dialog", reject)
    page.once("dialog", lambda dialog: dialog.accept())
    close()
    page.locator("#settings-center-overlay").wait_for(state="hidden")
    assert page.locator("#settings-center-frame").get_attribute("src").endswith("#env")
    frame.locator('body').evaluate("window.__settingsReuseToken = 'retained'")
    page.evaluate("myagentOpenSettings('env')")
    frame.locator('[data-env-key="FOO"]').wait_for()
    assert frame.locator('body').evaluate("window.__settingsReuseToken") == 'retained'
    assert frame.locator('[data-env-key="FOO"]').input_value() == 'original'


@pytest.mark.parametrize("embedded", [False, True])
@pytest.mark.parametrize("stored,theme,color", [
    ("deep-dark", "theme-dark", "rgb(44, 44, 46)"),
    ("purple", "theme-purple", "rgb(35, 35, 52)"),
    ("dark", "theme-purple", "rgb(35, 35, 52)"),
    ("light", "theme-light", "rgb(255, 255, 255)"),
])
def test_settings_first_paint_has_theme_and_embedded_canvas_before_core_load(settings_page, embedded, stored, theme, color):
    page, _ = settings_page
    original = page.evaluate("localStorage.getItem('myagent-theme')")
    page.evaluate("value=>localStorage.setItem('myagent-theme',value)", stored)
    held = []
    pattern = "**/static/settings/core.js?*"
    def delay_core(route):
        held.append(route)

    if embedded:
        page.goto("http://settings.test/host")
    page.route(pattern, delay_core)
    try:
        with page.expect_request(pattern):
            if embedded:
                page.evaluate("myagentOpenSettings('env')")
                page.frame_locator("#settings-center-frame").locator(".st-panel").wait_for()
                target = page.frame(url=lambda url: "/settings?" in url)
            else:
                page.goto("http://settings.test/settings?first-paint=1#env", wait_until="commit")
                page.locator(".st-panel").wait_for()
                target = page
        snapshot = target.evaluate("""() => ({
          coreLoaded:!!window.MyAgentSettings,
          classes:Array.from(document.documentElement.classList),
          panel:getComputedStyle(document.querySelector('.st-panel')).backgroundColor,
          body:getComputedStyle(document.body).backgroundColor
        })""")
        assert held and not snapshot["coreLoaded"]
        assert theme in snapshot["classes"]
        assert snapshot["panel"] == color
        assert ("st-embedded" in snapshot["classes"]) is embedded
        if embedded:
            assert snapshot["body"] == "rgba(0, 0, 0, 0)"
    finally:
        page.unroute(pattern, delay_core)
        for route in held:
            route.fulfill(status=200, content_type="application/javascript",
                          body=(ROOT / "app/templates/static/settings/core.js").read_text(encoding="utf-8"))
        page.evaluate("value=>{if(value===null)localStorage.removeItem('myagent-theme');else localStorage.setItem('myagent-theme',value);}", original)


def load_plugin(page, relative):
    page.goto("about:blank")
    source = (ROOT / relative).read_bytes()
    url = "data:text/javascript;base64," + base64.b64encode(source).decode()
    page.evaluate("url=>import(url).then(mod=>{window.plugin=mod;})", url)


def test_change_review_teardown_detaches_language_listener(browser_page):
    page = browser_page
    load_plugin(page, "plugins/change-review/web/change-review.js")
    page.set_content('<div class="chat-stage"><div class="panel-inner"><div class="composer-row"></div></div></div>')
    errors = []
    def record(error):
        errors.append(str(error))
    page.on("pageerror", record)
    try:
        page.evaluate("""async () => {
          const cleanup=await plugin.installChatExtension({});
          if(typeof cleanup!=='function')throw new Error('extension was not mounted');
          cleanup();document.dispatchEvent(new CustomEvent('myagent:language-change'));
        }""")
        page.wait_for_timeout(100)
        assert errors == []
    finally:
        page.remove_listener("pageerror", record)


@pytest.mark.parametrize("status", ["active", "paused"])
def test_goal_clock_preserves_narrow_buttons_and_skips_hidden_or_paused(browser_page, status):
    page = browser_page
    load_plugin(page, "plugins/agent-goal/web/session-panel.js")
    page.set_content('<div id="goal-panel"></div><div id="strip"><div data-pubar-narrow-item="goal"><span class="pni-chip"></span><button id="narrow-action">Action</button></div></div>')
    sidebar = (ROOT / "frontend/src/app/modules/public-sidebar.js").read_text(encoding="utf-8")
    # Extract the real functions without executing the complete application bootstrap.
    def _sidebar_fn(anchor):
        start = sidebar.index(anchor)
        return sidebar[start:sidebar.index("\n}", start) + 2]
    page.add_script_tag(content="var pubarNarrowConfigs={},pubarNarrowStripEl=document.getElementById('strip');"
                         "var pubarNarrowOpenId=null;"
                         "function pubarFindPane(id){return id==='goal'?{id}:null;}"
                         + _sidebar_fn("function pubarNarrowHasOpen(")
                         + _sidebar_fn("function pubarNarrowConfigOf(")
                         + _sidebar_fn("function pubarNarrowSignature(")
                         + _sidebar_fn("function pubarUpdateNarrowChip("))
    result = page.evaluate("""status => {
      let now=1000,configure=0;const originalNow=Date.now,interval=setInterval,clear=clearInterval;
      Date.now=()=>now;globalThis.setInterval=fn=>{window.tick=fn;return 1;};globalThis.clearInterval=()=>{};
      window.MyAgentPubar={notifyActivity(){},configureNarrow(id,config){configure++;pubarNarrowConfigs[id]=config;},
        updateNarrowChip:pubarUpdateNarrowChip};
      const cleanup=plugin.renderSessionPanel({container:document.getElementById('goal-panel'),sessionId:'s',
        item:{fields:[{label:'Objective',value:'Fixture goal'},{label:'Status',value:status}]},
        request:()=>new Promise(()=>{}),notifyStateChanged(){}});
      const action=document.getElementById('narrow-action');action.focus();
      now+=5000;tick();const afterTick=document.querySelector('.pni-chip').textContent;
      Object.defineProperty(document,'hidden',{configurable:true,value:true});
      now+=5000;tick();const afterHidden=document.querySelector('.pni-chip').textContent;
      delete document.hidden;document.dispatchEvent(new Event('visibilitychange'));
      const afterVisible=document.querySelector('.pni-chip').textContent;
      cleanup();Date.now=originalNow;globalThis.setInterval=interval;globalThis.clearInterval=clear;
      return {configure,afterTick,afterHidden,afterVisible,sameButton:action===document.getElementById('narrow-action'),
        focusKept:document.activeElement===action};
    }""", status)
    assert result["configure"] == 1 and result["sameButton"] and result["focusKept"]
    assert result["afterTick"] == result["afterHidden"]
    if status == "active":
        assert "5秒" in result["afterTick"] and "10秒" in result["afterVisible"]
    else:
        assert result["afterTick"] == result["afterVisible"]


def test_todo_clear_refreshes_once_and_removes_card(browser_page):
    page = browser_page
    load_plugin(page, "plugins/session-todo/web/session-panel.js")
    page.set_content('<div id="todo"></div>')
    result = page.evaluate("""async () => {
      const container=document.getElementById('todo');let refreshes=0,notifications=0,actions=0;
      globalThis.confirm=()=>true;
      plugin.renderSessionPanel({container,item:{fields:[{label:'Total',value:1},{label:'Completed',value:0}]},
        invokeAction:async()=>{actions++;},notifyStateChanged:()=>{notifications++;},
        refresh:async()=>{refreshes++;container.replaceChildren();}});
      container.querySelector('.chat-todo-plan-close').click();
      await Promise.resolve();await Promise.resolve();
      return {refreshes,notifications,actions,removed:!container.querySelector('.chat-todo-plan-panel')};
    }""")
    assert result == {"refreshes": 1, "notifications": 0, "actions": 1, "removed": True}


@pytest.mark.parametrize("kind", ["goal", "todo"])
def test_activity_uses_session_identity_across_recreated_panel_dom(browser_page, kind):
    page = browser_page
    module = "plugins/agent-goal/web/session-panel.js" if kind == "goal" else "plugins/session-todo/web/session-panel.js"
    load_plugin(page, module)
    page.set_content('<div id="panels"></div>')
    result = page.evaluate("""kind => {
      let notifications=0;
      window.MyAgentPubar={notifyActivity(){notifications++;},configureNarrow(){},updateNarrowChip(){}};
      function render(sessionId,status='active',text='Fixture',used=0) {
        const container=document.createElement('section');document.getElementById('panels').replaceChildren(container);
        const fields=kind==='goal'
          ? [{label:'Objective',value:text},{label:'Status',value:status},{label:'Used tokens',value:used}]
          : [{label:'Completed',value:0},{label:'Total',value:2},{label:'Items',rows:[
              {values:[status==='active'?'pending':'in_progress',text]},{values:['pending','Second']}]}];
        const cleanup=plugin.renderSessionPanel({container,sessionId,item:{pluginId:kind,id:'panel',fields},
          request:()=>new Promise(()=>{}),notifyStateChanged(){}});
        if(typeof cleanup==='function')cleanup();
      }
      render('a');render('a');render('a','active','Fixture',100);
      const unchanged=notifications;
      render('b');render('a');const sessions=notifications;
      render('a','paused');render('a','paused','Changed');
      return {unchanged,sessions,changed:notifications};
    }""", kind)
    assert result == {"unchanged": 1, "sessions": 2, "changed": 4}
