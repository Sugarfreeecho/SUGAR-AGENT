const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(
  path.resolve(__dirname, '../../frontend/src/app/modules/session-management.js'),
  'utf8'
);
const match = source.match(/function maybeTakeOverActiveRuntimeSession\([^]*?^}/m);
assert(match, 'maybeTakeOverActiveRuntimeSession');

async function flush() {
  await new Promise(resolve => setImmediate(resolve));
  await new Promise(resolve => setImmediate(resolve));
}

async function main() {
  let attaches = 0;
  let refreshes = 0;
  let activeMarks = 0;
  let reconnectResets = 0;
  let releaseAttach;
  const context = vm.createContext({
    console,
    Promise,
    currentSessionId: 's1',
    runtimeTakeoverBySession: Object.create(null),
    navigator: { online: true },
    isSessionStreamStopSuppressed: () => false,
    getSessionRunState: () => null,
    setSessionServerStreamActive: (_sid, active) => { if (active) activeMarks += 1; },
    resetStreamReconnectState: () => { reconnectResets += 1; },
    refreshSingleSessionRow: async () => { refreshes += 1; },
    attachSessionEventStream: async () => {
      attaches += 1;
      await new Promise(resolve => { releaseAttach = resolve; });
    },
    CustomEvent: class {
      constructor(type, options) { this.type = type; this.detail = options.detail; }
    },
    document: {
      dispatchEvent(event) {
        assert.equal(event.type, 'myagent:extension-state-changed');
        assert.equal(event.detail.sessionId, 's1');
      },
    },
  });
  vm.runInContext(match[0], context);

  context.maybeTakeOverActiveRuntimeSession({ active_session_ids: ['s1'] });
  context.maybeTakeOverActiveRuntimeSession({ active_session_ids: ['s1'] });
  assert.equal(attaches, 1, 'overlapping heartbeats must share one takeover');
  assert.equal(activeMarks, 1);
  assert.equal(reconnectResets, 1);
  assert.equal(refreshes, 1);
  releaseAttach();
  await flush();
  assert.equal(context.runtimeTakeoverBySession.s1, undefined);

  context.isSessionStreamStopSuppressed = () => true;
  context.maybeTakeOverActiveRuntimeSession({ active_session_ids: ['s1'] });
  context.maybeTakeOverActiveRuntimeSession({ active_session_ids: ['other'] });
  await flush();
  assert.equal(attaches, 1, 'manual stop and unrelated sessions must not be taken over');

  console.log('runtime status takeover: passed');
}

main().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
