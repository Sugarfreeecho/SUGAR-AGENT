/**
 * The docked surface: the split tree plus the tab and divider gestures over it.
 * This is the whole dock surface as far as the app's layout area is concerned —
 * chrome around it (a tool button, a collapsed presentation) belongs to the
 * embedder.
 *
 * A gesture only previews until it ends, then leaves through one intent call,
 * so the embedder's operation sequence stays the single source of truth.
 * Releasing a tab clear of this surface floats it; releasing inside it but on
 * no pane is not a move at all.
 *
 * Interaction rules copied from dsh's DockSurface/TabPanel, each one fixing a
 * defect found in a real browser:
 *   - the pointer is captured when a gesture starts;
 *   - the chips give way, the strip's end controls never do (CSS-side);
 *   - the chip box scrolls but never claims a gesture (touch-action: none);
 *   - focus lands on click, not on press;
 *   - a control nested inside a draggable chip stops its own press;
 *   - a divider drag is absorbed by its two neighbours and clamped.
 */

/** Width of the chip box's fade at a hidden side; mirrors the stylesheet's 24px. */
const DOCK_STRIP_FADE = 24;

/** The default policy for omitted callbacks: every pane offers add, every tab its close. */
function dockAlwaysTrue() {
    return true;
}

/** Fractions closer than this are the same split. */
const DOCK_SIZE_TOLERANCE = 1e-9;

function dockSameSizes(a, b) {
    if (!a || !b || a.length !== b.length) return false;
    for (let i = 0; i < a.length; i += 1) {
        if (Math.abs(a[i] - b[i]) >= DOCK_SIZE_TOLERANCE) return false;
    }
    return true;
}

/**
 * One docked surface view: renders a layout snapshot into DOM and reports
 * settled intents. No framework; the embedder drives `sync(state)` whenever the
 * store's snapshot changes.
 */
class DockSurfaceView {
    /**
     * @param {object} config The surface's wiring.
     */
    constructor(config) {
        this.root = config.root;
        this.labels = config.labels || {};
        this.renderTab = config.renderTab;
        this.renderTabTitle = config.renderTabTitle;
        this.canAddTab = config.canAddTab || dockAlwaysTrue;
        this.canCloseTab = config.canCloseTab || dockAlwaysTrue;
        this.canSplitSurface = config.canSplitSurface || dockAlwaysTrue;
        this.hideSplitWhenBlocked = !!config.hideSplitWhenBlocked;
        this.dropZones = config.dropZones === 'horizontal' ? 'horizontal' : 'edges';
        this.minPaneFraction = typeof config.minPaneFraction === 'number' ? config.minPaneFraction : DOCK_MIN_PANE_FRACTION;
        this.intents = config.intents;
        this.onRoom = config.onRoom;
        this.onTabRemoved = config.onTabRemoved;
        this.chrome = config.chrome || null;

        this.state = null;
        this.paneEls = Object.create(null);
        this.tabBodies = Object.create(null);
        this.fits = dockNoFits();
        this.preview = { draggingTabId: undefined, dropTarget: undefined, sizes: undefined };
        this.beginGesture = dockCreateGestureController(() => {
            this.preview = { draggingTabId: undefined, dropTarget: undefined, sizes: undefined };
            this.applyPreview();
        });
        this.el = null;
        this.observer = null;
        this.menu = null;
    }

    /** Create the surface element and start watching for room-rule readings. */
    mount() {
        const el = document.createElement('div');
        el.className = 'dock-surface';
        el.setAttribute('data-dock-surface', '1');
        el.setAttribute('data-dock-drop-zones', this.dropZones);
        this.el = el;
        if (this.root) this.root.appendChild(el);
        if (typeof ResizeObserver === 'function') {
            this.observer = new ResizeObserver(() => this.remeasure());
            this.observer.observe(el);
        }
        return el;
    }

    /** Remove the surface and every listener it owns. */
    destroy() {
        this.dismissMenu();
        if (this.observer) this.observer.disconnect();
        this.observer = null;
        this.paneEls = Object.create(null);
        this.tabBodies = Object.create(null);
        if (this.el && this.el.parentNode) this.el.parentNode.removeChild(this.el);
        this.el = null;
    }

    /**
     * Reconcile the whole surface against a layout snapshot.
     * @param {object} state Current layout.
     */
    sync(state) {
        this.state = state;
        this.renderTree();
        this.renderFloatsRemovedTabs(state);
        this.applyPreview();
        this.updateStripFades();
        this.remeasure();
    }

    /** Hand a tab body to the embedder when the tab is gone, so it can stop what it started. */
    renderFloatsRemovedTabs(state) {
        const ids = Object.keys(this.tabBodies);
        for (let i = 0; i < ids.length; i += 1) {
            if (state.tabs[ids[i]] === undefined) {
                const element = this.tabBodies[ids[i]];
                delete this.tabBodies[ids[i]];
                if (this.onTabRemoved) this.onTabRemoved(ids[i], element);
            }
        }
        // A tab can move to a floating pane: its body leaves the docked surface.
        const docked = {};
        const panes = dockPaneIds(state);
        for (let i = 0; i < panes.length; i += 1) {
            const tabs = state.nodes[panes[i]].tabs;
            for (let j = 0; j < tabs.length; j += 1) docked[tabs[j]] = true;
        }
        const bodyIds = Object.keys(this.tabBodies);
        for (let i = 0; i < bodyIds.length; i += 1) {
            if (docked[bodyIds[i]] !== true) {
                const element = this.tabBodies[bodyIds[i]];
                if (element && element.parentNode) element.parentNode.removeChild(element);
            }
        }
    }

    /** Rebuild the split shell, reusing pane elements (and their focus) by id. */
    renderTree() {
        const state = this.state;
        const shell = this.buildNode(state.rootId);
        const current = this.el.firstChild;
        if (current !== shell) this.el.replaceChildren(shell);
        const ids = dockPaneIds(state);
        for (let i = 0; i < ids.length; i += 1) this.renderPane(state, ids[i]);
    }

    buildNode(nodeId) {
        const state = this.state;
        const node = dockGetNode(state, nodeId);
        if (node.kind === 'pane') return this.ensurePane(node);
        const split = document.createElement('div');
        split.className = 'dock-split dock-split--' + node.axis;
        split.setAttribute('data-dock-split', node.id);
        const sizes = this.preview.sizes && this.preview.sizes.splitId === node.id ? this.preview.sizes.sizes : node.sizes;
        for (let i = 0; i < node.children.length; i += 1) {
            if (i > 0) {
                const divider = document.createElement('div');
                divider.className = 'dock-divider';
                divider.setAttribute('data-dock-divider', node.id + ':' + (i - 1));
                divider.addEventListener('pointerdown', (event) => this.onDividerPressed(node.id, i - 1, event));
                split.appendChild(divider);
            }
            const cell = document.createElement('div');
            cell.className = 'dock-cell';
            cell.setAttribute('data-dock-cell', node.id + ':' + i);
            cell.style.flexGrow = String(sizes[i]);
            cell.appendChild(this.buildNode(node.children[i]));
            split.appendChild(cell);
        }
        return split;
    }

    ensurePane(pane) {
        let entry = this.paneEls[pane.id];
        if (entry) return entry.el;
        const el = document.createElement('section');
        el.className = 'dock-pane';
        el.setAttribute('data-dock-pane', pane.id);
        el.addEventListener('click', () => {
            if (!this.state || this.state.activePaneId === pane.id) return;
            this.intents.focusPane(pane.id);
        });
        const strip = document.createElement('div');
        strip.className = 'dock-strip';
        strip.setAttribute('data-dock-strip', pane.id);
        strip.setAttribute('role', 'tablist');
        const tabsBox = document.createElement('div');
        tabsBox.className = 'dock-strip-tabs';
        tabsBox.setAttribute('data-dock-strip-tabs', pane.id);
        tabsBox.addEventListener('scroll', () => this.updateStripFadeFor(tabsBox), { passive: true });
        const fill = document.createElement('div');
        fill.className = 'dock-strip-fill';
        fill.setAttribute('data-dock-strip-fill', pane.id);
        const addButton = document.createElement('button');
        addButton.type = 'button';
        addButton.className = 'dock-icon-button dock-add-tab';
        addButton.setAttribute('aria-label', this.labels.addTab || '添加标签');
        addButton.textContent = '+';
        addButton.addEventListener('click', (event) => {
            event.stopPropagation();
            this.intents.addTab(pane.id);
        });
        const splitButton = document.createElement('button');
        splitButton.type = 'button';
        splitButton.className = 'dock-icon-button dock-split-button';
        splitButton.setAttribute('data-dock-split-button', pane.id);
        // The embedder may hand in its own glyph markup (the console's split
        // icon is the dock frame with the divider at its centre); the text
        // glyph is only a fallback for contexts that pass none.
        splitButton.innerHTML = this.labels.splitIconSVG || '<span aria-hidden="true">▥</span>';
        splitButton.addEventListener('click', (event) => {
            event.stopPropagation();
            const block = this.splitBlock(pane.id);
            if (block) return;
            this.intents.splitPane(pane.id);
        });
        const chrome = document.createElement('div');
        chrome.className = 'dock-strip-chrome';
        chrome.setAttribute('data-dock-strip-chrome', pane.id);
        chrome.addEventListener('click', (event) => event.stopPropagation());
        const body = document.createElement('div');
        body.className = 'dock-pane-body';
        body.setAttribute('data-dock-pane-body', pane.id);
        strip.appendChild(tabsBox);
        strip.appendChild(addButton);
        strip.appendChild(fill);
        strip.appendChild(splitButton);
        strip.appendChild(chrome);
        el.appendChild(strip);
        el.appendChild(body);
        entry = { el: el, strip: strip, tabsBox: tabsBox, addButton: addButton, splitButton: splitButton, chrome: chrome, body: body, chips: Object.create(null), bodyTabId: undefined };
        this.paneEls[pane.id] = entry;
        return el;
    }

    /** Update one pane: active flag, chips, strip controls, and the active body. */
    renderPane(state, paneId) {
        const pane = dockGetPane(state, paneId);
        const entry = this.paneEls[paneId];
        if (!entry) return;
        if (state.activePaneId === paneId) entry.el.setAttribute('data-dock-pane-active', '1');
        else entry.el.removeAttribute('data-dock-pane-active');

        this.renderChips(state, pane, entry);

        const addAllowed = this.canAddTab(paneId);
        entry.addButton.hidden = !addAllowed;
        const block = this.splitBlock(paneId);
        const hide = this.hideSplitWhenBlocked && block !== undefined;
        entry.splitButton.hidden = hide;
        entry.splitButton.disabled = block !== undefined;
        entry.splitButton.setAttribute('data-dock-split-blocked', block || '');
        entry.splitButton.setAttribute('aria-label', block === 'width'
            ? (this.labels.splitPaneNarrow || '当前面板宽度不足以再分屏')
            : block === 'budget'
                ? (this.labels.splitPaneDisabled || '分屏数量已达上限')
                : (this.labels.splitPane || '左右分屏'));
        entry.splitButton.title = block === 'width'
            ? (this.labels.splitPaneNarrow || '当前面板宽度不足以再分屏')
            : block === 'budget'
                ? (this.labels.splitPaneDisabled || '分屏数量已达上限')
                : (this.labels.splitPane || '左右分屏');

        const topRight = dockTopRightPaneId(state);
        const wantsChrome = paneId === topRight && this.chrome;
        if (wantsChrome && entry.chrome.childNodes.length === 0) entry.chrome.appendChild(this.chrome);
        entry.chrome.hidden = !wantsChrome;

        // The active tab's body: cached by tab id so a conversation view keeps
        // its scroll position, its stream, and its listeners across commits.
        const activeTab = pane.activeTabId === undefined ? undefined : state.tabs[pane.activeTabId];
        if (activeTab === undefined) {
            if (entry.bodyTabId !== undefined) {
                entry.body.replaceChildren();
                entry.bodyTabId = undefined;
            }
            if (!entry.emptyLabel) {
                entry.emptyLabel = document.createElement('p');
                entry.emptyLabel.className = 'dock-empty';
            }
            entry.emptyLabel.textContent = this.labels.emptyPane || '此面板暂无内容';
            if (entry.body.firstChild !== entry.emptyLabel) entry.body.replaceChildren(entry.emptyLabel);
            return;
        }
        let bodyEl = this.tabBodies[activeTab.id];
        if (bodyEl === undefined) {
            bodyEl = this.renderTab(activeTab);
            this.tabBodies[activeTab.id] = bodyEl;
        }
        if (entry.body.firstChild !== bodyEl) entry.body.replaceChildren(bodyEl);
        // A body re-attached after another tab held the pane restores its own
        // scroll position: detaching a scroller drops it in the browser.
        if (typeof bodyEl.__dockRestore === 'function') bodyEl.__dockRestore();
        entry.bodyTabId = activeTab.id;
    }

    renderChips(state, pane, entry) {
        const focusedChip = document.activeElement && document.activeElement.closest ? document.activeElement.closest('[data-dock-tab]') : null;
        const focusedTabId = focusedChip && entry.tabsBox.contains(focusedChip) ? focusedChip.getAttribute('data-dock-tab') : null;
        const target = this.preview.dropTarget;
        const stripIndex = target && target.kind === 'strip' && target.paneId === pane.id ? target.index : undefined;

        const children = [];
        for (let i = 0; i < pane.tabs.length; i += 1) {
            if (i > 0 || stripIndex === i) {
                children.push(this.makeSlot(i, stripIndex === i));
            }
            children.push(this.makeChip(state, pane, pane.tabs[i]));
        }
        if (stripIndex === pane.tabs.length && pane.tabs.length > 0) children.push(this.makeSlot(pane.tabs.length, true));
        entry.tabsBox.replaceChildren.apply(entry.tabsBox, children);
        entry.chips = Object.create(null);
        for (let i = 0; i < pane.tabs.length; i += 1) entry.chips[pane.tabs[i]] = true;

        if (focusedTabId) {
            const chip = entry.tabsBox.querySelector('[data-dock-tab="' + this.escapeAttr(focusedTabId) + '"]');
            if (chip && typeof chip.focus === 'function') chip.focus({ preventScroll: true });
        }
        if (pane.activeTabId !== undefined) this.scrollChipIntoView(entry, pane.activeTabId);
    }

    makeSlot(index, caret) {
        const slot = document.createElement('div');
        slot.className = 'dock-slot' + (caret ? ' dock-slot--caret' : '');
        slot.setAttribute('data-dock-slot', String(index));
        return slot;
    }

    makeChip(state, pane, tabId) {
        const tab = state.tabs[tabId];
        const selected = tabId === pane.activeTabId;
        const closable = this.canCloseTab(tabId);
        const quiet = !closable && pane.tabs.length === 1;
        const chip = document.createElement('div');
        chip.className = 'dock-chip' + (selected ? ' is-active' : '') + (quiet ? ' is-quiet' : '') + (this.preview.draggingTabId === tabId ? ' is-dragging' : '');
        chip.setAttribute('role', 'tab');
        chip.setAttribute('aria-selected', selected ? 'true' : 'false');
        chip.setAttribute('tabindex', selected ? '0' : '-1');
        chip.setAttribute('data-dock-tab', tabId);
        chip.addEventListener('contextmenu', (event) => {
            event.preventDefault();
            this.openMenu(tabId, event.currentTarget);
        });
        chip.addEventListener('pointerdown', (event) => {
            // A secondary press is the menu, never a drag.
            if (event.button === 2) return;
            this.onChipPressed(tabId, event);
        });
        chip.addEventListener('click', (event) => {
            event.stopPropagation();
            this.activateTab(state, pane, tabId);
        });
        chip.addEventListener('keydown', (event) => {
            if (event.target !== event.currentTarget) return;
            const next = this.chipToFocus(event.key, pane.tabs, tabId);
            if (next !== undefined) {
                event.preventDefault();
                const nextChip = this.paneEls[pane.id] && this.paneEls[pane.id].tabsBox.querySelector('[data-dock-tab="' + this.escapeAttr(next) + '"]');
                if (nextChip) nextChip.focus();
                return;
            }
            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                this.activateTab(state, pane, tabId);
            }
        });
        chip.addEventListener('dragstart', (event) => event.preventDefault());
        const title = document.createElement('span');
        title.className = 'dock-chip-title';
        if (this.renderTabTitle) {
            const rendered = this.renderTabTitle(tab);
            if (rendered && rendered.nodeType === 1) title.appendChild(rendered);
            else title.textContent = String(rendered === undefined || rendered === null ? tab.title : rendered);
        } else {
            title.textContent = tab.title;
        }
        chip.appendChild(title);
        if (closable) {
            const close = document.createElement('button');
            close.type = 'button';
            close.className = 'dock-chip-close';
            close.setAttribute('data-dock-tab-close', tabId);
            close.setAttribute('aria-label', this.labels.closeTab || '关闭标签');
            close.textContent = '×';
            close.addEventListener('pointerdown', (event) => event.stopPropagation());
            close.addEventListener('click', (event) => {
                event.stopPropagation();
                this.intents.closeTab(tabId);
            });
            chip.appendChild(close);
        }
        return chip;
    }

    chipToFocus(key, tabs, tabId) {
        const count = tabs.length;
        const index = tabs.indexOf(tabId);
        if (key === 'ArrowLeft') return tabs[(index - 1 + count) % count];
        if (key === 'ArrowRight') return tabs[(index + 1) % count];
        if (key === 'Home') return tabs[0];
        if (key === 'End') return tabs[tabs.length - 1];
        return undefined;
    }

    activateTab(state, pane, tabId) {
        if (state.activePaneId === pane.id && pane.activeTabId === tabId) return;
        this.intents.focusTab(tabId);
    }

    scrollChipIntoView(entry, tabId) {
        const chip = entry.tabsBox.querySelector('[data-dock-tab="' + this.escapeAttr(tabId) + '"]');
        if (!chip) return;
        const bounds = entry.tabsBox.getBoundingClientRect();
        const rect = chip.getBoundingClientRect();
        if (rect.left < bounds.left) entry.tabsBox.scrollLeft += rect.left - bounds.left - DOCK_STRIP_FADE;
        else if (rect.right > bounds.right) entry.tabsBox.scrollLeft += rect.right - bounds.right + DOCK_STRIP_FADE;
    }

    updateStripFades() {
        const entries = Object.keys(this.paneEls);
        for (let i = 0; i < entries.length; i += 1) this.updateStripFadeFor(this.paneEls[entries[i]].tabsBox);
    }

    updateStripFadeFor(box) {
        if (!box) return;
        const start = box.scrollLeft > 1;
        const end = box.scrollLeft + box.clientWidth < box.scrollWidth - 1;
        if (start && end) box.setAttribute('data-dock-strip-scroll', 'start end');
        else if (start) box.setAttribute('data-dock-strip-scroll', 'start');
        else if (end) box.setAttribute('data-dock-strip-scroll', 'end');
        else box.removeAttribute('data-dock-strip-scroll');
    }

    /**
     * Why a pane cannot split right now: the engine budget first, the
     * embedder's product budget, then the pane's own width.
     */
    splitBlock(paneId) {
        if (!this.state) return undefined;
        if (!dockCanSplit(this.state) || !this.canSplitSurface()) return 'budget';
        return dockFitOf(this.fits, paneId).row ? undefined : 'width';
    }

    /** Read every pane's room-rule verdict after a commit or a resize. */
    remeasure() {
        if (!this.el) return;
        const next = dockMeasurePaneFits(this.el, this.hideSplitWhenBlocked);
        if (!dockSameFits(this.fits, next)) {
            this.fits = next;
            if (this.state) {
                const ids = dockPaneIds(this.state);
                for (let i = 0; i < ids.length; i += 1) this.renderPane(this.state, ids[i]);
            }
        }
        if (this.onRoom) this.onRoom(this.fits);
    }

    /**
     * Resolve where a pointer sits inside the docked surface. An edge zone is
     * only offered where the split it would make is allowed: within the pane
     * budget and with room for two halves; otherwise the release is not a move.
     */
    hitTest(x, y) {
        const canSplit = !!this.state && dockCanSplit(this.state) && this.canSplitSurface();
        const panes = dockPaneElements(this.el);
        for (let i = 0; i < panes.length; i += 1) {
            const paneId = panes[i][0];
            const paneEl = panes[i][1];
            const rect = paneEl.getBoundingClientRect();
            if (!dockContainsPoint(rect, x, y)) continue;
            const strip = paneEl.querySelector('[data-dock-strip]');
            if (strip && dockContainsPoint(strip.getBoundingClientRect(), x, y)) {
                const chipEls = strip.querySelectorAll('[data-dock-tab]');
                const chipRects = [];
                for (let c = 0; c < chipEls.length; c += 1) chipRects.push(chipEls[c].getBoundingClientRect());
                return { kind: 'strip', paneId: paneId, index: dockInsertionIndex(chipRects, x) };
            }
            const zone = this.dropZones === 'horizontal'
                ? canSplit && dockFitOf(this.fits, paneId).row
                    ? (x < rect.x + rect.width / 2 ? 'left' : 'right')
                    : 'center'
                : dockZoneInRect(rect, x, y);
            if (zone !== 'center') {
                const fit = dockFitOf(this.fits, paneId);
                const room = zone === 'left' || zone === 'right' ? fit.row : fit.column;
                if (!canSplit || !room) return undefined;
            }
            return { kind: 'zone', paneId: paneId, zone: zone };
        }
        return undefined;
    }

    draggedSizes(drag, x, y) {
        const moved = (drag.axis === 'row' ? x : y) - drag.origin;
        const delta = drag.extent > 0 ? moved / drag.extent : 0;
        return dockClampSizes(dockDividerSizes(drag.sizes, drag.index, delta), this.minPaneFraction);
    }

    onDividerPressed(splitId, index, event) {
        if (event.button !== 0) return;
        const container = event.currentTarget.parentElement;
        if (!container || !this.state) return;
        event.preventDefault();
        const split = dockGetSplit(this.state, splitId);
        const box = container.getBoundingClientRect();
        const drag = {
            splitId: splitId,
            index: index,
            axis: split.axis,
            origin: split.axis === 'row' ? event.clientX : event.clientY,
            extent: split.axis === 'row' ? box.width : box.height,
            sizes: split.sizes,
        };
        const element = event.currentTarget;
        this.beginGesture(element, event.pointerId, {
            move: (moved) => {
                this.preview = {
                    draggingTabId: undefined,
                    dropTarget: undefined,
                    sizes: { splitId: splitId, sizes: this.draggedSizes(drag, moved.clientX, moved.clientY) },
                };
                this.renderTree();
            },
            up: (released) => {
                const sizes = this.draggedSizes(drag, released.clientX, released.clientY);
                if (dockSameSizes(sizes, drag.sizes)) return;
                this.intents.resizeSplit(splitId, sizes);
            },
        });
    }

    onChipPressed(tabId, event) {
        const chip = event.currentTarget;
        const startX = event.clientX;
        const startY = event.clientY;
        let dragging = false;
        // No preventDefault here: a cancelled pointerdown suppresses the
        // compatibility click, and the chip's click is what selects the tab.
        // Text selection and native drag are already off (user-select: none,
        // touch-action: none, dragstart prevented on the chip).
        this.beginGesture(chip, event.pointerId, {
            move: (moved) => {
                if (!dragging) {
                    if (!dockPassedThreshold(startX, startY, moved.clientX, moved.clientY)) return;
                    dragging = true;
                }
                this.preview = {
                    draggingTabId: tabId,
                    dropTarget: this.hitTest(moved.clientX, moved.clientY),
                    sizes: undefined,
                };
                this.applyPreview();
            },
            up: (released) => {
                if (!dragging) return;
                const target = this.hitTest(released.clientX, released.clientY);
                if (target === undefined) {
                    const rect = this.el.getBoundingClientRect();
                    if (dockContainsPoint(rect, released.clientX, released.clientY)) return;
                    this.intents.floatTab(tabId, dockFloatRectAt(released.clientX, released.clientY, DOCK_FLOAT_DEFAULT_SIZE));
                    return;
                }
                if (target.kind === 'strip') this.intents.placeTab(tabId, target.paneId, target.index);
                else this.intents.dropTab(tabId, target.paneId, target.zone);
            },
        });
    }

    /** Repaint the local gesture preview: caret slots, chip lift, drop hints. */
    applyPreview() {
        if (!this.state || !this.el) return;
        const entries = Object.keys(this.paneEls);
        for (let i = 0; i < entries.length; i += 1) this.updateStripFadeFor(this.paneEls[entries[i]].tabsBox);
        // Chips: lift the dragged one.
        const chips = this.el.querySelectorAll('[data-dock-tab]');
        for (let i = 0; i < chips.length; i += 1) {
            if (chips[i].getAttribute('data-dock-tab') === this.preview.draggingTabId) chips[i].classList.add('is-dragging');
            else chips[i].classList.remove('is-dragging');
        }
        // Clear every hint, then redraw the ones the preview names.
        const oldHints = this.el.querySelectorAll('.dock-hint, .dock-scrim, .dock-slot--caret');
        for (let i = 0; i < oldHints.length; i += 1) oldHints[i].remove();
        const target = this.preview.dropTarget;
        if (!target) return;
        if (target.kind === 'strip') {
            const entry = this.paneEls[target.paneId];
            if (!entry) return;
            const chipEls = entry.tabsBox.querySelectorAll('[data-dock-tab]');
            const slot = document.createElement('div');
            slot.className = 'dock-slot dock-slot--caret';
            if (target.index >= chipEls.length) entry.tabsBox.appendChild(slot);
            else entry.tabsBox.insertBefore(slot, chipEls[target.index]);
            return;
        }
        const entry = this.paneEls[target.paneId];
        if (!entry) return;
        const scrim = document.createElement('div');
        scrim.className = 'dock-scrim';
        entry.body.appendChild(scrim);
        const zones = this.dropZones === 'horizontal' && target.zone !== 'center' ? ['left', 'right'] : [target.zone];
        for (let i = 0; i < zones.length; i += 1) {
            const hint = document.createElement('div');
            hint.className = 'dock-hint dock-hint--' + zones[i];
            if (zones[i] === target.zone) hint.classList.add('is-active');
            const card = document.createElement('div');
            card.className = 'dock-hint-card';
            const label = document.createElement('span');
            label.textContent = this.dropZoneLabel(zones[i]);
            card.appendChild(label);
            hint.appendChild(card);
            entry.body.appendChild(hint);
        }
    }

    dropZoneLabel(zone) {
        const map = this.labels.dropZone || {};
        return map[zone] || map.center || '移入此面板';
    }

    /** A small context menu for a chip: duplicate and close. */
    openMenu(tabId, anchor) {
        this.dismissMenu();
        const state = this.state;
        if (!state || !state.tabs[tabId]) return;
        const menu = document.createElement('div');
        menu.className = 'dock-menu';
        menu.setAttribute('role', 'menu');
        const rect = anchor.getBoundingClientRect();
        menu.style.left = Math.round(rect.left) + 'px';
        menu.style.top = Math.round(rect.bottom + 4) + 'px';
        const duplicate = document.createElement('button');
        duplicate.type = 'button';
        duplicate.className = 'dock-menu-item';
        duplicate.setAttribute('role', 'menuitem');
        duplicate.textContent = this.labels.duplicateTab || '复制标签';
        duplicate.addEventListener('click', () => {
            this.dismissMenu();
            this.intents.duplicateTab(tabId);
        });
        menu.appendChild(duplicate);
        if (this.canCloseTab(tabId)) {
            const close = document.createElement('button');
            close.type = 'button';
            close.className = 'dock-menu-item';
            close.setAttribute('role', 'menuitem');
            close.textContent = this.labels.closeTab || '关闭标签';
            close.addEventListener('click', () => {
                this.dismissMenu();
                this.intents.closeTab(tabId);
            });
            menu.appendChild(close);
        }
        const dismiss = (event) => {
            if (menu.contains(event.target)) return;
            this.dismissMenu();
        };
        menu.__dockDismiss = dismiss;
        document.body.appendChild(menu);
        this.menu = menu;
        setTimeout(() => document.addEventListener('pointerdown', dismiss, true), 0);
    }

    dismissMenu() {
        if (!this.menu) return;
        if (this.menu.__dockDismiss) document.removeEventListener('pointerdown', this.menu.__dockDismiss, true);
        if (this.menu.parentNode) this.menu.parentNode.removeChild(this.menu);
        this.menu = null;
    }

    escapeAttr(value) {
        return String(value).replace(/["\\]/g, '\\$&');
    }
}
