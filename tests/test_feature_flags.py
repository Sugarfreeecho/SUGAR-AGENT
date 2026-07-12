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
        "goal": True,
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
        "goal": True,
        "followupRestart": True,
        "streamReconnect": True,
        "finalReconcile": False,
    }


def test_index_html_injects_goal_feature_override(monkeypatch):
    import webui

    monkeypatch.setenv("GOAL_ENABLED", "0")
    flags = _extract_feature_flags(str(webui.get_index_html()))
    assert flags["goal"] is False


def test_index_html_defaults_stream_reconnect_enabled(monkeypatch):
    import webui

    monkeypatch.delenv("MYAGENT_ENABLE_STREAM_RECONNECT", raising=False)

    flags = _extract_feature_flags(str(webui.get_index_html()))

    assert flags["streamReconnect"] is True


def test_frontend_feature_entrypoints_are_flag_guarded():
    sse = (ROOT / "frontend/src/app/modules/sse-handling.js").read_text(encoding="utf-8")
    sessions = (ROOT / "frontend/src/app/modules/session-management.js").read_text(encoding="utf-8")
    webui = (ROOT / "app/webui.py").read_text(encoding="utf-8")

    assert "isMyAgentFeatureEnabled('followupRestart', false)" in sse
    assert "isMyAgentFeatureEnabled('streamReconnect', true)" in sse
    assert "isMyAgentFeatureEnabled('finalReconcile', true)" in sse
    assert "function scheduleFinalVisibleAfterRunIfEnabled" in sse
    assert "const SSE_IDLE_TIMEOUT_MS = 120000" in sse
    assert "maybeAutoResumeInterruptedReact" in sse
    refresh_row = sessions.split("async function refreshSingleSessionRow", 1)[1].split("let sessionListLoadEpoch", 1)[0]
    event_cache_set = sessions.split("const uiEventCountCache", 1)[1].split("increment(sessionId)", 1)[0]
    assert "maybeAutoResumeInterruptedReact(sessionId, sess)" in refresh_row
    assert "maybeAutoResumeInterruptedReact" not in event_cache_set
    assert "window.addEventListener('online'" in sse
    assert sse.index("setSessionRunState(submitSessionIdInitial, optimisticRunState)") < sse.index("processRewriteTruncateAsync(pendingRewrite)")
    assert sse.index("setSessionRunState(submitSessionIdInitial, optimisticRunState)") < sse.index("let preCount = await getUiEventCount")
    assert "optimisticNewSessionRun = optimisticRunState;" in sse
    assert "if (ac.signal.aborted) return;" in sse
    assert "optimisticRunState.submitted = true;" in sse
    assert "!(activeRun && activeRun.suppressFollowupButton)" in sse
    assert "readSseChunkWithIdleTimeout(reader, SSE_IDLE_TIMEOUT_MS)" in sse
    assert "parsed.type === 'sse_keepalive' || parsed.keepalive === true" in sse
    assert 'os.getenv("MYAGENT_ENABLE_STREAM_RECONNECT", "1")' in webui
    assert "CHAT_SSE_KEEPALIVE_SEC" in webui
    assert "'type': 'sse_keepalive'" in webui
    assert "function markRunFinalSeen(ctx)" in sse
    assert "function initRunFinalTracking(ctx)" in sse
    assert "if (ctx && ctx.seenFinal === true) return;" in sse
    assert "if (eventSessionId === runSessionId) markRunFinalSeen(runCtx);" in sse
    assert "await ensureFinalVisibleAfterRunIfEnabled" not in sse
    assert "function fetchLatestStoredFinalRecord" not in sse
    assert "var latestFinal = await fetchLatestStoredFinalRecord(sid);" not in sse
    assert "messages?limit=120" not in sse
    assert "function reconcileProjectedMessagesAfter" not in sse
    assert "projected-reconcile" not in sse
    assert "messages?after_index=" not in sse
    assert "function enqueueCurrentInputAsFollowup()" in sse
    assert "if (!isMyAgentFeatureEnabled('followupRestart', false)) return false;" in sse
    assert "function onFollowupInputKeydown(e)" in sse
    assert "if (!isMyAgentFeatureEnabled('followupRestart', false)) return;" in sse
    assert "async function syncFollowupQueueFromServer(sessionId)" in sse
    assert "async function fetchSteerStatus(sessionId, item)" in sse
    assert "async function recoverSteerForRestart(sessionId, item)" in sse
    assert "const sendPipelineLock = acquireSendPipelineLock(submitSessionIdInitial);" in sse
    assert "if (!sendPipelineLock) return;" in sse
    assert "releaseSendPipelineLock(sendPipelineLock);" in sse
    assert "formData.append('steer_id', String(options.steerId))" in sse
    assert "scheduleFollowupQueueDrain" not in sse
    assert "drainFollowupQueue" not in sse
    assert "followupEnabled" in sessions
    assert "isMyAgentFeatureEnabled('followupRestart', false)" in sessions


def test_followups_wait_for_explicit_send_now_after_run_end():
    sse = (ROOT / "frontend/src/app/modules/sse-handling.js").read_text(encoding="utf-8")
    enqueue = sse.split("function enqueueCurrentInputAsFollowup()", 1)[1].split(
        "function takeFollowupItem", 1
    )[0]

    # Enter only appends to the durable browser queue. Ending the current run
    # must not consume it; only the explicit send-now button may do that.
    assert "sendFollowupNow" not in enqueue
    assert "scheduleFollowupQueueDrain" not in sse
    assert "drainFollowupQueue" not in sse

    assert "sendNow.addEventListener('click'" in sse
    assert "sendFollowupNow(String(item.id));" in sse


def test_model_profile_selector_fences_cross_session_responses():
    source = (ROOT / "frontend/src/app/modules/model-profiles.js").read_text(encoding="utf-8")

    assert "const modelProfilesRefreshPromises = Object.create(null);" in source
    assert "const modelProfileBusyBySession = Object.create(null);" in source
    assert "const requestEpoch = ++modelProfileSelectionEpoch;" in source
    assert "existing && existing.epoch === modelProfileSelectionEpoch" in source
    assert "sid !== String(currentSessionId || '') || requestEpoch !== modelProfileSelectionEpoch" in source
    assert "fetch('/sessions/' + encodeURIComponent(sid) + '/model_profile'" in source
    assert "if (sid !== String(currentSessionId || '')) return;" in source
    assert "selectContextTokens(sid)" in source
    assert "scheduleContextTokensAfterPaint(sid)" in source


def test_chat_input_supports_clipboard_files_and_images_as_paths():
    sources = [
        ROOT / "frontend/src/vendor/myagent_path_picker.js",
        ROOT / "app/templates/static/myagent_path_picker.js",
    ]
    for path in sources:
        source = path.read_text(encoding="utf-8")
        assert "function clipboardFilesFromEvent(ev)" in source
        assert "textarea.addEventListener('paste'" in source
        assert "item.kind !== 'file'" in source
        assert "insertUploadedFiles(textarea, files)" in source
        assert "fetch('/api/upload-chat-files'" in source
        assert "quotePickedPath(item.path || item.rel || item.name)" in source


def test_branch_completion_does_not_hijack_a_later_session_switch():
    source = (ROOT / "frontend/src/app/modules/message-rendering.js").read_text(encoding="utf-8")

    assert "const sourceSwitchEpoch" in source
    assert "const sourceStillActive = currentSessionId === sourceSessionId" in source
    assert "sourceSwitchEpoch === switchSessionEpoch" in source
    assert "if (!sourceStillActive)" in source


def test_chat_busy_response_rolls_back_optimistic_message_into_queue():
    sse = (ROOT / "frontend/src/app/modules/sse-handling.js").read_text(encoding="utf-8")
    busy = sse.split("if (response.status === 409)", 1)[1].split("streamEventIdx = await", 1)[0]

    assert "rollbackOptimisticUserEvent(runSessionId, preCount)" in busy
    assert "appendFollowupQueueItem(" in busy
    assert "scheduleActiveSessionReconnect(runSessionId" in busy
    assert "truncateMessageStateForSession(sid, before)" in sse
    assert "uiEventCountCache.updateFromServer(sid, before)" in sse


def test_frontend_final_reconcile_is_local_store_only():
    sse = (ROOT / "frontend/src/app/modules/sse-handling.js").read_text(encoding="utf-8")
    final_block = re.search(
        r"async function ensureFinalVisibleAfterRun\(sessionId, ctx, opts\) \{(?P<body>.*?)\n\}",
        sse,
        re.S,
    )
    assert final_block, "final visibility reconcile must stay explicit"
    body = final_block.group("body")

    assert "findStoredFinalAfterUser(sid, lastUserIdx)" in body
    assert "renderFinalRecordIfMissing(sid, ctx, stream, storedFinal, lastUserIdx)" in body
    assert "fetch(" not in body
    assert "/messages" not in body


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
    assert "function startTodoForSessionLoad(sessionId)" in toc
    assert "function setTodoPlanForSession(sessionId, snapshot)" in toc
    assert "function renderLoadedTodoPlanForSession(sessionId, snapshot, alreadyStarted)" in toc
    assert "startTocForSessionLoad(sessionId)" in sessions
    assert "startTodoForSessionLoad(sessionId)" in sessions
    assert "const tocAlreadyStarted = opts.useSnapshot === false" in sessions
    assert "tocAlreadyStarted: tocAlreadyStarted" in sessions
    assert "todoAlreadyStarted: tocAlreadyStarted" in sessions
    assert "tocAlreadyStarted: true" not in sessions
    assert "if (!opts.tocAlreadyStarted) rebuildToc();" in sessions
    assert "/history_snapshot?turns=" in sessions
    assert "setTocTurnsForSession(sessionId, snapshot.user_turns)" in sessions
    assert "setTodoPlanForSession(sessionId, snapshot.todo_plan)" in sessions
    assert "renderLoadedTodoPlanForSession(sessionId, snapshotTodoPlan, opts.todoAlreadyStarted)" in sessions
    assert "opts.useSnapshot === false && typeof startTocForSessionLoad === 'function'" in sessions


def test_frontend_session_load_logs_open_session_timing_from_snapshot():
    sessions = (ROOT / "frontend/src/app/modules/session-management.js").read_text(encoding="utf-8")

    assert "let snapshotTiming = null;" in sessions
    assert "snapshotTiming = snapshot.timing && typeof snapshot.timing === 'object'" in sessions
    assert "function logOpenSessionTiming(sessionId, data)" in sessions
    assert "'open_session_timing session=%s source=%s total=%sms events=%s backend_total=%sms read_page=%sms count=%sms user_turns=%sms context_tokens=%sms'" in sessions
    assert "logOpenSessionTiming(sessionId, {" in sessions


def test_frontend_session_switch_async_work_is_session_scoped():
    sessions = (ROOT / "frontend/src/app/modules/session-management.js").read_text(encoding="utf-8")
    subagent_sync = (ROOT / "frontend/src/app/state/subagent-sync.js").read_text(encoding="utf-8")

    assert "if (loadToken !== messageLoadEpoch || sessionId !== currentSessionId) return false;" in sessions
    assert "rebuildToc({ localOnly: true });" in sessions
    assert sessions.count("if (switchToken === switchSessionEpoch && sessionId === currentSessionId)") >= 3
    assert "subagentTreeRefreshInflightBySession" in subagent_sync
    assert "subagentTreeRefreshQueuedBySession" in subagent_sync
    assert "if (!sessionId || sessionId !== currentSessionId) return;" in subagent_sync
    assert "if (seq !== subagentPanelRefreshSeq || sessionId !== currentSessionId) return;" in subagent_sync


def test_frontend_background_followup_return_does_not_touch_active_composer():
    sse = (ROOT / "frontend/src/app/modules/sse-handling.js").read_text(encoding="utf-8")
    skills = (ROOT / "frontend/src/app/modules/skill-picker.js").read_text(encoding="utf-8")

    fn = re.search(
        r"function returnFollowupToInput\(sid, item\) \{(?P<body>.*?)\n\}",
        sse,
        re.S,
    )
    assert fn
    body = fn.group("body")
    background = body.split("if (sid !== currentSessionId) {", 1)[1].split("\n    }", 1)[0]
    assert "persistInputDraft(sid, nextDraft);" in background
    assert "messageInput.value" not in background
    assert "messageInput.focus()" not in background
    assert "window.setSelectedSkillsForSession" in background
    assert "function setSelectedSkillsForSession(sessionId, skills)" in skills


def test_frontend_send_and_reattach_reuse_event_count_cache():
    sessions = (ROOT / "frontend/src/app/modules/session-management.js").read_text(encoding="utf-8")
    scroll = (ROOT / "frontend/src/app/modules/session-scroll-history.js").read_text(encoding="utf-8")
    sse = (ROOT / "frontend/src/app/modules/sse-handling.js").read_text(encoding="utf-8")
    subagent_sync = (ROOT / "frontend/src/app/state/subagent-sync.js").read_text(encoding="utf-8")
    subagent_store = (ROOT / "frontend/src/app/state/subagent-store.js").read_text(encoding="utf-8")

    assert "has(sessionId)" in sessions
    assert "async function getUiEventCount(sessionId, opts)" in scroll
    assert "opts.preferCache" in scroll
    assert "uiEventCountCache.has(sid)" in scroll
    assert "uiEventCountCache.updateFromServer(sid, count)" in scroll
    assert "getUiEventCount(runSessionId, { preferCache: true })" in sse
    assert "uiEventCountCache.updateFromServer(runSessionId, preCount + 1)" in sse
    assert "getUiEventCount(submitSessionId).then" not in sse
    assert "/messages/count" not in subagent_sync
    assert "node.event_count" in subagent_store
    assert "messages?after_index=" in subagent_sync


def test_frontend_llm_stream_seq_increments_do_not_split_chunks():
    rendering = (ROOT / "frontend/src/app/modules/message-rendering.js").read_text(encoding="utf-8")

    assert "seq < l.llmDeltaLastSeq" in rendering
    assert "seq !== l.llmDeltaLastSeq" not in rendering


def test_stream_deltas_have_stable_dedupe_keys():
    agent_loop = (ROOT / "app/agent_loop.py").read_text(encoding="utf-8")
    rendering = (ROOT / "frontend/src/app/modules/message-rendering.js").read_text(encoding="utf-8")
    scroll = (ROOT / "frontend/src/app/modules/session-scroll-history.js").read_text(encoding="utf-8")

    assert "llm_delta_seq = 0" in agent_loop
    assert "tool_delta_seq = 0" in agent_loop
    assert '"delta_seq": llm_delta_seq' in agent_loop
    assert '"delta_seq": tool_delta_seq' in agent_loop
    assert "function deltaDedupeKey(parsed, scope)" in rendering
    assert "hasSeenStreamDelta(ctx, ev, 'llm_' + part)" in rendering
    assert "hasSeenStreamDelta(ctx, parsed, 'tool_call_delta')" in rendering
    assert "_seenStreamDeltaKeys: new Set()" in scroll


def test_tool_pending_switches_generated_draft_to_executing():
    agent_loop = (ROOT / "app/agent_loop.py").read_text(encoding="utf-8")
    sse = (ROOT / "frontend/src/app/modules/sse-handling.js").read_text(encoding="utf-8")
    rendering = (ROOT / "frontend/src/app/modules/message-rendering.js").read_text(encoding="utf-8")

    assert "await _emit_tool_pending_sse(" in agent_loop
    assert 'if emit and tool_name != "context_manage":' in agent_loop
    assert "if (parsed.type === 'tool_pending')" in sse
    assert "appendToolPendingRow(runCtx, parsed, runSessionId);" in sse
    assert "row.getAttribute('data-tool-pending') === '1'" in rendering
    assert "draftChunk.classList.remove('is-streaming')" in rendering


def test_prompt_allows_multi_tool_generation_independent_of_execution_mode():
    prompt = (ROOT / "app/prompt.md").read_text(encoding="utf-8")

    assert "这与工具最终是并行还是串行执行无关" in prompt
    assert "依照 `tool_calls` 原始顺序串行" in prompt
    assert "不得猜测未知参数" in prompt


def test_streamed_llm_commits_are_sse_fallbacks_without_repersisting():
    agent_loop = (ROOT / "app/agent_loop.py").read_text(encoding="utf-8")
    subagent_events = (ROOT / "app/agent_subagent_events.py").read_text(encoding="utf-8")

    streamed_block = re.search(
        r"if streamed_this_call:(?P<body>.*?)else:",
        agent_loop,
        re.S,
    )
    assert streamed_block, "streamed LLM branch must be explicit"
    body = streamed_block.group("body")

    assert 'session_manager.append_ui_event(' in body
    assert '"type": "llm_reasoning"' in body
    assert '"type": "llm_response"' in body
    assert '"_skip_persist": True' in body
    assert '"live_commit": True' in body
    assert "emit=emit" in body
    assert 'ev.get("_skip_persist")' in subagent_events


def test_frontend_llm_delta_recovers_missing_scrollers():
    rendering = (ROOT / "frontend/src/app/modules/message-rendering.js").read_text(encoding="utf-8")

    assert "l.llmStreamReasoningScroller && !l.llmStreamReasoningScroller.isConnected" in rendering
    assert "recoveredReasoning = findExistingLlmFeedRow" in rendering
    assert "createProcessFeedRow(ctx, 'llm-reasoning'" in rendering
    assert "l.llmStreamResponseScroller && !l.llmStreamResponseScroller.isConnected" in rendering
    assert "recoveredResponse = findExistingLlmFeedRow" in rendering
    assert "createProcessFeedRow(ctx, 'llm-response'" in rendering


def test_runtime_v2_todo_plan_events_are_persistable():
    agent_loop = (ROOT / "app/agent_loop.py").read_text(encoding="utf-8")

    assert '"type": "todo_plan"' in agent_loop
    assert '"ephemeral": not _runtime_v2_is_primary()' in agent_loop


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


def test_frontend_session_scoped_token_and_count_guards():
    sessions = (ROOT / "frontend/src/app/modules/session-management.js").read_text(encoding="utf-8")
    scroll = (ROOT / "frontend/src/app/modules/session-scroll-history.js").read_text(encoding="utf-8")
    sse = (ROOT / "frontend/src/app/modules/sse-handling.js").read_text(encoding="utf-8")

    assert "if (typeof applyContextTokenLabelForCurrentSession === 'function') applyContextTokenLabelForCurrentSession();" in sessions
    assert "if (sid === currentSessionId) applyContextTokenLabelForCurrentSession();" in scroll
    assert "isFresh(sessionId, maxAgeMs)" in sessions
    assert "uiEventCountCache.isFresh(sid, opts.maxAgeMs)" in scroll
    assert "let preCount = await getUiEventCount(submitSessionId, {" in sse
    assert "signal: ac.signal" in sse
    assert "timeoutMs: 5000" in sse
    assert "parsed.type === 'context_tokens' && eventSessionId === currentSessionId" in sse
    assert "parsed.type === 'cache_stats' && eventSessionId === currentSessionId" in sse


def test_frontend_llm_stream_rows_are_upserted_across_process_group_rebuilds():
    rendering = (ROOT / "frontend/src/app/modules/message-rendering.js").read_text(encoding="utf-8")

    assert "function findExistingLlmFeedRow(ctx, logType, reactIter, opts)" in rendering
    assert "findExistingLlmFeedRow(ctx, logType, ri)" in rendering
    assert "findExistingLlmFeedRow(ctx, 'llm-response'" in rendering
    assert "findExistingLlmFeedRow(ctx, 'llm-reasoning'" in rendering
    assert "roots.push(ctx.stream)" in rendering
    assert "function removeDuplicateLlmFeedRows(ctx, keepRow, logType, reactIter)" in rendering


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
    assert "function endRunForClient(sessionId, ctx, opts)" in sse
    assert "runCtx.runId = clientRunId;" in sse
    assert "clearSessionRunStateIfMatch(runSessionId, clientRunId)" in sse
    assert "clearSessionRunStateIfMatch(sid, opts.runId || (ctx && ctx.runId))" in sse
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


def test_followup_restart_enabled_prefers_native_steer(monkeypatch):
    import webui

    fake_manager = _FakeSessionManagerForSteer()
    monkeypatch.setenv("MYAGENT_ENABLE_FOLLOWUP_RESTART", "1")
    monkeypatch.setattr(webui, "session_manager", fake_manager)
    monkeypatch.setattr(webui, "_is_session_stream_active", lambda sid: True)
    monkeypatch.setattr(
        webui,
        "enqueue_session_steer",
        lambda sid, message, client_id="", **_kwargs: {
            "ok": True,
            "item": {"content": message, "client_id": client_id},
        },
    )
    monkeypatch.setattr(webui, "abort_session_steer_run", lambda sid, reason="": True)
    monkeypatch.setattr(
        webui,
        "_interrupt_runtime_v2_active_runs",
        lambda sid, reason="": (_ for _ in ()).throw(AssertionError("native steer must not restart")),
    )

    response = asyncio.run(webui.post_session_steer(
        "s1",
        _FakeJsonRequest({"message": "continue now", "client_id": "cid-1"}),
    ))
    payload = json.loads(response.body.decode("utf-8"))

    assert payload["ok"] is True
    assert payload["restart"] is False
    assert payload["aborted"] is True
    assert payload["item"]["content"] == "continue now"
    assert payload["item"]["client_id"] == "cid-1"
    assert fake_manager.interrupts == []


def test_followup_restart_keeps_same_durable_steer_until_replacement_claim(monkeypatch):
    import webui

    fake_manager = _FakeSessionManagerForSteer()
    monkeypatch.setenv("MYAGENT_ENABLE_FOLLOWUP_RESTART", "1")
    monkeypatch.setattr(webui, "session_manager", fake_manager)
    monkeypatch.setattr(webui, "_is_session_stream_active", lambda sid: True)
    monkeypatch.setattr(
        webui,
        "enqueue_session_steer",
        lambda sid, message, client_id="", **kwargs: {
            "ok": True,
            "item": {"id": "steer-stable", "content": message, "client_id": client_id, "state": "queued"},
        },
    )
    monkeypatch.setattr(webui, "abort_session_steer_run", lambda sid, reason="": False)
    monkeypatch.setattr(webui, "_interrupt_runtime_v2_active_runs", lambda sid, reason="": ["run-old"])
    transitions = []

    def transition(sid, steer_id, from_states, to_state, **updates):
        transitions.append((sid, steer_id, set(from_states), to_state, dict(updates)))
        return {
            "ok": True,
            "item": {
                "id": steer_id,
                "content": "continue now",
                "client_id": "cid-stable",
                "state": to_state,
                **updates,
            },
        }

    monkeypatch.setattr(webui, "transition_session_steer", transition)

    response = asyncio.run(webui.post_session_steer(
        "s-fallback",
        _FakeJsonRequest({"message": "continue now", "client_id": "cid-stable"}),
    ))
    payload = json.loads(response.body.decode("utf-8"))

    assert payload["ok"] is True
    assert payload["restart"] is True
    assert payload["item"]["id"] == "steer-stable"
    assert payload["item"]["state"] == "restarting"
    assert transitions[0][1:4] == ("steer-stable", {"queued", "interrupting"}, "restarting")


def test_followup_http_retry_after_run_finished_returns_consumed_operation(monkeypatch):
    import webui

    monkeypatch.setattr(webui, "_is_session_stream_active", lambda sid: False)
    monkeypatch.setattr(
        webui,
        "get_session_steer",
        lambda sid, steer_id="", client_id="": {
            "ok": True,
            "item": {"id": "steer-once", "client_id": client_id, "state": "consumed"},
        },
    )
    monkeypatch.setattr(
        webui,
        "enqueue_session_steer",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("retry must not enqueue again")),
    )

    response = asyncio.run(webui.post_session_steer(
        "s-finished",
        _FakeJsonRequest({"message": "same followup", "client_id": "cid-once"}),
    ))
    payload = json.loads(response.body.decode("utf-8"))
    assert payload["ok"] is True
    assert payload["deduplicated"] is True
    assert payload["item"]["state"] == "consumed"
    assert payload["restart"] is False
