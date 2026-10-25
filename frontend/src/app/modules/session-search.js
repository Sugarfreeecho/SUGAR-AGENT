/* Full-text search lives in a dialog, separate from the sidebar's local filter. */
var sessionSearchState = {
    epoch: 0, q: '', scope: 'all', tools: false, composing: false,
    requests: new Set(), timer: null, entries: new Map(), nodes: new Map(),
    order: { metadata: [], active_content: [], archived_content: [] },
    phases: {}, selected: '', root: null, opening: 0,
    storeKey: '', stale: false,
    dialog: null, host: null, previousFocus: null, previousOverflow: '', keyHandler: null,
};
var SESSION_SEARCH_PHASES = ['metadata', 'active_content', 'archived_content'];
var SESSION_SEARCH_TITLES = { metadata: '名称与目录', active_content: '会话正文', archived_content: '归档正文' };
var SESSION_SEARCH_PROGRESS = { metadata: '正在搜索会话信息', active_content: '正在搜索会话正文', archived_content: '正在搜索归档正文' };

function sessionSearchAliases() {
    try { return JSON.parse(localStorage.getItem('myagent-workdir-labels') || '{}') || {}; }
    catch (_) { return {}; }
}

function sessionSearchTerms() {
    return sessionSearchState.q.toLowerCase().split(/\s+/).filter(Boolean);
}

function sessionSearchMark(el, text, ranges) {
    text = String(text || '');
    // Server ranges are Unicode codepoint offsets, JS string offsets are UTF-16.
    var chars = Array.from(text), fragment = document.createDocumentFragment(), end = 0;
    (ranges || []).forEach(function (range) {
        var start = Math.max(end, Math.min(chars.length, Number(range[0])));
        var next = Math.max(start, Math.min(chars.length, Number(range[1])));
        fragment.appendChild(document.createTextNode(chars.slice(end, start).join('')));
        var mark = document.createElement('mark');
        mark.textContent = chars.slice(start, next).join('');
        fragment.appendChild(mark);
        end = next;
    });
    fragment.appendChild(document.createTextNode(chars.slice(end).join('')));
    el.replaceChildren(fragment);
}

function sessionSearchLocalRanges(text) {
    var chars = Array.from(String(text || '')), folded = chars.map(function (ch) { return ch.toLowerCase(); }).join('');
    var spans = [];
    sessionSearchTerms().forEach(function (term) {
        var from = 0, pos;
        while ((pos = folded.indexOf(term, from)) >= 0) {
            spans.push([Array.from(folded.slice(0, pos)).length, Array.from(folded.slice(0, pos + term.length)).length]);
            from = pos + term.length;
        }
    });
    spans.sort(function (a, b) { return a[0] - b[0]; });
    return spans.reduce(function (out, s) {
        if (out.length && s[0] <= out[out.length - 1][1]) out[out.length - 1][1] = Math.max(s[1], out[out.length - 1][1]);
        else out.push(s);
        return out;
    }, []);
}

function beginSessionSearch(value) {
    var state = sessionSearchState;
    if (!state.dialog || !state.host) return;
    clearTimeout(state.timer);
    state.requests.forEach(function (r) { r.abort(); });
    state.requests.clear();
    state.epoch++;
    state.opening++;
    state.q = String(value || '').trim();
    state.entries.clear();
    state.nodes.clear();
    state.root = null;
    state.selected = '';
    state.order = { metadata: [], active_content: [], archived_content: [] };
    state.phases = {};
    state.stale = false;
    state.storeKey = sessionSearchStoreKey();
    if (!state.q) {
        state.host.removeAttribute('aria-busy');
        var hint = document.createElement('p'); hint.className = 'session-search-empty';
        hint.textContent = '输入关键词，搜索全部会话及历史对话';
        state.host.replaceChildren(hint);
        var status = document.getElementById('session-search-status');
        if (status) status.textContent = '搜索标题、目录与全部历史对话';
        return;
    }
    SESSION_SEARCH_PHASES.forEach(function (phase) { state.phases[phase] = { status: 'waiting', cursor: null }; });
    sessionSearchSeedLocal();
    renderSessionSearchResults();
    if (!state.composing) state.timer = setTimeout(function () { void requestSessionSearch('all'); }, 250);
}

function sessionSearchSeedLocal() {
    var state = sessionSearchState, terms = sessionSearchTerms(), aliases = sessionSearchAliases();
    var all = selectAllSessions().concat(typeof selectArchivedSessions === 'function' ? selectArchivedSessions() : []);
    var seen = new Set(), matches = [];
    all.forEach(function (s) {
        if (!s || seen.has(s.id) || s.draft) return;
        seen.add(s.id);
        if (state.scope !== 'all' && !!s.archived !== (state.scope === 'archived')) return;
        var key = s.work_dir_is_default || !sessionWorkDirIdentity(s) ? SESSION_WORKDIR_DEFAULT_GROUP_KEY : 'workdir:' + sessionWorkDirIdentity(s);
        var fields = [['title', s.name || ''], ['id', s.id], ['directory', [s.work_dir, s.work_dir_label, aliases[key]].filter(Boolean).join(' ')], ['preview', s.last_user_preview || '']];
        var hay = fields.map(function (v) { return v[1]; }).join(' ').toLowerCase();
        if (!terms.every(function (t) { return hay.includes(t); })) return;
        var field = fields.find(function (f) { return terms.some(function (t) { return String(f[1]).toLowerCase().includes(t); }); });
        var title = String(s.name || '').toLowerCase(), q = terms.join(' ');
        var rank = title === q ? 0 : title.startsWith(q) ? 1 : terms.every(function (t) { return title.includes(t); }) ? 2 : field[0] !== 'preview' ? 3 : 4;
        var labels = { title: '标题', id: '会话 ID', directory: '目录', preview: '最近提问' };
        matches.push({ rank: rank, session: s, hit: { source: field[0], label: labels[field[0]], snippet: field[1], highlights: sessionSearchLocalRanges(field[1]) } });
    });
    matches.sort(function (a, b) { return a.rank - b.rank || sessionActivityTimeMs(b.session) - sessionActivityTimeMs(a.session); });
    matches.slice(0, 20).forEach(function (m) {
        state.order.metadata.push(m.session.id);
        state.entries.set(m.session.id, { session: m.session, phase: 'metadata', hits: [m.hit], provisional: true, expanded: false });
    });
}

function sessionSearchStoreKey() {
    return JSON.stringify(selectAllSessions().map(function (s) {
        return [s.id, s.name, s.archived, s.work_dir, s.last_activity_at, s.updated_at, s.last_user_preview];
    }));
}

function observeSessionSearchStore() {
    var state = sessionSearchState, next = sessionSearchStoreKey();
    if (next !== state.storeKey) {
        state.storeKey = next; state.stale = true;
        state.entries.forEach(function (entry, id) {
            if (typeof sessionStore !== 'undefined' && sessionStore.isDeletedSessionTombstoned(id)) state.entries.delete(id);
            else if (typeof sessionStore !== 'undefined' && sessionStore.get(id)) entry.session = sessionStore.get(id);
        });
    }
}

async function consumeSessionSearchStream(response, onEvent, signal) {
    var reader = response.body.getReader(), decoder = new TextDecoder(), pending = '';
    try {
        while (!signal.aborted) {
            var chunk = await reader.read();
            pending += decoder.decode(chunk.value || new Uint8Array(), { stream: !chunk.done });
            pending = pending.replace(/\r\n/g, '\n');
            var end;
            while ((end = pending.indexOf('\n\n')) >= 0) {
                var frame = pending.slice(0, end); pending = pending.slice(end + 2);
                var name = 'message', data = [];
                frame.split('\n').forEach(function (line) {
                    if (line.startsWith('event:')) name = line.slice(6).trim();
                    if (line.startsWith('data:')) data.push(line.slice(5).trimStart());
                });
                if (data.length) onEvent(name, JSON.parse(data.join('\n')));
            }
            if (chunk.done) break;
        }
    } finally {
        if (signal.aborted) await reader.cancel().catch(function () {});
        reader.releaseLock();
    }
}

async function requestSessionSearch(phase, cursor, sessionId) {
    var state = sessionSearchState, epoch = state.epoch, controller = new AbortController();
    var targets = phase === 'all' ? SESSION_SEARCH_PHASES : [phase];
    var finished = new Set();
    state.requests.add(controller);
    targets.forEach(function (p) {
        if (!sessionId) state.phases[p] = Object.assign({}, state.phases[p], { status: 'loading', error: '' });
    });
    renderSessionSearchResults();
    try {
        var response = await fetch('/sessions/search', {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, signal: controller.signal,
            body: JSON.stringify({ q: state.q, phase: phase, scope: state.scope, include_tools: state.tools,
                workdir_aliases: sessionSearchAliases(), cursor: cursor || null, session_id: sessionId || null }),
        });
        if (!response.ok) {
            var error = await response.json().catch(function () { return {}; });
            var failure = new Error(error.error || '检索失败，请重试'); failure.status = response.status; throw failure;
        }
        await consumeSessionSearchStream(response, function (name, data) {
            if (controller.signal.aborted || epoch !== state.epoch || !state.q) return;
            if (name === 'upsert') {
                var sid = data.session.id, entry = state.entries.get(sid);
                if (typeof sessionStore !== 'undefined' && sessionStore.isDeletedSessionTombstoned(sid)) return;
                if (!entry) {
                    entry = { session: data.session, phase: data.phase, hits: [], expanded: false };
                    state.entries.set(sid, entry);
                    state.order[data.phase].push(sid);
                }
                if (entry.provisional) {
                    entry.provisional = false;
                    entry.hits = [];
                }
                entry.session = data.session;
                data.hits.forEach(function (hit) {
                    var key = hit.ref || hit.source + ':' + hit.snippet;
                    var index = entry.hits.findIndex(function (h) { return (h.ref || h.source + ':' + h.snippet) === key; });
                    if (index < 0) entry.hits.push(hit);
                    else entry.hits[index] = hit;
                });
                if (data.phase !== 'metadata') {
                    entry.hitCursor = data.hit_cursor;
                    entry.contentPhase = data.phase;
                }
            } else if (name === 'progress' && !sessionId) {
                state.phases[data.phase] = Object.assign({}, state.phases[data.phase], data, { status: 'loading' });
            } else if (name === 'phase_done') {
                finished.add(data.phase);
                if (!sessionId) {
                    state.phases[data.phase] = Object.assign({}, data, { status: 'done' });
                    if (data.phase === 'metadata') {
                        state.entries.forEach(function (e, id) { if (e.provisional) { state.entries.delete(id); } });
                        state.order.metadata = state.order.metadata.filter(function (id) { return state.entries.has(id); });
                    }
                }
            } else if (name === 'error') {
                finished.add(data.phase);
                if (sessionId) {
                    var hitEntry = state.entries.get(sessionId);
                    if (hitEntry) { hitEntry.hitError = data.message; hitEntry.hitReset = data.status === 409; }
                } else state.phases[data.phase] = { status: 'error', error: data.message, cursor: cursor || null, reset: data.status === 409 };
            }
            renderSessionSearchResults();
        }, controller.signal);
        if (!controller.signal.aborted && epoch === state.epoch && targets.some(function (p) { return !finished.has(p); })) {
            throw new Error('连接已中断，请重试未完成的阶段');
        }
    } catch (error) {
        if (!controller.signal.aborted && epoch === state.epoch) {
            if (sessionId) {
                var entry = state.entries.get(sessionId);
                if (entry) { entry.hitError = error.message; entry.hitReset = error.status === 409; }
            } else targets.forEach(function (p) {
                if (!finished.has(p)) state.phases[p] = { status: 'error', error: error.message, cursor: cursor || null, reset: error.status === 409 };
            });
        }
    } finally {
        state.requests.delete(controller);
        if (epoch === state.epoch) {
            var target = state.entries.get(sessionId);
            if (target) target.hitLoading = false;
            renderSessionSearchResults();
        }
    }
}

function sessionSearchButton(label, action, className) {
    var button = document.createElement('button');
    button.type = 'button'; button.className = className || 'session-search-more';
    button.textContent = label; button.addEventListener('click', action);
    return button;
}

function sessionSearchBuildRow(id, entry) {
    var state = sessionSearchState, row = state.nodes.get(id);
    if (!row) {
        row = document.createElement('div'); row.className = 'session-search-result';
        row.dataset.searchSessionId = id; row.setAttribute('role', 'option');
        row.id = 'session-search-result-' + id;
        state.nodes.set(id, row);
    }
    var signature = JSON.stringify([entry.session, entry.hits, entry.expanded, entry.hitCursor, entry.hitLoading, entry.hitError, entry.hitReset]);
    row.classList.toggle('is-selected', state.selected === id);
    row.setAttribute('aria-selected', state.selected === id ? 'true' : 'false');
    if (row._searchSignature === signature) return row;
    row._searchSignature = signature;
    var focusWasInside = row.contains(document.activeElement), fragment = document.createDocumentFragment();
    var open = sessionSearchButton('', function () { void openSessionSearchHit(id); }, 'session-search-open');
    var heading = document.createElement('span'); heading.className = 'session-search-heading';
    var title = document.createElement('span'); title.className = 'session-search-title';
    title.setAttribute('data-i18n-skip', '');
    var name = entry.session.name || '未命名会话';
    title.title = name;
    sessionSearchMark(title, name, sessionSearchLocalRanges(name)); heading.appendChild(title);
    if (entry.session.archived) {
        var badge = document.createElement('span'); badge.className = 'session-search-badge'; badge.textContent = '已归档'; heading.appendChild(badge);
    }
    var date = document.createElement('time'); date.className = 'session-search-date';
    var rawDate = entry.session.last_activity_at || entry.session.updated_at || entry.session.created_at;
    if (rawDate) {
        date.dateTime = rawDate; date.title = rawDate;
        date.textContent = typeof formatSessionListRelativeTime === 'function' ? formatSessionListRelativeTime(entry.session) : String(rawDate).slice(5, 10);
    }
    heading.appendChild(date); open.appendChild(heading);
    var best = entry.hits.find(function (h) { return h.ref; }) || entry.hits[0];
    if (best) {
        var snippet = document.createElement('span'); snippet.className = 'session-search-snippet';
        var label = document.createElement('span'); label.className = 'session-search-source'; label.textContent = best.label + ' · ';
        var text = document.createElement('span'); text.setAttribute('data-i18n-skip', ''); sessionSearchMark(text, best.snippet, best.highlights);
        snippet.append(label, text); open.appendChild(snippet);
    }
    fragment.appendChild(open);
    var bodyHits = entry.hits.filter(function (h) { return h.ref; });
    if (bodyHits.length) {
        var expand = sessionSearchButton(entry.expanded ? '收起命中' : '展开命中', function () {
            entry.expanded = !entry.expanded; renderSessionSearchResults();
        }, 'session-search-expand');
        expand.setAttribute('aria-expanded', String(!!entry.expanded)); fragment.appendChild(expand);
        if (entry.expanded) {
            var details = document.createElement('div'); details.className = 'session-search-hits';
            bodyHits.forEach(function (hit) {
                var button = sessionSearchButton('', function () { void openSessionSearchHit(id, hit); }, 'session-search-hit');
                var label = document.createElement('span'); label.className = 'session-search-source'; label.textContent = hit.label + ' · ';
                var text = document.createElement('span'); text.setAttribute('data-i18n-skip', ''); sessionSearchMark(text, hit.snippet, hit.highlights);
                button.append(label, text); details.appendChild(button);
            });
            if (entry.hitError) { var error = document.createElement('p'); error.textContent = entry.hitError; details.appendChild(error); }
            if (entry.hitReset) details.appendChild(sessionSearchButton('重新搜索', function () { beginSessionSearch(state.q); }));
            if (entry.hitCursor && !entry.hitReset) {
                var more = sessionSearchButton(entry.hitLoading ? '正在加载…' : '更多命中', function () {
                    entry.hitLoading = true; entry.hitError = ''; void requestSessionSearch(entry.contentPhase, entry.hitCursor, id);
                });
                more.disabled = !!entry.hitLoading; details.appendChild(more);
            }
            fragment.appendChild(details);
        }
    }
    row.replaceChildren(fragment);
    if (focusWasInside) open.focus({ preventScroll: true });
    return row;
}

function renderSessionSearchResults() {
    var state = sessionSearchState;
    if (!state.q || !state.dialog || !state.host) return;
    if (!state.root || state.root.parentNode !== state.host) {
        state.root = document.createElement('div'); state.root.className = 'session-search-results';
        SESSION_SEARCH_PHASES.forEach(function (phase) {
            var section = document.createElement('section'); section.dataset.searchPhase = phase;
            var heading = document.createElement('h3'); heading.textContent = SESSION_SEARCH_TITLES[phase];
            var body = document.createElement('div'); body.className = 'session-search-phase-body';
            var footer = document.createElement('div'); footer.className = 'session-search-phase-footer';
            section.append(heading, body, footer); state.root.appendChild(section);
        });
        state.host.replaceChildren(state.root);
    }
    var visibleIds = new Set();
    SESSION_SEARCH_PHASES.forEach(function (phase) {
        var section = state.root.querySelector('[data-search-phase="' + phase + '"]');
        var body = section.querySelector('.session-search-phase-body');
        var ids = state.order[phase].filter(function (id) { return state.entries.has(id); });
        ids.forEach(function (id, index) {
            visibleIds.add(id);
            var row = sessionSearchBuildRow(id, state.entries.get(id));
            if (body.children[index] !== row) body.insertBefore(row, body.children[index] || null);
        });
        Array.from(body.children).forEach(function (row) { if (!ids.includes(row.dataset.searchSessionId)) row.remove(); });
        var status = state.phases[phase] || { status: 'waiting' };
        section.hidden = !ids.length && status.status !== 'error';
        var footer = section.querySelector('.session-search-phase-footer');
        var signature = JSON.stringify(status);
        if (footer._searchSignature !== signature) {
            footer._searchSignature = signature; footer.replaceChildren();
            if (status.status === 'error') {
                var error = document.createElement('span'); error.textContent = status.error; footer.appendChild(error);
                footer.appendChild(sessionSearchButton(status.reset ? '重新搜索' : '重试', function () {
                    if (status.reset) beginSessionSearch(state.q);
                    else void requestSessionSearch(phase, status.cursor);
                }));
            } else if (status.cursor) {
                var more = sessionSearchButton(status.status === 'loading' ? '正在加载…' : '显示更多', function () { void requestSessionSearch(phase, status.cursor); });
                more.disabled = status.status === 'loading'; footer.appendChild(more);
            }
        }
    });
    state.nodes.forEach(function (row, id) { if (!visibleIds.has(id)) { row.remove(); state.nodes.delete(id); } });
    var statuses = SESSION_SEARCH_PHASES.map(function (p) { return state.phases[p] || {}; });
    var loading = SESSION_SEARCH_PHASES.find(function (p) { return (state.phases[p] || {}).status === 'loading'; });
    var complete = statuses.every(function (p) { return p.status === 'done'; });
    var failed = statuses.some(function (p) { return p.status === 'error'; });
    var hasMore = statuses.some(function (p) { return p.cursor; });
    var statusEl = document.getElementById('session-search-status');
    var statusText = '已发现 ' + state.entries.size + ' 个会话';
    if (loading) {
        var progress = state.phases[loading];
        statusText += ' · ' + SESSION_SEARCH_PROGRESS[loading];
        if (progress.total) statusText += '（' + (progress.scanned || 0) + '/' + progress.total + '）';
    } else if (failed) statusText += ' · 部分阶段失败';
    else if (hasMore) statusText += ' · 还有更多结果';
    else if (complete) statusText += ' · 检索完成';
    else statusText += ' · 等待检索';
    if (statusEl) statusEl.textContent = statusText;
    if (statusEl && state.stale) statusEl.appendChild(sessionSearchButton('有新内容，重新搜索', function () { beginSessionSearch(state.q); }));
    state.host.setAttribute('aria-busy', loading ? 'true' : 'false');
    var empty = state.root.querySelector('.session-search-empty');
    if (complete && !state.entries.size) {
        if (!empty) { empty = document.createElement('p'); empty.className = 'session-search-empty'; state.root.appendChild(empty); }
        empty.textContent = '没有匹配的会话，试试其他关键词';
    } else if (empty) empty.remove();
    var input = document.getElementById('session-advanced-search-input');
    if (input) {
        if (state.selected && state.entries.has(state.selected)) input.setAttribute('aria-activedescendant', 'session-search-result-' + state.selected);
        else input.removeAttribute('aria-activedescendant');
    }
}

async function openSessionSearchHit(sid, hit) {
    var state = sessionSearchState, entry = state.entries.get(sid);
    if (!entry) return;
    hit = hit || entry.hits.find(function (h) { return h.ref; });
    var token = ++state.opening, epoch = state.epoch;
    try {
        var target = null;
        if (hit && hit.ref) {
            var response = await fetch('/sessions/' + encodeURIComponent(sid) + '/search-hit?ref=' + encodeURIComponent(hit.ref)
                + '&source_version=' + encodeURIComponent(hit.source_version) + '&offset=' + encodeURIComponent(hit.match_offset || 0));
            target = await response.json();
            if (!response.ok) throw new Error(target.error || '无法定位命中内容');
        }
        if (token !== state.opening || epoch !== state.epoch) return;
        closeAdvancedSessionSearch({ keepOpening: true });
        await switchSession(sid);
        if (token !== state.opening || currentSessionId !== sid) return;
        if (!target) return;
        if (target.archive) {
            await showUiAlert({ title: '压缩历史原文', subtitle: hit.label,
                message: (target.content_offset ? '…\n' : '') + target.content + (target.has_more ? '\n…\n（此处展示命中附近的 50,000 字符）' : '') });
            return;
        }
        // The turn loader preserves the live stream owner for running sessions.
        if (target.turn_index !== null) await scrollToUserTurnOrLoadOlder(target.turn_index, { silent: true, maxOlderLoads: 120 });
        else await loadHistoryWindowAroundEventIndex(sid, target.ui_index, { turns: 5 });
        if (token !== state.opening || currentSessionId !== sid) return;
        var stream = getVisibleChatStream();
        var node = stream && (target.execution_id ? stream.querySelector('[data-execution-id="' + CSS.escape(target.execution_id) + '"]') : null);
        node = node || (stream && stream.querySelector('[data-event-index="' + Number(target.ui_index) + '"]'));
        if (node) {
            node.scrollIntoView({ block: 'center', behavior: 'smooth' }); node.classList.add('session-search-target');
            setTimeout(function () { node.classList.remove('session-search-target'); }, 2000);
        } else {
            await showUiAlert({ title: '命中原文', message: target.content });
        }
    } catch (error) {
        if (token === state.opening) {
            await showUiAlert({ title: '无法定位搜索结果', message: error.message });
            if (state.dialog) {
                document.body.style.overflow = 'hidden';
                document.getElementById('session-advanced-search-input').focus();
            }
        }
    }
}

function closeAdvancedSessionSearch(options) {
    var state = sessionSearchState;
    if (!state.dialog) return;
    clearTimeout(state.timer);
    state.requests.forEach(function (request) { request.abort(); }); state.requests.clear();
    state.epoch++;
    if (!(options && options.keepOpening)) state.opening++;
    state.composing = false; state.q = '';
    document.removeEventListener('keydown', state.keyHandler);
    state.dialog.remove(); state.dialog = null; state.host = null; state.root = null;
    state.entries.clear(); state.nodes.clear();
    document.body.style.overflow = state.previousOverflow;
    if (state.previousFocus && state.previousFocus.isConnected) state.previousFocus.focus({ preventScroll: true });
}

function handleAdvancedSessionSearchKeydown(event) {
    var state = sessionSearchState;
    if (event.isComposing || state.composing || event.keyCode === 229) return;
    if (event.key === 'Escape') {
        event.preventDefault(); event.stopPropagation(); closeAdvancedSessionSearch();
    } else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        var ids = SESSION_SEARCH_PHASES.flatMap(function (p) { return state.order[p].filter(function (id) { return state.entries.has(id); }); });
        if (!ids.length) return;
        event.preventDefault();
        var index = ids.indexOf(state.selected);
        index = index < 0 ? (event.key === 'ArrowDown' ? 0 : ids.length - 1) : (index + (event.key === 'ArrowDown' ? 1 : -1) + ids.length) % ids.length;
        state.selected = ids[index]; renderSessionSearchResults();
        state.nodes.get(ids[index]).scrollIntoView({ block: 'nearest' });
    } else if (event.key === 'Enter' && state.q) {
        event.preventDefault();
        var first = Array.from(state.entries.keys())[0];
        void openSessionSearchHit(state.selected || first);
    }
}

function openAdvancedSessionSearch(query, trigger) {
    var state = sessionSearchState;
    if (state.dialog) { document.getElementById('session-advanced-search-input').focus(); return; }
    if (typeof sessionGroupManager !== 'undefined' && sessionGroupManager) {
        if (sessionGroupManager.busy) return;
        closeSessionGroupManager();
    }
    state.previousFocus = trigger || document.activeElement;
    state.previousOverflow = document.body.style.overflow;
    var root = document.createElement('div'); root.className = 'session-manager-overlay session-advanced-search-overlay';
    root.innerHTML = '<section class="session-manager-dialog session-advanced-search-dialog" role="dialog" tabindex="-1" aria-modal="true" aria-labelledby="session-advanced-search-title">'
        + '<header><div><h2 id="session-advanced-search-title">高级搜索</h2><p class="session-manager-group">搜索会话名称、目录与全部历史对话</p></div>'
        + '<button type="button" class="session-dialog-close" data-advanced-close aria-label="关闭高级搜索" title="关闭"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"></path></svg></button></header>'
        + '<div class="session-advanced-input-row"><input id="session-advanced-search-input" class="session-manager-filter" type="search" placeholder="输入关键词搜索全部历史" aria-label="高级搜索关键词" aria-controls="session-advanced-results" autocomplete="off" spellcheck="false" maxlength="120">'
        + '<button type="button" data-advanced-clear>清空</button></div>'
        + '<div class="session-search-options"><label>范围 <select id="session-search-scope" aria-label="搜索范围"><option value="all">全部会话</option><option value="active">未归档</option><option value="archived">已归档</option></select></label>'
        + '<label class="session-search-tools"><input id="session-search-tools" type="checkbox">包含工具执行内容</label></div>'
        + '<p id="session-search-status" class="session-manager-status" role="status" aria-live="polite"></p>'
        + '<div id="session-advanced-results" class="session-advanced-results" role="listbox" aria-label="高级搜索结果"></div>'
        + '<footer class="session-advanced-search-hint">↑↓ 选择 · Enter 打开 · Esc 关闭</footer></section>';
    state.dialog = root; state.host = root.querySelector('#session-advanced-results');
    var input = root.querySelector('#session-advanced-search-input'), scope = root.querySelector('#session-search-scope');
    var tools = root.querySelector('#session-search-tools');
    scope.value = state.scope; tools.checked = state.tools;
    input.value = String(query || '');
    root.querySelector('[data-advanced-close]').addEventListener('click', function () { closeAdvancedSessionSearch(); });
    root.querySelector('[data-advanced-clear]').addEventListener('click', function () { input.value = ''; beginSessionSearch(''); input.focus(); });
    input.addEventListener('compositionstart', function () {
        state.composing = true; clearTimeout(state.timer);
        state.requests.forEach(function (request) { request.abort(); });
    });
    input.addEventListener('compositionend', function () { state.composing = false; beginSessionSearch(input.value); });
    input.addEventListener('input', function (event) { if (!event.isComposing && !state.composing) beginSessionSearch(input.value); });
    input.addEventListener('keydown', handleAdvancedSessionSearchKeydown);
    scope.addEventListener('change', function () { state.scope = scope.value; if (input.value.trim()) beginSessionSearch(input.value); });
    tools.addEventListener('change', function () { state.tools = tools.checked; if (input.value.trim()) beginSessionSearch(input.value); });
    root.addEventListener('click', function (event) { if (event.target === root) closeAdvancedSessionSearch(); });
    state.keyHandler = function (event) {
        var alertRoot = document.getElementById('ui-modal-root');
        if (alertRoot && alertRoot.classList.contains('is-open')) return;
        if (event.isComposing || state.composing || event.keyCode === 229) return;
        if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); closeAdvancedSessionSearch(); return; }
        if (event.key === 'Tab') {
            var items = Array.from(root.querySelectorAll('button:not(:disabled), input:not(:disabled), select:not(:disabled)'));
            var first = items[0], last = items[items.length - 1];
            if (!root.contains(document.activeElement)) { event.preventDefault(); (event.shiftKey ? last : first).focus(); }
            else if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
            else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
        }
    };
    document.addEventListener('keydown', state.keyHandler);
    document.body.appendChild(root); document.body.style.overflow = 'hidden';
    beginSessionSearch(input.value); input.focus(); input.select();
}

function initSessionSearchControls(head) {
    var input = document.getElementById('session-search-input'), button = document.getElementById('session-search-btn');
    var clear = document.getElementById('session-search-clear'), advanced = document.getElementById('session-advanced-search-btn');
    if (!input || !button) return;
    function collapseSearch() {
        applySessionListSearch(''); setSessionSearchExpanded(false); button.focus();
    }
    button.addEventListener('click', function () { setSessionSearchExpanded(!head.classList.contains('is-searching'), { selectInput: true }); });
    input.addEventListener('input', function () { applySessionListSearch(input.value); });
    input.addEventListener('keydown', function (event) {
        if (event.key !== 'Escape' || event.isComposing || event.keyCode === 229) return;
        event.preventDefault(); event.stopPropagation(); collapseSearch();
    });
    clear.addEventListener('click', collapseSearch);
    if (advanced) {
        if (typeof bindUiHoverTip === 'function') bindUiHoverTip(advanced);
        advanced.addEventListener('click', function () { openAdvancedSessionSearch(input.value, advanced); });
    }
    if (typeof bindUiHoverTip === 'function') bindUiHoverTip(clear);
    document.addEventListener('keydown', function (event) {
        if ((event.ctrlKey || event.metaKey) && !event.altKey && !event.shiftKey && event.key.toLowerCase() === 'k') {
            var alertRoot = document.getElementById('ui-modal-root');
            if (alertRoot && alertRoot.classList.contains('is-open')) return;
            if (typeof sessionGroupManager !== 'undefined' && sessionGroupManager) return;
            event.preventDefault();
            if (sessionSearchState.dialog) document.getElementById('session-advanced-search-input').focus();
            else setSessionSearchExpanded(true, { selectInput: true });
        }
    });
    document.addEventListener('pointerdown', function (event) {
        if (sessionSearchState.dialog || !head.classList.contains('is-searching') || head.contains(event.target)) return;
        if (getSessionListSearchQuery()) { if (document.activeElement === input) input.blur(); }
        else setSessionSearchExpanded(false);
    }, true);
}
