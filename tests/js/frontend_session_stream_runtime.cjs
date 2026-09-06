const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const { execFileSync } = require('child_process');

const root = path.resolve(__dirname, '../..');
const ref = process.env.UI_REVIEW_REF;
function source(name) {
  const file = `frontend/src/app/modules/${name}.js`;
  return ref ? execFileSync('git', ['show', `${ref}:${file}`], { cwd: root, encoding: 'utf8' })
    : fs.readFileSync(path.join(root, file), 'utf8');
}
function between(text, start, end) {
  const a = text.indexOf(start), b = text.indexOf(end, a);
  assert(a >= 0 && b > a, `missing section ${start}`);
  return text.slice(a, b);
}
const scrolling = source('session-scroll-history');
const rendering = source('message-rendering');
function port() {
  const attrs = new Map();
  const listeners = {};
  return {
    isConnected: true, scrollTop: 800, scrollHeight: 1000, clientHeight: 100,
    style: {}, listeners, addEventListener(name, fn) { listeners[name] = fn; }, querySelectorAll: () => [],
    setAttribute(k, v) { attrs.set(k, v); }, removeAttribute(k) { attrs.delete(k); },
  };
}
function runtime(extra = {}) {
  const frames = new Map();
  let next = 1, now = 0;
  const context = vm.createContext(Object.assign({
    console, Date, Promise, window: { __MYAGENT_FEATURES__: { smoothStream: true } },
    performance: { now: () => now }, setTimeout: () => 1, clearTimeout() {},
    requestAnimationFrame(fn) { const id = next++; frames.set(id, fn); return id; },
    cancelAnimationFrame(id) { frames.delete(id); },
  }, extra));
  vm.runInContext(source('smooth-stream'), context);
  function frame() {
    now += 16.67;
    const batch = Array.from(frames.values()); frames.clear();
    batch.forEach(fn => fn(now));
  }
  return { context, frame, frames };
}
function switchFixture() {
  const gates = {}, effects = [];
  const rt = runtime({
    currentSessionId: 'old', switchSessionEpoch: 0, messageLoadEpoch: 0,
    replayingMessages: false, suppressTocDuringSessionLoad: false,
    pendingRewriteTruncate: null, recentComposerQueuedFollowup: null,
    sessionUnreadComplete: new Set(),
    sessionStore: { ui: {}, get: () => ({ last_activity_at: new Date().toISOString() }) },
    document: { dispatchEvent() {} }, CustomEvent: function () {}, localStorage: { setItem() {} },
    isSessionRunning: () => false, isServerStreamActive: () => false,
    restoreStreamForRunningSession: () => false,
    restoreCachedSessionStream(sid) { effects.push({ restored: sid, current: c.currentSessionId }); return true; },
    setCurrentSessionState(sid) { c.currentSessionId = sid; },
    refreshSingleSessionRow: sid => new Promise(resolve => { gates[sid] = resolve; }),
    streamChatNearBottom: true, streamProcNearBottom: true, liveAutoFollow: true,
  });
  const c = rt.context;
  for (const name of ['endHistorySmoothScroll', 'clearTocForSessionLoad', 'clearOptionalPanelsForSessionLoad',
    'hideRewriteUndoToast', 'clearSessionUnreadState', 'saveChatScrollForSession', 'stashInputDraft',
    'prepareStashLeaving', 'hideSubagentContinueBanner', 'resetSubagentPanelForSession', 'updateSessionTitle',
    'restoreInputDraft', 'syncSessionListIndicatorClasses', 'setSendButtonState', 'hideLoading', 'rebuildToc',
    'scheduleContextTokensAfterPaint', 'restoreCachedSessionScrollPosition', 'maybeStartStreamPollForSession']) c[name] = () => {};
  c.chatContainer = port();
  c.getVisibleChatStream = () => ({ querySelectorAll: () => [] });
  if (scrolling.includes('function cancelSmoothStreamFollowForSessionSwitch(')) {
    vm.runInContext(between(scrolling, 'function cancelSmoothStreamFollowForSessionSwitch(', 'function getVisibleChatStream('), c);
  }
  vm.runInContext(between(source('session-management'), 'async function switchSession(', 'async function createNewSession('), c);
  return { ...rt, gates, effects };
}
function loadTextHelpers(c) {
  vm.runInContext(between(rendering, 'function trimSurroundingBlankLines(', 'function reactFeedPhase('), c);
  if (scrolling.includes('function writeLlmStreamText(')) {
    vm.runInContext(between(scrolling, 'function writeLlmStreamText(', 'function flushLlmDeltaText('), c);
  }
  vm.runInContext(between(scrolling, 'function flushLlmDeltaText(', 'function scheduleLlmDeltaFlush('), c);
  Object.assign(c, { LOG_TRUNCATE_HEAD_LINES: 40, LOG_TRUNCATE_TAIL_LINES: 40,
    LOG_TRUNCATE_HEAD_CHARS: 5000, LOG_TRUNCATE_TAIL_CHARS: 5000 });
}
function scroller() {
  const row = { _processBriefRawText: '' };
  let textNode = null;
  const sc = {
    writes: 0, appends: 0, isConnected: true, closest: () => row,
    get firstChild() { return textNode; }, get lastChild() { return textNode; },
    get textContent() { return textNode ? textNode.data : ''; },
    set textContent(s) {
      sc.writes++;
      textNode = { nodeType: 3, data: s, appendData(delta) { this.data += delta; sc.appends++; } };
    },
  };
  return sc;
}
function flushText(c, sc, text, part = 'Response', smooth = true) {
  const ctx = { llm: { [`llmPending${part}Delta`]: text, [`llmStream${part}Scroller`]: sc } };
  let steps = 0;
  while (ctx.llm[`llmPending${part}Delta`] && steps++ < 2000) c.flushLlmDeltaText(ctx, { smooth, dtMs: 16.67 });
  assert(steps < 2000);
  return sc.textContent;
}
function loadNavigationHelpers(c) {
  vm.runInContext(between(scrolling, 'function setScrollTopImmediate(', '/** 当前运行会话'), c);
  vm.runInContext(between(scrolling, 'function cancelSmoothStreamFollowForHistoryLoad(', 'function getVisibleChatStream('), c);
  vm.runInContext(between(rendering, 'function scrollToBottom(', '// 滚动位置存储'), c);
  vm.runInContext(between(rendering, 'var historySmoothScrollSessionId', "window.addEventListener('beforeunload'"), c);
  vm.runInContext(between(rendering, 'function historyLoadScrollsToBottom(', 'function setWelcome('), c);
  c.getProcessBodyElForCurrentRun = () => null;
}
// Model the CSS smooth default and browser clamping. A bare scrollTop write
// after an immediate jump must not accidentally start another native glide.
function navigationPort() {
  const p = port();
  let top = 120;
  p.writes = [];
  p.style.scrollBehavior = 'smooth';
  Object.defineProperty(p, 'scrollTop', {
    get: () => top,
    set(y) {
      p.writes.push(p.style.scrollBehavior);
      top = Math.max(0, Math.min(y, p.scrollHeight - p.clientHeight));
    },
  });
  p.scrollTo = ({ top: y, behavior }) => { p.writes.push(behavior); top = Math.min(y, p.scrollHeight - p.clientHeight); };
  p.removeEventListener = (name, fn) => { if (p.listeners[name] === fn) delete p.listeners[name]; };
  return p;
}
async function testUnreadNavigation() {
  for (const badge of ['server', 'local', 'none']) {
    const rt = switchFixture(), c = rt.context, timers = [], modes = [];
    c.setTimeout = fn => { timers.push(fn); return timers.length; };
    c.sessionStore.get = () => ({ last_activity_at: '2020-01-01', unread_result: badge === 'server' });
    if (badge === 'local') c.sessionUnreadComplete.add('B');
    c.clearSessionUnreadState = sid => { c.sessionUnreadComplete.delete(sid); };
    c.restoreCachedSessionStream = () => { assert.equal(badge, 'none', 'unread must bypass old cached DOM'); return false; };
    for (const name of ['resetSessionHistoryPaging', 'emptyChatStreamKeepingStrip', 'showLoading', 'refreshSubagentTreePanel']) c[name] = () => {};
    c.loadSessionMessages = async (sid, mode) => { modes.push(mode); return true; };
    const switched = c.switchSession('B');
    await timers.shift()();
    await switched;
    assert.deepEqual(modes, [badge === 'none' ? 'smooth-bottom' : 'bottom']);
  }

  const rt = runtime({ currentSessionId: 's', switchSessionEpoch: 1,
    isSessionRunning: () => false, isServerStreamActive: () => false,
    chatContainer: navigationPort(), streamChatNearBottom: false, streamProcNearBottom: false, liveAutoFollow: false });
  const c = rt.context;
  loadNavigationHelpers(c);
  c.getSavedScrollPosition = c.getSavedScrollAnchorPosition = () => { throw new Error('unread must not read old anchors'); };
  vm.runInContext('smoothFollowController.request(chatContainer);', c);
  c.applyChatScrollAfterHistoryLoad('s', 'bottom');
  assert.equal(c.chatContainer.scrollTop, 900, 'first placement is immediate');
  c.chatContainer.scrollHeight += 300; // queued overflow/layout work
  rt.frame();
  for (let i = 0; i < 120; i++) rt.frame();
  assert.equal(c.chatContainer.scrollTop, 1200, 'layout correction stays at the newest result');
  assert(c.chatContainer.writes.every(mode => mode === 'auto'), 'no CSS or native smooth restart');
  assert.equal(vm.runInContext('smoothFollowController.isFollowing(chatContainer)', c), false);
  assert.equal(rt.frames.size, 0, 'no lingering follower');
  assert.equal(c.chatContainer.style.scrollBehavior, 'smooth', 'temporary style is restored');

  c.scrollToBottom();
  c.switchSessionEpoch += 2; // A -> B -> A before the old callback runs
  c.chatContainer.scrollTop = 120;
  rt.frame();
  assert.equal(c.chatContainer.scrollTop, 120, 'stale bottom callback cannot override a new visit');
  c.scrollToBottom();
  c.chatContainer.scrollTop = 200;
  rt.frame();
  assert.equal(c.chatContainer.scrollTop, 200, 'reader movement cancels the layout correction');

  c.beginHistorySmoothScroll('s');
  c.chatContainer.scrollTop = 100;
  const oldWait = c.waitForChatScrollAfterHistoryLoad('s', 'smooth-bottom');
  c.switchSessionEpoch += 2;
  c.beginHistorySmoothScroll('s');
  c.chatContainer.listeners.scrollend();
  assert.equal(await oldWait, false, 'old animation cannot retarget after A -> B -> A');
  assert.equal(c.chatContainer.scrollTop, 100);
  assert.equal(c.isHistorySmoothScrollActive(), true, 'old cleanup cannot release new scroll ownership');
}

async function testUnreadHistoryLoadLayout() {
  const rt = runtime({ currentSessionId: 's', switchSessionEpoch: 1, messageLoadEpoch: 0,
    sessionStore: { ui: {} }, replayingMessages: false, suppressTocDuringSessionLoad: false,
    HISTORY_DIALOGUES_PER_PAGE: 20, HISTORY_EVENT_BUDGET: 1000,
    chatContainer: navigationPort(), isSessionRunning: () => false, isServerStreamActive: () => false,
    getSessionRunState: () => null, document: { getElementById: () => null },
    beforeSessionMessageSnapshotAvailable: () => false,
    fetchWithTimeout: async () => ({ ok: true, json: async () => [{ type: 'user' }, { type: 'final' }] }),
    newDomContext: stream => ({ stream }), chatStreamHasConversationContent: () => true,
    streamChatNearBottom: true, streamProcNearBottom: true, liveAutoFollow: true,
    shouldGateScrollByRunSession: () => false, isSubagentStreamCtx: () => false,
  });
  const c = rt.context, stream = { hidden: false, querySelectorAll: () => [] }, order = [];
  c.getVisibleChatStream = () => stream;
  loadNavigationHelpers(c);
  vm.runInContext(between(scrolling, 'function followStreamProcessScroll(', 'function finishStreamScrollIfFollow('), c);
  for (const name of ['hideLoading', 'resetSessionHistoryPaging', 'emptyChatStreamKeepingStrip',
    'markVisibleSessionStreamLoadState', 'beginMessageReplay', 'rebuildToc', 'updateSessionTitle',
    'updateHistorySentinelVisibility', 'bindExistingLogInteractions', 'scheduleTocActiveUpdate',
    'scheduleContextTokensAfterPaint', 'logOpenSessionTiming']) c[name] = () => {};
  c.elapsedSince = () => 0;
  c.prepareWorkspaceImageLayout = async () => { order.push('images'); assert(stream.hidden); };
  c.reduceAndRenderMessageEvent = ctx => {
    c.followStreamProcessScroll(ctx, 's', 'row');
    assert.equal(vm.runInContext('smoothFollowController.isFollowing(chatContainer)', c), false,
      'history replay cannot start the live row follower');
  };
  c.finalizeExistingLogLayout = () => {
    order.push('layout');
    c.chatContainer.scrollHeight = 1600;
    c.requestAnimationFrame(() => { c.chatContainer.scrollHeight = 1800; });
  };
  vm.runInContext(between(source('session-management'), 'async function loadSessionMessages(', 'function chatStreamHasConversationContent('), c);
  let done = false;
  const loaded = c.loadSessionMessages('s', 'bottom').then(ok => { done = true; return ok; });
  for (let i = 0; i < 50 && !done; i++) { await Promise.resolve(); rt.frame(); }
  assert(done, 'instant history loading completes without waiting for an animation');
  assert.equal(await loaded, true);
  assert.deepEqual(order, ['images', 'layout']);
  assert.equal(c.chatContainer.scrollTop, 1700);
  assert(c.chatContainer.writes.every(mode => mode === 'auto'));
  assert.equal(c.replayingMessages, false);
  assert.equal(rt.frames.size, 0);
}
async function report() {
  const t = runtime(); loadTextHelpers(t.context);
  const newlineResult = flushText(t.context, scroller(), 'A\nB');
  const f = switchFixture();
  const a = f.context.switchSession('A'), b = f.context.switchSession('B');
  f.gates.B(); await b; f.gates.A(); await a;
  const q = switchFixture(), c = q.context;
  c.sessionStore.get = () => ({ last_activity_at: '2020-01-01' });
  Object.assign(c, { getSavedScrollPosition: () => 120,
    setScrollTopImmediate: (p, y) => { p.scrollTop = y; }, refreshLiveAutoFollowPins() {}, scheduleTocActiveUpdate() {} });
  vm.runInContext(between(scrolling, 'function restoreCachedSessionScrollPosition(', 'function markVisibleSessionStreamLoadState('), c);
  vm.runInContext('smoothFollowController.request(chatContainer, {channel: "text"});', c);
  await c.switchSession('B'); q.frame(); q.frame();

  let scans = 0, measurements = 0;
  const measure = runtime();
  const rows = Array.from({ length: 100 }, () => ({ getBoundingClientRect() { measurements++; return { height: 20 }; } }));
  const trace = { querySelector: () => ({}), querySelectorAll() { scans++; return rows; } };
  Object.assign(measure.context, { p1: port(), p2: port(), trace });
  vm.runInContext('smoothFollowController.request(p1, {traceHeightSource: trace}); smoothFollowController.request(p2, {traceHeightSource: trace});', measure.context);
  for (let i = 0; i < 120; i++) measure.frame();
  const textSc = scroller();
  for (let i = 0; i < 120; i++) flushText(t.context, textSc, 'x');
  return {
    ref: ref || 'working-tree', environment: 'Node VM with simulated DOM; operation counts, not browser timings',
    newlineResult, staleRestores: f.effects.filter(e => e.restored !== e.current).length,
    cachedScrollAfterFrames: c.chatContainer.scrollTop,
    sharedTrace: { frames: 120, rows: 100, ports: 2, scans, rowMeasurements: measurements },
    textUpdates: { characters: 120, replacements: textSc.writes, appends: textSc.appends },
  };
}
async function main() {
  const result = await report();
  if (process.argv.includes('--report')) { console.log(JSON.stringify(result, null, 2)); return; }
  await testUnreadNavigation();
  await testUnreadHistoryLoadLayout();
  assert.equal(result.newlineResult, 'A\nB');
  assert.equal(result.staleRestores, 0);
  assert.equal(result.cachedScrollAfterFrames, 120);
  assert.equal(result.sharedTrace.rowMeasurements, 12000);
  assert.equal(result.textUpdates.replacements, 1);
  const switchState = switchFixture();
  switchState.context.sessionStore.get = () => ({ last_activity_at: '2020-01-01' });
  switchState.context.replayingMessages = true;
  await switchState.context.switchSession('B');
  assert.equal(switchState.context.messageLoadEpoch, 1, 'cache restore invalidates old history requests');
  assert.equal(switchState.context.replayingMessages, false);
  const sealed = runtime({
    currentSessionId: 's', updateProcessBrief() {}, refreshProcessAggregateStats() {},
    refreshLiveProcessAggregateStats: () => false, stopLiveProcessAggregateStats() {},
    resetKeyContextStreamFilter() {}, finalizeProgressStreamChunks() {},
  });
  sealed.context.body = port();
  sealed.context.ctx = { currentProcessGroup: { isConnected: true, dataset: {},
    classList: { remove() {} }, querySelector: () => sealed.context.body } };
  vm.runInContext(between(rendering, 'function sealProcessGroup(', 'function getProcessBody('), sealed.context);
  vm.runInContext('smoothFollowController.request(body); sealProcessGroup(ctx);', sealed.context);
  assert.equal(sealed.frames.size, 0, 'sealed processes must not leave a perpetual animation callback');
  const follow = runtime({ currentSessionId: 's', liveAutoFollow: true, streamChatNearBottom: true,
    streamProcNearBottom: true, streamScrollFollowRaf: 0, isSubagentStreamCtx: () => false,
    shouldGateScrollByRunSession: () => false, refreshFeedChunksInCtx() {}, refreshLiveAutoFollowPins() {} });
  Object.assign(follow.context, { chatContainer: port(), processBody: port(),
    getProcessBodyElForCurrentRun: () => follow.context.processBody });
  vm.runInContext(between(scrolling, 'function followStreamProcessScroll(', 'function finishStreamScrollIfFollow('), follow.context);
  follow.context.followStreamProcessScroll({}, 's', 'text');
  follow.context.processBody.listeners.wheel({ deltaY: -8 });
  assert.equal(vm.runInContext('smoothFollowController.isFollowing(chatContainer)', follow.context), false);
  assert.equal(vm.runInContext('smoothFollowController.isFollowing(processBody)', follow.context), false);
  const visibleStream = {};
  follow.context.getVisibleChatStream = () => visibleStream;
  follow.context.background = { stream: {}, currentProcessGroup: { isConnected: true,
    querySelector: () => follow.context.processBody } };
  vm.runInContext(between(scrolling, 'function cancelSmoothStreamFollowForFinal(', 'function cancelSmoothStreamFollowForHistoryLoad('), follow.context);
  vm.runInContext('smoothFollowController.request(chatContainer); cancelSmoothStreamFollowForFinal(background);', follow.context);
  assert.equal(vm.runInContext('smoothFollowController.isFollowing(chatContainer)', follow.context), true,
    'background final must not cancel visible chat follow');
  const rt = runtime(); loadTextHelpers(rt.context);
  for (const smooth of [true, false]) for (const part of ['Response', 'Reasoning']) {
    const sc = scroller();
    for (const piece of ['  A', '\n', '\n', '  B', '😀']) flushText(rt.context, sc, piece, part, smooth);
    assert.equal(sc.textContent, '  A\n\n  B😀');
    const longSc = scroller();
    const text = Array.from({ length: 100 }, (_, i) => `line ${i}`).join('\n');
    flushText(rt.context, longSc, text, part, smooth);
    flushText(rt.context, longSc, '\nlast', part, smooth);
    assert.equal(longSc.textContent, rt.context.truncateLogTextForUi(text + '\nlast'));
  }
  // A reconnect snapshot replaces both visible and accumulated text.
  const recovered = scroller();
  flushText(rt.context, recovered, 'stale');
  rt.context.writeLlmStreamText(recovered, 'snapshot\n', 'response');
  flushText(rt.context, recovered, 'next');
  assert.equal(recovered.textContent, 'snapshot\nnext');
  // Committed content wins even if an older reveal buffer is still pending.
  const committed = scroller();
  flushText(rt.context, committed, 'partial');
  const row = { querySelector: sel => sel === '.feed-chunk-scroller' ? committed : null,
    removeAttribute() {}, setAttribute() {}, closest: () => null };
  Object.assign(rt.context, { splitThinkTagsForUi: text => ({ content: text }),
    findExistingLlmFeedRow: () => row, removeDuplicateLlmFeedRows() {}, scrollContentAreaIfFollow() {} });
  vm.runInContext(between(scrolling, 'function resetLlmState(', 'function showCopyFeedback('), rt.context);
  vm.runInContext(between(rendering, 'function upsertLlmFeedRow(', 'function findExistingLlmFeedRow('), rt.context);
  rt.context.upsertLlmFeedRow({ llm: { llmStreamResponseScroller: committed, llmPendingResponseDelta: ' obsolete' } },
    'canonical\nanswer', 'llm-response', 's', 1);
  assert.equal(committed.textContent, 'canonical\nanswer');
  console.log('frontend session and stream runtime checks passed');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
