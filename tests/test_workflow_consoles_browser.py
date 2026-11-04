"""Production console assets exercise real plugin APIs against isolated stores."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.test_llm_stream_full_text_browser import browser_page

ROOT = Path(__file__).resolve().parents[1]


def load_host(plugin_id):
    path = ROOT / "plugins" / plugin_id / "host.py"
    spec = importlib.util.spec_from_file_location("console_test_" + plugin_id.replace("-", "_"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def consoles(browser_page, tmp_path, monkeypatch):
    import agent_goal
    import agent_harness
    import agent_subagent
    import plugins.host
    import plugin_web_gateway
    import webui
    from plugins import load_plugin
    from plugins.web import resolve_plugin_asset
    from agent_team import tools
    from agent_team.service import AgentTeamService

    monkeypatch.setenv("GOAL_ENABLED", "1")
    monkeypatch.setenv("AGENT_TEAM_ENABLED", "1")
    monkeypatch.setenv("AGENT_TEAM_AUTO_SCHEDULE", "0")
    monkeypatch.setenv("RUNTIME_VERSION", "2")
    calls, metadata, errors, requests = [], {}, [], []

    class Sessions:
        repository = SimpleNamespace(sessions_dir=tmp_path)

        def _resolve_session_path(self, sid): return tmp_path / sid
        def get_session_summary(self, sid): return {"id": sid} if sid in {"s1", "s2"} else None
        def clear_interrupt(self, sid): calls.append(("resume", sid))
        def request_interrupt(self, sid, **kwargs): calls.append(("interrupt", sid))
        def _load_metadata(self, sid): return metadata.get(sid, {})
        def _save_metadata(self, sid, value): metadata[sid] = value
        def create_subagent_session(self, *args, **kwargs):
            sid = "child-" + str(len(metadata) + 1)
            metadata[sid] = {"is_subagent": True, "parent_session_id": args[0], "subagent_run_status": "completed"}
            return sid

    sessions = Sessions()
    for sid in ("s1", "s2"): (tmp_path / sid).mkdir()
    goals = agent_goal.GoalManager(tmp_path)
    teams = AgentTeamService(tmp_path)
    monkeypatch.setattr(agent_goal, "manager_for", lambda _: goals)
    monkeypatch.setattr(plugins.host, "bundled_host_plugin_enabled", lambda _: True)
    monkeypatch.setattr(agent_harness, "session_manager", sessions)
    monkeypatch.setattr(agent_harness, "inherited_executor_selection", lambda _: {"model_profile_id": "test-model"})
    monkeypatch.setattr(agent_subagent, "_create_managed_worktree", lambda _: None)
    monkeypatch.setattr(tools, "_service", lambda: teams)

    async def execute(**kwargs):
        calls.append(("dispatch", kwargs))
        return "Background execution accepted"

    monkeypatch.setattr(agent_subagent, "run_subagent_task", execute)
    app = FastAPI()
    monkeypatch.setattr(plugin_web_gateway, "plugin_page", lambda plugin_id: ROOT / "plugins" / plugin_id / "web/index.html")
    monkeypatch.setattr(plugin_web_gateway, "plugin_asset", lambda plugin_id, asset_path: resolve_plugin_asset(load_plugin(ROOT / "plugins" / plugin_id), asset_path))
    for plugin_id in ("agent-goal", "agent-team"):
        host = load_host(plugin_id)
        host.install(app, {"session_manager": sessions}, SimpleNamespace(plugin_id=plugin_id))
    app.add_api_route('/plugins/{plugin_id}', webui.plugin_web_page)
    app.add_api_route('/plugin-assets/{plugin_id}/{asset_path:path}', webui.plugin_web_asset)
    app.add_api_route('/settings', webui.settings_center_page)
    app.add_api_route('/static/settings/{asset_name}', webui.serve_settings_asset)
    app.add_api_route('/static/myagent_path_picker.js', webui.serve_path_picker_js)
    client = TestClient(app)
    client.__enter__()
    browser_context = browser_page.context.browser.new_context(viewport={"width": 1100, "height": 800})
    page = browser_context.new_page()
    def on_error(error): errors.append(str(error))
    def on_dialog(dialog): dialog.accept()
    page.on("pageerror", on_error)
    page.on("dialog", on_dialog)

    def route(request_route):
        request = request_route.request
        path = urlsplit(request.url).path
        requests.append((request.method, path))
        if path == '/settings' or path.startswith(("/plugins/", "/plugin-assets/", "/static/")):
            parsed = urlsplit(request.url)
            response = client.get(path + ('?' + parsed.query if parsed.query else ''))
            assert response.status_code == 200, f"Console resource unavailable: {path}"
            request_route.fulfill(status=response.status_code, headers=dict(response.headers), body=response.content)
        elif path == "/sessions":
            request_route.fulfill(json=[{"id": "s1", "name": "交付任务"}, {"id": "s2", "name": "另一会话"}])
        elif path == "/api/model_profiles":
            request_route.fulfill(json={"profiles": [{"id": "test-model", "name": "测试模型"}]})
        elif path in ('/api/plugins/catalog', '/api/extensions'):
            from plugins import plugin_ui_contributions
            request_route.fulfill(json={'ok': True, 'plugins': [], 'ui_contributions': [
                row for plugin_id in ('agent-goal', 'agent-team')
                for row in plugin_ui_contributions(load_plugin(ROOT / 'plugins' / plugin_id))]})
        else:
            response = client.request(request.method, path, content=request.post_data, headers={"Content-Type": "application/json"})
            request_route.fulfill(status=response.status_code, content_type="application/json", body=response.content)

    page.route("**/*", route)
    yield SimpleNamespace(page=page, goals=goals, teams=teams, client=client, calls=calls, requests=requests, output=tmp_path)
    page.unroute("**/*", route)
    page.remove_listener("pageerror", on_error)
    page.remove_listener("dialog", on_dialog)
    browser_context.close()
    client.__exit__(None, None, None)
    assert errors == []


def test_goal_create_edit_pause_resume_review_and_session_switch(consoles):
    c, page = consoles, consoles.page
    page.goto("http://127.0.0.1/plugins/agent-goal?session=s1")
    page.locator("#new-objective").fill("完成控制台并通过验证")
    page.locator("#new-budget").fill("1000")
    page.get_by_role("button", name="创建并开始").click()
    page.locator("#goal-status .badge[data-status=active]").wait_for()
    assert c.goals.get("s1")["token_budget"] == 1000
    page.get_by_role("button", name="编辑目标", exact=True).click()
    page.locator("#edit-objective").fill("完成两个插件的控制台")
    page.get_by_role("button", name="保存修改").click()
    page.locator("#edit-dialog").wait_for(state="hidden")
    assert page.locator("#objective").inner_text() == "完成两个插件的控制台"
    page.get_by_role("button", name="暂停目标").click()
    page.locator("#goal-status .badge[data-status=paused]").wait_for()
    assert ('interrupt', 's1') not in c.calls
    page.get_by_role("button", name="恢复目标", exact=True).click()
    page.locator("#resume-budget").fill("500")
    page.get_by_role("button", name="恢复执行").click()
    page.locator("#resume-dialog").wait_for(state="hidden")
    assert c.goals.get("s1")["token_budget"] == 1500
    requested = c.goals.update_status("s1", "completed", "verified", report_id="run-review")
    c.goals.record_judge_result("s1", verdict="done", reason="检查通过", run_id="run-review", expected_completion_request_id=requested["completion_request_id"])
    page.locator("#refresh").click()
    page.locator("#review-card").wait_for()
    page.locator("#feedback").fill("还需检查移动端")
    page.locator("#refresh").click()
    page.wait_for_function("document.getElementById('sync-status').textContent.startsWith('已同步')")
    assert page.locator("#feedback").input_value() == "还需检查移动端"
    page.get_by_role("button", name="保存审核", exact=True).click()
    page.wait_for_function("document.getElementById('notice').textContent==='审核内容已保存'")
    assert c.goals.get("s1")["review_judge_result"] == "还需检查移动端"
    page.get_by_role("button", name="要求继续执行").click()
    page.locator("#goal-status .badge[data-status=active]").wait_for()
    assert c.goals.get("s1")["review_feedback_pending"] is True
    page.locator("#session").fill("s2")
    page.get_by_role("button", name="打开会话").click()
    page.locator("#create-card").wait_for()
    assert page.locator("#new-objective").input_value() == ""
    assert page.locator("#goal-view").is_hidden()


def test_team_create_member_task_dispatch_message_and_archive(consoles):
    c, page = consoles, consoles.page
    page.goto("http://127.0.0.1/plugins/agent-team?session=s1")
    page.locator("#title").fill("交付团队")
    page.get_by_role("button", name="创建团队", exact=True).click()
    page.locator("#team-status .badge[data-status=active]").wait_for()
    page.locator("#new-member").click()
    page.locator("#member-name").fill("Coder")
    page.locator("#member-role").fill("实现与测试")
    page.get_by_role("button", name="创建成员").click()
    page.locator("#member-dialog").wait_for(state="hidden")
    assert len(c.teams.read_team("s1")["members"]) == 1
    assert page.get_by_role("tab", name="成员 1", exact=True).get_attribute("aria-selected") == "true"
    assert page.locator("#team-panel-members").is_visible()
    for title in ("实现控制台", "验证结果"):
        page.locator("#new-task").click()
        page.locator("#task-title").fill(title)
        if title == "验证结果":
            first = next(iter(c.teams.read_team("s1")["tasks"]))
            page.locator("#task-dependencies").select_option(first)
        page.get_by_role("button", name="创建任务", exact=True).click()
        page.locator("#task-dialog").wait_for(state="hidden")
    assert "等待依赖" in page.locator("main").inner_text()
    page.locator("#tasks .item").first.get_by_role("button", name="更新任务").click()
    page.locator("#update-title").fill("实现完整控制台")
    page.locator("#update-description").fill("接通操作与状态反馈")
    page.locator("#update-priority").select_option("high")
    page.get_by_role("button", name="保存任务", exact=True).click()
    page.locator("#update-dialog").wait_for(state="hidden")
    assert "实现完整控制台" in page.locator("#tasks").inner_text()
    page.locator("#tasks .item").first.get_by_role("button", name="派发成员").click()
    page.get_by_role("button", name="后台派发").click()
    page.locator("#dispatch-dialog").wait_for(state="hidden")
    assert any(name == "dispatch" for name, _ in c.calls)
    page.locator("#new-message").click()
    page.locator("#message-recipients").select_option("lead")
    page.locator("#message-content").fill("请检查交付证据 <script>bad()</script>")
    page.locator("#message-form button.primary").click()
    page.locator("#message-dialog").wait_for(state="hidden")
    page.get_by_role("button", name="标为已读").click()
    page.locator("#messages .badge[data-status=consumed]").first.wait_for()
    assert "<script>bad()</script>" in page.locator("#messages").inner_text()
    page.locator("#shutdown").click()
    page.locator("#complete-shutdown").click()
    page.locator("#archive").click()
    page.locator("#team-status .badge[data-status=archived]").wait_for()
    assert c.teams.read_team("s1")["status"] == "archived"


def test_console_mobile_layout_and_error_recovery(consoles):
    c, page = consoles, consoles.page
    c.goals.create("s1", "长目标 " * 600, token_budget=100)
    c.goals.record_usage("s1", 100, usage_id="exhausted", run_id="r1")
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto("http://127.0.0.1/plugins/agent-goal?session=missing")
    page.locator("#error").filter(has_text="session not found").wait_for()
    page.locator("#session").fill("s1")
    page.get_by_role("button", name="打开会话").click()
    page.locator("#goal-view").wait_for()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
    page.get_by_role("button", name="恢复目标", exact=True).click()
    page.get_by_role("button", name="恢复执行", exact=True).click()
    page.locator('#resume-dialog .dialog-error').filter(has_text="additional_budget").wait_for()
    assert page.get_by_role("button", name="恢复执行", exact=True).is_enabled()
    page.get_by_role("button", name="取消", exact=True).click()
    page.set_viewport_size({"width": 1100, "height": 800})


def test_console_ignores_stale_read_after_switching_session(consoles):
    c, page, held = consoles, consoles.page, []
    c.goals.create("s1", "旧会话目标")
    page.route("**/sessions/s1/goal", lambda route: held.append(route))
    page.goto("http://127.0.0.1/plugins/agent-goal?session=s1")
    page.wait_for_function("document.getElementById('sync-status').textContent==='正在同步…'")
    page.locator("#session").fill("s2")
    page.get_by_role("button", name="打开会话").click()
    page.locator("#create-card").wait_for()
    assert held
    try: held[0].fulfill(json={"enabled": True, "goal": c.goals.get("s1")})
    except Exception: pass  # The session switch may already have cancelled the network request.
    page.wait_for_timeout(50)
    assert page.locator("#goal-view").is_hidden()
    assert page.locator("#session").input_value() == "s2"


def test_action_timeout_recovers_controls_and_prevents_duplicate_post(consoles):
    c, page, held = consoles, consoles.page, []
    c.goals.create("s1", "检查超时与重复点击")
    page.clock.install()
    page.goto("http://127.0.0.1/plugins/agent-goal?session=s1")
    page.locator("#goal-view").wait_for()
    page.route("**/sessions/s1/goal/pause", lambda route: held.append(route))
    page.evaluate("""() => { const button = [...document.querySelectorAll('button')].find(el => el.textContent === '暂停目标'); button.click(); button.click(); }""")
    page.wait_for_function("document.getElementById('workspace').getAttribute('aria-busy')==='true'")
    page.wait_for_timeout(50)
    assert len(held) == 1
    page.clock.fast_forward(15001)
    page.locator("#error").filter(has_text="请求超时").wait_for()
    page.wait_for_function("document.getElementById('workspace').inert===false")
    assert page.locator("#refresh").is_enabled()


def test_embedded_console_binds_session_and_stops_polling_when_hidden(consoles):
    c, page = consoles, consoles.page
    c.goals.create("s1", "嵌入控制台目标")
    page.clock.install()
    page.route("**/embed", lambda route: route.fulfill(content_type="text/html", body='''
        <iframe id="console" src="/plugins/agent-goal?surface=details"></iframe>
        <script>addEventListener('message', event => {
          if(event.data.type === 'myagent:plugin-page-ready') document.querySelector('iframe').contentWindow.postMessage({
            type:'myagent:plugin-page-context',version:1,sessionId:'s1',visible:true,theme:'theme-light',lang:'zh'}, location.origin);
        });</script>'''))
    page.goto("http://127.0.0.1/embed")
    frame = page.frame_locator("#console")
    frame.locator("#goal-view").wait_for()
    assert frame.locator("#session").input_value() == "s1"
    page.evaluate("document.querySelector('iframe').contentWindow.postMessage({type:'myagent:plugin-page-context',version:1,sessionId:'s2',visible:true},location.origin)")
    frame.locator("#create-card").wait_for()
    assert frame.locator("#session").input_value() == "s2"
    page.evaluate("document.querySelector('iframe').contentWindow.postMessage({type:'myagent:plugin-page-context',version:1,sessionId:'s2',visible:false},location.origin)")
    page.wait_for_timeout(50)
    before = len([item for item in c.requests if item[1].endswith('/goal')])
    page.clock.fast_forward(20000)
    assert len([item for item in c.requests if item[1].endswith('/goal')]) == before


def test_console_visuals_and_goal_approval(consoles):
    c, page = consoles, consoles.page
    c.goals.create("s1", "完成 Goal 与 Agent Team 控制台\n验收：生命周期操作可用，状态可追踪，异常可恢复。", token_budget=120000)
    c.goals.record_usage("s1", 28640, usage_id="u1", run_id="r1")
    requested = c.goals.update_status("s1", "completed", "浏览器与后端回归通过", report_id="r1")
    c.goals.record_judge_result("s1", "done", "目标已达成，等待人工验收。", run_id="j1", expected_completion_request_id=requested["completion_request_id"])
    out = ROOT / ".analysis/workflow-consoles"
    out.mkdir(parents=True, exist_ok=True)
    page.set_viewport_size({"width": 1100, "height": 850})
    page.goto("http://127.0.0.1/plugins/agent-goal?session=s1")
    page.locator("#review-card").wait_for()
    page.screenshot(path=str(out / "goal-console-bili.png"), full_page=True)
    page.get_by_role("button", name="确认验收", exact=True).click()
    page.locator("#create-card").wait_for()
    assert c.goals.get("s1") is None
    c.teams.create_team("s1", "控制台交付团队")
    for name, role in (("Coder", "实现与集成"), ("Reviewer", "测试与审查")):
        member = c.teams.add_member("s1", name=name, role=role, child_session_id="child-" + name)
        c.teams.set_member_state("s1", member["member_id"], "idle")
    first = c.teams.create_task("s1", title="补齐控制台生命周期操作", description="提供明确状态、预算与审核记录。", priority="high")
    c.teams.update_task("s1", first["task_id"], status="completed", result="接口和浏览器验证通过")
    c.teams.create_task("s1", title="验证依赖任务与关停流程", description="验证任务分配、消息已读和归档。", depends_on=[first["task_id"]])
    c.teams.send_message("s1", sender_id="lead", recipient_ids=["lead"], content="控制台已就绪，请核对验收标准。")
    page.goto("http://127.0.0.1/plugins/agent-team?session=s1")
    page.locator("#team-view").wait_for()
    page.screenshot(path=str(out / "team-console-bili.png"), full_page=True)
    page.get_by_role("tab", name="成员 2", exact=True).click()
    assert page.locator("#members .member-avatar").count() == 2
    page.screenshot(path=str(out / "team-console-members-bili.png"), full_page=True)
    page.locator("#refresh").click()
    page.wait_for_function("document.getElementById('sync-status').textContent.startsWith('已同步')")
    assert page.locator("#team-panel-members").is_visible()
    page.get_by_role("tab", name="成员 2", exact=True).press("ArrowRight")
    assert page.locator("#team-panel-messages").is_visible()
    page.get_by_role("tab", name="消息 1", exact=True).press("Home")
    assert page.locator("#team-panel-tasks").is_visible()
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
    page.screenshot(path=str(out / "team-console-mobile-bili.png"), full_page=True)


@pytest.mark.parametrize("plugin_id", ["agent-goal", "agent-team"])
def test_empty_dashboard_uses_real_shared_assets_and_keeps_creation_visible(consoles, plugin_id):
    page = consoles.page
    page.set_viewport_size({"width": 1100, "height": 680})
    page.route("**/embed", lambda route: route.fulfill(content_type="text/html", body=f'''
        <style>html,body{{margin:0;height:100%}}iframe{{width:100%;height:100%;border:0;display:block}}</style>
        <iframe id="console" src="/plugins/{plugin_id}?surface=details"></iframe>
        <script>addEventListener('message', event => {{
          if(event.data.type === 'myagent:plugin-page-ready') document.querySelector('iframe').contentWindow.postMessage({{
            type:'myagent:plugin-page-context',version:1,sessionId:'s1',visible:true,theme:'theme-dark',lang:'zh'}}, location.origin);
        }});</script>'''))
    page.goto("http://127.0.0.1/embed")
    frame = page.frame_locator("#console")
    frame.locator("#create-card").wait_for()
    assert frame.locator(".session-picker").is_hidden()
    # This checks the public ASGI assets actually styled the iframe, rather than
    # a browser fixture supplying files that the real application cannot serve.
    assert frame.locator(".topbar").evaluate("el => getComputedStyle(el).position") == "sticky"
    assert frame.locator("#workspace").evaluate("el => getComputedStyle(el).display") == "grid"
    button = frame.locator("#create button.primary")
    rect = button.bounding_box()
    assert rect and rect["y"] + rect["height"] <= 680
    out = ROOT / ".analysis/workflow-consoles"
    out.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(out / f"{plugin_id}-empty-bili.png"), full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    assert frame.locator("main").evaluate("el => el.ownerDocument.documentElement.scrollWidth <= 391")


def test_stale_member_can_be_stopped_to_finish_shutdown(consoles):
    c, page = consoles, consoles.page
    c.teams.create_team("s1", "恢复关停")
    member = c.teams.add_member("s1", name="Stale", role="worker", child_session_id="missing-child")
    c.teams.set_member_state("s1", member["member_id"], "working")
    c.teams.request_shutdown("s1")
    page.goto("http://127.0.0.1/plugins/agent-team?session=s1")
    page.locator("#team-view").wait_for()
    assert page.locator("#complete-shutdown").is_disabled()
    page.locator("#members").get_by_role("button", name="中断", exact=True).click()
    page.locator("#members .badge[data-status=stopped]").wait_for()
    page.locator("#complete-shutdown").click()
    page.locator("#team-status .badge[data-status=stopped]").wait_for()
