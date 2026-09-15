/**
 * Pure geometry for the drag interaction: point tests, dock-zone resolution
 * against a real element rectangle, tab-strip insertion slots, and the room
 * rule. Kept free of DOM types so the drop rules can be asserted without a
 * browser; the renderer layer measures rectangles and calls in.
 */

/**
 * Whether a point is inside a rectangle, edges included.
 * @param {{x:number,y:number,width:number,height:number}} rect The rectangle.
 * @param {number} x Point x in the same coordinates.
 * @param {number} y Point y in the same coordinates.
 * @returns {boolean} whether the point lies on or inside the rectangle.
 */
function dockContainsPoint(rect, x, y) {
    return x >= rect.x && x <= rect.x + rect.width && y >= rect.y && y <= rect.y + rect.height;
}

/**
 * Dock region a point falls in, relative to one pane's rectangle.
 * @param {{x:number,y:number,width:number,height:number}} rect The pane's measured box.
 * @param {number} x Pointer x in the same coordinates.
 * @param {number} y Pointer y in the same coordinates.
 * @param {number} [edge] Edge band as a fraction; defaults to the model's value.
 * @returns {string} the region; 'center' when the point is not in an edge band.
 */
function dockZoneInRect(rect, x, y, edge) {
    if (!(rect.width > 0) || !(rect.height > 0)) return 'center';
    return dockZoneAt((x - rect.x) / rect.width, (y - rect.y) / rect.height, edge);
}

/**
 * Slot a tab would take in a strip, by comparing the pointer with each tab's midpoint.
 * @param {Array<{x:number,width:number}>} tabRects The strip's tab boxes in strip order.
 * @param {number} x Pointer x.
 * @returns {number} the insertion index, from 0 to `tabRects.length`.
 */
function dockInsertionIndex(tabRects, x) {
    let index = 0;
    for (let i = 0; i < tabRects.length; i += 1) {
        const rect = tabRects[i];
        if (x < rect.x + rect.width / 2) break;
        index += 1;
    }
    return index;
}

/**
 * Pixel minimums the room rule holds each half to.
 * Mirrors the stylesheet: a chip is 100px (80px min-width + 10px padding a
 * side, content-box); the divider takes no layout room (its hairline paints
 * over the seam, so a body's own rules run unbroken past it); a column half
 * must carry the strip plus a minimum body.
 */
const DOCK_SPLIT_MINIMUMS = { divider: 0, chip: 100, body: 48, stripHeight: 34 };

/**
 * The room rule. After an equal split each half must hold what cannot shrink:
 * horizontally the strip's fixed part — its width minus the chip box, the
 * fill, and the rendered split control's footprint — plus one chip at its
 * minimum; vertically the strip plus a minimum body. An unmeasured pane (no
 * layout) fits: the rule only blocks on a positive reading.
 * @param {{pane:object,strip:object,chipsWidth:number,fillWidth:number,splitControlWidth:number}} measure The pane's rectangles.
 * @param {object} [minimums] The pixel minimums; defaults to the stylesheet's.
 * @returns {{row:boolean,column:boolean}} whether a row and a column split each leave two working halves.
 */
function dockHalvesFit(measure, minimums) {
    const mins = minimums || DOCK_SPLIT_MINIMUMS;
    const pane = measure.pane;
    const strip = measure.strip;
    if (!(pane.width > 0) || !(pane.height > 0) || !(strip.width > 0)) return { row: true, column: true };
    const borders = Math.max(0, pane.width - strip.width);
    const control = Number(measure.splitControlWidth) || 0;
    const fixed = Math.max(0, strip.width - measure.chipsWidth - measure.fillWidth - control);
    const halfWidth = (pane.width - mins.divider) / 2 - borders;
    const halfHeight = (pane.height - mins.divider) / 2 - borders;
    return {
        row: halfWidth >= fixed + mins.chip,
        column: halfHeight >= (mins.stripHeight || DOCK_SPLIT_MINIMUMS.stripHeight) + mins.body,
    };
}

/** How far a pointer must travel before a press becomes a drag, in pixels. */
const DOCK_DRAG_THRESHOLD = 4;

/**
 * Whether a press has travelled far enough to be a drag.
 * @param {number} startX Press x.
 * @param {number} startY Press y.
 * @param {number} x Current pointer x.
 * @param {number} y Current pointer y.
 * @returns {boolean} whether either axis moved at least `DOCK_DRAG_THRESHOLD`.
 */
function dockPassedThreshold(startX, startY, x, y) {
    return Math.abs(x - startX) >= DOCK_DRAG_THRESHOLD || Math.abs(y - startY) >= DOCK_DRAG_THRESHOLD;
}

/**
 * Split fractions after a divider drag.
 * @param {number[]} sizes The split's current fractions.
 * @param {number} index Divider position: the boundary between `index` and `index + 1`.
 * @param {number} delta Pointer travel along the split axis, as a fraction of the split's extent.
 * @returns {number[]} new fractions; the two neighbours absorb the whole change.
 */
function dockDividerSizes(sizes, index, delta) {
    const before = sizes[index];
    const after = sizes[index + 1];
    if (before === undefined || after === undefined) return sizes.slice();
    const next = sizes.slice();
    next[index] = before + delta;
    next[index + 1] = after - delta;
    return next;
}

/**
 * A floating panel's rectangle after a drag.
 * @param {object} rect The rectangle the gesture started from.
 * @param {number} dx Pointer travel on x.
 * @param {number} dy Pointer travel on y.
 * @returns {object} the moved rectangle; the size is unchanged.
 */
function dockMovedRect(rect, dx, dy) {
    return Object.assign({}, rect, { x: rect.x + dx, y: rect.y + dy });
}

/**
 * A floating panel's rectangle after a bottom-right resize.
 * @param {object} rect The rectangle the gesture started from.
 * @param {number} dx Pointer travel on x.
 * @param {number} dy Pointer travel on y.
 * @param {{width:number,height:number}} min Smallest size the panel may take.
 * @returns {object} the resized rectangle; the origin is unchanged.
 */
function dockResizedRect(rect, dx, dy, min) {
    return Object.assign({}, rect, {
        width: Math.max(min.width, rect.width + dx),
        height: Math.max(min.height, rect.height + dy),
    });
}

/** How far a new panel's origin sits above and left of the drop point. */
const DOCK_FLOAT_GRAB_OFFSET = { x: 60, y: 14 };

/**
 * Where a panel should appear when a tab is dropped outside the docked area.
 * @param {number} x Drop point x.
 * @param {number} y Drop point y.
 * @param {{width:number,height:number}} size The panel's size.
 * @returns {object} a rectangle whose header sits under the drop point.
 */
function dockFloatRectAt(x, y, size) {
    return {
        x: Math.max(0, x - DOCK_FLOAT_GRAB_OFFSET.x),
        y: Math.max(0, y - DOCK_FLOAT_GRAB_OFFSET.y),
        width: size.width,
        height: size.height,
    };
}
