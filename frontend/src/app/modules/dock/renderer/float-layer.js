/**
 * The floating layer: one overlay panel per floating pane, bottom-to-top in the
 * model's z order. A floating pane hosts exactly one tab; its header is the
 * strip's row holding that tab's chip, never selectable or closable from the
 * chip, and the send-back and close controls. Pressing a panel's body raises it.
 * Its grip and corner report through their gesture instead: a press released in
 * place is a click and raises the panel; a drag records the move or resize, and
 * that operation raises the panel itself, so one gesture is one intent.
 *
 * The layer owns its own drag and resize gestures, so where it mounts is not
 * part of its contract: panels are positioned in viewport coordinates.
 */

/** One floating-panel gesture: what it moves and where it started. */
function dockDraggedFloatRect(drag, x, y) {
    const dx = x - drag.originX;
    const dy = y - drag.originY;
    return drag.mode === 'move'
        ? dockMovedRect(drag.rect, dx, dy)
        : dockResizedRect(drag.rect, dx, dy, DOCK_FLOAT_MIN_SIZE);
}

function dockSameRect(a, b) {
    return a.x === b.x && a.y === b.y && a.width === b.width && a.height === b.height;
}

/** One floating layer view: renders `state.floats` and reports settled intents. */
class DockFloatLayerView {
    /**
     * @param {object} config The layer's wiring.
     * @param {Element} config.root The host element (its own stacking area).
     * @param {object} config.intents Settled gesture results.
     * @param {object} config.labels Rendered strings.
     * @param {Function} config.renderTab Renders one tab's body.
     * @param {Function} [config.canCloseTab] Whether a tab offers its close control.
     * @param {Function} [config.renderTabTitle] What a chip shows as its title.
     */
    constructor(config) {
        this.root = config.root;
        this.intents = config.intents;
        this.labels = config.labels || {};
        this.renderTab = config.renderTab;
        this.renderTabTitle = config.renderTabTitle;
        this.canCloseTab = config.canCloseTab || dockAlwaysTrue;
        this.state = null;
        this.entries = Object.create(null);
        this.preview = undefined;
        this.beginGesture = dockCreateGestureController(() => {
            this.preview = undefined;
            this.applyPreview();
        });
        this.el = null;
    }

    /** Create the layer element. @returns {Element} */
    mount() {
        const el = document.createElement('div');
        el.className = 'dock-float-layer';
        el.setAttribute('data-dock-float-layer', '1');
        this.el = el;
        if (this.root) this.root.appendChild(el);
        return el;
    }

    /** Remove the layer and every panel in it. */
    destroy() {
        this.entries = Object.create(null);
        if (this.el && this.el.parentNode) this.el.parentNode.removeChild(this.el);
        this.el = null;
    }

    /** Reconcile the layer against a layout snapshot. */
    sync(state) {
        this.state = state;
        const wanted = {};
        for (let i = 0; i < state.floats.length; i += 1) wanted[state.floats[i]] = i;
        const existing = Object.keys(this.entries);
        for (let i = 0; i < existing.length; i += 1) {
            if (wanted[existing[i]] === undefined) {
                const entry = this.entries[existing[i]];
                if (entry.el.parentNode) entry.el.parentNode.removeChild(entry.el);
                delete this.entries[existing[i]];
            }
        }
        for (let i = 0; i < state.floats.length; i += 1) this.renderPanel(state, state.floats[i], i);
    }

    renderPanel(state, paneId, depth) {
        const pane = dockGetPane(state, paneId);
        const tab = dockGetTab(state, dockOnlyTabId(pane));
        let entry = this.entries[paneId];
        if (!entry) {
            const el = document.createElement('div');
            el.className = 'dock-float';
            el.setAttribute('data-dock-float', paneId);
            el.addEventListener('pointerdown', () => this.raise(paneId));
            const header = document.createElement('header');
            header.className = 'dock-float-header';
            header.setAttribute('data-dock-float-grip', paneId);
            header.addEventListener('pointerdown', (event) => this.drag('move', paneId, event));
            const title = document.createElement('div');
            title.className = 'dock-chip dock-float-title';
            const titleText = document.createElement('span');
            titleText.className = 'dock-chip-title';
            title.appendChild(titleText);
            const fill = document.createElement('div');
            fill.className = 'dock-strip-fill';
            const dockButton = document.createElement('button');
            dockButton.type = 'button';
            dockButton.className = 'dock-icon-button';
            dockButton.setAttribute('data-dock-float-dock', paneId);
            dockButton.setAttribute('aria-label', this.labels.dockFloat || '放回主区');
            dockButton.innerHTML = '<span aria-hidden="true">⇤</span>';
            dockButton.addEventListener('pointerdown', (event) => event.stopPropagation());
            dockButton.addEventListener('click', () => this.intents.unfloatPane(paneId));
            const closeButton = document.createElement('button');
            closeButton.type = 'button';
            closeButton.className = 'dock-icon-button';
            closeButton.setAttribute('data-dock-float-close', paneId);
            closeButton.setAttribute('aria-label', this.labels.closeFloat || '关闭浮窗');
            closeButton.innerHTML = '<span aria-hidden="true">×</span>';
            closeButton.addEventListener('pointerdown', (event) => event.stopPropagation());
            closeButton.addEventListener('click', () => this.intents.closeTab(tab.id));
            header.appendChild(title);
            header.appendChild(fill);
            header.appendChild(dockButton);
            header.appendChild(closeButton);
            const body = document.createElement('div');
            body.className = 'dock-float-body';
            const resize = document.createElement('div');
            resize.className = 'dock-float-resize';
            resize.setAttribute('data-dock-float-resize', paneId);
            resize.addEventListener('pointerdown', (event) => this.drag('resize', paneId, event));
            el.appendChild(header);
            el.appendChild(body);
            el.appendChild(resize);
            entry = { el: el, titleText: titleText, body: body, tabId: undefined, closeButton: closeButton };
            this.entries[paneId] = entry;
            this.el.appendChild(el);
        }
        if (entry.tabId !== tab.id) {
            const bodyEl = this.renderTab(tab);
            entry.body.replaceChildren(bodyEl);
            entry.tabId = tab.id;
            entry.closeButton.hidden = !this.canCloseTab(tab.id);
        }
        const titleValue = this.renderTabTitle ? this.renderTabTitle(tab) : tab.title;
        entry.titleText.textContent = String(titleValue === undefined || titleValue === null ? tab.title : titleValue);
        entry.el.setAttribute('data-dock-float-active', state.activePaneId === paneId ? '1' : '');
        const live = this.preview && this.preview.paneId === paneId ? this.preview.rect : dockFloatRect(pane);
        entry.el.style.left = Math.round(live.x) + 'px';
        entry.el.style.top = Math.round(live.y) + 'px';
        entry.el.style.width = Math.round(live.width) + 'px';
        entry.el.style.height = Math.round(live.height) + 'px';
        entry.el.style.zIndex = String(this.preview && this.preview.paneId === paneId ? state.floats.length + 1 : depth + 1);
    }

    applyPreview() {
        if (!this.state) return;
        for (let i = 0; i < this.state.floats.length; i += 1) this.renderPanel(this.state, this.state.floats[i], i);
    }

    /** Focus and raise a panel from a press, unless it is raised already. */
    raise(paneId) {
        const state = this.state;
        if (!state) return;
        const top = state.floats[state.floats.length - 1];
        if (state.activePaneId === paneId && top === paneId) return;
        this.intents.focusPane(paneId);
    }

    /** Start a move or resize from a press on the panel's grip or corner. */
    drag(mode, paneId, event) {
        if (event.button !== 0) return;
        event.stopPropagation();
        event.preventDefault();
        if (!this.state) return;
        const start = {
            mode: mode,
            originX: event.clientX,
            originY: event.clientY,
            rect: dockFloatRect(dockGetPane(this.state, paneId)),
        };
        this.beginGesture(event.currentTarget, event.pointerId, {
            move: (moved) => {
                this.preview = { paneId: paneId, rect: dockDraggedFloatRect(start, moved.clientX, moved.clientY) };
                this.applyPreview();
            },
            up: (released) => {
                const rect = dockDraggedFloatRect(start, released.clientX, released.clientY);
                if (dockSameRect(rect, start.rect)) {
                    this.raise(paneId);
                    return;
                }
                if (mode === 'move') this.intents.moveFloat(paneId, rect.x, rect.y);
                else this.intents.resizeFloat(paneId, rect);
            },
        });
    }
}
