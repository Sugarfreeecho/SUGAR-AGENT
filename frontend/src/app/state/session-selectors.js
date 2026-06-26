function selectCurrentSession() {
    return sessionStore.get(sessionStore.currentSessionId);
}

function selectAllSessions() {
    return sessionStore.list();
}

function selectArchivedSessions() {
    return sessionStore.archivedList();
}

function sessionActivityTimeMs(session) {
    if (!session) return 0;
    var raw = session.last_activity_at || session.updated_at || session.created_at || '';
    var t = Date.parse(String(raw || ''));
    return Number.isFinite(t) ? t : 0;
}

function selectNormalSessionTimeGroups(normalList) {
    var groups = [
        { key: 'today', title: '今天', sessions: [] },
        { key: 'yesterday', title: '昨天', sessions: [] },
        { key: 'week', title: '近7天', sessions: [] },
        { key: 'fortnight', title: '近14天', sessions: [] },
    ];
    var now = new Date();
    var startToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
    var startYesterday = startToday - 86400000;
    var sevenDaysAgo = Date.now() - (7 * 86400000);
    var fourteenDaysAgo = Date.now() - (14 * 86400000);
    for (var i = 0; i < normalList.length; i += 1) {
        var s = normalList[i];
        var t = sessionActivityTimeMs(s);
        if (t >= startToday) groups[0].sessions.push(s);
        else if (t >= startYesterday) groups[1].sessions.push(s);
        else if (t >= sevenDaysAgo) groups[2].sessions.push(s);
        else if (t >= fourteenDaysAgo) groups[3].sessions.push(s);
    }
    return groups.filter(function (g) { return g.sessions.length > 0; });
}

function selectSessionSections() {
    const pinnedList = [];
    const normalList = [];
    const allSessions = selectAllSessions();
    for (let i = 0; i < allSessions.length; i += 1) {
        const s = allSessions[i];
        if (!s || !s.id || !!s.archived) continue;
        if (s.pinned) pinnedList.push(s);
        else normalList.push(s);
    }
    return {
        pinned: pinnedList,
        normal: normalList,
        normalGroups: selectNormalSessionTimeGroups(normalList),
        archived: selectArchivedSessions(),
    };
}

function selectArchivedDisplayCount() {
    return sessionStore.archivedLoaded ? selectArchivedSessions().length : sessionStore.archivedCount;
}

function selectIsSessionRunning(sessionId) {
    if (!sessionId) return false;
    if (typeof isSessionStreamStopSuppressed === 'function' && isSessionStreamStopSuppressed(sessionId)) return false;
    if (sessionStore.hasRun(sessionId)) return true;
    const info = sessionStore.getActiveRunInfo(sessionId);
    if (info && Object.prototype.hasOwnProperty.call(info, 'run_active')) {
        return !!info.run_active;
    }
    const sess = sessionStore.get(sessionId);
    if (sess && Object.prototype.hasOwnProperty.call(sess, 'run_active')) {
        return !!sess.run_active;
    }
    return false;
}

function selectRunForSession(sessionId) {
    return sessionStore.getRun(sessionId);
}
