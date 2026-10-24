/** Stable page containers stay connected while Dock moves their lightweight seats. */
const DOCK_APP_SURFACE_KEY = 'myagent:application';
const dockPluginPages = new Map();
/** DSH ui-primitives plugin glyph, also used for the category and page list. */
const DOCK_PLUGIN_ICON = `<svg viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" stroke-width="1"> <path d="M3.16143 6.59068L1.75205 8.00006L3.10619 9.35419L2.39908 10.0613L0.832948 8.49517C0.559581 8.2218 0.559582 7.77831 0.832948 7.50494L2.45432 5.88357L3.16143 6.59068ZM8.49511 15.1671C8.22176 15.4405 7.77826 15.4404 7.50489 15.1671L5.93461 13.5968L6.64172 12.8897L8 14.248L9.40938 12.8386L10.1165 13.5457L8.49511 15.1671ZM15.1671 7.50494C15.4403 7.7782 15.4401 8.22179 15.1671 8.49517L13.652 10.0102L12.9449 9.30309L14.248 8.00006L12.8897 6.64178L13.5968 5.93467L15.1671 7.50494ZM9.35414 3.10624L8 1.7521L6.69696 3.05514L5.98986 2.34803L7.50489 0.833003C7.77828 0.559981 8.22186 0.559752 8.49511 0.833003L10.0612 2.39913L9.35414 3.10624Z" fill="currentColor" /> <circle cx="8" cy="8" r="1.76221" stroke="currentColor" /> </svg>`;
let dockRightPageHost = null;

function dockPageText(zh, en) {
    return document.documentElement.lang.startsWith('en') ? en : zh;
}

function dockPageKey(surfaceId, tabId) { return JSON.stringify([surfaceId, tabId]); }

class DockRetainedPages {
    constructor(host) {
        this.host = host;
        this.records = new Map();
        this.observed = new Set();
        this.frame = null;
        this.until = 0;
        this.layer = document.createElement('div');
        this.layer.className = 'dock-page-layer';
        host.appendChild(this.layer);
        this.resize = new ResizeObserver(() => this.schedule());
        this.observer = new MutationObserver(changes => {
            if (changes.some(change => !change.target.closest?.('.dock-retained-page'))) this.schedule();
        });
        this.observer.observe(host, { subtree: true, childList: true, attributes: true, attributeFilter: ['class', 'style'] });
        window.addEventListener('resize', () => this.schedule());
        document.addEventListener('myagent:ui-language-changed', () => this.context());
        this.theme = new MutationObserver(() => this.context());
        this.theme.observe(document.documentElement, { attributes: true, attributeFilter: ['class', 'lang', 'style'] });
    }

    seat(tab, factory) {
        const surfaceId = dockRightState.sessionId;
        const key = dockPageKey(surfaceId, tab.id);
        let record = this.records.get(key);
        if (!record) {
            const page = factory(() => queueMicrotask(() => dockRightRender()));
            page.element.classList.add('dock-retained-page');
            page.element.hidden = true;
            this.layer.appendChild(page.element);
            record = { key, surfaceId, tabId: tab.id, kind: tab.kind, contentId: tab.contentId, page, visible: false };
            this.records.set(key, record);
        }
        const seat = document.createElement('div');
        seat.className = 'dock-page-seat';
        seat.dataset.dockPageSeat = key;
        this.schedule();
        return seat;
    }

    context() {
        for (const record of this.records.values()) record.page.setContext?.();
    }

    schedule() {
        this.until = performance.now() + 340;
        if (this.frame === null) this.frame = requestAnimationFrame(() => this.update());
    }

    update() {
        this.frame = null;
        const seats = new Map();
        this.host.querySelectorAll('[data-dock-page-seat]').forEach(seat => seats.set(seat.dataset.dockPageSeat, seat));
        const connected = new Set(seats.values());
        for (const seat of this.observed) if (!connected.has(seat)) { this.resize.unobserve(seat); this.observed.delete(seat); }
        for (const seat of connected) if (!this.observed.has(seat)) { this.observed.add(seat); this.resize.observe(seat); }
        for (const [key, record] of this.records) {
            const surface = dockSurfaceOf(record.surfaceId, DOCK_RIGHT_AREA);
            const tab = surface?.layout.tabs[record.tabId];
            if (!tab || tab.contentId !== record.contentId) { this.release(key); continue; }
            const seat = seats.get(key);
            const rect = seat?.getBoundingClientRect();
            const visible = record.surfaceId === dockRightState.sessionId && !!surface.layout.expanded
                && !!rect && rect.width > 0 && rect.height > 0;
            const element = record.page.element;
            if (visible) {
                const float = seat.closest('.dock-float');
                const bounds = `left:${rect.left}px;top:${rect.top}px;width:${rect.width}px;height:${rect.height}px;z-index:${float ? Number(float.style.zIndex) + 1 : 1}`;
                if (element.style.cssText !== bounds + ';') element.style.cssText = bounds;
            }
            element.hidden = !visible;
            element.inert = !visible;
            if (visible !== record.visible) {
                record.visible = visible;
                record.page.setVisible?.(visible);
            }
        }
        if (performance.now() < this.until) this.frame = requestAnimationFrame(() => this.update());
    }

    release(key) {
        const record = this.records.get(key);
        if (!record) return;
        this.records.delete(key);
        record.page.dispose?.();
        record.page.element.remove();
    }

    title(tab) {
        return this.records.get(dockPageKey(dockRightState.sessionId, tab.id))?.page.title || tab.title;
    }
}

class DockPluginPage {
    constructor(tab, definition, binding) {
        this.tab = tab;
        this.definition = definition;
        this.binding = binding;
        this.visible = false;
        this.title = definition.title;
        this.element = document.createElement('div');
        this.element.className = 'dock-plugin-page';
        this.frame = document.createElement('iframe');
        this.frame.title = definition.title;
        this.frame.referrerPolicy = 'same-origin';
        this.frame.src = definition.href + '?embedded=1&surface=details';
        this.element.appendChild(this.frame);
        this.frame.addEventListener('load', () => this.setContext());
        this.listener = event => {
            if (event.origin !== location.origin || event.source !== this.frame.contentWindow) return;
            const data = event.data;
            if (!data || data.version !== 1) return;
            if (data.type === 'myagent:plugin-page-ready') this.setContext();
            if (data.type !== 'myagent:plugin-page-request') return;
            if (!this.visible) return;
            if (data.action === 'close') dockClosePageTab(tab.id, binding.surfaceId);
            if (data.action === 'open-url' && typeof data.url === 'string') dockRightOpenBrowser(data.url);
            if (data.action === 'open-plugin' && data.pluginId === definition.pluginId) {
                dockRightOpenPluginPage(definition.pluginId, { pageId: data.pageId, sessionId: binding.sessionId });
            }
        };
        window.addEventListener('message', this.listener);
    }

    setContext() {
        if (!this.frame.contentWindow) return;
        const root = document.documentElement;
        this.frame.contentWindow.postMessage({ type: 'myagent:plugin-page-context', version: 1,
            pluginId: this.definition.pluginId, pageId: this.definition.id, tabId: this.tab.id,
            sessionId: this.binding.sessionId, workDir: this.binding.workDir,
            theme: root.classList.contains('theme-dark') ? 'theme-dark' : root.classList.contains('theme-purple') ? 'theme-purple' : 'theme-light',
            lang: root.lang || 'zh-CN', fontPx: parseFloat(getComputedStyle(root).fontSize), visible: this.visible,
        }, location.origin);
    }

    setVisible(visible) { this.visible = visible; this.setContext(); }
    dispose() {
        this.frame.contentWindow?.postMessage({ type: 'myagent:plugin-page-dispose', version: 1 }, location.origin);
        window.removeEventListener('message', this.listener);
        this.frame.src = 'about:blank';
    }
}

function dockClosePageTab(tabId, surfaceId) {
    dockActionCloseTab(surfaceId, tabId, dockRightSeed(), DOCK_RIGHT_AREA);
    dockRightPageHost?.schedule();
    dockRightRender();
}

function dockRegisterPageType(definition) {
    const unregister = dockTabRegistry.register({ keepMounted: true, ...definition });
    return () => {
        unregister();
        for (const [key, record] of dockRightPageHost?.records || []) {
            if (record.kind === definition.kind) dockRightPageHost.release(key);
        }
        if (dockRightState.surface) dockRightState.surface.tabBodies = Object.create(null);
        dockRightRender();
    };
}

/** Backend-owned destinations only; old navigation declarations remain compatible. */
function dockSyncPluginPages(rows) {
    dockPluginPages.clear();
    const source = Array.isArray(rows) ? rows : [];
    for (const slot of ['details.tab', 'navigation', 'settings.section']) {
        for (const row of source.slice(0, 512)) {
            if (row?.slot !== slot || !/^[a-z0-9][a-z0-9._-]{0,127}$/.test(row.plugin_id)
                || !/^[a-z][a-z0-9._-]{0,63}$/.test(row.id)
                || row.href !== '/plugins/' + row.plugin_id || row.target !== 'plugin-page') continue;
            const key = row.plugin_id + ':' + row.id;
            if (dockPluginPages.has(key)) continue;
            dockPluginPages.set(key, { pluginId: row.plugin_id, id: row.id,
                title: String(row.title || row.label || row.plugin_id).slice(0, 64),
                description: String(row.description || '').slice(0, 200), href: row.href,
                signature: String(row.signature || '').slice(0, 64),
                scope: row.scope === 'app' ? 'app' : 'session', order: Number.isFinite(Number(row.order)) ? Number(row.order) : 100,
                settingsOnly: slot === 'settings.section' && row.embedded === true });
        }
    }
    if (dockRightPageHost) {
        for (const [key, record] of dockRightPageHost.records) {
            const definition = record.page.definition;
            const current = definition && dockPluginPages.get(definition.pluginId + ':' + definition.id);
            if (definition && (!current || current.signature !== definition.signature || current.scope !== definition.scope)) {
                dockClosePageTab(record.tabId, record.surfaceId);
                dockRightPageHost.release(key);
            }
        }
        // Refresh visible, floating, and cached catalogues without remounting plugin pages.
        const bodies = new Set([...Object.values(dockRightState.surface.tabBodies),
            ...dockRightState.host.querySelectorAll('[data-dock-plugin-catalog]')]);
        for (const body of bodies) body.__dockRefreshPlugins?.();
        dockRightRender();
    }
}

/** The guide exposes one plugin category; individual contributions live inside it. */
function dockPluginCatalogBody() {
    const element = document.createElement('div');
    element.className = 'dock-plugin-catalog';
    element.setAttribute('data-dock-plugin-catalog', '');
    const header = document.createElement('div');
    header.className = 'dock-plugin-catalog-header';
    const heading = document.createElement('span');
    const count = document.createElement('span');
    count.className = 'dock-plugin-catalog-count';
    header.append(heading, count);
    const list = document.createElement('div');
    list.className = 'dock-plugin-catalog-list';
    element.append(header, list);
    const refresh = () => {
        const pages = [...dockPluginPages.values()].filter(row => !row.settingsOnly)
            .sort((a, b) => a.order - b.order || a.title.localeCompare(b.title)
                || (a.pluginId + ':' + a.id).localeCompare(b.pluginId + ':' + b.id));
        heading.textContent = dockPageText('插件', 'Plugins');
        count.textContent = dockPageText(pages.length + ' 个页面', pages.length + ' pages');
        list.replaceChildren();
        if (!pages.length) {
            const empty = document.createElement('div');
            empty.className = 'dock-plugin-catalog-empty';
            empty.innerHTML = DOCK_PLUGIN_ICON;
            const label = document.createElement('span');
            label.textContent = dockPageText('暂无可用的插件页面', 'No plugin pages available');
            empty.appendChild(label); list.appendChild(empty);
        }
        for (const page of pages) {
            const button = document.createElement('button');
            button.type = 'button'; button.className = 'dock-plugin-catalog-entry';
            button.dataset.dockPluginPage = page.pluginId + ':' + page.id;
            const icon = document.createElement('span');
            icon.className = 'dock-plugin-catalog-icon'; icon.innerHTML = DOCK_PLUGIN_ICON;
            const copy = document.createElement('span');
            copy.className = 'dock-plugin-catalog-copy';
            const title = document.createElement('span');
            title.className = 'dock-plugin-catalog-title'; title.textContent = page.title;
            copy.appendChild(title);
            if (page.description) {
                const description = document.createElement('span');
                description.className = 'dock-plugin-catalog-description'; description.textContent = page.description;
                copy.appendChild(description);
            }
            const arrow = document.createElement('span');
            arrow.className = 'dock-plugin-catalog-arrow'; arrow.innerHTML = DOCK_BROWSER_TOOL_ICONS.forward;
            button.append(icon, copy, arrow);
            button.addEventListener('click', () => dockRightOpenPluginPage(page.pluginId, { pageId: page.id }));
            list.appendChild(button);
        }
    };
    element.__dockRestore = refresh;
    element.__dockRefreshPlugins = refresh;
    refresh();
    return element;
}

function dockRightOpenPluginPage(pluginId, options = {}) {
    const definition = [...dockPluginPages.values()].find(row => row.pluginId === pluginId && (!options.pageId || row.id === options.pageId));
    if (!definition) return false;
    if (definition.settingsOnly) { openSettingsCenter('plugin:' + pluginId + ':' + definition.id); return true; }
    const sessionId = definition.scope === 'app' ? '' : String(options.sessionId || currentSessionId || '');
    if (definition.scope === 'session' && !sessionId) {
        if (typeof showUiAlert === 'function') showUiAlert({ title: definition.title,
            message: dockPageText('请先选择一个会话', 'Select a session first') });
        return false;
    }
    dockRightEnsureMounted();
    const surfaceId = dockRightSurfaceKey(currentSessionId) || DOCK_APP_SURFACE_KEY;
    const binding = { pluginId, pageId: definition.id, sessionId, surfaceId,
        workDir: typeof getActiveWorkDir === 'function' ? getActiveWorkDir() : '' };
    const contentId = 'myagent-plugin://page/' + encodeURIComponent(JSON.stringify(binding));
    dockRightState.sessionId = surfaceId;
    dockActionOpenContent(surfaceId, { kind: 'plugin-page', contentId, title: definition.title, revealIfOpened: true },
        dockRightSeed(), null, DOCK_RIGHT_AREA);
    dockRightEnsureWidthMode(surfaceId);
    dockRightRender();
    return true;
}

function dockPluginPageBody(tab) {
    let binding;
    try { binding = JSON.parse(decodeURIComponent(tab.contentId.slice('myagent-plugin://page/'.length))); }
    catch { return dockRightNote(dockPageText('插件页面地址无效', 'Invalid plugin page address')); }
    const definition = dockPluginPages.get(binding.pluginId + ':' + binding.pageId);
    if (!definition) return dockRightNote(dockPageText('插件已停用', 'Plugin disabled'));
    return dockRightPageHost.seat(tab, () => new DockPluginPage(tab, definition, binding));
}

/** Main document owns navigation; settings and plugin frames use checked messages. */
function dockInitPageNavigation() {
    document.addEventListener('click', event => {
        if (event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
        const link = event.target.closest?.('a[href]');
        if (!link || link.hasAttribute('download')) return;
        let url;
        try { url = new URL(link.href, location.href); } catch { return; }
        const match = url.origin === location.origin && /^\/plugins\/([a-z0-9][a-z0-9._-]{0,127})$/.exec(url.pathname);
        if (match) { event.preventDefault(); dockRightOpenPluginPage(match[1]); }
        else if (url.origin !== location.origin && /^https?:$/.test(url.protocol)
            && link.closest('#chat-container, .chat-container, .feed-item, .message')) {
            event.preventDefault(); dockRightOpenBrowser(url.href);
        }
    });
    const deepLink = new URL(location.href);
    const pluginId = deepLink.searchParams.get('open_plugin');
    if (pluginId) {
        const open = () => {
            if (!dockPluginPages.size) return;
            dockRightOpenPluginPage(pluginId);
            deepLink.searchParams.delete('open_plugin');
            history.replaceState(history.state, '', deepLink);
            document.removeEventListener('myagent:plugin-ui-ready', open);
        };
        document.addEventListener('myagent:plugin-ui-ready', open);
        open();
    }
}
