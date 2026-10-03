"""Use real settings/plugin code with isolated API fixtures in a local browser."""
import base64
import json
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from tests.test_llm_stream_window_geometry import browser_page

ROOT = Path(__file__).resolve().parents[1]


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
        "/api/mcp_config": {"text": "{}", "path": "fixture/mcp_servers.json"},
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
                <script>var currentSessionId='fixture';</script><script src="/host-settings.js"></script>''')
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


def _mock_json(page, path, payload, method="GET"):
    def respond(route):
        if route.request.method != method:
            route.fallback()
            return
        route.fulfill(status=200, content_type="application/json", body=json.dumps({"ok": True, **payload}))
    page.route("**" + path, respond)


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


def test_skill_picker_updates_kind_after_source_switch(settings_page):
    page, requests = settings_page
    _mock_json(page, "/api/pick-path", {"path": "D:\\chosen\\example.zip"}, method="POST")
    page.evaluate("MyAgentSettings.showSection('skills',{force:true})")
    page.locator('[data-act="skill-add"]').click()
    field = page.locator('[data-field="source"]')
    assert field.get_attribute("data-path-kind") == "directory"
    page.locator('#st-dlg-body [data-val="zip"]').click()
    assert field.get_attribute("data-path-kind") == "file"
    page.locator("#st-dlg-body .path-browse-btn").click()
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
    assert page.locator("#st-body .st-card .st-t").all_text_contents()[:2] == ["添加服务器", "已添加服务器"]
    assert page.locator('[data-mcp-server="alpha"] [data-key^="mcp:"]').count() == 2
    assert page.locator('[data-mcp-server="beta"] [data-key^="mcp:"]').count() == 1


def test_plugin_page_link_is_in_contributed_pages_card(settings_page):
    page, _ = settings_page
    _mock_json(page, "/api/extensions", {"plugins": [{"id": "demo", "name": "Demo", "loaded": True}],
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
    assert page.locator("#settings-center-frame").get_attribute("src") == "about:blank"


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
    # Extract the real function without executing the complete application bootstrap.
    start = sidebar.index("function pubarUpdateNarrowChip(")
    end = sidebar.index("\n}", start) + 2
    page.add_script_tag(content="var pubarNarrowConfigs={},pubarNarrowStripEl=document.getElementById('strip');"
                         "function pubarFindPane(id){return id==='goal'?{id}:null;}" + sidebar[start:end])
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
