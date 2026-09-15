/**
 * DOM side of the room rule: read each docked pane's rectangles after a commit
 * and ask `dockHalvesFit` whether a split would leave two working halves.
 * Pixels live here and in geometry.js; the engine's planners never see them.
 */

/** What an unmeasured pane is taken to be: fitting, until a reading says otherwise. */
const DOCK_UNMEASURED_FIT = { row: true, column: true };

/** Nothing measured yet. */
function dockNoFits() {
    return new Map();
}

function dockRectOf(element) {
    if (!element) return { x: 0, y: 0, width: 0, height: 0 };
    return element.getBoundingClientRect();
}

function dockPx(value) {
    const parsed = Number.parseFloat(value);
    return Number.isFinite(parsed) ? parsed : 0;
}

/**
 * Every docked pane element under `root`, in document order, with the pane id
 * each carries.
 * @param {Element} root The docked surface's element.
 * @returns {Array<[string,Element]>} pane ids paired with their elements.
 */
function dockPaneElements(root) {
    const panes = [];
    if (!root || !root.querySelectorAll) return panes;
    const found = root.querySelectorAll('[data-dock-pane]');
    for (let i = 0; i < found.length; i += 1) {
        const paneId = found[i].getAttribute('data-dock-pane');
        if (paneId) panes.push([paneId, found[i]]);
    }
    return panes;
}

/**
 * One chip's minimum footprint from a rendered chip's computed style; the
 * stylesheet fallback where none is rendered or styles are not applied.
 */
function dockChipMinimum(root) {
    const chip = root.querySelector('[data-dock-tab]');
    if (!chip) return DOCK_SPLIT_MINIMUMS.chip;
    const style = getComputedStyle(chip);
    const min = dockPx(style.minWidth);
    if (min <= 0) return DOCK_SPLIT_MINIMUMS.chip;
    if (style.boxSizing === 'border-box') return min;
    return min + dockPx(style.paddingLeft) + dockPx(style.paddingRight) + dockPx(style.borderLeftWidth) + dockPx(style.borderRightWidth);
}

/** A rendered divider's thickness, or the stylesheet fallback before the first split. */
function dockDividerSize(root) {
    const divider = root.querySelector('[data-dock-divider]');
    if (!divider) return DOCK_SPLIT_MINIMUMS.divider;
    const rect = divider.getBoundingClientRect();
    const thickness = Math.min(rect.width, rect.height);
    return thickness > 0 ? thickness : DOCK_SPLIT_MINIMUMS.divider;
}

/**
 * The rendered split control's footprint in the strip's fixed part: its box
 * plus the strip's own gap, both of which the strip sheds when the control
 * hides. 0 while the control is hidden or unmeasured.
 */
function dockSplitControlFootprint(pane) {
    const control = pane.querySelector('[data-dock-split-button]');
    if (!control) return 0;
    const width = control.getBoundingClientRect().width;
    if (!(width > 0)) return 0;
    const strip = pane.querySelector('[data-dock-strip]');
    return width + (strip ? dockPx(getComputedStyle(strip).columnGap) : 0);
}

/**
 * Measure every docked pane under `root`.
 * @param {Element} root The docked surface's element.
 * @param {boolean} [splitHiddenWhenBlocked] Whether the embedder hides blocked
 *   split controls; the room rule then leaves the control's footprint out of
 *   each strip's fixed part, so the reading cannot flip with the control's
 *   visibility.
 * @returns {Map<string,{row:boolean,column:boolean}>} each pane's fit, keyed by pane id.
 */
function dockMeasurePaneFits(root, splitHiddenWhenBlocked) {
    const minimums = {
        divider: dockDividerSize(root),
        chip: dockChipMinimum(root),
        body: DOCK_SPLIT_MINIMUMS.body,
        stripHeight: DOCK_SPLIT_MINIMUMS.stripHeight,
    };
    const fits = new Map();
    const panes = dockPaneElements(root);
    for (let i = 0; i < panes.length; i += 1) {
        const paneId = panes[i][0];
        const pane = panes[i][1];
        fits.set(paneId, dockHalvesFit({
            pane: dockRectOf(pane),
            strip: dockRectOf(pane.querySelector('[data-dock-strip]')),
            chipsWidth: dockRectOf(pane.querySelector('[data-dock-strip-tabs]')).width,
            fillWidth: dockRectOf(pane.querySelector('[data-dock-strip-fill]')).width,
            splitControlWidth: splitHiddenWhenBlocked ? dockSplitControlFootprint(pane) : 0,
        }, minimums));
    }
    return fits;
}

/**
 * One pane's latest reading. A pane the map does not name has not been
 * measured and fits: the rule only blocks on a positive reading.
 * @param {Map} fits The latest measurement.
 * @param {string} paneId The pane asked about.
 * @returns {{row:boolean,column:boolean}} whether each split axis leaves two working halves.
 */
function dockFitOf(fits, paneId) {
    return (fits && fits.get(paneId)) || DOCK_UNMEASURED_FIT;
}

/**
 * Whether two measurements agree, so a re-measure that changed nothing
 * re-renders nothing.
 * @param {Map} a One measurement.
 * @param {Map} b The other.
 * @returns {boolean} whether both name the same panes with the same readings.
 */
function dockSameFits(a, b) {
    if (!a || !b || a.size !== b.size) return false;
    for (const entry of a) {
        const other = b.get(entry[0]);
        if (!other || other.row !== entry[1].row || other.column !== entry[1].column) return false;
    }
    return true;
}
