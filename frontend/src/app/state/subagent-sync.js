var subagentCardSyncTimer = null;
var subagentContextFetchInFlight = Object.create(null);
var subagentTreeRefreshTimer = null;
var subagentTreeRefreshTarget = null;
var subagentTreeRefreshInflight = null;
var subagentTreeRefreshInflightSid = null;
var subagentTreeRefreshQueued = false;
var subagentStatsRefreshRaf = 0;
var subagentStatsPending = new Set();

function scheduleSubagentCardStats(card) {
    if (!card) return;
    if (subagentPanelOpen
        && !card.classList.contains('is-expanded')
        && card.dataset.viewportVisible !== '1') return;
    subagentStatsPending.add(card);
    if (subagentStatsRefreshRaf) return;
    subagentStatsRefreshRaf = setTimeout(function () {
        subagentStatsRefreshRaf = 0;
        var cards = Array.from(subagentStatsPending);
        subagentStatsPending.clear();
        cards.forEach(refreshSubagentCardStats);
    }, 250);
}

function getSubagentIncrementalSyncDelay(runningCount) {
    if (isSessionRunning(currentSessionId)) return 8000;
    if (runningCount > 20) return 6000;
    if (runningCount > 10) return 4000;
    if (runningCount > 5) return 3000;
    return 2200;
}

function runTasksWithConcurrency(items, limit, worker) {
    if (!items || !items.length) return Promise.resolve();
    var idx = 0;
    var n = Math.max(1, Math.min(limit || 1, items.length));
    function next() {
        if (idx >= items.length) return Promise.resolve();
        var cur = idx++;
        return Promise.resolve(worker(items[cur], cur)).then(next);
    }
    var starters = [];
    for (var i = 0; i < n; i += 1) starters.push(next());
    return Promise.all(starters);
}

function scheduleRefreshSubagentTreePanel(sessionId, delayMs) {
    if (!sessionId || replayingMessages) return;
    subagentTreeRefreshTarget = sessionId;
    if (subagentTreeRefreshTimer) clearTimeout(subagentTreeRefreshTimer);
    subagentTreeRefreshTimer = setTimeout(function () {
        subagentTreeRefreshTimer = null;
        var sid = subagentTreeRefreshTarget;
        subagentTreeRefreshTarget = null;
        if (sid && sid === currentSessionId) void refreshSubagentTreePanel(sid);
    }, delayMs == null ? 150 : delayMs);
}

function cancelScheduledSubagentTreeRefresh() {
    if (subagentTreeRefreshTimer) {
        clearTimeout(subagentTreeRefreshTimer);
        subagentTreeRefreshTimer = null;
    }
    subagentTreeRefreshTarget = null;
    subagentTreeRefreshQueued = false;
}

function stopSubagentIncrementalSync() {
    if (subagentCardSyncTimer) {
        clearTimeout(subagentCardSyncTimer);
        subagentCardSyncTimer = null;
    }
}

function scheduleSubagentIncrementalSync() {
    if (subagentCardSyncTimer) return;
    var delay = isSessionRunning(currentSessionId) ? 4000 : 1200;
    subagentCardSyncTimer = setTimeout(function () {
        subagentCardSyncTimer = null;
        runSubagentIncrementalSync();
    }, delay);
}

function countRunningSubagentCards() {
    var n = 0;
    document.querySelectorAll('.subagent-grid-card .subagent-status-dot.is-running').forEach(function () { n += 1; });
    return n;
}

async function runSubagentIncrementalSync() {
    var grid = document.getElementById('subagent-grid');
    if (!grid || !currentSessionId || !subagentPanelOpen) {
        stopSubagentIncrementalSync();
        return;
    }
    if (document.visibilityState !== 'visible') {
        subagentCardSyncTimer = setTimeout(function () {
            subagentCardSyncTimer = null;
            runSubagentIncrementalSync();
        }, 5000);
        return;
    }
    var tasks = [];
    grid.querySelectorAll('.subagent-grid-card').forEach(function (card) {
        var dot = card.querySelector('.subagent-status-dot.is-running');
        if (!dot) return;
        var aid = card.getAttribute('data-agent-id');
        if (!aid) return;
        tasks.push({ aid: aid, card: card });
    });
    if (tasks.length) {
        await runTasksWithConcurrency(tasks, 1, function (t) {
            return incrementalSyncSubagentCard(t.aid, t.card);
        });
    }
    var runningN = countRunningSubagentCards();
    if (runningN === 0 && currentSessionId && !replayingMessages) {
        updateSubagentContinueBanner(currentSessionId);
        void tryMarkSessionUnreadComplete(currentSessionId);
    }
    if (runningN > 0 && subagentPanelOpen) {
        subagentCardSyncTimer = setTimeout(function () {
            subagentCardSyncTimer = null;
            runSubagentIncrementalSync();
        }, getSubagentIncrementalSyncDelay(runningN));
    }
}

async function incrementalSyncSubagentCard(agentId, card) {
    if (!agentId || !card) return;
    var body = card.querySelector('.subagent-card-body');
    if (!body || body.dataset.loading === '1') return;
    if (!shouldLoadSubagentCardBodies() && body.dataset.loaded !== '1') return;
    var parentRunning = isSessionRunning(currentSessionId);
    var prevCount = currentSessionId ? subagentStore.getEventCount(currentSessionId, agentId) : 0;
    var summaryOnly = !shouldStreamSubagentProcessDom(card);
    try {
        var afterIndex = Math.max(-1, Math.floor(Number(prevCount) || 0) - 1);
        var msgResp = await fetch('/sessions/' + encodeURIComponent(agentId)
            + '/messages?after_index=' + encodeURIComponent(String(afterIndex))
            + '&limit=500');
        if (!msgResp.ok) return;
        var msgData = await msgResp.json();
        var events = normalizeSubagentMessagesPayload(msgData);
        var rangeStart = msgData && Number.isFinite(Number(msgData.range_start))
            ? Math.floor(Number(msgData.range_start))
            : Math.max(0, afterIndex + 1);
        var total = msgData && Number.isFinite(Number(msgData.total))
            ? Math.floor(Number(msgData.total))
            : Math.max(prevCount, rangeStart + events.length);
        if (!events.length || total <= prevCount) {
            if (total > prevCount) setSubagentCardEventCount(agentId, total);
            return;
        }
        if (parentRunning && body.dataset.loaded === '1') {
            setSubagentCardEventCount(agentId, total);
            return;
        }
        if (!body.isConnected) return;
        var gotFinal = false;
        for (var fi = 0; fi < events.length; fi += 1) {
            if (events[fi] && events[fi].type === 'final') { gotFinal = true; break; }
        }
        if (body.dataset.loaded !== '1') {
            if (!shouldLoadSubagentCardBodies()) return;
            if (summaryOnly) {
                ensureSubagentCardStreamReady(card, agentId);
                var ctxNew = getSubagentCardStreamCtx(body, card, agentId);
                for (var si = 0; si < events.length; si += 1) {
                    var sev = events[si];
                    if (!sev || typeof sev !== 'object') continue;
                    if (sev.type !== 'user' && sev.type !== 'final') continue;
                    dispatchSubagentCardEvent(ctxNew, card, sev, rangeStart + si, agentId);
                }
                rebindSubagentCardBody(body, card, agentId);
            } else {
                renderSubagentProcessEvents(body, card, events, agentId, rangeStart);
            }
            setSubagentCardEventCount(agentId, total);
            if (gotFinal) markSubagentCardCompleted(card, true);
            return;
        }
        var ctx = getSubagentCardStreamCtx(body, card, agentId);
        for (var i = 0; i < events.length; i += 1) {
            if (events[i] && typeof events[i] === 'object') {
                if (summaryOnly && events[i].type !== 'user' && events[i].type !== 'final' && !events[i].ephemeral) continue;
                dispatchSubagentCardEvent(ctx, card, events[i], rangeStart + i, agentId);
            }
        }
        rebindSubagentCardBody(body, card, agentId);
        setSubagentCardEventCount(agentId, total);
        if (gotFinal) markSubagentCardCompleted(card, true);
    } catch (e) { /* ignore */ }
}

async function refreshSubagentContextForCard(card, agentId, force) {
    if (!card || !agentId) return;
    if (!force && !subagentPanelOpen) return;
    if (!force && card.dataset.procCtxEstimated != null && card.dataset.procCtxEstimated !== '') return;
    if (subagentContextFetchInFlight[agentId]) return subagentContextFetchInFlight[agentId];
    subagentContextFetchInFlight[agentId] = (async function () {
        try {
            var r = await fetch('/sessions/' + encodeURIComponent(agentId) + '/context_tokens');
            var j = await r.json();
            if (r.ok && j && j.ok && j.estimated != null && j.estimated >= 0) {
                card.dataset.procCtxEstimated = String(j.estimated);
                card.dataset.procCtxThreshold = String(j.threshold);
                refreshSubagentCardStats(card);
            }
        } catch (e) { /* ignore */ }
        finally {
            delete subagentContextFetchInFlight[agentId];
        }
    })();
    return subagentContextFetchInFlight[agentId];
}

async function refreshSubagentTreePanel(sessionId) {
    if (subagentTreeRefreshInflight && subagentTreeRefreshInflightSid === sessionId) {
        subagentTreeRefreshQueued = true;
        return subagentTreeRefreshInflight;
    }
    subagentTreeRefreshInflightSid = sessionId;
    subagentTreeRefreshInflight = refreshSubagentTreePanelInner(sessionId);
    try {
        return await subagentTreeRefreshInflight;
    } finally {
        subagentTreeRefreshInflight = null;
        subagentTreeRefreshInflightSid = null;
        if (subagentTreeRefreshQueued && sessionId === currentSessionId) {
            subagentTreeRefreshQueued = false;
            void refreshSubagentTreePanel(currentSessionId);
        }
    }
}

async function refreshSubagentTreePanelInner(sessionId) {
    bindSubagentPanelOnce();
    var seq = ++subagentPanelRefreshSeq;
    var grid = document.getElementById('subagent-grid');
    var toggleBtn = document.getElementById('subagent-toggle-btn');
    if (!grid || !sessionId) {
        if (toggleBtn) toggleBtn.classList.add('hidden');
        closeSubagentPanel();
        stopSubagentIncrementalSync();
        return;
    }
    if (grid.dataset.sessionId && grid.dataset.sessionId !== sessionId) {
        grid.innerHTML = '';
        subagentStore.clearEventCounts(sessionId);
    }
    grid.dataset.sessionId = sessionId;
    try {
        var resp = await fetch('/sessions/' + encodeURIComponent(sessionId) + '/subagents?lite=1');
        if (seq !== subagentPanelRefreshSeq || sessionId !== currentSessionId) return;
        var data = await resp.json();
        var flat = (data && data.subagents) ? data.subagents : [];
        applySubagentSnapshot(sessionId, flat);
        flat = selectSubagentList(sessionId);
        if (!flat.length) {
            if (toggleBtn) toggleBtn.classList.add('hidden');
            closeSubagentPanel();
            grid.innerHTML = '';
            grid.dataset.sessionId = sessionId;
            subagentStore.clearEventCounts(sessionId);
            stopSubagentIncrementalSync();
            return;
        }
        refreshSubagentToggleFromGrid(flat);
        syncSubagentGridFromFlat(flat, sessionId);
        if (seq !== subagentPanelRefreshSeq || sessionId !== currentSessionId) return;
        if (subagentPanelOpen) {
            document.getElementById('subagent-dock').classList.remove('hidden');
            ensureSubagentCardViewportObserver(grid);
            grid.querySelectorAll('.subagent-grid-card').forEach(function (card) {
                observeSubagentCardViewport(card);
                if (card.classList.contains('is-expanded')) {
                    scheduleSubagentCardStats(card);
                }
            });
            loadVisibleSubagentCardBodies(grid, sessionId);
            flat.forEach(function (n) {
                if (!n || !n.id) return;
                var card = grid.querySelector('.subagent-grid-card[data-agent-id="' + String(n.id || '') + '"]');
                if (card && card.classList.contains('is-expanded')) {
                    refreshSubagentContextForCard(card, String(n.id || ''), true);
                }
            });
        }
        var runningN = selectSubagentRunningCount(sessionId);
        if (runningN > 0 && subagentPanelOpen) scheduleSubagentIncrementalSync();
        else {
            stopSubagentIncrementalSync();
            if (sessionId === currentSessionId) updateSubagentContinueBanner(sessionId);
        }
    } catch (e) {
        if (toggleBtn) toggleBtn.classList.add('hidden');
        closeSubagentPanel();
        stopSubagentIncrementalSync();
    }
}
