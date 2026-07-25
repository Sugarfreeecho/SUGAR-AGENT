const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const root = path.resolve(__dirname, '..', '..');
const source = fs.readFileSync(
  path.join(root, 'frontend', 'src', 'app', 'modules', 'session-scroll-history.js'),
  'utf8',
);

function between(start, end) {
  const from = source.indexOf(start);
  const to = source.indexOf(end, from);
  assert(from >= 0, `missing start marker: ${start}`);
  assert(to > from, `missing end marker: ${end}`);
  return source.slice(from, to);
}

function context(extra = {}) {
  return vm.createContext(Object.assign({
    console,
    Object,
    Promise,
    setTimeout,
    clearTimeout,
  }, extra));
}

function loadPagingHelpers(ctx) {
  vm.runInContext(
    between('function persistHistoryPagingToStream', 'function ensureHistorySentinel'),
    ctx,
  );
  vm.runInContext(
    between('var latestHistoryTailRestoreBySession', 'var HISTORY_AUTO_LOAD_TOP_PX'),
    ctx,
  );
}

async function testGapMetadataSurvivesStreamCachingAndTailRestoreIsCoalesced() {
  const stream = { dataset: {} };
  let loadCalls = 0;
  let releaseLoad;
  const loadGate = new Promise((resolve) => { releaseLoad = resolve; });
  const ctx = context({
    currentSessionId: 's',
    sessionHistoryPaging: null,
    getVisibleChatStream: () => stream,
    updateHistorySentinelVisibility() {},
    isSessionRunning: () => false,
    isServerStreamActive: () => false,
    async loadSessionMessages() {
      loadCalls += 1;
      await loadGate;
      ctx.setSessionHistoryPaging({
        sessionId: 's',
        total: 1001,
        range_start: 980,
        range_end: 1001,
        has_older: true,
        has_newer: false,
      });
      return true;
    },
  });
  loadPagingHelpers(ctx);

  ctx.setSessionHistoryPaging({
    sessionId: 's',
    total: 1000,
    range_start: 0,
    range_end: 80,
    has_older: false,
    has_newer: true,
  });
  assert.strictEqual(JSON.parse(stream.dataset.historyPaging).has_newer, true);
  ctx.sessionHistoryPaging = null;
  assert.strictEqual(ctx.restoreHistoryPagingFromStream(stream).has_newer, true);

  const first = ctx.ensureLatestHistoryTailForLiveAppend('s');
  const second = ctx.ensureLatestHistoryTailForLiveAppend('s');
  assert.strictEqual(loadCalls, 1, 'concurrent live starts must share one tail reload');
  releaseLoad();
  assert.strictEqual(await first, true);
  assert.strictEqual(await second, true);
  assert.strictEqual(JSON.parse(stream.dataset.historyPaging).has_newer, false);
}

async function testRunStartingDuringTargetFetchCannotReplaceTheLiveOwner() {
  let cleared = 0;
  const stream = {};
  const ctx = context({
    currentSessionId: 's',
    replayingMessages: false,
    sessionHasLiveHistoryOwner: () => false,
    refreshSessionLiveHistoryOwner: async () => true,
    fetch: async () => ({
      ok: true,
      json: async () => ({
        events: [{ type: 'user', content: 'old' }],
        total: 1000,
        range_start: 0,
        range_end: 80,
        has_older: false,
        has_newer: true,
      }),
    }),
    getVisibleChatStream: () => stream,
    ensureVisibleChatStreamSlot() {},
    emptyChatStreamKeepingStrip() { cleared += 1; },
    beginMessageReplay() {},
    setSessionHistoryPaging() {},
    ensureHistorySentinel() {},
    newDomContext: () => ({}),
    reduceAndRenderMessageEvent() {},
    bindExistingLogs() {},
    rebuildToc() {},
    updateHistorySentinelVisibility() {},
  });
  vm.runInContext(
    between('async function loadHistoryWindowAroundEventIndex', 'const SESSION_STREAM_CACHE_LIMIT'),
    ctx,
  );

  assert.strictEqual(await ctx.loadHistoryWindowAroundEventIndex('s', 0, { turns: 50 }), false);
  assert.strictEqual(cleared, 0, 'a newly-live stream must not be cleared by the old history response');
}

async function testTargetWindowRecordsItsMissingNewerTail() {
  let paging = null;
  const stream = {};
  const ctx = context({
    currentSessionId: 's',
    replayingMessages: false,
    sessionHasLiveHistoryOwner: () => false,
    refreshSessionLiveHistoryOwner: async () => false,
    fetch: async () => ({
      ok: true,
      json: async () => ({
        events: [{ type: 'user', content: 'old' }],
        total: 1000,
        range_start: 0,
        range_end: 80,
        has_older: false,
      }),
    }),
    getVisibleChatStream: () => stream,
    ensureVisibleChatStreamSlot() {},
    emptyChatStreamKeepingStrip() {},
    beginMessageReplay() {},
    setSessionHistoryPaging(value) { paging = value; },
    ensureHistorySentinel() {},
    newDomContext: () => ({}),
    reduceAndRenderMessageEvent() {},
    bindExistingLogs() {},
    rebuildToc() {},
    updateHistorySentinelVisibility() {},
  });
  vm.runInContext(
    between('async function loadHistoryWindowAroundEventIndex', 'const SESSION_STREAM_CACHE_LIMIT'),
    ctx,
  );

  assert.strictEqual(await ctx.loadHistoryWindowAroundEventIndex('s', 0, { turns: 50 }), true);
  assert.strictEqual(paging.has_newer, true);
  assert.strictEqual(paging.range_end, 80);
  assert.strictEqual(paging.total, 1000);
}

(async () => {
  await testGapMetadataSurvivesStreamCachingAndTailRestoreIsCoalesced();
  await testRunStartingDuringTargetFetchCannotReplaceTheLiveOwner();
  await testTargetWindowRecordsItsMissingNewerTail();
  process.stdout.write('history tail runtime checks passed\n');
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
