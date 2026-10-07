import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const sourceUrl = new URL('../../plugins/change-review/web/change-review.js', import.meta.url);
const source = await readFile(sourceUrl, 'utf8');
const moduleUrl = `data:text/javascript;base64,${Buffer.from(source).toString('base64')}`;
const { stats, hasLineStats, acceptChangeUpdate, splitReviewRows,
    workspaceReviewKey, mergeReviewChanges, reviewUpdatesForTool } = await import(moduleUrl);

const scope = {run_id:'run', react_iter:2, stream_seq:4, tool_call_id:'same-call'};
assert.notEqual(workspaceReviewKey(scope), workspaceReviewKey({...scope, run_id:'other-run'}));
assert.notEqual(workspaceReviewKey(scope), workspaceReviewKey({...scope, react_iter:3}));
assert.notEqual(workspaceReviewKey(scope), workspaceReviewKey({...scope, stream_seq:5}));
const scopedUpdates = new Map([[workspaceReviewKey(scope), [{path:'scope.txt', snapshot_id:'scope', revision:1}]]]);
assert.equal(reviewUpdatesForTool(scope, null, scopedUpdates).length, 1);
assert.deepEqual(reviewUpdatesForTool({...scope, stream_seq:5}, null, scopedUpdates), []);
assert.equal(reviewUpdatesForTool({tool_call_id:'same-call'},
    {dataset:{runId:'run', reactIter:'2'}}, scopedUpdates).length, 1);
assert.deepEqual(reviewUpdatesForTool({tool_call_id:'same-call'},
    {dataset:{runId:'other-run', reactIter:'2'}}, scopedUpdates), []);
assert.deepEqual(reviewUpdatesForTool({tool_call_id:'same-call'},
    {dataset:{runId:'run', reactIter:'3'}}, scopedUpdates), []);
assert.deepEqual(reviewUpdatesForTool({tool_call_id:'same-call'}, null, scopedUpdates), []);
scopedUpdates.set(workspaceReviewKey({...scope, stream_seq:5}), [{path:'other-stream.txt', snapshot_id:'other'}]);
assert.deepEqual(reviewUpdatesForTool({tool_call_id:'same-call'},
    {dataset:{runId:'run', reactIter:'2'}}, scopedUpdates), []); // Ambiguous old hydration must not guess.
assert.deepEqual(mergeReviewChanges(
    [{path:'a.txt', snapshot_id:'a', revision:2, effective:true}],
    [{path:'a.txt', snapshot_id:'a', revision:3, effective:false},
     {path:'b.txt', snapshot_id:'b', revision:1}]),
    [{path:'a.txt', snapshot_id:'a', revision:3, effective:false},
     {path:'b.txt', snapshot_id:'b', revision:1}]);
assert.equal(mergeReviewChanges(
    [{path:'a.txt', snapshot_id:'a', revision:3}],
    [{path:'a.txt', snapshot_id:'a', revision:2}])[0].revision, 3);

// A null added/removed pair must count as "not measured", not as zero.
assert.equal(hasLineStats({ added: null, removed: null }), false);
assert.equal(hasLineStats({ added: null, removed: 0 }), false);
assert.equal(hasLineStats({ added: 0, removed: 0 }), true);
assert.equal(hasLineStats({ added: 3, removed: 1 }), true);

assert.deepEqual(
    stats([{ added: 3, removed: 1 }, { added: 0, removed: 0 }]),
    { added: 3, removed: 1, omitted: 0, reasons: {} },
);

// Binary / oversized / complex / missing-baseline rows are omitted with a
// reason breakdown instead of silently contributing "0" lines.
const mixed = stats([
    { added: 3, removed: 1 },
    { added: null, removed: null, diff_omitted_reason: 'binary' },
    { added: null, removed: null, diff_omitted_reason: 'too_large_bytes' },
    { added: null, removed: null, diff_omitted_reason: 'snapshot_missing' },
    { added: null, removed: null, diff_omitted_reason: 'too_complex' },
    // A directory row carries explicit zeroes and must stay out of "omitted".
    { added: 0, removed: 0, diff_omitted_reason: 'directory' },
]);
assert.equal(mixed.added, 3);
assert.equal(mixed.removed, 1);
assert.equal(mixed.omitted, 4);
assert.deepEqual(mixed.reasons, {
    binary: 1, too_large_bytes: 1, snapshot_missing: 1, too_complex: 1,
});

// A newer run's record (lower revision, new snapshot) must replace the old
// one; only a stale event for the same snapshot may be ignored.
assert.equal(acceptChangeUpdate(null, { snapshot_id: 'a', revision: 1 }), true);
assert.equal(acceptChangeUpdate(
    { snapshot_id: 'a', revision: 2 }, { snapshot_id: 'a', revision: 1 }), false);
assert.equal(acceptChangeUpdate(
    { snapshot_id: 'a', revision: 1 }, { snapshot_id: 'a', revision: 2 }), true);
assert.equal(acceptChangeUpdate(
    { snapshot_id: 'a', revision: 2 }, { snapshot_id: 'b', revision: 1 }), true);

// Reverted rows split away from active rows so the panel can offer restore.
const split = splitReviewRows([
    { snapshot_id: 'a', reverted: false },
    { snapshot_id: 'b', reverted: true },
    { snapshot_id: 'c' },
]);
assert.deepEqual(split.active.map(row => row.snapshot_id), ['a', 'c']);
assert.deepEqual(split.reverted.map(row => row.snapshot_id), ['b']);
assert.deepEqual(splitReviewRows(null), { active: [], reverted: [] });

// Exercise the actual event handler and application path: supplemental replay
// can precede lazy tool-row hydration, and session switches clear its cache.
const testSource = source + '\nexport {onUiEvent, applyTool, resetForSession, changesOf};'
    + '\nexport function initializeHarness() { drawer = {}; bar = {}; }';
const replay = await import(`data:text/javascript;base64,${Buffer.from(testSource).toString('base64')}`);
const element = () => ({dataset:{}, classList:{contains:() => false},
    setAttribute(){}, addEventListener(){}, replaceChildren(){}, append(){}, appendChild(){},
    querySelector:() => null, querySelectorAll:() => []});
const stream = {...element(), id:'chat-stream', dataset:{sessionId:'session'}};
const aggregate = {...element(), isConnected:true,
    closest:selector => selector === '.chat-stream' ? stream : null};
globalThis.document = {documentElement:{lang:'zh'},
    getElementById:id => id === 'chat-stream' ? stream : null,
    querySelector:() => null, createElement:element, createTextNode:text => ({textContent:text})};
const realSetTimeout = globalThis.setTimeout;
const realClearTimeout = globalThis.clearTimeout;
globalThis.setTimeout = () => 123;
globalThis.clearTimeout = () => {};
try {
    replay.initializeHarness();
    replay.resetForSession('session');
    replay.onUiEvent({rootSessionId:'session', event:{...scope, type:'file_changes_updated',
        session_id:'child-session', changes:[{path:'replayed.txt', snapshot_id:'replay', revision:2, turn_id:'turn', added:1, removed:0}]}});
    const lazyDetail = {event:{tool_call_id:'same-call'},
        row:{dataset:{runId:'run', reactIter:'2'}}, aggregate, sessionId:'session', rootSessionId:'session'};
    assert.equal(replay.applyTool(lazyDetail, {deferRender:true}), true);
    assert.equal(replay.changesOf(aggregate).get('replayed.txt').revision, 2);
    assert.equal(replay.changesOf(aggregate).get('replayed.txt')._sessionId, 'child-session');
    replay.onUiEvent({rootSessionId:'session', event:{...scope, type:'file_changes_updated',
        changes:[{path:'replayed.txt', snapshot_id:'replay', revision:1}]}});
    replay.applyTool(lazyDetail, {deferRender:true});
    assert.equal(replay.changesOf(aggregate).get('replayed.txt').revision, 2);
    assert.equal(replay.applyTool({...lazyDetail, row:{dataset:{runId:'different', reactIter:'2'}}}, {deferRender:true}), false);
    replay.resetForSession('other-session');
    replay.onUiEvent({rootSessionId:'session', event:{...scope, type:'file_changes_updated',
        changes:[{path:'wrong.txt', snapshot_id:'wrong'}]}});
    assert.equal(replay.applyTool(lazyDetail, {deferRender:true}), false);
} finally {
    globalThis.setTimeout = realSetTimeout;
    globalThis.clearTimeout = realClearTimeout;
    delete globalThis.document;
}

console.log('change review stats runtime checks passed');
