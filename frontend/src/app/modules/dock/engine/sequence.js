/**
 * Linear operation history over `dockApplyOp`. Recording is total — every
 * operation lands in the sequence, focus moves included — and grouped by
 * intent: the operations one gesture or command produced form one entry, so
 * stepping lands on a point the user actually stopped at. Stepping is coarser
 * still across focus: a run of consecutive focus-only entries undoes and redoes
 * as one step.
 *
 * Redoing re-applies the recorded operations; undoing applies the inverses that
 * were captured when they ran, so both directions stay exact. A new entry after
 * an undo drops the redo branch.
 */

/** A sequence that has recorded nothing. */
const DOCK_EMPTY_HISTORY = { entries: [], cursor: 0 };

/** Operation kinds that only move focus. */
const DOCK_FOCUS_OP_TYPES = { focusTab: true, focusPane: true, restoreFocus: true };

/**
 * Whether an operation only moves focus, and so merges into its neighbours' undo step.
 * @param {object} op The operation.
 * @returns {boolean} whether its type is focus-only.
 */
function dockIsFocusOp(op) {
    return DOCK_FOCUS_OP_TYPES[op.type] === true;
}

/** Whether the entry at `index` only moves focus. */
function dockIsFocusEntry(history, index) {
    const entry = history.entries[index];
    return entry !== undefined && entry.ops.every(dockIsFocusOp);
}

/**
 * Whether a step back exists.
 * @param {object} history The sequence so far.
 * @returns {boolean} whether any entry is applied.
 */
function dockCanStepBack(history) {
    return history.cursor > 0;
}

/**
 * Whether a step forward exists.
 * @param {object} history The sequence so far.
 * @returns {boolean} whether a redo branch remains.
 */
function dockCanStepForward(history) {
    return history.cursor < history.entries.length;
}

/**
 * The operations a sequence has recorded, redo branch included.
 * @param {object} history The sequence so far.
 * @returns {object[]} every entry's operations, in recorded order.
 */
function dockRecordedOps(history) {
    const out = [];
    for (let i = 0; i < history.entries.length; i += 1) {
        const ops = history.entries[i].ops;
        for (let j = 0; j < ops.length; j += 1) out.push(ops[j]);
    }
    return out;
}

/**
 * Apply one intent's operations and record them as one entry, dropping any redo
 * branch first. An intent with no operations records nothing.
 * @param {object} history The sequence so far.
 * @param {object} state The state the operations apply to.
 * @param {object[]} ops The intent's operations, in application order.
 * @returns {{history:object,state:object}} the extended history and the state after the operations.
 * @throws when an operation is invalid against the state it reaches; nothing is recorded.
 */
function dockRecord(history, state, ops) {
    if (ops.length === 0) return { history: history, state: state };
    let next = state;
    const inverse = [];
    for (let i = 0; i < ops.length; i += 1) {
        const result = dockApplyOp(next, ops[i]);
        next = result.state;
        // Undo runs the inverses in reverse operation order.
        for (let j = result.inverse.length - 1; j >= 0; j -= 1) inverse.unshift(result.inverse[j]);
    }
    const kept = history.cursor === history.entries.length
        ? history.entries
        : history.entries.slice(0, history.cursor);
    return {
        history: { entries: kept.concat([{ ops: ops, inverse: inverse }]), cursor: history.cursor + 1 },
        state: next,
    };
}

/**
 * Step back one intent, or one whole run of consecutive focus-only intents.
 * @param {object} history The sequence so far.
 * @param {object} state The current state.
 * @returns {{history:object,state:object}|undefined} the stepped-back pair, or undefined when nothing can be undone.
 */
function dockStepBack(history, state) {
    if (!dockCanStepBack(history)) return undefined;
    let count = 1;
    if (dockIsFocusEntry(history, history.cursor - 1)) {
        while (dockIsFocusEntry(history, history.cursor - 1 - count)) count += 1;
    }
    let next = state;
    const entries = history.entries.slice(history.cursor - count, history.cursor);
    for (let i = entries.length - 1; i >= 0; i -= 1) {
        const inverse = entries[i].inverse;
        for (let j = 0; j < inverse.length; j += 1) next = dockApplyOp(next, inverse[j]).state;
    }
    return { history: { entries: history.entries, cursor: history.cursor - count }, state: next };
}

/**
 * Step forward over the intents the matching step back undid.
 * @param {object} history The sequence so far.
 * @param {object} state The current state.
 * @returns {{history:object,state:object}|undefined} the stepped-forward pair, or undefined when nothing can be redone.
 */
function dockStepForward(history, state) {
    if (!dockCanStepForward(history)) return undefined;
    let count = 1;
    if (dockIsFocusEntry(history, history.cursor)) {
        while (dockIsFocusEntry(history, history.cursor + count)) count += 1;
    }
    let next = state;
    const entries = history.entries.slice(history.cursor, history.cursor + count);
    for (let i = 0; i < entries.length; i += 1) {
        const ops = entries[i].ops;
        for (let j = 0; j < ops.length; j += 1) next = dockApplyOp(next, ops[j]).state;
    }
    return { history: { entries: history.entries, cursor: history.cursor + count }, state: next };
}

/**
 * Layout state plus its history cursor, held here instead of by the embedder.
 * Same implementation as the pure functions above, one mutable wrapper.
 */
class DockSequencer {
    /** @param {object} initial State the sequence replays from; never mutated. */
    constructor(initial) {
        this.current = initial;
        this.recorded = DOCK_EMPTY_HISTORY;
    }

    /** Current state. */
    get state() {
        return this.current;
    }

    /** The recorded sequence as plain data. */
    get history() {
        return this.recorded;
    }

    /** The whole recorded sequence, including a redo branch that is not applied. */
    get ops() {
        return dockRecordedOps(this.recorded);
    }

    /** How many recorded operations are currently applied. */
    get cursor() {
        return this.recorded.cursor;
    }

    /** Whether a step back exists. */
    get canUndo() {
        return dockCanStepBack(this.recorded);
    }

    /** Whether a step forward exists. */
    get canRedo() {
        return dockCanStepForward(this.recorded);
    }

    /**
     * Apply and record one operation as its own entry, dropping any redo branch first.
     * @param {object} op The operation to record.
     * @returns {object} the state after it.
     */
    dispatch(op) {
        return this.dispatchAll([op]);
    }

    /**
     * Apply and record one intent's operations as one entry, dropping any redo
     * branch first.
     * @param {object[]} ops The intent's operations; none records nothing.
     * @returns {object} the state after them.
     */
    dispatchAll(ops) {
        const stepped = dockRecord(this.recorded, this.current, ops);
        this.recorded = stepped.history;
        this.current = stepped.state;
        return this.current;
    }

    /** Step back one intent, or one whole run of consecutive focus-only intents. @returns {boolean} false when there is nothing to undo. */
    undo() {
        const stepped = dockStepBack(this.recorded, this.current);
        if (stepped === undefined) return false;
        this.recorded = stepped.history;
        this.current = stepped.state;
        return true;
    }

    /** Step forward over the intents the matching undo stepped back. @returns {boolean} false when there is nothing to redo. */
    redo() {
        const stepped = dockStepForward(this.recorded, this.current);
        if (stepped === undefined) return false;
        this.recorded = stepped.history;
        this.current = stepped.state;
        return true;
    }
}
