function element(tag, text, className) {
    const node = document.createElement(tag);
    if (text != null) node.textContent = text;
    if (className) node.className = className;
    return node;
}

function button(label, action) {
    const node = element('button', label);
    node.type = 'button';
    node.addEventListener('click', async () => {
        node.disabled = true;
        try { await action(); }
        catch (error) { globalThis.alert(String(error.message || error)); }
        finally { node.disabled = false; }
    });
    return node;
}

export function renderSessionPanel(context) {
    const root = context.container;
    root.classList.add('execution-panel');
    const prefix = '/sessions/' + encodeURIComponent(context.sessionId);
    let alive = true;
    let busy = false;
    let modal = null;
    let closeView = null;
    const request = async (url, data) => {
        const response = await context.request(url, {
            method: data === undefined ? 'GET' : 'POST', credentials: 'same-origin', cache: 'no-store',
            headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
            ...(data === undefined ? {} : { body: JSON.stringify(data) }),
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.detail || result.error || `HTTP ${response.status}`);
        return result;
    };

    const jobs = element('div', null, 'execution-list');
    const terminals = element('div', null, 'execution-list');
    const status = element('p', '', 'execution-status');
    root.append(element('h3', '后台任务'), jobs, element('h3', '持久终端'), terminals);

    function viewer(title) {
        if (closeView) closeView();
        modal = element('div', null, 'execution-overlay');
        const dialog = element('section', null, 'execution-dialog');
        dialog.setAttribute('role', 'dialog');
        dialog.setAttribute('aria-modal', 'true');
        const heading = element('header');
        const close = button('关闭视图', () => closeView && closeView());
        heading.append(element('strong', title), close);
        dialog.append(heading);
        modal.append(dialog);
        document.body.append(modal);
        closeView = () => { modal?.remove(); modal = null; closeView = null; };
        return dialog;
    }

    async function showJob(job) {
        const dialog = viewer(job.label || job.id);
        const output = element('pre', '', 'execution-output');
        dialog.append(output);
        let offset = 0;
        let updating = false;
        let disposed = false;
        const refresh = async () => {
            if (updating || disposed) return;
            updating = true;
            try {
                const result = await request(`${prefix}/jobs/${encodeURIComponent(job.id)}/output?offset=${offset}`);
                offset = result.offset;
                output.textContent = (output.textContent + result.text).slice(-256 * 1024);
                output.scrollTop = output.scrollHeight;
            } catch (error) { status.textContent = error.message; }
            finally { updating = false; }
        };
        const timer = setInterval(refresh, 500);
        const remove = closeView;
        closeView = () => { disposed = true; clearInterval(timer); remove(); };
        await refresh();
    }

    async function showTerminal(session) {
        const dialog = viewer((session.actor === 'model' ? 'Agent 终端 · ' : '用户终端 · ') + session.name);
        const list = await request(prefix + '/terminals');
        if (!dialog.isConnected) return;
        const tabs = element('nav', null, 'execution-tabs');
        tabs.setAttribute('role', 'tablist');
        [...list.user, ...list.model].forEach((item) => {
            const tab = button((item.actor === 'model' ? 'Agent · ' : '') + item.name, () => showTerminal(item));
            tab.setAttribute('role', 'tab');
            tab.setAttribute('aria-selected', String(item.id === session.id));
            tabs.append(tab);
        });
        dialog.append(tabs);
        if (session.actor === 'model' || session.status !== 'running') {
            const pre = element('pre', session.detail || '正在读取…', 'execution-output');
            dialog.append(pre);
            const result = await request(`${prefix}/terminals/${encodeURIComponent(session.id)}/history?actor=${encodeURIComponent(session.actor)}`);
            pre.textContent = result.text || session.detail || '(无输出)';
            return;
        }
        if (!globalThis.MyAgentTerminal) throw new Error('终端组件尚未加载，请刷新页面');
        const area = element('div', null, 'execution-terminal');
        dialog.append(area);
        dialog.append(element('p', '用户终端以系统用户权限执行；关闭视图不会停止 shell。', 'execution-status'));
        const { Terminal, FitAddon } = globalThis.MyAgentTerminal;
        const terminal = new Terminal({ cursorBlink: true, scrollback: 1000, convertEol: false, fontSize: 14 });
        const fit = new FitAddon();
        terminal.loadAddon(fit);
        terminal.open(area);
        fit.fit();
        terminal.focus();
        const connection = crypto.randomUUID();
        let offset = 0;
        let source = null;
        let disposed = false;
        let retryTimer = null;
        let inputQueue = Promise.resolve();
        let writable = false;
        const action = (name, data) => request(`${prefix}/terminals/${encodeURIComponent(session.id)}/${name}`, { ...data, connection });
        const connect = () => {
            if (disposed) return;
            source = new EventSource(`${prefix}/terminals/${encodeURIComponent(session.id)}/events?connection=${encodeURIComponent(connection)}&offset=${offset}`);
            source.onmessage = (event) => {
                const result = JSON.parse(event.data);
                writable = result.status === 'running';
                if (result.truncated) { terminal.reset(); terminal.write(result.viewport.replace(/\n/g, '\r\n')); }
                else if (result.text) terminal.write(result.text);
                offset = result.offset;
                if (result.status !== 'running') { writable = false; source.close(); }
            };
            source.onerror = () => {
                writable = false;
                source.close();
                retryTimer = setTimeout(connect, 1000);
            };
        };
        connect();
        const input = terminal.onData((text) => {
            if (!writable) return;
            inputQueue = inputQueue.then(() => action('input', { text })).catch((error) => {
                writable = false;
                terminal.writeln('\r\n' + error.message);
            });
        });
        let resizeTimer;
        const observer = new ResizeObserver(() => {
            clearTimeout(resizeTimer);
            resizeTimer = setTimeout(() => {
                fit.fit();
                if (writable) action('resize', { rows: terminal.rows, cols: terminal.cols }).catch(() => {});
            }, 100);
        });
        observer.observe(area);
        const remove = closeView;
        closeView = () => {
            disposed = true;
            writable = false;
            source?.close();
            clearTimeout(retryTimer);
            clearTimeout(resizeTimer);
            observer.disconnect();
            input.dispose();
            terminal.dispose();
            remove();
        };
    }

    root.append(button('新建用户终端', async () => {
        const capabilities = await request('/api/execution/capabilities');
        const dialog = viewer('新建用户终端');
        const shell = element('select');
        const defaultOption = element('option', '默认 shell');
        defaultOption.value = '';
        shell.append(defaultOption);
        capabilities.shells.forEach((item) => {
            const option = element('option', item.name);
            option.value = item.path;
            shell.append(option);
        });
        const cwd = element('input');
        cwd.placeholder = '工作目录（留空使用会话工作区）';
        dialog.append(shell, cwd, element('p', '以系统用户权限执行。', 'execution-status'),
            button('创建', async () => {
                const session = await request(`${prefix}/terminals`, { shell: shell.value, cwd: cwd.value });
                await showTerminal(session);
                await refresh();
            }));
    }), status);

    const computer = element('details', null, 'execution-computer');
    computer.append(element('summary', 'Computer Use'));
    const enabled = element('input');
    enabled.type = 'checkbox';
    const label = element('label', '启用桌面操作 ');
    label.append(enabled);
    const provider = element('select');
    [['native', 'Native · Cua Driver'], ['mcp', 'MCP · 已配置服务器']].forEach(([value, text]) => {
        const option = element('option', text); option.value = value; provider.append(option);
    });
    const alias = element('select');
    const computerStatus = element('p', '', 'execution-status');
    const updateProvider = () => { alias.hidden = provider.value !== 'mcp'; };
    provider.addEventListener('change', updateProvider);
    computer.append(label, provider, alias, button('保存', async () => {
        const result = await request('/api/computer-use', { enabled: enabled.checked, provider: provider.value, server_alias: alias.value || 'cua-driver-mcp' });
        computerStatus.textContent = `${result.state} · ${result.tool_count} tools${result.error ? ' · ' + result.error : ''}`;
    }), computerStatus);
    root.append(computer);
    request('/api/computer-use').then((result) => {
        enabled.checked = result.enabled;
        provider.value = result.provider;
        result.mcp_servers.forEach((value) => { const option = element('option', value); option.value = value; alias.append(option); });
        alias.value = result.server_alias;
        computerStatus.textContent = `${result.state} · ${result.tool_count} tools${result.error ? ' · ' + result.error : ''}`;
        updateProvider();
    }).catch((error) => { computerStatus.textContent = error.message; });

    async function refresh() {
        if (!alive || busy || document.hidden) return;
        busy = true;
        try {
            const [jobResult, terminalResult] = await Promise.all([request(prefix + '/jobs'), request(prefix + '/terminals')]);
            jobs.replaceChildren();
            if (!jobResult.jobs.length) jobs.append(element('p', '暂无后台任务', 'execution-status'));
            jobResult.jobs.slice(-50).reverse().forEach((job) => {
                const row = element('div', null, 'execution-row');
                const title = element('span', `[${job.status}] ${job.label || job.id}`);
                title.title = job.id;
                row.append(title, button('输出', () => showJob(job)));
                if (['running', 'stopping'].includes(job.status)) row.append(button('停止', async () => { await request(`${prefix}/jobs/${encodeURIComponent(job.id)}/kill`, {}); await refresh(); }));
                jobs.append(row);
            });
            terminals.replaceChildren();
            [...terminalResult.user, ...terminalResult.model].forEach((session) => {
                const row = element('div', null, 'execution-row');
                row.append(element('span', `${session.actor === 'user' ? '用户' : 'Agent'} · ${session.name} [${session.status}]`),
                    button(session.actor === 'user' && session.status === 'running' ? '连接' : '查看', () => showTerminal(session)));
                if (session.actor === 'user' && session.status === 'running') row.append(button('结束', async () => { await request(`${prefix}/terminals/${encodeURIComponent(session.id)}/close`, {}); }));
                terminals.append(row);
            });
            status.textContent = '';
        } catch (error) { status.textContent = error.message; }
        finally { busy = false; }
    }
    refresh();
    const timer = setInterval(refresh, 1000);
    return (details) => {
        alive = false;
        clearInterval(timer);
        if (modal && String(details?.nextSessionId || '') === String(context.sessionId)) return false;
        closeView?.();
        return true;
    };
}
