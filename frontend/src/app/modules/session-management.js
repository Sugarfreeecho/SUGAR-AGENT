function setSendButtonState() {
    sendBtn.disabled = false;
    if (isSessionRunning(currentSessionId)) {
        const hasDraft = (typeof inputHasSendableText === 'function')
            ? inputHasSendableText()
            : !!(messageInput && String(messageInput.value || '').trim());
        const followupEnabled = (typeof isMyAgentFeatureEnabled === 'function') && isMyAgentFeatureEnabled('followupRestart', false);
        sendBtn.innerHTML = (followupEnabled && hasDraft) ? '追问' : '停止 <span class="loader" aria-hidden="true"></span>';
        sendBtn.classList.add('is-stop');
        sendBtn.classList.toggle('is-followup', followupEnabled && hasDraft);
    } else {
        sendBtn.textContent = '发送';
        sendBtn.classList.remove('is-stop');
        sendBtn.classList.remove('is-followup');
    }
}

async function requestInterrupt(sessionId, runId, reason) {
    if (!sessionId) return;
    try {
        await fetch('/sessions/' + sessionId + '/interrupt', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ run_id: runId || '', reason: reason || '' }),
        });
    }
    catch (e) { /* ignore */ }
}

function pauseCurrentRun() {
    if (!currentSessionId) return;
    const run = getSessionRunState(currentSessionId);
    const sid = currentSessionId;
    const activeInfo = sessionStore.getActiveRunInfo(sid) || {};
    const runId = run && run.runId ? run.runId : (activeInfo.run_id || activeInfo.runId || '');
    suppressSessionServerStreamActive(sid);
    if (!run) {
        setSendButtonState();
        syncSessionListIndicatorClasses();
        renderSessionListIfChanged(false);
        void requestInterrupt(sid, runId);
        setTimeout(function () { reconcileRunStateFromServer({ silent: true, respectStopSuppress: true }); }, 3000);
        return;
    }
    const ctx = run.ctx;
    /* 先同步 abort 本地 fetch 与从 sessionStore 摘除，UI 立即反映「已停止」状态；
       后端 interrupt 走 fire-and-forget，避免被主线程阻塞时按钮响应卡顿。*/
    abortSessionRun(sid, 'user');
    setSendButtonState();
    syncSessionListIndicatorClasses();
    renderSessionListIfChanged(false);
    appendLog(ctx, '已请求停止当前任务', 'status', sid);
    sealProcessGroup(ctx);
    void requestInterrupt(sid, runId);
    setTimeout(function () { reconcileRunStateFromServer({ silent: true, respectStopSuppress: true }); }, 3000);
}

/** 在当前会话中定位最近一条用户消息并重新发送。返回 true 表示已触发展开发送。*/
function resendLastUserMessage() {
    if (!currentSessionId) return false;
    if (isSessionRunning(currentSessionId)) return false;
    var lastMsg = lastUserMessageBySession[currentSessionId];
    if (!lastMsg || !String(lastMsg).trim()) {
        var chatStream = getVisibleChatStream();
        if (chatStream) {
            var wraps = chatStream.querySelectorAll('.msg-wrap--user');
            if (wraps.length) {
                var lastWrap = wraps[wraps.length - 1];
                lastMsg = messageRawMarkdown.get(lastWrap) || (lastWrap.querySelector('.message.user') && lastWrap.querySelector('.message.user').textContent);
            }
        }
    }
    if (!lastMsg || !String(lastMsg).trim()) {
        lastMsg = draftBySession[currentSessionId];
    }
    if (!lastMsg || !String(lastMsg).trim()) return false;
    messageInput.value = String(lastMsg);
    rewriteInputWorkspacePaths();
    autoResizeTextarea();
    sendMessage();
    return true;
}

function showLoading() {
    resetSessionHistoryPaging();
    clearTocForSessionLoad();
    if (!getVisibleChatStream()) ensureVisibleChatStreamSlot();
    const vs = getVisibleChatStream();
    if (vs) emptyChatStreamKeepingStrip(vs);
    const box = document.createElement('div');
    box.className = 'skeleton';
    box.id = 'chat-loading';
    box.setAttribute('role', 'status');
    box.innerHTML = ''
        + '<div class="skeleton-page" aria-hidden="true">'
        + '<div class="skeleton-mast"><span></span><span></span></div>'
        + '<div class="skeleton-hero"><div class="skeleton-image"></div><div class="skeleton-column"><span></span><span></span><span></span><span></span></div></div>'
        + '<div class="skeleton-grid"><div><span></span><span></span><span></span></div><div><span></span><span></span><span></span></div><div><span></span><span></span><span></span></div></div>'
        + '</div><div class="skeleton-copy">加载中...</div>';
    box.setAttribute('data-ui-tip', '加载会话');
    bindUiHoverTip(box);
    (getVisibleChatStream() || chatContainer).appendChild(box);
    scrollToBottom();
}

function hideLoading() { const loader = document.getElementById('chat-loading'); if (loader) loader.remove(); }

/** 根据 sessionStore / 服务端 stream_active / sessionUnreadComplete 更新红点、绿点 */
function applySessionItemIndicators(itemDiv, sessionId, opts) {
    opts = opts || {};
    if (!itemDiv || !sessionId) return;
    itemDiv.classList.remove('is-generating', 'is-unread-result', 'is-unread-failed');
    var nameEl = itemDiv.querySelector('.session-name');
    if (nameEl) nameEl.removeAttribute('data-ui-tip');
    if (isSessionRunning(sessionId)) {
        itemDiv.classList.add('is-generating');
        if (nameEl) nameEl.setAttribute('data-ui-tip', '生成中');
    } else {
        var sess = sessionStore.get(sessionId);
        var localUnreadResult = sessionUnreadComplete.has(sessionId);
        var hasUnreadResult = sess ? !!sess.unread_result : localUnreadResult;
        if (!hasUnreadResult) return;
        var failed = !!(sess && sess.unread_result_status === 'failed');
        itemDiv.classList.add(failed ? 'is-unread-failed' : 'is-unread-result');
        if (nameEl) nameEl.setAttribute('data-ui-tip', failed ? '任务失败，点击查看' : '有新回复，点击查看');
    }
    if (nameEl) bindUiHoverTip(nameEl);
}

/** 立即刷新侧栏全部指示点与当前选中项；不依赖 loadSessions 网络回流，与是否切换会话无关 */
function syncSessionListIndicatorClasses() {
    if (!sessionsList) return;
    sessionsList.querySelectorAll('.session-item').forEach(function (div) {
        var el = div.querySelector('.session-name[data-id]');
        if (!el) return;
        var sid = el.getAttribute('data-id');
        div.classList.toggle('active', !!sid && sid === currentSessionId);
        applySessionItemIndicators(div, sid);
    });
}

function sessionSectionExpanded(key) {
    try {
        return localStorage.getItem(LS_SESSION_SECTION_PREFIX + key) !== '0';
    } catch (e) {
        return true;
    }
}
function persistSessionSectionExpanded(key, expanded) {
    try {
        localStorage.setItem(LS_SESSION_SECTION_PREFIX + key, expanded ? '1' : '0');
    } catch (e) { /* ignore */ }
}
function closeAllSessionMenus() {
    document.querySelectorAll('.session-more-wrap.is-open').forEach(function (w) {
        w.classList.remove('is-open');
        var b = w.querySelector('.session-more-btn');
        if (b) b.setAttribute('aria-expanded', 'false');
    });
}
(function bindSessionMenuDocumentCloserOnce() {
    if (window.__myAgentSessionMenuCloser) return;
    window.__myAgentSessionMenuCloser = true;
    document.addEventListener('click', closeAllSessionMenus);
})();

(function bindSessionListDelegatedSwitcherOnce() {
    if (!sessionsList || window.__myAgentSessionListSwitcher) return;
    window.__myAgentSessionListSwitcher = true;
    sessionsList.addEventListener('click', function (e) {
        var target = e.target;
        if (!target || !target.closest) return;
        if (target.closest('button, .session-more-wrap, .session-more-menu, input, textarea, a')) return;
        if (target.isContentEditable) return;
        var row = target.closest('.session-item');
        if (!row || !sessionsList.contains(row)) return;
        var sid = row.dataset.sessionId;
        if (!sid) {
            var nameEl = row.querySelector('.session-name[data-id]');
            sid = nameEl ? nameEl.getAttribute('data-id') : '';
        }
        if (sid && sid !== currentSessionId) {
            Promise.resolve(switchSession(sid)).catch(function (err) {
                console.error('切换会话失败:', err);
            });
        }
    });
})();

/**
 * 创建并绑定单条会话（更多菜单：置顶 → 删除 → 归档 在末尾）
 */
function buildAndBindSessionRow(sess, allSessions, nextStreamMap) {
    const div = document.createElement('div');
    div.className = 'session-item';
    div.dataset.sessionId = sess.id || '';
    if (currentSessionId === sess.id) div.classList.add('active');
    if (sess.id) nextStreamMap[sess.id] = !!sess.stream_active;
    div.innerHTML = '<div class="session-item-head">'
        + '<span class="session-name" data-id="' + sess.id + '" data-original="' + escapeHtml(sess.name) + '">' + escapeHtml(sess.name) + '</span>'
        + '<div class="session-more-wrap">'
        + '<button type="button" class="session-more-btn" aria-label="更多操作" aria-expanded="false" aria-haspopup="true" data-ui-tip="更多">'
        + '<span class="session-more-dots" aria-hidden="true"><span></span><span></span><span></span></span></button>'
        + '<div class="session-more-menu" role="menu">'
        + '<button type="button" class="session-menu-pin" role="menuitem"></button>'
        + '<button type="button" class="session-menu-delete" role="menuitem">删除</button>'
        + '<button type="button" class="session-menu-archive" role="menuitem"></button>'
        + '</div></div>'
        + '</div>'
        + '<div class="session-last-query"></div>';
    var pinMi = div.querySelector('.session-menu-pin');
    var archMi = div.querySelector('.session-menu-archive');
    if (pinMi) pinMi.textContent = sess.pinned ? '取消置顶' : '置顶';
    if (archMi) archMi.textContent = sess.archived ? '取消归档' : '归档';
    var wsLine = formatSessionListSubtitle(sess);
    var wsEl = div.querySelector('.session-last-query');
    if (wsEl) {
        wsEl.textContent = wsLine;
        wsEl.setAttribute('data-ui-tip', wsLine);
        bindUiHoverTip(wsEl);
    }
    var moreWrap = div.querySelector('.session-more-wrap');
    var moreBtn = div.querySelector('.session-more-btn');
    if (moreBtn) bindUiHoverTip(moreBtn);
    if (moreWrap && moreBtn) {
        moreBtn.addEventListener('click', function (e) {
            e.stopPropagation();
            var wasOpen = moreWrap.classList.contains('is-open');
            closeAllSessionMenus();
            if (pinMi) pinMi.textContent = sess.pinned ? '取消置顶' : '置顶';
            if (archMi) archMi.textContent = sess.archived ? '取消归档' : '归档';
            if (!wasOpen) {
                moreWrap.classList.add('is-open');
                moreBtn.setAttribute('aria-expanded', 'true');
            }
        });
    }
    if (pinMi) {
        pinMi.addEventListener('click', async function (e) {
            e.stopPropagation();
            closeAllSessionMenus();
            try {
                const formData = new FormData();
                const nextPinned = !sess.pinned;
                const previous = applyOptimisticSessionUpdate(sess.id, { pinned: nextPinned });
                formData.append('pinned', nextPinned ? 'true' : 'false');
                const response = await fetch('/sessions/' + encodeURIComponent(sess.id) + '/pin', { method: 'PUT', body: formData });
                if (!response.ok) {
                    if (previous) applyOptimisticSessionUpdate(sess.id, previous);
                    throw new Error('pin failed: ' + response.status);
                }
                void refreshSingleSessionRow(sess.id);
            } catch (err) { console.error('置顶失败', err); }
        });
    }
    if (archMi) {
        archMi.addEventListener('click', async function (e) {
            e.stopPropagation();
            closeAllSessionMenus();
            try {
                const formData = new FormData();
                const nextArchived = !sess.archived;
                const previous = applyOptimisticSessionUpdate(sess.id, { archived: nextArchived });
                formData.append('archived', nextArchived ? 'true' : 'false');
                const response = await fetch('/sessions/' + encodeURIComponent(sess.id) + '/archive', { method: 'PUT', body: formData });
                if (!response.ok) {
                    if (previous) applyOptimisticSessionUpdate(sess.id, previous);
                    throw new Error('archive failed: ' + response.status);
                }
                void refreshSingleSessionRow(sess.id);
            } catch (err) { console.error('归档失败', err); }
        });
    }
    var delMi = div.querySelector('.session-menu-delete');
    if (delMi) {
        delMi.addEventListener('click', async function (e) {
            e.stopPropagation();
            closeAllSessionMenus();
            const okDel = await openUiModal({
                title: '删除会话',
                subtitle: '此操作不可恢复',
                message: '确定删除会话「' + String(sess.name || '未命名') + '」吗？其中的消息与记录将被移除。',
                danger: true,
                confirmText: '删除会话',
                cancelText: '取消',
            });
            if (!okDel) return;
            const wasArchivedLoaded = sessionStore.archivedLoaded;
            const deletedSessionId = String(sess.id || '');
            const nextSession = sessionStore.list().find(function (s) {
                return s && s.id && String(s.id) !== deletedSessionId && !s.archived;
            }) || null;
            sessionStore.markDeletedSession(deletedSessionId);
            if (wasArchivedLoaded) {
                sessionStore.setArchivedLoaded((sessionStore.archivedSessions || []).filter(function (s) {
                    return s && String(s.id) !== deletedSessionId;
                }));
                syncArchivedSessionStateFromStore();
            }
            renderSessionListIfChanged(true);
            if (div && div.parentNode) div.remove();
            sessionUnreadComplete.delete(deletedSessionId);
            persistSessionUnread();
            delete draftBySession[deletedSessionId];
            removeStoredInputDraft(deletedSessionId);
            if (typeof removeStoredFollowupQueue === 'function') removeStoredFollowupQueue(deletedSessionId);
            delete lastUserMessageBySession[deletedSessionId];
            clearContextStateForSession(deletedSessionId);
            if (typeof discardCachedSessionStream === 'function') discardCachedSessionStream(deletedSessionId);
            if (isSessionRunning(sess.id)) {
                const r = abortSessionRun(sess.id, 'delete');
                if (r && r.ctx && r.ctx.stream && r.ctx.stream.parentNode) r.ctx.stream.remove();
                setSendButtonState();
                syncSessionListIndicatorClasses();
            }
            if (currentSessionId === deletedSessionId) {
                if (nextSession) await switchSession(nextSession.id);
                else await createNewSession();
            }
            void requestInterrupt(deletedSessionId);
            void fetch('/sessions/' + encodeURIComponent(deletedSessionId), { method: 'DELETE' })
                .then(function (resp) {
                    if (!resp.ok) throw new Error('delete failed: ' + resp.status);
                })
                .catch(function (err) {
                    console.error('删除会话失败:', err);
                    sessionStore.clearDeletedSessionTombstone(deletedSessionId);
                    void loadSessions({ skipArchivedRefresh: true });
                    if (wasArchivedLoaded) void loadArchivedSessions({ background: true });
                });
        });
    }
    const nameSpan = div.querySelector('.session-name');
    if (nameSpan) {
        nameSpan.addEventListener('dblclick', function (e) {
            e.stopPropagation();
            if (nameSpan.classList.contains('editing')) return;
            nameSpan.classList.add('editing');
            nameSpan.contentEditable = 'true';
            nameSpan.focus();
            const range = document.createRange();
            range.selectNodeContents(nameSpan);
            const sel = window.getSelection();
            sel.removeAllRanges();
            sel.addRange(range);
        });
        nameSpan.addEventListener('blur', async function () {
            if (!nameSpan.classList.contains('editing')) return;
            nameSpan.classList.remove('editing');
            nameSpan.contentEditable = 'false';
            const newName = nameSpan.innerText.trim();
            if (newName && newName !== nameSpan.dataset.original) {
                const oldName = nameSpan.dataset.original;
                const previous = applyOptimisticSessionUpdate(sess.id, { name: newName });
                nameSpan.dataset.original = newName;
                if (currentSessionId === sess.id) updateSessionTitle();
                try {
                    const formData = new FormData();
                    formData.append('name', newName);
                    const response = await fetch('/sessions/' + encodeURIComponent(sess.id) + '/name', { method: 'PUT', body: formData });
                    if (!response.ok) throw new Error('rename failed: ' + response.status);
                    if (currentSessionId === sess.id) updateSessionTitle();
                } catch (err) {
                    console.error('重命名失败', err);
                    if (previous) applyOptimisticSessionUpdate(sess.id, previous);
                    nameSpan.innerText = oldName;
                    nameSpan.dataset.original = oldName;
                    if (currentSessionId === sess.id) updateSessionTitle();
                }
            } else nameSpan.innerText = nameSpan.dataset.original;
        });
        nameSpan.addEventListener('keydown', function (e) { if (e.key === 'Enter') { e.preventDefault(); nameSpan.blur(); } });
    }
    applySessionItemIndicators(div, sess.id, { serverStreamActive: !!sess.stream_active });
    return div;
}

async function refreshSingleSessionRow(sessionId) {
    if (!sessionId || !sessionsList) return;
    try {
        const response = await fetch('/sessions/' + encodeURIComponent(sessionId));
        if (!response.ok) return;
        const sess = await response.json();
        if (!sess || !sess.id) return;
        applySessionPatch({
            session: sess,
            session_id: sess.id,
            stream_active: !!sess.stream_active,
        });
        setSessionServerStreamActive(sess.id, !!sess.stream_active);
        if (sess.unread_result) {
            if (!sessionUnreadComplete.has(sess.id)) {
                sessionUnreadComplete.add(sess.id);
                persistSessionUnread();
            }
        } else if (sessionUnreadComplete.delete(sess.id)) {
            persistSessionUnread();
        }
        if (Number(sess.subagent_running || 0) > 0) {
            sessionUnreadComplete.delete(sess.id);
            persistSessionUnread();
        }
        renderSessionListIfChanged(false);
    } catch (e) {
        console.error('刷新会话摘要失败:', e);
    }
}

let sessionListLoadEpoch = 0;
let sessionListLoadPromise = null;
let sessionListRenderKey = '';
let createNewSessionQueue = Promise.resolve();
let archivedSessionsLoaded = false;
let archivedSessionsCache = null;
let archivedSessionsCount = 0;
let archivedSessionsLoadEpoch = 0;

function syncArchivedSessionStateFromStore() {
    archivedSessionsLoaded = !!sessionStore.archivedLoaded;
    archivedSessionsCache = sessionStore.archivedSessions;
    archivedSessionsCount = sessionStore.archivedCount;
}

function computeSessionListRenderKey() {
    const sessions = sessionStore.list();
    const parts = [
        'cur=' + String(currentSessionId || ''),
        'archivedLoaded=' + (sessionStore.archivedLoaded ? '1' : '0'),
        'archivedCount=' + String(sessionStore.archivedCount || 0),
    ];
    for (let i = 0; i < sessions.length; i += 1) {
        const s = sessions[i];
        if (!s || !s.id) continue;
        parts.push([
            s.id,
            s.name || '',
            s.pinned ? 'p' : '',
            s.archived ? 'a' : '',
            s.stream_active ? 'r' : '',
            s.unread_result ? ('u:' + (s.unread_result_status || 'success')) : '',
            s.last_activity_at || s.updated_at || '',
            s.last_user_preview || '',
            s.subagent_running || 0,
            s.subagent_pending_continue || 0,
            s.subagent_can_continue ? 'c' : '',
        ].join('\u001f'));
    }
    const archived = sessionStore.archivedList();
    for (let j = 0; j < archived.length; j += 1) {
        const a = archived[j];
        if (!a || !a.id) continue;
        parts.push('arch=' + [
            a.id,
            a.name || '',
            a.pinned ? 'p' : '',
            a.unread_result ? ('u:' + (a.unread_result_status || 'success')) : '',
            a.last_activity_at || a.updated_at || '',
            a.last_user_preview || '',
        ].join('\u001f'));
    }
    return parts.join('\u001e');
}

function renderSessionListIfChanged(force) {
    const nextKey = computeSessionListRenderKey();
    if (!force && nextKey === sessionListRenderKey) {
        syncSessionListIndicatorClasses();
        renderSessionTitleFromStore();
        return;
    }
    sessionListRenderKey = nextKey;
    const nextStreamMap = renderSessionListFromStore();
    applyServerStreamActiveMap(nextStreamMap);
    renderSessionTitleFromStore();
}

function clearSessionListError() {
    if (!sessionsList) return;
    sessionsList.classList.remove('sessions-list--error');
    if (sessionsList.dataset.loadError === '1') delete sessionsList.dataset.loadError;
}

function renderSessionListError(message) {
    if (!sessionsList) return;
    sessionListRenderKey = '';
    sessionsList.classList.add('sessions-list--error');
    sessionsList.dataset.loadError = '1';
    sessionsList.innerHTML = '';
    const row = document.createElement('div');
    row.className = 'session-list-error';
    row.setAttribute('role', 'status');
    row.textContent = message || '加载会话列表失败';
    sessionsList.appendChild(row);
}

function applyOptimisticSessionUpdate(sessionId, patch) {
    const sid = String(sessionId || '');
    const current = sessionStore.get(sid);
    if (!current) return null;
    const prev = Object.assign({}, current);
    const next = Object.assign({}, current, patch || {});
    if (Object.prototype.hasOwnProperty.call(patch || {}, 'pinned')) {
        next.pinned_at = next.pinned ? (next.pinned_at || new Date().toISOString()) : null;
    }
    sessionStore.upsert(next);
    if (prev.archived || next.archived) {
        const archivedList = (sessionStore.archivedSessions || []).filter(function (s) {
            return s && s.id !== sid;
        });
        if (next.archived && sessionStore.archivedLoaded) archivedList.unshift(next);
        if (sessionStore.archivedLoaded) {
            sessionStore.setArchivedLoaded(archivedList);
            syncArchivedSessionStateFromStore();
        }
    }
    renderSessionListIfChanged(true);
    return prev;
}

// Event count cache for optimistic UI updates.
const uiEventCountCache = {
    cache: new Map(),
    
    get(sessionId) {
        return this.cache.get(sessionId) || 0;
    },
    
    set(sessionId, count) {
        this.cache.set(sessionId, count);
    },
    
    increment(sessionId) {
        const current = this.get(sessionId);
        this.set(sessionId, current + 1);
        return current + 1;
    },
    
    updateFromServer(sessionId, count) {
        this.set(sessionId, count);
    }
};

async function fetchSessionsStateSnapshot(opts) {
    opts = opts || {};
    const url = '/sessions/state' + (opts.includeArchived ? '?include_archived=true' : '');
    const response = await fetchWithTimeout(url, {}, 12000);
    if (!response.ok) throw new Error('sessions state failed: ' + response.status);
    const snapshot = await response.json();
    if (!snapshot || !Array.isArray(snapshot.sessions)) {
        throw new Error('invalid sessions state response');
    }
    snapshot.include_archived = !!opts.includeArchived;
    return snapshot;
}

async function fetchWithTimeout(url, options, timeoutMs) {
    options = options || {};
    const ms = Number(timeoutMs) > 0 ? Number(timeoutMs) : 15000;
    if (options.signal) return fetch(url, options);
    const controller = new AbortController();
    const timer = setTimeout(function () { controller.abort(); }, ms);
    const nextOptions = Object.assign({}, options, { signal: controller.signal });
    try {
        return await fetch(url, nextOptions);
    } finally {
        clearTimeout(timer);
    }
}

async function loadArchivedSessions(opts) {
    opts = opts || {};
    const loadEpoch = ++archivedSessionsLoadEpoch;
    try {
        const response = await fetchWithTimeout('/sessions?include_archived=true', {}, 15000);
        const sessions = await response.json();
        if (loadEpoch !== archivedSessionsLoadEpoch) return;
        const all = Array.isArray(sessions) ? sessions : [];
        sessionStore.setArchivedLoaded(all);
        syncArchivedSessionStateFromStore();
        renderSessionListIfChanged(!!opts.forceRender);
        clearSessionListError();
    } catch (err) {
        console.error('加载归档目录失败:', err);
        if (!opts.background) throw err;
    }
}

async function loadSessions(opts) {
    opts = opts || {};
    if (sessionListLoadPromise && !opts.force) return sessionListLoadPromise;
    sessionListLoadPromise = loadSessionsInner(opts);
    try {
        return await sessionListLoadPromise;
    } finally {
        sessionListLoadPromise = null;
    }
}

async function loadSessionsInner(opts) {
    const loadEpoch = ++sessionListLoadEpoch;
    sessionStore.ui.loadingSessions = true;
    try {
        let allSessions;
        let snapshot = null;
        
        try {
            snapshot = await fetchSessionsStateSnapshot();
            if (loadEpoch !== sessionListLoadEpoch) return;
            allSessions = Array.isArray(snapshot.sessions) ? snapshot.sessions : [];
        } catch (stateErr) {
            console.error('加载会话状态快照失败，回退至旧接口', stateErr);
            const response = await fetchWithTimeout('/sessions', {}, 12000);
            const archivedCountHeader = response.headers.get('X-Archived-Count');
            if (archivedCountHeader != null && archivedCountHeader !== '') {
                const parsedArchivedCount = Number(archivedCountHeader);
                if (Number.isFinite(parsedArchivedCount) && parsedArchivedCount >= 0) {
                    sessionStore.setArchivedCount(parsedArchivedCount);
                    syncArchivedSessionStateFromStore();
                }
            }
            const sessions = await response.json();
            if (loadEpoch !== sessionListLoadEpoch) return;
            allSessions = Array.isArray(sessions) ? sessions : [];
            snapshot = {
                sessions: allSessions,
                archived_count: archivedSessionsCount,
            };
        }
        applySessionSnapshot(snapshot || { sessions: allSessions, archived_count: archivedSessionsCount });
        syncArchivedSessionStateFromStore();
        allSessions = sessionStore.list();
        
        const idSet = new Set();
        for (let si = 0; si < allSessions.length; si += 1) {
            if (allSessions[si] && allSessions[si].id) idSet.add(allSessions[si].id);
        }
        [...sessionUnreadComplete].forEach(function (uid) {
            if (!idSet.has(uid)) sessionUnreadComplete.delete(uid);
        });
        persistSessionUnread();

        renderSessionListIfChanged(!!opts.forceRender);
        clearSessionListError();
        sessionStore.ui.loadingSessions = false;
        if (opts.refreshArchived && !opts.skipArchivedRefresh && sessionStore.archivedLoaded) {
            void loadArchivedSessions({ background: true });
        }
        return true;
    } catch (error) {
        sessionStore.ui.loadingSessions = false;
        console.error('加载会话列表失败:', error);
        if (sessionStore.list().length > 0) {
            renderSessionListIfChanged(true);
            clearSessionListError();
        } else {
            renderSessionListError('加载会话列表失败');
        }
        return false;
    }
}

async function reconcileRunStateFromServer(opts) {
    opts = opts || {};
    const suppressedBeforeFetch = new Set();
    if (opts.respectStopSuppress) {
        sessionStore.sessionOrder.forEach(function (sid) {
            if (isSessionStreamStopSuppressed(sid)) suppressedBeforeFetch.add(String(sid));
        });
        if (currentSessionId && isSessionStreamStopSuppressed(currentSessionId)) {
            suppressedBeforeFetch.add(String(currentSessionId));
        }
    }
    let snapshot = null;
    try {
        const cur = currentSessionId ? sessionStore.get(currentSessionId) : null;
        snapshot = await fetchSessionsStateSnapshot({
            includeArchived: !!(sessionStore.archivedLoaded || (cur && cur.archived)),
        });
    } catch (e) {
        if (!opts.silent) console.error('reconcile run state failed:', e);
        return;
    }
    applySessionSnapshot(snapshot);
    if (opts.respectStopSuppress) {
        suppressedBeforeFetch.forEach(function (sid) {
            if (isSessionStreamStopSuppressed(sid)) {
                sessionStore.setStreamActive(sid, false);
                const sess = sessionStore.get(sid);
                if (sess) {
                    sess.stream_active = false;
                    sess.run_active = false;
                    sess.run_started_at = null;
                }
                sessionStore.activeRunInfoBySession.delete(sid);
            }
        });
    }
    const active = new Set();
    sessionStore.activeRunInfoBySession.forEach(function (info, sid) {
        if (info && info.run_active === true) active.add(String(sid));
    });
    const localIds = [];
    sessionStore.runsBySession.forEach(function (_run, sid) {
        localIds.push(String(sid));
    });
    localIds.forEach(function (sid) {
        if (!active.has(sid)) {
            var run = getSessionRunState(sid);
            if (run && run.reattached) {
                abortSessionRun(sid, 'reconcile-finished');
            }
        }
    });
    if (currentSessionId && active.has(currentSessionId)) {
        const info = sessionStore.getActiveRunInfo(currentSessionId) || {};
        const run = getSessionRunState(currentSessionId);
        const ctx = run && run.ctx;
        const agg = ctx && ctx.currentProcessGroup && ctx.currentProcessGroup.isConnected
            ? ctx.currentProcessGroup
            : (getVisibleChatStream() && getVisibleChatStream().querySelector('.process-aggregate:last-of-type'));
        if (agg && info.started_at) applyRunStartedAtToProcessGroup(agg, info.started_at);
    }
    syncSessionListIndicatorClasses();
    setSendButtonState();
    renderSessionListIfChanged(false);
}

function showSessionLoadRetry(sessionId) {
    var sid = String(sessionId || '');
    var stream = getVisibleChatStream();
    if (!sid || !stream) return;
    if (stream.querySelector('.session-load-retry')) return;
    var row = document.createElement('div');
    row.className = 'feed-item feed--err session-load-retry';
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'history-load-older-btn';
    btn.textContent = '重新加载';
    btn.addEventListener('click', function (e) {
        e.preventDefault();
        if (typeof discardCachedSessionStream === 'function') discardCachedSessionStream(sid);
        void switchSession(sid, { forceReload: true });
    });
    row.appendChild(btn);
    stream.appendChild(row);
}

async function loadSessionMessages(sessionId, scrollBehavior, opts) {
    const openSessionStartedAt = (typeof performance !== 'undefined' && performance.now)
        ? performance.now()
        : Date.now();
    scrollBehavior = scrollBehavior || 'saved-or-bottom';
    opts = opts || {};
    const loadToken = ++messageLoadEpoch;
    sessionStore.ui.loadingMessages = true;
    suppressTocDuringSessionLoad = true;
    replayingMessages = true;
    resetSessionHistoryPaging();
    try {
        let raw;
        let snapshotTocTurns = null;
        let historySource = 'messages';
        let snapshotTiming = null;
        const canUseSnapshot = !opts.full && opts.useSnapshot !== false && beforeSessionMessageSnapshotAvailable();
        if (canUseSnapshot) {
            try {
                const snapshotUrl = '/sessions/' + encodeURIComponent(sessionId)
                    + '/history_snapshot?turns=' + encodeURIComponent(String(HISTORY_DIALOGUES_PER_PAGE));
                const snapshotResp = await fetchWithTimeout(snapshotUrl, {}, 15000);
                if (snapshotResp.ok) {
                    const snapshot = await snapshotResp.json();
                    if (snapshot && snapshot.ok && snapshot.messages) {
                        raw = snapshot.messages;
                        historySource = 'history_snapshot';
                        snapshotTiming = snapshot.timing && typeof snapshot.timing === 'object'
                            ? snapshot.timing
                            : null;
                        if (typeof uiEventCountCache !== 'undefined' && typeof snapshot.count === 'number') {
                            uiEventCountCache.updateFromServer(sessionId, snapshot.count);
                        }
                        if (Array.isArray(snapshot.user_turns)) {
                            snapshotTocTurns = snapshot.user_turns;
                            if (typeof setTocTurnsForSession === 'function') setTocTurnsForSession(sessionId, snapshot.user_turns);
                        }
                    }
                }
            } catch (snapshotErr) {
                console.warn('history snapshot unavailable, falling back to messages:', snapshotErr);
            }
        }
        if (!raw) {
            let url = '/sessions/' + encodeURIComponent(sessionId) + '/messages';
            if (!opts.full) url += '?turns=' + HISTORY_DIALOGUES_PER_PAGE;
            const response = await fetchWithTimeout(url, {}, 15000);
            if (!response.ok) throw new Error('messages failed: ' + response.status);
            raw = await response.json();
        }
        if (loadToken !== messageLoadEpoch || sessionId !== currentSessionId) return;
        if (getSessionRunState(sessionId) && !opts.allowDuringRun) return;
        document.getElementById('chat-loading')?.remove();
        if (!getVisibleChatStream()) ensureVisibleChatStreamSlot();
        const vis = getVisibleChatStream();
        if (vis) emptyChatStreamKeepingStrip(vis);
        else {
            chatContainer.innerHTML = '';
            ensureVisibleChatStreamSlot();
        }
        markVisibleSessionStreamLoadState(sessionId, 'loading');
        let events;
        let pageMeta = null;
        if (Array.isArray(raw)) {
            events = raw;
        } else if (raw && typeof raw === 'object' && Array.isArray(raw.events)) {
            events = raw.events;
            pageMeta = {
                total: Number(raw.total) || 0,
                range_start: Number(raw.range_start) || 0,
                range_end: Number(raw.range_end) || 0,
                has_older: !!raw.has_older,
            };
            uiEventCountCache.updateFromServer(sessionId, pageMeta.total);
        } else {
            events = [];
        }
        beginMessageReplay(sessionId, pageMeta || {
            total: events.length,
            range_start: 0,
            range_end: events.length,
        });
        if (!opts.full && pageMeta) {
            setSessionHistoryPaging({
                sessionId: sessionId,
                total: pageMeta.total,
                range_start: pageMeta.range_start,
                range_end: pageMeta.range_end,
                has_older: !!pageMeta.has_older,
            });
            ensureHistorySentinel(getVisibleChatStream());
        }
        if (events.length === 0) {
            suppressTocDuringSessionLoad = false;
            setWelcome();
            updateSessionTitle();
            scheduleContextTokensAfterPaint(sessionId);
            applyChatScrollAfterHistoryLoad(sessionId, scrollBehavior);
            markVisibleSessionStreamLoadState(sessionId, 'ok');
            logOpenSessionTiming(sessionId, {
                source: historySource,
                events: 0,
                snapshotTiming: snapshotTiming,
                totalMs: elapsedSince(openSessionStartedAt),
            });
            return true;
        }
        const loadCtx = newDomContext(getVisibleChatStream());
        loadCtx.lastUserEventIndex = -1;
        const indexBase = pageMeta ? pageMeta.range_start : 0;
        const batchSize = opts.full ? 64 : 512;
        for (let evi = 0; evi < events.length; evi += 1) {
            const ev = events[evi];
            if (ev && typeof ev === 'object' && ev.type) {
                reduceAndRenderMessageEvent(loadCtx, ev, {
                    sessionId: sessionId,
                    eventIndex: indexBase + evi,
                    source: 'history',
                });
            }
            if (evi > 0 && evi % batchSize === 0) {
                await new Promise(function (resolve) { setTimeout(resolve, 0); });
                if (loadToken !== messageLoadEpoch || sessionId !== currentSessionId) return;
            }
        }
        if (!opts.full && opts.preloadOlderIfShort && pageMeta && pageMeta.has_older && events.length <= 2) {
            await loadOlderHistoryChunk({ keepTocStable: true });
            if (loadToken !== messageLoadEpoch || sessionId !== currentSessionId) return;
        }
        if (historyLoadScrollsToBottom(sessionId, scrollBehavior)) {
            tocScrollBottomOnNextBuild = true;
        }
        suppressTocDuringSessionLoad = false;
        if (snapshotTocTurns) rebuildToc({ turns: snapshotTocTurns });
        else if (!opts.tocAlreadyStarted) rebuildToc();
        updateSessionTitle();
        updateHistorySentinelVisibility();
        applyChatScrollAfterHistoryLoad(sessionId, scrollBehavior);
        await waitForChatScrollAfterHistoryLoad(sessionId, scrollBehavior);
        if (loadToken !== messageLoadEpoch || sessionId !== currentSessionId) return;
        bindExistingLogs();
        scheduleTocActiveUpdate();
        scheduleContextTokensAfterPaint(sessionId);
        renderTodoPlanForCurrentSession();
        markVisibleSessionStreamLoadState(sessionId, 'ok');
        logOpenSessionTiming(sessionId, {
            source: historySource,
            events: events.length,
            snapshotTiming: snapshotTiming,
            totalMs: elapsedSince(openSessionStartedAt),
        });
        return true;
    } catch (error) {
        console.error('加载会话消息失败:', error);
        document.getElementById('chat-loading')?.remove();
        appendLogVisible('加载历史消息失败', 'error-log');
        markVisibleSessionStreamLoadState(sessionId, 'failed');
        showSessionLoadRetry(sessionId);
        return false;
    } finally {
        if (loadToken === messageLoadEpoch) sessionStore.ui.loadingMessages = false;
        if (loadToken === messageLoadEpoch) suppressTocDuringSessionLoad = false;
        if (loadToken === messageLoadEpoch) replayingMessages = false;
    }
}

function elapsedSince(startedAt) {
    var now = (typeof performance !== 'undefined' && performance.now)
        ? performance.now()
        : Date.now();
    return Math.max(0, Math.round(now - Number(startedAt || now)));
}

function logOpenSessionTiming(sessionId, data) {
    data = data || {};
    var timing = data.snapshotTiming && typeof data.snapshotTiming === 'object' ? data.snapshotTiming : {};
    var backendTotal = Number(timing.total || 0);
    var frontendTotal = Number(data.totalMs || 0);
    if (frontendTotal < 500 && backendTotal < 500) return;
    console.info(
        'open_session_timing session=%s source=%s total=%sms events=%s backend_total=%sms read_page=%sms count=%sms user_turns=%sms',
        sessionId,
        data.source || 'unknown',
        frontendTotal,
        Number(data.events || 0),
        backendTotal,
        Number(timing.read_page || 0),
        Number(timing.count || 0),
        Number(timing.user_turns || 0)
    );
}

function beforeSessionMessageSnapshotAvailable() {
    return true;
}

async function switchSession(sessionId, opts) {
    opts = opts || {};
    if (currentSessionId === sessionId && !opts.forceReload) return;
    if (opts.forceReload && typeof discardCachedSessionStream === 'function') discardCachedSessionStream(sessionId);
    const switchToken = ++switchSessionEpoch;
    suppressTocDuringSessionLoad = true;
    clearTocForSessionLoad();
    clearTodoForSessionLoad();
    pendingRewriteTruncate = null;
    hideRewriteUndoToast();
    clearSessionUnreadState(sessionId);
    const leaving = currentSessionId;
    saveChatScrollForSession(leaving);
    stashInputDraft(leaving);
    prepareStashLeaving(leaving);
    hideSubagentContinueBanner();
    resetSubagentPanelForSession();
    setCurrentSessionState(sessionId);
    localStorage.setItem('lastSessionId', sessionId);
    restoreInputDraft(sessionId);
    if (typeof renderFollowupQueue === 'function') renderFollowupQueue(sessionId);
    if (typeof refreshModelProfileSelector === 'function') refreshModelProfileSelector(sessionId);
    syncSessionListIndicatorClasses();
    setSendButtonState();
    var restoredFromCache = false;
    if (!opts.forceReload && (restoreStreamForRunningSession(sessionId) || (restoredFromCache = restoreCachedSessionStream(sessionId)))) {
        suppressTocDuringSessionLoad = false;
        hideLoading();
        rebuildToc();
        updateSessionTitle();
        scheduleContextTokensAfterPaint(sessionId);
        if (restoredFromCache) restoreCachedSessionScrollPosition(sessionId);
        else applyChatScrollAfterHistoryLoad(sessionId, 'saved-or-bottom');
        renderTodoPlanForCurrentSession();
        if (switchToken !== switchSessionEpoch || sessionId !== currentSessionId) return;
        /* 让 rebuildToc 的 /user_turns fetch 先发出，subagent 面板（含 N 个 /messages）顺序后置，
           避免抢占带宽与主线程，让目录最后才稳态。*/
        setTimeout(function () { refreshSubagentTreePanel(sessionId); }, 0);
        void refreshSingleSessionRow(sessionId);
        setSendButtonState();
        maybeStartStreamPollForSession(sessionId, { skipInitialLoad: true });
        return;
    }
    const vs = getVisibleChatStream();
    resetSessionHistoryPaging();
    if (vs) emptyChatStreamKeepingStrip(vs);
    else {
        chatContainer.innerHTML = '';
        ensureVisibleChatStreamSlot();
    }
    showLoading();
    if (opts.useSnapshot === false && typeof startTocForSessionLoad === 'function') startTocForSessionLoad(sessionId);
    return new Promise(function (resolve) {
        setTimeout(async function () {
        if (switchToken !== switchSessionEpoch || sessionId !== currentSessionId) { resolve(false); return; }
        try {
            var loadedOk = await loadSessionMessages(sessionId, undefined, {
                preloadOlderIfShort: isServerStreamActive(sessionId),
                allowDuringRun: isServerStreamActive(sessionId),
                tocAlreadyStarted: true,
            });
            if (!loadedOk) { resolve(false); return; }
        } catch (error) {
            console.error('切换会话加载失败:', error);
            resolve(false);
            return;
        } finally {
            if (switchToken === switchSessionEpoch && sessionId === currentSessionId) {
                hideLoading();
                sessionStore.ui.loadingMessages = false;
                suppressTocDuringSessionLoad = false;
                replayingMessages = false;
            }
        }
        if (switchToken !== switchSessionEpoch || sessionId !== currentSessionId) { resolve(false); return; }
        /* loadSessionMessages 内部已发起 rebuildToc()；这里再延后一步调用 subagent panel
           重建，保证「目录 → 消息 → 副 agent 按钮」的稳定顺序（无 subagent 的会话表现一致）。*/
        setTimeout(function () { refreshSubagentTreePanel(sessionId); }, 0);
        void refreshSingleSessionRow(sessionId);
        setSendButtonState();
        maybeStartStreamPollForSession(sessionId, { skipInitialLoad: true });
        resolve(true);
        }, 20);
    });
}

async function createNewSession() {
    createNewSessionQueue = createNewSessionQueue.then(
        function () { return createNewSessionInner(); },
        function () { return createNewSessionInner(); }
    );
    return createNewSessionQueue;
}

async function createNewSessionInner() {
    try {
        saveChatScrollForSession(currentSessionId);
        stashInputDraft(currentSessionId);
        prepareStashLeaving(currentSessionId);
        const response = await fetch('/sessions', { method: 'POST' });
        const data = await response.json();
        if (data && data.session) sessionStore.upsert(data.session);
        resetSubagentPanelForSession();
        switchSessionEpoch += 1;
        messageLoadEpoch += 1;
        setCurrentSessionState(data.session_id);
        localStorage.setItem('lastSessionId', currentSessionId);
        restoreInputDraft(currentSessionId);
        if (typeof renderFollowupQueue === 'function') renderFollowupQueue(currentSessionId);
        if (typeof refreshModelProfileSelector === 'function') refreshModelProfileSelector(currentSessionId);
        if (!getVisibleChatStream()) ensureVisibleChatStreamSlot();
        setWelcome();
        replayingMessages = false;
        if (data && data.session) {
            syncArchivedSessionStateFromStore();
            renderSessionListIfChanged(true);
            void refreshSingleSessionRow(data.session_id);
        } else {
            await loadSessions();
        }
        setSendButtonState();
        maybeStartStreamPollForSession(currentSessionId);
        scheduleContextTokensAfterPaint(currentSessionId);
    } catch (error) {
        console.error('创建新会话失败', error);
        appendLogVisible('创建新会话失败', 'error-log');
    }
}
