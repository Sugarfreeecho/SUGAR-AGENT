/**
 * The right details column: dsh's third column, built on the same dock engine
 * and renderer as the main split view.
 *
 * dsh divides the page into three parts — the session list on the left, the
 * conversation in the middle, and a details column on the right that opens from
 * a button at the conversation header's top-right corner and shows the file
 * tree, document previews, and file-change history. This module is that column:
 *
 *   - it mounts a dock surface in an area of its own (`right`), so its layouts
 *     are per session and completely separate from the main split view's;
 *   - it pushes the workspace (the column takes width; the conversation gives
 *     it up) and covers the viewport in fullscreen, which narrow screens use;
 *   - it ships three built-in page types, plus resource viewers:
 *       `files`     — the workspace tree            (/api/workspace-files)
 *       `document`  — one file's content           (images/media/text via the
 *                                                    workspace endpoints)
 *       `changes`   — the session's file changes   (the `ui.changes` payloads
 *                                                    already in the session's
 *                                                    history, with the same
 *                                                    undo/restore routes the
 *                                                    Change Review plugin uses)
 *   - opening a file from the tree lands in a `document` tab, exactly as dsh's
 *     tree opens `dsh-resource://file/…` addresses in its preview types.
 *
 * The column's width is draggable and remembered per browser; its surfaces stay
 * memory-only like dsh's.
 */

/** The area id this column's surfaces live under. */
const DOCK_RIGHT_AREA = 'right';

/** localStorage key for the column width. */
const DOCK_RIGHT_WIDTH_KEY = 'myagent-dock-rightbar-width';

/** Default column width in pixels. */
const DOCK_RIGHT_WIDTH_DEFAULT = 460;

/** Smallest and largest column widths in pixels. */
const DOCK_RIGHT_WIDTH_MIN = 320;
const DOCK_RIGHT_WIDTH_MAX = 960;

/** An expanded column must leave the workspace at least this many pixels of
    usable width; a narrower window keeps the column collapsed instead
    (feedback: a half-screen snap must not squeeze the workspace into a sliver). */
const DOCK_RIGHT_WORKSPACE_FLOOR = 560;

/** How much of the session history the change list scans, in pages of 500 events. */
const DOCK_RIGHT_CHANGE_PAGE_LIMIT = 500;
const DOCK_RIGHT_CHANGE_PAGE_MAX = 8;

/** Address prefix resource viewers claim. */
const DOCK_RIGHT_FILE_PREFIX = 'myagent-resource://file/';

/** Text reads are capped here; the endpoint truncates and says so. */
const DOCK_RIGHT_TEXT_MAX_BYTES = 200000;

/** The dsh-style refresh glyph (28px circle, 15px arrow) used by every page head. */
const DOCK_ICON_REFRESH = '<svg viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="M13.2 8a5.2 5.2 0 1 1-1.62-3.76" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" fill="none"/><path d="M13.4 2.6v3.1h-3.1" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" fill="none"/></svg>';

/** Session-overview glyph, verbatim from dsh `ui-primitives` `IconChecklistOutline14`. */
const DOCK_ICON_OVERVIEW = '<svg viewBox="0 0 14 14" fill="none" aria-hidden="true"><path d="M13.3277 9.69629V10.976H7.28086V9.69629H13.3277Z" fill="currentColor"/><path d="M13.3277 2.97256V4.25225H7.28086V2.97256H13.3277Z" fill="currentColor"/><path d="M4.64512 10.336C4.64505 9.62755 4.07081 9.05322 3.3623 9.05322C2.65386 9.05329 2.07956 9.62759 2.07949 10.336C2.07949 11.0445 2.65382 11.6188 3.3623 11.6188C4.07085 11.6188 4.64512 11.0446 4.64512 10.336ZM5.92559 10.336C5.92559 11.7515 4.77777 12.8993 3.3623 12.8993C1.94689 12.8993 0.799805 11.7515 0.799805 10.336C0.799871 8.92066 1.94693 7.7736 3.3623 7.77354C4.77773 7.77354 5.92552 8.92062 5.92559 10.336Z" fill="currentColor"/><path d="M4.64531 3.6123C4.6453 2.90382 4.07098 2.32949 3.3625 2.32949C2.65403 2.32951 2.0797 2.90383 2.07969 3.6123C2.07969 4.32079 2.65402 4.8951 3.3625 4.89512C4.07099 4.89512 4.64531 4.3208 4.64531 3.6123ZM5.925 3.6123C5.925 5.02772 4.77792 6.1748 3.3625 6.1748C1.9471 6.17479 0.8 5.02771 0.8 3.6123C0.800013 2.19691 1.9471 1.04982 3.3625 1.0498C4.77791 1.0498 5.92499 2.1969 5.925 3.6123Z" fill="currentColor"/></svg>';

/** Reveal-in-folder glyph, verbatim from dsh `ui-primitives` `IconFolderOpenOutline16`. */
const DOCK_ICON_REVEAL = '<svg viewBox="0 0 16 16" fill="none" aria-hidden="true"><path fill="currentColor" d="M5.19629 1.57104C5.81144 1.5711 6.38623 1.8786 6.72754 2.39038L7.19922 3.09839C7.28454 3.22635 7.42824 3.30344 7.58203 3.30347H12.1699C13.5039 3.30348 14.5859 4.38548 14.5859 5.71948V6.62671C15.2694 7.02689 15.6605 7.85012 15.4385 8.68726L14.3848 12.658C14.1037 13.7164 13.1449 14.4527 12.0498 14.4529H2.91699C1.51651 14.4529 0.451662 13.2814 0.501954 11.9519V3.98706C0.501954 2.65305 1.58396 1.57104 2.91797 1.57104H5.19629ZM3.7793 7.75562C3.30994 7.75562 2.89883 8.07153 2.77832 8.52515L1.91602 11.7722C1.74167 12.4291 2.23734 13.073 2.91699 13.073H12.0498C12.5191 13.0728 12.9304 12.757 13.0508 12.3035L14.1045 8.33374C14.1819 8.04202 13.9619 7.756 13.6602 7.75562H3.7793ZM2.91797 2.9519C2.34625 2.9519 1.88281 3.41534 1.88281 3.98706V7.2937C2.33068 6.7269 3.02249 6.37476 3.7793 6.37476H13.2051V5.71948C13.2051 5.14777 12.7416 4.68434 12.1699 4.68433H7.58203C6.96675 4.6843 6.39209 4.37595 6.05078 3.86401L5.5791 3.15601C5.49379 3.02821 5.34995 2.95196 5.19629 2.9519H2.91797Z"/></svg>';

/** Suffixes rendered as an inline image. Mirrors the backend's viewable image set. */
const DOCK_RIGHT_IMAGE_SUFFIXES = ['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'svg', 'ico', 'avif', 'jfif', 'tif', 'tiff'];

/** Suffixes rendered with a media element. */
const DOCK_RIGHT_AUDIO_SUFFIXES = ['mp3', 'wav', 'ogg', 'oga', 'm4a', 'aac', 'flac', 'opus', 'weba'];
const DOCK_RIGHT_VIDEO_SUFFIXES = ['mp4', 'webm', 'ogv', 'mov', 'm4v', 'mkv'];

/** Suffixes rendered as a sandboxed web page (with a source toggle). */
const DOCK_RIGHT_HTML_SUFFIXES = ['html', 'htm'];

/** Suffixes rendered as a document (rich markdown, with a source toggle). */
const DOCK_RIGHT_MD_SUFFIXES = ['md', 'markdown'];

/** Suffixes that go straight to the system app: never read as text (feedback #5). */
const DOCK_RIGHT_BINARY_SUFFIXES = ['pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'odt', 'ods', 'epub', 'zip', '7z', 'rar', 'gz', 'tar', 'exe', 'msi', 'dll', 'so', 'dylib', 'bin', 'pyc', 'class', 'jar', 'woff', 'woff2', 'ttf', 'otf', 'eot', 'db', 'sqlite', 'mp3', 'wav', 'flac', 'aac', 'ogg', 'mp4', 'mov', 'mkv', 'avi'];

/** The column's private state. */
const dockRightState = {
    host: null,
    sash: null,
    surface: null,
    floats: null,
    button: null,
    sessionId: null,
    width: DOCK_RIGHT_WIDTH_DEFAULT,
    tabState: Object.create(null),
    dragging: false,
    revealFrame: null,
};

/** Plugin-fed child-agent rows and pending deep links, retained even before the page opens. */
const dockRightChangeReviewRows = new Map();
const dockRightChangeReviewFocus = new Map();

/** The column's rendered strings; the i18n observer translates them in English. */
function dockRightLabels() {
    return {
        toggle: '详情栏',
        open: '打开侧边栏',
        openAria: '打开右侧边栏',
        close: '收起侧边栏',
        fullscreen: '全屏显示',
        exitFullscreen: '退出全屏',
        guide: '开始',
        guideFiles: '工作区文件',
        guideFilesDesc: '浏览会话工作区的文件',
        guideChanges: '修改历史',
        guideChangesDesc: '查看本会话的文件改动',
        newTab: '新建窗口',
        preview: '网页预览',
        viewSource: '查看源码',
        viewPreview: '预览网页',
        previewDoc: '预览文档',
        reveal: '打开文件目录',
        files: '工作区文件',
        document: '文件内容',
        changes: '修改历史',
        refresh: '刷新',
        openSystem: '在系统应用中打开',
        loading: '正在载入…',
        loadFailed: '载入失败',
        emptyDir: '（空目录）',
        emptyChanges: '本会话暂无文件改动',
        emptyTurnChanges: '本轮暂无文件改动',
        scopeSession: '会话总览',
        turnFallback: '未命名提问',
        noLineStats: '未统计行数',
        undoAll: '全部撤销',
        restoreAll: '全部恢复',
        undoing: '正在撤销…',
        restoring: '正在恢复…',
        allUndone: '已全部撤销',
        allRestored: '已全部恢复',
        taskRunningReview: '任务和子任务全部结束后才可撤销或恢复',
        unsupported: '此文件类型暂不支持内嵌预览，可在系统应用中打开。',
        textUnavailable: '文本接口尚不可用（需重启服务加载新接口），可在系统应用中打开。',
        truncated: '文本过长，仅显示前 200 KB。',
        undo: '撤销',
        restore: '恢复',
        undone: '已撤销',
        restored: '已恢复',
        fileSize: '大小',
        diff: '差分',
        added: '新增',
        removed: '删除',
        modified: '修改',
        renamed: '重命名',
    };
}

/** The labels the surface/float renderers read (split, chips, drop zones). */
function dockRightSurfaceLabels() {
    return {
        emptyPane: '此面板暂无内容',
        splitPane: '左右分屏',
        splitPaneDisabled: '分栏数量已达上限',
        splitPaneNarrow: '栏宽不足，拖宽侧边栏后再分栏',
        // Exact dsh glyph (dock frame with the divider at its centre).
        splitIconSVG: DOCK_ICON_SPLIT,
        closeTab: '关闭标签',
        addTab: '新建窗口',
        duplicateTab: '复制标签',
        dockFloat: '收回到侧边栏',
        closeFloat: '关闭浮窗',
        dropZone: { center: '移入此面板', left: '分屏到左侧', right: '分屏到右侧' },
    };
}

/** One label. */
function dockRightText(key) {
    const labels = dockRightLabels();
    return labels[key] || key;
}

/** The suffix of a path, lower-case and without the dot. */
function dockRightSuffix(path) {
    const text = String(path || '');
    const index = text.lastIndexOf('.');
    if (index < 0 || index === text.length - 1) return '';
    return text.slice(index + 1).toLowerCase();
}

/** A human size. */
function dockRightSize(bytes) {
    const value = Number(bytes);
    if (!Number.isFinite(value) || value < 0) return '';
    if (value < 1024) return value + ' B';
    if (value < 1024 * 1024) return (value / 1024).toFixed(1) + ' KB';
    if (value < 1024 * 1024 * 1024) return (value / (1024 * 1024)).toFixed(1) + ' MB';
    return (value / (1024 * 1024 * 1024)).toFixed(2) + ' GB';
}

/** The workspace-relative form of an absolute path, when it is inside the workspace. */
function dockRightRelPath(path) {
    const text = String(path || '');
    const marker = 'workspace' + (text.indexOf('\\') >= 0 ? '\\' : '/');
    const index = text.toLowerCase().lastIndexOf(marker.toLowerCase());
    if (index < 0) return text;
    return text.slice(index + marker.length).replace(/\\/g, '/');
}

/** The basename of a path. */
function dockRightBasename(path) {
    const text = String(path || '').replace(/\\/g, '/');
    const index = text.lastIndexOf('/');
    return index < 0 ? text : text.slice(index + 1);
}

/**
 * Remember one page's scroll position per tab, so switching tabs away and
 * back lands where the reader left it (feedback #4). The positions live in
 * the tab's state object, next to the body's other bookkeeping.
 */
function dockRightTrackScroll(tabId, el) {
    if (!el) return;
    const state = dockRightState.tabState[tabId] || (dockRightState.tabState[tabId] = {});
    const apply = () => {
        if (!state.scroll) return;
        el.scrollTop = state.scroll.y;
        el.scrollLeft = state.scroll.x;
    };
    // Re-attached by the surface on every commit that shows this body again:
    // the browser drops a detached scroller's position, so the body carries
    // its own restore hook (feedback #4).
    el.__dockRestore = apply;
    if (state.scroll) requestAnimationFrame(apply);
    el.addEventListener('scroll', () => {
        state.scroll = { x: el.scrollLeft, y: el.scrollTop };
    }, { passive: true });
}

/** A JSON fetch with its own deadline, so a stalled request cannot wedge a scan. */
async function dockRightFetchJSON(url, timeoutMs) {
    const controller = typeof AbortController === 'function' ? new AbortController() : null;
    const timer = setTimeout(() => {
        if (controller) {
            try { controller.abort(); } catch (error) { /* ignore */ }
        }
    }, Math.max(1000, Number(timeoutMs) || 15000));
    try {
        const response = await fetch(url, controller ? { signal: controller.signal } : undefined);
        let data = null;
        try { data = await response.json(); } catch (error) { data = null; }
        return { response: response, data: data };
    } finally {
        clearTimeout(timer);
    }
}

/** A small per-category glyph for the file tree, in dsh's spirit (feedback #6). */
function dockRightFileIcon(name) {
    const ext = dockRightSuffix(name);
    const groups = [
        { test: ['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'svg', 'ico', 'avif', 'jfif', 'tif', 'tiff'], color: '#61afef',
          body: '<rect x="2.5" y="3" width="11" height="10" rx="2" fill="none" stroke="currentColor" stroke-width="1.3"/><circle cx="6" cy="6.6" r="1.15" fill="currentColor"/><path d="M4 11.4l2.6-2.6 1.9 1.8 2.2-2.2 2.3 2.3" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>' },
        { test: ['js', 'mjs', 'cjs', 'ts', 'tsx', 'jsx', 'py', 'css', 'scss', 'html', 'htm', 'sh', 'ps1', 'bat', 'java', 'go', 'rs', 'c', 'cpp', 'h'], color: '#c678dd',
          body: '<path d="M6 4.2L3.2 8l2.8 3.8M10 4.2L12.8 8 10 11.8" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>' },
        { test: ['json', 'yaml', 'yml', 'toml', 'ini', 'cfg', 'lock'], color: '#e5c07b',
          body: '<path d="M6.4 3.4C4.9 3.4 5 5.4 5 6.6c0 1-1 1.2-1.4 1.4.4.2 1.4.4 1.4 1.4 0 1.2-.1 3.2 1.4 3.2M9.6 3.4c1.5 0 1.4 2 1.4 3.2 0 1 1 1.2 1.4 1.4-.4.2-1.4.4-1.4 1.4 0 1.2.1 3.2-1.4 3.2" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>' },
        { test: ['md', 'markdown', 'txt', 'rst', 'log', 'csv', 'tsv'], color: '#98c379',
          body: '<rect x="2.5" y="3" width="11" height="10" rx="2" fill="none" stroke="currentColor" stroke-width="1.3"/><path d="M5 6.2h6M5 8.4h6M5 10.6h3.6" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>' },
        { test: ['pdf'], color: '#e06c75',
          body: '<rect x="2.5" y="3" width="11" height="10" rx="2" fill="none" stroke="currentColor" stroke-width="1.3"/><path d="M5.2 11V5.4h2a1.6 1.6 0 010 3.2h-2" fill="none" stroke="currentColor" stroke-width="1.25" stroke-linecap="round" stroke-linejoin="round"/>' },
    ];
    let hit = groups.find((group) => group.test.indexOf(ext) >= 0);
    const color = hit ? hit.color : 'var(--text-tertiary)';
    const body = hit ? hit.body
        : '<path d="M4.6 2.8h4.2L12 6v7.2H4.6z" fill="none" stroke="currentColor" stroke-width="1.3"/><path d="M8.8 2.8V6H12" fill="none" stroke="currentColor" stroke-width="1.3"/>';
    return '<svg class="dock-files-icon" viewBox="0 0 16 16" aria-hidden="true" style="color:' + color + '">' + body + '</svg>';
}

/** The folder glyph for the tree's directories. */
const DOCK_FOLDER_ICON = '<svg class="dock-files-icon" viewBox="0 0 16 16" aria-hidden="true" style="color:#e5c07b"><path d="M2 4.2A1.2 1.2 0 013.2 3h2.9l1.4 1.5H13A1.2 1.2 0 0114.2 5.7v6.1A1.2 1.2 0 0113 13H3.2A1.2 1.2 0 012 11.8z" fill="currentColor" opacity="0.9"/></svg>';

/** The card a file that cannot be shown inline falls back to: open it in the system app. */
function dockRightSystemCard(rel) {
    const wrap = document.createElement('div');
    wrap.className = 'dock-doc-fallback';
    const note = document.createElement('div');
    note.className = 'dock-note';
    note.textContent = dockRightText('unsupported');
    const open = document.createElement('button');
    open.type = 'button';
    open.className = 'dock-link-button';
    open.textContent = dockRightText('openSystem');
    open.addEventListener('click', () => {
        void fetch('/api/open-workspace-file?' + new URLSearchParams({ rel: rel }));
    });
    wrap.appendChild(note);
    wrap.appendChild(open);
    return wrap;
}

/** Suffixes the column shows inline as text; everything else goes to the system app. */
const DOCK_RIGHT_TEXT_SUFFIXES = ['md', 'markdown', 'txt', 'log', 'csv', 'tsv', 'json', 'jsonl', 'yaml', 'yml', 'toml', 'ini', 'cfg', 'conf', 'env', 'py', 'js', 'mjs', 'cjs', 'ts', 'tsx', 'jsx', 'html', 'htm', 'css', 'scss', 'less', 'sql', 'sh', 'bash', 'zsh', 'bat', 'cmd', 'ps1', 'psm1', 'c', 'cc', 'cpp', 'h', 'hpp', 'java', 'go', 'rs', 'rb', 'php', 'pl', 'lua', 'r', 'swift', 'kt', 'gradle', 'gitignore', 'editorconfig'];

/** Whether a workspace path should open as text in the details column. */
function dockRightIsTextPath(path) {
    const suffix = dockRightSuffix(path);
    if (!suffix) return false;
    if (DOCK_RIGHT_BINARY_SUFFIXES.indexOf(suffix) >= 0) return false;
    if (DOCK_RIGHT_IMAGE_SUFFIXES.indexOf(suffix) >= 0) return false;
    if (DOCK_RIGHT_AUDIO_SUFFIXES.indexOf(suffix) >= 0 || DOCK_RIGHT_VIDEO_SUFFIXES.indexOf(suffix) >= 0) return false;
    return DOCK_RIGHT_TEXT_SUFFIXES.indexOf(suffix) >= 0;
}

/**
 * The shared "open a file" policy for the app: text opens in the details
 * column, everything else goes to the system app — the same rule the tree's
 * click follows. Session file links call this through `MyAgentDock`.
 */
function dockRightOpenPathSmart(pathValue) {
    const rel = String(pathValue || '');
    if (!rel) return;
    if (dockRightIsTextPath(rel)) {
        dockRightOpenResource(DOCK_RIGHT_FILE_PREFIX + encodeURIComponent(rel));
        return;
    }
    void fetch('/api/open-workspace-file?' + new URLSearchParams({ rel: rel }));
}

/** The seed thunk for this column: an emptied pane is backfilled with its "start" page. */
function dockRightSeed() {
    return () => ({ kind: 'guide', contentId: dockPageAddress('guide'), title: dockRightText('guide') });
}

// ── mount ────────────────────────────────────────────────────────────────────

/** Build the column's DOM and views; idempotent. */
function dockRightEnsureMounted() {
    if (dockRightState.host) return;
    const app = document.querySelector('.app');
    const main = document.querySelector('.main');
    if (!app || !main) return;

    const host = document.createElement('aside');
    host.className = 'dock-rightbar is-collapsed';
    host.setAttribute('data-dock-rightbar', '1');
    host.setAttribute('aria-label', dockRightText('toggle'));
    host.setAttribute('aria-hidden', 'true');
    host.inert = true;
    host.style.setProperty('--dock-rightbar-width', dockRightState.width + 'px');

    const sash = document.createElement('div');
    sash.className = 'dock-rightbar-sash';
    sash.setAttribute('role', 'separator');
    sash.setAttribute('aria-orientation', 'vertical');
    sash.setAttribute('aria-label', '拖动调整详情栏宽度');
    sash.addEventListener('pointerdown', (event) => dockRightStartResize(event));
    sash.addEventListener('dblclick', () => {
        dockRightState.width = DOCK_RIGHT_WIDTH_DEFAULT;
        dockRightApplyWidth();
        try { localStorage.setItem(DOCK_RIGHT_WIDTH_KEY, String(DOCK_RIGHT_WIDTH_DEFAULT)); } catch (error) { /* ignore */ }
    });
    host.appendChild(sash);

    if (app.lastElementChild === main) app.appendChild(host);
    else app.insertBefore(host, main.nextSibling);

    dockRightState.host = host;
    dockRightState.sash = sash;
    dockRightLoadWidth();

    const labels = dockRightSurfaceLabels();
    dockRightState.surface = new DockSurfaceView({
        root: host,
        labels: labels,
        renderTab: (tab) => dockRightRenderTabBody(tab),
        // `+` opens a fresh "start" page in that pane, exactly like dsh: a
        // pane may hold one start page, so the control hides once it has one.
        canAddTab: (paneId) => {
            const surface = dockRightState.sessionId ? dockSurfaceOf(dockRightState.sessionId, DOCK_RIGHT_AREA) : null;
            return !!surface && dockPanePage(surface.layout, paneId, 'guide') === undefined;
        },
        canCloseTab: () => true,
        // Two panes is the column's ceiling: with two already open the split
        // control hides (below), so a dead button never lingers (feedback #8).
        canSplitSurface: () => {
            const surface = dockRightState.sessionId ? dockSurfaceOf(dockRightState.sessionId, DOCK_RIGHT_AREA) : null;
            return !!surface && dockPaneIds(surface.layout).length < 2;
        },
        // dsh's right column hides the split control while it cannot act
        // (`hideSplitWhenBlocked`), rather than leaving a dead button.
        hideSplitWhenBlocked: true,
        dropZones: 'horizontal',
        minPaneFraction: DOCK_PRODUCT_MIN_FRACTION,
        intents: dockRightIntents(),
        onRoom: () => {},
        onTabRemoved: (tabId) => dockRightDisposeTab(tabId),
        chrome: dockRightBuildChrome(),
    });
    dockRightState.surface.mount();
    dockRightState.floats = new DockFloatLayerView({
        root: host,
        labels: labels,
        intents: dockRightIntents(),
        renderTab: (tab) => dockRightRenderTabBody(tab),
        canCloseTab: () => true,
    });
    dockRightState.floats.mount();

    dockRightEnsureButton();
    dockRightRegisterTabs();
    if (!dockRightState.viewportHooked) {
        dockRightState.viewportHooked = true;
        window.addEventListener('resize', () => {
            if (!dockRightExpanded()) return;
            // The column yields by closing when the window can no longer hold
            // both: the workspace keeps a usable width and the details column
            // stays collapsed (a half-screen snap must not crush the chat).
            if (dockRightState.sessionId && dockRightWouldCrushWorkspace()) {
                const surface = dockSurfaceOf(dockRightState.sessionId, DOCK_RIGHT_AREA);
                if (surface && surface.layout.mode !== 'fullscreen') {
                    dockActionToggleExpanded(dockRightState.sessionId, dockRightSeed(), DOCK_RIGHT_AREA);
                    dockRightRender();
                    return;
                }
            }
            if (window.innerWidth < 768 && dockRightState.sessionId) {
                const surface = dockSurfaceOf(dockRightState.sessionId, DOCK_RIGHT_AREA);
                if (surface && surface.layout.mode !== 'fullscreen') {
                    dockActionSetMode(dockRightState.sessionId, 'fullscreen', dockRightSeed(), DOCK_RIGHT_AREA);
                }
            }
            dockRightRender();
        }, { passive: true });
    }
}

/** The column's surface-wide controls: fullscreen and collapse. */
function dockRightBuildChrome() {
    const wrap = document.createElement('div');
    wrap.className = 'dock-chrome-controls';
    const fullscreenButton = document.createElement('button');
    fullscreenButton.type = 'button';
    fullscreenButton.className = 'dock-icon-button';
    fullscreenButton.setAttribute('data-dock-rightbar-fullscreen', '1');
    fullscreenButton.innerHTML = DOCK_ICON_FULLSCREEN;
    fullscreenButton.addEventListener('click', () => {
        const sessionId = dockRightState.sessionId;
        if (!sessionId) return;
        const surface = dockSurfaceOf(sessionId, DOCK_RIGHT_AREA);
        if (!surface) return;
        // Fullscreen is a snap, not a slide: the column goes straight to the
        // viewport (and straight back). The push-mode open/close animation is
        // untouched.
        const host = dockRightState.host;
        if (host) host.classList.add('is-instant');
        dockActionSetMode(sessionId, surface.layout.mode === 'fullscreen' ? 'push' : 'fullscreen', dockRightSeed(), DOCK_RIGHT_AREA);
        dockRightRender();
        if (host) {
            requestAnimationFrame(() => requestAnimationFrame(() => host.classList.remove('is-instant')));
        }
    });
    const collapseButton = document.createElement('button');
    collapseButton.type = 'button';
    collapseButton.className = 'dock-icon-button';
    collapseButton.setAttribute('data-dock-rightbar-collapse', '1');
    collapseButton.setAttribute('aria-label', dockRightText('close'));
    // The collapse glyph is the panel icon mirrored, exactly like dsh's.
    collapseButton.innerHTML = DOCK_EXPAND_ICON;
    collapseButton.addEventListener('click', () => dockRightToggle());
    wrap.appendChild(fullscreenButton);
    wrap.appendChild(collapseButton);
    return wrap;
}

/**
 * The header corner button that opens the column, the same control dsh puts in
 * `conversation.session.header.corner`: an icon-only 28px circle holding the
 * left sidebar's panel glyph mirrored (the divider on the right), shown only
 * while the column is collapsed — an open column costs the header nothing.
 * The glyph is the icon primitive's path, inlined because this page has no
 * icon library.
 */
const DOCK_EXPAND_ICON = '<svg class="dock-expand-icon" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><path fill-rule="evenodd" clip-rule="evenodd" fill="currentColor" d="M9.67272 0.522841C10.8339 0.522841 11.76 0.522714 12.4963 0.602493C13.2453 0.683657 13.8789 0.854248 14.4264 1.25197C14.7504 1.48739 15.0355 1.77247 15.2709 2.0965C15.6686 2.64394 15.8392 3.27758 15.9204 4.02655C16.0002 4.7629 16 5.68895 16 6.85014V9.14986C16 10.3111 16.0002 11.2371 15.9204 11.9735C15.8392 12.7224 15.6686 13.3561 15.2709 13.9035C15.0355 14.2275 14.7504 14.5126 14.4264 14.748C13.8789 15.1458 13.2453 15.3163 12.4963 15.3975C11.76 15.4773 10.8339 15.4772 9.67272 15.4772H6.3273C5.16611 15.4772 4.24006 15.4773 3.50371 15.3975C2.75474 15.3163 2.1211 15.1458 1.57366 14.748C1.24963 14.5126 0.964549 14.2275 0.729131 13.9035C0.331407 13.3561 0.160817 12.7224 0.0796529 11.9735C-0.000126137 11.2371 1.25338e-09 10.3111 1.25338e-09 9.14986V6.85014C1.25329e-09 5.68895 -0.000126137 4.7629 0.0796529 4.02655C0.160817 3.27758 0.331407 2.64394 0.729131 2.0965C0.964549 1.77247 1.24963 1.48739 1.57366 1.25197C2.1211 0.854248 2.75474 0.683657 3.50371 0.602493C4.24006 0.522714 5.16611 0.522841 6.3273 0.522841H9.67272ZM5.54303 1.88715V14.1118C5.78636 14.1128 6.04709 14.1169 6.3273 14.1169H9.67272C10.8639 14.1169 11.7032 14.1164 12.3493 14.0465C12.9824 13.9779 13.3497 13.8494 13.6268 13.6482C13.8354 13.4966 14.0195 13.3125 14.1711 13.1039C14.3723 12.8268 14.5007 12.4595 14.5693 11.8264C14.6393 11.1803 14.6398 10.341 14.6398 9.14986V6.85014C14.6398 5.65896 14.6393 4.81967 14.5693 4.1736C14.5007 3.54048 14.3723 3.17318 14.1711 2.89609C14.0195 2.68747 13.8354 2.50337 13.6268 2.35179C13.3497 2.1506 12.9824 2.02212 12.3493 1.95353C11.7032 1.88358 10.8639 1.88307 9.67272 1.88307H6.3273C6.04709 1.88307 5.78636 1.8862 5.54303 1.88715ZM4.1828 1.91166C3.99125 1.9216 3.8148 1.93577 3.65076 1.95353C3.01764 2.02212 2.65034 2.1506 2.37325 2.35179C2.16463 2.50337 1.98052 2.68747 1.82895 2.89609C1.62776 3.17318 1.49928 3.54048 1.43069 4.1736C1.36074 4.81967 1.36023 5.65896 1.36023 6.85014V9.14986C1.36023 10.341 1.36074 11.1803 1.43069 11.8264C1.49928 12.4595 1.62776 12.8268 1.82895 13.1039C1.98052 13.3125 2.16463 13.4966 2.37325 13.6482C2.65034 13.8494 3.01764 13.9779 3.65076 14.0465C3.81478 14.0642 3.99127 14.0774 4.1828 14.0873V1.91166Z"/></svg>';

function dockRightEnsureButton() {
    if (dockRightState.button && dockRightState.button.isConnected) return;
    const right = document.querySelector('.titlebar-right');
    if (!right) return;
    const button = document.createElement('button');
    button.type = 'button';
    button.id = 'dock-rightbar-toggle-btn';
    button.className = 'dock-expand-btn';
    button.setAttribute('aria-label', dockRightText('openAria'));
    button.setAttribute('title', dockRightText('open'));
    button.innerHTML = DOCK_EXPAND_ICON;
    button.addEventListener('click', () => dockRightToggle());
    // The header's own corner, past the utilities' edge (the seat's last slot).
    right.appendChild(button);
    dockRightState.button = button;
}

/** Restore the remembered column width. */
function dockRightLoadWidth() {
    let width = DOCK_RIGHT_WIDTH_DEFAULT;
    try {
        const saved = parseInt(localStorage.getItem(DOCK_RIGHT_WIDTH_KEY), 10);
        if (Number.isFinite(saved)) width = saved;
    } catch (error) { /* ignore */ }
    dockRightState.width = dockRightClampWidth(width);
    dockRightApplyWidth();
}

/** Would an expanded column leave the workspace below its usable floor? */
function dockRightWouldCrushWorkspace() {
    const app = document.querySelector('.app');
    const appWidth = app ? app.clientWidth : (window.innerWidth || 0);
    let reserved = 0;
    const sidebar = document.getElementById('sidebar');
    if (sidebar) {
        const rect = sidebar.getBoundingClientRect();
        if (rect.width > 0) reserved += rect.width;
    }
    const sash = document.getElementById('sash');
    if (sash) {
        const rect = sash.getBoundingClientRect();
        if (rect.width > 0) reserved += rect.width;
    }
    const frame = Math.max(0, appWidth - reserved);
    return frame - dockRightState.width < DOCK_RIGHT_WORKSPACE_FLOOR;
}

/** A narrow window covers with the fullscreen mode instead of squeezing the
    workspace: every open path (button, file link, review) goes through here. */
function dockRightEnsureNarrowOpenMode(sessionId) {
    if (!sessionId) return;
    if (!(window.innerWidth < 768 || dockRightWouldCrushWorkspace())) return;
    const surface = dockSurfaceOf(sessionId, DOCK_RIGHT_AREA);
    if (surface && surface.layout.expanded && surface.layout.mode !== 'fullscreen') {
        dockActionSetMode(sessionId, 'fullscreen', dockRightSeed(), DOCK_RIGHT_AREA);
    }
}

/** Clamp a width to the column's bounds and the viewport. */
function dockRightClampWidth(width) {
    const viewport = Math.max(0, window.innerWidth || DOCK_RIGHT_WIDTH_MAX);
    const max = Math.max(DOCK_RIGHT_WIDTH_MIN, Math.min(DOCK_RIGHT_WIDTH_MAX, Math.floor(viewport * 0.72)));
    return Math.max(DOCK_RIGHT_WIDTH_MIN, Math.min(max, Math.round(Number(width) || DOCK_RIGHT_WIDTH_DEFAULT)));
}

/** Write the width onto the element. */
function dockRightApplyWidth() {
    if (dockRightState.host) dockRightState.host.style.setProperty('--dock-rightbar-width', dockRightState.width + 'px');
}

/** Drag the sash to resize the column. */
function dockRightStartResize(event) {
    if (event.button !== 0) return;
    event.preventDefault();
    const startX = event.clientX;
    const startWidth = dockRightState.host ? dockRightState.host.getBoundingClientRect().width : dockRightState.width;
    const onMove = (moved) => {
        dockRightState.width = dockRightClampWidth(startWidth - (moved.clientX - startX));
        dockRightApplyWidth();
    };
    const onUp = () => {
        window.removeEventListener('pointermove', onMove);
        window.removeEventListener('pointerup', onUp);
        try { localStorage.setItem(DOCK_RIGHT_WIDTH_KEY, String(dockRightState.width)); } catch (error) { /* ignore */ }
        if (dockRightState.surface) dockRightState.surface.remeasure();
    };
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
}

// ── intents and rendering ────────────────────────────────────────────────────

/** Settled intent results for the column, routed into the `right` area's store. */
function dockRightIntents() {
    const redraw = () => dockRightRender();
    const session = () => dockRightState.sessionId;
    return {
        focusTab: (tabId) => { if (dockActionFocusTab(session(), tabId, dockRightSeed(), DOCK_RIGHT_AREA)) redraw(); },
        focusPane: (paneId) => { if (dockActionFocusPane(session(), paneId, dockRightSeed(), DOCK_RIGHT_AREA)) redraw(); },
        splitPane: (paneId) => { if (dockActionSplitPane(session(), paneId, dockRightSeed(), null, DOCK_RIGHT_AREA)) redraw(); },
        // `+`: a fresh start page in that pane — the "new empty window".
        addTab: (paneId) => dockRightOpenPageKind('guide', undefined, paneId),
        closeTab: (tabId) => { if (dockActionCloseTab(session(), tabId, dockRightSeed(), DOCK_RIGHT_AREA)) { dockRightDisposeTab(tabId); redraw(); } },
        duplicateTab: (tabId) => { if (dockActionDuplicateTab(session(), tabId, dockRightSeed(), DOCK_RIGHT_AREA)) redraw(); },
        floatTab: (tabId, rect) => { if (dockActionFloatTab(session(), tabId, rect, dockRightSeed(), DOCK_RIGHT_AREA)) redraw(); },
        unfloatPane: (paneId) => { if (dockActionUnfloatPane(session(), paneId, dockRightSeed(), DOCK_RIGHT_AREA)) redraw(); },
        moveFloat: (paneId, x, y) => { if (dockActionMoveFloat(session(), paneId, x, y, dockRightSeed(), DOCK_RIGHT_AREA)) redraw(); },
        resizeFloat: (paneId, rect) => { if (dockActionResizeFloat(session(), paneId, rect, dockRightSeed(), DOCK_RIGHT_AREA)) redraw(); },
        placeTab: (tabId, toPaneId, index) => { if (dockActionPlaceTab(session(), tabId, toPaneId, index, dockRightSeed(), DOCK_RIGHT_AREA)) redraw(); },
        dropTab: (tabId, paneId, zone) => { if (dockActionDropTab(session(), tabId, paneId, zone, dockRightSeed(), DOCK_RIGHT_AREA)) redraw(); },
        resizeSplit: (splitId, sizes) => { if (dockActionResizeSplit(session(), splitId, sizes, dockRightSeed(), DOCK_RIGHT_AREA)) redraw(); },
    };
}

/** Whether the column is shown. */
function dockRightExpanded() {
    const surface = dockRightState.sessionId ? dockSurfaceOf(dockRightState.sessionId, DOCK_RIGHT_AREA) : null;
    return !!(surface && surface.layout.expanded);
}

/**
 * Open the column for the current session, or collapse it. Opening a collapsed
 * column that still holds tabs only re-expands it — the earlier code asked for
 * the files page and, seeing it already there, planned nothing at all, which
 * made the second click a no-op. Only an empty column is seeded with a page.
 */
function dockRightToggle() {
    // A subagent view toggles the parent session's column (see the key above).
    const sessionId = dockRightSurfaceKey(currentSessionId);
    if (!sessionId) return;
    dockRightEnsureMounted();
    if (!dockRightState.host) return;
    dockActionOpen(sessionId, DOCK_RIGHT_AREA);
    const surface = dockSurfaceOf(sessionId, DOCK_RIGHT_AREA);
    dockRightState.sessionId = sessionId;
    if (surface.layout.expanded) {
        dockActionToggleExpanded(sessionId, dockRightSeed(), DOCK_RIGHT_AREA);
        dockRightRender();
        return;
    }
    const hasTabs = Object.keys(surface.layout.tabs).length > 0;
    if (hasTabs) {
        dockActionSetExpanded(sessionId, true, dockRightSeed(), DOCK_RIGHT_AREA);
    } else {
        dockActionOpenContent(sessionId, {
            kind: 'guide',
            contentId: dockPageAddress('guide'),
            title: dockRightText('guide'),
            revealIfOpened: false,
        }, dockRightSeed(), null, DOCK_RIGHT_AREA);
    }
    dockRightEnsureNarrowOpenMode(sessionId);
    dockRightRender();
}

/** Show or hide the column and sync everything the current snapshot implies. */
function dockRightRender() {
    const host = dockRightState.host;
    if (!host) return;
    const sessionId = dockRightState.sessionId;
    const surface = sessionId ? dockSurfaceOf(sessionId, DOCK_RIGHT_AREA) : null;
    const expanded = !!(surface && surface.layout.expanded);
    const fullscreen = !!(expanded && surface.layout.mode === 'fullscreen');
    host.classList.toggle('is-fullscreen', fullscreen);
    host.setAttribute('aria-hidden', expanded ? 'false' : 'true');
    host.inert = !expanded;
    if (expanded) {
        // Let a newly mounted zero-width column paint once before revealing it;
        // otherwise the browser coalesces both states and skips the transition.
        if (host.classList.contains('is-collapsed') && dockRightState.revealFrame === null) {
            dockRightState.revealFrame = requestAnimationFrame(() => {
                dockRightState.revealFrame = null;
                if (dockRightExpanded()) host.classList.remove('is-collapsed');
            });
        }
    } else {
        if (dockRightState.revealFrame !== null) cancelAnimationFrame(dockRightState.revealFrame);
        dockRightState.revealFrame = null;
        host.classList.add('is-collapsed');
    }
    if (dockRightState.button) {
        // dsh's original behaviour (restored on request): the corner button is
        // the way in, shown only while the column is collapsed.
        dockRightState.button.hidden = expanded;
        dockRightState.button.setAttribute('aria-pressed', expanded ? 'true' : 'false');
        dockRightState.button.title = dockRightText('open');
    }
    if (!surface || !expanded) {
        if (dockRightState.surface && surface) dockRightState.surface.sync(surface.layout);
        return;
    }
    if (dockRightState.surface) {
        dockRightState.surface.intents = dockRightIntents();
        dockRightState.surface.sync(surface.layout);
    }
    if (dockRightState.floats) {
        dockRightState.floats.intents = dockRightIntents();
        dockRightState.floats.sync(surface.layout);
    }
    const fullscreenButton = host.querySelector('[data-dock-rightbar-fullscreen]');
    if (fullscreenButton) {
        fullscreenButton.setAttribute('aria-label', fullscreen ? dockRightText('exitFullscreen') : dockRightText('fullscreen'));
        fullscreenButton.innerHTML = fullscreen ? DOCK_ICON_EXIT_FULLSCREEN : DOCK_ICON_FULLSCREEN;
    }
}

/**
 * The surface key for a session: a subagent's addressed view belongs to its
 * parent session, so entering or leaving a child keeps the parent column's
 * state (open, on the same page) instead of collapsing it.
 */
function dockRightSurfaceKey(sessionId) {
    const sid = String(sessionId || '');
    if (!sid) return sid;
    try {
        if (typeof subagentAddressing !== 'undefined' && subagentAddressing
            && typeof subagentAddressing.current === 'function') {
            const info = subagentAddressing.current();
            if (info && String(info.childSessionId) === sid && info.parentSessionId) {
                return String(info.parentSessionId);
            }
        }
    } catch (error) { /* ignore */ }
    try {
        if (typeof subagentCatalogStore !== 'undefined' && subagentCatalogStore
            && typeof subagentCatalogStore.getAddress === 'function') {
            const address = subagentCatalogStore.getAddress(sid);
            if (address && address.parentSessionId) return String(address.parentSessionId);
        }
    } catch (error) { /* ignore */ }
    return sid;
}

/** The session-switch hook: show the entering session's own column surface. */
function dockRightHandleSessionSwitch(sessionId) {
    if (!dockRightState.host) return;
    const sid = dockRightSurfaceKey(sessionId);
    if (!sid) return;
    if (dockRightState.sessionId === sid) return;
    if (!dockSurfaceExists(sid, DOCK_RIGHT_AREA)) {
        dockRightState.sessionId = sid;
        dockRightRender();
        return;
    }
    dockRightState.sessionId = sid;
    dockRightRender();
        // The entering session's own open state still yields to a narrow window.
        if (dockRightExpanded() && dockRightWouldCrushWorkspace()) {
            dockActionToggleExpanded(sid, dockRightSeed(), DOCK_RIGHT_AREA);
            dockRightRender();
        }
}

/**
 * A belt-and-braces session watcher: the list's active marker is the app's
 * authoritative "current session" signal, so watching it keeps the column in
 * step even on a path that reaches `switchSession` without the wrapper.
 */
function dockRightWatchSessions() {
    if (dockRightState.sessionWatch) return;
    const list = document.querySelector('#sessions-list');
    if (!list) return;
    const sync = () => {
        const row = list.querySelector('.session-item.active[data-session-id]');
        const sid = row ? String(row.getAttribute('data-session-id') || '') : '';
        if (sid) dockRightHandleSessionSwitch(sid);
    };
    dockRightState.sessionWatch = new MutationObserver(sync);
    dockRightState.sessionWatch.observe(list, { subtree: true, attributes: true, attributeFilter: ['class', 'data-session-id'] });
    sync();
}

// ── tab bodies ───────────────────────────────────────────────────────────────

/** The body for one tab of this column. */
function dockRightRenderTabBody(tab) {
    if (tab.kind === 'guide') return dockRightGuideBody(tab);
    if (tab.kind === 'files') return dockRightFilesBody(tab);
    if (tab.kind === 'document') return dockRightDocumentBody(tab);
    if (tab.kind === 'changes') return dockRightChangesBody(tab);
    const fallback = document.createElement('div');
    fallback.className = 'dock-unknown-tab';
    fallback.textContent = tab.title || tab.kind;
    return fallback;
}

/** Register the column's built-in page types. Called once at mount. */
function dockRightRegisterTabs() {
    if (dockRightState.registered) return;
    dockRightState.registered = true;
    const register = (definition) => {
        try {
            dockTabRegistry.register(definition);
        } catch (error) {
            console.warn('dock details tab registration skipped', definition && definition.id, error && error.message);
        }
    };
    register({
        id: 'myagent.details.guide',
        kind: 'guide',
        priority: 'builtin',
        title: () => dockRightText('guide'),
        body: dockRightGuideBody,
    });
    register({
        id: 'myagent.details.files',
        kind: 'files',
        priority: 'builtin',
        title: () => dockRightText('files'),
        body: dockRightFilesBody,
    });
    register({
        id: 'myagent.details.document',
        kind: 'document',
        priority: 'builtin',
        patterns: ['myagent-resource://file/**'],
        canOpen: () => true,
        title: (address) => dockRightBasename(decodeURIComponent(String(address).slice(DOCK_RIGHT_FILE_PREFIX.length)) || 'file'),
        body: dockRightDocumentBody,
    });
    register({
        id: 'myagent.details.changes',
        kind: 'changes',
        priority: 'builtin',
        title: () => dockRightText('changes'),
        body: dockRightChangesBody,
    });
}

// ── files page ───────────────────────────────────────────────────────────────

/**
 * The "start" page: the column's home and the pane's fallback. Closing the
 * last tab never collapses the column — the settle step re-seeds this page —
 * and opening the column for the first time lands here, exactly like dsh's
 * guide page (feedback #3 and #7).
 */
function dockRightGuideBody(tab) {
    const el = document.createElement('div');
    el.className = 'dock-guide';
    el.setAttribute('data-dock-guide', tab.id);
    const glyph = document.createElement('div');
    glyph.className = 'dock-guide-glyph';
    glyph.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9.2" fill="none" stroke="currentColor" stroke-width="1.4"/><path d="M15.6 8.4l-2.2 5-5 2.2 2.2-5z" fill="currentColor"/></svg>';
    const entries = document.createElement('div');
    entries.className = 'dock-guide-entries';
    const cards = [
        { label: dockRightText('guideFiles'), desc: dockRightText('guideFilesDesc'), icon: DOCK_FOLDER_ICON, kind: 'files' },
        { label: dockRightText('guideChanges'), desc: dockRightText('guideChangesDesc'), icon: dockRightFileIcon('changes.md'), kind: 'changes' },
    ];
    for (let i = 0; i < cards.length; i += 1) {
        const card = document.createElement('button');
        card.type = 'button';
        card.className = 'dock-guide-card';
        card.setAttribute('data-dock-guide-entry', cards[i].kind);
        const icon = document.createElement('span');
        icon.className = 'dock-guide-card-icon';
        icon.innerHTML = cards[i].icon;
        const text = document.createElement('span');
        text.className = 'dock-guide-card-text';
        const title = document.createElement('span');
        title.className = 'dock-guide-card-title';
        title.textContent = cards[i].label;
        const desc = document.createElement('span');
        desc.className = 'dock-guide-card-desc';
        desc.textContent = cards[i].desc;
        text.appendChild(title);
        text.appendChild(desc);
        card.appendChild(icon);
        card.appendChild(text);
        card.addEventListener('click', () => dockRightOpenPageKind(cards[i].kind, tab.id));
        entries.appendChild(card);
    }
    el.appendChild(glyph);
    el.appendChild(entries);
    return el;
}

/** Open one of the column's pages (guide entries, `+`, the public API) in a pane. */
function dockRightOpenPageKind(kind, replaceTab, paneId, revealIfOpened) {
    dockRightEnsureMounted();
    const sessionId = dockRightSurfaceKey(dockRightState.sessionId || currentSessionId);
    if (!sessionId) return;
    const address = dockPageAddress(String(kind));
    const definition = dockTabRegistry.get(String(kind));
    dockActionOpenContent(sessionId, {
        kind: String(kind),
        contentId: address,
        title: definition ? dockTitleOf(definition, address) : String(kind),
        replaceTab: replaceTab,
        paneId: paneId,
        revealIfOpened: Boolean(revealIfOpened),
    }, dockRightSeed(), null, DOCK_RIGHT_AREA);
    dockRightState.sessionId = sessionId;
    dockRightRender();
}

/** The workspace tree page. */
function dockRightFilesBody(tab) {
    const el = document.createElement('div');
    el.className = 'dock-files';
    el.setAttribute('data-dock-files', tab.id);
    // dsh's files page keeps a path bar under the strip: the current root on
    // the left (its absolute path) and its refresh control at the right edge.
    const pathRow = document.createElement('div');
    pathRow.className = 'dock-files-pathrow';
    const pathLabel = document.createElement('span');
    pathLabel.className = 'dock-files-path';
    pathLabel.setAttribute('data-dock-files-path', '1');
    pathLabel.textContent = '';
    const refresh = document.createElement('button');
    refresh.type = 'button';
    refresh.className = 'dock-icon-button dock-files-refresh';
    refresh.setAttribute('data-dock-files-refresh', '1');
    refresh.setAttribute('aria-label', dockRightText('refresh'));
    refresh.title = dockRightText('refresh');
    refresh.innerHTML = DOCK_ICON_REFRESH;
    pathRow.appendChild(pathLabel);
    pathRow.appendChild(refresh);
    const tree = document.createElement('div');
    tree.className = 'dock-files-tree';
    refresh.addEventListener('click', () => {
        tree.replaceChildren();
        void dockRightLoadDir(tree, '', 0, { onRoot: (root) => { pathLabel.textContent = root; } });
    });
    el.appendChild(pathRow);
    el.appendChild(tree);
    dockRightTrackScroll(tab.id, tree);
    el.__dockRestore = tree.__dockRestore;
    void dockRightLoadDir(tree, '', 0, { onRoot: (root) => { pathLabel.textContent = root; } });
    return el;
}

/** Load one directory level into `container`, recursively expandable. */
async function dockRightLoadDir(container, dir, depth, options) {
    const loading = document.createElement('div');
    loading.className = 'dock-note';
    loading.textContent = dockRightText('loading');
    container.appendChild(loading);
    try {
        const response = await fetch('/api/workspace-files?' + new URLSearchParams({ dir: dir || '' }));
        const data = await response.json();
        loading.remove();
        if (!response.ok || !data || data.ok !== true || !Array.isArray(data.files)) {
            throw new Error((data && data.error) || ('HTTP ' + response.status));
        }
        if (options && typeof options.onRoot === 'function' && data.root) options.onRoot(String(data.root));
        const rows = data.files.slice().sort((left, right) => {
            const leftDir = left.kind === 'directory' ? 0 : 1;
            const rightDir = right.kind === 'directory' ? 0 : 1;
            if (leftDir !== rightDir) return leftDir - rightDir;
            return String(left.name).localeCompare(String(right.name), 'zh-Hans-CN');
        });
        if (rows.length === 0) {
            const empty = document.createElement('div');
            empty.className = 'dock-note';
            empty.textContent = dockRightText('emptyDir');
            container.appendChild(empty);
            return;
        }
        for (let i = 0; i < rows.length; i += 1) container.appendChild(dockRightFileRow(rows[i], depth));
    } catch (error) {
        loading.textContent = dockRightText('loadFailed') + ': ' + (error && error.message ? error.message : error);
    }
}

/** One row of the tree: a directory that expands, or a file that opens. */
function dockRightFileRow(item, depth) {
    const wrap = document.createElement('div');
    wrap.className = 'dock-files-node';
    const isDir = item.kind === 'directory';
    const row = document.createElement('button');
    row.type = 'button';
    row.className = 'dock-files-row' + (isDir ? ' dock-files-row--dir' : '');
    row.style.paddingLeft = (8 + depth * 14) + 'px';
    row.setAttribute('data-rel', item.rel);
    row.title = item.path || item.rel;
    const marker = document.createElement('span');
    marker.className = 'dock-files-marker';
    if (isDir) {
        marker.classList.add('dock-files-marker--dir');
        marker.innerHTML = '<span class="dock-files-caret">▸</span>' + DOCK_FOLDER_ICON;
    }
    else {
        marker.classList.add('dock-files-marker--icon');
        marker.innerHTML = dockRightFileIcon(item.name);
    }
    const name = document.createElement('span');
    name.className = 'dock-files-name';
    name.textContent = item.name;
    row.appendChild(marker);
    row.appendChild(name);
    if (!isDir && Number.isFinite(Number(item.size))) {
        const size = document.createElement('span');
        size.className = 'dock-files-size';
        size.textContent = dockRightSize(item.size);
        row.appendChild(size);
    }
    wrap.appendChild(row);
    if (!isDir) {
        row.addEventListener('click', () => dockRightOpenResource(DOCK_RIGHT_FILE_PREFIX + encodeURIComponent(item.rel)));
        return wrap;
    }
    const children = document.createElement('div');
    children.className = 'dock-files-children';
    children.hidden = true;
    let loaded = false;
    row.addEventListener('click', () => {
        const expanding = children.hidden;
        children.hidden = !expanding;
        const caret = marker.querySelector('.dock-files-caret');
        if (caret) caret.textContent = expanding ? '▾' : '▸';
        if (expanding && !loaded) {
            loaded = true;
            void dockRightLoadDir(children, item.rel, depth + 1);
        }
    });
    wrap.appendChild(children);
    return wrap;
}

/** Open a resource address in the column (expanding it), focusing it if open. */
function dockRightOpenResource(address) {
    dockRightEnsureMounted();
    const sessionId = dockRightSurfaceKey(dockRightState.sessionId || currentSessionId);
    if (!sessionId) return;
    let claim;
    try {
        claim = dockTabRegistry.claim(address);
    } catch (error) {
        console.warn('dock details: no tab type claims', address, error && error.message);
        return;
    }
    dockActionOpenContent(sessionId, {
        kind: claim.kind,
        contentId: claim.contentId,
        title: claim.title,
    }, dockRightSeed(), null, DOCK_RIGHT_AREA);
    dockRightState.sessionId = sessionId;
    dockRightEnsureNarrowOpenMode(sessionId);
    dockRightRender();
}

// ── document page ────────────────────────────────────────────────────────────

/** One file's content: image, media, or text, with an open-in-system fallback. */
function dockRightDocumentBody(tab) {
    const el = document.createElement('div');
    el.className = 'dock-doc';
    el.setAttribute('data-dock-document', tab.id);
    const rel = decodeURIComponent(String(tab.contentId || '').slice(DOCK_RIGHT_FILE_PREFIX.length));
    const suffix = dockRightSuffix(rel);
    const state = { abort: null, released: false, rel: rel, suffix: suffix };
    dockRightState.tabState[tab.id] = state;

    const head = document.createElement('div');
    head.className = 'dock-doc-head';
    const name = document.createElement('span');
    name.className = 'dock-doc-name';
    name.textContent = dockRightBasename(rel) || rel;
    name.title = rel;
    const refresh = document.createElement('button');
    refresh.type = 'button';
    refresh.className = 'dock-icon-button dock-doc-refresh';
    refresh.setAttribute('data-dock-doc-refresh', '1');
    refresh.setAttribute('aria-label', dockRightText('refresh'));
    refresh.title = dockRightText('refresh');
    refresh.innerHTML = DOCK_ICON_REFRESH;
    const reveal = document.createElement('button');
    reveal.type = 'button';
    reveal.className = 'dock-icon-button dock-doc-reveal';
    reveal.setAttribute('data-dock-doc-reveal', '1');
    reveal.setAttribute('aria-label', dockRightText('reveal'));
    reveal.title = dockRightText('reveal');
    reveal.innerHTML = DOCK_ICON_REVEAL;
    reveal.addEventListener('click', () => {
        void fetch('/api/open-workspace-dir?' + new URLSearchParams({ rel: rel }))
            .then((response) => response.json().catch(() => null))
            .then((data) => {
                if (typeof showOpenFileFeedback === 'function') {
                    if (data && data.ok) showOpenFileFeedback('已打开文件目录');
                    else showOpenFileFeedback('无法打开文件目录：' + ((data && data.error) || '服务未就绪'));
                }
            })
            .catch(() => {
                if (typeof showOpenFileFeedback === 'function') showOpenFileFeedback('无法打开文件目录：无法连接服务');
            });
    });
    const openSystem = document.createElement('button');
    openSystem.type = 'button';
    openSystem.className = 'dock-link-button';
    openSystem.textContent = dockRightText('openSystem');
    openSystem.addEventListener('click', () => {
        void fetch('/api/open-workspace-file?' + new URLSearchParams({ rel: rel }));
    });
    // The refresh control keeps the head's far right corner on every page;
    // the system-open action sits beside the title instead (it ran between
    // the name and the corner and pushed the refresh icon into the middle).
    head.appendChild(name);
    head.appendChild(openSystem);
    head.appendChild(reveal);
    head.appendChild(refresh);
    const content = document.createElement('div');
    content.className = 'dock-doc-content';
    el.appendChild(head);
    el.appendChild(content);

    if (DOCK_RIGHT_IMAGE_SUFFIXES.indexOf(suffix) >= 0) {
        const image = document.createElement('img');
        image.className = 'dock-doc-image';
        image.alt = name.textContent;
        image.src = '/api/workspace-image?' + new URLSearchParams({ rel: rel });
        image.addEventListener('error', () => {
            content.replaceChildren(dockRightSystemCard(rel));
        });
        content.appendChild(image);
        refresh.addEventListener('click', () => {
            image.src = '/api/workspace-image?' + new URLSearchParams({ rel: rel, _: String(Date.now()) });
        });
    } else if (DOCK_RIGHT_AUDIO_SUFFIXES.indexOf(suffix) >= 0 || DOCK_RIGHT_VIDEO_SUFFIXES.indexOf(suffix) >= 0) {
        const media = document.createElement(DOCK_RIGHT_VIDEO_SUFFIXES.indexOf(suffix) >= 0 ? 'video' : 'audio');
        media.className = 'dock-doc-media';
        media.controls = true;
        media.src = '/api/workspace-media?' + new URLSearchParams({ rel: rel });
        content.appendChild(media);
        refresh.addEventListener('click', () => {
            try { media.load(); } catch (error) { /* ignore */ }
        });
    } else if (DOCK_RIGHT_BINARY_SUFFIXES.indexOf(suffix) >= 0) {
        // Feedback #5: a non-text file goes straight to the system-app card
        // instead of showing mojibake.
        content.appendChild(dockRightSystemCard(rel));
        refresh.disabled = true;
    } else if (DOCK_RIGHT_HTML_SUFFIXES.indexOf(suffix) >= 0) {
        // HTML renders as a page by default — sandboxed iframe, its own
        // origin, sibling assets resolved through /api/workspace-assets/ —
        // with a one-click switch to the source view.
        let mode = 'preview';
        const toggle = document.createElement('button');
        toggle.type = 'button';
        toggle.className = 'dock-link-button dock-doc-source-toggle';
        toggle.setAttribute('data-dock-doc-source-toggle', '1');
        const assetUrl = '/api/workspace-assets/' + String(rel).split(/[\\/]/).map(encodeURIComponent).join('/');
        const renderPreview = () => {
            mode = 'preview';
            content.style.padding = '0';
            const frame = document.createElement('iframe');
            frame.className = 'dock-doc-frame';
            frame.setAttribute('data-dock-doc-frame', '1');
            frame.setAttribute('sandbox', 'allow-scripts');
            frame.setAttribute('referrerpolicy', 'no-referrer');
            frame.title = name.textContent;
            frame.src = assetUrl + '?_=' + String(Date.now());
            content.replaceChildren(frame);
            toggle.textContent = dockRightText('viewSource');
        };
        const renderSource = () => {
            mode = 'source';
            content.style.padding = '';
            void dockRightLoadText(content, state);
            toggle.textContent = dockRightText('viewPreview');
        };
        toggle.addEventListener('click', () => {
            if (mode === 'preview') renderSource();
            else renderPreview();
        });
        head.insertBefore(toggle, openSystem);
        refresh.addEventListener('click', () => {
            if (mode === 'preview') renderPreview();
            else void dockRightLoadText(content, state);
        });
        renderPreview();
    } else if (DOCK_RIGHT_MD_SUFFIXES.indexOf(suffix) >= 0) {
        // Markdown renders through the app's own pipeline (`renderMarkdown`,
        // the same parser the chat uses), so documents look identical in the
        // column and the timeline; a toggle keeps the raw source one click away.
        const baseDir = String(rel).replace(/[\\/][^\\/]*$/, '');
        const assetBase = '/api/workspace-assets/' + (baseDir ? baseDir.split(/[\\/]/).map(encodeURIComponent).join('/') + '/' : '');
        let mode = 'rendered';
        const toggle = document.createElement('button');
        toggle.type = 'button';
        toggle.className = 'dock-link-button dock-doc-source-toggle';
        toggle.setAttribute('data-dock-doc-source-toggle', '1');
        const resolveRelative = (text) => String(text).replace(
            /(!?\[[^\]]*\]\()(?!(?:[a-z][a-z0-9+.-]*:|\/|#))([^)]+)(\))/gi,
            (whole, head, target, tail) => head + assetBase + target.split(/[\\/]/).map(encodeURIComponent).join('/') + tail,
        );
        const renderDoc = async () => {
            mode = 'rendered';
            content.style.padding = '';
            content.replaceChildren(dockRightNote(dockRightText('loading')));
            try {
                const scanned = await dockRightFetchJSON('/api/workspace-file-text?' + new URLSearchParams({
                    rel: rel,
                    max_bytes: String(DOCK_RIGHT_TEXT_MAX_BYTES),
                }));
                const data = scanned.data;
                if (state.released) return;
                if (!scanned.response.ok || !data || data.ok !== true) {
                    throw new Error((data && data.error) || ('HTTP ' + scanned.response.status));
                }
                const body = document.createElement('div');
                body.className = 'dock-doc-markdown';
                body.setAttribute('data-dock-doc-markdown', '1');
                const html = typeof renderMarkdown === 'function'
                    ? renderMarkdown(resolveRelative(String(data.text || '')))
                    : null;
                if (html === null) {
                    throw new Error(dockRightText('loadFailed'));
                }
                body.innerHTML = html;
                content.replaceChildren(body);
                if (data.truncated) content.appendChild(dockRightNote(dockRightText('truncated')));
                toggle.textContent = dockRightText('viewSource');
            } catch (error) {
                if (state.released) return;
                content.replaceChildren(dockRightNote(dockRightText('loadFailed') + ': ' + (error && error.message ? error.message : error)));
            }
        };
        const renderSource = () => {
            mode = 'source';
            content.style.padding = '';
            void dockRightLoadText(content, state);
            toggle.textContent = dockRightText('previewDoc');
        };
        toggle.addEventListener('click', () => {
            if (mode === 'rendered') renderSource();
            else void renderDoc();
        });
        head.insertBefore(toggle, openSystem);
        refresh.addEventListener('click', () => {
            if (mode === 'rendered') void renderDoc();
            else void dockRightLoadText(content, state);
        });
        void renderDoc();
    } else {
        void dockRightLoadText(content, state);
        refresh.addEventListener('click', () => { void dockRightLoadText(content, state); });
    }
    dockRightTrackScroll(tab.id, content);
    el.__dockRestore = content.__dockRestore;
    return el;
}

/** Read a text file into a `<pre>`. */
async function dockRightLoadText(content, state) {
    const loading = dockRightNote(dockRightText('loading'));
    content.replaceChildren(loading);
    try {
        const controller = typeof AbortController === 'function' ? new AbortController() : null;
        state.abort = controller;
        const response = await fetch('/api/workspace-file-text?' + new URLSearchParams({
            rel: state.rel,
            max_bytes: String(DOCK_RIGHT_TEXT_MAX_BYTES),
        }), controller ? { signal: controller.signal } : undefined);
        const data = await response.json().catch(() => null);
        if (state.released) return;
        if (!response.ok || !data || data.ok !== true) {
            if (response.status === 404 || response.status === 405 || response.status === 501) {
                content.replaceChildren(dockRightNote(dockRightText('textUnavailable')));
                return;
            }
            throw new Error((data && data.error) || ('HTTP ' + response.status));
        }
        const text = String(data.text || '');
        const replacements = (text.match(/\uFFFD/g) || []).length;
        if (replacements > 0 && replacements > text.length * 0.02) {
            // Undecodable bytes: this is not a text file after all; hand it to
            // the system app instead of displaying replacement glyphs.
            content.replaceChildren(dockRightSystemCard(state.rel));
            return;
        }
        const pre = document.createElement('pre');
        pre.className = 'dock-doc-text';
        pre.textContent = text;
        const nodes = [pre];
        if (data.truncated) nodes.push(dockRightNote(dockRightText('truncated')));
        content.replaceChildren.apply(content, nodes);
    } catch (error) {
        if (error && error.name === 'AbortError') return;
        content.replaceChildren(dockRightNote(dockRightText('loadFailed') + ': ' + (error && error.message ? error.message : error)));
    }
}

/** A quiet note line. */
function dockRightNote(text) {
    const note = document.createElement('div');
    note.className = 'dock-note';
    note.textContent = text;
    return note;
}

// ── changes page ─────────────────────────────────────────────────────────────

/**
 * Official turn boundary: a non-follow-up `user` event starts a turn; `user_steer`
 * remains inside it. Every review row is assigned to the latest such boundary.
 */
function dockRightChangesBody(tab) {
    const el = document.createElement('div');
    el.className = 'dock-changes';
    el.setAttribute('data-dock-changes', tab.id);
    const sessionId = dockRightSurfaceKey(dockRightState.sessionId || currentSessionId);
    const state = {
        changeReview: true,
        sessionId: sessionId,
        rows: new Map(),
        turns: new Map(),
        turnTokens: new Map(),
        selectedTurnId: null,
        scope: 'turn',
        focusRequest: dockRightChangeReviewFocus.get(String(sessionId || '')) || null,
        expandedChanges: new Set(),
        released: false,
        listener: null,
        abort: null,
        loaded: false,
        status: '',
        statusError: false,
    };
    dockRightState.tabState[tab.id] = state;

    const head = document.createElement('div');
    head.className = 'dock-changes-head';
    const title = document.createElement('span');
    title.className = 'dock-changes-title';
    title.textContent = dockRightText('changes');
    const refresh = document.createElement('button');
    refresh.type = 'button';
    refresh.className = 'dock-icon-button dock-changes-refresh';
    refresh.setAttribute('data-dock-changes-refresh', '1');
    refresh.setAttribute('aria-label', dockRightText('refresh'));
    refresh.title = dockRightText('refresh');
    refresh.innerHTML = DOCK_ICON_REFRESH;
    head.append(title, refresh);

    const controls = document.createElement('div');
    controls.className = 'dock-changes-scope';
    const turnSelect = document.createElement('select');
    turnSelect.className = 'dock-turn-select';
    turnSelect.setAttribute('aria-label', '选择轮次');
    turnSelect.setAttribute('data-dock-changes-scope', 'turn');
    const sessionScope = document.createElement('button');
    sessionScope.type = 'button';
    sessionScope.className = 'dock-scope-pill';
    sessionScope.setAttribute('data-dock-changes-scope', 'session');
    sessionScope.setAttribute('aria-label', dockRightText('scopeSession'));
    sessionScope.title = dockRightText('scopeSession');
    sessionScope.innerHTML = DOCK_ICON_OVERVIEW;
    controls.append(turnSelect, sessionScope);

    const status = document.createElement('div');
    status.className = 'dock-change-status';
    status.setAttribute('role', 'status');
    status.setAttribute('aria-live', 'polite');
    const list = document.createElement('div');
    list.className = 'dock-changes-list';
    el.append(head, controls, status, list);
    dockRightTrackScroll(tab.id, list);
    el.__dockRestore = list.__dockRestore;

    const turnRows = (turnId) => Array.from(state.rows.values()).filter((row) => (
        String(row._turnId || '') === String(turnId || '')
        && (row._reverted || row.effective !== false)
    )).sort((left, right) => String(left.path).localeCompare(String(right.path)));

    const addTurn = (id, preview, createdAt, token) => {
        const key = String(id === undefined || id === null ? '' : id);
        if (!key) return null;
        const old = state.turns.get(key) || {};
        const row = {
            id: key,
            preview: String(preview || old.preview || '').replace(/\s+/g, ' ').trim(),
            createdAt: createdAt || old.createdAt || '',
            token: String(token || old.token || ''),
        };
        state.turns.set(key, row);
        if (row.token) state.turnTokens.set(row.token, key);
        return row;
    };

    const accept = (raw, at, turnId, originSessionId) => {
        if (!raw || !raw.path) return;
        const token = String(raw._turnToken || raw.turn_id || '');
        let resolvedTurn = String(raw._turnId || turnId || '');
        if (token && state.turnTokens.has(token)) resolvedTurn = state.turnTokens.get(token);
        if (!resolvedTurn) resolvedTurn = String(state.selectedTurnId || '');
        if (resolvedTurn && !state.turns.has(resolvedTurn)) addTurn(resolvedTurn, '', '', token);
        const origin = String(raw._sessionId || originSessionId || state.sessionId || '');
        const key = String(raw.snapshot_id || (origin + '\0' + resolvedTurn + '\0' + String(raw.path).toLowerCase()));
        const previous = state.rows.get(key);
        if (previous && Number(previous.revision || 0) > Number(raw.revision || 0)) return;
        state.rows.set(key, Object.assign({}, previous || {}, raw, {
            at: at === undefined ? Number((previous || {}).at || 0) : at,
            _turnId: resolvedTurn,
            _turnToken: token,
            _sessionId: origin,
            _reverted: raw.reverted === true || raw.effective === false || raw._reverted === true,
        }));
    };
    state.acceptExternal = (payload) => {
        const rows = payload && Array.isArray(payload.rows) ? payload.rows : [];
        for (let i = 0; i < rows.length; i += 1) accept(rows[i], undefined, rows[i]._turnId, rows[i]._sessionId);
        render();
    };

    const resolveFocus = () => {
        const focus = state.focusRequest;
        if (!focus) return;
        let turnId = String(focus.turnId === undefined ? '' : focus.turnId);
        const token = String(focus.turnToken || '');
        if (token && state.turnTokens.has(token)) turnId = state.turnTokens.get(token);
        if (turnId && state.turns.has(turnId)) {
            state.scope = 'turn';
            state.selectedTurnId = turnId;
        }
    };

    const render = () => {
        if (state.released) return;
        resolveFocus();
        const turns = Array.from(state.turns.values()).sort((left, right) => Number(left.id) - Number(right.id));
        if (!state.selectedTurnId && turns.length) state.selectedTurnId = turns[turns.length - 1].id;
        turnSelect.replaceChildren();
        for (let i = 0; i < turns.length; i += 1) {
            const option = document.createElement('option');
            option.value = turns[i].id;
            const preview = turns[i].preview || dockRightText('turnFallback');
            option.textContent = '第 ' + (i + 1) + ' 轮 · ' + (preview.length > 42 ? preview.slice(0, 42) + '…' : preview);
            option.selected = state.scope === 'turn' && turns[i].id === String(state.selectedTurnId || '');
            turnSelect.appendChild(option);
        }
        turnSelect.disabled = turns.length === 0;
        turnSelect.classList.toggle('is-active', state.scope === 'turn');
        sessionScope.classList.toggle('is-active', state.scope === 'session');
        status.textContent = state.status || '';
        status.classList.toggle('is-error', Boolean(state.statusError));
        list.replaceChildren();
        list.setAttribute('data-dock-selected-turn', String(state.selectedTurnId || ''));
        list.setAttribute('data-dock-session', String(state.sessionId || ''));

        let visibleTurns = state.scope === 'session'
            ? turns.slice().reverse()
            : turns.filter((turn) => turn.id === String(state.selectedTurnId || ''));
        visibleTurns = visibleTurns.filter((turn) => turnRows(turn.id).length > 0);
        if (!visibleTurns.length) {
            list.appendChild(dockRightNote(state.scope === 'turn' ? dockRightText('emptyTurnChanges') : dockRightText('emptyChanges')));
        } else {
            for (let i = 0; i < visibleTurns.length; i += 1) {
                const turnIndex = turns.findIndex((turn) => turn.id === visibleTurns[i].id);
                list.appendChild(dockRightChangeGroup(visibleTurns[i], turnIndex, turnRows(visibleTurns[i].id), state, render));
            }
        }

        const focus = state.focusRequest;
        if (!focus) return;
        const selector = focus.snapshotId
            ? '[data-dock-snapshot-id="' + CSS.escape(String(focus.snapshotId)) + '"]'
            : focus.path ? '[data-dock-change-path="' + CSS.escape(String(focus.path)) + '"]' : '';
        const target = selector ? list.querySelector(selector) : null;
        if (target) {
            const body = target.querySelector('.dock-change-body');
            const toggle = target.querySelector('.dock-change-toggle');
            if (typeof target.__dockSetExpanded === 'function') target.__dockSetExpanded(true);
            else {
                if (body) { body.classList.add('is-open'); body.setAttribute('aria-hidden', 'false'); }
                if (toggle) { toggle.classList.add('is-open'); toggle.setAttribute('aria-expanded', 'true'); }
            }
            if (toggle) toggle.focus();
            requestAnimationFrame(() => target.scrollIntoView({ block: 'center' }));
            state.focusRequest = null;
            dockRightChangeReviewFocus.delete(String(state.sessionId || ''));
        } else if (!focus.snapshotId && !focus.path && state.selectedTurnId) {
            state.focusRequest = null;
            dockRightChangeReviewFocus.delete(String(state.sessionId || ''));
        }
    };
    state.render = render;

    const mergeCachedRows = () => {
        const cached = dockRightChangeReviewRows.get(String(state.sessionId || ''));
        if (!cached) return;
        cached.forEach((row) => accept(row, undefined, row._turnId, row._sessionId));
    };

    const load = async () => {
        try {
            const pages = [];
            let before = null;
            for (let page = 0; page < DOCK_RIGHT_CHANGE_PAGE_MAX; page += 1) {
                const params = new URLSearchParams({
                    limit: String(DOCK_RIGHT_CHANGE_PAGE_LIMIT), turns: '50', event_budget: '5000', include_aux: 'false',
                });
                if (before !== null) params.set('before_index', String(before));
                const scanned = await dockRightFetchJSON('/sessions/' + encodeURIComponent(state.sessionId)
                    + '/history_snapshot?' + params.toString(), 20000);
                const response = scanned.response;
                const data = scanned.data;
                if (state.released) return;
                if (!response.ok || !data || data.ok !== true) throw new Error((data && data.error) || ('HTTP ' + response.status));
                const pageData = data.messages && typeof data.messages === 'object' ? data.messages : {};
                pages.push({ start: Number(pageData.range_start) || 0, events: Array.isArray(pageData.events) ? pageData.events : [] });
                const indexedTurns = Array.isArray(data.user_turns) ? data.user_turns : [];
                for (let i = 0; i < indexedTurns.length; i += 1) {
                    addTurn(indexedTurns[i].event_index, indexedTurns[i].preview, indexedTurns[i].created_at, indexedTurns[i].turn_id);
                }
                const start = Number(pageData.range_start);
                if (!pageData.has_older || !Number.isFinite(start) || start <= 0) break;
                before = start;
            }
            pages.sort((left, right) => left.start - right.start);
            let currentTurnId = '';
            const reviewStates = new Map();
            for (let p = 0; p < pages.length; p += 1) {
                const events = pages[p].events;
                for (let i = 0; i < events.length; i += 1) {
                    const event = events[i] || {};
                    const at = pages[p].start + i;
                    // `user_steer` deliberately does not enter this branch.
                    if (event.type === 'user') {
                        currentTurnId = String(at);
                        addTurn(currentTurnId, event.content, event.created_at, event.turn_id);
                    }
                    if (event.type === 'file_changes_reverted') {
                        (event.snapshot_ids || []).forEach((id) => reviewStates.set(String(id), true));
                    } else if (event.type === 'file_changes_restored') {
                        (event.snapshot_ids || []).forEach((id) => reviewStates.set(String(id), false));
                    }
                    const ui = event.ui;
                    const changes = ui && Array.isArray(ui.changes) ? ui.changes : [];
                    for (let j = 0; j < changes.length; j += 1) accept(changes[j], at, currentTurnId, state.sessionId);
                }
            }
            mergeCachedRows();
            state.rows.forEach((row) => {
                const snapshotId = String(row.snapshot_id || '');
                if (!reviewStates.has(snapshotId)) return;
                const isReverted = reviewStates.get(snapshotId) === true;
                row._reverted = isReverted;
                row.reverted = isReverted;
                row.effective = !isReverted;
            });
            const sortedTurns = Array.from(state.turns.values()).sort((left, right) => Number(left.id) - Number(right.id));
            if (!state.selectedTurnId && sortedTurns.length) state.selectedTurnId = sortedTurns[sortedTurns.length - 1].id;
            state.loadTries = 0;
            state.loaded = true;
            render();
        } catch (error) {
            if (state.released) return;
            state.loadTries = (state.loadTries || 0) + 1;
            if (state.loadTries <= 2) { setTimeout(() => { void load(); }, 400); return; }
            console.warn('[dock details] changes load failed', error);
            list.replaceChildren(dockRightNote(dockRightText('loadFailed') + ': ' + (error && error.message ? error.message : error)));
        }
    };

    turnSelect.addEventListener('change', () => {
        state.scope = 'turn';
        state.selectedTurnId = turnSelect.value;
        render();
    });
    sessionScope.addEventListener('click', () => { state.scope = 'session'; render(); });
    refresh.addEventListener('click', () => {
        state.rows.clear(); state.turns.clear(); state.turnTokens.clear(); state.selectedTurnId = null;
        state.loadTries = 0; state.loaded = false; state.status = '';
        void load();
    });
    state.listener = (event) => {
        const detail = event && event.detail ? event.detail : {};
        const ownerSessionId = String(detail.rootSessionId || detail.sessionId || '');
        if (ownerSessionId && ownerSessionId !== String(state.sessionId)) return;
        const incoming = detail.event || {};
        if (incoming.type === 'user') {
            const id = String(Number.isFinite(Number(detail.eventIndex)) ? Number(detail.eventIndex) : Date.now());
            addTurn(id, incoming.content, incoming.created_at, incoming.turn_id);
            state.selectedTurnId = id;
            state.scope = 'turn';
            render();
            return;
        }
        if (incoming.type === 'run_started' || incoming.type === 'run_finished'
            || incoming.type === 'run_failed' || incoming.type === 'run_cancelled') {
            requestAnimationFrame(render);
            return;
        }
        if (incoming.type === 'file_changes_reverted' || incoming.type === 'file_changes_restored') {
            dockRightMarkChangeRows(incoming.snapshot_ids || [], incoming.type === 'file_changes_reverted', state);
            render();
            return;
        }
        const changes = incoming.ui && Array.isArray(incoming.ui.changes) ? incoming.ui.changes : [];
        for (let i = 0; i < changes.length; i += 1) accept(changes[i], undefined, state.selectedTurnId, detail.sessionId);
        if (changes.length) render();
    };
    document.addEventListener('myagent:ui-event', state.listener);
    mergeCachedRows();
    render();
    void load();
    setTimeout(() => { if (!state.released && !state.loaded) void load(); }, 2000);
    return el;
}

function dockRightReviewRunning() {
    const stream = document.getElementById('chat-stream');
    return Boolean(stream && stream.querySelector('.process-aggregate.is-running'));
}

function dockRightReviewSummary(rows) {
    let added = 0; let removed = 0; let omitted = 0;
    rows.filter((row) => !row._reverted).forEach((row) => {
        if (Number.isFinite(Number(row.added)) && Number.isFinite(Number(row.removed))) {
            added += Number(row.added); removed += Number(row.removed);
        } else if (row.diff_omitted_reason !== 'directory') omitted += 1;
    });
    return rows.length + ' 个文件 · +' + added + ' −' + removed + (omitted ? ' · ' + omitted + ' 个未统计' : '');
}

function dockRightOmittedReason(row) {
    const reason = String(row.diff_omitted_reason || '');
    const labels = {
        directory: '目录结构改动，无逐行差分', binary: '二进制文件，无逐行差分',
        too_many_lines: '文件超过 20,000 行，已省略逐行差分',
        too_complex: '改动过于复杂，已省略逐行差分；仍可撤销',
        snapshot_missing: '未保存基线内容，无法预览或撤销',
        too_large_bytes: '文件超过 1 MiB，已省略逐行差分',
    };
    const before = row.before || {}; const after = row.after || {};
    return (labels[reason] || dockRightText('diff')) + ' · '
        + dockRightSize(before.bytes || 0) + ' / ' + (before.lines || 0) + ' 行 → '
        + dockRightSize(after.bytes || 0) + ' / ' + (after.lines || 0) + ' 行';
}

function dockRightChangeGroup(turn, turnIndex, rows, state, rerender) {
    const section = document.createElement('section');
    section.className = 'dock-change-turn';
    section.setAttribute('data-dock-turn-id', turn.id);
    const head = document.createElement('div');
    head.className = 'dock-change-turn-head';
    const copy = document.createElement('div');
    copy.className = 'dock-change-turn-copy';
    const name = document.createElement('strong');
    name.textContent = '第 ' + (turnIndex + 1) + ' 轮';
    const preview = document.createElement('span');
    preview.textContent = turn.preview || dockRightText('turnFallback');
    preview.title = turn.preview || '';
    const summary = document.createElement('span');
    summary.className = 'dock-change-turn-summary';
    summary.textContent = dockRightReviewSummary(rows);
    copy.append(name, preview, summary);
    const actions = document.createElement('div');
    actions.className = 'dock-change-turn-actions';
    const active = rows.filter((row) => !row._reverted && row.undoable !== false && row.diff_omitted_reason !== 'snapshot_missing');
    const reverted = rows.filter((row) => row._reverted && row.undoable !== false && row.diff_omitted_reason !== 'snapshot_missing');
    const running = dockRightReviewRunning();
    const undoAll = document.createElement('button');
    undoAll.type = 'button'; undoAll.className = 'dock-link-button'; undoAll.textContent = dockRightText('undoAll');
    undoAll.hidden = active.length === 0; undoAll.disabled = running;
    const restoreAll = document.createElement('button');
    restoreAll.type = 'button'; restoreAll.className = 'dock-link-button'; restoreAll.textContent = dockRightText('restoreAll');
    restoreAll.hidden = reverted.length === 0; restoreAll.disabled = running;
    if (running) { undoAll.title = dockRightText('taskRunningReview'); restoreAll.title = dockRightText('taskRunningReview'); }
    undoAll.addEventListener('click', () => { void dockRightBulkChangeAction(active, 'undo', state, rerender); });
    restoreAll.addEventListener('click', () => { void dockRightBulkChangeAction(reverted, 'restore', state, rerender); });
    actions.append(undoAll, restoreAll);
    head.append(copy, actions);
    section.appendChild(head);
    for (let i = 0; i < rows.length; i += 1) section.appendChild(dockRightChangeRow(rows[i], state, rerender));
    return section;
}

/** One complete change row: path, counts/omission, diff, reverted state and action. */
function dockRightChangeRow(row, state, rerender) {
    const expandKey = String(row.snapshot_id || row.path || '');
    const item = document.createElement('article');
    item.className = 'dock-change' + (row._reverted ? ' is-reverted' : '');
    item.setAttribute('data-dock-snapshot-id', String(row.snapshot_id || ''));
    item.setAttribute('data-dock-change-path', String(row.path || ''));
    const head = document.createElement('div'); head.className = 'dock-change-head';
    const toggle = document.createElement('button');
    toggle.type = 'button'; toggle.className = 'dock-change-toggle'; toggle.textContent = '›';
    toggle.setAttribute('aria-expanded', 'false');
    const name = document.createElement('span');
    name.className = 'dock-change-name'; name.textContent = dockRightBasename(row.path); name.title = row.path;
    const dir = document.createElement('span');
    dir.className = 'dock-change-dir'; dir.textContent = dockRightRelPath(row.path).replace(/[^/]+$/, '');
    const stats = document.createElement('span'); stats.className = 'dock-change-stats';
    if (Number.isFinite(Number(row.added)) && Number.isFinite(Number(row.removed))) {
        const added = document.createElement('span'); added.className = 'dock-change-added'; added.textContent = '+' + Number(row.added);
        const removed = document.createElement('span'); removed.className = 'dock-change-removed'; removed.textContent = '−' + Number(row.removed);
        stats.append(added, removed);
    } else {
        stats.textContent = dockRightText('noLineStats');
        stats.title = dockRightOmittedReason(row);
    }
    if (row._reverted) {
        const tag = document.createElement('span'); tag.className = 'dock-change-reverted'; tag.textContent = dockRightText('undone');
        stats.appendChild(tag);
    }
    const action = document.createElement('button');
    action.type = 'button'; action.className = 'dock-link-button dock-change-action';
    action.textContent = row._reverted ? dockRightText('restore') : dockRightText('undo');
    action.disabled = dockRightReviewRunning() || row.undoable === false || row.diff_omitted_reason === 'snapshot_missing';
    if (dockRightReviewRunning()) action.title = dockRightText('taskRunningReview');
    action.addEventListener('click', (event) => {
        event.stopPropagation();
        void dockRightRunChangeAction([row], row._reverted ? 'restore' : 'undo', state, rerender);
    });
    head.append(toggle, name, dir, stats, action);
    const body = document.createElement('div'); body.className = 'dock-change-body'; body.setAttribute('aria-hidden', 'true');
    const diffLines = row.diff ? String(row.diff).split('\n') : null;
    let diffPre = null; let nextDiffLine = 0; let diffFrame = null; let bodyReady = false;
    const ensureBody = () => {
        if (bodyReady) return;
        bodyReady = true;
        if (diffLines) {
            diffPre = document.createElement('pre'); diffPre.className = 'dock-change-diff';
            body.appendChild(diffPre);
        } else body.appendChild(dockRightNote(dockRightOmittedReason(row)));
    };
    const renderDiffChunk = () => {
        diffFrame = null;
        if (!diffPre || !body.classList.contains('is-open') || !body.isConnected) return;
        const fragment = document.createDocumentFragment();
        const end = Math.min(diffLines.length, nextDiffLine + 240);
        for (; nextDiffLine < end; nextDiffLine += 1) {
            const text = diffLines[nextDiffLine];
            const line = document.createElement('span');
            const file = text.startsWith('+++') || text.startsWith('---');
            const prefix = text.charAt(0);
            line.className = 'dock-diff-line' + (file ? ' is-file' : prefix === '+' ? ' is-added' : prefix === '-' ? ' is-removed' : prefix === '@' ? ' is-hunk' : '');
            line.textContent = text + '\n'; fragment.appendChild(line);
        }
        diffPre.appendChild(fragment);
        if (nextDiffLine < diffLines.length) diffFrame = requestAnimationFrame(renderDiffChunk);
    };
    const setExpanded = (opening) => {
        if (state && state.expandedChanges) {
            if (opening) state.expandedChanges.add(expandKey);
            else state.expandedChanges.delete(expandKey);
        }
        ensureBody();
        body.classList.toggle('is-open', opening);
        body.setAttribute('aria-hidden', opening ? 'false' : 'true');
        toggle.classList.toggle('is-open', opening);
        toggle.setAttribute('aria-expanded', opening ? 'true' : 'false');
        if (opening && diffLines && nextDiffLine < diffLines.length && diffFrame === null) renderDiffChunk();
        if (!opening && diffFrame !== null) { cancelAnimationFrame(diffFrame); diffFrame = null; }
    };
    const toggleBody = () => setExpanded(!body.classList.contains('is-open'));
    toggle.addEventListener('click', (event) => { event.stopPropagation(); toggleBody(); });
    head.addEventListener('click', (event) => { if (event.target !== action) toggleBody(); });
    item.append(head, body);
    item.__dockSetExpanded = setExpanded;
    // 执行期间新改动注册会全量重建列表；恢复用户此前打开的详情，避免"被关掉"。
    if (state && state.expandedChanges && state.expandedChanges.has(expandKey)) setExpanded(true);
    return item;
}

function dockRightOperationId(action) {
    return globalThis.crypto && typeof globalThis.crypto.randomUUID === 'function'
        ? globalThis.crypto.randomUUID() : action + '-' + Date.now() + '-' + Math.random();
}

function dockRightMarkChangeRows(snapshotIds, reverted, onlyState) {
    const ids = new Set((snapshotIds || []).map(String));
    const states = onlyState ? [onlyState] : Object.values(dockRightState.tabState).filter((state) => state && state.changeReview);
    states.forEach((state) => state.rows.forEach((row) => {
        if (ids.has(String(row.snapshot_id || ''))) {
            row._reverted = reverted; row.reverted = reverted; row.effective = !reverted;
        }
    }));
    states.forEach((state) => {
        if (state !== onlyState && typeof state.render === 'function') state.render();
    });
    dockRightChangeReviewRows.forEach((rows) => rows.forEach((row) => {
        if (ids.has(String(row.snapshot_id || ''))) {
            row._reverted = reverted; row.reverted = reverted; row.effective = !reverted;
        }
    }));
}

async function dockRightRunChangeAction(rows, action, state, rerender) {
    if (!rows.length || dockRightReviewRunning()) return;
    state.status = action === 'undo' ? dockRightText('undoing') : dockRightText('restoring');
    state.statusError = false; rerender();
    const groups = new Map();
    rows.forEach((row) => {
        const sid = String(row._sessionId || state.sessionId || '');
        if (!groups.has(sid)) groups.set(sid, []);
        groups.get(sid).push(row);
    });
    const changed = [];
    try {
        for (const [sid, group] of groups.entries()) {
            const response = await fetch('/sessions/' + encodeURIComponent(sid) + '/change-reviews/' + action, {
                method: 'POST', credentials: 'same-origin', cache: 'no-store',
                headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    snapshot_ids: group.map((row) => row.snapshot_id), operation_id: dockRightOperationId(action),
                }),
            });
            const data = await response.json().catch(() => ({}));
            if (!response.ok || data.ok !== true) {
                const paths = Array.isArray(data.paths) && data.paths.length ? '\n' + data.paths.join('\n') : '';
                throw new Error(String(data.error || ('HTTP ' + response.status)) + paths);
            }
            changed.push.apply(changed, data.snapshot_ids || group.map((row) => row.snapshot_id));
        }
        dockRightMarkChangeRows(changed, action === 'undo');
        state.status = rows.length > 1
            ? (action === 'undo' ? dockRightText('allUndone') : dockRightText('allRestored'))
            : (action === 'undo' ? dockRightText('undone') : dockRightText('restored'));
        document.dispatchEvent(new CustomEvent('myagent:change-review-state', {
            detail: { snapshotIds: changed, reverted: action === 'undo' },
        }));
    } catch (error) {
        state.status = String(error && error.message ? error.message : error); state.statusError = true;
    }
    rerender();
}

async function dockRightBulkChangeAction(rows, action, state, rerender) {
    if (!rows.length) return;
    await dockRightRunChangeAction(rows, action, state, rerender);
}

/** Keep plugin-owned child-agent rows available to the built-in details page. */
function dockRightRegisterChangeReviewRows(payload) {
    const sessionId = String(payload && payload.sessionId || dockRightSurfaceKey(dockRightState.sessionId || currentSessionId) || '');
    const incoming = payload && Array.isArray(payload.rows) ? payload.rows : [];
    if (!sessionId || !incoming.length) return;
    let cached = dockRightChangeReviewRows.get(sessionId);
    if (!cached) { cached = new Map(); dockRightChangeReviewRows.set(sessionId, cached); }
    incoming.forEach((row) => {
        if (!row || !row.path) return;
        const key = String(row._sessionId || '') + '\0' + String(row.snapshot_id || row.path);
        const previous = cached.get(key);
        if (!previous || Number(previous.revision || 0) <= Number(row.revision || 0)) cached.set(key, Object.assign({}, row));
    });
    Object.values(dockRightState.tabState).forEach((state) => {
        if (state && state.changeReview && String(state.sessionId || '') === sessionId
            && typeof state.acceptExternal === 'function') state.acceptExternal(payload);
    });
}

/** Expand the details column, open Modification History, and deep-link to a turn/file. */
function dockRightOpenChangeReview(options) {
    const sessionId = String(dockRightSurfaceKey(dockRightState.sessionId || currentSessionId) || '');
    if (!sessionId) return;
    const focus = Object.assign({}, options || {});
    dockRightChangeReviewFocus.set(sessionId, focus);
    Object.values(dockRightState.tabState).forEach((state) => {
        if (state && state.changeReview && String(state.sessionId || '') === sessionId) {
            state.focusRequest = focus;
            state.scope = 'turn';
            if (typeof state.render === 'function') state.render();
        }
    });
    dockRightOpenPageKind('changes', undefined, undefined, true);
    if (!dockRightExpanded()) dockRightToggle();
    else dockRightRender();
}

/** Release whatever a tab's body started. */
function dockRightDisposeTab(tabId) {
    const state = dockRightState.tabState[tabId];
    if (!state) return;
    state.released = true;
    if (state.listener) document.removeEventListener('myagent:ui-event', state.listener);
    if (state.abort) {
        try { state.abort.abort(); } catch (error) { /* ignore */ }
    }
    delete dockRightState.tabState[tabId];
}

// ── init ─────────────────────────────────────────────────────────────────────

/** Wire the column's session hook and expose its public API. */
function dockRightInit() {
    if (typeof document === 'undefined') return;
    dockRightEnsureMounted();
    dockRightWatchSessions();
    if (typeof switchSession === 'function' && !dockRightState.switchWrapped) {
        dockRightState.switchWrapped = true;
        const original = switchSession;
        switchSession = async function dockRightWrappedSwitchSession(sessionId, opts) {
            const result = await original(sessionId, opts);
            try {
                if (result !== false) dockRightHandleSessionSwitch(sessionId);
            } catch (error) {
                console.warn('dock details column switch failed', error);
            }
            return result;
        };
    }
    globalThis.MyAgentDock = Object.assign(globalThis.MyAgentDock || {}, {
            /** Register one content type; the column renders tabs it claims. */
            registerTabType: (definition) => dockTabRegistry.register(definition),
            /** Open a resource address (`myagent-resource://<type>/…`) in the column. */
            openResource: (address) => dockRightOpenResource(String(address || '')),
            /** Switch the app to another session; its own column state follows. */
            openSession: (sessionId) => {
                const sid = String(sessionId || '');
                if (!sid || typeof switchSession !== 'function') return undefined;
                // The wrapper above keeps the app's own sidebar clicks in sync;
                // calling the hook here as well makes this API deterministic
                // even if some path reaches switchSession before the wrapper
                // is installed.
                return Promise.resolve(switchSession(sid)).then((result) => {
                    try {
                        if (result !== false) dockRightHandleSessionSwitch(sid);
                    } catch (error) {
                        console.warn('dock details column switch failed', error);
                    }
                    return result;
                });
            },
            /** Open (or keep) the details column. */
            openDetails: () => {
                dockRightEnsureMounted();
                if (!dockRightExpanded()) dockRightToggle();
                else dockRightRender();
            },
            /** Collapse the details column. */
            closeDetails: () => {
                if (dockRightExpanded() && dockRightState.sessionId) {
                    dockActionToggleExpanded(dockRightState.sessionId, dockRightSeed(), DOCK_RIGHT_AREA);
                    dockRightRender();
                }
            },
            /** Toggle the details column. */
            toggleDetails: () => dockRightToggle(),
            /** Open one of the column's pages by kind ('guide' | 'files' | 'changes'). */
            openDetailsTab: (kind) => dockRightOpenPageKind(String(kind)),
            /** Open Modification History at a specific official user turn/file. */
            openChangeReview: (options) => dockRightOpenChangeReview(options),
            /** Feed child-agent review rows into the session-level details page. */
            registerChangeReviewRows: (payload) => dockRightRegisterChangeReviewRows(payload),
            /** Open a file in the column by workspace-relative path. */
            openDetailsFile: (rel) => dockRightOpenResource(DOCK_RIGHT_FILE_PREFIX + encodeURIComponent(String(rel || ''))),
            /** The tree's open policy: text in the column, anything else in the system app. */
            openPathSmart: (pathValue) => dockRightOpenPathSmart(String(pathValue || '')),
            /** Whether a path would open inline (text) rather than through the system app. */
            isTextPath: (pathValue) => dockRightIsTextPath(String(pathValue || '')),
            /** The surface key a session resolves to (a subagent maps to its parent). */
            surfaceKey: (sessionId) => dockRightSurfaceKey(String(sessionId || '')),
            /** The details column's state, for tests and plugins. */
            detailsState: () => {
                const surface = dockRightState.sessionId ? dockSurfaceOf(dockRightState.sessionId, DOCK_RIGHT_AREA) : null;
                return surface ? surface.layout : null;
            },
            /** The current session id, for scripts and tests. */
            sessionId: () => (typeof currentSessionId === 'string' ? currentSessionId : null),
    });
    document.dispatchEvent(new CustomEvent('myagent:dock-ready', { detail: { api: globalThis.MyAgentDock } }));
}

if (typeof document !== 'undefined') {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', dockRightInit);
    else dockRightInit();
}
