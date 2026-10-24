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
  return {contains: x => values.has(x), add: x => values.add(x), remove: x => values.delete(x),
    toggle(x, on) { if (on) values.add(x); else values.delete(x); }};
}
function runtime({enabled = true, reduced = false} = {}) {
  const rows = [], frames = new Map(); let now = 0, next = 1, follows = 0;
  const group = {isConnected: true, dataset: {processGroupId: 'turn:1'}};
  const body = {querySelectorAll: () => rows, closest: () => group};
  group.querySelector = () => body;
  const ctx = {stream: {querySelectorAll: () => rows, contains: item => rows.includes(item)}, currentProcessGroup: group,
    llm: {}, runId: 'run', reactGeneration: 0, lastRuntimeSeq: 0};
  const c = vm.createContext({console, TextDecoder, Date, Map, Set,
    window: {__MYAGENT_FEATURES__: {smoothStream: enabled}, matchMedia: () => ({matches: reduced})},
    performance: {now: () => now}, requestAnimationFrame(cb) {const id = next++; frames.set(id, cb); return id;},
    cancelAnimationFrame: id => frames.delete(id), setTimeout: (fn, delay) => delay === 0 ? setTimeout(fn, 0) : 1, clearTimeout() {},
    currentSessionId: 's', replayingMessages: false, executionRecordsBySession: new Map(), executionRowsByStream: new WeakMap(),
    reactGenerationForContext: target => target.reactGeneration || 0, selectExecutionProcessGroup() {},
    removeTemporaryStatus() {}, refreshFeedChunkOverflow() {},
    scheduleFeedChunkOverflowRefresh() {}, refreshAggregateStatsSmart() {}, autoCollapseLlmReasoningRow() {},
    unregisterProcessAggregateRow() {}, registerProcessAggregateRow() {},
    findToolCallRow: (_ctx, id) => rows.find(row => row.dataset.toolCallId === id),
    getExistingProcessBody: () => body, getProcessBody: () => body,
    uiI18nRuntimeOriginal: new WeakMap(), uiLanguage: 'zh', translateUiString: text => text.replace('生成中...', 'Generating...'),
    truncateLogTextForUi: text => text,
    scrollContentAreaIfFollow() {follows++;}, followStreamProcessScroll() {follows++;},
    getFeedItemText: row => row.sc.textContent,
    queryFeedChunksInCtx: () => rows.map(row => row.chunk).filter(ch => ch.classList.contains('is-streaming')),
    createProcessFeedRow(_ctx, type, text) {
      const row = {dataset: {logType:type}, isConnected: true, parentNode:body,
        get nextElementSibling() {return rows[rows.indexOf(this) + 1] || null;},
        matches: () => false,
        classList: classes('feed-item', type === 'tool-call' ? 'feed--tool' : 'feed--llm'),
        hasAttribute: () => false, getAttribute(name) {return this.dataset[name.replace(/^data-/, '').replace(/-([a-z])/g, (_, x) => x.toUpperCase())];},
        setAttribute(name, value) {this.dataset[name.replace(/^data-/, '').replace(/-([a-z])/g, (_, x) => x.toUpperCase())] = value;},
        removeAttribute(name) {delete this.dataset[name.replace(/^data-/, '').replace(/-([a-z])/g, (_, x) => x.toUpperCase())];},
        remove() {this.isConnected = false; this.sc.isConnected = false;},
        closest: selector => selector === '.process-aggregate' ? group : row};
      let node = null;
      const sc = {isConnected: true, replacements: 0, setAttribute() {},
        closest: selector => selector === '.feed-chunk' ? chunk : row,
        get firstChild() {return node;}, get lastChild() {return node;},
        get textContent() {return node ? node.data : '';},
        set textContent(value) {this.replacements++; node = {nodeType: 3, data: value,
          appendData(delta) {this.data += delta;},
          replaceData(start, count, text) {this.data = this.data.slice(0, start) + text + this.data.slice(start + count);}};}};
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
  vm.runInContext(['setUiRuntimeText', 'getUiRuntimeText'].map(name => fn(source('i18n'), name)).join('\n'), c);
  vm.runInContext(['trimSurroundingBlankLines', 'executionRowIndexForStream', 'findIndexedExecutionRow',
    'updateExecutionRecord', 'renderExecutionRecord', 'renderExecutionEvent']
    .map(name => fn(rendering, name)).join('\n'), c);
  vm.runInContext(['formatToolDraftLine', 'writeToolCallLlmText', 'formatToolPendingLine',
    'ensureToolStreamRenderState', 'rememberToolStreamRow', 'discardPendingToolRowRender',
    'scheduleToolRowRender', 'setToolRowText', 'removeAbortedToolDraftRows',
    'flushProgressDeltaText', 'scheduleProgressDeltaFlush', 'prepareContextProgressRows', 'ensureProgressScroller',
    'appendProgressStreamDelta', 'appendProgressLog', 'applyProgressPersistedBody',
    'appendCompressionReasoningDelta', 'finishCompressionReasoning', 'finalizeProgressStreamForType',
    'finalizeProgressStreamChunks', 'discardProgressStreamChunks'].map(name => fn(rendering, name)).join('\n'), c);
  c.appendLog = (ctx, text, type) => c.createProcessFeedRow(ctx, type, text);
  c.createCompressionReasoningScroller = ctx => c.createProcessFeedRow(ctx, 'context-summary', '');
  vm.runInContext(['resetKeyContextStreamFilter', 'extractKeyContextVisibleDelta', 'appendKeyContextStreamDelta']
    .map(name => fn(scrolling, name)).join('\n'), c);
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
function toolDelta(id, name, args, seq) {
  return {type: 'tool_call_delta', execution_id: id, id: 'call-' + id, name_delta: name,
    arguments_delta: args, execution_runtime_seq: seq, ephemeral: true, run_id: 'run', react_iter: 1};
}
function toolUpdate(id, name, args, seq) {
  return {protocol: 'runtime_v2', seq, session_id: 's', ui_event: {type: 'execution_update', ephemeral: true,
    update: {execution_id: id, tool_call_id: 'call-' + id, kind: 'tool', run_id: 'run', react_iter: 1,
      status: 'generating', name_delta: name, arguments_delta: args}}};
}
async function toolsAndProgress() {
  const named = runtime(); await send(named, [toolDelta('name', 'run_shell', '', 1)]); named.frame();
  assert(named.row('name').sc._llmToolName.length > 0 && named.row('name').sc._llmToolName.length < 9,
    'tool names also reveal progressively when they arrive before arguments');
  named.drain(); assert.equal(named.row('name').sc._llmToolName, 'run_shell');
  for (const makeEvent of [toolDelta, toolUpdate]) {
    const rt = runtime(), args = '{"content":"' + '工具😀'.repeat(30);
    await send(rt, [makeEvent('tool', 'write_', args, 1), makeEvent('tool', 'write_', args, 1)]);
    const sc = rt.row('tool').sc;
    assert.equal(sc.textContent, ''); assert.equal(rt.frames.size, 1);
    rt.frame();
    assert(sc._llmToolArgs.length > 0 && sc._llmToolArgs.length < args.length);
    assert(!/[\uD800-\uDBFF]$/.test(sc._llmToolArgs));
    const first = sc.textContent, node = sc.firstChild;
    await send(rt, [makeEvent('tool', 'file', '"}', 2)]);
    assert.equal(sc.textContent, first, 'both tool fields join their reveal queue');
    rt.drain();
    assert.equal(sc.textContent, rt.c.formatToolDraftLine('write_file', args + '"}'));
    assert.strictEqual(sc.firstChild, node, 'draft footer changes retain the text node');
    const record = rt.c.executionRecordsBySession.get('s').get('tool');
    assert.equal(record.tool, 'write_file'); assert.equal(record.arguments_raw, args + '"}');
  }
  for (const options of [{enabled: false}, {reduced: true}]) {
    const rt = runtime(options); await send(rt, [toolDelta('plain-tool', 'run_shell', 'x'.repeat(80), 1)]);
    assert.equal(rt.row('plain-tool').sc.textContent, rt.c.formatToolDraftLine('run_shell', 'x'.repeat(80)));
    assert.equal(rt.frames.size, 0);
  }
  const rt = runtime();
  await send(rt, [toolDelta('a', 'run_shell', 'x'.repeat(80), 1), toolDelta('b', 'read_file', 'y'.repeat(80), 2)]);
  rt.frame();
  await send(rt, [{type: 'tool_pending', execution_id: 'a', execution_runtime_seq: 3,
    tool: 'run_shell', tool_call_id: 'call-a', command_preview: 'run_shell(command="echo")', args: {command: 'echo'}}]);
  assert.equal(rt.row('a').sc.textContent, 'run_shell(command="echo")\n执行中...');
  await send(rt, [{type: 'tool_command_delta', execution_id: 'a', execution_runtime_seq: 4,
    tool_call_id: 'call-a', delta: 'stdout'.repeat(30)}]);
  assert(rt.row('a').sc.textContent.includes('stdout'.repeat(30)), 'execution output is installed in one update');
  await send(rt, [{type: 'tool_call', execution_id: 'a', execution_runtime_seq: 5,
    tool: 'run_shell', tool_call_id: 'call-a', result: 'result'.repeat(30)}]);
  const done = rt.row('a').sc.textContent; assert(done.includes('result'.repeat(30)));
  rt.drain(); assert.equal(rt.row('a').sc.textContent, done, 'old tool drafting cannot overwrite execution/results');
  assert.equal(rt.row('b').sc.textContent, rt.c.formatToolDraftLine('read_file', 'y'.repeat(80)));

  const snap = runtime(); await send(snap, [toolDelta('snap', 'read_', 'old'.repeat(30), 1)]); snap.frame();
  await send(snap, [{...toolDelta('snap', 'read_file', '{"path":"new"}', 2), replayed_snapshot: true}]);
  assert.equal(snap.row('snap').sc.textContent, snap.c.formatToolDraftLine('read_file', '{"path":"new"}'));
  assert.equal(snap.frames.size, 0);
  await send(snap, [toolDelta('snap', '', ' tail'.repeat(20), 3)]);
  assert.equal(snap.row('snap').sc._llmToolArgs, '{"path":"new"}'); snap.drain();
  assert.equal(snap.row('snap').sc._llmToolArgs, '{"path":"new"}' + ' tail'.repeat(20));

  const legacy = runtime(), sc = legacy.c.createProcessFeedRow(legacy.ctx, 'tool-call', '工具调用生成中...');
  const row = legacy.rows[0]; row.dataset.pendingToolName = 'run_shell'; row.dataset.pendingToolArgs = 'z'.repeat(80);
  legacy.c.scheduleToolRowRender(legacy.ctx, row, 's', 'draft', {}); legacy.frame();
  assert(sc._llmToolArgs.length < 80);
  legacy.c.setToolRowText(row, 'execution output', legacy.ctx, 's'); legacy.drain();
  assert.equal(sc.textContent, 'execution output');

  for (const type of ['context-summary-reasoning', 'context-summary', 'key-context']) {
    const progress = runtime(), text = '压缩😀'.repeat(30);
    const event = type === 'context-summary-reasoning'
      ? {type: 'context_summary_reasoning_delta', delta: text, ephemeral: true}
      : {type: type === 'key-context' ? 'key_context_delta' : 'context_summary_delta', ephemeral: true,
        delta: type === 'key-context' ? '<summary>' + text + '</summary>' : text};
    await send(progress, [event]); const sc = progress.ctx.progressStream[type].scroller;
    assert.equal(sc.textContent, ''); progress.frame();
    assert(sc.textContent.length > 0 && sc.textContent.length < text.length);
    assert(!/[\uD800-\uDBFF]$/.test(sc.textContent));
    if (type !== 'context-summary-reasoning') {
      const shown = sc.textContent;
      progress.c.appendProgressLog(progress.ctx, 'new status', type, 's');
      assert.equal(sc.textContent, 'new status\n\n' + shown, 'system status changes preserve pending model output');
    }
    progress.c.finalizeProgressStreamForType(progress.ctx, type); progress.drain();
    assert.equal(sc.textContent, (type === 'context-summary-reasoning' ? '' : 'new status\n\n') + text);
    assert.equal(progress.frames.size, 0);
    await send(progress, [{...event, delta: type === 'key-context' ? '<summary>snapshot</summary>' : 'snapshot', replayed_snapshot: true}]);
    assert.equal(progress.ctx.progressStream[type].scroller.textContent,
      (type === 'context-summary-reasoning' ? '' : 'new status\n\n') + 'snapshot');
    assert.equal(progress.frames.size, 0, 'snapshots install full model output immediately');
  }
  const plain = runtime(); plain.c.appendProgressStreamDelta(plain.ctx, 'runtime'.repeat(40), 'context-trim', 's');
  plain.frame(); assert.equal(plain.ctx.progressStream['context-trim'].scroller.textContent, 'runtime'.repeat(40));
}
async function main() {
  await toolsAndProgress();
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

  for (const boundary of ['finalizeLlmStreamChunks', 'resetLlmState', 'discardLlmStreamChunks']) for (const kind of ['response', 'tool']) {
    const ended = runtime(), text = 'y'.repeat(80);
    await send(ended, [kind === 'tool' ? toolDelta('end', 'read_file', text, 1) : delta(kind, 'end', text, 1)]); ended.frame();
    const expected = kind === 'tool' ? ended.c.formatToolDraftLine('read_file', text) : text;
    ended.c[boundary](ended.ctx, {});
    assert.equal(ended.row('end').sc.textContent, expected, boundary + ' keeps received durable text');
    assert.equal(ended.ctx.llm.llmDeltaFlushRaf, 0, boundary + ' stops the reveal loop');
    assert.equal(ended.ctx.llm.llmExecutionReveals.size, 0);
    ended.drain();
    assert.equal(ended.row('end').sc.textContent, expected);
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
