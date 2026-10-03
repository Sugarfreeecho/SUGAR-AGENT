function translated(value) {
    return typeof globalThis.translateUiString === 'function'
        ? globalThis.translateUiString(value) : value;
}

function fieldByLabel(item, label) {
    return (item.fields || []).find(function (field) { return field.label === label; });
}

function statusLabel(status) {
    if (status === 'completed') return translated('已完成');
    if (status === 'in_progress') return translated('进行中');
    return translated('待处理');
}

/* 状态图标：已完成=绿勾（圆环+勾）、进行中=半环、待处理=空环；语义文字走 aria-label / title。 */
function statusIconMarkup(status) {
    if (status === 'completed') {
        return '<svg viewBox="0 0 24 24" aria-hidden="true" class="todo-plan-status-icon">'
            + '<circle cx="12" cy="12" r="8.2"/><path d="M8.3 12.4l2.6 2.6 4.9-5.2"/></svg>';
    }
    if (status === 'in_progress') {
        /* 进行中：描边播放三角（对齐 DSH 的 IconPlayOutlineRegular；ZCode 侧栏同样以 “[>]” 表达进行中）。
           旧的 3/4 缺口弧环不易辨识，已退役。 */
        return '<svg viewBox="0 0 24 24" aria-hidden="true" class="todo-plan-status-icon">'
            + '<path d="M8.6 6.6 17.6 12 8.6 17.4Z"/></svg>';
    }
    return '<svg viewBox="0 0 24 24" aria-hidden="true" class="todo-plan-status-icon">'
        + '<circle cx="12" cy="12" r="8.2"/></svg>';
}

// Hosts recreate panel DOM on refresh; track the stable session/item identity.
const lastRenderedSignature = new Map();
const ACTIVITY_HISTORY_LIMIT = 64;

export function renderSessionPanel(context) {
    const panel = context.container;
    const activityKey = JSON.stringify([context.sessionId, context.item.pluginId, context.item.id]);
    panel.classList.add('session-todo-panel-host');

    const card = document.createElement('div');
    card.className = 'chat-todo-plan-panel workspace-side-panel';
    const heading = document.createElement('div');
    heading.className = 'chat-todo-plan-title workspace-side-panel-title';
    const headingText = document.createElement('span');
    headingText.className = 'chat-todo-plan-heading-text';
    headingText.textContent = translated('当前计划');
    heading.appendChild(headingText);
    const clear = document.createElement('button');
    clear.type = 'button';
    clear.className = 'chat-todo-plan-close';
    clear.textContent = '×';
    clear.title = translated('清除当前计划');
    clear.setAttribute('aria-label', translated('清除计划'));

    const doneField = fieldByLabel(context.item, 'Completed');
    const totalField = fieldByLabel(context.item, 'Total');
    const itemsField = fieldByLabel(context.item, 'Items');
    const done = Number(doneField && doneField.value) || 0;
    const total = Number(totalField && totalField.value) || 0;
    if (total === 0 || done >= total) {
        lastRenderedSignature.delete(activityKey);
        panel.hidden = true;
        return;
    }
    const stats = document.createElement('div');
    stats.className = 'chat-todo-plan-stats workspace-side-panel-meta';
    stats.setAttribute('aria-live', 'polite');
    stats.textContent = `${done} / ${total} ${translated('已完成')}`;
    heading.append(stats, clear);

    const list = document.createElement('ul');
    list.className = 'chat-todo-plan-list workspace-side-panel-list';
    const rows = itemsField && Array.isArray(itemsField.rows) ? itemsField.rows : [];
    rows.forEach(function (row) {
        const status = String(row.values && row.values[0] || 'pending');
        const text = String(row.values && row.values[1] || '');
        const li = document.createElement('li');
        li.className = `todo-plan-item workspace-side-panel-item todo-plan--${status}`;
        const tag = document.createElement('span');
        tag.className = 'todo-plan-status-tag';
        tag.setAttribute('role', 'img');
        tag.setAttribute('aria-label', statusLabel(status));
        tag.title = statusLabel(status);
        tag.innerHTML = statusIconMarkup(status);
        const body = document.createElement('span');
        body.className = 'todo-plan-text';
        body.textContent = text;
        li.append(tag, body);
        list.appendChild(li);
    });
    card.append(heading, list);
    panel.appendChild(card);

    /* 条目文本最多 3 行；被截断的条目在悬停浮框中呈现全文（布局后惰性补测，面板不可见时等下轮）。 */
    const applyTodoTextTips = function () {
        panel.querySelectorAll('.todo-plan-text').forEach(function (el) {
            if (el.getAttribute('data-ui-tip')) return;
            if (el.clientHeight <= 0) return;
            if (el.scrollHeight <= el.clientHeight + 1) return;
            el.setAttribute('data-ui-tip', el.textContent || '');
            const bindTip = globalThis.bindUiHoverTip;
            if (typeof bindTip === 'function') bindTip(el);
        });
    };
    if (typeof requestAnimationFrame === 'function') requestAnimationFrame(applyTodoTextTips);
    if (typeof setTimeout === 'function') setTimeout(applyTodoTextTips, 350);

    /* 窄态条目（输入框上方，左栏收起时）：计数摘要与左栏内页签一致。 */
    const pubar = globalThis.MyAgentPubar;
    if (pubar && typeof pubar.configureNarrow === 'function') {
        pubar.configureNarrow('plan', {
            icon: 'check',
            label: translated('当前计划'),
            summary: `${done} / ${total} ${translated('已完成')}`,
        });
    }

    const signature = `${done}/${total}|` + rows.map(function (row) {
        return `${String((row.values && row.values[0]) || '')}:${String((row.values && row.values[1]) || '')}`;
    }).join('\u0001');
    if (lastRenderedSignature.get(activityKey) !== signature) {
        lastRenderedSignature.set(activityKey, signature);
        if (lastRenderedSignature.size > ACTIVITY_HISTORY_LIMIT) {
            lastRenderedSignature.delete(lastRenderedSignature.keys().next().value);
        }
        const pubar = globalThis.MyAgentPubar;
        if (pubar && typeof pubar.notifyActivity === 'function') {
            pubar.notifyActivity(panel);
        }
    }

    clear.addEventListener('click', async function () {
        if (typeof globalThis.confirm === 'function'
            && !globalThis.confirm(translated('清除当前计划？'))) return;
        clear.disabled = true;
        try {
            await context.invokeAction('clear-plan');
            lastRenderedSignature.delete(activityKey);
            await context.refresh();
        } catch (error) {
            console.warn('Todo plan clear failed', error);
            clear.disabled = false;
        }
    });
}
