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

export function renderSessionPanel(context) {
    const panel = context.container;
    panel.classList.add('session-todo-panel-host');

    const card = document.createElement('div');
    card.className = 'chat-todo-plan-panel';
    const heading = document.createElement('div');
    heading.className = 'chat-todo-plan-title';
    heading.appendChild(document.createTextNode(translated('当前计划')));
    const clear = document.createElement('button');
    clear.type = 'button';
    clear.className = 'chat-todo-plan-close';
    clear.textContent = '×';
    clear.title = translated('清除当前计划');
    clear.setAttribute('aria-label', translated('清除计划'));
    heading.appendChild(clear);

    const doneField = fieldByLabel(context.item, 'Completed');
    const totalField = fieldByLabel(context.item, 'Total');
    const itemsField = fieldByLabel(context.item, 'Items');
    const done = Number(doneField && doneField.value) || 0;
    const total = Number(totalField && totalField.value) || 0;
    if (total === 0 || done >= total) {
        panel.hidden = true;
        return;
    }
    const stats = document.createElement('div');
    stats.className = 'chat-todo-plan-stats';
    stats.setAttribute('aria-live', 'polite');
    stats.textContent = `${done} / ${total} ${translated('已完成')}`;

    const list = document.createElement('ul');
    list.className = 'chat-todo-plan-list';
    const rows = itemsField && Array.isArray(itemsField.rows) ? itemsField.rows : [];
    rows.forEach(function (row) {
        const status = String(row.values && row.values[0] || 'pending');
        const text = String(row.values && row.values[1] || '');
        const li = document.createElement('li');
        li.className = `todo-plan-item todo-plan--${status}`;
        const tag = document.createElement('span');
        tag.className = 'todo-plan-status-tag';
        tag.textContent = statusLabel(status);
        const body = document.createElement('span');
        body.textContent = text;
        li.append(tag, body);
        list.appendChild(li);
    });
    card.append(heading, stats, list);
    panel.appendChild(card);

    clear.addEventListener('click', async function () {
        if (typeof globalThis.confirm === 'function'
            && !globalThis.confirm(translated('清除当前计划？'))) return;
        clear.disabled = true;
        try {
            await context.invokeAction('clear-plan');
            context.notifyStateChanged();
            await context.refresh();
        } catch (error) {
            console.warn('Todo plan clear failed', error);
            clear.disabled = false;
        }
    });
}
