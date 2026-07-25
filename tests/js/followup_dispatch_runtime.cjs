const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const root = path.resolve(__dirname, '..', '..');
const source = fs.readFileSync(
  path.join(root, 'frontend', 'src', 'app', 'modules', 'sse-handling.js'),
  'utf8',
);

function between(startMarker, endMarker) {
  const start = source.indexOf(startMarker);
  const end = source.indexOf(endMarker, start);
  assert(start >= 0 && end > start, `missing source section: ${startMarker}`);
  return source.slice(start, end);
}

function context(extra = {}) {
  return vm.createContext(Object.assign({
    console,
    Promise,
    Date,
    Math,
    Object,
    String,
    Number,
    Array,
    Set,
    setTimeout,
    clearTimeout,
  }, extra));
}

async function testDispatcherDoesNotConsumePendingRows() {
  let queue = [{ id: 'pending', status: '' }];
  const ctx = context({
    followupDispatchChain: Object.create(null),
    sleepMs: (ms) => new Promise((resolve) => setTimeout(resolve, ms)),
    isSendPipelineLocked: () => false,
    getFollowupQueue: () => queue,
    renderFollowupQueue() {},
  });
  vm.runInContext(between('function withFollowupDispatch', 'function shouldApplySseSeqFilter'), ctx);

  const order = [];
  const first = ctx.withFollowupDispatch('s', async () => {
    order.push('first-start');
    await new Promise((resolve) => setTimeout(resolve, 20));
    order.push('first-end');
  });
  const second = ctx.withFollowupDispatch('s', async () => {
    order.push('second');
  });
  await Promise.all([first, second]);
  assert.deepStrictEqual(order, ['first-start', 'first-end', 'second']);

  ctx.refreshPendingFollowupQueue('s');
  await new Promise((resolve) => setTimeout(resolve, 20));
  assert.strictEqual(queue.length, 1, 'status refresh must not consume a pending row');
}

async function testAutoDrainRequiresACompleteIdleBoundary() {
  const queue = [
    { id: 'first', status: '' },
    { id: 'second', status: '' },
  ];
  const sent = [];
  const timers = new Map();
  let timerSeq = 0;
  let localRunning = true;
  let serverRunning = false;
  let sendLocked = false;
  let dispatchBusy = false;
  let stopSuppressed = false;
  const ctx = context({
    followupDrainTimers: Object.create(null),
    isSessionRunning: () => localRunning,
    isSessionStreamStopSuppressed: () => stopSuppressed,
    isServerStreamActive: () => serverRunning,
    isSendPipelineLocked: () => sendLocked,
    isFollowupDispatchBusy: () => dispatchBusy,
    getFollowupQueue: () => queue,
    renderFollowupQueue() {},
    sendFollowupNow: async (id, sid, options) => { sent.push([id, sid, options]); },
    setTimeout: (fn, delay) => {
      const id = ++timerSeq;
      timers.set(id, { fn, delay });
      return id;
    },
    clearTimeout: (id) => { timers.delete(id); },
  });
  vm.runInContext(
    between('function isFollowupAutoDrainReady', 'function scheduleAcceptedFollowupWatch'),
    ctx,
  );

  ctx.drainFollowupQueue('s');
  assert.deepStrictEqual(sent, [], 'an active local run must block automatic transmission');
  assert.strictEqual(timers.size, 0, 'an active run owns the next completion boundary; do not poll it');

  localRunning = false;
  serverRunning = true;
  ctx.drainFollowupQueue('s');
  assert.deepStrictEqual(sent, [], 'an active server stream must block automatic transmission');
  assert.strictEqual(timers.size, 0);

  serverRunning = false;
  stopSuppressed = true;
  ctx.drainFollowupQueue('s');
  assert.deepStrictEqual(sent, [], 'a user stop suppression window must block automatic transmission');
  assert.strictEqual(timers.size, 0, 'a user stop must not leave a delayed automatic send behind');

  stopSuppressed = false;
  sendLocked = true;
  ctx.drainFollowupQueue('s');
  assert.deepStrictEqual(sent, []);
  assert.strictEqual(timers.size, 1, 'a transient send lock should schedule one retry');
  const lockedRetry = [...timers.values()][0];
  assert.strictEqual(lockedRetry.delay, 120);

  // A nearer completion signal replaces the retry, while a later duplicate is ignored.
  ctx.scheduleFollowupQueueDrain('s', 0);
  assert.strictEqual(timers.size, 1, 'per-session drain timers must coalesce');
  const immediateTimerId = [...timers.keys()][0];
  ctx.scheduleFollowupQueueDrain('s', 250);
  assert.strictEqual([...timers.keys()][0], immediateTimerId, 'a later duplicate must not replace an earlier drain');

  sendLocked = false;
  const immediate = timers.get(immediateTimerId);
  timers.delete(immediateTimerId);
  immediate.fn();
  await Promise.resolve();
  await Promise.resolve();
  assert.strictEqual(sent.length, 1, 'automatic continuation must send only one row');
  assert.strictEqual(sent[0][0], 'first');
  assert.strictEqual(sent[0][1], 's');
  assert.strictEqual(sent[0][2].autoAfterRun, true, 'automatic continuation must use normal-chat mode');
  assert.strictEqual(queue.length, 2, 'the dispatcher owns queue state transitions; drain must not delete rows');
  assert.strictEqual(timers.size, 0, 'a completed attempt must not arm an automatic retry loop');
}

async function testRunStartSignalAndFallbacks() {
  const startHelper = between('function startFollowupChat', 'async function sendFollowupNowImpl');

  let streamCompleted = false;
  const signalCtx = context({
    sendMessage: (options) => new Promise((resolve) => {
      setTimeout(() => options.onRunStarted({ sessionId: 's', runId: 'r' }), 5);
      setTimeout(() => {
        streamCompleted = true;
        resolve(true);
      }, 80);
    }),
  });
  vm.runInContext(startHelper, signalCtx);
  const started = await signalCtx.startFollowupChat({ sessionId: 's' });
  assert.strictEqual(started, true);
  assert.strictEqual(streamCompleted, false, 'dispatcher must release at SSE acceptance, not run completion');
  await new Promise((resolve) => setTimeout(resolve, 90));

  let queue = [];
  let sendCalls = 0;
  let lastSendOptions = null;
  let waitForLock = true;
  let steerResponse = null;
  const ctx = context({
    currentSessionId: 's',
    sessionStore: { setStreamActive() {} },
    nowPipelineMs: () => 0,
    getFollowupQueue: () => queue,
    persistFollowupQueue() {},
    renderFollowupQueue() {},
    reportClientPipelineStep() {},
    isSessionRunning: () => false,
    isServerStreamActive: () => false,
    isSendPipelineLocked: () => false,
    sendSteerMessage: async () => {
      if (steerResponse) return steerResponse;
      throw new Error('session is not running');
    },
    refreshFollowupRunState: async () => {},
    sleepMs: async () => {},
    markSessionRunInactive() {},
    waitForSendPipelineIdle: async () => waitForLock,
    appendLogVisible() {},
    sendMessage: async (options) => {
      sendCalls += 1;
      lastSendOptions = options;
      options.onRunStarted({ sessionId: 's', runId: 'new-run' });
      return true;
    },
    takeFollowupItem: (sid, id) => {
      const index = queue.findIndex((item) => String(item.id) === String(id));
      return index >= 0 ? queue.splice(index, 1)[0] : null;
    },
    isMyAgentFeatureEnabled: () => true,
    abortSessionRun() {},
    getSessionRunState: () => null,
    setSendButtonState() {},
    syncSessionListIndicatorClasses() {},
    cancelSteerMessage: async () => {},
    returnFollowupToInput() {},
    syncFollowupQueueFromServer: async () => {},
    scheduleAcceptedFollowupWatch() {},
    appendPendingSteerToProcess() {},
  });
  vm.runInContext(startHelper + between('async function sendFollowupNowImpl', 'async function sendFollowupNow(itemId'), ctx);

  queue = [{ id: 'auto', text: 'next task', display: 'next task', skills: [], steerMode: 'interrupt', status: '' }];
  await ctx.sendFollowupNowImpl('auto', 's', { autoAfterRun: true });
  assert.strictEqual(sendCalls, 1);
  assert.strictEqual(lastSendOptions.fromQueue, true);
  assert.strictEqual(lastSendOptions.forceStart, true);
  assert.strictEqual(queue.length, 0, 'automatic continuation must become an ordinary accepted /chat turn');

  queue = [{ id: 'fallback', text: 'hello', display: 'hello', skills: [], steerMode: 'append', status: '' }];
  await ctx.sendFollowupNowImpl('fallback', 's');
  assert.strictEqual(sendCalls, 2);
  assert.strictEqual(queue.length, 0, 'accepted fallback /chat must remove the queue item exactly once');

  steerResponse = {
    restart: true,
    replacement_run_id: 'replacement',
    item: { id: 'steer', mode: 'interrupt' },
  };
  waitForLock = false;
  queue = [{ id: 'restart', text: 'take over', display: 'take over', skills: [], steerMode: 'interrupt', status: '' }];
  await ctx.sendFollowupNowImpl('restart', 's');
  assert.strictEqual(queue.length, 1);
  assert.strictEqual(queue[0].status, 'restarting');
  assert.strictEqual(sendCalls, 2, 'restart must not call /chat while the previous send lock is held');

  waitForLock = true;
  queue[0].status = '';
  await ctx.sendFollowupNowImpl('restart', 's');
  assert.strictEqual(sendCalls, 3);
  assert.strictEqual(queue.length, 0, 'restart item is removed only after the replacement stream is accepted');
}

async function testManualSendPrioritizesTheClickedRow() {
  const queue = [
    { id: 'first', text: 'first', status: '' },
    { id: 'clicked', text: 'clicked', status: '' },
  ];
  const cleared = [];
  const dispatched = [];
  const drainTimers = { s: { timer: 37 } };
  const ctx = context({
    currentSessionId: 'other',
    followupDrainTimers: drainTimers,
    clearTimeout: (id) => { cleared.push(id); },
    cancelFollowupQueueDrain(sessionId) {
      const existing = drainTimers[sessionId];
      if (!existing) return;
      cleared.push(existing.timer);
      delete drainTimers[sessionId];
    },
    getFollowupQueue: () => queue,
    persistFollowupQueue() {},
    renderFollowupQueue() {},
    withFollowupDispatch: async (sid, callback) => {
      dispatched.push(['before', sid, queue.map((item) => item.id)]);
      return callback();
    },
    sendFollowupNowImpl: async (id, sid, options) => {
      dispatched.push(['sent', id, sid, options.manual, queue.map((item) => item.id)]);
    },
  });
  vm.runInContext(
    between('async function sendFollowupNow(itemId', 'async function sendMessage'),
    ctx,
  );

  await ctx.sendFollowupNow('clicked', 's', { manual: true });
  assert.deepStrictEqual(cleared, [37], 'manual send must cancel an older automatic drain');
  assert.deepStrictEqual(
    Array.from(queue, (item) => item.id),
    ['clicked', 'first'],
    'the clicked row must be promoted before entering the session dispatcher',
  );
  assert.deepStrictEqual(
    JSON.parse(JSON.stringify(dispatched[1])),
    ['sent', 'clicked', 's', true, ['clicked', 'first']],
  );
}

function testAppendOptimisticRowCommitsInPlace() {
  const rows = [];
  let boundaries = 0;
  const body = {
    querySelectorAll() { return rows; },
  };
  const ctxObject = {};
  const ctx = context({
    getProcessBody: () => body,
    truncateLogTextForUi: (text) => text,
    appendLog: (runCtx, content) => {
      const scroller = { textContent: content, closest: () => row };
      const row = {
        dataset: {},
        isConnected: true,
        querySelector: () => scroller,
        removeAttribute(name) {
          if (name === 'data-steer-pending') delete this.dataset.steerPending;
        },
      };
      rows.push(row);
      return scroller;
    },
    getSessionRunState: () => ({ ctx: ctxObject }),
    finalizeLlmStreamChunks() {},
    finalizeProgressStreamChunks() {},
    sealProcessGroup() { boundaries += 1; },
    resetLlmState() {},
  });
  vm.runInContext(
    between('function findSteerProcessRow', 'async function sendSteerMessage'),
    ctx,
  );

  const pending = ctx.appendSteerProcessMessage(
    's', ctxObject, 'follow up', 'client-1', 'append', true,
  );
  assert.strictEqual(rows.length, 1);
  assert.strictEqual(pending.dataset.steerPending, '1');

  const committed = ctx.appendSteerProcessMessage(
    's', ctxObject, 'follow up', 'client-1', 'append', false,
  );
  assert.strictEqual(rows.length, 1, 'SSE commit must reuse the optimistic append row');
  assert.strictEqual(committed, pending);
  assert.strictEqual(committed.dataset.steerCommitted, '1');
  assert.strictEqual(committed.dataset.steerPending, undefined);

  ctx.prepareSteerProcessBoundary(ctxObject, 'append', 'append-1');
  assert.strictEqual(boundaries, 0, 'append mode must retain the active process block');
  ctx.prepareSteerProcessBoundary(ctxObject, 'interrupt', 'interrupt-1');
  ctx.prepareSteerProcessBoundary(ctxObject, 'interrupt', 'interrupt-1');
  assert.strictEqual(boundaries, 0, 'interrupt must retain the active execution-process block');
  assert.strictEqual(ctxObject.reactGeneration, 1, 'one interrupt operation advances one logical generation');
  ctx.prepareSteerProcessBoundary(ctxObject, 'interrupt', 'interrupt-2');
  assert.strictEqual(boundaries, 0, 'later interrupts also stay in the same process block');
  assert.strictEqual(ctxObject.reactGeneration, 2);

  ctxObject.lastUserEventIndex = 3;
  ctx.markSteerEventPosition(ctxObject, 7, 11);
  assert.strictEqual(ctxObject.lastUserEventIndex, 7);
  assert.strictEqual(ctxObject.lastUserRuntimeSeq, 11);
}

(async () => {
  await testDispatcherDoesNotConsumePendingRows();
  await testAutoDrainRequiresACompleteIdleBoundary();
  await testRunStartSignalAndFallbacks();
  await testManualSendPrioritizesTheClickedRow();
  testAppendOptimisticRowCommitsInPlace();
  process.stdout.write('followup dispatcher runtime checks passed\n');
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
