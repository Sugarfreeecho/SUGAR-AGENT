const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.resolve(__dirname, '../..');
const read = file => fs.readFileSync(path.join(root, 'frontend/src/app', file), 'utf8');
const shared = read('modules/shared-state-and-dialogs.js');
const management = read('modules/session-management.js');
const requests = [];
const context = vm.createContext({
    console, Date, currentSessionId: 'other',
    sessionUnreadComplete: new Set(), sessionUnreadClearInFlight: {},
    persistSessionUnread() {}, syncSessionListIndicatorClasses() {},
    syncSessionDraftBadge() {}, syncSessionRowQuickActions() {}, bindUiHoverTip() {},
    isSessionRunning: sid => context.store.isStreamActive(sid), getSessionRunState: () => null,
    markSessionRunInactive: sid => context.setSessionServerStreamActive(sid, false),
    applyMessageEvent: () => null,
    fetch: async url => {
        requests.push(url);
        return {ok: true, json: async () => ({cleared: true})};
    },
});
vm.runInContext(read('state/session-store.js') + '\nglobalThis.store = sessionStore;', context);
vm.runInContext(shared.slice(shared.indexOf('function clearSessionUnreadState('), shared.indexOf('function userMessageShouldCollapse(')), context);
vm.runInContext(read('state/session-event-reducer.js'), context);
vm.runInContext(management.slice(management.indexOf('function applySessionItemIndicators('), management.indexOf('function sidebarHighlightedSessionId(')), context);

function indicator() {
    const classes = new Set();
    const row = {
        classList: {add: value => classes.add(value), remove: (...values) => values.forEach(value => classes.delete(value))},
        querySelector: () => ({setAttribute() {}, removeAttribute() {}}),
    };
    context.applySessionItemIndicators(row, 's1');
    return classes;
}
function terminal(type, run, extra = {}) {
    return context.applySessionEvent({type, run_id: run, ...extra}, {sessionId: 's1', source: 'sse'});
}

(async () => {
    context.store.upsert({id: 's1'});
    terminal('run_failed', 'run-1');
    assert(indicator().has('is-unread-failed'));
    context.currentSessionId = 's1';
    assert.equal(await context.clearSessionUnreadState('s1'), false);
    assert.equal(requests.length, 0, 'viewing errors must not acknowledge them');
    assert(indicator().has('is-unread-failed'), 'the selected failed session stays red');
    terminal('run_started', 'retry-1');
    assert(indicator().has('is-generating'), 'resuming execution shows the yellow pulsing running indicator');
    assert(!indicator().has('is-unread-failed'), 'a prior failure must not make the resumed indicator red');
    assert(!indicator().has('is-unread-result'), 'resuming execution is not a completed result');
    assert.equal(context.store.get('s1').unread_result_status, 'failed', 'resuming does not resolve the prior error');
    context.currentSessionId = 'other';
    context.store.applySnapshot([{id: 's1', stream_active: true, unread_result: true,
        unread_result_status: 'failed', unread_result_run_id: 'run-1'}]);
    assert(indicator().has('is-generating'), 'a refreshed running snapshot keeps the yellow pulse in the background');
    assert(!indicator().has('is-unread-failed'), 'a refreshed old failure cannot override the running indicator');
    terminal('run_interrupted', 'retry-1');
    assert(indicator().has('is-unread-failed'), 'interrupting the resumed run restores red');
    assert(!indicator().has('is-generating'), 'an interrupted session no longer pulses');
    context.currentSessionId = 's1';
    terminal('run_started', 'retry-2');
    assert(indicator().has('is-generating'), 'a second retry returns to yellow');
    assert(!indicator().has('is-unread-failed'));
    context.store.markRunFinalizing('s1', 'retry-2');
    assert(indicator().has('is-finalizing'), 'retry finalization keeps its own running stage');
    assert(!indicator().has('is-unread-failed'), 'an old error cannot override retry finalization');
    terminal('run_failed', 'retry-2');
    assert(indicator().has('is-unread-failed'), 'a failed retry restores red');
    terminal('run_finished', 'retry-2');
    assert(indicator().has('is-unread-failed'), 'a late success for the same failed run cannot resolve it');
    terminal('run_finished', 'run-2', {result_status: 'pending'});
    assert(indicator().has('is-unread-failed'), 'an intermediate Goal round cannot resolve it');
    terminal('run_finished', 'run-3', {result_status: 'success'});
    await Promise.resolve();
    assert(!indicator().has('is-unread-failed'), 'a successful subsequent terminal resolves the error');

    terminal('run_finished', 'run-4', {result_status: 'failed'});
    assert(indicator().has('is-unread-failed'), 'a budget stop is red even when the run finished');
    context.isGoalActiveForSession = () => true;
    terminal('run_interrupted', 'run-5');
    assert(indicator().has('is-unread-failed'), 'active Goal state must not hide a runtime failure');
    context.isGoalActiveForSession = () => false;
    context.currentSessionId = 'other';
    terminal('run_finished', 'run-6', {content: '失败、异常和 Error: 已修复'});
    assert(indicator().has('is-unread-result'), 'successful response text cannot turn a session red');
    terminal('run_started', 'run-7');
    assert(indicator().has('is-generating'), 'a queued turn retains the pulse');
    assert(indicator().has('is-unread-result'), 'a completed unread queued result still shows green');
    terminal('run_finished', 'run-7');
    assert.equal(await context.clearSessionUnreadState('s1'), true);
    assert(!indicator().has('is-unread-result'), 'successful unread replies still clear on reading');
    context.store.applySnapshot([{id: 's1', unread_result: true, unread_result_status: 'failed', unread_result_run_id: 'run-7'}]);
    assert(indicator().has('is-unread-failed'), 'a read barrier cannot hide a later failure for the same run');
    context.store.applySnapshot([{id: 's1', unread_result: true, unread_result_status: 'failed', unread_result_run_id: 'run-8'}]);
    assert(indicator().has('is-unread-failed'), 'a refreshed failed snapshot stays red');
    console.log('session result attention runtime checks passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
