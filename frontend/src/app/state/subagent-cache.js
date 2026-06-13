var subagentBodyHtmlCache = Object.create(null);

function subagentBodyCacheKey(sessionId, agentId) {
    return String(sessionId || '') + ':' + String(agentId || '');
}

function isSubagentDetailPendingHtml(html) {
    return !html || html.indexOf('加载中') >= 0;
}

function forgetSubagentBodyCache(sessionId, agentId) {
    if (sessionId && agentId) {
        delete subagentBodyHtmlCache[subagentBodyCacheKey(sessionId, agentId)];
        return;
    }
    if (sessionId) {
        var prefix = String(sessionId) + ':';
        Object.keys(subagentBodyHtmlCache).forEach(function (k) {
            if (k.indexOf(prefix) === 0) delete subagentBodyHtmlCache[k];
        });
    }
}

function isSubagentBodyCacheComplete(html) {
    if (!html || isSubagentDetailPendingHtml(html)) return false;
    if (html.indexOf('subagent-detail-empty') >= 0) return false;
    if (html.indexOf('subagent-turn-process') < 0) {
        return html.indexOf('subagent-turn') >= 0 || html.indexOf('msg-wrap--assistant') >= 0;
    }
    return html.indexOf('msg-wrap--user') >= 0;
}

function rememberSubagentBodyCache(sessionId, agentId, html) {
    if (!sessionId || !agentId || !html || !isSubagentBodyCacheComplete(html)) return;
    subagentBodyHtmlCache[subagentBodyCacheKey(sessionId, agentId)] = html;
}

function readSubagentBodyCache(sessionId, agentId) {
    return subagentBodyHtmlCache[subagentBodyCacheKey(sessionId, agentId)] || '';
}
