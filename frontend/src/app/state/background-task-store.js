/** The current conversation subtree's live jobs; output reads never consume model cursors. */
var backgroundTaskStore = (function () {
    var state = { sessionId: '', jobs: [], loading: false, error: '' };
    var listeners = new Set();
    var lifetime = new AbortController();
    var flight = null;
    var generation = 0;

    function emit() { listeners.forEach(function (listener) { listener(state); }); }
    function snapshot() { return state; }
    function subscribe(listener) { listeners.add(listener); return function () { listeners.delete(listener); }; }
    function isActive(job) { return job && (job.status === 'running' || job.status === 'stopping'); }
    function key(job) { return String(job.owner_session_id || state.sessionId) + ':' + job.id; }
    function path(job) {
        return '/sessions/' + encodeURIComponent(job.owner_session_id || state.sessionId)
            + '/jobs/' + encodeURIComponent(job.id);
    }
    async function request(url, options) {
        options = options || {};
        var signals = [lifetime.signal, AbortSignal.timeout(15000)];
        if (options.signal) signals.push(options.signal);
        var response = await fetch(url, Object.assign({
            credentials: 'same-origin', cache: 'no-store', headers: { Accept: 'application/json' },
        }, options, { signal: AbortSignal.any(signals) }));
        var value = await response.json();
        if (!response.ok) throw new Error(value.detail || value.error || ('HTTP ' + response.status));
        return value;
    }
    function refresh(force) {
        if (!state.sessionId) return Promise.resolve();
        if (flight && !force) return flight.promise;
        if (flight) flight.controller.abort();
        var sid = state.sessionId;
        var epoch = generation;
        var pending = { controller: new AbortController(), promise: null };
        flight = pending;
        state = Object.assign({}, state, { loading: true });
        pending.promise = (async function () {
            try {
                var value = await request('/sessions/' + encodeURIComponent(sid)
                    + '/jobs?include_descendants=true&active_only=true', { signal: pending.controller.signal });
                if (!Array.isArray(value.jobs)) throw new Error('Invalid background task response');
                if (generation !== epoch || flight !== pending) return;
                var jobs = value.jobs.filter(function (job) { return job && job.id && isActive(job); })
                    .map(function (job) { return Object.assign({ owner_session_id: sid }, job); })
                    .sort(function (a, b) {
                        return Number(a.started_at || 0) - Number(b.started_at || 0)
                            || String(a.id).localeCompare(String(b.id));
                    });
                state = { sessionId: sid, jobs: jobs, error: '', loading: false };
            } catch (error) {
                if (generation !== epoch || flight !== pending || pending.controller.signal.aborted) return;
                state = Object.assign({}, state, { error: String(error.message || error), loading: false });
            } finally {
                if (generation === epoch && flight === pending) {
                    flight = null;
                    state = Object.assign({}, state, { loading: false });
                    emit();
                }
            }
        })();
        emit();
        return pending.promise;
    }
    function setSession(sessionId) {
        var sid = String(sessionId || '');
        if (state.sessionId === sid) return;
        generation += 1;
        lifetime.abort();
        lifetime = new AbortController();
        if (flight) flight.controller.abort();
        flight = null;
        state = { sessionId: sid, jobs: [], loading: false, error: '' };
        emit();
        if (sid) void refresh();
    }
    async function stop(job) {
        var epoch = generation;
        var value = await request(path(job) + '/kill', {
            method: 'POST', headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
            body: JSON.stringify({ reason: 'user cancellation' }),
        });
        if (generation !== epoch) return;
        if (value.job) {
            state = Object.assign({}, state, { jobs: state.jobs.map(function (entry) {
                return key(entry) === key(job) ? Object.assign({}, entry, value.job) : entry;
            }).filter(isActive) });
            emit();
        }
        await refresh(true);
        return value;
    }
    function output(job, offset, signal) { return request(path(job) + '/output?offset=' + offset, { signal: signal }); }
    return { snapshot: snapshot, subscribe: subscribe, setSession: setSession, refresh: refresh,
        stop: stop, output: output, isActive: isActive, key: key };
})();
