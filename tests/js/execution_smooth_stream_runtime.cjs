const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.resolve(__dirname, '../..');
const source = name => fs.readFileSync(path.join(root, 'frontend/src/app/modules', name + '.js'), 'utf8');
const rendering = source('message-rendering'), scrolling = source('session-scroll-history'), sse = source('sse-handling');
function fn(text, name) {
  const match = text.match(new RegExp('^(?:async )?function ' + name + '\\([^]*?^}', 'm'));
  assert(match, `missing ${name}`);
  return match[0];
}
function classes(...initial) {
  const values = new Set(initial);
  return {contains: x => values.has(x), remove: x => values.delete(x),
    toggle(x, on) { if (on) values.add(x); else values.delete(x); }};
}
function runtime({enabled = true, reduced = false} = {}) {
  const rows = [], frames = new Map(); let now = 0, next = 1, follows = 0;
  const group = {isConnected: true, dataset: {processGroupId: 'turn:1'}};
  const body = {querySelectorAll: () => rows, closest: () => group};
  group.querySelector = () => body;
  const ctx = {stream: {querySelectorAll: () => rows}, currentProcessGroup: group,
    llm: {}, runId: 'run', reactGeneration: 0, lastRuntimeSeq: 0};
  const c = vm.createContext({console, TextDecoder, Date, Map, Set,
    window: {__MYAGENT_FEATURES__: {smoothStream: enabled}, matchMedia: () => ({matches: reduced})},
    performance: {now: () => now}, requestAnimationFrame(cb) {const id = next++; frames.set(id, cb); return id;},
    cancelAnimationFrame: id => frames.delete(id), setTimeout: () => 1, clearTimeout() {},
    currentSessionId: 's', replayingMessages: false, executionRecordsBySession: new Map(),
    reactGenerationForContext: target => target.reactGeneration || 0, selectExecutionProcessGroup() {},
    removeTemporaryStatus() {}, discardPendingToolRowRender() {}, refreshFeedChunkOverflow() {},
    scheduleFeedChunkOverflowRefresh() {}, refreshAggregateStatsSmart() {}, autoCollapseLlmReasoningRow() {},
    unregisterProcessAggregateRow() {}, registerProcessAggregateRow() {},
    scrollContentAreaIfFollow() {follows++;}, followStreamProcessScroll() {follows++;},
    getFeedItemText: row => row.sc.textContent,
    queryFeedChunksInCtx: () => rows.map(row => row.chunk).filter(ch => ch.classList.contains('is-streaming')),
    createProcessFeedRow(_ctx, type, text) {
      const row = {dataset: {}, isConnected: true, classList: classes('feed-item', 'feed--llm'),
        hasAttribute: () => false, getAttribute(name) {return this.dataset[name.replace(/^data-/, '').replace(/-([a-z])/g, (_, x) => x.toUpperCase())];},
        removeAttribute() {}, remove() {this.isConnected = false; this.sc.isConnected = false;},
        closest: selector => selector === '.process-aggregate' ? group : row};
      let node = null;
      const sc = {isConnected: true, replacements: 0, closest: () => row,
        get firstChild() {return node;}, get lastChild() {return node;},
        get textContent() {return node ? node.data : '';},
        set textContent(value) {this.replacements++; node = {nodeType: 3, data: value, appendData(delta) {this.data += delta;}};}};
      sc.textContent = text;
      const chunk = {classList: classes('feed-chunk'), closest: () => row};
      row.sc = sc; row.chunk = chunk;
      row.querySelector = selector => selector === '.feed-chunk-scroller' ? sc : chunk;
      rows.push(row); return sc;
    },
    SSE_IDLE_TIMEOUT_MS: 1000, readSseChunkWithIdleTimeout: reader => reader.read(),
    sessionStore: {shouldAcceptSseEvent: () => true}, consumeExtensionControlEvent: () => false,
    streamHistoryRecoveryBySession: new Set(), applySessionEvent: () => ({}),
    scheduleFinalVisibleAfterRunIfEnabled() {},
  });
  vm.runInContext(source('smooth-stream'), c);
  vm.runInContext(['trimSurroundingBlankLines', 'updateExecutionRecord', 'renderExecutionRecord', 'renderExecutionEvent']
    .map(name => fn(rendering, name)).join('\n'), c);
  // Load the actual text queue and its lifecycle functions, including new helpers.
  vm.runInContext(scrolling.slice(scrolling.indexOf('/** Keep the full source'), scrolling.indexOf('function showCopyFeedback')), c);
  vm.runInContext(['finalizeLlmStreamChunks', 'discardLlmStreamChunks'].map(name => fn(scrolling, name)).join('\n'), c);
  vm.runInContext(['shouldApplySseSeqFilter', 'sseSequenceScope', 'shouldSkipRecoveredEphemeralEvent', 'consumeAgentSseResponseInner']
    .map(name => fn(sse, name)).join('\n'), c);
  return {c, ctx, rows, frames, follows: () => follows,
    row: id => rows.find(row => row.dataset.executionId === id),
    frame() {now += 16.67; const batch = [...frames.values()]; frames.clear(); batch.forEach(cb => cb(now));},
    drain() {let count = 0; while (frames.size && count++ < 1000) this.frame(); assert(count < 1000);},
  };
}
function delta(kind, id, text, seq) {
  return {type: 'llm_' + kind + '_delta', execution_id: id, delta: text, ephemeral: true,
    session_id: 's', run_id: 'run', react_iter: 1, execution_runtime_seq: seq};
}
function update(kind, id, text, seq) {
  return {protocol: 'runtime_v2', seq, session_id: 's', ui_event: {type: 'execution_update', ephemeral: true,
    update: {execution_id: id, kind, run_id: 'run', react_iter: 1, status: 'generating', text_delta: text}}};
}
async function send(rt, events) {
  const bytes = new TextEncoder().encode(events.map(event => 'data: ' + JSON.stringify(event) + '\n\n').join(''));
  let offset = 0;
  await rt.c.consumeAgentSseResponseInner({ok: true, headers: {get: () => 'text/event-stream'},
    body: {getReader: () => ({read: async () => {
      if (offset >= bytes.length) return {done: true};
      const value = bytes.slice(offset, offset += 13); return {done: false, value};
    }})}}, rt.ctx, 's', 0);
}
async function main() {
  for (const kind of ['reasoning', 'response']) for (const makeEvent of [delta, update]) {
    const rt = runtime(), text = '正文😀'.repeat(20), event = makeEvent(kind, 'live', text, 1);
    await send(rt, [event, event]);
    assert.equal(rt.row('live').sc.textContent, '', 'live first chunk waits for a reveal frame');
    assert.equal(rt.frames.size, 1, 'duplicate deliveries share one reveal loop');
    rt.frame();
    const first = rt.row('live').sc.textContent;
    assert(first.length > 0 && first.length < text.length, 'first frame reveals only part of the chunk');
    assert(text.startsWith(first));
    assert(!/[\uD800-\uDBFF]$/.test(first), 'a reveal never splits an emoji');
    const node = rt.row('live').sc.firstChild, writes = rt.row('live').sc.replacements;
    await send(rt, [makeEvent(kind, 'live', '追加', 2)]);
    assert.equal(rt.row('live').sc.textContent, first, 'next chunk joins the remaining queue');
    rt.drain();
    assert.equal(rt.row('live').sc.textContent, text + '追加');
    assert.strictEqual(rt.row('live').sc.firstChild, node, 'incremental appends retain the text node');
    assert.equal(rt.row('live').sc.replacements, writes);
    assert.equal(rt.c.executionRecordsBySession.get('s').get('live').content, text + '追加');
    assert(rt.follows() > 1, 'scroll follow continues on reveal frames');
  }
  for (const options of [{enabled: false}, {reduced: true}]) {
    const rt = runtime(options); await send(rt, [delta('reasoning', 'plain', 'x'.repeat(80), 1)]);
    assert.equal(rt.row('plain').sc.textContent.length, 80); assert.equal(rt.frames.size, 0);
  }
  const rt = runtime();
  await send(rt, [delta('reasoning', 'a', 'a'.repeat(80), 1), delta('response', 'b', 'b'.repeat(80), 2)]);
  rt.frame(); assert.equal(rt.row('a').sc.textContent.length, 10); assert.equal(rt.row('b').sc.textContent.length, 10);
  await send(rt, [{type: 'llm_reasoning', execution_id: 'a', content: 'authoritative', execution_runtime_seq: 3}]);
  assert.equal(rt.row('a').sc.textContent, 'authoritative'); rt.drain();
  assert.equal(rt.row('a').sc.textContent, 'authoritative', 'completion cannot be overwritten by an old queue');
  assert.equal(rt.row('b').sc.textContent, 'b'.repeat(80), 'finishing one row preserves another queue');

  const snapshot = runtime(); await send(snapshot, [delta('response', 'snap', 'x'.repeat(80), 1)]);
  snapshot.frame(); await send(snapshot, [{...delta('response', 'snap', 'snapshot', 2), replayed_snapshot: true}]);
  assert.equal(snapshot.row('snap').sc.textContent, 'snapshot', 'reconnect snapshots replace accumulated deltas');
  snapshot.drain(); assert.equal(snapshot.row('snap').sc.textContent, 'snapshot');

  const overlap = runtime();
  await send(overlap, [delta('reasoning', 'both', 'c'.repeat(80), 1), update('reasoning', 'both', 'c'.repeat(80), 1)]);
  overlap.drain(); assert.equal(overlap.row('both').sc.textContent, 'c'.repeat(80), 'journal and live bridge deliveries dedupe');
  for (const status of ['interrupted', 'failed']) {
    const stopped = runtime(); await send(stopped, [delta('response', 'stop', 'partial'.repeat(20), 1)]); stopped.frame();
    await send(stopped, [{type: 'execution_update', runtime_seq: 2,
      update: {execution_id: 'stop', kind: 'response', status, content: 'received'}}]);
    stopped.drain();
    assert(stopped.row('stop').sc.textContent.startsWith('received\n['));
    assert.equal(stopped.frames.size, 0);
  }

  const recovered = runtime();
  recovered.c.renderExecutionRecord(recovered.ctx, recovered.c.updateExecutionRecord('s', {
    execution_id: 'recovered', kind: 'reasoning', status: 'generating', content: 'saved', last_runtime_seq: 1,
  }), 's');
  assert.equal(recovered.row('recovered').sc.textContent, 'saved');
  await send(recovered, [delta('reasoning', 'recovered', 'x'.repeat(80), 2)]);
  assert.equal(recovered.row('recovered').sc.textContent, 'saved'); recovered.frame();
  assert.equal(recovered.row('recovered').sc.textContent, 'saved' + 'x'.repeat(10));
  const sameSeq = delta('reasoning', 'recovered', 'saved' + 'x'.repeat(80), 2);
  await send(recovered, [{...sameSeq, replayed_snapshot: true}]);
  assert.equal(recovered.row('recovered').sc.textContent, 'saved' + 'x'.repeat(10), 'already consumed snapshot stays filtered');
  recovered.c.renderExecutionRecord(recovered.ctx, recovered.c.executionRecordsBySession.get('s').get('recovered'), 's', {snapshot: true});
  assert.equal(recovered.row('recovered').sc.textContent, sameSeq.delta);
  assert.equal(recovered.frames.size, 0, 'same-sequence snapshot drains an existing reveal');

  for (const boundary of ['finalizeLlmStreamChunks', 'resetLlmState', 'discardLlmStreamChunks']) {
    const ended = runtime(); await send(ended, [delta('response', 'end', 'y'.repeat(80), 1)]); ended.frame();
    ended.c[boundary](ended.ctx, {});
    assert.equal(ended.row('end').sc.textContent, 'y'.repeat(80), boundary + ' keeps received durable text');
    assert.equal(ended.ctx.llm.llmDeltaFlushRaf, 0, boundary + ' stops the reveal loop');
    assert.equal(ended.ctx.llm.llmExecutionReveals.size, 0);
    ended.drain();
    assert.equal(ended.row('end').sc.textContent, 'y'.repeat(80));
  }
  const history = runtime(); history.c.replayingMessages = true;
  await send(history, [delta('reasoning', 'old', 'history', 1)]);
  assert.equal(history.row('old').sc.textContent, 'history'); assert.equal(history.frames.size, 0);
  const detached = runtime(); await send(detached, [delta('response', 'gone', 'z'.repeat(80), 1)]);
  detached.row('gone').sc.isConnected = false; detached.drain();
  assert.equal(detached.row('gone').sc.textContent, '');
  console.log('execution smooth stream SSE checks passed');
}
main().catch(error => {console.error(error); process.exitCode = 1;});
