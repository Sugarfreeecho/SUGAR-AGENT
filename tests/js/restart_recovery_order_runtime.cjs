const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.resolve(__dirname, '../..');
function source(name) {
  return fs.readFileSync(path.join(root, 'frontend', 'src', 'app', 'modules', name + '.js'), 'utf8');
}
function fn(name, text) {
  const match = text.match(new RegExp('^(?:async )?function ' + name + '\\([^]*?^}', 'm'));
  assert(match, `missing ${name}`);
  return match[0];
}
function row(runId, generation) {
  return {
    getAttribute(name) {
      if (name === 'data-run-id') return runId;
      if (name === 'data-react-generation') return String(generation);
      return null;
    },
  };
}

const rendering = source('message-rendering');
const sse = source('sse-handling');
const dispatch = source('event-dispatch');
let resets = 0;
const context = vm.createContext({
  Math, Number, String,
  replayingMessages: false,
  resetLlmState() { resets += 1; },
});
vm.runInContext([
  fn('reactGenerationForContext', rendering),
  fn('findExistingLlmFeedRow', rendering),
  fn('reactFeedPhase', rendering),
  fn('appendProcessRowBeforePendingAppendSteer', rendering),
  fn('appendMonotonicProcessRow', rendering),
  fn('insertReactOrderedFeedRow', rendering),
  fn('restoreReactGenerationFromProcessGroup', sse),
  fn('syncRenderContextRunScope', dispatch),
].join('\n'), context);

const oldRow = row('run-old', 0);
const oldGroup = {
  isConnected: true,
  querySelectorAll() { return [oldRow]; },
};
const restored = {runId: 'run-new', reactGeneration: 0};
assert.equal(context.restoreReactGenerationFromProcessGroup(restored, oldGroup), 1);
assert.equal(restored.reactGeneration, 1, 'a replacement run must append after the old generation');

const sameRun = {runId: 'run-old', reactGeneration: 0};
assert.equal(context.restoreReactGenerationFromProcessGroup(sameRun, oldGroup), 0);

const history = {runId: 'run-old', reactGeneration: 0, llm: {}};
context.syncRenderContextRunScope(history, {type: 'llm_reasoning', run_id: 'run-new'});
assert.equal(history.runId, 'run-new');
assert.equal(history.reactGeneration, 1);
assert.equal(resets, 1);
context.syncRenderContextRunScope(history, {type: 'llm_response', run_id: 'run-new'});
assert.equal(history.reactGeneration, 1, 'same-run rows must share their generation');

const newRow = row('run-new', 1);
const group = {
  isConnected: true,
  querySelectorAll() { return [oldRow, newRow]; },
};
const lookup = {runId: 'run-new', reactGeneration: 1, currentProcessGroup: group};
assert.equal(context.findExistingLlmFeedRow(lookup, 'llm-reasoning', 1), newRow);
group.querySelectorAll = () => [oldRow];
assert.equal(context.findExistingLlmFeedRow(lookup, 'llm-reasoning', 1), null,
  'a resumed run must never overwrite the old run\'s row');

const oldProcessRow = {
  matches: () => false,
  getAttribute(name) {
    return ({'data-log-type': 'llm-response', 'data-react-iter': '2',
      'data-react-generation': '0'})[name] || null;
  },
};
const inserted = {};
const body = {
  children: [oldProcessRow],
  _reactOrderTailKey: [0, 2, 1],
  get lastElementChild() { return this.children[this.children.length - 1]; },
  appendChild(item) { this.children.push(item); },
  insertBefore(item, before) { this.children.splice(this.children.indexOf(before), 0, item); },
  querySelectorAll() { return this.children; },
};
inserted.setAttribute = (name, value) => { inserted[name] = value; };
context.insertReactOrderedFeedRow(body, inserted, 'llm-reasoning', 1, 1);
assert.deepEqual(body.children, [oldProcessRow, inserted],
  'replacement run iteration 1 must appear after old run iteration 2');

async function checkResumedSseTokens() {
  const accepted = new Map([['s::event_bus:old-process', 100]]);
  const deltas = [];
  const sseContext = vm.createContext({
    console, Date, Number, String, Promise, TextDecoder,
    SSE_IDLE_TIMEOUT_MS: 1000,
    sessionStore: {
      shouldAcceptSseEvent(sid, seq, scope) {
        const key = sid + '::' + scope;
        const previous = accepted.get(key) || 0;
        if (seq <= previous) return false;
        accepted.set(key, seq);
        return true;
      },
    },
    readSseChunkWithIdleTimeout: reader => reader.read(),
    consumeExtensionControlEvent: () => false,
    applySessionEvent: () => ({}),
    appendLlmStreamDelta: (_ctx, event) => deltas.push(event.delta),
    scheduleFinalVisibleAfterRunIfEnabled() {},
  });
  vm.runInContext([
    fn('shouldApplySseSeqFilter', sse),
    fn('sseSequenceScope', sse),
    fn('consumeAgentSseResponseInner', sse),
  ].join('\n'), sseContext);
  const event = (seq, delta) => 'data: ' + JSON.stringify({
    type: 'llm_response_delta', ephemeral: true, session_id: 's',
    seq, seq_scope: 'event_bus', event_bus_epoch: 'new-process', delta,
  }) + '\n\n';
  const bytes = new TextEncoder().encode(event(1, 'A') + event(1, 'duplicate') + event(2, 'B'));
  let readCount = 0;
  const response = {
    ok: true,
    headers: {get: () => 'text/event-stream'},
    body: {getReader: () => ({read: async () => readCount++ ? {done: true} : {done: false, value: bytes}})},
  };
  await sseContext.consumeAgentSseResponseInner(response, {}, 's', 10);
  assert.deepEqual(deltas, ['A', 'B'], 'new-process token stream must survive an old high-water mark');
}

checkResumedSseTokens().then(() => {
  process.stdout.write('restart recovery order runtime checks passed\n');
}).catch(error => { console.error(error); process.exitCode = 1; });
