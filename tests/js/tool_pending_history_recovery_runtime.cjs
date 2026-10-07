const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.resolve(__dirname, '../../frontend/src/app/modules/sse-handling.js'), 'utf8');
const renderingSource = fs.readFileSync(path.resolve(__dirname, '../../frontend/src/app/modules/message-rendering.js'), 'utf8');
function fn(name) {
  const match = source.match(new RegExp('^(?:async )?function ' + name + '\\([^]*?^}', 'm'));
  assert(match, `missing ${name}`);
  return match[0];
}

async function testDurableSubagentEventsKeepHistoryCursorCurrent() {
  let readCount = 0;
  let aborted = 0;
  let pendingRows = 0;
  let lifecycleFrames = 0;
  const events = [
    {type: 'tool_pending', ephemeral: true, seq: 1, seq_scope: 'event_bus',
      session_id: 's', tool: 'task', tool_call_id: 'call-task'},
    {type: 'subagent_start', seq: 11, seq_scope: 'ui_projection',
      session_id: 's', agent_id: 'child'},
    {type: 'context_tokens', seq: 12, seq_scope: 'ui_projection',
      session_id: 's', estimated: 123},
  ];
  const bytes = new TextEncoder().encode(events.map(event =>
    `data: ${JSON.stringify(event)}\n\n`).join(''));
  const ctx = {streamConsuming: true, lastBusinessEventAt: Date.now() - 40000};
  const run = {ctx, controller: {abort() { aborted += 1; }}};
  const context = vm.createContext({
    console, Date, Number, String, Promise, TextDecoder,
    SSE_IDLE_TIMEOUT_MS: 120000,
    currentSessionId: 's', streamHistoryRecoveryBySession: new Set(),
    sessionStore: {shouldAcceptSseEvent: () => true},
    readSseChunkWithIdleTimeout: reader => reader.read(),
    consumeExtensionControlEvent: () => false,
    applySessionEvent: event => ({contextStateChanged: event.type === 'context_tokens'}),
    applyContextTokenLabelForCurrentSession() {},
    appendToolPendingRow() { pendingRows += 1; },
    noteSubagentLifecycleFrame() { lifecycleFrames += 1; },
    scheduleFinalVisibleAfterRunIfEnabled() {},
    reconcileRunStateFromServer: async () => {},
    getSessionRunState: () => run,
    getUiEventCount: async () => 12,
    markRunAbortReason() {},
  });
  vm.runInContext([
    fn('shouldApplySseSeqFilter'), fn('sseSequenceScope'),
    fn('consumeAgentSseResponseInner'), fn('checkSessionStreamProgress'),
  ].join('\n'), context);
  const response = {ok: true, headers: {get: () => 'text/event-stream'},
    body: {getReader: () => ({read: async () => readCount++
      ? {done: true} : {done: false, value: bytes}})}};
  await context.consumeAgentSseResponseInner(response, ctx, 's', 10);
  assert.equal(pendingRows, 1);
  assert.equal(lifecycleFrames, 1);
  assert.equal(ctx.streamEventIndex, 12,
    'skipped durable events still consume positions in the UI history');
  await context.checkSessionStreamProgress('s', ctx);
  assert.equal(aborted, 0, 'a healthy long-running task must not force a history rebuild');
}

async function testHistoryRebuildAcceptsPendingToolReplay() {
  const accepted = new Map([['s::event_bus', 7]]);
  let replayedPending = false;
  let historyLoads = 0;
  const stream = {querySelector: () => null, querySelectorAll: () => []};
  const sessionStore = {
    getActiveRunInfo: () => null,
    shouldAcceptSseEvent(sid, seq, scope) {
      const key = `${sid}::${scope}`;
      if (seq <= (accepted.get(key) || 0)) return false;
      accepted.set(key, seq);
      return true;
    },
    resetSseSeq(sid) {
      for (const key of accepted.keys()) {
        if (key.startsWith(`${sid}::`)) accepted.delete(key);
      }
    },
  };
  const context = vm.createContext({
    console, Date, Number, String, Promise, AbortController,
    currentSessionId: 's', streamHistoryRecoveryBySession: new Set(['s']),
    sessionStore,
    getSessionRunState: () => null,
    getRunAbortReason: () => '',
    isServerStreamActive: () => true,
    requestExtensionStateConvergence() {},
    loadSessionMessages: async () => { historyLoads += 1; },
    refreshHumanInteractions() {},
    getVisibleChatStream: () => stream,
    newDomContext: () => ({stream}),
    resetLlmState() {}, initRunFinalTracking() {}, finalizeLlmStreamChunks() {},
    setSessionRunState() {}, setSendButtonState() {}, syncSessionListIndicatorClasses() {},
    getUiEventCount: async () => 11,
    fetch: async () => ({ok: true}),
    consumeAgentSseResponse: async () => {
      replayedPending = sessionStore.shouldAcceptSseEvent('s', 7, 'event_bus');
    },
    finalizeProgressStreamChunks() {},
    refreshSingleSessionRow: async () => {},
    setTimeout() {},
    reconcileRunStateFromServer: async () => {},
    scheduleActiveSessionReconnect() {},
    applyContextTokenLabelForCurrentSession() {},
  });
  const findGroup = renderingSource.match(/^function findExecutionProcessGroup\([^]*?^}/m);
  assert(findGroup, 'missing findExecutionProcessGroup');
  vm.runInContext(findGroup[0] + '\n' + fn('attachSessionEventStream'), context);
  await context.attachSessionEventStream('s', {skipInitialLoad: true});
  assert.equal(historyLoads, 1);
  assert.equal(replayedPending, true,
    'the rebuilt DOM must accept the active tool_pending snapshot');
}

Promise.resolve().then(testDurableSubagentEventsKeepHistoryCursorCurrent)
  .then(testHistoryRebuildAcceptsPendingToolReplay)
  .then(() => console.log('tool pending history recovery: passed'))
  .catch(error => { console.error(error); process.exitCode = 1; });
