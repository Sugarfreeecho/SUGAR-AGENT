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
vm.runInContext(read('state/session-selectors.js'), context);
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

    // Interleave SSE turn boundaries with cached and fresh HTTP snapshots.
    // The queued answers deliberately share one run identity.
    context.currentSessionId = 's1';
    context.store.upsert({id: 's1', stream_active: true});
    const snapshot = (phase, seq, run = 'queued-run') => ({
        session_id: 's1', run_id: run, run_active: true, runtime_v2: true,
        phase, phase_seq: seq,
    });
    context.store.applyActiveRuns([snapshot('running', 5)]);
    terminal('final', 'queued-run', {runtime_seq: 10});
    assert(indicator().has('is-finalizing'), 'the first answer can show its blue finalization stage');
    terminal('user', 'queued-run', {queued_followup: true, runtime_seq: 20});
    assert(indicator().has('is-generating'), 'the second queued answer returns to yellow');
    context.store.applyActiveRuns([snapshot('finalizing', 10)]);
    assert(indicator().has('is-generating'), 'a cached first-answer snapshot must not turn the second answer blue');
    context.store.applyActiveRuns([snapshot('running', 20)]);
    assert(indicator().has('is-generating'), 'fresh running snapshots keep the second answer yellow');
    assert(!context.store.finalizingRunIdsBySession.has('s1'), 'running snapshots clear the old finalization marker');
    context.store.applyActiveRunForSession('s1', snapshot('finalizing', 10));
    assert(indicator().has('is-generating'), 'a stale detail refresh cannot undo the second turn boundary');
    context.store.applyActiveRuns([snapshot('finalizing', undefined)]);
    assert(indicator().has('is-generating'), 'unversioned cached snapshots cannot override a sequenced live boundary');
    terminal('final', 'queued-run', {runtime_seq: 10});
    assert(indicator().has('is-generating'), 'replayed old final events must not finalize the new answer');
    terminal('final', 'queued-run', {runtime_seq: 30});
    assert(indicator().has('is-finalizing'), 'a genuinely newer final event still turns blue');
    context.store.applyActiveRuns([snapshot('running', 20)]);
    assert(indicator().has('is-finalizing'), 'an older running snapshot cannot erase a newer final');
    terminal('user', 'queued-run', {queued_followup: true, runtime_seq: 20});
    assert(indicator().has('is-finalizing'), 'replayed older user boundaries cannot undo a newer final');
    context.store.applyActiveRunForSession('s1', snapshot('running', 40));
    assert(indicator().has('is-generating'), 'a newer server-side turn can resume even before its SSE arrives');
    context.store.applyActiveRuns([snapshot('finalizing', 50)]);
    assert(indicator().has('is-finalizing'), 'newer server finalization snapshots remain visible');
    terminal('run_finished', 'queued-run', {runtime_seq: 60});
    assert(!indicator().has('is-finalizing'), 'the durable terminal clears blue');
    context.store.applyActiveRuns([snapshot('finalizing', 50)]);
    assert(!indicator().has('is-finalizing'), 'an old active snapshot cannot reopen the terminal run');

    // Existing unversioned snapshots also need to clear a stale marker when
    // they explicitly report running, for both bulk and single-row refreshes.
    context.store.applyActiveRunForSession('s1', snapshot('finalizing', 0, 'legacy-run'));
    context.store.applyActiveRuns([snapshot('running', 0, 'legacy-run')]);
    assert(!context.store.isRunFinalizing('s1'));
    assert(!context.store.finalizingRunIdsBySession.has('s1'));
    context.store.applyActiveRuns([snapshot('finalizing', 0, 'legacy-run')]);
    context.store.applyActiveRunForSession('s1', snapshot('running', 0, 'legacy-run'));
    assert(!context.store.isRunFinalizing('s1'));
    assert(!context.store.finalizingRunIdsBySession.has('s1'));

    // Background work owns a steady yellow indicator after the main run ends,
    // including snapshots with a stale successful/failed unread result.
    for (const field of ['background_jobs_running', 'subagent_running']) {
        for (const selected of ['s1', 'other']) {
            context.currentSessionId = selected;
            context.store.applyActiveRuns([]);
            context.store.applySnapshot([{id: 's1', [field]: 1, unread_result: true,
                unread_result_status: 'success'}]);
            assert.deepEqual([...indicator()], ['is-background-running']);
            terminal('run_finished', 'background-parent-' + field, {[field]: 1, result_status: 'pending'});
            assert.deepEqual([...indicator()], ['is-background-running'], 'the terminal event cannot flash green');
            assert.equal(context.store.get('s1').unread_result, false);
        }
        context.store.applySnapshot([{id: 's1', [field]: 1, unread_result: true,
            unread_result_status: 'failed'}]);
        assert.deepEqual([...indicator()], ['is-background-running'], 'running work takes indicator priority');
        terminal('run_started', 'background-followup-' + field);
        assert(indicator().has('is-generating'), 'the resumed main run pulses normally');
        assert(!indicator().has('is-unread-result'));
        terminal('run_finished', 'background-followup-' + field, {
            background_jobs_running: 0, subagent_running: 0, result_status: 'success',
        });
        assert.deepEqual([...indicator()], ['is-unread-result'], 'completion is restored after all work ends');
        context.store.applySnapshot([{id: 's1'}]);
        assert.equal(indicator().size, 0, 'a later read idle session has no background indicator');
    }
    console.log('session result attention runtime checks passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
