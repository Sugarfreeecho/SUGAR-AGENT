from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SESSION_MANAGEMENT = ROOT / "frontend/src/app/modules/session-management.js"
SESSION_RENDERERS = ROOT / "frontend/src/app/state/session-renderers.js"


def test_unarchive_updates_cached_row_and_refreshes_archive_directory():
    source = SESSION_MANAGEMENT.read_text(encoding="utf-8")

    optimistic_start = source.index("function applyOptimisticSessionUpdate(sessionId, patch) {")
    optimistic_end = source.index("// Event count cache", optimistic_start)
    optimistic_body = source[optimistic_start:optimistic_end]
    assert "sessionStore.get(sid) || (sessionStore.archivedLoaded" in optimistic_body
    assert "sessionStore.archivedSessions || []" in optimistic_body
    assert "String(session.id) === sid" in optimistic_body

    archive_handler_start = source.index("async function toggleSessionArchivedFromMenu(sess) {")
    archive_handler_end = source.index("async function renameSessionFromMenu(sess) {", archive_handler_start)
    archive_handler = source[archive_handler_start:archive_handler_end]
    assert "await refreshSingleSessionRow(sess.id);" in archive_handler
    assert "if (!nextArchived && sessionStore.archivedLoaded)" in archive_handler
    assert (
        "await loadArchivedSessions({ background: true, refresh: true, forceRender: true });"
        in archive_handler
    )


def test_archive_load_more_auto_triggers_near_sidebar_bottom():
    source = SESSION_RENDERERS.read_text(encoding="utf-8")

    auto_start = source.index("function maybeAutoLoadMoreArchivedSessions() {")
    auto_end = source.index("function renderSessionTitleFromStore()", auto_start)
    auto_loader = source[auto_start:auto_end]

    assert "ARCHIVED_AUTO_LOAD_BOTTOM_PX = 32" in source
    assert "sessionStore.archivedLoaded" in auto_loader
    assert "sessionStore.hasMoreArchivedSessions()" in auto_loader
    assert "archiveSection.classList.contains('is-collapsed')" in auto_loader
    assert "sessionsList.scrollHeight - sessionsList.scrollTop - sessionsList.clientHeight" in auto_loader
    assert "loadBtn.click();" in auto_loader
    assert (
        "sessionsList.addEventListener('scroll', maybeAutoLoadMoreArchivedSessions, { passive: true });"
        in auto_loader
    )
    assert "requestAnimationFrame(maybeAutoLoadMoreArchivedSessions);" in source
