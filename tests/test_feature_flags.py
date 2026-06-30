import json
import re
import sys
from pathlib import Path
import asyncio


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


def _extract_feature_flags(html: str) -> dict:
    match = re.search(r"window\.__MYAGENT_FEATURES__=([^<;]+);", html)
    assert match, "feature flag injection missing"
    return json.loads(match.group(1))


def test_index_html_injects_conservative_feature_values(monkeypatch):
    import webui

    monkeypatch.setenv("MYAGENT_ENABLE_FOLLOWUP_RESTART", "0")
    monkeypatch.setenv("MYAGENT_ENABLE_STREAM_RECONNECT", "0")
    monkeypatch.setenv("MYAGENT_ENABLE_FINAL_RECONCILE", "1")

    flags = _extract_feature_flags(str(webui.get_index_html()))

    assert flags == {
        "followupRestart": False,
        "streamReconnect": False,
        "finalReconcile": True,
    }


def test_index_html_injects_independent_feature_overrides(monkeypatch):
    import webui

    monkeypatch.setenv("MYAGENT_ENABLE_FOLLOWUP_RESTART", "1")
    monkeypatch.setenv("MYAGENT_ENABLE_STREAM_RECONNECT", "true")
    monkeypatch.setenv("MYAGENT_ENABLE_FINAL_RECONCILE", "0")

    flags = _extract_feature_flags(str(webui.get_index_html()))

    assert flags == {
        "followupRestart": True,
        "streamReconnect": True,
        "finalReconcile": False,
    }


def test_frontend_feature_entrypoints_are_flag_guarded():
    sse = (ROOT / "frontend/src/app/modules/sse-handling.js").read_text(encoding="utf-8")
    sessions = (ROOT / "frontend/src/app/modules/session-management.js").read_text(encoding="utf-8")

    assert "isMyAgentFeatureEnabled('followupRestart', false)" in sse
    assert "isMyAgentFeatureEnabled('streamReconnect', false)" in sse
    assert "isMyAgentFeatureEnabled('finalReconcile', true)" in sse
    assert "function scheduleFinalVisibleAfterRunIfEnabled" in sse
    assert "function markRunFinalSeen(ctx)" in sse
    assert "function initRunFinalTracking(ctx)" in sse
    assert "if (ctx && ctx.seenFinal === true) return;" in sse
    assert "if (eventSessionId === runSessionId) markRunFinalSeen(runCtx);" in sse
    assert "await ensureFinalVisibleAfterRunIfEnabled" not in sse
    assert "function enqueueCurrentInputAsFollowup()" in sse
    assert "if (!isMyAgentFeatureEnabled('followupRestart', false)) return false;" in sse
    assert "function onFollowupInputKeydown(e)" in sse
    assert "if (!isMyAgentFeatureEnabled('followupRestart', false)) return;" in sse
    assert "followupEnabled" in sessions
    assert "isMyAgentFeatureEnabled('followupRestart', false)" in sessions


def test_removed_high_risk_dom_stream_shims_do_not_return():
    bundle_sources = [
        ROOT / "frontend/src/app/modules/sse-handling.js",
        ROOT / "frontend/src/app/modules/session-scroll-history.js",
        ROOT / "frontend/src/app/modules/toc-todo.js",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in bundle_sources)

    for symbol in [
        "ensureDomContextForSession",
        "resolveRenderStreamForSession",
        "shouldIgnoreMainProcessAfterFinal",
        "tocRebuildPendingAfterLoad",
    ]:
        assert symbol not in combined


def test_frontend_session_load_lets_snapshot_own_toc_build():
    sessions = (ROOT / "frontend/src/app/modules/session-management.js").read_text(encoding="utf-8")
    toc = (ROOT / "frontend/src/app/modules/toc-todo.js").read_text(encoding="utf-8")

    assert "function startTocForSessionLoad(sessionId)" in toc
    assert "startTocForSessionLoad(sessionId)" in sessions
    assert "const tocAlreadyStarted = opts.useSnapshot === false" in sessions
    assert "tocAlreadyStarted: tocAlreadyStarted" in sessions
    assert "tocAlreadyStarted: true" not in sessions
    assert "if (!opts.tocAlreadyStarted) rebuildToc();" in sessions
    assert "/history_snapshot?turns=" in sessions
    assert "setTocTurnsForSession(sessionId, snapshot.user_turns)" in sessions
    assert "opts.useSnapshot === false && typeof startTocForSessionLoad === 'function'" in sessions


def test_frontend_session_load_logs_open_session_timing_from_snapshot():
    sessions = (ROOT / "frontend/src/app/modules/session-management.js").read_text(encoding="utf-8")

    assert "let snapshotTiming = null;" in sessions
    assert "snapshotTiming = snapshot.timing && typeof snapshot.timing === 'object'" in sessions
    assert "function logOpenSessionTiming(sessionId, data)" in sessions
    assert "'open_session_timing session=%s source=%s total=%sms events=%s backend_total=%sms read_page=%sms count=%sms user_turns=%sms'" in sessions
    assert "logOpenSessionTiming(sessionId, {" in sessions


def test_frontend_send_and_reattach_reuse_event_count_cache():
    sessions = (ROOT / "frontend/src/app/modules/session-management.js").read_text(encoding="utf-8")
    scroll = (ROOT / "frontend/src/app/modules/session-scroll-history.js").read_text(encoding="utf-8")
    sse = (ROOT / "frontend/src/app/modules/sse-handling.js").read_text(encoding="utf-8")

    assert "has(sessionId)" in sessions
    assert "async function getUiEventCount(sessionId, opts)" in scroll
    assert "opts.preferCache" in scroll
    assert "uiEventCountCache.has(sid)" in scroll
    assert "uiEventCountCache.updateFromServer(sid, count)" in scroll
    assert "getUiEventCount(runSessionId, { preferCache: true })" in sse
    assert "uiEventCountCache.updateFromServer(runSessionId, preCount + 1)" in sse
    assert "getUiEventCount(submitSessionId).then" not in sse


def test_frontend_suppressed_toc_rebuild_does_not_clear_started_toc():
    toc = (ROOT / "frontend/src/app/modules/toc-todo.js").read_text(encoding="utf-8")
    suppress_block = re.search(
        r"if\s*\(\s*suppressTocDuringSessionLoad\s*\)\s*\{(?P<body>.*?)\}",
        toc,
        re.S,
    )
    assert suppress_block, "rebuildToc must keep an explicit suppress guard"
    body = suppress_block.group("body")

    assert "clearTocForSessionLoad" not in body
    assert re.search(r"\breturn\s*;", body), "suppressed TOC rebuild should be a no-op"


def test_frontend_toc_supports_snapshot_turns_and_skips_empty_active_update():
    toc = (ROOT / "frontend/src/app/modules/toc-todo.js").read_text(encoding="utf-8")

    assert "function setTocTurnsForSession(sessionId, turns)" in toc
    assert "Array.isArray(options.turns)" in toc
    assert "tocTurnsCacheBySession.set(sid, turns)" in toc
    assert "if (!list || !list.querySelector('a[data-event-index]')) return;" in toc


def test_frontend_initial_bottom_scroll_remains_smooth_without_saved_position():
    rendering = (ROOT / "frontend/src/app/modules/message-rendering.js").read_text(encoding="utf-8")

    assert "function scrollToBottom(opts)" in rendering
    assert "chatContainer.scrollTo({ top: chatContainer.scrollHeight, behavior: 'smooth' })" in rendering
    assert "scrollToBottom({ smooth: mode === 'saved-or-bottom' });" in rendering


def test_frontend_run_state_cleanup_is_run_id_scoped():
    actions = (ROOT / "frontend/src/app/state/session-actions.js").read_text(encoding="utf-8")
    sse = (ROOT / "frontend/src/app/modules/sse-handling.js").read_text(encoding="utf-8")
    sessions = (ROOT / "frontend/src/app/modules/session-management.js").read_text(encoding="utf-8")

    assert "function clearSessionRunStateIfMatch(sessionId, runId)" in actions
    assert "String(run.runId || '') === expected" in actions
    assert "runCtx.runId = clientRunId;" in sse
    assert "clearSessionRunStateIfMatch(runSessionId, clientRunId)" in sse
    assert "clearSessionRunStateIfMatch(runSessionId, runCtx && runCtx.runId)" in sse
    assert "if (run && run.reattached)" in sessions
    assert "abortSessionRun(sid, 'reconcile-finished')" in sessions


class _FakeJsonRequest:
    def __init__(self, payload: dict):
        self._payload = payload

    async def json(self):
        return dict(self._payload)


class _FakeSessionManagerForSteer:
    def __init__(self):
        self.interrupts: list[tuple[str, str]] = []

    def request_interrupt(self, session_id: str, reason: str = ""):
        self.interrupts.append((session_id, reason))


def test_followup_restart_enabled_steer_returns_restart(monkeypatch):
    import webui

    fake_manager = _FakeSessionManagerForSteer()
    monkeypatch.setenv("MYAGENT_ENABLE_FOLLOWUP_RESTART", "1")
    monkeypatch.setattr(webui, "session_manager", fake_manager)
    monkeypatch.setattr(webui, "_is_session_stream_active", lambda sid: True)
    monkeypatch.setattr(webui, "abort_session_steer_run", lambda sid, reason="": True)
    monkeypatch.setattr(webui, "_interrupt_runtime_v2_active_runs", lambda sid, reason="": ["run-1"])

    response = asyncio.run(webui.post_session_steer(
        "s1",
        _FakeJsonRequest({"message": "continue now", "client_id": "cid-1"}),
    ))
    payload = json.loads(response.body.decode("utf-8"))

    assert payload["ok"] is True
    assert payload["restart"] is True
    assert payload["aborted"] is True
    assert payload["item"]["content"] == "continue now"
    assert payload["item"]["client_id"] == "cid-1"
    assert fake_manager.interrupts == [("s1", "followup")]
