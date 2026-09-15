/**
 * Node assertions for the dock engine. The engine files are written for the
 * browser bundle (shared-scope concatenation, no modules), so this runner
 * evaluates them in a `node:vm` context — the same way the app concatenates
 * them — and then exercises the pure functions without a browser.
 *
 * Run: node tests/dock-engine.test.mjs
 */
// Loose asserts on purpose: the engine lives in a vm realm, so its plain
// objects do not share this realm's prototypes. `node:assert` (non-strict)
// compares structurally instead.
import assert from 'node:assert';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import vm from 'node:vm';

const here = dirname(fileURLToPath(import.meta.url));
const engineDir = join(here, '..', 'src', 'app', 'modules', 'dock', 'engine');
const FILES = [
    'types.js',
    'tree.js',
    'constraints.js',
    'geometry.js',
    'operations.js',
    'planner.js',
    'sequence.js',
    'controller.js',
];

const GLUE = `
globalThis.__dockApi = {
    DOCK_PANE_PREFIX, DOCK_SPLIT_PREFIX, DOCK_TAB_PREFIX, DOCK_FLOAT_PREFIX,
    dockCreateMinter, dockIsPaneNode, dockIsSplitNode, dockAssertNever,
    dockGetNode, dockGetPane, dockGetSplit, dockGetTab, dockFloatRect, dockFloatIndex,
    dockOnlyTabId, dockFindParent, dockFindTabPane, dockPaneIds, dockNormalizeSizes,
    dockWithNodes, dockWithTabs, dockInsertAt, dockRemoveAt, dockNeighbourTabId,
    dockPaneWithTabs, dockReplaceInParent, dockFirstPaneId, dockTopRightPaneId,
    DOCK_MAX_PANES, DOCK_MIN_PANE_FRACTION, DOCK_FLOAT_DEFAULT_SIZE, DOCK_FLOAT_MIN_SIZE,
    DOCK_EDGE_FRACTION, DOCK_ZONES, dockPaneCount, dockCanSplit, dockZoneAt, dockZoneSplit,
    dockClampSizes,
    dockContainsPoint, dockZoneInRect, dockInsertionIndex, DOCK_SPLIT_MINIMUMS, dockHalvesFit,
    DOCK_DRAG_THRESHOLD, dockPassedThreshold, dockDividerSizes, dockMovedRect, dockResizedRect,
    dockFloatRectAt,
    dockApplyOp, dockReplay,
    dockFindPaneContentTab, dockFindContentTab, dockActiveDockPaneId, dockPlanSetExpanded,
    dockPlanSetMode, dockPlanSplitPane, dockPlanAddTab, dockPlanOpenContent, dockPlanDuplicateTab,
    dockPlanPlaceTab, dockPlanDropTab, dockPlanFloatTab, dockPlanUnfloatPane, dockPlanResizeSplit,
    dockPlanSettle,
    dockIsFocusOp, dockCanStepBack, dockCanStepForward, dockRecordedOps, dockRecord, dockStepBack,
    dockStepForward, DOCK_EMPTY_HISTORY, DockSequencer,
    dockCreateInitialState, DockController,
};
`;

const source = FILES.map((file) => readFileSync(join(engineDir, file), 'utf8')).join('\n\n') + '\n\n' + GLUE;
const context = vm.createContext({ console });
vm.runInContext(source, context);
const api = context.__dockApi;

// ── helpers ──────────────────────────────────────────────────────────────────
const mint = () => api.dockCreateMinter(0);

// Small helper: exercise setMode through the planner to keep sequences honest.
api.dockPlanModeSafe = (state) => api.dockPlanSetMode(state, state.mode === 'push' ? 'fullscreen' : 'push');

function surfaceWithTab(title) {
    const share = api.dockCreateMinter(0);
    const state = api.dockCreateInitialState(share, (id) => ({ id, kind: 'conversation', contentId: 's-1', title: title || 'S' }));
    return { mint: share, state };
}

let passed = 0;
function test(name, fn) {
    try {
        fn();
        passed += 1;
        console.log('  ok  ' + name);
    } catch (error) {
        console.error('FAIL  ' + name);
        console.error('      ' + (error && error.stack ? error.stack.split('\n').slice(0, 4).join('\n      ') : error));
        process.exitCode = 1;
    }
}

// ── model + ids ──────────────────────────────────────────────────────────────
test('initial state: collapsed, single docked pane, minted ids carry prefixes', () => {
    const { state } = surfaceWithTab();
    assert.equal(state.expanded, false);
    assert.equal(state.mode, 'push');
    const ids = api.dockPaneIds(state);
    assert.equal(ids.length, 1);
    assert.equal(ids[0], state.rootId);
    assert.ok(ids[0].startsWith(api.DOCK_PANE_PREFIX));
    assert.ok(state.tabs[state.nodes[ids[0]].activeTabId].id.startsWith(api.DOCK_TAB_PREFIX));
    assert.equal(state.floats.length, 0);
});

test('readers throw on dangling ids', () => {
    const { state } = surfaceWithTab();
    assert.throws(() => api.dockGetNode(state, 'pane-999'));
    assert.throws(() => api.dockGetSplit(state, state.rootId));
    assert.throws(() => api.dockGetTab(state, 'tab-999'));
});

// ── operations: split / merge / inverse ──────────────────────────────────────
test('split creates an equal sibling and its inverse restores the exact tree', () => {
    const { mint: share, state } = surfaceWithTab();
    const ops = api.dockPlanSplitPane(state, share, state.rootId);
    assert.equal(ops.length, 1, 'without a pane factory there is nothing to seed');
    const seeded = api.dockPlanSplitPane(state, share, state.rootId, (id) => ({ id, kind: 'conversation', contentId: 's-1', title: 'Seed' }));
    assert.equal(seeded.length, 2, 'the seed is its own operation inside the same intent');
    const after = api.dockReplay(state, ops);
    assert.equal(api.dockPaneIds(after).length, 2);
    const split = api.dockGetSplit(after, after.rootId);
    assert.deepEqual(split.sizes, [0.5, 0.5]);
    // One intent, one entry; stepping back restores the original tree exactly.
    const recorded = api.dockRecord(api.DOCK_EMPTY_HISTORY, state, ops);
    const back = api.dockStepBack(recorded.history, recorded.state);
    assert.deepEqual(back.state, state);
    // And redo replays to the same ids without minting during apply.
    const forward = api.dockStepForward(back.history, back.state);
    assert.deepEqual(forward.state, after);
});

test('applyOp(split) inverse is merge + resize and reverts sizes', () => {
    const { mint: share, state } = surfaceWithTab();
    const first = api.dockPlanSplitPane(state, share, state.rootId);
    const two = api.dockReplay(state, first);
    const wide = api.dockReplay(two, [{ type: 'resize', splitId: two.rootId, sizes: [0.7, 0.3] }]);
    const second = api.dockPlanSplitPane(wide, share, api.dockPaneIds(wide)[0]);
    let current = wide;
    const inverse = [];
    for (const op of second) {
        const result = api.dockApplyOp(current, op);
        current = result.state;
        for (let i = result.inverse.length - 1; i >= 0; i -= 1) inverse.unshift(result.inverse[i]);
    }
    assert.equal(api.dockPaneIds(current).length, 3);
    let reverted = current;
    for (const op of inverse) reverted = api.dockApplyOp(reverted, op).state;
    assert.deepEqual(reverted, wide);
});

test('normalizeSizes keeps an already-normalized list byte-identical', () => {
    assert.deepEqual(api.dockNormalizeSizes([0.5, 0.5]), [0.5, 0.5]);
    assert.deepEqual(api.dockNormalizeSizes([2, 2]), [0.5, 0.5]);
    assert.throws(() => api.dockNormalizeSizes([0, 0]));
});

// ── planner: open / place / drop ─────────────────────────────────────────────
test('planOpenContent dedupes by (kind, contentId) and focus-only updates are empty', () => {
    const { mint: share, state } = surfaceWithTab();
    const first = api.dockPlanOpenContent(state, share, { kind: 'conversation', contentId: 's-2', title: 'Second' });
    const two = api.dockReplay(state, first.ops);
    const again = api.dockPlanOpenContent(two, share, { kind: 'conversation', contentId: 's-2', title: 'Second' });
    assert.deepEqual(again.ops, [{ type: 'focusTab', tabId: first.tabId }]);
    assert.equal(again.tabId, first.tabId);
    const forced = api.dockPlanOpenContent(two, share, { kind: 'conversation', contentId: 's-2', title: 'Second', revealIfOpened: false });
    assert.equal(forced.ops[0].type, 'openTab');
    assert.notEqual(forced.tabId, first.tabId);
});

test('planPlaceTab converts the caret over the dragged chip', () => {
    const { mint: share, state } = surfaceWithTab();
    const second = api.dockPlanOpenContent(state, share, { kind: 'conversation', contentId: 's-2', title: 'B' });
    const two = api.dockReplay(state, second.ops);
    const paneId = two.rootId;
    const tabs = two.nodes[paneId].tabs;
    const dragId = tabs[0];
    // Caret past its own chip (index = own index + 1) is where it already sits.
    assert.deepEqual(api.dockPlanPlaceTab(two, dragId, paneId, 1), []);
    // Caret at the end moves it after the second chip.
    const moved = api.dockPlanPlaceTab(two, dragId, paneId, 2);
    assert.deepEqual(moved, [{ type: 'reorderTab', tabId: dragId, index: 1 }]);
    const after = api.dockReplay(two, moved);
    assert.deepEqual(after.nodes[paneId].tabs, [tabs[1], tabs[0]]);
});

test('a pane\'s only tab released on its own centre changes nothing', () => {
    const { mint: share, state } = surfaceWithTab();
    assert.deepEqual(api.dockPlanDropTab(state, share, state.nodes[state.rootId].tabs[0], state.rootId, 'center'), []);
});

test('a sole tab released on its own edge splits and the factory backfills the vacated pane', () => {
    const { mint: share, state } = surfaceWithTab();
    const tabId = state.nodes[state.rootId].tabs[0];
    const backfill = (id) => ({ id, kind: 'conversation', contentId: 's-1', title: 'Backfill' });
    const ops = api.dockPlanDropTab(state, share, tabId, state.rootId, 'right', backfill);
    assert.equal(ops.length, 3);
    const after = api.dockReplay(state, ops);
    assert.equal(api.dockPaneIds(after).length, 2);
    // Both halves hold a conversation; the dragged tab ended focused in the new half.
    const draggedPane = api.dockFindTabPane(after, tabId);
    assert.equal(after.activePaneId, draggedPane.id);
    const other = api.dockPaneIds(after).find((id) => id !== draggedPane.id);
    assert.equal(after.nodes[other].tabs.length, 1);
    // Without a factory, the same release changes nothing.
    assert.deepEqual(api.dockPlanDropTab(state, share, tabId, state.rootId, 'right'), []);
});

// ── settle ───────────────────────────────────────────────────────────────────
test('planSettle merges emptied side panes and reseeds an emptied root', () => {
    const { mint: share, state } = surfaceWithTab();
    const seed = (id) => ({ id, kind: 'conversation', contentId: 's-1', title: 'Seed' });
    const split = api.dockPlanSplitPane(state, share, state.rootId, seed);
    const two = api.dockReplay(state, split);
    const left = api.dockPaneIds(two)[0];
    const leftTab = two.nodes[left].tabs[0];
    const closed = api.dockReplay(two, [{ type: 'closeTab', tabId: leftTab }]);
    const settled = api.dockPlanSettle(closed, share, seed);
    const after = api.dockReplay(closed, settled);
    assert.equal(api.dockPaneIds(after).length, 1);
    assert.equal(after.nodes[after.rootId].tabs.length, 1);
    // Both panes emptied: the settle merges one away and reseeds the surviving root.
    const right = api.dockPaneIds(two)[1];
    const aloneClosed = api.dockReplay(two, [
        { type: 'closeTab', tabId: two.nodes[left].tabs[0] },
        { type: 'closeTab', tabId: two.nodes[right].tabs[0] },
    ]);
    assert.equal(api.dockPaneIds(aloneClosed).length, 2);
    const reseeded = api.dockReplay(aloneClosed, api.dockPlanSettle(aloneClosed, share, seed));
    assert.equal(api.dockPaneIds(reseeded).length, 1);
    assert.equal(reseeded.nodes[reseeded.rootId].tabs.length, 1);
});

// ── float ────────────────────────────────────────────────────────────────────
test('planFloatTab cascades and unfloat returns the tab to the docked pane', () => {
    const { mint: share, state } = surfaceWithTab();
    const tabId = state.nodes[state.rootId].tabs[0];
    const first = api.dockPlanFloatTab(state, share, tabId);
    const floated = api.dockReplay(state, first.ops);
    assert.equal(floated.floats.length, 1);
    assert.deepEqual(api.dockFloatRect(floated.nodes[first.paneId]), { x: 160, y: 120, width: 380, height: 300 });
    const secondTab = api.dockPlanOpenContent(floated, share, { kind: 'conversation', contentId: 's-9', title: 'Nine' });
    const two = api.dockReplay(floated, secondTab.ops);
    const secondFloat = api.dockPlanFloatTab(two, share, secondTab.tabId);
    const both = api.dockReplay(two, secondFloat.ops);
    assert.deepEqual(api.dockFloatRect(both.nodes[secondFloat.paneId]), { x: 184, y: 144, width: 380, height: 300 });
    const back = api.dockReplay(both, api.dockPlanUnfloatPane(both, secondFloat.paneId));
    assert.equal(back.floats.length, 1);
    assert.equal(api.dockPaneIds(back).length, 1);
    assert.ok(back.nodes[back.rootId].tabs.length >= 1);
});

test('floating panes do not count against the docked pane budget', () => {
    const { mint: share, state } = surfaceWithTab();
    let current = state;
    const tabIds = [];
    for (let i = 0; i < 4; i += 1) {
        const opened = api.dockPlanOpenContent(current, share, { kind: 'conversation', contentId: 's-' + (10 + i), title: 'T' + i });
        current = api.dockReplay(current, opened.ops);
        tabIds.push(opened.tabId);
    }
    for (const tabId of tabIds) {
        const planned = api.dockPlanFloatTab(current, share, tabId);
        current = api.dockReplay(current, planned.ops);
    }
    assert.equal(current.floats.length, 4);
    assert.equal(api.dockPaneCount(current), 1);
    assert.equal(api.dockCanSplit(current), true);
});

// ── history ──────────────────────────────────────────────────────────────────
test('records one entry per intent and drops the redo branch on a new record', () => {
    const { mint: share, state } = surfaceWithTab();
    let history = api.DOCK_EMPTY_HISTORY;
    let current = state;
    const stepped = api.dockRecord(history, current, api.dockPlanSplitPane(current, share, current.rootId));
    history = stepped.history;
    current = stepped.state;
    assert.equal(history.entries.length, 1);
    assert.equal(history.cursor, 1);
    const back = api.dockStepBack(history, current);
    assert.equal(api.dockCanStepForward(back.history), true);
    const recordAfterUndo = api.dockRecord(back.history, back.state, api.dockPlanSetExpanded(back.state, true));
    assert.equal(api.dockCanStepForward(recordAfterUndo.history), false);
    assert.equal(recordAfterUndo.history.entries.length, 1);
});

test('a run of consecutive focus-only intents steps as one', () => {
    const { mint: share, state } = surfaceWithTab();
    let history = api.DOCK_EMPTY_HISTORY;
    let current = state;
    const withSplit = api.dockRecord(
        history,
        current,
        api.dockPlanSplitPane(current, share, current.rootId, (id) => ({ id, kind: 'conversation', contentId: 's-2', title: 'Two' }))
    );
    history = withSplit.history;
    current = withSplit.state;
    const ids = api.dockPaneIds(current);
    const focusA = api.dockRecord(history, current, [{ type: 'focusPane', paneId: ids[0] }]);
    const focusB = api.dockRecord(focusA.history, focusA.state, [{ type: 'focusTab', tabId: current.nodes[ids[1]].tabs[0] }]);
    assert.ok(api.dockIsFocusOp({ type: 'focusPane' }));
    const back = api.dockStepBack(focusB.history, focusB.state);
    assert.equal(back.history.cursor, 1);
    assert.deepEqual(back.state.activePaneId, withSplit.state.activePaneId);
});

test('replay determinism: same initial state + same sequence reproduce the same ids', () => {
    const { mint: share, state } = surfaceWithTab();
    const ops = [];
    let current = state;
    const push = (planned) => {
        const list = Array.isArray(planned) ? planned : planned.ops;
        for (const op of list) {
            ops.push(op);
            current = api.dockApplyOp(current, op).state;
        }
    };
    push(api.dockPlanSplitPane(state, share, state.rootId, (id) => ({ id, kind: 'conversation', contentId: 's-1', title: 'Seed' })));
    push(api.dockPlanOpenContent(current, share, { kind: 'conversation', contentId: 's-2', title: 'Two' }));
    push(api.dockPlanOpenContent(current, share, { kind: 'conversation', contentId: 's-3', title: 'Three' }));
    const firstPane = api.dockPaneIds(current)[0];
    push(api.dockPlanPlaceTab(current, current.nodes[firstPane].tabs[0], api.dockPaneIds(current)[1], 0));
    push(api.dockPlanSetExpanded(current, true));
    push(api.dockPlanModeSafe(current));
    const replayed = api.dockReplay(state, ops);
    assert.deepEqual(replayed, current);
    // Ids are part of the equality: replaying in a fresh context would build the same id strings.
    assert.equal(JSON.stringify(replayed).includes('pane-'), true);
});

// ── constraints / geometry ───────────────────────────────────────────────────
test('dockZoneAt picks the nearest edge band, else centre', () => {
    assert.equal(api.dockZoneAt(0.1, 0.5), 'left');
    assert.equal(api.dockZoneAt(0.9, 0.5), 'right');
    assert.equal(api.dockZoneAt(0.5, 0.05), 'top');
    assert.equal(api.dockZoneAt(0.5, 0.95), 'bottom');
    assert.equal(api.dockZoneAt(0.5, 0.5), 'center');
    assert.deepEqual(api.dockZoneSplit('left'), { axis: 'row', direction: 'before' });
    assert.equal(api.dockZoneSplit('center'), undefined);
});

test('dockClampSizes pins shares at the floor and renormalizes to 1', () => {
    const clamped = api.dockClampSizes([0.05, 0.45, 0.5], 0.12);
    assert.equal(clamped.length, 3);
    const sum = clamped.reduce((total, size) => total + size, 0);
    assert.ok(Math.abs(sum - 1) < 1e-12);
    assert.ok(clamped.every((size) => size >= 0.12 - 1e-12));
    assert.ok(Math.abs(clamped[0] - 0.12) < 1e-12);
    // Extreme drags cannot drive every share to the floor.
    const desperate = api.dockClampSizes([0, 1, 0], 0.12);
    assert.ok(Math.abs(desperate.reduce((t, s) => t + s, 0) - 1) < 1e-12);
    assert.ok(desperate.every((size) => size >= 0.12 - 1e-12));
});

test('dividerSizes moves only the two neighbours', () => {
    const near = (actual, expected) => actual.forEach((value, index) => {
        assert.ok(Math.abs(value - expected[index]) < 1e-12, `index ${index}: ${value} !== ${expected[index]}`);
    });
    near(api.dockDividerSizes([0.2, 0.3, 0.5], 0, 0.1), [0.3, 0.2, 0.5]);
    near(api.dockDividerSizes([0.5, 0.5, 0.5], 1, -0.2), [0.5, 0.3, 0.7]);
});

test('dockInsertionIndex returns the caret slot between chip midpoints', () => {
    const rects = [{ x: 0, width: 100 }, { x: 100, width: 100 }];
    assert.equal(api.dockInsertionIndex(rects, 20), 0);
    assert.equal(api.dockInsertionIndex(rects, 51), 1);
    assert.equal(api.dockInsertionIndex(rects, 151), 2);
    assert.equal(api.dockInsertionIndex(rects, 999), 2);
});

test('dockHalvesFit blocks a narrow pane and lets an unmeasured one pass', () => {
    const wide = api.dockHalvesFit({
        pane: { x: 0, y: 0, width: 800, height: 400 },
        strip: { x: 0, y: 0, width: 798, height: 34 },
        chipsWidth: 200,
        fillWidth: 300,
        splitControlWidth: 32,
    });
    assert.equal(wide.row, true);
    assert.equal(wide.column, true);
    const narrow = api.dockHalvesFit({
        pane: { x: 0, y: 0, width: 300, height: 400 },
        strip: { x: 0, y: 0, width: 298, height: 34 },
        chipsWidth: 120,
        fillWidth: 20,
        splitControlWidth: 32,
    });
    assert.equal(narrow.row, false);
    const unmeasured = api.dockHalvesFit({ pane: { width: 0, height: 0 }, strip: { width: 0, height: 0 }, chipsWidth: 0, fillWidth: 0 });
    assert.deepEqual(unmeasured, { row: true, column: true });
    const short = api.dockHalvesFit({
        pane: { x: 0, y: 0, width: 800, height: 90 },
        strip: { x: 0, y: 0, width: 798, height: 34 },
        chipsWidth: 200,
        fillWidth: 300,
    });
    assert.equal(short.column, false);
});

test('passedThreshold is the 4px drag gate', () => {
    assert.equal(api.dockPassedThreshold(10, 10, 10, 13), false);
    assert.equal(api.dockPassedThreshold(10, 10, 14, 10), true);
    assert.equal(api.DOCK_DRAG_THRESHOLD, 4);
});

// ── controller ───────────────────────────────────────────────────────────────
test('DockController records intents, notifies once, and steps focus runs as one', () => {
    const controller = new api.DockController({
        makeInitialTab: (id) => ({ id, kind: 'conversation', contentId: 's-1', title: 'One' }),
        makePaneTab: (id) => ({ id, kind: 'conversation', contentId: 's-2', title: 'Two' }),
    });
    let notifications = 0;
    const dispose = controller.subscribe(() => { notifications += 1; });
    controller.splitPane();
    assert.equal(notifications, 1);
    const first = controller.getSnapshot();
    assert.equal(first.state.expanded, false);
    assert.equal(api.dockPaneIds(first.state).length, 2);
    controller.focusPane(api.dockPaneIds(first.state)[0]);
    controller.focusPane(api.dockPaneIds(first.state)[1]);
    assert.equal(notifications, 3);
    assert.equal(controller.undo(), true);
    assert.equal(notifications, 4);
    assert.equal(controller.getSnapshot().cursor, 1);
    assert.equal(controller.getSnapshot().canSplit, true);
    dispose();
    controller.splitPane();
    assert.equal(notifications, 4, 'disposed listener no longer notified');
});

test('a planner that plans nothing records nothing and notifies nobody', () => {
    const controller = new api.DockController();
    let notifications = 0;
    controller.subscribe(() => { notifications += 1; });
    controller.setExpanded(false); // already collapsed
    assert.equal(notifications, 0);
    assert.equal(controller.ops.length, 0);
    controller.setExpanded(true);
    assert.equal(notifications, 1);
    controller.setExpanded(true);
    assert.equal(notifications, 1);
});

test('undo restores the exact previous state object shape after several intents', () => {
    const controller = new api.DockController({
        makeInitialTab: (id) => ({ id, kind: 'conversation', contentId: 's-1', title: 'One' }),
    });
    const original = controller.getSnapshot().state;
    controller.setExpanded(true);
    controller.splitPane();
    controller.setMode('fullscreen');
    assert.equal(controller.undo(), true);
    assert.equal(controller.getSnapshot().state.mode, 'push');
    assert.equal(controller.undo(), true);
    assert.equal(api.dockPaneIds(controller.getSnapshot().state).length, 1);
    assert.equal(controller.undo(), true);
    assert.deepEqual(controller.getSnapshot().state, original);
    assert.equal(controller.undo(), false);
});

console.log('\n' + passed + ' checks passed' + (process.exitCode ? ' — WITH FAILURES' : ''));
