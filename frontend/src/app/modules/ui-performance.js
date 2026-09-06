// Bounded local diagnostics. No message bodies, prompts or network uploads.
const uiPerformance = (function () {
    var storageKey = 'myagent-ui-performance-v1';
    var limits = [0.5, 1, 2, 4, 8, 16.7, 25, 33.4, 50, 100, 250, 500, 1000, 3000, 10000];
    var previous = [];
    var timer = 0;
    var visibleSince = 0;
    var enabled = !(window.__MYAGENT_FEATURES__ && window.__MYAGENT_FEATURES__.uiPerformance === false);
    try {
        var saved = JSON.parse(localStorage.getItem(storageKey) || 'null');
        if (saved && saved.version === 1 && Array.isArray(saved.reports)) previous = saved.reports.slice(-3);
    } catch (_e) { /* Storage is optional. */ }
    function newReport() {
        return { revision: 'session-stream-2026-09-06-v1', startedAt: new Date().toISOString(),
            updatedAt: '', sessions: [], sessionLimit: 12,
            frameNote: 'Visible-page callback intervals, not display FPS; histogram p95 is an upper bound.' };
    }
    var report = newReport();
    function session(sid) {
        var id = String(sid || 'ui');
        var entry = report.sessions.find(function (item) { return item.sessionId === id; });
        if (!entry) {
            entry = { sessionId: id, timings: {}, counters: {} };
            if (report.sessions.length >= report.sessionLimit) report.sessions.shift();
            report.sessions.push(entry);
        }
        if (!timer) timer = setTimeout(flush, 5000);
        return entry;
    }
    function sample(sid, name, ms) {
        if (!enabled || document.hidden || !Number.isFinite(ms) || ms < 0) return;
        // A background-tab pause is not a visible rendering stall.
        if (visibleSince && performance.now() - ms < visibleSince) return;
        var timings = session(sid).timings;
        var metric = timings[name];
        if (!metric) metric = timings[name] = { count: 0, totalMs: 0, maxMs: 0, buckets: limits.map(function () { return 0; }).concat(0) };
        metric.count += 1;
        metric.totalMs += ms;
        metric.maxMs = Math.max(metric.maxMs, ms);
        var index = limits.findIndex(function (limit) { return ms <= limit; });
        metric.buckets[index < 0 ? limits.length : index] += 1;
    }
    function count(sid, name, amount) {
        if (!enabled || document.hidden) return;
        var counters = session(sid).counters;
        counters[name] = (counters[name] || 0) + (amount == null ? 1 : amount);
    }
    function snapshot() {
        var current = JSON.parse(JSON.stringify(report));
        current.updatedAt = new Date().toISOString();
        current.sessions.forEach(function (entry) {
            Object.keys(entry.timings).forEach(function (name) {
                var metric = entry.timings[name], sum = 0;
                metric.meanMs = metric.totalMs / metric.count;
                for (var i = 0; i < metric.buckets.length; i += 1) {
                    sum += metric.buckets[i];
                    if (sum >= Math.ceil(metric.count * 0.95)) {
                        metric.p95UpperMs = i < limits.length ? limits[i] : metric.maxMs;
                        break;
                    }
                }
                delete metric.buckets;
            });
        });
        return { version: 1, reports: previous.concat(current) };
    }
    function flush() {
        if (timer) clearTimeout(timer);
        timer = 0;
        if (!enabled || !report.sessions.length) return;
        try { localStorage.setItem(storageKey, JSON.stringify(snapshot())); } catch (_e) { /* Quota/private mode. */ }
    }
    function reset() {
        if (timer) clearTimeout(timer);
        timer = 0;
        previous = [];
        report = newReport();
        try { localStorage.removeItem(storageKey); } catch (_e) {}
    }
    function download() {
        flush();
        var url = URL.createObjectURL(new Blob([JSON.stringify(snapshot(), null, 2)], { type: 'application/json' }));
        var link = document.createElement('a');
        link.href = url;
        link.download = 'myagent-ui-performance-' + Date.now() + '.json';
        link.click();
        setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
    }
    window.addEventListener('pagehide', flush);
    document.addEventListener('visibilitychange', function () {
        if (document.hidden) flush();
        else visibleSince = performance.now();
    });
    window.__MYAGENT_UI_PERF__ = { snapshot: snapshot, reset: reset, download: download, flush: flush };
    return { sample: sample, count: count, flush: flush };
})();
