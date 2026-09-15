/**
 * The store shell over the docking engine: one surface per session, held as
 * plain data so the engine's pure functions are the only thing that ever
 * computes a layout.
 *
 * Every action follows the same steps — mint the ids the intent needs, ask the
 * engine's planner what operations carry it out, let the settle planner keep
 * every pane populated, record it all as one history entry — and then assigns
 * the session's whole surface back in one go. Nothing here reaches into a
 * surface to edit a layout in place.
 *
 * The settle step is this product's rule, not the engine's: an intent never
 * leaves an expanded column with an empty pane — emptied side panes merge away,
 * and an empty root pane seeds the default tab. A collapsed column may stand
 * empty; the seed waits for the expansion that would otherwise show nothing.
 *
 * Page uniqueness is this product's rule too: a pane holds at most one tab of
 * each page kind (a tab whose content is the kind's own page address). A page
 * dragged into a pane that shows it merges into the pane's own — the arriving
 * tab closes and the pane's own is focused. The engine plans none of this; it
 * is decided here before its planners run.
 *
 * The product also tightens the engine's limits: at most two horizontal docked
 * panes here (the engine keeps its tree, other split directions, and the wider
 * pane budget).
 */

/** This product's ceiling on docked panes. */
const DOCK_PRODUCT_MAX_PANES = 2;

/** This product's divider floor, as a share of the split. */
const DOCK_PRODUCT_MIN_FRACTION = 0.2;

/**
 * Every session's surface, keyed by area then session id. Two areas exist —
 * `main` (the conversation split view) and `right` (the dsh-style details
 * column) — and neither can see the other's layouts. Plain data, safe to store.
 */
const dockSurfacesByArea = Object.create(null);

/**
 * One area's surface map, materialized on first use.
 * @param {string} [area] Area id; defaults to 'main'.
 * @returns {object} session id -> surface.
 */
function dockAreaSurfaces(area) {
    const id = String(area || 'main');
    if (!dockSurfacesByArea[id]) dockSurfacesByArea[id] = Object.create(null);
    return dockSurfacesByArea[id];
}

/**
 * The surface a session starts with: collapsed, one pane, no tabs. The default
 * tab is not seeded here — the settle rule seeds it when the dock first expands
 * still empty, so an open into a fresh surface shows only what it opened.
 * @returns {object} the initial surface.
 */
function dockCreateSurface() {
    const counter = dockCreateMinter(0);
    return {
        layout: dockCreateInitialState(counter, undefined, 'push'),
        history: DOCK_EMPTY_HISTORY,
        minted: counter.used(),
    };
}

/** The surface for a session, materializing it on first read. */
function dockSurfaceOf(sessionId, area) {
    const sid = String(sessionId || '');
    const surfaces = dockAreaSurfaces(area);
    if (!sid) return undefined;
    if (!surfaces[sid]) surfaces[sid] = dockCreateSurface();
    return surfaces[sid];
}

/** Whether a surface has been materialized for a session. */
function dockSurfaceExists(sessionId, area) {
    return !!dockAreaSurfaces(area)[String(sessionId || '')];
}

/** Replace one session's surface, leaving every other session by reference. */
function dockSeat(sessionId, next, area) {
    const sid = String(sessionId || '');
    if (!sid) return false;
    const surfaces = dockAreaSurfaces(area);
    const existing = surfaces[sid] || dockCreateSurface();
    const updated = next(existing);
    if (updated === existing) {
        surfaces[sid] = existing;
        return false;
    }
    surfaces[sid] = updated;
    return true;
}

/** A mint that counts, so the surface can carry its position forward. */
function dockCountingMint(from) {
    const minter = dockCreateMinter(from);
    return minter;
}

/**
 * Run one planner against a surface, settle what it left behind, and record the
 * whole intent as one history entry.
 * @param {object} surface The session's current surface.
 * @param {Function} plan `(state, mint) => ops`.
 * @param {Function} seed Thunk returning the tab a reseeded pane should hold.
 * @returns {object} the next surface, or the same one when nothing changed.
 */
function dockAdvance(surface, plan, seed) {
    const minter = dockCountingMint(surface.minted);
    const makeTab = (id) => {
        const spec = seed();
        return { id: id, kind: spec.kind, contentId: spec.contentId, title: spec.title };
    };
    const planned = plan(surface.layout, minter) || [];
    if (planned.length === 0) return surface;
    // The settle planner reads the state the intent produces, so it is applied
    // to a scratch copy first; the record then applies both parts once. The
    // seed factory is withheld while the intent leaves the column collapsed.
    const after = dockReplay(surface.layout, planned);
    const settled = dockPlanSettle(after, minter, after.expanded ? makeTab : undefined);
    const stepped = dockRecord(surface.history, surface.layout, planned.concat(settled));
    return { layout: stepped.state, history: stepped.history, minted: minter.used() };
}

/** Whether the product allows another split: engine budget plus this product's two-pane ceiling. */
function dockProductCanSplit(state) {
    return dockCanSplit(state) && dockPaneIds(state).length < DOCK_PRODUCT_MAX_PANES;
}

/** The kind whose page a tab shows, or undefined for a resource tab. */
function dockPageKind(state, tabId) {
    const tab = state.tabs[tabId];
    return tab !== undefined && tab.contentId === 'myagent-page://' + tab.kind ? tab.kind : undefined;
}

/** The tab showing `kind`'s page in a pane, if any. */
function dockPanePage(state, paneId, kind) {
    return dockFindPaneContentTab(state, paneId, 'myagent-page://' + kind, kind);
}

/** Focus a tab: nothing to plan while it is its pane's active tab and its pane is the active one. */
function dockPlanFocusTab(state, tabId) {
    const pane = dockFindTabPane(state, tabId);
    return pane.activeTabId === tabId && state.activePaneId === pane.id ? [] : [{ type: 'focusTab', tabId: tabId }];
}

/** Focus a pane: nothing to plan while it is the active one. */
function dockPlanFocusPane(state, paneId) {
    return state.activePaneId === paneId ? [] : [{ type: 'focusPane', paneId: paneId }];
}

/**
 * Plan a tab's arrival in a docked pane: a page arriving where its kind's page
 * already shows merges into it, anything else plans as the engine does.
 */
function dockArriving(state, tabId, toPaneId, otherwise) {
    const kind = dockPageKind(state, tabId);
    if (kind === undefined) return otherwise();
    const existing = dockPanePage(state, toPaneId, kind);
    if (existing === undefined || existing === tabId) return otherwise();
    return [{ type: 'closeTab', tabId: tabId }, { type: 'focusTab', tabId: existing }];
}

/**
 * The default tab an empty pane is seeded with: the seed thunk decides its
 * content; here it is stamped at the page address of its kind so uniqueness and
 * open-by-kind agree on one identity.
 */
function dockSeedRecord(id, spec) {
    return { id: id, kind: spec.kind, contentId: spec.contentId, title: spec.title };
}

// ── actions ──────────────────────────────────────────────────────────────────

/** Materialize a session's surface without changing it. */
function dockActionOpen(sessionId, area) {
    return dockSeat(sessionId, (surface) => surface, area);
}

/** Expand or collapse the docked area. */
function dockActionSetExpanded(sessionId, expanded, seed, area) {
    return dockSeat(sessionId, (surface) => dockAdvance(surface, (state) => dockPlanSetExpanded(state, expanded), seed), area);
}

/** Flip the docked area between expanded and collapsed. */
function dockActionToggleExpanded(sessionId, seed, area) {
    return dockSeat(sessionId, (surface) => dockAdvance(surface, (state) => dockPlanSetExpanded(state, !state.expanded), seed), area);
}

/** Switch how the docked area is presented. */
function dockActionSetMode(sessionId, mode, seed, area) {
    return dockSeat(sessionId, (surface) => dockAdvance(surface, (state) => dockPlanSetMode(state, mode), seed), area);
}

/**
 * Split a docked pane to its right and seed the new pane. Product rules: at
 * most two panes, and an empty pane is not split (nothing to put beside).
 */
function dockActionSplitPane(sessionId, paneId, seed, settled, area) {
    let created;
    const changed = dockSeat(sessionId, (surface) => {
        const next = dockAdvance(surface, (state, mint) => {
            const target = paneId === undefined ? dockActiveDockPaneId(state) : paneId;
            if (!dockProductCanSplit(state)) return [];
            if (dockGetPane(state, target).tabs.length === 0) return [];
            return dockPlanSplitPane(state, mint, target, (id) => dockSeedRecord(id, seed()));
        }, seed);
        if (next !== surface && settled) {
            const before = dockPaneIds(surface.layout);
            const ids = dockPaneIds(next.layout);
            for (let i = 0; i < ids.length; i += 1) {
                if (before.indexOf(ids[i]) < 0) created = ids[i];
            }
        }
        return next;
    }, area);
    if (changed && settled) settled(created);
    return changed;
}

/**
 * One entry carries the whole open: revealing the column (an open behind a
 * collapsed panel is not an open), focusing or seating the tab, and closing the
 * tab it replaces.
 * @param {string} sessionId The session whose surface receives the open.
 * @param {object} intent `{ kind, contentId, title, paneId?, replaceTab?, revealIfOpened? }`.
 * @param {Function} seed Thunk returning the default tab for an emptied pane.
 * @param {Function} [settled] Called synchronously with the tab the open landed on.
 */
function dockActionOpenContent(sessionId, intent, seed, settled, area) {
    dockSeat(sessionId, (surface) => dockAdvance(surface, (state, mint) => {
        const ops = dockPlanSetExpanded(state, true).slice();
        const replace = intent.replaceTab;
        const replaced = replace === undefined ? undefined : dockFindTabPane(state, replace);
        const lent = replace !== undefined && replaced !== undefined && replaced.host === 'dock' ? replaced : undefined;
        const paneId = lent ? lent.id : intent.paneId;
        const index = lent === undefined || replace === undefined ? undefined : lent.tabs.indexOf(replace);
        // A page is unique per pane, not per surface: the pane it would land in
        // may already show it, which is then the tab this open settles on.
        const page = intent.contentId === 'myagent-page://' + intent.kind;
        const held = page ? dockPanePage(state, paneId === undefined ? dockActiveDockPaneId(state) : paneId, intent.kind) : undefined;
        let planned;
        if (held !== undefined) {
            planned = { ops: [{ type: 'focusTab', tabId: held }], tabId: held };
        } else {
            const input = {
                kind: intent.kind,
                contentId: intent.contentId,
                title: intent.title,
                revealIfOpened: page ? false : intent.revealIfOpened,
            };
            if (paneId !== undefined) input.paneId = paneId;
            if (index !== undefined) input.index = index;
            planned = dockPlanOpenContent(state, mint, input);
        }
        for (let i = 0; i < planned.ops.length; i += 1) ops.push(planned.ops[i]);
        if (replace !== undefined && replace !== planned.tabId) ops.push({ type: 'closeTab', tabId: replace });
        if (settled) settled(planned.tabId);
        return ops;
    }, seed), area);
}

/** Open a page kind by kind, at the page address the kind records. */
function dockActionOpenPage(sessionId, kind, options, seed, settled, area) {
    const opts = options || {};
    dockActionOpenContent(sessionId, {
        kind: kind,
        contentId: 'myagent-page://' + kind,
        title: opts.title,
        paneId: opts.paneId,
        replaceTab: opts.replaceTab,
        revealIfOpened: false,
    }, seed, settled, area);
}

/** A page is never copied: the copy would sit beside it in the same pane. */
function dockActionDuplicateTab(sessionId, tabId, seed, area) {
    return dockSeat(sessionId, (surface) => dockAdvance(
        surface,
        (state, mint) => (dockPageKind(state, tabId) !== undefined ? [] : dockPlanDuplicateTab(state, mint, tabId).ops),
        seed
    ), area);
}

/**
 * Close a tab. A tab already gone is left alone. A pane emptied by the close
 * is backfilled by `dockAdvance`'s settle step with the seed default (the
 * column's "start" page) — except the column's very last tab when that tab is
 * the start page itself: closing the lone start page closes the column
 * (feedback #5).
 */
function dockActionCloseTab(sessionId, tabId, seed, area) {
    return dockSeat(sessionId, (surface) => dockAdvance(surface, (state) => {
        const tab = state.tabs[tabId];
        if (tab === undefined) return [];
        const lastOne = dockPaneIds(state).length === 1 && Object.keys(state.tabs).length === 1;
        if (area === 'right' && lastOne && tab.kind === 'guide') {
            return [
                { type: 'closeTab', tabId: tabId },
                ...dockPlanSetExpanded(state, false),
            ];
        }
        return [{ type: 'closeTab', tabId: tabId }];
    }, seed), area);
}

/** Focus a tab and the pane holding it. */
function dockActionFocusTab(sessionId, tabId, seed, area) {
    return dockSeat(sessionId, (surface) => dockAdvance(surface, (state) => (state.tabs[tabId] === undefined ? [] : dockPlanFocusTab(state, tabId)), seed), area);
}

/** Focus a pane, raising it when it floats. */
function dockActionFocusPane(sessionId, paneId, seed, area) {
    return dockSeat(sessionId, (surface) => dockAdvance(surface, (state) => (state.nodes[paneId] === undefined ? [] : dockPlanFocusPane(state, paneId)), seed), area);
}

/** Put a tab at an explicit slot: a reorder, a move, or a return. */
function dockActionPlaceTab(sessionId, tabId, toPaneId, index, seed, area) {
    return dockSeat(sessionId, (surface) => dockAdvance(
        surface,
        (state) => (state.tabs[tabId] === undefined ? [] : dockArriving(state, tabId, toPaneId, () => dockPlanPlaceTab(state, tabId, toPaneId, index))),
        seed
    ), area);
}

/**
 * Resolve a tab drop inside the docked area. Product rules: this product only
 * accepts horizontal edges and its two-pane ceiling; a second-pane release
 * falls back to a move in the target pane's centre.
 */
function dockActionDropTab(sessionId, tabId, paneId, zone, seed, area) {
    return dockSeat(sessionId, (surface) => dockAdvance(surface, (state, mint) => {
        if (state.tabs[tabId] === undefined) return [];
        const productZone = zone === 'top' || zone === 'bottom' ? 'center' : zone;
        if (productZone !== 'center' && !dockProductCanSplit(state)) return dockArriving(state, tabId, paneId, () => dockPlanDropTab(state, mint, tabId, paneId, 'center', (id) => dockSeedRecord(id, seed())));
        const plan = () => dockPlanDropTab(state, mint, tabId, paneId, productZone, (id) => dockSeedRecord(id, seed()));
        return productZone === 'center' ? dockArriving(state, tabId, paneId, plan) : plan();
    }, seed), area);
}

/** Take a tab out into a floating panel. */
function dockActionFloatTab(sessionId, tabId, rect, seed, area) {
    return dockSeat(sessionId, (surface) => dockAdvance(
        surface,
        (state, mint) => (state.tabs[tabId] === undefined ? [] : dockPlanFloatTab(state, mint, tabId, rect).ops),
        seed
    ), area);
}

/** Return a floating panel's tab to the docked tree. */
function dockActionUnfloatPane(sessionId, paneId, seed, area) {
    return dockSeat(sessionId, (surface) => dockAdvance(surface, (state) => {
        const node = state.nodes[paneId];
        if (node === undefined || node.kind !== 'pane' || node.host !== 'float') return [];
        const floated = node.tabs[0];
        const plan = () => dockPlanUnfloatPane(state, paneId);
        return floated === undefined ? plan() : dockArriving(state, floated, dockActiveDockPaneId(state), plan);
    }, seed), area);
}

/** Record the net position of a floating-panel drag. */
function dockActionMoveFloat(sessionId, paneId, x, y, seed, area) {
    return dockSeat(sessionId, (surface) => dockAdvance(surface, () => [{ type: 'moveFloat', paneId: paneId, x: x, y: y }], seed), area);
}

/** Record the net rectangle of a floating-panel resize. */
function dockActionResizeFloat(sessionId, paneId, rect, seed, area) {
    return dockSeat(sessionId, (surface) => dockAdvance(surface, () => [{ type: 'resizeFloat', paneId: paneId, rect: rect }], seed), area);
}

/** Record the net sizes of a divider drag, clamped to this product's floor. */
function dockActionResizeSplit(sessionId, splitId, sizes, seed, area) {
    return dockSeat(sessionId, (surface) => dockAdvance(surface, () => dockPlanResizeSplit(splitId, sizes, DOCK_PRODUCT_MIN_FRACTION), seed), area);
}

/** Step a surface through the history in one direction. */
function dockActionStep(sessionId, direction, area) {
    return dockSeat(sessionId, (surface) => {
        const moved = direction === 'redo'
            ? dockStepForward(surface.history, surface.layout)
            : dockStepBack(surface.history, surface.layout);
        if (moved === undefined) return surface;
        return { layout: moved.state, history: moved.history, minted: surface.minted };
    }, area);
}

/** Undo one intent, or one run of consecutive focus-only intents. */
function dockActionUndo(sessionId, area) {
    return dockActionStep(sessionId, 'undo', area);
}

/** Redo one intent the matching undo stepped back. */
function dockActionRedo(sessionId, area) {
    return dockActionStep(sessionId, 'redo', area);
}
