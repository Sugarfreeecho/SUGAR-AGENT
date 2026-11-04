import { Console, node, badge, button, option, count, labels, time } from '/static/workflow-console.js?v=20261030-native';
import { markup } from './view.js?v=20261030-native';

export function mountConsole({ root = document, sessionId } = {}) {
    const $ = id => root.querySelector("#" + CSS.escape(id));

    let team = null, taskPage = 0, messagePage = 0, editingTask = '', editingTaskSeq = 0;
    const PAGE_SIZE = 20;
    function selectTeamView(view) {
        if (!['tasks', 'members', 'messages', 'diagnostics'].includes(view)) return;
        root.querySelectorAll('[data-team-view]').forEach(tab => {
            tab.setAttribute('aria-selected', String(tab.dataset.teamView === view));
            tab.tabIndex = tab.dataset.teamView === view ? 0 : -1;
        });
        root.querySelectorAll('[data-team-panel]').forEach(panel => { panel.hidden = panel.dataset.teamPanel !== view; });
    }
    const members = () => Object.values(team?.members || {});
    const tasks = () => Object.values(team?.tasks || {});
    const mutable = () => team && !['stopped', 'archived'].includes(team.status);
    const memberName = id => id === 'lead' ? 'Lead' : team?.members?.[id]?.name || id || '未分配';
    const terminal = task => ['completed', 'cancelled'].includes(task.status);
    const blockers = task => (task.depends_on || []).filter(id => team?.tasks?.[id]?.status !== 'completed');
    const ready = task => task.status === 'pending' && !task.assignee_id && !blockers(task).length;
    function reset() {
        team = null; taskPage = messagePage = 0; editingTask = '';
        selectTeamView('tasks');
        $('team-view').hidden = $('create-card').hidden = true;
        $('empty').hidden = false;
        root.querySelectorAll('dialog[open]').forEach(dialog => dialog.close());
        root.querySelectorAll('#workspace form').forEach(form => form.reset());
        $('empty').querySelector('h2').textContent = '选择会话以查看团队';
    }
    function pages(id, length, page, change) {
        const total = Math.max(1, Math.ceil(length / PAGE_SIZE));
        $(id).replaceChildren();
        if (total < 2) return;
        const previous = button('上一页', () => change(page - 1)); previous.disabled = page <= 0;
        const next = button('下一页', () => change(page + 1)); next.disabled = page >= total - 1;
        $(id).append(previous, node('span', '', `${page + 1} / ${total} · ${length} 条`), next);
    }
    function render(body) {
        const previousId = team?.team_id;
        team = body.data;
        if (previousId !== team?.team_id) {
            root.querySelectorAll('dialog[open]').forEach(dialog => dialog.close());
            taskPage = messagePage = 0;
        }
        $('empty').hidden = Boolean(team);
        $('empty').querySelector('h2').textContent = '此会话尚无团队';
        $('create-card').hidden = Boolean(team && team.status !== 'archived');
        $('team-view').hidden = !team;
        if (!team) return;
        const roster = members().filter(member => !member.removed);
        if (previousId !== team.team_id) selectTeamView(!tasks().length && roster.length ? 'members' : 'tasks');
        $('team-title').textContent = team.title || '未命名团队';
        $('team-id').textContent = team.team_id;
        $('team-status').replaceChildren(badge(team.status));
        $('team-updated').textContent = `最近更新 ${time(team.updated_at)}`;
        $('member-count').textContent = `${roster.length} / ${team.max_members || 4}`;
        $('task-count').textContent = `${tasks().filter(task => task.status === 'completed').length} / ${tasks().length}`;
        $('ready-count').textContent = `${tasks().filter(ready).length} / ${tasks().filter(task => !terminal(task) && blockers(task).length).length}`;
        const messages = Object.values(team.messages || {});
        $('task-tab-count').textContent = count(tasks().length);
        $('member-tab-count').textContent = count(roster.length);
        $('message-tab-count').textContent = count(messages.filter(message => message.status !== 'consumed').length);
        $('message-count').textContent = count(messages.filter(message => message.status !== 'consumed').length);
        $('schedule').disabled = team.status !== 'active' || !tasks().some(ready) || !roster.some(member => member.state === 'idle');
        $('shutdown').hidden = team.status !== 'active';
        $('complete-shutdown').hidden = team.status !== 'shutting_down';
        $('complete-shutdown').disabled = roster.some(member => ['working', 'stopping', 'waiting_permission'].includes(member.state));
        $('archive').hidden = team.status !== 'stopped';
        $('new-task').disabled = $('new-member').disabled = $('new-message').disabled = team.status !== 'active';
        const health = [];
        if (team.status === 'shutting_down') health.push('已停止接收新工作。请等待或中断执行中的成员，再完成关停并归档。');
        if (tasks().some(task => !terminal(task) && (task.depends_on || []).some(id => team.tasks?.[id]?.status === 'cancelled'))) health.push('有任务依赖已取消的任务，请处理这些任务的阻塞状态。');
        if (roster.some(member => member.state === 'failed')) health.push('有成员执行失败，可查看错误、恢复成员并释放或重新派发其任务。');
        $('team-health').textContent = health.join('\n');
        // Rebuild options only if the roster changed; preserve the inbox filter.
        const filter = $('inbox-filter'), selected = filter.value;
        filter.replaceChildren(option('all', '全部收件人'), option('lead', 'Lead 收件箱'), ...roster.map(member => option(member.member_id, `${member.name} 收件箱`)));
        filter.value = [...filter.options].some(item => item.value === selected) ? selected : 'all';
        renderMembers(); renderTasks(); renderMessages();
        $('state').textContent = JSON.stringify(team, null, 2);
    }
    function renderMembers() {
        const roster = members().filter(member => !member.removed);
        $('members').replaceChildren();
        if (!roster.length) { const empty = node('div', 'board-empty'); empty.append(node('h3', '', '团队还在等待第一位成员'), node('p', 'muted', '添加成员，设置职责与模型，然后派发工作。')); $('members').append(empty); return; }
        roster.forEach(member => {
            const item = node('article', 'item'), head = node('div', 'item-head'), copy = node('div');
            copy.append(node('h3', '', member.name), node('p', 'muted', member.role));
            const identity = node('div', 'member-identity');
            identity.append(node('span', 'member-avatar', Array.from(String(member.name || '?'))[0]), copy);
            head.append(identity, badge(member.state)); item.append(head);
            item.append(node('div', 'id', member.member_id));
            if (member.model_profile_id) item.append(node('p', 'hint', `模型：${member.model_profile_id}`));
            if (member.detail) item.append(node('p', 'prose', member.detail));
            const actions = node('div', 'toolbar');
            if (member.child_session_id) {
                const link = node('a', '', '打开成员会话');
                link.href = `/?session=${encodeURIComponent(member.child_session_id)}`;
                link.target = '_blank'; link.rel = 'noopener'; actions.append(link);
            }
            if (team.status === 'active' && member.state === 'idle') actions.append(button('派发', () => openDispatch(member.member_id)));
            if (mutable() && ['working', 'stopping', 'waiting_permission'].includes(member.state)) actions.append(button('中断', () => void runtime('interrupt_member', { member_id: member.member_id }, '已请求中断成员')));
            if (team.status === 'active' && ['failed', 'stopped', 'working', 'starting', 'stopping'].includes(member.state)) actions.append(button('恢复为空闲', () => void runtime('recover_member', { member_id: member.member_id }, '成员已恢复为空闲；请检查其未完成任务')));
            if (mutable() && !['working', 'stopping', 'waiting_permission'].includes(member.state)) actions.append(button('移除', () => {
                if (confirm(`移除成员 ${member.name}？请先释放其执行中的任务。`)) void consoleUi.action(`/members/${encodeURIComponent(member.member_id)}`, {}, '成员已移除', { method: 'DELETE' });
            }, 'danger'));
            item.append(actions); $('members').append(item);
        });
    }
    function renderTasks() {
        const filter = $('task-filter').value, search = $('task-search').value.trim().toLowerCase();
        const rows = tasks().filter(task => {
            const matches = filter === 'all' || (filter === 'ready' ? ready(task) : filter === 'dependencies' ? !terminal(task) && blockers(task).length : task.status === filter);
            return matches && `${task.title} ${task.description || ''} ${memberName(task.assignee_id)}`.toLowerCase().includes(search);
        });
        const rank = { urgent: 0, high: 1, normal: 2, low: 3 };
        rows.sort((a, b) => Number(terminal(a)) - Number(terminal(b)) || (rank[a.priority] ?? 2) - (rank[b.priority] ?? 2) || (a.seq || 0) - (b.seq || 0));
        taskPage = Math.min(taskPage, Math.max(0, Math.ceil(rows.length / PAGE_SIZE) - 1));
        $('tasks').replaceChildren();
        if (!rows.length) {
            const empty = node('div', 'board-empty');
            empty.append(node('h3', '', tasks().length ? '没有符合条件的任务' : '把工作拆成可交付的任务'), node('p', 'muted', tasks().length ? '调整状态筛选或搜索词，再试一次。' : '设置优先级和依赖，团队就能按顺序推进。'));
            $('tasks').append(empty);
        }
        const lanes = new Map();
        const laneKey = task => terminal(task) ? 'finished' : task.status === 'in_progress' ? 'working' : 'pending';
        for (const [key, title] of [['pending', '待处理'], ['working', '执行中'], ['finished', '已结束']]) {
            const total = rows.filter(task => laneKey(task) === key).length;
            if (!total) continue;
            const lane = node('div', 'task-lane'); lane.dataset.lane = key;
            const head = node('div', 'lane-head'); head.append(node('h3', '', title), node('span', 'lane-count', total));
            lane.append(head); lanes.set(key, lane); $('tasks').append(lane);
        }
        $('tasks').dataset.columns = lanes.size || 1;
        rows.slice(taskPage * PAGE_SIZE, (taskPage + 1) * PAGE_SIZE).forEach(task => {
            const item = node('article', 'item'), head = node('div', 'item-head');
            head.append(node('h3', '', task.title), badge(task.status)); item.append(head);
            item.append(node('div', 'id', task.task_id), node('p', 'hint', `${labels[task.priority] || task.priority}优先级 · 负责人：${memberName(task.assignee_id)}${ready(task) ? ' · 可调度' : ''}`));
            if (task.description) item.append(node('p', 'prose', task.description));
            if (task.depends_on?.length) item.append(node('p', 'task-dependencies', `依赖：${task.depends_on.map(id => `${team.tasks?.[id]?.title || id}（${labels[team.tasks?.[id]?.status] || '未知'}）`).join('、')}`));
            if (task.result || task.detail) {
                const details = node('details'); details.append(node('summary', '', '结果与说明'), node('div', 'prose', [task.result, task.detail].filter(Boolean).join('\n'))); item.append(details);
            }
            const actions = node('div', 'toolbar');
            if (mutable()) actions.append(button('更新任务', () => openUpdate(task)));
            if (team.status === 'active' && !terminal(task)) actions.append(button('派发成员', () => openDispatch(task.assignee_id || '', task.task_id)));
            if (mutable() && task.assignee_id && ['in_progress', 'blocked'].includes(task.status)) actions.append(button('释放任务', () => {
                if (confirm('将任务退回待处理队列？成员仍在运行时请先中断。')) void consoleUi.action(`/tasks/${encodeURIComponent(task.task_id)}/release`, { member_id: task.assignee_id, reason: 'released by operator' }, '任务已释放');
            }));
            item.append(actions); lanes.get(laneKey(task)).append(item);
        });
        pages('task-pages', rows.length, taskPage, value => { taskPage = value; renderTasks(); });
    }
    function renderMessages() {
        const recipient = $('inbox-filter').value;
        const rows = Object.values(team?.messages || {}).filter(message => recipient === 'all' || message.recipient_ids?.includes(recipient)).sort((a, b) => (b.seq || 0) - (a.seq || 0));
        messagePage = Math.min(messagePage, Math.max(0, Math.ceil(rows.length / PAGE_SIZE) - 1));
        $('messages').replaceChildren();
        if (!rows.length) $('messages').append(node('p', 'muted', '此收件箱暂无消息。'));
        rows.slice(messagePage * PAGE_SIZE, (messagePage + 1) * PAGE_SIZE).forEach(message => {
            const item = node('article', 'item'), head = node('div', 'item-head');
            head.append(node('strong', '', `${memberName(message.sender_id)} → ${(message.recipient_ids || []).map(memberName).join('、')}`), badge(message.status));
            item.append(head, node('div', 'message-content', message.content), node('div', 'hint', time(message.created_at)));
            Object.entries(message.deliveries || {}).forEach(([id, delivery]) => {
                const row = node('div', 'row'); row.append(node('span', 'hint', memberName(id)), badge(delivery.status));
                if (delivery.error) row.append(node('span', 'warning', delivery.error));
                // Operator acknowledgement is limited to the Lead inbox.
                if (id === 'lead' && delivery.status !== 'consumed' && mutable()) row.append(button('标为已读', () => void consoleUi.action(`/messages/${encodeURIComponent(message.message_id)}/delivery`, { recipient_id: id, status: 'consumed' }, '消息已标为已读')));
                item.append(row);
            });
            $('messages').append(item);
        });
        pages('message-pages', rows.length, messagePage, value => { messagePage = value; renderMessages(); });
    }
    function openDispatch(memberId = '', taskId = '') {
        const available = members().filter(member => !member.removed && member.state === 'idle' && member.child_session_id);
        if (!available.length) { consoleUi.message('没有空闲的持久成员。请先添加或恢复成员。', true); return; }
        $('dispatch-form').reset();
        $('dispatch-member').replaceChildren(...available.map(member => option(member.member_id, member.name)));
        if (available.some(member => member.member_id === memberId)) $('dispatch-member').value = memberId;
        const updateTasks = () => {
            const selected = $('dispatch-task').value;
            const mid = $('dispatch-member').value;
            const assignable = tasks().filter(task => !terminal(task) && !blockers(task).length && (!task.assignee_id || task.assignee_id === mid));
            $('dispatch-task').replaceChildren(option('', '不关联共享任务'), ...assignable.map(task => option(task.task_id, task.title)));
            if (assignable.some(task => task.task_id === selected)) $('dispatch-task').value = selected;
        };
        updateTasks(); $('dispatch-member').onchange = updateTasks;
        if ([...$('dispatch-task').options].some(item => item.value === taskId)) $('dispatch-task').value = taskId;
        $('dispatch-dialog').showModal();
    }
    function openUpdate(task) {
        editingTask = task.task_id; editingTaskSeq = task.seq || 0;
        $('update-title').value = task.title;
        $('update-description').value = task.description || '';
        $('update-priority').value = task.priority || 'normal';
        $('update-dependencies').replaceChildren(...tasks().filter(item => item.task_id !== task.task_id).map(item => option(item.task_id, item.title)));
        [...$('update-dependencies').options].forEach(item => { item.selected = (task.depends_on || []).includes(item.value); });
        $('update-status').value = task.status; $('update-result').value = task.result || ''; $('update-detail').value = task.detail || '';
        [...$('update-status').options].forEach(item => { item.disabled = terminal(task) ? item.value !== task.status : item.value === 'in_progress' && !task.assignee_id; });
        $('update-dialog').showModal();
    }
    async function runtime(action, payload = {}, notice = '操作已接受') { return consoleUi.action('/control', { action, ...payload }, notice, { timeout: 60000 }); }
    const consoleUi = new Console({ root, sessionId, path: sid => `/api/agent-team/${encodeURIComponent(sid)}`, render, reset });
    $('create').onsubmit = async event => { event.preventDefault(); await consoleUi.action('', { title: $('title').value.trim() }, '团队已创建'); };
    $('new-member').onclick = () => { $('member-form').reset(); $('member-dialog').showModal(); };
    $('member-form').onsubmit = async event => {
        event.preventDefault();
        if (await runtime('spawn_member', { name: $('member-name').value.trim(), role: $('member-role').value.trim(), prompt: $('member-prompt').value.trim(), model_profile_id: $('member-model').value.trim(), readonly: $('member-readonly').checked }, '持久成员已创建')) { $('member-dialog').close(); selectTeamView('members'); }
    };
    $('new-task').onclick = () => {
        $('task-form').reset();
        $('task-dependencies').replaceChildren(...tasks().filter(task => task.status !== 'cancelled').map(task => option(task.task_id, `${task.title}（${labels[task.status]}）`)));
        $('task-dialog').showModal();
    };
    $('task-form').onsubmit = async event => {
        event.preventDefault();
        if (await consoleUi.action('/tasks', { title: $('task-title').value.trim(), description: $('task-description').value.trim(), priority: $('task-priority').value, depends_on: [...$('task-dependencies').selectedOptions].map(item => item.value) }, '任务已创建')) { $('task-dialog').close(); selectTeamView('tasks'); }
    };
    $('dispatch-form').onsubmit = async event => {
        event.preventDefault();
        const prompt = $('dispatch-prompt').value.trim(), taskId = $('dispatch-task').value;
        if (!prompt && !taskId) { consoleUi.message('请填写本次指令，或选择关联任务。', true); return; }
        if (await runtime('dispatch', { member_id: $('dispatch-member').value, task_id: taskId, prompt }, '已派发后台执行')) $('dispatch-dialog').close();
    };
    $('update-form').onsubmit = async event => {
        event.preventDefault();
        if (await consoleUi.action(`/tasks/${encodeURIComponent(editingTask)}`, { expected_seq: editingTaskSeq, title: $('update-title').value.trim(),
            description: $('update-description').value.trim(), priority: $('update-priority').value,
            depends_on: [...$('update-dependencies').selectedOptions].map(item => item.value),
            status: $('update-status').value, result: $('update-result').value.trim(), detail: $('update-detail').value.trim() }, '任务已更新', { method: 'PATCH' })) $('update-dialog').close();
    };
    $('new-message').onclick = () => {
        $('message-form').reset();
        $('message-recipients').replaceChildren(option('lead', 'Lead'), ...members().filter(member => !member.removed && member.state !== 'stopped').map(member => option(member.member_id, member.name)));
        $('message-dialog').showModal();
    };
    $('message-form').onsubmit = async event => {
        event.preventDefault();
        if (await consoleUi.action('/messages', { sender_id: 'lead', recipient_ids: [...$('message-recipients').selectedOptions].map(item => item.value), content: $('message-content').value.trim() }, '消息已写入团队邮箱')) { $('message-dialog').close(); selectTeamView('messages'); }
    };
    $('schedule').onclick = () => void runtime('auto_schedule', {}, '已尝试调度就绪任务，请查看成员与任务状态');
    $('shutdown').onclick = () => { if (confirm('停止接收新工作并进入团队关停流程？')) void consoleUi.action('/shutdown', {}, '已请求团队关停'); };
    $('complete-shutdown').onclick = () => void consoleUi.action('/shutdown/complete', {}, '团队已停止，可以归档');
    $('archive').onclick = () => { if (confirm('归档已停止的团队？记录会保留，可在此会话创建新团队。')) void consoleUi.action('/archive', {}, '团队已归档'); };
    $('task-filter').onchange = $('task-search').oninput = () => { taskPage = 0; renderTasks(); };
    $('inbox-filter').onchange = () => { messagePage = 0; renderMessages(); };
    root.querySelectorAll('[data-close]').forEach(el => { el.onclick = () => $(el.dataset.close).close(); });
    root.querySelectorAll('[data-team-view]').forEach((tab, index, tabs) => {
        tab.onclick = () => selectTeamView(tab.dataset.teamView);
        tab.onkeydown = event => {
            const next = event.key === 'ArrowRight' ? (index + 1) % tabs.length : event.key === 'ArrowLeft' ? (index + tabs.length - 1) % tabs.length : event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : -1;
            if (next >= 0) { event.preventDefault(); selectTeamView(tabs[next].dataset.teamView); tabs[next].focus(); }
        };
    });
    // Model suggestions are optional; a model profile can also be entered directly.
    fetch('/api/model_profiles', { credentials: 'same-origin', signal: AbortSignal.any([consoleUi.events.signal, AbortSignal.timeout(10000)]) }).then(response => response.ok ? response.json() : {}).then(body => {
        if (consoleUi.disposed) return;
        $('model-profiles').replaceChildren(...(body.profiles || []).filter(profile => profile.enabled !== false).map(profile => option(profile.id, profile.name || profile.id)));
    }).catch(() => {});

    return consoleUi;
}

if (document.body.dataset.console === 'team') {
    document.querySelector('main').innerHTML = markup;
    mountConsole();
}
