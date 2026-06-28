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


def test_index_html_injects_conservative_feature_defaults(monkeypatch):
    monkeypatch.delenv("MYAGENT_ENABLE_FOLLOWUP_RESTART", raising=False)
    monkeypatch.delenv("MYAGENT_ENABLE_STREAM_RECONNECT", raising=False)
    monkeypatch.delenv("MYAGENT_ENABLE_FINAL_RECONCILE", raising=False)

    import webui

    flags = _extract_feature_flags(str(webui.get_index_html()))

    assert flags == {
        "followupRestart": False,
        "streamReconnect": False,
        "finalReconcile": True,
    }


def test_index_html_injects_independent_feature_overrides(monkeypatch):
    monkeypatch.setenv("MYAGENT_ENABLE_FOLLOWUP_RESTART", "1")
    monkeypatch.setenv("MYAGENT_ENABLE_STREAM_RECONNECT", "true")
    monkeypatch.setenv("MYAGENT_ENABLE_FINAL_RECONCILE", "0")

    import webui

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


def test_frontend_session_load_starts_toc_before_messages_finish():
    sessions = (ROOT / "frontend/src/app/modules/session-management.js").read_text(encoding="utf-8")
    toc = (ROOT / "frontend/src/app/modules/toc-todo.js").read_text(encoding="utf-8")

    assert "function startTocForSessionLoad(sessionId)" in toc
    assert "startTocForSessionLoad(sessionId)" in sessions
    assert "tocAlreadyStarted: true" in sessions
    assert "if (!opts.tocAlreadyStarted) rebuildToc();" in sessions
    switch_body = sessions[sessions.index("async function switchSession"):]
    assert switch_body.index("startTocForSessionLoad(sessionId)") < switch_body.index("loadSessionMessages(sessionId")


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
