const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const root = path.resolve(__dirname, '../..');
const read = name => fs.readFileSync(path.join(root, 'frontend/src/app/modules', name + '.js'), 'utf8');
function section(text, start, end) {
  const a = text.indexOf(start), b = text.indexOf(end, a);
  assert(a >= 0 && b > a);
  return text.slice(a, b);
}
const management = read('session-management'), history = read('session-scroll-history'), rendering = read('message-rendering');

function loader(fetcher) {
  const errors = [], requests = [];
  const context = vm.createContext({
    console: { error() {}, warn() {} }, AbortController, Date, Promise, setTimeout, clearTimeout,
    performance: { now: Date.now }, currentSessionId: 's', messageLoadEpoch: 0, replayingMessages: false,
    sessionStore: { ui: {} }, HISTORY_DIALOGUES_PER_PAGE: 5, HISTORY_EVENT_BUDGET: 500,
    resetSessionHistoryPaging() {}, hideLoading() {}, getVisibleChatStream: () => null,
    document: { getElementById: () => null }, beforeSessionMessageSnapshotAvailable: () => true,
    appendLogVisible: message => errors.push(message), markVisibleSessionStreamLoadState() {}, showSessionLoadRetry() {},
    fetchWithTimeout: async (url, options, timeout) => {
      requests.push({ url, signal: options.signal, timeout });
      return fetcher(url, options, timeout);
    },
  });
  vm.runInContext(section(management, 'var sessionHistoryLoadController', 'function chatStreamHasConversationContent'), context);
  return { context, errors, requests };
}

async function main() {
  const timed = loader(async () => {
    assert.equal(timed.context.replayingMessages, false, 'waiting for a snapshot must not turn live SSE into history replay');
    const error = new Error('timeout'); error.name = 'AbortError'; throw error;
  });
  assert.equal(await timed.context.loadSessionMessages('s'), false);
  assert.equal(timed.requests.length, 1, 'timeout must not launch a second projection via /messages');
  assert.equal(timed.requests[0].timeout, 30000);
  assert(timed.requests[0].url.includes('prefer_active_turn=true'));

  let first = true;
  const cancelled = loader(async (_url, options) => {
    if (first) {
      first = false;
      return new Promise((_resolve, reject) => options.signal.addEventListener('abort', () => {
        const error = new Error('cancelled'); error.name = 'AbortError'; reject(error);
      }, { once: true }));
    }
    return { status: 503, ok: false, json: async () => ({}) };
  });
  const old = cancelled.context.loadSessionMessages('s');
  cancelled.context.currentSessionId = 'new';
  const next = cancelled.context.loadSessionMessages('new');
  assert.equal(await old, false);
  assert.equal(await next, false);
  assert(cancelled.requests[0].signal.aborted);
  assert.equal(cancelled.errors.length, 1, 'superseded session must not show a load failure');

  let olderCalls = 0;
  const pagingStream = {};
  const paging = vm.createContext({
    currentSessionId: 's', chatContainer: { scrollTop: 0 },
    getVisibleChatStream: () => pagingStream,
    sessionHasLiveHistoryOwner: () => true,
    sessionStore: { ui: { loadingMessages: false } },
    getSessionHistoryPaging: () => ({ manual_history: true }),
    loadOlderHistoryChunk: () => olderCalls++,
  });
  vm.runInContext(section(history, 'var HISTORY_AUTO_LOAD_TOP_PX', 'function updateHistorySentinelVisibility'), paging);
  paging.maybeAutoLoadOlderHistory();
  assert.equal(olderCalls, 0, 'live-turn history stays deferred even at scrollTop=0');
  paging.enableHistoryAutoLoadForReader();
  paging.maybeAutoLoadOlderHistory();
  assert.equal(olderCalls, 1, 'upward reading re-enables automatic pagination during generation');
  paging.sessionStore.ui.loadingMessages = true;
  paging.maybeAutoLoadOlderHistory();
  assert.equal(olderCalls, 1, 'first-screen hydration must not trigger older pages');
  paging.sessionStore.ui.loadingMessages = false;
  delete pagingStream._historyAutoLoadEnabled;
  paging.sessionHasLiveHistoryOwner = () => false;
  paging.maybeAutoLoadOlderHistory();
  assert.equal(olderCalls, 2, 'a cached current-turn flag must not disable pagination after stopping');

  let resolveOlder;
  const olderStream = {};
  const olderContext = vm.createContext({
    console, currentSessionId: 's', historyOlderLoading: false, replayingMessages: false,
    sessionHistoryPaging: { sessionId: 's', has_older: true, range_start: 5 },
    HISTORY_DIALOGUES_PER_PAGE: 5, HISTORY_EVENT_BUDGET: 500, chatContainer: null,
    getVisibleChatStream: () => olderStream, updateHistorySentinelVisibility() {},
    fetchWithTimeout: () => new Promise(resolve => { resolveOlder = resolve; }),
  });
  vm.runInContext(section(history, 'function cancelHistoryPrependViewport', 'async function loadOlderHistoryChunk'), olderContext);
  vm.runInContext(section(history, 'async function loadOlderHistoryChunk', 'function insertNewEmptyChatStream'), olderContext);
  const olderPending = olderContext.loadOlderHistoryChunk();
  assert.equal(olderContext.replayingMessages, false, 'waiting for older pages must not change live rendering');
  // A new session starts hydration while the obsolete network request waits.
  olderContext.currentSessionId = 'new';
  olderContext.replayingMessages = true;
  olderContext.historyOlderLoading = true;
  resolveOlder({ ok: true, json: async () => ({ events: [] }) });
  await olderPending;
  assert.equal(olderContext.replayingMessages, true, 'an obsolete request must not end a newer replay');
  assert.equal(olderContext.historyOlderLoading, true, 'an obsolete request must not reset a newer load');

  let timer;
  const timeoutContext = vm.createContext({
    AbortController, Number, Object,
    setTimeout: callback => { timer = callback; return 1; }, clearTimeout() {},
    fetch: (_url, options) => new Promise((_resolve, reject) => options.signal.addEventListener('abort', () => {
      const error = new Error('aborted'); error.name = 'AbortError'; reject(error);
    }, { once: true })),
  });
  vm.runInContext(section(management, 'async function fetchWithTimeout', 'async function fetchArchivedSessionPage'), timeoutContext);
  const external = new AbortController();
  const pending = timeoutContext.fetchWithTimeout('/history', { signal: external.signal }, 30000);
  assert.equal(typeof timer, 'function', 'external cancellation must not disable the timeout');
  timer();
  await assert.rejects(pending, error => error.name === 'AbortError');
  assert.equal(external.signal.aborted, false);

  const oldGroup = { dataset: { processGroupId: 'turn:1' }, isConnected: true };
  const currentGroup = { dataset: { processGroupId: 'turn:2' }, isConnected: true };
  const unrelated = { dataset: { processGroupId: 'turn:99' }, isConnected: true };
  const stream = { querySelectorAll: () => [oldGroup, currentGroup, unrelated] };
  const groups = vm.createContext({ Array, String, replayingMessages: false });
  vm.runInContext(section(rendering, 'function findExecutionProcessGroup', 'function selectExecutionProcessGroup'), groups);
  vm.runInContext(section(rendering, 'function ensureProcessGroup', 'function sealProcessGroup'), groups);
  const ctx = { stream, processGroupId: 'turn:2', currentProcessGroup: unrelated };
  assert.strictEqual(groups.ensureProcessGroup(ctx), currentGroup);
  assert.strictEqual(groups.ensureProcessGroup(ctx), currentGroup, 'stable group must be reused on repeated recovery');
  assert.strictEqual(groups.findExecutionProcessGroup(stream, 'turn:2', 'r'), currentGroup);
  assert.strictEqual(groups.findExecutionProcessGroup(stream, 'missing', 'r'), null, 'attach must not claim an unrelated last group');

  function runningGroup(groupId) {
    const classes = new Set(['is-running']);
    return { dataset: { processGroupId: groupId, procStartedAt: '1' }, isConnected: true,
      classList: { remove: value => classes.delete(value), contains: value => classes.has(value) },
      querySelector: () => null };
  }
  const duplicateA = runningGroup('turn:2'), duplicateB = runningGroup('turn:2');
  const otherRun = runningGroup('turn:3');
  const sealContext = vm.createContext({
    Array, String, procNow: () => 20, refreshProcessAggregateStats() {}, updateProcessBrief() {},
    refreshLiveProcessAggregateStats: () => false, stopLiveProcessAggregateStats() {},
    resetKeyContextStreamFilter() {}, finalizeProgressStreamChunks() {},
  });
  vm.runInContext(section(rendering, 'function sealProcessGroup', 'function getProcessBody'), sealContext);
  sealContext.sealProcessGroup({
    stream: { querySelectorAll: () => [duplicateA, duplicateB, otherRun] },
    processGroupId: 'turn:2', currentProcessGroup: duplicateA,
  });
  assert(!duplicateA.classList.contains('is-running') && !duplicateB.classList.contains('is-running'));
  assert.equal(duplicateB.dataset.procEndedAt, '20', 'all duplicate timers must stop on completion');
  assert(otherRun.classList.contains('is-running'), 'sealing must respect process ownership');
  process.stdout.write('session loading runtime checks passed\n');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
