/**
 * Intent planning: each interaction, as a pure function from the current state
 * to the operations that carry it out.
 *
 * Planners mint the ids their operations create and enforce the interaction
 * limits, but they hold no state and apply nothing. A planner returning no
 * operations means the intent changes nothing; the caller records nothing and
 * notifies nobody.
 */

/** Distance each newly floated panel steps down and right from the last. */
const DOCK_FLOAT_CASCADE_STEP = 24;

/** Where the first floating panel appears, in viewport pixels. */
const DOCK_FLOAT_ORIGIN = { x: 160, y: 120 };

/** No operations: the intent is a no-op against this state. */
const DOCK_NOTHING = [];

/**
 * First tab in one pane carrying `contentId`, in strip order.
 * @param {object} state Current layout.
 * @param {string} paneId The pane to search, docked or floating.
 * @param {string} contentId The content identity.
 * @param {string} [kind] Restrict to tabs of this kind; omit to match any kind.
 * @returns {string|undefined} the tab, or undefined when that pane shows no such content.
 */
function dockFindPaneContentTab(state, paneId, contentId, kind) {
    const tabs = dockGetPane(state, paneId).tabs;
    for (let i = 0; i < tabs.length; i += 1) {
        const tab = state.tabs[tabs[i]];
        if (tab && tab.contentId === contentId && (kind === undefined || tab.kind === kind)) return tabs[i];
    }
    return undefined;
}

/**
 * First tab carrying `contentId`, searched docked panes first, in visual order.
 * @param {object} state Current layout.
 * @param {string} contentId The content identity.
 * @param {string} [kind] Restrict to tabs of this kind; omit to match any kind.
 * @returns {string|undefined} the tab, or undefined when nothing shows the content.
 */
function dockFindContentTab(state, contentId, kind) {
    const order = dockPaneIds(state).concat(state.floats);
    for (let i = 0; i < order.length; i += 1) {
        const found = dockFindPaneContentTab(state, order[i], contentId, kind);
        if (found !== undefined) return found;
    }
    return undefined;
}

/**
 * The pane a new tab lands in.
 * @param {object} state Current layout.
 * @returns {string} the active pane when docked, else the first docked pane.
 */
function dockActiveDockPaneId(state) {
    const active = dockGetPane(state, state.activePaneId);
    return active.host === 'dock' ? active.id : dockFirstPaneId(state);
}

/** Send a tab into a docked pane, choosing the operation its current host needs. */
function dockTabInto(source, tabId, toPaneId, index) {
    return source.host === 'float'
        ? { type: 'unfloat', paneId: source.id, toPaneId: toPaneId, index: index }
        : { type: 'moveTab', tabId: tabId, toPaneId: toPaneId, index: index };
}

/**
 * Expand or collapse the docked area.
 * @param {object} state Current layout.
 * @param {boolean} expanded Whether the docked area is shown.
 * @returns {object[]} the operation, or none when the value is already current.
 */
function dockPlanSetExpanded(state, expanded) {
    return state.expanded === expanded ? DOCK_NOTHING : [{ type: 'setExpanded', expanded: expanded }];
}

/**
 * Switch the presentation.
 * @param {object} state Current layout.
 * @param {string} mode The presentation to record.
 * @returns {object[]} the operation, or none when the value is already current.
 */
function dockPlanSetMode(state, mode) {
    return state.mode === mode ? DOCK_NOTHING : [{ type: 'setMode', mode: mode }];
}

/**
 * Split a pane to its right and seed the new pane.
 * @param {object} state Current layout.
 * @param {{next:Function}} mint Id source for the pane, split, and seeded tab.
 * @param {string} [paneId] Pane to split; defaults to the active docked pane.
 * @param {Function} [makePaneTab] Builds the seeded tab; omit to leave the new pane empty.
 * @returns {object[]} the operations, or none when the pane budget is spent.
 */
function dockPlanSplitPane(state, mint, paneId, makePaneTab) {
    if (!dockCanSplit(state)) return DOCK_NOTHING;
    const target = paneId === undefined ? dockActiveDockPaneId(state) : paneId;
    if (dockGetPane(state, target).host !== 'dock') return DOCK_NOTHING;
    const newPaneId = mint.next(DOCK_PANE_PREFIX);
    const ops = [{
        type: 'split',
        paneId: target,
        axis: 'row',
        direction: 'after',
        newPaneId: newPaneId,
        newSplitId: mint.next(DOCK_SPLIT_PREFIX),
    }];
    // Seeding is its own operation inside the same intent: the record keeps the
    // two apart, one step back undoes both — and the factory decides whether
    // there is anything to seat.
    const seed = makePaneTab === undefined ? undefined : makePaneTab(mint.next(DOCK_TAB_PREFIX));
    if (seed !== undefined) ops.push({ type: 'openTab', paneId: newPaneId, tab: seed, index: 0 });
    return ops;
}

/**
 * Seat the embedder's seeded tab at the end of a docked pane's strip.
 * @param {object} state Current layout.
 * @param {{next:Function}} mint Id source for the new tab.
 * @param {string} paneId The pane whose strip asked; must be docked.
 * @param {Function} [makeTab] Builds the seeded tab; omit to plan nothing.
 * @returns {object[]} the operations, or none when there is nothing to seat.
 */
function dockPlanAddTab(state, mint, paneId, makeTab) {
    if (makeTab === undefined) return DOCK_NOTHING;
    const pane = dockGetPane(state, paneId);
    if (pane.host !== 'dock') return DOCK_NOTHING;
    return [{ type: 'openTab', paneId: paneId, tab: makeTab(mint.next(DOCK_TAB_PREFIX)), index: pane.tabs.length }];
}

/**
 * Open content, or focus the tab already showing it.
 * @param {object} state Current layout.
 * @param {{next:Function}} mint Id source for a newly opened tab.
 * @param {object} input Identity, copy, and optional placement.
 * @returns {{ops:object[],tabId:string}} the operations plus the tab they settle on.
 */
function dockPlanOpenContent(state, mint, input) {
    const existing = input.revealIfOpened === false
        ? undefined
        : dockFindContentTab(state, input.contentId, input.kind);
    if (existing !== undefined) return { ops: [{ type: 'focusTab', tabId: existing }], tabId: existing };
    const paneId = input.paneId === undefined ? dockActiveDockPaneId(state) : input.paneId;
    const index = input.index === undefined ? dockGetPane(state, paneId).tabs.length : input.index;
    const tab = {
        id: mint.next(DOCK_TAB_PREFIX),
        kind: input.kind,
        contentId: input.contentId,
        title: input.title,
    };
    return { ops: [{ type: 'openTab', paneId: paneId, tab: tab, index: index }], tabId: tab.id };
}

/**
 * Open a second, independent tab on the same content, beside the original.
 * @param {object} state Current layout.
 * @param {{next:Function}} mint Id source for the copy.
 * @param {string} tabId Tab to copy.
 * @returns {{ops:object[],tabId:string}} the operations plus the new tab's id.
 */
function dockPlanDuplicateTab(state, mint, tabId) {
    const source = dockGetTab(state, tabId);
    const pane = dockFindTabPane(state, tabId);
    const host = pane.host === 'dock' ? pane.id : dockActiveDockPaneId(state);
    const index = pane.host === 'dock' ? pane.tabs.indexOf(tabId) + 1 : dockGetPane(state, host).tabs.length;
    const tab = Object.assign({}, source, { id: mint.next(DOCK_TAB_PREFIX) });
    return { ops: [{ type: 'openTab', paneId: host, tab: tab, index: index }], tabId: tab.id };
}

/**
 * Put a tab at an explicit strip slot: a reorder inside its own pane, otherwise a
 * move, or a return when it currently floats.
 * @param {object} state Current layout.
 * @param {string} tabId The tab being placed.
 * @param {string} toPaneId Destination docked pane.
 * @param {number} index Caret slot in the destination strip, counted over the
 *   chips as drawn — the dragged chip included when the destination is its own
 *   pane, so the slot just before or just after it is where it already sits.
 * @returns {object[]} the operations, or none when the placement changes nothing.
 */
function dockPlanPlaceTab(state, tabId, toPaneId, index) {
    const source = dockFindTabPane(state, tabId);
    if (dockGetPane(state, toPaneId).host !== 'dock') return DOCK_NOTHING;
    if (source.id === toPaneId) {
        // `reorderTab` indexes the strip without the tab: a caret past the chip
        // counts one slot the chip itself vacates.
        const from = source.tabs.indexOf(tabId);
        const to = index > from ? index - 1 : index;
        return to === from ? DOCK_NOTHING : [{ type: 'reorderTab', tabId: tabId, index: to }];
    }
    return [dockTabInto(source, tabId, toPaneId, index)];
}

/**
 * Resolve a tab release on a pane body: the centre moves the tab in, an edge
 * splits the pane and seats the tab in the new half. A pane's only tab released
 * on that pane's centre changes nothing; released on its edge it splits, and
 * the factory's tab backfills the pane the drag would otherwise empty — without
 * a factory that release also changes nothing, since the split would empty the
 * pane and seat the tab beside where it already was.
 * @param {object} state Current layout.
 * @param {{next:Function}} mint Id source for a pane an edge release creates.
 * @param {string} tabId The dragged tab.
 * @param {string} targetPaneId Pane under the pointer.
 * @param {string} zone Dock region the pointer released in.
 * @param {Function} [makeTab] Builds the tab that backfills a pane its only tab splits away from.
 * @returns {object[]} the operations, or none when the release changes nothing.
 */
function dockPlanDropTab(state, mint, tabId, targetPaneId, zone, makeTab) {
    const source = dockFindTabPane(state, tabId);
    const target = dockGetPane(state, targetPaneId);
    if (target.host !== 'dock') return DOCK_NOTHING;
    const split = dockZoneSplit(zone);

    if (split === undefined) {
        if (source.id === targetPaneId) return DOCK_NOTHING;
        return [dockTabInto(source, tabId, targetPaneId, target.tabs.length)];
    }

    const vacates = source.id === targetPaneId && source.tabs.length === 1;
    if (vacates && makeTab === undefined) return DOCK_NOTHING;
    if (!dockCanSplit(state)) return DOCK_NOTHING;
    const newPaneId = mint.next(DOCK_PANE_PREFIX);
    const ops = [{
        type: 'split',
        paneId: targetPaneId,
        axis: split.axis,
        direction: split.direction,
        newPaneId: newPaneId,
        newSplitId: mint.next(DOCK_SPLIT_PREFIX),
    }];
    // The backfill seats before the move so the moved tab ends focused, as any
    // other drop leaves it.
    if (vacates && makeTab !== undefined) {
        ops.push({ type: 'openTab', paneId: targetPaneId, tab: makeTab(mint.next(DOCK_TAB_PREFIX)), index: source.tabs.length });
    }
    ops.push(dockTabInto(source, tabId, newPaneId, 0));
    return ops;
}

/**
 * Take a tab out into a floating panel.
 * @param {object} state Current layout.
 * @param {{next:Function}} mint Id source for the floating pane.
 * @param {string} tabId Tab to float.
 * @param {object} [rect] Explicit rectangle; defaults to a cascade from the last panel.
 * @returns {{ops:object[],paneId:string}} the operations plus the floating pane's id.
 */
function dockPlanFloatTab(state, mint, tabId, rect) {
    const step = state.floats.length * DOCK_FLOAT_CASCADE_STEP;
    const newPaneId = mint.next(DOCK_FLOAT_PREFIX);
    return {
        ops: [{
            type: 'float',
            tabId: tabId,
            newPaneId: newPaneId,
            rect: rect === undefined
                ? {
                    x: DOCK_FLOAT_ORIGIN.x + step,
                    y: DOCK_FLOAT_ORIGIN.y + step,
                    width: DOCK_FLOAT_DEFAULT_SIZE.width,
                    height: DOCK_FLOAT_DEFAULT_SIZE.height,
                }
                : rect,
        }],
        paneId: newPaneId,
    };
}

/**
 * Send a floating panel's tab back into the docked tree.
 * @param {object} state Current layout.
 * @param {string} paneId The floating pane.
 * @param {string} [toPaneId] Destination docked pane; defaults to the active one.
 * @returns {object[]} the operations.
 */
function dockPlanUnfloatPane(state, paneId, toPaneId) {
    const destination = toPaneId === undefined ? dockActiveDockPaneId(state) : toPaneId;
    return [{
        type: 'unfloat',
        paneId: paneId,
        toPaneId: destination,
        index: dockGetPane(state, destination).tabs.length,
    }];
}

/**
 * Record the net sizes of a divider drag, clamped to the pane minimum.
 * @param {string} splitId The split whose divider moved.
 * @param {number[]} sizes The fractions the drag reached.
 * @param {number} [minimum] Smallest pane share; defaults to the kit's fraction.
 * @returns {object[]} the resize operation.
 */
function dockPlanResizeSplit(splitId, sizes, minimum) {
    return [{ type: 'resize', splitId: splitId, sizes: dockClampSizes(sizes, minimum) }];
}

/**
 * Keep the docked area populated after an intent: drop every docked pane the
 * intent left empty, and when the surviving root pane is itself empty, seed it.
 *
 * A pane empties when its last tab is closed, moved out, or floated; each such
 * pane is merged away, innermost first, until none remains. The root pane cannot
 * be merged, so it is reseeded instead — with the factory's tab, or left empty
 * when the embedder supplies none. The returned operations continue the intent
 * they follow, so a caller records both as one entry.
 * @param {object} state The layout after the intent's own operations.
 * @param {{next:Function}} mint Id source for the reseeded tab.
 * @param {Function} [makeTab] Builds the tab an emptied root pane is reseeded with.
 * @returns {object[]} the follow-up operations, or none when every docked pane holds a tab.
 */
function dockPlanSettle(state, mint, makeTab) {
    const ops = [];
    let current = state;
    for (;;) {
        const ids = dockPaneIds(current);
        let emptied;
        for (let i = 0; i < ids.length; i += 1) {
            if (ids[i] !== current.rootId && dockGetPane(current, ids[i]).tabs.length === 0) { emptied = ids[i]; break; }
        }
        if (emptied === undefined) break;
        const merge = { type: 'merge', paneId: emptied };
        ops.push(merge);
        current = dockApplyOp(current, merge).state;
    }
    const root = dockGetNode(current, current.rootId);
    if (root.kind === 'pane' && root.tabs.length === 0 && makeTab !== undefined) {
        ops.push({ type: 'openTab', paneId: root.id, tab: makeTab(mint.next(DOCK_TAB_PREFIX)), index: 0 });
    }
    return ops;
}
