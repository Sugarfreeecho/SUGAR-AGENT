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
    var record = Object.assign({}, previous, event, {
        kind: kind,
        status: humanInteractionStatusFromEvent(event),
    });
    collection[id] = record;
    state.loaded = true;
    syncHumanInteractionSessionSummary(sid);
    if (sid === String(currentSessionId || '')) updateHumanInteractionBanner(sid);
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
        return String(a.created_at || '').localeCompare(String(b.created_at || ''));
    });
    return rows;
}

function humanInteractionPendingCounts(sessionId) {
    var rows = pendingHumanInteractionRecords(sessionId);
    var questions = rows.filter(function (row) { return row.kind === 'question'; }).length;
    return { questions: questions, approvals: rows.length - questions, total: rows.length };
}

function syncHumanInteractionSessionSummary(sessionId) {
    var sid = String(sessionId || '');
    var counts = humanInteractionPendingCounts(sid);
    var session = typeof sessionStore !== 'undefined' ? sessionStore.get(sid) : null;
    if (session) session.pending_human_interactions = counts;
    updateHumanInteractionSessionBadge(sid);
}

function sessionPendingHumanCount(sessionId) {
    var sid = String(sessionId || '');
    var state = humanInteractionStoreBySession[sid];
    if (state && state.loaded) return humanInteractionPendingCounts(sid).total;
    var session = typeof sessionStore !== 'undefined' ? sessionStore.get(sid) : null;
    return Math.max(0, Number(session && session.pending_human_interactions && session.pending_human_interactions.total) || 0);
}

function updateHumanInteractionSessionBadge(sessionId) {
    var sid = String(sessionId || '');
    if (!sid || !sessionsList) return;
    var row = sessionsList.querySelector('.session-item[data-session-id="' + (window.CSS && CSS.escape ? CSS.escape(sid) : sid.replace(/"/g, '\\"')) + '"]');
    if (!row) return;
    var head = row.querySelector('.session-item-head');
    if (!head) return;
    var badge = head.querySelector('.session-human-badge');
    var count = sessionPendingHumanCount(sid);
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
        badge.textContent = String(count);
        badge.setAttribute('data-ui-tip', count + ' 个待处理请求');
        if (typeof bindUiHoverTip === 'function') bindUiHoverTip(badge);
    }
    row.classList.add('has-human-pending');
}

function updateAllHumanInteractionSessionBadges() {
    if (!sessionsList) return;
    sessionsList.querySelectorAll('.session-item[data-session-id]').forEach(function (row) {
        updateHumanInteractionSessionBadge(row.dataset.sessionId || '');
    });
}

function updateHumanInteractionBanner(sessionId) {
    var sid = String(sessionId || currentSessionId || '');
    var banner = document.getElementById('human-interaction-banner');
    if (!banner) return;
    var rows = sid ? pendingHumanInteractionRecords(sid) : [];
    banner.classList.toggle('is-on', rows.length > 0);
    banner.classList.toggle('hidden', rows.length === 0);
    var text = banner.querySelector('.human-interaction-banner-msg');
    if (text) {
        var q = rows.filter(function (row) { return row.kind === 'question'; }).length;
        var a = rows.length - q;
        var parts = [];
        if (q) parts.push(q + ' 个问题');
        if (a) parts.push(a + ' 个审批');
        text.textContent = rows.length ? ('Agent 正在等待你处理' + parts.join('、')) : '';
    }
}

function focusFirstPendingHumanInteraction() {
    var stream = typeof getVisibleChatStream === 'function' ? getVisibleChatStream() : document.getElementById('chat-stream');
    var card = stream && stream.querySelector('.human-interaction-card[data-status="pending"]');
    if (card) {
        card.scrollIntoView({ behavior: 'smooth', block: 'center' });
        card.classList.add('is-highlighted');
        setTimeout(function () { card.classList.remove('is-highlighted'); }, 1200);
    }
}

function humanInteractionDraftKey(sessionId, interactionId) {
    return HUMAN_INTERACTION_DRAFT_PREFIX + String(sessionId || '') + ':' + String(interactionId || '');
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
    Array.from(stream.querySelectorAll('.human-interaction-card[data-tool-call-id="' + escaped + '"]')).forEach(function (card) {
        if (card.parentNode !== slot) slot.appendChild(card);
    });
    return true;
}

function persistHumanInteractionDraft(card) {
    if (!card || card.dataset.kind !== 'question') return;
    var draft = { selections: {}, others: {} };
    card.querySelectorAll('.human-question-pane').forEach(function (pane) {
        var qid = pane.dataset.questionId || '';
        draft.selections[qid] = Array.from(pane.querySelectorAll('input[data-option-id]:checked')).map(function (input) {
            return input.dataset.optionId;
        });
        var other = pane.querySelector('.human-other-input');
        draft.others[qid] = other ? other.value : '';
    });
    try { sessionStorage.setItem(humanInteractionDraftKey(card.dataset.sessionId, card.dataset.interactionId), JSON.stringify(draft)); } catch (e) { /* ignore */ }
}

function restoreHumanInteractionDraft(card) {
    if (!card || card.dataset.kind !== 'question') return;
    var draft = null;
    try { draft = JSON.parse(sessionStorage.getItem(humanInteractionDraftKey(card.dataset.sessionId, card.dataset.interactionId)) || 'null'); } catch (e) { draft = null; }
    if (!draft) return;
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
}

function clearHumanInteractionDraft(sessionId, interactionId) {
    try { sessionStorage.removeItem(humanInteractionDraftKey(sessionId, interactionId)); } catch (e) { /* ignore */ }
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
    copy.appendChild(humanElement('div', 'human-card-title', kind === 'approval'
        ? (record.title || 'Agent 请求执行操作')
        : ((record.questions && record.questions.length > 1) ? (record.questions.length + ' 个问题待确认') : ((record.questions && record.questions[0] && record.questions[0].header) || '确认下一步'))));
    var status = humanElement('span', 'human-card-status', record.status === 'pending' ? '等待中' : ({ resolved: '已处理', cancelled: '已取消', expired: '已过期' }[record.status] || record.status));
    head.appendChild(icon);
    head.appendChild(copy);
    head.appendChild(status);
    card.appendChild(head);
}

function setHumanQuestionStep(card, index) {
    var panes = Array.from(card.querySelectorAll('.human-question-pane'));
    if (!panes.length) return;
    var next = Math.max(0, Math.min(Number(index) || 0, panes.length - 1));
    card.dataset.step = String(next);
    panes.forEach(function (pane, idx) { pane.classList.toggle('is-active', idx === next); });
    card.querySelectorAll('.human-question-tab').forEach(function (tab, idx) {
        tab.classList.toggle('is-active', idx === next);
        tab.setAttribute('aria-selected', idx === next ? 'true' : 'false');
    });
    var back = card.querySelector('.human-back-btn');
    var nextBtn = card.querySelector('.human-next-btn');
    var submit = card.querySelector('.human-submit-btn');
    if (back) back.disabled = next === 0;
    if (nextBtn) nextBtn.classList.toggle('hidden', next >= panes.length - 1);
    if (submit) submit.classList.toggle('hidden', next < panes.length - 1);
}

function createHumanQuestionCard(record, sessionId) {
    var card = humanElement('section', 'human-interaction-card human-question-card');
    card.dataset.kind = 'question';
    card.dataset.sessionId = sessionId;
    card.dataset.interactionId = String(record.interaction_id || '');
    appendHumanCardHeader(card, record, 'question');
    var questions = Array.isArray(record.questions) ? record.questions : [];
    if (questions.length > 1) {
        var tabs = humanElement('div', 'human-question-tabs');
        tabs.setAttribute('role', 'tablist');
        questions.forEach(function (question, index) {
            var tab = humanElement('button', 'human-question-tab', question.header || ('问题 ' + (index + 1)));
            tab.type = 'button';
            tab.addEventListener('click', function () { setHumanQuestionStep(card, index); });
            tabs.appendChild(tab);
        });
        card.appendChild(tabs);
    }
    var body = humanElement('div', 'human-card-body');
    questions.forEach(function (question, qIndex) {
        var pane = humanElement('div', 'human-question-pane');
        pane.dataset.questionId = String(question.question_id || ('q' + (qIndex + 1)));
        pane.appendChild(humanElement('div', 'human-question-text', question.question || ''));
        pane.appendChild(humanElement('div', 'human-question-hint', question.multi_select ? '可多选' : '单选'));
        var options = humanElement('div', 'human-options');
        (question.options || []).forEach(function (option) {
            var label = humanElement('label', 'human-option');
            var input = document.createElement('input');
            input.type = question.multi_select ? 'checkbox' : 'radio';
            input.name = 'human-' + record.interaction_id + '-' + pane.dataset.questionId;
            input.dataset.optionId = String(option.option_id || '');
            var copy = humanElement('span', 'human-option-copy');
            copy.appendChild(humanElement('span', 'human-option-label', option.label || ''));
            copy.appendChild(humanElement('span', 'human-option-description', option.description || ''));
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
    var error = humanElement('div', 'human-card-error');
    error.setAttribute('role', 'alert');
    card.appendChild(error);
    var actions = humanElement('div', 'human-card-actions');
    var cancel = humanElement('button', 'human-secondary-btn', '取消提问');
    cancel.type = 'button';
    cancel.addEventListener('click', function () { void cancelHumanQuestion(card); });
    var nav = humanElement('div', 'human-card-nav');
    var back = humanElement('button', 'human-secondary-btn human-back-btn', '上一步');
    back.type = 'button';
    back.addEventListener('click', function () { setHumanQuestionStep(card, Number(card.dataset.step || 0) - 1); });
    var next = humanElement('button', 'human-primary-btn human-next-btn', '下一步');
    next.type = 'button';
    next.addEventListener('click', function () { setHumanQuestionStep(card, Number(card.dataset.step || 0) + 1); });
    var submit = humanElement('button', 'human-primary-btn human-submit-btn', '提交答案');
    submit.type = 'button';
    submit.addEventListener('click', function () { void submitHumanQuestion(card); });
    nav.appendChild(back);
    nav.appendChild(next);
    nav.appendChild(submit);
    actions.appendChild(cancel);
    actions.appendChild(nav);
    card.appendChild(actions);
    restoreHumanInteractionDraft(card);
    setHumanQuestionStep(card, 0);
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
        if (!selected.length && !otherText && !invalidPane) invalidPane = pane;
        answers.push({
            question_id: pane.dataset.questionId || '',
            selected_option_ids: selected,
            other_text: otherText || null,
            notes: null,
        });
    });
    return { answers: answers, invalidPane: invalidPane };
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
    card.dataset.submitting = '1';
    card.classList.add('is-submitting');
    if (error) error.textContent = '';
    try {
        var response = await fetch('/sessions/' + encodeURIComponent(card.dataset.sessionId) + '/interactions/' + encodeURIComponent(card.dataset.interactionId) + '/resolve', {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ answers: collected.answers }),
        });
        var data = await response.json();
        if (!response.ok || !data.ok) throw new Error(data.error || ('HTTP ' + response.status));
        clearHumanInteractionDraft(card.dataset.sessionId, card.dataset.interactionId);
        var record = applyHumanInteractionEvent(card.dataset.sessionId, Object.assign({ type: 'interaction_resolved' }, data.interaction || {}));
        renderHumanInteractionRecord(record, card.dataset.sessionId, card.parentNode);
    } catch (err) {
        card.dataset.submitting = '0';
        card.classList.remove('is-submitting');
        if (error) error.textContent = '提交失败：' + String(err && err.message ? err.message : err);
    }
}

async function cancelHumanQuestion(card) {
    if (!card || card.dataset.submitting === '1') return;
    card.dataset.submitting = '1';
    card.classList.add('is-submitting');
    try {
        var response = await fetch('/sessions/' + encodeURIComponent(card.dataset.sessionId) + '/interactions/' + encodeURIComponent(card.dataset.interactionId) + '/cancel', {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ reason: 'user_cancelled' }),
        });
        var data = await response.json();
        if (!response.ok || !data.ok) throw new Error(data.error || ('HTTP ' + response.status));
        clearHumanInteractionDraft(card.dataset.sessionId, card.dataset.interactionId);
        var record = applyHumanInteractionEvent(card.dataset.sessionId, Object.assign({ type: 'interaction_cancelled' }, data.interaction || {}));
        renderHumanInteractionRecord(record, card.dataset.sessionId, card.parentNode);
    } catch (err) {
        card.dataset.submitting = '0';
        card.classList.remove('is-submitting');
        var error = card.querySelector('.human-card-error');
        if (error) error.textContent = '取消失败：' + String(err && err.message ? err.message : err);
    }
}

function createHumanApprovalCard(record, sessionId) {
    var card = humanElement('section', 'human-interaction-card human-approval-card');
    card.dataset.kind = 'approval';
    card.dataset.sessionId = sessionId;
    card.dataset.interactionId = String(record.approval_id || '');
    appendHumanCardHeader(card, record, 'approval');
    var body = humanElement('div', 'human-card-body');
    if (record.subtitle) body.appendChild(humanElement('div', 'human-approval-subtitle', record.subtitle));
    body.appendChild(humanElement('div', 'human-approval-message', record.message || '是否允许 Agent 执行此操作？'));
    if (record.tool) {
        var detail = humanElement('div', 'human-approval-detail');
        detail.appendChild(humanElement('span', '', '工具'));
        detail.appendChild(humanElement('code', '', record.tool));
        body.appendChild(detail);
    }
    card.appendChild(body);
    var error = humanElement('div', 'human-card-error');
    card.appendChild(error);
    var actions = humanElement('div', 'human-card-actions human-approval-actions');
    var deny = humanElement('button', 'human-secondary-btn human-deny-btn', '拒绝');
    deny.type = 'button';
    deny.addEventListener('click', function () { void resolveHumanApproval(card, 'deny'); });
    actions.appendChild(deny);
    if (record.allow_always_available) {
        var always = humanElement('button', 'human-secondary-btn', '始终允许');
        always.type = 'button';
        always.addEventListener('click', function () { void resolveHumanApproval(card, 'allow_always'); });
        actions.appendChild(always);
    }
    var allow = humanElement('button', 'human-primary-btn human-allow-btn', '仅本次允许');
    allow.type = 'button';
    allow.addEventListener('click', function () { void resolveHumanApproval(card, 'allow_once'); });
    actions.appendChild(allow);
    card.appendChild(actions);
    return card;
}

async function resolveHumanApproval(card, decision) {
    if (!card || card.dataset.submitting === '1') return;
    card.dataset.submitting = '1';
    card.classList.add('is-submitting');
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
        card.dataset.submitting = '0';
        card.classList.remove('is-submitting');
        var error = card.querySelector('.human-card-error');
        if (error) error.textContent = '处理失败：' + String(err && err.message ? err.message : err);
    }
}

function createHumanTerminalCard(record, sessionId) {
    var kind = record.kind === 'approval' ? 'approval' : 'question';
    var card = humanElement('section', 'human-interaction-card is-terminal');
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
        summary.textContent = record.decision === 'deny' ? '你已拒绝本次操作。' : (record.decision === 'allow_always' ? '你已允许同类操作。' : '你已允许本次操作。');
    } else {
        var answers = Array.isArray(record.answers) ? record.answers : [];
        answers.forEach(function (answer) {
            var line = humanElement('div', 'human-terminal-answer');
            var values = (answer.selected_labels || []).slice();
            if (answer.other_text) values.push(answer.other_text);
            line.textContent = values.join('、') || '已回答';
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
    if (!replayingMessages && record.status === 'pending') {
        requestAnimationFrame(function () { card.scrollIntoView({ behavior: 'smooth', block: 'nearest' }); });
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
    updateHumanInteractionBanner(sid);
}

async function refreshHumanInteractions(sessionId) {
    var sid = String(sessionId || '');
    if (!sid) return false;
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
        if (sid === String(currentSessionId || '')) renderPendingHumanInteractions(sid);
        return true;
    } catch (err) {
        console.error('加载待处理交互失败:', err);
        return false;
    }
}

(function bindHumanInteractionBanner() {
    var button = document.getElementById('human-interaction-banner-btn');
    if (button) button.addEventListener('click', focusFirstPendingHumanInteraction);
})();
