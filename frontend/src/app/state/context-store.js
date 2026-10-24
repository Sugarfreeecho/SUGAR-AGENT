const contextStore = {
    tokensBySession: new Map(),
    tokenVersionsBySession: new Map(),
    progressBySession: new Map(),

    setTokens(sessionId, estimated, threshold, breakdown, options) {
        const sid = String(sessionId || '');
        if (!sid) return false;
        options = options || {};
        if (options.expectedVersion != null && options.expectedVersion !== this.tokenVersion(sid)) return false;
        if (estimated != null && Number.isFinite(Number(estimated)) && Number(estimated) >= 0) {
            const previous = this.tokensBySession.get(sid);
            const nextThreshold = Number(threshold) > 0 ? Number(threshold) : previous && previous.threshold;
            const sameReading = previous && previous.estimated === Number(estimated)
                && previous.threshold === nextThreshold;
            this.tokenVersionsBySession.set(sid, this.tokenVersion(sid) + 1);
            this.tokensBySession.set(sid, {
                estimated: Number(estimated),
                threshold: nextThreshold,
                // Composition is reusable only for the same reading.
                breakdown: breakdown != null ? breakdown : (sameReading ? previous.breakdown : null),
                updatedAt: options.stale ? 0 : Date.now(),
            });
        } else {
            this.clearTokens(sid);
        }
        return true;
    },

    tokenVersion(sessionId) {
        return this.tokenVersionsBySession.get(String(sessionId || '')) || 0;
    },

    getTokens(sessionId) {
        return this.tokensBySession.get(String(sessionId || '')) || null;
    },

    clearTokens(sessionId) {
        const sid = String(sessionId || '');
        this.tokenVersionsBySession.set(sid, this.tokenVersion(sid) + 1);
        this.tokensBySession.delete(sid);
    },

    appendProgress(sessionId, kind, delta) {
        const sid = String(sessionId || '');
        const k = String(kind || '');
        if (!sid || !k) return null;
        let st = this.progressBySession.get(sid);
        if (!st) {
            st = {
                sessionId: sid,
                contextSummary: '',
                keyContext: '',
                updatedAt: 0,
            };
            this.progressBySession.set(sid, st);
        }
        const text = delta == null ? '' : String(delta);
        if (k === 'context-summary') st.contextSummary += text;
        else if (k === 'key-context') st.keyContext += text;
        st.updatedAt = Date.now();
        return st;
    },

    clearProgress(sessionId) {
        this.progressBySession.delete(String(sessionId || ''));
    },

    clearSession(sessionId) {
        const sid = String(sessionId || '');
        if (!sid) return;
        this.clearTokens(sid);
        this.clearProgress(sid);
    },
};

function setContextTokensForSession(sessionId, estimated, threshold, breakdown, options) {
    return contextStore.setTokens(sessionId, estimated, threshold, breakdown, options);
}

function getContextTokenVersion(sessionId) {
    return contextStore.tokenVersion(sessionId);
}

function selectContextTokens(sessionId) {
    return contextStore.getTokens(sessionId);
}

function clearContextStateForSession(sessionId) {
    contextStore.clearSession(sessionId);
}

function appendContextProgressForSession(sessionId, kind, delta) {
    return contextStore.appendProgress(sessionId, kind, delta);
}

