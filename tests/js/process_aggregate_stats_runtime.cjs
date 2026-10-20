const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.resolve(__dirname, '../../frontend/src/app/modules/message-rendering.js'), 'utf8');
function fn(name) {
  const match = source.match(new RegExp('^function ' + name + '\\([^]*?^}', 'm'));
  assert(match, `missing ${name}`);
  return match[0];
}
const dataKey = name => name.replace(/^data-/, '').replace(/-([a-z])/g, (_, c) => c.toUpperCase());
function runtime() {
  const groups = [];
  const stream = {children: groups,
    contains: row => groups.some(group => group.body.children.includes(row)),
    querySelectorAll: selector => selector === '.process-aggregate' ? groups
      : groups.flatMap(group => group.body.children).filter(row => row.dataset.executionId)};
  function group() {
    const agg = {dataset: {processGroupId: 'turn:1'}, isConnected: true,
      classList: {contains: name => name === 'process-aggregate'},
      remove() { groups.splice(groups.indexOf(agg), 1); }};
    const body = {children: [], closest: () => agg, scans: 0,
      querySelectorAll() { this.scans++; return this.children; },
      appendChild(row) {
        const old = row.owner.body.children;
        old.splice(old.indexOf(row), 1);
        row.owner = agg;
        this.children.push(row);
      }};
    agg.body = body;
    agg.stats = {};
    agg.querySelector = selector => selector === '.process-aggregate-body' ? body : agg.stats;
    groups.push(agg);
    return agg;
  }
  const c = vm.createContext({console, replayingMessages: false, currentSessionId: 's',
    processAggregateStateByElement: new WeakMap(), executionRecordsBySession: new Map(),
    executionRowsByStream: new WeakMap(),
    document: {dispatchEvent() {}}, CustomEvent: function () {},
    getProcessBody: ctx => ctx.currentProcessGroup.body,
    findToolCallRow: (ctx, id) => ctx.currentProcessGroup.body.children.find(row => row.dataset.toolCallId === id),
    findToolDraftRow: () => null, uiEventReactIter: event => event.react_iter,
    reactGenerationForContext: () => 0, reactFeedPhase: () => 2,
    removeTemporaryStatus() {}, discardPendingToolRowRender() {}, rememberToolStreamRow() {},
    refreshFeedChunkOverflow() {}, renderDurableAttachmentImages() {}, autoCollapseToolRowAfterResult() {},
    scrollContentAreaIfFollow() {}, rootSessionIdForRenderedNode: () => 's',
    processAggregateNeedsLiveStats: () => false, refreshLiveProcessAggregateStats: () => false,
    stopLiveProcessAggregateStats() {},
    truncateLogTextForUi: text => text, trimSurroundingBlankLines: text => text,
    formatToolDoneLine: (_tool, _args, result) => result,
    formatToolPendingLine: (_tool, _args, text) => text,
    renderProcessAggregateStats(el, text) { el.textContent = text; },
    createProcessFeedRow(ctx, type, text, opts, _sid, tid) {
      const row = {owner: ctx.currentProcessGroup, dataset: {logType: type, toolCallId: tid || '',
        reactIter: String(opts && opts.reactIter || 1)},
        getAttribute(name) { return this.dataset[dataKey(name)]; },
        setAttribute(name, value) { this.dataset[dataKey(name)] = value; },
        removeAttribute(name) { delete this.dataset[dataKey(name)]; },
        closest(selector) { return selector === '.feed-item' ? row
          : selector === '.process-aggregate' ? row.owner : row.owner.body; }};
      const scroller = {textContent: text, closest: selector => row.closest(selector)};
      const chunk = {classList: {toggle() {}}};
      row.querySelector = selector => selector === '.feed-chunk-scroller' ? scroller : chunk;
      row.scroller = scroller;
      row.owner.body.children.push(row);
      c.registerProcessAggregateRow(row.owner, row);
      return scroller;
    },
  });
  vm.runInContext([
    'emptyProcessAggregateState', 'ensureProcessAggregateState', 'registerProcessAggregateRow',
    'unregisterProcessAggregateRow', 'hydrateProcessAggregateState', 'refreshProcessAggregateStats',
    'refreshAggregateStatsSmart', 'applyProcessMetricsFromEvent',
    'invalidateExecutionRowIndex', 'executionRowIndexForStream',
    'findIndexedExecutionRow', 'findExecutionProcessGroup', 'selectExecutionProcessGroup',
    'updateExecutionRecord', 'renderExecutionRecord', 'renderExecutionEvent', 'mergeAdjacentExecutionGroups',
    'upsertToolCallResult',
  ].map(fn).join('\n'), c);
  const agg = group();
  const ctx = {stream, currentProcessGroup: agg};
  function counts(tools, failures, owner = agg) {
    c.refreshProcessAggregateStats(owner);
    assert.match(owner.stats.textContent, new RegExp(`工具 ${tools} 次 · 失败 ${failures} 次$`));
  }
  let seq = 0;
  function event(id, fields = {}) {
    const event = {type: 'tool_call', execution_id: id, process_group_id: 'turn:1',
      tool: 'read_file', tool_call_id: 'call-' + id, result: 'result', execution_runtime_seq: ++seq, ...fields};
    c.renderExecutionEvent(ctx, event, 's');
    return event;
  }
  return {c, ctx, agg, group, counts, event};
}

// A pending row must contribute its failure as soon as its result arrives.
{
  const {c, ctx, agg, counts, event} = runtime();
  event('one', {type: 'tool_pending'});
  counts(1, 0);
  const failed = event('one', {status: {ok: false}});
  assert.match(agg.body.children[0].scroller.textContent, /\[执行失败\]/);
  counts(1, 1);
  c.renderExecutionEvent(ctx, failed, 's');
  event('one', {status: {ok: false}});
  counts(1, 1);
  // Late output cannot undo or count the same terminal failure again.
  event('one', {type: 'tool_command_delta', delta: 'late output'});
  counts(1, 1);
  event('two', {execution_status: 'failed'});
  event('three', {status: {ok: false, timed_out: true}});
  counts(3, 3);
  event('interrupted', {execution_status: 'interrupted', status: {ok: false}});
  event('unknown', {execution_status: 'unknown'});
  event('success', {status: {ok: true}, result: 'file contents: [执行失败], Error: example'});
  c.renderExecutionRecord(ctx, {execution_id: 'reasoning', kind: 'reasoning', status: 'failed'}, 's');
  counts(6, 3);
  // Metrics can lag parallel results or restart their run-local counters.
  c.applyProcessMetricsFromEvent(ctx, {tool_calls: 0, tool_failures: 0});
  counts(6, 3);
  c.applyProcessMetricsFromEvent(ctx, {tool_calls: 2, tool_failures: 2});
  counts(6, 3);
  c.applyProcessMetricsFromEvent(ctx, {tool_calls: 10, tool_failures: 7});
  counts(10, 7); // Preserve summaries when only part of the history is loaded.
  delete agg.dataset.procToolFails;
  delete agg.dataset.procToolCalls;
  c.processAggregateStateByElement = new WeakMap();
  counts(6, 3); // Cached DOM/history hydration recovers failure counts.
  const scans = agg.body.scans;
  for (let i = 0; i < 100; i++) counts(6, 3);
  assert.equal(agg.body.scans, scans, 'refreshes must not rescan tool rows');
  const row = agg.body.children[0];
  c.unregisterProcessAggregateRow(row);
  c.unregisterProcessAggregateRow(row);
  counts(5, 2);
  c.registerProcessAggregateRow(agg, row);
  c.registerProcessAggregateRow(agg, row);
  counts(6, 3);
}

// Legacy tool_call results use structured status even without execution IDs.
{
  const {c, ctx, agg, counts} = runtime();
  const pending = c.createProcessFeedRow(ctx, 'tool-call', 'pending', {}, 's', 'legacy');
  const failed = {tool: 'run_shell', tool_call_id: 'legacy', result: 'command failed', status: {ok: false}};
  c.upsertToolCallResult(ctx, failed, 's');
  counts(1, 1);
  c.upsertToolCallResult(ctx, failed, 's');
  counts(1, 1);
  c.upsertToolCallResult(ctx, {...failed, tool_call_id: 'timeout', status: {timed_out: true}}, 's');
  counts(2, 2);
  c.upsertToolCallResult(ctx, {...failed, status: {ok: true}}, 's');
  counts(2, 1); // Replacing a row removes its previously counted failure.
  assert.equal(pending.closest('.feed-item').dataset.toolCallId, 'legacy');
  c.processAggregateStateByElement = new WeakMap();
  counts(2, 1);
  assert.equal(agg.body.children.length, 2);
}

// Moving rows when continuation groups merge transfers each failure once.
{
  const {c, ctx, agg, group, counts, event} = runtime();
  event('first', {status: {ok: false}});
  const continuation = group();
  const sc = c.createProcessFeedRow({currentProcessGroup: continuation}, 'tool-call', 'failed', {}, 's');
  sc.closest('.feed-item').dataset.executionStatus = 'failed';
  c.hydrateProcessAggregateState(continuation);
  continuation.dataset.procToolFails = '1';
  c.mergeAdjacentExecutionGroups(ctx.stream);
  assert.equal(ctx.stream.children.length, 1);
  counts(2, 2);
  assert.equal(agg.body.children.length, 2);
}

console.log('process aggregate failure stats runtime checks passed');
