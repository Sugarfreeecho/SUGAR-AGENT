var agentTeamModalKeyHandler = null;
var agentTeamBusy = false;

function agentTeamSessionId() {
    return typeof currentSessionId !== 'undefined' && currentSessionId
        ? String(currentSessionId)
        : '';
}

function setAgentTeamError(message) {
    var row = document.getElementById('agent-team-error');
    if (!row) return;
    row.textContent = String(message || '');
    row.classList.toggle('hidden', !message);
}

async function agentTeamApi(path, options) {
    var response = await fetch(path, options || { cache: 'no-store' });
    var data = await response.json();
    if (!response.ok || !data || data.ok !== true) {
        throw new Error((data && data.error) || ('HTTP ' + response.status));
    }
    return data.data;
}

function agentTeamRow(title, meta, badge) {
    var row = document.createElement('div');
    row.className = 'agent-team-row';
    var copy = document.createElement('div');
    copy.className = 'agent-team-row__copy';
    var strong = document.createElement('strong');
    strong.textContent = String(title || '—');
    var small = document.createElement('span');
    small.textContent = String(meta || '');
    copy.appendChild(strong);
    copy.appendChild(small);
    var state = document.createElement('span');
    state.className = 'agent-team-badge';
    state.textContent = String(badge || '—');
    row.appendChild(copy);
    row.appendChild(state);
    return row;
}

function renderAgentTeam(team) {
    var empty = document.getElementById('agent-team-empty');
    var content = document.getElementById('agent-team-content');
    var toolbar = document.querySelector('.agent-team-toolbar');
    if (empty) empty.classList.toggle('hidden', !!team);
    if (content) content.classList.toggle('hidden', !team);
    if (toolbar) toolbar.classList.toggle('hidden', !team);
    if (!team) return;

    var members = Object.values(team.members || {});
    var tasks = Object.values(team.tasks || {});
    var permissions = Object.values(team.permissions || {});
    var summary = document.getElementById('agent-team-summary');
    if (summary) {
        summary.textContent = (team.title || team.team_id || 'Agent Team')
            + ' · ' + (team.status || 'unknown')
            + ' · ' + members.length + ' 成员 · ' + tasks.length + ' 任务';
    }

    var memberRoot = document.getElementById('agent-team-members');
    if (memberRoot) {
        memberRoot.replaceChildren();
        members.forEach(function (member) {
            memberRoot.appendChild(agentTeamRow(
                member.name || member.member_id,
                (member.role || '') + (member.child_session_id ? ' · ' + member.child_session_id.slice(0, 8) : ''),
                member.state || 'unknown'
            ));
        });
        if (!members.length) memberRoot.appendChild(agentTeamRow('暂无成员', '请让 Agent 使用 team spawn_member', 'empty'));
    }

    var taskRoot = document.getElementById('agent-team-tasks');
    if (taskRoot) {
        taskRoot.replaceChildren();
        tasks.forEach(function (task) {
            taskRoot.appendChild(agentTeamRow(
                task.title || task.task_id,
                (task.priority || 'normal') + (task.assignee_id ? ' · ' + task.assignee_id.slice(0, 12) : ''),
                task.status || 'pending'
            ));
        });
        if (!tasks.length) taskRoot.appendChild(agentTeamRow('暂无任务', '', 'empty'));
    }

    var permissionRoot = document.getElementById('agent-team-permissions');
    if (permissionRoot) {
        permissionRoot.replaceChildren();
        permissions.slice().reverse().forEach(function (permission) {
            var row = agentTeamRow(
                permission.action || permission.permission_id,
                (permission.member_id || '') + (permission.resource ? ' · ' + permission.resource : ''),
                permission.status || 'pending'
            );
            if (permission.status === 'pending') {
                var actions = document.createElement('div');
                actions.className = 'agent-team-row__actions';
                ['allowed', 'denied'].forEach(function (decision) {
                    var button = document.createElement('button');
                    button.type = 'button';
                    button.className = 'agent-team-mini-btn';
                    button.textContent = decision === 'allowed' ? '允许一次' : '拒绝';
                    button.addEventListener('click', function () {
                        void resolveAgentTeamPermission(permission.permission_id, decision);
                    });
                    actions.appendChild(button);
                });
                row.appendChild(actions);
            }
            permissionRoot.appendChild(row);
        });
        if (!permissions.length) permissionRoot.appendChild(agentTeamRow('暂无权限请求', '', 'clear'));
    }
}

async function refreshAgentTeamPanel() {
    var sid = agentTeamSessionId();
    var subtitle = document.getElementById('agent-team-modal-subtitle');
    if (!sid) {
        setAgentTeamError('请先选择或新建一个会话。');
        renderAgentTeam(null);
        return;
    }
    if (subtitle) subtitle.textContent = '会话 ' + sid;
    setAgentTeamError('');
    try {
        renderAgentTeam(await agentTeamApi('/api/agent-team/' + encodeURIComponent(sid)));
    } catch (error) {
        setAgentTeamError(error && error.message ? error.message : error);
    }
}

async function mutateAgentTeam(path, payload, method) {
    if (agentTeamBusy) return;
    agentTeamBusy = true;
    setAgentTeamError('');
    try {
        await agentTeamApi(path, {
            method: method || 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: payload === undefined ? undefined : JSON.stringify(payload),
        });
        await refreshAgentTeamPanel();
    } catch (error) {
        setAgentTeamError(error && error.message ? error.message : error);
    } finally {
        agentTeamBusy = false;
    }
}

async function resolveAgentTeamPermission(permissionId, decision) {
    var sid = agentTeamSessionId();
    if (!sid) return;
    await mutateAgentTeam(
        '/api/agent-team/' + encodeURIComponent(sid) + '/permissions/' + encodeURIComponent(permissionId) + '/resolve',
        { decision: decision, resolved_by: 'lead' }
    );
}

async function openAgentTeamModal() {
    var root = document.getElementById('agent-team-modal-root');
    var panel = root && root.querySelector('.agent-team-modal');
    if (!root || !panel) return;
    root.classList.add('is-open');
    root.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
    try { panel.focus(); } catch (e) {}
    agentTeamModalKeyHandler = function (event) {
        if (event.key === 'Escape') closeAgentTeamModal();
    };
    document.addEventListener('keydown', agentTeamModalKeyHandler);
    await refreshAgentTeamPanel();
}

function closeAgentTeamModal() {
    var root = document.getElementById('agent-team-modal-root');
    if (!root) return;
    root.classList.remove('is-open');
    root.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
    if (agentTeamModalKeyHandler) {
        document.removeEventListener('keydown', agentTeamModalKeyHandler);
        agentTeamModalKeyHandler = null;
    }
}

function initAgentTeamControls() {
    var root = document.getElementById('agent-team-modal-root');
    var close = document.getElementById('agent-team-modal-close');
    if (close) close.addEventListener('click', closeAgentTeamModal);
    if (root) root.addEventListener('click', function (event) {
        if (event.target === root) closeAgentTeamModal();
    });
    var refresh = document.getElementById('agent-team-refresh');
    if (refresh) refresh.addEventListener('click', function () { void refreshAgentTeamPanel(); });
    var create = document.getElementById('agent-team-create');
    if (create) create.addEventListener('click', function () {
        var sid = agentTeamSessionId();
        var input = document.getElementById('agent-team-title-input');
        if (sid) void mutateAgentTeam('/api/agent-team/' + encodeURIComponent(sid), { title: input ? input.value : '' });
    });
    var createTask = document.getElementById('agent-team-task-create');
    if (createTask) createTask.addEventListener('click', function () {
        var sid = agentTeamSessionId();
        var input = document.getElementById('agent-team-task-title');
        var title = input ? input.value.trim() : '';
        if (sid && title) void mutateAgentTeam('/api/agent-team/' + encodeURIComponent(sid) + '/tasks', { title: title });
    });
    [['agent-team-shutdown', 'shutdown'], ['agent-team-complete-shutdown', 'shutdown/complete'], ['agent-team-archive', 'archive']].forEach(function (entry) {
        var button = document.getElementById(entry[0]);
        if (button) button.addEventListener('click', function () {
            var sid = agentTeamSessionId();
            if (sid) void mutateAgentTeam('/api/agent-team/' + encodeURIComponent(sid) + '/' + entry[1], {});
        });
    });
}

initAgentTeamControls();
