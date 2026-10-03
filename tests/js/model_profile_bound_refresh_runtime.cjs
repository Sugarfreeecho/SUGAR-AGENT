/* 右下角模型选择器刷新链路：model_profile_bound 事件 + 流关闭兜底。
 *
 * 背景：fallback 接管会在服务端把会话绑定改写成实际服务的 profile，但
 * ① 失败时的 model_switch 状态事件发生在改绑之前，前端那次刷新读到旧值；
 * ② 改绑完成时原本没有任何事件（_fallback_adopted_callback 从未接线）。
 * 结果：选择器一直显示旧模型，直到用户手动点开菜单才刷新。
 *
 * 本测试校验前端侧的两条链路：
 *   1. 收到 ephemeral 的 model_profile_bound 事件 → 静默重取绑定（silent）；
 *   2. 无论有没有该事件，SSE 流关闭时兜底刷新一次。
 * 用 UI_REVIEW_REF=HEAD 可对旧版本跑同一断言（应失败）。
 */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { execFileSync } = require('node:child_process');

const root = path.resolve(__dirname, '../..');
const ref = process.env.UI_REVIEW_REF;
const source = ref
  ? execFileSync('git', ['show', `${ref}:frontend/src/app/modules/sse-handling.js`], { cwd: root, encoding: 'utf8' })
  : fs.readFileSync(path.resolve(root, 'frontend/src/app/modules/sse-handling.js'), 'utf8');
const modelSource = fs.readFileSync(path.resolve(root, 'frontend/src/app/modules/model-profiles.js'), 'utf8');

function fn(name) {
  const match = source.match(new RegExp('^(?:async )?function ' + name + '\\([^]*?^}', 'm'));
  assert(match, `missing ${name}`);
  return match[0];
}

function frameStream(events) {
  const bytes = new TextEncoder().encode(
    events.map(event => `data: ${JSON.stringify(event)}\n\n`).join('')
  );
  let reads = 0;
  return {
    ok: true,
    headers: { get: () => 'text/event-stream' },
    body: {
      getReader: () => ({
        read: async () => (reads++ ? { done: true, value: undefined } : { done: false, value: bytes }),
      }),
    },
  };
}

function fixture() {
  const refreshes = [];
  const extensionRefreshes = [];
  const ctx = { streamConsuming: true, streamEventIndex: 10, lastBusinessEventAt: Date.now() };
  let run = { ctx, controller: { abort() {} } };
  const context = vm.createContext({
    console, Date, Number, String, Promise, TextDecoder, JSON, Set, Map,
    SSE_IDLE_TIMEOUT_MS: 120000,
    currentSessionId: 's', modelProfileSelectionEpoch: 0,
    streamHistoryRecoveryBySession: new Set(),
    sessionStore: { shouldAcceptSseEvent: () => true },
    readSseChunkWithIdleTimeout: reader => reader.read(),
    consumeExtensionControlEvent: () => false,
    applySessionEvent: () => ({}),
    applyContextTokenLabelForCurrentSession() {},
    appendToolPendingRow() {},
    noteSubagentLifecycleFrame() {},
    scheduleFinalVisibleAfterRunIfEnabled() {},
    reconcileRunStateFromServer: async () => {},
    getSessionRunState: () => run,
    clearSessionRunState: () => { run = null; },
    getRunAbortReason: () => '',
    scheduleActiveSessionReconnect() {},
    getUiEventCount: async () => 12,
    markRunAbortReason() {},
    setInterval: () => 1,
    clearInterval: () => {},
    setTimeout: () => 1,
    clearTimeout: () => {},
    CustomEvent: class {
      constructor(type, options) {
        this.type = type;
        this.detail = options && options.detail;
      }
    },
    document: {
      dispatchEvent: event => {
        if (event && event.type === 'myagent:extension-state-changed') extensionRefreshes.push(event.detail);
      },
    },
    refreshModelProfileSelectorInBackground(sessionId, opts) {
      refreshes.push({ sessionId, silent: !!(opts && opts.silent), invalidate: !!(opts && opts.invalidate) });
      return Promise.resolve(true);
    },
  });
  vm.runInContext(modelSource.match(/^function noteModelBindingChanged\([^]*?^}/m)[0] + '\n' + [
    fn('shouldApplySseSeqFilter'),
    fn('sseSequenceScope'),
    fn('consumeAgentSseResponseInner'),
    fn('checkSessionStreamProgress'),
    fn('consumeAgentSseResponse'),
    fn('requestExtensionStateConvergence'),
  ].join('\n'), context);
  return { context, ctx, refreshes, extensionRefreshes };
}

async function testBoundEventRefreshesSelector() {
  const f = fixture();
  await f.context.consumeAgentSseResponseInner(frameStream([
    { type: 'model_profile_bound', ephemeral: true, session_id: 's', profile_id: 'p2', model: 'm2', seq: 3, seq_scope: 'event_bus' },
  ]), f.ctx, 's', 10);
  assert.equal(f.refreshes.length, 1, 'model_profile_bound 必须触发选择器静默刷新');
  assert.equal(f.refreshes[0].sessionId, 's');
  assert.equal(f.refreshes[0].silent, true, '后台刷新必须静默，不能把标签改成“正在加载模型配置”');
  assert.equal(f.refreshes[0].invalidate, true, '改绑通知必须使旧请求失效');
  assert.equal(f.ctx.streamEventIndex, 10, 'ephemeral 事件不得推进 UI 历史游标');
}

async function testBoundEventFallsBackToRunSession() {
  const f = fixture();
  f.context.currentSessionId = 'run-session';
  await f.context.consumeAgentSseResponseInner(frameStream([
    { type: 'model_profile_bound', ephemeral: true, seq: 4, seq_scope: 'event_bus' },
  ]), f.ctx, 'run-session', 10);
  assert.equal(f.refreshes.length, 1);
  assert.equal(f.refreshes[0].sessionId, 'run-session', '事件没带 session_id 时用 runSessionId');
}

async function testUnrelatedEphemeralDoesNotRefresh() {
  const f = fixture();
  await f.context.consumeAgentSseResponseInner(frameStream([
    { type: 'sse_keepalive', ephemeral: true, seq: 5, seq_scope: 'event_bus' },
  ]), f.ctx, 's', 10);
  assert.equal(f.refreshes.length, 0, '无关的 ephemeral 事件不应触发选择器刷新');
}

async function testSelectorRefreshMissingIsHarmless() {
  const f = fixture();
  delete f.context.refreshModelProfileSelectorInBackground;
  delete f.context.noteModelBindingChanged;
  await f.context.consumeAgentSseResponseInner(frameStream([
    { type: 'model_profile_bound', ephemeral: true, session_id: 's', seq: 6, seq_scope: 'event_bus' },
  ]), f.ctx, 's', 10);
  assert.equal(f.ctx.streamEventIndex, 10);
}

async function testStreamCloseAlwaysRefreshes() {
  const f = fixture();
  await f.context.consumeAgentSseResponse(frameStream([]), f.ctx, 's', 10);
  assert.equal(f.refreshes.length, 1, '流关闭必须兜底刷新一次选择器');
  assert.equal(f.refreshes[0].sessionId, 's');
  assert.equal(f.refreshes[0].silent, true);
  assert.equal(f.refreshes[0].invalidate, true);
  assert.equal(f.extensionRefreshes.length, 1, '流关闭仍要收敛扩展面板（既有行为）');
  assert.equal(f.ctx.streamConsuming, false);
}

async function testBackgroundEventsDoNotRefreshActiveSelector() {
  const f = fixture();
  await f.context.consumeAgentSseResponse(frameStream([
    { type: 'model_profile_bound', ephemeral: true, session_id: 'background', seq: 7 },
  ]), f.ctx, 'background', 10);
  assert.equal(f.refreshes.length, 0, '后台事件和流关闭不得使当前选择器请求失效');
  assert.equal(f.extensionRefreshes.length, 1, '后台扩展状态仍应收敛');
}

async function testBoundThenCloseUsesOneRefresh() {
  const f = fixture();
  await f.context.consumeAgentSseResponse(frameStream([
    { type: 'model_profile_bound', ephemeral: true, session_id: 's', profile_id: 'p2', seq: 8 },
  ]), f.ctx, 's', 10);
  assert.equal(f.refreshes.length, 1, '改绑和关闭必须复用同一次权威刷新');
}

async function testReusedContextRechecksEachStream() {
  const f = fixture();
  f.ctx.modelBindingVerified = true;
  await f.context.consumeAgentSseResponse(frameStream([]), f.ctx, 's', 10);
  assert.equal(f.refreshes.length, 1, '新流不能沿用上一轮的绑定验证结果');
}

async function main() {
  await testBoundEventRefreshesSelector();
  await testBoundEventFallsBackToRunSession();
  await testUnrelatedEphemeralDoesNotRefresh();
  await testSelectorRefreshMissingIsHarmless();
  await testStreamCloseAlwaysRefreshes();
  await testBackgroundEventsDoNotRefreshActiveSelector();
  await testBoundThenCloseUsesOneRefresh();
  await testReusedContextRechecksEachStream();
  console.log('model profile bound refresh runtime checks passed');
}

main().catch(error => {
  console.error(error);
  process.exit(1);
});
