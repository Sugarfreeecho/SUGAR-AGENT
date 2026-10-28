/* Shared lifecycle for the bundled Goal and Team consoles. */
export const $ = id => document.getElementById(id);
export function node(tag, className, text) {
    const el = document.createElement(tag);
    if (className) el.className = className;
    if (text != null) el.textContent = String(text);
    return el;
}
export const labels = {
    active: '进行中', paused: '已暂停', blocked: '已阻塞', completed: '已完成',
    cancelled: '已取消', shutting_down: '关停中', stopped: '已停止', archived: '已归档',
    starting: '准备中', idle: '空闲', working: '执行中', waiting_permission: '等待审批',
    stopping: '停止中', failed: '失败', pending: '待处理', in_progress: '执行中',
    queued: '待接收', delivering: '投递中', delivered: '已投递', consumed: '已读',
    low: '低', normal: '普通', high: '高', urgent: '紧急', done: '通过', continue: '继续执行',
};
export function badge(value) {
    const el = node('span', 'badge', labels[value] || value || '—');
    el.dataset.status = value || '';
    return el;
}
export function button(text, fn, className = '') {
    const el = node('button', className, text);
    el.type = 'button';
    el.addEventListener('click', fn);
    return el;
}
export function option(value, text) {
    const el = node('option', '', text);
    el.value = value;
    return el;
}
export function detail(label, value) {
    const el = node('div', 'detail');
    el.append(node('dt', '', label), node('dd', '', value || '—'));
    return el;
}
export const count = value => new Intl.NumberFormat('zh-CN').format(Number(value) || 0);
export function time(value) {
    const date = new Date(value);
    return value && Number.isFinite(date.getTime()) ? date.toLocaleString() : '—';
}
export function duration(value) {
    const secs = Math.max(0, Math.floor(Number(value) || 0));
    return `${Math.floor(secs / 3600)} 小时 ${Math.floor(secs % 3600 / 60)} 分 ${secs % 60} 秒`;
}
export function budget(id) {
    const raw = $(id).value.trim();
    if (!raw) return undefined;
    const value = Number(raw);
    if (!Number.isSafeInteger(value) || value <= 0) throw new Error('Token 预算必须是正整数。');
    return value;
}

export class Console {
    constructor({ path, render, reset, prepare = value => value }) {
        this.path = path;
        this.render = render;
        this.reset = reset;
        this.prepare = prepare;
        this.session = '';
        this.sessionNames = new Map();
        this.generation = 0;
        this.busy = false;
        this.reading = false;
        this.disposed = false;
        this.lifetime = new AbortController();
        $('select').addEventListener('submit', event => {
            event.preventDefault();
            this.open($('session').value.trim());
        });
        $('refresh').onclick = () => { if (!this.busy) void this.refresh(); };
        document.addEventListener('myagent:plugin-page-context', event => {
            const sid = String(event.detail?.sessionId || '').trim();
            if (sid !== this.session) { $('session').value = sid; this.open(sid); }
        });
        const visibility = () => {
            clearTimeout(this.timer);
            if (this.visible() && this.session && !this.disposed) void this.refresh();
        };
        document.addEventListener('visibilitychange', visibility);
        document.addEventListener('myagent:plugin-page-visibility', visibility);
        const dispose = () => {
            this.disposed = true;
            clearTimeout(this.timer);
            this.lifetime.abort();
            document.removeEventListener('visibilitychange', visibility);
            document.removeEventListener('myagent:plugin-page-visibility', visibility);
        };
        document.addEventListener('myagent:plugin-page-dispose', dispose, { once: true });
        window.addEventListener('pagehide', dispose, { once: true });
        document.querySelectorAll('dialog').forEach(dialog => dialog.addEventListener('close', () => dialog.querySelector('.dialog-error')?.remove()));
        const query = new URLSearchParams(location.search);
        const initial = window.MyAgentPluginPage?.context?.sessionId || query.get('session_id') || query.get('sessionId') || query.get('session') || '';
        if (initial) { $('session').value = initial; this.open(initial); }
        else { this.reset(); this.status('请选择会话'); }
        void this.loadSessions();
    }
    visible() { return !document.hidden && (!window.MyAgentPluginPage || window.MyAgentPluginPage.visible); }
    status(text) { $('sync-status').textContent = text; }
    showBinding() {
        const name = $('session-name'), short = $('session-short-id');
        if (name) name.textContent = this.session ? this.sessionNames.get(this.session) || '当前会话' : '尚未绑定会话';
        if (short) { short.textContent = this.session ? this.session.slice(0, 8) : ''; short.title = this.session; }
    }
    message(text, error = false) {
        $('error').textContent = error ? text : '';
        $('notice').textContent = error ? '' : text;
        document.querySelectorAll('.dialog-error').forEach(el => el.remove());
        const dialog = document.querySelector('dialog[open]');
        if (error && text && dialog) {
            const message = node('p', 'dialog-error', text);
            message.setAttribute('role', 'alert');
            dialog.prepend(message);
        }
    }
    open(sid) {
        if (this.disposed) return;
        if (sid === this.session) { void this.refresh(); return; }
        this.lifetime.abort();
        this.lifetime = new AbortController();
        this.session = sid;
        this.showBinding();
        this.generation++;
        this.busy = false;
        this.reading = false;
        clearTimeout(this.timer);
        this.setBusy(false);
        this.reset();
        this.message('');
        if (sid) void this.refresh(); else this.status('请选择会话');
    }
    async request(path = '', options = {}, { timeout = 15000 } = {}) {
        if (!this.session) throw new Error('请先选择会话。');
        const timeoutController = new AbortController();
        const timer = setTimeout(() => timeoutController.abort(), timeout);
        const signal = AbortSignal.any([this.lifetime.signal, timeoutController.signal]);
        try {
            const response = await fetch(this.path(this.session) + path, {
                credentials: 'same-origin', cache: 'no-store', ...options,
                headers: { Accept: 'application/json', 'Content-Type': 'application/json', ...options.headers }, signal,
            });
            let body;
            try { body = await response.json(); }
            catch { throw new Error(`服务返回了无法解析的响应（HTTP ${response.status}）。`); }
            if (!response.ok || body.ok === false) {
                const error = new Error(typeof body.error === 'string' ? body.error : body.error?.message || body.detail || `请求失败（HTTP ${response.status}）`);
                error.status = response.status;
                throw error;
            }
            return body;
        } catch (error) {
            if (timeoutController.signal.aborted) throw new Error('请求超时。操作可能已被接受，请刷新状态后再决定是否重试。');
            throw error;
        } finally { clearTimeout(timer); }
    }
    schedule() {
        clearTimeout(this.timer);
        if (!this.disposed && this.session && this.visible()) this.timer = setTimeout(() => void this.refresh(), 5000);
    }
    async refresh() {
        if (this.disposed || !this.session || this.busy || this.reading) return;
        const generation = this.generation;
        const readVersion = this.readVersion || 0;
        this.reading = true;
        this.status('正在同步…');
        try {
            const body = await this.request();
            if (generation !== this.generation || readVersion !== (this.readVersion || 0) || this.disposed) return;
            this.render(body);
            this.status(`已同步 · ${new Date().toLocaleTimeString()}`);
        } catch (error) {
            if (generation !== this.generation || readVersion !== (this.readVersion || 0) || this.disposed || error.name === 'AbortError') return;
            this.message(error.message, true);
            this.status('同步失败 · 可手动刷新');
        } finally {
            if (generation === this.generation && readVersion === (this.readVersion || 0) && !this.disposed) { this.reading = false; this.schedule(); }
        }
    }
    setBusy(value) {
        this.busy = value;
        $('workspace').inert = value;
        $('workspace').setAttribute('aria-busy', String(value));
        $('refresh').disabled = value;
        document.querySelectorAll('.dialog-progress').forEach(el => el.remove());
        const dialog = document.querySelector('dialog[open]');
        if (value && dialog) dialog.prepend(node('p', 'dialog-progress muted', '正在处理，请稍候…'));
    }
    async action(path, payload = {}, success = '操作已保存', options = {}) {
        if (this.busy || this.disposed) return false;
        const generation = this.generation;
        // Invalidate an older GET without cancelling an accepted server-side action.
        this.reading = false;
        this.readVersion = (this.readVersion || 0) + 1;
        this.setBusy(true);
        clearTimeout(this.timer);
        this.message('');
        this.status('正在处理…');
        let accepted = false;
        try {
            await this.request(path, { method: options.method || 'POST', body: JSON.stringify(this.prepare(payload)) }, options);
            if (generation !== this.generation || this.disposed) return false;
            this.message(success);
            accepted = true;
        } catch (error) {
            if (generation === this.generation && !this.disposed && error.name !== 'AbortError') this.message(error.message, true);
        } finally {
            if (generation === this.generation && !this.disposed) {
                this.setBusy(false);
                await this.refresh();
            }
        }
        return accepted && generation === this.generation && !this.disposed;
    }
    async loadSessions() {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), 10000);
        try {
            const response = await fetch('/sessions?limit=100', { credentials: 'same-origin', signal: controller.signal });
            if (!response.ok || this.disposed) return;
            const body = await response.json();
            const rows = Array.isArray(body) ? body : body.sessions || [];
            this.sessionNames = new Map(rows.map(row => [row.id, row.name || row.title || row.id]));
            this.showBinding();
            $('sessions').replaceChildren(...rows.map(row => option(row.id, row.name || row.title || row.id)));
        } catch { /* Manual session entry and the embedded context remain available. */ }
        finally { clearTimeout(timer); }
    }
}
