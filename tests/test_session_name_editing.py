from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SESSION_MANAGEMENT = ROOT / "frontend/src/app/modules/session-management.js"


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
