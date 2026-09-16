/**
 * 子代理标题栏谱系 + 目录树（dsh 的 `SubagentHeaderLineage` 子集，原生 DOM 实现）。
 *
 * 组成：
 *   1. 计数触发器：挂在标题后面（普通会话追加；寻址在子会话时挂在子会话名后）。
 *      有任一后代 running 时显示活动点，文案为「N 个子代理」/「N 个 · M 运行中」。
 *   2. 门户下拉目录树（role=tree）：行 = 状态点 + 名称 + 「类型 · running/inactive」
 *      + 右侧指标。键盘：↑↓ 线性导航、Enter/→ 打开、Esc 关闭并归还焦点、Home/End。
 *
 * 数据：只读 subagentCatalogStore 的快照（对象层持有业务数据，本模块不缓存事实）；
 *      打开目录时 setCatalogOpen(parentId, true) 触发单飞刷新。
 *
 * 与 dsh 的差异（有意）：MyAgent 后端暂无 hasChildren 树形展开，因此目录只列
 * 直接子代（够用且与后端契约一致）；后代汇总数由 summarizeDescendants 提供。
 */
var subagentCatalogUi = (function () {
    var HOVER_OPEN_MS = 150;
    var HOVER_CLOSE_MS = 120;

    var triggerEl = null;
    var menuEl = null;
    var menuOpen = false;
    var hoverTimer = null;
    var closeTimer = null;
    var unsubscribeStore = null;
    var activeParentId = '';
    var rows = [];            // 当前渲染的行（含 DOM 引用）
    var focusedIndex = -1;
    var selectedIndex = -1;   // 当前已寻址（正在查看）的兄弟行，供 ←→ 折叠语义使用

    function store() {
        return (typeof subagentCatalogStore !== 'undefined' && subagentCatalogStore) ? subagentCatalogStore : null;
    }

    function escapeText(value) {
        var s = String(value == null ? '' : value);
        if (typeof escapeHtml === 'function') return escapeHtml(s);
        return s.replace(/[&<>"']/g, function (c) {
            return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
        });
    }

    function currentParentId() {
        var storeRef = store();
        if (!storeRef) return '';
        // 寻址在子会话时，父标识取寻址栈顶的父；否则用当前会话
        if (typeof subagentAddressing !== 'undefined' && subagentAddressing && subagentAddressing.isChildOpen()) {
            var top = subagentAddressing.current();
            if (top && top.parentSessionId) return String(top.parentSessionId);
        }
        var sid = '';
        try {
            if (typeof currentSessionId !== 'undefined' && currentSessionId) sid = String(currentSessionId);
        } catch (e) { sid = ''; }
        if (!sid && typeof sessionStore !== 'undefined' && sessionStore && sessionStore.currentSessionId) {
            sid = String(sessionStore.currentSessionId);
        }
        return sid;
    }

    /** 有子代理证据才显示触发器（避免无子代理会话闪烁）。 */
    function hasEvidence(parentId) {
        var storeRef = store();
        if (!storeRef || !parentId) return false;
        var catalog = storeRef.getCatalog(parentId);
        if (catalog && Array.isArray(catalog.entries) && catalog.entries.length) return true;
        if (storeRef.isCatalogOpen(parentId)) return true;
        // 流里已出现该父会话的子代理（目录尚未覆盖）也算证据
        if (typeof subagentFrames !== 'undefined' && subagentFrames
            && typeof subagentFrames.hasUnknownChildEvidence === 'function') {
            return subagentFrames.hasUnknownChildEvidence(parentId);
        }
        return false;
    }

    function fmtCount(summary) {
        var total = summary.total;
        var running = summary.running;
        var suffix = running > 0 ? (' · ' + running + ' 运行中') : '';
        return total + ' 个子代理' + suffix;
    }

    // ── 触发器 ──────────────────────────────────────────────────────────────
    function ensureTrigger() {
        if (triggerEl && triggerEl.isConnected) return triggerEl;
        triggerEl = document.createElement('button');
        triggerEl.type = 'button';
        triggerEl.id = 'subagent-catalog-trigger';
        triggerEl.className = 'subagent-catalog-trigger hidden';
        triggerEl.setAttribute('aria-haspopup', 'tree');
        triggerEl.setAttribute('aria-expanded', 'false');
        triggerEl.addEventListener('click', function (event) {
            event.preventDefault();
            event.stopPropagation();
            toggleMenu();
        });
        triggerEl.addEventListener('mouseenter', function () {
            scheduleHoverOpen();
        });
        triggerEl.addEventListener('mouseleave', function () {
            scheduleHoverClose();
        });
        return triggerEl;
    }

    /**
     * 渲染触发器到标题栏（普通会话挂在标题后）。
     * @param {HTMLElement} titleRow 标题行容器
     * @param {string} parentId 该标题对应的会话 id（目录的父）
     */
    function renderTrigger(titleRow, parentId) {
        if (!titleRow || !parentId) return hideTrigger();
        var storeRef = store();
        if (!storeRef) return hideTrigger();
        var el = ensureTrigger();
            if (!hasEvidence(parentId)) {
            if (el.parentNode) el.parentNode.removeChild(el);
            el.classList.add('hidden');
            if (menuOpen) closeMenu();
            return;
        }
        activeParentId = String(parentId);
        var summary = storeRef.summarizeDescendants(parentId);
        var label = fmtCount(summary);
        var running = summary.running > 0;
        el.innerHTML = '<span class="subagent-catalog-dot' + (running ? ' is-running' : '')
            + '" aria-hidden="true"></span>'
            + '<span class="subagent-catalog-label">' + escapeText(label) + '</span>';
            el.classList.remove('hidden');
            // 挂在标题行（#breadcrumb-text 的兄弟位置）：纯文本标题不受影响，
            // 且与标题、会话菜单同处一条 flex 行 → 天然垂直对齐。
            if (el.parentNode !== titleRow) {
                var actions = titleRow.querySelector
                    ? titleRow.querySelector('.breadcrumb-session-actions')
                    : null;
                if (actions && actions.parentNode === titleRow) titleRow.insertBefore(el, actions);
                else titleRow.appendChild(el);
            }
        el.setAttribute('aria-expanded', menuOpen ? 'true' : 'false');
    }

    function hideTrigger() {
        if (triggerEl) {
            triggerEl.classList.add('hidden');
            if (triggerEl.parentNode) triggerEl.parentNode.removeChild(triggerEl);
        }
        if (menuOpen) closeMenu();
    }

    // ── 目录树 ──────────────────────────────────────────────────────────────
    function ensureMenu() {
        if (menuEl && menuEl.isConnected) return menuEl;
        menuEl = document.createElement('div');
        menuEl.id = 'subagent-catalog-menu';
        menuEl.className = 'subagent-catalog-menu';
        menuEl.setAttribute('role', 'tree');
        menuEl.setAttribute('aria-label', '子代理目录');
        menuEl.hidden = true;
        menuEl.addEventListener('keydown', onMenuKeydown);
        menuEl.addEventListener('mouseenter', function () {
            if (closeTimer != null) { clearTimeout(closeTimer); closeTimer = null; }
        });
        menuEl.addEventListener('mouseleave', function () {
            if (menuOpen) scheduleHoverClose();
        });
        document.body.appendChild(menuEl);
        return menuEl;
    }

    function positionMenu() {
        if (!menuEl || !triggerEl) return;
        var rect = triggerEl.getBoundingClientRect();
        var width = Math.min(340, Math.max(240, window.innerWidth - 32));
        var left = Math.max(8, Math.min(rect.left, window.innerWidth - width - 8));
        menuEl.style.left = Math.round(left) + 'px';
        menuEl.style.top = Math.round(rect.bottom + 6) + 'px';
        menuEl.style.width = Math.round(width) + 'px';
    }

    /**
     * 圆点色彩语义（用户规格）：
     *   ● 琥珀  is-running  进行中
     *   ● 绿色  is-unread   正常完成且未读
     *   ● 蓝色  is-read     正常完成且已读
     *   ● 红色  is-error    错误（失败/中断/取消/缺结果/诊断行）
     */
    function statusDotClass(entry) {
        if (entry.diagnostic) return 'is-error';
        if (entry.outcome === 'failed') return 'is-error';
        if (entry.outcome === 'running' || entry.activity === 'running') return 'is-running';
        var storeRef = store();
        var read = !!(storeRef && storeRef.isSubagentRead && storeRef.isSubagentRead(entry.childId));
        return read ? 'is-read' : 'is-unread';
    }

    function activityText(entry) {
        if (entry.diagnostic) return '不可用';
        return entry.activity === 'running' ? 'running' : 'inactive';
    }

    function modeText(entry) {
        if (entry.diagnostic) return '';
        return entry.mode === 'one-shot' ? '一次性' : '可续接';
    }

    /** 行指标：token 占用（惰性拉取）+ 已用时长（本地时钟，running 时每秒刷新）。 */
    function metricsText(entry) {
        if (!entry || entry.diagnostic) return '';
        var parts = [];
        var storeRef = store();
        var tokens = storeRef && storeRef.getTokens ? storeRef.getTokens(entry.childId) : null;
        if (tokens && tokens.estimated) {
            parts.push(formatTokenCount(tokens.estimated));
        }
        var duration = formatDuration(entry);
        if (duration) parts.push(duration);
        return parts.join(' · ');
    }

    function formatTokenCount(value) {
        var n = Number(value) || 0;
        if (n >= 1000) return (Math.round(n / 100) / 10) + 'k';
        return String(n);
    }

    function formatDuration(entry) {
        var startedAt = Number(entry.startedAt || 0) || 0;
        if (!startedAt) return '';
        var endAt = entry.activity === 'running'
            ? Date.now()
            : (Number(entry.finishedAt || 0) || Number(entry.updatedAt || 0) || Date.now());
        var seconds = Math.max(0, Math.floor((endAt - startedAt) / 1000));
        if (seconds < 60) return seconds + 's';
        var minutes = Math.floor(seconds / 60);
        if (minutes < 60) return minutes + 'm';
        var hours = Math.floor(minutes / 60);
        if (hours < 24) return hours + 'h';
        return Math.floor(hours / 24) + 'd';
    }

    /** 目录打开后按需拉取缺指标的 token（并发上限 5，失败不重试）。 */
    var tokenFetchInFlight = 0;
    function primeTokenMetrics(entries) {
        var storeRef = store();
        if (!storeRef || !storeRef.fetchTokens) return;
        entries.forEach(function (entry) {
            if (entry.diagnostic) return;
            if (storeRef.getTokens(entry.childId)) return;
            if (tokenFetchInFlight >= 5) return;
            tokenFetchInFlight += 1;
            void storeRef.fetchTokens(entry.childId).then(function () {
                tokenFetchInFlight -= 1;
            }, function () {
                tokenFetchInFlight -= 1;
            });
        });
    }

    /** 当前已寻址的子代理在该目录中的行号（用于 is-selected 与 ←→ 折叠语义）。 */
    function indexOfAddressedChild(entries) {
        var addrRef = (typeof subagentAddressing !== 'undefined' && subagentAddressing) ? subagentAddressing : null;
        var top = addrRef ? addrRef.current() : null;
        if (!top) return -1;
        var cid = String(top.childSessionId || '');
        for (var i = 0; i < entries.length; i += 1) {
            if (!entries[i].diagnostic && entries[i].childId === cid) return i;
        }
        return -1;
    }

    function renderMenu() {
        var storeRef = store();
        var menu = ensureMenu();
        if (!storeRef || !menuOpen || !activeParentId) return;
        var catalog = storeRef.getCatalog(activeParentId);
        var entries = (catalog && Array.isArray(catalog.entries)) ? catalog.entries : [];
        rows = [];
        focusedIndex = -1;
        selectedIndex = indexOfAddressedChild(entries);
        var html = '';
        if (catalog && catalog.state === 'loading' && !entries.length) {
            html += '<div class="subagent-catalog-loading" aria-busy="true">加载中…</div>';
        } else if (!entries.length) {
            html += '<div class="subagent-catalog-empty">暂无子代理</div>';
        } else {
            entries.forEach(function (entry, index) {
                var key = entry.diagnostic ? ('diag-' + index) : entry.childId;
                var name = entry.diagnostic
                    ? ('诊断行（' + String(entry.reason || 'corrupt') + '）')
                    : (entry.label || entry.childId.slice(0, 12));
                var meta = [modeText(entry), activityText(entry)].filter(Boolean).join(' · ');
                var metrics = metricsText(entry);
                html += '<div class="subagent-catalog-row' + (entry.diagnostic ? ' is-diagnostic' : '')
                    + ((!entry.diagnostic && index === selectedIndex) ? ' is-selected' : '')
                    + '" role="treeitem" tabindex="-1" data-key="' + escapeText(key) + '"'
                    + (entry.diagnostic ? ' aria-disabled="true"' : '')
                    + '>'
                    + '<span class="subagent-catalog-status ' + statusDotClass(entry) + '" aria-hidden="true"></span>'
                    + '<span class="subagent-catalog-name">' + escapeText(name) + '</span>'
                    + '<span class="subagent-catalog-metrics">' + escapeText(metrics) + '</span>'
                    + '<span class="subagent-catalog-meta">' + escapeText(meta) + '</span>'
                    + '</div>';
            });
        }
        if (catalog && catalog.state === 'error') {
            html += '<div class="subagent-catalog-error">目录加载失败：'
                + escapeText(catalog.error || '') + '</div>';
        }
        menu.innerHTML = html;
        primeTokenMetrics(entries);
        Array.prototype.slice.call(menu.querySelectorAll('.subagent-catalog-row')).forEach(function (rowEl) {
            rows.push({
                el: rowEl,
                key: rowEl.getAttribute('data-key'),
                diagnostic: rowEl.classList.contains('is-diagnostic'),
            });
            rowEl.addEventListener('click', function (event) {
                event.preventDefault();
                selectRow(rowEl.getAttribute('data-key'));
            });
            rowEl.addEventListener('mouseenter', function () {
                focusRow(rows.findIndex(function (r) { return r.el === rowEl; }));
            });
        });
    }

    function focusRow(index) {
        if (!rows.length) return;
        focusedIndex = ((index % rows.length) + rows.length) % rows.length;
        rows.forEach(function (row, i) {
            row.el.classList.toggle('is-focused', i === focusedIndex);
            if (i === focusedIndex) row.el.setAttribute('tabindex', '0');
            else row.el.setAttribute('tabindex', '-1');
        });
        var target = rows[focusedIndex];
        if (target && target.el.focus) {
            try { target.el.focus({ preventScroll: true }); } catch (e) { try { target.el.focus(); } catch (e2) { /* ignore */ } }
        }
    }

    function selectRow(key) {
        var storeRef = store();
        if (!storeRef || !key) return;
        var row = rows.find(function (r) { return r.key === key; });
        if (!row || row.diagnostic) return false;
        var entry = null;
        var entries = storeRef.entriesOf(activeParentId) || [];
        for (var i = 0; i < entries.length; i += 1) {
            if (!entries[i].diagnostic && entries[i].childId === key) { entry = entries[i]; break; }
        }
        if (!entry) return false;
        var addr = storeRef.selectSubagent(entry.childId);
        if (!addr) return false;
        // 打开即已读（圆点由绿转蓝）
        if (storeRef.markSubagentRead) storeRef.markSubagentRead(entry.childId);
        closeMenu({ restoreFocus: false });
        if (typeof subagentAddressing !== 'undefined' && subagentAddressing) {
            void subagentAddressing.openChild(entry.childId, {
                parentSessionId: addr.parentSessionId,
                title: entry.label,
                mode: entry.mode,
            });
        }
        return true;
    }

    function onMenuKeydown(event) {
        if (!menuOpen) return;
        var key = String(event.key || '');
        if (key === 'Escape') {
            event.preventDefault();
            closeMenu();
            return;
        }
        if (key === 'ArrowDown') {
            event.preventDefault();
            focusRow(focusedIndex < 0 ? 0 : focusedIndex + 1);
            return;
        }
        if (key === 'ArrowUp') {
            event.preventDefault();
            focusRow(focusedIndex < 0 ? rows.length - 1 : focusedIndex - 1);
            return;
        }
        if (key === 'Home') { event.preventDefault(); focusRow(0); return; }
        if (key === 'End') { event.preventDefault(); focusRow(rows.length - 1); return; }
        if (key === 'ArrowRight') {
            // 进入：把焦点行作为当前子会话打开（树语义的 "expand into"）
            event.preventDefault();
            var rightTarget = rows[focusedIndex] || rows[0];
            if (rightTarget && !rightTarget.diagnostic) selectRow(rightTarget.key);
            return;
        }
        if (key === 'ArrowLeft') {
            // 收起：回到父会话（等价于面包屑返回）
            event.preventDefault();
            if (selectedIndex >= 0) {
                closeMenu({ restoreFocus: false });
                if (typeof subagentAddressing !== 'undefined' && subagentAddressing) {
                    void subagentAddressing.returnToParent();
                }
            }
            return;
        }
        if (key === 'Enter' || key === ' ') {
            event.preventDefault();
            var target = rows[focusedIndex] || rows[0];
            if (target && !target.diagnostic) selectRow(target.key);
        }
    }

    function openMenu() {
        var storeRef = store();
        if (!storeRef || !activeParentId || menuOpen) return;
        menuOpen = true;
        if (triggerEl) triggerEl.setAttribute('aria-expanded', 'true');
        storeRef.setCatalogOpen(activeParentId, true);
        var menu = ensureMenu();
        menu.hidden = false;
        positionMenu();
        renderMenu();
        if (typeof initUiHoverTips === 'function') initUiHoverTips(menu);
        document.addEventListener('mousedown', onDocumentMouseDown, true);
        window.addEventListener('resize', positionMenu, { passive: true });
        requestAnimationFrame(function () {
            if (!menuOpen) return;
            focusRow(0);
        });
    }

    function closeMenu(opts) {
        opts = opts || {};
        if (!menuOpen) return;
        menuOpen = false;
        if (hoverTimer != null) { clearTimeout(hoverTimer); hoverTimer = null; }
        if (closeTimer != null) { clearTimeout(closeTimer); closeTimer = null; }
        if (triggerEl) triggerEl.setAttribute('aria-expanded', 'false');
        if (menuEl) {
            menuEl.hidden = true;
            menuEl.innerHTML = '';
        }
        rows = [];
        focusedIndex = -1;
        document.removeEventListener('mousedown', onDocumentMouseDown, true);
        window.removeEventListener('resize', positionMenu);
        var storeRef = store();
        if (storeRef && activeParentId) storeRef.setCatalogOpen(activeParentId, false);
        if (opts.restoreFocus !== false && triggerEl && triggerEl.isConnected) {
            try { triggerEl.focus({ preventScroll: true }); } catch (e) { try { triggerEl.focus(); } catch (e2) { /* ignore */ } }
        }
    }

    function toggleMenu() {
        if (menuOpen) closeMenu();
        else openMenu();
    }

    function onDocumentMouseDown(event) {
        if (!menuOpen) return;
        var target = event.target;
        if (menuEl && menuEl.contains(target)) return;
        if (triggerEl && triggerEl.contains(target)) return;
        closeMenu({ restoreFocus: false });
    }

    function scheduleHoverOpen() {
        if (closeTimer != null) { clearTimeout(closeTimer); closeTimer = null; }
        if (menuOpen) return;
        if (hoverTimer != null) clearTimeout(hoverTimer);
        hoverTimer = setTimeout(function () {
            hoverTimer = null;
            openMenu();
        }, HOVER_OPEN_MS);
    }

    function scheduleHoverClose() {
        if (hoverTimer != null) { clearTimeout(hoverTimer); hoverTimer = null; }
        if (closeTimer != null) clearTimeout(closeTimer);
        closeTimer = setTimeout(function () {
            closeTimer = null;
            closeMenu({ restoreFocus: false });
        }, HOVER_CLOSE_MS);
    }

    // ── 订阅：目录/寻址变化时重绘 ────────────────────────────────────────────
    var refreshDebounceTimer = null;
    var lastRefreshedParentId = '';

    /**
     * 会话切换/标题刷新时调用：去抖刷新该会话的直接目录，
     * 使「有没有子代理」这个证据尽快到位（无子代理的会话只多一次轻量请求）。
     */
    function noteCurrentSession(parentId) {
        var storeRef = store();
        var pid = String(parentId || '');
        if (!storeRef || !pid) return;
        if (pid === lastRefreshedParentId) return;
        lastRefreshedParentId = pid;
        if (refreshDebounceTimer != null) clearTimeout(refreshDebounceTimer);
        refreshDebounceTimer = setTimeout(function () {
            refreshDebounceTimer = null;
            void storeRef.refreshCatalogs(pid, { debounce: false });
        }, 120);
    }

    /**
     * 流里出现了目录尚未覆盖的子代理：立刻让触发器显形并去抖刷新目录，
     * 使新成员尽快进入目录树（权威仍来自目录读取）。
     */
    function noteUnknownChildEvidence(parentId) {
        var storeRef = store();
        var pid = String(parentId || '');
        if (!storeRef || !pid) return;
        if (pid === activeParentId && triggerEl && triggerEl.parentNode) {
            renderTrigger(triggerEl.parentNode, pid);
        }
        void storeRef.refreshCatalogs(pid, { debounce: true });
    }

    function bindStore() {
        var storeRef = store();
        if (!storeRef || unsubscribeStore) return;
        unsubscribeStore = storeRef.subscribe(function () {
            if (!triggerEl || !triggerEl.isConnected) return;
            var parentId = activeParentId || currentParentId();
            var titleRow = triggerEl.parentNode;
            if (titleRow) renderTrigger(titleRow, parentId);
            if (menuOpen) renderMenu();
        });
    }

    function isMenuOpen() {
        return menuOpen;
    }

    /**
     * 测试钩子：直接投放当前行集合（跳过 innerHTML → DOM 行的解析），
     * 使 selectRow / focusRow 这类逻辑可以在无浏览器的环境里被驱动。
     */
    function setRowsForTests(list) {
        rows = (Array.isArray(list) ? list : []).map(function (item) {
            var el = (typeof document !== 'undefined' && document.createElement)
                ? document.createElement('div')
                : { classList: { add() {}, remove() {}, toggle() {}, contains() { return false; } }, setAttribute() {}, getAttribute() { return null; }, focus() {} };
            return {
                el: el,
                key: String(item && item.key || ''),
                diagnostic: !!(item && item.diagnostic),
            };
        });
        focusedIndex = rows.length ? 0 : -1;
    }

    function resetForTests() {
        if (hoverTimer != null) clearTimeout(hoverTimer);
        if (closeTimer != null) clearTimeout(closeTimer);
        hoverTimer = null;
        closeTimer = null;
        menuOpen = false;
        rows = [];
        focusedIndex = -1;
        activeParentId = '';
        triggerEl = null;
        menuEl = null;
    }

    return {
        HOVER_OPEN_MS: HOVER_OPEN_MS,
        HOVER_CLOSE_MS: HOVER_CLOSE_MS,
        bindStore: bindStore,
        noteCurrentSession: noteCurrentSession,
        noteUnknownChildEvidence: noteUnknownChildEvidence,
        renderTrigger: renderTrigger,
        hideTrigger: hideTrigger,
        openMenu: openMenu,
        closeMenu: closeMenu,
        toggleMenu: toggleMenu,
        isMenuOpen: isMenuOpen,
        selectRow: selectRow,
        focusRow: focusRow,
        setRowsForTests: setRowsForTests,
        currentParentId: currentParentId,
        hasEvidence: hasEvidence,
        resetForTests: resetForTests,
    };
})();
