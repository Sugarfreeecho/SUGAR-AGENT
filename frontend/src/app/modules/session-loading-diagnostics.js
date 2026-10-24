// Bounded metadata only; never records message bodies, prompts or error text.
const sessionLoadingDiagnostics = (function () {
    const records = [], pending = [], resources = [];
    try {
        const saved = JSON.parse(localStorage.getItem('myagent-loading-diagnostics-v1') || '[]');
        if (Array.isArray(saved)) records.push(...saved.filter(row => row && typeof row === 'object').slice(-128));
    } catch (_error) {}
    const endpoint = '/api/ui-loading-diagnostics';
    let timer = null, stopped = false;
    const now = () => typeof performance !== 'undefined' ? performance.now() : Date.now();
    const id = () => typeof crypto !== 'undefined' && crypto.randomUUID
        ? crypto.randomUUID() : Date.now().toString(36) + '-' + Math.random().toString(36).slice(2);
    const reason = error => error && error.uiLoadReason || (error && error.name === 'AbortError' ? 'cancelled'
        : error && error.name === 'SyntaxError' ? 'json_parse' : error && error.name === 'TypeError' ? 'network' : 'unknown');
    if (typeof PerformanceObserver === 'function') {
        try {
            new PerformanceObserver(list => {
                for (const entry of list.getEntries()) if (entry.name.includes('ui_request_id=')) {
                    resources.push(entry);
                    if (resources.length > 64) resources.shift();
                }
            }).observe({type:'resource', buffered:true});
        } catch (_error) { /* Older browsers still record headers/body timing. */ }
    }
    function emit(record) {
        records.push(record);
        if (records.length > 128) records.shift();
        const output = record.status === 'failed' ? console.warn : console.info;
        if (output) output.call(console, 'ui_loading ' + JSON.stringify(record));
        if (!stopped) {
            pending.push(record);
            if (pending.length > 32) pending.shift();
        }
        if (!timer) timer = setTimeout(flush, 1000);
    }
    function flush() {
        if (timer) clearTimeout(timer);
        timer = null;
        try { localStorage.setItem('myagent-loading-diagnostics-v1', JSON.stringify(records)); } catch (_error) {}
        if (stopped || !pending.length) return;
        const body = JSON.stringify({records:pending.splice(0, 32)});
        // Same-origin delivery has its own short deadline and is never awaited
        // by history loading. No retries compete with a struggling backend.
        const controller = new AbortController();
        const deadline = setTimeout(() => controller.abort(), 3000);
        try {
            Promise.resolve(fetch(endpoint, {method:'POST', headers:{'Content-Type':'application/json'},
                body:body, keepalive:true, signal:controller.signal}))
                .then(response => { if (response.status === 404) stopped = true; })
                .catch(() => {}).finally(() => clearTimeout(deadline));
        } catch (_error) { clearTimeout(deadline); }
    }
    function start(sessionId, kind) {
        const span = {session_id:String(sessionId || ''), kind:kind, load_id:id(), started:now(),
            started_at:new Date().toISOString(), phase:'fetch', phaseStarted:now(), phases:{}, finished:false};
        emit({event:'load_start', session_id:span.session_id, kind:kind, load_id:span.load_id, started_at:span.started_at});
        return span;
    }
    function phase(span, next) {
        if (!span || span.finished) return;
        span.phases[span.phase + '_ms'] = (span.phases[span.phase + '_ms'] || 0) + now() - span.phaseStarted;
        span.phase = next; span.phaseStarted = now();
    }
    function end(span, status, error) {
        if (!span || span.finished) return;
        const lastPhase = span.phase;
        phase(span, 'complete'); span.finished = true;
        emit({event:'load_end', session_id:span.session_id, kind:span.kind, load_id:span.load_id,
            request_id:span.request_id || '', started_at:span.started_at, status:status, phase:lastPhase,
            elapsed_ms:Math.round(now() - span.started), reason:status === 'cancelled' ? 'cancelled' : error ? (reason(error) === 'unknown'
                && ['hydrate','images','layout','scroll'].includes(lastPhase) ? 'render' : reason(error))
                : undefined,
            error_name:error && error.name || '', ...span.phases});
    }
    async function fetchJSON(span, url, options, timeoutMs, attempt) {
        const requestId = id(), started = now();
        if (span) span.request_id = requestId;
        const route = url.includes('/history_snapshot') ? 'history_snapshot' : url.includes('/messages') ? 'messages'
            : url.startsWith('/sessions/state') ? 'state' : 'list';
        const requestUrl = url + (url.includes('?') ? '&' : '?') + 'ui_request_id=' + encodeURIComponent(requestId);
        const base = {session_id:span ? span.session_id : '', kind:span ? span.kind : 'history',
            load_id:span ? span.load_id : '', request_id:requestId, route:route, attempt:attempt || 1, timeout_ms:timeoutMs,
            started_at:new Date().toISOString()};
        const requestOptions = {...options, headers:{...(options && options.headers),
            'X-Request-ID':requestId, 'X-UI-Load-ID':base.load_id}};
        let headersAt = null, statusCode = 0, currentPhase = 'headers', outcome = 'failed', caught = null, serverMs;
        emit({event:'request_start', ...base, phase:currentPhase});
        try {
            const result = await fetchWithTimeout(requestUrl, requestOptions, timeoutMs, async response => {
                headersAt = now(); statusCode = response.status; currentPhase = 'body';
                let data;
                try { data = await response.json(); }
                catch (error) {
                    if (error.name === 'AbortError' || (options && options.signal && options.signal.aborted)) throw error;
                    if (response.ok) { error.uiLoadReason = 'json_parse'; throw error; }
                    data = null;
                }
                serverMs = data && data.timing && Number(data.timing.total);
                return {response:response, data:data};
            });
            outcome = result.response.ok ? 'success' : 'failed';
            return result;
        } catch (error) { caught = error; outcome = reason(error) === 'cancelled' ? 'cancelled' : 'failed'; throw error; }
        finally {
            const finished = now(), extra = {};
            let entries = resources;
            try { entries = entries.concat(performance.getEntriesByType('resource')); } catch (_error) {}
            const entry = entries.find(item => item.name.includes('ui_request_id=' + requestId));
            if (entry && entry.requestStart > 0 && entry.responseEnd > 0) {
                extra.queue_ms = Math.max(0, entry.requestStart - entry.fetchStart);
                extra.ttfb_ms = Math.max(0, entry.responseStart - entry.requestStart);
                extra.network_body_ms = Math.max(0, entry.responseEnd - entry.responseStart);
                extra.after_network_ms = Math.max(0, finished - entry.responseEnd);
            }
            emit({event:'request_end', ...base, status:outcome, phase:currentPhase,
                reason:caught ? reason(caught) : outcome === 'failed' ? 'http' : undefined,
                error_name:caught && caught.name || '', status_code:statusCode,
                elapsed_ms:Math.round(finished - started), headers_ms:headersAt == null ? undefined : headersAt - started,
                body_ms:headersAt == null ? undefined : finished - headersAt, server_ms:serverMs, ...extra});
        }
    }
    if (typeof window !== 'undefined') window.addEventListener('pagehide', flush);
    if (typeof globalThis !== 'undefined') globalThis.__MYAGENT_LOADING_DIAGNOSTICS__ = {snapshot:() => records.slice(), flush:flush};
    return {start:start, phase:phase, end:end, fetchJSON:fetchJSON};
})();
