/** Compact activity entry with a persistent, non-modal list/output popover. */
var backgroundTaskUi = (function () {
    var trigger = null, menu = null, list = null, empty = null, status = null, retry = null;
    var heading = null, listView = null, logView = null, logTitle = null, logStatus = null, logOutput = null;
    var logTerminal = null, logError = null, logRetry = null;
    var opened = false, pinned = false, hoverTimer = null, closeTimer = null;
    var activeSessionId = '', lastRefresh = 0, bound = false;
    var viewGeneration = 0;
    var rows = new Map(), stopping = new Set(), errors = new Map();
    var log = null, logFlight = null, logController = null;

    function text(zh, en) { return document.documentElement.lang.indexOf('en') === 0 ? en : zh; }
    function node(tag, value, className) {
        var el = document.createElement(tag);
        if (value != null) el.textContent = value;
        if (className) el.className = className;
        return el;
    }
    function put(el, value) { if (el.textContent !== value) el.textContent = value; }
    function button(label, action, className) {
        var el = node('button', label, className || 'background-task-action');
        el.type = 'button'; el.addEventListener('click', action); return el;
    }
    function cancelHover() { clearTimeout(hoverTimer); clearTimeout(closeTimer); hoverTimer = closeTimer = null; }
    function leave() {
        clearTimeout(hoverTimer); clearTimeout(closeTimer);
        if (!opened || !menu || pinned || log || !backgroundTaskStore.snapshot().jobs.length) return;
        closeTimer = setTimeout(function () {
            if (pinned || log || menu.contains(document.activeElement)) return;
            if ((trigger && trigger.matches(':hover')) || menu.matches(':hover')) return;
            close({ restoreFocus: false });
        }, 120);
    }
    function ensureTrigger() {
        if (trigger) return trigger;
        trigger = button('', function () {
            cancelHover();
            if (opened && pinned) close();
            else { pinned = true; open(false); }
        }, 'subagent-catalog-trigger background-task-trigger');
        trigger.id = 'background-task-trigger';
        trigger.setAttribute('aria-haspopup', 'dialog');
        trigger.setAttribute('aria-controls', 'background-task-menu');
        trigger.setAttribute('aria-expanded', 'false');
        trigger.append(node('span', '', 'subagent-catalog-dot'), node('span', '', 'subagent-catalog-label'));
        trigger.firstChild.setAttribute('aria-hidden', 'true');
        trigger.addEventListener('mouseenter', function () {
            cancelHover();
            if (!opened) hoverTimer = setTimeout(function () { open(false); }, 150);
        });
        trigger.addEventListener('mouseleave', leave);
        trigger.addEventListener('keydown', function (event) {
            if (event.key === 'ArrowDown') {
                event.preventDefault(); pinned = true; open(true);
            } else if (event.key === 'Escape' && opened) { event.preventDefault(); close(); }
        });
        return trigger;
    }
    function ensureMenu() {
        if (menu) return;
        menu = node('section', null, 'subagent-catalog-menu background-task-menu');
        menu.id = 'background-task-menu'; menu.hidden = true;
        menu.setAttribute('role', 'dialog'); menu.setAttribute('aria-modal', 'false');
        menu.setAttribute('aria-labelledby', 'background-task-heading');
        menu.addEventListener('mouseenter', cancelHover); menu.addEventListener('mouseleave', leave);
        menu.addEventListener('keydown', function (event) {
            if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); close(); }
        });
        var header = node('header', null, 'background-task-head');
        heading = node('strong'); heading.id = 'background-task-heading';
        var closeButton = button('×', function () { close(); });
        closeButton.setAttribute('aria-label', text('关闭后台任务', 'Close background tasks'));
        header.append(heading, closeButton);
        status = node('div', '', 'background-task-error'); status.setAttribute('role', 'status');
        retry = button(text('重试', 'Retry'), function () { void refresh(); });
        listView = node('div'); list = node('div', null, 'background-task-list');
        empty = node('p', '', 'background-task-empty');
        listView.append(list, empty);
        logView = node('div', null, 'background-task-log'); logView.hidden = true;
        logTitle = node('strong', '', 'background-task-log-title');
        logStatus = node('p', '', 'background-task-meta');
        logTerminal = button(text('查看对应终端', 'View corresponding terminal'), function () {
            if (log) openConsole(log.job.owner_session_id, log.job.terminal_id);
        });
        logError = node('p', '', 'background-task-error'); logError.setAttribute('role', 'status');
        logRetry = button(text('重试读取输出', 'Retry output'), function () { if (log) { log.done = false; void refreshOutput(); } });
        logOutput = node('pre', '', 'background-task-output'); logOutput.tabIndex = 0;
        logOutput.setAttribute('aria-label', text('任务输出', 'Task output'));
        logOutput.setAttribute('data-i18n-skip', 'true');
        logView.append(button(text('← 返回列表', '← Back to list'), backToList), logTitle, logStatus,
            logTerminal, logError, logRetry, logOutput);
        var footer = node('footer', null, 'background-task-footer');
        footer.append(button(text('打开执行与终端 →', 'Open execution and terminals →'), function () {
            openConsole(activeSessionId);
        }));
        menu.append(header, status, retry, listView, logView, footer);
        document.body.appendChild(menu);
    }
    function position() {
        if (!opened || !trigger || !menu) return;
        var anchor = trigger.isConnected ? trigger : document.querySelector('.breadcrumb-title-row');
        if (!anchor) return;
        var rect = anchor.getBoundingClientRect();
        var width = Math.max(0, Math.min(420, window.innerWidth - 32));
        menu.style.width = width + 'px';
        menu.style.left = Math.max(16, Math.min(rect.left, window.innerWidth - width - 16)) + 'px';
        menu.style.top = Math.max(8, Math.min(rect.bottom + 6, window.innerHeight - menu.offsetHeight - 8)) + 'px';
    }
    function open(focus) {
        if (!activeSessionId || !backgroundTaskStore.snapshot().jobs.length && !opened) return;
        ensureMenu(); cancelHover();
        if (typeof subagentCatalogUi !== 'undefined') subagentCatalogUi.closeMenu({ restoreFocus: false });
        opened = true; menu.hidden = false;
        trigger.setAttribute('aria-expanded', 'true');
        render(); position();
        document.addEventListener('mousedown', outside, true);
        document.addEventListener('keydown', onDocumentKeydown);
        window.addEventListener('resize', position, { passive: true });
        window.addEventListener('scroll', position, { passive: true, capture: true });
        if (focus) (list.querySelector('button') || menu.querySelector('button')).focus();
        void refresh();
    }
    function close(options) {
        options = options || {}; cancelHover();
        if (!opened) return;
        opened = pinned = false; menu.hidden = true;
        trigger.setAttribute('aria-expanded', 'false');
        backToList();
        document.removeEventListener('mousedown', outside, true);
        document.removeEventListener('keydown', onDocumentKeydown);
        window.removeEventListener('resize', position);
        window.removeEventListener('scroll', position, true);
        if (options.restoreFocus !== false) {
            var target = trigger.isConnected ? trigger : document.querySelector('.breadcrumb-session-actions button, #message-input');
            if (target) target.focus({ preventScroll: true });
        }
    }
    function outside(event) {
        if (!menu.contains(event.target) && !trigger.contains(event.target)) close({ restoreFocus: false });
    }
    function onDocumentKeydown(event) {
        if (event.key === 'Escape') { event.preventDefault(); close(); }
    }
    function duration(job) {
        var seconds = Math.max(0, Math.floor(((job.finished_at || Date.now() / 1000) - Number(job.started_at || Date.now() / 1000))));
        if (seconds < 60) return seconds + 's';
        if (seconds < 3600) return Math.floor(seconds / 60) + 'm ' + seconds % 60 + 's';
        return Math.floor(seconds / 3600) + 'h ' + Math.floor(seconds % 3600 / 60) + 'm';
    }
    function jobStatus(job) {
        if (job.kind === 'pty-send') {
            if (job.status === 'completed') return job.command_state === 'shell_ready'
                ? text('发送等待结束 · Shell 已就绪', 'Send observation ended · Shell ready')
                : text('发送等待结束 · 命令状态未知', 'Send observation ended · Command state unknown');
            if (job.status === 'killed') return job.interruption && job.interruption.interruptVerified
                ? text('发送等待已取消 · 已观察到中断', 'Send observation cancelled · Interrupt observed')
                : text('发送等待已取消 · 中断未确认', 'Send observation cancelled · Interrupt unconfirmed');
        }
        var labels = { running: text('运行中', 'Running'), stopping: text('停止中', 'Stopping'),
            completed: text('已完成', 'Completed'), failed: text('失败', 'Failed'), killed: text('已停止', 'Stopped') };
        return labels[job.status] || job.status;
    }
    function createRow(key) {
        var row = node('article', null, 'background-task-row');
        var top = node('div', null, 'background-task-row-top');
        var dot = node('span', '', 'subagent-catalog-status is-running'); dot.setAttribute('aria-hidden', 'true');
        var name = node('span', '', 'background-task-name'); name.setAttribute('data-i18n-skip', 'true');
        var state = node('span', '', 'background-task-state'); top.append(dot, name, state);
        var bottom = node('div', null, 'background-task-row-bottom');
        var meta = node('span', '', 'background-task-meta');
        var actions = node('span', null, 'background-task-actions');
        var item = { el: row, name: name, state: state, meta: meta, job: null, stop: null, error: null };
        var output = button(text('日志', 'Output'), function () { showOutput(item.job); });
        item.stop = button(text('停止', 'Stop'), async function () {
            if (stopping.has(key) || !item.job || item.job.status !== 'running') return;
            var epoch = viewGeneration;
            stopping.add(key); errors.delete(key); render();
            try { await backgroundTaskStore.stop(item.job); }
            catch (error) {
                if (epoch === viewGeneration && error.name !== 'AbortError') errors.set(key, String(error.message || error));
            } finally {
                if (epoch === viewGeneration) { stopping.delete(key); render(); }
            }
        });
        actions.append(output, item.stop); bottom.append(meta, actions);
        item.error = node('p', '', 'background-task-error'); item.error.setAttribute('role', 'status');
        row.append(top, bottom, item.error);
        return item;
    }
    function render() {
        var snapshot = backgroundTaskStore.snapshot();
        if (snapshot.sessionId !== activeSessionId) return;
        var jobs = snapshot.jobs;
        if (jobs.length) {
            var el = ensureTrigger();
            var running = jobs.some(function (job) { return job.status === 'running'; });
            el.firstChild.classList.toggle('is-running', running);
            el.firstChild.classList.toggle('is-stopping', !running);
            var label = text('后台任务 ', 'Background tasks ') + jobs.length
                + (running ? '' : text(' · 停止中', ' · Stopping'))
                + (snapshot.error ? text(' · 更新失败', ' · Update failed') : '');
            put(el.lastChild, label);
            el.title = snapshot.error || text('查看当前会话及子代理的活动执行任务', 'Active execution jobs in this conversation and its descendants');
            titlebarActivity.mount(el);
        } else if (trigger && trigger.isConnected) trigger.remove();
        if (!opened) return;
        put(heading, text('后台任务 · ', 'Background tasks · ') + jobs.length + text(' 个活动任务', ' active'));
        put(status, snapshot.error ? text('更新失败：', 'Update failed: ') + snapshot.error : '');
        status.hidden = retry.hidden = !snapshot.error;
        empty.hidden = jobs.length > 0;
        put(empty, snapshot.loading ? text('加载中…', 'Loading…') : text('当前无活动任务', 'No active tasks'));
        var keys = new Set(), lostFocus = false;
        jobs.forEach(function (job, index) {
            var key = backgroundTaskStore.key(job); keys.add(key);
            var item = rows.get(key);
            if (!item) { item = createRow(key); rows.set(key, item); }
            item.job = job;
            put(item.name, job.label || job.id); item.name.title = job.label || job.id;
            put(item.state, jobStatus(job));
            var owner = job.owner_session_id === activeSessionId ? text('当前会话', 'Current conversation')
                : text('子代理：', 'Subagent: ') + (job.owner_label || job.owner_session_id.slice(0, 12));
            put(item.meta, owner + ' · ' + (job.kind === 'pty-send' ? text('终端', 'Terminal') : text('进程', 'Process')) + ' · ' + duration(job));
            item.meta.title = owner;
            item.stop.disabled = job.status !== 'running' || stopping.has(key);
            put(item.stop, stopping.has(key) ? text('停止中…', 'Stopping…') : text('停止', 'Stop'));
            put(item.error, errors.get(key) || ''); item.error.hidden = !errors.has(key);
            if (list.children[index] !== item.el) list.insertBefore(item.el, list.children[index] || null);
        });
        rows.forEach(function (item, key) {
            if (!keys.has(key)) {
                lostFocus = lostFocus || item.el.contains(document.activeElement);
                item.el.remove(); rows.delete(key); errors.delete(key);
            }
        });
        if (lostFocus) (list.querySelector('button') || menu.querySelector('button')).focus({ preventScroll: true });
        position();
    }
    function showOutput(job) {
        backToList(); pinned = true;
        log = { job: Object.assign({}, job), offset: 0, done: false };
        logController = new AbortController();
        listView.hidden = true; logView.hidden = false;
        logOutput.textContent = ''; logOutput.scrollTop = 0;
        logTitle.textContent = job.label || job.id; logTitle.setAttribute('data-i18n-skip', 'true');
        logError.hidden = logRetry.hidden = true;
        updateLogStatus(); position();
        logView.querySelector('button').focus({ preventScroll: true });
        void refreshOutput();
    }
    function updateLogStatus() {
        if (!log) return;
        put(logStatus, jobStatus(log.job) + ' · ' + duration(log.job));
        logTerminal.hidden = log.job.kind !== 'pty-send' || !log.job.terminal_id;
        var warning = logView.querySelector('.background-task-terminal-note');
        if (log.job.kind === 'pty-send' && !warning) {
            warning = node('p', text('此任务记录一次发送的等待窗口；等待结束或 Shell 就绪不代表命令执行成功。后续输出请查看对应终端。',
                'This job records a send observation window. Observation ending or shell readiness does not establish command success. See the corresponding terminal for continuing output.'), 'background-task-terminal-note');
            logView.insertBefore(warning, logOutput);
        }
    }
    async function refreshOutput() {
        if (!log || log.done || logFlight || document.hidden) return;
        var current = log;
        var pending = backgroundTaskStore.output(current.job, current.offset, logController.signal);
        logFlight = pending;
        try {
            var result = await pending;
            if (log !== current || !opened) return;
            var following = logOutput.scrollHeight - logOutput.clientHeight - logOutput.scrollTop < 24;
            if (result.text) {
                logOutput.appendChild(document.createTextNode(result.text));
                if (logOutput.textContent.length > 256 * 1024) logOutput.textContent = logOutput.textContent.slice(-256 * 1024);
            }
            current.offset = result.offset;
            if (result.job) current.job = Object.assign({}, current.job, result.job);
            current.done = !backgroundTaskStore.isActive(current.job);
            logError.hidden = logRetry.hidden = true;
            updateLogStatus();
            if (following) logOutput.scrollTop = logOutput.scrollHeight;
        } catch (error) {
            if (log !== current || error.name === 'AbortError') return;
            put(logError, text('读取输出失败：', 'Output unavailable: ') + String(error.message || error));
            logError.hidden = logRetry.hidden = false;
        } finally { if (logFlight === pending) logFlight = null; }
    }
    function backToList(event) {
        var oldKey = log && backgroundTaskStore.key(log.job);
        if (logController) logController.abort();
        logController = null; logFlight = null; log = null;
        if (!logView) return;
        logView.hidden = true; listView.hidden = false;
        var warning = logView.querySelector('.background-task-terminal-note');
        if (warning) warning.remove();
        if (event && oldKey) {
            var row = rows.get(oldKey);
            (row ? row.el.querySelector('button') : menu.querySelector('button')).focus({ preventScroll: true });
        }
    }
    function openConsole(sessionId, terminalId) {
        var options = { sessionId: sessionId || activeSessionId };
        if (terminalId) options.terminalId = terminalId;
        if (!globalThis.MyAgentDock || !globalThis.MyAgentDock.openPluginPage('execution-tools', options)) {
            put(status, text('执行与终端当前不可用', 'Execution and terminals is unavailable'));
            status.hidden = false; return;
        }
        close({ restoreFocus: false });
    }
    function refresh() { lastRefresh = Date.now(); return backgroundTaskStore.refresh(); }
    function noteCurrentSession(sessionId) {
        var sid = String(sessionId || '');
        if (sid === activeSessionId) { render(); return; }
        close({ restoreFocus: false });
        viewGeneration += 1;
        activeSessionId = sid; lastRefresh = Date.now();
        rows.forEach(function (item) { item.el.remove(); }); rows.clear(); stopping.clear(); errors.clear();
        backgroundTaskStore.setSession(sid);
        render();
    }
    function bind() {
        if (bound) return; bound = true;
        backgroundTaskStore.subscribe(render);
        document.addEventListener('myagent:session-change', function (event) {
            noteCurrentSession(event.detail && event.detail.sessionId);
        });
        registerSidebarRefreshTask('background-task-capsule', 1000, function () {
            if (!activeSessionId) return;
            if (Date.now() - lastRefresh >= (opened ? 1000 : 4000)) void refresh();
            if (opened) { render(); void refreshOutput(); }
        }, { runWhenHidden: false });
        document.addEventListener('visibilitychange', function () {
            if (!document.hidden && activeSessionId) { void refresh(); if (opened) void refreshOutput(); }
        });
        window.addEventListener('focus', function () {
            if (!document.hidden && activeSessionId) { void refresh(); if (opened) void refreshOutput(); }
        });
        noteCurrentSession(typeof currentSessionId !== 'undefined' ? currentSessionId : '');
    }
    return { bind: bind, noteCurrentSession: noteCurrentSession, close: close, isOpen: function () { return opened; } };
})();
