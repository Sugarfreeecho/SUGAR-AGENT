async function consumeAgentSseResponse(response, runCtx, runSessionId, streamEventIdx) {
    if (!response || !response.body) throw new Error('stream response missing body');
    var ct0 = (response.headers && response.headers.get ? (response.headers.get('content-type') || '') : '').toLowerCase();
    if (!response.ok || ct0.indexOf('text/event-stream') < 0) {
        throw new Error('stream response failed: ' + (response.status || 'no status'));
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop();
        for (const line of lines) {
            if (!line.startsWith('data: ')) continue;
            const data = line.slice(6);
            if (data === '[DONE]') {
                finalizeLlmStreamChunks(runCtx);
                finalizeProgressStreamChunks(runCtx);
                scheduleFinalVisibleAfterRunIfEnabled(runSessionId, runCtx, { delayMs: 80 });
                sealProcessGroup(runCtx);
                markSessionRunInactive(runSessionId);
                if (getSessionRunState(runSessionId)) clearSessionRunStateIfMatch(runSessionId, runCtx && runCtx.runId);
                syncSessionListIndicatorClasses();
                setSendButtonState();
                if (runSessionId === currentSessionId) renderTodoPlanForCurrentSession();
                scheduleFollowupQueueDrain(runSessionId, 0);
                if (liveAutoFollow) {
                    scrollProcessBodyToBottom(runCtx, runSessionId);
                    scrollChatToBottomIfFollow(runSessionId, {});
                }
                return streamEventIdx;
            }
            try {
                let parsed = JSON.parse(data);
                if (parsed && parsed.protocol === 'runtime_v2') {
                    const envelopeSessionId = parsed.session_id || parsed.sessionId || runSessionId;
                    if (!sessionStore.shouldAcceptSseEvent(envelopeSessionId, parsed.seq)) continue;
                    if (parsed.skip_ui) continue;
                    const uiEvent = parsed.ui_event && typeof parsed.ui_event === 'object' ? parsed.ui_event : null;
                    if (!uiEvent) continue;
                    const runtimeSeq = parsed.runtime_seq || parsed.seq;
                    parsed = Object.assign({}, uiEvent, {
                        protocol: 'runtime_v2',
                        runtime_seq: runtimeSeq,
                        seq: parsed.seq,
                        session_id: uiEvent.session_id || envelopeSessionId,
                    });
                }
                const eventSessionId = parsed.session_id || parsed.sessionId || runSessionId;
                if (parsed.protocol !== 'runtime_v2' && !sessionStore.shouldAcceptSseEvent(eventSessionId, parsed.seq)) continue;
                if (parsed.type === 'user_steer' && parsed.steer) {
                    var steerEventIndex = parsed.ephemeral && Number.isFinite(Number(parsed.seq)) ? Number(parsed.seq) : streamEventIdx;
                    try {
                        applyMessageEvent(eventSessionId, parsed, steerEventIndex, 'sse');
                    } catch (eStoreSteer) {
                        console.error('store user steer event failed:', eStoreSteer);
                    }
                    removeConsumedFollowupSteer(eventSessionId, parsed);
                    appendLog(runCtx, parsed.content || '', 'user-steer', runSessionId);
                    streamEventIdx += 1;
                    continue;
                }
                const reduced = applySessionEvent(parsed, {
                    sessionId: eventSessionId,
                    eventIndex: parsed.ephemeral && Number.isFinite(Number(parsed.seq)) ? Number(parsed.seq) : streamEventIdx,
                    source: 'sse',
                });
                if (reduced.runStateChanged) {
                    if (parsed.type === 'run_finished' || parsed.type === 'run_interrupted' || parsed.type === 'run_failed') {
                        finalizeLlmStreamChunks(runCtx);
                        finalizeProgressStreamChunks(runCtx);
                        if (parsed.type === 'run_finished') {
                            scheduleFinalVisibleAfterRunIfEnabled(eventSessionId, runCtx, { delayMs: 80 });
                        }
                        sealProcessGroup(runCtx);
                        if (eventSessionId === runSessionId && getSessionRunState(runSessionId)) {
                            clearSessionRunStateIfMatch(runSessionId, runCtx && runCtx.runId);
                        }
                        syncSessionListIndicatorClasses();
                        setSendButtonState();
                        if (eventSessionId === runSessionId) scheduleFollowupQueueDrain(runSessionId, 0);
                        streamEventIdx += 1;
                        continue;
                    }
                    syncSessionListIndicatorClasses();
                    continue;
                }
                if (reduced.contextStateChanged && eventSessionId === currentSessionId) {
                    if (parsed.type === 'context_tokens') applyContextTokenLabelForCurrentSession();
                    else if (parsed.type === 'todo_plan') renderTodoPlanForCurrentSession();
                    if (parsed.type === 'context_tokens' || parsed.type === 'todo_plan') continue;
                }
                if (parsed.ephemeral) {
                    /* 任何携带 agent_id 的 ephemeral 都属于子 agent；无论投递成功与否都不能 fall-through
                       到父 ctx 的 appendLlmStreamDelta，否则会污染主对话区。 */
                    if (parsed.agent_id) { handleSubagentStreamEvent(parsed, streamEventIdx, runSessionId); continue; }
                    if (parsed.type === 'llm_stream_aborted') {
                        removeTemporaryStatus(runCtx);
                        discardLlmStreamChunks(runCtx, parsed);
                        continue;
                    }
                    if (parsed.type === 'tool_approval_required') {
                        finalizeLlmStreamChunks(runCtx);
                        var aidApr = parsed.approval_id != null ? String(parsed.approval_id) : '';
                        var ttlApr = parsed.title != null ? String(parsed.title) : '需要确认';
                        var msgApr = parsed.message != null ? String(parsed.message) : '';
                        var subApr = parsed.subtitle != null ? String(parsed.subtitle) : '';
                        var allowApr = false;
                        try {
                            allowApr = await openUiModal({
                                title: ttlApr,
                                subtitle: subApr,
                                message: msgApr,
                                danger: true,
                                confirmText: '允许执行',
                                cancelText: '拒绝',
                            });
                        } catch (eApr) {
                            allowApr = false;
                        }
                        try {
                            await fetch('/sessions/' + encodeURIComponent(runSessionId) + '/tool-approval', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ approval_id: aidApr, approve: allowApr }),
                            });
                        } catch (errApr) {
                            console.error('tool-approval POST failed:', errApr);
                        }
                        continue;
                    }
                    if (parsed.type === 'tool_pending') {
                        finalizeLlmStreamChunks(runCtx);
                        removeTemporaryStatus(runCtx);
                        appendToolPendingRow(runCtx, parsed, runSessionId);
                        continue;
                    }
                    if (parsed.type === 'tool_call_delta') {
                        appendToolCallDelta(runCtx, parsed, runSessionId);
                        continue;
                    }
                    if (parsed.type === 'tool_command_delta') {
                        appendToolCommandDelta(runCtx, parsed, runSessionId);
                        continue;
                    }
                    if (parsed.type === 'llm_reasoning_delta' || parsed.type === 'llm_response_delta') appendLlmStreamDelta(runCtx, parsed, runSessionId);
                    else if (parsed.type === 'context_summary_delta') appendProgressStreamDelta(runCtx, parsed.delta, 'context-summary', runSessionId);
                    else if (parsed.type === 'key_context_delta') appendKeyContextStreamDelta(runCtx, parsed.delta, runSessionId);
                    else if (parsed.type === 'context_tokens') applyContextTokenLabelForCurrentSession();
                    else if (parsed.type === 'cache_stats' && runSessionId === currentSessionId) applyCacheStatsFromEvent(runCtx, parsed);
                    else if (parsed.type === 'todo_plan' && runSessionId === currentSessionId) renderTodoPlanForCurrentSession();
                    else if (parsed.type === 'status') {
                        var statusContent = String(parsed.content || '');
                        var isTemporaryStatus = statusContent.indexOf('正在思考中...') >= 0;
                        isTemporaryStatus = isTemporaryStatus || !!parsed.ephemeral || statusContent.indexOf('正在重连') >= 0;
                        if (isTemporaryStatus) removeTemporaryStatus(runCtx);
                        var statusRow = appendLog(runCtx, statusContent, 'status', runSessionId);
                        if (isTemporaryStatus && statusRow) {
                            statusRow.dataset.temporaryStatus = '1';
                        }
                    }
                    continue;
                }
                if (parsed.agent_id) {
                    /* 非 ephemeral 子 agent 事件：必须走子 agent 通道，绝不能落到 renderEvent(runCtx,...) */
                    handleSubagentStreamEvent(parsed, streamEventIdx, runSessionId);
                    streamEventIdx += 1;
                    continue;
                }
                finalizeLlmStreamChunks(runCtx);
                if (parsed.type === 'tool_call') {
                    upsertToolCallResult(runCtx, parsed, runSessionId);
                    streamEventIdx += 1;
                    continue;
                }
                if (parsed.type === 'final') {
                    if (eventSessionId === runSessionId) markRunFinalSeen(runCtx);
                    var finalStream = runCtx && runCtx.stream && runCtx.stream.isConnected ? runCtx.stream : getVisibleChatStream();
                    var finalLastUserIdx = latestVisibleUserEventIndex(finalStream);
                    if (hasDuplicateVisibleFinal(finalStream, finalLastUserIdx, parsed.content)) {
                        streamEventIdx += 1;
                        continue;
                    }
                }
                renderMessageRecord(runCtx, reduced.messageRecord || {
                    index: streamEventIdx,
                    event: parsed,
                    source: 'sse',
                }, runSessionId);
                if (parsed.type === 'final' && eventSessionId === runSessionId) {
                    finalizeLlmStreamChunks(runCtx);
                    finalizeProgressStreamChunks(runCtx);
                    markSessionRunInactive(runSessionId);
                    if (getSessionRunState(runSessionId)) clearSessionRunStateIfMatch(runSessionId, runCtx && runCtx.runId);
                    syncSessionListIndicatorClasses();
                    setSendButtonState();
                    scheduleFollowupQueueDrain(runSessionId, 250);
                }
                streamEventIdx += 1;
            } catch (e) { console.error('解析事件失败:', e); }
        }
    }
    scheduleFinalVisibleAfterRunIfEnabled(runSessionId, runCtx, { delayMs: 120 });
    return streamEventIdx;
}

function latestVisibleUserEventIndex(stream) {
    var maxIdx = -1;
    if (!stream || !stream.querySelectorAll) return maxIdx;
    stream.querySelectorAll('.msg-wrap--user[data-event-index]').forEach(function (wrap) {
        var n = Number(wrap.getAttribute('data-event-index'));
        if (Number.isFinite(n)) maxIdx = Math.max(maxIdx, Math.floor(n));
    });
    return maxIdx;
}

function hasVisibleFinalAfterUser(stream, userEventIndex) {
    if (!stream || !stream.querySelectorAll) return false;
    var found = false;
    stream.querySelectorAll('.msg-wrap--assistant[data-event-index]').forEach(function (wrap) {
        if (found) return;
        var n = Number(wrap.getAttribute('data-event-index'));
        if (Number.isFinite(n) && Math.floor(n) > userEventIndex) found = true;
    });
    return found;
}

function hasDuplicateVisibleFinal(stream, userEventIndex, content) {
    if (!stream || !stream.querySelectorAll) return false;
    var expected = String(content || '').replace(/\s+/g, ' ').trim();
    if (!expected) return false;
    var found = false;
    stream.querySelectorAll('.msg-wrap--assistant[data-event-index]').forEach(function (wrap) {
        if (found) return;
        var n = Number(wrap.getAttribute('data-event-index'));
        if (!Number.isFinite(n) || Math.floor(n) <= userEventIndex) return;
        var raw = messageRawMarkdown.get(wrap);
        var actual = String(raw != null ? raw : (wrap.textContent || '')).replace(/\s+/g, ' ').trim();
        if (actual === expected) found = true;
    });
    return found;
}

function findStoredFinalAfterUser(sessionId, userEventIndex) {
    var events = [];
    try { events = selectMessageEvents(sessionId) || []; } catch (e) { events = []; }
    for (var i = events.length - 1; i >= 0; i -= 1) {
        var rec = events[i];
        if (!rec || rec.type !== 'final') continue;
        if (Number.isFinite(Number(rec.index)) && Number(rec.index) > userEventIndex) return rec;
    }
    return null;
}

function renderFinalRecordIfMissing(sessionId, ctx, stream, finalRecord, userEventIndex) {
    if (!finalRecord || !finalRecord.event || finalRecord.type !== 'final') return false;
    var content = finalRecord.event.content || '';
    if (hasVisibleFinalAfterUser(stream, userEventIndex)) return true;
    if (hasDuplicateVisibleFinal(stream, userEventIndex, content)) return true;
    var renderCtx = ctx || newDomContext(stream);
    renderCtx.stream = stream;
    renderCtx.lastUserEventIndex = Math.max(renderCtx.lastUserEventIndex || -1, userEventIndex);
    renderMessageRecord(renderCtx, finalRecord, sessionId);
    return hasVisibleFinalAfterUser(stream, userEventIndex);
}

async function ensureFinalVisibleAfterRunIfEnabled(sessionId, ctx, opts) {
    if (!isMyAgentFeatureEnabled('finalReconcile', true)) return false;
    return ensureFinalVisibleAfterRun(sessionId, ctx, opts);
}

function markRunFinalSeen(ctx) {
    if (ctx) ctx.seenFinal = true;
}

function initRunFinalTracking(ctx) {
    if (ctx) ctx.seenFinal = false;
}

function scheduleFinalVisibleAfterRunIfEnabled(sessionId, ctx, opts) {
    if (!isMyAgentFeatureEnabled('finalReconcile', true)) return;
    if (ctx && ctx.seenFinal === true) return;
    setTimeout(function () {
        if (ctx && ctx.seenFinal === true) return;
        ensureFinalVisibleAfterRun(sessionId, ctx, opts).catch(function (e) {
            console.error('final reconcile failed:', e);
        });
    }, 0);
}

async function fetchLatestStoredFinalRecord(sessionId) {
    try {
        var response = await fetch('/sessions/' + encodeURIComponent(sessionId) + '/messages?limit=120');
        var data = await response.json().catch(function () { return null; });
        if (!response.ok || !data) return null;
        var events = Array.isArray(data) ? data : (Array.isArray(data.events) ? data.events : []);
        if (!events.length) return null;
        var base = Number.isFinite(Number(data.range_start)) ? Math.floor(Number(data.range_start)) : 0;
        var lastUserOffset = -1;
        for (var i = events.length - 1; i >= 0; i -= 1) {
            if (events[i] && events[i].type === 'user') {
                lastUserOffset = i;
                break;
            }
        }
        if (lastUserOffset < 0) return null;
        for (var j = events.length - 1; j > lastUserOffset; j -= 1) {
            var ev = events[j];
            if (ev && ev.type === 'final') {
                return {
                    index: base + j,
                    type: 'final',
                    event: ev,
                    source: 'final-reconcile',
                };
            }
        }
    } catch (e) {
        console.error('final-only reconcile fetch failed:', e);
    }
    return null;
}

async function ensureFinalVisibleAfterRun(sessionId, ctx, opts) {
    opts = opts || {};
    var sid = String(sessionId || '');
    if (!sid || sid !== currentSessionId) return false;
    var stream = (ctx && ctx.stream && ctx.stream.isConnected) ? ctx.stream : getVisibleChatStream();
    if (!stream) return false;
    var lastUserIdx = latestVisibleUserEventIndex(stream);
    if (hasVisibleFinalAfterUser(stream, lastUserIdx)) return true;
    var storedFinal = findStoredFinalAfterUser(sid, lastUserIdx);
    if (storedFinal) {
        if (renderFinalRecordIfMissing(sid, ctx, stream, storedFinal, lastUserIdx)) return true;
    }
    var delayMs = Math.max(0, Number(opts.delayMs) || 0);
    if (delayMs) await new Promise(function (resolve) { setTimeout(resolve, delayMs); });
    if (sid !== currentSessionId) return false;
    stream = getVisibleChatStream();
    if (!stream || hasVisibleFinalAfterUser(stream, lastUserIdx)) return true;
    var latestFinal = await fetchLatestStoredFinalRecord(sid);
    if (sid !== currentSessionId) return false;
    stream = getVisibleChatStream();
    if (!stream || hasVisibleFinalAfterUser(stream, lastUserIdx)) return true;
    if (latestFinal) return renderFinalRecordIfMissing(sid, ctx, stream, latestFinal, lastUserIdx);
    return false;
}

async function reconcileProjectedMessagesAfter(sessionId, ctx, afterIndex) {
    var sid = String(sessionId || '');
    var idx = Number(afterIndex);
    if (!sid || !Number.isFinite(idx)) return Number.isFinite(idx) ? idx + 1 : 0;
    var nextIndex = Math.max(0, Math.floor(idx) + 1);
    var renderCtx = ctx || null;
    var pageAfter = Math.floor(idx);
    var safety = 0;
    while (safety < 6) {
        safety += 1;
        try {
            var url = '/sessions/' + encodeURIComponent(sid)
                + '/messages?after_index=' + encodeURIComponent(String(pageAfter))
                + '&limit=500';
            var response = await fetch(url);
            var data = await response.json().catch(function () { return null; });
            if (!response.ok || !data || typeof data !== 'object') break;
            var events = Array.isArray(data.events) ? data.events : [];
            var rangeStart = Number.isFinite(Number(data.range_start)) ? Math.floor(Number(data.range_start)) : (pageAfter + 1);
            for (var i = 0; i < events.length; i += 1) {
                var ev = events[i];
                var eventIndex = rangeStart + i;
                nextIndex = Math.max(nextIndex, eventIndex + 1);
                if (!ev || typeof ev !== 'object' || !ev.type) continue;
                var existing = selectMessageEventsInRange(sid, eventIndex, eventIndex + 1);
                if (existing && existing.length) continue;
                if (!renderCtx) {
                    var stream = sid === currentSessionId ? getVisibleChatStream() : null;
                    if (stream) renderCtx = newDomContext(stream);
                }
                if (renderCtx && renderCtx.stream && renderCtx.stream.isConnected) {
                    reduceAndRenderMessageEvent(renderCtx, ev, {
                        sessionId: sid,
                        eventIndex: eventIndex,
                        source: 'projected-reconcile',
                    });
                } else {
                    applySessionEvent(ev, {
                        sessionId: sid,
                        eventIndex: eventIndex,
                        source: 'projected-reconcile',
                    });
                }
            }
            if (!data.has_newer || !events.length) break;
            pageAfter = nextIndex - 1;
        } catch (e) {
            console.error('projected message reconcile failed:', e);
            break;
        }
    }
    return nextIndex;
}

async function startContinueAfterSubagents(sessionId) {
    if (!sessionId || sessionId !== currentSessionId) return;
    delete subagentContinueDismissedForSession[sessionId];
    if (isSessionRunning(sessionId) || subagentContinueInFlight) {
        updateSubagentContinueBanner(sessionId);
        return;
    }
    if (sendPipelineLock && sendPipelineLockSessionId === sessionId) {
        updateSubagentContinueBanner(sessionId);
        return;
    }
    hideSubagentContinueBanner();
    subagentContinueInFlight = true;
    var runCtx = null;
    var runSessionId = sessionId;
    try {
    var banner = document.getElementById('subagent-continue-banner');
    var continueMode = banner && banner.dataset && banner.dataset.continueMode === 'react' ? 'react' : 'subagents';
    var continueUrl = continueMode === 'react'
        ? '/sessions/' + encodeURIComponent(sessionId) + '/continue'
        : '/sessions/' + encodeURIComponent(sessionId) + '/continue-subagents';
        const response = await fetch(continueUrl, { method: 'POST' });
        if (response.status === 204) {
            hideSubagentContinueBanner();
            return;
        }
        if (response.status === 409) {
            updateSubagentContinueBanner(sessionId);
            return;
        }
        var ct = (response.headers.get('content-type') || '').toLowerCase();
        if (!response.ok || !response.body || ct.indexOf('text/event-stream') < 0) return;
        const preCount = await getUiEventCount();
        if (!getVisibleChatStream()) ensureVisibleChatStreamSlot();
        runCtx = newDomContext(getVisibleChatStream());
        initRunFinalTracking(runCtx);
        runCtx.runStartedAt = new Date().toISOString();
        if (getSessionRunState(runSessionId) && getSessionRunState(runSessionId).ctx) {
            runCtx = getSessionRunState(runSessionId).ctx;
            initRunFinalTracking(runCtx);
            if (!runCtx.runStartedAt) runCtx.runStartedAt = new Date().toISOString();
        } else {
            runCtx.lastUserEventIndex = Math.max(0, preCount - 1);
            resetLlmState(runCtx);
            finalizeLlmStreamChunks(runCtx);
        }
        const ac = new AbortController();
        setSessionRunState(runSessionId, { controller: ac, ctx: runCtx });
        if (sessionStore && typeof sessionStore.resetSseSeq === 'function') {
            sessionStore.resetSseSeq(runSessionId);
        }
        setSendButtonState();
        syncSessionListIndicatorClasses();
        liveAutoFollow = true;
        streamProcNearBottom = true;
        scheduleContextTokensAfterPaint(runSessionId);
        let streamEventIdx = preCount;
        try {
            await consumeAgentSseResponse(response, runCtx, runSessionId, streamEventIdx);
        } catch (error) {
            if (error.name === 'AbortError') {
                if (getRunAbortReason(runSessionId, runCtx) === 'user') appendLog(runCtx, '任务已中断', 'status', runSessionId);
            }
            else {
                console.error('续接 subagent 失败:', error);
                const msg = (error && error.message) ? String(error.message) : String(error);
                appendLog(runCtx, '续接失败: ' + msg, 'error-log', runSessionId);
            }
        } finally {
            finalizeLlmStreamChunks(runCtx);
            finalizeProgressStreamChunks(runCtx);
            if (runSessionId === currentSessionId && getRunAbortReason(runSessionId, runCtx) !== 'user') {
                scheduleFinalVisibleAfterRunIfEnabled(runSessionId, runCtx, { delayMs: 120 });
            }
            if (runSessionId === currentSessionId) renderTodoPlanForCurrentSession();
            if (liveAutoFollow) {
                scrollProcessBodyToBottom(runCtx, runSessionId);
                scrollChatToBottomIfFollow(runSessionId, {});
            }
            if (getSessionRunState(runSessionId)) clearSessionRunState(runSessionId);
            setSendButtonState();
            syncSessionListIndicatorClasses();
            void refreshSingleSessionRow(runSessionId);
            applyContextTokenLabelForCurrentSession();
        }
        hideSubagentContinueBanner();
        if (!subagentContinueDismissedForSession[sessionId]) updateSubagentContinueBanner(sessionId);
    } finally {
        subagentContinueInFlight = false;
    }
}

async function attachSessionEventStream(sessionId, opts) {
    opts = opts || {};
    if (!sessionId || getSessionRunState(sessionId)) return;
    if (!isServerStreamActive(sessionId)) return;
    var runSessionId = sessionId;
    var runCtx = null;
    try {
        if (runSessionId !== currentSessionId) return;
        if (!opts.skipInitialLoad) {
            await loadSessionMessages(runSessionId, 'saved-or-bottom', { preloadOlderIfShort: true });
            if (runSessionId !== currentSessionId) return;
        }
        if (!getVisibleChatStream()) ensureVisibleChatStreamSlot();
        runCtx = newDomContext(getVisibleChatStream());
        var activeInfoForAttach = sessionStore.getActiveRunInfo(runSessionId) || {};
        runCtx.runStartedAt = activeInfoForAttach.started_at || new Date().toISOString();
        var existingProcessGroup = runCtx.stream.querySelector('.process-aggregate:last-of-type');
        if (existingProcessGroup) {
            runCtx.currentProcessGroup = existingProcessGroup;
            existingProcessGroup.classList.add('is-running');
            bindProcessAggregate(existingProcessGroup);
            var activeInfo = sessionStore.getActiveRunInfo(runSessionId) || {};
            if (activeInfo.started_at) {
                applyRunStartedAtToProcessGroup(existingProcessGroup, activeInfo.started_at);
            } else if (!existingProcessGroup.dataset.procStartedAt && !existingProcessGroup.dataset.procDurationMs) {
                existingProcessGroup.dataset.procStartedAt = String(procNow());
                refreshProcessAggregateStats(existingProcessGroup);
            }
            existingProcessGroup.classList.remove('is-collapsed');
            var top = existingProcessGroup.querySelector('.process-aggregate-top');
            if (top) top.setAttribute('aria-expanded', 'true');
        }
        resetLlmState(runCtx);
        initRunFinalTracking(runCtx);
        finalizeLlmStreamChunks(runCtx);
        const ac = new AbortController();
        setSessionRunState(runSessionId, { controller: ac, ctx: runCtx, reattached: true });
        setSendButtonState();
        syncSessionListIndicatorClasses();
        liveAutoFollow = true;
        streamProcNearBottom = true;
        const preCount = await getUiEventCount(runSessionId);
        const streamUrl = '/sessions/' + encodeURIComponent(runSessionId)
            + '/stream?after_index=' + encodeURIComponent(String(preCount - 1));
        const response = await fetch(streamUrl, { signal: ac.signal });
        await consumeAgentSseResponse(response, runCtx, runSessionId, preCount);
    } catch (error) {
        if (error && error.name === 'AbortError') return;
        console.error('reattach stream failed:', error);
        const msg = (error && error.message) ? String(error.message) : String(error);
        if (runCtx && runSessionId === currentSessionId) appendLog(runCtx, '恢复实时流失败: ' + msg, 'error-log', runSessionId);
    } finally {
        if (runCtx) {
            finalizeLlmStreamChunks(runCtx);
            finalizeProgressStreamChunks(runCtx);
        }
        if (runSessionId === currentSessionId && getRunAbortReason(runSessionId, runCtx) !== 'user') {
            scheduleFinalVisibleAfterRunIfEnabled(runSessionId, runCtx, { delayMs: 120 });
        }
        if (getSessionRunState(runSessionId) && getSessionRunState(runSessionId).reattached) {
            clearSessionRunState(runSessionId);
        }
        setSendButtonState();
        syncSessionListIndicatorClasses();
        void refreshSingleSessionRow(runSessionId);
        setTimeout(function () { reconcileRunStateFromServer({ silent: true }); }, 800);
        applyContextTokenLabelForCurrentSession();
        if (runSessionId === currentSessionId) {
            clearSessionUnreadState(runSessionId);
            updateSubagentContinueBanner(runSessionId);
        }
    }
}

function scheduleActiveSessionReconnect(sessionId, opts) {
    if (!isMyAgentFeatureEnabled('streamReconnect', false)) return;
    opts = opts || {};
    var sid = String(sessionId || '');
    if (!sid) return;
    var delayMs = Math.max(0, Number(opts.delayMs) || 0);
    setTimeout(async function () {
        if (sid !== currentSessionId) return;
        try {
            if (typeof reconcileRunStateFromServer === 'function') {
                await reconcileRunStateFromServer({ silent: true });
            }
            if (sid !== currentSessionId) return;
            if ((isServerStreamActive(sid) || isSessionRunning(sid)) && typeof maybeStartStreamPollForSession === 'function') {
                maybeStartStreamPollForSession(sid, { skipInitialLoad: true });
            }
        } catch (e) {
            /* keep current UI state; normal polling or user action can retry later */
        }
    }, delayMs);
}

async function processRewriteTruncateAsync(pr) {
    try {
        const anchor = document.querySelector('.msg-wrap--user[data-truncate-from="' + String(pr.before) + '"]');
        const res = await truncateSessionOnServer(pr.before, { sessionId: pr.sessionId, backup: false });
        if (!res || !res.ok) {
            showUiAlert({
                title: '截断失败',
                message: describeServerSyncFailure(res, '无法同步服务器，改写未生效。'),
                variant: 'error'
            });
            return false;
        }
        if (currentSessionId === pr.sessionId) {
            scheduleContextTokensAfterPaint(pr.sessionId);
            if (anchor) {
                removeMessagesFromNode(anchor);
                if (activeInlineRewriteWrap === anchor) activeInlineRewriteWrap = null;
                syncDisconnectedProcessGroups();
                rebuildToc();
            }
        }
        return true;
    } catch (error) {
        console.error('异步截断失败:', error);
        showUiAlert({
            title: '截断失败',
            message: describeServerSyncFailure({ error: (error && error.message) || String(error) }, '无法同步服务器，改写未生效。'),
            variant: 'error'
        });
        return false;
    }
}

function getFollowupQueue(sessionId) {
    const sid = String(sessionId || '');
    if (!sid) return [];
    if (!followupQueueLoadedBySession[sid]) {
        followupQueueBySession[sid] = readStoredFollowupQueue(sid);
        followupQueueLoadedBySession[sid] = true;
    }
    if (!followupQueueBySession[sid]) followupQueueBySession[sid] = [];
    return followupQueueBySession[sid];
}

function followupQueueStorageKey(sessionId) {
    return LS_FOLLOWUP_QUEUE_PREFIX + String(sessionId || '');
}

function normalizeStoredFollowupItem(item) {
    if (!item || typeof item !== 'object') return null;
    var text = String(item.text || '').trim();
    if (!text) return null;
    var display = String(item.display || item.text || '').trim();
    return {
        id: item.id || ('stored-followup-' + (followupQueueSeq++)),
        text: text,
        display: display || text,
        createdAt: Number(item.createdAt) || Date.now(),
    };
}

function readStoredFollowupQueue(sessionId) {
    try {
        var raw = localStorage.getItem(followupQueueStorageKey(sessionId));
        if (!raw) return [];
        var arr = JSON.parse(raw);
        if (!Array.isArray(arr)) return [];
        var out = arr.map(normalizeStoredFollowupItem).filter(Boolean);
        out.forEach(function (item) {
            var n = Number(item.id);
            if (Number.isFinite(n)) followupQueueSeq = Math.max(followupQueueSeq, Math.floor(n) + 1);
        });
        return out;
    } catch (e) {
        return [];
    }
}

function persistFollowupQueue(sessionId) {
    const sid = String(sessionId || '');
    if (!sid) return;
    var q = followupQueueBySession[sid] || [];
    var pending = q.filter(function (item) {
        var status = item && item.status ? String(item.status) : '';
        return item && item.text && !status;
    }).map(function (item) {
        return {
            id: item.id,
            text: item.text,
            display: item.display || item.text,
            createdAt: item.createdAt || Date.now(),
        };
    });
    try {
        var key = followupQueueStorageKey(sid);
        if (pending.length) localStorage.setItem(key, JSON.stringify(pending));
        else localStorage.removeItem(key);
    } catch (e) { /* ignore */ }
}

function removeStoredFollowupQueue(sessionId) {
    const sid = String(sessionId || '');
    if (!sid) return;
    delete followupQueueBySession[sid];
    delete followupQueueLoadedBySession[sid];
    try { localStorage.removeItem(followupQueueStorageKey(sid)); } catch (e) { /* ignore */ }
}

function inputHasSendableText() {
    if (!messageInput) return false;
    return String(messageInput.value || '').replace(/[\u200B-\u200D\uFEFF]/g, '').trim().length > 0;
}

function ensureFollowupQueueHost() {
    var existing = document.getElementById('followup-queue-panel');
    if (existing) return existing;
    var panel = document.createElement('div');
    panel.id = 'followup-queue-panel';
    panel.className = 'followup-queue-panel';
    panel.setAttribute('aria-live', 'polite');
    var anchor = messageInput && messageInput.closest ? messageInput.closest('.composer-row') : null;
    var host = anchor && anchor.parentNode ? anchor.parentNode : null;
    if (host && anchor) host.insertBefore(panel, anchor);
    else document.body.appendChild(panel);
    return panel;
}

function positionFollowupQueuePanel() {
    var panel = document.getElementById('followup-queue-panel');
    if (!panel) return;
    panel.style.left = '';
    panel.style.top = '';
    panel.style.width = '';
}

function renderFollowupQueue(sessionId) {
    var sid = String(sessionId != null ? sessionId : (currentSessionId || ''));
    var panel = ensureFollowupQueueHost();
    if (!panel) return;
    if (!sid || sid !== currentSessionId) {
        if (!currentSessionId) {
            panel.innerHTML = '';
            panel.classList.remove('is-visible');
            panel.removeAttribute('data-session-id');
        }
        return;
    }
    var q = getFollowupQueue(sid);
    panel.innerHTML = '';
    panel.dataset.sessionId = sid;
    panel.classList.toggle('is-visible', !!q.length);
    if (!q.length) {
        positionFollowupQueuePanel();
        return;
    }
    q.forEach(function (item, idx) {
        var row = document.createElement('div');
        row.className = 'followup-queue-row';
        row.classList.toggle('is-sending', item.status === 'sending' || item.status === 'submitting');
        row.classList.toggle('is-accepted', item.status === 'accepted');
        row.classList.toggle('is-sent', item.status === 'sent');
        row.dataset.id = String(item.id);
        var order = document.createElement('div');
        order.className = 'followup-queue-order';
        order.textContent = String(idx + 1);
        var text = document.createElement('div');
        text.className = 'followup-queue-text';
        text.textContent = item.display || item.text || '';
        var status = document.createElement('div');
        status.className = 'followup-queue-status';
        status.textContent = getFollowupStatusText(item);
        var sendNow = document.createElement('button');
        sendNow.type = 'button';
        sendNow.className = 'followup-queue-action followup-queue-send';
        sendNow.textContent = '立即发送';
        sendNow.disabled = !!item.status;
        var undo = document.createElement('button');
        undo.type = 'button';
        undo.className = 'followup-queue-action followup-queue-undo';
        undo.textContent = '撤回';
        undo.disabled = item.status === 'sent' || item.status === 'withdrawing';
        sendNow.addEventListener('click', function (ev) {
            ev.preventDefault();
            sendFollowupNow(String(item.id));
        });
        undo.addEventListener('click', function (ev) {
            ev.preventDefault();
            withdrawFollowup(String(item.id));
        });
        row.appendChild(order);
        row.appendChild(text);
        row.appendChild(status);
        row.appendChild(sendNow);
        row.appendChild(undo);
        panel.appendChild(row);
    });
    positionFollowupQueuePanel();
    if (typeof scrollChatToBottomIfFollow === 'function') {
        scrollChatToBottomIfFollow(sid, {});
    }
}

function getFollowupStatusText(item) {
    var status = item && item.status ? String(item.status) : '';
    if (status === 'withdrawing') return '撤回中';
    if (status === 'submitting') return '提交中';
    if (status === 'accepted') return '已接收，等待插入';
    if (status === 'sending') return '发送中';
    if (status === 'sent') return '已发送';
    return '待发送';
}

function enqueueCurrentInputAsFollowup() {
    if (!isMyAgentFeatureEnabled('followupRestart', false)) return false;
    const sid = currentSessionId;
    if (!sid) return false;
    rewriteInputWorkspacePaths();
    const visibleMessage = messageInput.value;
    const rawMessage = expandInputPathTokens(visibleMessage);
    if (!String(rawMessage).trim()) return false;
    getFollowupQueue(sid).push({
        id: followupQueueSeq++,
        text: rawMessage,
        display: visibleMessage,
        createdAt: Date.now(),
    });
    persistFollowupQueue(sid);
    messageInput.value = '';
    persistInputDraft(sid, '');
    clearInputPathTokens();
    autoResizeTextarea();
    renderFollowupQueue(sid);
    setSendButtonState();
    return true;
}

function takeFollowupItem(sessionId, itemId) {
    var q = getFollowupQueue(sessionId);
    var idx = q.findIndex(function (item) { return String(item.id) === String(itemId); });
    if (idx < 0) return null;
    var item = q.splice(idx, 1)[0] || null;
    persistFollowupQueue(sessionId);
    return item;
}

function withdrawFollowup(itemId) {
    const sid = currentSessionId;
    var q = getFollowupQueue(sid);
    var pendingItem = q.find(function (entry) { return String(entry.id) === String(itemId); });
    if (pendingItem && (pendingItem.status === 'sending' || pendingItem.status === 'submitting' || pendingItem.status === 'accepted')) {
        pendingItem.cancelRequested = true;
        pendingItem.status = 'withdrawing';
        persistFollowupQueue(sid);
        renderFollowupQueue(sid);
        if (pendingItem.steerInFlight && !pendingItem.steerId) return;
        cancelSteerMessage(sid, pendingItem).then(function () {
            var item = takeFollowupItem(sid, itemId);
            if (item) returnFollowupToInput(sid, item);
        }).catch(function (e) {
            var item = q.find(function (entry) { return String(entry.id) === String(itemId); });
            if (item) item.status = 'sending';
            persistFollowupQueue(sid);
            renderFollowupQueue(sid);
            appendLogVisible('追问已被接收，无法撤回: ' + ((e && e.message) || String(e)), 'error-log');
        });
        return;
    }
    const item = takeFollowupItem(sid, itemId);
    if (!item) return;
    returnFollowupToInput(sid, item);
}

function returnFollowupToInput(sid, item) {
    const existing = String(messageInput.value || '');
    const returned = String(item.display || item.text || '');
    messageInput.value = existing.trim() ? (returned + '\n' + existing) : returned;
    rewriteInputWorkspacePaths();
    persistInputDraft(sid, messageInput.value);
    autoResizeTextarea();
    renderFollowupQueue(sid);
    setSendButtonState();
    messageInput.focus();
}

async function sendSteerMessage(sessionId, text, clientId) {
    var r = await fetch('/sessions/' + encodeURIComponent(sessionId) + '/steer', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, client_id: clientId || '' }),
    });
    var j = await r.json().catch(function () {
        return { ok: false, error: 'steer failed' };
    });
    if (!r.ok || !j.ok) throw new Error((j && j.error) || 'steer failed');
    return j;
}

async function cancelSteerMessage(sessionId, item) {
    var r = await fetch('/sessions/' + encodeURIComponent(sessionId) + '/steer', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            steer_id: (item && item.steerId) || '',
            client_id: (item && item.clientId) || '',
        }),
    });
    var j = await r.json().catch(function () {
        return { ok: false, error: 'cancel steer failed' };
    });
    if (!r.ok || !j.ok) throw new Error((j && j.error) || 'cancel steer failed');
    return j;
}

function removeConsumedFollowupSteer(sessionId, ev) {
    const sid = String(sessionId || '');
    if (!sid || !ev || !ev.steer) return false;
    var steerId = String(ev.steer_id || '');
    var clientId = String(ev.client_id || '');
    if (!steerId && !clientId) return false;
    var q = getFollowupQueue(sid);
    var item = q.find(function (entry) {
        return (clientId && String(entry.clientId || '') === clientId)
            || (steerId && String(entry.steerId || '') === steerId);
    });
    if (!item) return false;
    takeFollowupItem(sid, item.id);
    renderFollowupQueue(sid);
    return true;
}

function scheduleFollowupQueueDrain(sessionId, delayMs) {
    const sid = String(sessionId || '');
    if (!sid) return;
    setTimeout(function () { drainFollowupQueue(sid); }, Math.max(0, Number(delayMs) || 0));
}

async function sendFollowupNow(itemId, sessionId) {
    const sid = String(sessionId || currentSessionId || '');
    if (!sid) return;
    var q = getFollowupQueue(sid);
    var idx = q.findIndex(function (item) { return String(item.id) === String(itemId); });
    if (idx < 0) return;
    const item = q[idx];
    if (!item) return;
    item.clientId = item.clientId || ('followup-' + item.id + '-' + Date.now());
    item.status = 'submitting';
    persistFollowupQueue(sid);
    renderFollowupQueue(sid);
    try {
        item.steerInFlight = true;
        var steerResult = await sendSteerMessage(sid, item.text, item.clientId);
        item.steerInFlight = false;
        item.steerId = steerResult && steerResult.item && steerResult.item.id ? String(steerResult.item.id) : '';
        if (item.cancelRequested) {
            await cancelSteerMessage(sid, item);
            var withdrawn = takeFollowupItem(sid, item.id);
            if (withdrawn) returnFollowupToInput(sid, withdrawn);
            return;
        }
        if (steerResult && steerResult.restart && isMyAgentFeatureEnabled('followupRestart', false)) {
            var previousRun = getSessionRunState(sid);
            if (previousRun) abortSessionRun(sid, 'followup-restart');
            markSessionRunInactive(sid);
            item.status = 'sent';
            persistFollowupQueue(sid);
            renderFollowupQueue(sid);
            setSendButtonState();
            syncSessionListIndicatorClasses();
            setTimeout(function () {
                takeFollowupItem(sid, itemId);
                renderFollowupQueue(sid);
            }, 1200);
            return sendMessage({
                message: item.text,
                fromQueue: true,
                sessionId: sid,
                forceStart: true,
                preserveInput: true,
            });
        }
        item.status = 'accepted';
        persistFollowupQueue(sid);
        renderFollowupQueue(sid);
        return;
    } catch (e) {
        item.steerInFlight = false;
        var msg = (e && e.message) ? String(e.message) : String(e);
        var canFallbackToChat = /session is not running/i.test(msg);
        if (!canFallbackToChat) {
            if (item.cancelRequested) {
                item.status = 'sending';
                item.cancelRequested = false;
                persistFollowupQueue(sid);
                renderFollowupQueue(sid);
                appendLogVisible('追问已被接收，无法撤回: ' + msg, 'error-log');
                return;
            }
            item.status = '';
            persistFollowupQueue(sid);
            renderFollowupQueue(sid);
            appendLogVisible('追问插入失败: ' + msg, 'error-log');
            return;
        }
    }
    item.status = 'sent';
    persistFollowupQueue(sid);
    renderFollowupQueue(sid);
    setTimeout(function () {
        takeFollowupItem(sid, itemId);
        renderFollowupQueue(sid);
    }, 1200);
    return sendMessage({ message: item.text, fromQueue: true, sessionId: sid });
}

function drainFollowupQueue(sessionId) {
    const sid = String(sessionId || '');
    if (!sid || followupQueueDraining[sid]) return;
    if (isSessionRunning(sid) || (sendPipelineLock && sendPipelineLockSessionId === sid)) return;
    var q = getFollowupQueue(sid);
    if (!q.length) {
        renderFollowupQueue(sid);
        return;
    }
    var nextIdx = q.findIndex(function (item) { return !item.status; });
    if (nextIdx < 0) {
        renderFollowupQueue(sid);
        return;
    }
    var item = q[nextIdx];
    followupQueueDraining[sid] = true;
    var attemptedId = String(item.id);
    Promise.resolve(sendFollowupNow(item.id, sid))
        .finally(function () {
            delete followupQueueDraining[sid];
            var q2 = getFollowupQueue(sid);
            var same = q2.find(function (entry) { return String(entry.id) === attemptedId; });
            if (same && same.status && same.status !== 'sent') return;
            if (same && !same.status) return;
            if (q2.some(function (entry) { return !entry.status; })) {
                scheduleFollowupQueueDrain(sid, 0);
            }
        });
}

async function sendMessage(options) {
    options = options || {};
    messageLoadEpoch += 1;
    /* 立即快照「提交会话」：之后所有 await 都不能改变它，避免用户在 await 空隙切走后消息发到新会话。
       关键不变式：runSessionId === submitSessionId 全程恒等。 */
    const submitSessionIdInitial = options.sessionId || currentSessionId;
    if (!options.fromQueue && !options.fromInlineRewrite) rewriteInputWorkspacePaths();
    const visibleMessage = options.message != null ? String(options.message) : messageInput.value;
    const rawMessage = (options.fromQueue || options.fromInlineRewrite) ? visibleMessage : expandInputPathTokens(visibleMessage);
    if (!String(rawMessage).trim()) return;
    if (isSessionRunning(submitSessionIdInitial) && !options.forceStart) return;
    if (sendPipelineLock && sendPipelineLockSessionId === submitSessionIdInitial && !options.forceStart) return;
    if (options.forceStart && submitSessionIdInitial) {
        var previousRun = getSessionRunState(submitSessionIdInitial);
        if (previousRun) abortSessionRun(submitSessionIdInitial, 'followup-restart');
    }

    /* 立即上锁：阻止后续连击；锁的 key 是提交时的会话，而非当前会话。 */
    sendPipelineLock = true;
    sendPipelineLockSessionId = submitSessionIdInitial;
    let submittedRunCtx = null;
    let submittedRunSessionId = submitSessionIdInitial;
    try {

    if (pendingRewriteTruncate && pendingRewriteTruncate.sessionId === submitSessionIdInitial) {
        const pendingRewrite = pendingRewriteTruncate;
        const truncated = await processRewriteTruncateAsync(pendingRewrite);
        if (!truncated) {
            pendingRewriteTruncate = null;
            return;
        }
        pendingRewriteTruncate = null;
        uiEventCountCache.updateFromServer(submitSessionIdInitial, pendingRewrite.before);
    }
    hideRewriteUndoToast();

    hideSubagentContinueBanner();
    const userSentAt = new Date().toISOString();

    let submitSessionId = submitSessionIdInitial;
    if (!submitSessionId) {
        await createNewSession();
        submitSessionId = currentSessionId;
        if (!submitSessionId) return;
        sendPipelineLockSessionId = submitSessionId;
    }
    // 使用缓存的事件计数，实现乐观更新
    let preCount = uiEventCountCache.get(submitSessionId);
    try {
        const serverCountBeforeSend = preCount;
        if (Number.isFinite(Number(serverCountBeforeSend))) {
            preCount = Math.max(preCount, Number(serverCountBeforeSend));
            uiEventCountCache.updateFromServer(submitSessionId, preCount);
        }
    } catch (err) {
        console.error('获取事件计数失败:', err);
    }
    const existingStreamForIndex = (submitSessionId === currentSessionId) ? getVisibleChatStream() : null;
    if (existingStreamForIndex) {
        existingStreamForIndex.querySelectorAll('.msg-wrap--user[data-event-index]').forEach(function (wrap) {
            const n = Number(wrap.getAttribute('data-event-index'));
            if (Number.isFinite(n)) preCount = Math.max(preCount, Math.floor(n) + 1);
        });
    }
    const runSessionId = submitSessionId;
    submittedRunSessionId = runSessionId;
    if (sessionStore && typeof sessionStore.resetSseSeq === 'function') {
        sessionStore.resetSseSeq(runSessionId);
    }
    const clientRunId = (window.crypto && window.crypto.randomUUID)
        ? window.crypto.randomUUID()
        : ('run-' + Date.now() + '-' + Math.random().toString(16).slice(2));

    /* 用户在 createNewSession / getUiEventCount 期间切走：
       后台仍然发起 /chat（消息已属于 runSessionId），但不要往当前可见 stream 画用户气泡。 */
    const switchedAway = currentSessionId !== runSessionId;
    let runCtx;
    if (switchedAway) {
        const offscreen = document.createElement('div');
        offscreen.className = 'chat-stream is-offscreen';
        if (typeof offscreenRoot !== 'undefined' && offscreenRoot) offscreenRoot.appendChild(offscreen);
        runCtx = newDomContext(offscreen);
    } else {
        if (!getVisibleChatStream()) ensureVisibleChatStreamSlot();
        runCtx = newDomContext(getVisibleChatStream());
    }
    submittedRunCtx = runCtx;
    runCtx.runId = clientRunId;
    initRunFinalTracking(runCtx);
    runCtx.runStartedAt = userSentAt;
    runCtx.lastUserEventIndex = preCount;
    resetLlmState(runCtx);
    finalizeLlmStreamChunks(runCtx);
    sealProcessGroup(runCtx);
    const ac = new AbortController();
    if (typeof clearSessionStreamStopSuppress === 'function') clearSessionStreamStopSuppress(runSessionId);
    setSessionRunState(runSessionId, { controller: ac, ctx: runCtx, runId: clientRunId });
    setSendButtonState();
    syncSessionListIndicatorClasses();
    applySessionEvent({ type: 'user', content: rawMessage, created_at: userSentAt }, {
        sessionId: runSessionId,
        eventIndex: preCount,
        source: 'local-send',
    });
        if (!switchedAway) {
        liveAutoFollow = true;
        streamChatNearBottom = true;
        streamProcNearBottom = true;
        appendMessage(runCtx, 'user', rawMessage, { eventIndex: preCount, turnTruncateIdx: preCount, createdAt: userSentAt }, runSessionId);
        if (!options.fromQueue && !options.preserveInput) {
            messageInput.value = '';
            persistInputDraft(runSessionId, '');
            clearInputPathTokens();
            autoResizeTextarea();
            setSendButtonState();
        }
    }
    updateSidebarLastUserPreviewImmediate(runSessionId, rawMessage);
    lastUserMessageBySession[runSessionId] = rawMessage;
    const formData = new FormData();
    formData.append('message', rawMessage);
    formData.append('session_id', runSessionId);
    formData.append('client_run_id', clientRunId);
    formData.append('stream_protocol', 'runtime_v2');
    /* 发送后优先使用本轮 API usage/cache_stats 刷新 token；缺少 usage 时仍保留上一快照。 */
    if (!switchedAway) applyContextTokenLabelForCurrentSession();
    let streamEventIdx = preCount + 1;
    
    // 异步更新事件计数缓存（从服务器获取真实计数）
    getUiEventCount(submitSessionId).then(function(serverCount) {
        uiEventCountCache.updateFromServer(submitSessionId, serverCount);
    }).catch(function(err) {
        console.error('更新事件计数缓存失败:', err);
    });
    let streamDisconnectedUnexpectedly = false;
    try {
        const response = await fetch('/chat', { method: 'POST', body: formData, signal: ac.signal });
        streamEventIdx = await consumeAgentSseResponse(response, runCtx, runSessionId, streamEventIdx);
    } catch (error) {
        if (error.name === 'AbortError') {
            if (getRunAbortReason(runSessionId, runCtx) === 'user') appendLog(runCtx, '任务已中断', 'status', runSessionId);
        }
        else {
            console.error('请求失败:', error);
            streamDisconnectedUnexpectedly = true;
            const msg = (error && error.message) ? String(error.message) : String(error);
            appendLog(runCtx, '请求失败: ' + msg, 'error-log', runSessionId);
        }
    } finally {
        finalizeLlmStreamChunks(runCtx);
        finalizeProgressStreamChunks(runCtx);
        if (!switchedAway && runSessionId === currentSessionId && getRunAbortReason(runSessionId, runCtx) !== 'user') {
            scheduleFinalVisibleAfterRunIfEnabled(runSessionId, runCtx, { delayMs: 120 });
        }
        if (runSessionId === currentSessionId) renderTodoPlanForCurrentSession();
        if (liveAutoFollow && !switchedAway) {
            scrollProcessBodyToBottom(runCtx, runSessionId);
            scrollChatToBottomIfFollow(runSessionId, {});
        }
        if (runSessionId !== currentSessionId) {
            void tryMarkSessionUnreadComplete(runSessionId);
        } else {
            clearSessionUnreadState(runSessionId);
            updateSubagentContinueBanner(runSessionId);
        }
        if (getSessionRunState(runSessionId)) {
            clearSessionRunStateIfMatch(runSessionId, clientRunId);
        }
        if (streamDisconnectedUnexpectedly && runSessionId === currentSessionId && getRunAbortReason(runSessionId, runCtx) !== 'user') {
            scheduleActiveSessionReconnect(runSessionId, { delayMs: 500 });
            scheduleActiveSessionReconnect(runSessionId, { delayMs: 2500 });
        }
        if (runSessionId !== currentSessionId) {
            const el = runCtx.stream;
            if (el && el.parentNode) el.remove();
        }
        setSendButtonState();
        syncSessionListIndicatorClasses();
        void refreshSingleSessionRow(runSessionId);
        applyContextTokenLabelForCurrentSession();
        if (runSessionId === currentSessionId && countRunningSubagentCards() > 0) {
            scheduleSubagentIncrementalSync();
        }
    }
    } finally {
        sendPipelineLock = false;
        sendPipelineLockSessionId = null;
        var stoppedByUser = getRunAbortReason(submittedRunSessionId, submittedRunCtx) === 'user';
        if (!stoppedByUser && (!options.fromQueue || getFollowupQueue(submittedRunSessionId).length)) {
            setTimeout(function () { drainFollowupQueue(submittedRunSessionId); }, 0);
        }
    }
}

messageInput.addEventListener('keydown', function onFollowupInputKeydown(e) {
    if (!isMyAgentFeatureEnabled('followupRestart', false)) return;
    if (e.key !== 'Enter') return;
    e.stopImmediatePropagation();
    if (e.ctrlKey && !e.shiftKey && !e.metaKey) {
        const start = this.selectionStart;
        const end = this.selectionEnd;
        this.value = this.value.substring(0, start) + '\n' + this.value.substring(end);
        this.selectionStart = this.selectionEnd = start + 1;
        e.preventDefault();
        autoResizeTextarea();
        return;
    }
    if (e.shiftKey) return;
    e.preventDefault();
    if (isSessionRunning(currentSessionId)) {
        enqueueCurrentInputAsFollowup();
        return;
    }
    sendMessage();
}, true);

messageInput.addEventListener('keydown', function onInputKeydown(e) {
    if (e.key !== 'Enter') return;
    // Ctrl+Enter → 插入换行（跨浏览器兼容）
    if (e.ctrlKey && !e.shiftKey && !e.metaKey) {
        const start = this.selectionStart;
        const end = this.selectionEnd;
        this.value = this.value.substring(0, start) + '\n' + this.value.substring(end);
        this.selectionStart = this.selectionEnd = start + 1;
        e.preventDefault();
        autoResizeTextarea();
        return;
    }
    // Shift+Enter → 浏览器默认插入换行
    if (e.shiftKey) return;
    // 纯 Enter → 发送
    if (isSessionRunning(currentSessionId)) return;
    e.preventDefault();
    sendMessage();
});
chatContainer.addEventListener('scroll', function () {
    refreshLiveAutoFollowPins();
    scheduleTocActiveUpdate();
}, { passive: true });
sendBtn.addEventListener('click', function (e) {
    e.stopImmediatePropagation();
    if (isSessionRunning(currentSessionId)) {
        if (isMyAgentFeatureEnabled('followupRestart', false) && inputHasSendableText()) enqueueCurrentInputAsFollowup();
        else pauseCurrentRun();
        return;
    }
    sendMessage();
}, true);
sendBtn.addEventListener('click', function () {
    if (isSessionRunning(currentSessionId)) pauseCurrentRun();
    else sendMessage();
});
window.addEventListener('resize', positionFollowupQueuePanel);
window.addEventListener('scroll', positionFollowupQueuePanel, true);
(function bindRewriteUndo() {
    const toast = document.getElementById('rewrite-undo-toast');
    const btn = toast && toast.querySelector('.rewrite-undo-btn');
    if (!btn) return;
    btn.addEventListener('click', async function (e) {
        e.preventDefault();
        if (!rewriteUndoState) { hideRewriteUndoToast(); return; }
        const s = rewriteUndoState;
        if (s.type === 'rewrite_pending') {
            const prevIn = (s.data && s.data.prevInput != null) ? s.data.prevInput : '';
            messageInput.value = prevIn;
            rewriteInputWorkspacePaths();
            autoResizeTextarea();
            messageInput.focus();
            pendingRewriteTruncate = null;
            hideRewriteUndoToast();
            return;
        }
        if (s.type === 'input' && s.data) {
            messageInput.value = s.data.prev;
            rewriteInputWorkspacePaths();
            autoResizeTextarea();
            messageInput.focus();
            hideRewriteUndoToast();
            return;
        }
        if (s.type === 'tail' && s.data && s.data.sessionId && s.data.tail && s.data.tail.length) {
            try {
                const r = await historyOperationJson(
                    '/sessions/' + encodeURIComponent(s.data.sessionId) + '/append_ui_events',
                    { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ events: s.data.tail }) },
                    45000
                );
                if (!r || !r.ok) { alert('撤销失败，请重试。'); return; }
                if (s.data.sessionId === currentSessionId) {
                    showLoading();
                    try {
                        await loadSessionMessages(s.data.sessionId, 'bottom', { full: true });
                    } finally {
                        hideLoading();
                    }
                }
            } catch (err) { console.error(err); alert('撤销失败，请重试。'); return; }
        }
        hideRewriteUndoToast();
    });
})();
(function bindSubagentContinueBannerOnce() {
    if (window.__myAgentSubagentContinueBound) return;
    window.__myAgentSubagentContinueBound = true;
    var btn = document.getElementById('subagent-continue-btn');
    var dismissBtn = document.getElementById('subagent-continue-dismiss');
    if (btn) btn.addEventListener('click', function (e) {
        e.preventDefault();
        if (!currentSessionId || subagentContinueInFlight) return;
        void startContinueAfterSubagents(currentSessionId);
    });
    if (dismissBtn) dismissBtn.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        dismissSubagentContinueBanner(currentSessionId);
    });
})();
initUiHoverTips(document);
