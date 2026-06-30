function formatTokenCompact(n) {
    if (n == null || !Number.isFinite(Number(n))) return '—';
    const x = Math.max(0, Math.round(Number(n)));
    if (x >= 1000000) return (x / 1000000).toFixed(1).replace(/\.0$/, '') + 'M';
    if (x >= 10000) return (x / 1000).toFixed(x % 1000 === 0 ? 0 : 1).replace(/\.0$/, '') + 'k';
    if (x >= 1000) return (x / 1000).toFixed(1).replace(/\.0$/, '') + 'k';
    return String(x);
}

function setContextTokenLabel(estimated, threshold) {
    const el = document.getElementById('ctx-tokens');
    if (!el) return;
    const label = el.querySelector('.ctx-label');
    const fill = el.querySelector('.ctx-fill');
    const pctEl = el.querySelector('.ctx-pct');
    const t = (threshold != null && Number(threshold) > 0) ? Number(threshold) : defaultCtxThreshold;
    const n = (estimated != null && Number(estimated) >= 0) ? Math.round(Number(estimated)) : null;
    if (n == null) {
        if (label) label.textContent = '— / —';
        if (pctEl) pctEl.textContent = '';
        if (fill) fill.style.width = '0%';
        el.classList.remove('is-warn', 'is-bad');
        el.setAttribute('data-ui-tip', '预估上下文 token：选择会话并加载或发送消息后显示。分母为压缩摘要阈值。');
        bindUiHoverTip(el);
        return;
    }
    const pct = (n / t) * 100;
    const pctDisp = (Math.round(pct * 10) / 10);
    if (label) label.textContent = formatTokenCompact(n) + ' / ' + formatTokenCompact(t);
    if (pctEl) pctEl.textContent = pctDisp + '%';
    if (fill) fill.style.width = Math.min(100, pct) + '%';
    el.classList.remove('is-warn', 'is-bad');
    if (pct >= 100) el.classList.add('is-bad');
    else if (pct >= 80) el.classList.add('is-warn');
    var tipPct = pct >= 100
        ? ('约 ' + pctDisp + '%，超出门限 ' + (Math.round((pct - 100) * 10) / 10) + '%')
        : ('约 ' + pctDisp + '%');
    el.setAttribute(
        'data-ui-tip',
        formatTokenCompact(n) + ' / ' + formatTokenCompact(t) + ' tokens（' + tipPct
            + '）。预估进入模型的上下文规模，含历史与系统提示；分母为触发压缩摘要的门限，可在.env文件中 CONTEXT_WINDOW 修改。'
    );
    bindUiHoverTip(el);
}

let contextTokenRequestSeq = 0;
const contextTokenInFlightBySession = Object.create(null);
const CONTEXT_TOKEN_CACHE_TTL_MS = 3000;

async function refreshContextTokensFromServer(sid, seq) {
    if (!sid) return;
    const cached = selectContextTokens(sid);
    if (cached && cached.updatedAt && (Date.now() - cached.updatedAt) < CONTEXT_TOKEN_CACHE_TTL_MS) {
        if (sid === currentSessionId) setContextTokenLabel(cached.estimated, cached.threshold);
        return;
    }
    if (contextTokenInFlightBySession[sid]) return;
    contextTokenInFlightBySession[sid] = true;
    try {
        const r = await fetch('/sessions/' + encodeURIComponent(sid) + '/context_tokens');
        const j = await r.json();
        if (seq != null && seq !== contextTokenRequestSeq) return;
        if (sid !== currentSessionId) return;
        if (r.ok && j && j.ok && j.estimated != null && j.estimated >= 0) {
            recordContextTokens(sid, j.estimated, j.threshold);
            return;
        }
    } catch (e) { /* ignore */ }
    finally {
        delete contextTokenInFlightBySession[sid];
    }
    applyContextTokenLabelForCurrentSession();
}

/** 在浏览器完成首帧绘制后再请求 context_tokens，避免与切换会话/新建会话的 DOM 抢主线程。 */
function scheduleContextTokensAfterPaint(sid) {
    if (!sid) return;
    if (sid === currentSessionId) applyContextTokenLabelForCurrentSession();
    const seq = ++contextTokenRequestSeq;
    requestAnimationFrame(function () {
        requestAnimationFrame(function () {
            refreshContextTokensFromServer(sid, seq);
        });
    });
}

function recordContextTokens(sessionId, estimated, threshold) {
    if (!sessionId) return;
    setContextTokensForSession(sessionId, estimated, threshold);
    if (sessionId === currentSessionId) setContextTokenLabel(estimated, threshold);
}

function applyContextTokenLabelForCurrentSession() {
    if (!currentSessionId) { setContextTokenLabel(null, null); return; }
    const x = selectContextTokens(currentSessionId);
    if (x) setContextTokenLabel(x.estimated, x.threshold);
    else setContextTokenLabel(null, null);
}

/** 主对话区跟到底 */
function scrollChatToBottomIfFollow(runSessionId, opts) {
    opts = opts || {};
    if (shouldGateScrollByRunSession(null, runSessionId)) return;
    if (!opts.force && !liveAutoFollow) return;
    if (chatContainer) chatContainer.scrollTop = chatContainer.scrollHeight;
}

function setScrollTopImmediate(el, y) {
    if (!el) return;
    var prev = el.style.scrollBehavior;
    el.style.scrollBehavior = 'auto';
    el.scrollTop = y;
    requestAnimationFrame(function () {
        if (el) el.style.scrollBehavior = prev;
    });
}

/** 当前运行会话对应的执行过程框滚动容器（.process-aggregate-body） */
function getProcessBodyElForCurrentRun() {
    var sid = currentSessionId;
    var run = sid && getSessionRunState(sid);
    if (!run || !run.ctx) return null;
    var c = run.ctx;
    if (c.currentProcessGroup && c.currentProcessGroup.isConnected) {
        return c.currentProcessGroup.querySelector('.process-aggregate-body');
    }
    if (!c.stream) return null;
    var agg = c.stream.querySelector('.process-aggregate:last-of-type');
    return agg ? agg.querySelector('.process-aggregate-body') : null;
}

var STREAM_PROC_NEAR_BOTTOM_PX = 96;
var STREAM_CHAT_NEAR_BOTTOM_PX = 72;

/** 生成中时：对话区与当前执行过程区均在底部附近时才允许自动跟随流式滚动 */
function refreshLiveAutoFollowPins() {
    if (!chatContainer) return;
    if (isSessionRunning(currentSessionId)) {
        streamChatNearBottom = isNearBottom(chatContainer, STREAM_CHAT_NEAR_BOTTOM_PX);
        var pb = getProcessBodyElForCurrentRun();
        streamProcNearBottom = !pb || isNearBottom(pb, STREAM_PROC_NEAR_BOTTOM_PX);
        liveAutoFollow = streamChatNearBottom && streamProcNearBottom;
    } else {
        liveAutoFollow = isNearBottom(chatContainer, STREAM_CHAT_NEAR_BOTTOM_PX);
    }
}

function isSubagentStreamCtx(ctx) {
    if (!ctx) return false;
    if (ctx._subagentBody && ctx._subagentBody.isConnected) return true;
    if (ctx.currentProcessGroup && ctx.currentProcessGroup.isConnected
        && ctx.currentProcessGroup.classList.contains('subagent-grid-card')) return true;
    return false;
}

/** 子 agent 卡片流式更新用 agentId 作 runSessionId，不能按主会话 currentSessionId 拦截滚动 */
function shouldGateScrollByRunSession(ctx, runSessionId) {
    if (!runSessionId) return false;
    if (isSubagentStreamCtx(ctx)) return false;
    return runSessionId !== currentSessionId;
}

function collectFeedChunkRootsFromCtx(ctx) {
    var roots = [];
    var seen = new Set();
    function addRoot(root) {
        if (!root || !root.isConnected || seen.has(root)) return;
        seen.add(root);
        roots.push(root);
    }
    if (ctx && ctx.stream && ctx.stream.isConnected) addRoot(ctx.stream);
    if (ctx && ctx._subagentTurnProcess) addRoot(ctx._subagentTurnProcess);
    if (ctx && ctx._subagentBody) addRoot(ctx._subagentBody);
    return roots;
}

function queryFeedChunksInCtx(ctx, selector) {
    var sel = selector || '.feed-chunk';
    var out = [];
    var seen = new Set();
    collectFeedChunkRootsFromCtx(ctx).forEach(function (root) {
        root.querySelectorAll(sel).forEach(function (ch) {
            if (!seen.has(ch)) {
                seen.add(ch);
                out.push(ch);
            }
        });
    });
    return out;
}

function refreshFeedChunksInCtx(ctx, selector) {
    queryFeedChunksInCtx(ctx, selector).forEach(function (ch) {
        scheduleFeedChunkOverflowRefresh(ch);
    });
}

function ensureSubagentTurnProcessOpen(ctx) {
    /* 默认折叠执行过程，不在自动滚动时强制展开 */
}

function shouldDeferSubagentProcessDom(ctx) {
    if (!ctx || !ctx.currentTurn || !ctx.currentTurn.isConnected) return true;
    return !ctx.currentTurn.classList.contains('is-process-open');
}

function deferSubagentProcessEvent(turn, event, eventIndex) {
    if (!turn || !event) return;
    if (!turn._deferredProcessEvents) turn._deferredProcessEvents = [];
    turn._deferredProcessEvents.push({ event: event, eventIndex: eventIndex });
    turn.dataset.processDeferred = '1';
}

function pinSubagentCardScrollForManualExpand(body) {
    if (!body) return { savedScroll: 0, release: function () {} };
    var ctx = body._subagentStreamCtx;
    var savedScroll = body.scrollTop;
    if (ctx) ctx._suppressSubagentScrollFollow = true;
    return {
        savedScroll: savedScroll,
        release: function () {
            if (ctx) ctx._suppressSubagentScrollFollow = false;
        },
        restoreScroll: function () {
            if (body.isConnected) body.scrollTop = savedScroll;
        }
    };
}

function restoreSubagentCardScrollAfterLayout(body, savedScroll) {
    if (!body) return;
    requestAnimationFrame(function () {
        requestAnimationFrame(function () {
            if (body.isConnected) body.scrollTop = savedScroll;
        });
    });
}

var SUBAGENT_PROCESS_HYDRATE_BATCH = 24;
var SUBAGENT_PROCESS_REFRESH_CHUNK_LIMIT = 80;

function runSubagentProcessBatch(fn) {
    if (typeof requestIdleCallback === 'function') {
        requestIdleCallback(fn, { timeout: 120 });
    } else {
        requestAnimationFrame(fn);
    }
}

function refreshSubagentProcessChunksLightly(turn) {
    if (!turn || !turn.querySelectorAll) return;
    var chunks = turn.querySelectorAll('.feed-chunk');
    var limit = Math.min(chunks.length, SUBAGENT_PROCESS_REFRESH_CHUNK_LIMIT);
    for (var i = 0; i < limit; i += 1) {
        scheduleFeedChunkOverflowRefresh(chunks[i]);
    }
}

function hydrateSubagentTurnProcess(turn, ctx, agentId) {
    if (!turn || !ctx) return;
    var processEl = turn.querySelector('.subagent-turn-process');
    if (turn.dataset.processHydrated === '1' && processEl && processEl.children.length) return;
    var items = turn._deferredProcessEvents;
    if (!items || !items.length) {
        turn.dataset.processHydrated = '1';
        return;
    }
    var body = ctx._subagentBody;
    var pin = pinSubagentCardScrollForManualExpand(body);
    ctx.currentTurn = turn;
    ctx._subagentTurnProcess = processEl;
    ctx._subagentTurnFinalSlot = turn.querySelector('.subagent-turn-final-slot');
    resetLlmState(ctx);
    finalizeProgressStreamChunks(ctx);
    function replayDeferredProcessEvent(item) {
        var ev = item && item.event;
        if (!ev || typeof ev !== 'object') return;
        if (shouldSkipSubagentProcessEvent(ev)) return;
        if (ev.ephemeral) {
            if (ev.type === 'llm_reasoning_delta' || ev.type === 'llm_response_delta') {
                appendLlmStreamDelta(ctx, ev, agentId);
            } else if (ev.type === 'context_summary_delta') {
                appendProgressStreamDelta(ctx, ev.delta, 'context-summary', agentId);
            } else if (ev.type === 'key_context_delta') {
                appendKeyContextStreamDelta(ctx, ev.delta, agentId);
            } else if (ev.type === 'context_tokens' || ev.type === 'process_metrics' || ev.type === 'cache_stats') {
                /* metrics 类事件只更新卡片统计，不在展开过程里落一条“信息”。 */
            }
            return;
        }
        reduceAndRenderMessageEvent(ctx, ev, {
            sessionId: agentId,
            eventIndex: item.eventIndex,
            source: 'subagent-history',
        });
    }
    var index = 0;
    turn.dataset.processLoading = '1';
    function finishHydrate() {
        finalizeLlmStreamChunks(ctx);
        finalizeProgressStreamChunks(ctx);
        delete turn._deferredProcessEvents;
        delete turn.dataset.processDeferred;
        delete turn.dataset.processLoading;
        turn.dataset.processHydrated = '1';
        markSubagentTurnHasProcess(turn);
        refreshSubagentProcessChunksLightly(turn);
        pin.release();
        restoreSubagentCardScrollAfterLayout(body, pin.savedScroll);
    }
    function step() {
        if (!turn.isConnected || !body || !body.isConnected) {
            delete turn.dataset.processLoading;
            pin.release();
            return;
        }
        var end = Math.min(index + SUBAGENT_PROCESS_HYDRATE_BATCH, items.length);
        for (; index < end; index += 1) {
            replayDeferredProcessEvent(items[index]);
        }
        if (index < items.length) {
            runSubagentProcessBatch(step);
        } else {
            finishHydrate();
        }
    }
    step();
}

function repairMisplacedSubagentFeedItems(body, turn) {
    if (!body || !turn) return;
    var proc = turn.querySelector('.subagent-turn-process');
    if (!proc) return;
    Array.prototype.slice.call(body.children).forEach(function (node) {
        if (!node || !node.classList || !node.classList.contains('feed-item')) return;
        proc.appendChild(node);
    });
}

function collectSubagentTurnProcessSlice(events, userEventIndex) {
    var slice = [];
    if (!events || !events.length || !Number.isFinite(userEventIndex) || userEventIndex < 0) return slice;
    for (var i = userEventIndex + 1; i < events.length; i += 1) {
        var ev = events[i];
        if (!ev || typeof ev !== 'object') continue;
        var t = ev.type;
        if (t === 'user') break;
        if (t === 'final') break;
        if (t === 'subagent_start' || t === 'subagent_finish') continue;
        if (shouldSkipSubagentProcessEvent(ev)) continue;
        slice.push({ event: ev, eventIndex: i });
    }
    return slice;
}

async function fetchAndHydrateSubagentTurnProcess(turn, body) {
    if (!turn || !body || turn.dataset.processLoading === '1' || turn.dataset.processFetching === '1') return;
    var card = body.closest('.subagent-grid-card');
    var agentId = (card && card.getAttribute('data-agent-id')) || body.getAttribute('data-agent-id') || '';
    if (!agentId) return;
    var userWrap = turn.querySelector('.msg-wrap--user');
    var userIdx = userWrap ? parseInt(userWrap.getAttribute('data-event-index') || '-1', 10) : -1;
    if (!Number.isFinite(userIdx) || userIdx < 0) return;
    var pin = pinSubagentCardScrollForManualExpand(body);
    turn.dataset.processFetching = '1';
    try {
        var resp = await fetch('/sessions/' + encodeURIComponent(agentId) + '/messages');
        if (!resp.ok) return;
        var events = normalizeSubagentMessagesPayload(await resp.json());
        if (!turn.isConnected) return;
        turn._deferredProcessEvents = collectSubagentTurnProcessSlice(events, userIdx);
        delete turn.dataset.processHydrated;
        hydrateSubagentTurnProcessFromEl(turn, body);
    } catch (e) { /* ignore */ }
    finally {
        delete turn.dataset.processFetching;
        pin.release();
        restoreSubagentCardScrollAfterLayout(body, pin.savedScroll);
    }
}

function ensureSubagentTurnProcessContent(turn, body) {
    if (!turn || !body) return;
    repairMisplacedSubagentFeedItems(body, turn);
    var processEl = turn.querySelector('.subagent-turn-process');
    if (processEl && processEl.children.length) return;
    if (turn._deferredProcessEvents && turn._deferredProcessEvents.length) {
        hydrateSubagentTurnProcessFromEl(turn, body);
        return;
    }
    if (turn.dataset.processDeferred === '1' || turn.querySelector('.msg-wrap--user.has-turn-process')) {
        void fetchAndHydrateSubagentTurnProcess(turn, body);
    }
}

function toggleSubagentTurnProcess(turn, body, userWrap) {
    if (!turn || !body || !userWrap) return;
    var open = !turn.classList.contains('is-process-open');
    turn.classList.toggle('is-process-open', open);
    userWrap.classList.toggle('is-process-open', open);
    delete body.dataset.cacheClean;
    if (open) {
        ensureSubagentTurnProcessContent(turn, body);
        refreshSubagentProcessChunksLightly(turn);
        return;
    }
}

function hydrateSubagentTurnProcessFromEl(turn, body) {
    if (!turn || !body) return;
    var card = body.closest('.subagent-grid-card');
    var agentId = (card && card.getAttribute('data-agent-id')) || body.getAttribute('data-agent-id') || '';
    var ctx = body._subagentStreamCtx || (agentId && card ? getSubagentCardStreamCtx(body, card, agentId) : null);
    if (ctx && agentId) hydrateSubagentTurnProcess(turn, ctx, agentId);
}

function feedChunkCollapsedMax(chunk) {
    var styles = getComputedStyle(chunk);
    var line = parseFloat(styles.getPropertyValue('--line')) || 21.6;
    var pad = parseFloat(styles.getPropertyValue('--scroller-pad-y')) || 4;
    return line * 2.5 + pad * 2;
}

function feedChunkInHiddenSubagentProcess(chunk) {
    var process = chunk.closest('.subagent-turn-process');
    if (!process || !process.children.length) return false;
    var turn = process.closest('.subagent-turn');
    return !!(turn && !turn.classList.contains('is-process-open'));
}

function measureFeedChunkScrollerHeight(sc, chunk) {
    if (!sc) return 0;
    var h = sc.scrollHeight;
    if (h > 1) return h;
    var process = chunk && chunk.closest('.subagent-turn-process');
    var turn = process && process.closest('.subagent-turn');
    if (!process || !turn || turn.classList.contains('is-process-open')) return h;
    var prevDisplay = process.style.display;
    var prevVis = process.style.visibility;
    var prevPos = process.style.position;
    var prevLeft = process.style.left;
    var prevRight = process.style.right;
    var prevPointer = process.style.pointerEvents;
    process.style.display = 'block';
    process.style.visibility = 'hidden';
    process.style.position = 'absolute';
    process.style.left = '0';
    process.style.right = '0';
    process.style.pointerEvents = 'none';
    h = sc.scrollHeight;
    process.style.display = prevDisplay;
    process.style.visibility = prevVis;
    process.style.position = prevPos;
    process.style.left = prevLeft;
    process.style.right = prevRight;
    process.style.pointerEvents = prevPointer;
    return h;
}

function refreshAllFeedChunksUnder(root) {
    if (!root || !root.querySelectorAll) return;
    root.querySelectorAll('.feed-chunk').forEach(scheduleFeedChunkOverflowRefresh);
}

function shouldFollowSubagentCard(ctx) {
    if (!ctx || ctx._suppressSubagentScrollFollow) return false;
    if (!ctx._subagentBody || !ctx._subagentBody.isConnected) return false;
    var aid = ctx._subagentBody.getAttribute('data-agent-id') || '';
    if (aid && subagentCardNearBottom[aid] === false) return false;
    return liveAutoFollow || subagentCardNearBottom[aid] !== false;
}

function bindSubagentCardBodyScrollFollow(body) {
    if (!body || body.dataset.subagentScrollFollowBound) return;
    body.dataset.subagentScrollFollowBound = '1';
    var aid = body.getAttribute('data-agent-id') || ('body-' + Math.random());
    if (subagentCardNearBottom[aid] == null) subagentCardNearBottom[aid] = true;
    body.addEventListener('scroll', function () {
        subagentCardNearBottom[aid] = isNearBottom(body, SUBAGENT_CARD_NEAR_BOTTOM_PX);
    }, { passive: true });
}

function scrollSubagentCardBodyToBottom(ctx) {
    if (!ctx || !ctx._subagentBody || !ctx._subagentBody.isConnected) return;
    var body = ctx._subagentBody;
    var aid = body.getAttribute('data-agent-id') || '';
    if (aid) subagentCardNearBottom[aid] = true;
    requestAnimationFrame(function () {
        body.scrollTop = body.scrollHeight;
        requestAnimationFrame(function () {
            body.scrollTop = body.scrollHeight;
        });
    });
}

function scrollContentAreaIfFollow(ctx, runSessionId) {
    if (shouldGateScrollByRunSession(ctx, runSessionId)) return;
    if (isSubagentStreamCtx(ctx)) {
        if (!shouldFollowSubagentCard(ctx)) return;
        scrollSubagentCardBodyToBottom(ctx);
        return;
    }
    if (!liveAutoFollow) return;
    scrollProcessBodyToBottom(ctx, runSessionId);
    scrollChatToBottomIfFollow(runSessionId, {});
}

/** 将当前轮次的执行框滚到底（流式增量主要长在这里，必须滚 procBody 而不是只滚对话区） */
function scrollProcessBodyToBottom(ctx, runSessionId) {
    if (shouldGateScrollByRunSession(ctx, runSessionId)) return;
    if (isSubagentStreamCtx(ctx)) {
        scrollSubagentCardBodyToBottom(ctx);
        return;
    }
    if (!ctx || !ctx.stream) return;
    var agg = (ctx.currentProcessGroup && ctx.currentProcessGroup.isConnected)
        ? ctx.currentProcessGroup
        : ctx.stream.querySelector('.process-aggregate:last-of-type');
    if (agg) {
        var procBody = agg.querySelector('.process-aggregate-body');
        if (procBody) procBody.scrollTop = procBody.scrollHeight;
    }
}

function followStreamProcessScroll(ctx, runSessionId) {
    if (shouldGateScrollByRunSession(ctx, runSessionId)) return;
    if (isSubagentStreamCtx(ctx)) {
        if (!shouldFollowSubagentCard(ctx)) return;
        if (subagentScrollFollowRaf) return;
        subagentScrollFollowRaf = requestAnimationFrame(function () {
            subagentScrollFollowRaf = 0;
            scrollSubagentCardBodyToBottom(ctx);
            refreshFeedChunksInCtx(ctx, '.feed-chunk.is-streaming');
        });
        return;
    }
    if (!liveAutoFollow) return;
    if (streamScrollFollowRaf) return;
    streamScrollFollowRaf = requestAnimationFrame(function () {
        streamScrollFollowRaf = 0;
        if (!liveAutoFollow) return;
        if (ctx && ctx.currentProcessGroup && ctx.currentProcessGroup.isConnected) {
            if (ctx.currentProcessGroup.classList.contains('is-collapsed')) {
                ctx.currentProcessGroup.classList.remove('is-collapsed');
                const topN = ctx.currentProcessGroup.querySelector('.process-aggregate-top');
                if (topN) topN.setAttribute('aria-expanded', 'true');
            }
        }
        scrollProcessBodyToBottom(ctx, runSessionId);
        scrollChatToBottomIfFollow(runSessionId, {});
        refreshLiveAutoFollowPins();
    });
}

function getVisibleChatStream() { return document.getElementById('chat-stream'); }

function ensureVisibleChatStreamSlot() {
    if (getVisibleChatStream() || !chatContainer) return;
    const ns = document.createElement('div');
    ns.className = 'chat-stream';
    ns.id = 'chat-stream';
    ns.setAttribute('aria-label', '消息');
    chatContainer.appendChild(ns);
}

function emptyChatStreamKeepingStrip(streamEl) {
    if (!streamEl) return;
    const strip = streamEl.querySelector('#history-load-sentinel');
    Array.from(streamEl.children).forEach(function (ch) {
        if (strip && ch === strip) return;
        ch.remove();
    });
}

function persistHistoryPagingToStream(streamEl, paging) {
    if (!streamEl) return;
    if (!paging || paging.sessionId !== currentSessionId) {
        delete streamEl.dataset.historyPaging;
        return;
    }
    streamEl.dataset.historyPaging = JSON.stringify({
        sessionId: paging.sessionId,
        total: Number(paging.total) || 0,
        range_start: Number(paging.range_start) || 0,
        range_end: Number(paging.range_end) || 0,
        has_older: !!paging.has_older,
    });
}

function restoreHistoryPagingFromStream(streamEl) {
    if (!streamEl || !streamEl.dataset.historyPaging) return null;
    try {
        var raw = JSON.parse(streamEl.dataset.historyPaging);
        if (!raw || raw.sessionId !== currentSessionId) return null;
        return {
            sessionId: raw.sessionId,
            total: Number(raw.total) || 0,
            range_start: Number(raw.range_start) || 0,
            range_end: Number(raw.range_end) || 0,
            has_older: !!raw.has_older,
        };
    } catch (_e) {
        delete streamEl.dataset.historyPaging;
        return null;
    }
}

function setSessionHistoryPaging(paging) {
    sessionHistoryPaging = paging || null;
    persistHistoryPagingToStream(getVisibleChatStream(), sessionHistoryPaging);
    updateHistorySentinelVisibility();
}

function ensureHistorySentinel(streamEl) {
    if (!streamEl) return null;
    var el = streamEl.querySelector('#history-load-sentinel');
    if (el) return el;
    el = document.createElement('div');
    el.id = 'history-load-sentinel';
    el.className = 'history-load-sentinel';
    el.hidden = true;
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'history-load-older-btn';
    btn.textContent = '更早 ' + HISTORY_DIALOGUES_PER_PAGE + ' 轮对话';
    btn.addEventListener('click', function () { loadOlderHistoryChunk(); });
    el.appendChild(btn);
    streamEl.insertBefore(el, streamEl.firstChild);
    return el;
}

function getHistoryScrollAnchor(container) {
    if (!container) return null;
    var cr = container.getBoundingClientRect();
    var nodes = container.querySelectorAll('.msg-wrap, .process-aggregate, .welcome');
    for (var i = 0; i < nodes.length; i += 1) {
        var n = nodes[i];
        if (!n || !n.isConnected || n.id === 'chat-loading') continue;
        var r = n.getBoundingClientRect();
        if (r.bottom >= cr.top + 4) return { el: n, top: r.top };
    }
    return null;
}

function updateHistorySentinelVisibility() {
    var strip = document.getElementById('history-load-sentinel');
    var btn = strip && strip.querySelector('.history-load-older-btn');
    var ph = sessionHistoryPaging;
    if (!strip || !btn) return;
    if (!ph || !ph.has_older || ph.sessionId !== currentSessionId) {
        strip.hidden = true;
        btn.disabled = false;
        btn.textContent = '更早 ' + HISTORY_DIALOGUES_PER_PAGE + ' 轮对话';
        return;
    }
    strip.hidden = false;
    btn.disabled = historyOlderLoading;
    btn.textContent = historyOlderLoading ? '加载中…' : ('更早 ' + HISTORY_DIALOGUES_PER_PAGE + ' 轮对话');
}

function resetSessionHistoryPaging() {
    setSessionHistoryPaging(null);
    historyOlderLoading = false;
    updateHistorySentinelVisibility();
}

async function loadOlderHistoryChunk(opts) {
    opts = opts || {};
    var sid = currentSessionId;
    var stream = getVisibleChatStream();
    var ph = sessionHistoryPaging;
    if ((!ph || ph.sessionId !== sid) && stream) {
        ph = restoreHistoryPagingFromStream(stream);
        if (ph) sessionHistoryPaging = ph;
    }
    if (!sid || !ph || ph.sessionId !== sid || !ph.has_older || historyOlderLoading) return;
    historyOlderLoading = true;
    var prevReplaying = replayingMessages;
    replayingMessages = true;
    updateHistorySentinelVisibility();
    var cc = chatContainer;
    var prevScrollTop = cc ? cc.scrollTop : 0;
    var anchor = getHistoryScrollAnchor(cc);
    var loadedOlder = false;
    try {
        var pageTurns = Math.max(1, Math.min(Number(opts.turns) || HISTORY_DIALOGUES_PER_PAGE, 50));
        var url = '/sessions/' + encodeURIComponent(sid) + '/messages?turns=' + encodeURIComponent(String(pageTurns)) + '&before_index=' + ph.range_start;
        var response = await fetch(url);
        var data = await response.json();
        if (!response.ok || !data || typeof data !== 'object') return;
        var events = data.events;
        if (!Array.isArray(events) || events.length === 0) {
            setSessionHistoryPaging(Object.assign({}, ph, { has_older: !!data.has_older }));
            return;
        }
        ensureHistorySentinel(stream);
        var frag = document.createDocumentFragment();
        var tmpCtx = newDomContext(frag);
        tmpCtx.lastUserEventIndex = -1;
        var rs = typeof data.range_start === 'number' ? data.range_start : 0;
        for (var i = 0; i < events.length; i += 1) {
            var ev = events[i];
            if (ev && typeof ev === 'object' && ev.type) {
                reduceAndRenderMessageEvent(tmpCtx, ev, {
                    sessionId: sid,
                    eventIndex: rs + i,
                    source: 'history-older',
                });
            }
        }
        var sen = stream && stream.querySelector('#history-load-sentinel');
        if (stream && frag.childNodes.length) {
            stream.insertBefore(frag, sen ? sen.nextSibling : stream.firstChild);
        }
        loadedOlder = true;
        setSessionHistoryPaging({
            sessionId: sid,
            total: typeof data.total === 'number' ? data.total : ph.total,
            range_start: typeof data.range_start === 'number' ? data.range_start : ph.range_start,
            range_end: ph.range_end,
            has_older: !!data.has_older,
        });
    } catch (e) {
        console.error('加载更早消息失败:', e);
    } finally {
        historyOlderLoading = false;
        updateHistorySentinelVisibility();
        if (cc && stream && stream.parentNode === cc) {
            if (anchor && anchor.el && anchor.el.isConnected) {
                var nextTop = anchor.el.getBoundingClientRect().top;
                setScrollTopImmediate(cc, cc.scrollTop + (nextTop - anchor.top));
            } else {
                setScrollTopImmediate(cc, prevScrollTop);
            }
        }
        if (loadedOlder) {
            bindExistingLogs(stream);
            if (!opts.keepTocStable) rebuildToc();
            scheduleTocActiveUpdate();
        }
        replayingMessages = prevReplaying;
    }
}

function insertNewEmptyChatStream() { ensureVisibleChatStreamSlot(); }

const SESSION_STREAM_CACHE_LIMIT = 6;
const cachedSessionStreamOrder = [];

function cssEscapeIdent(value) {
    if (window.CSS && typeof window.CSS.escape === 'function') return window.CSS.escape(value);
    return String(value || '').replace(/["\\]/g, '\\$&');
}

function cacheOrderTouch(sessionId) {
    var sid = String(sessionId || '');
    if (!sid) return;
    var idx = cachedSessionStreamOrder.indexOf(sid);
    if (idx >= 0) cachedSessionStreamOrder.splice(idx, 1);
    cachedSessionStreamOrder.push(sid);
}

function discardCachedSessionStream(sessionId) {
    var sid = String(sessionId || '');
    if (!sid || !offscreenRoot) return;
    var cached = offscreenRoot.querySelector('.chat-stream[data-cache-session-id="' + cssEscapeIdent(sid) + '"]');
    if (cached && cached.parentNode) cached.remove();
    var idx = cachedSessionStreamOrder.indexOf(sid);
    if (idx >= 0) cachedSessionStreamOrder.splice(idx, 1);
}

function trimCachedSessionStreams() {
    if (!offscreenRoot) return;
    while (cachedSessionStreamOrder.length > SESSION_STREAM_CACHE_LIMIT) {
        var sid = cachedSessionStreamOrder.shift();
        var cached = offscreenRoot.querySelector('.chat-stream[data-cache-session-id="' + cssEscapeIdent(sid) + '"]');
        if (cached && cached.parentNode) cached.remove();
    }
}

function stashVisibleStreamForSession(sessionId, opts) {
    opts = opts || {};
    var sid = String(sessionId || '');
    if (!sid || !offscreenRoot) return false;
    const el = getVisibleChatStream();
    if (!el || !el.parentNode) return false;
    if (!opts.force && el.dataset.sessionLoadOk !== '1') return false;
    if (el.dataset.sessionLoadFailed === '1') return false;
    discardCachedSessionStream(sid);
    el.remove();
    el.removeAttribute('id');
    el.removeAttribute('aria-label');
    el.classList.add('is-offscreen');
    el.setAttribute('data-cache-session-id', sid);
    offscreenRoot.appendChild(el);
    cacheOrderTouch(sid);
    trimCachedSessionStreams();
    return true;
}

function prepareStashLeaving(leavingId) {
    if (!leavingId) return;
    if (isSessionRunning(leavingId)) {
        stashVisibleStreamForSession(leavingId, { force: true });
        insertNewEmptyChatStream();
    } else {
        if (!stashVisibleStreamForSession(leavingId)) ensureVisibleChatStreamSlot();
        insertNewEmptyChatStream();
    }
}

function restoreStreamForRunningSession(enteringId) {
    const run = getSessionRunState(enteringId);
    if (!run || !run.ctx || !run.ctx.stream) return false;
    const st = run.ctx.stream;
    if (!st.parentNode) return false;
    if (st.parentNode === chatContainer) return st.id === 'chat-stream';
    if (offscreenRoot && st.parentNode !== offscreenRoot) return false;
    const cur = getVisibleChatStream();
    if (cur && cur.parentNode === chatContainer) cur.remove();
    st.classList.remove('is-offscreen');
    st.removeAttribute('data-cache-session-id');
    st.id = 'chat-stream';
    st.setAttribute('aria-label', '消息');
    chatContainer.appendChild(st);
    cacheOrderTouch(enteringId);
    var restoredPaging = restoreHistoryPagingFromStream(st);
    if (restoredPaging) sessionHistoryPaging = restoredPaging;
    updateHistorySentinelVisibility();
    bindExistingLogs(st);
    return true;
}

function restoreCachedSessionStream(enteringId) {
    var sid = String(enteringId || '');
    if (!sid || !offscreenRoot) return false;
    var st = offscreenRoot.querySelector('.chat-stream[data-cache-session-id="' + cssEscapeIdent(sid) + '"]');
    if (!st || !st.parentNode) return false;
    if (st.dataset.sessionLoadOk !== '1' || st.dataset.sessionLoadFailed === '1') {
        discardCachedSessionStream(sid);
        return false;
    }
    const cur = getVisibleChatStream();
    if (cur && cur.parentNode === chatContainer) cur.remove();
    st.classList.remove('is-offscreen');
    st.removeAttribute('data-cache-session-id');
    st.id = 'chat-stream';
    st.setAttribute('aria-label', '消息');
    chatContainer.appendChild(st);
    cacheOrderTouch(sid);
    var restoredPaging = restoreHistoryPagingFromStream(st);
    if (restoredPaging) sessionHistoryPaging = restoredPaging;
    updateHistorySentinelVisibility();
    bindExistingLogs(st);
    return true;
}

function restoreCachedSessionScrollPosition(sessionId) {
    if (!chatContainer || !sessionId) return;
    requestAnimationFrame(function () {
        if (sessionId !== currentSessionId) return;
        var saved = (typeof getSavedScrollPosition === 'function') ? getSavedScrollPosition(sessionId) : null;
        if (saved !== null && Number.isFinite(Number(saved)) && Number(saved) > 0) {
            setScrollTopImmediate(chatContainer, Number(saved));
        } else {
            chatContainer.scrollTop = chatContainer.scrollHeight;
        }
        refreshLiveAutoFollowPins();
        scheduleTocActiveUpdate();
    });
}

function markVisibleSessionStreamLoadState(sessionId, state) {
    var stream = getVisibleChatStream();
    if (!stream) return;
    stream.dataset.sessionId = String(sessionId || '');
    if (state === 'ok') {
        stream.dataset.sessionLoadOk = '1';
        delete stream.dataset.sessionLoadFailed;
        delete stream.dataset.sessionLoading;
    } else if (state === 'failed') {
        stream.dataset.sessionLoadFailed = '1';
        delete stream.dataset.sessionLoadOk;
        delete stream.dataset.sessionLoading;
        discardCachedSessionStream(sessionId);
    } else if (state === 'loading') {
        stream.dataset.sessionLoading = '1';
        delete stream.dataset.sessionLoadOk;
        delete stream.dataset.sessionLoadFailed;
    }
}

function appendLogVisible(msg, type) {
    if (!getVisibleChatStream()) ensureVisibleChatStreamSlot();
    const c = newDomContext(getVisibleChatStream());
    appendLog(c, msg, type, currentSessionId);
}

function newLlmState() {
    return {
        llmStreamReasoningIter: null,
        llmStreamResponseIter: null,
        llmStreamReasoningScroller: null,
        llmStreamResponseScroller: null,
        llmDeltaLastSeq: null,
        llmPendingReasoningDelta: '',
        llmPendingResponseDelta: '',
        llmDeltaFlushRaf: 0,
    };
}

function newDomContext(streamEl) {
    return {
        stream: streamEl,
        currentProcessGroup: null,
        lastUserEventIndex: -1,
        progressScrollers: {},
        progressStream: {},
        keyContextStreamFilter: { phase: 'seek', carry: '' },
        runStartedAt: null,
        _seenStreamDeltaKeys: new Set(),
        llm: newLlmState(),
    };
}

function resetKeyContextStreamFilter(ctx) {
    if (ctx) ctx.keyContextStreamFilter = { phase: 'seek', carry: '' };
}

/** 要点流式输出：隐藏 <analysis>…</analysis>，仅展示 <summary> 内正文 */
function extractKeyContextVisibleDelta(filter, delta) {
    if (!filter) return String(delta || '');
    filter.carry += String(delta || '');
    var out = '';
    var tagTail = 24;
    while (filter.carry.length > 0) {
        var lower = filter.carry.toLowerCase();
        if (filter.phase === 'seek') {
            var ai = lower.indexOf('<analysis');
            var si = lower.indexOf('<summary');
            if (ai >= 0 && (si < 0 || ai < si)) {
                if (ai > 0) out += filter.carry.slice(0, ai);
                filter.carry = filter.carry.slice(ai);
                filter.phase = 'in_analysis';
                continue;
            }
            if (si >= 0) {
                if (si > 0) out += filter.carry.slice(0, si);
                filter.carry = filter.carry.slice(si);
                filter.phase = 'in_summary';
                continue;
            }
            if (filter.carry.length > tagTail) {
                var safe = filter.carry.length - tagTail;
                out += filter.carry.slice(0, safe);
                filter.carry = filter.carry.slice(safe);
            }
            break;
        }
        if (filter.phase === 'in_analysis') {
            var ae = lower.indexOf('</analysis>');
            if (ae >= 0) {
                var aClose = filter.carry.slice(ae).match(/^<\/analysis\s*>/i);
                var aLen = aClose ? aClose[0].length : 11;
                filter.carry = filter.carry.slice(ae + aLen);
                filter.phase = 'seek';
                continue;
            }
            filter.carry = '';
            break;
        }
        if (filter.phase === 'in_summary') {
            var se = lower.indexOf('</summary>');
            var chunk = se >= 0 ? filter.carry.slice(0, se) : filter.carry;
            chunk = chunk.replace(/^<summary[^>]*>\s*/i, '');
            out += chunk;
            if (se >= 0) {
                var sClose = filter.carry.slice(se).match(/^<\/summary\s*>/i);
                var sLen = sClose ? sClose[0].length : 10;
                filter.carry = filter.carry.slice(se + sLen);
                filter.phase = 'done';
            } else {
                filter.carry = '';
            }
            break;
        }
        if (filter.phase === 'done') {
            filter.carry = '';
            break;
        }
        break;
    }
    return out;
}

function appendKeyContextStreamDelta(ctx, delta, runSessionId) {
    if (!ctx || !delta) return;
    if (!ctx.keyContextStreamFilter) resetKeyContextStreamFilter(ctx);
    var vis = extractKeyContextVisibleDelta(ctx.keyContextStreamFilter, delta);
    if (vis) appendProgressStreamDelta(ctx, vis, 'key-context', runSessionId);
}

function isSessionRunning(sessionId) {
    return selectIsSessionRunning(sessionId);
}

function syncDisconnectedProcessGroups() {
    sessionStore.runsBySession.forEach(function (run, sid) {
        const c = run && run.ctx;
        if (c && c.currentProcessGroup && !c.currentProcessGroup.isConnected) c.currentProcessGroup = null;
    });
}

function finalizeLlmStreamChunks(ctx) {
    if (!ctx) return;
    flushLlmDeltaText(ctx);
    queryFeedChunksInCtx(ctx, '.feed-chunk.is-streaming').forEach(function (ch) {
        ch.classList.remove('is-streaming');
        scheduleFeedChunkOverflowRefresh(ch);
    });
    if (ctx.llm) {
        const l = ctx.llm;
        l.llmStreamReasoningIter = null;
        l.llmStreamResponseIter = null;
        l.llmStreamReasoningScroller = null;
        l.llmStreamResponseScroller = null;
        l.llmDeltaLastSeq = null;
    }
    var bodies = [];
    if (ctx.currentProcessGroup && !isSubagentStreamCtx(ctx)) {
        var mainBody = ctx.currentProcessGroup.querySelector('.process-aggregate-body');
        if (mainBody) bodies.push(mainBody);
    }
    if (ctx._subagentTurnProcess && ctx._subagentTurnProcess.isConnected) {
        bodies.push(ctx._subagentTurnProcess);
    }
    bodies.forEach(function (body) {
        body.querySelectorAll('.feed-item.feed--llm, .feed-item.feed--llm2').forEach(function (el) {
            var sc = el.querySelector('.feed-chunk-scroller');
            var ch = el.querySelector('.feed-chunk');
            if (sc) {
                var norm = trimSurroundingBlankLines(sc.textContent || '');
                sc.textContent = truncateLogTextForUi(norm);
                if (ch) {
                    refreshFeedChunkOverflow(ch);
                    requestAnimationFrame(function () { refreshFeedChunkOverflow(ch); });
                }
            }
            if (!getFeedItemText(el).trim()) el.remove();
        });
    });
}

function discardLlmStreamChunks(ctx, ev) {
    if (!ctx) return;
    if (ctx.llm) {
        const l = ctx.llm;
        if (l.llmDeltaFlushRaf) {
            cancelAnimationFrame(l.llmDeltaFlushRaf);
            l.llmDeltaFlushRaf = 0;
        }
        l.llmPendingReasoningDelta = '';
        l.llmPendingResponseDelta = '';
        l.llmStreamReasoningIter = null;
        l.llmStreamResponseIter = null;
        l.llmStreamReasoningScroller = null;
        l.llmStreamResponseScroller = null;
        l.llmDeltaLastSeq = null;
    }
    var bodies = [];
    if (ctx.currentProcessGroup && !isSubagentStreamCtx(ctx)) {
        var mainBody = ctx.currentProcessGroup.querySelector('.process-aggregate-body');
        if (mainBody) bodies.push(mainBody);
    }
    if (ctx._subagentTurnProcess && ctx._subagentTurnProcess.isConnected) {
        bodies.push(ctx._subagentTurnProcess);
    }
    var reactIter = ev && ev.react_iter != null && Number.isFinite(Number(ev.react_iter))
        ? String(Math.max(1, Math.floor(Number(ev.react_iter))))
        : '';
    bodies.forEach(function (body) {
        body.querySelectorAll('.feed-item.feed--llm, .feed-item.feed--llm2').forEach(function (el) {
            var ch = el.querySelector('.feed-chunk');
            if (ch && ch.classList.contains('is-streaming')) el.remove();
        });
        body.querySelectorAll('.feed-item.feed--tool[data-tool-pending="1"]').forEach(function (el) {
            el.remove();
        });
        if (reactIter) {
            var sel = '.feed-item[data-react-iter="' + reactIter + '"]';
            body.querySelectorAll(sel).forEach(function (el) {
                if (
                    el.classList.contains('feed--tool')
                    || el.classList.contains('feed--llm')
                    || el.classList.contains('feed--llm2')
                ) {
                    el.remove();
                }
            });
        }
    });
}

function flushLlmDeltaText(ctx) {
    if (!ctx || !ctx.llm) return;
    const l = ctx.llm;
    if (l.llmDeltaFlushRaf) {
        cancelAnimationFrame(l.llmDeltaFlushRaf);
        l.llmDeltaFlushRaf = 0;
    }
    if (l.llmPendingReasoningDelta && l.llmStreamReasoningScroller) {
        var rs = trimSurroundingBlankLines((l.llmStreamReasoningScroller.textContent || '') + l.llmPendingReasoningDelta);
        l.llmStreamReasoningScroller.textContent = truncateLogTextForUi(rs);
    }
    l.llmPendingReasoningDelta = '';
    if (l.llmPendingResponseDelta && l.llmStreamResponseScroller) {
        var rsp = trimSurroundingBlankLines((l.llmStreamResponseScroller.textContent || '') + l.llmPendingResponseDelta);
        l.llmStreamResponseScroller.textContent = truncateLogTextForUi(rsp);
    }
    l.llmPendingResponseDelta = '';
}

function scheduleLlmDeltaFlush(ctx, runSessionId) {
    const l = ctx.llm;
    if (!l || l.llmDeltaFlushRaf) return;
    l.llmDeltaFlushRaf = requestAnimationFrame(function () {
        l.llmDeltaFlushRaf = 0;
        flushLlmDeltaText(ctx);
        followStreamProcessScroll(ctx, runSessionId);
    });
}

function resetLlmState(ctx) {
    if (!ctx || !ctx.llm) return;
    flushLlmDeltaText(ctx);
    const l = ctx.llm;
    l.llmStreamReasoningIter = null;
    l.llmStreamResponseIter = null;
    l.llmStreamReasoningScroller = null;
    l.llmStreamResponseScroller = null;
    l.llmDeltaLastSeq = null;
}

function showCopyFeedback() {
    const t = document.getElementById('copy-toast');
    if (!t) return;
    t.classList.add('is-on');
    if (t._copyTm) clearTimeout(t._copyTm);
    t._copyTm = setTimeout(function () { t.classList.remove('is-on'); }, 1500);
}

function showOpenFileFeedback(msg) {
    var t = document.getElementById('copy-toast');
    if (!t) return;
    var prev = t.getAttribute('data-default-msg') || t.textContent || '已复制';
    if (!t.getAttribute('data-default-msg')) t.setAttribute('data-default-msg', prev);
    t.textContent = msg || '已请求打开';
    t.classList.add('is-on');
    if (t._openFileTm) clearTimeout(t._openFileTm);
    t._openFileTm = setTimeout(function () {
        t.classList.remove('is-on');
        t.textContent = t.getAttribute('data-default-msg') || '已复制';
    }, 2200);
}

(function initWorkspaceFileOpenDelegation() {
    if (document.body.dataset.workspaceFileOpenBound) return;
    document.body.dataset.workspaceFileOpenBound = '1';
    document.body.addEventListener('click', function (ev) {
        var el = ev.target;
        if (!el || !el.closest) return;
        var a = el.closest('a.msg-link-workspace-open');
        if (!a) return;
        ev.preventDefault();
        var rel = a.getAttribute('data-workspace-open') || '';
        var controller = (typeof AbortController !== 'undefined') ? new AbortController() : null;
        var timer = controller ? setTimeout(function () { controller.abort(); }, 8000) : null;
        fetch('/api/open-workspace-file?rel=' + encodeURIComponent(rel), controller ? { signal: controller.signal } : undefined)
            .then(function (r) {
                if (timer) clearTimeout(timer);
                return r.json().catch(function () { return { ok: false, error: '响应异常' }; });
            })
            .then(function (j) {
                if (j && j.ok) showOpenFileFeedback('已调用系统打开文件');
                else showOpenFileFeedback((j && j.error) ? ('无法打开：' + j.error) : '无法打开文件');
            })
            .catch(function () { showOpenFileFeedback('无法连接服务'); });
    });
})();

let rewriteUndoState = null;
/** 改写待发送：仅在点击发送时调用截断；取消则丢弃 */
let pendingRewriteTruncate = null;
function hideRewriteUndoToast() {
    const t = document.getElementById('rewrite-undo-toast');
    if (t) {
        t.classList.remove('is-on');
        const btn = t.querySelector('.rewrite-undo-btn');
        if (btn) btn.textContent = '撤销';
    }
    rewriteUndoState = null;
}
function showRewriteUndoToast(type, data) {
    const t = document.getElementById('rewrite-undo-toast');
    const msgEl = t && t.querySelector('.rewrite-undo-msg');
    const btn = t && t.querySelector('.rewrite-undo-btn');
    if (!t || !msgEl) return;
    rewriteUndoState = { type: type, data: data };
    if (type === 'rewrite_pending') {
        msgEl.textContent = '改写待生效：发送消息后才会截断历史并发送；点此取消改写。';
        if (btn) btn.textContent = '取消改写';
    } else if (type === 'tail') {
        msgEl.textContent = '已截断历史，可撤销恢复';
        if (btn) btn.textContent = '撤销';
    } else {
        msgEl.textContent = '已填入输入框，可撤销';
        if (btn) btn.textContent = '撤销';
    }
    t.classList.add('is-on');
}

function smoothScrollBy(el, dy) {
    if (!el || !dy) return;
    const bMax = Math.max(0, el.scrollHeight - el.clientHeight);
    const start = el.scrollTop;
    const target = Math.max(0, Math.min(bMax, start + dy));
    const dist = target - start;
    if (Math.abs(dist) < 0.5) return;
    const frames = 3;
    let f = 0;
    function step() {
        f += 1;
        const t = f / frames;
        const ease = 1 - Math.pow(1 - t, 2);
        el.scrollTop = start + dist * ease;
        if (f < frames) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
}

function isNearBottom(el, thresholdPx) {
    if (!el) return true;
    const th = (thresholdPx == null) ? 56 : thresholdPx;
    return (el.scrollHeight - el.clientHeight - el.scrollTop) <= th;
}

async function getUiEventCount(sessionId, opts) {
    opts = opts || {};
    const sid = sessionId != null ? sessionId : currentSessionId;
    if (!sid) return 0;
    if (
        opts.preferCache
        && typeof uiEventCountCache !== 'undefined'
        && typeof uiEventCountCache.has === 'function'
        && uiEventCountCache.has(sid)
        && (typeof uiEventCountCache.isFresh !== 'function' || uiEventCountCache.isFresh(sid, opts.maxAgeMs))
    ) {
        return uiEventCountCache.get(sid);
    }
    try {
        const r = await fetch('/sessions/' + encodeURIComponent(sid) + '/messages/count');
        if (!r.ok) return 0;
        const j = await r.json();
        const count = (j && typeof j.count === 'number') ? j.count : 0;
        if (typeof uiEventCountCache !== 'undefined') uiEventCountCache.updateFromServer(sid, count);
        return count;
    } catch (e) { return 0; }
}

function loadUnreadFromStorage() {
    try {
        const raw = localStorage.getItem(LS_SESSION_UNREAD);
        if (!raw) return;
        const arr = JSON.parse(raw);
        if (!Array.isArray(arr)) return;
        arr.forEach(function (id) { sessionUnreadComplete.add(String(id)); });
    } catch (e) { /* ignore */ }
}

function persistSessionUnread() {
    try {
        localStorage.setItem(LS_SESSION_UNREAD, JSON.stringify([...sessionUnreadComplete]));
    } catch (e) { /* ignore */ }
}

function stashInputDraft(sessionId) {
    if (!messageInput || !sessionId) return;
    draftBySession[sessionId] = messageInput.value;
    persistInputDraft(sessionId, messageInput.value);
}

function restoreInputDraft(sessionId) {
    if (!messageInput) return;
    const v = (sessionId && Object.prototype.hasOwnProperty.call(draftBySession, sessionId))
        ? draftBySession[sessionId]
        : readStoredInputDraft(sessionId);
    messageInput.value = v != null ? String(v) : '';
    rewriteInputWorkspacePaths();
    autoResizeTextarea();
}

function inputDraftStorageKey(sessionId) {
    return LS_INPUT_DRAFT_PREFIX + String(sessionId || '');
}

function persistInputDraft(sessionId, value) {
    if (!sessionId) return;
    const text = String(value || '');
    draftBySession[sessionId] = text;
    try {
        const key = inputDraftStorageKey(sessionId);
        if (text) localStorage.setItem(key, text);
        else localStorage.removeItem(key);
    } catch (e) { /* ignore */ }
}

function readStoredInputDraft(sessionId) {
    if (!sessionId) return '';
    try {
        return localStorage.getItem(inputDraftStorageKey(sessionId)) || '';
    } catch (e) {
        return '';
    }
}

function removeStoredInputDraft(sessionId) {
    if (!sessionId) return;
    delete draftBySession[sessionId];
    try { localStorage.removeItem(inputDraftStorageKey(sessionId)); } catch (e) { /* ignore */ }
}

function clearStreamPoll() {
    if (streamPollTimer) {
        clearInterval(streamPollTimer);
        streamPollTimer = null;
    }
}

async function fetchSessionStreamActiveMap() {
    try {
        const response = await fetch('/sessions');
        const sessions = await response.json();
        if (!Array.isArray(sessions)) return Object.create(null);
        const m = Object.create(null);
        for (let i = 0; i < sessions.length; i += 1) {
            const s = sessions[i];
            if (s && s.id) m[s.id] = !!s.stream_active;
        }
        return m;
    } catch (e) {
        return Object.create(null);
    }
}

function maybeStartStreamPollForSession(sid, opts) {
    opts = opts || {};
    clearStreamPoll();
    if (!sid) return;
    if (!isSessionRunning(sid)) return;
    if (!getSessionRunState(sid) && typeof attachSessionEventStream === 'function') {
        void attachSessionEventStream(sid, { skipInitialLoad: !!opts.skipInitialLoad });
    }
    let pollCount = 0;
    let MAX_POLL_COUNT = 20;
    streamPollTimer = setInterval(function () {
        (async function () {
            if (currentSessionId !== sid) {
                clearStreamPoll();
                return;
            }
            pollCount += 1;
            const m = await fetchSessionStreamActiveMap();
            applyServerStreamActiveMap(m);
            const still = !!m[sid];
            if (!still || pollCount >= MAX_POLL_COUNT) {
                clearStreamPoll();
                await loadSessions();
                syncSessionListIndicatorClasses();
                setSendButtonState();
                return;
            }
            if (currentSessionId === sid && document.visibilityState === 'visible') {
                syncSessionListIndicatorClasses();
                setSendButtonState();
            }
        })();
    }, 15000);
}

async function scrollToUserTurnOrLoadOlder(eventIndex, opts) {
    opts = opts || {};
    var ei = Number(eventIndex);
    if (!Number.isFinite(ei)) return false;
    var silent = !!opts.silent;
    var allowFullReload = opts.allowFullReload !== false && !silent;
    var maxOlderLoads = Number.isFinite(Number(opts.maxOlderLoads))
        ? Math.max(0, Number(opts.maxOlderLoads))
        : 120;
    function setTocJumpLoading(active) {
        var list = document.getElementById('chat-toc-list');
        var link = list && list.querySelector('a[data-event-index="' + ei + '"]');
        if (!link) return;
        link.classList.toggle('is-loading', !!active);
        if (active) link.setAttribute('aria-busy', 'true');
        else link.removeAttribute('aria-busy');
    }
    function findWrap() {
        var stream = getVisibleChatStream();
        if (!stream) return null;
        return stream.querySelector('.msg-wrap--user[data-event-index="' + ei + '"]')
            || stream.querySelector('#user-msg-' + ei);
    }
    async function loadFullHistoryForTarget(sid) {
        if (!allowFullReload) return;
        if (sid !== currentSessionId || typeof loadSessionMessages !== 'function') return;
        try {
            await loadSessionMessages(sid, 'saved-or-bottom', {
                full: true,
                allowDuringRun: typeof isServerStreamActive === 'function' && isServerStreamActive(sid),
            });
        } catch (e) {
            console.error('reload full history for toc target failed:', e);
        }
    }
    setTocJumpLoading(true);
    try {
        var wrap = findWrap();
        if (wrap) {
            wrap.scrollIntoView({ behavior: 'smooth', block: 'start' });
            return true;
        }
        var sid = currentSessionId;
        var safety = 0;
        var olderLoads = 0;
        var pagingCoveredTarget = false;
        while (sid === currentSessionId && safety < 120) {
            safety += 1;
            wrap = findWrap();
            if (wrap) {
                wrap.scrollIntoView({ behavior: 'smooth', block: 'start' });
                return true;
            }
            var ph = sessionHistoryPaging;
            if ((!ph || ph.sessionId !== sid) && getVisibleChatStream()) {
                ph = restoreHistoryPagingFromStream(getVisibleChatStream());
                if (ph) sessionHistoryPaging = ph;
            }
            if (!ph || ph.sessionId !== sid) {
                await loadFullHistoryForTarget(sid);
                break;
            }
            if (ei >= ph.range_start) {
                pagingCoveredTarget = true;
                break;
            }
            if (!ph.has_older) break;
            if (olderLoads >= maxOlderLoads) break;
            while (historyOlderLoading && currentSessionId === sid) {
                await new Promise(function (r) { setTimeout(r, 40); });
            }
            olderLoads += 1;
            await loadOlderHistoryChunk({ keepTocStable: true, turns: 50 });
        }
        wrap = findWrap();
        if (wrap) {
            wrap.scrollIntoView({ behavior: 'smooth', block: 'start' });
            return true;
        }
        if (allowFullReload && sid === currentSessionId && pagingCoveredTarget) {
            await loadFullHistoryForTarget(sid);
            if (sid !== currentSessionId) return false;
            wrap = findWrap();
            if (wrap) {
                wrap.scrollIntoView({ behavior: 'smooth', block: 'start' });
                return true;
            }
            rebuildToc();
        }
        if (wrap) wrap.scrollIntoView({ behavior: 'smooth', block: 'start' });
        else if (!silent) {
            showUiAlert({
                title: '无法定位该条',
                message: '未能加载到对应的用户提问（可能索引不一致）。可刷新页面或使用「更早 ' + HISTORY_DIALOGUES_PER_PAGE + ' 轮对话」手动分页。',
                showCancel: false,
                confirmText: '知道了',
            });
        }
        return !!wrap;
    } finally {
        setTocJumpLoading(false);
    }
}
