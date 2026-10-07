from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SESSION_MANAGEMENT = ROOT / "frontend/src/app/modules/session-management.js"
SHARED_DIALOGS = ROOT / "frontend/src/app/modules/shared-state-and-dialogs.js"
SHELL_BODY = ROOT / "frontend/src/shell-body.html"
INDEX_HTML = ROOT / "frontend/index.html"


def test_session_list_render_key_only_tracks_structural_content():
    source = SESSION_MANAGEMENT.read_text(encoding="utf-8")

    layout_start = source.index("function computeSessionListLayoutKey() {")
    content_start = source.index("function computeSessionListContentMap() {", layout_start)
    content_end = source.index("function sessionContentMapsEqual(", content_start)
    layout_body = source[layout_start:content_start]
    content_body = source[content_start:content_end]

    for section in ("sections.pinned", "sections.normalGroups", "sections.archived"):
        assert section in layout_body
    for visible_field in ("s.name", "s.pinned", "s.archived", "s.last_activity_at", "s.last_user_preview"):
        assert visible_field in content_body
    for transient_field in (
        "currentSessionId",
        "stream_active",
        "unread_result",
        "subagent_running",
        "subagent_pending_continue",
        "subagent_can_continue",
    ):
        assert transient_field not in layout_body
        assert transient_field not in content_body
    assert "computeSessionListLayoutKey()" in source
    assert "computeSessionListContentMap()" in source


def test_switch_session_updates_active_state_without_direct_list_render():
    source = SESSION_MANAGEMENT.read_text(encoding="utf-8")

    switch_start = source.index("async function switchSession(sessionId, opts) {")
    switch_end = source.index("async function createNewSession(", switch_start)
    switch_body = source[switch_start:switch_end]

    assert "syncSessionListIndicatorClasses();" in switch_body
    assert "renderSessionListIfChanged" not in switch_body


def test_session_rename_uses_modal_input_for_menu_and_double_click():
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
    assert "nameEl.addEventListener('dblclick'" in sessions
    assert "renameSessionFromMenu(current)" in sessions
    assert all('id="ui-modal-input"' in shell for shell in shells)
    assert "closeUiModal(value);" in dialogs


def test_modal_backdrop_ignores_text_selection_drag_from_input():
    dialogs = SHARED_DIALOGS.read_text(encoding="utf-8")

    assert "root.onpointerdown = function (e)" in dialogs
    assert "backdropPressStarted = e.target === root;" in dialogs
    assert "root.onpointerup = function (e)" in dialogs
    assert "backdropPressCompleted = backdropPressStarted && e.target === root;" in dialogs
    assert "if (e.target === root && backdropPressCompleted) onCancel();" in dialogs
    assert "root.onpointercancel = function ()" in dialogs
