from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SESSION_MANAGEMENT = ROOT / "frontend/src/app/modules/session-management.js"
SESSION_DRAFTS = ROOT / "frontend/src/app/modules/session-scroll-history.js"
APP_CSS = ROOT / "frontend/src/styles/app.css"
I18N = ROOT / "frontend/src/app/modules/i18n.js"


def test_background_session_with_unsent_input_shows_draft_badge():
    sessions = SESSION_MANAGEMENT.read_text(encoding="utf-8")

    assert 'class="session-draft-badge"' in sessions
    assert "String(sessionId) !== String(currentSessionId || '') && sessionHasUnsentDraft(sessionId)" in sessions
    assert "String(draft || '').trim()" in sessions
    assert "badge.hidden = !visible" in sessions
    assert "syncSessionDraftBadge(itemDiv, sessionId);" in sessions


def test_draft_badge_tracks_persist_and_clear_without_list_rerender():
    drafts = SESSION_DRAFTS.read_text(encoding="utf-8")

    persist_start = drafts.index("function persistInputDraft(sessionId, value) {")
    persist_end = drafts.index("function readStoredInputDraft(sessionId) {", persist_start)
    persist_body = drafts[persist_start:persist_end]
    remove_start = drafts.index("function removeStoredInputDraft(sessionId) {")
    remove_end = drafts.index("function clearStreamPoll() {", remove_start)
    remove_body = drafts[remove_start:remove_end]

    assert "syncSessionDraftBadges(sessionId);" in persist_body
    assert "syncSessionDraftBadges(sessionId);" in remove_body
    assert "renderSessionList" not in persist_body
    assert "renderSessionList" not in remove_body


def test_draft_badge_has_yellow_pill_style_and_english_translation():
    css = APP_CSS.read_text(encoding="utf-8")
    i18n = I18N.read_text(encoding="utf-8")

    assert ".session-draft-badge" in css
    assert "var(--amber-accent)" in css
    assert ".session-draft-badge[hidden] { display: none; }" in css
    assert "'草稿': 'Draft'" in i18n
