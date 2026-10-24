function renderMessageRecord(ctx, record, sessionId) {
    if (!ctx || !record || !record.event) return null;
    const sid = sessionId || record.sessionId || currentSessionId;
    if (typeof renderExecutionEvent === 'function' && renderExecutionEvent(ctx, record.event, sid)) return record;
    renderEvent(ctx, record.event, record.index, sid, { source: record.source || 'render' });
    var runtimeSeq = Number(record.event.runtime_seq || record.event.runtimeSeq || 0);
    if (record.event.type === 'user') {
        // renderEvent seals the previous turn first. A UI message index is not
        // a durable sequence: an unnumbered live turn remains provisional so
        // its thinking row can adopt the first execution record's group ID.
        ctx.processGroupId = record.event.process_group_id
            || (runtimeSeq > 0 ? 'turn:' + String(runtimeSeq) : '');
    }
    if (record.event.type === 'final') {
        ctx.processGroupId = runtimeSeq > 0 ? 'after-final:' + String(runtimeSeq) : '';
    }
    return record;
}

function reduceAndRenderMessageEvent(ctx, event, opts) {
    opts = opts || {};
    if (!event || typeof event !== 'object') return { handled: false };
    const reduced = applySessionEvent(event, opts);
    if (!opts.skipRender && !(reduced && reduced.handled)) {
        const record = reduced && reduced.messageRecord
            ? reduced.messageRecord
            : {
                index: opts.eventIndex,
                event: event,
                source: opts.source || 'render',
            };
        renderMessageRecord(ctx, record, opts.sessionId || event.session_id || event.sessionId);
    }
    return reduced || { handled: false };
}

