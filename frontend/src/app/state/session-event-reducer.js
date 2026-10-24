function markUiEventStoreApplied(event) {
    if (!event || typeof event !== 'object') return;
    try {
        Object.defineProperty(event, '__storeApplied', {
            value: true,
            configurable: true,
            enumerable: false,
        });
    } catch (e) {
        event.__storeApplied = true;
    }
}

function applySessionEvent(event, opts) {
    if (!event || typeof event !== 'object') return { handled: false };
    opts = opts || {};
    const sessionId = String(
        opts.sessionId
        || event.session_id
        || event.sessionId
        || currentSessionId
        || ''
    );
    const eventIndex = opts.eventIndex;
    const source = opts.source || 'event';
    const type = String(event.type || '');
    if (type === 'session_work_dir_changed') {
        applySessionWorkspaceChange(sessionId, event.session);
        return { handled: true };
    }
    const runId = String(event.run_id || event.runId || '').trim();
    const phaseSeq = Number(event.runtime_seq || event.runtimeSeq || 0);
    let messageRecord = null;
    const ephemeral = !!event.ephemeral;
    const isLiveOnlyDelta = ephemeral && (
        type === 'llm_reasoning_delta'
        || type === 'llm_response_delta'
        || type === 'tool_call_delta'
        || type === 'tool_command_delta'
        || type === 'context_summary_delta'
        || type === 'context_summary_reasoning_delta'
        || type === 'key_context_delta'
    );
    // Ephemeral events belong to the live DOM only. Recording statuses,
    // lifecycle heartbeats, or tool drafts in the durable message index lets
    // reconnect-only event-bus sequence numbers collide with projected UI
    // indexes. The later durable event then replaces/reorders that slot and
    // makes the process panel jump.
    if (sessionId && !ephemeral && !isLiveOnlyDelta) {
        messageRecord = applyMessageEvent(sessionId, event, eventIndex, source);
        markUiEventStoreApplied(event);
    }
    if (type === 'run_started' || type === 'run_attached') {
        if (runId && sessionStore.isTerminalRun(sessionId, runId)) {
            markSessionRunInactive(sessionId);
            return { handled: true, runStateChanged: true, messageRecord: messageRecord };
        }
        const suppressed = typeof isSessionStreamStopSuppressed === 'function'
            && isSessionStreamStopSuppressed(sessionId);
        const finalizingRunId = String(sessionStore.finalizingRunIdsBySession.get(sessionId) || '');
        if (!runId || (finalizingRunId && finalizingRunId !== runId)) {
            sessionStore.clearRunFinalizing(sessionId);
        }
        setSessionServerStreamActive(sessionId, !suppressed);
        const sess = sessionStore.get(sessionId);
        if (sess) {
            sess.run_active = !suppressed;
            sess.run_started_at = suppressed
                ? null
                : (event.started_at || event.startedAt || sess.run_started_at || new Date().toISOString());
        }
        if (typeof updateSidebarRuntimeStatus === 'function') updateSidebarRuntimeStatus(true);
        return { handled: true, runStateChanged: true, messageRecord: messageRecord };
    }
    if (type === 'run_finished' || type === 'run_interrupted' || type === 'run_failed') {
        if (runId) sessionStore.markTerminalRun(sessionId, runId);
        const localRun = getSessionRunState(sessionId);
        const localRunId = String((localRun && localRun.runId) || '').trim();
        const activeInfo = sessionStore.activeRunInfoBySession.get(sessionId);
        const activeRunId = String((activeInfo && (activeInfo.run_id || activeInfo.runId)) || '').trim();
        const knownCurrentRunId = localRunId || activeRunId;
        if (runId && knownCurrentRunId && runId !== knownCurrentRunId) {
            return { handled: true, staleTerminalIgnored: true, messageRecord: messageRecord };
        }
        if (type === 'run_finished' && typeof clearSessionStreamStopSuppress === 'function') clearSessionStreamStopSuppress(sessionId);
        markSessionRunInactive(sessionId);
        const resultStatus = (type === 'run_interrupted' || type === 'run_failed')
            ? 'failed' : event.result_status;
        const goalContinues = !resultStatus && type === 'run_finished'
            && typeof isGoalActiveForSession === 'function'
            && isGoalActiveForSession(sessionId);
        if (resultStatus === 'failed') {
            markSessionResultComplete(sessionId, 'failed', runId);
        } else if ((goalContinues || resultStatus === 'pending') && typeof clearSessionUnreadState === 'function') {
            clearSessionUnreadState(sessionId, { server: false });
        } else {
            // A successful new terminal resolves the previous failed result.
            markSessionResultComplete(sessionId, 'success', runId);
            if (sessionId === String(currentSessionId || '')
                && typeof clearSessionUnreadState === 'function') {
                clearSessionUnreadState(sessionId, { expectedRunId: runId });
            }
        }
        return {
            handled: true,
            runStateChanged: true,
            goalContinues: goalContinues,
            messageRecord: messageRecord,
        };
    }
    if (type === 'user' && event.queued_followup) {
        sessionStore.clearRunFinalizing(sessionId, runId, phaseSeq);
        return { handled: false, finalStateChanged: true, messageRecord: messageRecord };
    }
    if (type === 'final' && source === 'sse') {
        const localRun = getSessionRunState(sessionId);
        const localRunId = String((localRun && localRun.runId) || '').trim();
        const activeInfo = sessionStore.activeRunInfoBySession.get(sessionId);
        const activeRunId = String((activeInfo && (activeInfo.run_id || activeInfo.runId)) || '').trim();
        const knownCurrentRunId = localRunId || activeRunId;
        const finalizingRunId = runId || knownCurrentRunId;
        if (finalizingRunId && (!runId || !knownCurrentRunId || runId === knownCurrentRunId)) {
            sessionStore.markRunFinalizing(sessionId, finalizingRunId, phaseSeq);
        }
        return { handled: false, finalStateChanged: true, messageRecord: messageRecord };
    }
    if (type === 'context_tokens') {
        // A historical observation is not the current request's context.
        if (source.indexOf('history') === 0) {
            return { handled: true, messageRecord: messageRecord };
        }
        setContextTokensForSession(sessionId, event.estimated, event.threshold, event.breakdown);
        return { handled: false, contextStateChanged: true, messageRecord: messageRecord };
    }
    if (type === 'context_summary_delta') {
        if (source.indexOf('history') !== 0) appendContextProgressForSession(sessionId, 'context-summary', event.delta);
        return { handled: false, contextStateChanged: true, messageRecord: messageRecord };
    }
    if (type === 'key_context_delta') {
        if (source.indexOf('history') !== 0) appendContextProgressForSession(sessionId, 'key-context', event.delta);
        return { handled: false, contextStateChanged: true, messageRecord: messageRecord };
    }
    return { handled: false, messageRecord: messageRecord };
}
