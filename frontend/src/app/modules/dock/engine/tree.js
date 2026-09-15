/**
 * Pure tree helpers over the dock layout. Every reader throws on a dangling id
 * (the operation vocabulary is closed, so a miss is a caller defect, never
 * silently tolerated), and every writer returns a new state that keeps
 * untouched nodes at their old identity.
 */

/**
 * Read any node.
 * @param {object} state Current layout.
 * @param {string} id The node.
 * @returns {object} the split or pane.
 * @throws when `id` is not in the tree.
 */
function dockGetNode(state, id) {
    const node = state.nodes[id];
    if (node === undefined) throw new Error('layout: unknown node ' + id);
    return node;
}

/**
 * Read a pane.
 * @param {object} state Current layout.
 * @param {string} id The pane.
 * @returns {object} the pane node.
 * @throws when `id` is missing or names a split.
 */
function dockGetPane(state, id) {
    const node = dockGetNode(state, id);
    if (node.kind !== 'pane') throw new Error('layout: ' + id + ' is not a pane');
    return node;
}

/**
 * Read a split.
 * @param {object} state Current layout.
 * @param {string} id The split.
 * @returns {object} the split node.
 * @throws when `id` is missing or names a pane.
 */
function dockGetSplit(state, id) {
    const node = dockGetNode(state, id);
    if (node.kind !== 'split') throw new Error('layout: ' + id + ' is not a split');
    return node;
}

/**
 * Read a tab record.
 * @param {object} state Current layout.
 * @param {string} id The tab.
 * @returns {object} the record.
 * @throws when `id` is not open.
 */
function dockGetTab(state, id) {
    const tab = state.tabs[id];
    if (tab === undefined) throw new Error('layout: unknown tab ' + id);
    return tab;
}

/**
 * A floating pane's rectangle.
 * @param {object} pane The pane.
 * @returns {{x:number,y:number,width:number,height:number}} its viewport rectangle.
 * @throws when `pane` is docked.
 */
function dockFloatRect(pane) {
    if (pane.host !== 'float' || pane.rect === undefined) throw new Error('layout: ' + pane.id + ' is not floating');
    return pane.rect;
}

/**
 * A floating pane's position in the z order.
 * @param {object} state Current layout.
 * @param {string} id The floating pane.
 * @returns {number} its index in `floats`, bottom first.
 * @throws when `id` is not listed in `floats`.
 */
function dockFloatIndex(state, id) {
    const index = state.floats.indexOf(id);
    if (index < 0) throw new Error('layout: floating pane ' + id + ' is not in the z order');
    return index;
}

/**
 * The one tab a pane holds.
 * @param {object} pane The pane.
 * @returns {string} its tab's id.
 * @throws when `pane` holds any other number of tabs.
 */
function dockOnlyTabId(pane) {
    const tabId = pane.tabs[0];
    if (tabId === undefined || pane.tabs.length !== 1) throw new Error('layout: ' + pane.id + ' does not hold exactly one tab');
    return tabId;
}

/**
 * The split holding a node.
 * @param {object} state Current layout.
 * @param {string} id The node.
 * @returns {object|undefined} its parent split, or undefined for the docked root and floating panes.
 */
function dockFindParent(state, id) {
    const nodes = Object.keys(state.nodes);
    for (let i = 0; i < nodes.length; i += 1) {
        const node = state.nodes[nodes[i]];
        if (node.kind === 'split' && node.children.indexOf(id) >= 0) return node;
    }
    return undefined;
}

/**
 * The pane holding a tab.
 * @param {object} state Current layout.
 * @param {string} tabId The tab.
 * @returns {object} the pane whose strip lists it.
 * @throws when no pane lists it.
 */
function dockFindTabPane(state, tabId) {
    const nodes = Object.keys(state.nodes);
    for (let i = 0; i < nodes.length; i += 1) {
        const node = state.nodes[nodes[i]];
        if (node.kind === 'pane' && node.tabs.indexOf(tabId) >= 0) return node;
    }
    throw new Error('layout: tab ' + tabId + ' has no pane');
}

/**
 * Docked pane ids in visual order (depth-first through the split tree).
 * @param {object} state Current layout.
 * @returns {string[]} every docked pane's id; floating panes are absent.
 */
function dockPaneIds(state) {
    const out = [];
    const walk = (id) => {
        const node = dockGetNode(state, id);
        if (node.kind === 'pane') {
            out.push(node.id);
            return;
        }
        for (let i = 0; i < node.children.length; i += 1) walk(node.children[i]);
    };
    walk(state.rootId);
    return out;
}

/**
 * Scale `sizes` so they sum to 1. Input that already sums to 1 is copied
 * unchanged, so restoring recorded sizes never drifts.
 * @param {number[]} sizes Fractions or any positive weights.
 * @returns {number[]} the fractions, summing to 1.
 * @throws when the input cannot be normalized.
 */
function dockNormalizeSizes(sizes) {
    let total = 0;
    for (let i = 0; i < sizes.length; i += 1) total += sizes[i];
    if (!(total > 0)) throw new Error('layout: sizes must sum above zero');
    if (Math.abs(total - 1) < 1e-12) return sizes.slice();
    return sizes.map((size) => size / total);
}

/**
 * Replace or delete nodes.
 * @param {object} state Current layout.
 * @param {object} updates Nodes by id; a null update deletes that id.
 * @returns {object} the layout with those nodes replaced; untouched nodes keep their identity.
 */
function dockWithNodes(state, updates) {
    const nodes = {};
    const keys = Object.keys(state.nodes);
    for (let i = 0; i < keys.length; i += 1) {
        const id = keys[i];
        if (!Object.prototype.hasOwnProperty.call(updates, id)) nodes[id] = state.nodes[id];
    }
    const updateKeys = Object.keys(updates);
    for (let i = 0; i < updateKeys.length; i += 1) {
        const id = updateKeys[i];
        if (updates[id] !== null) nodes[id] = updates[id];
    }
    return Object.assign({}, state, { nodes: nodes });
}

/**
 * Replace or delete tab records.
 * @param {object} state Current layout.
 * @param {object} updates Records by id; a null update deletes that id.
 * @returns {object} the layout with those records replaced; untouched records keep their identity.
 */
function dockWithTabs(state, updates) {
    const tabs = {};
    const keys = Object.keys(state.tabs);
    for (let i = 0; i < keys.length; i += 1) {
        const id = keys[i];
        if (!Object.prototype.hasOwnProperty.call(updates, id)) tabs[id] = state.tabs[id];
    }
    const updateKeys = Object.keys(updates);
    for (let i = 0; i < updateKeys.length; i += 1) {
        const id = updateKeys[i];
        if (updates[id] !== null) tabs[id] = updates[id];
    }
    return Object.assign({}, state, { tabs: tabs });
}

/**
 * Insert a value into a list.
 * @param {Array} items The list.
 * @param {number} index The slot, clamped to the list's bounds.
 * @param {*} value What to insert.
 * @returns {Array} a new list with the value at the slot.
 */
function dockInsertAt(items, index, value) {
    const at = Math.max(0, Math.min(index, items.length));
    return items.slice(0, at).concat([value], items.slice(at));
}

/**
 * Remove one entry from a list.
 * @param {Array} items The list.
 * @param {number} index The entry to drop.
 * @returns {Array} a new list without it.
 */
function dockRemoveAt(items, index) {
    return items.slice(0, index).concat(items.slice(index + 1));
}

/**
 * Which tab a pane focuses after one leaves it.
 * @param {string[]} tabs The strip before the removal.
 * @param {number} removedIndex The leaving tab's slot.
 * @returns {string|undefined} the previous neighbour when one exists, otherwise the next, otherwise undefined.
 */
function dockNeighbourTabId(tabs, removedIndex) {
    const remaining = dockRemoveAt(tabs, removedIndex);
    if (remaining.length === 0) return undefined;
    return remaining[Math.max(0, removedIndex - 1)];
}

/**
 * Copy a pane with a new tab list.
 * @param {object} pane The pane.
 * @param {string[]} tabs Its new strip.
 * @param {string|undefined} activeTabId The active tab, which the caller keeps consistent with `tabs`.
 * @returns {object} the copied pane.
 */
function dockPaneWithTabs(pane, tabs, activeTabId) {
    return Object.assign({}, pane, { tabs: tabs, activeTabId: activeTabId });
}

/**
 * Swap a node for another in its parent's slot, or make the replacement the docked root.
 * @param {object} state Current layout.
 * @param {string} targetId The node to swap out.
 * @param {string} replacementId The node taking its slot.
 * @returns {object} the layout with the slot rewritten.
 * @throws when `targetId` is neither rooted nor parented.
 */
function dockReplaceInParent(state, targetId, replacementId) {
    const parent = dockFindParent(state, targetId);
    if (parent === undefined) {
        if (state.rootId !== targetId) throw new Error('layout: ' + targetId + ' is neither rooted nor parented');
        return Object.assign({}, state, { rootId: replacementId });
    }
    const children = parent.children.map((child) => (child === targetId ? replacementId : child));
    const updates = {};
    updates[parent.id] = Object.assign({}, parent, { children: children });
    return dockWithNodes(state, updates);
}

/** Walk from the docked root to a pane, taking the child `choose` names at every split. */
function dockDescend(state, choose) {
    let node = dockGetNode(state, state.rootId);
    while (node.kind === 'split') {
        const next = choose(node);
        if (next === undefined) throw new Error('layout: split ' + node.id + ' has no children');
        node = dockGetNode(state, next);
    }
    return node.id;
}

/**
 * The first docked pane in visual order: the docked root, or the first leaf
 * under it. Focus falls back here when the focused pane is removed, and a new
 * tab lands here when the focused pane floats.
 * @param {object} state Current layout.
 * @returns {string} the first docked pane's id.
 */
function dockFirstPaneId(state) {
    return dockDescend(state, (split) => split.children[0]);
}

/**
 * The docked pane in the top-right corner: from the root, the last child of
 * every row split and the first child of every column split. Its tab strip is
 * where the surface-wide controls sit, so they read as the surface's own
 * top-right corner however the tree is divided.
 * @param {object} state Current layout.
 * @returns {string} the top-right docked pane's id.
 */
function dockTopRightPaneId(state) {
    return dockDescend(state, (split) => (split.axis === 'row' ? split.children[split.children.length - 1] : split.children[0]));
}
