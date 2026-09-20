const aggregateChanges = new Map();
const aggregateRecency = [];
let activeAggregate = null;
let drawer = null;
let bar = null;
let resizeObserver = null;
let processObserver = null;
let sessionObserver = null;
let scanTimer = null;
let renderFrame = null;
let viewportFrame = null;
let mountedSessionId = '';
const aggregateOwners = new WeakMap();
let clippingAncestors = new WeakMap();

function zh() {
    return String(document.documentElement.lang || 'zh').toLowerCase().startsWith('zh');
}
function t(cn, en) { return zh() ? cn : en; }
function activeSessionId() {
    const row = document.querySelector('#sessions-list .session-item.active[data-session-id]');
    if (row) return String(row.dataset.sessionId || '');
    if (typeof globalThis.currentSessionId === 'string') return globalThis.currentSessionId;
    return '';
}
function aggregateSessionId(aggregate, detail) {
    if (!aggregate || !aggregate.closest) return '';
    const explicit = String((detail && detail.rootSessionId) || '');
    if (explicit) return explicit;
    const stream = aggregate.closest('.chat-stream');
    if (stream) {
        const streamSession = String(stream.dataset.sessionId || stream.dataset.cacheSessionId || '');
        if (streamSession) return streamSession;
        if (stream.id === 'chat-stream') return mountedSessionId || activeSessionId();
    }
    return '';
}
function aggregateIsCurrent(aggregate) {
    if (!aggregate || !aggregate.isConnected || !mountedSessionId) return false;
    const owner = aggregateOwners.get(aggregate) || aggregateSessionId(aggregate);
    if (owner && owner !== mountedSessionId) return false;
    const stream = aggregate.closest('.chat-stream');
    return Boolean(stream && stream.id === 'chat-stream');
}
function changesOf(aggregate) {
    if (!aggregateChanges.has(aggregate)) aggregateChanges.set(aggregate, new Map());
    return aggregateChanges.get(aggregate);
}
function latestRootTurnId() {
    const stream = document.getElementById('chat-stream');
    if (!stream) return '';
    const turns = stream.querySelectorAll('.msg-wrap--user[data-event-index]');
    if (!turns.length) return '';
    return String(turns[turns.length - 1].getAttribute('data-event-index') || '');
}
function inferredAggregateTurnId(aggregate) {
    if (!aggregate) return '';
    const remembered = String(aggregate.dataset.changeReviewTurnId || '');
    if (remembered) return remembered;
    let sibling = aggregate.previousElementSibling;
    while (sibling) {
        if (sibling.matches && sibling.matches('.msg-wrap--user[data-event-index]')) {
            return String(sibling.getAttribute('data-event-index') || '');
        }
        sibling = sibling.previousElementSibling;
    }
    return latestRootTurnId();
}
function turnKeyOf(aggregate) {
    return String(aggregate && aggregate.dataset.changeReviewTurnToken
        || inferredAggregateTurnId(aggregate) || '');
}
function displayTurnRows(aggregate) {
    const key = turnKeyOf(aggregate);
    const merged = new Map();
    aggregateChanges.forEach(function (_rows, candidate) {
        if (!aggregateIsCurrent(candidate) || turnKeyOf(candidate) !== key) return;
        displayRows(candidate).forEach(function (row) {
            const rowKey = `${row._sessionId || ''}\0${row.snapshot_id || row.path || ''}`;
            const previous = merged.get(rowKey);
            if (!previous || Number(previous.revision || 0) <= Number(row.revision || 0)) merged.set(rowKey, row);
        });
    });
    return Array.from(merged.values());
}
function activeRows(aggregate) {
    return sessionRows(aggregate).filter(function (row) {
        return row.effective !== false && row.reverted !== true;
    });
}
function sessionRows(aggregate) {
    return Array.from(changesOf(aggregate).values()).filter(function (row) {
        return row && row._rootSessionId === mountedSessionId;
    });
}
function displayRows(aggregate) {
    // Everything still actionable or still meaningful to show: net changes
    // plus reverted ones (they can be restored from the same panel).
    return sessionRows(aggregate).filter(function (row) {
        return row.reverted === true || row.effective !== false;
    });
}
export function splitReviewRows(rows) {
    const active = [];
    const reverted = [];
    (Array.isArray(rows) ? rows : []).forEach(function (row) {
        if (!row) return;
        (row.reverted === true ? reverted : active).push(row);
    });
    return { active: active, reverted: reverted };
}
function isExpanded(aggregate) {
    if (!aggregate) return false;
    return !aggregate.classList.contains('is-collapsed');
}
function remember(aggregate) {
    const index = aggregateRecency.indexOf(aggregate);
    if (index >= 0) aggregateRecency.splice(index, 1);
    aggregateRecency.push(aggregate);
}

export function chooseVisibleChangeReviewIndex(metrics) {
    let best = -1;
    (Array.isArray(metrics) ? metrics : []).forEach(function (item, index) {
        if (!item || Number(item.visibleHeight || 0) <= 1 || Number(item.ratio || 0) <= 0) return;
        if (best < 0) { best = index; return; }
        const current = metrics[best];
        const ratioDelta = Number(item.ratio || 0) - Number(current.ratio || 0);
        if (Math.abs(ratioDelta) > 0.001) {
            if (ratioDelta > 0) best = index;
            return;
        }
        const centerDelta = Number(item.centerDistance || 0) - Number(current.centerDistance || 0);
        if (Math.abs(centerDelta) > 0.001) {
            if (centerDelta < 0) best = index;
            return;
        }
        const heightDelta = Number(item.visibleHeight || 0) - Number(current.visibleHeight || 0);
        if (Math.abs(heightDelta) > 0.5) {
            if (heightDelta > 0) best = index;
            return;
        }
        if (Boolean(item.preferred) !== Boolean(current.preferred)) {
            if (item.preferred) best = index;
            return;
        }
        if (Number(item.recency || 0) > Number(current.recency || 0)) best = index;
    });
    return best;
}
function overflowClips(style) {
    return /^(auto|scroll|hidden|clip)$/.test(String(style || '').toLowerCase());
}
function clippingParents(aggregate) {
    const cached = clippingAncestors.get(aggregate);
    if (cached) return cached;
    const parents = [];
    let node = aggregate && aggregate.parentElement;
    while (node && node !== document.documentElement) {
        const style = typeof globalThis.getComputedStyle === 'function'
            ? globalThis.getComputedStyle(node) : null;
        if (style && (overflowClips(style.overflowY) || overflowClips(style.overflow))) parents.push(node);
        node = node.parentElement;
    }
    clippingAncestors.set(aggregate, parents);
    return parents;
}
function visibilityMetric(aggregate) {
    if (!aggregate || !aggregate.getBoundingClientRect) return null;
    const rect = aggregate.getBoundingClientRect();
    const documentHeight = document.documentElement && document.documentElement.clientHeight;
    let top = 0;
    let bottom = Math.max(0, Number(documentHeight || globalThis.innerHeight || 0));
    clippingParents(aggregate).forEach(function (parent) {
        if (!parent.isConnected || !parent.getBoundingClientRect) return;
        const bounds = parent.getBoundingClientRect();
        top = Math.max(top, bounds.top);
        bottom = Math.min(bottom, bounds.bottom);
    });
    const visibleTop = Math.max(top, rect.top);
    const visibleBottom = Math.min(bottom, rect.bottom);
    const visibleHeight = Math.max(0, visibleBottom - visibleTop);
    const availableHeight = Math.max(0, bottom - top);
    const comparableHeight = Math.min(Math.max(0, rect.height), availableHeight);
    return {
        visibleHeight,
        ratio: comparableHeight > 0 ? Math.min(1, visibleHeight / comparableHeight) : 0,
        centerDistance: availableHeight > 0
            ? Math.abs(((visibleTop + visibleBottom) / 2) - ((top + bottom) / 2)) / availableHeight
            : Number.POSITIVE_INFINITY,
        preferred: aggregate === activeAggregate,
        recency: aggregateRecency.indexOf(aggregate),
    };
}
function viewportAggregate() {
    const candidates = [];
    const metrics = [];
    aggregateChanges.forEach(function (_rows, aggregate) {
        if (!aggregateIsCurrent(aggregate) || !isExpanded(aggregate) || !displayRows(aggregate).length) return;
        candidates.push(aggregate);
        metrics.push(visibilityMetric(aggregate));
    });
    const index = chooseVisibleChangeReviewIndex(metrics);
    return index >= 0 ? candidates[index] : null;
}
function syncActiveAggregateToViewport(options) {
    const next = viewportAggregate();
    const changed = next !== activeAggregate;
    activeAggregate = next;
    if (changed && !(options && options.deferRender)) scheduleRender();
    return changed;
}
function scheduleViewportSync() {
    if (viewportFrame !== null) return;
    const enqueue = typeof globalThis.requestAnimationFrame === 'function'
        ? globalThis.requestAnimationFrame.bind(globalThis)
        : function (callback) { return globalThis.setTimeout(callback, 0); };
    viewportFrame = enqueue(function () {
        viewportFrame = null;
        syncActiveAggregateToViewport();
    });
}
export function hasLineStats(row) {
    return row.added != null && row.removed != null
        && Number.isFinite(Number(row.added)) && Number.isFinite(Number(row.removed));
}
function omittedReasonLabel(reason) {
    return reason === 'binary' ? t('二进制', 'binary')
        : reason === 'too_many_lines' ? t('超 20,000 行', 'over 20,000 lines')
        : reason === 'too_complex' ? t('改动过于复杂', 'too complex')
        : reason === 'snapshot_missing' ? t('未保存基线内容', 'no baseline content')
        : t('超过 1 MiB', 'over 1 MiB');
}
export function stats(rows) {
    let added = 0; let removed = 0; let omitted = 0;
    const reasons = {};
    rows.forEach(function (row) {
        if (hasLineStats(row)) {
            added += Number(row.added); removed += Number(row.removed);
            return;
        }
        const reason = String(row.diff_omitted_reason || '');
        if (reason === 'directory') return;
        omitted += 1;
        const key = reason || 'too_large_bytes';
        reasons[key] = (reasons[key] || 0) + 1;
    });
    return { added, removed, omitted, reasons };
}
function statsTitle(value) {
    const lines = [t(
        '统计口径：一条非追问用户输入到下一条非追问用户输入（或链路结束）为一轮；追问不切轮。显示该用户轮内的净变更，已还原或改回原样的改动不计入。',
        'Scope: one user turn runs from a non-follow-up user message to the next such message (or the end of the chain). Follow-ups stay in the same turn. Reverted and no-op changes are excluded.')];
    const reasons = value.reasons || {};
    const breakdown = Object.keys(reasons).filter(function (reason) {
        return reasons[reason];
    }).map(function (reason) {
        return `${omittedReasonLabel(reason)} ${reasons[reason]}`;
    });
    if (breakdown.length) {
        lines.push(t('未统计行数的文件：', 'Files without line stats: ') + breakdown.join(' · '));
    }
    return lines.join('\n');
}
function appendColoredStats(container, value, includeOmitted) {
    if (!container) return;
    const add = document.createElement('span'); add.className = 'change-review-stat-added';
    add.textContent = `+${value.added}`;
    const remove = document.createElement('span'); remove.className = 'change-review-stat-removed';
    remove.textContent = `−${value.removed}`;
    container.append(add, document.createTextNode(' '), remove);
    if (!includeOmitted) return;
    if (value.omitted) {
        container.append(document.createTextNode(
            ` · ${value.omitted} ${t('个文件未统计行数', 'files without line stats')}`));
    }
    container.title = statsTitle(value);
}
function setSummary(container, active, reverted) {
    if (!container) return;
    container.replaceChildren();
    if (!active.length) {
        if (reverted.length) {
            container.append(document.createTextNode(
                `${reverted.length} ${t('个文件已撤销，可恢复', 'files reverted, restorable')}`));
        }
        return;
    }
    const value = stats(active);
    container.append(document.createTextNode(`${active.length} ${t('个文件', 'files')} · `));
    appendColoredStats(container, value, true);
    if (reverted.length) {
        container.append(document.createTextNode(` · ${reverted.length} ${t('已撤销', 'reverted')}`));
    }
}
function updateBadge(aggregate) {
    if (!aggregate || !aggregate.querySelector) return;
    const rows = displayTurnRows(aggregate);
    let badge = aggregate.querySelector('.change-review-process-badge');
    if (!rows.length) {
        if (badge) badge.remove();
        return;
    }
    if (!badge) {
        badge = document.createElement('button');
        badge.type = 'button';
        badge.className = 'change-review-process-badge';
        badge.setAttribute('aria-label', t('查看本轮改动', 'View changes for this turn'));
        badge.addEventListener('click', function (event) {
            event.stopPropagation();
            openDetails();
        });
        const title = aggregate.querySelector('.process-aggregate-title');
        const wrap = aggregate.querySelector('.process-aggregate-title-wrap');
        if (title) title.appendChild(badge);
        else if (wrap) wrap.insertBefore(badge, wrap.querySelector('.process-aggregate-stats'));
    }
    const parts = splitReviewRows(rows);
    badge.replaceChildren();
    if (parts.active.length) {
        appendColoredStats(badge, stats(parts.active), true);
        if (parts.reverted.length) {
            badge.append(document.createTextNode(` · ${parts.reverted.length} ${t('已撤销', 'reverted')}`));
        }
    } else {
        badge.append(document.createTextNode(`${parts.reverted.length} ${t('已撤销', 'reverted')}`));
    }
}
function updateTurnBadges(turnKey) {
    aggregateChanges.forEach(function (_rows, aggregate) {
        if (!turnKey || turnKeyOf(aggregate) === turnKey) updateBadge(aggregate);
    });
}
function formatBytes(value) {
    const number = Number(value) || 0;
    if (number < 1024) return `${number} B`;
    if (number < 1048576) return `${(number / 1024).toFixed(1)} KiB`;
    return `${(number / 1048576).toFixed(1)} MiB`;
}
function button(label, className) {
    const el = document.createElement('button');
    el.type = 'button';
    el.className = className || '';
    el.textContent = label;
    return el;
}
function omittedText(row) {
    const reason = String(row.diff_omitted_reason || '');
    const why = reason === 'directory' ? t('目录结构', 'Directory structure')
        : reason === 'binary' ? t('二进制文件', 'Binary file')
        : reason === 'too_many_lines' ? t('超过 20,000 行', 'More than 20,000 lines')
        : reason === 'too_complex' ? t('改动较复杂，已省略逐行预览；仍可撤销', 'Line preview omitted for complex changes; undo is available')
        : reason === 'snapshot_missing' ? t('未保存基线内容，无法预览或撤销', 'No baseline content was saved; preview and undo are unavailable')
            : t('超过 1 MiB', 'Larger than 1 MiB');
    const before = row.before || {}; const after = row.after || {};
    return `${why} · ${formatBytes(before.bytes)} / ${before.lines || 0} ${t('行', 'lines')} → `
        + `${formatBytes(after.bytes)} / ${after.lines || 0} ${t('行', 'lines')}`;
}
function markRows(snapshotIds, reverted) {
    const ids = new Set(snapshotIds || []);
    aggregateChanges.forEach(function (rows, aggregate) {
        rows.forEach(function (row) {
            if (ids.has(String(row.snapshot_id || ''))) {
                row.reverted = reverted; row.effective = !reverted;
            }
        });
        updateBadge(aggregate);
    });
    updateTurnBadges();
    syncActiveAggregateToViewport({ deferRender: true });
    render();
}
function markReverted(snapshotIds) {
    markRows(snapshotIds, true);
}
function markRestored(snapshotIds) {
    markRows(snapshotIds, false);
}
function renderFile(row, options) {
    options = options || {};
    const reverted = row.reverted === true;
    const item = document.createElement('article'); item.className = 'change-review-file';
    if (reverted) item.classList.add('is-reverted');
    item.dataset.snapshotId = String(row.snapshot_id || '');
    const head = document.createElement('div'); head.className = 'change-review-file-head';
    const toggle = button('', 'change-review-file-toggle');
    toggle.setAttribute('aria-expanded', 'false');
    const path = document.createElement('span'); path.className = 'change-review-path'; path.textContent = row.path || '';
    const count = document.createElement('span'); count.className = 'change-review-count';
    if (!hasLineStats(row)) {
        count.textContent = t('未统计', 'no line stats');
        count.title = omittedText(row);
    } else {
        appendColoredStats(count, { added: Number(row.added) || 0, removed: Number(row.removed) || 0 }, false);
    }
    toggle.append(path, count);
    item.classList.add('change-review-file--link');
    toggle.setAttribute('aria-label', `${t('查看改动', 'View changes')}: ${row.path || ''}`);
    if (reverted) {
        const tag = document.createElement('span');
        tag.className = 'change-review-reverted-tag';
        tag.textContent = t('已撤销', 'Reverted');
        head.append(toggle, tag);
    } else head.append(toggle);
    item.appendChild(head);
    toggle.addEventListener('click', function () {
        if (typeof options.onOpen === 'function') options.onOpen(row);
    });
    return item;
}
function renderReviewHost(host, rows, options) {
    options = options || {};
    const list = host.querySelector('.change-review-list'); list.replaceChildren();
    rows.forEach(function (row) {
        list.appendChild(renderFile(row, {
            onOpen: options.onOpen,
        }));
    });
    const parts = splitReviewRows(rows);
    const summary = host.querySelector('.change-review-summary');
    setSummary(summary, parts.active, parts.reverted);
    const view = host.querySelector('.change-review-view');
    if (view) {
        view.hidden = !options.showView;
        view.onclick = function () { openDetails(); };
    }
}
function shell(className) {
    const host = document.createElement('aside'); host.className = className;
    host.innerHTML = `<div class="change-review-card"><header class="change-review-head">`
        + `<div><strong>${t('改动审查', 'Change review')}</strong><div class="change-review-summary"></div></div>`
        + `</header><div class="change-review-list"></div>`
        + `<footer><button type="button" class="change-review-view">${t('查看', 'View')}</button></footer></div>`;
    return host;
}
function openDetails(selectedRow) {
    const aggregate = activeAggregate;
    const payload = {
        turnId: inferredAggregateTurnId(aggregate),
        turnToken: turnKeyOf(aggregate),
        snapshotId: selectedRow && selectedRow.snapshot_id,
        path: selectedRow && selectedRow.path,
    };
    const open = function () {
        if (globalThis.MyAgentDock && typeof globalThis.MyAgentDock.openChangeReview === 'function') {
            globalThis.MyAgentDock.openChangeReview(payload);
        }
    };
    if (globalThis.MyAgentDock && typeof globalThis.MyAgentDock.openChangeReview === 'function') open();
    else document.addEventListener('myagent:dock-ready', open, { once: true });
}
function hasRoom() {
    const stage = document.querySelector('.chat-stage'); const panel = document.querySelector('.panel-inner');
    if (!stage || !panel) return false;
    const spare = Math.max(0, (stage.getBoundingClientRect().width - panel.getBoundingClientRect().width) / 2);
    const goal = document.getElementById('chat-todo-plan');
    const goalWidth = goal && goal.classList.contains('is-open') ? goal.getBoundingClientRect().width + 12 : 0;
    return spare >= 224 + goalWidth;
}
function updatePlacement(visible) {
    const wide = visible && hasRoom();
    drawer.hidden = !wide; bar.hidden = !visible || wide;
    if (visible && !wide) {
        const parts = splitReviewRows(displayTurnRows(activeAggregate));
        setSummary(bar.querySelector('.change-review-bar-summary'), parts.active, parts.reverted);
    }
}
function render() {
    const rows = activeAggregate ? displayTurnRows(activeAggregate) : [];
    const visible = Boolean(activeAggregate && aggregateIsCurrent(activeAggregate) && rows.length
        && isExpanded(activeAggregate));
    if (visible) renderReviewHost(drawer, rows, {
        showView: true,
        onOpen: openDetails,
    });
    updatePlacement(visible);
}
function scheduleRender() {
    if (renderFrame !== null) return;
    const enqueue = typeof globalThis.requestAnimationFrame === 'function'
        ? globalThis.requestAnimationFrame.bind(globalThis)
        : function (callback) { return globalThis.setTimeout(callback, 0); };
    renderFrame = enqueue(function () {
        renderFrame = null;
        render();
    });
}
function scheduleScanExisting() {
    if (scanTimer !== null) return;
    scanTimer = globalThis.setTimeout(function () {
        scanTimer = null;
        scanExisting();
    }, 0);
}
export function acceptChangeUpdate(old, raw) {
    if (!old) return true;
    // Revisions restart at 1 for every run.  Only a stale event for the same
    // snapshot may be ignored; a different snapshot is a newer run's record
    // and must replace the previous one even at a lower revision.
    if (!old.snapshot_id || !raw || !raw.snapshot_id) return true;
    if (String(old.snapshot_id) !== String(raw.snapshot_id)) return true;
    return !(Number(old.revision || 0) > Number(raw.revision || 0));
}
function applyTool(detail, options) {
    options = options || {};
    const event = detail && detail.event; const aggregate = detail && detail.aggregate;
    const incoming = event && event.ui && Array.isArray(event.ui.changes) ? event.ui.changes : [];
    if (!incoming.length) return false;
    if (!aggregate) {
        // 工具行已渲染但过程框尚未就绪（或正在移动）：安排一次重扫，尽快补挂改动统计，
        // 避免要等到下一个工具事件/整段重放才出现 +- 数字。
        scheduleScanExisting();
        return false;
    }
    const ownerSessionId = aggregateSessionId(aggregate, detail);
    if (!ownerSessionId || ownerSessionId !== mountedSessionId || !aggregateIsCurrent(aggregate)) {
        if (!ownerSessionId || ownerSessionId === mountedSessionId) scheduleScanExisting();
        return false;
    }
    aggregateOwners.set(aggregate, ownerSessionId);
    aggregate.dataset.changeReviewSessionId = ownerSessionId;
    const fallbackTurnId = inferredAggregateTurnId(aggregate);
    const incomingTurnToken = String((incoming[0] && incoming[0].turn_id) || fallbackTurnId || '');
    if (fallbackTurnId) aggregate.dataset.changeReviewTurnId = fallbackTurnId;
    if (incomingTurnToken) aggregate.dataset.changeReviewTurnToken = incomingTurnToken;
    const rows = changesOf(aggregate);
    incoming.forEach(function (raw) {
        if (!raw || !raw.snapshot_id || !raw.path) return;
        const old = rows.get(String(raw.path).toLowerCase());
        if (!acceptChangeUpdate(old, raw)) return;
        const enriched = Object.assign({}, raw, {
            _sessionId: String(detail.sessionId || ''),
            _rootSessionId: ownerSessionId,
            _turnId: fallbackTurnId,
            _turnToken: String(raw.turn_id || incomingTurnToken || fallbackTurnId),
        });
        rows.set(String(raw.path).toLowerCase(), enriched);
        if (globalThis.MyAgentDock && typeof globalThis.MyAgentDock.registerChangeReviewRows === 'function') {
            globalThis.MyAgentDock.registerChangeReviewRows({ sessionId: ownerSessionId, rows: [enriched] });
        }
    });
    remember(aggregate); updateTurnBadges(turnKeyOf(aggregate));
    if (!options.deferRender) {
        syncActiveAggregateToViewport({ deferRender: true });
        scheduleRender();
    }
    return true;
}
function onToggle(detail) {
    const aggregate = detail && detail.aggregate;
    if (!aggregate || !aggregateChanges.has(aggregate) || !aggregateIsCurrent(aggregate)) return;
    if (detail.expanded && displayRows(aggregate).length) remember(aggregate);
    syncActiveAggregateToViewport({ deferRender: true });
    render();
}
function onUiEvent(detail) {
    const event = detail && detail.event;
    const ownerSessionId = String((detail && detail.rootSessionId) || (detail && detail.sessionId) || '');
    if (ownerSessionId && ownerSessionId !== mountedSessionId) return;
    if (event && event.type === 'file_changes_reverted') markReverted(event.snapshot_ids || []);
    if (event && event.type === 'file_changes_restored') markRestored(event.snapshot_ids || []);
}
function scanExisting() {
    let found = false;
    const roots = [];
    const stream = document.getElementById('chat-stream');
    if (stream) roots.push(stream);
    roots.forEach(function (root) { root.querySelectorAll('.feed-item.feed--tool').forEach(function (row) {
        if (!row._toolCallEvent) return;
        const aggregate = row.closest('.process-aggregate');
        const applied = applyTool({ event: row._toolCallEvent, row, aggregate,
            sessionId: row._toolCallEvent.session_id || mountedSessionId,
            rootSessionId: aggregateSessionId(aggregate) || mountedSessionId },
        { deferRender: true });
        found = found || Boolean(applied);
    }); });
    if (found) {
        syncActiveAggregateToViewport({ deferRender: true });
        scheduleRender();
    }
}
function resetForSession(nextSessionId) {
    if (scanTimer !== null) {
        globalThis.clearTimeout(scanTimer);
        scanTimer = null;
    }
    if (renderFrame !== null) {
        if (typeof globalThis.cancelAnimationFrame === 'function') {
            globalThis.cancelAnimationFrame(renderFrame);
        } else globalThis.clearTimeout(renderFrame);
        renderFrame = null;
    }
    if (viewportFrame !== null) {
        if (typeof globalThis.cancelAnimationFrame === 'function') {
            globalThis.cancelAnimationFrame(viewportFrame);
        } else globalThis.clearTimeout(viewportFrame);
        viewportFrame = null;
    }
    mountedSessionId = String(nextSessionId || '');
    activeAggregate = null;
    aggregateChanges.clear();
    aggregateRecency.splice(0);
    clippingAncestors = new WeakMap();
    render();
}
function mount() {
    const stage = document.querySelector('.chat-stage'); const inner = document.querySelector('.panel-inner');
    if (!stage || !inner) return false;
    drawer = shell('change-review-drawer'); drawer.hidden = true; stage.appendChild(drawer);
    bar = document.createElement('div'); bar.className = 'change-review-bar'; bar.hidden = true;
    bar.innerHTML = `<strong>${t('改动审查', 'Change review')}</strong>`
        + `<span class="change-review-bar-summary"></span><button type="button" class="change-review-view">${t('查看', 'View')}</button>`;
    inner.insertBefore(bar, inner.querySelector('.composer-row'));
    bar.querySelector('.change-review-view').addEventListener('click', function () { openDetails(); });
    // Resizing only changes drawer-vs-bar placement; rebuilding the complete
    // file list on every geometry notification caused ResizeObserver feedback
    // and long main-thread stalls on large histories.
    resizeObserver = typeof ResizeObserver === 'function' ? new ResizeObserver(function () {
        const rows = activeAggregate ? displayTurnRows(activeAggregate) : [];
        updatePlacement(Boolean(activeAggregate && aggregateIsCurrent(activeAggregate)
            && rows.length && isExpanded(activeAggregate)));
        scheduleViewportSync();
    }) : null;
    if (resizeObserver) { resizeObserver.observe(stage); resizeObserver.observe(inner); }
    processObserver = typeof MutationObserver === 'function' ? new MutationObserver(function (mutations) {
        let hasInsertedRows = false;
        let shouldSync = false;
        mutations.forEach(function (mutation) {
            if (mutation.type === 'childList' && mutation.addedNodes && mutation.addedNodes.length) {
                // The compact review drawer is also mounted under chat-stage.
                // Rescan when a real tool row was inserted, or when a process
                // aggregate / its title is (re)built, since both can detach
                // review badges; otherwise a review render would observe
                // itself and spin indefinitely.
                hasInsertedRows = hasInsertedRows || Array.from(mutation.addedNodes).some(function (node) {
                    return node && node.nodeType === 1 && (
                        (node.matches && (node.matches('.feed-item.feed--tool')
                            || node.matches('.process-aggregate')
                            || node.matches('.process-aggregate-title')))
                        || (node.querySelector && (node.querySelector('.feed-item.feed--tool')
                            || node.querySelector('.process-aggregate-title')))
                    );
                });
            }
            // Only the aggregate's own expanded/collapsed class affects which
            // review is active. Streaming text and child-node mutations inside
            // it must not rebuild the review UI.
            if (mutation.type !== 'attributes') return;
            const aggregate = mutation.target && mutation.target.matches
                && mutation.target.matches('.process-aggregate')
                ? mutation.target : null;
            if (!aggregate || !aggregateChanges.has(aggregate) || !aggregateIsCurrent(aggregate)) return;
            shouldSync = true;
            if (isExpanded(aggregate) && activeRows(aggregate).length) remember(aggregate);
        });
        // Historical process bodies are rendered lazily after expansion. Re-read
        // their tool rows so persisted ui.changes become visible immediately.
        if (hasInsertedRows) scheduleScanExisting();
        if (shouldSync) syncActiveAggregateToViewport();
    }) : null;
    if (processObserver) processObserver.observe(stage, {
        subtree: true, attributes: true, childList: true, attributeFilter: ['class'],
    });
    return true;
}

export async function installChatExtension(context) {
    if (!mount()) return;
    mountedSessionId = activeSessionId();
    const toolListener = function (event) { applyTool(event.detail || {}); };
    const toggleListener = function (event) { onToggle(event.detail || {}); };
    const uiListener = function (event) { onUiEvent(event.detail || {}); };
    const reviewStateListener = function (event) {
        const detail = event && event.detail ? event.detail : {};
        markRows(detail.snapshotIds || [], detail.reverted === true);
    };
    const viewportListener = function () { scheduleViewportSync(); };
    const switchSessionView = function (next) {
        next = String(next || '');
        if (next === mountedSessionId) return;
        resetForSession(next);
        scheduleScanExisting();
    };
    const sessionListener = function (event) {
        const detail = event && event.detail ? event.detail : {};
        const active = activeSessionId();
        // Child-agent extension events must not switch the root conversation.
        // The session list's active marker is authoritative for the reader.
        if (detail.sessionId && active && String(detail.sessionId) !== active) return;
        switchSessionView(active || detail.sessionId || '');
    };
    sessionObserver = typeof MutationObserver === 'function' ? new MutationObserver(function () {
        switchSessionView(activeSessionId());
    }) : null;
    const sessions = document.querySelector('#sessions-list');
    if (sessionObserver && sessions) sessionObserver.observe(sessions, {
        subtree: true, attributes: true, childList: true, attributeFilter: ['class'],
    });
    document.addEventListener('myagent:tool-call-rendered', toolListener);
    document.addEventListener('myagent:process-aggregate-toggle', toggleListener);
    document.addEventListener('myagent:ui-event', uiListener);
    document.addEventListener('myagent:change-review-state', reviewStateListener);
    document.addEventListener('myagent:extension-state-changed', sessionListener);
    document.addEventListener('myagent:language-change', render);
    // Scroll events do not bubble, so capture them to cover both the main chat
    // scroller and the sub-agent grid without installing per-panel listeners.
    document.addEventListener('scroll', viewportListener, true);
    if (typeof globalThis.addEventListener === 'function') {
        globalThis.addEventListener('resize', viewportListener);
    }
    // Installing a chat extension is awaited by the page bootstrap. Defer the
    // historical scan so plugin discovery never blocks first paint.
    scheduleScanExisting();
    return function () {
        document.removeEventListener('myagent:tool-call-rendered', toolListener);
        document.removeEventListener('myagent:process-aggregate-toggle', toggleListener);
        document.removeEventListener('myagent:ui-event', uiListener);
        document.removeEventListener('myagent:change-review-state', reviewStateListener);
        document.removeEventListener('myagent:extension-state-changed', sessionListener);
        document.removeEventListener('scroll', viewportListener, true);
        if (typeof globalThis.removeEventListener === 'function') {
            globalThis.removeEventListener('resize', viewportListener);
        }
        if (resizeObserver) resizeObserver.disconnect();
        if (processObserver) processObserver.disconnect();
        if (sessionObserver) sessionObserver.disconnect();
        if (scanTimer !== null) {
            globalThis.clearTimeout(scanTimer);
            scanTimer = null;
        }
        if (renderFrame !== null) {
            if (typeof globalThis.cancelAnimationFrame === 'function') {
                globalThis.cancelAnimationFrame(renderFrame);
            } else globalThis.clearTimeout(renderFrame);
            renderFrame = null;
        }
        if (viewportFrame !== null) {
            if (typeof globalThis.cancelAnimationFrame === 'function') {
                globalThis.cancelAnimationFrame(viewportFrame);
            } else globalThis.clearTimeout(viewportFrame);
            viewportFrame = null;
        }
        document.querySelectorAll('.change-review-process-badge').forEach(function (node) { node.remove(); });
        document.querySelectorAll('[data-change-review-session-id]').forEach(function (node) {
            delete node.dataset.changeReviewSessionId;
        });
        activeAggregate = null; aggregateChanges.clear(); aggregateRecency.splice(0);
        clippingAncestors = new WeakMap();
        [drawer, bar].forEach(function (node) { if (node) node.remove(); });
        drawer = bar = null;
    };
}
