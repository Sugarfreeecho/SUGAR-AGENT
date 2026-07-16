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

  queue = [{ id: 'fallback', text: 'hello', display: 'hello', skills: [], steerMode: 'append', status: '' }];
  await ctx.sendFollowupNowImpl('fallback', 's');
  assert.strictEqual(sendCalls, 1);
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
  assert.strictEqual(sendCalls, 1, 'restart must not call /chat while the previous send lock is held');

  waitForLock = true;
  queue[0].status = '';
  await ctx.sendFollowupNowImpl('restart', 's');
  assert.strictEqual(sendCalls, 2);
  assert.strictEqual(queue.length, 0, 'restart item is removed only after the replacement stream is accepted');
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
  assert.strictEqual(boundaries, 1, 'one interrupt operation must seal the old block exactly once');
  ctx.prepareSteerProcessBoundary(ctxObject, 'interrupt', 'interrupt-2');
  assert.strictEqual(boundaries, 2, 'a later interrupt starts another process block');

  ctxObject.lastUserEventIndex = 3;
  ctx.markSteerEventPosition(ctxObject, 7, 11);
  assert.strictEqual(ctxObject.lastUserEventIndex, 7);
  assert.strictEqual(ctxObject.lastUserRuntimeSeq, 11);
}

(async () => {
  await testDispatcherDoesNotConsumePendingRows();
  await testRunStartSignalAndFallbacks();
  testAppendOptimisticRowCommitsInPlace();
  process.stdout.write('followup dispatcher runtime checks passed\n');
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
