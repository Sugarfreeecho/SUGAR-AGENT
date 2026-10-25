/* A group's complete membership is independent of the sidebar's reveal quota. */
var sessionGroupManager = null;

function sessionGroupManagerMembers(group) {
    var sessions = selectAllSessions().filter(function (s) { return s && !s.archived && !s.draft; });
    var groups = group.isWorkDirGroup ? selectNormalSessionWorkDirGroups(sessions) : selectNormalSessionTimeGroups(sessions);
    var current = groups.find(function (g) { return g.key === group.key; });
    return current ? current.sessions.slice() : [];
}

function closeSessionGroupManager() {
    var state = sessionGroupManager;
    if (!state || state.busy) return;
    document.removeEventListener('keydown', state.keyHandler);
    state.root.remove();
    document.body.style.overflow = state.previousOverflow;
    sessionGroupManager = null;
    if (state.previousFocus && state.previousFocus.isConnected) state.previousFocus.focus({ preventScroll: true });
}

function sessionGroupManagerVisible(state) {
    var terms = state.filter.value.trim().toLowerCase().split(/\s+/).filter(Boolean);
    return state.sessions.filter(function (s) {
        var hay = [s.name, s.id, s.last_user_preview, s.effective_work_dir, s.work_dir, s.work_dir_label].join(' ').toLowerCase();
        return terms.every(function (term) { return hay.includes(term); });
    });
}

function renderSessionGroupManager() {
    var state = sessionGroupManager;
    if (!state) return;
    var visible = sessionGroupManagerVisible(state), scroll = state.list.scrollTop;
    var fragment = document.createDocumentFragment();
    visible.forEach(function (session) {
        var row = document.createElement('label'); row.className = 'session-manager-row';
        row.dataset.managedSessionId = session.id;
        var checkbox = document.createElement('input'); checkbox.type = 'checkbox';
        checkbox.checked = state.selected.has(session.id); checkbox.disabled = state.busy;
        checkbox.setAttribute('aria-label', '选择会话：' + (session.name || '未命名会话'));
        checkbox.addEventListener('change', function () {
            if (checkbox.checked) state.selected.add(session.id); else state.selected.delete(session.id);
            renderSessionGroupManager();
        });
        var copy = document.createElement('span'); copy.className = 'session-manager-row-copy';
        var name = document.createElement('span'); name.className = 'session-manager-row-name';
        name.textContent = session.name || '未命名会话'; name.title = name.textContent; name.setAttribute('data-i18n-skip', '');
        var path = document.createElement('span'); path.className = 'session-manager-row-path';
        path.textContent = session.effective_work_dir || session.work_dir || window.__WORK_DIR__ || '默认工作目录';
        path.title = path.textContent; path.setAttribute('data-i18n-skip', '');
        copy.append(name, path);
        var result = state.results.get(session.id);
        if (result) {
            var message = document.createElement('span'); message.className = 'session-manager-row-result' + (result.error ? ' is-error' : '');
            message.textContent = result.message; copy.appendChild(message);
        }
        var meta = document.createElement('span'); meta.className = 'session-manager-row-meta';
        var running = typeof isSessionRunning === 'function' && isSessionRunning(session.id);
        var background = typeof sessionHasBackgroundWork === 'function' && sessionHasBackgroundWork(session);
        meta.textContent = running || background ? '运行中' : typeof formatSessionListRelativeTime === 'function' ? formatSessionListRelativeTime(session) : '';
        row.append(checkbox, copy, meta); fragment.appendChild(row);
    });
    if (!visible.length) {
        var empty = document.createElement('p'); empty.className = 'session-manager-empty';
        empty.textContent = state.sessions.length ? '没有匹配的会话' : '此分组已没有会话'; fragment.appendChild(empty);
    }
    // Preserve focus when a checkbox changes or a batch updates its status.
    var activeId = document.activeElement && document.activeElement.closest('[data-managed-session-id]');
    activeId = activeId && activeId.dataset.managedSessionId;
    state.list.replaceChildren(fragment); state.list.scrollTop = scroll;
    if (activeId) {
        var active = state.list.querySelector('[data-managed-session-id="' + CSS.escape(activeId) + '"] input');
        if (active && !active.disabled) active.focus({ preventScroll: true });
    }
    var selectedVisible = visible.filter(function (s) { return state.selected.has(s.id); }).length;
    state.all.checked = !!visible.length && selectedVisible === visible.length;
    state.all.indeterminate = selectedVisible > 0 && selectedVisible < visible.length;
    state.all.disabled = state.busy || !visible.length;
    state.count.textContent = '已选 ' + state.selected.size + ' / ' + state.sessions.length + ' 个会话'
        + (state.filter.value.trim() ? ' · 当前结果 ' + visible.length + ' 个' : '');
    state.summary.textContent = state.message || '选择会话后可批量删除，或迁移到目标工作区。';
    state.root.setAttribute('aria-busy', String(state.busy));
    state.filter.disabled = state.busy; state.target.disabled = state.busy; state.pick.disabled = state.busy;
    state.remove.disabled = state.busy || !state.selected.size;
    state.move.disabled = state.busy || !state.selected.size || !state.target.value;
    state.close.disabled = state.busy;
}

function sessionGroupManagerAddTarget(state, path, label) {
    path = String(path || '').trim();
    if (!path) return;
    var existing = Array.from(state.target.options).find(function (o) {
        return o.value && normalizeWorkDirIdentity(o.value) === normalizeWorkDirIdentity(path);
    });
    if (!existing) {
        existing = document.createElement('option'); existing.value = path;
        existing.textContent = (label || workDirDisplayName(path)) + ' · ' + path;
        state.target.appendChild(existing);
    }
    return existing.value;
}

async function pickSessionGroupManagerTarget() {
    var state = sessionGroupManager;
    if (!state || state.busy) return;
    state.busy = true; renderSessionGroupManager();
    try {
        var path = await pickNewSessionWorkDir(state.target.value || state.group.tip || '');
        if (path && sessionGroupManager === state) state.target.value = sessionGroupManagerAddTarget(state, path);
    } catch (error) {
        state.message = '无法选择工作区：' + String(error.message || error);
    } finally {
        document.body.style.overflow = 'hidden';
        state.busy = false; renderSessionGroupManager(); state.pick.focus();
    }
}

async function runSessionGroupBatch(action) {
    var state = sessionGroupManager;
    if (!state || state.busy || !state.selected.size) return;
    var chosen = state.sessions.filter(function (s) { return state.selected.has(s.id); });
    var target = state.target.value;
    if (action === 'move' && !target) return;
    state.busy = true; renderSessionGroupManager();
    var token = null, revision = 0, succeeded = 0, failed = 0, deletedIds = new Set();
    try {
        var names = chosen.slice(0, 6).map(function (s) { return '• ' + (s.name || '未命名会话'); }).join('\n');
        if (chosen.length > 6) names += '\n…等 ' + chosen.length + ' 个会话';
        var confirmed = await openUiModal({
            title: action === 'delete' ? '批量删除 ' + chosen.length + ' 个会话' : '迁移 ' + chosen.length + ' 个会话的工作区',
            subtitle: action === 'delete' ? '此操作不可恢复' : '目标工作区：' + target,
            message: names + (action === 'delete'
                ? '\n\n将移除所选会话的消息与记录；仍在运行的相关任务会先停止。'
                : '\n\n切换这些会话的工作目录，历史和附件保留。运行中的会话及托管工作树会由服务端检查，无法迁移时显示原因。'),
            danger: action === 'delete', confirmText: action === 'delete' ? '删除选中会话' : '确认迁移', cancelText: '取消',
        });
        document.body.style.overflow = 'hidden';
        state.root.querySelector('[role="dialog"]').focus();
        if (!confirmed) return;
        token = beginSidebarMetadataMutation();
        for (var i = 0; i < chosen.length; i++) {
            var session = chosen[i];
            state.message = '正在' + (action === 'delete' ? '删除' : '迁移') + ' ' + (i + 1) + ' / ' + chosen.length + ' · 成功 ' + succeeded + '，失败 ' + failed;
            renderSessionGroupManager();
            try {
                var options = action === 'delete' ? { method: 'DELETE' } : {
                    method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ work_dir: target }),
                };
                var response = await fetchWithTimeout('/sessions/' + encodeURIComponent(session.id)
                    + (action === 'move' ? '/work-dir' : ''), options, action === 'delete' ? 45000 : 12000);
                var payload = await response.json().catch(function () { return {}; });
                if (!(action === 'delete' && response.status === 404)
                        && (!response.ok || action === 'move' && payload.ok !== true)) {
                    throw new Error(payload.error || ('请求失败（HTTP ' + response.status + '）'));
                }
                revision = Math.max(revision, Number(payload.state_revision) || 0);
                if (action === 'delete') {
                    deletedIds.add(session.id);
                    await removeDeletedSessionFromUi(session, null, { deferSwitch: true });
                    releaseDeletedSessionDock(session.id);
                    state.sessions = state.sessions.filter(function (s) { return s.id !== session.id; });
                } else {
                    applyOptimisticSessionUpdate(session.id, payload.session);
                    syncSessionWorkspaceUi(session.id);
                    var next = sessionStore.get(session.id) || Object.assign({}, session, payload.session);
                    state.sessions = state.sessions.map(function (s) { return s.id === session.id ? next : s; });
                    state.results.set(session.id, { message: '已迁移到：' + target });
                }
                state.selected.delete(session.id); succeeded++;
            } catch (error) {
                failed++;
                state.results.set(session.id, { error: true, message: String(error.message || error) });
            }
        }
        commitSidebarMetadataMutation(token, { state_revision: revision }); token = null;
        state.message = (action === 'delete' ? '删除' : '迁移') + '完成：成功 ' + succeeded + '，失败 ' + failed
            + (failed ? '。失败项保留选中，可重试。' : '。');
        if (deletedIds.has(currentSessionId)) {
            var nextSession = sessionStore.list().find(function (s) { return !s.archived && !deletedIds.has(s.id); });
            if (nextSession) await switchSession(nextSession.id); else await createNewSession();
        }
        try { await loadSessions({ skipArchivedRefresh: true }); }
        catch (_) { state.message += ' 列表刷新失败，请稍后刷新核对。'; }
    } catch (error) {
        state.message = '操作中断：' + String(error.message || error);
    } finally {
        if (token !== null) cancelSidebarMetadataMutation(token);
        state.busy = false;
        document.body.style.overflow = 'hidden';
        renderSessionGroupManager();
        var actionButton = action === 'delete' ? state.remove : state.move;
        (actionButton.disabled ? state.close : actionButton).focus();
    }
}

function openSessionGroupManager(group, trigger) {
    if (sessionGroupManager && sessionGroupManager.busy) return;
    closeSessionGroupManager();
    var root = document.createElement('div'); root.className = 'session-manager-overlay';
    root.innerHTML = '<section class="session-manager-dialog" role="dialog" tabindex="-1" aria-modal="true" aria-labelledby="session-manager-title">'
        + '<header><div><h2 id="session-manager-title">会话管理</h2><p class="session-manager-group"></p></div>'
        + '<button type="button" class="session-dialog-close" data-manager-close aria-label="关闭会话管理" title="关闭"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"></path></svg></button></header>'
        + '<input class="session-manager-filter" type="search" placeholder="筛选会话名称、内容摘要或工作目录" aria-label="筛选分组内的会话">'
        + '<div class="session-manager-selection"><label><input type="checkbox" data-manager-all>全选当前结果</label><span data-manager-count></span></div>'
        + '<div class="session-manager-list" role="group" aria-label="分组内全部会话"></div>'
        + '<div class="session-manager-target"><label>目标工作区<select aria-label="目标工作区"><option value="">请选择工作区</option></select></label>'
        + '<button type="button" data-manager-pick>选择其他文件夹</button></div>'
        + '<p class="session-manager-status" role="status" aria-live="polite"></p>'
        + '<footer><button type="button" data-manager-move>迁移工作区</button><button type="button" data-manager-delete class="is-danger">批量删除</button></footer></section>';
    var state = {
        root: root, group: group, sessions: sessionGroupManagerMembers(group), selected: new Set(), results: new Map(), busy: false,
        previousFocus: trigger || document.activeElement, previousOverflow: document.body.style.overflow,
        list: root.querySelector('.session-manager-list'), filter: root.querySelector('.session-manager-filter'),
        all: root.querySelector('[data-manager-all]'), count: root.querySelector('[data-manager-count]'),
        target: root.querySelector('select'), pick: root.querySelector('[data-manager-pick]'),
        summary: root.querySelector('.session-manager-status'), close: root.querySelector('[data-manager-close]'),
        move: root.querySelector('[data-manager-move]'), remove: root.querySelector('[data-manager-delete]'),
    };
    sessionGroupManager = state;
    var label = root.querySelector('.session-manager-group'); label.textContent = group.title || ''; label.setAttribute('data-i18n-skip', '');
    listCreatedSessionWorkDirs().forEach(function (entry) { sessionGroupManagerAddTarget(state, entry.absolutePath || entry.path, entry.label); });
    state.close.addEventListener('click', closeSessionGroupManager);
    state.filter.addEventListener('input', renderSessionGroupManager);
    state.target.addEventListener('change', renderSessionGroupManager);
    state.pick.addEventListener('click', pickSessionGroupManagerTarget);
    state.move.addEventListener('click', function () { void runSessionGroupBatch('move'); });
    state.remove.addEventListener('click', function () { void runSessionGroupBatch('delete'); });
    state.all.addEventListener('change', function () {
        sessionGroupManagerVisible(state).forEach(function (s) { if (state.all.checked) state.selected.add(s.id); else state.selected.delete(s.id); });
        renderSessionGroupManager();
    });
    root.addEventListener('click', function (event) { if (event.target === root) closeSessionGroupManager(); });
    state.keyHandler = function (event) {
        var confirmation = document.getElementById('ui-modal-root');
        if (confirmation && confirmation.classList.contains('is-open')) return;
        if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); closeSessionGroupManager(); }
        if (event.key === 'Tab') {
            var items = Array.from(root.querySelectorAll('button:not(:disabled), input:not(:disabled), select:not(:disabled)'));
            var first = items[0], last = items[items.length - 1];
            if (!items.length) { event.preventDefault(); return; }
            if (!root.contains(document.activeElement)) { event.preventDefault(); (event.shiftKey ? last : first).focus(); }
            else if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
            else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
        }
    };
    document.addEventListener('keydown', state.keyHandler);
    document.body.appendChild(root); document.body.style.overflow = 'hidden';
    renderSessionGroupManager(); state.filter.focus();
}
