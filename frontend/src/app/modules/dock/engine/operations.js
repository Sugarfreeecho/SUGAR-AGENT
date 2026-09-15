/**
 * The operation engine: one pure `dockApplyOp` that returns the next state plus
 * the operations that undo it. No DOM, no framework, no ambient state —
 * replaying the same operations over the same initial state always yields the
 * same result, because every id an operation creates travels inside the
 * operation itself.
 *
 * Interaction limits (pane count, drag preview) are not enforced here; they
 * belong to the interaction layer (constraints.js and the planner).
 */

/** Capture the focus facts of `paneIds` plus global focus, as the operation that restores them. */
function dockFocusSnapshot(state, paneIds) {
    const paneActiveTabs = {};
    for (let i = 0; i < paneIds.length; i += 1) {
        paneActiveTabs[paneIds[i]] = dockGetPane(state, paneIds[i]).activeTabId;
    }
    return {
        type: 'restoreFocus',
        activePaneId: state.activePaneId,
        floats: state.floats,
        paneActiveTabs: paneActiveTabs,
    };
}

/** Move `paneId` to the top of the floating z order. */
function dockRaise(floats, paneId) {
    return floats.filter((id) => id !== paneId).concat([paneId]);
}

/** Keep `activePaneId` on a live pane after `state` lost the focused one. */
function dockReseatFocus(state, removedPaneId) {
    if (state.activePaneId !== removedPaneId) return state;
    return Object.assign({}, state, { activePaneId: dockFirstPaneId(state) });
}

/** A fresh empty docked pane. */
function dockEmptyDockPane(id) {
    return { kind: 'pane', id: id, host: 'dock', tabs: [], activeTabId: undefined, rect: undefined };
}

/** Reject an id that a creating operation expects to be free. */
function dockAssertFreeNode(state, id) {
    if (state.nodes[id] !== undefined) throw new Error('layout: node ' + id + ' already exists');
}

/** Reject a tab id that an opening operation expects to be free. */
function dockAssertFreeTab(state, id) {
    if (state.tabs[id] !== undefined) throw new Error('layout: tab ' + id + ' already exists');
}

/** Give `paneId` an empty sibling along `axis`. */
function dockApplySplit(state, op) {
    const pane = dockGetPane(state, op.paneId);
    if (pane.host !== 'dock') throw new Error('layout: split requires a docked pane');
    dockAssertFreeNode(state, op.newPaneId);
    const newPane = dockEmptyDockPane(op.newPaneId);
    const parent = dockFindParent(state, op.paneId);

    if (parent !== undefined && parent.axis === op.axis) {
        const index = parent.children.indexOf(op.paneId);
        const at = op.direction === 'after' ? index + 1 : index;
        const children = dockInsertAt(parent.children, at, op.newPaneId);
        // The reference pane's share is halved between it and the new pane; the
        // two halves are equal, so the sizes align with `children` whichever
        // side it took.
        const sizes = [];
        for (let i = 0; i < parent.sizes.length; i += 1) {
            if (i === index) sizes.push(parent.sizes[i] / 2, parent.sizes[i] / 2);
            else sizes.push(parent.sizes[i]);
        }
        const updates = {};
        updates[op.newPaneId] = newPane;
        updates[parent.id] = Object.assign({}, parent, { children: children, sizes: sizes });
        return {
            state: dockWithNodes(state, updates),
            inverse: [
                { type: 'merge', paneId: op.newPaneId },
                { type: 'resize', splitId: parent.id, sizes: parent.sizes },
            ],
        };
    }

    dockAssertFreeNode(state, op.newSplitId);
    // The reference pane's slot takes the new split; compute that swap before
    // the split node exists, or findParent would find the split itself.
    const rehomed = dockReplaceInParent(state, op.paneId, op.newSplitId);
    const children = op.direction === 'after' ? [op.paneId, op.newPaneId] : [op.newPaneId, op.paneId];
    const splitUpdates = {};
    splitUpdates[op.newPaneId] = newPane;
    splitUpdates[op.newSplitId] = { kind: 'split', id: op.newSplitId, axis: op.axis, children: children, sizes: [0.5, 0.5] };
    return {
        state: dockWithNodes(rehomed, splitUpdates),
        inverse: [{ type: 'merge', paneId: op.newPaneId }],
    };
}

/** Drop an empty pane; a two-child split collapses into its surviving child. */
function dockApplyMerge(state, op) {
    const pane = dockGetPane(state, op.paneId);
    if (pane.tabs.length > 0) throw new Error('layout: merge requires an empty pane');
    const focus = dockFocusSnapshot(state, []);

    if (pane.host === 'float') {
        const index = dockFloatIndex(state, op.paneId);
        const updates = {};
        updates[op.paneId] = null;
        const dropped = dockWithNodes(Object.assign({}, state, { floats: dockRemoveAt(state.floats, index) }), updates);
        return {
            state: dockReseatFocus(dropped, op.paneId),
            inverse: [{ type: 'insertPane', pane: pane, tabs: [], attach: { mode: 'float', index: index } }, focus],
        };
    }

    const parent = dockFindParent(state, op.paneId);
    if (parent === undefined) throw new Error('layout: the docked root pane cannot be merged');
    const index = parent.children.indexOf(op.paneId);

    if (parent.children.length > 2) {
        const children = dockRemoveAt(parent.children, index);
        const sizes = dockNormalizeSizes(dockRemoveAt(parent.sizes, index));
        const updates = {};
        updates[op.paneId] = null;
        updates[parent.id] = Object.assign({}, parent, { children: children, sizes: sizes });
        const dropped = dockWithNodes(state, updates);
        return {
            state: dockReseatFocus(dropped, op.paneId),
            inverse: [
                {
                    type: 'insertPane',
                    pane: pane,
                    tabs: [],
                    attach: { mode: 'child', parentId: parent.id, index: index, sizes: parent.sizes },
                },
                focus,
            ],
        };
    }

    const siblingId = parent.children[1 - index];
    if (siblingId === undefined) throw new Error('layout: merge found a split without a sibling');
    const updates = {};
    updates[op.paneId] = null;
    updates[parent.id] = null;
    const collapsed = dockWithNodes(dockReplaceInParent(state, parent.id, siblingId), updates);
    return {
        state: dockReseatFocus(collapsed, op.paneId),
        inverse: [
            { type: 'insertPane', pane: pane, tabs: [], attach: { mode: 'wrap', targetId: siblingId, split: parent } },
            focus,
        ],
    };
}

/** Add a new tab to a docked pane and focus it. */
function dockApplyOpenTab(state, op) {
    const pane = dockGetPane(state, op.paneId);
    if (pane.host !== 'dock') throw new Error('layout: openTab requires a docked pane');
    dockAssertFreeTab(state, op.tab.id);
    const focus = dockFocusSnapshot(state, [pane.id]);
    const tabUpdates = {};
    tabUpdates[op.tab.id] = op.tab;
    const nodeUpdates = {};
    nodeUpdates[pane.id] = dockPaneWithTabs(pane, dockInsertAt(pane.tabs, op.index, op.tab.id), op.tab.id);
    const seated = dockWithNodes(dockWithTabs(state, tabUpdates), nodeUpdates);
    return {
        state: Object.assign({}, seated, { activePaneId: pane.id }),
        inverse: [{ type: 'closeTab', tabId: op.tab.id }, focus],
    };
}

/** Put one tab record back where it was, without stealing focus. */
function dockApplyInsertTab(state, op) {
    const pane = dockGetPane(state, op.paneId);
    if (pane.host !== 'dock') throw new Error('layout: insertTab requires a docked pane');
    dockAssertFreeTab(state, op.tab.id);
    const focus = dockFocusSnapshot(state, [pane.id]);
    const tabs = dockInsertAt(pane.tabs, op.index, op.tab.id);
    const tabUpdates = {};
    tabUpdates[op.tab.id] = op.tab;
    const nodeUpdates = {};
    nodeUpdates[pane.id] = dockPaneWithTabs(pane, tabs, pane.activeTabId === undefined ? op.tab.id : pane.activeTabId);
    return {
        state: dockWithNodes(dockWithTabs(state, tabUpdates), nodeUpdates),
        inverse: [{ type: 'closeTab', tabId: op.tab.id }, focus],
    };
}

/** Destroy a tab and its content state; a floating host pane goes with its only tab. */
function dockApplyCloseTab(state, op) {
    const tab = dockGetTab(state, op.tabId);
    const pane = dockFindTabPane(state, op.tabId);
    const index = pane.tabs.indexOf(op.tabId);
    const focus = dockFocusSnapshot(state, [pane.id]);

    if (pane.host === 'float') {
        const floatIndex = dockFloatIndex(state, pane.id);
        const updates = {};
        updates[pane.id] = null;
        const tabUpdates = {};
        tabUpdates[op.tabId] = null;
        const dropped = dockWithTabs(
            dockWithNodes(Object.assign({}, state, { floats: dockRemoveAt(state.floats, floatIndex) }), updates),
            tabUpdates
        );
        return {
            state: dockReseatFocus(dropped, pane.id),
            inverse: [{ type: 'insertPane', pane: pane, tabs: [tab], attach: { mode: 'float', index: floatIndex } }, focus],
        };
    }

    const activeTabId = pane.activeTabId === op.tabId ? dockNeighbourTabId(pane.tabs, index) : pane.activeTabId;
    const nodeUpdates = {};
    nodeUpdates[pane.id] = dockPaneWithTabs(pane, dockRemoveAt(pane.tabs, index), activeTabId);
    const tabUpdates = {};
    tabUpdates[op.tabId] = null;
    return {
        state: dockWithTabs(dockWithNodes(state, nodeUpdates), tabUpdates),
        inverse: [{ type: 'insertTab', paneId: pane.id, tab: tab, index: index }, focus],
    };
}

/**
 * Put a pane back, with the tab records it owned. A docked pane returns empty
 * (its tabs return through `insertTab`, as `closeTab` records them); a
 * floating pane returns with its one tab, or empty.
 */
function dockApplyInsertPane(state, op) {
    dockAssertFreeNode(state, op.pane.id);
    if (op.pane.tabs.length !== op.tabs.length) throw new Error('layout: insertPane tab records do not match the pane');
    if (op.pane.host === 'dock' && op.tabs.length > 0) throw new Error('layout: insertPane returns a docked pane empty');
    const tabUpdates = {};
    for (let i = 0; i < op.tabs.length; i += 1) {
        dockAssertFreeTab(state, op.tabs[i].id);
        tabUpdates[op.tabs[i].id] = op.tabs[i];
    }
    const restoredTab = op.tabs[0];
    const inverse = restoredTab === undefined
        ? [{ type: 'merge', paneId: op.pane.id }]
        : [{ type: 'closeTab', tabId: restoredTab.id }, dockFocusSnapshot(state, [])];

    const attach = op.attach;
    if (attach.mode === 'child') {
        const parent = dockGetSplit(state, attach.parentId);
        const children = dockInsertAt(parent.children, attach.index, op.pane.id);
        if (attach.sizes.length !== children.length) throw new Error('layout: insertPane sizes do not match the split');
        inverse.push({ type: 'resize', splitId: parent.id, sizes: parent.sizes });
        const nodeUpdates = {};
        nodeUpdates[op.pane.id] = op.pane;
        nodeUpdates[parent.id] = Object.assign({}, parent, { children: children, sizes: attach.sizes });
        return { state: dockWithNodes(dockWithTabs(state, tabUpdates), nodeUpdates), inverse: inverse };
    }
    if (attach.mode === 'wrap') {
        if (attach.split.children.indexOf(op.pane.id) < 0) {
            throw new Error('layout: insertPane wrap split does not list the pane');
        }
        const rehomed = dockReplaceInParent(state, attach.targetId, attach.split.id);
        const nodeUpdates = {};
        nodeUpdates[op.pane.id] = op.pane;
        nodeUpdates[attach.split.id] = attach.split;
        return { state: dockWithNodes(dockWithTabs(rehomed, tabUpdates), nodeUpdates), inverse: inverse };
    }
    if (attach.mode === 'float') {
        if (op.pane.host !== 'float') throw new Error('layout: float attachment requires a floating pane');
        const floats = dockInsertAt(state.floats, attach.index, op.pane.id);
        const nodeUpdates = {};
        nodeUpdates[op.pane.id] = op.pane;
        return {
            state: dockWithNodes(dockWithTabs(Object.assign({}, state, { floats: floats }), tabUpdates), nodeUpdates),
            inverse: inverse,
        };
    }
    return dockAssertNever(attach, 'layout: insertPane attachment');
}

/** Move a tab to a different docked pane and focus it there. */
function dockApplyMoveTab(state, op) {
    const from = dockFindTabPane(state, op.tabId);
    if (from.host !== 'dock') throw new Error('layout: moveTab source must be docked; use unfloat');
    const to = dockGetPane(state, op.toPaneId);
    if (to.host !== 'dock') throw new Error('layout: moveTab target must be docked');
    if (to.id === from.id) throw new Error('layout: moveTab across one pane; use reorderTab');
    const index = from.tabs.indexOf(op.tabId);
    const focus = dockFocusSnapshot(state, [from.id, to.id]);
    const activeTabId = from.activeTabId === op.tabId ? dockNeighbourTabId(from.tabs, index) : from.activeTabId;
    const updates = {};
    updates[from.id] = dockPaneWithTabs(from, dockRemoveAt(from.tabs, index), activeTabId);
    updates[to.id] = dockPaneWithTabs(to, dockInsertAt(to.tabs, op.index, op.tabId), op.tabId);
    const moved = dockWithNodes(state, updates);
    return {
        state: Object.assign({}, moved, { activePaneId: to.id }),
        inverse: [{ type: 'moveTab', tabId: op.tabId, toPaneId: from.id, index: index }, focus],
    };
}

/** Move a tab within its own pane. */
function dockApplyReorderTab(state, op) {
    const pane = dockFindTabPane(state, op.tabId);
    const from = pane.tabs.indexOf(op.tabId);
    const tabs = dockInsertAt(dockRemoveAt(pane.tabs, from), op.index, op.tabId);
    const updates = {};
    updates[pane.id] = Object.assign({}, pane, { tabs: tabs });
    return {
        state: dockWithNodes(state, updates),
        inverse: [{ type: 'reorderTab', tabId: op.tabId, index: from }],
    };
}

/** Focus a tab, its pane, and raise that pane when floating. */
function dockApplyFocusTab(state, op) {
    const pane = dockFindTabPane(state, op.tabId);
    const focus = dockFocusSnapshot(state, [pane.id]);
    const updates = {};
    updates[pane.id] = Object.assign({}, pane, { activeTabId: op.tabId });
    const focused = dockWithNodes(state, updates);
    const floats = pane.host === 'float' ? dockRaise(focused.floats, pane.id) : focused.floats;
    return { state: Object.assign({}, focused, { activePaneId: pane.id, floats: floats }), inverse: [focus] };
}

/** Focus a pane and raise it when floating. */
function dockApplyFocusPane(state, op) {
    const pane = dockGetPane(state, op.paneId);
    const focus = dockFocusSnapshot(state, []);
    const floats = pane.host === 'float' ? dockRaise(state.floats, pane.id) : state.floats;
    return { state: Object.assign({}, state, { activePaneId: pane.id, floats: floats }), inverse: [focus] };
}

/** Record the net result of a divider drag. */
function dockApplyResize(state, op) {
    const split = dockGetSplit(state, op.splitId);
    if (op.sizes.length !== split.children.length) throw new Error('layout: resize sizes do not match the split');
    for (let i = 0; i < op.sizes.length; i += 1) {
        if (!(op.sizes[i] > 0)) throw new Error('layout: resize sizes must all be above zero');
    }
    const updates = {};
    updates[split.id] = Object.assign({}, split, { sizes: dockNormalizeSizes(op.sizes) });
    return {
        state: dockWithNodes(state, updates),
        inverse: [{ type: 'resize', splitId: split.id, sizes: split.sizes }],
    };
}

/** Take a tab out of the docked tree into a new floating pane on top. */
function dockApplyFloat(state, op) {
    dockGetTab(state, op.tabId);
    const from = dockFindTabPane(state, op.tabId);
    if (from.host !== 'dock') throw new Error('layout: float requires a docked tab');
    dockAssertFreeNode(state, op.newPaneId);
    const index = from.tabs.indexOf(op.tabId);
    const focus = dockFocusSnapshot(state, [from.id]);
    const activeTabId = from.activeTabId === op.tabId ? dockNeighbourTabId(from.tabs, index) : from.activeTabId;
    const updates = {};
    updates[from.id] = dockPaneWithTabs(from, dockRemoveAt(from.tabs, index), activeTabId);
    updates[op.newPaneId] = {
        kind: 'pane',
        id: op.newPaneId,
        host: 'float',
        tabs: [op.tabId],
        activeTabId: op.tabId,
        rect: op.rect,
    };
    const floated = dockWithNodes(state, updates);
    return {
        state: Object.assign({}, floated, { floats: floated.floats.concat([op.newPaneId]), activePaneId: op.newPaneId }),
        inverse: [{ type: 'unfloat', paneId: op.newPaneId, toPaneId: from.id, index: index }, focus],
    };
}

/** Return a floating pane's only tab to a docked pane and destroy the floating pane. */
function dockApplyUnfloat(state, op) {
    const pane = dockGetPane(state, op.paneId);
    const rect = dockFloatRect(pane);
    const tabId = dockOnlyTabId(pane);
    const to = dockGetPane(state, op.toPaneId);
    if (to.host !== 'dock') throw new Error('layout: unfloat target must be docked');
    const focus = dockFocusSnapshot(state, [to.id]);
    const updates = {};
    updates[op.paneId] = null;
    updates[to.id] = dockPaneWithTabs(to, dockInsertAt(to.tabs, op.index, tabId), tabId);
    const docked = dockWithNodes(
        Object.assign({}, state, { floats: dockRemoveAt(state.floats, dockFloatIndex(state, op.paneId)) }),
        updates
    );
    return {
        state: Object.assign({}, docked, { activePaneId: to.id }),
        inverse: [{ type: 'float', tabId: tabId, newPaneId: op.paneId, rect: rect }, focus],
    };
}

/** Give a floating pane a new rectangle, focus it, and raise it. */
function dockReshapeFloat(state, pane, rect) {
    const updates = {};
    updates[pane.id] = Object.assign({}, pane, { rect: rect });
    const reshaped = dockWithNodes(state, updates);
    return Object.assign({}, reshaped, { activePaneId: pane.id, floats: dockRaise(reshaped.floats, pane.id) });
}

/** Record the net result of dragging a floating pane, which also focuses and raises it. */
function dockApplyMoveFloat(state, op) {
    const pane = dockGetPane(state, op.paneId);
    const rect = dockFloatRect(pane);
    return {
        state: dockReshapeFloat(state, pane, Object.assign({}, rect, { x: op.x, y: op.y })),
        inverse: [{ type: 'moveFloat', paneId: op.paneId, x: rect.x, y: rect.y }, dockFocusSnapshot(state, [])],
    };
}

/** Record the net result of resizing a floating pane, which also focuses and raises it. */
function dockApplyResizeFloat(state, op) {
    const pane = dockGetPane(state, op.paneId);
    const rect = dockFloatRect(pane);
    if (!(op.rect.width > 0) || !(op.rect.height > 0)) throw new Error('layout: float size must be above zero');
    return {
        state: dockReshapeFloat(state, pane, op.rect),
        inverse: [{ type: 'resizeFloat', paneId: op.paneId, rect: rect }, dockFocusSnapshot(state, [])],
    };
}

/** Restore focus facts a previous operation displaced. */
function dockApplyRestoreFocus(state, op) {
    const inverse = dockFocusSnapshot(state, Object.keys(op.paneActiveTabs));
    for (let i = 0; i < op.floats.length; i += 1) {
        const pane = dockGetPane(state, op.floats[i]);
        if (pane.host !== 'float') throw new Error('layout: restoreFocus lists docked pane ' + op.floats[i] + ' as floating');
    }
    let next = state;
    const paneIds = Object.keys(op.paneActiveTabs);
    for (let i = 0; i < paneIds.length; i += 1) {
        const paneId = paneIds[i];
        const pane = dockGetPane(next, paneId);
        const updates = {};
        updates[paneId] = Object.assign({}, pane, { activeTabId: op.paneActiveTabs[paneId] });
        next = dockWithNodes(next, updates);
    }
    dockGetPane(next, op.activePaneId);
    return {
        state: Object.assign({}, next, { activePaneId: op.activePaneId, floats: op.floats }),
        inverse: [inverse],
    };
}

/**
 * Apply one operation.
 * @param {object} state State the operation reads; never mutated.
 * @param {object} op The operation, carrying every id it creates.
 * @returns {{state:object,inverse:object[]}} the next state and the operations that undo it, applied in order.
 * @throws when the operation addresses missing nodes or breaks a model rule.
 */
function dockApplyOp(state, op) {
    switch (op.type) {
        case 'split': return dockApplySplit(state, op);
        case 'merge': return dockApplyMerge(state, op);
        case 'openTab': return dockApplyOpenTab(state, op);
        case 'insertTab': return dockApplyInsertTab(state, op);
        case 'closeTab': return dockApplyCloseTab(state, op);
        case 'insertPane': return dockApplyInsertPane(state, op);
        case 'moveTab': return dockApplyMoveTab(state, op);
        case 'reorderTab': return dockApplyReorderTab(state, op);
        case 'focusTab': return dockApplyFocusTab(state, op);
        case 'focusPane': return dockApplyFocusPane(state, op);
        case 'resize': return dockApplyResize(state, op);
        case 'float': return dockApplyFloat(state, op);
        case 'unfloat': return dockApplyUnfloat(state, op);
        case 'moveFloat': return dockApplyMoveFloat(state, op);
        case 'resizeFloat': return dockApplyResizeFloat(state, op);
        case 'setExpanded':
            return {
                state: Object.assign({}, state, { expanded: op.expanded }),
                inverse: [{ type: 'setExpanded', expanded: state.expanded }],
            };
        case 'setMode':
            return {
                state: Object.assign({}, state, { mode: op.mode }),
                inverse: [{ type: 'setMode', mode: state.mode }],
            };
        case 'restoreFocus': return dockApplyRestoreFocus(state, op);
        default: return dockAssertNever(op, 'layout: operation');
    }
}

/**
 * Fold operations forward, discarding inverses.
 * @param {object} state Starting state.
 * @param {object[]} ops Operations in recorded order.
 * @returns {object} the state after every operation.
 */
function dockReplay(state, ops) {
    let current = state;
    for (let i = 0; i < ops.length; i += 1) current = dockApplyOp(current, ops[i]).state;
    return current;
}
