/** Shared context menus for the workbench and plugin-owned views. */
const uiContextMenuBindings = new WeakMap();
let uiContextMenuActive = null;

function uiContextMenuLabel(text) {
    return typeof uiLanguage !== 'undefined' && uiLanguage === 'en'
        ? translateUiString(String(text)) : String(text);
}

async function uiContextMenuCopy(text) {
    const value = String(text == null ? '' : text);
    try {
        if (!navigator.clipboard || !navigator.clipboard.writeText) throw new Error('clipboard unavailable');
        await navigator.clipboard.writeText(value);
    } catch (error) {
        const previous = document.activeElement;
        const selection = window.getSelection();
        const ranges = selection ? Array.from({ length: selection.rangeCount }, (_, i) => selection.getRangeAt(i).cloneRange()) : [];
        const input = document.createElement('textarea');
        input.value = value;
        input.style.cssText = 'position:fixed;left:-10000px;top:0';
        document.body.appendChild(input);
        input.select();
        const copied = document.execCommand('copy');
        input.remove();
        if (previous && previous.isConnected) previous.focus({ preventScroll: true });
        if (selection) { selection.removeAllRanges(); ranges.forEach(range => selection.addRange(range)); }
        if (!copied) throw error;
    }
    if (typeof showOpenFileFeedback === 'function') showOpenFileFeedback('已复制');
}

function uiContextMenuClose(restoreFocus) {
    const active = uiContextMenuActive;
    if (!active) return;
    uiContextMenuActive = null;
    active.observer.disconnect();
    active.menu.remove();
    if (restoreFocus && active.focus && active.focus.isConnected) active.focus.focus({ preventScroll: true });
}

/** Items: {label, action, disabled?, danger?, valid?}; null separates groups. */
function uiContextMenuOpen(event, items, owner) {
    const rows = items.filter((item, i) => item || (i > 0 && items[i - 1] && items.slice(i + 1).some(Boolean)));
    if (!rows.some(Boolean)) return false;
    event.preventDefault();
    event.stopPropagation();
    uiContextMenuClose(false);
    if (typeof hideUiHoverTooltip === 'function') hideUiHoverTooltip();
    if (typeof closeAllSessionMenus === 'function') closeAllSessionMenus();
    if (typeof closeAllMessageCopyPopovers === 'function') closeAllMessageCopyPopovers();
    const menu = document.createElement('div');
    menu.className = 'ui-context-menu';
    menu.setAttribute('role', 'menu');
    menu.setAttribute('aria-label', uiContextMenuLabel('右键菜单'));
    menu.tabIndex = -1;
    const focus = document.activeElement;
    rows.forEach(item => {
        if (!item) {
            const separator = document.createElement('div');
            separator.className = 'ui-context-menu-separator';
            separator.setAttribute('role', 'separator');
            menu.appendChild(separator);
            return;
        }
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'ui-context-menu-item' + (item.danger ? ' is-danger' : '');
        button.setAttribute('role', 'menuitem');
        button.tabIndex = -1;
        button.textContent = uiContextMenuLabel(item.label);
        button.disabled = !!item.disabled;
        if (item.title) button.title = uiContextMenuLabel(item.title);
        button.addEventListener('click', () => {
            if (button.disabled) return;
            uiContextMenuClose(true);
            // A rerender or session switch must never redirect a stale action.
            if ((owner && !owner.isConnected) || (item.valid && !item.valid())) return;
            try {
                Promise.resolve(item.action()).catch(uiContextMenuError);
            } catch (error) { uiContextMenuError(error); }
        });
        menu.appendChild(button);
    });
    // Prevent a second native menu and preserve selection on mouse activation.
    menu.addEventListener('contextmenu', e => e.preventDefault());
    menu.addEventListener('pointerdown', e => e.preventDefault());
    menu.addEventListener('keydown', e => {
        const buttons = Array.from(menu.querySelectorAll('button:not(:disabled)'));
        const index = buttons.indexOf(document.activeElement);
        let next;
        if (e.key === 'ArrowDown') next = (index + 1) % buttons.length;
        else if (e.key === 'ArrowUp') next = (index + buttons.length - 1) % buttons.length;
        else if (e.key === 'Home') next = 0;
        else if (e.key === 'End') next = buttons.length - 1;
        else if (e.key === 'Tab') { e.preventDefault(); e.stopPropagation(); uiContextMenuClose(true); return; }
        else if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault(); e.stopPropagation();
            if (index >= 0) buttons[index].click();
            return;
        }
        if (next !== undefined) {
            e.preventDefault(); e.stopPropagation();
            if (buttons[next]) buttons[next].focus({ preventScroll: true });
        }
    });
    document.body.appendChild(menu);
    const anchor = owner && owner.getBoundingClientRect();
    const keyboard = event.type === 'keydown' || (!event.clientX && !event.clientY);
    const x = keyboard && anchor ? anchor.left : event.clientX;
    const y = keyboard && anchor ? anchor.bottom : event.clientY;
    const bounds = menu.getBoundingClientRect();
    menu.style.left = Math.max(6, Math.min(x || 0, window.innerWidth - bounds.width - 6)) + 'px';
    menu.style.top = Math.max(6, Math.min(y || 0, window.innerHeight - bounds.height - 6)) + 'px';
    const observer = new MutationObserver(() => {
        if (owner && !owner.isConnected) uiContextMenuClose(false);
    });
    observer.observe(document.body, { childList: true, subtree: true });
    const scrollPositions = new Map();
    for (let node = owner; node; node = node.parentElement) scrollPositions.set(node, [node.scrollLeft, node.scrollTop]);
    const scrollingElement = document.scrollingElement;
    if (scrollingElement) scrollPositions.set(document, [scrollingElement.scrollLeft, scrollingElement.scrollTop]);
    uiContextMenuActive = { menu, owner, focus, observer, scrollPositions, width: window.innerWidth, height: window.innerHeight };
    (menu.querySelector('button:not(:disabled)') || menu).focus({ preventScroll: true });
    return true;
}

function uiContextMenuError(error) {
    if (typeof showUiAlert === 'function') showUiAlert({ title: '操作失败', message: String(error.message || error), variant: 'error' });
}

function uiContextMenuButton(button, label, danger) {
    return button ? {
        label: label || button.getAttribute('aria-label') || button.textContent.trim(),
        disabled: button.disabled, danger: !!danger,
        valid: () => button.isConnected && !button.disabled,
        action: () => button.click(),
    } : null;
}

function uiContextMenuButtons(root, selector) {
    return Array.from(root.querySelectorAll(selector)).filter(button => !button.hidden)
        .map(button => uiContextMenuButton(button));
}

async function uiContextMenuOpenFile(rel, directory) {
    const response = await fetch(workspaceApiUrl(directory ? '/api/open-workspace-dir' : '/api/open-workspace-file', { rel }));
    const result = await response.json();
    if (!response.ok || !result.ok) throw new Error(result.error || '无法打开文件');
    showOpenFileFeedback(directory ? '已打开文件目录' : '已打开文件');
}

function uiContextMenuFileItems(rel, path, directory) {
    let relative = String(rel || '').replace(/\\/g, '/');
    if (/^(?:[a-z]:\/|\/)/i.test(relative)) {
        const root = String(getActiveWorkDir() || '').replace(/\\/g, '/').replace(/\/+$/, '');
        const windows = /^(?:[a-z]:\/|\/\/)/i.test(root);
        const candidate = windows ? relative.toLowerCase() : relative;
        const prefix = windows ? root.toLowerCase() : root;
        relative = root && candidate.startsWith(prefix + '/') ? relative.slice(root.length + 1) : null;
    }
    return [
        { label: directory ? '在资源管理器打开' : '在系统应用中打开', action: () => uiContextMenuOpenFile(rel, directory) },
        !directory ? { label: '打开文件目录', action: () => uiContextMenuOpenFile(rel, true) } : null,
        null,
        { label: '复制路径', action: () => uiContextMenuCopy(path || rel) },
        { label: '复制相对路径', disabled: relative == null, action: () => uiContextMenuCopy(relative) },
    ];
}

function uiContextMenuAbsolutePath(rel) {
    if (/^(?:[a-z]:[\\/]|[\\/]{2}|\/)/i.test(rel)) return rel;
    const root = String(getActiveWorkDir() || '').replace(/[\\/]+$/, '');
    return root ? root + (root.includes('\\') ? '\\' : '/') + String(rel).replace(/[\\/]/g, root.includes('\\') ? '\\' : '/') : rel;
}

function uiContextMenuWorkbenchItems(target) {
    let node;
    if ((node = target.closest('.session-item, .breadcrumb'))) {
        const wrap = node.querySelector('.session-more-wrap');
        const sessionId = node.dataset.sessionId || currentSessionId;
        const session = findSessionForActions(sessionId, wrap && wrap._sessionMenuSession);
        if (wrap && session) syncSessionMenuLabels(wrap, session);
        return { owner: node, items: [
            { label: '打开会话', disabled: !sessionId, action: () => switchSession(sessionId) },
            ...uiContextMenuButtons(node, '.session-more-menu button').map(item => ({ ...item, danger: item.label === uiContextMenuLabel('删除会话') })),
            null, { label: '复制会话 ID', disabled: !sessionId, action: () => uiContextMenuCopy(sessionId) },
        ] };
    }
    if ((node = target.closest('.session-group-head'))) {
        return { owner: node, items: [uiContextMenuButton(node.querySelector('.session-time-group-title'), '展开 / 折叠分组'),
            ...uiContextMenuButtons(node, '.session-group-actions button:not([data-popup-trigger])')] };
    }
    if ((node = target.closest('.input-path-chip, a.msg-link-workspace-open'))) {
        const link = node.matches('a') ? node : node.querySelector('a[data-workspace-open]');
        const rel = link && link.getAttribute('data-workspace-open');
        if (rel) return { owner: node, items: [
            { label: '打开文件', action: () => link.click() },
            ...uiContextMenuFileItems(rel, uiContextMenuAbsolutePath(rel), false),
            uiContextMenuButton(node.querySelector('.input-path-chip-remove'), '移除附件'),
        ] };
    }
    if ((node = target.closest('video, audio'))) {
        const media = node;
        return { owner: media, items: [
            { label: media.paused ? '播放' : '暂停播放', action: () => media.paused ? media.play() : media.pause() },
            { label: media.muted ? '取消静音' : '静音', action: () => { media.muted = !media.muted; } },
            { label: media.loop ? '取消循环播放' : '循环播放', action: () => { media.loop = !media.loop; } },
            null, { label: '复制媒体地址', action: () => uiContextMenuCopy(media.currentSrc || media.src) },
        ] };
    }
    if ((node = target.closest('.dock-files-row'))) {
        const directory = node.classList.contains('dock-files-row--dir');
        return { owner: node, items: [uiContextMenuButton(node, directory
            ? (node.getAttribute('aria-expanded') === 'true' ? '折叠目录' : '展开目录') : '预览文件'),
            null, ...uiContextMenuFileItems(node.dataset.rel, node.title, directory)] };
    }
    if ((node = target.closest('.dock-change'))) {
        const rel = dockRightRelPath(node.getAttribute('data-dock-change-path'));
        return { owner: node, items: [
            uiContextMenuButton(node.querySelector('.dock-change-toggle'), '展开 / 折叠差分'),
            { label: '预览文件', action: () => dockRightOpenResource(DOCK_RIGHT_FILE_PREFIX + encodeURIComponent(rel)) },
            { label: '复制差分', action: () => uiContextMenuCopy(node.__myagentContextDiff || ''), disabled: !node.__myagentContextDiff },
            uiContextMenuButton(node.querySelector('.dock-change-action'), null, true), null,
            ...uiContextMenuFileItems(rel, node.getAttribute('data-dock-change-path'), false),
        ] };
    }
    if ((node = target.closest('.dock-doc'))) {
        const rel = node.getAttribute('data-dock-file-rel');
        const content = node.querySelector('.dock-doc-text, .dock-doc-markdown');
        return { owner: node, items: [
            uiContextMenuButton(node.querySelector('.dock-doc-refresh'), '刷新文件'),
            uiContextMenuButton(node.querySelector('.dock-doc-source-toggle')),
            content ? { label: '复制内容', action: () => uiContextMenuCopy(content.innerText) } : null,
            null, ...uiContextMenuFileItems(rel, uiContextMenuAbsolutePath(rel), false),
        ] };
    }
    if ((node = target.closest('.dock-files, .dock-changes'))) {
        return { owner: node, items: [uiContextMenuButton(node.querySelector('.dock-files-refresh, .dock-changes-refresh'), '刷新'),
            node.classList.contains('dock-files') ? { label: '复制路径', action: () => uiContextMenuCopy(node.querySelector('.dock-files-path').textContent) } : null] };
    }
    if ((node = target.closest('.change-review-file'))) {
        const path = node.querySelector('.change-review-path').textContent;
        return { owner: node, items: [
            uiContextMenuButton(node.querySelector('.change-review-file-toggle'), '查看改动'),
            { label: '复制路径', action: () => uiContextMenuCopy(path) },
        ] };
    }
    if ((node = target.closest('.change-review-card'))) {
        return { owner: node, items: [uiContextMenuButton(node.querySelector('.change-review-view'), '查看本轮改动')] };
    }
    if ((node = target.closest('.msg-wrap'))) {
        const role = node.classList.contains('msg-wrap--user') ? 'user' : 'assistant';
        const sessionId = currentSessionId;
        const running = isSessionRunning(sessionId);
        const items = [{ label: '复制消息', action: () => copyMessageText(node) }];
        if (role === 'assistant') items.push(
            { label: '导出文本', action: () => applyMessageCopyOption(node, role, 'text') },
            { label: '导出图片', action: () => applyMessageCopyOption(node, role, 'image') });
        items.push(null);
        ['rewrite', 'branch', 'delete'].forEach(action => {
            const button = node.querySelector('.msg-tb[data-act="' + action + '"]');
            if (!button) return;
            const item = uiContextMenuButton(button, action === 'delete' ? '删除本条及之后的对话' : null, action === 'delete');
            item.disabled = button.disabled || (running && action !== 'branch') || node.dataset.branching === '1';
            item.valid = () => node.isConnected && currentSessionId === sessionId && !button.disabled;
            items.push(item);
        });
        return { owner: node, items };
    }
    if ((node = target.closest('.feed-item, .process-aggregate'))) {
        const group = node.closest('.process-aggregate');
        return { owner: node, items: [
            { label: '复制执行内容', action: () => uiContextMenuCopy(node.classList.contains('feed-item') ? getFeedItemText(node)
                : Array.from(node.querySelectorAll('.feed-item')).map(getFeedItemText).join('\n\n')) },
            group ? { label: group.classList.contains('is-collapsed') ? '展开执行过程' : '折叠执行过程', action: () => group.querySelector('.process-aggregate-top').click() } : null,
        ] };
    }
    if ((node = target.closest('.execution-row'))) {
        return { owner: node, items: [...uiContextMenuButtons(node, 'button'),
            { label: '复制信息', action: () => uiContextMenuCopy(node.querySelector('span').textContent) }] };
    }
    if ((node = target.closest('.execution-dialog'))) {
        const output = node.querySelector('.execution-output');
        return { owner: node, items: [output ? { label: '复制输出', action: () => uiContextMenuCopy(output.textContent) } : null,
            ...uiContextMenuButtons(node, 'header button')] };
    }
    if ((node = target.closest('.chat-goal-card'))) {
        return { owner: node, items: [
            { label: '复制内容', action: () => uiContextMenuCopy(node.querySelector('.chat-goal-objective').textContent) },
            ...uiContextMenuButtons(node, '.chat-goal-actions button').map(item => ({ ...item, danger: /删除|Delete/.test(item.label) })),
        ] };
    }
    if ((node = target.closest('.todo-plan-item, .chat-todo-plan-panel'))) {
        const card = node.closest('.chat-todo-plan-panel');
        return { owner: node, items: [
            { label: '复制内容', action: () => uiContextMenuCopy(node.innerText) },
            card ? uiContextMenuButton(card.querySelector('.chat-todo-plan-close'), '清除计划', true) : null,
        ] };
    }
    if ((node = target.closest('.pni, .pubar-pane'))) {
        return { owner: node, items: [{ label: '复制内容', action: () => uiContextMenuCopy(node.innerText) },
            ...uiContextMenuButtons(node, '.pni-actions button')] };
    }
    if ((node = target.closest('#chat-toc'))) {
        const link = target.closest('a[data-event-index]');
        return { owner: node, items: [link ? { label: '跳转到此消息', action: () => link.click() } : null,
            link ? { label: '复制内容', action: () => uiContextMenuCopy(link.textContent) } : null,
            { label: '折叠历史面板', action: () => toggleTocPanel() }] };
    }
    if ((node = target.closest('#chat-todo-plan'))) {
        return { owner: node, items: [{ label: '折叠会话状态面板', action: () => toggleTodoPlanPanel() }] };
    }
    if ((node = target.closest('.sidebar'))) {
        return { owner: node, items: [
            { label: '新建会话', action: () => createNewSession() },
            { label: '在当前工作目录新建会话', action: () => startNewSessionInCurrentDir() },
            { label: '刷新会话列表', action: () => loadSessions({ forceRender: true }) },
        ] };
    }
    if ((node = target.closest('.chat-container'))) {
        return { owner: node, items: [{ label: '回到最新消息', action: () => scrollToBottom({ smooth: true }) },
            { label: '展开 / 折叠历史面板', action: () => toggleTocPanel() },
            { label: '展开 / 折叠会话状态面板', action: () => toggleTodoPlanPanel() }] };
    }
    return null;
}

function uiContextMenuResolve(event) {
    const target = event.target && event.target.closest ? event.target : event.target && event.target.parentElement;
    if (!target || event.defaultPrevented || target.closest('.ui-context-menu')) return false;
    // Plugin providers take precedence, including xterm's hidden textarea.
    for (let node = target; node; node = node.parentElement) {
        const provider = uiContextMenuBindings.get(node);
        if (provider) return uiContextMenuOpen(event, provider(event), node);
    }
    // Chromium/Electron owns editing, undo history, password fields and file paste.
    if (target.closest('input, textarea, select, [contenteditable]:not([contenteditable="false"])')) return false;
    // Native image menus supply copy/save without a clipboard IPC bridge.
    if (target.closest('img')) return false;
    const resolved = uiContextMenuWorkbenchItems(target);
    const items = [];
    const selection = String(window.getSelection() || '');
    if (selection.trim()) items.push({ label: '复制选中文本', action: () => uiContextMenuCopy(selection) });
    const code = target.closest('pre code');
    if (code) items.push({ label: '复制代码', action: () => uiContextMenuCopy(code.textContent) });
    const link = target.closest('a[href]');
    if (link && !link.matches('.msg-link-workspace-open, [data-event-index]') && /^https?:$/i.test(new URL(link.href, location.href).protocol)) {
        const href = link.href;
        items.push({ label: '打开链接', action: () => {
            if (window.sugarAgentDesktop) return window.sugarAgentDesktop.openExternal(href);
            window.open(href, '_blank', 'noopener,noreferrer');
        } }, { label: '复制链接地址', action: () => uiContextMenuCopy(href) });
    }
    if (items.length && resolved) items.push(null);
    if (resolved) items.push(...resolved.items);
    return uiContextMenuOpen(event, items, resolved ? resolved.owner : target);
}

globalThis.MyAgentContextMenu = {
    open: uiContextMenuOpen, close: uiContextMenuClose, copy: uiContextMenuCopy,
    isOpenFor: element => !!(uiContextMenuActive && element.contains(uiContextMenuActive.owner)),
    bind: (element, provider) => {
        uiContextMenuBindings.set(element, provider);
        return () => { uiContextMenuBindings.delete(element); if (uiContextMenuActive && uiContextMenuActive.owner === element) uiContextMenuClose(false); };
    },
};
document.addEventListener('contextmenu', uiContextMenuResolve);
document.addEventListener('pointerdown', event => {
    if (uiContextMenuActive && !uiContextMenuActive.menu.contains(event.target)) uiContextMenuClose(false);
}, true);
document.addEventListener('keydown', event => {
    if (uiContextMenuActive && event.key === 'Escape') {
        event.preventDefault(); event.stopImmediatePropagation(); uiContextMenuClose(true);
    } else if (event.key === 'ContextMenu' || (event.shiftKey && event.key === 'F10')) {
        uiContextMenuResolve(event);
    }
}, true);
document.addEventListener('scroll', event => {
    const active = uiContextMenuActive;
    if (!active || active.menu.contains(event.target)) return;
    const node = event.target === document ? document.scrollingElement : event.target;
    const initial = active.scrollPositions.get(event.target);
    // Focus/right-click can queue a scroll event before the menu opens.
    if (initial && node && node.scrollLeft === initial[0] && node.scrollTop === initial[1]) return;
    uiContextMenuClose(false);
}, true);
window.addEventListener('resize', () => {
    if (uiContextMenuActive && (uiContextMenuActive.width !== window.innerWidth || uiContextMenuActive.height !== window.innerHeight)) uiContextMenuClose(false);
});
window.addEventListener('blur', () => uiContextMenuClose(false));
document.addEventListener('myagent:language-change', () => uiContextMenuClose(false));
