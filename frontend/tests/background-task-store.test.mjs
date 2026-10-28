import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const source = readFileSync(new URL('../src/app/state/background-task-store.js', import.meta.url), 'utf8');
const requests = [];
const context = vm.createContext({ AbortController, AbortSignal, Set, Promise,
    fetch: (url, options) => new Promise((resolve, reject) => requests.push({ url, options, resolve, reject })),
});
vm.runInContext(source, context);
const store = context.backgroundTaskStore;
const respond = (request, value, ok = true) => request.resolve({ ok, status: ok ? 200 : 500, json: async () => value });
const flush = async () => { for (let i = 0; i < 12; i++) await Promise.resolve(); };
const job = { id: 'one', owner_session_id: 'child', kind: 'process', label: 'build', status: 'running', started_at: 1 };

store.setSession('root');
assert.equal(requests.length, 1);
assert.match(requests[0].url, /include_descendants=true&active_only=true/);
const first = store.refresh();
assert.equal(store.refresh(), first, 'refresh requests are single-flight');
respond(requests[0], { jobs: [job] }); await first;
assert.equal(store.snapshot().jobs.length, 1);

const failed = store.refresh();
respond(requests[1], { detail: 'offline' }, false); await failed;
assert.equal(store.snapshot().jobs.length, 1, 'network failure retains the snapshot');
assert.equal(store.snapshot().error, 'offline');

const stale = store.refresh();
store.setSession('another');
assert.equal(requests[2].options.signal.aborted, true);
respond(requests[2], { jobs: [job] }); await stale;
respond(requests[3], { jobs: [] }); await flush();
assert.equal(store.snapshot().sessionId, 'another');
assert.equal(store.snapshot().jobs.length, 0, 'late results cannot leak across sessions');

store.setSession('root');
respond(requests[4], { jobs: [job] }); await flush();
const output = store.output(job, 12);
assert.equal(requests[5].url, '/sessions/child/jobs/one/output?offset=12');
respond(requests[5], { text: 'line', offset: 16, job }); await output;
const stop = store.stop(job);
assert.equal(requests[6].url, '/sessions/child/jobs/one/kill');
assert.equal(requests[6].options.method, 'POST');
respond(requests[6], { job: { ...job, status: 'stopping' } }); await flush();
assert.equal(store.snapshot().jobs[0].status, 'stopping');
respond(requests[7], { jobs: [] }); await stop;
assert.equal(store.snapshot().jobs.length, 0);

store.setSession('');
assert.equal(store.snapshot().sessionId, '');
console.log('Background task store: ownership, single-flight, stale responses, failure retention and stopping passed.');
