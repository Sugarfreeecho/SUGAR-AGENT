from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SESSION_MANAGEMENT = ROOT / "frontend/src/app/modules/session-management.js"
MESSAGE_RENDERING = ROOT / "frontend/src/app/modules/message-rendering.js"
SHELL_BODY = ROOT / "frontend/src/shell-body.html"
INDEX_HTML = ROOT / "frontend/index.html"
APP_STYLES = ROOT / "frontend/src/styles/app.css"


def test_session_menu_has_requested_groups_and_order():
    source = SESSION_MANAGEMENT.read_text(encoding="utf-8")
    start = source.index("function buildSessionMoreMenuMarkup() {")
    end = source.index("function findSessionForActions", start)
    menu = source[start:end]

    ordered = [
        "session-menu-pin",
        "session-menu-rename",
        "session-menu-archive",
        "session-menu-separator",
        "session-menu-export",
        "session-menu-delete",
    ]
    positions = [menu.index(token) for token in ordered]
    assert positions == sorted(positions)


def test_export_menu_confirms_then_downloads_session_zip():
    source = SESSION_MANAGEMENT.read_text(encoding="utf-8")
    start = source.index("async function exportSessionFromMenu(sess) {")
    end = source.index("async function deleteSessionFromMenu", start)
    export_body = source[start:end]

    assert "await openUiModal({" in export_body
    assert "'/sessions/' + encodeURIComponent(sess.id) + '/export'" in export_body
    assert "link.download" in export_body
    assert "link.click();" in export_body


def test_titlebar_has_persistent_session_action_menu():
    sessions = SESSION_MANAGEMENT.read_text(encoding="utf-8")
    rendering = MESSAGE_RENDERING.read_text(encoding="utf-8")
    shells = [SHELL_BODY.read_text(encoding="utf-8"), INDEX_HTML.read_text(encoding="utf-8")]
    styles = APP_STYLES.read_text(encoding="utf-8")

    assert all('id="breadcrumb-session-actions"' in shell for shell in shells)
    assert "function syncTitlebarSessionMenu(sess)" in sessions
    assert "bindSessionActionMenu(wrap" in sessions
    assert "syncTitlebarSessionMenu(sess" in rendering
    assert ".breadcrumb-session-actions .session-more-btn { opacity: 0.68; }" in styles
    assert ".session-item:hover .session-more-btn" in styles
