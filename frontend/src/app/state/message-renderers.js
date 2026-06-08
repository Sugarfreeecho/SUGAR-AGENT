function renderMessageRecord(ctx, record, sessionId) {
    if (!ctx || !record || !record.event) return null;
    const sid = sessionId || record.sessionId || currentSessionId;
    renderEvent(ctx, record.event, record.index, sid);
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

function renderMessageRecords(ctx, records, sessionId) {
    const list = Array.isArray(records) ? records : [];
    for (let i = 0; i < list.length; i += 1) {
        renderMessageRecord(ctx, list[i], sessionId);
    }
}
