from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_model_profile_switcher_and_configuration_page_expose_enablement_controls():
    switcher = (ROOT / "frontend/src/app/modules/model-profiles.js").read_text(encoding="utf-8")
    settings = (ROOT / "app/templates/advance_config.html").read_text(encoding="utf-8")
    backend = (ROOT / "app/webui.py").read_text(encoding="utf-8")

    assert "data-toggle-profile-id" in switcher
    assert "setModelProfileEnabled" in switcher
    assert "data-act='toggle'" in settings
    assert "setConfiguredProfileEnabled" in settings
    assert '@fastapi_app.post("/api/model_profiles/{profile_id}/enabled")' in backend


def test_running_subagent_model_switch_is_exposed_in_tool_api_and_ui():
    tools = (ROOT / "app/agent_tools.py").read_text(encoding="utf-8")
    backend = (ROOT / "app/webui.py").read_text(encoding="utf-8")
    frontend_entry = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    shell_body = (ROOT / "frontend/src/shell-body.html").read_text(encoding="utf-8")
    renderers = (ROOT / "frontend/src/app/state/subagent-renderers.js").read_text(encoding="utf-8")
    actions = (ROOT / "frontend/src/app/state/subagent-actions.js").read_text(encoding="utf-8")
    dialogs = (ROOT / "frontend/src/app/modules/shared-state-and-dialogs.js").read_text(encoding="utf-8")
    styles = (ROOT / "frontend/src/styles/app.css").read_text(encoding="utf-8")

    assert '"switch_model"' in tools
    assert "use action=switch_model to change it" in tools
    assert '@fastapi_app.post("/sessions/{parent_id}/subagents/{child_id}/model_profile")' in backend
    assert "subagent-card-switch-model" in renderers
    assert "chooseSubagentModelProfile" in actions
    assert "/model_profile'" in actions
    assert "selectOptions" in dialogs
    assert 'id="ui-modal-select"' in frontend_entry
    assert 'id="ui-modal-select"' in shell_body
    assert 'id="ui-modal-select-control"' in frontend_entry
    assert 'id="ui-modal-select-control"' in shell_body
    assert ".ui-modal-select-trigger" in styles
    assert ".ui-modal-select-menu" in styles
    assert ".ui-modal-select-option.is-selected" in styles
    assert "background: var(--floating-surface); box-shadow: var(--floating-shadow);" in styles
    assert "--floating-surface: rgba(255, 255, 255, 0.99);" in styles
    assert "subagentModelProfileOptionMeta" in actions
    assert "ui-modal-select-control" in dialogs
    assert "setSelectMenuOpen" in dialogs


def test_model_profile_hover_detail_exposes_profile_id():
    switcher = (ROOT / "frontend/src/app/modules/model-profiles.js").read_text(encoding="utf-8")

    assert "'model_porfile_id: ' + String(p.id" in switcher


def test_pending_followup_mode_uses_custom_picker_instead_of_native_select():
    frontend = (ROOT / "frontend/src/app/modules/sse-handling.js").read_text(encoding="utf-8")
    styles = (ROOT / "frontend/src/styles/app.css").read_text(encoding="utf-8")

    assert "createFollowupModePicker" in frontend
    assert "closeActiveFollowupModePicker" in frontend
    assert "document.createElement('select')" not in frontend[frontend.index("function renderFollowupQueue"):frontend.index("function getFollowupStatusText")]
    assert "立即插入当前运行" in frontend
    assert "下一轮继续处理" in frontend
    assert ".followup-mode-picker" in styles
    assert ".followup-mode-menu" in styles
    assert ".followup-mode-option.is-selected" in styles
    assert "background: var(--floating-surface); box-shadow: var(--floating-shadow);" in styles
    assert "--floating-surface: rgba(255, 255, 255, 0.99);" in styles
    assert "position: fixed; z-index: 390" in styles
    assert "document.body.appendChild(menu)" in frontend
    assert "getBoundingClientRect()" in frontend
    assert "var visualSelect = document.createElement('select');" in frontend
    assert "visualSelect.className = 'followup-queue-mode';" in frontend
    assert ".followup-mode-hit-target" in styles
    assert ".followup-mode-direction" in styles
    assert "rotate(225deg)" in styles
    assert ".followup-mode-picker { position: relative; min-width: 3.7rem; height: 1.55rem; }" in styles
    assert "height: 1.55rem;" in styles
    assert "padding: 0 1.2rem 0 0.48rem;" in styles
    assert "function followupQueueRenderSignature" in frontend
    render_source = frontend[frontend.index("function renderFollowupQueue"):frontend.index("function getFollowupStatusText")]
    assert render_source.index("panel.dataset.renderSignature === renderSignature") < render_source.index("closeActiveFollowupModePicker();")
    assert "followup-mode-trigger-mark" not in frontend
    assert "followup-mode-option-mark" not in frontend
    assert "window.addEventListener('scroll', closeMenu, true)" not in frontend


def test_skill_picker_exposes_enablement_controls():
    picker = (ROOT / "frontend/src/app/modules/skill-picker.js").read_text(encoding="utf-8")
    settings = (ROOT / "app/templates/advance_config.html").read_text(encoding="utf-8")
    styles = (ROOT / "frontend/src/styles/app.css").read_text(encoding="utf-8")
    i18n = (ROOT / "frontend/src/app/modules/i18n.js").read_text(encoding="utf-8")
    backend = (ROOT / "app/webui.py").read_text(encoding="utf-8")

    assert "skill-picker-toggle" in picker
    assert "skill-toggle-action" in picker
    assert "querySelectorAll('.skill-toggle-action')" in picker
    assert "querySelectorAll('.skill-picker-toggle').forEach(function (button)" not in picker
    assert "setSkillPickerEnabled" in picker
    assert "reconcileSelectedSkillsWithEnabledCatalog" in picker
    assert "data-skill-picker-tab" in picker
    assert 'data-skill-picker-tab="hooks"' in picker
    assert 'data-skill-picker-tab="plugins"' in picker
    assert "loadSkillPickerMcpTools" in picker
    assert "mcpServersCache" in picker
    assert "当前没有已配置的 MCP 服务器" in picker
    assert "is-undiscovered" in picker
    assert "'未注册'" in picker
    assert "'未注册': 'Not registered'" in i18n
    assert "mcp-server-register-btn" in picker
    assert "registerMcpServer" in picker
    assert "/api/mcp/servers/" in picker
    assert "服务器尚未完成工具注册；请检查连接、凭据或服务配置。" in picker
    assert "mcp-tool-toggle" in picker
    assert "setMcpToolEnabled" in picker
    assert "loadSkillPickerExtensions" in picker
    assert "plugin-toggle-action" in picker
    assert "plugin-state" in picker
    assert "enabled ? '已启用' : '已禁用'" in picker
    assert "toggleSkillPickerPlugin" in picker
    assert "skillPickerPluginPageHref" in picker
    assert "skillPickerOpenPageHtml" in picker
    assert 'class="skill-picker-toggle plugin-toggle-action"' in picker
    assert "plugin-open-action" in picker
    assert 'plugin-open-action" href="' in picker
    assert 'target="_blank" rel="noopener noreferrer"' in picker
    assert "window.location.assign(link.href)" not in picker
    assert "advanced-plugin-open' href='\"+esc(pageHref)+\"'" in settings
    assert "advanced-plugin-open' href='\"+esc(pageHref)+\"' target='_blank'" not in settings
    assert "'/api/plugins/' + encodeURIComponent(id) + '/enabled'" in picker
    assert '/api/mcp/tools' in picker
    assert '/api/extensions' in picker
    assert "skillPickerCollapsedGroups" in picker
    assert "skillPickerGroupHtml" in picker
    assert "data-skill-picker-group" in picker
    assert "skill-picker-group-toggle" in picker
    assert ".skill-picker-group" in styles
    assert ".skill-picker-group.is-collapsed .skill-picker-group-chevron" in styles
    assert ".skill-picker-group-items[hidden]" in styles
    assert ".skill-picker-group-summary.is-undiscovered" in styles
    assert ".mcp-server-register-btn" in styles
    assert ".plugin-option-actions" in styles
    assert ".plugin-option-actions .skill-picker-toggle" in styles
    plugin_actions_css = styles[styles.index(".plugin-option-actions {"):styles.index(".plugin-option-actions .skill-picker-toggle")]
    assert "opacity: 1;" in plugin_actions_css
    assert "pointer-events: auto;" in plugin_actions_css
    assert "pointer-events: none;" not in plugin_actions_css
    assert ".plugin-option-action {" not in styles
    assert "grid-auto-rows: max-content" in styles
    assert "align-content: start" in styles
    assert "共 (\\d+) 个工具" in i18n
    assert "个服务器 · (\\d+) 个工具" in i18n
    assert "'未命名服务器': 'Unnamed server'" in i18n
    assert '@fastapi_app.post("/api/skills/{skill_name}/enabled")' in backend
    assert '@fastapi_app.get("/api/mcp/tools")' in backend
    assert '@fastapi_app.post("/api/mcp/servers/{server_name:path}/register")' in backend
    assert '@fastapi_app.post("/api/mcp/tools/{function_name}/enabled")' in backend


def test_ui_presence_tracks_foreground_state_and_attention_notifications():
    frontend = (ROOT / "frontend/src/app/modules/message-rendering.js").read_text(encoding="utf-8")
    backend = (ROOT / "app/webui.py").read_text(encoding="utf-8")
    bus = (ROOT / "app/session_event_bus.py").read_text(encoding="utf-8")
    notify = (ROOT / "app/desktop_notify.py").read_text(encoding="utf-8")

    # The page reports whether it is visible and focused, and pushes updates on
    # visibility/focus changes instead of waiting for the next heartbeat.
    assert "getUiPresenceActive" in frontend
    assert "active: getUiPresenceActive()" in frontend
    assert "sendUiPresence('update')" in frontend
    assert "window.addEventListener('blur'" in frontend
    assert "setTimeout(registerUiPresence, 10000)" in frontend

    # The backend accepts register/update/unregister and tracks the active flag.
    assert '@fastapi_app.post("/api/ui-presence")' in backend
    assert '"register", "update", "unregister"' in backend
    assert "_ui_presence_has_active" in backend
    assert '@fastapi_app.post("/api/ui-activation")' in backend
    assert '@fastapi_app.get("/api/runtime-status")' in backend

    # Conversation completion and pending human interactions feed the same
    # desktop notification path when no UI tab is actively used.
    assert "add_event_listener(_on_session_event_for_attention_notify)" in backend
    assert '"run_finished"' in backend
    assert '"run_failed"' in backend
    assert '"approval_requested"' in backend
    assert '"interaction_requested"' in backend
    assert "show_desktop_notification" in notify
    assert "add_event_listener" in bus

    # The production entrypoint replaces the app's default lifespan, so it
    # must reuse the shared Web UI lifecycle explicitly.
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    assert "initialize_ui_attention_notifications" in backend
    lifespan_start = main.index("async def lifespan(app: FastAPI):")
    lifespan_end = main.index("fastapi_app.router.lifespan_context = lifespan", lifespan_start)
    assert "await start_webui_lifecycle()" in main[lifespan_start:lifespan_end]
    assert "await stop_webui_lifecycle()" in main[lifespan_start:lifespan_end]
