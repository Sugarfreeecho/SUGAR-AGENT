const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.resolve(__dirname, '../../frontend/src/app/modules/sse-handling.js'), 'utf8');
const management = fs.readFileSync(path.resolve(__dirname, '../../frontend/src/app/modules/session-management.js'), 'utf8');
function fn(name, text = source) {
  const match = text.match(new RegExp('(?:async )?function ' + name + '\\([^]*?^}', 'm'));
  assert(match, name);
  return match[0];
}
async function flush() {
  await new Promise(resolve => setImmediate(resolve));
}

function fixture() {
  const timers = new Map();
  const reconnects = [];
  let nextTimer = 1, run = null, active = true, requests = 0, resets = 0;
  const c = vm.createContext({
    console: { error() {}, warn() {} }, Promise, AbortController, Date, Map, Set,
    SSE_CONNECT_TIMEOUT_MS: 20000,
    setTimeout(callback, delay) { const id = nextTimer++; timers.set(id, { callback, delay }); return id; },
    clearTimeout(id) { timers.delete(id); },
    currentSessionId: 's', navigator: { onLine: true },
    sessionStore: { ui: {}, getActiveRunInfo: () => ({ run_id: 'run' }) },
    runtimeTakeoverBySession: Object.create(null),
    executionRecoveryBySession: new Map(), streamHistoryRecoveryBySession: new Set(),
    getSessionRunState: () => run,
    setSessionRunState: (_sid, state) => { run = state; },
    clearSessionRunState: () => { run = null; },
    isServerStreamActive: () => active,
    isSessionStreamStopSuppressed: () => false,
    getVisibleChatStream: () => ({}), newDomContext: stream => ({ stream }),
    findExecutionProcessGroup: () => null, seedEphemeralRecoveryScope() {},
    requestExtensionStateConvergence() {}, resetLlmState() {}, initRunFinalTracking() {},
    finalizeLlmStreamChunks() {}, finalizeProgressStreamChunks() {},
    setSendButtonState() {}, syncSessionListIndicatorClasses() {}, appendLog() {},
    refreshSingleSessionRow: async () => {}, reconcileRunStateFromServer: async () => {},
    getUiEventCount: async () => 0, getRunAbortReason: () => '',
    applyContextTokenLabelForCurrentSession() {},
    scheduleFinalVisibleAfterRunIfEnabled() {},
    scheduleActiveSessionReconnect: (_sid, opts) => { reconnects.push(opts); },
    resetStreamReconnectState: () => { resets++; },
    setSessionServerStreamActive() {},
    document: { dispatchEvent() {} }, CustomEvent: class {},
    consumeAgentSseResponse: async (_response, ctx) => { ctx.terminalSeen = true; },
    fetch: (_url, options) => {
      requests++;
      return new Promise((_resolve, reject) => {
        options.signal.addEventListener('abort', () => {
          const error = new Error('aborted'); error.name = 'AbortError'; reject(error);
        }, { once: true });
      });
    },
  });
  for (const name of ['fetchSessionEventStream', 'attachSessionEventStream']) vm.runInContext(fn(name), c);
  vm.runInContext(fn('maybeTakeOverActiveRuntimeSession', management), c);
  return {
    c, timers, reconnects,
    run: () => run,
    setActive: value => { active = value; },
    stats: () => ({ requests, resets }),
    expireHandshake() {
      const timer = [...timers.values()].find(value => value.delay === 20000);
      assert(timer, 'connection watchdog must be armed');
      timer.callback();
    },
  };
}

async function main() {
  const hung = fixture();
  const controller = new AbortController();
  const pending = hung.c.fetchSessionEventStream('/stream', controller);
  hung.expireHandshake();
  await assert.rejects(pending, error => error.name === 'SseConnectTimeout');
  assert.equal(controller.signal.aborted, true);
  assert.equal(hung.timers.size, 0);

  const ignoredAbort = fixture();
  ignoredAbort.c.fetch = () => new Promise(() => {});
  const ignored = ignoredAbort.c.fetchSessionEventStream('/stream', new AbortController());
  ignoredAbort.expireHandshake();
  await assert.rejects(ignored, error => error.name === 'SseConnectTimeout');

  const connected = fixture();
  const liveController = new AbortController();
  let liveSignal;
  const response = { ok: true, body: {} };
  connected.c.fetch = async (_url, options) => { liveSignal = options.signal; return response; };
  assert.equal(await connected.c.fetchSessionEventStream('/stream', liveController), response);
  assert.equal(connected.timers.size, 0, 'successful handshake must cancel the watchdog');
  assert.equal(liveSignal, liveController.signal);
  assert.equal(liveSignal.aborted, false);
  liveController.abort();
  assert.equal(liveSignal.aborted, true, 'stop must still abort the connected response body');

  const aborted = fixture();
  const abortController = new AbortController();
  const cancelled = aborted.c.fetchSessionEventStream('/stream', abortController);
  abortController.abort();
  await assert.rejects(cancelled, error => error.name === 'AbortError');
  assert.equal(aborted.timers.size, 0);

  const recovery = fixture();
  const attach = recovery.c.attachSessionEventStream('s', { force: true, skipInitialLoad: true, afterIndex: 0 });
  assert(recovery.run(), 'connecting observer owns a local run slot');
  recovery.expireHandshake();
  await attach;
  assert.equal(recovery.run(), null, 'timed-out handshake must release its local run slot');
  assert(recovery.reconnects.some(options => options.failure === true));
  assert(![...recovery.timers.values()].some(timer => timer.delay === 20000));

  recovery.c.maybeTakeOverActiveRuntimeSession({ active_session_ids: ['s'] });
  await flush();
  assert.equal(recovery.stats().requests, 2, 'heartbeat must be able to reacquire the observer');
  assert.equal(recovery.stats().resets, 1);
  recovery.setActive(false);
  recovery.expireHandshake();
  await recovery.c.runtimeTakeoverBySession.s;
  await flush();
  assert.equal(recovery.run(), null);
  assert.equal(recovery.c.runtimeTakeoverBySession.s, undefined);
  console.log('stream connection timeout and heartbeat recovery: passed');
}

main().catch(error => { console.error(error); process.exitCode = 1; });
