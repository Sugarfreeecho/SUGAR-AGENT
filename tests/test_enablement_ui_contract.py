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
