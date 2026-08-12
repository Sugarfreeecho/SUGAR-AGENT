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
    assert ":root.theme-light .ui-modal-select-menu" in styles
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
    assert ":root.theme-light .followup-mode-menu" in styles
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
    backend = (ROOT / "app/webui.py").read_text(encoding="utf-8")

    assert "skill-picker-toggle" in picker
    assert "setSkillPickerEnabled" in picker
    assert "reconcileSelectedSkillsWithEnabledCatalog" in picker
    assert "data-skill-picker-tab" in picker
    assert 'data-skill-picker-tab="hooks"' in picker
    assert 'data-skill-picker-tab="plugins"' in picker
    assert "loadSkillPickerMcpTools" in picker
    assert "mcp-tool-toggle" in picker
    assert "setMcpToolEnabled" in picker
    assert "loadSkillPickerExtensions" in picker
    assert '/api/mcp/tools' in picker
    assert '/api/extensions' in picker
    assert '@fastapi_app.post("/api/skills/{skill_name}/enabled")' in backend
    assert '@fastapi_app.get("/api/mcp/tools")' in backend
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

    # The backend accepts register/update/unregister and tracks the active flag.
    assert '@fastapi_app.post("/api/ui-presence")' in backend
    assert '"register", "update", "unregister"' in backend
    assert "_ui_presence_has_active" in backend

    # Conversation completion and pending human interactions feed the same
    # desktop notification path when no UI tab is actively used.
    assert "add_event_listener(_on_session_event_for_attention_notify)" in backend
    assert '"run_finished"' in backend
    assert '"run_failed"' in backend
    assert '"approval_requested"' in backend
    assert '"interaction_requested"' in backend
    assert "show_desktop_notification" in notify
    assert "add_event_listener" in bus
