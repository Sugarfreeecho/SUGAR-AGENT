/* Contract: change-review rows survive the execution-record render path.

   The chat-side change review reads `row._toolCallEvent.ui.changes`. Both the
   replayed history projection (tool_call events from the UI projection) and the
   live execution records must forward that plugin-owned payload. */
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const root = path.resolve(__dirname, '../..');
const rendering = fs.readFileSync(path.join(root, 'frontend/src/app/modules/message-rendering.js'), 'utf8');
function section(source, start, end) {
  return source.slice(source.indexOf(start), source.indexOf(end, source.indexOf(start)));
}
function node(classes, attrs = {}) {
  const names = new Set(classes.split(' '));
  return {dataset: {...attrs}, children: [], isConnected: true,
    classList: {contains: name => names.has(name), toggle: (name, on) => on ? names.add(name) : names.delete(name)},
    getAttribute(name) { return this.dataset[name.replace(/^data-/, '').replace(/-([a-z])/g, (_, c) => c.toUpperCase())]; },
    setAttribute(name, value) { this.dataset[name.replace(/^data-/, '').replace(/-([a-z])/g, (_, c) => c.toUpperCase())] = value; },
    removeAttribute(name) { delete this.dataset[name.replace(/^data-/, '').replace(/-([a-z])/g, (_, c) => c.toUpperCase())]; },
    remove() { this.removed = true; },
  };
}

async function main() {
  const dispatched = [];
  const group = node('process-aggregate', {processGroupId: 'turn:1'});
  const rows = [];
  const stream = {children: [group], dataset: {sessionId: 's'},
    querySelectorAll(selector) { return selector === '.process-aggregate' ? [group] : rows; }};
  const ctx = {stream, currentProcessGroup: group};
  const c = vm.createContext({
    Map, Object, String, Number, Array, JSON,
    replayingMessages: true,
    document: {dispatchEvent(event) { dispatched.push(event); }, querySelectorAll: () => []},
    CustomEvent: class { constructor(type, init) { this.type = type; this.detail = (init || {}).detail; } },
    rootSessionIdForRenderedNode: () => 's',
    findToolCallRow: (_ctx, id) => rows.find(row => row.dataset.toolCallId === id),
    createProcessFeedRow: (_ctx, _type, text) => {
      const row = node('feed-item');
      const sc = {textContent: text, closest: () => row};
      const chunk = node('feed-chunk');
      row.querySelector = selector => selector === '.feed-chunk-scroller' ? sc : chunk;
      row.sc = sc;
      rows.push(row);
      return sc;
    },
    discardPendingToolRowRender() {}, rememberToolStreamRow() {}, truncateLogTextForUi: t => t,
    removeTemporaryStatus() {}, refreshFeedChunkOverflow() {}, refreshAggregateStatsSmart() {},
    reactGenerationForContext: () => 0,
    unregisterProcessAggregateRow() {}, registerProcessAggregateRow() {},
    selectExecutionProcessGroup() {}, autoCollapseToolRowAfterResult() {},
    attachHumanInteractionCardsForToolCall() {}, renderDurableAttachmentImages() {},
  });
  vm.runInContext(section(rendering, 'var executionRecordsBySession', 'function ensureProcessGroup'), c);
  vm.runInContext(section(rendering, 'function formatToolDraftLine', 'function formatToolDoneLine'), c);

  const change = {path: 'workspace/demo.txt', operation: 'create', snapshot_id: 'snap-1', revision: 1,
    turn_id: 'turn-1', diff: '--- a/workspace/demo.txt\n+++ b/workspace/demo.txt\n+hello\n',
    added: 1, removed: 0, effective: true};

  // 1. Replayed history projection: a tool_call event carrying the plugin payload.
  c.renderExecutionEvent(ctx, {type:'tool_call', execution_id:'exec-1', process_group_id:'turn:1',
    tool_call_id:'call-1', tool:'write_file', args:{path:'workspace/demo.txt'}, result:'ok',
    execution_status:'completed', execution_runtime_seq:5, run_id:'run-1', react_iter:2, stream_seq:3,
    ui:{changes:[change]}}, 's');
  assert.equal(rows.length, 1, 'the tool row is rendered once');
  const replayed = rows[0]._toolCallEvent;
  assert(replayed, 'the tool row keeps a tool-call event');
  assert(replayed.ui && replayed.ui.changes && replayed.ui.changes.length === 1,
    'the replayed tool_call event forwards the change-review ui payload');
  assert.equal(replayed.ui.changes[0].snapshot_id, 'snap-1');
  const lastDispatch = dispatched[dispatched.length - 1];
  assert.equal(lastDispatch.type, 'myagent:tool-call-rendered', 'the renderer dispatches the tool row event');
  assert(lastDispatch.detail.event.ui.changes[0].path === 'workspace/demo.txt',
    'the dispatched event carries the change-review rows');

  // 2. Live execution record (execution_update from the journal) keeps the payload too.
  c.renderExecutionRecord(ctx, {execution_id:'exec-2', kind:'tool', process_group_id:'turn:1',
    tool_call_id:'call-2', tool:'apply_patch', args:{}, result:'done', status:'completed',
    ui_committed:true, last_runtime_seq:9, run_id:'run-1', react_iter:3, stream_seq:4,
    ui:{changes:[{...change, snapshot_id:'snap-2', revision:2}]}}, 's');
  const live = rows[rows.length - 1]._toolCallEvent;
  assert(live && live.ui && live.ui.changes[0].snapshot_id === 'snap-2',
    'the execution-record render forwards the change-review ui payload');

  // 3. A tool result without plugin metadata must not fabricate one.
  c.renderExecutionEvent(ctx, {type:'tool_call', execution_id:'exec-3', process_group_id:'turn:1',
    tool_call_id:'call-3', tool:'run_shell', args:{command:'dir'}, result:'ok',
    execution_status:'completed', execution_runtime_seq:11, run_id:'run-1', react_iter:4, stream_seq:5}, 's');
  const plain = rows[rows.length - 1]._toolCallEvent;
  assert(plain && !plain.ui, 'no ui payload is invented for ordinary tool results');

  console.log('change review ui payload runtime checks passed');
}

main().catch(error => { console.error(error); process.exitCode = 1; });
