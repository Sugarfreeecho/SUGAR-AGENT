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
    renderDurableAttachmentImages() {},
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
  let pendingAsk = false;
  const ctx = context({
    followupDrainTimers: Object.create(null),
    isSessionRunning: () => localRunning,
    isSessionStreamStopSuppressed: () => stopSuppressed,
    isServerStreamActive: () => serverRunning,
    isSendPipelineLocked: () => sendLocked,
    isFollowupDispatchBusy: () => dispatchBusy,
    pendingHumanQuestions: () => pendingAsk ? [{ interaction_id: 'ask' }] : [],
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
  pendingAsk = true;
  ctx.drainFollowupQueue('s');
  assert.deepStrictEqual(sent, [], 'an unanswered Ask must block automatic transmission');
  assert.strictEqual(timers.size, 0, 'the Ask completion boundary owns the next drain attempt');

  pendingAsk = false;
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

async function testPendingQueueCanBeReordered() {
  const queue = [
    { id: 'a', status: '' },
    { id: 'b', status: '' },
    { id: 'c', status: '' },
  ];
  const ctx = context({
    getFollowupQueue: () => queue,
    persistFollowupQueue() {},
    renderFollowupQueue() {},
  });
  vm.runInContext(between('function moveFollowupQueueItem', 'function withdrawFollowup'), ctx);

  assert.strictEqual(ctx.moveFollowupQueueItem('s', 'c', 'a', 'before'), true);
  assert.deepStrictEqual(queue.map((item) => item.id), ['c', 'a', 'b']);
  assert.deepStrictEqual(queue.map((item) => item.order), [0, 1, 2], 'reorder must renumber explicit order');

  assert.strictEqual(ctx.moveFollowupQueueItem('s', 'a', 'c', 'after'), true);
  assert.deepStrictEqual(queue.map((item) => item.id), ['c', 'a', 'b']);

  assert.strictEqual(ctx.moveFollowupQueueItem('s', 'b', 'a', 'before'), true);
  assert.deepStrictEqual(queue.map((item) => item.id), ['c', 'b', 'a']);

  assert.strictEqual(ctx.moveFollowupQueueItem('s', 'a', 'c', 'before'), true);
  assert.deepStrictEqual(queue.map((item) => item.id), ['a', 'c', 'b']);

  assert.strictEqual(ctx.moveFollowupQueueItem('s', 'a', 'a', 'before'), false);
  assert.strictEqual(ctx.moveFollowupQueueItem('s', 'missing', 'a', 'before'), false);
  assert.deepStrictEqual(queue.map((item) => item.id), ['a', 'c', 'b']);

  queue.splice(0, queue.length,
    { id: 'p1', status: '' },
    { id: 'accepted', status: 'accepted' },
    { id: 'p2', status: '' },
    { id: 'p3', status: '' },
    { id: 'sending', status: 'sending' },
  );
  assert.strictEqual(ctx.moveFollowupQueueItem('s', 'p3', 'p1', 'before'), true);
  assert.deepStrictEqual(
    queue.map((item) => item.id),
    ['p3', 'accepted', 'p1', 'p2', 'sending'],
    'pending rows must reorder only within pending slots',
  );
  assert.strictEqual(queue[1].id, 'accepted', 'accepted row must keep its exact index');
  assert.strictEqual(queue[4].id, 'sending', 'sending row must keep its exact index');
  assert.strictEqual(
    ctx.moveFollowupQueueItem('s', 'p1', 'accepted', 'before'),
    false,
    'in-flight rows must not be valid drop targets',
  );
  assert.strictEqual(
    ctx.moveFollowupQueueItem('s', 'accepted', 'p1', 'before'),
    false,
    'in-flight rows must not be draggable',
  );
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
  let localRunning = false;
  let pendingAsk = false;
  const ctx = context({
    currentSessionId: 's',
    followupManualDispatchEpochBySession: Object.create(null),
    sessionStore: { setStreamActive() {} },
    nowPipelineMs: () => 0,
    getFollowupQueue: () => queue,
    persistFollowupQueue() {},
    renderFollowupQueue() {},
    reportClientPipelineStep() {},
    isSessionRunning: () => localRunning,
    isServerStreamActive: () => false,
    pendingHumanQuestions: () => pendingAsk ? [{ interaction_id: 'ask' }] : [],
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

  queue = [{
    id: 'ask-deferred',
    text: 'after ask',
    display: 'after ask',
    skills: [],
    steerMode: 'interrupt',
    status: '',
    awaitingRunEnd: true,
    deferUntilRunEnd: true,
  }];
  localRunning = true;
  await ctx.sendFollowupNowImpl('ask-deferred', 's');
  assert.strictEqual(sendCalls, 0, 'an Ask-queued follow-up must not interrupt the owning run');
  assert.strictEqual(queue[0].status, '');
  localRunning = false;

  queue = [{ id: 'auto', text: 'next task', display: 'next task', skills: [], steerMode: 'interrupt', status: '' }];
  await ctx.sendFollowupNowImpl('auto', 's', { autoAfterRun: true });
  assert.strictEqual(sendCalls, 1);
  assert.strictEqual(lastSendOptions.fromQueue, true);
  assert.strictEqual(lastSendOptions.forceStart, true);
  assert.strictEqual(queue.length, 0, 'automatic continuation must become an ordinary accepted /chat turn');

  let releaseAutoLock;
  waitForLock = new Promise((resolve) => { releaseAutoLock = resolve; });
  queue = [{
    id: 'superseded-auto',
    text: 'old head',
    display: 'old head',
    skills: [],
    steerMode: 'interrupt',
    status: '',
    awaitingRunEnd: true,
  }];
  const pendingAuto = ctx.sendFollowupNowImpl(
    'superseded-auto',
    's',
    { autoAfterRun: true, autoDispatchEpoch: 0 },
  );
  ctx.followupManualDispatchEpochBySession.s = 1;
  releaseAutoLock(true);
  await pendingAuto;
  assert.strictEqual(sendCalls, 1, 'a superseded auto send must not start /chat after its lock wait');
  assert.strictEqual(queue[0].status, '');
  assert.strictEqual(queue[0].awaitingRunEnd, true);
  waitForLock = true;

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
    followupManualDispatchEpochBySession: Object.create(null),
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

async function testManualSendSupersedesAnAlreadyQueuedAutoHead() {
  const queue = [
    { id: 'first', text: 'first', status: '', awaitingRunEnd: true },
    { id: 'clicked', text: 'clicked', status: '', awaitingRunEnd: true },
  ];
  const sent = [];
  let releaseGate;
  const gate = new Promise((resolve) => { releaseGate = resolve; });
  const ctx = context({
    currentSessionId: 's',
    followupDispatchChain: Object.create(null),
    followupManualDispatchEpochBySession: Object.create(null),
    sleepMs: async () => {},
    isSendPipelineLocked: () => false,
    getFollowupQueue: () => queue,
    persistFollowupQueue() {},
    renderFollowupQueue() {},
    cancelFollowupQueueDrain() {},
    sendFollowupNowImpl: async (id) => { sent.push(id); },
  });
  vm.runInContext(
    between('function withFollowupDispatch', 'function shouldApplySseSeqFilter'),
    ctx,
  );
  vm.runInContext(
    between('function isFollowupAutoDispatchSuperseded', 'async function sendQueuedFollowupAsChat'),
    ctx,
  );
  vm.runInContext(
    between('async function sendFollowupNow(itemId', 'async function sendMessage'),
    ctx,
  );

  const blocker = ctx.withFollowupDispatch('s', () => gate);
  const automatic = ctx.sendFollowupNow('first', 's', { autoAfterRun: true });
  const manual = ctx.sendFollowupNow('clicked', 's', { manual: true });
  releaseGate();
  await Promise.all([blocker, automatic, manual]);

  assert.deepStrictEqual(
    sent,
    ['clicked'],
    'a manual click must invalidate an older queued automatic head send',
  );
  assert.deepStrictEqual(
    Array.from(queue, (item) => item.id),
    ['clicked', 'first'],
  );
}

async function testAutoDrainDefersBehindSessionAutoResume() {
  const queue = [{
    id: 'queued',
    text: 'follow up',
    display: 'follow up',
    skills: [],
    steerMode: 'interrupt',
    status: '',
    awaitingRunEnd: false,
  }];
  const scheduled = [];
  let sendCalls = 0;
  let autoResumeCalls = 0;
  let resumePending = true;
  const ctx = context({
    currentSessionId: 's',
    followupManualDispatchEpochBySession: Object.create(null),
    getFollowupQueue: () => queue,
    persistFollowupQueue() {},
    renderFollowupQueue() {},
    isSessionRunning: () => false,
    isServerStreamActive: () => false,
    isSendPipelineLocked: () => false,
    waitForSendPipelineIdle: async () => true,
    scheduleFollowupQueueDrain: (sid, delay) => {
      scheduled.push([sid, delay]);
    },
    fetch: async () => ({
      ok: true,
      json: async () => ({
        react_auto_resume: resumePending,
        run_active: false,
        stream_active: false,
      }),
    }),
    maybeAutoResumeInterruptedReact: () => {
      autoResumeCalls += 1;
    },
    encodeURIComponent: encodeURIComponent,
    startFollowupChat: async () => {
      sendCalls += 1;
      return true;
    },
    takeFollowupItem: (sid, id) => {
      const index = queue.findIndex((item) => String(item.id) === String(id));
      return index >= 0 ? queue.splice(index, 1)[0] : null;
    },
  });
  vm.runInContext(
    between('function isFollowupAutoDispatchSuperseded', 'async function sendFollowupNowImpl'),
    ctx,
  );

  const deferred = await ctx.sendQueuedFollowupAsChat('s', queue[0], 'queued', 0);
  assert.strictEqual(deferred, false, 'pending auto-drain must defer while the session auto-resumes');
  assert.strictEqual(sendCalls, 0, 'an auto-resuming session must not start an ordinary /chat turn');
  assert.strictEqual(autoResumeCalls, 1, 'the drain must wake the existing auto-resume path');
  assert.deepStrictEqual(scheduled, [['s', 1000]], 'deferred drain should retry after the resume window');
  assert.strictEqual(queue[0].status, '');
  assert.strictEqual(queue[0].awaitingRunEnd, true);

  resumePending = false;
  scheduled.length = 0;
  const sent = await ctx.sendQueuedFollowupAsChat('s', queue[0], 'queued', 0);
  assert.strictEqual(sent, true, 'once auto-resume is no longer pending the queued follow-up may send');
  assert.strictEqual(sendCalls, 1);
  assert.strictEqual(queue.length, 0);
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

function testStreamingFramesKeepFollowupRenderSignatureStable() {
  let running = true;
  let streaming = true;
  const queue = [{
    id: 'pending-1',
    status: '',
    steerMode: 'interrupt',
    display: 'keep this menu open',
    skills: [],
    awaitingRunEnd: true,
  }];
  const ctx = context({
    isSessionRunning: () => running,
    isServerStreamActive: () => streaming,
    pendingHumanQuestions: () => [],
  });
  vm.runInContext(
    between('function followupQueueRenderSignature', 'function refreshFollowupQueueRenderSignature'),
    ctx,
  );

  const first = ctx.followupQueueRenderSignature('s', queue);
  const nextAnimationFrame = ctx.followupQueueRenderSignature('s', queue);
  assert.strictEqual(nextAnimationFrame, first, 'stream animation frames must not rebuild the pending list');

  queue[0].steerMode = 'append';
  const modeChanged = ctx.followupQueueRenderSignature('s', queue);
  assert.notStrictEqual(modeChanged, first, 'a real queue mode change must invalidate the render');

  queue[0].steerMode = 'interrupt';
  running = false;
  streaming = false;
  const runEnded = ctx.followupQueueRenderSignature('s', queue);
  assert.notStrictEqual(runEnded, first, 'a run boundary must still refresh pending controls');
}

function testReattachRestoresReactGenerationFromHistory() {
  const ctx = context();
  vm.runInContext(
    between('function restoreReactGenerationFromProcessGroup', 'async function attachSessionEventStream'),
    ctx,
  );
  const rows = ['0', '1', '1'].map((generation) => ({
    getAttribute(name) {
      return name === 'data-react-generation' ? generation : null;
    },
  }));
  const processGroup = { querySelectorAll: () => rows };
  const runCtx = { reactGeneration: 0 };

  assert.strictEqual(ctx.restoreReactGenerationFromProcessGroup(runCtx, processGroup), 1);
  assert.strictEqual(runCtx.reactGeneration, 1,
    'reconnected rows must continue after the latest historical interrupt generation');
}

function rowStub(id, reorderable, top, height) {
  return {
    dataset: { id: String(id), reorderable: reorderable ? 'true' : 'false' },
    getBoundingClientRect: () => ({
      top,
      bottom: top + height,
      height,
      left: 0,
      right: 120,
    }),
  };
}

function classListStub() {
  const classes = new Set();
  return {
    add: (name) => classes.add(name),
    remove: (name) => classes.delete(name),
    contains: (name) => classes.has(name),
    toggle: (name, on) => (on ? classes.add(name) : classes.delete(name)),
    values: () => Array.from(classes),
  };
}

function testPointerCancelKeepsNativeDragAlive() {
  const calls = { ended: 0 };
  const ctx = context({
    followupDragState: { mode: 'html5', itemId: 'a', row: null },
    endFollowupDrag() { calls.ended += 1; },
  });
  vm.runInContext(between('function onFollowupPointerCancel', 'function startFollowupTouchDrag'), ctx);

  ctx.onFollowupPointerCancel({ pointerType: 'mouse' });
  assert.strictEqual(calls.ended, 0,
    'Chromium fires pointercancel when a native drag takes over the mouse pointer; '
    + 'tearing the drag state down here makes every following dragover refuse the drop');
  assert.ok(ctx.followupDragState, 'the html5 drag must survive a mouse pointercancel');

  ctx.onFollowupPointerCancel({ pointerType: 'pen' });
  assert.strictEqual(calls.ended, 0, 'a pen pointercancel must not tear down an html5 drag either');

  ctx.followupDragState = { mode: 'touch', itemId: 'a', row: null, pointerId: 7 };
  ctx.onFollowupPointerCancel({ pointerType: 'mouse' });
  assert.strictEqual(calls.ended, 0, 'a mouse pointercancel must not end a touch drag');

  ctx.onFollowupPointerCancel({ pointerType: 'touch' });
  assert.strictEqual(calls.ended, 1, 'an interrupted touch drag still has to be cleaned up');
}

function testDropTargetSnappingCoversGapsAndInFlightRows() {
  const ctx = context();
  vm.runInContext(
    between('function followupQueueRows', 'function resolveFollowupDropTargetAtPoint'),
    ctx,
  );

  const panel = (rows) => ({ querySelectorAll: () => rows });
  const q1 = rowStub('q1', true, 0, 28);
  const q2 = rowStub('q2', true, 31.4, 28);
  const q3 = rowStub('q3', true, 62.8, 28);
  const gapY = (q2.getBoundingClientRect().bottom + q3.getBoundingClientRect().top) / 2;

  const inGap = ctx.resolveFollowupDropTarget(panel([q1, q2, q3]), gapY, q1, null);
  assert.deepStrictEqual(
    JSON.parse(JSON.stringify(inGap)),
    { row: { dataset: { id: 'q2', reorderable: 'true' } }, placement: 'after' },
    'the 3.4px gap between rows must snap to the pending row above it',
  );

  const belowLast = ctx.resolveFollowupDropTarget(panel([q1, q2, q3]), 200, q1, null);
  assert.strictEqual(belowLast.row, q3, 'the panel padding below the list drops after the last row');
  assert.strictEqual(belowLast.placement, 'after');

  const aboveFirst = ctx.resolveFollowupDropTarget(panel([q1, q2, q3]), -20, q1, null);
  assert.strictEqual(aboveFirst.row, q2, 'the dragged row is never its own drop target');
  assert.strictEqual(aboveFirst.placement, 'before', 'dropping above the list inserts at the top');

  // Hovering an in-flight row is valid too: it snaps to the nearest pending row.
  const sending = rowStub('sending', false, 31.4, 28);
  const overInFlight = ctx.resolveFollowupDropTarget(panel([q1, sending, q3]), 45, q1, null);
  assert.strictEqual(overInFlight.row, q3, 'an in-flight row snaps to the next pending row');
  assert.strictEqual(overInFlight.placement, 'before');

  const hint = ctx.resolveFollowupDropTarget(panel([q1, q2, q3]), 80, q1, q3);
  assert.strictEqual(hint.row, q3, 'a direct hit keeps the row under the pointer');
  assert.strictEqual(hint.placement, 'after', 'the lower half of a row inserts after it');

  const onlyInFlight = ctx.resolveFollowupDropTarget(
    panel([q1, rowStub('a', false, 31.4, 28)]),
    45,
    q1,
    null,
  );
  assert.strictEqual(onlyInFlight, null, 'without another pending row there is nothing to reorder against');
  assert.strictEqual(ctx.resolveFollowupDropTarget(panel([q1]), 10, q1, null), null);
}

function testEdgeAutoScrollZones() {
  // The two tuning constants live above the sliced helpers in the same module.
  const ctx = context({ FOLLOWUP_DRAG_SCROLL_ZONE: 30, FOLLOWUP_DRAG_SCROLL_MAX_STEP: 16 });
  vm.runInContext(between('function followupEdgeScrollDelta', 'function stopFollowupAutoScroll'), ctx);
  const rect = { top: 100, bottom: 300, height: 200 };

  assert.strictEqual(ctx.followupEdgeScrollDelta(200, rect), 0, 'the middle of the panel must not scroll');
  assert.ok(ctx.followupEdgeScrollDelta(104, rect) < 0, 'hugging the top edge scrolls up');
  assert.ok(ctx.followupEdgeScrollDelta(296, rect) > 0, 'hugging the bottom edge scrolls down');
  assert.ok(
    Math.abs(ctx.followupEdgeScrollDelta(101, rect)) > Math.abs(ctx.followupEdgeScrollDelta(128, rect)),
    'the deeper the pointer sits inside the edge zone, the faster the list scrolls',
  );
  assert.strictEqual(ctx.followupEdgeScrollDelta(200, null), 0);
}

function testKeyboardReorderMovesWithinPendingSlots() {
  const queue = [
    { id: 'p1', status: '' },
    { id: 'sending', status: 'sending' },
    { id: 'p2', status: '' },
    { id: 'p3', status: '' },
  ];
  const ctx = context({
    getFollowupQueue: () => queue,
    persistFollowupQueue() {},
    renderFollowupQueue() {},
    document: { getElementById: () => null },
  });
  vm.runInContext(between('function moveFollowupQueueItem', 'function withdrawFollowup'), ctx);

  assert.strictEqual(ctx.moveFollowupQueueItemByOffset('s', 'p3', -1), true);
  assert.deepStrictEqual(
    queue.map((item) => item.id),
    ['p1', 'sending', 'p3', 'p2'],
    'keyboard reorder moves pending rows only; the in-flight row keeps its exact slot',
  );
  assert.strictEqual(queue[1].id, 'sending');
  assert.deepStrictEqual(queue.map((item) => item.order), [0, 1, 2, 3]);

  assert.strictEqual(ctx.moveFollowupQueueItemByOffset('s', 'p1', -1), false,
    'the first pending row cannot move up');
  assert.strictEqual(ctx.moveFollowupQueueItemByOffset('s', 'p2', 1), false,
    'the last pending row cannot move down');
  assert.strictEqual(ctx.moveFollowupQueueItemByOffset('s', 'sending', -1), false,
    'in-flight rows are not keyboard-reorderable');
}

function testDropCaretKeepsASingleIndicator() {
  const first = rowStub('a', true, 0, 28);
  const second = rowStub('b', true, 31.4, 28);
  first.classList = classListStub();
  second.classList = classListStub();
  const panel = { querySelectorAll: () => [first, second] };
  const ctx = context({ followupDropCaret: null });
  vm.runInContext(
    between('function followupQueueRows', 'function resolveFollowupDropTargetAtPoint'),
    ctx,
  );

  ctx.applyFollowupDropIndicator(panel, first, 'before');
  assert.ok(first.classList.contains('is-drag-over-before'));
  ctx.applyFollowupDropIndicator(panel, second, 'after');
  assert.ok(second.classList.contains('is-drag-over-after'));
  assert.ok(!first.classList.contains('is-drag-over-before'), 'only one insert caret may be visible');

  ctx.applyFollowupDropIndicator(panel, second, 'after');
  assert.ok(second.classList.contains('is-drag-over-after'));

  ctx.clearFollowupDragIndicators(panel);
  assert.strictEqual(second.classList.values().length, 0, 'the caret is dropped when the drag ends');
}

async function testQueuedTurnsPublishInOrderWithoutEndingTheRun() {
  const queue = [{id: 'a', text: 'a', awaitingRunEnd: true}, {id: 'b', text: 'b', awaitingRunEnd: true}];
  const requests = [];
  let releaseFirst;
  const ctx = context({
    followupDispatchChain: Object.create(null),
    isSessionRunning: () => true,
    isServerStreamActive: () => true,
    isSessionStreamStopSuppressed: () => false,
    getFollowupQueue: () => queue,
    getSessionRunState: () => ({runId: 'same-run'}),
    persistFollowupQueue() {}, renderFollowupQueue() {},
    takeFollowupItem: (sid, id) => queue.splice(queue.findIndex(item => item.id === id), 1),
    fetch: async (url, options) => {
      const body = JSON.parse(options.body);
      requests.push(body);
      if (requests.length === 1) await new Promise(resolve => { releaseFirst = resolve; });
      return {ok: true, json: async () => ({ok: true, items: body.items.map(item => ({
        id: 'server-' + item.message, client_id: item.client_id, state: 'queued', after_turn: true,
      }))})};
    },
  });
  vm.runInContext(between('function withFollowupDispatch', 'function shouldApplySseSeqFilter'), ctx);
  vm.runInContext(between('function publishFollowupQueueToRun', 'function appendFollowupQueueItem'), ctx);
  vm.runInContext(between('function moveFollowupQueueItem', 'function focusFollowupQueueGrip'), ctx);
  const first = ctx.publishFollowupQueueToRun('s');
  await Promise.resolve();
  await Promise.resolve();
  assert.strictEqual(requests.length, 1);
  const clientId = queue[0].clientId;
  ctx.moveFollowupQueueItem('s', 'b', 'a', 'before');
  releaseFirst();
  await first;
  await ctx.withFollowupDispatch('s', async () => {});
  assert.deepStrictEqual(requests.map(request => request.items.map(item => item.message)), [['a', 'b'], ['b', 'a']]);
  assert.strictEqual(queue[1].clientId, clientId, 'reorder/retries must reuse durable operation identities');
  assert.ok(queue.every(item => item.serverQueued && !item.status), 'server-queued turns remain sortable until claimed');
  assert.ok(requests.every(request => request.source_run_id === 'same-run'));
}

async function testQueuedTurnWithdrawalWaitsForItsRegistration() {
  const queue = [{id: 'a', text: 'a', awaitingRunEnd: true}];
  let release;
  const cancellations = [];
  const restored = [];
  const ctx = context({
    currentSessionId: 's', followupDispatchChain: Object.create(null),
    isSessionRunning: () => true, isServerStreamActive: () => true,
    getSessionRunState: () => ({runId: 'same-run'}), getFollowupQueue: () => queue,
    persistFollowupQueue() {}, renderFollowupQueue() {},
    cancelSteerMessage: async (sid, item) => { cancellations.push(item.steerId); },
    returnFollowupToInput: (sid, item) => { restored.push(item.text); },
    fetch: async (url, options) => {
      const item = JSON.parse(options.body).items[0];
      await new Promise(resolve => { release = resolve; });
      return {ok: true, json: async () => ({ok: true, items: [{id: 'server-a', client_id: item.client_id, state: 'queued', after_turn: true}]})};
    },
  });
  vm.runInContext(between('function withFollowupDispatch', 'function shouldApplySseSeqFilter'), ctx);
  vm.runInContext(between('function publishFollowupQueueToRun', 'function appendFollowupQueueItem'), ctx);
  vm.runInContext(between('function takeFollowupItem', 'function moveFollowupQueueItem'), ctx);
  vm.runInContext(between('function withdrawFollowup', 'function returnFollowupToInput'), ctx);
  const registering = ctx.publishFollowupQueueToRun('s');
  await Promise.resolve(); await Promise.resolve();
  ctx.withdrawFollowup('a');
  assert.strictEqual(queue[0].status, 'withdrawing');
  release();
  await registering;
  await ctx.withFollowupDispatch('s', async () => {});
  assert.deepStrictEqual(cancellations, ['server-a']);
  assert.deepStrictEqual(restored, ['a']);
  assert.strictEqual(queue.length, 0);
}

async function testLateQueueAcknowledgementCannotResendAConsumedTurn() {
  const queue = [{id: 'a', text: 'a', clientId: 'stable-client'}];
  const ctx = context({
    getFollowupQueue: () => queue, persistFollowupQueue() {}, renderFollowupQueue() {},
    takeFollowupItem: () => queue.pop(),
    scheduleFollowupQueueDrain() {},
    fetch: async () => ({ok: true, json: async () => ({ok: true, items: [{id: 'server-a', client_id: 'stable-client', after_turn: true, state: 'consumed'}]})}),
  });
  vm.runInContext(between('async function ensureQueuedFollowupRegistered', 'function startFollowupChat'), ctx);
  assert.strictEqual(await ctx.ensureQueuedFollowupRegistered('s', queue[0]), false);
  assert.strictEqual(queue.length, 0);
}

(async () => {
  await testQueuedTurnsPublishInOrderWithoutEndingTheRun();
  await testQueuedTurnWithdrawalWaitsForItsRegistration();
  await testLateQueueAcknowledgementCannotResendAConsumedTurn();
  await testDispatcherDoesNotConsumePendingRows();
  await testAutoDrainRequiresACompleteIdleBoundary();
  await testPendingQueueCanBeReordered();
  await testRunStartSignalAndFallbacks();
  await testManualSendPrioritizesTheClickedRow();
  await testManualSendSupersedesAnAlreadyQueuedAutoHead();
  await testAutoDrainDefersBehindSessionAutoResume();
  testAppendOptimisticRowCommitsInPlace();
  testStreamingFramesKeepFollowupRenderSignatureStable();
  testReattachRestoresReactGenerationFromHistory();
  testPointerCancelKeepsNativeDragAlive();
  testDropTargetSnappingCoversGapsAndInFlightRows();
  testEdgeAutoScrollZones();
  testKeyboardReorderMovesWithinPendingSlots();
  testDropCaretKeepsASingleIndicator();
  process.stdout.write('followup dispatcher runtime checks passed\n');
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
