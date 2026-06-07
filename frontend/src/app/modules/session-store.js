const sessionStore = {
    sessionsById: new Map(),
    order: [],
    archivedCount: 0,

    applySnapshot(sessions, archivedCount) {
        const nextById = new Map();
        const nextOrder = [];
        const list = Array.isArray(sessions) ? sessions : [];
        for (let i = 0; i < list.length; i += 1) {
            const s = list[i];
            if (!s || !s.id) continue;
            nextById.set(String(s.id), s);
            nextOrder.push(String(s.id));
        }
        this.sessionsById = nextById;
        this.order = nextOrder;
        if (Number.isFinite(Number(archivedCount)) && Number(archivedCount) >= 0) {
            this.archivedCount = Number(archivedCount);
        }
    },

    upsert(session) {
        if (!session || !session.id) return;
        const sid = String(session.id);
        this.sessionsById.set(sid, session);
        if (this.order.indexOf(sid) < 0) this.order.unshift(sid);
    },

    remove(sessionId) {
        const sid = String(sessionId || '');
        if (!sid) return;
        this.sessionsById.delete(sid);
        this.order = this.order.filter(function (id) { return id !== sid; });
    },

    list() {
        const out = [];
        for (let i = 0; i < this.order.length; i += 1) {
            const s = this.sessionsById.get(this.order[i]);
            if (s) out.push(s);
        }
        return out;
    },

    get(sessionId) {
        return this.sessionsById.get(String(sessionId || '')) || null;
    },

    setArchivedCount(count) {
        if (Number.isFinite(Number(count)) && Number(count) >= 0) {
            this.archivedCount = Number(count);
        }
    },
};
