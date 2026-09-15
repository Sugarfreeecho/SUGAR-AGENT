/**
 * Interaction limits and dock geometry. The model itself is unbounded; these
 * are the rules the interaction layer enforces before it dispatches, kept pure
 * so they can be asserted without a browser.
 */

/** Caps the docked grid; floating panes do not count. */
const DOCK_MAX_PANES = 4;

/** Smallest fraction a divider drag may leave a pane, as a share of its split. */
const DOCK_MIN_PANE_FRACTION = 0.12;

/** Size a tab takes when it first floats, in CSS pixels. */
const DOCK_FLOAT_DEFAULT_SIZE = { width: 380, height: 300 };

/** Smallest size a floating panel may be resized to, in CSS pixels. */
const DOCK_FLOAT_MIN_SIZE = { width: 220, height: 140 };

/** Fraction of a pane's width or height that counts as its dock edge. */
const DOCK_EDGE_FRACTION = 0.25;

/** The five dock regions a tab can be dropped on. */
const DOCK_ZONES = ['center', 'top', 'right', 'bottom', 'left'];

/**
 * Number of docked panes.
 * @param {object} state Current layout.
 * @returns {number} how many panes the docked tree holds; floating panes do not count.
 */
function dockPaneCount(state) {
    return dockPaneIds(state).length;
}

/**
 * Whether another docked pane is allowed by the engine budget.
 * @param {object} state Current layout.
 * @returns {boolean} whether the docked tree is under `DOCK_MAX_PANES`.
 */
function dockCanSplit(state) {
    return dockPaneCount(state) < DOCK_MAX_PANES;
}

/**
 * Which dock region a pointer sits in.
 * @param {number} x Pointer x as a fraction of pane width.
 * @param {number} y Pointer y as a fraction of pane height.
 * @param {number} [edge] Edge band width as a fraction; defaults to `DOCK_EDGE_FRACTION`.
 * @returns {string} the closest edge when the pointer is inside its band, else 'center'.
 */
function dockZoneAt(x, y, edge) {
    const band = typeof edge === 'number' ? edge : DOCK_EDGE_FRACTION;
    let zone = 'left';
    let distance = x;
    if (1 - x < distance) { zone = 'right'; distance = 1 - x; }
    if (y < distance) { zone = 'top'; distance = y; }
    if (1 - y < distance) { zone = 'bottom'; distance = 1 - y; }
    return distance < band ? zone : 'center';
}

/**
 * How a dock region splits the pane it targets.
 * @param {string} zone The region the pointer released in.
 * @returns {{axis:string,direction:string}|undefined} the split's axis and
 *   direction, or undefined for 'center', which moves the tab into the pane.
 */
function dockZoneSplit(zone) {
    switch (zone) {
        case 'center': return undefined;
        case 'left': return { axis: 'row', direction: 'before' };
        case 'right': return { axis: 'row', direction: 'after' };
        case 'top': return { axis: 'column', direction: 'before' };
        case 'bottom': return { axis: 'column', direction: 'after' };
        default: return dockAssertNever(zone, 'layout: dock zone');
    }
}

/**
 * Clamp divider sizes so no pane falls under the minimum fraction.
 * @param {number[]} sizes Candidate fractions from the drag preview.
 * @param {number} [minimum] Smallest allowed share; defaults to `DOCK_MIN_PANE_FRACTION`.
 * @returns {number[]} fractions summing to 1 with every entry at or above the minimum.
 */
function dockClampSizes(sizes, minimum) {
    if (sizes.length === 0) return [];
    const floor = Math.min(typeof minimum === 'number' ? minimum : DOCK_MIN_PANE_FRACTION, 1 / sizes.length);
    const positive = sizes.map((size) => (size > 0 ? size : 0));
    let total = 0;
    for (let i = 0; i < positive.length; i += 1) total += positive[i];
    let shares = total > 0 ? positive.map((size) => size / total) : positive.map(() => 1 / sizes.length);
    // Pin every share under the floor at the floor and hand the remainder to
    // the others in proportion; a share that only now drops under joins the
    // pinned set on the next pass, so the result holds the floor exactly.
    const pinned = [];
    for (;;) {
        const under = [];
        for (let i = 0; i < shares.length; i += 1) {
            if (pinned.indexOf(i) < 0 && shares[i] < floor) under.push(i);
        }
        if (under.length === 0) return shares;
        for (let i = 0; i < under.length; i += 1) pinned.push(under[i]);
        const remainder = 1 - pinned.length * floor;
        let freeTotal = 0;
        for (let i = 0; i < shares.length; i += 1) {
            if (pinned.indexOf(i) < 0) freeTotal += shares[i];
        }
        shares = shares.map((share, index) => (pinned.indexOf(index) >= 0 ? floor : (share / freeTotal) * remainder));
    }
}
