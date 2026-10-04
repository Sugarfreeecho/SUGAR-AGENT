const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.resolve(__dirname, '../..');
const rendering = fs.readFileSync(path.join(root, 'frontend/src/app/modules/message-rendering.js'), 'utf8');
const sse = fs.readFileSync(path.join(root, 'frontend/src/app/modules/sse-handling.js'), 'utf8');
const messages = fs.readFileSync(path.join(root, 'frontend/src/app/state/message-renderers.js'), 'utf8');
function fn(source, name) {
  const match = source.match(new RegExp('^(?:async )?function ' + name + '\\([^]*?^}', 'm'));
  assert(match, `missing ${name}`);
  return match[0];
}
function classList(...initial) {
  const names = new Set(initial);
  return {contains: name => names.has(name), add: name => names.add(name), remove: name => names.delete(name),
    toggle(name, on) { if (on) names.add(name); else names.delete(name); }};
}
function display() {
  const group = {dataset: {processGroupId: 'turn:1'}, classList: classList('process-aggregate'), isConnected: true};
  const body = {children: [], closest: () => group,
    querySelectorAll: selector => selector === '[data-temporary-status="1"]'
      ? body.children.map(row => row.scroller).filter(sc => sc.dataset.temporaryStatus === '1') : body.children,
    querySelector: selector => body.querySelectorAll(selector)[0] || null};
  group.body = body;
  group.querySelector = () => body;
  const stream = {children: [group], isConnected: true, querySelectorAll: selector =>
    selector === '.process-aggregate' ? [group]
      : selector === '[data-execution-id]' ? body.children.filter(row => row.dataset.executionId) : body.children};
  const ctx = {stream, currentProcessGroup: group, lastRuntimeSeq: 0, streamEventIndex: 0};
  return {ctx, group, body, rows: () => body.children,
    pending: () => body.querySelectorAll('[data-temporary-status="1"]').length,
    row: id => body.children.find(row => row.dataset.executionId === id)};
}
function createRow(ctx, type, text) {
  const body = ctx.currentProcessGroup.body;
  const row = {dataset: {}, isConnected: true, classList: classList('feed-item', type === 'tool-call' ? 'feed--tool' : ''),
    remove() { body.children.splice(body.children.indexOf(row), 1); row.isConnected = false; scroller.isConnected = false; },
    closest: selector => selector === '.feed-item' ? row : selector === '.process-aggregate' ? ctx.currentProcessGroup : body,
    getAttribute: name => row.dataset[name.replace(/^data-/, '').replace(/-([a-z])/g, (_, c) => c.toUpperCase())],
    removeAttribute(name) { delete row.dataset[name.replace(/^data-/, '').replace(/-([a-z])/g, (_, c) => c.toUpperCase())]; }};
  const chunk = {classList: classList('feed-chunk')};
  const scroller = {dataset: {}, textContent: text, isConnected: true,
    closest: selector => selector === '.feed-chunk' ? chunk : row};
  row.scroller = scroller;
  row.querySelector = selector => selector === '.feed-chunk-scroller' ? scroller : selector === '.feed-chunk' ? chunk : null;
  body.children.push(row);
  return scroller;
}
function runtime() {
  const c = vm.createContext({console, Date, Number, String, Array, Object, Map, Set, JSON, TextDecoder,
    replayingMessages: false, currentSessionId: 'parent', SSE_IDLE_TIMEOUT_MS: 1000,
    readSseChunkWithIdleTimeout: reader => reader.read(),
    sessionStore: {shouldAcceptSseEvent: () => true}, consumeExtensionControlEvent: () => false,
    applySessionEvent: () => ({}), streamHistoryRecoveryBySession: new Set(),
    noteSubagentLifecycleFrame() {}, scheduleFinalVisibleAfterRunIfEnabled() {},
    createProcessFeedRow: createRow, appendLog: (ctx, text, type) => createRow(ctx, type, text),
    getExistingProcessBody: ctx => ctx.currentProcessGroup && ctx.currentProcessGroup.body,
    getLastProcessFeedItem: body => body.children.at(-1),
    getUiRuntimeText: sc => sc.textContent, setUiRuntimeText: (sc, text) => { sc.textContent = text; },
    findToolCallRow: (ctx, id) => ctx.currentProcessGroup.body.children.find(row => row.dataset.toolCallId === id),
    discardPendingToolRowRender() {}, rememberToolStreamRow() {}, truncateLogTextForUi: text => text,
    refreshFeedChunkOverflow() {}, refreshAggregateStatsSmart() {}, reactGenerationForContext: () => 0,
    unregisterProcessAggregateRow() {}, registerProcessAggregateRow() {}, scrollContentAreaIfFollow() {},
    renderEvent() { throw new Error('execution identity must use the durable renderer'); }});
  vm.runInContext(rendering.slice(rendering.indexOf('var executionRecordsBySession'), rendering.indexOf('function ensureProcessGroup')), c);
  for (const name of ['removeTemporaryStatus', 'upsertTemporaryStatus', 'formatToolDraftLine', 'formatToolPendingLine']) {
    vm.runInContext(fn(rendering, name), c);
  }
  vm.runInContext(fn(messages, 'renderMessageRecord'), c);
  for (const name of ['shouldApplySseSeqFilter', 'sseSequenceScope', 'consumeAgentSseResponseInner']) vm.runInContext(fn(sse, name), c);
  return c;
}
async function send(c, ui, events) {
  // Exercise the real SSE decoder/dispatcher, including split UTF-8 chunks.
  const bytes = new TextEncoder().encode(events.map(event => 'data: ' + JSON.stringify(event) + '\n\n').join(''));
  let offset = 0;
  const response = {ok: true, headers: {get: () => 'text/event-stream'}, body: {getReader: () => ({read: async () => {
    if (offset >= bytes.length) return {done: true};
    const value = bytes.slice(offset, offset + 17); offset += value.length;
    return {done: false, value};
  }})}};
  return c.consumeAgentSseResponseInner(response, ui.ctx, 'parent', ui.ctx.streamEventIndex);
}
const waiting = {type: 'status', ephemeral: true, session_id: 'parent', content: '正在思考中...'};
function event(type, id, fields = {}) {
  return {type, execution_id: id, process_group_id: 'turn:1', session_id: 'parent', ephemeral: true,
    execution_runtime_seq: 2, ...fields};
}
function update(seq, fields) {
  return {type: 'execution_update', session_id: 'parent', ephemeral: true, runtime_seq: seq,
    update: {process_group_id: 'turn:1', ...fields}};
}

async function main() {
  for (const type of ['llm_reasoning_delta', 'llm_response_delta', 'llm_reasoning', 'llm_response']) {
    const c = runtime(), ui = display();
    await send(c, ui, [waiting]);
    assert.equal(ui.pending(), 1);
    await send(c, ui, [event(type, 'text', {delta: '第一段真实内容', content: '第一段真实内容'})]);
    assert.equal(ui.pending(), 0, `${type} must clear the temporary wait row`);
    assert.equal(ui.rows().length, 1);
    assert.equal(ui.row('text').scroller.textContent, '第一段真实内容');
    assert(!ui.row('text').scroller.textContent.includes('[生成中]'));
    assert.equal(ui.ctx._temporaryStatusScroller, null);
  }
  for (const kind of ['reasoning', 'response']) {
    const c = runtime(), ui = display();
    await send(c, ui, [waiting, update(3, {execution_id: 'text', kind, status: 'generating', text_delta: '恢复的正文'})]);
    assert.equal(ui.pending(), 0, `execution_update/${kind} must clear the wait row`);
    assert.equal(ui.row('text').scroller.textContent, '恢复的正文');
  }

  const c = runtime(), ui = display();
  await send(c, ui, [waiting, event('tool_call_delta', 'tool', {id: 'call', name_delta: '', arguments_delta: ''})]);
  assert.equal(ui.pending(), 1, 'an ID-only delta is not real content');
  assert.equal(ui.row('tool').scroller.textContent, '工具调用生成中...');
  await send(c, ui, [event('tool_call_delta', 'tool', {execution_runtime_seq: 3, id: 'call', name_delta: 'run_shell', arguments_delta: '{"command":'})]);
  assert.equal(ui.pending(), 0);
  assert.equal(ui.row('tool').scroller.textContent, 'run_shell({"command":\n生成中...');
  const pending = event('tool_pending', 'tool', {execution_runtime_seq: 4, tool_call_id: 'call', tool: 'run_shell',
    args: {command: 'test'}, command_preview: 'test'});
  await send(c, ui, [pending, pending]);
  assert.equal(ui.rows().length, 1);
  assert.equal(ui.row('tool').scroller.textContent, 'test\n执行中...');
  await send(c, ui, [event('tool_execution_state', 'tool', {execution_runtime_seq: 5, tool_call_id: 'call', status: 'running'}),
    event('tool_command_delta', 'tool', {execution_runtime_seq: 6, tool_call_id: 'call', delta: '部分输出\n'})]);
  assert(ui.row('tool').scroller.textContent.includes('部分输出'));
  assert(ui.row('tool').scroller.textContent.endsWith('执行中...'));
  assert(!ui.row('tool').scroller.textContent.includes('[执行中]'));
  await send(c, ui, [update(7, {execution_id: 'tool', kind: 'tool', status: 'running', output_delta: '恢复输出\n'})]);
  const saved = JSON.parse(JSON.stringify(c.executionRecordsBySession.get('parent').get('tool')));
  assert(ui.row('tool').scroller.textContent.includes('恢复输出'));
  assert.equal(ui.rows().length, 1);

  // Reconnection on the same DOM, then a fresh DOM with a restored snapshot.
  ui.ctx = {...ui.ctx, currentProcessGroup: null};
  await send(c, ui, [pending, update(7, {execution_id: 'tool', kind: 'tool', output_delta: '恢复输出\n'})]);
  assert.equal(ui.rows().length, 1);
  assert.equal(c.executionRecordsBySession.get('parent').get('tool').output, '部分输出\n恢复输出\n');
  const fresh = display(), restored = runtime();
  restored.replayingMessages = true;
  restored.renderExecutionRecord(fresh.ctx, restored.updateExecutionRecord('parent', saved), 'parent');
  restored.replayingMessages = false;
  await send(restored, fresh, [update(7, {...saved}), pending,
    update(8, {execution_id: 'tool', kind: 'tool', status: 'running', output_delta: '下一段\n'})]);
  assert.equal(fresh.rows().length, 1);
  assert.equal(restored.executionRecordsBySession.get('parent').get('tool').output, '部分输出\n恢复输出\n下一段\n');
  assert(fresh.row('tool').scroller.textContent.endsWith('执行中...'));
  // History events and auxiliary records converge on the same stable row.
  restored.renderMessageRecord(fresh.ctx, {event: {...pending, execution_runtime_seq: 4}}, 'parent');
  assert.equal(fresh.rows().length, 1);
  let terminalSeq = 8;
  for (const [status, label] of [['interrupted', '已中断'], ['failed', '执行失败'], ['timed_out', '已超时'], ['unknown', '执行状态未知']]) {
    await send(restored, fresh, [update(++terminalSeq, {execution_id: 'tool', kind: 'tool', status})]);
    assert(fresh.row('tool').scroller.textContent.includes('[' + label + ']'));
    assert(fresh.row('tool').scroller.textContent.includes('部分输出'));
    assert(!fresh.row('tool').scroller.textContent.includes('[执行中]'));
  }

  // Durable tool replay also removes a wait row without a live tool_pending.
  for (const status of ['generating', 'waiting_execution', 'running']) {
    const recovered = runtime(), target = display();
    await send(recovered, target, [waiting, update(2, {execution_id: 'tool', kind: 'tool', status,
      tool: 'run_shell', arguments_raw: '{"command":', command_preview: 'test'})]);
    assert.equal(target.pending(), 0);
    assert(!target.row('tool').scroller.textContent.includes('[生成中]'));
    if (status !== 'generating') assert(target.row('tool').scroller.textContent.endsWith('执行中...'));
  }
  // Child frames must be isolated before both execution rendering branches.
  const parent = display(), childRuntime = runtime();
  await send(childRuntime, parent, [waiting]);
  const childEvents = [
    event('llm_reasoning_delta', 'child-1', {agent_id: 'child', _subagent_forward: true, delta: 'child', execution_runtime_seq: 99}),
    event('llm_response_delta', 'child-2', {agent_id: 'child', session_id: 'child-session', delta: 'child', execution_runtime_seq: 100}),
    event('tool_call_delta', 'child-3', {agent_id: 'child', name_delta: 'task', arguments_delta: '{}', execution_runtime_seq: 101}),
    {...update(102, {execution_id: 'child-4', kind: 'response', text_delta: 'child'}), agent_id: 'child'},
    {...update(103, {execution_id: 'child-update', kind: 'response', text_delta: 'child'}), agent_id: 'child', ephemeral: false},
    {protocol: 'runtime_v2', seq: 103, session_id: 'parent', ui_event:
      event('llm_reasoning_delta', 'child-5', {agent_id: 'child', delta: 'child'})},
    event('tool_call', 'child-6', {agent_id: 'child', ephemeral: false, execution_runtime_seq: undefined,
      tool: 'task', result: 'child result'}),
  ];
  await send(childRuntime, parent, childEvents);
  assert.equal(parent.pending(), 1);
  assert.equal(parent.rows().length, 1, 'child content must not create a parent row');
  assert.equal(parent.ctx.lastRuntimeSeq, 0);
  assert.equal(parent.ctx.streamEventIndex, 1, 'legacy durable child frames still occupy their parent UI history position');
  assert.equal(childRuntime.executionRecordsBySession.has('parent'), false);
  await send(childRuntime, parent, [event('llm_response_delta', 'parent-text', {delta: '父会话正文'})]);
  assert.equal(parent.pending(), 0);
  assert.equal(parent.rows().length, 1);
  assert.equal(parent.row('parent-text').scroller.textContent, '父会话正文');
  console.log('execution display compatibility SSE checks passed');
}
main().catch(error => {console.error(error); process.exitCode = 1;});
