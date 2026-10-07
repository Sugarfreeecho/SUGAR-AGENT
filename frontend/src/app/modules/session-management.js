function setSendButtonState() {
    syncMessageInputPlaceholder();
    sendBtn.disabled = false;
    const uploadBusy = isChatFileUploadBusy();
    const newSessionPreflight = !currentSessionId && optimisticNewSessionRun;
    const newSessionCreating = !currentSessionId && materializeNewSessionQueue;
    if (uploadBusy) {
        sendBtn.textContent = '上传中';
        sendBtn.classList.remove('is-stop');
        sendBtn.classList.remove('is-followup');
        sendBtn.disabled = true;
        return;
    }
    if (newSessionCreating && !newSessionPreflight) {
        sendBtn.textContent = '创建中';
        sendBtn.classList.remove('is-stop');
        sendBtn.classList.remove('is-followup');
        sendBtn.disabled = true;
        return;
    }
    if (isSessionRunning(currentSessionId) || newSessionPreflight) {
        const run = newSessionPreflight || (typeof getSessionRunState === 'function' ? getSessionRunState(currentSessionId) : null);
        const suppressFollowup = !!(run && run.suppressFollowupButton);
        const hasDraft = (typeof inputHasSendableText === 'function')
            ? inputHasSendableText()
            : !!(messageInput && String(messageInput.value || '').trim());
        const followupEnabled = (typeof isMyAgentFeatureEnabled === 'function') && isMyAgentFeatureEnabled('followupRestart', false);
        sendBtn.innerHTML = (followupEnabled && hasDraft && !suppressFollowup) ? '追问' : '停止 <span class="loader" aria-hidden="true"></span>';
        sendBtn.classList.add('is-stop');
        sendBtn.classList.toggle('is-followup', followupEnabled && hasDraft && !suppressFollowup);
    } else {
        sendBtn.textContent = '发送';
        sendBtn.classList.remove('is-stop');
        sendBtn.classList.remove('is-followup');
        sendBtn.disabled = false;
    }
}

const MESSAGE_INPUT_PLACEHOLDER_DEFAULT = '说说你想做什么…（Enter 发送 · Shift/Ctrl/Cmd + Enter 换行）';
const MESSAGE_INPUT_PLACEHOLDER_RUNNING = 'Agent运行中，输入后续任务';
const MESSAGE_INPUT_PLACEHOLDER_QUEUED = '按 Enter 发送刚加入或第一条待发送任务';

function syncMessageInputPlaceholder() {
    if (!messageInput) return;
    var queue = currentSessionId && typeof getFollowupQueue === 'function'
        ? getFollowupQueue(currentSessionId)
        : [];
    var running = !!(optimisticNewSessionRun || isSessionRunning(currentSessionId));
    var value = queue.some(function (item) { return item && !item.status; })
        ? MESSAGE_INPUT_PLACEHOLDER_QUEUED
        : (running ? MESSAGE_INPUT_PLACEHOLDER_RUNNING : MESSAGE_INPUT_PLACEHOLDER_DEFAULT);
    messageInput.placeholder = typeof translateUiString === 'function'
        ? translateUiString(value)
        : value;
}

function isChatFileUploadBusy() {
    return !!(messageInput && messageInput.dataset.fileUploadBusy === '1');
}

document.addEventListener('myagent:language-change', syncMessageInputPlaceholder);
document.addEventListener('myagent:language-change', function () {
    if (typeof renderSessionListIfChanged === 'function') renderSessionListIfChanged(true);
});

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
    if (!currentSessionId) {
        if (optimisticNewSessionRun) {
            markRunAbortReason(optimisticNewSessionRun, 'user');
            try { optimisticNewSessionRun.controller.abort(); } catch (e) { /* ignore */ }
            optimisticNewSessionRun = null;
            setSendButtonState();
        }
        return;
    }
    const run = getSessionRunState(currentSessionId);
    const sid = currentSessionId;
    const activeInfo = sessionStore.getActiveRunInfo(sid) || {};
    const runId = run && run.runId ? run.runId : (activeInfo.run_id || activeInfo.runId || '');
    if (typeof markFollowupQueueManualOnly === 'function') markFollowupQueueManualOnly(sid);
    suppressSessionServerStreamActive(sid);
    if (!run) {
        setSendButtonState();
        syncSessionListIndicatorClasses();
        renderSessionListIfChanged(false);
        void requestInterrupt(sid, runId, 'user_button');
        setTimeout(function () { reconcileRunStateFromServer({ silent: true, respectStopSuppress: true }); }, 3000);
        return;
    }
    const ctx = run.ctx;
    const reachedServer = run.submitted !== false;
    /* 先同步 abort 本地 fetch 与从 sessionStore 摘除，UI 立即反映「已停止」状态；
       后端 interrupt 走 fire-and-forget，避免被主线程阻塞时按钮响应卡顿。*/
    abortSessionRun(sid, 'user');
    setSendButtonState();
    syncSessionListIndicatorClasses();
    renderSessionListIfChanged(false);
    appendLog(ctx, '已请求停止当前任务', 'status', sid);
    sealProcessGroup(ctx);
    if (reachedServer) void requestInterrupt(sid, runId, 'user_button');
    setTimeout(function () { reconcileRunStateFromServer({ silent: true, respectStopSuppress: true }); }, 3000);
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

function sessionHasUnsentDraft(sessionId) {
    if (!sessionId) return false;
    var draft = Object.prototype.hasOwnProperty.call(draftBySession, sessionId)
        ? draftBySession[sessionId]
        : readStoredInputDraft(sessionId);
    return !!String(draft || '').trim();
}

function syncSessionDraftBadge(itemDiv, sessionId) {
    if (!itemDiv || !sessionId) return;
    var badge = itemDiv.querySelector('.session-draft-badge');
    if (!badge) return;
    var visible = String(sessionId) !== String(currentSessionId || '') && sessionHasUnsentDraft(sessionId);
    badge.hidden = !visible;
    itemDiv.classList.toggle('has-unsent-draft', visible);
}

/** 只同步草稿标签，不重绘会话列表；传入 sessionId 时仅更新对应行。 */
function syncSessionDraftBadges(sessionId) {
    if (!sessionsList) return;
    var targetId = sessionId ? String(sessionId) : '';
    sessionsList.querySelectorAll('.session-item').forEach(function (div) {
        var sid = String(div.dataset.sessionId || '');
        if (!sid || (targetId && sid !== targetId)) return;
        syncSessionDraftBadge(div, sid);
    });
}

/** 同步行内高频动作（置顶）的按下态与文案；状态变了也不重建行。 */
function syncSessionRowQuickActions(itemDiv, sessionId) {
    var btn = itemDiv && itemDiv.querySelector ? itemDiv.querySelector('[data-session-pin]') : null;
    if (!btn) return;
    var sess = findSessionForActions(sessionId, null);
    var pinned = !!(sess && sess.pinned);
    var label = pinned ? '取消置顶' : '置顶会话';
    btn.setAttribute('aria-pressed', pinned ? 'true' : 'false');
    btn.setAttribute('data-ui-tip', label);
    btn.classList.toggle('is-on', pinned);
}

/** 根据 sessionStore / 服务端 stream_active / sessionUnreadComplete 更新红点、绿点 */
function applySessionItemIndicators(itemDiv, sessionId, opts) {
    opts = opts || {};
    if (!itemDiv || !sessionId) return;
    syncSessionDraftBadge(itemDiv, sessionId);
    syncSessionRowQuickActions(itemDiv, sessionId);
    itemDiv.classList.remove('is-generating', 'is-finalizing', 'is-unread-result', 'is-unread-failed');
    var nameEl = itemDiv.querySelector('.session-name');
    if (nameEl) nameEl.removeAttribute('data-ui-tip');
    var sess = sessionStore.get(sessionId);
    var localUnreadResult = sessionUnreadComplete.has(sessionId);
    var isSelectedSession = String(sessionId) === String(currentSessionId || '');
    var hasUnreadResult = !isSelectedSession && (sess ? !!sess.unread_result : localUnreadResult);
    var failed = !!(sess && sess.unread_result_status === 'failed');
    var running = isSessionRunning(sessionId);
    var finalizing = running && sessionStore.isRunFinalizing(sessionId);
    if (running) {
        itemDiv.classList.add(finalizing ? 'is-finalizing' : 'is-generating');
        if (hasUnreadResult) {
            // A completed queued turn is still unread while the next pending
            // turn is running. Combining the classes keeps the pulse animation
            // but changes the dot to the result color.
            itemDiv.classList.add(failed ? 'is-unread-failed' : 'is-unread-result');
        }
        if (nameEl) {
            nameEl.setAttribute(
                'data-ui-tip',
                hasUnreadResult
                    ? (failed ? '已有任务失败，当前任务仍在处理' : '已有任务完成，当前任务仍在处理')
                    : (finalizing ? '回复已生成，正在收尾' : '生成中')
            );
        }
    } else {
        if (!hasUnreadResult) return;
        itemDiv.classList.add(failed ? 'is-unread-failed' : 'is-unread-result');
        if (nameEl) nameEl.setAttribute('data-ui-tip', failed ? '任务失败，点击查看' : '有新回复，点击查看');
    }
    if (nameEl) bindUiHoverTip(nameEl);
}

/** 子代理在对话区打开时，侧栏仍高亮它所属的根主会话。 */
function sidebarHighlightedSessionId() {
    var sid = String(currentSessionId || '');
    if (typeof subagentAddressing !== 'undefined' && subagentAddressing
        && typeof subagentAddressing.sidebarSessionId === 'function') {
        return subagentAddressing.sidebarSessionId(sid);
    }
    return sid;
}

/** 指示器全量同步的本体（同步执行，读取的永远是最新状态）。 */
function performSessionListIndicatorSync() {
    if (!sessionsList) return;
    var highlightedId = sidebarHighlightedSessionId();
    sessionsList.querySelectorAll('.session-item').forEach(function (div) {
        var el = div.querySelector('.session-name[data-id]');
        if (!el) return;
        var sid = el.getAttribute('data-id');
        div.classList.toggle('active', !!sid && sid === highlightedId);
        applySessionItemIndicators(div, sid);
    });
    if (typeof updateAllHumanInteractionSessionBadges === 'function') updateAllHumanInteractionSessionBadges();
}

/** 立即刷新侧栏全部指示点与当前选中项；不依赖 loadSessions 网络回流，与是否切换会话无关。
 *  突发合并：同一帧内被多处（多为 SSE 高频分支）连续调用时只跑一次——幂等操作，合并后状态一致。 */
var sessionIndicatorSyncQueued = false;
function syncSessionListIndicatorClasses() {
    if (sessionIndicatorSyncQueued) return;
    sessionIndicatorSyncQueued = true;
    var run = function () {
        sessionIndicatorSyncQueued = false;
        performSessionListIndicatorSync();
    };
    if (typeof requestAnimationFrame === 'function') requestAnimationFrame(run);
    else run();
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
    document.querySelectorAll('.sidebar-popup.is-open').forEach(function (p) {
        p.classList.remove('is-open');
        var t = p.querySelector('[data-popup-trigger]');
        if (t) t.setAttribute('aria-expanded', 'false');
    });
}
(function bindSessionMenuDocumentCloserOnce() {
    if (window.__myAgentSessionMenuCloser) return;
    window.__myAgentSessionMenuCloser = true;
    document.addEventListener('click', closeAllSessionMenus);
})();

/* ── 侧栏通用弹出菜单（视图选项 / 分组动作 / 会话行动作共用） ──────────────
   结构：<div class="sidebar-popup" data-sidebar-popup>
          <button data-popup-trigger aria-haspopup="menu" aria-expanded="false">…</button>
          <div class="sidebar-popup-menu" role="menu">…</div></div>
   行为对齐 DSH：Esc 关闭并把焦点还给触发按钮、外部 pointerdown 关闭、
   ↑↓/Home/End 在菜单项之间走查。 */
function sidebarPopupMenuItems(popup) {
    if (!popup) return [];
    return Array.prototype.slice.call(
        popup.querySelectorAll('.sidebar-popup-menu [role="menuitem"]:not([disabled]), .sidebar-popup-menu [role="menuitemradio"]:not([disabled])')
    );
}

function setSidebarPopupOpen(popup, open, opts) {
    if (!popup) return;
    var options = opts || {};
    var trigger = popup.querySelector('[data-popup-trigger]');
    var next = !!open;
    if (next) {
        // 同时只允许一个侧栏弹出层（含会话行菜单）。
        document.querySelectorAll('.sidebar-popup.is-open').forEach(function (other) {
            if (other !== popup) setSidebarPopupOpen(other, false);
        });
        document.querySelectorAll('.session-more-wrap.is-open').forEach(function (w) {
            w.classList.remove('is-open');
            var b = w.querySelector('.session-more-btn');
            if (b) b.setAttribute('aria-expanded', 'false');
        });
    }
    popup.classList.toggle('is-open', next);
    if (trigger) trigger.setAttribute('aria-expanded', next ? 'true' : 'false');
    // 菜单展开期间抑制/撤掉悬停提示，避免提示框压住菜单投影。
    if (next && typeof hideUiHoverTipsNow === 'function') hideUiHoverTipsNow();
    if (next && options.focusFirst) {
        var items = sidebarPopupMenuItems(popup);
        if (items.length) requestAnimationFrame(function () { items[0].focus(); });
    }
    if (!next && options.returnFocus && trigger && typeof trigger.focus === 'function') {
        try { trigger.focus(); } catch (e) { /* ignore */ }
    }
}

/** 给一个 .sidebar-popup 绑定开关、键盘与外部关闭；items 变化时由调用方重建菜单内容。 */
function bindSidebarPopup(popup) {
    if (!popup || popup.dataset.popupBound === '1') return;
    popup.dataset.popupBound = '1';
    var trigger = popup.querySelector('[data-popup-trigger]');
    if (!trigger) return;
    if (typeof bindUiHoverTip === 'function') bindUiHoverTip(trigger);
    trigger.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        var willOpen = !popup.classList.contains('is-open');
        // e.detail === 0 表示键盘触发（Enter/Space）：打开后把焦点送给第一项。
        setSidebarPopupOpen(popup, willOpen, { focusFirst: willOpen && e.detail === 0 });
    });
    popup.addEventListener('keydown', function (e) {
        if (!popup.classList.contains('is-open')) return;
        var items = sidebarPopupMenuItems(popup);
        if (!items.length) return;
        if (e.key === 'Escape') {
            e.preventDefault();
            e.stopPropagation();
            setSidebarPopupOpen(popup, false, { returnFocus: true });
            return;
        }
        var idx = items.indexOf(document.activeElement);
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            items[idx < 0 ? 0 : (idx + 1) % items.length].focus();
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            items[idx < 0 ? items.length - 1 : (idx - 1 + items.length) % items.length].focus();
        } else if (e.key === 'Home') {
            e.preventDefault();
            items[0].focus();
        } else if (e.key === 'End') {
            e.preventDefault();
            items[items.length - 1].focus();
        }
    });
}

// 全局只有一个 pointerdown 关闭器：弹出层随列表重绘频繁重建，逐元素挂 document 监听会累积泄漏。
(function bindSidebarPopupDocumentCloserOnce() {
    if (window.__myAgentSidebarPopupCloser) return;
    window.__myAgentSidebarPopupCloser = true;
    document.addEventListener('pointerdown', function (e) {
        var open = document.querySelectorAll('.sidebar-popup.is-open, .session-more-wrap.is-open');
        if (!open.length) return;
        open.forEach(function (popup) {
            if (popup.contains(e.target)) return;
            if (popup.classList.contains('sidebar-popup')) setSidebarPopupOpen(popup, false);
            else {
                popup.classList.remove('is-open');
                var b = popup.querySelector('.session-more-btn');
                if (b) b.setAttribute('aria-expanded', 'false');
            }
        });
    }, true);
})();

var SIDEBAR_ICON_SVG = {
    search: '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="7"></circle><path d="M20 20l-3.5-3.5"></path></svg>',
    sliders: '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 5v14M12 5v14M19 5v14"></path><circle cx="5" cy="14" r="2"></circle><circle cx="12" cy="9" r="2"></circle><circle cx="19" cy="15" r="2"></circle></svg>',
    folderPlus: window.MyAgentIcons.svg('folder-plus'),
    plus: '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M12 5v14M5 12h14"></path></svg>',
    dots: '<svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor" aria-hidden="true"><circle cx="5" cy="12" r="1.6"></circle><circle cx="12" cy="12" r="1.6"></circle><circle cx="19" cy="12" r="1.6"></circle></svg>',
    pin: '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 17v5"></path><path d="M9 3h6l-1 6 3 3v2H7v-2l3-3z"></path></svg>',
    close: '<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"></path></svg>',
    chevron: '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m7 10 5 5 5-5"></path></svg>',
    check: '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12.5l4.5 4.5L19 7"></path></svg>',
    newChat: '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="8.2"></circle><path d="M12 8.6v6.8M8.6 12h6.8"></path></svg>',
};

(function bindSessionListDelegatedSwitcherOnce() {
    if (!sessionsList || window.__myAgentSessionListSwitcher) return;
    window.__myAgentSessionListSwitcher = true;
    // 指针刚进入该行就点了图标（⋯ / 置顶）：那枚图标是 hover 之后才浮出的，
    // 用户来不及"瞄准"它 —— 判定为"想点这一行"，拦下这次点击并切换会话。
    // 行情景：行右侧正是相对时间的位置，用户点那里切会话时会撞上刚浮出的 ⋯。
    // 真正想点图标的人（进入该行 ≥220ms 后才点）不受影响。
    sessionsList.addEventListener('click', function (e) {
        var iconTarget = e.target;
        if (!iconTarget || !iconTarget.closest) return;
        var icon = iconTarget.closest('.session-more-btn, [data-session-pin]');
        if (!icon) return;
        var iconRow = icon.closest('.session-item');
        if (!iconRow || !sessionsList.contains(iconRow)) return;
        var hoverAt = Number(iconRow.dataset.hoverAt || 0);
        if (!hoverAt || Date.now() - hoverAt >= 220) return;
        e.preventDefault();
        e.stopPropagation();
        var iconSid = iconRow.dataset.sessionId;
        if (!iconSid) return;
        if (iconSid === currentSessionId) {
            clearSessionUnreadState(iconSid);
        } else {
            Promise.resolve(switchSession(iconSid)).catch(function (err) {
                console.error('切换会话失败:', err);
            });
        }
    }, true);
    sessionsList.addEventListener('click', function (e) {
        var target = e.target;
        if (!target || !target.closest) return;
        if (target.closest('button, .session-item-actions, .session-more-wrap, .session-more-menu, .sidebar-popup, input, textarea, a')) return;
        if (target.isContentEditable) return;
        var row = target.closest('.session-item');
        if (!row || !sessionsList.contains(row)) return;
        var sid = row.dataset.sessionId;
        if (!sid) {
            var nameEl = row.querySelector('.session-name[data-id]');
            sid = nameEl ? nameEl.getAttribute('data-id') : '';
        }
        if (sid && sid === currentSessionId) {
            clearSessionUnreadState(sid);
        } else if (sid) {
            Promise.resolve(switchSession(sid)).catch(function (err) {
                console.error('切换会话失败:', err);
            });
        }
    });
})();

function buildSessionMoreMenuMarkup() {
    return '<div class="session-more-wrap">'
        + '<button type="button" class="session-more-btn" aria-label="更多操作" aria-expanded="false" aria-haspopup="true" data-ui-tip="更多">'
        + '<span class="session-more-dots" aria-hidden="true"><span></span><span></span><span></span></span></button>'
        + '<div class="session-more-menu" role="menu">'
        + '<button type="button" class="session-menu-pin" role="menuitem"></button>'
        + '<button type="button" class="session-menu-todo" role="menuitem"></button>'
        + '<button type="button" class="session-menu-rename" role="menuitem">重命名</button>'
        + '<button type="button" class="session-menu-archive" role="menuitem"></button>'
        + '<div class="session-menu-separator" role="separator"></div>'
        + '<button type="button" class="session-menu-export" role="menuitem">导出会话</button>'
        + '<button type="button" class="session-menu-delete" role="menuitem">删除会话</button>'
        + '</div></div>';
}

function findSessionForActions(sessionId, fallback) {
    var sid = String(sessionId || '');
    var current = sessionStore.get(sid);
    if (current) return current;
    if (sessionStore.archivedLoaded) {
        current = (sessionStore.archivedSessions || []).find(function (item) {
            return item && String(item.id) === sid;
        });
    }
    return current || fallback || null;
}

function syncSessionMenuLabels(wrap, sess) {
    if (!wrap || !sess) return;
    wrap._sessionMenuSession = sess;
    var pin = wrap.querySelector('.session-menu-pin');
    var todo = wrap.querySelector('.session-menu-todo');
    var archive = wrap.querySelector('.session-menu-archive');
    if (pin) pin.textContent = sess.pinned ? '取消置顶' : '置顶会话';
    if (todo) todo.textContent = sess.todo ? '取消待办' : '设为待办';
    if (archive) archive.textContent = sess.archived ? '取消归档' : '归档会话';
}

function beginSidebarMetadataMutation() {
    // Invalidate list/archive loads already in flight. Direct reconciliation
    // calls are independently fenced by sessionStore.shouldAcceptSnapshot().
    sessionListLoadEpoch += 1;
    archivedSessionsLoadEpoch += 1;
    return sessionStore.beginMetadataMutation();
}

function commitSidebarMetadataMutation(token, responsePayload) {
    sessionListLoadEpoch += 1;
    archivedSessionsLoadEpoch += 1;
    sessionStore.commitMetadataMutation(
        token,
        responsePayload && responsePayload.state_revision
    );
}

function cancelSidebarMetadataMutation(token) {
    sessionListLoadEpoch += 1;
    archivedSessionsLoadEpoch += 1;
    sessionStore.cancelMetadataMutation(token);
}

async function toggleSessionPinnedFromMenu(sess) {
    const mutationToken = beginSidebarMetadataMutation();
    let mutationCommitted = false;
    let previous = null;
    try {
        const formData = new FormData();
        const nextPinned = !sess.pinned;
        previous = applyOptimisticSessionUpdate(sess.id, { pinned: nextPinned });
        formData.append('pinned', nextPinned ? 'true' : 'false');
        const response = await fetchWithTimeout(
            '/sessions/' + encodeURIComponent(sess.id) + '/pin',
            { method: 'PUT', body: formData },
            12000
        );
        if (!response.ok) {
            throw new Error('pin failed: ' + response.status);
        }
        const responsePayload = await response.json().catch(function () { return null; });
        commitSidebarMetadataMutation(mutationToken, responsePayload);
        mutationCommitted = true;
        await refreshSingleSessionRow(sess.id);
    } catch (err) {
        if (!mutationCommitted) {
            cancelSidebarMetadataMutation(mutationToken);
            if (previous) applyOptimisticSessionUpdate(sess.id, previous);
        }
        console.error('置顶失败', err);
    }
}

async function toggleSessionTodoFromMenu(sess) {
    const mutationToken = beginSidebarMetadataMutation();
    let mutationCommitted = false;
    let previous = null;
    try {
        const formData = new FormData();
        const nextTodo = !sess.todo;
        previous = applyOptimisticSessionUpdate(sess.id, { todo: nextTodo });
        formData.append('todo', nextTodo ? 'true' : 'false');
        const response = await fetchWithTimeout(
            '/sessions/' + encodeURIComponent(sess.id) + '/todo',
            { method: 'PUT', body: formData },
            12000
        );
        if (!response.ok) {
            throw new Error('todo failed: ' + response.status);
        }
        const responsePayload = await response.json().catch(function () { return null; });
        commitSidebarMetadataMutation(mutationToken, responsePayload);
        mutationCommitted = true;
        await refreshSingleSessionRow(sess.id);
    } catch (err) {
        if (!mutationCommitted) {
            cancelSidebarMetadataMutation(mutationToken);
            if (previous) applyOptimisticSessionUpdate(sess.id, previous);
        }
        console.error('待办设置失败', err);
    }
}

async function toggleSessionArchivedFromMenu(sess) {
    const mutationToken = beginSidebarMetadataMutation();
    let mutationCommitted = false;
    let previous = null;
    try {
        const formData = new FormData();
        const nextArchived = !sess.archived;
        previous = applyOptimisticSessionUpdate(sess.id, { archived: nextArchived });
        formData.append('archived', nextArchived ? 'true' : 'false');
        const response = await fetchWithTimeout(
            '/sessions/' + encodeURIComponent(sess.id) + '/archive',
            { method: 'PUT', body: formData },
            12000
        );
        if (!response.ok) {
            throw new Error('archive failed: ' + response.status);
        }
        const responsePayload = await response.json().catch(function () { return null; });
        commitSidebarMetadataMutation(mutationToken, responsePayload);
        mutationCommitted = true;
        await refreshSingleSessionRow(sess.id);
        if (!nextArchived && sessionStore.archivedLoaded) {
            await loadArchivedSessions({ background: true, refresh: true, forceRender: true });
        }
    } catch (err) {
        if (!mutationCommitted) {
            cancelSidebarMetadataMutation(mutationToken);
            if (previous) applyOptimisticSessionUpdate(sess.id, previous);
        }
        console.error('归档失败', err);
    }
}

async function renameSessionFromMenu(sess) {
    var requestedName = await openUiModal({
        title: '重命名会话',
        subtitle: '编辑会话名称',
        message: '',
        inputLabel: '会话名称',
        inputValue: String(sess.name || ''),
        inputMaxLength: 160,
        inputRequired: true,
        confirmText: '保存名称',
        cancelText: '取消',
    });
    if (typeof requestedName !== 'string') return;
    var newName = requestedName.trim().slice(0, 160);
    if (!newName || newName === String(sess.name || '')) return;
    const mutationToken = beginSidebarMetadataMutation();
    let mutationCommitted = false;
    const previous = applyOptimisticSessionUpdate(sess.id, { name: newName });
    if (currentSessionId === sess.id) updateSessionTitle();
    try {
        const formData = new FormData();
        formData.append('name', newName);
        const response = await fetchWithTimeout(
            '/sessions/' + encodeURIComponent(sess.id) + '/name',
            { method: 'PUT', body: formData },
            12000
        );
        if (!response.ok) throw new Error('rename failed: ' + response.status);
        const responsePayload = await response.json().catch(function () { return null; });
        commitSidebarMetadataMutation(mutationToken, responsePayload);
        mutationCommitted = true;
        await refreshSingleSessionRow(sess.id);
        if (currentSessionId === sess.id) updateSessionTitle();
    } catch (err) {
        console.error('重命名失败', err);
        if (!mutationCommitted) {
            cancelSidebarMetadataMutation(mutationToken);
            if (previous) applyOptimisticSessionUpdate(sess.id, previous);
        }
        if (currentSessionId === sess.id) updateSessionTitle();
    }
}

async function exportSessionFromMenu(sess) {
    var confirmed = await openUiModal({
        title: '导出会话',
        subtitle: '下载会话文件',
        message: '将会话「' + String(sess.name || '未命名') + '」对应的 session 文件夹压缩为 ZIP 并下载。',
        confirmText: '确认导出',
        cancelText: '取消',
    });
    if (!confirmed) return;
    var link = document.createElement('a');
    link.href = '/sessions/' + encodeURIComponent(sess.id) + '/export';
    link.download = 'session-' + String(sess.id || 'export') + '.zip';
    link.hidden = true;
    document.body.appendChild(link);
    link.click();
    link.remove();
}

async function deleteSessionFromMenu(sess, rowDiv) {
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
    if (wasArchivedLoaded && sess.archived) {
        const archivedBeforeDelete = sessionStore.archivedSessions || [];
        const deletedArchiveIndex = archivedBeforeDelete.findIndex(function (s) {
            return s && String(s.id) === deletedSessionId;
        });
        sessionStore.setArchivedLoaded(archivedBeforeDelete.filter(function (s) {
            return s && String(s.id) !== deletedSessionId;
        }), {
            visibleCount: Math.max(
                0,
                sessionStore.archivedVisibleCount
                    - (deletedArchiveIndex >= 0 && deletedArchiveIndex < sessionStore.archivedVisibleCount ? 1 : 0)
            ),
            totalCount: Math.max(0, sessionStore.archivedCount - 1),
        });
        syncArchivedSessionStateFromStore();
    }
    renderSessionListIfChanged(true);
    if (rowDiv && rowDiv.parentNode) rowDiv.remove();
    sessionUnreadComplete.delete(deletedSessionId);
    scheduleTitleGenerationRefresh(deletedSessionId, false);
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
    void requestInterrupt(deletedSessionId, '', 'session_deleted');
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
}

function bindSessionActionMenu(wrap, getSession, rowDiv) {
    if (!wrap || wrap.dataset.sessionMenuBound === '1') return;
    wrap.dataset.sessionMenuBound = '1';
    var moreBtn = wrap.querySelector('.session-more-btn');
    if (moreBtn) {
        bindUiHoverTip(moreBtn);
        moreBtn.addEventListener('click', function (e) {
            e.stopPropagation();
            var wasOpen = wrap.classList.contains('is-open');
            closeAllSessionMenus();
            var sess = getSession();
            if (!sess) return;
            syncSessionMenuLabels(wrap, sess);
            if (!wasOpen) {
                wrap.classList.add('is-open');
                moreBtn.setAttribute('aria-expanded', 'true');
                // 打开后把焦点留在触发按钮上：↑↓/Esc 的键盘走查才有事件起点。
                try { moreBtn.focus(); } catch (err) { /* ignore */ }
                if (typeof hideUiHoverTipsNow === 'function') hideUiHoverTipsNow();
            }
        });
    }
    // DSH 对齐：Esc 关闭并把焦点还给触发按钮，↑↓/Home/End 在菜单项之间走查。
    wrap.addEventListener('keydown', function (e) {
        var menu = wrap.querySelector('.session-more-menu');
        if (!menu || !wrap.classList.contains('is-open')) return;
        var items = Array.prototype.slice.call(menu.querySelectorAll('[role="menuitem"]'));
        if (!items.length) return;
        if (e.key === 'Escape') {
            e.preventDefault();
            e.stopPropagation();
            wrap.classList.remove('is-open');
            if (moreBtn) {
                moreBtn.setAttribute('aria-expanded', 'false');
                try { moreBtn.focus(); } catch (err) { /* ignore */ }
            }
            return;
        }
        var idx = items.indexOf(document.activeElement);
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            items[idx < 0 ? 0 : (idx + 1) % items.length].focus();
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            items[idx < 0 ? items.length - 1 : (idx - 1 + items.length) % items.length].focus();
        } else if (e.key === 'Home') {
            e.preventDefault();
            items[0].focus();
        } else if (e.key === 'End') {
            e.preventDefault();
            items[items.length - 1].focus();
        }
    });
    wrap.addEventListener('click', function (e) {
        var target = e.target && e.target.closest ? e.target.closest('[role="menuitem"]') : null;
        if (!target || !wrap.contains(target)) return;
        var handler = target.classList.contains('session-menu-pin') ? toggleSessionPinnedFromMenu
            : target.classList.contains('session-menu-todo') ? toggleSessionTodoFromMenu
                : target.classList.contains('session-menu-rename') ? renameSessionFromMenu
                    : target.classList.contains('session-menu-archive') ? toggleSessionArchivedFromMenu
                        : target.classList.contains('session-menu-export') ? exportSessionFromMenu
                            : target.classList.contains('session-menu-delete') ? deleteSessionFromMenu
                                : null;
        if (!handler) return;
        e.stopPropagation();
        closeAllSessionMenus();
        var sess = getSession();
        if (!sess) return;
        Promise.resolve(handler(sess, rowDiv)).catch(function (err) {
            console.error('会话菜单操作失败:', err);
        });
    });
}

var titlebarSessionMenuSnapshot = null;

function getTitlebarSessionForActions(host, wrap) {
    var sessionId = (host && host.dataset.sessionId) || currentSessionId;
    return findSessionForActions(sessionId, wrap && wrap._sessionMenuSession)
        || titlebarSessionMenuSnapshot;
}

function syncTitlebarSessionMenu(sess) {
    var host = document.getElementById('breadcrumb-session-actions');
    if (!host) return;
    titlebarSessionMenuSnapshot = sess ? Object.assign({}, titlebarSessionMenuSnapshot || {}, sess) : null;
    host.dataset.sessionId = titlebarSessionMenuSnapshot ? String(titlebarSessionMenuSnapshot.id || '') : '';
    host.classList.toggle('hidden', !sess);
    var wrap = host.querySelector('.session-more-wrap');
    if (wrap && titlebarSessionMenuSnapshot) syncSessionMenuLabels(wrap, titlebarSessionMenuSnapshot);
}

(function mountTitlebarSessionMenu() {
    var host = document.getElementById('breadcrumb-session-actions');
    if (!host || host.dataset.sessionMenuMounted === '1') return;
    host.dataset.sessionMenuMounted = '1';
    host.innerHTML = buildSessionMoreMenuMarkup();
    var wrap = host.querySelector('.session-more-wrap');
    bindSessionActionMenu(wrap, function () {
        return getTitlebarSessionForActions(host, wrap);
    }, null);
    syncTitlebarSessionMenu(currentSessionId ? findSessionForActions(currentSessionId, null) : null);
})();

/** 创建并绑定单条会话及其分区操作菜单。 */
function buildAndBindSessionRow(sess, allSessions, nextStreamMap) {
    const div = document.createElement('div');
    div.className = 'session-item';
    div.dataset.sessionId = sess.id || '';
    // 记录指针进入本行的时刻（见上面的 capture 拦截）：用于区分"点这一行"与"点浮出的图标"。
    div.addEventListener('mouseenter', function () {
        div.dataset.hoverAt = String(Date.now());
    });
    if (sidebarHighlightedSessionId() === sess.id) div.classList.add('active');
    if (sess.id) nextStreamMap[sess.id] = !!sess.stream_active;
    if (sess.id) scheduleTitleGenerationRefresh(sess.id, !!sess.title_generation_pending);
    var displayName = typeof localizeSessionPlaceholderName === 'function'
        ? localizeSessionPlaceholderName(sess.name)
        : (sess.name || '');
    div.innerHTML = '<div class="session-item-head">'
        + '<div class="session-item-main">'
        + '<div class="session-item-title-row">'
        + '<span class="session-name" data-id="' + sess.id + '" data-original="' + escapeHtml(sess.name) + '">' + escapeHtml(displayName) + '</span>'
        + '<span class="session-todo-badge" aria-label="待办"' + (sess.todo ? '' : ' hidden') + '>待办</span>'
        + '<span class="session-draft-badge" aria-label="草稿" hidden>草稿</span>'
        + '<span class="session-item-date"></span>'
        // 置顶标记（DSH 同款）：行尾、相对时间之后的一枚 16px 图钉；hover 时与时间一起淡出，
        // 把位置让给行内动作（置顶/⋯），避免同一位置出现两个图钉。
        + '<span class="session-pin-mark" aria-label="置顶" title="置顶"' + (sess.pinned ? '' : ' hidden') + '>' + SIDEBAR_ICON_SVG.pin + '</span>'
        + '</div>'
        + '<div class="session-last-query"></div>'
        + '</div>'
        + '<div class="session-item-actions">'
        + '<button type="button" class="session-row-icon session-row-pin" data-session-pin aria-label="置顶会话" aria-pressed="false" data-ui-tip="置顶会话">'
        + SIDEBAR_ICON_SVG.pin + '</button>'
        + buildSessionMoreMenuMarkup()
        + '</div>'
        + '</div>';
    if (typeof updateHumanInteractionSessionBadge === 'function') {
        setTimeout(function () { updateHumanInteractionSessionBadge(sess.id); }, 0);
    }
    var wsLine = formatSessionListSubtitle(sess);
    var wsEl = div.querySelector('.session-last-query');
    if (wsEl) wsEl.textContent = wsLine;
    var dateEl = div.querySelector('.session-item-date');
    var dateLine = '';
    if (dateEl) {
        // 行列尾用相对时间（DSH 风格），完整时间仍在整行 tooltip 里。
        // 活动时间戳落一份在 DOM 上：30 秒共享时钟据此做纯文本刷新（不动列表结构）。
        var activityTs = typeof sessionActivityTimestampMs === 'function' ? sessionActivityTimestampMs(sess) : 0;
        if (activityTs > 0) dateEl.setAttribute('data-activity-at', String(activityTs));
        dateLine = typeof formatSessionListRelativeTime === 'function'
            ? formatSessionListRelativeTime(sess)
            : '';
        dateEl.textContent = dateLine || '';
    }
    var itemTip = typeof buildSessionItemTooltip === 'function' ? buildSessionItemTooltip(sess) : '';
    if (itemTip) {
        div.setAttribute('data-ui-tip', itemTip);
        bindUiHoverTip(div);
    }
    var moreWrap = div.querySelector('.session-more-wrap');
    syncSessionMenuLabels(moreWrap, sess);
    bindSessionActionMenu(moreWrap, function () {
        return findSessionForActions(sess.id, sess);
    }, div);
    var pinBtn = div.querySelector('[data-session-pin]');
    if (pinBtn) {
        bindUiHoverTip(pinBtn);
        pinBtn.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            var target = findSessionForActions(sess.id, sess);
            if (!target) return;
            Promise.resolve(toggleSessionPinnedFromMenu(target)).catch(function (err) {
                console.error('置顶失败:', err);
            });
                // 点「置顶」按钮时也切换到该会话：行尾这个位置在原版里就是"点行切会话"的热区，
                // 用户期望点这里能进入该会话（置顶动作照旧执行）。
                if (String(sess.id) !== String(currentSessionId || '') && typeof switchSession === 'function') {
                    Promise.resolve(switchSession(sess.id)).catch(function (err) {
                        console.error('切换会话失败:', err);
                    });
                }
        });
    }
    var nameEl = div.querySelector('.session-name');
    if (nameEl) {
        nameEl.addEventListener('dblclick', function (e) {
            e.preventDefault();
            e.stopPropagation();
            var current = findSessionForActions(sess.id, sess);
            if (!current) return;
            Promise.resolve(renameSessionFromMenu(current)).catch(function (err) {
                console.error('双击重命名会话失败:', err);
            });
        });
    }
    applySessionItemIndicators(div, sess.id, { serverStreamActive: !!sess.stream_active });
    ensureSidebarTextTimesAutoRefresh();
    return div;
}

/** 侧栏行时间自动刷新（学 DSH 的 relative-clock）：30 秒共享节拍（经统一节拍器）+ 聚焦/可见性即时补拍。
 *  只更新 .session-item-date 的文本，不触碰列表结构。 */
function refreshSessionListTimes(root) {
    var scope = root || document;
    if (!scope || !scope.querySelectorAll) return;
    if (typeof formatSessionListRelativeTimeFromTs !== 'function') return;
    var now = Date.now();    // 一次采样：列表所有行共用同一 now（与 DSH 的行 props 传递方式一致）
    scope.querySelectorAll('.session-item-date[data-activity-at]').forEach(function (el) {
        var ts = Number(el.getAttribute('data-activity-at')) || 0;
        var txt = ts > 0 ? formatSessionListRelativeTimeFromTs(ts, now) : '';
        if (el.textContent !== txt) el.textContent = txt;
    });
}

// ═══════════════════════════════════════════════════════════
// 侧栏统一刷新节拍（学 DSH 的共享时钟思路）
//   一个动态定时器驱动所有周期性刷新任务：任务各自带周期与可见性策略；
//   「只在可见时有意义」的任务在窗口隐藏时整体跳过；恢复可见/聚焦时立即补拍。
//   取代此前彼此独立的 5s / 30s / 60s 三个 setInterval。
// ═══════════════════════════════════════════════════════════
var sidebarRefreshTasks = [];
var sidebarRefreshTimer = null;

function registerSidebarRefreshTask(key, everyMs, run, opts) {
    opts = opts || {};
    if (!key || typeof run !== 'function') return;
    var existing = sidebarRefreshTasks.find(function (t) { return t.key === key; });
    if (existing) {
        existing.everyMs = Math.max(1000, Number(everyMs) || 30000);
        existing.run = run;
        existing.runWhenHidden = !!opts.runWhenHidden;
    } else {
        // lastAt = 0：注册后的第一次到期判定即为「立即执行」（保留各任务"启动先跑一次"的旧语义）。
        sidebarRefreshTasks.push({
            key: key,
            everyMs: Math.max(1000, Number(everyMs) || 30000),
            run: run,
            runWhenHidden: !!opts.runWhenHidden,
            lastAt: 0,
        });
    }
    scheduleSidebarRefreshTimer();
}

function scheduleSidebarRefreshTimer() {
    if (sidebarRefreshTimer) { clearTimeout(sidebarRefreshTimer); sidebarRefreshTimer = null; }
    var now = Date.now();
    var nextIn = Infinity;
    sidebarRefreshTasks.forEach(function (t) {
        if (document.hidden && !t.runWhenHidden) return;
        nextIn = Math.min(nextIn, Math.max(t.lastAt + t.everyMs - now, 0));
    });
    // 全部任务都被隐藏跳过时不再武装定时器，等 visibilitychange 重新校准。
    if (!isFinite(nextIn)) return;
    sidebarRefreshTimer = setTimeout(runSidebarRefreshDue, Math.max(nextIn, 16));
}

function runSidebarRefreshDue() {
    sidebarRefreshTimer = null;
    var now = Date.now();
    sidebarRefreshTasks.forEach(function (t) {
        if (document.hidden && !t.runWhenHidden) return;
        if (now - t.lastAt < t.everyMs) return;
        t.lastAt = now;
        try { t.run(); } catch (e) { /* 单任务失败不影响其它任务 */ }
    });
    scheduleSidebarRefreshTimer();
}

/** 恢复可见 / 聚焦时立即补拍「可见才有意义」的任务（跳过常驻任务，避免聚焦触发额外网络请求）。 */
function catchUpSidebarRefresh() {
    var now = Date.now();
    sidebarRefreshTasks.forEach(function (t) {
        if (t.runWhenHidden || document.hidden) return;
        t.lastAt = now;
        try { t.run(); } catch (e) { /* ignore */ }
    });
    scheduleSidebarRefreshTimer();
}

document.addEventListener('visibilitychange', function () {
    if (document.hidden) scheduleSidebarRefreshTimer();   // 隐藏：按隐藏策略重排
    else catchUpSidebarRefresh();                          // 恢复可见：立即补拍
});
window.addEventListener('focus', catchUpSidebarRefresh);

/** 只读调试句柄：用于自动化验证节拍统一与任务周期。 */
window.__sidebarRefreshDebug = function () {
    return sidebarRefreshTasks.map(function (t) {
        return { key: t.key, everyMs: t.everyMs, runWhenHidden: t.runWhenHidden, lastAt: t.lastAt };
    });
};

/** 两类时间文案（侧栏相对时间 + 消息绝对时间）共用一个 30 秒任务：
 *  同属分钟粒度、同属"只改文本"，分两个任务只是重复；合并后一拍完成、状态天然一致。 */
function ensureSidebarTextTimesAutoRefresh() {
    if (window.__sidebarTextTimesBound) return;
    window.__sidebarTextTimesBound = true;
    registerSidebarRefreshTask('text-times', 30000, function () {
        refreshSessionListTimes();
        if (typeof refreshUserMessageTimes === 'function') refreshUserMessageTimes(document);
    }, { runWhenHidden: false });
}

const sessionTitleRefreshState = Object.create(null);

function scheduleTitleGenerationRefresh(sessionId, pending) {
    const sid = String(sessionId || '');
    if (!sid) return;
    let state = sessionTitleRefreshState[sid];
    if (!pending) {
        if (state && state.timer) clearTimeout(state.timer);
        delete sessionTitleRefreshState[sid];
        return;
    }
    if (!state) state = sessionTitleRefreshState[sid] = { attempts: 0, timer: null };
    if (state.timer || state.attempts >= 60) return;
    const delayMs = Math.min(10000, Math.round(1000 * Math.pow(1.45, state.attempts)));
    state.timer = setTimeout(function () {
        state.timer = null;
        state.attempts += 1;
        void refreshSingleSessionRow(sid);
    }, delayMs);
}

const sessionNameRecheckState = Object.create(null);

/**
 * run 结束后对「名字可能刚生成」的会话做有限复查（兜底）。
 *
 * 标题由服务端后台 worker 生成，前端只在 title_generation_pending 窗口内轮询；
 * 一旦本次 run 的收尾请求与「生成完成」擦肩而过（错过窗口），会话名会一直停留
 * 在旧值，直到用户手动切换会话。这里以 run 结束时的名字为基线短周期复查：
 * 名字一变立即停止；到上限（默认 30s）无变化也停止。
 */
function scheduleSessionNameRecheck(sessionId, opts) {
    const sid = String(sessionId || '');
    if (!sid || !sessionsList) return;
    const baseline = String((opts && opts.baseline) || '');
    const maxAttempts = Math.max(1, Math.min(60, Number((opts && opts.maxAttempts) || 15)));
    const delayMs = Math.max(600, Number((opts && opts.delayMs) || 2000));
    let state = sessionNameRecheckState[sid];
    if (!state) {
        state = sessionNameRecheckState[sid] = { attempts: 0, timer: null, baseline: '', maxAttempts: maxAttempts, delayMs: delayMs };
    }
    if (baseline) state.baseline = baseline;
    state.maxAttempts = maxAttempts;
    state.delayMs = delayMs;
    if (state.timer) return;
    const tick = async function () {
        state.timer = null;
        state.attempts += 1;
        await refreshSingleSessionRow(sid);
        const live = sessionNameRecheckState[sid];
        if (!live) return;
        const session = sessionStore.get(sid);
        const currentName = session ? String(session.name || '') : '';
        if (currentName && live.baseline && currentName !== live.baseline) {
            delete sessionNameRecheckState[sid];
            return;
        }
        if (live.attempts >= live.maxAttempts) {
            delete sessionNameRecheckState[sid];
            return;
        }
        live.timer = setTimeout(tick, live.delayMs);
    };
    state.timer = setTimeout(tick, delayMs);
}

async function refreshSingleSessionRow(sessionId) {
    if (!sessionId || !sessionsList) return;
    try {
        const response = await fetch('/sessions/' + encodeURIComponent(sessionId));
        if (!response.ok) return;
        const sess = await response.json();
        if (!sess || !sess.id) return;
        scheduleTitleGenerationRefresh(sess.id, !!sess.title_generation_pending);
        if (sess.is_subagent) {
            // Child details must be addressable without inserting a duplicate
            // row into the root-session sidebar.
            sessionStore.sessionsById.set(String(sess.id), sess);
            setSessionServerStreamActive(sess.id, !!sess.stream_active);
        } else {
            applySessionPatch({
                session: sess,
                session_id: sess.id,
            });
        }
        const appliedSession = sessionStore.get(sess.id) || sess;
        sessionStore.applyActiveRunForSession(
            sess.id,
            sess.active_run || (sess.run_active ? {
                session_id: sess.id,
                run_active: true,
                started_at: sess.run_started_at || null,
            } : null)
        );
        if (appliedSession.unread_result) {
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
        if (typeof subagentComposerUi !== 'undefined' && subagentComposerUi) {
            subagentComposerUi.syncFromSessionSummary(sess.id, sess);
        }
        renderSessionListIfChanged(false);
        if (!sess.is_subagent && typeof maybeAutoResumeInterruptedReact === 'function') {
            maybeAutoResumeInterruptedReact(sessionId, sess);
        }
    } catch (e) {
        console.error('刷新会话摘要失败:', e);
    }
}

let sessionListLoadEpoch = 0;
let sessionListLoadPromise = null;
let sessionListLayoutKey = '';
let sessionListContentMap = null;
let materializeNewSessionQueue = null;
// 点“新会话”后立即启动的后台预取（服务端隐藏草稿会话）：{ sessionId, response, session }。
// 页面内重复点击与刷新后重新进入草稿态都复用它，避免把会话文件创建算进首条消息的等待。
let pendingNewSession = null;
let prefetchNewSessionPromise = null;
let prefetchNewSessionWorkDir = null;
const PENDING_NEW_SESSION_KEY = 'myagent-pending-new-session-id';
// 下一个新会话要用的工作目录（绝对路径）。由「在新工作目录新建会话」设置，
// 随 POST /sessions 的 work_dir 字段提交；会话创建后即清空，回到全局默认目录。
let newSessionWorkDir = '';
let newSessionWorkDirRevision = 0;
let archivedSessionsLoaded = false;
let archivedSessionsCache = null;
let archivedSessionsCount = 0;
let archivedSessionsLoadEpoch = 0;

function syncArchivedSessionStateFromStore() {
    archivedSessionsLoaded = !!sessionStore.archivedLoaded;
    archivedSessionsCache = sessionStore.archivedSessions;
    archivedSessionsCount = sessionStore.archivedCount;
}

/** 渲染键拆两半（增量渲染的地基）：
 *  - 布局键：分组方式/筛选 + 实际渲染出的 (区块·分组·会话) 有序序列 + 归档计数类装饰。
 *    只在"结构或顺序"变化时改变（新建/删除/置顶/归档/排序变化 → 整表重建）。
 *  - 内容键：每会话的"可见字段"指纹（名字/待办/活动时间/预览/工作目录…）。
 *    纯内容变化可以只替换受影响的行，不再整表重建。 */
function computeSessionListLayoutKey() {
    const sections = selectSessionSections();
    const query = (typeof getSessionListSearchQuery === 'function') ? getSessionListSearchQuery() : '';
    const parts = [
        'groupBy=' + (typeof getSessionGroupBy === 'function' ? getSessionGroupBy() : 'time'),
        'q=' + query,
        'archive=' + (typeof getSessionArchiveFilter === 'function' ? getSessionArchiveFilter() : 'show'),
        'archivedLoaded=' + (sessionStore.archivedLoaded ? '1' : '0'),
        'archivedCount=' + String(sessionStore.archivedCount || 0),
        'archivedVisible=' + String(sessionStore.archivedVisibleCount || 0),
        'searching=' + (query ? '1' : '0'),
    ];
    const pushIds = function (tag, list) {
        if (!Array.isArray(list)) return;
        for (let i = 0; i < list.length; i += 1) {
            const s = list[i];
            if (s && s.id) parts.push(tag + ':' + s.id);
        }
    };
    pushIds('p', sections.pinned);
    if (Array.isArray(sections.normalGroups) && sections.normalGroups.length) {
        sections.normalGroups.forEach(function (group) {
            parts.push('g:' + String((group && group.key) || ''));
            // 实际渲染出的行 = 配额截断后的集合；「显示更多」按钮存在与否也进键，
            // 展开/收起时布局键变化 → 触发整表重建。
            var vis = (group && group.isWorkDirGroup && typeof sessionGroupSessionsVisible === 'function')
                ? sessionGroupSessionsVisible(group, { noLimit: !!query })
                : { rows: (group && group.sessions) || [], hiddenCount: 0 };
            pushIds('n', vis.rows);
            if (vis.hiddenCount > 0) parts.push('of:' + String((group && group.key) || ''));
        });
    } else {
        pushIds('n', sections.normal);
    }
    pushIds('a', sections.archived);
    return parts.join('\u001e');
}

function computeSessionListContentMap() {
    const map = Object.create(null);
    const stamp = function (s) {
        if (!s || !s.id) return;
        map[s.id] = [
            s.name || '',
            s.pinned ? 'p' : '',
            s.todo ? 't' : '',
            s.archived ? 'a' : '',
            s.last_activity_at || s.updated_at || '',
            s.last_user_preview || '',
            s.work_dir || '',
            s.work_dir_label || '',
            s.work_dir_is_default ? 'd' : '',
        ].join('\u001f');
    };
    sessionStore.list().forEach(stamp);
    sessionStore.archivedList().forEach(stamp);
    return map;
}

function sessionContentMapsEqual(a, b) {
    if (a === b) return true;
    if (!a || !b) return false;
    const keys = Object.keys(a);
    if (keys.length !== Object.keys(b).length) return false;
    for (let i = 0; i < keys.length; i += 1) {
        if (a[keys[i]] !== b[keys[i]]) return false;
    }
    return true;
}

/** 内容级变化：只就地替换受影响的会话行（保序、保结构）。
 *  stream 映射按"实际渲染出的集合"构建，与整表渲染语义一致；
 *  行数过多（> 24）时退化为整表重建，避免逐行替换的调度开销得不偿失。 */
function patchSessionListRows(ids) {
    if (!sessionsList || !ids || !ids.length) return;
    const sections = selectSessionSections();
    const nextStreamMap = Object.create(null);
    const collect = function (s) {
        if (s && s.id) nextStreamMap[s.id] = !!s.stream_active;
    };
    (sections.pinned || []).forEach(collect);
    if (Array.isArray(sections.normalGroups) && sections.normalGroups.length) {
        sections.normalGroups.forEach(function (g) {
            // 与渲染/布局键一致：stream 映射只覆盖"实际渲染出的行"。
            var rows = (g && g.isWorkDirGroup && typeof sessionGroupSessionsVisible === 'function')
                ? sessionGroupSessionsVisible(g, {
                    noLimit: !!(typeof getSessionListSearchQuery === 'function' && getSessionListSearchQuery())
                }).rows
                : ((g && g.sessions) || []);
            rows.forEach(collect);
        });
    } else {
        (sections.normal || []).forEach(collect);
    }
    (sections.archived || []).forEach(collect);

    const allSessions = selectAllSessions();
    const byId = Object.create(null);
    allSessions.forEach(function (s) { if (s && s.id) byId[s.id] = s; });

    let replaced = 0;
    ids.forEach(function (id) {
        const sess = byId[id];
        if (!sess) return;
        let node = null;
        try {
            node = sessionsList.querySelector('.session-item[data-session-id="' +
                ((window.CSS && CSS.escape) ? CSS.escape(id) : id) + '"]');
        } catch (e) { node = null; }
        if (!node) return;
        node.replaceWith(buildAndBindSessionRow(sess, allSessions, nextStreamMap));
        replaced += 1;
    });
    applyServerStreamActiveMap(nextStreamMap);
    if (replaced) {
        normalizeTruncatedSessionNames(sessionsList);
        if (typeof syncSessionListHead === 'function') {
            syncSessionListHead(sections, { searching: !!getSessionListSearchQuery() });
        }
        syncSessionListIndicatorClasses();
    }
    renderSessionTitleFromStore();
}

function renderSessionListIfChanged(force) {
    const nextLayout = computeSessionListLayoutKey();
    const nextContent = computeSessionListContentMap();
    if (!force && nextLayout === sessionListLayoutKey && sessionContentMapsEqual(nextContent, sessionListContentMap)) {
        syncSessionListIndicatorClasses();
        renderSessionTitleFromStore();
        return;
    }
    const layoutChanged = nextLayout !== sessionListLayoutKey;
    const prevContent = sessionListContentMap;
    sessionListLayoutKey = nextLayout;
    sessionListContentMap = nextContent;

    if (!force && !layoutChanged && prevContent) {
        const changedIds = [];
        for (const id in nextContent) {
            if (prevContent[id] !== nextContent[id]) changedIds.push(id);
        }
        if (changedIds.length && changedIds.length <= 24) {
            patchSessionListRows(changedIds);
            return;
        }
    }

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
    sessionListLayoutKey = '';
    sessionListContentMap = null;
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
    const current = sessionStore.get(sid) || (sessionStore.archivedLoaded
        ? (sessionStore.archivedSessions || []).find(function (session) {
            return session && String(session.id) === sid;
        })
        : null);
    if (!current) return null;
    const prev = Object.assign({}, current);
    const next = Object.assign({}, current, patch || {});
    if (Object.prototype.hasOwnProperty.call(patch || {}, 'pinned')) {
        next.pinned_at = next.pinned ? (next.pinned_at || new Date().toISOString()) : null;
    }
    sessionStore.upsert(next);
    if (prev.archived || next.archived) {
        if (sessionStore.archivedLoaded) {
            const archivedList = (sessionStore.archivedSessions || []).slice();
            const archivedIndex = archivedList.findIndex(function (s) {
                return s && String(s.id) === sid;
            });
            let visibleCount = sessionStore.archivedVisibleCount;
            let totalCount = sessionStore.archivedCount;
            if (prev.archived && next.archived) {
                if (archivedIndex >= 0) archivedList[archivedIndex] = next;
            } else if (prev.archived) {
                if (archivedIndex >= 0) archivedList.splice(archivedIndex, 1);
                if (archivedIndex >= 0 && archivedIndex < visibleCount) visibleCount -= 1;
                totalCount = Math.max(0, totalCount - 1);
            } else if (next.archived) {
                archivedList.unshift(next);
                visibleCount += 1;
                totalCount += 1;
            }
            sessionStore.setArchivedLoaded(archivedList, {
                visibleCount: visibleCount,
                totalCount: totalCount,
            });
            syncArchivedSessionStateFromStore();
        } else if (!!prev.archived !== !!next.archived) {
            sessionStore.setArchivedCount(Math.max(
                0,
                sessionStore.archivedCount + (next.archived ? 1 : -1)
            ));
        }
    }
    renderSessionListIfChanged(true);
    return prev;
}

// Event count cache for optimistic UI updates.
const uiEventCountCache = {
    cache: new Map(),
    maxAgeMs: 10000,

    get(sessionId) {
        var entry = this.cache.get(sessionId);
        if (entry && typeof entry === 'object') return Number(entry.count) || 0;
        return Number(entry) || 0;
    },

    has(sessionId) {
        return this.cache.has(sessionId);
    },

    isFresh(sessionId, maxAgeMs) {
        var entry = this.cache.get(sessionId);
        if (!entry || typeof entry !== 'object') return false;
        var age = Date.now() - Number(entry.updatedAt || 0);
        var limit = Number(maxAgeMs) > 0 ? Number(maxAgeMs) : this.maxAgeMs;
        return age >= 0 && age <= limit;
    },

    set(sessionId, count) {
        this.cache.set(sessionId, {
            count: Math.max(0, Number(count) || 0),
            updatedAt: Date.now(),
        });
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
    const requestSeq = ++sessionStore.snapshotRequestSeq;
    const url = '/sessions/state' + (opts.includeArchived ? '?include_archived=true' : '');
    const response = await fetchWithTimeout(url, {}, 12000);
    if (!response.ok) throw new Error('sessions state failed: ' + response.status);
    const snapshot = await response.json();
    if (!snapshot || !Array.isArray(snapshot.sessions)) {
        throw new Error('invalid sessions state response');
    }
    snapshot.include_archived = !!opts.includeArchived;
    snapshot.client_request_seq = requestSeq;
    return snapshot;
}

function deriveSidebarRuntimeStatus() {
    var busy = false;
    sessionStore.runsBySession.forEach(function () { busy = true; });
    if (!busy) {
        sessionStore.activeRunInfoBySession.forEach(function (info) {
            if (!info || info.run_active !== false) busy = true;
        });
    }
    if (busy) return 'busy';
    return 'online';
}

function updateSidebarRuntimeStatus(nextStatus) {
    var footer = document.querySelector('.sidebar-runtime');
    var status = document.getElementById('sidebar-runtime-status');
    if (!footer || !status) return;
    var state = nextStatus === false ? 'offline'
        : (nextStatus === true || !nextStatus ? deriveSidebarRuntimeStatus() : String(nextStatus));
    if (['online', 'busy', 'waiting', 'alert', 'offline'].indexOf(state) < 0) state = 'online';
    footer.classList.remove('is-online', 'is-busy', 'is-waiting', 'is-alert', 'is-offline');
    footer.classList.add('is-' + state);
    var labels = {
        online: 'Runtime 在线',
        busy: 'Runtime 繁忙',
        waiting: 'Runtime 待处理',
        alert: 'Runtime 告警',
        offline: 'Runtime 离线'
    };
    setUiRuntimeText(status, labels[state]);
    footer.dataset.runtimeStatus = state;
}

var runtimeStatusHeartbeatPending = false;
var runtimeTakeoverBySession = Object.create(null);
var lastUiActivationSeq = 0;
var pendingQuerySession = (function () {
    // Deep link support: /?session=<id> selects that conversation once the
    // session list is ready, then the parameter is stripped so a manual
    // refresh does not yank the user back.
    try {
        var params = new URLSearchParams(window.location.search || '');
        var sid = String(params.get('session') || '').trim();
        if (sid && /^[A-Za-z0-9][A-Za-z0-9\-]{0,63}$/.test(sid)) {
            params.delete('session');
            var nextSearch = params.toString();
            try {
                window.history.replaceState(
                    {}, '',
                    window.location.pathname + (nextSearch ? '?' + nextSearch : '') + (window.location.hash || '')
                );
            } catch (e) { /* history may be unavailable */ }
            return sid;
        }
    } catch (e) { /* ignore */ }
    return '';
})();

function maybeTakeOverActiveRuntimeSession(payload) {
    var sid = String(currentSessionId || '').trim();
    var activeIds = payload && Array.isArray(payload.active_session_ids)
        ? payload.active_session_ids.map(function (value) { return String(value || '').trim(); })
        : [];
    if (!sid || activeIds.indexOf(sid) < 0) return;
    if (typeof navigator !== 'undefined' && navigator.onLine === false) return;
    if (typeof isSessionStreamStopSuppressed === 'function' && isSessionStreamStopSuppressed(sid)) return;
    if (typeof getSessionRunState === 'function' && getSessionRunState(sid)) return;
    if (runtimeTakeoverBySession[sid]) return;

    var task = (async function () {
        try {
            if (sid !== String(currentSessionId || '')) return;
            if (typeof isSessionStreamStopSuppressed === 'function' && isSessionStreamStopSuppressed(sid)) return;
            if (typeof getSessionRunState === 'function' && getSessionRunState(sid)) return;
            // The heartbeat is the authoritative local-process signal. Mark
            // the selected session active before attaching so the observer's
            // guards and UI state agree during history catch-up.
            if (typeof setSessionServerStreamActive === 'function') {
                setSessionServerStreamActive(sid, true);
            }
            if (typeof resetStreamReconnectState === 'function') resetStreamReconnectState(sid);
            document.dispatchEvent(new CustomEvent('myagent:extension-state-changed', {
                detail: { sessionId: sid, phase: 'runtime-takeover' },
            }));
            if (typeof refreshSingleSessionRow === 'function') void refreshSingleSessionRow(sid);
            if (typeof attachSessionEventStream === 'function') {
                await attachSessionEventStream(sid, { skipInitialLoad: true, force: true });
            }
        } catch (error) {
            console.warn('自动接管服务端会话流失败:', error);
        }
    })();
    runtimeTakeoverBySession[sid] = task;
    void task.finally(function () {
        if (runtimeTakeoverBySession[sid] === task) delete runtimeTakeoverBySession[sid];
    });
}

async function refreshRuntimeStatus() {
    if (runtimeStatusHeartbeatPending) return;
    runtimeStatusHeartbeatPending = true;
    try {
        var response = await fetchWithTimeout('/api/runtime-status', { cache: 'no-store' }, 5000);
        if (!response.ok) throw new Error('runtime status failed: ' + response.status);
        var payload = await response.json();
        updateSidebarRuntimeStatus(payload && payload.status ? payload.status : true);
        maybeTakeOverActiveRuntimeSession(payload);
        var activationSeq = Number(payload && payload.activation_seq) || 0;
        if (activationSeq > lastUiActivationSeq) {
            lastUiActivationSeq = activationSeq;
            try { window.focus(); } catch (e) { /* browser policy may reject focus */ }
            var activationSession = String((payload && payload.activation_session) || '').trim();
            if (activationSession && activationSession !== currentSessionId
                    && typeof switchSession === 'function') {
                void Promise.resolve(switchSession(activationSession)).catch(function (err) { /* session may be gone */ });
            }
        }
    } catch (error) {
        updateSidebarRuntimeStatus(false);
    } finally {
        runtimeStatusHeartbeatPending = false;
    }
}

function startRuntimeStatusHeartbeat() {
    // 统一节拍：5 秒任务；窗口隐藏时仍需运行（要支持「服务端拉起窗口 / 自动接管」能力）。
    registerSidebarRefreshTask('runtime-status', 5000, function () {
        void refreshRuntimeStatus();
    }, { runWhenHidden: true });
}

async function fetchWithTimeout(url, options, timeoutMs) {
    options = options || {};
    const ms = Number(timeoutMs) > 0 ? Number(timeoutMs) : 15000;
    const controller = new AbortController();
    const outerSignal = options.signal;
    const abortFromOuter = function () { controller.abort(); };
    if (outerSignal) {
        if (outerSignal.aborted) controller.abort();
        else outerSignal.addEventListener('abort', abortFromOuter, { once: true });
    }
    const timer = setTimeout(function () { controller.abort(); }, ms);
    const nextOptions = Object.assign({}, options, { signal: controller.signal });
    try {
        return await fetch(url, nextOptions);
    } finally {
        clearTimeout(timer);
        if (outerSignal) outerSignal.removeEventListener('abort', abortFromOuter);
    }
}

async function fetchArchivedSessionPage(offset, limit) {
    const url = '/sessions?include_archived=true&archived_only=true&offset=' + String(offset)
        + '&limit=' + String(limit);
    const response = await fetchWithTimeout(url, {}, 15000);
    if (!response.ok) throw new Error('archived sessions failed: ' + response.status);
    const sessions = await response.json();
    const countHeader = response.headers.get('X-Archived-Count');
    const parsedCount = Number(countHeader);
    return {
        sessions: Array.isArray(sessions) ? sessions : [],
        totalCount: Number.isFinite(parsedCount) && parsedCount >= 0
            ? parsedCount
            : Math.max(offset + (Array.isArray(sessions) ? sessions.length : 0), sessionStore.archivedCount),
    };
}

function appendArchivedSessionPage(page, visibleCount) {
    const combined = (sessionStore.archivedSessions || []).concat(page.sessions || []);
    const seen = new Set();
    const deduplicated = combined.filter(function (s) {
        const sid = s && s.id ? String(s.id) : '';
        if (!sid || seen.has(sid)) return false;
        seen.add(sid);
        return true;
    });
    sessionStore.setArchivedLoaded(deduplicated, {
        visibleCount: visibleCount,
        totalCount: page.totalCount,
    });
}

async function prefetchNextArchivedPage(loadEpoch) {
    const cachedCount = Array.isArray(sessionStore.archivedSessions)
        ? sessionStore.archivedSessions.length
        : 0;
    const wantedCount = Math.min(
        sessionStore.archivedCount,
        sessionStore.archivedVisibleCount + ARCHIVED_SESSIONS_PAGE_SIZE
    );
    if (cachedCount >= wantedCount) return;
    const page = await fetchArchivedSessionPage(cachedCount, wantedCount - cachedCount);
    if (loadEpoch !== archivedSessionsLoadEpoch) return;
    appendArchivedSessionPage(page, sessionStore.archivedVisibleCount);
}

async function loadArchivedSessions(opts) {
    opts = opts || {};
    const loadEpoch = ++archivedSessionsLoadEpoch;
    try {
        if (!sessionStore.archivedLoaded) {
            const initialPage = await fetchArchivedSessionPage(0, ARCHIVED_SESSIONS_PAGE_SIZE * 2);
            if (loadEpoch !== archivedSessionsLoadEpoch) return;
            sessionStore.setArchivedLoaded(initialPage.sessions, {
                visibleCount: ARCHIVED_SESSIONS_PAGE_SIZE,
                totalCount: initialPage.totalCount,
            });
        } else if (opts.background || opts.refresh || !sessionStore.hasMoreArchivedSessions()) {
            const refreshLimit = Math.max(
                ARCHIVED_SESSIONS_PAGE_SIZE * 2,
                sessionStore.archivedVisibleCount + ARCHIVED_SESSIONS_PAGE_SIZE
            );
            const refreshedPage = await fetchArchivedSessionPage(0, refreshLimit);
            if (loadEpoch !== archivedSessionsLoadEpoch) return;
            sessionStore.setArchivedLoaded(refreshedPage.sessions, {
                visibleCount: sessionStore.archivedVisibleCount,
                totalCount: refreshedPage.totalCount,
            });
        } else {
            if (sessionStore.revealNextArchivedPage() === 0) {
                const cachedCount = Array.isArray(sessionStore.archivedSessions)
                    ? sessionStore.archivedSessions.length
                    : 0;
                const nextPage = await fetchArchivedSessionPage(cachedCount, ARCHIVED_SESSIONS_PAGE_SIZE);
                if (loadEpoch !== archivedSessionsLoadEpoch) return;
                appendArchivedSessionPage(nextPage, sessionStore.archivedVisibleCount);
                sessionStore.revealNextArchivedPage();
            }
            syncArchivedSessionStateFromStore();
            renderSessionListIfChanged(true);
            clearSessionListError();
            try {
                await prefetchNextArchivedPage(loadEpoch);
            } catch (prefetchErr) {
                console.error('预加载下一批归档目录失败:', prefetchErr);
            }
        }
        if (loadEpoch !== archivedSessionsLoadEpoch) return;
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
            updateSidebarRuntimeStatus(true);
            allSessions = Array.isArray(snapshot.sessions) ? snapshot.sessions : [];
        } catch (stateErr) {
            console.error('加载会话状态快照失败，回退至旧接口', stateErr);
            const fallbackRequestSeq = ++sessionStore.snapshotRequestSeq;
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
            updateSidebarRuntimeStatus(true);
            allSessions = Array.isArray(sessions) ? sessions : [];
            snapshot = {
                sessions: allSessions,
                archived_count: archivedSessionsCount,
                client_request_seq: fallbackRequestSeq,
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

        if (pendingQuerySession) {
            var queryTarget = pendingQuerySession;
            pendingQuerySession = '';
            var known = allSessions.some(function (s) { return s && s.id === queryTarget; });
            if (known && queryTarget !== currentSessionId && typeof switchSession === 'function') {
                void Promise.resolve(switchSession(queryTarget)).catch(function (err) { /* ignore */ });
            }
        }

        renderSessionListIfChanged(!!opts.forceRender);
        clearSessionListError();
        sessionStore.ui.loadingSessions = false;
        if (opts.refreshArchived && !opts.skipArchivedRefresh && sessionStore.archivedLoaded) {
            void loadArchivedSessions({ background: true });
        }
        return true;
    } catch (error) {
        sessionStore.ui.loadingSessions = false;
        updateSidebarRuntimeStatus(false);
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
        updateSidebarRuntimeStatus(false);
        if (!opts.silent) console.error('reconcile run state failed:', e);
        return;
    }
    applySessionSnapshot(snapshot);
    updateSidebarRuntimeStatus(true);
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
            // 本地仍在消费 SSE 且未见真终态时不得误杀：/sessions/state 轻快照有 5s TTL
            // 且在“新一轮刚启动”的首步窗口可能瞬时报 inactive；15s reconcile 若此时
            // abort/endRun 会收起过程框并 seal，导致后续增量无处渲染而“卡死”。
            var streamAlive = !!(run && run.ctx && run.ctx.streamConsuming && run.ctx.terminalSeen !== true);
            if (streamAlive) return;
            var staleSubmittedStream = !!(
                run && run.submitted && run.ctx && run.ctx.streamConsuming
            );
            if (run && (run.reattached || staleSubmittedStream || run.transportClosed)) {
                abortSessionRun(sid, 'reconcile-finished');
                if (run.ctx && typeof endRunForClient === 'function') {
                    // A missing terminal SSE event must not leave the process
                    // panel running after the server has already ended this run.
                    endRunForClient(sid, run.ctx, {
                        runId: run.runId,
                        drainFollowup: false,
                        syncFollowup: false,
                        scroll: false,
                        // 对账路径不是真终态：禁止折叠/封印过程框（渲染中的内容仍需收尾）。
                        collapseProcess: false,
                    });
                }
            }
        }
    });
    if (currentSessionId && active.has(currentSessionId)) {
        const info = sessionStore.getActiveRunInfo(currentSessionId) || {};
        const run = getSessionRunState(currentSessionId);
        const ctx = run && run.ctx;
        const recovery = executionRecoveryBySession.get(String(currentSessionId)) || {};
        const agg = ctx && ctx.currentProcessGroup && ctx.currentProcessGroup.isConnected
            ? ctx.currentProcessGroup
            : findExecutionProcessGroup(getVisibleChatStream(), recovery.processGroupId, info.run_id || info.runId);
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

var sessionHistoryLoadController = null;

async function loadSessionMessages(sessionId, scrollBehavior, opts) {
    const openSessionStartedAt = (typeof performance !== 'undefined' && performance.now)
        ? performance.now()
        : Date.now();
    scrollBehavior = scrollBehavior || 'saved-or-bottom';
    opts = opts || {};
    const loadToken = ++messageLoadEpoch;
    if (typeof sessionHistoryLoadController !== 'undefined' && sessionHistoryLoadController) sessionHistoryLoadController.abort();
    const loadController = new AbortController();
    sessionHistoryLoadController = loadController;
    let historyHydrationStream = null;
    const finishHistoryHydration = function () {
        if (historyHydrationStream) {
            if (loadToken === messageLoadEpoch || historyHydrationStream !== getVisibleChatStream()) {
                historyHydrationStream.hidden = false;
            }
            historyHydrationStream = null;
        }
        if (loadToken !== messageLoadEpoch) return;
        hideLoading();
        if (typeof attachAllHumanInteractionCards === 'function') {
            attachAllHumanInteractionCards(getVisibleChatStream());
        }
    };
    sessionStore.ui.loadingMessages = true;
    suppressTocDuringSessionLoad = true;
    if (typeof cancelSmoothStreamFollowForHistoryLoad === 'function') {
        cancelSmoothStreamFollowForHistoryLoad();
    }
    resetSessionHistoryPaging();
    try {
        let raw;
        let snapshotTocTurns = null;
        let historySource = 'messages';
        let snapshotTiming = null;
        let savedExecutions = [];
        let manualHistory = false;
        const canUseSnapshot = !opts.full && opts.useSnapshot !== false && beforeSessionMessageSnapshotAvailable();
        if (canUseSnapshot) {
            const snapshotUrl = '/sessions/' + encodeURIComponent(sessionId)
                + '/history_snapshot?turns=' + encodeURIComponent(String(HISTORY_DIALOGUES_PER_PAGE))
                + '&event_budget=' + encodeURIComponent(String(HISTORY_EVENT_BUDGET))
                + '&include_aux=false&prefer_active_turn=true';
            for (let migrationAttempt = 0; migrationAttempt < 120; migrationAttempt += 1) {
                const snapshotResp = await fetchWithTimeout(snapshotUrl, { signal: loadController.signal }, 30000);
                const snapshot = await snapshotResp.json().catch(function () { return null; });
                if (snapshot && snapshot.migration_pending) {
                    if (loadToken !== messageLoadEpoch || sessionId !== currentSessionId) return;
                    if (migrationAttempt === 119) throw new Error('历史迁移尚未完成，请稍后重新加载');
                    const retryMs = Math.max(100, Math.min(Number(snapshot.retry_after_ms) || 250, 1000));
                    await new Promise(function (resolve) { setTimeout(resolve, retryMs); });
                    continue;
                }
                // Only an older server/runtime needs the compatibility route.
                // Retrying the same projection on timeout doubles its work.
                if ([404, 405, 409].indexOf(snapshotResp.status) >= 0) break;
                if (!snapshotResp.ok || !snapshot || !snapshot.ok || !snapshot.messages) {
                    throw new Error('history snapshot failed: ' + snapshotResp.status);
                }
                raw = snapshot.messages;
                manualHistory = snapshot.history_mode === 'current_turn';
                savedExecutions = Array.isArray(snapshot.execution_records) ? snapshot.execution_records : [];
                executionRecoveryBySession.set(String(sessionId), {
                    lastRuntimeSeq:Number(snapshot.last_runtime_seq || 0),
                    revision:Number(snapshot.projection_revision || 0),
                    projectionVersion:Number(snapshot.projection_version || 0),
                    processGroupId:String(snapshot.process_group_id || ''),
                });
                executionRecordsBySession.set(String(sessionId), new Map());
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
                if (snapshot.context_tokens && snapshot.context_tokens.estimated != null) {
                    recordContextTokens(
                        sessionId,
                        snapshot.context_tokens.estimated,
                        snapshot.context_tokens.threshold,
                        snapshot.context_tokens.breakdown
                    );
                }
                if (typeof snapshot.stream_active === 'boolean' || typeof snapshot.run_active === 'boolean') {
                    const __snapActive = !!(snapshot.stream_active || snapshot.run_active);
                    sessionStore.applyActiveRunForSession(
                        sessionId,
                        snapshot.active_run || (__snapActive ? {
                            session_id: sessionId,
                            run_active: true,
                            started_at: snapshot.run_started_at || null,
                            runtime_v2: snapshot.source === 'runtime_v2_snapshot',
                        } : null)
                    );
                }
                break;
            }
        }
        if (!raw) {
            manualHistory = !opts.full && !!(getSessionRunState(sessionId) || isServerStreamActive(sessionId));
            let url = '/sessions/' + encodeURIComponent(sessionId) + '/messages';
            if (!opts.full) {
                url += '?turns=' + (manualHistory ? 1 : HISTORY_DIALOGUES_PER_PAGE)
                    + '&event_budget=' + encodeURIComponent(String(HISTORY_EVENT_BUDGET));
            }
            const response = await fetchWithTimeout(url, { signal: loadController.signal }, 30000);
            if (!response.ok) throw new Error('messages failed: ' + response.status);
            raw = await response.json();
        }
        if (loadToken !== messageLoadEpoch || sessionId !== currentSessionId) return;
        if (getSessionRunState(sessionId) && !opts.allowDuringRun) return;
        replayingMessages = true;
        if (typeof uiPerformance !== 'undefined') uiPerformance.sample(sessionId, 'history.fetch', elapsedSince(openSessionStartedAt));
        if (!getVisibleChatStream()) ensureVisibleChatStreamSlot();
        const vis = getVisibleChatStream();
        if (vis) {
            const loader = document.getElementById('chat-loading');
            if (loader && loader.parentNode === vis && chatContainer) {
                chatContainer.insertBefore(loader, vis);
            }
            vis.hidden = true;
            historyHydrationStream = vis;
            emptyChatStreamKeepingStrip(vis);
        }
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
            const pageTotal = Number(raw.total) || 0;
            const pageRangeEnd = Number(raw.range_end) || 0;
            pageMeta = {
                total: pageTotal,
                range_start: Number(raw.range_start) || 0,
                range_end: pageRangeEnd,
                has_older: !!raw.has_older,
                has_newer: raw.has_newer == null ? pageRangeEnd < pageTotal : !!raw.has_newer,
                manual_history: manualHistory,
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
                has_newer: !!pageMeta.has_newer,
                manual_history: !!pageMeta.manual_history,
            });
            ensureHistorySentinel(getVisibleChatStream());
        }
        if (events.length === 0) {
            suppressTocDuringSessionLoad = false;
            setWelcome();
            finishHistoryHydration();
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
        if (typeof seedRenderContextRunGenerations === 'function') {
            seedRenderContextRunGenerations(loadCtx, events, savedExecutions);
        }
        const hydrationStartedAt = performance.now();
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
        savedExecutions.forEach(function (record) {
            updateExecutionRecord(sessionId, record);
            if (!record.ui_committed) renderExecutionRecord(loadCtx, record, sessionId);
        });
        mergeAdjacentExecutionGroups(loadCtx.stream);
        if (typeof uiPerformance !== 'undefined') {
            uiPerformance.sample(sessionId, 'history.hydrate', performance.now() - hydrationStartedAt);
            uiPerformance.count(sessionId, 'history.events', events.length);
        }
        var imageLayoutStartedAt = performance.now();
        var historyScrollBehavior = scrollBehavior;
        if ((scrollBehavior === 'smooth-bottom' || scrollBehavior === 'bottom') && typeof prepareWorkspaceImageLayout === 'function') {
            await prepareWorkspaceImageLayout(getVisibleChatStream());
            if (loadToken !== messageLoadEpoch || sessionId !== currentSessionId) return;
        }
        var historyImagesReady = await waitForHistoryImageLayout(
            sessionId,
            scrollBehavior,
            getVisibleChatStream()
        );
        if (loadToken !== messageLoadEpoch || sessionId !== currentSessionId) return;
        if (scrollBehavior === 'smooth-bottom' && !historyImagesReady) {
            historyScrollBehavior = 'bottom';
        }
        if (typeof uiPerformance !== 'undefined') {
            uiPerformance.sample(sessionId, 'history.images', performance.now() - imageLayoutStartedAt);
            if (!historyImagesReady) uiPerformance.count(sessionId, 'history.imageFallbacks');
        }
        finishHistoryHydration();
        if (!chatStreamHasConversationContent()) {
            suppressTocDuringSessionLoad = false;
            setWelcome();
            updateSessionTitle();
            scheduleContextTokensAfterPaint(sessionId);
            applyChatScrollAfterHistoryLoad(sessionId, scrollBehavior);
            markVisibleSessionStreamLoadState(sessionId, 'ok');
            logOpenSessionTiming(sessionId, {
                source: historySource,
                events: events.length,
                snapshotTiming: snapshotTiming,
                totalMs: elapsedSince(openSessionStartedAt),
            });
            return true;
        }
        if (!manualHistory && !opts.full && opts.preloadOlderIfShort && pageMeta && pageMeta.has_older && events.length <= 2) {
            await loadOlderHistoryChunk({ keepTocStable: true });
            if (loadToken !== messageLoadEpoch || sessionId !== currentSessionId) return;
        }
        if (historyLoadScrollsToBottom(sessionId, historyScrollBehavior)) {
            tocScrollBottomOnNextBuild = true;
        }
        suppressTocDuringSessionLoad = false;
        if (snapshotTocTurns) rebuildToc({ turns: snapshotTocTurns });
        else if (!opts.tocAlreadyStarted) rebuildToc();
        updateSessionTitle();
        updateHistorySentinelVisibility();
        bindExistingLogInteractions();
        var historyScrollStartedAt = performance.now();
        // Completed unread results have no animation phase. Settle the log
        // layout before placing the viewport, including queued overflow work.
        if (historyScrollBehavior === 'bottom') finalizeExistingLogLayout();
        applyChatScrollAfterHistoryLoad(sessionId, historyScrollBehavior);
        var initialSmoothReachedBottom = await waitForChatScrollAfterHistoryLoad(sessionId, historyScrollBehavior);
        if (loadToken !== messageLoadEpoch || sessionId !== currentSessionId) return;
        if (historyScrollBehavior !== 'bottom') finalizeExistingLogLayout();
        if (typeof uiPerformance !== 'undefined') uiPerformance.sample(sessionId, 'history.scroll', performance.now() - historyScrollStartedAt);
        if (historyScrollBehavior === 'smooth-bottom' && initialSmoothReachedBottom) {
            setScrollTopImmediate(chatContainer, chatContainer.scrollHeight);
            requestAnimationFrame(function () {
                requestAnimationFrame(function () {
                    if (loadToken !== messageLoadEpoch || sessionId !== currentSessionId) return;
                    setScrollTopImmediate(chatContainer, chatContainer.scrollHeight);
                });
            });
        }
        scheduleTocActiveUpdate();
        scheduleContextTokensAfterPaint(sessionId);
        markVisibleSessionStreamLoadState(sessionId, 'ok');
        logOpenSessionTiming(sessionId, {
            source: historySource,
            events: events.length,
            snapshotTiming: snapshotTiming,
            totalMs: elapsedSince(openSessionStartedAt),
        });
        return true;
    } catch (error) {
        if (loadController.signal.aborted || loadToken !== messageLoadEpoch || sessionId !== currentSessionId) return false;
        console.error('加载会话消息失败:', error);
        document.getElementById('chat-loading')?.remove();
        appendLogVisible('加载历史消息失败', 'error-log');
        markVisibleSessionStreamLoadState(sessionId, 'failed');
        showSessionLoadRetry(sessionId);
        return false;
    } finally {
        if (sessionHistoryLoadController === loadController) sessionHistoryLoadController = null;
        finishHistoryHydration();
        if (loadToken === messageLoadEpoch) sessionStore.ui.loadingMessages = false;
        if (loadToken === messageLoadEpoch) suppressTocDuringSessionLoad = false;
        if (loadToken === messageLoadEpoch) replayingMessages = false;
    }
}

function chatStreamHasConversationContent() {
    var stream = getVisibleChatStream();
    if (!stream) return false;
    return !!stream.querySelector('.msg-wrap, .process-aggregate, .human-interaction-card, .human-interaction-banner');
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
    if (typeof uiPerformance !== 'undefined') {
        uiPerformance.sample(sessionId, 'history.total', frontendTotal);
        if (timing.total != null && Number.isFinite(Number(timing.total))) {
            uiPerformance.sample(sessionId, 'history.backend', backendTotal);
        }
    }
    if (frontendTotal < 500 && backendTotal < 500) return;
    console.info(
        'open_session_timing session=%s source=%s total=%sms events=%s backend_total=%sms read_page=%sms count=%sms user_turns=%sms context_tokens=%sms',
        sessionId,
        data.source || 'unknown',
        frontendTotal,
        Number(data.events || 0),
        backendTotal,
        Number(timing.read_page || 0),
        Number(timing.count || 0),
        Number(timing.user_turns || 0),
        Number(timing.context_tokens || 0)
    );
}

function beforeSessionMessageSnapshotAvailable() {
    return true;
}

async function switchSession(sessionId, opts) {
    opts = opts || {};
    if (typeof sessionHistoryLoadController !== 'undefined' && sessionHistoryLoadController) sessionHistoryLoadController.abort();
    if (typeof endHistorySmoothScroll === 'function') endHistorySmoothScroll();
    // 子代理寻址：任何不是"由寻址栈驱动"的会话切换都退出寻址态
    // （返回父会话时栈已先弹出，此处同样得到正确结果）。
    if (typeof subagentAddressing !== 'undefined' && subagentAddressing) {
        var addressingTop = subagentAddressing.current();
        if (!addressingTop || String(addressingTop.childSessionId || '') !== String(sessionId || '')) {
            subagentAddressing.reset();
        }
    }
    if (currentSessionId === sessionId && !opts.forceReload) {
        clearSessionUnreadState(sessionId);
        return true;
    }
    const switchStartedAt = performance.now();
    if (opts.forceReload && typeof discardCachedSessionStream === 'function') discardCachedSessionStream(sessionId);
    const switchToken = ++switchSessionEpoch;
    // Cached restores do not start a new message request. Invalidate the old
    // request here as well, including A -> B -> A switches during hydration.
    messageLoadEpoch += 1;
    sessionStore.ui.loadingMessages = false;
    replayingMessages = false;
    cancelSmoothStreamFollowForSessionSwitch();
    // 子代理会话寻址：子会话在主对话区打开时，右侧扩展面板/历史面板保持与
    // 主 Agent 一致（不清空、不收起），只有普通会话切换才重置这些面板。
    var addressingChildSwitch = false;
    if (typeof subagentAddressing !== 'undefined' && subagentAddressing) {
        var __addrTop = subagentAddressing.current();
        addressingChildSwitch = !!__addrTop
            && String(__addrTop.childSessionId || '') === String(sessionId || '');
    }
    suppressTocDuringSessionLoad = true;
    if (!addressingChildSwitch) {
        clearTocForSessionLoad();
        clearOptionalPanelsForSessionLoad();
    }
    pendingRewriteTruncate = null;
    hideRewriteUndoToast();
    // A green-dot session represents an unread completed result. Opening it
    // must land at the newest result, never at a stale reading anchor.
    var sessionHadUnreadResult = !!(
        (sessionStore.get(sessionId) && sessionStore.get(sessionId).unread_result)
        || sessionUnreadComplete.has(sessionId)
    );
    clearSessionUnreadState(sessionId);
    const leaving = currentSessionId;
    recentComposerQueuedFollowup = null;
    saveChatScrollForSession(leaving);
    stashInputDraft(leaving);
    if (typeof stashSkillPickerDraft === 'function') stashSkillPickerDraft(leaving);
    prepareStashLeaving(leaving);
    setCurrentSessionState(sessionId);
    // Hold observer attachment until the addressed session's durable history
    // has been restored (or its complete in-memory stream has been reused).
    sessionStore.ui.loadingMessages = true;
    // The session identity and its side-panel contents must cross the switch
    // boundary together. Waiting for history requests leaves the previous
    // session title or plan visible for a frame (and sometimes much longer on
    // a cold load).
    updateSessionTitle();
    if (typeof updateHumanInteractionBanner === 'function') updateHumanInteractionBanner(sessionId);
    localStorage.setItem('lastSessionId', sessionId);
    if (typeof applyContextTokenLabelForCurrentSession === 'function') applyContextTokenLabelForCurrentSession();
    restoreInputDraft(sessionId);
    if (typeof restoreSkillPickerDraft === 'function') restoreSkillPickerDraft(sessionId);
    if (typeof renderFollowupQueue === 'function') renderFollowupQueue(sessionId);
    if (typeof syncFollowupQueueFromServer === 'function') syncFollowupQueueFromServer(sessionId);
    if (typeof refreshModelProfileSelector === 'function') refreshModelProfileSelector(sessionId);
    syncSessionListIndicatorClasses();
    // Refresh extension panels only after the new row owns the active marker;
    // otherwise the projection request can render the session we just left.
    document.dispatchEvent(new CustomEvent('myagent:extension-state-changed', {
        detail: { sessionId: sessionId },
    }));
    setSendButtonState();
    if (!isSessionRunning(sessionId) && !(typeof isServerStreamActive === 'function' && isServerStreamActive(sessionId))) {
        let __shouldPreflight = true;
        try {
            const __sess = sessionStore.get(sessionId);
            const __last = __sess ? Date.parse(__sess.last_activity_at || __sess.updated_at || __sess.created_at || "") : 0;
            if (Number.isFinite(__last) && Date.now() - __last > 12 * 60 * 1000) __shouldPreflight = false;
        } catch (e) {}
        if (__shouldPreflight) {
            try {
                await Promise.race([
                    (async () => {
                        if (typeof refreshSingleSessionRow === 'function') await refreshSingleSessionRow(sessionId);
                    })(),
                    new Promise(resolve => setTimeout(resolve, 450))
                ]);
            } catch (e) { /* preflight best-effort */ }
        }
    }
    if (switchToken !== switchSessionEpoch || sessionId !== currentSessionId) {
        if (typeof uiPerformance !== 'undefined') uiPerformance.count(sessionId, 'switch.cancelled');
        return false;
    }
    if (typeof uiPerformance !== 'undefined') uiPerformance.sample(sessionId, 'switch.prepare', performance.now() - switchStartedAt);
    var restoredFromCache = false;
    var restoredRunningStream = false;
    var sessionHasActiveServerRun = !!(
        isSessionRunning(sessionId)
        || (typeof isServerStreamActive === 'function' && isServerStreamActive(sessionId))
    );
    if (!opts.forceReload && (
        (restoredRunningStream = restoreStreamForRunningSession(sessionId))
        || (!sessionHadUnreadResult
            && !sessionHasActiveServerRun
            && (restoredFromCache = restoreCachedSessionStream(sessionId)))
    )) {
        suppressTocDuringSessionLoad = false;
        sessionStore.ui.loadingMessages = false;
        hideLoading();
        rebuildToc({ localOnly: true });
        updateSessionTitle();
        scheduleContextTokensAfterPaint(sessionId);
        // Only a complete, idle stream restored from the in-memory cache may
        // return to its prior reading position. A live run and a green-dot
        // completion always open on their newest content.
        var sessionIsRunningNow = !!(
            restoredRunningStream
            || isSessionRunning(sessionId)
            || (typeof isServerStreamActive === 'function' && isServerStreamActive(sessionId))
        );
        if (restoredFromCache && !sessionHadUnreadResult && !sessionIsRunningNow) {
            restoreCachedSessionScrollPosition(sessionId);
        } else {
            streamChatNearBottom = true;
            streamProcNearBottom = true;
            liveAutoFollow = true;
            scrollToBottom();
            if (sessionIsRunningNow && typeof scrollCurrentRunningProcessToBottom === 'function') {
                scrollCurrentRunningProcessToBottom(sessionId);
            }
        }
        if (typeof refreshHumanInteractions === 'function') void refreshHumanInteractions(sessionId);
        if (switchToken !== switchSessionEpoch || sessionId !== currentSessionId) return;
        void refreshSingleSessionRow(sessionId);
        document.dispatchEvent(new CustomEvent('myagent:extension-state-changed', {
            detail: { sessionId: sessionId, phase: 'loaded' },
        }));
        setSendButtonState();
        maybeStartStreamPollForSession(sessionId, { skipInitialLoad: true });
        if (typeof uiPerformance !== 'undefined') uiPerformance.sample(sessionId,
            restoredRunningStream ? 'switch.live' : 'switch.cached', performance.now() - switchStartedAt);
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
    const tocAlreadyStarted = opts.useSnapshot === false && typeof startTocForSessionLoad === 'function';
    if (tocAlreadyStarted) startTocForSessionLoad(sessionId);
    return new Promise(function (resolve) {
        setTimeout(async function () {
        if (switchToken !== switchSessionEpoch || sessionId !== currentSessionId) { resolve(false); return; }
        try {
            // Capture unread intent before clearing the badge and preserve it
            // through the async load: completed results open without a glide.
            var loadedOk = await loadSessionMessages(sessionId, sessionHadUnreadResult ? 'bottom' : 'smooth-bottom', {
                preloadOlderIfShort: isServerStreamActive(sessionId),
                allowDuringRun: addressingChildSwitch || isServerStreamActive(sessionId),
                tocAlreadyStarted: tocAlreadyStarted,
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
        void refreshSingleSessionRow(sessionId);
        document.dispatchEvent(new CustomEvent('myagent:extension-state-changed', {
            detail: { sessionId: sessionId, phase: 'loaded' },
        }));
        setSendButtonState();
        maybeStartStreamPollForSession(sessionId, { skipInitialLoad: true });
        if (typeof refreshHumanInteractions === 'function') void refreshHumanInteractions(sessionId);
        if (typeof uiPerformance !== 'undefined') uiPerformance.sample(sessionId, 'switch.loaded', performance.now() - switchStartedAt);
        resolve(true);
        }, 20);
    });
}

async function createNewSession(targetWorkDir) {
    if (typeof targetWorkDir === 'string') {
        const requestedWorkDir = targetWorkDir.trim();
        if (requestedWorkDir !== newSessionWorkDir) {
            newSessionWorkDir = requestedWorkDir;
            newSessionWorkDirRevision += 1;
            clearPendingNewSession();
        }
        if (typeof syncWelcomeSessionDirectory === 'function') {
            syncWelcomeSessionDirectory(null, requestedWorkDir);
        }
    }
    const leavingSessionId = currentSessionId;
    if (!leavingSessionId) {
        setCurrentSessionState(null);
        // 已在草稿态：复用（或继续）后台预取，不重复创建会话。
        void ensurePrefetchedNewSession();
        localStorage.setItem('lastSessionId', NEW_SESSION_DRAFT_KEY);
        if (!getVisibleChatStream()) ensureVisibleChatStreamSlot();
        const draftStream = getVisibleChatStream();
        if (!draftStream || !draftStream.querySelector('.welcome')) setWelcome();
        restoreInputDraft(null);
        if (typeof restoreSkillPickerDraft === 'function') restoreSkillPickerDraft(null);
        updateSessionTitle();
        syncSessionListIndicatorClasses();
        setSendButtonState();
        if (messageInput) messageInput.focus();
        return null;
    }

    cancelSmoothStreamFollowForSessionSwitch();
    saveChatScrollForSession(leavingSessionId);
    stashInputDraft(leavingSessionId);
    if (typeof stashSkillPickerDraft === 'function') stashSkillPickerDraft(leavingSessionId);
    prepareStashLeaving(leavingSessionId);
    clearOptionalPanelsForSessionLoad();
    clearTocForSessionLoad();
    switchSessionEpoch += 1;
    messageLoadEpoch += 1;
    setCurrentSessionState(null);
    // 点“新会话”即开始后台物化：会话目录、元数据与索引在用户写首条消息之前落好，
    // 发送时直接复用，不再把真实会话文件的创建算进首条消息的等待时间。
    void ensurePrefetchedNewSession();
    localStorage.setItem('lastSessionId', NEW_SESSION_DRAFT_KEY);
    if (!getVisibleChatStream()) ensureVisibleChatStreamSlot();
    setWelcome();
    restoreInputDraft(null);
    if (typeof restoreSkillPickerDraft === 'function') restoreSkillPickerDraft(null);
    if (typeof renderFollowupQueue === 'function') renderFollowupQueue(null);
    if (typeof refreshModelProfileSelector === 'function') refreshModelProfileSelector(null);
    updateSessionTitle();
    syncSessionListIndicatorClasses();
    replayingMessages = false;
    hideLoading();
    setSendButtonState();
    document.dispatchEvent(new CustomEvent('myagent:extension-state-changed', {
        detail: { sessionId: null, phase: 'draft' },
    }));
    if (messageInput) messageInput.focus();
    return null;
}

/* ── 新建会话：可选工作目录 ────────────────────────────────────────────────
   菜单两项：在当前工作目录新建 / 在新工作目录新建（复用 MyAgentPathPicker 的原生目录
   选择器）。选定的目录只作用于「下一个新会话」：草稿态会立刻按新目录重开隐藏草稿
   （服务端 work_dir 建会话时指定、之后不可改），已有会话则等下次点新建时生效。 */

/** 目录选择器不可用（无原生对话框 / 无该 API）时的手填兜底；返回绝对路径或 null。 */
function promptNewSessionWorkDirFallback(initial) {
    if (typeof openUiModal !== 'function') return Promise.resolve(null);
    return openUiModal({
        title: '选择工作目录',
        message: '无法打开系统目录选择器，请直接填写新会话的工作目录绝对路径。',
        inputLabel: '工作目录绝对路径',
        inputValue: String(initial || ''),
        inputPlaceholder: 'D:\\work\\my-project',
        confirmText: '在此目录新建',
        cancelText: '取消',
    }).then(function (value) {
        return typeof value === 'string' ? value : null;
    });
}

async function pickNewSessionWorkDir() {
    const initial = activeSessionWorkDir()
        || newSessionWorkDirTarget()
        || ((typeof getActiveWorkDir === 'function') ? getActiveWorkDir() : '');
    const picker = (typeof window !== 'undefined' && window.MyAgentPathPicker)
        ? window.MyAgentPathPicker
        : null;
    if (picker && typeof picker.pickPath === 'function') {
        try {
            const picked = await picker.pickPath('directory', initial, false);
            if (picked) return String(picked);
            return null; // 用户取消
        } catch (error) {
            console.warn('目录选择器不可用，改为手填路径:', error);
        }
    }
    return promptNewSessionWorkDirFallback(initial);
}

(function bindWelcomeSessionDirectoryPickerOnce() {
    if (typeof window === 'undefined' || window.__myAgentWelcomeSessionDirectoryBound) return;
    window.__myAgentWelcomeSessionDirectoryBound = true;
    document.addEventListener('click', async function (event) {
        const target = event.target && event.target.closest
            ? event.target.closest('[data-welcome-session-directory-picker]')
            : null;
        if (!target || target.disabled || currentSessionId) return;
        event.preventDefault();
        event.stopPropagation();
        target.disabled = true;
        let selectedWorkDir = '';
        try {
            const picked = await pickNewSessionWorkDir();
            const workDir = String(picked || '').trim();
            if (!workDir || currentSessionId) return;
            selectedWorkDir = workDir;
            // Update the existing draft in place. Keep any text already typed in
            // the composer; only its hidden server draft is recreated for this path.
            await applyNewSessionWorkDir(workDir);
        } catch (error) {
            console.error('选择会话目录失败:', error);
        } finally {
            target.disabled = false;
            if (typeof syncWelcomeSessionDirectory === 'function') {
                syncWelcomeSessionDirectory(null, selectedWorkDir || undefined);
            }
        }
    });
})();

/** 记下目标目录；草稿态下立刻按新目录重开隐藏草稿（旧草稿的 work_dir 不可改）。 */
function applyNewSessionWorkDir(workDir) {
    const next = String(workDir || '').trim();
    if (next === newSessionWorkDir) return Promise.resolve(null);
    newSessionWorkDir = next;
    newSessionWorkDirRevision += 1;
    const targetRevision = newSessionWorkDirRevision;
    if (typeof syncWelcomeSessionDirectory === 'function') syncWelcomeSessionDirectory(null, next);
    clearPendingNewSession();
    const inFlight = prefetchNewSessionPromise
        ? Promise.resolve(prefetchNewSessionPromise).catch(function () { return null; })
        : Promise.resolve(null);
    return inFlight.then(function () {
        // The old request may have finished after clearPendingNewSession() and
        // published a draft for its previous directory. ensurePrefetchedNewSession()
        // checks the captured target before reusing or creating a draft.
        if (currentSessionId) return null;
        return ensurePrefetchedNewSession();
    }).then(function (pending) {
        if (targetRevision === newSessionWorkDirRevision
                && next === newSessionWorkDirTarget()
                && typeof syncWelcomeSessionDirectory === 'function') {
            syncWelcomeSessionDirectory(null, next);
        }
        return pending;
    });
}

/** 「在新工作目录新建会话」：选目录 → 记下 → 进入新会话草稿态。 */
async function startNewSessionInFolder() {
    const picked = await pickNewSessionWorkDir();
    const dir = String(picked || '').trim();
    if (!dir) return null;
    return startNewSessionInDir(dir);
}

/** 在指定工作目录（空=服务端默认目录）里新建会话；各入口共用这一条链路。 */
async function startNewSessionInDir(dir) {
    const next = String(dir || '').trim();
    await applyNewSessionWorkDir(next);
    return createNewSession(next);
}

/** 当前会话（= 当前分组）的工作目录；没有会话（草稿态）时返回空串。 */
function activeSessionWorkDir() {
    const active = currentSessionId ? sessionStore.get(currentSessionId) : null;
    return (active && typeof active.work_dir === 'string') ? active.work_dir.trim() : '';
}

/** 主按钮与菜单「当前工作目录」：在当前会话的目录里新建（DSH 的当前工作区语义）。 */
async function startNewSessionInCurrentDir() {
    // 已在草稿态：只回到草稿，不改变已选定的目标目录（否则会把刚建好的草稿丢掉）。
    if (!currentSessionId) return createNewSession();
    return startNewSessionInDir(activeSessionWorkDir());
}

// 刷新后重新进入草稿态时，草稿自身的工作目录来自服务端；把待用目录恢复成它，
// 避免下一次 ensurePrefetchedNewSession 把仍然有效的草稿当成「目录不符」丢弃。
(function restorePendingNewSessionWorkDirOnce() {
    const stored = readStoredPendingNewSession();
    if (stored && typeof stored.work_dir === 'string' && stored.work_dir) {
        newSessionWorkDir = stored.work_dir;
    }
})();

/** 「新会话」右侧 ▾：当前目录 / 新目录两条入口（开关与键盘行为走通用弹出层）。 */
(function bindNewSessionMenuOnce() {
    const menu = document.getElementById('new-session-menu');
    const popup = document.getElementById('new-session-options');
    if (!menu || !popup || window.__myAgentNewSessionMenuBound) return;
    window.__myAgentNewSessionMenuBound = true;
    bindSidebarPopup(popup);
    menu.querySelectorAll('[data-new-session-scope]').forEach(function (item) {
        item.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            setSidebarPopupOpen(popup, false);
            const scope = String(item.getAttribute('data-new-session-scope') || '');
            const task = scope === 'new' ? startNewSessionInFolder() : startNewSessionInCurrentDir();
            Promise.resolve(task).catch(function (error) {
                console.error('新建会话失败:', error);
            });
        });
    });
})();

/* ── 工作目录分组头的 hover 动作：在该目录新建会话 / 目录更多操作 ────────── */

/** 复制工作目录绝对路径到剪贴板（失败时回退到临时 textarea）。 */
function copyWorkDirPath(path) {
    var text = String(path || '');
    if (!text) return;
    var done = function () {
        if (typeof showCopyFeedback === 'function') showCopyFeedback();
    };
    var fallback = function () {
        try {
            var ta = document.createElement('textarea');
            ta.value = text;
            ta.setAttribute('readonly', '1');
            ta.style.position = 'fixed';
            ta.style.left = '-9999px';
            document.body.appendChild(ta);
            ta.select();
            document.execCommand('copy');
            ta.remove();
            done();
        } catch (e) {
            console.error('复制工作目录路径失败:', e);
        }
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(done).catch(fallback);
    } else {
        fallback();
    }
}

/** 在系统文件管理器中打开工作目录（复用后端已有的 open-workspace-dir）。 */
function revealWorkDirInExplorer(path) {
    var rel = String(path || '');
    if (!rel) return;
    fetch('/api/open-workspace-dir?' + new URLSearchParams({ rel: rel }))
        .then(function (response) { return response.json().catch(function () { return { ok: false }; }); })
        .then(function (data) {
            if (typeof showOpenFileFeedback !== 'function') return;
            if (data && data.ok) showOpenFileFeedback('已请求打开');
            else showOpenFileFeedback((data && data.error) ? ('无法打开：' + data.error) : '无法打开文件');
        })
        .catch(function () {
            if (typeof showOpenFileFeedback === 'function') showOpenFileFeedback('无法连接服务');
        });
}

/** 工作目录重命名：只改侧栏显示名（localStorage 记忆，空名恢复为目录名），不动磁盘。 */
async function renameWorkDirGroup(group, workDirPath) {
    var current = String((group && group.title) || '');
    var requested = await openUiModal({
        title: '重命名工作目录',
        subtitle: '只改侧栏显示的名称（留空恢复为目录名），不影响磁盘目录',
        message: String(workDirPath || '') ? ('目录：' + String(workDirPath)) : '',
        inputLabel: '显示名称',
        inputValue: current,
        inputMaxLength: 60,
        inputRequired: false,
        confirmText: '保存名称',
        cancelText: '取消',
    });
    if (typeof requested !== 'string') return;
    var next = requested.trim().slice(0, 60);
    if (typeof setWorkDirCustomLabel === 'function') setWorkDirCustomLabel(group.key, next);
    renderSessionListIfChanged(true);
}

/** 工作目录分组的拖拽排序（Pointer 事件；移动超过阈值才算拖拽，原地点击仍是折叠/展开）。
 *  顺序写入 localStorage（getWorkDirOrder/setWorkDirOrder），下次渲染按新顺序排布。 */
function bindSessionGroupDrag(wrap, headRow, group) {
    if (!wrap || !headRow || !group || !group.isWorkDirGroup) return;
    if (headRow.dataset.groupDragBound === '1') return;
    headRow.dataset.groupDragBound = '1';
    var drag = null;
    var suppressClickUntil = 0;
    var DRAG_THRESHOLD_PX = 5;

    // 拖拽结束后抑制紧随其后的 click（否则会顺带触发折叠开关）。
    headRow.addEventListener('click', function (e) {
        if (Date.now() < suppressClickUntil) {
            e.preventDefault();
            e.stopPropagation();
        }
    }, true);

    headRow.addEventListener('pointerdown', function (e) {
        if (e.button !== 0) return;
        var t = e.target;
        if (t && t.closest && t.closest('.session-group-actions')) return;   // 动作区自己处理
        drag = { pointerId: e.pointerId, startY: e.clientY, started: false, target: null, half: null };
    });

    function clearDropIndicators() {
        document.querySelectorAll('.session-group.is-drop-before, .session-group.is-drop-after')
            .forEach(function (el) { el.classList.remove('is-drop-before', 'is-drop-after'); });
    }

    function updateDropIndicator(clientY) {
        clearDropIndicators();
        drag.target = null;
        drag.half = null;
        var groups = document.querySelectorAll('.session-group');
        for (var i = 0; i < groups.length; i += 1) {
            var el = groups[i];
            if (el === wrap) continue;
            var r = el.getBoundingClientRect();
            if (clientY < r.top || clientY > r.bottom) continue;
            var half = clientY < (r.top + r.bottom) / 2 ? 'before' : 'after';
            drag.target = el;
            drag.half = half;
            el.classList.add(half === 'before' ? 'is-drop-before' : 'is-drop-after');
            return;
        }
    }

    headRow.addEventListener('pointermove', function (e) {
        if (!drag || e.pointerId !== drag.pointerId) return;
        if (!drag.started) {
            if (Math.abs(e.clientY - drag.startY) < DRAG_THRESHOLD_PX) return;
            drag.started = true;
            wrap.classList.add('is-dragging');
            document.body.classList.add('session-group-drag-active');
            try { headRow.setPointerCapture(drag.pointerId); } catch (err) { /* ignore */ }
        }
        e.preventDefault();
        updateDropIndicator(e.clientY);
    });

    function finishDrag(e) {
        if (!drag || e.pointerId !== drag.pointerId) return;
        var started = drag.started;
        var target = drag.target;
        var half = drag.half;
        drag = null;
        wrap.classList.remove('is-dragging');
        document.body.classList.remove('session-group-drag-active');
        clearDropIndicators();
        if (!started) return;
        suppressClickUntil = Date.now() + 400;
        if (!target) return;
        // 以 DOM 顺序为基准重排（搜索态下只含可见组；未渲染的组按原相对顺序保留在后面）。
        var domKeys = [];
        document.querySelectorAll('.session-group').forEach(function (el) {
            var key = el.dataset.groupKey;
            if (key && key.indexOf('workdir:') === 0) {
                domKeys.push(key);
            }
        });
        var fromKey = wrap.dataset.groupKey;
        var targetKey = target.dataset.groupKey;
        var prevOrder = (typeof getWorkDirOrder === 'function') ? getWorkDirOrder() : [];
        prevOrder.forEach(function (key) {
            if (domKeys.indexOf(key) < 0) domKeys.push(key);
        });
        var fromIdx = domKeys.indexOf(fromKey);
        if (fromIdx < 0) return;
        domKeys.splice(fromIdx, 1);
        var at = domKeys.indexOf(targetKey);
        if (at < 0) return;
        domKeys.splice(half === 'before' ? at : at + 1, 0, fromKey);
        if (typeof setWorkDirOrder === 'function') setWorkDirOrder(domKeys);
        renderSessionListIfChanged(false);
    }
    headRow.addEventListener('pointerup', finishDrag);
    headRow.addEventListener('pointercancel', function (e) {
        if (!drag || e.pointerId !== drag.pointerId) return;
        drag = null;
        wrap.classList.remove('is-dragging');
        document.body.classList.remove('session-group-drag-active');
        clearDropIndicators();
    });
}

/** 工作目录分组头右侧：+（在该目录新建）/ ⋯（重命名、复制路径、在资源管理器打开）。 */
function buildSessionGroupActions(group, workDirPath) {
    const actions = document.createElement('div');
    actions.className = 'session-group-actions';
    // 标题可能是自定义名（默认组也可改名），动作文案统一用当前显示名。
    const name = String((group && group.title) || '');
    const newLabel = '在“' + name + '”中新建会话';
    const moreLabel = '“' + name + '”的更多操作';

    const newBtn = document.createElement('button');
    newBtn.type = 'button';
    newBtn.className = 'session-row-icon session-group-icon';
    newBtn.setAttribute('aria-label', newLabel);
    newBtn.setAttribute('data-ui-tip', newLabel);
    newBtn.innerHTML = SIDEBAR_ICON_SVG.plus;
    bindUiHoverTip(newBtn);
    newBtn.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        Promise.resolve(startNewSessionInDir(workDirPath)).catch(function (err) {
            console.error('在该工作目录中新建会话失败:', err);
        });
    });

    const popup = document.createElement('div');
    popup.className = 'sidebar-popup session-group-popup';
    popup.setAttribute('data-sidebar-popup', '1');
    popup.innerHTML = '<button type="button" class="session-row-icon session-group-icon" data-popup-trigger'
        + ' aria-haspopup="menu" aria-expanded="false"'
        + ' aria-label="' + escapeHtml(moreLabel) + '" data-ui-tip="' + escapeHtml(moreLabel) + '">'
        + SIDEBAR_ICON_SVG.dots + '</button>'
        + '<div class="sidebar-popup-menu session-group-menu" role="menu" aria-label="'
        + escapeHtml(moreLabel) + '">'
        + '<button type="button" role="menuitem" data-group-action="rename">重命名</button>'
        + '<button type="button" role="menuitem" data-group-action="copy">复制路径</button>'
        + '<button type="button" role="menuitem" data-group-action="reveal">在资源管理器打开</button>'
        + '</div>';
    bindSidebarPopup(popup);
    popup.addEventListener('click', function (e) {
        const item = (e.target && e.target.closest) ? e.target.closest('[data-group-action]') : null;
        if (!item) return;
        e.preventDefault();
        e.stopPropagation();
        setSidebarPopupOpen(popup, false);
        const action = item.getAttribute('data-group-action');
        if (action === 'copy') copyWorkDirPath(workDirPath);
        else if (action === 'reveal') revealWorkDirInExplorer(workDirPath);
        else if (action === 'rename') renameWorkDirGroup(group, workDirPath);
    });

    actions.appendChild(newBtn);
    actions.appendChild(popup);
    return actions;
}

/* ── 侧栏静态头：会话 / 工作区 + 搜索 + 视图选项 + 在新文件夹中新建 ──────── */

function buildSessionViewMenuMarkup() {
    function row(attr, value, text) {
        return '<button type="button" role="menuitemradio" aria-checked="false" '
            + attr + '="' + value + '">'
            + '<span class="session-view-menu-text">' + text + '</span>'
            + '<span class="session-view-menu-check" aria-hidden="true">' + SIDEBAR_ICON_SVG.check + '</span>'
            + '</button>';
    }
    return '<div class="sidebar-popup-label" role="presentation">分组方式</div>'
        + row('data-session-group-by', 'time', '按时间')
        + row('data-session-group-by', 'workdir', '按工作目录')
        + '<div class="sidebar-popup-separator" role="separator"></div>'
        + '<div class="sidebar-popup-label" role="presentation">列表模式</div>'
        + row('data-session-list-mode-option', 'compact', '紧凑')
        + row('data-session-list-mode-option', 'detailed', '详细')
        + '<div class="sidebar-popup-separator" role="separator"></div>'
        + '<div class="sidebar-popup-label" role="presentation">筛选会话</div>'
        + row('data-session-archive-filter', 'hide', '隐藏已归档')
        + row('data-session-archive-filter', 'show', '全部')
        + row('data-session-archive-filter', 'only', '仅已归档');
}

/** 让视图选项菜单的对勾与当前状态（分组方式 / 列表模式 / 归档筛选）一致。 */
function syncSessionViewMenu() {
    const menu = document.getElementById('session-view-menu');
    if (!menu) return;
    const groupBy = (typeof getSessionGroupBy === 'function') ? getSessionGroupBy() : 'time';
    const listMode = (typeof getStoredSessionListMode === 'function') ? getStoredSessionListMode() : 'detailed';
    const archiveFilter = (typeof getSessionArchiveFilter === 'function') ? getSessionArchiveFilter() : 'show';
    const mark = function (selector, attr, value) {
        menu.querySelectorAll(selector).forEach(function (btn) {
            const on = String(btn.getAttribute(attr)) === String(value);
            btn.classList.toggle('is-active', on);
            if (btn.getAttribute('role') === 'menuitemradio') {
                btn.setAttribute('aria-checked', on ? 'true' : 'false');
            }
        });
    };
    mark('[data-session-group-by]', 'data-session-group-by', groupBy);
    mark('[data-session-list-mode-option]', 'data-session-list-mode-option', listMode);
    mark('[data-session-archive-filter]', 'data-session-archive-filter', archiveFilter);
}

/** 切换归档筛选（show=显示归档区段，历史行为；hide=不渲染；only=只看归档）。 */
function applySessionArchiveFilter(filter) {
    const next = (typeof setSessionArchiveFilter === 'function') ? setSessionArchiveFilter(filter) : filter;
    syncSessionViewMenu();
    if (next === 'only' && !sessionStore.archivedLoaded) {
        void loadArchivedSessions({ background: true, forceRender: true });
    }
    if (typeof renderSessionListIfChanged === 'function') renderSessionListIfChanged(true);
}

function setSessionSearchExpanded(expanded, opts) {
    const head = document.getElementById('session-list-head');
    const box = document.getElementById('session-search-box');
    const btn = document.getElementById('session-search-btn');
    const input = document.getElementById('session-search-input');
    if (!head || !box || !btn) return;
    const next = !!expanded;
    head.classList.toggle('is-searching', next);
    box.hidden = !next;
    btn.setAttribute('aria-expanded', next ? 'true' : 'false');
    if (next && typeof hideUiHoverTipsNow === 'function') hideUiHoverTipsNow();
    if (next) {
        if (input) {
            input.focus();
            if (opts && opts.selectInput) input.select();
        }
    } else if (input) {
        input.value = '';
    }
}

function applySessionListSearch(value) {
    setSessionListSearchQuery(value);
    if (typeof renderSessionListIfChanged === 'function') renderSessionListIfChanged(true);
}

/** 收起/展开「会话（工作区）」区段；标题在侧栏静态头里，被折叠的区段体仍在列表内。 */
function toggleSessionListHeadCollapse() {
    const next = !sessionSectionExpanded('normal');
    persistSessionSectionExpanded('normal', next);
    const sec = sessionsList ? sessionsList.querySelector('.session-section[data-section="normal"]') : null;
    if (sec) sec.classList.toggle('is-collapsed', !next);
    syncSessionListHead(null, {});
}

/** 每次列表重绘后同步静态头：标题（会话 / 工作区）、计数、折叠态、视图选项对勾。 */
function syncSessionListHead(sections, opts) {
    const head = document.getElementById('session-list-head');
    if (!head) return;
    const options = opts || {};
    const labelEl = document.getElementById('session-head-label');
    if (labelEl) {
        const workDirGrouping = (typeof getSessionGroupBy === 'function') && getSessionGroupBy() === 'workdir';
        labelEl.textContent = workDirGrouping ? '工作区' : '会话';
    }
    const countEl = document.getElementById('session-head-count');
    if (countEl && sections) countEl.textContent = String((sections.normal || []).length);
    if (options.searching !== undefined) {
        const head2 = document.getElementById('session-list-head');
        if (head2) head2.classList.toggle('is-filtering', !!options.searching);
    }
    const expanded = sessionSectionExpanded('normal');
    const toggle = document.getElementById('session-head-toggle');
    if (toggle) {
        toggle.setAttribute('aria-expanded', expanded ? 'true' : 'false');
        toggle.classList.toggle('is-collapsed', !expanded);
    }
    const sec = sessionsList ? sessionsList.querySelector('.session-section[data-section="normal"]') : null;
    if (sec) sec.classList.toggle('is-collapsed', !expanded);
    syncSessionViewMenu();
}

(function mountSessionListHeadOnce() {
    const head = document.getElementById('session-list-head');
    if (!head || head.dataset.headMounted === '1') return;
    head.dataset.headMounted = '1';

    const viewMenu = document.getElementById('session-view-menu');
    if (viewMenu) viewMenu.innerHTML = buildSessionViewMenuMarkup();
    const viewPopup = document.getElementById('session-view-options');
    if (viewPopup) {
        bindSidebarPopup(viewPopup);
        viewPopup.addEventListener('click', function (e) {
            const item = (e.target && e.target.closest) ? e.target.closest('[role="menuitemradio"]') : null;
            if (!item) return;
            e.preventDefault();
            e.stopPropagation();
            setSidebarPopupOpen(viewPopup, false);
            const groupBy = item.getAttribute('data-session-group-by');
            const listMode = item.getAttribute('data-session-list-mode-option');
            const archive = item.getAttribute('data-session-archive-filter');
            if (groupBy && typeof applySessionGroupBy === 'function') applySessionGroupBy(groupBy, true);
            else if (listMode && typeof applySessionListMode === 'function') applySessionListMode(listMode, true);
            else if (archive) applySessionArchiveFilter(archive);
            syncSessionViewMenu();
        });
    }

    const toggle = document.getElementById('session-head-toggle');
    if (toggle) {
        toggle.addEventListener('click', function (e) {
            e.preventDefault();
            toggleSessionListHeadCollapse();
        });
    }

    const searchBtn = document.getElementById('session-search-btn');
    const searchBox = document.getElementById('session-search-box');
    const searchInput = document.getElementById('session-search-input');
    const searchClear = document.getElementById('session-search-clear');
    const collapseSearch = function (returnFocus) {
        applySessionListSearch('');
        setSessionSearchExpanded(false);
        if (returnFocus && searchBtn) {
            try { searchBtn.focus(); } catch (err) { /* ignore */ }
        }
    };
    if (searchBtn) {
        searchBtn.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            const next = !head.classList.contains('is-searching');
            setSessionSearchExpanded(next, { selectInput: true });
        });
    }
    if (searchInput) {
        searchInput.addEventListener('input', function () {
            applySessionListSearch(searchInput.value);
        });
        searchInput.addEventListener('keydown', function (e) {
            if (e.key !== 'Escape') return;
            e.preventDefault();
            e.stopPropagation();
            collapseSearch(true);
        });
    }
    if (searchClear) {
        searchClear.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            collapseSearch(true);
        });
        bindUiHoverTip(searchClear);
    }
    // DSH 对齐：点击外部时若有查询词只失焦（保留过滤），没有查询词才收起。
    document.addEventListener('pointerdown', function (e) {
        if (!head.classList.contains('is-searching')) return;
        if (head.contains(e.target)) return;
        if (getSessionListSearchQuery()) {
            if (searchInput && document.activeElement === searchInput) searchInput.blur();
            return;
        }
        setSessionSearchExpanded(false);
    }, true);

    const addFolder = document.getElementById('session-add-folder-btn');
    if (addFolder) {
        if (window.MyAgentIcons) window.MyAgentIcons.mount(addFolder);
        bindUiHoverTip(addFolder);
        addFolder.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            Promise.resolve(startNewSessionInFolder()).catch(function (err) {
                console.error('在新文件夹中新建会话失败:', err);
            });
        });
    }
    if (searchBox && searchInput) searchBox.hidden = true;
    syncSessionViewMenu();
    syncSessionListHead(null, {});
})();

async function materializeNewSession() {
    if (currentSessionId) return currentSessionId;
    if (materializeNewSessionQueue) return materializeNewSessionQueue;
    materializeNewSessionQueue = Promise.resolve()
        .then(function () { return materializeNewSessionInner(); })
        .finally(function () {
            materializeNewSessionQueue = null;
        });
    return materializeNewSessionQueue;
}

function collectNewSessionCreateOptions(targetWorkDir) {
    const createOptions = {};
    if (typeof newSessionModelProfileId === 'function') {
        const modelProfileId = newSessionModelProfileId();
        if (modelProfileId) createOptions.model_profile_id = modelProfileId;
    }
    if (typeof newSessionReasoningEffort === 'function') {
        const effort = newSessionReasoningEffort();
        if (effort) createOptions.reasoning_effort = effort;
    }
    if (typeof selectedNewSessionPermissionMode === 'function') {
        const permissionMode = selectedNewSessionPermissionMode();
        if (permissionMode) createOptions.permission_mode = permissionMode;
    }
    // 会话创建时指定工作目录，之后不可改（服务端契约：POST /sessions 的可选 work_dir）。
    const workDir = (typeof targetWorkDir === 'string')
        ? targetWorkDir.trim()
        : newSessionWorkDirTarget();
    if (workDir) createOptions.work_dir = workDir;
    return createOptions;
}

/** 当前待用的新会话工作目录；空串表示用服务端全局默认目录。 */
function newSessionWorkDirTarget() {
    return String(newSessionWorkDir || '').trim();
}

function readStoredPendingNewSession() {
    try {
        // Keep one pending server draft per tab. sessionStorage survives reloads
        // without letting two tabs send independent first turns to the same ID.
        let raw = sessionStorage.getItem(PENDING_NEW_SESSION_KEY);
        if (!raw) {
            // One-time handoff for drafts created by the earlier build, which
            // stored this pointer in localStorage shared by all tabs.
            raw = localStorage.getItem(PENDING_NEW_SESSION_KEY);
            if (raw) {
                sessionStorage.setItem(PENDING_NEW_SESSION_KEY, raw);
                localStorage.removeItem(PENDING_NEW_SESSION_KEY);
            }
        }
        if (!raw) return null;
        const parsed = JSON.parse(raw);
        if (parsed && typeof parsed === 'object' && parsed.session_id) return parsed;
    } catch (error) { /* 旧格式或存储不可用：按未预取处理 */ }
    return null;
}

function writeStoredPendingNewSession(sessionId, data, workDir) {
    try {
        if (!sessionId) {
            sessionStorage.removeItem(PENDING_NEW_SESSION_KEY);
            return;
        }
        sessionStorage.setItem(PENDING_NEW_SESSION_KEY, JSON.stringify({
            session_id: String(sessionId),
            model_profile_id: (data && data.model_profile_id) || '',
            permission_mode: (data && data.permission_status && data.permission_status.mode) || '',
            // 记录草稿用的是哪个工作目录：刷新后重新进入草稿态时据此判断能否复用。
            work_dir: String(workDir || '').trim(),
        }));
    } catch (error) { /* 存储不可用时退化为页面内复用 */ }
}

function clearPendingNewSession() {
    pendingNewSession = null;
    writeStoredPendingNewSession('');
}

function sessionWorkDirMatchesTarget(session, targetWorkDir) {
    const actual = String(session && session.work_dir || '').trim();
    const defaultWorkDir = (typeof window !== 'undefined') ? window.__WORK_DIR__ : '';
    const expected = String(targetWorkDir || defaultWorkDir || '').trim();
    if (!actual || !expected) return false;
    function normalize(path) {
        const windowsPath = /^[a-z]:[\\/]/i.test(path) || path.indexOf('\\') >= 0;
        const normalized = path.replace(/\\/g, '/').replace(/\/+$/, '');
        return windowsPath ? normalized.toLowerCase() : normalized;
    }
    return normalize(actual) === normalize(expected);
}

/**
 * 后台预取：创建隐藏草稿会话（服务端 metadata.draft，首条 user 事件落盘后才进入列表）。
 * 页面内多次点击“新会话”复用同一份；刷新后重新进入草稿态时按记录的会话 ID 复用。
 */
function ensurePrefetchedNewSession() {
    if (currentSessionId) return Promise.resolve(null);
    const targetWorkDir = newSessionWorkDirTarget();
    if (pendingNewSession) {
        if (String(pendingNewSession.workDir || '') === targetWorkDir) {
            return Promise.resolve(pendingNewSession);
        }
        clearPendingNewSession();
    }
    if (prefetchNewSessionPromise) {
        if (String(prefetchNewSessionWorkDir || '') === targetWorkDir) {
            return prefetchNewSessionPromise;
        }
        return Promise.resolve(prefetchNewSessionPromise).catch(function () { return null; }).then(function () {
            if (currentSessionId) return null;
            return ensurePrefetchedNewSession();
        });
    }
    const targetRevision = newSessionWorkDirRevision;
    const promise = Promise.resolve()
        .then(function () { return prefetchNewSessionInner(targetWorkDir, targetRevision); })
        .catch(function (error) {
            console.warn('新会话后台预取失败，发送时回退为即时创建:', error);
            clearPendingNewSession();
            return null;
        })
        .finally(function () {
            if (prefetchNewSessionPromise === promise) {
                prefetchNewSessionPromise = null;
                prefetchNewSessionWorkDir = null;
            }
        });
    prefetchNewSessionWorkDir = targetWorkDir;
    prefetchNewSessionPromise = promise;
    return promise;
}

async function prefetchNewSessionInner(targetWorkDir, targetRevision) {
    const prefetchStartedAt = performance.now();
    const requestIsCurrent = function () {
        return targetRevision === newSessionWorkDirRevision
            && targetWorkDir === newSessionWorkDirTarget();
    };
    let stored = readStoredPendingNewSession();
    // 用户刚换了目标工作目录：旧草稿是在别的目录（或默认目录）建的，且 work_dir 不可改，
    // 只能丢弃重开，否则新会话会落在错误目录里。
    if (stored && String(stored.work_dir || '') !== targetWorkDir) {
        writeStoredPendingNewSession('');
        stored = null;
    }
    if (stored) {
        try {
            const response = await fetch('/sessions/' + encodeURIComponent(stored.session_id), { cache: 'no-store' });
            if (response.ok) {
                const sess = await response.json();
                if (sess && sess.id && sess.draft
                        && sessionWorkDirMatchesTarget(sess, targetWorkDir)
                        && requestIsCurrent()) {
                    pendingNewSession = {
                        sessionId: String(sess.id),
                        workDir: targetWorkDir,
                        response: {
                            model_profile_id: stored.model_profile_id || '',
                            permission_status: stored.permission_mode ? { mode: stored.permission_mode } : null,
                        },
                        session: sess,
                    };
                    return pendingNewSession;
                }
            }
        } catch (error) { /* 校验失败则重新预取 */ }
        writeStoredPendingNewSession('');
    }
    if (!requestIsCurrent()) return null;
    const createOptions = collectNewSessionCreateOptions(targetWorkDir);
    const response = await fetch('/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(Object.assign({ prefetch: true }, createOptions)),
    });
    if (!response.ok) throw new Error('HTTP ' + response.status);
    const data = await response.json();
    if (!data || !data.session_id) throw new Error('服务端未返回会话 ID');
    // A directory switch can happen while POST /sessions is in flight. Do not
    // let the stale response become the pending draft for the newly selected path.
    if (!requestIsCurrent() || !sessionWorkDirMatchesTarget(data.session, targetWorkDir)) return null;
    pendingNewSession = {
        sessionId: String(data.session_id),
        workDir: targetWorkDir,
        response: data,
        session: data.session || null,
    };
    writeStoredPendingNewSession(pendingNewSession.sessionId, data, targetWorkDir);
    if (typeof uiPerformance !== 'undefined') {
        uiPerformance.sample(pendingNewSession.sessionId, 'session.prefetch', performance.now() - prefetchStartedAt);
    }
    return pendingNewSession;
}

async function applyNewSessionOptionsToLegacyBackend(sessionId, createOptions, createResponse) {
    const tasks = [];
    if (createOptions.reasoning_effort && createResponse.reasoning_effort !== createOptions.reasoning_effort) {
        tasks.push(fetch('/sessions/' + encodeURIComponent(sessionId) + '/reasoning_effort', {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'same-origin',
            body: JSON.stringify({ reasoning_effort: createOptions.reasoning_effort }),
        }).then(async function (response) {
            const data = await response.json();
            if (!response.ok || !data || !data.ok) throw new Error((data && data.error) || '推理强度应用失败');
        }));
    }
    if (createOptions.model_profile_id
        && String(createResponse.model_profile_id || '') !== String(createOptions.model_profile_id)) {
        tasks.push(fetch('/sessions/' + encodeURIComponent(sessionId) + '/model_profile', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin',
            body: JSON.stringify({ profile_id: createOptions.model_profile_id }),
        }).then(async function (response) {
            const data = await response.json();
            if (!response.ok || !data || !data.ok) {
                throw new Error((data && data.error) || '模型配置应用失败');
            }
        }));
    }
    if (createOptions.permission_mode
        && (!createResponse.permission_status
            || String(createResponse.permission_status.mode || '') !== String(createOptions.permission_mode))) {
        tasks.push(fetch('/sessions/' + encodeURIComponent(sessionId) + '/permissions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin',
            body: JSON.stringify({ mode: createOptions.permission_mode }),
        }).then(async function (response) {
            const data = await response.json();
            if (!response.ok || !data || !data.ok) {
                throw new Error((data && data.error) || '权限等级应用失败');
            }
            createResponse.permission_status = data;
        }));
    }
    if (tasks.length) await Promise.all(tasks);
}

async function materializeNewSessionInner() {
    const draftEpoch = switchSessionEpoch;
    const createStartedAt = performance.now();
    let createdSessionId = '';
    try {
        const createOptions = collectNewSessionCreateOptions();
        // 优先复用点“新会话”时启动的后台预取（可能仍在途）；预取失败或超时才回退到
        // 发送时创建，保证这条路径永远可用。
        const prefetched = await ensurePrefetchedNewSession();
        let sessionId = prefetched && prefetched.sessionId ? String(prefetched.sessionId) : '';
        let data = prefetched && prefetched.response ? prefetched.response : null;
        if (!sessionId) {
            const response = await fetch('/sessions', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(createOptions),
            });
            if (!response.ok) throw new Error('HTTP ' + response.status);
            data = await response.json();
            if (!data || !data.session_id) throw new Error('服务端未返回会话 ID');
            sessionId = String(data.session_id);
        }
        clearPendingNewSession();
        // 这次选定的工作目录已被本会话消费；下一次「新建对话」回到全局默认目录。
        newSessionWorkDir = '';
        createdSessionId = sessionId;
        const session = (data && data.session)
            || (prefetched && prefetched.session)
            || { id: sessionId, name: '新会话' };
        sessionStore.protectFromSnapshots(session);

        const ownsDraft = !currentSessionId && switchSessionEpoch === draftEpoch;
        const draftText = ownsDraft && messageInput
            ? messageInput.value
            : readStoredInputDraft(null);
        persistInputDraft(sessionId, draftText);
        removeStoredInputDraft(null);

        if (ownsDraft) {
            setCurrentSessionState(sessionId);
            if (typeof updateHumanInteractionBanner === 'function') updateHumanInteractionBanner(sessionId);
            localStorage.setItem('lastSessionId', sessionId);
            // Do not restore the composer here: it is already the live source
            // of truth and restoring an older value causes the visible blink.
            if (typeof renderFollowupQueue === 'function') renderFollowupQueue(sessionId);
            if (typeof syncFollowupQueueFromServer === 'function') syncFollowupQueueFromServer(sessionId);
        }
        syncArchivedSessionStateFromStore();
        renderSessionListIfChanged(false);
        await applyNewSessionOptionsToLegacyBackend(sessionId, createOptions, data || {});
        if (typeof commitNewSessionModelProfile === 'function') {
            commitNewSessionModelProfile(sessionId);
        }
        if (typeof commitNewSessionReasoningEffort === 'function') commitNewSessionReasoningEffort(sessionId);
        if (typeof commitNewSessionPermissionMode === 'function') {
            commitNewSessionPermissionMode(data.permission_status || null);
        }
        if (ownsDraft && typeof refreshModelProfileSelector === 'function') {
            refreshModelProfileSelector(sessionId);
        }
        document.dispatchEvent(new CustomEvent('myagent:extension-state-changed', {
            detail: { sessionId: sessionId, phase: 'created' },
        }));
        if (typeof uiPerformance !== 'undefined') {
            uiPerformance.sample(sessionId, 'session.create', performance.now() - createStartedAt);
        }
        return sessionId;
    } catch (error) {
        console.error('创建新会话失败', error);
        if (createdSessionId) {
            appendLogVisible('新会话配置应用失败，请重新选择模型或权限后再发送', 'error-log');
        } else if (!currentSessionId && switchSessionEpoch === draftEpoch) {
            appendLogVisible('创建新会话失败，请重试发送', 'error-log');
        }
        return null;
    }
}
