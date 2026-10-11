/**
 * 上下文拆解卡（对齐 DSH token-meter 的 ContextMeter 面板）：
 * 标题行「上下文已用 24.7%」+ 右侧「~24.5k / 128k」，一条按构成分色的占比条，
 * 下方三行图例（系统提示词 / 工具定义 / 对话消息）。条的总长永远等于精确占比，
 * 分段只按启发式构成分配宽度。
 *
 * 只有"有数值 / 没数值"两种状态：有数值就恒为这张卡（拿不到三段时退回单色整条并
 * 隐藏图例，同时补一次取三段的请求），没数值才退回原来的纯文字提示。会话打开时
 * 快照先写入的旧检查点可能还没有三段，若那时改回纯文字提示，用户就会在同一处看到
 * 两种浮窗来回切换 —— 这正是要避免的。三条泳道的键与后端 breakdown 一致。
 */
var CTX_BREAKDOWN_LANES = [
    { key: 'system_tokens', lane: 'system' },
    { key: 'tools_tokens', lane: 'tools' },
    { key: 'message_tokens', lane: 'messages' },
];
/* 悬停展开的迟滞：足够长到划过标题栏时不闪，远短于通用提示的 500ms（那是纯文字提示）。 */
var CTX_CARD_HOVER_DELAY_MS = 180;
/* 有数值但还没有三段时，读到的说明行要讲清"分段为什么还没出来"。 */
var CTX_CARD_NOTE_WITH_LANES = '分母为压缩摘要阈值；构成按本地估算';
var CTX_CARD_NOTE_WITHOUT_LANES = '分母为压缩摘要阈值；构成待本次请求估算后补齐';
var ctxCardOpenTimer = null;
/* 有数值即可展开卡片（是否含三段只决定图例与分段颜色，不决定卡片是否存在）。 */
var ctxCardReady = false;
/* 每个会话只补取一次三段，避免请求风暴；拿到三段后清除，值再次退化时可以再补。 */
var contextBreakdownRefetchTried = Object.create(null);

function contextBreakdownOrNull(raw) {
    if (!raw || typeof raw !== 'object') return null;
    var parts = {};
    for (var i = 0; i < CTX_BREAKDOWN_LANES.length; i += 1) {
        var value = Number(raw[CTX_BREAKDOWN_LANES[i].key]);
        if (!Number.isFinite(value) || value < 0) return null;
        parts[CTX_BREAKDOWN_LANES[i].key] = value;
    }
    ['deferred_tools_count', 'deferred_tools_tokens', 'saved_tools_tokens'].forEach(function (key) {
        var value = Number(raw[key]);
        if (Number.isFinite(value) && value >= 0) parts[key] = value;
    });
    return parts;
}

function closeContextBreakdownCard() {
    if (ctxCardOpenTimer) {
        clearTimeout(ctxCardOpenTimer);
        ctxCardOpenTimer = null;
    }
    var card = document.getElementById('ctx-breakdown');
    if (card) {
        card.hidden = true;
        card.setAttribute('aria-hidden', 'true');
    }
}

function openContextBreakdownCard() {
    if (ctxCardOpenTimer) {
        clearTimeout(ctxCardOpenTimer);
        ctxCardOpenTimer = null;
    }
    var card = document.getElementById('ctx-breakdown');
    if (!card || !ctxCardReady) return;
    card.hidden = false;
    card.setAttribute('aria-hidden', 'false');
}

/**
 * A value stored without the three lanes (an older checkpoint read straight from
 * the history snapshot) would leave the legend permanently empty, because the
 * meter's own refresh is rate-limited to one request per session per few seconds
 * and nothing else re-asks. Ask once, bypassing that freshness window.
 */
function ensureContextBreakdownForCurrentSession(breakdown) {
    var sid = String(currentSessionId || '');
    if (!sid) return;
    if (contextBreakdownOrNull(breakdown)) {
        delete contextBreakdownRefetchTried[sid];
        return;
    }
    if (contextBreakdownRefetchTried[sid]) return;
    if (contextTokenInFlightBySession[sid]) return;
    requestAnimationFrame(function () {
        requestAnimationFrame(function () {
            // 标记只在"补取真的发起"时消费（见 refreshContextTokensFromServer）。若此刻
            // 恰有在途请求，那次请求落地后仍会带着同一个缺三段的数值回到这里重排一次，
            // 因此这里提前登记会把唯一机会浪费在一次不会发出的请求上。
            var latest = selectContextTokens(sid);
            if (latest && contextBreakdownOrNull(latest.breakdown)) {
                delete contextBreakdownRefetchTried[sid];
                return;
            }
            refreshContextTokensFromServer(sid, null, true);
        });
    });
}

/** 卡片内容：占比条分段宽度按构成比例分配，行值按同一份构成标注 ~。 */
function renderContextBreakdownCard(card, pctDisp, estimated, threshold, breakdown) {
    if (!card) return;
    var widthPct = Math.max(0, Math.min(100, pctDisp));
    var pctEl = card.querySelector('.ctx-card-pct');
    var figuresEl = card.querySelector('.ctx-card-figures');
    var barEl = card.querySelector('.ctx-card-bar');
    var rowsEl = card.querySelector('.ctx-card-rows');
    if (pctEl) pctEl.textContent = pctDisp + '%';
    if (figuresEl) {
        figuresEl.textContent = '~' + formatTokenCompact(estimated) + ' / ' + formatTokenCompact(threshold);
    }
    var total = breakdown
        ? (breakdown.system_tokens + breakdown.tools_tokens + breakdown.message_tokens)
        : 0;
    var segments = [];
    if (!breakdown || total <= 0) {
        segments.push('<span class="ctx-card-seg" style="width:' + widthPct + '%"></span>');
    } else {
        CTX_BREAKDOWN_LANES.forEach(function (lane) {
            var width = widthPct * breakdown[lane.key] / total;
            if (!(width > 0)) return;
            segments.push(
                '<span class="ctx-card-seg ctx-lane-' + lane.lane + '" style="width:' + width.toFixed(3) + '%"></span>'
            );
        });
    }
    if (barEl) barEl.innerHTML = segments.join('');
    if (rowsEl) {
        rowsEl.hidden = !breakdown;
        if (breakdown) {
            Array.prototype.forEach.call(rowsEl.querySelectorAll('[data-lane]'), function (valueEl) {
                var laneKey = valueEl.getAttribute('data-lane');
                valueEl.textContent = '~' + formatTokenCompact(breakdown[laneKey]);
            });
        }
    }
    var noteEl = card.querySelector('.ctx-card-note');
    if (noteEl) {
        noteEl.textContent = breakdown ? CTX_CARD_NOTE_WITH_LANES : CTX_CARD_NOTE_WITHOUT_LANES;
        if (breakdown && breakdown.deferred_tools_count > 0) {
            noteEl.textContent += '；已延迟 ' + breakdown.deferred_tools_count +
                ' 个工具，本轮工具定义节省约 ' + formatTokenCompact(breakdown.saved_tools_tokens || 0) + ' tokens';
        }
    }
}

function bindContextBreakdownHover(el) {
    if (!el || el._ctxCardHoverBound) return;
    el._ctxCardHoverBound = true;
    el.addEventListener('mouseenter', function () {
        if (!ctxCardReady) return;
        if (ctxCardOpenTimer) clearTimeout(ctxCardOpenTimer);
        ctxCardOpenTimer = setTimeout(function () {
            ctxCardOpenTimer = null;
            openContextBreakdownCard();
        }, CTX_CARD_HOVER_DELAY_MS);
    });
    // 卡片是触发器的子节点，指针移入卡片不会触发 mouseleave；离开整块才收起。
    el.addEventListener('mouseleave', closeContextBreakdownCard);
    document.addEventListener('keydown', function (ev) {
        if (ev.key === 'Escape') closeContextBreakdownCard();
    });
}

function formatTokenCompact(n) {
    if (n == null || !Number.isFinite(Number(n))) return '—';
    const x = Math.max(0, Math.round(Number(n)));
    if (x >= 1000000) return (x / 1000000).toFixed(1).replace(/\.0$/, '') + 'M';
    if (x >= 10000) return (x / 1000).toFixed(x % 1000 === 0 ? 0 : 1).replace(/\.0$/, '') + 'k';
    if (x >= 1000) return (x / 1000).toFixed(1).replace(/\.0$/, '') + 'k';
    return String(x);
}

function setContextTokenLabel(estimated, threshold, breakdown) {
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
        ctxCardReady = false;
        closeContextBreakdownCard();
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
    const card = el.querySelector('#ctx-breakdown');
    const parts = contextBreakdownOrNull(breakdown);
    renderContextBreakdownCard(card, pctDisp, n, t, parts);
    // 有数值就恒为拆解卡；三段只决定图例与分段颜色（缺口由下面的一次补取填上）。
    ctxCardReady = true;
    bindContextBreakdownHover(el);
    ensureContextBreakdownForCurrentSession(parts);
    // 拆解卡接管说明职责；同一元素上不再挂纯文字提示，避免两种浮窗叠加。
    el.removeAttribute('data-ui-tip');
    if (typeof hideUiHoverTooltip === 'function') hideUiHoverTooltip();
}

let contextTokenRequestSeq = 0;
const contextTokenInFlightBySession = Object.create(null);
const CONTEXT_TOKEN_CACHE_TTL_MS = 3000;

async function refreshContextTokensFromServer(sid, seq, force) {
    if (!sid) return;
    const cached = selectContextTokens(sid);
    // ``force`` 只给"有值但缺三段"的补取用：它绕开新鲜度窗口，仍受在途去重约束。
    if (!force && cached && cached.updatedAt && (Date.now() - cached.updatedAt) < CONTEXT_TOKEN_CACHE_TTL_MS) {
        if (sid === currentSessionId) setContextTokenLabel(cached.estimated, cached.threshold, cached.breakdown);
        return;
    }
    if (contextTokenInFlightBySession[sid]) return;
    contextTokenInFlightBySession[sid] = true;
    // 补取机会在这里消费：只有真的发出去了才算用过，被在途请求挡下的那次不算。
    if (force) contextBreakdownRefetchTried[sid] = true;
    try {
        const r = await fetch('/sessions/' + encodeURIComponent(sid) + '/context_tokens');
        const j = await r.json();
        if (r.ok && j && j.ok && j.estimated != null && j.estimated >= 0) {
            // Clear the in-flight mark BEFORE recording: applying a value without
            // the three lanes is what schedules the one-shot lane refetch, and an
            // in-flight mark that is still set would make that refetch look
            // redundant — it would never happen, leaving the legend empty.
            delete contextTokenInFlightBySession[sid];
            // A session switch invalidates the paint, not the session's data.
            // Keep successful refetches so returning within the cache TTL has lanes.
            if (sid !== currentSessionId || (seq != null && seq !== contextTokenRequestSeq)) {
                setContextTokensForSession(sid, j.estimated, j.threshold, j.breakdown);
                if (contextBreakdownOrNull(j.breakdown)) delete contextBreakdownRefetchTried[sid];
                return;
            }
            recordContextTokens(sid, j.estimated, j.threshold, j.breakdown);
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

function recordContextTokens(sessionId, estimated, threshold, breakdown) {
    if (!sessionId) return;
    setContextTokensForSession(sessionId, estimated, threshold, breakdown);
    if (sessionId === currentSessionId) setContextTokenLabel(estimated, threshold, breakdown);
}

function applyContextTokenLabelForCurrentSession() {
    if (!currentSessionId) { setContextTokenLabel(null, null, null); return; }
    const x = selectContextTokens(currentSessionId);
    if (x) setContextTokenLabel(x.estimated, x.threshold, x.breakdown);
    else setContextTokenLabel(null, null, null);
}

/** 主对话区跟到底 */
function scrollChatToBottomIfFollow(runSessionId, opts) {
    opts = opts || {};
    if (shouldGateScrollByRunSession(null, runSessionId)) return;
    if (!opts.force && !liveAutoFollow) return;
    if (chatContainer) setScrollTopImmediate(chatContainer, chatContainer.scrollHeight);
}

function setScrollTopImmediate(el, y) {
    if (!el) return;
    var prev = el.style.scrollBehavior;
    el.style.scrollBehavior = 'auto';
    try {
        el.scrollTop = y;
    } finally {
        // Restore synchronously so overlapping writes cannot restore each
        // other's temporary style on later frames.
        el.style.scrollBehavior = prev;
    }
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

function isSmoothStreamPortNearBottom(port, thresholdPx) {
    if (!port) return false;
    if (!isSmoothStreamActive()) return isNearBottom(port, thresholdPx);
    if (smoothFollowController.isReaderDetached(port)) {
        // An intentional upward gesture must win over the legacy broad
        // near-bottom threshold. Re-arm only once the reader reaches the floor.
        if (!isNearBottom(port, 2)) return false;
        smoothFollowController.clearReaderDetached(port);
    }
    return smoothFollowController.isFollowing(port) || isNearBottom(port, thresholdPx);
}

/** 生成中时：对话区与当前执行过程区均在底部附近时才允许自动跟随流式滚动 */
function refreshLiveAutoFollowPins() {
    if (!chatContainer) return;
    if (isSessionRunning(currentSessionId)) {
        streamChatNearBottom = isSmoothStreamPortNearBottom(
            chatContainer,
            STREAM_CHAT_NEAR_BOTTOM_PX
        );
        var pb = getProcessBodyElForCurrentRun();
        streamProcNearBottom = !pb || isSmoothStreamPortNearBottom(pb, STREAM_PROC_NEAR_BOTTOM_PX);
        liveAutoFollow = streamChatNearBottom && streamProcNearBottom;
    } else {
        liveAutoFollow = isSmoothStreamPortNearBottom(chatContainer, STREAM_CHAT_NEAR_BOTTOM_PX);
    }
}

function shouldGateScrollByRunSession(ctx, runSessionId) {
    if (!runSessionId) return false;
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

function feedChunkCollapsedMax(chunk) {
    var styles = getComputedStyle(chunk);
    var line = parseFloat(styles.getPropertyValue('--line')) || 21.6;
    var pad = parseFloat(styles.getPropertyValue('--scroller-pad-y')) || 4;
    return line * 2.5 + pad * 2;
}

function measureFeedChunkScrollerHeight(sc, chunk) {
    if (!sc) return 0;
    var h = sc.scrollHeight;
    if (h > 1) return h;
    return h;
}

function scrollContentAreaIfFollow(ctx, runSessionId, channel) {
    if (typeof replayingMessages !== 'undefined' && replayingMessages) return;
    if (shouldGateScrollByRunSession(ctx, runSessionId)) return;
    // Trace events and text wrapping share the same follow motion.
    if (isSmoothStreamActive()) {
        if (typeof isHistorySmoothScrollActive === 'function' && isHistorySmoothScrollActive()) return;
        followStreamProcessScroll(ctx, runSessionId, channel || 'row');
        return;
    }
    if (!liveAutoFollow) return;
    scrollProcessBodyToBottom(ctx, runSessionId);
    scrollChatToBottomIfFollow(runSessionId, {});
}

/** 将当前步的执行框滚到底（流式增量主要长在这里，必须滚 procBody 而不是只滚对话区） */
function scrollProcessBodyToBottom(ctx, runSessionId) {
    if (shouldGateScrollByRunSession(ctx, runSessionId)) return;
    if (!ctx || !ctx.stream) return;
    var agg = (ctx.currentProcessGroup && ctx.currentProcessGroup.isConnected)
        ? ctx.currentProcessGroup
        : ctx.stream.querySelector('.process-aggregate:last-of-type');
    if (agg) {
        var procBody = agg.querySelector('.process-aggregate-body');
        if (procBody) procBody.scrollTop = procBody.scrollHeight;
    }
}

function followStreamProcessScroll(ctx, runSessionId, channel) {
    // Keep the caller argument for the existing entry points; it no longer
    // selects a motion profile in the unified follower.
    if (typeof replayingMessages !== 'undefined' && replayingMessages) return;
    if (shouldGateScrollByRunSession(ctx, runSessionId)) return;
    if (
        isSmoothStreamActive()
        && typeof isHistorySmoothScrollActive === 'function'
        && isHistorySmoothScrollActive()
    ) return;
    if (!liveAutoFollow) return;
    if (isSmoothStreamActive()) {
        if (ctx && ctx.currentProcessGroup && ctx.currentProcessGroup.isConnected
            && ctx.currentProcessGroup.classList.contains('is-collapsed')) {
            ctx.currentProcessGroup.classList.remove('is-collapsed');
            var smoothTop = ctx.currentProcessGroup.querySelector('.process-aggregate-top');
            if (smoothTop) smoothTop.setAttribute('aria-expanded', 'true');
        }
        var smoothProcessBody = getProcessBodyElForCurrentRun();
        var releaseMainFollow = function (port) {
            if (port === chatContainer) streamChatNearBottom = false;
            else streamProcNearBottom = false;
            liveAutoFollow = false;
            smoothFollowController.cancel(port === chatContainer ? smoothProcessBody : chatContainer);
        };
        if (smoothProcessBody) {
            smoothFollowController.request(smoothProcessBody, {
                onUnpin: releaseMainFollow,
            });
        }
        if (chatContainer) {
            smoothFollowController.request(chatContainer, {
                onUnpin: releaseMainFollow,
            });
        }
        if (!streamScrollFollowRaf) {
            streamScrollFollowRaf = requestAnimationFrame(function () {
                streamScrollFollowRaf = 0;
                refreshFeedChunksInCtx(ctx, '.feed-chunk.is-streaming');
                refreshLiveAutoFollowPins();
            });
        }
        return;
    }
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

/** Finish without a long easing tail once no more stream content can arrive. */
function finishStreamScrollIfFollow(ctx, runSessionId) {
    if (isSmoothStreamActive()) {
        if (shouldGateScrollByRunSession(ctx, runSessionId)) return;
        if (!liveAutoFollow) return;
        var processBody = getProcessBodyElForCurrentRun();
        if (processBody) {
            settleSmoothTraceHeightAnimations(processBody);
            smoothFollowController.snapToBottom(processBody);
        }
        if (chatContainer) smoothFollowController.snapToBottom(chatContainer);
        return;
    }
    scrollProcessBodyToBottom(ctx, runSessionId);
    scrollChatToBottomIfFollow(runSessionId, {});
}

/** Final answer cards keep the legacy snap and must not race an active glide. */
function cancelSmoothStreamFollowForFinal(ctx) {
    if (!isSmoothStreamActive()) return;
    if (ctx && ctx.stream === getVisibleChatStream()) {
        smoothFollowController.cancel(chatContainer);
    }
    var processBody = null;
    if (ctx && ctx.currentProcessGroup && ctx.currentProcessGroup.isConnected) {
        processBody = ctx.currentProcessGroup.querySelector('.process-aggregate-body');
    }
    if (processBody) smoothFollowController.cancel(processBody);
}

/** Keep the native history-load animation isolated from the live follower. */
function cancelSmoothStreamFollowForHistoryLoad() {
    smoothFollowController.cancel(chatContainer);
    var processBody = getProcessBodyElForCurrentRun();
    if (processBody) smoothFollowController.cancel(processBody);
}

/** The shared viewport must not retain the previous session's animation. */
function cancelSmoothStreamFollowForSessionSwitch() {
    if (typeof streamScrollFollowRaf !== 'undefined' && streamScrollFollowRaf) {
        cancelAnimationFrame(streamScrollFollowRaf);
        streamScrollFollowRaf = 0;
    }
    smoothFollowController.reset(chatContainer);
    var stream = getVisibleChatStream();
    if (typeof cancelHistoryPrependViewport === 'function') cancelHistoryPrependViewport(stream);
    if (stream) stream.querySelectorAll('.process-aggregate-body').forEach(function (port) {
        smoothFollowController.reset(port);
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
        has_newer: !!paging.has_newer,
        manual_history: !!paging.manual_history,
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
            has_newer: !!raw.has_newer,
            manual_history: !!raw.manual_history,
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
    btn.textContent = '加载更早记录';
    btn.addEventListener('click', function () { loadOlderHistoryChunk(); });
    el.appendChild(btn);
    streamEl.insertBefore(el, streamEl.firstChild);
    return el;
}

var latestHistoryTailRestoreBySession = Object.create(null);

function getSessionHistoryPaging(sessionId) {
    var sid = String(sessionId || '');
    if (!sid) return null;
    var paging = sessionHistoryPaging;
    var stream = getVisibleChatStream();
    if ((!paging || paging.sessionId !== sid) && stream) {
        paging = restoreHistoryPagingFromStream(stream);
        if (paging) sessionHistoryPaging = paging;
    }
    return paging && paging.sessionId === sid ? paging : null;
}

function sessionHasLiveHistoryOwner(sessionId) {
    var sid = String(sessionId || '');
    return !!sid && (
        isSessionRunning(sid)
        || (typeof isServerStreamActive === 'function' && isServerStreamActive(sid))
    );
}

async function refreshSessionLiveHistoryOwner(sessionId) {
    var sid = String(sessionId || '');
    if (!sid || sessionHasLiveHistoryOwner(sid)) return !!sid;
    if (typeof fetchSessionStreamActiveMap !== 'function') return sessionHasLiveHistoryOwner(sid);
    var activeMap = await fetchSessionStreamActiveMap();
    if (activeMap && Object.prototype.hasOwnProperty.call(activeMap, sid)) {
        if (typeof applyServerStreamActiveMap === 'function') applyServerStreamActiveMap(activeMap);
        if (activeMap[sid]) return true;
    }
    return sessionHasLiveHistoryOwner(sid);
}

async function ensureLatestHistoryTailForLiveAppend(sessionId) {
    var sid = String(sessionId || '');
    if (!sid || sid !== currentSessionId) return true;
    var paging = getSessionHistoryPaging(sid);
    if (!paging || !paging.has_newer) return true;
    if (latestHistoryTailRestoreBySession[sid]) return latestHistoryTailRestoreBySession[sid];
    var restore = (async function () {
        var loaded = await loadSessionMessages(sid, 'bottom', {
            useSnapshot: false,
            preloadOlderIfShort: false,
        });
        if (sid !== currentSessionId) return true;
        var current = getSessionHistoryPaging(sid);
        return loaded === true && !(current && current.has_newer);
    })();
    latestHistoryTailRestoreBySession[sid] = restore;
    try {
        return await restore;
    } finally {
        if (latestHistoryTailRestoreBySession[sid] === restore) {
            delete latestHistoryTailRestoreBySession[sid];
        }
    }
}

var HISTORY_AUTO_LOAD_TOP_PX = 32;

/** 当前轮首屏保持轻量；读者主动翻阅后，允许继续自动向前分页。 */
function enableHistoryAutoLoadForReader() {
    var stream = getVisibleChatStream();
    if (stream) stream._historyAutoLoadEnabled = true;
}

/** 滚到历史顶部附近时自动向前分页；按钮仍保留为加载状态提示和手动兜底。 */
function maybeAutoLoadOlderHistory() {
    if (typeof replayingMessages !== 'undefined' && replayingMessages) return;
    if (typeof sessionStore !== 'undefined' && sessionStore.ui && sessionStore.ui.loadingMessages) return;
    var stream = getVisibleChatStream();
    if (!stream || stream.hidden) return;
    var paging = getSessionHistoryPaging(currentSessionId);
    if (paging && paging.manual_history && !stream._historyAutoLoadEnabled
        && sessionHasLiveHistoryOwner(currentSessionId)) return;
    if (typeof isHistorySmoothScrollActive === 'function' && isHistorySmoothScrollActive()) return;
    if (!chatContainer || chatContainer.scrollTop > HISTORY_AUTO_LOAD_TOP_PX) return;
    void loadOlderHistoryChunk({ trigger: 'scroll-top' });
}

function updateHistorySentinelVisibility() {
    var strip = document.getElementById('history-load-sentinel');
    var btn = strip && strip.querySelector('.history-load-older-btn');
    var ph = sessionHistoryPaging;
    if (!strip || !btn) return;
    if (!ph || !ph.has_older || ph.sessionId !== currentSessionId) {
        strip.hidden = true;
        btn.disabled = false;
        btn.textContent = '加载更早记录';
        return;
    }
    strip.hidden = false;
    btn.disabled = historyOlderLoading;
    btn.textContent = historyOlderLoading ? '加载中…' : '加载更早记录';
}

function resetSessionHistoryPaging() {
    setSessionHistoryPaging(null);
    var stream = getVisibleChatStream();
    cancelHistoryPrependViewport(stream);
    if (stream) {
        delete stream._historyOlderLoadToken;
        delete stream._historyAutoLoadEnabled;
    }
    historyOlderLoading = false;
    updateHistorySentinelVisibility();
}

function cancelHistoryPrependViewport(stream) {
    if (stream && stream._historyPrependViewport) stream._historyPrependViewport.stop();
}

/** 在插入前记录可见元素。总高度差会把下方的增长也算进去，元素锚点不会。 */
function captureHistoryPrependViewport(stream, port, sid) {
    if (!port || stream.parentNode !== port) return null;
    cancelHistoryPrependViewport(stream);
    var viewport = port.getBoundingClientRect();
    var anchors = [];
    function remember(node) {
        var rect = node.getBoundingClientRect();
        if (rect.height > 0 && rect.bottom > viewport.top) {
            anchors.push({ node: node, offset: rect.top - viewport.top });
            return true;
        }
        return false;
    }
    var children = Array.from(stream.children);
    for (var i = 0; i < children.length && anchors.length < 3; i += 1) {
        var child = children[i];
        if (child.id === 'history-load-sentinel' || !remember(child)) continue;
        // 相邻过程框合并可能移除外框，但其中的执行行会保留。
        if (child.classList.contains('process-aggregate')) {
            var rows = child.querySelectorAll('.feed-item');
            for (var j = 0; j < rows.length; j += 1) {
                if (remember(rows[j])) break;
            }
        }
    }
    return { stream: stream, port: port, sessionId: sid, anchors: anchors,
        top: port.scrollTop, height: port.scrollHeight, lastTop: port.scrollTop };
}

function restoreHistoryPrependViewport(state) {
    if (!state || state.sessionId !== currentSessionId
        || state.stream !== getVisibleChatStream() || state.stream.parentNode !== state.port
        || (typeof isHistorySmoothScrollActive === 'function' && isHistorySmoothScrollActive())) return false;
    var port = state.port;
    var delta = null;
    for (var i = 0; i < state.anchors.length; i += 1) {
        var anchor = state.anchors[i];
        if (!state.stream.contains(anchor.node)) continue;
        delta = anchor.node.getBoundingClientRect().top - port.getBoundingClientRect().top - anchor.offset;
        break;
    }
    if (delta == null) delta = state.top + port.scrollHeight - state.height - port.scrollTop;
    if (Math.abs(delta) > 0.5) setScrollTopImmediate(port, port.scrollTop + delta);
    state.lastTop = port.scrollTop;
    return true;
}

/** 补偿下一帧折叠测量和迟到的图片；读者再次操作或切换会话时立即退出。 */
function settleHistoryPrependViewport(state) {
    if (!state || !restoreHistoryPrependViewport(state)) return;
    var stream = state.stream, port = state.port;
    var observer = null, timer = 0, raf = 0, stopped = false;
    var inputs = ['wheel', 'touchstart', 'pointerdown', 'keydown'];
    function stop() {
        if (stopped) return;
        stopped = true;
        if (observer) observer.disconnect();
        if (timer) clearTimeout(timer);
        if (raf) cancelAnimationFrame(raf);
        inputs.forEach(function (type) { port.removeEventListener(type, stop, true); });
        port.removeEventListener('scroll', onScroll);
        stream.removeEventListener('load', correct, true);
        if (stream._historyPrependViewport === state) delete stream._historyPrependViewport;
    }
    function correct() {
        if (stopped) return;
        if (!restoreHistoryPrependViewport(state)) stop();
    }
    function onScroll() {
        if (Math.abs(port.scrollTop - state.lastTop) > 1) stop();
    }
    state.stop = stop;
    stream._historyPrependViewport = state;
    inputs.forEach(function (type) { port.addEventListener(type, stop, { capture: true, passive: true }); });
    port.addEventListener('scroll', onScroll, { passive: true });
    stream.addEventListener('load', correct, true);
    if (typeof ResizeObserver === 'function') {
        observer = new ResizeObserver(correct);
        observer.observe(stream);
        observer.observe(port);
    }
    raf = requestAnimationFrame(function () {
        correct();
        if (!stopped) raf = requestAnimationFrame(correct);
    });
    timer = setTimeout(stop, 3000);
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
    if (!sid || !stream || !ph || ph.sessionId !== sid || !ph.has_older || historyOlderLoading) return;
    historyOlderLoading = true;
    var historyLoadToken = {};
    stream._historyOlderLoadToken = historyLoadToken;
    var prevReplaying = null;
    updateHistorySentinelVisibility();
    var cc = chatContainer;
    var prependViewport = null;
    var loadedOlder = false;
    try {
        var pageTurns = Math.max(1, Math.min(Number(opts.turns) || HISTORY_DIALOGUES_PER_PAGE, 50));
        var url = '/sessions/' + encodeURIComponent(sid)
            + '/messages?turns=' + encodeURIComponent(String(pageTurns))
            + '&before_index=' + ph.range_start
            + '&event_budget=' + encodeURIComponent(String(HISTORY_EVENT_BUDGET));
        var response = await fetchWithTimeout(url, {}, 30000);
        var data = await response.json();
        if (!response.ok || !data || typeof data !== 'object') return;
        // 自动加载请求返回前可能已切换会话，旧页不能插入新的可见消息流。
        if (sid !== currentSessionId || stream !== getVisibleChatStream()
            || stream._historyOlderLoadToken !== historyLoadToken) return;
        prevReplaying = replayingMessages;
        replayingMessages = true;
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
            // fetch 期间用户仍可能滚动，所以必须在真正插入前才记录视口。
            prependViewport = captureHistoryPrependViewport(stream, cc, sid);
            stream.insertBefore(frag, sen ? sen.nextSibling : stream.firstChild);
        }
        loadedOlder = true;
        if (typeof mergeAdjacentExecutionGroups === 'function') mergeAdjacentExecutionGroups(stream);
        setSessionHistoryPaging({
            sessionId: sid,
            total: typeof data.total === 'number' ? data.total : ph.total,
            range_start: typeof data.range_start === 'number' ? data.range_start : ph.range_start,
            range_end: ph.range_end,
            has_older: !!data.has_older,
            has_newer: !!ph.has_newer,
            manual_history: false,
        });
    } catch (e) {
        console.error('加载更早消息失败:', e);
    } finally {
        if (stream._historyOlderLoadToken === historyLoadToken) {
            delete stream._historyOlderLoadToken;
            if (sid === currentSessionId && stream === getVisibleChatStream()) {
                historyOlderLoading = false;
                updateHistorySentinelVisibility();
            }
        }
        if (loadedOlder) {
            bindExistingLogs(stream);
            if (!opts.keepTocStable) rebuildToc();
            scheduleTocActiveUpdate();
        }
        settleHistoryPrependViewport(prependViewport);
        if (prevReplaying !== null) replayingMessages = prevReplaying;
    }
}

function insertNewEmptyChatStream() { ensureVisibleChatStreamSlot(); }

async function loadHistoryWindowAroundEventIndex(sessionId, eventIndex, opts) {
    opts = opts || {};
    var sid = String(sessionId || '');
    var ei = Number(eventIndex);
    if (!sid || !Number.isFinite(ei)) return false;
    // A running session's ctx.stream is the append target for live SSE. Never
    // replace that DOM with an isolated history window or subsequent output
    // will be inserted in the middle of history. Older pages are prepended by
    // scrollToUserTurnOrLoadOlder instead.
    if (sessionHasLiveHistoryOwner(sid)) return false;
    var prevReplaying = replayingMessages;
    try {
        var turns = Math.max(1, Math.min(Number(opts.turns) || 50, 50));
        var url = '/sessions/' + encodeURIComponent(sid)
            + '/messages?turns=' + encodeURIComponent(String(turns))
            + '&target_index=' + encodeURIComponent(String(Math.floor(ei)));
        var response = await fetch(url);
        var data = await response.json().catch(function () { return null; });
        if (!response.ok || !data || typeof data !== 'object' || !Array.isArray(data.events)) return false;
        if (sid !== currentSessionId) return false;
        // The run may have started while the target window request was in
        // flight, or the local stream-active snapshot may have been stale.
        // Revalidate against the server before mutating the live append owner.
        if (await refreshSessionLiveHistoryOwner(sid)) return false;
        if (sid !== currentSessionId) return false;
        if (!getVisibleChatStream()) ensureVisibleChatStreamSlot();
        var stream = getVisibleChatStream();
        if (!stream) return false;
        emptyChatStreamKeepingStrip(stream);
        var total = Number(data.total) || 0;
        var rangeEnd = Number(data.range_end) || 0;
        var pageMeta = {
            total: total,
            range_start: Number(data.range_start) || 0,
            range_end: rangeEnd,
            has_older: !!data.has_older,
            has_newer: data.has_newer == null ? rangeEnd < total : !!data.has_newer,
        };
        beginMessageReplay(sid, pageMeta);
        setSessionHistoryPaging({
            sessionId: sid,
            total: pageMeta.total,
            range_start: pageMeta.range_start,
            range_end: pageMeta.range_end,
            has_older: !!pageMeta.has_older,
            has_newer: !!pageMeta.has_newer,
        });
        ensureHistorySentinel(stream);
        var ctx = newDomContext(stream);
        ctx.lastUserEventIndex = -1;
        replayingMessages = true;
        for (var i = 0; i < data.events.length; i += 1) {
            var ev = data.events[i];
            if (ev && typeof ev === 'object' && ev.type) {
                reduceAndRenderMessageEvent(ctx, ev, {
                    sessionId: sid,
                    eventIndex: pageMeta.range_start + i,
                    source: 'history-target',
                });
            }
        }
        replayingMessages = prevReplaying;
        bindExistingLogs(stream);
        rebuildToc();
        updateHistorySentinelVisibility();
        return true;
    } catch (e) {
        replayingMessages = prevReplaying;
        console.error('load target history window failed:', e);
        return false;
    }
}

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

function isCompleteLocalRunStream(sessionId, stream) {
    var run = getSessionRunState(sessionId);
    return !!(run && run.ctx && run.ctx.stream === stream
        && stream && stream.dataset
        && stream.dataset.partialBackgroundRun !== '1'
        && stream.dataset.sessionLoadFailed !== '1'
        // An observer stream is complete only after durable history hydration.
        // A local submitted run already contains its optimistic first turn.
        && (stream.dataset.sessionLoadOk === '1' || !run.reattached));
}

function stashVisibleStreamForSession(sessionId, opts) {
    opts = opts || {};
    var sid = String(sessionId || '');
    if (!sid || !offscreenRoot) return false;
    const el = getVisibleChatStream();
    if (!el || !el.parentNode) return false;
    /* A stream owned by this tab's active run is already the authoritative,
       gap-free UI projection even when no history request was needed (notably
       a newly-created session).  Certify it before moving it offscreen so a
       same-page switch can restore the live DOM instead of fetching snapshot. */
    if (opts.certifyLocalRun && isCompleteLocalRunStream(sid, el)) {
        el.dataset.sessionLoadOk = '1';
        delete el.dataset.sessionLoading;
    }
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
        stashVisibleStreamForSession(leavingId, { force: true, certifyLocalRun: true });
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
    const completeLocalRun = isCompleteLocalRunStream(enteringId, st);
    if (st.dataset && (st.dataset.partialBackgroundRun === '1'
        || (st.dataset.sessionLoadOk !== '1' && !completeLocalRun))) {
        abortSessionRun(enteringId, 'reattach-incomplete-background');
        if (st.parentNode) st.remove();
        return false;
    }
    if (completeLocalRun && st.dataset.sessionLoadOk !== '1') {
        st.dataset.sessionLoadOk = '1';
        delete st.dataset.sessionLoading;
    }
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

function scrollCurrentRunningProcessToBottom(sessionId) {
    if (!sessionId || sessionId !== currentSessionId) return;
    var run = getSessionRunState(sessionId);
    var ctx = run && run.ctx;
    var stream = ctx && ctx.stream && ctx.stream.isConnected ? ctx.stream : getVisibleChatStream();
    if (!stream) return;
    var agg = ctx && ctx.currentProcessGroup && ctx.currentProcessGroup.isConnected
        ? ctx.currentProcessGroup
        : null;
    if (!agg) {
        var runningAggs = stream.querySelectorAll('.process-aggregate.is-running');
        agg = runningAggs.length ? runningAggs[runningAggs.length - 1] : null;
    }
    // A restored server-side run may not yet have rebuilt the local run
    // context or the is-running class. Its last process block still owns the
    // newest generated entries, so use it as the authoritative fallback.
    if (!agg) {
        var allAggs = stream.querySelectorAll('.process-aggregate');
        agg = allAggs.length ? allAggs[allAggs.length - 1] : null;
    }
    if (!agg) return;
    if (agg.classList.contains('is-collapsed')) {
        agg.classList.remove('is-collapsed');
        var top = agg.querySelector('.process-aggregate-top');
        if (top) top.setAttribute('aria-expanded', 'true');
    }
    var viewports = [
        agg.querySelector('.process-aggregate-body'),
        agg.querySelector('.process-aggregate-brief'),
    ].filter(function (el) { return !!el; });
    function pinBottom() {
        viewports.forEach(function (el) {
            setScrollTopImmediate(el, el.scrollHeight);
        });
    }
    requestAnimationFrame(function () {
        pinBottom();
        requestAnimationFrame(pinBottom);
    });
}

function restoreCachedSessionScrollPosition(sessionId) {
    if (!chatContainer || !sessionId) return;
    if (sessionId !== currentSessionId) return;
    var restoreEpoch = switchSessionEpoch;
    var running = isSessionRunning(sessionId)
        || (typeof isServerStreamActive === 'function' && isServerStreamActive(sessionId));
    var saved = (typeof getSavedScrollPosition === 'function') ? getSavedScrollPosition(sessionId) : null;
    if (running) {
        setScrollTopImmediate(chatContainer, chatContainer.scrollHeight);
        scrollCurrentRunningProcessToBottom(sessionId);
        streamChatNearBottom = true;
        streamProcNearBottom = true;
        liveAutoFollow = true;
    } else if (saved !== null && Number.isFinite(Number(saved))) {
        setScrollTopImmediate(chatContainer, Number(saved));
    } else {
        setScrollTopImmediate(chatContainer, chatContainer.scrollHeight);
    }
    refreshLiveAutoFollowPins();
    scheduleTocActiveUpdate();
    requestAnimationFrame(function () {
        if (sessionId !== currentSessionId || restoreEpoch !== switchSessionEpoch) return;
        if (running) {
            setScrollTopImmediate(chatContainer, chatContainer.scrollHeight);
            scrollCurrentRunningProcessToBottom(sessionId);
        }
        else if (saved !== null && Number.isFinite(Number(saved))) setScrollTopImmediate(chatContainer, Number(saved));
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
        llmRevealLastTs: 0,
        llmThinkTagMode: 'response',
        llmThinkTagCarry: '',
        llmThinkTagAllowLeading: true,
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
        reactGeneration: 0,
        _seenStreamDeltaKeys: new Set(),
        _toolStreamRenderState: {
            draftRows: new Map(),
            rowsById: new Map(),
            pendingRows: new Map(),
            flushRaf: 0,
        },
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
        var row = ch.closest ? ch.closest('.feed-item') : null;
        if (row && row.classList.contains('feed--llm')) autoCollapseLlmReasoningRow(row);
        scheduleFeedChunkOverflowRefresh(ch);
    });
    if (ctx.llm) {
        const l = ctx.llm;
        l.llmStreamReasoningIter = null;
        l.llmStreamResponseIter = null;
        l.llmStreamReasoningScroller = null;
        l.llmStreamResponseScroller = null;
        l.llmDeltaLastSeq = null;
        l.llmRevealLastTs = 0;
        l.llmThinkTagMode = 'response';
        l.llmThinkTagCarry = '';
        l.llmThinkTagAllowLeading = true;
    }
    var bodies = [];
    if (ctx.currentProcessGroup) {
        var mainBody = ctx.currentProcessGroup.querySelector('.process-aggregate-body');
        if (mainBody) bodies.push(mainBody);
    }
    bodies.forEach(function (body) {
        body.querySelectorAll('.feed-item.feed--llm, .feed-item.feed--llm2').forEach(function (el) {
            var sc = el.querySelector('.feed-chunk-scroller');
            var ch = el.querySelector('.feed-chunk');
            if (sc) {
                if (!sc._llmTextNode || sc._llmTextNode !== sc.firstChild
                    || sc._llmRenderedText !== sc.textContent) {
                    // 已经通过增量写入的节点保留原样，只规范化其他来源的首尾空白行。
                    var norm = trimSurroundingBlankLines(typeof sc._llmRawText === 'string'
                        ? sc._llmRawText : (sc.textContent || ''));
                    sc.textContent = norm;
                    sc._llmTextNode = sc.firstChild;
                    sc._llmRenderedText = sc.textContent;
                }
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
    ev = ev || {};
    if (ev.cleanup_scope === 'none') {
        finalizeLlmStreamChunks(ctx);
        return;
    }
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
        l.llmRevealLastTs = 0;
        l.llmThinkTagMode = 'response';
        l.llmThinkTagCarry = '';
        l.llmThinkTagAllowLeading = true;
    }
    var bodies = [];
    if (ctx.currentProcessGroup) {
        var mainBody = ctx.currentProcessGroup.querySelector('.process-aggregate-body');
        if (mainBody) bodies.push(mainBody);
    }
    var reactIter = ev && ev.react_iter != null && Number.isFinite(Number(ev.react_iter))
        ? String(Math.max(1, Math.floor(Number(ev.react_iter))))
        : '';
    var runId = String((ev && (ev.run_id || ev.runId)) || '');
    var hasScopedAbort = !!(reactIter || runId || (ev && ev.react_generation != null));
    var reactGeneration = ev && ev.react_generation != null && Number.isFinite(Number(ev.react_generation))
        ? String(Math.max(0, Math.floor(Number(ev.react_generation))))
        : (hasScopedAbort ? String(reactGenerationForContext(ctx)) : null);
    function matchesAbortScope(el) {
        if (!el) return false;
        if (reactIter && String(el.getAttribute('data-react-iter') || '') !== reactIter) return false;
        if (reactGeneration !== null && String(el.getAttribute('data-react-generation') || '0') !== reactGeneration) return false;
        var rowRunId = String(el.getAttribute('data-run-id') || '');
        if (runId && rowRunId && rowRunId !== runId) return false;
        return true;
    }
    bodies.forEach(function (body) {
        body.querySelectorAll('.feed-item[data-llm-live-row="1"]').forEach(function (el) {
            if (!matchesAbortScope(el)) return;
            el.remove();
        });
        body.querySelectorAll(
            '.feed-item.feed--tool[data-tool-draft-key], '
            + '.feed-item.feed--tool[data-tool-pending="1"]'
        ).forEach(function (el) {
            if (matchesAbortScope(el)) el.remove();
        });
    });
}

/** Keep the full source for incremental appends and reconnect snapshot replacement. */
function writeLlmStreamText(scroller, raw, part) {
    if (!scroller) return;
    scroller._llmRawText = String(raw || '');
    var row = scroller.closest ? scroller.closest('.feed-item') : null;
    /* 行还在做插入/高度动画（data-smooth-trace-layout-owned）时文字已经流入：动画的
       裁切高度是「插入瞬间」的快照，继续裁切会把新文字切掉，并在动画结束时整行突然
       跳高（窄栏实测裁切 289px、释放瞬间单帧跳 440px）。释放动画，让行高跟随内容。 */
    if (row && row.hasAttribute && row.hasAttribute('data-smooth-trace-layout-owned')
        && typeof cancelSmoothTraceLayoutAnimation === 'function') {
        cancelSmoothTraceLayoutAnimation(row);
    }
    if (part === 'response' && row) row._processBriefRawText = scroller._llmRawText;
    var displayed = trimSurroundingBlankLines(scroller._llmRawText);
    var node = scroller.firstChild;
    var previous = node && node === scroller._llmTextNode
        ? scroller._llmRenderedText
        : (scroller.textContent || '');
    if (displayed !== previous) {
        if (node && node === scroller.lastChild && node.nodeType === 3
            && displayed.indexOf(previous) === 0) {
            node.appendData(displayed.slice(previous.length));
            if (typeof uiPerformance !== 'undefined') uiPerformance.count(currentSessionId, 'text.nodeAppends');
        } else {
            scroller.textContent = displayed;
            if (typeof uiPerformance !== 'undefined') uiPerformance.count(currentSessionId, 'text.nodeReplacements');
        }
    }
    scroller._llmTextNode = scroller.firstChild;
    scroller._llmRenderedText = displayed;
}

function appendLlmRevealedText(scroller, segment, part) {
    var row = scroller.closest ? scroller.closest('.feed-item') : null;
    var head = typeof scroller._llmRawText === 'string' ? scroller._llmRawText
        : (part === 'response' && row && typeof row._processBriefRawText === 'string'
            ? row._processBriefRawText : (scroller.textContent || ''));
    writeLlmStreamText(scroller, head + segment, part);
}

function flushLlmDeltaText(ctx, opts) {
    if (!ctx || !ctx.llm) return;
    opts = opts || {};
    const l = ctx.llm;
    if (typeof flushThinkTagCarry === 'function') flushThinkTagCarry(ctx);
    var smoothCommit = opts.smooth === true && isSmoothStreamActive();
    if (!smoothCommit && l.llmDeltaFlushRaf) {
        cancelAnimationFrame(l.llmDeltaFlushRaf);
        l.llmDeltaFlushRaf = 0;
    }
    var revealedChars = 0;
    if (l.llmPendingReasoningDelta && l.llmStreamReasoningScroller) {
        var reasoningPending = String(l.llmPendingReasoningDelta || '');
        var reasoningTake = smoothCommit
            ? takeSmoothTextPrefix(
                reasoningPending,
                computeSmoothRevealCount(reasoningPending.length, opts.dtMs || 16.67)
            )
            : { segment: reasoningPending, rest: '', count: reasoningPending.length };
        appendLlmRevealedText(l.llmStreamReasoningScroller, reasoningTake.segment, 'reasoning');
        l.llmPendingReasoningDelta = reasoningTake.rest;
        revealedChars += reasoningTake.count;
    } else if (l.llmPendingReasoningDelta && !l.llmStreamReasoningScroller && !smoothCommit) {
        l.llmPendingReasoningDelta = '';
    }
    if (l.llmPendingResponseDelta && l.llmStreamResponseScroller) {
        var responsePending = String(l.llmPendingResponseDelta || '');
        var responseTake = smoothCommit
            ? takeSmoothTextPrefix(
                responsePending,
                computeSmoothRevealCount(responsePending.length, opts.dtMs || 16.67)
            )
            : { segment: responsePending, rest: '', count: responsePending.length };
        appendLlmRevealedText(l.llmStreamResponseScroller, responseTake.segment, 'response');
        l.llmPendingResponseDelta = responseTake.rest;
        revealedChars += responseTake.count;
    } else if (l.llmPendingResponseDelta && !l.llmStreamResponseScroller && !smoothCommit) {
        l.llmPendingResponseDelta = '';
    }
    return revealedChars;
}

function scheduleLlmDeltaFlush(ctx, runSessionId) {
    const l = ctx.llm;
    if (!l || l.llmDeltaFlushRaf) return;
    l.llmDeltaFlushRaf = requestAnimationFrame(function (now) {
        l.llmDeltaFlushRaf = 0;
        var flushStartedAt = performance.now();
        if (!isSmoothStreamActive()) {
            flushLlmDeltaText(ctx);
            followStreamProcessScroll(ctx, runSessionId, 'text');
            return;
        }
        var dtMs = l.llmRevealLastTs > 0
            ? smoothStreamClamp(now - l.llmRevealLastTs, 1, 120)
            : SMOOTH_STREAM_CONFIG.referenceFrameMs;
        if (l.llmRevealLastTs > 0 && typeof uiPerformance !== 'undefined') {
            uiPerformance.sample(runSessionId, 'stream.frameGap', now - l.llmRevealLastTs);
        }
        l.llmRevealLastTs = now;
        var revealed = flushLlmDeltaText(ctx, { smooth: true, dtMs: dtMs }) || 0;
        if (typeof uiPerformance !== 'undefined') {
            uiPerformance.sample(runSessionId, 'stream.flush', performance.now() - flushStartedAt);
            uiPerformance.count(runSessionId, 'stream.revealedCodePoints', revealed);
        }
        followStreamProcessScroll(ctx, runSessionId, 'text');
        if (l.llmPendingReasoningDelta || l.llmPendingResponseDelta) {
            scheduleLlmDeltaFlush(ctx, runSessionId);
        } else {
            l.llmRevealLastTs = 0;
        }
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
    l.llmRevealLastTs = 0;
    l.llmThinkTagMode = 'response';
    l.llmThinkTagCarry = '';
    l.llmThinkTagAllowLeading = true;
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
        // The details column owns the file-open policy now: text files open
        // inline there, everything else still goes to the system app. Older
        // bundles without the dock keep the plain system-open path below.
        if (rel && typeof globalThis !== 'undefined' && globalThis.MyAgentDock
            && typeof globalThis.MyAgentDock.isTextPath === 'function'
            && typeof globalThis.MyAgentDock.openPathSmart === 'function') {
            if (globalThis.MyAgentDock.isTextPath(rel)) {
                globalThis.MyAgentDock.openPathSmart(rel);
                showOpenFileFeedback('已在详情栏打开');
            } else {
                globalThis.MyAgentDock.openPathSmart(rel);
            }
            return;
        }
        var controller = (typeof AbortController !== 'undefined') ? new AbortController() : null;
        var timer = controller ? setTimeout(function () { controller.abort(); }, 8000) : null;
        fetch(workspaceApiUrl('/api/open-workspace-file', { rel: rel }), controller ? { signal: controller.signal } : undefined)
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
        const controller = new AbortController();
        const externalSignal = opts.signal;
        const abortFromExternal = function () { controller.abort(); };
        if (externalSignal) {
            if (externalSignal.aborted) controller.abort();
            else externalSignal.addEventListener('abort', abortFromExternal, { once: true });
        }
        const timer = setTimeout(function () { controller.abort(); }, Math.max(250, Number(opts.timeoutMs) || 5000));
        let r;
        try {
            r = await fetch('/sessions/' + encodeURIComponent(sid) + '/messages/count', {
                signal: controller.signal
            });
        } finally {
            clearTimeout(timer);
            if (externalSignal) externalSignal.removeEventListener('abort', abortFromExternal);
        }
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
    if (!messageInput) return;
    const draftKey = sessionId ? String(sessionId) : NEW_SESSION_DRAFT_KEY;
    draftBySession[draftKey] = messageInput.value;
    persistInputDraft(sessionId, messageInput.value);
}

function restoreInputDraft(sessionId) {
    if (!messageInput) return;
    const draftKey = sessionId ? String(sessionId) : NEW_SESSION_DRAFT_KEY;
    const v = Object.prototype.hasOwnProperty.call(draftBySession, draftKey)
        ? draftBySession[draftKey]
        : readStoredInputDraft(sessionId);
    messageInput.value = v != null ? String(v) : '';
    restoreDraftPathTokens(sessionId, messageInput.value);
    rewriteInputWorkspacePaths();
    autoResizeTextarea();
}

function inputDraftStorageKey(sessionId) {
    const draftKey = sessionId ? String(sessionId) : NEW_SESSION_DRAFT_KEY;
    return LS_INPUT_DRAFT_PREFIX + draftKey;
}

/* 输入框里的绝对路径会被改写成 @基名 胶囊标签，真实路径只存在 inputPathTokenMap 里。
   草稿落盘的是标签形式，不同时持久化标签→路径映射，刷新/切会话后标签就成了死文本，
   再发送时真实路径会被吞掉。 */
function inputDraftPathTokenStorageKey(sessionId) {
    return inputDraftStorageKey(sessionId) + '::path-tokens';
}

/** 取出文本中仍被引用的 标签→真实路径 映射（只保留确实出现过的标签）。 */
function collectDraftPathTokens(text) {
    const source = String(text || '');
    const out = Object.create(null);
    if (!source || typeof inputPathTokenMap === 'undefined') return out;
    Object.keys(inputPathTokenMap).forEach(function (label) {
        if (label && source.indexOf(label) >= 0 && inputPathTokenMap[label]) {
            out[label] = inputPathTokenMap[label];
        }
    });
    return out;
}

function persistDraftPathTokens(sessionId, text) {
    const key = inputDraftPathTokenStorageKey(sessionId);
    const tokens = collectDraftPathTokens(text);
    try {
        if (Object.keys(tokens).length) localStorage.setItem(key, JSON.stringify(tokens));
        else localStorage.removeItem(key);
    } catch (e) { /* ignore */ }
}

/** 恢复草稿前先重建标签映射，让草稿里的 @基名 胶囊重新可用（否则发送会丢路径）。 */
function restoreDraftPathTokens(sessionId, text) {
    const source = String(text || '');
    if (!source || typeof inputPathTokenMap === 'undefined') return;
    let stored = null;
    try {
        stored = JSON.parse(localStorage.getItem(inputDraftPathTokenStorageKey(sessionId)) || 'null');
    } catch (e) {
        stored = null;
    }
    if (!stored || typeof stored !== 'object') return;
    Object.keys(stored).forEach(function (label) {
        const path = String(stored[label] || '');
        if (!label || !path || source.indexOf(label) < 0) return;
        const existing = inputPathTokenMap[label];
        if (existing && typeof normalizeInputPathTokenIdentity === 'function'
            && normalizeInputPathTokenIdentity(existing) !== normalizeInputPathTokenIdentity(path)) return;
        inputPathTokenMap[label] = path;
    });
}

function persistInputDraft(sessionId, value) {
    const draftKey = sessionId ? String(sessionId) : NEW_SESSION_DRAFT_KEY;
    const text = String(value || '');
    draftBySession[draftKey] = text;
    try {
        const key = inputDraftStorageKey(sessionId);
        if (text) {
            localStorage.setItem(key, text);
            persistDraftPathTokens(sessionId, text);
        } else {
            localStorage.removeItem(key);
            localStorage.removeItem(inputDraftPathTokenStorageKey(sessionId));
        }
    } catch (e) { /* ignore */ }
    if (typeof syncSessionDraftBadges === 'function') syncSessionDraftBadges(sessionId);
}

function readStoredInputDraft(sessionId) {
    try {
        return localStorage.getItem(inputDraftStorageKey(sessionId)) || '';
    } catch (e) {
        return '';
    }
}

function removeStoredInputDraft(sessionId) {
    const draftKey = sessionId ? String(sessionId) : NEW_SESSION_DRAFT_KEY;
    delete draftBySession[draftKey];
    try {
        localStorage.removeItem(inputDraftStorageKey(sessionId));
        localStorage.removeItem(inputDraftPathTokenStorageKey(sessionId));
    } catch (e) { /* ignore */ }
    if (typeof syncSessionDraftBadges === 'function') syncSessionDraftBadges(sessionId);
}

function clearStreamPoll() {
    if (streamPollTimer) {
        clearInterval(streamPollTimer);
        streamPollTimer = null;
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
    let pollPending = false;
    streamPollTimer = setInterval(function () {
        if (pollPending) return;
        pollPending = true;
        (async function () {
            try {
            if (currentSessionId !== sid) {
                clearStreamPoll();
                return;
            }
            if (typeof reconcileRunStateFromServer === 'function') {
                await reconcileRunStateFromServer({ silent: true });
            }
            const still = typeof isServerStreamActive === 'function'
                ? isServerStreamActive(sid)
                : isSessionRunning(sid);
            if (!still) {
                clearStreamPoll();
                await loadSessions();
                await ensureFinalVisibleAfterRunIfEnabled(sid, null, {});
                syncSessionListIndicatorClasses();
                setSendButtonState();
                return;
            }
            if (currentSessionId === sid && document.visibilityState === 'visible') {
                syncSessionListIndicatorClasses();
                setSendButtonState();
            }
            } catch (error) {
                console.warn('session stream poll failed:', error);
            } finally {
                pollPending = false;
            }
        })();
    }, 15000);
}

async function scrollToUserTurnOrLoadOlder(eventIndex, opts) {
    opts = opts || {};
    var ei = Number(eventIndex);
    if (!Number.isFinite(ei)) return false;
    var silent = !!opts.silent;
    var scrollBehavior = opts.instant ? 'auto' : 'smooth';
    var viewportOffset = Number(opts.viewportOffset);
    var hasViewportOffset = Number.isFinite(viewportOffset);
    var liveHistoryOwner = isSessionRunning(currentSessionId)
        || (typeof isServerStreamActive === 'function' && isServerStreamActive(currentSessionId));
    var allowFullReload = opts.allowFullReload !== false && !silent && !liveHistoryOwner;
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
    function scrollToWrap(wrap) {
        if (!wrap) return;
        if (!hasViewportOffset || !chatContainer) {
            wrap.scrollIntoView({ behavior: scrollBehavior, block: 'start' });
            return;
        }
        var viewportRect = chatContainer.getBoundingClientRect();
        var wrapRect = wrap.getBoundingClientRect();
        var maxTop = Math.max(0, chatContainer.scrollHeight - chatContainer.clientHeight);
        var targetTop = chatContainer.scrollTop + wrapRect.top - viewportRect.top - viewportOffset;
        targetTop = Math.max(0, Math.min(maxTop, targetTop));
        if (scrollBehavior === 'smooth' && typeof chatContainer.scrollTo === 'function') {
            chatContainer.scrollTo({ top: targetTop, behavior: 'smooth' });
        } else {
            setScrollTopImmediate(chatContainer, targetTop);
        }
    }
    async function loadFullHistoryForTarget(sid) {
        if (!allowFullReload) return;
        if (sid !== currentSessionId || typeof loadSessionMessages !== 'function') return;
        try {
            await loadSessionMessages(sid, 'saved-or-bottom', { full: true });
        } catch (e) {
            console.error('reload full history for toc target failed:', e);
        }
    }
    setTocJumpLoading(true);
    try {
        var wrap = findWrap();
        if (wrap) {
            scrollToWrap(wrap);
            return true;
        }
        var sid = currentSessionId;
        if (allowFullReload) {
            var loadedTargetWindow = await loadHistoryWindowAroundEventIndex(sid, ei, { turns: 50 });
            if (loadedTargetWindow && sid === currentSessionId) {
                wrap = findWrap();
                if (wrap) {
                    scrollToWrap(wrap);
                    return true;
                }
            }
        }
        var safety = 0;
        var olderLoads = 0;
        var pagingCoveredTarget = false;
        while (sid === currentSessionId && safety < 120) {
            safety += 1;
            wrap = findWrap();
            if (wrap) {
                scrollToWrap(wrap);
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
            scrollToWrap(wrap);
            return true;
        }
        if (allowFullReload && sid === currentSessionId && pagingCoveredTarget) {
            await loadFullHistoryForTarget(sid);
            if (sid !== currentSessionId) return false;
            wrap = findWrap();
            if (wrap) {
                wrap.scrollIntoView({ behavior: scrollBehavior, block: 'start' });
                return true;
            }
            rebuildToc();
        }
        if (wrap) wrap.scrollIntoView({ behavior: scrollBehavior, block: 'start' });
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
