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

/** How much of the session history the change list scans, in pages of 500 events. */
const DOCK_RIGHT_CHANGE_PAGE_LIMIT = 500;
const DOCK_RIGHT_CHANGE_PAGE_MAX = 8;

/** Address prefix resource viewers claim. */
const DOCK_RIGHT_FILE_PREFIX = 'myagent-resource://file/';

/** Text reads are capped here; the endpoint truncates and says so. */
const DOCK_RIGHT_TEXT_MAX_BYTES = 200000;

/** Suffixes rendered as an inline image. Mirrors the backend's viewable image set. */
const DOCK_RIGHT_IMAGE_SUFFIXES = ['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'svg', 'ico', 'avif', 'jfif', 'tif', 'tiff'];

/** Suffixes rendered with a media element. */
const DOCK_RIGHT_AUDIO_SUFFIXES = ['mp3', 'wav', 'ogg', 'oga', 'm4a', 'aac', 'flac', 'opus', 'weba'];
const DOCK_RIGHT_VIDEO_SUFFIXES = ['mp4', 'webm', 'ogv', 'mov', 'm4v', 'mkv'];

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
};

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
        scopeTurn: '本轮',
        scopeSession: '本次会话',
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
    host.className = 'dock-rightbar';
    host.setAttribute('data-dock-rightbar', '1');
    host.setAttribute('aria-label', dockRightText('toggle'));
    host.hidden = true;
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
        dockActionSetMode(sessionId, surface.layout.mode === 'fullscreen' ? 'push' : 'fullscreen', dockRightSeed(), DOCK_RIGHT_AREA);
        dockRightRender();
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
    const sessionId = currentSessionId;
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
    if (window.innerWidth < 768) dockActionSetMode(sessionId, 'fullscreen', dockRightSeed(), DOCK_RIGHT_AREA);
    dockRightRender();
}

/** Show or hide the column and sync everything the current snapshot implies. */
function dockRightRender() {
    const host = dockRightState.host;
    if (!host) return;
    const sessionId = dockRightState.sessionId;
    const surface = sessionId ? dockSurfaceOf(sessionId, DOCK_RIGHT_AREA) : null;
    const expanded = !!(surface && surface.layout.expanded);
    host.hidden = !expanded;
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
    const fullscreen = surface.layout.mode === 'fullscreen';
    host.classList.toggle('is-fullscreen', fullscreen);
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

/** The session-switch hook: show the entering session's own column surface. */
function dockRightHandleSessionSwitch(sessionId) {
    if (!dockRightState.host) return;
    const sid = String(sessionId || '');
    if (!sid) return;
    if (dockRightState.sessionId === sid) return;
    if (!dockSurfaceExists(sid, DOCK_RIGHT_AREA)) {
        dockRightState.sessionId = sid;
        dockRightRender();
        return;
    }
    dockRightState.sessionId = sid;
    dockRightRender();
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
function dockRightOpenPageKind(kind, replaceTab, paneId) {
    dockRightEnsureMounted();
    const sessionId = dockRightState.sessionId || currentSessionId;
    if (!sessionId) return;
    const address = dockPageAddress(String(kind));
    const definition = dockTabRegistry.get(String(kind));
    dockActionOpenContent(sessionId, {
        kind: String(kind),
        contentId: address,
        title: definition ? dockTitleOf(definition, address) : String(kind),
        replaceTab: replaceTab,
        paneId: paneId,
        revealIfOpened: false,
    }, dockRightSeed(), null, DOCK_RIGHT_AREA);
    dockRightState.sessionId = sessionId;
    dockRightRender();
}

/** The workspace tree page. */
function dockRightFilesBody(tab) {
    const el = document.createElement('div');
    el.className = 'dock-files';
    el.setAttribute('data-dock-files', tab.id);
    const head = document.createElement('div');
    head.className = 'dock-files-head';
    const title = document.createElement('span');
    title.className = 'dock-files-title';
    title.textContent = dockRightText('files');
    const refresh = document.createElement('button');
    refresh.type = 'button';
    refresh.className = 'dock-link-button';
    refresh.textContent = dockRightText('refresh');
    const tree = document.createElement('div');
    tree.className = 'dock-files-tree';
    refresh.addEventListener('click', () => {
        tree.replaceChildren();
        void dockRightLoadDir(tree, '', 0);
    });
    head.appendChild(title);
    head.appendChild(refresh);
    el.appendChild(head);
    el.appendChild(tree);
    dockRightTrackScroll(tab.id, tree);
    el.__dockRestore = tree.__dockRestore;
    void dockRightLoadDir(tree, '', 0);
    return el;
}

/** Load one directory level into `container`, recursively expandable. */
async function dockRightLoadDir(container, dir, depth) {
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
    const sessionId = dockRightState.sessionId || currentSessionId;
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
    const openSystem = document.createElement('button');
    openSystem.type = 'button';
    openSystem.className = 'dock-link-button';
    openSystem.textContent = dockRightText('openSystem');
    openSystem.addEventListener('click', () => {
        void fetch('/api/open-workspace-file?' + new URLSearchParams({ rel: rel }));
    });
    head.appendChild(name);
    head.appendChild(openSystem);
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
    } else if (DOCK_RIGHT_AUDIO_SUFFIXES.indexOf(suffix) >= 0 || DOCK_RIGHT_VIDEO_SUFFIXES.indexOf(suffix) >= 0) {
        const media = document.createElement(DOCK_RIGHT_VIDEO_SUFFIXES.indexOf(suffix) >= 0 ? 'video' : 'audio');
        media.className = 'dock-doc-media';
        media.controls = true;
        media.src = '/api/workspace-media?' + new URLSearchParams({ rel: rel });
        content.appendChild(media);
    } else if (DOCK_RIGHT_BINARY_SUFFIXES.indexOf(suffix) >= 0) {
        // Feedback #5: a non-text file goes straight to the system-app card
        // instead of showing mojibake.
        content.appendChild(dockRightSystemCard(rel));
    } else {
        void dockRightLoadText(content, state);
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
 * The session's file changes, aggregated from the `ui.changes` payloads in its
 * history, in two scopes: the current round (everything after the latest user
 * turn — the default, matching the Change Review plugin's "this run" wording)
 * and the whole session (feedback #4).
 */
function dockRightChangesBody(tab) {
    const el = document.createElement('div');
    el.className = 'dock-changes';
    el.setAttribute('data-dock-changes', tab.id);
    const sessionId = dockRightState.sessionId || currentSessionId;
    const state = {
        sessionId: sessionId,
        rows: new Map(),
        released: false,
        listener: null,
        abort: null,
        sequence: 0,
        turnStart: -1,
        scope: 'turn',
        pills: null,
        loaded: false,
    };
    dockRightState.tabState[tab.id] = state;

    const head = document.createElement('div');
    head.className = 'dock-changes-head';
    const title = document.createElement('span');
    title.className = 'dock-changes-title';
    title.textContent = dockRightText('changes');
    const pills = document.createElement('div');
    pills.className = 'dock-changes-scope';
    const scopeDefs = [
        { id: 'turn', label: dockRightText('scopeTurn') },
        { id: 'session', label: dockRightText('scopeSession') },
    ];
    for (let i = 0; i < scopeDefs.length; i += 1) {
        const pill = document.createElement('button');
        pill.type = 'button';
        pill.className = 'dock-scope-pill' + (scopeDefs[i].id === 'turn' ? ' is-active' : '');
        pill.setAttribute('data-dock-changes-scope', scopeDefs[i].id);
        pill.textContent = scopeDefs[i].label;
        pill.addEventListener('click', () => {
            state.scope = scopeDefs[i].id;
            render();
        });
        pills.appendChild(pill);
    }
    state.pills = pills;
    const refresh = document.createElement('button');
    refresh.type = 'button';
    refresh.className = 'dock-link-button';
    refresh.textContent = dockRightText('refresh');
    head.appendChild(title);
    head.appendChild(pills);
    head.appendChild(refresh);
    const list = document.createElement('div');
    list.className = 'dock-changes-list';
    el.appendChild(head);
    el.appendChild(list);
    dockRightTrackScroll(tab.id, list);
    el.__dockRestore = list.__dockRestore;

    const scopedRows = () => {
        const all = Array.from(state.rows.values());
        const rows = state.scope === 'turn'
            ? all.filter((row) => Number(row.at || 0) > state.turnStart)
            : all;
        return rows.sort((left, right) => String(left.path).localeCompare(String(right.path)));
    };
    const render = () => {
        if (state.released) return;
        const buttons = pills.querySelectorAll('.dock-scope-pill');
        for (let i = 0; i < buttons.length; i += 1) {
            const active = buttons[i].getAttribute('data-dock-changes-scope') === state.scope;
            buttons[i].classList.toggle('is-active', active);
        }
        list.replaceChildren();
        list.setAttribute('data-dock-turn-start', String(state.turnStart));
        list.setAttribute('data-dock-sequence', String(state.sequence));
        list.setAttribute('data-dock-session', String(state.sessionId || ''));
        const rows = scopedRows();
        if (rows.length === 0) {
            list.appendChild(dockRightNote(state.scope === 'turn' ? dockRightText('emptyTurnChanges') : dockRightText('emptyChanges')));
            return;
        }
        for (let i = 0; i < rows.length; i += 1) list.appendChild(dockRightChangeRow(rows[i], state, render));
    };
    const accept = (raw, at) => {
        if (!raw || !raw.path) return;
        const key = String(raw.path).toLowerCase();
        const previous = state.rows.get(key);
        if (previous && Number(previous.revision) > Number(raw.revision)) return;
        state.rows.set(key, Object.assign({}, raw, {
            at: at === undefined ? (state.sequence += 1) : at,
            _reverted: raw.reverted === true || raw.effective === false,
        }));
    };
    const load = async () => {
        try {
            const pages = [];
            let before = null;
            for (let page = 0; page < DOCK_RIGHT_CHANGE_PAGE_MAX; page += 1) {
                const params = new URLSearchParams({
                    limit: String(DOCK_RIGHT_CHANGE_PAGE_LIMIT),
                    turns: '50',
                    event_budget: '5000',
                    include_aux: 'false',
                });
                if (before !== null) params.set('before_index', String(before));
                const url = '/sessions/' + encodeURIComponent(state.sessionId) + '/history_snapshot?' + params.toString();
                const scanned = await dockRightFetchJSON(url, 20000);
                const response = scanned.response;
                const data = scanned.data;
                if (state.released) return;
                if (!response.ok || !data || data.ok !== true) throw new Error((data && data.error) || ('HTTP ' + response.status));
                const pageData = data.messages && typeof data.messages === 'object' ? data.messages : {};
                pages.push({ start: Number(pageData.range_start) || 0, events: Array.isArray(pageData.events) ? pageData.events : [] });
                const start = Number(pageData.range_start);
                if (!pageData.has_older || !Number.isFinite(start) || start <= 0) break;
                before = start;
            }
            // Pages arrive newest-first: walk the oldest run's events first so
            // `sequence` grows with time and the latest user turn is the last
            // boundary seen.
            pages.sort((left, right) => left.start - right.start);
            let sequence = 0;
            let turnStart = -1;
            for (let p = 0; p < pages.length; p += 1) {
                const events = pages[p].events;
                for (let i = 0; i < events.length; i += 1) {
                    sequence += 1;
                    if (events[i] && events[i].type === 'user') turnStart = sequence;
                    const ui = events[i] && events[i].ui;
                    const changes = ui && Array.isArray(ui.changes) ? ui.changes : null;
                    if (changes) for (let j = 0; j < changes.length; j += 1) accept(changes[j], sequence);
                }
            }
            state.sequence = sequence;
            state.turnStart = turnStart;
            state.loadTries = 0;
            state.loaded = true;
            render();
        } catch (error) {
            if (state.released) return;
            state.loadTries = (state.loadTries || 0) + 1;
            if (state.loadTries <= 2) {
                // One silent retry: the first attempt can lose a race with the
                // app's own session-switch traffic.
                setTimeout(() => { void load(); }, 400);
                return;
            }
            console.warn('[dock details] changes load failed', error);
            list.replaceChildren(dockRightNote(dockRightText('loadFailed') + ': ' + (error && error.message ? error.message : error)));
        }
    };
    refresh.addEventListener('click', () => {
        state.rows.clear();
        state.sequence = 0;
        state.loadTries = 0;
        void load();
    });
    state.listener = (event) => {
        const detail = event && event.detail ? event.detail : {};
        if (detail.sessionId && String(detail.sessionId) !== String(state.sessionId)) return;
        // A new user turn moves the "this round" boundary forward the moment
        // it happens; without this the scope kept showing the previous round's
        // changes until the next full rescan.
        if (detail.event && detail.event.type === 'user') {
            state.sequence += 1;
            state.turnStart = state.sequence;
            render();
            return;
        }
        const ui = detail.event && detail.event.ui;
        const changes = ui && Array.isArray(ui.changes) ? ui.changes : null;
        if (!changes) return;
        for (let i = 0; i < changes.length; i += 1) accept(changes[i]);
        render();
    };
    document.addEventListener('myagent:ui-event', state.listener);
    // The initial scan starts a beat after the body mounts: opening a tab
    // happens in the middle of the app's own session-switch fetches, and the
    // very first attempt raced them into an early failure (the refresh button
    // always worked). A short delay plus the retry below makes the first open
    // as reliable as refresh.
    void load();
    // Watchdog: if neither the scan nor the live stream has produced anything
    // two seconds in, run the scan again (a dropped first attempt must not
    // leave the page empty until the user finds the refresh button).
    setTimeout(() => {
        if (state.released || state.loaded) return;
        void load();
    }, 2000);
    return el;
}

/** One change row: path, operation, line counts, expandable diff, undo/restore. */
function dockRightChangeRow(row, state, rerender) {
    const item = document.createElement('article');
    item.className = 'dock-change' + (row._reverted ? ' is-reverted' : '');
    item.setAttribute('data-dock-change-at', String(row.at === undefined ? '' : row.at));
    const head = document.createElement('div');
    head.className = 'dock-change-head';
    const toggle = document.createElement('button');
    toggle.type = 'button';
    toggle.className = 'dock-change-toggle';
    toggle.textContent = '▸';
    const name = document.createElement('span');
    name.className = 'dock-change-name';
    name.textContent = dockRightBasename(row.path);
    name.title = row.path;
    const dir = document.createElement('span');
    dir.className = 'dock-change-dir';
    dir.textContent = dockRightRelPath(row.path).replace(/[^/]+$/, '');
    const stats = document.createElement('span');
    stats.className = 'dock-change-stats';
    if (Number.isFinite(Number(row.added)) && Number(row.added) > 0) {
        const added = document.createElement('span');
        added.className = 'dock-change-added';
        added.textContent = '+' + row.added;
        stats.appendChild(added);
    }
    if (Number.isFinite(Number(row.removed)) && Number(row.removed) > 0) {
        const removed = document.createElement('span');
        removed.className = 'dock-change-removed';
        removed.textContent = '-' + row.removed;
        stats.appendChild(removed);
    }
    const action = document.createElement('button');
    action.type = 'button';
    action.className = 'dock-link-button dock-change-action';
    action.textContent = row._reverted ? dockRightText('restore') : dockRightText('undo');
    action.addEventListener('click', (event) => {
        event.stopPropagation();
        void dockRightChangeAction(row, action, state, rerender);
    });
    head.appendChild(toggle);
    head.appendChild(name);
    head.appendChild(dir);
    head.appendChild(stats);
    head.appendChild(action);
    const body = document.createElement('div');
    body.className = 'dock-change-body';
    body.hidden = true;
    if (row.diff) {
        const pre = document.createElement('pre');
        pre.className = 'dock-change-diff';
        const lines = String(row.diff).split('\n');
        for (let i = 0; i < lines.length; i += 1) {
            const line = document.createElement('span');
            const prefix = lines[i].charAt(0);
            line.className = 'dock-diff-line'
                + (prefix === '+' ? ' is-added' : prefix === '-' ? ' is-removed' : prefix === '@' ? ' is-hunk' : '');
            line.textContent = lines[i] + '\n';
            pre.appendChild(line);
        }
        body.appendChild(pre);
    } else {
        body.appendChild(dockRightNote(row.diff_omitted_reason || dockRightText('diff')));
    }
    toggle.addEventListener('click', () => {
        body.hidden = !body.hidden;
        toggle.textContent = body.hidden ? '▸' : '▾';
    });
    head.addEventListener('click', (event) => {
        if (event.target === action) return;
        body.hidden = !body.hidden;
        toggle.textContent = body.hidden ? '▸' : '▾';
    });
    item.appendChild(head);
    item.appendChild(body);
    return item;
}

/** Undo or restore one change through the Change Review routes. */
async function dockRightChangeAction(row, button, state, rerender) {
    const action = row._reverted ? 'restore' : 'undo';
    button.disabled = true;
    try {
        const response = await fetch('/sessions/' + encodeURIComponent(state.sessionId) + '/change-reviews/' + action, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ snapshot_ids: [row.snapshot_id] }),
        });
        const data = await response.json().catch(() => null);
        if (!response.ok || !data || data.ok !== true) {
            throw new Error((data && data.error) || ('HTTP ' + response.status));
        }
        row._reverted = action === 'undo';
        row.effective = action !== 'undo';
        rerender();
    } catch (error) {
        button.disabled = false;
        button.textContent = dockRightText(action === 'undo' ? 'undo' : 'restore');
        button.title = String(error && error.message ? error.message : error);
        button.classList.add('is-error');
    }
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
            /** Open a file in the column by workspace-relative path. */
            openDetailsFile: (rel) => dockRightOpenResource(DOCK_RIGHT_FILE_PREFIX + encodeURIComponent(String(rel || ''))),
            /** The tree's open policy: text in the column, anything else in the system app. */
            openPathSmart: (pathValue) => dockRightOpenPathSmart(String(pathValue || '')),
            /** Whether a path would open inline (text) rather than through the system app. */
            isTextPath: (pathValue) => dockRightIsTextPath(String(pathValue || '')),
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
