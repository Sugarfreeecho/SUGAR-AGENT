/** HTTP(S) browser UI with iframe and desktop guest carriers. */
/** Browser glyph paths from DSH ui-primitives; keep the regular one-pixel weight. */
const DOCK_BROWSER_ICON = `<svg viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" stroke-width="1"> <path d="M7.99986 14.0887C11.3626 14.0887 14.0886 11.3627 14.0886 7.99998C14.0886 4.63727 11.3626 1.91125 7.99986 1.91125C4.63715 1.91125 1.91113 4.63727 1.91113 7.99998C1.91113 11.3627 4.63715 14.0887 7.99986 14.0887Z" stroke="currentColor" /> <path d="M2.34619 8H13.6538" stroke="currentColor" stroke-linecap="square" /> <path d="M7.99976 14.0889C9.23509 14.0889 10.1743 11.3629 10.1743 8.00006C10.1743 4.63739 9.23509 1.91138 7.99976 1.91138" stroke="currentColor" /> <path d="M7.99973 14.0889C6.76445 14.0889 5.8252 11.3629 5.8252 8.00006C5.8252 4.63739 6.76445 1.91138 7.99973 1.91138" stroke="currentColor" /> </svg>`;
const DOCK_BROWSER_TOOL_ICONS = {
    back: `<svg viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" stroke-width="1"> <path d="M10 4L6.70711 7.29289C6.31658 7.68342 6.31658 8.31658 6.70711 8.70711L10 12" stroke="currentColor" /> </svg>`,
    forward: `<svg viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" stroke-width="1"> <path d="M6 12L9.29289 8.70711C9.68342 8.31658 9.68342 7.68342 9.29289 7.29289L6 4" stroke="currentColor" /> </svg>`,
    reload: `<svg viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" stroke-width="1"> <path d="M14.5001 8C14.5 9.28552 14.1188 10.5422 13.4045 11.611C12.6903 12.6799 11.6752 13.5129 10.4875 14.0049C9.29982 14.4968 7.99295 14.6255 6.73212 14.3747C5.4713 14.124 4.31314 13.505 3.4041 12.596C2.49514 11.687 1.87614 10.5288 1.62537 9.26798C1.37459 8.00716 1.50331 6.70028 1.99525 5.51261C2.48719 4.32494 3.32025 3.30981 4.3891 2.59557C5.45795 1.88134 6.71458 1.50008 8.0001 1.5C9.9001 1.5 11.7001 2.3 13.0001 3.6L14.5001 5.1" stroke="currentColor" /> <path d="M14.4999 1.5V5.1H10.8999" stroke="currentColor" /> </svg>`,
    go: `<svg viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" stroke-width="1"> <path d="M6.59961 9.40051C6.82779 9.6334 7.10015 9.81842 7.40074 9.94472C7.70132 10.071 8.02409 10.1361 8.35013 10.1361C8.67618 10.1361 8.99894 10.071 9.29953 9.94472C9.60011 9.81842 9.87247 9.6334 10.1007 9.40051L12.9015 6.59967C13.3658 6.13541 13.6266 5.50572 13.6266 4.84915C13.6266 4.19258 13.3658 3.56289 12.9015 3.09863C12.4372 2.63436 11.8075 2.37354 11.151 2.37354C10.4944 2.37354 9.86472 2.63436 9.40045 3.09863L9.05034 3.44873" stroke="currentColor" /> <path d="M9.40051 6.59959C9.17233 6.3667 8.89997 6.18169 8.59939 6.05538C8.2988 5.92907 7.97603 5.86401 7.64999 5.86401C7.32395 5.86401 7.00118 5.92907 6.70059 6.05538C6.40001 6.18169 6.12765 6.3667 5.89946 6.59959L3.09863 9.40043C2.63436 9.8647 2.37354 10.4944 2.37354 11.151C2.37354 11.8075 2.63436 12.4372 3.09863 12.9015C3.56289 13.3657 4.19258 13.6266 4.84915 13.6266C5.50572 13.6266 6.13541 13.3657 6.59967 12.9015L6.94978 12.5514" stroke="currentColor" /> </svg>`,
    external: `<svg viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" stroke-width="1"> <path d="M11.7256 2.77441C12.5538 2.77469 13.2256 3.44616 13.2256 4.27441V10.1416H12.2256V4.27441C12.2256 3.99844 12.0015 3.77469 11.7256 3.77441H5.7207V2.77441H11.7256Z" fill="currentColor" /> <path d="M2.77441 13.2255L12.3756 3.62427" stroke="currentColor" /> </svg>`,
};
function dockParseBrowserAddress(value) {
    const input = String(value || '').trim();
    if (!input || input.length > 16384) return null;
    try {
        const explicit = /^[a-z][a-z\d+.-]*:(?!\d+(?:[/?#]|$))/i.test(input);
        const url = new URL(explicit ? input : 'https://' + input);
        if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password) return null;
        const app = new URL(location.href);
        if (url.origin === app.origin || (url.port === app.port && ['127.0.0.1', 'localhost', '[::1]'].includes(url.hostname))) return null;
        return url;
    } catch { return null; }
}

class DockBrowserPage {
    constructor(initialUrl, workspace, changed) {
        this.changed = changed;
        this.workspace = workspace;
        this.title = dockPageText('浏览器', 'Browser');
        this.history = [];
        this.index = -1;
        this.unknown = false;
        this.disposed = false;
        this.epoch = 0;
        this.bridge = globalThis.sugarAgentDesktop?.browser;
        this.element = document.createElement('div');
        this.element.className = 'dock-browser-page';
        const form = document.createElement('form');
        form.className = 'dock-browser-toolbar';
        const button = (icon, zh, en, action) => {
            const item = document.createElement('button');
            item.type = 'button'; item.className = 'dock-browser-tool';
            item.innerHTML = DOCK_BROWSER_TOOL_ICONS[icon]; item.title = dockPageText(zh, en);
            item.setAttribute('aria-label', item.title); item.addEventListener('click', action);
            form.appendChild(item); return item;
        };
        this.back = button('back', '后退', 'Back', () => this.navigateHistory(-1));
        this.forward = button('forward', '前进', 'Forward', () => this.navigateHistory(1));
        this.reloadButton = button('reload', '刷新', 'Reload', () => this.reload());
        this.addressBox = document.createElement('div');
        this.addressBox.className = 'dock-browser-address-box';
        this.address = document.createElement('input');
        this.address.className = 'dock-browser-address';
        this.address.type = 'text'; this.address.placeholder = dockPageText('输入网址', 'Enter a URL');
        this.address.autocomplete = 'off'; this.address.spellcheck = false;
        this.address.setAttribute('autocapitalize', 'off'); this.address.setAttribute('inputmode', 'url');
        this.address.setAttribute('aria-label', this.address.placeholder);
        this.addressChanged = document.createElement('span');
        this.addressChanged.className = 'dock-browser-address-changed';
        this.addressChanged.textContent = dockPageText('地址已变化', 'Address changed');
        this.addressBox.append(this.address, this.addressChanged);
        form.appendChild(this.addressBox);
        const go = button('go', '前往', 'Go', () => this.load(this.address.value));
        go.classList.add('dock-browser-address-go');
        this.addressBox.appendChild(go);
        this.external = button('external', '在系统浏览器中打开', 'Open in system browser', () => {
            if (!this.current || this.unknown) return;
            if (globalThis.sugarAgentDesktop?.openExternal) globalThis.sugarAgentDesktop.openExternal(this.current);
            else window.open(this.current, '_blank', 'noopener,noreferrer');
        });
        form.addEventListener('submit', event => { event.preventDefault(); this.load(this.address.value); });
        this.notice = document.createElement('div');
        this.notice.className = 'dock-browser-notice'; this.notice.setAttribute('role', 'status');
        this.viewport = document.createElement('div');
        this.viewport.className = 'dock-browser-viewport';
        this.placeholder = document.createElement('div');
        this.placeholder.className = 'dock-browser-placeholder';
        const globe = document.createElement('span');
        globe.className = 'dock-browser-placeholder-icon'; globe.innerHTML = DOCK_BROWSER_ICON;
        this.placeholderText = document.createElement('span');
        this.placeholderText.setAttribute('role', 'status');
        this.placeholder.append(globe, this.placeholderText);
        this.viewport.appendChild(this.placeholder);
        this.element.append(form, this.viewport, this.notice);
        this.updateControls();
        this.setLoading(false);
        if (initialUrl) this.load(initialUrl);
    }

    setLoading(loading) {
        this.placeholder.hidden = Boolean(this.current) && !loading;
        this.placeholderText.textContent = loading ? dockPageText('正在加载网页…', 'Loading page…')
            : dockPageText('输入网址开始浏览', 'Enter a URL to browse');
    }

    async load(value, historyIndex) {
        const url = dockParseBrowserAddress(value);
        if (!url) {
            this.notice.textContent = dockPageText('请输入有效的 HTTP(S) 地址，不能访问应用自身或包含账号密码',
                'Use an HTTP(S) URL without credentials or the application address');
            return;
        }
        this.current = url.href; this.unknown = false; this.address.value = url.href;
        this.notice.textContent = ''; this.setLoading(true);
        this.title = url.hostname; this.changed();
        if (!this.bridge) {
            if (historyIndex === undefined) {
                this.history.splice(this.index + 1);
                this.history.push(url.href); this.index = this.history.length - 1;
            } else this.index = historyIndex;
            this.createIframe(url.href);
        } else {
            try {
                const frame = await this.ensureGuest();
                if (!frame || this.disposed || this.current !== url.href) return;
                await frame.loadURL(url.href);
            } catch (error) {
                if (!this.disposed && this.current === url.href && error?.code !== 'ERR_ABORTED') {
                    this.setLoading(false);
                    this.notice.textContent = dockPageText('网页加载失败：', 'Page failed: ') + error.message;
                }
            }
        }
        this.updateControls();
    }

    createIframe(url) {
        this.frame?.remove();
        const frame = document.createElement('iframe');
        frame.title = this.title; frame.referrerPolicy = 'no-referrer';
        // Popups route through the explicit external action; no top navigation is granted.
        frame.setAttribute('sandbox', 'allow-scripts allow-forms');
        let loads = 0;
        frame.addEventListener('load', () => {
            if (this.disposed || frame !== this.frame) return;
            this.setLoading(false);
            if (++loads > 1) {
                this.unknown = true;
                this.notice.textContent = dockPageText('页面已导航，当前地址不可读取；刷新返回地址栏中的网址。',
                    'The page navigated; its address is unavailable. Reload returns to the displayed URL.');
            }
            this.updateControls();
        });
        frame.addEventListener('error', () => {
            if (this.disposed || frame !== this.frame) return;
            this.setLoading(false);
            this.notice.textContent = dockPageText('页面加载失败，可在系统浏览器中打开', 'Page failed; open it in the system browser');
        });
        this.notice.textContent = dockPageText('网页可能限制嵌入；无法显示时请在系统浏览器中打开。',
            'Some sites block embedding. Use the system browser if the page cannot be displayed.');
        frame.src = url; this.frame = frame; this.viewport.appendChild(frame);
    }

    ensureGuest() {
        if (this.frame) return Promise.resolve(this.frame);
        if (this.pending) return this.pending;
        const epoch = ++this.epoch;
        this.pending = (async () => {
            const reservation = await this.bridge.acquire(this.workspace);
            if (this.disposed || epoch !== this.epoch) { await this.bridge.release(reservation.lease); return null; }
            this.lease = reservation.lease;
            const frame = document.createElement('webview');
            frame.setAttribute('partition', reservation.partition);
            frame.setAttribute('allowpopups', '');
            frame.setAttribute('src', 'about:blank#' + reservation.lease);
            this.frame = frame;
            this.unsubscribe = this.bridge.onOpenRequested(reservation.lease, url => dockRightOpenBrowser(url));
            const ready = new Promise((resolve, reject) => {
                const timer = setTimeout(() => reject(new Error('Browser startup timed out')), 15000);
                this.cancelReady = () => { clearTimeout(timer); resolve(null); };
                frame.addEventListener('dom-ready', () => { clearTimeout(timer); this.cancelReady = null; resolve(frame); }, { once: true });
            });
            const observe = () => {
                if (this.disposed || frame !== this.frame) return;
                try {
                    const url = dockParseBrowserAddress(frame.getURL());
                    if (url) {
                        if (!this.firstDocument) { frame.clearHistory(); this.firstDocument = true; }
                        this.current = url.href; this.address.value = url.href;
                        this.title = frame.getTitle() || url.hostname;
                        this.notice.textContent = ''; this.changed();
                    }
                    this.updateControls();
                } catch { /* A newly attached guest has no readable navigation state yet. */ }
            };
            for (const name of ['did-navigate', 'did-navigate-in-page', 'page-title-updated', 'did-stop-loading']) frame.addEventListener(name, observe);
            frame.addEventListener('did-start-loading', () => { if (!this.disposed && frame === this.frame) this.setLoading(true); });
            frame.addEventListener('did-stop-loading', () => { if (!this.disposed && frame === this.frame) this.setLoading(false); });
            frame.addEventListener('did-fail-load', event => {
                if (!this.disposed && frame === this.frame && event.isMainFrame && event.errorCode !== -3) {
                    this.setLoading(false);
                    this.notice.textContent = dockPageText('网页加载失败：', 'Page failed: ') + event.errorDescription;
                }
            });
            frame.addEventListener('render-process-gone', () => {
                this.setLoading(false);
                this.notice.textContent = dockPageText('浏览器进程已退出，点击刷新重试', 'Browser exited; reload to retry');
                this.dropGuest();
            });
            this.viewport.appendChild(frame);
            try { return await ready; }
            catch (error) { await this.dropGuest(); throw error; }
        })().finally(() => { this.pending = null; });
        return this.pending;
    }

    navigateHistory(delta) {
        if (this.bridge) {
            try { if (delta < 0) this.frame?.goBack(); else this.frame?.goForward(); } catch { /* Guest may have closed. */ }
        } else if (!this.unknown && this.history[this.index + delta]) this.load(this.history[this.index + delta], this.index + delta);
    }

    reload() {
        if (!this.current) return;
        if (this.bridge && this.frame) { try { this.frame.reload(); } catch { this.load(this.current); } }
        else this.load(this.current, this.index);
    }

    updateControls() {
        let back = false, forward = false;
        if (this.bridge && this.frame) {
            try { back = this.frame.canGoBack(); forward = this.frame.canGoForward(); } catch { /* Guest is starting. */ }
        } else if (!this.unknown) { back = this.index > 0; forward = this.index >= 0 && this.index < this.history.length - 1; }
        this.back.disabled = !back; this.forward.disabled = !forward;
        this.reloadButton.disabled = !this.current;
        this.external.disabled = !this.current || this.unknown;
        this.addressBox.classList.toggle('is-unknown', this.unknown);
        this.addressChanged.hidden = !this.unknown;
    }

    async dropGuest() {
        const lease = this.lease;
        this.lease = null; this.epoch++;
        this.cancelReady?.(); this.cancelReady = null;
        this.unsubscribe?.(); this.unsubscribe = null;
        this.frame?.remove(); this.frame = null; this.firstDocument = false;
        if (lease) await this.bridge.release(lease).catch(error => console.warn('Browser release failed', error));
    }

    dispose() { this.disposed = true; this.dropGuest(); }
}

function dockRightOpenBrowser(value = '', options = {}) {
    if (value && !dockParseBrowserAddress(value)) return false;
    dockRightEnsureMounted();
    const surfaceId = dockRightSurfaceKey(currentSessionId) || DOCK_APP_SURFACE_KEY;
    const request = { url: value, workspace: typeof getActiveWorkDir === 'function' ? getActiveWorkDir() : '',
        sessionId: String(currentSessionId || ''), nonce: String(options.presentationId || crypto.randomUUID()) };
    dockRightState.sessionId = surfaceId;
    dockActionOpenContent(surfaceId, { kind: 'browser', title: String(options.title || dockPageText('浏览器', 'Browser')).slice(0, 100),
        contentId: 'myagent-browser://page/' + encodeURIComponent(JSON.stringify(request)),
        replaceTab: options.replaceTab, revealIfOpened: !!options.presentationId }, dockRightSeed(), null, DOCK_RIGHT_AREA);
    dockRightEnsureWidthMode(surfaceId); dockRightRender();
    return true;
}

function dockBrowserPageBody(tab) {
    let request;
    try { request = JSON.parse(decodeURIComponent(tab.contentId.slice('myagent-browser://page/'.length))); }
    catch { return dockRightNote(dockPageText('浏览器页面地址无效', 'Invalid browser page address')); }
    return dockRightPageHost.seat(tab, changed => new DockBrowserPage(request.url,
        request.workspace || 'session:' + request.sessionId, changed));
}
