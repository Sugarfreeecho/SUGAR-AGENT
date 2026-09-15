/**
 * Dock layout model — types, id minting, and structural predicates.
 *
 * Mirrors dsh's `ui-dockkit/src/contract/types.ts`: a normalized recursive
 * split tree. `nodes` holds every split and pane keyed by id; `rootId` names
 * the docked root; `floats` lists floating panes bottom-to-top. A floating
 * panel is not a second concept — it is a pane whose `host` is 'float',
 * capacity 1 tab, drawn without a tab strip.
 *
 *   LayoutState = {
 *     nodes:  { [id]: SplitNode | PaneNode },
 *     tabs:   { [id]: TabRecord },
 *     rootId, floats: [], activePaneId, expanded, mode,
 *   }
 *   SplitNode = { kind:'split', id, axis:'row'|'column', children:[], sizes:[] }
 *   PaneNode  = { kind:'pane', id, host:'dock'|'float', tabs:[], activeTabId, rect? }
 *   TabRecord = { id, kind, contentId, title }   // kind is opaque to the engine
 *
 * Ids are branded by convention: `pane-…`, `split-…`, `tab-…`, `float-…` are
 * minted only by a minter, so a pane id, a split id, and a tab id never stand
 * in for one another. Every writer returns a new state and keeps untouched
 * nodes at their old identity, so consumers can compare by reference.
 *
 * This file is part of the shared-scope bundle: no modules, no DOM, no host
 * concepts. It can also be evaluated standalone under node:vm (see
 * frontend/tests/dock-engine.test.mjs).
 */

/** Prefix under which docked pane ids are minted. */
const DOCK_PANE_PREFIX = 'pane-';

/** Prefix under which floating pane ids are minted. */
const DOCK_FLOAT_PREFIX = 'float-';

/** Prefix under which split node ids are minted. */
const DOCK_SPLIT_PREFIX = 'split-';

/** Prefix under which tab ids are minted. */
const DOCK_TAB_PREFIX = 'tab-';

/**
 * Create an id source. One instance belongs to one surface's sequence, so the
 * counter (and the ids built from it) are part of what a recorded surface
 * carries forward for replay.
 * @param {number} seed Number the first id counts from; defaults to 0.
 * @returns {{ next: (prefix: string) => string }} the monotonic mint.
 */
function dockCreateMinter(seed) {
    let counter = Number.isFinite(Number(seed)) ? Math.floor(Number(seed)) : 0;
    return {
        next(prefix) {
            counter += 1;
            return String(prefix) + counter;
        },
        used() {
            return counter;
        },
    };
}

/** Whether a node is a pane. @param {*} node Candidate. @returns {boolean} */
function dockIsPaneNode(node) {
    return !!node && node.kind === 'pane';
}

/** Whether a node is a split. @param {*} node Candidate. @returns {boolean} */
function dockIsSplitNode(node) {
    return !!node && node.kind === 'split';
}

/**
 * Reject an unhandled discriminant at the end of a closed switch.
 * @param {never} value The discriminant the switch did not handle.
 * @param {string} what The union being switched on, for the message.
 * @throws {Error} always.
 */
function dockAssertNever(value, what) {
    throw new Error(what + ': unhandled ' + JSON.stringify(value));
}
