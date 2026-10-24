const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.resolve(__dirname, '../../frontend/src/app/modules/session-management.js'), 'utf8');
const fn = name => source.match(new RegExp('^(?:async )?function ' + name + '\\([^]*?^}', 'm'))[0];
const tick = () => new Promise(resolve => setImmediate(resolve));

(async () => {
    const requests = [], timers = [], loads = [];
    let applySnapshot = false;
    const c = vm.createContext({
        console, AbortController, Number,
        sessionListChangeWatcherStarted: false, sessionListChangeController: null, sessionListChangeTimer: null,
        sessionListChangeWatcherEpoch: 0,
        sessionStore: { lastAppliedStateRevision: 10 },
        setTimeout(fn, delay) { const timer = {fn, delay}; timers.push(timer); return timer; },
        clearTimeout(timer) { timers.splice(timers.indexOf(timer), 1); },
        fetchWithTimeout(url, options, timeout, consume) {
            return new Promise(resolve => requests.push({url, options, respond: payload =>
                resolve(consume({ok: true, json: async () => payload}))}));
        },
        async loadSessions(opts) {
            loads.push(opts);
            if (applySnapshot) c.sessionStore.lastAppliedStateRevision = 11;
            return true;
        },
    });
    vm.runInContext(['startSessionListChangeWatcher', 'stopSessionListChangeWatcher'].map(fn).join('\n'), c);
    c.startSessionListChangeWatcher(); c.startSessionListChangeWatcher();
    assert.equal(requests.length, 1, 'one watcher per page');
    assert.match(requests[0].url, /after_revision=10$/);
    requests[0].respond({state_revision: 11});
    await tick();
    assert.equal(loads.length, 1, 'event creation immediately refreshes the sidebar');
    assert.equal(loads[0].force, true, 'do not reuse a pre-notification request');
    assert.equal(timers[0].delay, 2000, 'retry snapshots rejected during local edits');

    timers.shift().fn();
    assert.match(requests[1].url, /after_revision=10$/, 'do not lose an unapplied notification');
    applySnapshot = true;
    requests[1].respond({state_revision: 11}); await tick();
    timers.shift().fn();
    assert.match(requests[2].url, /after_revision=11$/);
    requests[2].respond({state_revision: 11}); await tick();
    assert.equal(loads.length, 2, 'unchanged long-poll keepalive does not rebuild the sidebar');
    timers.shift().fn();
    c.stopSessionListChangeWatcher();
    assert.equal(requests[3].options.signal.aborted, true);
    c.startSessionListChangeWatcher();
    assert.equal(requests.length, 5);
    requests[3].respond({state_revision: 11}); await tick();
    assert.equal(timers.length, 0, 'a stale request cannot restart an old watcher after page restore');
    c.stopSessionListChangeWatcher();
    requests[4].respond({state_revision: 11}); await tick();
    assert.equal(timers.length, 0, 'leaving the page stops polling');
    console.log('session changes notification checks passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
