const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const root = path.resolve(__dirname, '..', '..');
const scrollSource = fs.readFileSync(
  path.join(root, 'frontend', 'src', 'app', 'modules', 'session-scroll-history.js'),
  'utf8',
);
const renderingSource = fs.readFileSync(
  path.join(root, 'frontend', 'src', 'app', 'modules', 'message-rendering.js'),
  'utf8',
);

function between(source, startMarker, endMarker) {
  const start = source.indexOf(startMarker);
  const end = source.indexOf(endMarker, start);
  assert(start >= 0 && end > start, `missing source section: ${startMarker}`);
  return source.slice(start, end);
}

function makeRow(attrs) {
  return {
    attrs: Object.assign({}, attrs),
    removed: false,
    getAttribute(name) { return this.attrs[name] == null ? null : String(this.attrs[name]); },
    remove() { this.removed = true; },
  };
}

function testAbortCleanupKeepsCommittedRows() {
  const live = makeRow({
    'data-llm-live-row': '1',
    'data-react-iter': '2',
    'data-react-generation': '1',
    'data-run-id': 'run-1',
  });
  const committedLlm = makeRow({
    'data-event-committed': '1',
    'data-react-iter': '2',
    'data-react-generation': '1',
    'data-run-id': 'run-1',
  });
  const pendingTool = makeRow({
    'data-tool-pending': '1',
    'data-react-iter': '2',
    'data-react-generation': '1',
    'data-run-id': 'run-1',
  });
  const committedTool = makeRow({
    'data-event-committed': '1',
    'data-react-iter': '2',
    'data-react-generation': '1',
    'data-run-id': 'run-1',
  });
  const otherGenerationLive = makeRow({
    'data-llm-live-row': '1',
    'data-react-iter': '2',
    'data-react-generation': '0',
    'data-run-id': 'run-1',
  });
  const rows = [live, committedLlm, pendingTool, committedTool, otherGenerationLive];
  const body = {
    querySelectorAll(selector) {
      if (selector === '.feed-item[data-llm-live-row="1"]') {
        return rows.filter((row) => row.getAttribute('data-llm-live-row') === '1');
      }
      if (selector.includes('data-tool-draft-key') || selector.includes('data-tool-pending')) {
        return rows.filter((row) => (
          row.getAttribute('data-tool-draft-key') != null
          || row.getAttribute('data-tool-pending') === '1'
        ));
      }
      return [];
    },
  };
  const ctx = {
    reactGeneration: 1,
    llm: {},
    currentProcessGroup: { querySelector: () => body },
  };
  const sandbox = vm.createContext({
    console,
    isSubagentStreamCtx: () => false,
    reactGenerationForContext: (value) => Number(value.reactGeneration || 0),
    finalizeLlmStreamChunks() {},
  });
  vm.runInContext(
    between(scrollSource, 'function discardLlmStreamChunks', 'function flushLlmDeltaText'),
    sandbox,
  );
  sandbox.discardLlmStreamChunks(ctx, {
    run_id: 'run-1',
    react_iter: 2,
    react_generation: 1,
    cleanup_scope: 'drafts_only',
  });

  assert.strictEqual(live.removed, true, 'current live LLM row should be removed');
  assert.strictEqual(pendingTool.removed, true, 'current pending tool should be removed');
  assert.strictEqual(committedLlm.removed, false, 'committed LLM row must survive');
  assert.strictEqual(committedTool.removed, false, 'completed tool row must survive');
  assert.strictEqual(otherGenerationLive.removed, false, 'another generation must survive');
}

function testReplayedSnapshotReplacesInsteadOfAppending() {
  const scroller = { isConnected: true, textContent: 'stale partial' };
  const ctx = {
    llm: {
      llmDeltaLastSeq: null,
      llmStreamResponseIter: 1,
      llmStreamResponseScroller: scroller,
      llmPendingResponseDelta: '',
      llmThinkTagMode: 'response',
      llmThinkTagCarry: '',
      llmThinkTagAllowLeading: true,
    },
  };
  const sandbox = vm.createContext({
    console,
    removeTemporaryStatus() {},
    finalizeLlmStreamChunks() {},
    hasSeenStreamDelta: () => false,
    getProcessBody: () => null,
    bumpAggregateMaxReactIter() {},
    feedThinkTaggedResponseDelta: (_state, text) => [{ part: 'response', text }],
    findExistingLlmFeedRow: () => null,
    createProcessFeedRow: () => scroller,
    scheduleLlmDeltaFlush() {},
    truncateLogTextForUi: (text) => String(text),
  });
  vm.runInContext(
    between(renderingSource, 'function appendLlmStreamDelta', 'function upsertLlmFeedRow'),
    sandbox,
  );
  sandbox.appendLlmStreamDelta(ctx, {
    type: 'llm_response_delta',
    delta: 'authoritative snapshot',
    react_iter: 1,
    stream_seq: 3,
    delta_seq: 8,
    replayed_snapshot: true,
  }, 'session-1');
  assert.strictEqual(scroller.textContent, 'authoritative snapshot');

  sandbox.appendLlmStreamDelta(ctx, {
    type: 'llm_response_delta',
    delta: ' + next',
    react_iter: 1,
    stream_seq: 3,
    delta_seq: 9,
  }, 'session-1');
  assert.strictEqual(ctx.llm.llmPendingResponseDelta, ' + next');
}

testAbortCleanupKeepsCommittedRows();
testReplayedSnapshotReplacesInsteadOfAppending();
console.log('interrupt stream runtime checks passed');
