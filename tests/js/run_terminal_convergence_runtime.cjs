const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.resolve(__dirname, '../..');
const read = file => fs.readFileSync(path.join(root, 'frontend/src/app', file), 'utf8');
const c = vm.createContext({console, Map, Set, Date, Number, Object, Array});
vm.runInContext(read('state/session-store.js') + '\nglobalThis.store = sessionStore;', c);
vm.runInContext(read('state/session-selectors.js'), c);
const store = c.store;
const running = run => ({id: 's', name: 'old', run_active: true, stream_active: true,
  active_run: {session_id: 's', run_id: run, run_active: true, runtime_v2: true}});

store.upsert(running('old'));
store.markTerminalRun('s', 'old');
store.setStreamActive('s', false);
store.get('s').run_active = false;
store.upsert({...running('old'), name: 'updated title'});
assert.equal(c.selectIsSessionRunning('s'), false, 'a late row response must not reopen a terminal run');
assert.equal(store.get('s').name, 'updated title', 'terminal protection must retain unrelated metadata changes');
store.applySnapshot([running('old')]);
assert.equal(c.selectIsSessionRunning('s'), false, 'full/fallback snapshots must preserve the terminal boundary');
store.setArchivedLoaded([{...running('old'), archived: true}]);
assert.equal(store.archivedList()[0].stream_active, false, 'archived rows cannot restore an ended running flag');

store.applyActiveRunForSession('s', running('new').active_run);
store.upsert(running('old'));
assert.equal(c.selectIsSessionRunning('s'), true, 'an old response must not clear a genuinely newer run');
assert.equal(store.get('s').active_run.run_id, 'new');
store.applyActiveRunForSession('s', running('old').active_run);
assert.equal(store.getActiveRunInfo('s').run_id, 'new', 'the second stage of a late detail refresh cannot delete the newer identity');
assert.equal(c.selectIsSessionRunning('s'), true);
store.upsert(running('new'));
assert.equal(store.get('s').run_active, true);

const notifications = [];
let draftCleanups = 0;
const e = vm.createContext({
  console, Map, Set, Date, Number, Object, Array, currentSessionId: 'other', liveAutoFollow: false,
  composerDraftRevision: 0, applyMessageEvent() {}, markSessionResultComplete() {},
  finalizeLlmStreamChunks() {}, finalizeProgressStreamChunks() {}, sealProcessGroup() {},
  removeTemporaryStatus() {}, removeAbortedToolDraftRows() {draftCleanups++;},
  discardLlmStreamChunks() {}, discardProgressStreamChunks() {},
  scheduleFinalVisibleAfterRunIfEnabled() {}, resetStreamReconnectState() {},
  syncSessionListIndicatorClasses() {}, setSendButtonState() {},
  syncFollowupQueueFromServer: async () => {notifications.push('sync');},
  scheduleFollowupQueueDrain: () => {notifications.push('drain');},
  getFollowupQueue: () => [],
});
vm.runInContext(read('state/session-store.js') + '\nglobalThis.store = sessionStore;', e);
vm.runInContext(read('state/session-selectors.js'), e);
vm.runInContext(read('state/session-actions.js'), e);
vm.runInContext(read('state/session-event-reducer.js'), e);
const sse = read('modules/sse-handling.js');
for (const name of ['endRunForClient', 'applySessionTerminalNotifications']) {
  vm.runInContext(sse.match(new RegExp('^function ' + name + '\\([^]*?^}', 'm'))[0], e);
}

(async () => {
  const ctx = {runId: 'missed', streamConsuming: true};
  let aborts = 0;
  e.store.upsert(running('missed'));
  e.setSessionRunState('s', {runId: 'missed', ctx, controller: {abort() {aborts++;}}});
  const event = {type: 'run_finished', session_id: 's', run_id: 'missed'};
  e.applySessionTerminalNotifications([event]);
  await new Promise(setImmediate);
  assert.equal(aborts, 1, 'committed change notifications must retire the reader that missed SSE terminal');
  assert.equal(e.selectIsSessionRunning('s'), false);
  assert.equal(e.store.getRun('s'), null);
  assert.equal(ctx.terminalSeen, true);
  assert.deepEqual(notifications, ['sync', 'drain'], 'the terminal boundary immediately releases queued follow-ups');
  e.applySessionTerminalNotifications([event]);
  await new Promise(setImmediate);
  assert.equal(aborts, 1, 'replayed notifications must be idempotent');
  assert.equal(notifications.length, 2);
  e.store.upsert(running('missed'));
  assert.equal(e.selectIsSessionRunning('s'), false, 'an HTTP response delayed past the repair cannot reopen it');

  const newer = {runId: 'newer', ctx: {}, controller: {abort() {aborts++;}}};
  e.setSessionRunState('s', newer);
  e.store.applyActiveRunForSession('s', running('newer').active_run);
  e.applySessionTerminalNotifications([{...event, run_id: 'older'}]);
  assert.equal(e.store.getRun('s'), newer, 'a delayed old terminal must not abort the next run');
  assert.equal(aborts, 1);

  const noContext = {runId: 'no-context', controller: {abort() {aborts++;}}};
  e.setSessionRunState('s', noContext);
  e.store.applyActiveRunForSession('s', running('no-context').active_run);
  e.applySessionTerminalNotifications([{...event, run_id: 'no-context'}]);
  assert.equal(e.store.getRun('s'), null, 'cleanup must also handle detached readers');
  await new Promise(setImmediate);
  const beforeReplay = notifications.length;
  e.applySessionTerminalNotifications([{...event, session_id: 'background', run_id: 'past'}]);
  await new Promise(setImmediate);
  assert.equal(notifications.length, beforeReplay, 'old background completions must add no history or queue requests');

  const beforeInterrupted = draftCleanups;
  e.setSessionRunState('s', {runId: 'interrupted', ctx: {}, controller: {abort() {}}});
  e.applySessionTerminalNotifications([{...event, type: 'run_interrupted', run_id: 'interrupted', checkpoint_ok: false}]);
  await new Promise(setImmediate);
  assert.equal(draftCleanups, beforeInterrupted, 'an uncheckpointed interrupt must preserve the displayed partial tool result');

  e.setSessionRunState('s', {runId: 'stopped', ctx: {}, abortReason: 'user', controller: {abort() {}}});
  const beforeStop = notifications.filter(item => item === 'drain').length;
  e.applySessionTerminalNotifications([{...event, type: 'run_interrupted', run_id: 'stopped'}]);
  await new Promise(setImmediate);
  assert.equal(notifications.filter(item => item === 'drain').length, beforeStop, 'user Stop must not become an automatic queue restart');
  console.log('run terminal convergence runtime checks passed');
})().catch(error => {console.error(error); process.exitCode = 1;});
