/**
 * The intent layer's stateful embedding: one controller per docking surface,
 * itself the observable source the renderer subscribes to (`subscribe` plus
 * `getSnapshot`, whose reference only changes when the layout does).
 *
 * Every method here is a planner call plus recording plus one notification. The
 * decisions live in planner.js so an embedder holding its layout in an external
 * store shares them rather than reimplementing them; a planner that returns no
 * operations records nothing and notifies nobody.
 *
 * The controller holds no host concepts: what a seeded tab contains arrives as
 * a factory, and a tab's `kind` is an opaque string.
 */

/**
 * The state a surface starts in: collapsed, one docked pane, and whatever tab
 * `makeInitialTab` supplies.
 *
 * The first tab belongs to the initial state rather than to an operation, so
 * expanding and collapsing never accumulates copies of it.
 * @param {{next:Function}} minter Id source this surface's sequence will keep using.
 * @param {Function} [makeInitialTab] Builds the starting tab; omit for an empty pane.
 * @param {string} [mode] Starting presentation; the embedder's product default.
 * @returns {object} the collapsed single-pane starting state.
 */
function dockCreateInitialState(minter, makeInitialTab, mode) {
    const paneId = minter.next(DOCK_PANE_PREFIX);
    const initial = makeInitialTab === undefined ? undefined : makeInitialTab(minter.next(DOCK_TAB_PREFIX));
    const pane = {
        kind: 'pane',
        id: paneId,
        host: 'dock',
        tabs: initial === undefined ? [] : [initial.id],
        activeTabId: initial === undefined ? undefined : initial.id,
        rect: undefined,
    };
    const nodes = {};
    nodes[paneId] = pane;
    const tabs = {};
    if (initial !== undefined) tabs[initial.id] = initial;
    return {
        nodes: nodes,
        tabs: tabs,
        rootId: paneId,
        floats: [],
        activePaneId: paneId,
        expanded: false,
        mode: mode === undefined ? 'push' : mode,
    };
}

/** One docking surface: history, interaction limits, and change notification. */
class DockController {
    /**
     * @param {object} [options] The tab factories this surface seeds panes with.
     * @param {Function} [options.makeInitialTab] Builds the tab the starting pane holds; omit to start empty.
     * @param {Function} [options.makePaneTab] Builds the tab a pane created by `splitPane` holds; omit to leave it empty.
     * @param {string} [options.mode] Starting presentation; defaults to 'push'.
     */
    constructor(options) {
        const config = options || {};
        this.minter = dockCreateMinter(0);
        this.makePaneTab = config.makePaneTab;
        this.sequencer = new DockSequencer(dockCreateInitialState(this.minter, config.makeInitialTab, config.mode));
        this.listeners = [];
        this.snapshot = this.buildSnapshot();
    }

    /**
     * Observe layout changes.
     * @param {Function} listener Called after every committed change.
     * @returns {Function} disposer removing the listener.
     */
    subscribe(listener) {
        this.listeners.push(listener);
        return () => {
            const index = this.listeners.indexOf(listener);
            if (index >= 0) this.listeners.splice(index, 1);
        };
    }

    /** Current snapshot; the same reference until the layout changes. @returns {object} */
    getSnapshot() {
        return this.snapshot;
    }

    /** Recorded sequence, for tests and the operation readout. @returns {object[]} */
    get ops() {
        return this.sequencer.ops;
    }

    buildSnapshot() {
        const state = this.sequencer.state;
        return {
            state: state,
            canUndo: this.sequencer.canUndo,
            canRedo: this.sequencer.canRedo,
            canSplit: dockCanSplit(state),
            opCount: this.sequencer.ops.length,
            cursor: this.sequencer.cursor,
        };
    }

    commit() {
        this.snapshot = this.buildSnapshot();
        const listeners = this.listeners.slice();
        for (let i = 0; i < listeners.length; i += 1) listeners[i]();
    }

    get state() {
        return this.sequencer.state;
    }

    /** Record a planned intent as one history entry. @returns {boolean} whether anything was recorded. */
    run(ops) {
        if (ops.length === 0) return false;
        this.sequencer.dispatchAll(ops);
        this.commit();
        return true;
    }

    /** Expand or collapse the docked area. Floating panels are unaffected. */
    setExpanded(expanded) {
        this.run(dockPlanSetExpanded(this.state, expanded));
    }

    /** Flip the docked area between expanded and collapsed. */
    toggleExpanded() {
        this.setExpanded(!this.state.expanded);
    }

    /** Switch how the docked area is presented. */
    setMode(mode) {
        this.run(dockPlanSetMode(this.state, mode));
    }

    /**
     * Split a pane to its right and seat the embedder's pane tab in the new pane.
     * @returns {boolean} false when the docked grid is already at the engine cap.
     */
    splitPane(paneId) {
        return this.run(dockPlanSplitPane(this.state, this.minter, paneId, this.makePaneTab));
    }

    /** Seat the pane-tab factory's tab at the end of a pane's strip. */
    addTab(paneId) {
        return this.run(dockPlanAddTab(this.state, this.minter, paneId, this.makePaneTab));
    }

    /**
     * Open content, or focus the tab already showing it.
     * @returns {string} the tab now focused.
     */
    openContent(input) {
        const planned = dockPlanOpenContent(this.state, this.minter, input);
        this.run(planned.ops);
        return planned.tabId;
    }

    /** Open a second, independent tab on the same content. @returns {string} the new tab id. */
    duplicateTab(tabId) {
        const planned = dockPlanDuplicateTab(this.state, this.minter, tabId);
        this.run(planned.ops);
        return planned.tabId;
    }

    /** Destroy a tab and its content state. A floating host panel goes with it. */
    closeTab(tabId) {
        this.run([{ type: 'closeTab', tabId: tabId }]);
    }

    /** Focus a tab, its pane, and raise that pane when it floats. */
    focusTab(tabId) {
        this.run([{ type: 'focusTab', tabId: tabId }]);
    }

    /** Focus a pane, raising it when it floats. */
    focusPane(paneId) {
        this.run([{ type: 'focusPane', paneId: paneId }]);
    }

    /** Move a tab inside its own pane. */
    reorderTab(tabId, index) {
        this.run([{ type: 'reorderTab', tabId: tabId, index: index }]);
    }

    /** Put a tab at an explicit slot: a reorder, a move, or a return. */
    placeTab(tabId, toPaneId, index) {
        return this.run(dockPlanPlaceTab(this.state, tabId, toPaneId, index));
    }

    /** Resolve a tab drop inside the docked area. */
    dropTab(tabId, targetPaneId, zone) {
        return this.run(dockPlanDropTab(this.state, this.minter, tabId, targetPaneId, zone, this.makePaneTab));
    }

    /** Take a tab out into a floating panel. @returns {string} the new floating pane id. */
    floatTab(tabId, rect) {
        const planned = dockPlanFloatTab(this.state, this.minter, tabId, rect);
        this.run(planned.ops);
        return planned.paneId;
    }

    /** Send a floating panel's tab back into the docked tree. */
    unfloatPane(paneId, toPaneId) {
        this.run(dockPlanUnfloatPane(this.state, paneId, toPaneId));
    }

    /** Record the net position of a floating-panel drag; the panel is focused and raised with it. */
    moveFloat(paneId, x, y) {
        this.run([{ type: 'moveFloat', paneId: paneId, x: x, y: y }]);
    }

    /** Record the net rectangle of a floating-panel resize; the panel is focused and raised with it. */
    resizeFloat(paneId, rect) {
        this.run([{ type: 'resizeFloat', paneId: paneId, rect: rect }]);
    }

    /** Record the net sizes of a divider drag, clamped to the pane minimum. */
    resizeSplit(splitId, sizes) {
        this.run(dockPlanResizeSplit(splitId, sizes));
    }

    /** Keep the docked area populated after an intent: merge emptied panes, reseed an emptied root. */
    settle() {
        return this.run(dockPlanSettle(this.state, this.minter, this.makePaneTab));
    }

    /** Step back one intent, or one run of consecutive focus-only intents. */
    undo() {
        if (!this.sequencer.undo()) return false;
        this.commit();
        return true;
    }

    /** Step forward over what the matching undo stepped back. */
    redo() {
        if (!this.sequencer.redo()) return false;
        this.commit();
        return true;
    }

    /** The pane a new tab lands in, for an embedder that needs to name it. */
    activeDockPaneId() {
        return dockActiveDockPaneId(this.state);
    }
}
