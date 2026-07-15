const sessionStore = {
    seq: 0,
    sessionsById: new Map(),
    sessionOrder: [],
    currentSessionId: null,
    runsBySession: new Map(),
    terminalRunIdsBySession: new Map(),
    activeRunInfoBySession: new Map(),
    archivedCount: 0,
    archivedLoaded: false,
    archivedSessions: null,
    unreadComplete: new Set(),
    sseSeqBySession: new Map(),
    deletedSessionTombstones: new Map(),
    ui: {
        loadingSessions: false,
        loadingMessages: false,
    },
    streamActiveById: Object.create(null),

    applySnapshot(sessions, archivedCount) {
        this.pruneDeletedSessionTombstones();
        const nextById = new Map();
        const nextOrder = [];
        const nextStreamActive = Object.create(null);
        const list = Array.isArray(sessions) ? sessions : [];
        let unreadChanged = false;
        for (let i = 0; i < list.length; i += 1) {
            const s = list[i];
            if (!s || !s.id) continue;
            const sid = String(s.id);
            if (this.isDeletedSessionTombstoned(sid)) continue;
            const nextSession = Object.assign({}, s);
            if (typeof isSessionStreamStopSuppressed === 'function' && isSessionStreamStopSuppressed(sid)) {
                nextSession.stream_active = false;
                nextSession.run_active = false;
                nextSession.run_started_at = null;
            }
            if (typeof sessionUnreadComplete !== 'undefined') {
                if (nextSession.unread_result) {
                    if (!sessionUnreadComplete.has(sid)) {
                        sessionUnreadComplete.add(sid);
                        unreadChanged = true;
                    }
                } else if (sessionUnreadComplete.delete(sid)) {
                    unreadChanged = true;
                }
            }
            nextById.set(sid, nextSession);
            nextOrder.push(sid);
            nextStreamActive[sid] = !!nextSession.stream_active;
        }
        this.sessionsById = nextById;
        this.sessionOrder = nextOrder;
        this.streamActiveById = nextStreamActive;
        if (Number.isFinite(Number(archivedCount)) && Number(archivedCount) >= 0) {
            this.archivedCount = Number(archivedCount);
        }
        if (unreadChanged && typeof persistSessionUnread === 'function') persistSessionUnread();
    },

    upsert(session) {
        if (!session || !session.id) return;
        const sid = String(session.id);
        if (this.isDeletedSessionTombstoned(sid)) return;
        const existed = this.sessionOrder.indexOf(sid) >= 0;
        this.sessionsById.set(sid, session);
        if (!existed) {
            this.sessionOrder.unshift(sid);
        }
        // 任何字段更新都可能改变 last_activity_at / pinned_at，需立即重排，
        // 否则老会话有了新对话后仍停留在原分组、原位置（仅靠 800ms 后的
        // applySnapshot 兜底，期间 UI 顺序与时间分组不一致）。
        this._reorderSessionOrder();
        if (Object.prototype.hasOwnProperty.call(session, 'stream_active')) {
            this.streamActiveById[sid] = !!session.stream_active;
        }
    },

    // 与后端 list_sessions 的 sort_key 保持一致：
    //   pinned 在前；pinned 之间按 pinned_at 倒序；非 pinned 按 last_activity_at 倒序。
    // 缺失时间字段时回退到 updated_at / created_at，仍解析失败则视为 0（沉底）。
    _activityTimeMs(session) {
        if (!session) return 0;
        var raw = session.last_activity_at || session.updated_at || session.created_at || '';
        var t = Date.parse(String(raw || ''));
        return Number.isFinite(t) ? t : 0;
    },

    _pinnedTimeMs(session) {
        if (!session) return 0;
        var raw = session.pinned_at || session.updated_at || session.created_at || '';
        var t = Date.parse(String(raw || ''));
        return Number.isFinite(t) ? t : 0;
    },

    _reorderSessionOrder() {
        const self = this;
        this.sessionOrder.sort(function (aId, bId) {
            const a = self.sessionsById.get(aId);
            const b = self.sessionsById.get(bId);
            if (!a) return 1;
            if (!b) return -1;
            const aPinned = !!a.pinned;
            const bPinned = !!b.pinned;
            if (aPinned !== bPinned) return aPinned ? -1 : 1;
            if (aPinned) return self._pinnedTimeMs(b) - self._pinnedTimeMs(a);
            return self._activityTimeMs(b) - self._activityTimeMs(a);
        });
    },

    remove(sessionId) {
        const sid = String(sessionId || '');
        if (!sid) return;
        this.sessionsById.delete(sid);
        delete this.streamActiveById[sid];
        this.runsBySession.delete(sid);
        this.terminalRunIdsBySession.delete(sid);
        this.activeRunInfoBySession.delete(sid);
        this.unreadComplete.delete(sid);
        this.sessionOrder = this.sessionOrder.filter(function (id) { return id !== sid; });
    },

    markDeletedSession(sessionId) {
        const sid = String(sessionId || '');
        if (!sid) return;
        this.deletedSessionTombstones.set(sid, Date.now());
        this.remove(sid);
    },

    clearDeletedSessionTombstone(sessionId) {
        const sid = String(sessionId || '');
        if (!sid) return;
        this.deletedSessionTombstones.delete(sid);
    },

    pruneDeletedSessionTombstones() {
        const now = Date.now();
        const ttl = 120000;
        this.deletedSessionTombstones.forEach(function (createdAt, sid, map) {
            if (now - Number(createdAt || 0) > ttl) map.delete(sid);
        });
    },

    isDeletedSessionTombstoned(sessionId) {
        this.pruneDeletedSessionTombstones();
        return this.deletedSessionTombstones.has(String(sessionId || ''));
    },

    list() {
        const out = [];
        for (let i = 0; i < this.sessionOrder.length; i += 1) {
            const s = this.sessionsById.get(this.sessionOrder[i]);
            if (s) out.push(s);
        }
        return out;
    },

    get(sessionId) {
        return this.sessionsById.get(String(sessionId || '')) || null;
    },

    setCurrentSession(sessionId) {
        this.currentSessionId = sessionId ? String(sessionId) : null;
    },

    setArchivedCount(count) {
        if (Number.isFinite(Number(count)) && Number(count) >= 0) {
            this.archivedCount = Number(count);
        }
    },

    setArchivedLoaded(sessions) {
        const list = Array.isArray(sessions)
            ? sessions.filter(function (s) { return s && s.id && !!s.archived; })
            : [];
        this.archivedLoaded = true;
        this.archivedSessions = list;
        this.archivedCount = list.length;
    },

    clearArchivedLoaded() {
        this.archivedLoaded = false;
        this.archivedSessions = null;
    },

    archivedList() {
        return this.archivedLoaded && Array.isArray(this.archivedSessions) ? this.archivedSessions : [];
    },

    isStreamActive(sessionId) {
        const sid = String(sessionId || '');
        if (!sid) return false;
        if (Object.prototype.hasOwnProperty.call(this.streamActiveById, sid)) {
            return !!this.streamActiveById[sid];
        }
        const sess = this.get(sid);
        return !!(sess && sess.stream_active);
    },

    setStreamActive(sessionId, active) {
        const sid = String(sessionId || '');
        if (!sid) return;
        this.streamActiveById[sid] = !!active;
        const sess = this.sessionsById.get(sid);
        if (sess) sess.stream_active = !!active;
    },

    applyStreamActiveMap(activeMap) {
        const next = Object.create(null);
        const src = activeMap || {};
        Object.keys(src).forEach(function (sid) {
            next[String(sid)] = !!src[sid];
        });
        this.streamActiveById = next;
        this.sessionsById.forEach(function (sess, sid) {
            sess.stream_active = !!next[sid];
            sess.run_active = !!next[sid];
            if (!next[sid]) sess.run_started_at = null;
        });
    },

    setRun(sessionId, run) {
        const sid = String(sessionId || '');
        if (!sid) return;
        if (run) this.runsBySession.set(sid, run);
        else this.runsBySession.delete(sid);
    },

    getRun(sessionId) {
        return this.runsBySession.get(String(sessionId || '')) || null;
    },

    hasRun(sessionId) {
        return this.runsBySession.has(String(sessionId || ''));
    },

    markTerminalRun(sessionId, runId) {
        const sid = String(sessionId || '');
        const rid = String(runId || '').trim();
        if (!sid || !rid) return;
        let bucket = this.terminalRunIdsBySession.get(sid);
        if (!bucket) {
            bucket = new Set();
            this.terminalRunIdsBySession.set(sid, bucket);
        }
        bucket.add(rid);
    },

    isTerminalRun(sessionId, runId) {
        const sid = String(sessionId || '');
        const rid = String(runId || '').trim();
        if (!sid || !rid) return false;
        const bucket = this.terminalRunIdsBySession.get(sid);
        return !!(bucket && bucket.has(rid));
    },

    applyActiveRuns(activeRuns) {
        const next = new Map();
        const list = Array.isArray(activeRuns) ? activeRuns : [];
        list.forEach(function (run) {
            const sid = typeof run === 'string' ? run : (run && run.session_id);
            if (!sid) return;
            const runId = typeof run === 'string' ? '' : String((run && (run.run_id || run.runId)) || '').trim();
            if (runId && this.isTerminalRun(sid, runId)) return;
            if (typeof isSessionStreamStopSuppressed === 'function' && isSessionStreamStopSuppressed(sid)) return;
            next.set(String(sid), typeof run === 'string' ? { session_id: String(sid) } : Object.assign({}, run));
        }, this);
        this.activeRunInfoBySession = next;
    },

    activeRunIds() {
        return Array.from(this.activeRunInfoBySession.keys());
    },

    getActiveRunInfo(sessionId) {
        return this.activeRunInfoBySession.get(String(sessionId || '')) || null;
    },

    shouldAcceptSseEvent(sessionId, seq, scope) {
        const sid = String(sessionId || '');
        const n = Number(seq);
        if (!sid || !Number.isFinite(n) || n <= 0) return true;
        const seqScope = String(scope || 'default');
        const key = sid + '::' + seqScope;
        const prev = Number(this.sseSeqBySession.get(key) || 0);
        if (n <= prev) return false;
        this.sseSeqBySession.set(key, n);
        if (Number.isFinite(Number(this.seq)) && n > Number(this.seq)) this.seq = n;
        return true;
    },

    resetSseSeq(sessionId) {
        const sid = String(sessionId || '');
        if (!sid) return;
        this.sseSeqBySession.delete(sid);
        Array.from(this.sseSeqBySession.keys()).forEach(function (key) {
            if (String(key).indexOf(sid + '::') === 0) this.sseSeqBySession.delete(key);
        }, this);
    },
};

const SESSION_STREAM_STOP_SUPPRESS_MS = 60000;
const sessionStreamStopSuppressUntil = Object.create(null);

function isSessionStreamStopSuppressed(sessionId) {
    const sid = String(sessionId || '');
    if (!sid) return false;
    const until = Number(sessionStreamStopSuppressUntil[sid] || 0);
    if (!until) return false;
    if (Date.now() <= until) return true;
    delete sessionStreamStopSuppressUntil[sid];
    return false;
}

function clearSessionStreamStopSuppress(sessionId) {
    const sid = String(sessionId || '');
    if (!sid) return;
    delete sessionStreamStopSuppressUntil[sid];
}

function suppressSessionServerStreamActive(sessionId, ms) {
    const sid = String(sessionId || '');
    if (!sid) return;
    sessionStreamStopSuppressUntil[sid] = Date.now() + (Number(ms) > 0 ? Number(ms) : SESSION_STREAM_STOP_SUPPRESS_MS);
    sessionStore.setStreamActive(sid, false);
    sessionStore.activeRunInfoBySession.delete(sid);
    const sess = sessionStore.get(sid);
    if (sess) {
        sess.stream_active = false;
        sess.run_active = false;
        sess.run_started_at = null;
    }
}

function setSessionServerStreamActive(sessionId, active) {
    const sid = String(sessionId || '');
    if (!sid) return;
    if (active && isSessionStreamStopSuppressed(sid)) active = false;
    sessionStore.setStreamActive(sid, !!active);
}

function isServerStreamActive(sessionId) {
    const sid = String(sessionId || '');
    if (!sid) return false;
    if (isSessionStreamStopSuppressed(sid)) return false;
    return sessionStore.isStreamActive(sid);
}

function applyServerStreamActiveMap(activeMap) {
    const src = activeMap || Object.create(null);
    const m = Object.create(null);
    Object.keys(src).forEach(function (sid) {
        var active = !!src[sid];
        if (active && isSessionStreamStopSuppressed(sid)) active = false;
        m[sid] = active;
    });
    sessionStore.applyStreamActiveMap(m);
}
