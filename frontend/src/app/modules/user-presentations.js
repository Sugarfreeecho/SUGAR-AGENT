// show_user presents content immediately; ask_user owns the separate answer flow.
var showUserRecords = new Map();
var showUserPending = new Map();
var showUserSeen = new Set();
var showUserRegistered = false;
var showUserNoticeClose = null;
var SHOW_USER_ADDRESS = 'myagent-user://presentation/';
try { JSON.parse(sessionStorage.getItem('myagent-show-user-seen') || '[]').slice(-256).forEach(function (key) { showUserSeen.add(key); }); } catch (_) { /* optional cache */ }

function showUserText(zh, en) { return document.documentElement.lang.startsWith('en') ? en : zh; }
function showUserKey(record) { return JSON.stringify([record.session_id, record.presentation_id]); }

function rememberShowUser(key) {
    var seen = showUserSeen.has(key);
    showUserSeen.add(key);
    while (showUserSeen.size > 256) showUserSeen.delete(showUserSeen.values().next().value);
    try { sessionStorage.setItem('myagent-show-user-seen', JSON.stringify(Array.from(showUserSeen))); } catch (_) { /* optional cache */ }
    return seen;
}

function showUserElement(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = String(text);
    return node;
}

function showUserStatus(record, text) {
    document.querySelectorAll('.show-user-card').forEach(function (card) {
        if (card.dataset.presentationKey === showUserKey(record)) card.querySelector('.show-user-status').textContent = text;
    });
}

function showUserNotificationStatus(record) {
    return ({
        requested: showUserText('已向系统请求通知。', 'System notification requested.'),
        unavailable: showUserText('桌面通知未启用，内容已保存在此处。', 'Desktop notifications are unavailable; the content is saved here.'),
        failed: showUserText('系统通知请求失败，内容已保存在此处。', 'System notification request failed; the content is saved here.'),
        unknown: showUserText('系统通知状态未知，为避免重复提醒未自动重发。', 'Notification status is unknown; it will not be resent automatically.')
    })[record.notification_status] || showUserText('系统通知结果尚未记录，请以工具结果为准。', 'Notification result not recorded yet; check the tool result.');
}

function showUserTopNotice(record) {
    if (showUserNoticeClose) showUserNoticeClose();
    var banner = showUserElement('section', 'show-user-notice');
    banner.dataset.level = ['info', 'success', 'warning', 'error'].includes(record.level) ? record.level : 'info';
    banner.setAttribute('role', banner.dataset.level === 'error' ? 'alert' : 'status');
    banner.setAttribute('aria-atomic', 'true');
    var copy = showUserElement('div', 'show-user-notice-copy');
    copy.append(showUserElement('strong', 'show-user-title', record.title), showUserElement('p', 'show-user-notice-text', record.text));
    var close = showUserElement('button', 'show-user-notice-close', '×');
    close.type = 'button'; close.setAttribute('aria-label', showUserText('关闭提示', 'Dismiss notice'));
    banner.append(copy, close);
    var remaining = Number.isInteger(record.duration_ms) ? record.duration_ms : 8000;
    var timer = null, started = 0;
    function pause() {
        if (timer === null) return;
        clearTimeout(timer); timer = null;
        remaining = Math.max(1, remaining - (Date.now() - started));
    }
    function resume() {
        if (!remaining || timer !== null || document.hidden || banner.matches(':hover') || banner.contains(document.activeElement)) return;
        started = Date.now(); timer = setTimeout(dismiss, remaining);
    }
    function visibility() { if (document.hidden) pause(); else resume(); }
    function dismiss() {
        clearTimeout(timer);
        document.removeEventListener('visibilitychange', visibility);
        banner.remove();
        if (showUserNoticeClose === dismiss) showUserNoticeClose = null;
    }
    showUserNoticeClose = dismiss;
    close.addEventListener('click', dismiss);
    banner.addEventListener('mouseenter', pause); banner.addEventListener('mouseleave', resume);
    banner.addEventListener('focusin', pause); banner.addEventListener('focusout', function () { setTimeout(resume, 0); });
    document.addEventListener('visibilitychange', visibility);
    document.body.appendChild(banner);
    resume();
}

function openShowUserPresentation(record, automatic) {
    var api = globalThis.MyAgentDock;
    // Native notifications are dispatched once by the server, independently of
    // this browser. History, rendering and reopening can never resend one.
    if (record.kind === 'notification') { showUserStatus(record, showUserNotificationStatus(record)); return true; }
    var current = typeof currentSessionId === 'string' ? currentSessionId : '';
    var surface = function (id) { return api?.surfaceKey?.(id) || id; };
    if (!current || surface(record.session_id) !== surface(current)) {
        showUserStatus(record, showUserText('请在来源会话中查看。', 'Open this from its source chat.'));
        return false;
    }
    showUserRecords.set(showUserKey(record), record);
    if (record.kind === 'notice') {
        showUserTopNotice(record);
        showUserStatus(record, showUserText('已显示顶部提示。', 'Top notice shown.'));
        return true;
    }
    if (record.kind === 'settings') {
        var accepted = typeof openSettingsCenter === 'function' && openSettingsCenter(record.section, { preserveUnsaved: true }) !== false;
        showUserStatus(record, accepted ? showUserText('已请求打开设置页签。', 'Settings tab requested.') : showUserText('设置暂不可用，请重试。', 'Settings unavailable. Please retry.'));
        return accepted;
    }
    if (!api || !showUserRegistered) {
        showUserPending.set(showUserKey(record), record);
        showUserStatus(record, showUserText('等待详情栏就绪…', 'Waiting for the details sidebar…'));
        return false;
    }
    var opened = false;
    try {
        if (record.kind === 'webpage') opened = api.openBrowser(record.url, { presentationId: record.presentation_id, title: record.title });
        else if (record.kind === 'plugin') {
            opened = record.plugin_id
                ? api.openPluginPage(record.plugin_id, { pageId: record.page_id, sessionId: record.session_id })
                : (api.openDetailsTab('plugins'), true);
        } else if (record.kind === 'file') {
            api.openDetailsFile(record.path);
            opened = true;
        } else {
            opened = api.openPresentation({ contentId: SHOW_USER_ADDRESS + encodeURIComponent(showUserKey(record)), title: record.title });
        }
    } catch (error) { console.warn('show_user details open failed', error); }
    if (!opened && automatic && record.kind === 'plugin') showUserPending.set(showUserKey(record), record);
    showUserStatus(record, opened
        ? showUserText('已打开详情栏。', 'Details sidebar opened.')
        : showUserText('暂时无法打开，请重试；目标页面或插件可能不可用。', 'Unable to open. Retry; the page or plugin may be unavailable.'));
    return !!opened;
}

function renderShowUserEvent(ctx, event, sessionId, options) {
    var value = event && event.presentation;
    if (!value || !/^[a-f0-9]{32}$/.test(value.presentation_id || '')
        || !['text', 'image', 'webpage', 'plugin', 'file', 'notice', 'settings', 'notification'].includes(value.kind)) return;
    // The history route owns the current identity when a branch copied a display.
    var origin = event._subagent_forward ? value.session_id : (sessionId || value.session_id);
    var record = Object.assign({}, value, { session_id: String(origin || '') });
    if (!record.session_id || typeof record.title !== 'string') return;
    var key = showUserKey(record);
    showUserRecords.set(key, record);
    var seen = rememberShowUser(key);
    var stream = ctx && ctx.stream;
    if (stream) {
        var card = Array.from(stream.querySelectorAll('.show-user-card')).find(function (node) { return node.dataset.presentationKey === key; });
        if (!card) {
            var slot = typeof humanInteractionToolSlot === 'function' ? humanInteractionToolSlot(stream, event.tool_call_id, event) : null;
            if (!slot && typeof appendToolPendingRow === 'function' && event.tool_call_id) {
                appendToolPendingRow(ctx, Object.assign({}, event, { type: 'tool_pending', tool: 'show_user',
                    args: { kind: record.kind, title: record.title }, command_preview: 'show_user', ephemeral: true }), sessionId);
                slot = typeof humanInteractionToolSlot === 'function' ? humanInteractionToolSlot(stream, event.tool_call_id, event) : null;
            }
            if (!slot && typeof appendLog === 'function') slot = appendLog(ctx, '', 'status', sessionId, event.react_iter);
            if (slot) {
                card = showUserElement('div', 'show-user-card');
                card.dataset.presentationKey = key;
                var copy = showUserElement('div', 'show-user-copy');
                copy.appendChild(showUserElement('strong', 'show-user-title', record.title));
                if (record.kind === 'notice' || record.kind === 'notification') copy.appendChild(showUserElement('p', 'show-user-card-text', record.text));
                var status = showUserElement('span', 'show-user-status', record.kind === 'notification' ? showUserNotificationStatus(record)
                    : record.kind === 'notice' ? showUserText('可重新显示顶部提示。', 'Top notice available.')
                    : record.kind === 'settings' ? showUserText('设置页签：', 'Settings tab: ') + record.section
                    : showUserText('可在详情栏查看。', 'Available in the details sidebar.'));
                status.setAttribute('role', 'status');
                copy.appendChild(status);
                card.appendChild(copy);
                if (record.kind !== 'notification') {
                    var label = record.kind === 'notice' ? showUserText('显示顶部提示', 'Show top notice')
                        : record.kind === 'settings' ? showUserText('打开设置', 'Open settings') : showUserText('在详情栏查看', 'View in details');
                    var open = showUserElement('button', 'human-secondary-btn show-user-open', label);
                    open.type = 'button';
                    open.addEventListener('click', function () { openShowUserPresentation(showUserRecords.get(key), false); });
                    card.appendChild(open);
                }
                slot.appendChild(card);
            }
        }
        // Notification request and receipt are two durable facts with the same
        // identity. Update the existing card when the receipt arrives.
        if (card && record.kind === 'notification') card.querySelector('.show-user-status').textContent = showUserNotificationStatus(record);
    }
    if (!seen && options && options.source === 'sse' && !event.replayed_recent && !event.replayed_snapshot
        && typeof currentSessionId === 'string' && record.session_id === currentSessionId) {
        openShowUserPresentation(record, true);
    }
}

// Build Markdown from tokens with DOM text nodes. Raw HTML never enters innerHTML,
// and Markdown images do not cause network requests. Use kind=image for pictures.
function renderShowUserMarkdown(host, text) {
    var parser = globalThis.marked;
    if (!parser || typeof parser.lexer !== 'function') { host.appendChild(showUserElement('pre', 'show-user-plain', text)); return; }
    var remaining = 5000, truncated = false;
    function render(parent, tokens, inline, depth) {
        (tokens || []).forEach(function (token) {
            if (--remaining < 0 || depth > 12) { truncated = true; return; }
            var type = token.type, node;
            if (type === 'space') return;
            if (type === 'list') {
                node = document.createElement(token.ordered ? 'ol' : 'ul');
                if (token.ordered && Number(token.start) > 0) node.start = Number(token.start);
                (token.items || []).forEach(function (item) { var li = document.createElement('li'); render(li, item.tokens, false, depth + 1); node.appendChild(li); });
            } else if (type === 'table') {
                node = document.createElement('table');
                var head = document.createElement('tr');
                (token.header || []).forEach(function (cell) { var th = document.createElement('th'); render(th, cell.tokens, true, depth + 1); head.appendChild(th); });
                var thead = document.createElement('thead'); thead.appendChild(head); node.appendChild(thead);
                var tbody = document.createElement('tbody');
                (token.rows || []).forEach(function (row) { var tr = document.createElement('tr'); row.forEach(function (cell) { var td = document.createElement('td'); render(td, cell.tokens, true, depth + 1); tr.appendChild(td); }); tbody.appendChild(tr); });
                node.appendChild(tbody);
            } else if (type === 'link') {
                node = document.createElement('span');
                try { var url = new URL(token.href); if (['http:', 'https:'].includes(url.protocol) && !url.username && !url.password) {
                    node = document.createElement('a'); node.href = url.href; node.target = '_blank'; node.rel = 'noopener noreferrer';
                } } catch (_) { /* display the label without navigation */ }
                render(node, token.tokens, true, depth + 1);
            } else if (type === 'image') node = document.createTextNode(token.text || showUserText('图片', 'Image'));
            else if (type === 'html') node = document.createTextNode(token.raw || token.text || '');
            else if (type === 'code' || type === 'codespan') {
                node = document.createElement(type === 'code' ? 'pre' : 'code');
                node.textContent = token.text || '';
            } else if (type === 'br' || type === 'hr') node = document.createElement(type);
            else if (type === 'heading' || type === 'paragraph' || type === 'blockquote' || type === 'strong' || type === 'em' || type === 'del') {
                var tag = type === 'heading' ? 'h' + Math.max(1, Math.min(6, token.depth || 1)) : ({ paragraph: 'p', blockquote: 'blockquote', strong: 'strong', em: 'em', del: 'del' })[type];
                node = document.createElement(tag);
                render(node, token.tokens || [{ type: 'text', text: token.text || '' }], type !== 'blockquote', depth + 1);
            } else if (token.tokens) { render(parent, token.tokens, inline, depth + 1); return; }
            else node = document.createTextNode(token.text || token.raw || '');
            parent.appendChild(node);
        });
    }
    try { render(host, parser.lexer(String(text || '').slice(0, 65536)), false, 0); }
    catch (_) { host.replaceChildren(showUserElement('pre', 'show-user-plain', text)); }
    if (truncated) host.appendChild(showUserElement('p', 'show-user-status', showUserText('内容过长，部分内容已省略。', 'Some content was omitted because it is too long.')));
}

function showUserPresentationBody(tab) {
    var key;
    try { key = decodeURIComponent(tab.contentId.slice(SHOW_USER_ADDRESS.length)); } catch (_) { /* invalid address */ }
    var record = showUserRecords.get(key);
    var root = showUserElement('section', 'show-user-view');
    root.setAttribute('data-show-user-view', key || '');
    if (!record) { root.appendChild(showUserElement('p', '', showUserText('展示内容暂不可用，请从会话记录重新打开。', 'Content unavailable. Reopen it from the chat.'))); return root; }
    root.appendChild(showUserElement('h2', 'show-user-view-title', record.title));
    if (record.kind === 'text') {
        var body = showUserElement('div', 'show-user-document');
        if (record.format === 'markdown') renderShowUserMarkdown(body, record.text);
        else body.appendChild(showUserElement('pre', 'show-user-plain', record.text));
        root.appendChild(body);
    } else if (record.kind === 'image' && record.image && /^sha256:[a-f0-9]{64}$/.test(record.image.attachment?.attachmentId || '')) {
        var image = document.createElement('img');
        image.className = 'show-user-image msg-attachment-image';
        image.alt = record.image.alt || record.title;
        image.loading = 'lazy'; image.decoding = 'async'; image.referrerPolicy = 'no-referrer';
        var source = '/sessions/' + encodeURIComponent(record.session_id) + '/presentations/' + encodeURIComponent(record.presentation_id) + '/image';
        var error = showUserElement('p', 'show-user-image-error', showUserText('图片加载失败。', 'Image failed to load.')); error.hidden = true;
        var retry = showUserElement('button', 'human-secondary-btn', showUserText('重新加载', 'Reload')); retry.type = 'button'; retry.hidden = true;
        image.addEventListener('error', function () { error.hidden = false; retry.hidden = false; image.hidden = true; });
        image.addEventListener('load', function () { error.hidden = true; retry.hidden = true; image.hidden = false; });
        retry.addEventListener('click', function () { error.hidden = true; retry.hidden = true; image.hidden = false; image.src = source + '?retry=' + Date.now(); });
        image.src = source;
        root.append(image);
        if (record.image.caption) root.appendChild(showUserElement('p', 'show-user-image-caption', record.image.caption));
        root.append(error, retry);
    }
    return root;
}

function initShowUserPresentations() {
    var api = globalThis.MyAgentDock;
    if (!api) return;
    if (!showUserRegistered) {
        api.registerTabType({ id: 'myagent.details.user-presentation', kind: 'user-presentation', priority: 'builtin',
            patterns: [SHOW_USER_ADDRESS + '**'], title: function () { return showUserText('展示内容', 'Presentation'); }, body: showUserPresentationBody });
        showUserRegistered = true;
    }
    flushShowUserPending();
}

function flushShowUserPending() {
    if (!globalThis.MyAgentDock || !showUserRegistered) return;
    var records = Array.from(showUserPending.values());
    showUserPending.clear();
    records.slice(-16).forEach(function (record) {
        if (typeof currentSessionId === 'string' && record.session_id === currentSessionId) openShowUserPresentation(record, false);
    });
}
document.addEventListener('myagent:dock-ready', initShowUserPresentations);
document.addEventListener('myagent:plugin-ui-ready', flushShowUserPending);
if (globalThis.MyAgentDock) initShowUserPresentations();
