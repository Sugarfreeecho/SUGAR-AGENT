function t(value) {
    return typeof globalThis.translateUiString === 'function'
        ? globalThis.translateUiString(value) : value;
}

function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
}

function icon(paths, className) {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', '0 0 24 24');
    svg.setAttribute('aria-hidden', 'true');
    if (className) svg.setAttribute('class', className);
    paths.forEach(function (definition) {
        const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        path.setAttribute('d', definition);
        svg.appendChild(path);
    });
    return svg;
}

function fieldValue(item, label) {
    const field = (item.fields || []).find(function (entry) { return entry.label === label; });
    return field ? field.value : '';
}

function initialGoal(item) {
    return {
        id: 'projected', objective: fieldValue(item, 'Objective'),
        status: fieldValue(item, 'Status') || 'active',
        used_tokens: Number(fieldValue(item, 'Used tokens')) || 0,
        remaining_tokens: Number(fieldValue(item, 'Remaining')) || 0,
        last_judge_verdict: fieldValue(item, 'Judge'),
        last_judge_reason: fieldValue(item, 'Judge reason'),
        elapsed_seconds: 0,
    };
}

function elapsedText(seconds) {
    const total = Math.max(0, Math.floor(Number(seconds) || 0));
    const hours = Math.floor(total / 3600);
    const minutes = Math.floor((total % 3600) / 60);
    const secs = total % 60;
    if (hours) return `${hours}${t('小时')} ${minutes}${t('分')} ${String(secs).padStart(2, '0')}${t('秒')}`;
    if (minutes) return `${minutes}${t('分')} ${String(secs).padStart(2, '0')}${t('秒')}`;
    return `${secs}${t('秒')}`;
}

function objectiveSummary(value) {
    const full = String(value || '').replace(/\s+/g, ' ').trim();
    return full.length <= 200 ? full : `${full.slice(0, 199).trimEnd()}…`;
}

function modalShell(kind, title, subtitle) {
    const overlay = element('div', `${kind}-modal-overlay is-open`);
    overlay.setAttribute('aria-hidden', 'false');
    const modal = element('div', `${kind}-modal`);
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-modal', 'true');
    const head = element('div', `${kind}-modal__head`);
    const copy = element('div');
    copy.append(element('h2', `${kind}-modal__title`, title), element('p', `${kind}-modal__subtitle`, subtitle));
    const close = element('button', `${kind}-modal__close`, '×');
    close.type = 'button';
    close.setAttribute('aria-label', t('关闭'));
    head.append(copy, close);
    modal.appendChild(head);
    overlay.appendChild(modal);
    document.body.appendChild(overlay);
    return { overlay, modal, close };
}

function askBudget() {
    const raw = typeof globalThis.prompt === 'function'
        ? globalThis.prompt(t('请输入要增加的 Token 预算'), '10000') : null;
    if (raw == null) return null;
    const value = Number(raw);
    if (!Number.isInteger(value) || value <= 0) {
        if (typeof globalThis.alert === 'function') globalThis.alert(t('预算必须是大于 0 的整数。'));
        return null;
    }
    return value;
}

export function renderSessionPanel(context) {
    const panel = context.container;
    panel.classList.add('agent-goal-panel-host');
    let alive = true;
    let goal = initialGoal(context.item);
    let receivedAt = Date.now();
    let activeModal = null;

    const card = element('section', 'chat-goal-card');
    const heading = element('div', 'chat-goal-heading');
    const status = element('span');
    heading.append(element('span', '', 'GOAL'), status);
    const objective = element('div', 'chat-goal-objective');
    objective.tabIndex = 0;
    const actions = element('div', 'chat-goal-actions');
    actions.setAttribute('role', 'toolbar');
    actions.setAttribute('aria-label', t('Goal 操作'));
    const stats = element('button', 'chat-goal-icon-btn chat-goal-stats-btn');
    stats.type = 'button';
    stats.appendChild(icon(['M5 20V10', 'M12 20V4', 'M19 20v-7']));
    const toggle = element('button', 'chat-goal-icon-btn');
    toggle.type = 'button';
    toggle.append(icon(['M9 5v14', 'M15 5v14'], 'chat-goal-icon-pause'), icon(['m8 5 11 7-11 7Z'], 'chat-goal-icon-play'));
    const edit = element('button', 'chat-goal-icon-btn');
    edit.type = 'button'; edit.title = t('编辑 Goal');
    edit.appendChild(icon(['m4 20 4.5-1 10-10a2.1 2.1 0 0 0-3-3l-10 10Z', 'm14 7 3 3']));
    const remove = element('button', 'chat-goal-icon-btn chat-goal-icon-btn--danger');
    remove.type = 'button'; remove.title = t('删除 Goal');
    remove.appendChild(icon(['M4 7h16', 'M9 7V4h6v3', 'M7 7l1 13h8l1-13', 'M10 11v5', 'M14 11v5']));
    const review = element('button', 'chat-goal-review-btn', t('结果审核'));
    review.type = 'button';
    actions.append(stats, toggle, edit, remove, review);
    card.append(heading, objective, actions);
    panel.appendChild(card);

    function closeModal() {
        if (!activeModal) return;
        activeModal.remove();
        activeModal = null;
        document.body.classList.remove('goal-editing', 'goal-reviewing');
    }

    function hideGoalPanel() {
        goal = null;
        closeModal();
        card.hidden = true;
        panel.hidden = true;
    }

    async function requestAction(action, payload) {
        const response = await context.request(`/sessions/${encodeURIComponent(context.sessionId)}/goal/${encodeURIComponent(action)}`, {
            method: 'POST', credentials: 'same-origin', cache: 'no-store',
            headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
            body: JSON.stringify(payload || {}),
        });
        const data = await response.json();
        if (!response.ok) {
            if (response.status === 409 && data.error === 'No goal exists for this session.') {
                if (alive) hideGoalPanel();
                context.notifyStateChanged();
                return null;
            }
            throw new Error(data.error || `Goal action failed (${response.status})`);
        }
        if (alive) {
            if (data.goal && data.goal.deleted !== true) {
                goal = data.goal;
                receivedAt = Date.now();
                render();
            } else hideGoalPanel();
        }
        context.notifyStateChanged();
        return data.goal;
    }

    function liveElapsed() {
        return Number(goal && goal.elapsed_seconds || 0)
            + (goal && goal.status === 'active' ? Math.max(0, Date.now() - receivedAt) / 1000 : 0);
    }

    function metaText() {
        const used = Math.max(0, Number(goal.used_tokens || 0));
        const tokens = goal.token_budget == null ? `Token ${t('已消耗')} ${used}` : `Token ${used} / ${goal.token_budget}`;
        const reasonLabels = {
            token_budget_exhausted: 'Token 预算已耗尽', consecutive_run_failures: '连续运行失败',
            judge_parse_failures: 'Judge 解析连续失败', judge_transport_failures: 'Judge 调用连续失败',
            react_iteration_limit: 'ReAct 已达到轮次上限', manual: '手动暂停',
        };
        const reason = reasonLabels[goal.pause_reason] || goal.pause_reason || '';
        let value = `${tokens} · ${t('用时')} ${elapsedText(liveElapsed())} · Judge ${goal.judge_count || 0}`
            + ` · ${t('续跑')} ${goal.continuation_count || 0} · ${t('连续失败')} ${goal.consecutive_failures || 0}`;
        if (reason) value += ` · ${t(reason)}`;
        if (goal.last_error) value += `\n${t('最近错误')}: ${goal.last_error}`;
        if (goal.last_judge_verdict) value += `\n${t('最近 Judge')}: ${goal.last_judge_verdict}${goal.last_judge_reason ? ` · ${goal.last_judge_reason}` : ''}`;
        return value;
    }

    function render() {
        if (!goal) return;
        const labels = { active: '进行中', paused: '已暂停', completed: '已完成', blocked: '已阻塞', cancelled: '已取消' };
        const currentStatus = String(goal.status || 'active');
        status.textContent = t(labels[currentStatus] || currentStatus)
            + (currentStatus === 'active' ? ` · ${elapsedText(liveElapsed())}` : '');
        const full = String(goal.objective || '').trim();
        objective.textContent = objectiveSummary(full);
        objective.title = full;
        objective.setAttribute('aria-label', full);
        const meta = metaText();
        stats.title = meta;
        stats.setAttribute('aria-label', `${t('统计信息')}: ${meta}`);
        const paused = currentStatus === 'paused';
        toggle.hidden = currentStatus !== 'active' && !paused;
        toggle.title = t(paused ? '开始 Goal' : '暂停 Goal');
        toggle.querySelector('.chat-goal-icon-play').hidden = !paused;
        toggle.querySelector('.chat-goal-icon-pause').hidden = paused;
        edit.hidden = currentStatus === 'completed';
        remove.hidden = currentStatus === 'completed';
        review.hidden = currentStatus !== 'completed';
    }

    function openEdit() {
        closeModal();
        const shell = modalShell('goal-edit', t('编辑 Goal 内容'), t('支持多行编辑，保存后会立即同步到当前会话。'));
        activeModal = shell.overlay;
        document.body.classList.add('goal-editing');
        const label = element('label', 'goal-edit-modal__label', t('Goal 内容'));
        const input = element('textarea', 'goal-edit-modal__textarea');
        input.maxLength = 12000; input.rows = 14; input.value = String(goal.objective || '');
        const meta = element('div', 'goal-edit-modal__meta');
        const count = element('span', '', `${input.value.length} / 12000`);
        meta.append(element('span', '', 'Ctrl/Cmd + Enter ' + t('保存')), count);
        const buttons = element('div', 'goal-edit-modal__actions');
        const cancel = element('button', 'ui-modal-btn ui-modal-btn--ghost', t('取消'));
        const save = element('button', 'ui-modal-btn ui-modal-btn--primary', t('保存修改'));
        cancel.type = save.type = 'button';
        buttons.append(cancel, save); shell.modal.append(label, input, meta, buttons);
        const saveNow = async function () {
            const value = input.value.trim();
            if (!value || value.length > 12000) return;
            save.disabled = true;
            try { await requestAction('edit', { objective: value }); closeModal(); }
            catch (error) { globalThis.alert?.(String(error.message || error)); save.disabled = false; }
        };
        input.addEventListener('input', function () { count.textContent = `${input.value.length} / 12000`; });
        input.addEventListener('keydown', function (event) {
            if (event.key === 'Escape') closeModal();
            if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) { event.preventDefault(); void saveNow(); }
        });
        shell.close.addEventListener('click', closeModal); cancel.addEventListener('click', closeModal);
        save.addEventListener('click', function () { void saveNow(); });
        shell.overlay.addEventListener('mousedown', function (event) { if (event.target === shell.overlay) closeModal(); });
        input.focus();
    }

    function openReview() {
        closeModal();
        const shell = modalShell('goal-review', t('Goal 结果审核'), t('核对目标与 Judge 结论，再决定是否通过或继续执行。'));
        activeModal = shell.overlay;
        document.body.classList.add('goal-reviewing');
        const objectiveLabel = element('label', 'goal-review-modal__label', t('当前 Goal 描述'));
        const objectiveInput = element('textarea', 'goal-review-modal__textarea');
        objectiveInput.maxLength = 12000; objectiveInput.rows = 8; objectiveInput.value = String(goal.objective || '');
        const judgeLabel = element('label', 'goal-review-modal__label goal-review-modal__judge-label', t('本次 Judge 结果'));
        const judgeInput = element('textarea', 'goal-review-modal__textarea goal-review-modal__textarea--judge');
        judgeInput.maxLength = 12000; judgeInput.rows = 8;
        judgeInput.value = String(goal.review_judge_result != null ? goal.review_judge_result : goal.last_judge_reason || '');
        const message = element('div', 'goal-review-modal__status');
        const meta = element('div', 'goal-review-modal__meta'); meta.append(message, element('span', 'input-shortcut-hint', 'Ctrl/Cmd + Enter ' + t('保存修改')));
        const buttons = element('div', 'goal-review-modal__actions');
        const approve = element('button', 'ui-modal-btn goal-review-btn--approve', t('审核通过'));
        const save = element('button', 'ui-modal-btn ui-modal-btn--ghost', t('保存修改'));
        const continueGoal = element('button', 'ui-modal-btn ui-modal-btn--primary', t('继续 Goal 任务'));
        [approve, save, continueGoal].forEach(function (button) { button.type = 'button'; buttons.appendChild(button); });
        shell.modal.append(objectiveLabel, objectiveInput, judgeLabel, judgeInput, meta, buttons);
        const submit = async function (decision) {
            const value = objectiveInput.value.trim();
            if (!value) { message.textContent = t('Goal 描述不能为空。'); message.className = 'goal-review-modal__status is-error'; return; }
            const payload = { decision, objective: value, judge_result: judgeInput.value.trim() };
            if (decision === 'continue' && goal.token_budget != null && Number(goal.remaining_tokens || 0) <= 0) {
                const additional = askBudget(); if (additional == null) return; payload.additional_budget = additional;
            }
            [approve, save, continueGoal].forEach(function (button) { button.disabled = true; });
            try {
                await requestAction('review', payload);
                if (decision === 'save') {
                    message.textContent = t('修改已保存，可继续编辑或选择审核结果。');
                    message.className = 'goal-review-modal__status is-success';
                    [approve, save, continueGoal].forEach(function (button) { button.disabled = false; });
                } else closeModal();
            } catch (error) {
                message.textContent = String(error.message || error); message.className = 'goal-review-modal__status is-error';
                [approve, save, continueGoal].forEach(function (button) { button.disabled = false; });
            }
        };
        approve.addEventListener('click', function () { void submit('approve'); });
        save.addEventListener('click', function () { void submit('save'); });
        continueGoal.addEventListener('click', function () { void submit('continue'); });
        shell.close.addEventListener('click', closeModal);
        shell.overlay.addEventListener('mousedown', function (event) { if (event.target === shell.overlay) closeModal(); });
        shell.overlay.addEventListener('keydown', function (event) {
            if (event.key === 'Escape') closeModal();
            if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) { event.preventDefault(); void submit('save'); }
        });
        objectiveInput.focus();
    }

    toggle.addEventListener('click', async function () {
        let action = goal.status === 'paused' ? 'resume' : 'pause';
        const payload = {};
        if (action === 'resume' && goal.token_budget != null && Number(goal.remaining_tokens || 0) <= 0) {
            const additional = askBudget(); if (additional == null) return; payload.additional_budget = additional;
        }
        toggle.disabled = true;
        try { await requestAction(action, payload); } catch (error) { globalThis.alert?.(String(error.message || error)); }
        finally { toggle.disabled = false; }
    });
    edit.addEventListener('click', openEdit);
    remove.addEventListener('click', async function () {
        if (globalThis.confirm?.(t('删除后当前 Goal 将从此会话中移除。确定删除吗？')) === false) return;
        try { await requestAction('delete'); } catch (error) { globalThis.alert?.(String(error.message || error)); }
    });
    review.addEventListener('click', openReview);

    render();
    const timer = globalThis.setInterval(function () { if (alive && goal) render(); }, 1000);
    void context.request(`/sessions/${encodeURIComponent(context.sessionId)}/goal`, {
        method: 'GET', credentials: 'same-origin', cache: 'no-store', headers: { Accept: 'application/json' },
    }).then(function (response) { return response.ok ? response.json() : null; }).then(function (data) {
        if (!alive || !data) return;
        if (data.goal && data.goal.deleted !== true) {
            goal = data.goal; receivedAt = Date.now(); render();
        } else {
            hideGoalPanel();
            context.notifyStateChanged();
        }
    }).catch(function () {});

    return function (details) {
        alive = false;
        globalThis.clearInterval(timer);
        const sameSession = details
            && String(details.nextSessionId || '') === String(context.sessionId || '');
        if (sameSession && activeModal) return false;
        closeModal();
        return true;
    };
}
