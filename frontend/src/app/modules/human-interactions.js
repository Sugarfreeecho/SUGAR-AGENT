const humanInteractionStoreBySession = Object.create(null);
const HUMAN_INTERACTION_DRAFT_PREFIX = 'myagent-human-interaction-draft:';

function humanInteractionSessionState(sessionId) {
    var sid = String(sessionId || '');
    if (!humanInteractionStoreBySession[sid]) {
        humanInteractionStoreBySession[sid] = {
            interactions: Object.create(null),
            approvals: Object.create(null),
            loaded: false,
        };
    }
    return humanInteractionStoreBySession[sid];
}

function isHumanInteractionEventType(type) {
    var t = String(type || '');
    return t.indexOf('interaction_') === 0 || t.indexOf('approval_') === 0;
}

function humanInteractionKindForEvent(event) {
    return String((event && event.type) || '').indexOf('approval_') === 0 ? 'approval' : 'question';
}

function humanInteractionId(event, kind) {
    return String(kind === 'approval' ? (event.approval_id || '') : (event.interaction_id || ''));
}

function humanInteractionStatusFromEvent(event) {
    var explicit = String((event && event.status) || '');
    if (explicit) return explicit;
    var type = String((event && event.type) || '');
    if (type.endsWith('_resolved')) return 'resolved';
    if (type.endsWith('_cancelled')) return 'cancelled';
    if (type.endsWith('_expired')) return 'expired';
    return 'pending';
}

function applyHumanInteractionEvent(sessionId, event) {
    if (!event || !isHumanInteractionEventType(event.type)) return null;
    var sid = String(sessionId || event.session_id || '');
    if (!sid) return null;
    var kind = humanInteractionKindForEvent(event);
    var id = humanInteractionId(event, kind);
    if (!id) return null;
    var state = humanInteractionSessionState(sid);
    var collection = kind === 'approval' ? state.approvals : state.interactions;
    var previous = collection[id] || {};
    var terminalStatuses = { resolved: true, cancelled: true, expired: true };
    var incomingStatus = humanInteractionStatusFromEvent(event);
    var previousVersion = Number(previous.request_version || 0);
    var incomingVersion = Number(event.request_version || previousVersion || 0);
    if (previousVersion && incomingVersion && incomingVersion < previousVersion) return previous;
    if (terminalStatuses[previous.status] && incomingStatus === 'pending') return previous;
    var record = Object.assign({}, previous, event, {
        kind: kind,
        status: incomingStatus,
    });
    collection[id] = record;
    state.loaded = true;
    syncHumanInteractionSessionSummary(sid);
    updateHumanInteractionBanner(currentSessionId);
    return record;
}

function pendingHumanInteractionRecords(sessionId) {
    var state = humanInteractionSessionState(sessionId);
    var rows = [];
    Object.keys(state.interactions).forEach(function (id) {
        var row = state.interactions[id];
        if (row && row.status === 'pending') rows.push(row);
    });
    Object.keys(state.approvals).forEach(function (id) {
        var row = state.approvals[id];
        if (row && row.status === 'pending') rows.push(row);
    });
    rows.sort(function (a, b) {
        var kindOrder = (a.kind === 'approval' ? 0 : 1) - (b.kind === 'approval' ? 0 : 1);
        if (kindOrder) return kindOrder;
        return String(a.created_at || '').localeCompare(String(b.created_at || ''));
    });
    return rows;
}

function humanInteractionPendingCounts(sessionId) {
    var rows = pendingHumanInteractionRecords(sessionId);
    var questions = rows.filter(function (row) { return row.kind === 'question'; }).length;
    return { questions: questions, approvals: rows.length - questions, total: rows.length };
}

function pendingHumanQuestions(sessionId) {
    return pendingHumanInteractionRecords(sessionId).filter(function (row) { return row.kind === 'question'; });
}

async function confirmAndCancelPendingHumanQuestionsForMessage(sessionId) {
    var sid = String(sessionId || '');
    var rows = pendingHumanQuestions(sid);
    if (!rows.length) return true;
    var confirmed = typeof openUiModal === 'function'
        ? await openUiModal({
            title: '发送新消息并取消当前问题？',
            message: 'Agent 正在等待你的回答。发送新消息会取消当前问题，并用新消息接管当前任务。',
            confirmText: '取消问题并发送',
            cancelText: '返回回答问题',
        })
        : false;
    if (!confirmed) return false;
    try {
        var resolved = await Promise.all(rows.map(async function (row) {
            var response = await fetch('/sessions/' + encodeURIComponent(sid) + '/interactions/' + encodeURIComponent(row.interaction_id) + '/cancel', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ reason: 'superseded_by_user_message' }),
            });
            var data = await response.json();
            if (!response.ok || !data.ok) throw new Error(data.error || ('HTTP ' + response.status));
            return data.interaction || row;
        }));
        resolved.forEach(function (row) {
            clearHumanInteractionDraft(sid, row.interaction_id, row.request_version);
            var record = applyHumanInteractionEvent(sid, Object.assign({ type: 'interaction_cancelled' }, row));
            renderHumanInteractionRecord(record, sid);
        });
        return true;
    } catch (err) {
        if (typeof showUiAlert === 'function') {
            showUiAlert({
                title: '无法发送新消息',
                message: '取消当前问题失败：' + String(err && err.message ? err.message : err),
                variant: 'error',
            });
        }
        return false;
    }
}

function syncHumanInteractionSessionSummary(sessionId) {
    var sid = String(sessionId || '');
    var counts = humanInteractionPendingCounts(sid);
    var session = typeof sessionStore !== 'undefined' ? sessionStore.get(sid) : null;
    if (session) session.pending_human_interactions = counts;
    updateHumanInteractionSessionBadge(sid);
    updateHumanInteractionBanner(currentSessionId);
}

function sessionPendingHumanCounts(sessionId) {
    var sid = String(sessionId || '');
    var state = humanInteractionStoreBySession[sid];
    if (state && state.loaded) return humanInteractionPendingCounts(sid);
    var session = typeof sessionStore !== 'undefined' ? sessionStore.get(sid) : null;
    var pending = session && session.pending_human_interactions;
    var questions = Math.max(0, Number(pending && pending.questions) || 0);
    var approvals = Math.max(0, Number(pending && pending.approvals) || 0);
    var total = Math.max(questions + approvals, Number(pending && pending.total) || 0);
    return { questions: questions, approvals: approvals, total: total };
}

function sessionListForPendingCounts() {
    if (typeof sessionStore !== 'undefined' && sessionStore && typeof sessionStore.list === 'function') {
        return sessionStore.list();
    }
    return [];
}

function globalHumanInteractionPendingCounts() {
    var questions = 0;
    var approvals = 0;
    sessionListForPendingCounts().forEach(function (session) {
        if (!session || !session.id) return;
        var counts = sessionPendingHumanCounts(session.id);
        questions += counts.questions;
        approvals += counts.approvals;
    });
    return { questions: questions, approvals: approvals, total: questions + approvals };
}

function firstSessionWithPendingHumanInteractions() {
    var sessions = sessionListForPendingCounts();
    for (var i = 0; i < sessions.length; i += 1) {
        var session = sessions[i];
        if (session && session.id && sessionPendingHumanCounts(session.id).total > 0) return session;
    }
    return null;
}

function pendingCountDetailText(counts) {
    var parts = [];
    if (counts.approvals > 0) parts.push(counts.approvals + ' 个审批');
    if (counts.questions > 0) parts.push(counts.questions + ' 个回答');
    return parts.join('、') || '无待办';
}

function updateHumanInteractionSessionBadge(sessionId) {
    var sid = String(sessionId || '');
    if (!sid || !sessionsList) return;
    var row = sessionsList.querySelector('.session-item[data-session-id="' + (window.CSS && CSS.escape ? CSS.escape(sid) : sid.replace(/"/g, '\\"')) + '"]');
    if (!row) return;
    var head = row.querySelector('.session-item-head');
    if (!head) return;
    var badge = head.querySelector('.session-human-badge');
    var counts = sessionPendingHumanCounts(sid);
    var count = counts.total;
    if (count <= 0) {
        if (badge) badge.remove();
        row.classList.remove('has-human-pending');
        return;
    }
    if (!badge && count > 0) {
        badge = document.createElement('span');
        badge.className = 'session-human-badge';
        badge.setAttribute('aria-label', '待处理的人机交互');
        var more = head.querySelector('.session-more-wrap');
        head.insertBefore(badge, more || null);
    }
    if (badge) {
        var hasQuestions = counts.questions > 0;
        var hasApprovals = counts.approvals > 0;
        badge.textContent = hasQuestions && hasApprovals
            ? String(count)
            : ((hasQuestions ? '?' : '!') + (count > 1 ? String(count) : ''));
        var badgeLabel = hasQuestions && hasApprovals
            ? ('有 ' + count + ' 项待处理')
            : (hasQuestions ? ('有 ' + count + ' 个问题待回答') : ('有 ' + count + ' 个审批待处理'));
        badge.setAttribute('aria-label', badgeLabel);
        badge.setAttribute('data-ui-tip', badgeLabel);
        if (typeof bindUiHoverTip === 'function') bindUiHoverTip(badge);
    }
    row.classList.add('has-human-pending');
}

function updateAllHumanInteractionSessionBadges() {
    if (!sessionsList) return;
    sessionsList.querySelectorAll('.session-item[data-session-id]').forEach(function (row) {
        updateHumanInteractionSessionBadge(row.dataset.sessionId || '');
    });
    updateHumanInteractionBanner(currentSessionId);
}

function updateHumanInteractionBanner(sessionId) {
    var sid = String(sessionId || currentSessionId || '');
    var banner = document.getElementById('human-interaction-banner');
    if (!banner) return;
    var globalCounts = globalHumanInteractionPendingCounts();
    var sessionCounts = sid ? sessionPendingHumanCounts(sid) : { questions: 0, approvals: 0, total: 0 };
    var visible = globalCounts.total > 0;
    banner.classList.toggle('is-on', visible);
    banner.classList.toggle('hidden', !visible);
    var globalCountEl = banner.querySelector('.human-todo-count[data-scope="global"]');
    var globalDetailEl = banner.querySelector('.human-todo-detail[data-scope="global"]');
    var sessionCountEl = banner.querySelector('.human-todo-count[data-scope="session"]');
    var sessionDetailEl = banner.querySelector('.human-todo-detail[data-scope="session"]');
    if (globalCountEl) globalCountEl.textContent = globalCounts.total + ' 项';
    if (globalDetailEl) globalDetailEl.textContent = pendingCountDetailText(globalCounts);
    if (sessionCountEl) sessionCountEl.textContent = sessionCounts.total + ' 项';
    if (sessionDetailEl) sessionDetailEl.textContent = pendingCountDetailText(sessionCounts);
}

function focusFirstPendingHumanInteraction() {
    var stream = typeof getVisibleChatStream === 'function' ? getVisibleChatStream() : document.getElementById('chat-stream');
    var card = stream && stream.querySelector('.human-interaction-card[data-status="pending"]');
    if (!card) return;
    var needsLayout = false;
    var collapsedRow = card.closest ? card.closest('.feed-item.is-collapsed') : null;
    if (collapsedRow) {
        collapsedRow.classList.remove('is-collapsed');
        collapsedRow.dataset.manualToggle = '1';
        var rowBtn = collapsedRow.querySelector('.feed-row-collapse');
        if (rowBtn) {
            rowBtn.setAttribute('aria-expanded', 'true');
            rowBtn.setAttribute('aria-label', '收起工具行');
        }
        needsLayout = true;
    }
    var collapsedAgg = card.closest ? card.closest('.process-aggregate.is-collapsed') : null;
    if (collapsedAgg) {
        collapsedAgg.classList.remove('is-collapsed');
        var aggTop = collapsedAgg.querySelector('.process-aggregate-top');
        if (aggTop) aggTop.setAttribute('aria-expanded', 'true');
        needsLayout = true;
    }
    if (needsLayout && collapsedAgg) {
        requestAnimationFrame(function () {
            requestAnimationFrame(function () {
                if (typeof syncProcessAggregateHeightUi === 'function') syncProcessAggregateHeightUi(collapsedAgg);
                collapsedAgg.querySelectorAll('.process-aggregate-body .feed-chunk').forEach(function (ch) {
                    if (typeof refreshFeedChunkOverflow === 'function') refreshFeedChunkOverflow(ch);
                });
                if (typeof registerMermaidLazy === 'function') registerMermaidLazy(collapsedAgg);
            });
        });
    }
    requestAnimationFrame(function () {
        card.scrollIntoView({ behavior: 'smooth', block: 'center' });
        var focusTarget = card.querySelector('input:not(:disabled), textarea:not(:disabled), button:not(:disabled)');
        if (focusTarget) focusTarget.focus({ preventScroll: true });
        else {
            card.setAttribute('tabindex', '-1');
            card.focus({ preventScroll: true });
        }
    });
    card.classList.add('is-highlighted');
    setTimeout(function () { card.classList.remove('is-highlighted'); }, 1200);
}

async function handleHumanTodoFloaterAction() {
    var current = String(currentSessionId || '');
    var currentCounts = current ? sessionPendingHumanCounts(current) : { total: 0 };
    if (currentCounts.total > 0) {
        focusFirstPendingHumanInteraction();
        return;
    }
    var target = firstSessionWithPendingHumanInteractions();
    if (!target) return;
    if (typeof switchSession === 'function') {
        await switchSession(target.id, { forceReload: false });
    }
    requestAnimationFrame(function () { focusFirstPendingHumanInteraction(); });
}

function humanInteractionDraftKey(sessionId, interactionId, requestVersion) {
    return HUMAN_INTERACTION_DRAFT_PREFIX + String(sessionId || '') + ':' + String(interactionId || '') + ':' + String(requestVersion || 1);
}

function humanInteractionToolSlot(stream, toolCallId) {
    var tid = String(toolCallId || '');
    if (!stream || !tid || typeof CSS === 'undefined' || !CSS.escape) return null;
    var row = null;
    try {
        row = stream.querySelector('.feed-item.feed--tool[data-tool-call-id="' + CSS.escape(tid) + '"]');
    } catch (e) { row = null; }
    if (!row) return null;
    var slot = row.querySelector('.human-interaction-tool-slot');
    if (!slot) {
        slot = document.createElement('div');
        slot.className = 'human-interaction-tool-slot';
        row.appendChild(slot);
    }
    return slot;
}

function attachHumanInteractionCardsForToolCall(stream, toolCallId) {
    var tid = String(toolCallId || '');
    var slot = humanInteractionToolSlot(stream, tid);
    if (!slot) return false;
    var escaped = (window.CSS && CSS.escape) ? CSS.escape(tid) : tid.replace(/"/g, '\\"');
    var cards = Array.from(stream.querySelectorAll('.human-interaction-card[data-tool-call-id="' + escaped + '"]'));
    cards.forEach(function (card) {
        if (card.parentNode !== slot) slot.appendChild(card);
    });
    return true;
}

function attachAllHumanInteractionCards(stream) {
    if (!stream || !stream.querySelectorAll) return;
    Array.from(stream.querySelectorAll('.human-interaction-card[data-tool-call-id]')).forEach(function (card) {
        var tid = card.getAttribute('data-tool-call-id') || '';
        if (!tid) return;
        var slot = humanInteractionToolSlot(stream, tid);
        if (slot && card.parentNode !== slot) slot.appendChild(card);
    });
}

function autoReviewStatusElement(stream, toolCallId) {
    var slot = humanInteractionToolSlot(stream, toolCallId);
    if (!slot) return null;
    var el = slot.querySelector('.auto-review-status');
    if (!el) {
        el = humanElement('div', 'auto-review-status');
        slot.insertBefore(el, slot.firstChild);
    }
    return el;
}

function renderAutoReviewStatusEvent(ctx, event, runSessionId) {
    var stream = ctx && ctx.stream
        ? ctx.stream
        : (typeof getVisibleChatStream === 'function'
            ? getVisibleChatStream()
            : document.getElementById('chat-stream'));
    var tid = String((event && event.tool_call_id) || '');
    var status = String((event && event.status) || '');
    if (!stream || !tid) {
        var fallback = String((event && event.content) || '');
        if (fallback && typeof appendLog === 'function') appendLog(ctx, fallback, 'status', runSessionId);
        return;
    }
    var el = autoReviewStatusElement(stream, tid);
    if (!el) return;
    el.className = 'auto-review-status';
    el.setAttribute('data-status', status);
    if (status === 'in_progress') {
        el.classList.add('is-in-progress');
        el.appendChild(humanElement('span', 'auto-review-spin'));
        el.appendChild(humanElement(
            'span',
            'auto-review-text',
            '自动审查中：审查 Agent 正在核对你的任务意图与请求风险。'
        ));
        return;
    }
    var approved = status === 'approved';
    var risk = String((event && event.risk) || 'unknown');
    var reason = String((event && event.reason) || '');
    var unknown = risk === 'unknown' || risk === 'timed_out';
    el.classList.add(approved ? 'is-approved' : (unknown ? 'is-timedout' : 'is-denied'));
    var text = humanElement('span', 'auto-review-text');
    var title = humanElement(
        'span',
        'auto-review-title',
        approved
            ? '自动审批已批准'
            : (unknown ? '自动审查不可用（已转人工确认）' : '自动审批已拒绝')
    );
    if (!approved && !unknown) {
        title.appendChild(humanElement('span', 'auto-review-risk', risk));
    }
    text.appendChild(title);
    if (reason) {
        text.appendChild(document.createTextNode('：'));
        text.appendChild(humanElement('span', 'auto-review-reason', reason));
    }
    if (!approved && !unknown) {
        text.appendChild(humanElement(
            'div',
            'auto-review-hint',
            '可人工覆盖本次请求（只此一次，不沉淀规则）'
        ));
    }
    el.appendChild(text);
}

function persistHumanInteractionDraft(card) {
    if (!card || card.dataset.kind !== 'question') return;
    var draft = { selections: {}, others: {}, step: Number(card.dataset.step || 0), updatedAt: Date.now() };
    card.querySelectorAll('.human-question-pane').forEach(function (pane) {
        var qid = pane.dataset.questionId || '';
        draft.selections[qid] = Array.from(pane.querySelectorAll('input[data-option-id]:checked')).map(function (input) {
            return input.dataset.optionId;
        });
        var other = pane.querySelector('.human-other-input');
        draft.others[qid] = other ? other.value : '';
    });
    try { sessionStorage.setItem(humanInteractionDraftKey(card.dataset.sessionId, card.dataset.interactionId, card.dataset.requestVersion), JSON.stringify(draft)); } catch (e) { /* ignore */ }
}

function restoreHumanInteractionDraft(card) {
    if (!card || card.dataset.kind !== 'question') return null;
    var draft = null;
    try { draft = JSON.parse(sessionStorage.getItem(humanInteractionDraftKey(card.dataset.sessionId, card.dataset.interactionId, card.dataset.requestVersion)) || 'null'); } catch (e) { draft = null; }
    if (!draft) return null;
    card.querySelectorAll('.human-question-pane').forEach(function (pane) {
        var qid = pane.dataset.questionId || '';
        var selected = (draft.selections && draft.selections[qid]) || [];
        pane.querySelectorAll('input[data-option-id]').forEach(function (input) {
            input.checked = selected.indexOf(input.dataset.optionId) >= 0;
        });
        var other = pane.querySelector('.human-other-input');
        if (other && draft.others) {
            other.value = draft.others[qid] || '';
            var otherMark = pane.querySelector('.human-other-mark');
            if (otherMark && other.value) otherMark.checked = true;
        }
    });
    return draft;
}

function clearHumanInteractionDraft(sessionId, interactionId, requestVersion) {
    try { sessionStorage.removeItem(humanInteractionDraftKey(sessionId, interactionId, requestVersion)); } catch (e) { /* ignore */ }
}

function humanElement(tag, className, text) {
    var el = document.createElement(tag);
    if (className) el.className = className;
    if (text != null) el.textContent = String(text);
    return el;
}

function appendHumanCardHeader(card, record, kind) {
    var head = humanElement('div', 'human-card-head');
    var icon = humanElement('span', 'human-card-icon', kind === 'approval' ? '!' : '?');
    icon.setAttribute('aria-hidden', 'true');
    var copy = humanElement('div', 'human-card-head-copy');
    copy.appendChild(humanElement('div', 'human-card-kicker', kind === 'approval' ? '安全审批' : '需要你的回答'));
    var title = humanElement('h3', 'human-card-title', kind === 'approval'
        ? (record.title || 'Agent 请求执行操作')
        : ((record.questions && record.questions.length > 1) ? (record.questions.length + ' 个问题待确认') : ((record.questions && record.questions[0] && record.questions[0].header) || '确认下一步')));
    var recordId = String(kind === 'approval' ? (record.approval_id || '') : (record.interaction_id || ''));
    title.id = 'human-card-title-' + recordId.replace(/[^a-zA-Z0-9_-]/g, '-');
    copy.appendChild(title);
    card.setAttribute('aria-labelledby', title.id);
    var statusText = record.status === 'pending'
        ? (kind === 'approval' ? '待审批' : '待回答')
        : ({ resolved: kind === 'approval' ? '已处理' : '已回答', cancelled: '已取消', expired: '已过期' }[record.status] || record.status);
    var status = humanElement('span', 'human-card-status', statusText);
    head.appendChild(icon);
    head.appendChild(copy);
    head.appendChild(status);
    card.appendChild(head);
}

function humanQuestionPaneState(pane) {
    var selected = Array.from(pane.querySelectorAll('input[data-option-id]:checked'));
    var otherMark = pane.querySelector('.human-other-mark');
    var otherInput = pane.querySelector('.human-other-input');
    var otherSelected = !!(otherMark && otherMark.checked);
    var otherText = otherSelected && otherInput ? otherInput.value.trim() : '';
    return {
        selected: selected,
        otherSelected: otherSelected,
        otherText: otherText,
        answered: selected.length > 0 || !!otherText,
        invalidOther: otherSelected && !otherText,
    };
}

function validateHumanQuestionPane(card, pane) {
    var error = card.querySelector('.human-card-error');
    var state = humanQuestionPaneState(pane);
    if (state.invalidOther) {
        if (error) error.textContent = '请输入其他答案。';
        var other = pane.querySelector('.human-other-input');
        if (other) other.focus();
        return false;
    }
    if (!state.answered) {
        if (error) error.textContent = pane.querySelector('input[type="checkbox"]') ? '请至少选择一个选项。' : '请选择一个选项。';
        var firstControl = pane.querySelector('input');
        if (firstControl) firstControl.focus();
        return false;
    }
    if (error) error.textContent = '';
    return true;
}

function setHumanQuestionStep(card, index) {
    var panes = Array.from(card.querySelectorAll('.human-question-pane'));
    if (!panes.length) return;
    var next = Math.max(0, Math.min(Number(index) || 0, panes.length - 1));
    card.dataset.review = '0';
    card.dataset.step = String(next);
    panes.forEach(function (pane, idx) { pane.classList.toggle('is-active', idx === next); });
    card.querySelectorAll('.human-question-tab').forEach(function (tab, idx) {
        tab.classList.toggle('is-active', idx === next);
        tab.classList.toggle('is-answered', humanQuestionPaneState(panes[idx]).answered);
        tab.setAttribute('aria-selected', idx === next ? 'true' : 'false');
        tab.setAttribute('tabindex', idx === next ? '0' : '-1');
    });
    var tabs = card.querySelector('.human-question-tabs');
    if (tabs) tabs.classList.remove('hidden');
    var body = card.querySelector('.human-card-body');
    if (body) body.classList.remove('hidden');
    var review = card.querySelector('.human-question-review');
    if (review) review.classList.add('hidden');
    var progress = card.querySelector('.human-question-progress');
    if (progress) progress.textContent = '问题 ' + (next + 1) + '/' + panes.length + ' · ' + String(panes[next].dataset.questionHeader || '');
    var back = card.querySelector('.human-back-btn');
    var nextBtn = card.querySelector('.human-next-btn');
    var reviewBtn = card.querySelector('.human-review-btn');
    var submit = card.querySelector('.human-submit-btn');
    if (back) {
        back.textContent = '上一步';
        back.classList.toggle('hidden', panes.length === 1);
        back.disabled = next === 0;
    }
    if (nextBtn) nextBtn.classList.toggle('hidden', next >= panes.length - 1);
    if (reviewBtn) reviewBtn.classList.toggle('hidden', panes.length === 1 || next < panes.length - 1);
    if (submit) submit.classList.toggle('hidden', panes.length > 1);
    if (card.dataset.draftReady === '1') persistHumanInteractionDraft(card);
}

function showHumanQuestionReview(card) {
    var panes = Array.from(card.querySelectorAll('.human-question-pane'));
    var invalidIndex = panes.findIndex(function (pane) { return !validateHumanQuestionPane(card, pane); });
    if (invalidIndex >= 0) {
        setHumanQuestionStep(card, invalidIndex);
        return false;
    }
    var review = card.querySelector('.human-question-review');
    if (!review) return false;
    review.innerHTML = '';
    review.appendChild(humanElement('h4', 'human-review-title', '确认回答'));
    panes.forEach(function (pane) {
        var state = humanQuestionPaneState(pane);
        var row = humanElement('div', 'human-review-row');
        row.appendChild(humanElement('div', 'human-review-label', pane.dataset.questionHeader || '问题'));
        var labels = state.selected.map(function (input) {
            var option = input.closest('.human-option');
            var label = option && option.querySelector('.human-option-label');
            return label ? label.textContent : input.dataset.optionId;
        });
        if (state.otherText) labels.push(state.otherText);
        row.appendChild(humanElement('div', 'human-review-value', labels.join('、')));
        review.appendChild(row);
    });
    card.dataset.review = '1';
    var tabs = card.querySelector('.human-question-tabs');
    if (tabs) tabs.classList.add('hidden');
    var body = card.querySelector('.human-card-body');
    if (body) body.classList.add('hidden');
    review.classList.remove('hidden');
    var back = card.querySelector('.human-back-btn');
    if (back) {
        back.classList.remove('hidden');
        back.disabled = false;
        back.textContent = '返回修改';
    }
    var nextBtn = card.querySelector('.human-next-btn');
    if (nextBtn) nextBtn.classList.add('hidden');
    var reviewBtn = card.querySelector('.human-review-btn');
    if (reviewBtn) reviewBtn.classList.add('hidden');
    var submit = card.querySelector('.human-submit-btn');
    if (submit) submit.classList.remove('hidden');
    review.setAttribute('tabindex', '-1');
    review.focus();
    persistHumanInteractionDraft(card);
    return true;
}

function createHumanQuestionCard(record, sessionId) {
    var card = humanElement('article', 'human-interaction-card human-question-card');
    card.dataset.kind = 'question';
    card.dataset.sessionId = sessionId;
    card.dataset.interactionId = String(record.interaction_id || '');
    card.dataset.requestVersion = String(record.request_version || 1);
    appendHumanCardHeader(card, record, 'question');
    var questions = Array.isArray(record.questions) ? record.questions : [];
    if (questions.length > 1) {
        var tabs = humanElement('div', 'human-question-tabs');
        tabs.setAttribute('role', 'tablist');
        questions.forEach(function (question, index) {
            var tab = humanElement('button', 'human-question-tab', question.header || ('问题 ' + (index + 1)));
            tab.type = 'button';
            tab.id = 'human-tab-' + record.interaction_id + '-' + index;
            tab.setAttribute('role', 'tab');
            tab.setAttribute('aria-controls', 'human-pane-' + record.interaction_id + '-' + index);
            tab.addEventListener('click', function () {
                var current = Number(card.dataset.step || 0);
                if (index > current && !validateHumanQuestionPane(card, card.querySelectorAll('.human-question-pane')[current])) return;
                setHumanQuestionStep(card, index);
            });
            tab.addEventListener('keydown', function (event) {
                if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
                event.preventDefault();
                var target = index + (event.key === 'ArrowRight' ? 1 : -1);
                target = Math.max(0, Math.min(target, questions.length - 1));
                var current = Number(card.dataset.step || 0);
                if (target > current && !validateHumanQuestionPane(card, card.querySelectorAll('.human-question-pane')[current])) return;
                setHumanQuestionStep(card, target);
                var targetTab = card.querySelectorAll('.human-question-tab')[target];
                if (targetTab) targetTab.focus();
            });
            tabs.appendChild(tab);
        });
        card.appendChild(tabs);
        card.appendChild(humanElement('div', 'human-question-progress'));
    }
    var body = humanElement('div', 'human-card-body');
    questions.forEach(function (question, qIndex) {
        var pane = humanElement('fieldset', 'human-question-pane');
        pane.id = 'human-pane-' + record.interaction_id + '-' + qIndex;
        pane.setAttribute('role', 'tabpanel');
        if (questions.length > 1) pane.setAttribute('aria-labelledby', 'human-tab-' + record.interaction_id + '-' + qIndex);
        pane.dataset.questionId = String(question.question_id || ('q' + (qIndex + 1)));
        pane.dataset.questionHeader = String(question.header || ('问题 ' + (qIndex + 1)));
        pane.appendChild(humanElement('legend', 'human-question-text', question.question || ''));
        pane.appendChild(humanElement('div', 'human-question-hint', question.multi_select ? '可多选' : '单选'));
        var options = humanElement('div', 'human-options');
        (question.options || []).forEach(function (option, optionIndex) {
            var label = humanElement('label', 'human-option');
            var input = document.createElement('input');
            input.type = question.multi_select ? 'checkbox' : 'radio';
            input.name = 'human-' + record.interaction_id + '-' + pane.dataset.questionId;
            input.dataset.optionId = String(option.option_id || '');
            var copy = humanElement('span', 'human-option-copy');
            copy.appendChild(humanElement('span', 'human-option-label', option.label || ''));
            var description = humanElement('span', 'human-option-description', option.description || '');
            description.id = 'human-option-desc-' + record.interaction_id + '-' + qIndex + '-' + optionIndex;
            input.setAttribute('aria-describedby', description.id);
            copy.appendChild(description);
            if (option.preview) {
                var details = humanElement('details', 'human-option-preview');
                details.appendChild(humanElement('summary', '', '查看预览'));
                details.appendChild(humanElement('pre', '', option.preview));
                copy.appendChild(details);
            }
            label.appendChild(input);
            label.appendChild(copy);
            options.appendChild(label);
        });
        var other = humanElement('label', 'human-option human-option-other');
        var otherMark = document.createElement('input');
        otherMark.type = question.multi_select ? 'checkbox' : 'radio';
        otherMark.name = 'human-' + record.interaction_id + '-' + pane.dataset.questionId;
        otherMark.className = 'human-other-mark';
        var otherCopy = humanElement('span', 'human-option-copy');
        otherCopy.appendChild(humanElement('span', 'human-option-label', '其他'));
        var otherInput = document.createElement('textarea');
        otherInput.className = 'human-other-input';
        otherInput.rows = 2;
        otherInput.maxLength = 2000;
        otherInput.placeholder = '输入你的答案…';
        otherInput.setAttribute('aria-label', '其他答案');
        otherInput.addEventListener('focus', function () { otherMark.checked = true; persistHumanInteractionDraft(card); });
        otherCopy.appendChild(otherInput);
        other.appendChild(otherMark);
        other.appendChild(otherCopy);
        options.appendChild(other);
        options.addEventListener('change', function () { persistHumanInteractionDraft(card); });
        options.addEventListener('input', function () { persistHumanInteractionDraft(card); });
        pane.appendChild(options);
        body.appendChild(pane);
    });
    card.appendChild(body);
    var review = humanElement('section', 'human-question-review hidden');
    review.setAttribute('aria-label', '回答摘要');
    card.appendChild(review);
    var error = humanElement('div', 'human-card-error');
    error.setAttribute('role', 'alert');
    card.appendChild(error);
    var actions = humanElement('div', 'human-card-actions');
    var cancel = humanElement('button', 'human-secondary-btn', '不回答');
    cancel.type = 'button';
    cancel.title = '取消当前问题并让 Agent 继续';
    cancel.addEventListener('click', function () { void cancelHumanQuestion(card); });
    var nav = humanElement('div', 'human-card-nav');
    var back = humanElement('button', 'human-secondary-btn human-back-btn', '上一步');
    back.type = 'button';
    back.addEventListener('click', function () {
        if (card.dataset.review === '1') setHumanQuestionStep(card, questions.length - 1);
        else setHumanQuestionStep(card, Number(card.dataset.step || 0) - 1);
    });
    var next = humanElement('button', 'human-primary-btn human-next-btn', '下一步');
    next.type = 'button';
    next.addEventListener('click', function () {
        var current = Number(card.dataset.step || 0);
        var pane = card.querySelectorAll('.human-question-pane')[current];
        if (validateHumanQuestionPane(card, pane)) setHumanQuestionStep(card, current + 1);
    });
    var reviewButton = humanElement('button', 'human-primary-btn human-review-btn', '确认回答');
    reviewButton.type = 'button';
    reviewButton.addEventListener('click', function () { showHumanQuestionReview(card); });
    var submit = humanElement('button', 'human-primary-btn human-submit-btn', '提交答案');
    submit.type = 'button';
    submit.addEventListener('click', function () { void submitHumanQuestion(card); });
    nav.appendChild(back);
    nav.appendChild(next);
    nav.appendChild(reviewButton);
    nav.appendChild(submit);
    actions.appendChild(cancel);
    actions.appendChild(nav);
    card.appendChild(actions);
    var draft = restoreHumanInteractionDraft(card);
    setHumanQuestionStep(card, draft && Number.isFinite(Number(draft.step)) ? Number(draft.step) : 0);
    card.dataset.draftReady = '1';
    card.addEventListener('keydown', function (event) {
        if (event.key !== 'Enter' || (!event.ctrlKey && !event.metaKey)) return;
        event.preventDefault();
        if (questions.length > 1 && card.dataset.review !== '1') showHumanQuestionReview(card);
        else void submitHumanQuestion(card);
    });
    return card;
}

function collectHumanQuestionAnswers(card) {
    var answers = [];
    var invalidPane = null;
    card.querySelectorAll('.human-question-pane').forEach(function (pane) {
        var selected = Array.from(pane.querySelectorAll('input[data-option-id]:checked')).map(function (input) { return input.dataset.optionId; });
        var otherMark = pane.querySelector('.human-other-mark');
        var otherInput = pane.querySelector('.human-other-input');
        var otherText = otherMark && otherMark.checked && otherInput ? otherInput.value.trim() : '';
        if ((!selected.length && !otherText || (otherMark && otherMark.checked && !otherText)) && !invalidPane) invalidPane = pane;
        answers.push({
            question_id: pane.dataset.questionId || '',
            selected_option_ids: selected,
            other_text: otherText || null,
            notes: null,
        });
    });
    return { answers: answers, invalidPane: invalidPane };
}

function setHumanInteractionSubmitting(card, submitting, label) {
    if (!card) return;
    card.dataset.submitting = submitting ? '1' : '0';
    card.classList.toggle('is-submitting', !!submitting);
    card.setAttribute('aria-busy', submitting ? 'true' : 'false');
    var status = card.querySelector('.human-card-status');
    if (status) {
        if (!status.dataset.defaultLabel) status.dataset.defaultLabel = status.textContent || '';
        status.textContent = submitting ? (label || '正在提交…') : status.dataset.defaultLabel;
    }
    var primary = card.querySelector('.human-submit-btn, .human-allow-btn');
    if (!primary) return;
    if (!primary.dataset.defaultLabel) primary.dataset.defaultLabel = primary.textContent || '';
    primary.textContent = submitting ? (label || '正在提交…') : primary.dataset.defaultLabel;
}

async function submitHumanQuestion(card) {
    if (!card || card.dataset.submitting === '1') return;
    var collected = collectHumanQuestionAnswers(card);
    var error = card.querySelector('.human-card-error');
    if (collected.invalidPane) {
        var panes = Array.from(card.querySelectorAll('.human-question-pane'));
        setHumanQuestionStep(card, panes.indexOf(collected.invalidPane));
        if (error) error.textContent = '请完成当前问题后再提交。';
        return;
    }
    setHumanInteractionSubmitting(card, true, '正在提交…');
    if (error) error.textContent = '';
    try {
        var response = await fetch('/sessions/' + encodeURIComponent(card.dataset.sessionId) + '/interactions/' + encodeURIComponent(card.dataset.interactionId) + '/resolve', {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ answers: collected.answers }),
        });
        var data = await response.json();
        if (!response.ok || !data.ok) throw new Error(data.error || ('HTTP ' + response.status));
        clearHumanInteractionDraft(card.dataset.sessionId, card.dataset.interactionId, card.dataset.requestVersion);
        var record = applyHumanInteractionEvent(card.dataset.sessionId, Object.assign({ type: 'interaction_resolved' }, data.interaction || {}));
        renderHumanInteractionRecord(record, card.dataset.sessionId, card.parentNode);
    } catch (err) {
        setHumanInteractionSubmitting(card, false);
        if (error) error.textContent = '提交失败：' + String(err && err.message ? err.message : err);
    }
}

async function cancelHumanQuestion(card) {
    if (!card || card.dataset.submitting === '1') return;
    setHumanInteractionSubmitting(card, true, '正在取消…');
    try {
        var response = await fetch('/sessions/' + encodeURIComponent(card.dataset.sessionId) + '/interactions/' + encodeURIComponent(card.dataset.interactionId) + '/cancel', {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ reason: 'user_cancelled' }),
        });
        var data = await response.json();
        if (!response.ok || !data.ok) throw new Error(data.error || ('HTTP ' + response.status));
        clearHumanInteractionDraft(card.dataset.sessionId, card.dataset.interactionId, card.dataset.requestVersion);
        var record = applyHumanInteractionEvent(card.dataset.sessionId, Object.assign({ type: 'interaction_cancelled' }, data.interaction || {}));
        renderHumanInteractionRecord(record, card.dataset.sessionId, card.parentNode);
    } catch (err) {
        setHumanInteractionSubmitting(card, false);
        var error = card.querySelector('.human-card-error');
        if (error) error.textContent = '取消失败：' + String(err && err.message ? err.message : err);
    }
}

function createHumanApprovalCard(record, sessionId) {
    var danger = record.approval_level === 'danger';
    var forced = !!record.force_approval;
    var card = humanElement('article', 'human-interaction-card human-approval-card' + (danger ? ' is-danger' : ''));
    card.dataset.kind = 'approval';
    card.dataset.sessionId = sessionId;
    card.dataset.interactionId = String(record.approval_id || '');
    appendHumanCardHeader(card, record, 'approval');
    var body = humanElement('div', 'human-card-body');
    if (record.subtitle) body.appendChild(humanElement('div', 'human-approval-subtitle', record.subtitle));
    body.appendChild(humanElement('div', 'human-approval-message', record.message || '是否允许 Agent 执行此操作？'));
    if (danger && record.consequence) {
        body.appendChild(humanElement('div', 'human-approval-consequence', record.consequence));
    }
    if (record.tool) {
        var detail = humanElement('div', 'human-approval-detail');
        detail.appendChild(humanElement('span', '', '工具'));
        detail.appendChild(humanElement('code', '', record.tool));
        body.appendChild(detail);
    }
    if (!forced && record.rule_pattern) {
        body.appendChild(
            humanElement(
                'div',
                'human-approval-rule-hint',
                '“始终允许此类操作”将保存为长期规则：' + record.rule_pattern
            )
        );
    }
    card.appendChild(body);
    var error = humanElement('div', 'human-card-error');
    error.setAttribute('role', 'alert');
    card.appendChild(error);
    var actions = humanElement('div', 'human-card-actions human-approval-actions');
    var deny = humanElement('button', 'human-secondary-btn human-deny-btn', danger ? '拒绝执行' : '拒绝');
    deny.type = 'button';
    deny.addEventListener('click', function () { void resolveHumanApproval(card, 'deny'); });
    actions.appendChild(deny);
    var cmdRow = null;
    var wsRow = null;
    if (!forced && record.external_workspace_grantable) {
        var cmdGroup = humanElement('div', 'human-approval-group');
        cmdGroup.appendChild(humanElement('span', 'human-approval-group-label', '命令授权'));
        cmdRow = humanElement('div', 'human-approval-group-row');
        cmdGroup.appendChild(cmdRow);
        actions.appendChild(cmdGroup);
        var wsGroup = humanElement('div', 'human-approval-group');
        wsGroup.appendChild(humanElement('span', 'human-approval-group-label', '工作区沙箱外处理权限'));
        wsRow = humanElement('div', 'human-approval-group-row');
        wsGroup.appendChild(wsRow);
        actions.appendChild(wsGroup);
    }
    if (!forced) {
        var sessionAllow = humanElement('button', 'human-secondary-btn', '本任务内允许相同请求');
        sessionAllow.type = 'button';
        sessionAllow.title = '仅在当前任务中，对命令、参数、路径和工作目录完全相同的请求自动放行';
        sessionAllow.addEventListener('click', function () { void resolveHumanApproval(card, 'allow_session'); });
        (cmdRow || actions).appendChild(sessionAllow);
    }
    if (!forced && record.allow_always_available && record.rule_pattern) {
        var always = humanElement('button', 'human-secondary-btn', '始终允许此类操作');
        always.type = 'button';
        if (record.rule_pattern) always.title = '保存为长期规则，后续匹配时自动放行：' + record.rule_pattern;
        always.addEventListener('click', function () { void resolveHumanApproval(card, 'allow_always'); });
        (cmdRow || actions).appendChild(always);
    }
    var allowPrimary = !record.external_workspace_grantable;
    if (!forced && record.external_workspace_grantable) {
        var externalGrant = humanElement('button', 'human-primary-btn human-external-grant-btn', '授权工作区沙箱外处理权限');
        externalGrant.type = 'button';
        externalGrant.title = '一次性授权：写、删除和 Shell 在工作区外的操作以后自动放行';
        externalGrant.addEventListener('click', function () { void resolveHumanApproval(card, 'allow_external_workspace'); });
        wsRow.appendChild(externalGrant);
        var allowOnce = humanElement('button', 'human-secondary-btn human-allow-btn', '允许一次');
        allowOnce.type = 'button';
        allowOnce.title = '仅放行这一次；下一次工作区外操作仍会询问';
        allowOnce.addEventListener('click', function () { void resolveHumanApproval(card, 'allow_once'); });
        cmdRow.appendChild(allowOnce);
    } else {
        var allow = humanElement(
            'button',
            (allowPrimary ? 'human-primary-btn human-allow-btn' : 'human-secondary-btn human-allow-btn'),
            '允许一次'
        );
        allow.type = 'button';
        allow.title = '仅放行这一次；执行后授权立即失效';
        allow.addEventListener('click', function () { void resolveHumanApproval(card, 'allow_once'); });
        actions.appendChild(allow);
    }
    card.appendChild(actions);
    return card;
}

async function resolveHumanApproval(card, decision) {
    if (!card || card.dataset.submitting === '1') return;
    setHumanInteractionSubmitting(card, true, '正在处理…');
    try {
        var response = await fetch('/sessions/' + encodeURIComponent(card.dataset.sessionId) + '/approvals/' + encodeURIComponent(card.dataset.interactionId) + '/resolve', {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ decision: decision }),
        });
        var data = await response.json();
        if (!response.ok || !data.ok) {
            if (data.approval) {
                var staleRecord = applyHumanInteractionEvent(card.dataset.sessionId, Object.assign({ type: 'approval_cancelled' }, data.approval));
                renderHumanInteractionRecord(staleRecord, card.dataset.sessionId, card.parentNode);
                return;
            }
            throw new Error(data.error || ('HTTP ' + response.status));
        }
        var record = applyHumanInteractionEvent(card.dataset.sessionId, Object.assign({ type: 'approval_resolved' }, data.approval || {}));
        renderHumanInteractionRecord(record, card.dataset.sessionId, card.parentNode);
    } catch (err) {
        setHumanInteractionSubmitting(card, false);
        var error = card.querySelector('.human-card-error');
        if (error) error.textContent = '处理失败：' + String(err && err.message ? err.message : err);
    }
}

function createHumanTerminalCard(record, sessionId) {
    var kind = record.kind === 'approval' ? 'approval' : 'question';
    var card = humanElement('article', 'human-interaction-card is-terminal');
    card.dataset.kind = kind;
    card.dataset.sessionId = sessionId;
    card.dataset.interactionId = String(kind === 'approval' ? record.approval_id : record.interaction_id);
    appendHumanCardHeader(card, record, kind);
    var summary = humanElement('div', 'human-terminal-summary');
    if (record.status === 'cancelled') {
        summary.textContent = record.reason || '该请求已取消。';
    } else if (record.status === 'expired') {
        summary.textContent = '该请求已过期。';
    } else if (kind === 'approval') {
        summary.textContent = record.decision === 'deny'
            ? '你已拒绝本次操作。'
            : (record.decision === 'allow_always'
                ? ('已保存长期规则，后续匹配的操作将自动放行。' + (record.rule_pattern ? '（规则：' + record.rule_pattern + '）' : ''))
                : (record.decision === 'allow_session'
                    ? '当前任务内将自动允许完全相同的请求。'
                    : '已允许这一次；执行后授权失效。'));
    } else {
        var answers = Array.isArray(record.answers) ? record.answers : [];
        var questionsById = Object.create(null);
        (record.questions || []).forEach(function (question) {
            questionsById[String(question.question_id || '')] = question;
        });
        answers.forEach(function (answer) {
            var line = humanElement('div', 'human-terminal-answer');
            var values = (answer.selected_labels || []).slice();
            if (answer.other_text) values.push(answer.other_text);
            var question = questionsById[String(answer.question_id || '')] || {};
            line.appendChild(humanElement('span', 'human-terminal-answer-label', question.header || '回答'));
            line.appendChild(humanElement('span', 'human-terminal-answer-value', values.join('、') || '已回答'));
            summary.appendChild(line);
        });
    }
    card.appendChild(summary);
    return card;
}

function renderHumanInteractionRecord(record, sessionId, stream) {
    if (!record) return null;
    var sid = String(sessionId || record.session_id || '');
    var kind = record.kind === 'approval' ? 'approval' : 'question';
    var id = String(kind === 'approval' ? (record.approval_id || '') : (record.interaction_id || ''));
    if (!id) return null;
    stream = stream && stream.querySelectorAll ? stream : (typeof getVisibleChatStream === 'function' ? getVisibleChatStream() : document.getElementById('chat-stream'));
    if (!stream) return null;
    var existing = Array.from(stream.querySelectorAll('.human-interaction-card')).find(function (card) {
        return card.dataset.kind === kind && card.dataset.interactionId === id;
    });
    var restoreFocus = !!(existing && existing.contains(document.activeElement));
    var card = record.status === 'pending'
        ? (kind === 'approval' ? createHumanApprovalCard(record, sid) : createHumanQuestionCard(record, sid))
        : createHumanTerminalCard(record, sid);
    card.dataset.status = record.status || 'pending';
    var toolCallId = String(record.tool_call_id || '');
    if (toolCallId) card.dataset.toolCallId = toolCallId;
    if (existing && existing.parentNode) existing.parentNode.replaceChild(card, existing);
    else {
        var slot = humanInteractionToolSlot(stream, toolCallId);
        (slot || stream).appendChild(card);
    }
    if (toolCallId) {
        attachHumanInteractionCardsForToolCall(stream, toolCallId);
    }
    if (restoreFocus && record.status !== 'pending') {
        card.setAttribute('tabindex', '-1');
        requestAnimationFrame(function () { card.focus({ preventScroll: true }); });
    }
    return card;
}

function renderHumanInteractionEvent(ctx, event, runSessionId) {
    var sid = String(runSessionId || event.session_id || currentSessionId || '');
    var record = applyHumanInteractionEvent(sid, event);
    var stream = ctx && ctx.stream ? ctx.stream : null;
    return renderHumanInteractionRecord(record, sid, stream);
}

function renderPendingHumanInteractions(sessionId) {
    var sid = String(sessionId || '');
    if (!sid || sid !== String(currentSessionId || '')) return;
    var stream = typeof getVisibleChatStream === 'function' ? getVisibleChatStream() : document.getElementById('chat-stream');
    pendingHumanInteractionRecords(sid).forEach(function (record) { renderHumanInteractionRecord(record, sid, stream); });
    if (typeof attachAllHumanInteractionCards === 'function') attachAllHumanInteractionCards(stream);
    updateHumanInteractionBanner(sid);
}

async function refreshHumanInteractions(sessionId, options) {
    var sid = String(sessionId || '');
    if (!sid) return false;
    options = options || {};
    try {
        var responses = await Promise.all([
            fetch('/sessions/' + encodeURIComponent(sid) + '/interactions?status=pending'),
            fetch('/sessions/' + encodeURIComponent(sid) + '/approvals?status=pending'),
        ]);
        if (!responses[0].ok || !responses[1].ok) throw new Error('HTTP ' + responses[0].status + '/' + responses[1].status);
        var payloads = await Promise.all([responses[0].json(), responses[1].json()]);
        var state = humanInteractionSessionState(sid);
        state.interactions = Object.create(null);
        state.approvals = Object.create(null);
        (payloads[0].interactions || []).forEach(function (row) {
            row.kind = 'question';
            state.interactions[String(row.interaction_id || '')] = row;
        });
        (payloads[1].approvals || []).forEach(function (row) {
            row.kind = 'approval';
            state.approvals[String(row.approval_id || '')] = row;
        });
        state.loaded = true;
        syncHumanInteractionSessionSummary(sid);
        if (options.render !== false && sid === String(currentSessionId || '')) renderPendingHumanInteractions(sid);
        return true;
    } catch (err) {
        console.error('加载待处理交互失败:', err);
        return false;
    }
}

(function bindHumanInteractionBanner() {
    var button = document.getElementById('human-interaction-banner-btn');
    if (button) button.addEventListener('click', function () { void handleHumanTodoFloaterAction(); });
})();
