from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SESSION_MANAGEMENT = ROOT / "frontend/src/app/modules/session-management.js"
SHARED_DIALOGS = ROOT / "frontend/src/app/modules/shared-state-and-dialogs.js"
SHELL_BODY = ROOT / "frontend/src/shell-body.html"
INDEX_HTML = ROOT / "frontend/index.html"


def test_session_list_render_key_only_tracks_structural_content():
    source = SESSION_MANAGEMENT.read_text(encoding="utf-8")

    key_start = source.index("function computeSessionListRenderKey() {")
    render_start = source.index("function renderSessionListIfChanged(force) {", key_start)
    key_body = source[key_start:render_start]

    for structural_field in ("s.name", "s.pinned", "s.archived", "s.last_activity_at", "s.last_user_preview"):
        assert structural_field in key_body
    for transient_field in (
        "currentSessionId",
        "stream_active",
        "unread_result",
        "subagent_running",
        "subagent_pending_continue",
        "subagent_can_continue",
    ):
        assert transient_field not in key_body


def test_switch_session_updates_active_state_without_direct_list_render():
    source = SESSION_MANAGEMENT.read_text(encoding="utf-8")

    switch_start = source.index("async function switchSession(sessionId, opts) {")
    switch_end = source.index("async function createNewSession()", switch_start)
    switch_body = source[switch_start:switch_end]

    assert "syncSessionListIndicatorClasses();" in switch_body
    assert "renderSessionListIfChanged" not in switch_body


def test_session_rename_uses_modal_input_instead_of_sidebar_contenteditable():
    sessions = SESSION_MANAGEMENT.read_text(encoding="utf-8")
    dialogs = SHARED_DIALOGS.read_text(encoding="utf-8")
    shells = [
        SHELL_BODY.read_text(encoding="utf-8"),
        INDEX_HTML.read_text(encoding="utf-8"),
    ]

    rename_start = sessions.index("async function renameSessionFromMenu(sess) {")
    rename_end = sessions.index("async function exportSessionFromMenu(sess) {", rename_start)
    rename_body = sessions[rename_start:rename_end]
    assert "openUiModal({" in rename_body
    assert "inputValue: String(sess.name || '')" in rename_body
    assert "inputMaxLength: 160" in rename_body
    assert "contentEditable" not in sessions
    assert "addEventListener('dblclick'" not in sessions
    assert all('id="ui-modal-input"' in shell for shell in shells)
    assert "closeUiModal(value);" in dialogs
