const contextStore = {
    tokensBySession: new Map(),
    progressBySession: new Map(),

    setTokens(sessionId, estimated, threshold) {
        const sid = String(sessionId || '');
        if (!sid) return;
        if (estimated != null && Number(estimated) >= 0) {
            this.tokensBySession.set(sid, {
                estimated: Number(estimated),
                threshold: threshold,
                updatedAt: Date.now(),
            });
        } else {
            this.tokensBySession.delete(sid);
        }
    },

    getTokens(sessionId) {
        return this.tokensBySession.get(String(sessionId || '')) || null;
    },

    clearTokens(sessionId) {
        this.tokensBySession.delete(String(sessionId || ''));
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

function setContextTokensForSession(sessionId, estimated, threshold) {
    contextStore.setTokens(sessionId, estimated, threshold);
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

function selectContextProgress(sessionId) {
    return contextStore.progressBySession.get(String(sessionId || '')) || null;
}
