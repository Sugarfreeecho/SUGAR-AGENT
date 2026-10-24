function applySessionSnapshot(snapshot) {
    snapshot = snapshot || {};
    if (!sessionStore.shouldAcceptSnapshot(snapshot)) return false;
    const requestSeq = Number(snapshot.client_request_seq || 0);
    if (requestSeq > 0 && requestSeq < sessionStore.lastAppliedSnapshotRequestSeq) return false;
    if (requestSeq > 0) sessionStore.lastAppliedSnapshotRequestSeq = requestSeq;
    const sessions = Array.isArray(snapshot.sessions) ? snapshot.sessions : [];
    const archivedCount = snapshot.archived_count != null ? snapshot.archived_count : snapshot.archivedCount;
    const previousActive = new Set();
    sessionStore.activeRunInfoBySession.forEach(function (_run, sid) {
        if (sid) previousActive.add(String(sid));
    });
    if (Number.isFinite(Number(snapshot.seq)) && Number(snapshot.seq) > sessionStore.seq) {
        sessionStore.seq = Number(snapshot.seq);
    }
    const previousWorkDir = typeof getActiveWorkDir === 'function' ? getActiveWorkDir() : '';
    sessionStore.applySnapshot(sessions, archivedCount);
    if (typeof getActiveWorkDir === 'function' && getActiveWorkDir() !== previousWorkDir) {
        syncSessionWorkspaceUi(currentSessionId);
    }
    if (sessionStore.archivedLoaded && (snapshot.include_archived || snapshot.includeArchived)) {
        const loadedCount = Array.isArray(sessionStore.archivedSessions)
            ? sessionStore.archivedSessions.length
            : 0;
        const visibleCount = sessionStore.archivedVisibleCount;
        const archived = sessions.filter(function (s) { return s && s.id && !!s.archived; });
        sessionStore.setArchivedLoaded(archived.slice(0, loadedCount), {
            visibleCount: visibleCount,
            totalCount: archivedCount,
        });
    }
    if (snapshot.current_session_id || snapshot.currentSessionId) {
        sessionStore.setCurrentSession(snapshot.current_session_id || snapshot.currentSessionId);
    }
    if (Array.isArray(snapshot.active_runs)) {
        sessionStore.applyActiveRuns(snapshot.active_runs);
        const active = Object.create(null);
        sessionStore.activeRunInfoBySession.forEach(function (_run, sid) {
            if (sid) active[String(sid)] = true;
        });
        applyServerStreamActiveMap(active);
        if (typeof recoverFollowupQueueDrainsFromSessionSnapshot === 'function') {
            recoverFollowupQueueDrainsFromSessionSnapshot(previousActive, new Set(Object.keys(active)));
        }
    }
    // Parent streams may be idle while background children wait for a person.
    // The sidebar snapshot carries descendant counts; restore their cards too.
    if (typeof refreshHumanInteractions === 'function' && typeof humanInteractionPendingCounts === 'function') {
        var visibleSid = String(typeof currentSessionId !== 'undefined' ? currentSessionId || '' : '');
        var visible = sessions.find(function (row) { return String(row.id || '') === visibleSid; });
        var pending = visible && visible.pending_human_interactions;
        var localPending = humanInteractionPendingCounts(visibleSid);
        if (pending && (Number(pending.total || 0) > 0 || Number(pending.questions || 0) !== localPending.questions
            || Number(pending.approvals || 0) !== localPending.approvals)) {
            void refreshHumanInteractions(visibleSid);
        }
    }
    if (snapshot.state_revision != null) sessionStore.lastAppliedStateRevision = Number(snapshot.state_revision) || 0;
    return true;
}

function syncSessionWorkspaceUi(sessionId) {
    if (String(sessionId || '') !== String(currentSessionId || '')) return;
    if (typeof updateSessionTitle === 'function') updateSessionTitle();
    if (typeof dockRightHandleSessionSwitch === 'function') dockRightHandleSessionSwitch(sessionId);
    if (typeof refreshPermissionModeSelector === 'function') void refreshPermissionModeSelector(sessionId);
    if (typeof document !== 'undefined') document.dispatchEvent(new CustomEvent('myagent:workspace-change', {
        detail: { sessionId: sessionId, workDir: typeof getActiveWorkDir === 'function' ? getActiveWorkDir() : '' },
    }));
}

function applySessionWorkspaceChange(sessionId, session) {
    if (!session || !sessionId) return;
    applyOptimisticSessionUpdate(sessionId, session);
    syncSessionWorkspaceUi(sessionId);
}

function applySessionPatch(patch) {
    patch = patch || {};
    if (Number.isFinite(Number(patch.seq)) && Number(patch.seq) <= sessionStore.seq) return;
    if (Number.isFinite(Number(patch.seq))) sessionStore.seq = Number(patch.seq);
    if (patch.session) sessionStore.upsert(patch.session);
    if (patch.remove_session_id || patch.removedSessionId) {
        sessionStore.remove(patch.remove_session_id || patch.removedSessionId);
    }
    if (patch.current_session_id || patch.currentSessionId) {
        sessionStore.setCurrentSession(patch.current_session_id || patch.currentSessionId);
    }
    if (patch.archived_count != null || patch.archivedCount != null) {
        sessionStore.setArchivedCount(patch.archived_count != null ? patch.archived_count : patch.archivedCount);
    }
    if (patch.stream_active != null && (patch.session_id || patch.sessionId)) {
        setSessionServerStreamActive(patch.session_id || patch.sessionId, !!patch.stream_active);
    }
}

function setCurrentSessionState(sessionId) {
    const changed = currentSessionId !== (sessionId || null);
    if (changed) composerDraftRevision++;
    currentSessionId = sessionId || null;
    sessionStore.setCurrentSession(currentSessionId);
    if (changed) {
        document.dispatchEvent(new CustomEvent('myagent:session-change', { detail: { sessionId: currentSessionId } }));
    }
    if (typeof refreshPermissionModeSelector === 'function') refreshPermissionModeSelector(currentSessionId);
}

function setSessionRunState(sessionId, run) {
    const sid = String(sessionId || '');
    if (!sid) return;
    sessionStore.setRun(sid, run || null);
    if (run) limitBackgroundSessionStreams();
    if (typeof updateSidebarRuntimeStatus === 'function') updateSidebarRuntimeStatus(true);
}

function limitBackgroundSessionStreams() {
    // HTTP/1 browsers have a small per-origin connection pool. Long-lived
    // background observers must leave room for navigation, metadata and Stop.
    // The server owns generation; aborting this reader never sends /interrupt.
    const maximum = 3;
    const streams = [];
    sessionStore.runsBySession.forEach(function (run, sid) {
        if (run && run.controller && run.ctx && !(run.controller.signal && run.controller.signal.aborted)) {
            streams.push({ sid, run });
        }
    });
    let excess = streams.length - maximum;
    streams.forEach(function (entry) {
        if (excess <= 0 || String(entry.sid) === String(currentSessionId || '')) return;
        const run = entry.run;
        if (!run.ctx.streamConsuming || run.submitted === false) return;
        // A detached projection cannot be restored as a complete live stream.
        // Switching back reloads durable history before acquiring a new reader.
        if (run.ctx.stream && run.ctx.stream.dataset) {
            run.ctx.stream.dataset.partialBackgroundRun = '1';
            delete run.ctx.stream.dataset.sessionLoadOk;
        }
        setSessionServerStreamActive(entry.sid, true);
        abortSessionRun(entry.sid, 'background-stream-budget');
        if (typeof resetStreamReconnectState === 'function') resetStreamReconnectState(entry.sid);
        excess--;
    });
}

function getSessionRunState(sessionId) {
    const sid = String(sessionId || '');
    if (!sid) return null;
    return sessionStore.getRun(sid) || null;
}

function clearSessionRunState(sessionId) {
    setSessionRunState(sessionId, null);
}

function clearSessionRunStateIfMatch(sessionId, runId) {
    const sid = String(sessionId || '');
    if (!sid) return;
    const expected = String(runId || '');
    if (!expected) {
        clearSessionRunState(sid);
        return;
    }
    const run = getSessionRunState(sid);
    if (!run || String(run.runId || '') === expected) {
        clearSessionRunState(sid);
    }
}

function markSessionRunInactive(sessionId) {
    const sid = String(sessionId || '');
    if (!sid) return;
    setSessionServerStreamActive(sid, false);
    sessionStore.activeRunInfoBySession.delete(sid);
    const sess = sessionStore.get(sid);
    if (sess) {
        sess.run_active = false;
        sess.run_started_at = null;
        sess.stream_active = false;
    }
    if (typeof updateSidebarRuntimeStatus === 'function') updateSidebarRuntimeStatus(true);
}

function markRunAbortReason(run, reason) {
    if (!run) return;
    var r = reason || 'cleanup';
    run.abortReason = r;
    if (run.ctx) run.ctx.abortReason = r;
}

function getRunAbortReason(sessionId, ctx) {
    const run = getSessionRunState(sessionId);
    return (run && run.abortReason) || (ctx && ctx.abortReason) || '';
}

function abortSessionRun(sessionId, reason, opts) {
    opts = opts || {};
    const run = getSessionRunState(sessionId);
    if (!run) return null;
    markRunAbortReason(run, reason || 'cleanup');
    try { if (run.controller) run.controller.abort(); } catch (e) { /* ignore */ }
    if (opts.clear !== false) clearSessionRunState(sessionId);
    return run;
}
