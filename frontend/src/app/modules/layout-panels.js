newSessionBtn.addEventListener('click', async () => { await createNewSession(); });

var chatOverlayScrollbarRaf = null;
var chatOverlayScrollbarResizeObserver = null;
var chatOverlayScrollbarMutationObserver = null;
var chatOverlayScrollbarPortal = null;
var chatOverlayScrollbarStates = new Map();
var CHAT_OVERLAY_SCROLL_TARGET_SELECTOR = [
    '#chat-container',
    '.chat-toc-list',
    '.chat-todo-plan-list',
    '.process-aggregate-brief',
    '.process-aggregate-body',
    '.subagent-grid',
    '.subagent-card-body',
    '.subagent-output-panel',
    '.subagent-block-body',
    '.feed-chunk-scroller',
    '.followup-queue-panel',
    '.skill-picker-popover',
    '.composer-model-menu',
    '.subagent-card-summary'
].join(',');

function computeChatOverlayScrollbarGeometry(viewportHeight, scrollHeight, scrollTop) {
    var height = Math.max(0, Number(viewportHeight) || 0);
    var total = Math.max(0, Number(scrollHeight) || 0);
    var maxScroll = Math.max(0, total - height);
    if (!height || maxScroll <= 1) return null;
    return {
        trackHeight: height,
        spacerHeight: total,
        scrollTop: Math.max(0, Math.min(maxScroll, Number(scrollTop) || 0))
    };
}

function ensureChatOverlayScrollbarPortal() {
    if (chatOverlayScrollbarPortal && chatOverlayScrollbarPortal.isConnected) {
        return chatOverlayScrollbarPortal;
    }
    var main = document.querySelector('.main');
    if (!main) return null;
    var portal = document.createElement('div');
    portal.id = 'chat-overlay-scrollbars';
    portal.className = 'chat-overlay-scrollbars';
    portal.setAttribute('aria-hidden', 'true');
    main.appendChild(portal);
    chatOverlayScrollbarPortal = portal;
    return portal;
}

function syncChatOverlayScrollbarVisibility(state) {
    if (!state || !state.track) return;
    state.track.classList.toggle(
        'is-visible',
        !!(state.hovered || state.trackHovered || state.focused)
    );
}

function getChatOverlayScrollbarClip(target, main, targetTop, targetBottom) {
    var mainRect = main.getBoundingClientRect();
    var clipTop = Math.max(0, mainRect.top);
    var clipBottom = Math.min(
        Number(window.innerHeight) || mainRect.bottom,
        mainRect.bottom
    );
    var parent = target.parentElement;
    while (parent && parent !== main) {
        var style = window.getComputedStyle(parent);
        if (/(auto|scroll|overlay|hidden|clip)/.test(String(style.overflowY || ''))) {
            var rect = parent.getBoundingClientRect();
            var top = rect.top + Math.max(0, Number(parent.clientTop) || 0);
            clipTop = Math.max(clipTop, top);
            clipBottom = Math.min(
                clipBottom,
                top + Math.max(0, Number(parent.clientHeight) || 0)
            );
        }
        parent = parent.parentElement;
    }
    return {
        top: Math.max(targetTop, clipTop),
        bottom: Math.min(targetBottom, clipBottom)
    };
}

function updateChatOverlayScrollbarState(state) {
    if (!state || !state.target || !state.target.isConnected) return;
    var main = document.querySelector('.main');
    var portal = ensureChatOverlayScrollbarPortal();
    if (!main || !portal) return;
    var target = state.target;
    var geometry = computeChatOverlayScrollbarGeometry(
        target.clientHeight,
        target.scrollHeight,
        target.scrollTop
    );
    var targetRect = target.getBoundingClientRect();
    var mainRect = main.getBoundingClientRect();
    var targetTop = targetRect.top + Math.max(0, Number(target.clientTop) || 0);
    var rightInset = Math.max(
        0,
        (Number(target.offsetWidth) || targetRect.width)
            - (Number(target.clientWidth) || targetRect.width)
            - (Number(target.clientLeft) || 0)
    );
    var targetRight = targetRect.right - rightInset;
    var targetBottom = targetTop + Math.max(0, Number(target.clientHeight) || 0);
    var clip = getChatOverlayScrollbarClip(target, main, targetTop, targetBottom);
    var outsideMain = clip.bottom <= clip.top
        || targetRight <= mainRect.left
        || targetRect.left >= mainRect.right;
    if (!geometry || outsideMain || targetRect.width <= 0) {
        state.track.hidden = true;
        state.space.style.height = '0px';
        return;
    }
    state.track.hidden = false;
    state.track.style.left = Math.round(targetRight - mainRect.left - 3) + 'px';
    state.track.style.top = Math.round(targetTop - mainRect.top) + 'px';
    state.track.style.height = Math.round(geometry.trackHeight) + 'px';
    state.track.style.clipPath = 'inset('
        + Math.max(0, clip.top - targetTop) + 'px 0 '
        + Math.max(0, targetBottom - clip.bottom) + 'px 0)';
    state.space.style.height = geometry.spacerHeight + 'px';
    if (Math.abs(state.track.scrollTop - geometry.scrollTop) > 0.5) {
        state.track.scrollTop = geometry.scrollTop;
    }
    syncChatOverlayScrollbarVisibility(state);
}

function updateAllChatOverlayScrollbars() {
    chatOverlayScrollbarStates.forEach(function (state) {
        updateChatOverlayScrollbarState(state);
    });
}

function scheduleChatOverlayScrollbarUpdate() {
    if (chatOverlayScrollbarRaf != null) return;
    chatOverlayScrollbarRaf = requestAnimationFrame(function () {
        chatOverlayScrollbarRaf = null;
        updateAllChatOverlayScrollbars();
    });
}

function unregisterChatOverlayScrollbarTarget(target) {
    var state = chatOverlayScrollbarStates.get(target);
    if (!state) return;
    target.removeEventListener('scroll', state.onScroll);
    target.removeEventListener('pointerenter', state.onPointerEnter);
    target.removeEventListener('pointerleave', state.onPointerLeave);
    target.removeEventListener('focusin', state.onFocusIn);
    target.removeEventListener('focusout', state.onFocusOut);
    state.track.removeEventListener('scroll', state.onTrackScroll);
    target.classList.remove('chat-overlay-scroll-target');
    if (chatOverlayScrollbarResizeObserver) chatOverlayScrollbarResizeObserver.unobserve(target);
    if (state.track && state.track.parentNode) state.track.parentNode.removeChild(state.track);
    chatOverlayScrollbarStates.delete(target);
}

function registerChatOverlayScrollbarTarget(target) {
    if (!target || chatOverlayScrollbarStates.has(target)) return;
    var portal = ensureChatOverlayScrollbarPortal();
    if (!portal) return;
    var track = document.createElement('div');
    track.className = 'chat-overlay-scrollbar';
    track.hidden = true;
    var space = document.createElement('div');
    space.className = 'chat-overlay-scrollbar-space';
    track.appendChild(space);
    portal.appendChild(track);
    var state = {
        target: target,
        track: track,
        space: space,
        hovered: false,
        trackHovered: false,
        focused: false
    };
    state.onScroll = function () {
        scheduleChatOverlayScrollbarUpdate();
    };
    state.onPointerEnter = function () {
        state.hovered = true;
        syncChatOverlayScrollbarVisibility(state);
        scheduleChatOverlayScrollbarUpdate();
    };
    state.onPointerLeave = function () {
        state.hovered = false;
        syncChatOverlayScrollbarVisibility(state);
    };
    state.onFocusIn = function () {
        state.focused = true;
        syncChatOverlayScrollbarVisibility(state);
    };
    state.onFocusOut = function () {
        state.focused = target.contains(document.activeElement);
        syncChatOverlayScrollbarVisibility(state);
    };
    track.addEventListener('pointerenter', function () {
        state.trackHovered = true;
        syncChatOverlayScrollbarVisibility(state);
    });
    track.addEventListener('pointerleave', function () {
        state.trackHovered = false;
        syncChatOverlayScrollbarVisibility(state);
    });
    state.onTrackScroll = function () {
        if (Math.abs(target.scrollTop - track.scrollTop) > 0.5) {
            target.scrollTop = track.scrollTop;
        }
        scheduleChatOverlayScrollbarUpdate();
    };
    track.addEventListener('scroll', state.onTrackScroll, { passive: true });
    target.classList.add('chat-overlay-scroll-target');
    target.addEventListener('scroll', state.onScroll, { passive: true });
    target.addEventListener('pointerenter', state.onPointerEnter);
    target.addEventListener('pointerleave', state.onPointerLeave);
    target.addEventListener('focusin', state.onFocusIn);
    target.addEventListener('focusout', state.onFocusOut);
    chatOverlayScrollbarStates.set(target, state);
    if (chatOverlayScrollbarResizeObserver) chatOverlayScrollbarResizeObserver.observe(target);
    updateChatOverlayScrollbarState(state);
}

function discoverChatOverlayScrollbarTargets() {
    var root = document.querySelector('.main-center');
    if (!root) return;
    var current = new Set(root.querySelectorAll(CHAT_OVERLAY_SCROLL_TARGET_SELECTOR));
    chatOverlayScrollbarStates.forEach(function (_state, target) {
        if (!target.isConnected || !current.has(target)) {
            unregisterChatOverlayScrollbarTarget(target);
        }
    });
    current.forEach(registerChatOverlayScrollbarTarget);
    scheduleChatOverlayScrollbarUpdate();
}

function initChatOverlayScrollbar() {
    var root = document.querySelector('.main-center');
    if (!root || chatOverlayScrollbarMutationObserver) return;
    ensureChatOverlayScrollbarPortal();
    chatOverlayScrollbarResizeObserver = new ResizeObserver(function () {
        scheduleChatOverlayScrollbarUpdate();
    });
    chatOverlayScrollbarMutationObserver = new MutationObserver(function () {
        discoverChatOverlayScrollbarTargets();
    });
    chatOverlayScrollbarMutationObserver.observe(root, {
        childList: true,
        subtree: true,
        attributes: true,
        attributeFilter: ['class', 'hidden'],
        characterData: true
    });
    window.addEventListener('resize', scheduleChatOverlayScrollbarUpdate, { passive: true });
    window.addEventListener('load', scheduleChatOverlayScrollbarUpdate, { passive: true });
    discoverChatOverlayScrollbarTargets();
}

function initSidebarSash() {
    const side = document.getElementById('sidebar');
    const sash = document.getElementById('sash');
    if (!side || !sash) return;
    const KEY = 'sidebar-width-px';
    function clampW(n) {
        const max = Math.min(480, Math.floor(window.innerWidth * 0.5));
        return Math.max(120, Math.min(max, n));
    }
    const saved = localStorage.getItem(KEY);
    if (saved) { const w = parseInt(saved, 10); if (!isNaN(w)) side.style.width = clampW(w) + 'px'; }
    let startX = 0, startW = 0;
    function onMouseMove(e) { side.style.width = clampW(startW + e.clientX - startX) + 'px'; }
    function onMouseUp() {
        sash.classList.remove('is-dragging');
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
        document.removeEventListener('mousemove', onMouseMove);
        document.removeEventListener('mouseup', onMouseUp);
        localStorage.setItem(KEY, String(Math.round(side.getBoundingClientRect().width)));
    }
    sash.addEventListener('mousedown', function (e) {
        e.preventDefault();
        startX = e.clientX;
        startW = side.getBoundingClientRect().width;
        sash.classList.add('is-dragging');
        document.body.style.cursor = 'col-resize';
        document.body.style.userSelect = 'none';
        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', onMouseUp);
    });
}

async function init() {
    loadUnreadFromStorage();
    initSidebarSash();
    showLoading();
    const sessionsLoaded = await loadSessions();
    const sessions = sessionStore.list();
    let lastSessionId = localStorage.getItem('lastSessionId');
    let targetSession = null;
    if (lastSessionId && sessions.some(s => s.id === lastSessionId)) targetSession = lastSessionId;
    else if (!sessionsLoaded && lastSessionId) targetSession = lastSessionId;
    else if (sessions.length > 0) targetSession = sessions[0].id;
    if (targetSession) await switchSession(targetSession);
    else await createNewSession();
    bindExistingLogs();
}
init();
function toggleTocPanel() {
    panelWasAutoCollapsed = false;
    const toc = document.getElementById('chat-toc');
    if (!toc) return;
    toc.classList.toggle('is-open');
    syncEdgeTabArrows();
    schedulePanelEdgeTabsLayout();
}

function toggleTodoPlanPanel() {
    panelWasAutoCollapsed = false;
    const root = document.getElementById('chat-todo-plan');
    if (!root) return;
    root.classList.toggle('is-open');
    syncEdgeTabArrows();
    schedulePanelEdgeTabsLayout();
}

function syncEdgeTabArrows() {
    const toc = document.getElementById('chat-toc');
    const todo = document.getElementById('chat-todo-plan');
    const tocTab = document.getElementById('toc-edge-tab');
    const todoTab = document.getElementById('todo-edge-tab');
    if (tocTab && toc) {
        tocTab.textContent = toc.classList.contains('is-open') ? '▶' : '◀';
    }
    if (todoTab && todo) {
        todoTab.textContent = todo.classList.contains('is-open') ? '◀' : '▶';
    }
}

function updatePanelToggles() {
    const tocList = document.getElementById('chat-toc-list');
    const todoList = document.getElementById('chat-todo-plan-list');
    const tocTab = document.getElementById('toc-edge-tab');
    const todoTab = document.getElementById('todo-edge-tab');
    if (tocTab) tocTab.classList.toggle('visible', !!(tocList && tocList.children.length));
    if (todoTab) todoTab.classList.toggle('visible', !!(todoList && todoList.children.length));
    syncEdgeTabArrows();
    schedulePanelEdgeTabsLayout();
}

function notifyPanelContentChanged() {
    if (typeof updatePanelToggles !== 'function') return;
    updatePanelToggles();
    if (typeof runPanelAutoCollapseCheck === 'function') {
        requestAnimationFrame(function () {
            runPanelAutoCollapseCheck();
            schedulePanelEdgeTabsLayout();
        });
    }
}

/* 折叠三角挂在 stage 外层面，对齐面板边缘（收起后只剩按钮，不被 aside 裁切） */
var panelEdgeTabsObserver = null;
var panelEdgeTabsRaf = null;
function layoutPanelEdgeTabs() {
    var stage = document.querySelector('.chat-stage');
    var todo = document.getElementById('chat-todo-plan');
    var toc = document.getElementById('chat-toc');
    var todoTab = document.getElementById('todo-edge-tab');
    var tocTab = document.getElementById('toc-edge-tab');
    if (!stage || !todoTab || !tocTab) return;
    var sr = stage.getBoundingClientRect();
    todoTab.style.top = '50%';
    tocTab.style.top = '50%';
    /* Todo：仅用 left，与 CSS 一致（贴在面板右缘） */
    todoTab.style.right = 'auto';
    if (todo) {
        var tr = todo.getBoundingClientRect();
        todoTab.style.left = (tr.right - sr.left) + 'px';
    }
    /* TOC：仅用 right，勿写 left（否则与样式表里 right 并存导致错位 / hover 异常） */
    tocTab.style.left = 'auto';
    if (toc) {
        var cr = toc.getBoundingClientRect();
        tocTab.style.right = (sr.right - cr.left) + 'px';
    }
}

function schedulePanelEdgeTabsLayout() {
    if (panelEdgeTabsRaf != null) return;
    panelEdgeTabsRaf = requestAnimationFrame(function () {
        panelEdgeTabsRaf = null;
        layoutPanelEdgeTabs();
    });
}

function initPanelEdgeTabsLayout() {
    var stage = document.querySelector('.chat-stage');
    var todo = document.getElementById('chat-todo-plan');
    var toc = document.getElementById('chat-toc');
    if (!stage || panelEdgeTabsObserver) return;
    panelEdgeTabsObserver = new ResizeObserver(schedulePanelEdgeTabsLayout);
    panelEdgeTabsObserver.observe(stage);
    if (todo) panelEdgeTabsObserver.observe(todo);
    if (toc) panelEdgeTabsObserver.observe(toc);
    schedulePanelEdgeTabsLayout();
}

/* 自动折叠：约在 750–805px 档就要收起；正文占比不足也收起；显著变宽后再展开（滞回 + 冷却） */
var panelAutoCollapseObserver = null;
var panelCollapseRaf = null;
var panelAutoCollapseCooldownUntil = 0;
var panelWasAutoCollapsed = false;

function runPanelAutoCollapseCheck() {
    var mainEl = document.querySelector('.main');
    var stage = document.querySelector('.chat-stage');
    if (!mainEl || !stage) return;
    var mainW = mainEl.clientWidth;
    var stageW = stage.clientWidth;
    var layoutW = Math.min(mainW, stageW);
    var todo = document.getElementById('chat-todo-plan');
    var toc = document.getElementById('chat-toc');
    var tocList = document.getElementById('chat-toc-list');
    var todoList = document.getElementById('chat-todo-plan-list');
    var now = (typeof performance !== 'undefined' && performance.now) ? performance.now() : Date.now();

    var LAYOUT_COLLAPSE_AT = 805;
    var LAYOUT_EXPAND_AT = 940;

    if (panelWasAutoCollapsed && now >= panelAutoCollapseCooldownUntil && layoutW >= LAYOUT_EXPAND_AT) {
        panelWasAutoCollapsed = false;
        if (toc && tocList && tocList.children.length && !toc.classList.contains('is-open')) toc.classList.add('is-open');
        if (todo && todoList && todoList.children.length && !todo.classList.contains('is-open')) todo.classList.add('is-open');
        syncEdgeTabArrows();
        return;
    }

    var todoOpen = todo && todo.classList.contains('is-open');
    var tocOpen = toc && toc.classList.contains('is-open');
    if (!todoOpen && !tocOpen) return;

    var todoW = todoOpen ? todo.offsetWidth : 0;
    var tocW = tocOpen ? toc.offsetWidth : 0;
    var centerW = layoutW - todoW - tocW;
    var minCenterByRatio = Math.max(400, Math.floor(layoutW * 0.52));
    var layoutTooNarrow = layoutW <= LAYOUT_COLLAPSE_AT;
    var centerTooTight = centerW < minCenterByRatio;

    if (layoutTooNarrow || centerTooTight) {
        var did = false;
        if (tocOpen) { toc.classList.remove('is-open'); did = true; }
        if (todoOpen) { todo.classList.remove('is-open'); did = true; }
        if (did) {
            panelWasAutoCollapsed = true;
            panelAutoCollapseCooldownUntil = now + 420;
            syncEdgeTabArrows();
        }
    }
}

function initPanelAutoCollapse() {
    var mainEl = document.querySelector('.main');
    var stage = document.querySelector('.chat-stage');
    if (!mainEl || !stage || panelAutoCollapseObserver) return;
    function schedule() {
        if (panelCollapseRaf != null) return;
        panelCollapseRaf = requestAnimationFrame(function () {
            panelCollapseRaf = null;
            runPanelAutoCollapseCheck();
        });
    }
    panelAutoCollapseObserver = new ResizeObserver(schedule);
    panelAutoCollapseObserver.observe(mainEl);
    panelAutoCollapseObserver.observe(stage);
}

initPanelAutoCollapse();
initPanelEdgeTabsLayout();
initChatOverlayScrollbar();

// Inline HTML (onclick) still expects these on globalThis.
if (typeof globalThis !== 'undefined') {
    globalThis.clearTodoPlan = clearTodoPlan;
    globalThis.toggleTodoPlanPanel = toggleTodoPlanPanel;
    globalThis.toggleTocPanel = toggleTocPanel;
}
