import '/assets/terminal-runtime.js';
import './context-menu.js';
import { renderSessionPanel } from './session-panel.js';
import { $, option } from '/static/workflow-console.js';

let sessionId = '', cleanup = null, lifetime = new AbortController(), disposed = false;
let requestedTerminalId = new URLSearchParams(location.search).get('terminal_id') || '';
function open(sid, force = false) {
    if (disposed || (sid === sessionId && !force)) return;
    cleanup?.({ nextSessionId: '' }); cleanup = null;
    lifetime.abort(); lifetime = new AbortController();
    sessionId = sid; $('session').value = sid;
    $('execution').replaceChildren(); $('execution').hidden = !sid;
    $('empty').hidden = Boolean(sid); $('error').textContent = '';
    $('sync-status').textContent = sid ? '已绑定会话 · 状态自动刷新' : '请选择会话';
    if (!sid) return;
    const signal = lifetime.signal;
    cleanup = renderSessionPanel({ container: $('execution'), sessionId: sid,
        terminalId: requestedTerminalId,
        request: (url, options = {}) => fetch(url, { ...options,
            signal: AbortSignal.any([signal, options.signal, AbortSignal.timeout(15000)].filter(Boolean)) }),
    });
    requestedTerminalId = '';
}
$('select').onsubmit = event => { event.preventDefault(); open($('session').value.trim()); };
$('refresh').onclick = () => open(sessionId, true);
document.addEventListener('myagent:plugin-page-context', event => open(String(event.detail?.sessionId || '')));
function dispose() { disposed = true; cleanup?.({ nextSessionId: '' }); lifetime.abort(); }
document.addEventListener('myagent:plugin-page-dispose', dispose, { once: true });
window.addEventListener('pagehide', dispose, { once: true });
const query = new URLSearchParams(location.search);
open(window.MyAgentPluginPage?.context?.sessionId || query.get('session') || query.get('session_id') || query.get('sessionId') || '');
fetch('/sessions?limit=100', { credentials: 'same-origin', signal: AbortSignal.timeout(10000) }).then(response => response.ok ? response.json() : []).then(rows => {
    if (!disposed) $('sessions').replaceChildren(...(Array.isArray(rows) ? rows : []).map(row => option(row.id, row.name || row.id)));
}).catch(() => {});
