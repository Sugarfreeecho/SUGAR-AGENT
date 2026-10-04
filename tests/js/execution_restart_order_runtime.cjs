const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.resolve(__dirname, '../..');
const source = name => fs.readFileSync(path.join(root, 'frontend/src/app', name), 'utf8');
const rendering = source('modules/message-rendering.js');
const dispatch = source('modules/event-dispatch.js');
const sse = source('modules/sse-handling.js');
const messages = source('state/message-renderers.js');
function fn(text, name) {
  const match = text.match(new RegExp('^(?:async )?function ' + name + '\\([^]*?^}', 'm'));
  assert(match, `missing ${name}`);
  return match[0];
}

// The production session resumed iteration 1 after iteration 172 in this turn.
const oldRun = '6f161f3d-5ae3-44ba-b563-1c342dd8f53f';
const newRun = 'workflow-runner-8e278a9df7ae41149e9d1644c88f7a8b';
const groupId = 'turn:1104';
function runtime() {
  let writes = 0, follows = 0, resets = 0;
  const group = {dataset: {processGroupId: groupId}, isConnected: true,
    classList: {contains: name => name === 'process-aggregate'}};
  function row(label, iter, generation, runId, owner = group) {
    const item = {dataset: {label, logType: 'llm-reasoning', reactIter: String(iter),
      reactGeneration: String(generation), runId}, classList: {contains: () => false, toggle() {}},
      matches: () => false,
      getAttribute(name) { return this.dataset[name.replace(/^data-/, '').replace(/-([a-z])/g, (_, c) => c.toUpperCase())]; },
      setAttribute(name, value) { this.dataset[name.replace(/^data-/, '').replace(/-([a-z])/g, (_, c) => c.toUpperCase())] = value; },
      removeAttribute() {}, closest: () => owner};
    let text = '';
    const scroller = {isConnected: true, closest: () => item,
      get textContent() { return text; }, set textContent(value) { writes++; text = value; }};
    const chunk = {classList: {toggle() {}}};
    item.querySelector = selector => selector === '.feed-chunk-scroller' ? scroller : chunk;
    item.scroller = scroller;
    return item;
  }
  const body = {children: [row('old', 171, 0, oldRun)], _reactOrderTailKey: [0, 171, 0],
    get lastElementChild() { return this.children.at(-1); },
    appendChild(item) { this.children.push(item); },
    insertBefore(item, before) { this.children.splice(this.children.indexOf(before), 0, item); },
    querySelectorAll() { return this.children; }, closest: () => group};
  group.body = body;
  group.querySelectorAll = () => body.children;
  const groups = [group];
  const stream = {querySelectorAll(selector) {
    if (selector === '.process-aggregate') return groups;
    const rows = groups.flatMap(owner => owner.body.children);
    return selector === '[data-execution-id]' ? rows.filter(item => item.dataset.executionId) : rows;
  }};
  const ctx = {stream, currentProcessGroup: group, processGroupId: groupId, runId: oldRun, reactGeneration: 0,
    llm: {llmDeltaLastSeq: null, llmStreamReasoningIter: null, llmStreamReasoningScroller: null}};
  const c = vm.createContext({console, Math, Number, String, Map, Set, Object, Array, JSON, Date, Promise, TextDecoder,
    replayingMessages: false, currentSessionId: 's', document: {dispatchEvent() {}}, CustomEvent: function () {},
    resetLlmState(target) { resets++; target.llm = {llmDeltaLastSeq: null, llmStreamReasoningIter: null, llmStreamReasoningScroller: null}; },
    renderPluginExtensionEvent: () => false, applyMessageEvent() {}, uiEventReactIter: event => event.react_iter,
    removeTemporaryStatus() {}, discardPendingToolRowRender() {}, truncateLogTextForUi: text => text,
    refreshFeedChunkOverflow() {}, refreshAggregateStatsSmart() {}, unregisterProcessAggregateRow() {},
    registerProcessAggregateRow() {}, autoCollapseLlmReasoningRow() {}, findToolCallRow: () => null,
    scrollContentAreaIfFollow() { follows++; }, getProcessBody: target => target.currentProcessGroup.body,
    bumpAggregateMaxReactIter() {}, hasSeenStreamDelta: () => false, flushLlmDeltaText() {},
    findExistingLlmFeedRow: () => null, scheduleLlmDeltaFlush() {},
    createProcessFeedRow(target, type, text, opts) {
      const item = row('new', opts.reactIter, opts.reactGeneration ?? target.reactGeneration,
        opts.runId || target.runId, target.currentProcessGroup);
      c.insertReactOrderedFeedRow(target.currentProcessGroup.body, item, type, opts.reactIter,
        opts.reactGeneration ?? target.reactGeneration);
      item.scroller.textContent = text;
      return item.scroller;
    },
    upsertLlmFeedRow(target, text, type, sid, iter) { return c.createProcessFeedRow(target, type, text, {reactIter: iter}); },
    SSE_IDLE_TIMEOUT_MS: 1000, readSseChunkWithIdleTimeout: reader => reader.read(),
    sessionStore: {shouldAcceptSseEvent: () => true}, consumeExtensionControlEvent: () => false,
    applySessionEvent: event => event.type === 'run_started' ? {handled: true, runStateChanged: true} : {},
    syncSessionListIndicatorClasses() {}, scheduleFinalVisibleAfterRunIfEnabled() {},
  });
  vm.runInContext(['seedRenderContextRunGenerations', 'syncRenderContextRunScope', 'renderEvent']
    .map(name => fn(dispatch, name)).join('\n'), c);
  vm.runInContext(['reactGenerationForContext', 'reactFeedPhase', 'appendProcessRowBeforePendingAppendSteer',
    'appendMonotonicProcessRow', 'insertReactOrderedFeedRow', 'appendLlmStreamDelta']
    .map(name => fn(rendering, name)).join('\n'), c);
  const start = rendering.indexOf('var executionRecordsBySession');
  vm.runInContext(rendering.slice(start, rendering.indexOf('function ensureProcessGroup', start)), c);
  vm.runInContext(fn(messages, 'renderMessageRecord'), c);
  vm.runInContext(['shouldApplySseSeqFilter', 'sseSequenceScope', 'consumeAgentSseResponseInner',
    'restoreReactGenerationFromProcessGroup'].map(name => fn(sse, name)).join('\n'), c);
  return {c, ctx, group, groups, body, counters: () => ({writes, follows, resets}),
    order: () => body.children.map(item => [item.dataset.runId, Number(item.dataset.reactIter), Number(item.dataset.reactGeneration)])};
}
const record = {execution_id: newRun + ':reasoning:1:0', process_group_id: groupId,
  run_id: newRun, kind: 'reasoning', status: 'generating', react_iter: 1, content: '恢复后的正文',
  first_runtime_seq: 27194, last_runtime_seq: 27194};
async function send(x, frames) {
  const bytes = new TextEncoder().encode(frames.map(frame => 'data: ' + JSON.stringify({session_id: 's', ephemeral: true, ...frame}) + '\n\n').join(''));
  let read = false;
  await x.c.consumeAgentSseResponseInner({ok: true, headers: {get: () => 'text/event-stream'},
    body: {getReader: () => ({read: async () => read ? {done: true} : (read = true, {done: false, value: bytes})})}}, x.ctx, 's', 1000);
}
function appended(x) {
  assert.deepEqual(x.order(), [[oldRun, 171, 0], [newRun, 1, 1]]);
  assert.equal(x.ctx.runId, newRun);
}
async function main() {
  // A direct history record must apply the same run boundary as renderEvent.
  const history = runtime();
  history.c.renderMessageRecord(history.ctx, {event: {...record, type: 'llm_reasoning', execution_runtime_seq: 27194}}, 's');
  appended(history);

  for (const knownAtAttach of [false, true]) {
    for (const journal of [false, true]) {
      const x = runtime();
      if (knownAtAttach) x.ctx.runId = newRun;
      x.c.restoreReactGenerationFromProcessGroup(x.ctx, x.group);
      const token = journal ? {type: 'execution_update', runtime_seq: 27194, run_id: newRun, update: record}
        : {type: 'llm_reasoning_delta', run_id: newRun, react_iter: 1, stream_seq: 1, delta: '恢复后的正文'};
      await send(x, [{type: 'run_started', run_id: newRun}, token]);
      appended(x);
    }
  }
  // The first business event also establishes the run when lifecycle replay is absent.
  const noStart = runtime();
  await send(noStart, [{type: 'execution_update', runtime_seq: 27194, run_id: newRun,
    update: {...record, run_id: undefined}}]);
  appended(noStart);

  const x = runtime();
  await send(x, [{type: 'execution_update', runtime_seq: 27194, run_id: newRun, update: record}]);
  const beforeDuplicate = x.counters();
  await send(x, [{type: 'llm_reasoning_delta', run_id: newRun, execution_id: record.execution_id,
    execution_runtime_seq: 27194, process_group_id: groupId, react_iter: 1, delta: '重复的正文'}]);
  assert.deepEqual(x.counters(), beforeDuplicate, 'duplicate bus/replay frames cannot rewrite text, reset streams or follow');
  const existing = x.body.children.at(-1);
  const oldPartial = {execution_id: oldRun + ':reasoning:172:0', process_group_id: groupId,
    run_id: oldRun, kind: 'reasoning', status: 'generating', react_iter: 172,
    first_runtime_seq: 27130, last_runtime_seq: 27188, content: '重启前的部分思考'};
  const beforeOld = x.counters();
  x.c.renderExecutionRecord(x.ctx, oldPartial, 's');
  assert.deepEqual(x.order(), [[oldRun, 171, 0], [oldRun, 172, 0], [newRun, 1, 1]]);
  assert.equal(x.ctx.runId, newRun);
  assert.equal(x.ctx.reactGeneration, 1);
  assert.equal(x.counters().follows, beforeOld.follows, 'older draft backfill cannot steal live follow');
  x.c.renderExecutionRecord(x.ctx, {...record, last_runtime_seq: 27195, content: '恢复后的正文继续'}, 's');
  assert.strictEqual(x.body.children.at(-1), existing, 'new tokens update the same tail row');
  assert.equal(existing.dataset.reactGeneration, '1');
  assert.equal(existing.scroller.textContent, '恢复后的正文继续');

  // Snapshot records may arrive after newer UI history: seed by durable birth sequence.
  const fresh = runtime();
  delete fresh.ctx.runId;
  fresh.c.seedRenderContextRunGenerations(fresh.ctx,
    [{run_id: newRun, runtime_seq: 27410}], [oldPartial, record]);
  fresh.c.renderExecutionRecord(fresh.ctx, record, 's');
  fresh.c.renderExecutionRecord(fresh.ctx, oldPartial, 's');
  assert.deepEqual(fresh.order(), [[oldRun, 171, 0], [oldRun, 172, 0], [newRun, 1, 1]]);
  assert.equal(fresh.ctx.runId, newRun);
  assert.equal(fresh.c.restoreReactGenerationFromProcessGroup(fresh.ctx, fresh.group), 1);
  assert.equal(fresh.c.restoreReactGenerationFromProcessGroup(fresh.ctx, fresh.group), 1, 'reattachment cannot add another generation to the same run');

  const activeGroup = {dataset: {processGroupId: 'after-final:28502'}, body: {children: []},
    classList: {contains: name => name === 'process-aggregate'}};
  x.groups.push(activeGroup);
  x.ctx.currentProcessGroup = activeGroup;
  x.ctx.processGroupId = activeGroup.dataset.processGroupId;
  x.c.renderExecutionRecord(x.ctx, {...oldPartial, last_runtime_seq: 27189, content: '旧记录修正'}, 's');
  assert.strictEqual(x.ctx.currentProcessGroup, activeGroup, 'historical updates cannot change the active process group');
  assert.equal(x.ctx.processGroupId, activeGroup.dataset.processGroupId);

  // Interrupt steer may also advance a generation without changing run_id.
  const steer = runtime();
  steer.ctx.reactGeneration = 1;
  steer.ctx.reactGenerationsByRunId = new Map([[oldRun, 0]]);
  steer.c.renderExecutionRecord(steer.ctx, {...oldPartial, execution_id: 'post-steer', react_iter: 1}, 's');
  assert.equal(steer.body.children.at(-1).dataset.reactGeneration, '1');
  const snapshotSteer = runtime();
  delete snapshotSteer.ctx.runId;
  snapshotSteer.c.seedRenderContextRunGenerations(snapshotSteer.ctx,
    [{run_id: oldRun, type: 'user_steer', steer_mode: 'interrupt', runtime_seq: 27190}],
    [oldPartial, {...record, run_id: oldRun, execution_id: 'same-run-after-steer'}]);
  snapshotSteer.c.renderExecutionRecord(snapshotSteer.ctx, {...record, run_id: oldRun, execution_id: 'same-run-after-steer'}, 's');
  snapshotSteer.c.renderExecutionRecord(snapshotSteer.ctx, oldPartial, 's');
  assert.deepEqual(snapshotSteer.body.children.map(item => Number(item.dataset.reactGeneration)), [0, 0, 1]);
  assert.equal(snapshotSteer.ctx.reactGeneration, 1);
  assert.equal(snapshotSteer.c.restoreReactGenerationFromProcessGroup(snapshotSteer.ctx, snapshotSteer.group), 1);
  process.stdout.write('execution restart order runtime checks passed\n');
}
main().catch(error => {console.error(error); process.exitCode = 1;});
