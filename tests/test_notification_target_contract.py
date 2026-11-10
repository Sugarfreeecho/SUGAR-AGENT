from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_frontend_consumes_notification_activation_target():
    session = (ROOT / "frontend/src/app/modules/session-management.js").read_text(encoding="utf-8")
    host = (ROOT / "frontend/src/app/modules/dock/embedder/page-host.js").read_text(encoding="utf-8")

    assert "payload.activation_target" in session
    assert "applyUiActivationTarget(activationTarget" in session
    assert "function applyUiActivationTarget" in host
    assert "open_plugin" in host and "open_page" in host and "open_settings" in host
    assert "myagent:plugin-ui-ready" in host
    assert "myagent:session-change" in host


def test_desktop_shell_and_toast_share_target_parameter_names():
    electron = (ROOT / "packaging/electron/main.js").read_text(encoding="utf-8")
    notify = (ROOT / "packaging/electron/notifications.js").read_text(encoding="utf-8")
    toast = (ROOT / "app/notify_ui_closed.ps1").read_text(encoding="utf-8")

    for source in (electron, notify):
        assert "plugin" in source and "page" in source and "section" in source
        assert "open_plugin" in source or "plugin_id" in source
    assert "SUGARAGENT_NOTIFY_PLUGIN" in toast
    assert "SUGARAGENT_NOTIFY_PAGE" in toast
    assert "SUGARAGENT_NOTIFY_SECTION" in toast
    assert "$safeLaunchUri" in toast
