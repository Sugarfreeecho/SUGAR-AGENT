const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('frontend/src/app/state/session-actions.js', 'utf8');
const runs = new Map(), remote = new Set(), detached = [];
const context = vm.createContext({
    AbortController, console, currentSessionId: '',
    sessionStore: {
        runsBySession: runs,
        setRun(sid, run) { if (run) runs.set(sid, run); else runs.delete(sid); },
        getRun: sid => runs.get(sid),
    },
    setSessionServerStreamActive(sid, active) { if (active) remote.add(sid); else remote.delete(sid); },
    resetStreamReconnectState(sid) { detached.push(sid); },
});
vm.runInContext(source, context);
const all = [];
for (let i = 0; i < 12; i++) {
    const sid = 's' + i;
    context.currentSessionId = sid;
    const run = { controller: new AbortController(), submitted: true,
        ctx: { streamConsuming: true, stream: { dataset: { sessionLoadOk: '1' } } } };
    all.push(run);
    context.setSessionRunState(sid, run);
    assert(runs.size <= 3, 'generation in other sessions must leave HTTP connections for navigation');
    assert(runs.has(sid), 'the visible stream remains attached');
}
assert.equal(all.filter(run => run.controller.signal.aborted).length, 9);
assert.equal(remote.size, 9, 'detaching an observer preserves the server run indicator');
assert.equal(detached.length, 9);
for (const run of all.slice(0, 9)) {
    assert.equal(run.abortReason, 'background-stream-budget');
    assert.equal(run.ctx.stream.dataset.partialBackgroundRun, '1');
    assert.equal(run.ctx.stream.dataset.sessionLoadOk, undefined, 'returning requires a fresh durable snapshot');
}
const newest = runs.get('s11');
context.clearSessionRunStateIfMatch('s11', 'obsolete-run');
// A real run identity prevents late cleanup from deleting its replacement.
newest.runId = 'new-run';
context.setSessionRunState('s11', newest);
context.clearSessionRunStateIfMatch('s11', 'old-run');
assert.strictEqual(runs.get('s11'), newest);

runs.clear();
for (let i = 0; i < 4; i++) {
    context.currentSessionId = 'pending' + i;
    context.setSessionRunState(context.currentSessionId, {
        submitted: false, controller: new AbortController(), ctx: { streamConsuming: false },
    });
}
assert.equal(runs.size, 4, 'an unaccepted message is never aborted as an observer');
console.log('session stream budget: 12 sessions, at most 3 readers; server runs and pending submissions preserved');
