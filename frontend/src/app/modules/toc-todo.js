function ensureUiHoverTooltipEl() {
    if (uiHoverTooltipEl) return uiHoverTooltipEl;
    uiHoverTooltipEl = document.getElementById('ui-hover-tooltip');
    if (!uiHoverTooltipEl) {
        uiHoverTooltipEl = document.createElement('div');
        uiHoverTooltipEl.id = 'ui-hover-tooltip';
        uiHoverTooltipEl.setAttribute('role', 'tooltip');
        document.body.appendChild(uiHoverTooltipEl);
    }
    return uiHoverTooltipEl;
}

function showUiHoverTooltip(ev, text) {
    var t = (text != null) ? String(text) : '';
    if (!t.trim()) return;
    var el = ensureUiHoverTooltipEl();
    el.textContent = t;
    el.classList.add('is-visible');
    requestAnimationFrame(function () {
        positionUiHoverTooltip(ev);
    });
}

function moveUiHoverTooltip(ev) {
    if (!uiHoverTooltipEl || !uiHoverTooltipEl.classList.contains('is-visible')) return;
    if (hoverTooltipMoveScheduled) return;
    hoverTooltipMoveScheduled = true;
    requestAnimationFrame(function () {
        hoverTooltipMoveScheduled = false;
        positionUiHoverTooltip(ev);
    });
}

function clearUiHoverTipTimer() {
    if (uiHoverTipTimer) {
        clearTimeout(uiHoverTipTimer);
        uiHoverTipTimer = null;
    }
}

function hideUiHoverTooltip() {
    clearUiHoverTipTimer();
    uiHoverTipActiveEl = null;
    uiHoverTipLastEv = null;
    if (uiHoverTooltipEl) uiHoverTooltipEl.classList.remove('is-visible');
}

function positionUiHoverTooltip(ev) {
    var el = uiHoverTooltipEl;
    if (!el) return;
    el.style.left = '-9999px';
    el.style.top = '0';
    var pad = 14;
    var bw = el.offsetWidth;
    var bh = el.offsetHeight;
    var vw = window.innerWidth;
    var vh = window.innerHeight;
    var x = ev.clientX + pad;
    var y = ev.clientY + pad;
    if (x + bw > vw - 10) x = Math.max(10, vw - bw - 10);
    if (y + bh > vh - 10) y = Math.max(10, ev.clientY - bh - pad);
    if (x < 10) x = 10;
    if (y < 10) y = 10;
    el.style.left = x + 'px';
    el.style.top = y + 'px';
}

/** 统一悬停说明（替代原生 title），文案来自 data-ui-tip；停留超过 UI_HOVER_TIP_DELAY_MS 才显示 */
function bindUiHoverTip(el) {
    if (!el || el._uiHoverTipBound) return;
    var tip = el.getAttribute('data-ui-tip');
    if (!tip || !String(tip).trim()) {
        var legacyTitle = el.getAttribute('title');
        if (legacyTitle && String(legacyTitle).trim()) {
            el.setAttribute('data-ui-tip', legacyTitle);
            tip = legacyTitle;
        }
    }
    if (!tip || !String(tip).trim()) return;
    el._uiHoverTipBound = true;
    el.removeAttribute('title');
    el.addEventListener('mouseenter', function (ev) {
        var t = el.getAttribute('data-ui-tip');
        if (t == null || !String(t).trim()) return;
        if (typeof translateUiString === 'function') t = translateUiString(t);
        clearUiHoverTipTimer();
        hideUiHoverTooltip();
        uiHoverTipActiveEl = el;
        uiHoverTipLastEv = ev;
        uiHoverTipTimer = setTimeout(function () {
            uiHoverTipTimer = null;
            if (uiHoverTipActiveEl !== el) return;
            showUiHoverTooltip(uiHoverTipLastEv || ev, t);
        }, UI_HOVER_TIP_DELAY_MS);
    });
    el.addEventListener('mousemove', function (ev) {
        uiHoverTipLastEv = ev;
        moveUiHoverTooltip(ev);
    });
    el.addEventListener('mouseleave', function () {
        if (uiHoverTipActiveEl === el) uiHoverTipActiveEl = null;
        clearUiHoverTipTimer();
        hideUiHoverTooltip();
    });
    el.addEventListener('focus', function () {
        var t = el.getAttribute('data-ui-tip');
        if (t == null || !String(t).trim()) return;
        if (typeof translateUiString === 'function') t = translateUiString(t);
        var rect = el.getBoundingClientRect();
        showUiHoverTooltip({ clientX: rect.right, clientY: rect.top }, t);
    });
    el.addEventListener('blur', hideUiHoverTooltip);
}

function initUiHoverTips(root) {
    root = root || document;
    root.querySelectorAll('[data-ui-tip]').forEach(function (el) {
        bindUiHoverTip(el);
    });
    root.querySelectorAll('[title]').forEach(function (el) {
        bindUiHoverTip(el);
    });
}

function scheduleTocActiveUpdate() {
    var list = document.getElementById('chat-toc-list');
    if (!list || !list.querySelector('a[data-event-index]')) return;
    if (tocActiveUpdateRaf) return;
    tocActiveUpdateRaf = requestAnimationFrame(function () {
        tocActiveUpdateRaf = 0;
        updateTocActiveFromViewport();
    });
}

function updateTocActiveFromViewport() {
    var list = document.getElementById('chat-toc-list');
    if (!list || !chatContainer) return;
    var stream = getVisibleChatStream();
    if (!stream) return;
    var users = stream.querySelectorAll('.msg-wrap--user[data-event-index]');
    if (!users.length) return;
    var cr = chatContainer.getBoundingClientRect();
    var pivot = cr.top + cr.height * 0.5;
    var chosen = null;
    for (var i = 0; i < users.length; i += 1) {
        var u = users[i];
        var r = u.getBoundingClientRect();
        if (r.top <= pivot) {
            chosen = u;
            continue;
        }
        break;
    }
    if (!chosen) chosen = users[0];
    if (!chosen) return;
    var idx = chosen.getAttribute('data-event-index');
    if (idx == null) return;
    var active = list.querySelector('a[data-event-index="' + idx + '"]');
    list.querySelectorAll('a.is-current').forEach(function (a) {
        if (a !== active) a.classList.remove('is-current');
    });
    if (!active) return;
    active.classList.add('is-current');
    var pad = 6;
    var top = active.offsetTop;
    var bottom = top + active.offsetHeight;
    if (top < list.scrollTop + pad) {
        list.scrollTop = Math.max(0, top - pad);
    } else if (bottom > list.scrollTop + list.clientHeight - pad) {
        list.scrollTop = bottom - list.clientHeight + pad;
    }
}

function clearTocForSessionLoad() {
    const toc = document.getElementById('chat-toc');
    const list = document.getElementById('chat-toc-list');
    tocRebuildEpoch += 1;
    if (list) list.textContent = '';
    if (toc) toc.classList.remove('is-open');
    notifyPanelContentChanged();
}

function clearTodoForSessionLoad() {
    const root = document.getElementById('chat-todo-plan');
    const statsEl = document.getElementById('chat-todo-plan-stats');
    const listEl = document.getElementById('chat-todo-plan-list');
    todoRefreshEpoch += 1;
    if (currentSessionId) clearTodoPlanState(currentSessionId);
    if (statsEl) statsEl.textContent = '';
    if (listEl) listEl.textContent = '';
    if (root) root.classList.remove('is-open');
    notifyPanelContentChanged();
}

const tocTurnsCacheBySession = new Map();

function setTocTurnsForSession(sessionId, turns) {
    if (!sessionId || !Array.isArray(turns)) return;
    tocTurnsCacheBySession.set(sessionId, turns);
}

function truncateTocTurnsForSession(sessionId, beforeIndex) {
    if (!sessionId) return;
    const before = Math.max(0, Number(beforeIndex) || 0);
    const turns = tocTurnsCacheBySession.get(sessionId) || [];
    tocTurnsCacheBySession.set(sessionId, turns.filter(function (row) {
        return Number(row && row.event_index) < before;
    }));
}

function startTocForSessionLoad(sessionId) {
    if (!sessionId || sessionId !== currentSessionId) return;
    var prevSuppress = suppressTocDuringSessionLoad;
    suppressTocDuringSessionLoad = false;
    try {
        rebuildToc();
    } finally {
        suppressTocDuringSessionLoad = prevSuppress;
    }
}

function rebuildToc(options) {
    options = options || {};
    const toc = document.getElementById('chat-toc');
    const list = document.getElementById('chat-toc-list');
    if (!toc || !list) return;
    if (suppressTocDuringSessionLoad) {
        return;
    }
    if (!list._tocTipScrollHide) {
        list._tocTipScrollHide = true;
        list.addEventListener('scroll', hideUiHoverTooltip, { passive: true });
    }
    list.textContent = '';
    const sid = currentSessionId;
    const epoch = ++tocRebuildEpoch;
    (async function () {
        let turns = [];
        if (sid) {
            if (Array.isArray(options.turns)) {
                turns = options.turns;
                tocTurnsCacheBySession.set(sid, turns);
            } else if (options.localOnly) {
                turns = tocTurnsCacheBySession.get(sid) || [];
            } else {
                try {
                    const r = await fetch('/sessions/' + encodeURIComponent(sid) + '/user_turns');
                    if (epoch !== tocRebuildEpoch || sid !== currentSessionId) return;
                    if (r.ok) {
                        const j = await r.json();
                        if (Array.isArray(j)) {
                            turns = j;
                            tocTurnsCacheBySession.set(sid, j);
                        }
                    }
                } catch (e) {
                    turns = tocTurnsCacheBySession.get(sid) || [];
                }
            }
        }
        if (epoch !== tocRebuildEpoch || sid !== currentSessionId) return;
        /** event_index → 预览（服务端与当前 DOM 合并：刚发出的提问尚未写入 ui_events，由气泡补上） */
        const merged = new Map();
        turns.forEach(function (row) {
            const ei = Number(row.event_index);
            if (!Number.isFinite(ei)) return;
            merged.set(ei, String(row.preview || '').trim());
        });
        const vs = getVisibleChatStream();
        const rootForUsers = vs || chatContainer;
        if (rootForUsers) {
            rootForUsers.querySelectorAll('.msg-wrap--user[data-event-index]').forEach(function (wrap) {
                const ei = parseInt(wrap.getAttribute('data-event-index'), 10);
                if (!Number.isFinite(ei)) return;
                const text = (wrap.querySelector('.message') && wrap.querySelector('.message').innerText || '').trim();
                merged.set(ei, text);
            });
        }
        if (epoch !== tocRebuildEpoch || sid !== currentSessionId) return;
        list.replaceChildren();
        let indices = [...merged.keys()].filter(function (x) { return Number.isFinite(x); }).sort(function (a, b) { return a - b; });
        function normalizedPreviewKey(p) {
            return String(p || '').trim().replace(/\s+/g, ' ');
        }
        const dupCountByKey = new Map();
        indices.forEach(function (ei) {
            const k = normalizedPreviewKey(merged.get(ei));
            dupCountByKey.set(k, (dupCountByKey.get(k) || 0) + 1);
        });
        function appendTocLink(label, titleFull, scrollToWrap, eventIndex) {
            const a = document.createElement('a');
            a.href = '#';
            if (eventIndex != null) a.setAttribute('data-event-index', String(eventIndex));
            var tipText = (titleFull != null && String(titleFull).trim() !== '')
                ? String(titleFull)
                : String(label || '');
            a.setAttribute('data-ui-tip', tipText);
            bindUiHoverTip(a);
            const tocSpan = document.createElement('span');
            tocSpan.className = 'chat-toc-text';
            tocSpan.textContent = label;
            a.appendChild(tocSpan);
            a.addEventListener('click', function (e) {
                e.preventDefault();
                hideUiHoverTooltip();
                if (typeof scrollToWrap === 'function') scrollToWrap();
            });
            list.appendChild(a);
        }
        if (indices.length === 0) {
            const users = rootForUsers ? rootForUsers.querySelectorAll('.msg-wrap--user') : [];
            if (users.length === 0) {
                toc.classList.remove('is-open');
                notifyPanelContentChanged();
                return;
            }
            toc.classList.add('is-open');
            users.forEach(function (wrap, idx) {
                if (!wrap.id) wrap.id = 'user-msg-' + idx;
                const text = (wrap.querySelector('.message') && wrap.querySelector('.message').innerText || '').trim();
                const label = text.length > 44 ? text.slice(0, 42) + '…' : (text || ('问题 ' + (idx + 1)));
                appendTocLink(label, text, function () {
                    wrap.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                }, wrap.getAttribute('data-event-index'));
            });
        } else {
            toc.classList.add('is-open');
            indices.forEach(function (ei) {
                const preview = merged.get(ei) || '';
                var label = preview.length > 44 ? preview.slice(0, 42) + '…' : (preview || ('问题 #' + (ei + 1)));
                var titleFull = preview || label;
                const nk = normalizedPreviewKey(preview);
                if ((dupCountByKey.get(nk) || 0) > 1) {
                    label = label + ' #' + (ei + 1);
                    titleFull = (preview || '') + '（事件索引 ' + ei + '）';
                }
                appendTocLink(label, titleFull, function () {
                    void scrollToUserTurnOrLoadOlder(ei);
                }, ei);
            });
        }
        notifyPanelContentChanged();
        if (tocScrollBottomOnNextBuild) {
            tocScrollBottomOnNextBuild = false;
            list.scrollTop = list.scrollHeight;
        } else if (!replayingMessages) {
            requestAnimationFrame(function () {
                requestAnimationFrame(function () {
                    list.scrollTop = list.scrollHeight;
                });
            });
        } else {
            scheduleTocActiveUpdate();
        }
    })();
}

function todoPlanStatusLabel(st) {
    if (st === 'completed') return '已完成';
    if (st === 'in_progress') return '进行中';
    return '待处理';
}

function syncGoalTodoPanelVisibility() {
    const root = document.getElementById('chat-todo-plan');
    const goalCard = document.getElementById('chat-goal-card');
    const todoCard = document.getElementById('chat-todo-card');
    if (!root) return;
    const hasVisibleCard = !!((goalCard && !goalCard.hidden) || (todoCard && !todoCard.hidden));
    root.classList.toggle('is-open', hasVisibleCard);
    notifyPanelContentChanged();
}

async function clearTodoPlan() {
    const sid = currentSessionId;
    if (!sid) return;
    try {
        await fetch('/sessions/' + encodeURIComponent(sid) + '/todo_plan', { method: 'DELETE' });
    } catch (e) { /* ignore */ }
    clearTodoPlanState(sid);
    const todoCard = document.getElementById('chat-todo-card');
    if (todoCard) todoCard.hidden = true;
    const statsEl = document.getElementById('chat-todo-plan-stats');
    const listEl = document.getElementById('chat-todo-plan-list');
    if (statsEl) statsEl.textContent = '';
    if (listEl) listEl.textContent = '';
    syncGoalTodoPanelVisibility();
}

function renderTodoPlanSnapshot(snapshot) {
    const root = document.getElementById('chat-todo-plan');
    const listEl = document.getElementById('chat-todo-plan-list');
    const statsEl = document.getElementById('chat-todo-plan-stats');
    const todoCard = document.getElementById('chat-todo-card');
    if (!root || !listEl || !statsEl || !todoCard) return;
    const data = snapshot || { items: [], done: 0, total: 0, has_plan: false };
    const items = Array.isArray(data.items) ? data.items : [];
    const has = !!(data.has_plan && items.length > 0);
    todoCard.hidden = !has;
    if (!has) {
        listEl.textContent = '';
        statsEl.textContent = '';
        syncGoalTodoPanelVisibility();
        return;
    }
    const done = data.done;
    const total = data.total;
    const statsText = String(done) + ' / ' + String(total) + ' 已完成';
    statsEl.textContent = typeof translateUiString === 'function' ? translateUiString(statsText) : statsText;
    listEl.textContent = '';
    items.forEach(function (it) {
        const li = document.createElement('li');
        const st = (it && it.status) || 'pending';
        li.className = 'todo-plan-item todo-plan--' + String(st);
        const tag = document.createElement('span');
        tag.className = 'todo-plan-status-tag';
        const statusLabel = todoPlanStatusLabel(st);
        tag.textContent = typeof translateUiString === 'function' ? translateUiString(statusLabel) : statusLabel;
        li.appendChild(tag);
        const text = document.createElement('span');
        text.textContent = (it && it.text != null) ? String(it.text) : '';
        li.appendChild(text);
        listEl.appendChild(li);
    });
    syncGoalTodoPanelVisibility();
}

function applyTodoPlanFromPayload(data) {
    renderTodoPlanSnapshot(applyTodoPlanToStore(currentSessionId, data));
}

function renderTodoPlanForCurrentSession() {
    renderTodoPlanSnapshot(selectTodoPlan(currentSessionId));
    renderGoalForCurrentSession();
    void refreshGoalCard();
}

let renderedGoalState = null;
const goalStateBySession = new Map();
const goalElapsedAnchorBySession = new Map();
const goalRefreshInFlightBySession = new Map();
const goalStreamRecoveryInFlightBySession = new Set();

function summarizeGoalObjective(value, maxLength) {
    const full = String(value == null ? '' : value).replace(/\s+/g, ' ').trim();
    const limit = Math.max(24, Number(maxLength) || 96);
    if (full.length <= limit) return full;
    return full.slice(0, limit - 1).trimEnd() + '…';
}

function renderGoalForCurrentSession() {
    const sid = String(currentSessionId || '');
    const goal = sid && goalStateBySession.has(sid) ? goalStateBySession.get(sid) : null;
    renderGoalCard(goal, sid);
}

function setGoalStateForSession(sessionId, goal) {
    const sid = String(sessionId || '').trim();
    if (!sid) return;
    const now = Date.now();
    const previous = goalStateBySession.get(sid);
    const previousAnchor = goalElapsedAnchorBySession.get(sid);
    const normalized = goal && goal.id
        ? Object.assign({}, goal)
        : null;
    goalStateBySession.set(sid, normalized);
    if (normalized) {
        let elapsedSeconds = Math.max(0, Number(normalized.elapsed_seconds || 0));
        const sameGoal = previous && previousAnchor
            && String(previous.id || '') === String(normalized.id || '')
            && String(previousAnchor.goalId || '') === String(normalized.id || '');
        if (sameGoal) {
            const previousLiveSeconds = String(previousAnchor.status || '') === 'active'
                ? Math.max(0, (now - Number(previousAnchor.receivedAt || now)) / 1000)
                : 0;
            elapsedSeconds = Math.max(
                elapsedSeconds,
                Number(previousAnchor.elapsedSeconds || 0) + previousLiveSeconds,
            );
        }
        normalized.elapsed_seconds = elapsedSeconds;
        goalElapsedAnchorBySession.set(sid, {
            goalId: String(normalized.id || ''),
            status: String(normalized.status || ''),
            elapsedSeconds: elapsedSeconds,
            receivedAt: now,
        });
    } else {
        goalElapsedAnchorBySession.delete(sid);
    }
    if (sid === String(currentSessionId || '')) {
        renderGoalCard(normalized, sid);
        if (normalized && String(normalized.status || '') === 'active') {
            void recoverActiveGoalStream(sid);
        }
    }
}

async function recoverActiveGoalStream(sessionId) {
    const sid = String(sessionId || '').trim();
    if (!sid || sid !== String(currentSessionId || '') || document.visibilityState === 'hidden') return false;
    const goal = goalStateBySession.get(sid);
    if (!goal || String(goal.status || '') !== 'active') return false;
    if (typeof getSessionRunState === 'function' && getSessionRunState(sid)) return false;
    if (goalStreamRecoveryInFlightBySession.has(sid)) return false;
    goalStreamRecoveryInFlightBySession.add(sid);
    try {
        if (typeof reconcileRunStateFromServer === 'function') {
            await reconcileRunStateFromServer({ silent: true });
        }
        if (sid !== String(currentSessionId || '')) return false;
        const latestGoal = goalStateBySession.get(sid);
        if (!latestGoal || String(latestGoal.status || '') !== 'active') return false;
        if (typeof getSessionRunState === 'function' && getSessionRunState(sid)) return false;
        const serverActive = (typeof isServerStreamActive === 'function' && isServerStreamActive(sid))
            || (typeof isSessionRunning === 'function' && isSessionRunning(sid));
        if (!serverActive || typeof maybeStartStreamPollForSession !== 'function') return false;
        maybeStartStreamPollForSession(sid, { skipInitialLoad: true });
        return true;
    } catch (error) {
        return false;
    } finally {
        goalStreamRecoveryInFlightBySession.delete(sid);
    }
}

function formatGoalElapsed(seconds) {
    const total = Math.max(0, Math.floor(Number(seconds) || 0));
    const hours = Math.floor(total / 3600);
    const minutes = Math.floor((total % 3600) / 60);
    const secs = total % 60;
    const translate = function (value) {
        return typeof translateUiString === 'function' ? translateUiString(value) : value;
    };
    if (hours > 0) return String(hours) + translate('小时') + ' ' + String(minutes) + translate('分') + ' ' + String(secs).padStart(2, '0') + translate('秒');
    if (minutes > 0) return String(minutes) + translate('分') + ' ' + String(secs).padStart(2, '0') + translate('秒');
    return String(secs) + translate('秒');
}

function renderGoalMeta(goal, sessionId) {
    const sid = String(sessionId || currentSessionId || '');
    if (!goal || sid !== String(currentSessionId || '')) return;
    const metaEl = document.getElementById('chat-goal-meta');
    if (!metaEl) return;
    const translate = function (value) {
        return typeof translateUiString === 'function' ? translateUiString(value) : value;
    };
    const status = String(goal.status || 'active');
    const anchor = goalElapsedAnchorBySession.get(sid);
    const anchorMatches = anchor && String(anchor.goalId || '') === String(goal.id || '');
    const receivedAt = Number(anchorMatches ? anchor.receivedAt : Date.now());
    const liveSeconds = status === 'active' ? Math.max(0, (Date.now() - receivedAt) / 1000) : 0;
    const elapsed = Number(anchorMatches ? anchor.elapsedSeconds : goal.elapsed_seconds || 0) + liveSeconds;
    const statusEl = document.getElementById('chat-goal-status');
    if (statusEl && status === 'active') {
        statusEl.textContent = translate('进行中') + ' · ' + formatGoalElapsed(elapsed);
    }
    const usedTokens = Math.max(0, Number(goal.used_tokens || 0));
    const tokenText = goal.token_budget == null
        ? 'Token ' + translate('已消耗') + ' ' + String(usedTokens)
        : 'Token ' + String(usedTokens) + ' / ' + String(goal.token_budget);
    const continuationText = translate('续跑') + ' ' + String(goal.continuation_count || 0);
    const failureText = translate('连续失败') + ' ' + String(goal.consecutive_failures || 0);
    const judgeText = 'Judge ' + String(goal.judge_count || 0);
    const reasonLabels = {
        token_budget_exhausted: 'Token 预算已耗尽',
        consecutive_run_failures: '连续运行失败',
        judge_parse_failures: 'Judge 解析连续失败',
        judge_transport_failures: 'Judge 调用连续失败',
        react_iteration_limit: 'ReAct 已达到轮次上限',
        manual: '手动暂停'
    };
    const rawReason = String(goal.pause_reason || '');
    const reasonText = reasonLabels[rawReason] || rawReason;
    const pauseReason = reasonText ? ' · ' + translate(reasonText) : '';
    const metaText = tokenText + ' · ' + translate('用时') + ' ' + formatGoalElapsed(elapsed)
        + ' · ' + judgeText + ' · ' + continuationText + ' · ' + failureText + pauseReason;
    let help = translate('连续失败表示 Goal 执行中连续以失败或错误结束的运行次数（包括初始执行和自动续跑）；任一轮成功完成后会归零。');
    if (goal.last_error) help += '\n' + translate('最近错误') + ': ' + String(goal.last_error);
    if (goal.last_judge_verdict) {
        help += '\n' + translate('最近 Judge') + ': ' + String(goal.last_judge_verdict);
        if (goal.last_judge_reason) help += ' · ' + String(goal.last_judge_reason);
    }
    metaEl.setAttribute('data-ui-tip', metaText + '\n' + help);
    metaEl.setAttribute('aria-label', translate('统计信息') + ': ' + metaText + '. ' + help);
    bindUiHoverTip(metaEl);
}

function renderGoalCard(goal, sessionId) {
    const sid = String(sessionId || currentSessionId || '');
    if (sid !== String(currentSessionId || '')) return;
    const card = document.getElementById('chat-goal-card');
    if (!card) return;
    const has = !!(goal && goal.id);
    renderedGoalState = has ? Object.assign({}, goal) : null;
    const statusEl = document.getElementById('chat-goal-status');
    const objectiveEl = document.getElementById('chat-goal-objective');
    const metaEl = document.getElementById('chat-goal-meta');
    const toggle = document.getElementById('chat-goal-toggle');
    const edit = document.getElementById('chat-goal-edit');
    const remove = document.getElementById('chat-goal-delete');
    const review = document.getElementById('chat-goal-review');
    card.hidden = !has;
    if (!has) {
        if (statusEl) statusEl.textContent = '';
        if (objectiveEl) {
            objectiveEl.textContent = '';
            objectiveEl.removeAttribute('data-ui-tip');
            objectiveEl.removeAttribute('aria-label');
        }
        if (metaEl) {
            metaEl.removeAttribute('data-ui-tip');
            metaEl.removeAttribute('aria-label');
            metaEl.hidden = true;
        }
        if (toggle) toggle.hidden = true;
        if (edit) edit.hidden = true;
        if (remove) remove.hidden = true;
        if (review) review.hidden = true;
        syncGoalTodoPanelVisibility();
        return;
    }
    if (metaEl) metaEl.hidden = false;
    const status = String(goal.status || 'active');
    const statusLabels = {
        active: '进行中', paused: '已暂停', completed: '已完成', blocked: '已阻塞', cancelled: '已取消'
    };
    if (statusEl) {
        const label = statusLabels[status] || status;
        statusEl.textContent = typeof translateUiString === 'function' ? translateUiString(label) : label;
    }
    if (objectiveEl) {
        const fullObjective = String(goal.objective || '').trim();
        const summary = summarizeGoalObjective(fullObjective, 200);
        objectiveEl.textContent = summary;
        objectiveEl.setAttribute('aria-label', fullObjective);
        if (summary !== fullObjective) {
            objectiveEl.setAttribute('data-ui-tip', fullObjective);
            bindUiHoverTip(objectiveEl);
        } else {
            objectiveEl.removeAttribute('data-ui-tip');
        }
    }
    renderGoalMeta(goal, sid);
    if (toggle) {
        const canToggle = status === 'active' || status === 'paused';
        const isPaused = status === 'paused';
        const toggleLabel = isPaused ? '开始 Goal' : '暂停 Goal';
        const translatedToggleLabel = typeof translateUiString === 'function' ? translateUiString(toggleLabel) : toggleLabel;
        toggle.hidden = !canToggle;
        toggle.setAttribute('aria-label', translatedToggleLabel);
        toggle.setAttribute('data-ui-tip', translatedToggleLabel);
        const playIcon = toggle.querySelector('.chat-goal-icon-play');
        const pauseIcon = toggle.querySelector('.chat-goal-icon-pause');
        if (playIcon) playIcon.toggleAttribute('hidden', !isPaused);
        if (pauseIcon) pauseIcon.toggleAttribute('hidden', isPaused);
    }
    const isCompleted = status === 'completed';
    if (edit) edit.hidden = isCompleted;
    if (remove) remove.hidden = isCompleted;
    if (review) review.hidden = !isCompleted;
    syncGoalTodoPanelVisibility();
}

async function refreshGoalCard() {
    const sid = currentSessionId;
    if (!sid) { renderGoalCard(null, ''); return; }
    if (goalRefreshInFlightBySession.has(sid)) return goalRefreshInFlightBySession.get(sid);
    const task = (async function () {
        try {
            const r = await fetch('/sessions/' + encodeURIComponent(sid) + '/goal');
            if (!r.ok) return;
            const data = await r.json();
            setGoalStateForSession(sid, data.goal || null);
        } catch (e) { /* the session-scoped cache or hidden state remains authoritative */ }
        finally { goalRefreshInFlightBySession.delete(sid); }
    })();
    goalRefreshInFlightBySession.set(sid, task);
    return task;
}

setInterval(function () {
    if (document.visibilityState === 'hidden' || isGoalEditModalOpen() || isGoalReviewModalOpen()) return;
    const sid = String(currentSessionId || '');
    const goal = sid ? goalStateBySession.get(sid) : null;
    if (goal) renderGoalMeta(goal, sid);
}, 1000);

setInterval(function () {
    if (document.visibilityState === 'hidden' || !currentSessionId || isGoalEditModalOpen() || isGoalReviewModalOpen()) return;
    void refreshGoalCard();
}, 5000);

setInterval(function () {
    if (document.visibilityState === 'hidden' || isGoalEditModalOpen() || isGoalReviewModalOpen()) return;
    const sid = String(currentSessionId || '');
    const goal = sid ? goalStateBySession.get(sid) : null;
    if (!goal || String(goal.status || '') !== 'active') return;
    if (typeof getSessionRunState === 'function' && getSessionRunState(sid)) return;
    void recoverActiveGoalStream(sid);
}, 2000);

async function controlCurrentGoal(action, payloadOverrides) {
    const sid = currentSessionId;
    if (!sid) return false;
    try {
        const payload = Object.assign({}, payloadOverrides || {});
        if (action === 'resume' && renderedGoalState
            && renderedGoalState.token_budget != null
            && Number(renderedGoalState.remaining_tokens || 0) <= 0) {
            const promptText = typeof translateUiString === 'function'
                ? translateUiString('请输入要增加的 Token 预算')
                : '请输入要增加的 Token 预算';
            const raw = window.prompt(promptText, '10000');
            if (raw == null) return false;
            const additional = Number(raw);
            if (!Number.isInteger(additional) || additional <= 0) {
                const message = typeof translateUiString === 'function'
                    ? translateUiString('预算必须是大于 0 的整数。')
                    : '预算必须是大于 0 的整数。';
                if (typeof showUiAlert === 'function') showUiAlert({ title: 'Goal', message: message, variant: 'error' });
                return false;
            }
            payload.additional_budget = additional;
        }
        const r = await fetch('/sessions/' + encodeURIComponent(sid) + '/goal/' + encodeURIComponent(action), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        const data = await r.json();
        if (r.ok) setGoalStateForSession(sid, data.goal || null);
        if (!r.ok && typeof showUiAlert === 'function') {
            const title = typeof translateUiString === 'function' ? translateUiString('Goal 操作失败') : 'Goal 操作失败';
            showUiAlert({ title: title, message: String(data.error || 'Unknown error'), variant: 'error' });
        }
        if (action === 'resume' || (action === 'review' && String(payload.decision || '') === 'continue')) {
            void refreshSingleSessionRow(sid);
        }
        return r.ok;
    } catch (e) {
        if (typeof showUiAlert === 'function') {
            const title = typeof translateUiString === 'function' ? translateUiString('Goal 操作失败') : 'Goal 操作失败';
            showUiAlert({ title: title, message: String((e && e.message) || e), variant: 'error' });
        }
        return false;
    }
}

function toggleCurrentGoalState() {
    if (!renderedGoalState) return;
    const status = String(renderedGoalState.status || '');
    if (status === 'active') void controlCurrentGoal('pause');
    else if (status === 'paused') void controlCurrentGoal('resume');
}

function goalEditModalElements() {
    return {
        root: document.getElementById('goal-edit-modal-root'),
        input: document.getElementById('goal-edit-textarea'),
        count: document.getElementById('goal-edit-char-count'),
        save: document.getElementById('goal-edit-save'),
        cancel: document.getElementById('goal-edit-cancel'),
        close: document.getElementById('goal-edit-modal-close'),
    };
}

function isGoalEditModalOpen() {
    const root = document.getElementById('goal-edit-modal-root');
    return !!(root && root.classList.contains('is-open'));
}

function updateGoalEditModalState() {
    const elements = goalEditModalElements();
    if (!elements.root || !elements.input) return;
    const value = String(elements.input.value || '');
    const normalized = value.trim();
    const original = String(elements.root._goalOriginalObjective || '').trim();
    if (elements.count) elements.count.textContent = String(value.length) + ' / 12000';
    if (elements.save) {
        elements.save.disabled = !!elements.root._goalSaving
            || !normalized
            || normalized === original
            || value.length > 12000;
    }
}

function closeGoalEditModal(restoreFocus) {
    const elements = goalEditModalElements();
    if (!elements.root || !elements.root.classList.contains('is-open')) return;
    elements.root.classList.remove('is-open');
    elements.root.setAttribute('aria-hidden', 'true');
    elements.root._goalSaving = false;
    document.body.classList.remove('goal-editing');
    document.body.style.overflow = '';
    const returnFocus = elements.root._goalReturnFocus;
    elements.root._goalReturnFocus = null;
    if (restoreFocus !== false && returnFocus && typeof returnFocus.focus === 'function') {
        requestAnimationFrame(function () { returnFocus.focus(); });
    }
}

async function saveGoalEditModal() {
    const elements = goalEditModalElements();
    if (!elements.root || !elements.input || elements.root._goalSaving) return false;
    const objective = String(elements.input.value || '').trim();
    if (!objective || objective.length > 12000) return false;
    const sid = String(elements.root.dataset.sessionId || '');
    const goalId = String(elements.root.dataset.goalId || '');
    if (sid !== String(currentSessionId || '') || !renderedGoalState || String(renderedGoalState.id || '') !== goalId) {
        closeGoalEditModal(false);
        return false;
    }
    elements.root._goalSaving = true;
    updateGoalEditModalState();
    const saved = await controlCurrentGoal('edit', { objective: objective });
    elements.root._goalSaving = false;
    if (saved) closeGoalEditModal();
    else updateGoalEditModalState();
    return saved;
}

function ensureGoalEditModalBindings() {
    const elements = goalEditModalElements();
    if (!elements.root || elements.root._goalEditBound) return elements;
    elements.root._goalEditBound = true;
    if (elements.input) {
        elements.input.addEventListener('input', updateGoalEditModalState);
        elements.input.addEventListener('keydown', function (event) {
            if (event.key === 'Escape') {
                event.preventDefault();
                closeGoalEditModal();
            } else if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
                event.preventDefault();
                void saveGoalEditModal();
            }
        });
    }
    if (elements.save) elements.save.addEventListener('click', function () { void saveGoalEditModal(); });
    if (elements.cancel) elements.cancel.addEventListener('click', function () { closeGoalEditModal(); });
    if (elements.close) elements.close.addEventListener('click', function () { closeGoalEditModal(); });
    elements.root.addEventListener('mousedown', function (event) {
        if (event.target === elements.root) closeGoalEditModal();
    });
    return elements;
}

function editCurrentGoal() {
    if (!renderedGoalState) return;
    const elements = ensureGoalEditModalBindings();
    if (!elements.root || !elements.input) return;
    const currentObjective = String(renderedGoalState.objective || '');
    elements.root.dataset.sessionId = String(currentSessionId || '');
    elements.root.dataset.goalId = String(renderedGoalState.id || '');
    elements.root._goalOriginalObjective = currentObjective;
    elements.root._goalReturnFocus = document.activeElement;
    elements.root._goalSaving = false;
    elements.input.value = currentObjective;
    elements.root.classList.add('is-open');
    elements.root.setAttribute('aria-hidden', 'false');
    document.body.classList.add('goal-editing');
    document.body.style.overflow = 'hidden';
    updateGoalEditModalState();
    requestAnimationFrame(function () {
        elements.input.focus();
        elements.input.setSelectionRange(0, 0);
        elements.input.scrollTop = 0;
    });
}

async function deleteCurrentGoal() {
    if (!renderedGoalState) return;
    const translate = function (value) {
        return typeof translateUiString === 'function' ? translateUiString(value) : value;
    };
    const confirmed = typeof openUiModal === 'function'
        ? await openUiModal({
            title: translate('确认删除 Goal'),
            message: translate('删除后当前 Goal 将从此会话中移除。此操作不会删除历史审计事件。'),
            confirmText: translate('确认删除'),
            cancelText: translate('取消'),
            danger: true,
        })
        : window.confirm(translate('确认删除 Goal'));
    if (!confirmed) return;
    await controlCurrentGoal('delete');
}

function goalReviewModalElements() {
    return {
        root: document.getElementById('goal-review-modal-root'),
        objective: document.getElementById('goal-review-objective'),
        judge: document.getElementById('goal-review-judge-result'),
        status: document.getElementById('goal-review-modal-status'),
        approve: document.getElementById('goal-review-approve'),
        save: document.getElementById('goal-review-save'),
        continueGoal: document.getElementById('goal-review-continue'),
        close: document.getElementById('goal-review-modal-close'),
    };
}

function isGoalReviewModalOpen() {
    const root = document.getElementById('goal-review-modal-root');
    return !!(root && root.classList.contains('is-open'));
}

function setGoalReviewModalStatus(message, kind) {
    const elements = goalReviewModalElements();
    if (!elements.status) return;
    elements.status.textContent = String(message || '');
    elements.status.classList.toggle('is-error', kind === 'error');
    elements.status.classList.toggle('is-success', kind === 'success');
}

function setGoalReviewModalBusy(busy) {
    const elements = goalReviewModalElements();
    if (!elements.root) return;
    elements.root._goalReviewSaving = !!busy;
    [elements.approve, elements.save, elements.continueGoal].forEach(function (button) {
        if (button) button.disabled = !!busy;
    });
    if (elements.objective) elements.objective.disabled = !!busy;
    if (elements.judge) elements.judge.disabled = !!busy;
}

function closeGoalReviewModal(restoreFocus) {
    const elements = goalReviewModalElements();
    if (!elements.root || !elements.root.classList.contains('is-open')) return;
    elements.root.classList.remove('is-open');
    elements.root.setAttribute('aria-hidden', 'true');
    setGoalReviewModalBusy(false);
    document.body.classList.remove('goal-reviewing');
    document.body.style.overflow = '';
    const returnFocus = elements.root._goalReturnFocus;
    elements.root._goalReturnFocus = null;
    if (restoreFocus !== false && returnFocus && typeof returnFocus.focus === 'function') {
        requestAnimationFrame(function () { returnFocus.focus(); });
    }
}

async function submitGoalReview(decision) {
    const elements = goalReviewModalElements();
    if (!elements.root || elements.root._goalReviewSaving) return false;
    const objective = String((elements.objective && elements.objective.value) || '').trim();
    const judgeResult = String((elements.judge && elements.judge.value) || '').trim();
    if (!objective) {
        setGoalReviewModalStatus(
            typeof translateUiString === 'function' ? translateUiString('Goal 描述不能为空。') : 'Goal 描述不能为空。',
            'error'
        );
        return false;
    }
    const sid = String(elements.root.dataset.sessionId || '');
    const goalId = String(elements.root.dataset.goalId || '');
    if (
        sid !== String(currentSessionId || '')
        || !renderedGoalState
        || String(renderedGoalState.id || '') !== goalId
        || String(renderedGoalState.status || '') !== 'completed'
    ) {
        closeGoalReviewModal(false);
        return false;
    }
    const payload = {
        decision: String(decision || ''),
        objective: objective,
        judge_result: judgeResult
    };
    if (
        decision === 'continue'
        && renderedGoalState.token_budget != null
        && Number(renderedGoalState.remaining_tokens || 0) <= 0
    ) {
        const promptText = typeof translateUiString === 'function'
            ? translateUiString('请输入要增加的 Token 预算')
            : '请输入要增加的 Token 预算';
        const raw = window.prompt(promptText, '10000');
        if (raw == null) return false;
        const additional = Number(raw);
        if (!Number.isInteger(additional) || additional <= 0) {
            setGoalReviewModalStatus(
                typeof translateUiString === 'function'
                    ? translateUiString('预算必须是大于 0 的整数。')
                    : '预算必须是大于 0 的整数。',
                'error'
            );
            return false;
        }
        payload.additional_budget = additional;
    }

    setGoalReviewModalBusy(true);
    setGoalReviewModalStatus(
        typeof translateUiString === 'function' ? translateUiString('正在保存审核结果…') : '正在保存审核结果…',
        ''
    );
    const saved = await controlCurrentGoal('review', payload);
    setGoalReviewModalBusy(false);
    if (!saved) {
        setGoalReviewModalStatus(
            typeof translateUiString === 'function' ? translateUiString('审核结果保存失败。') : '审核结果保存失败。',
            'error'
        );
        return false;
    }
    if (decision === 'save') {
        elements.root._goalOriginalObjective = objective;
        elements.root._goalOriginalJudgeResult = judgeResult;
        setGoalReviewModalStatus(
            typeof translateUiString === 'function'
                ? translateUiString('修改已保存，可继续编辑或选择审核结果。')
                : '修改已保存，可继续编辑或选择审核结果。',
            'success'
        );
        return true;
    }
    closeGoalReviewModal();
    if (decision === 'continue') {
        const activeSid = String(currentSessionId || '');
        window.setTimeout(function () {
            if (activeSid === String(currentSessionId || '')) void recoverActiveGoalStream(activeSid);
        }, 150);
    }
    return true;
}

function ensureGoalReviewModalBindings() {
    const elements = goalReviewModalElements();
    if (!elements.root || elements.root._goalReviewBound) return elements;
    elements.root._goalReviewBound = true;
    if (elements.close) elements.close.addEventListener('click', function () { closeGoalReviewModal(); });
    if (elements.approve) elements.approve.addEventListener('click', function () { void submitGoalReview('approve'); });
    if (elements.save) elements.save.addEventListener('click', function () { void submitGoalReview('save'); });
    if (elements.continueGoal) elements.continueGoal.addEventListener('click', function () { void submitGoalReview('continue'); });
    elements.root.addEventListener('mousedown', function (event) {
        if (event.target === elements.root) closeGoalReviewModal();
    });
    elements.root.addEventListener('keydown', function (event) {
        if (event.key === 'Escape') {
            event.preventDefault();
            closeGoalReviewModal();
        }
    });
    return elements;
}

function openGoalReviewModal() {
    if (!renderedGoalState || String(renderedGoalState.status || '') !== 'completed') return;
    const elements = ensureGoalReviewModalBindings();
    if (!elements.root || !elements.objective || !elements.judge) return;
    const objective = String(renderedGoalState.objective || '');
    const judgeResult = String(
        renderedGoalState.review_judge_result != null
            ? renderedGoalState.review_judge_result
            : (renderedGoalState.last_judge_reason || '')
    );
    elements.root.dataset.sessionId = String(currentSessionId || '');
    elements.root.dataset.goalId = String(renderedGoalState.id || '');
    elements.root._goalOriginalObjective = objective;
    elements.root._goalOriginalJudgeResult = judgeResult;
    elements.root._goalReturnFocus = document.activeElement;
    elements.objective.value = objective;
    elements.judge.value = judgeResult;
    elements.root.classList.add('is-open');
    elements.root.setAttribute('aria-hidden', 'false');
    document.body.classList.add('goal-reviewing');
    document.body.style.overflow = 'hidden';
    setGoalReviewModalBusy(false);
    const reviewStatus = String(renderedGoalState.review_status || '');
    setGoalReviewModalStatus(
        reviewStatus === 'approved'
            ? (typeof translateUiString === 'function' ? translateUiString('该结果已审核通过。') : '该结果已审核通过。')
            : '',
        reviewStatus === 'approved' ? 'success' : ''
    );
    requestAnimationFrame(function () {
        elements.objective.focus();
        elements.objective.setSelectionRange(0, 0);
        elements.objective.scrollTop = 0;
    });
}

document.addEventListener('myagent:language-change', function () {
    renderGoalForCurrentSession();
});

if (typeof globalThis !== 'undefined') {
    globalThis.toggleCurrentGoalState = toggleCurrentGoalState;
    globalThis.editCurrentGoal = editCurrentGoal;
    globalThis.deleteCurrentGoal = deleteCurrentGoal;
    globalThis.openGoalReviewModal = openGoalReviewModal;
}

function setTodoPlanForSession(sessionId, snapshot) {
    if (!sessionId || !snapshot || typeof snapshot !== 'object') return;
    applyTodoPlanToStore(sessionId, snapshot);
}

function startTodoForSessionLoad(sessionId) {
    if (!sessionId || sessionId !== currentSessionId) return;
    void refreshTodoPlanPanel();
}

function renderLoadedTodoPlanForSession(sessionId, snapshot, alreadyStarted) {
    if (!sessionId || sessionId !== currentSessionId) return;
    if (snapshot && typeof snapshot === 'object') {
        setTodoPlanForSession(sessionId, snapshot);
        renderTodoPlanForCurrentSession();
        return;
    }
    if (alreadyStarted) {
        renderTodoPlanForCurrentSession();
        return;
    }
    void refreshTodoPlanPanel();
}

const TODO_PLAN_CACHE_TTL_MS = 2000;

async function refreshTodoPlanPanel() {
    const sid = currentSessionId;
    const epoch = ++todoRefreshEpoch;
    if (!sid) {
        clearTodoPlanState(sid);
        hideTodoPlanPanel();
        const statsEl = document.getElementById('chat-todo-plan-stats');
        const listEl = document.getElementById('chat-todo-plan-list');
        if (statsEl) statsEl.textContent = '';
        if (listEl) listEl.textContent = '';
        notifyPanelContentChanged();
        return;
    }
    const cached = selectTodoPlan(sid);
    if (cached && cached.updatedAt && (Date.now() - cached.updatedAt) < TODO_PLAN_CACHE_TTL_MS) {
        renderTodoPlanSnapshot(cached);
        return;
    }
    try {
        const r = await fetch('/sessions/' + encodeURIComponent(sid) + '/todo_plan');
        if (epoch !== todoRefreshEpoch || sid !== currentSessionId) return;
        if (!r.ok) {
            hideTodoPlanPanel();
            return;
        }
        const j = await r.json();
        if (epoch !== todoRefreshEpoch || sid !== currentSessionId) return;
        applyTodoPlanFromPayload(j);
    } catch (e) {
        if (epoch !== todoRefreshEpoch || sid !== currentSessionId) return;
        hideTodoPlanPanel();
    }
}
