function selectCurrentSession() {
    return sessionStore.get(sessionStore.currentSessionId);
}

/** 侧栏列表的当前搜索词（视图选项 → 搜索框；纯前端过滤，不落盘）。 */
var sessionListSearchQuery = '';

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
        { key: 'd3', title: '近三天', sessions: [] },
        { key: 'd7', title: '近7天', sessions: [] },
        { key: 'd15', title: '近半月', sessions: [] },
        { key: 'd30', title: '近一月', sessions: [] },
    ];
    // 时间分桶（2026-10 调整）：置顶单独成组在最前 → 今天 → 昨天 → 近三天 → 近7天 → 近半月(15天) → 近一月(30天)。
    // 超过一个月的会话由后端自动归档（AUTO_ARCHIVE_AFTER_DAYS=30），不再落入时间组；
    // 归档后可在「归档目录」查看（默认筛选为"隐藏已归档"）。
    // 时间模式下：置顶会话单独成一个二级分组，排在最前（工作目录模式不分出来，
    // 那里的置顶留在各自项目分组内最前 —— 见 selectNormalSessionWorkDirGroups）。
    var pinnedSessions = [];
    var now = new Date();
    var startToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
    var startYesterday = startToday - 86400000;
    var threeDaysAgo = Date.now() - (3 * 86400000);
    var sevenDaysAgo = Date.now() - (7 * 86400000);
    var fifteenDaysAgo = Date.now() - (15 * 86400000);
    var thirtyDaysAgo = Date.now() - (30 * 86400000);
    for (var i = 0; i < normalList.length; i += 1) {
        var s = normalList[i];
        if (s && s.pinned) {
            pinnedSessions.push(s);
            continue;
        }
        var t = sessionActivityTimeMs(s);
        if (t >= startToday) groups[0].sessions.push(s);
        else if (t >= startYesterday) groups[1].sessions.push(s);
        else if (t >= threeDaysAgo) groups[2].sessions.push(s);
        else if (t >= sevenDaysAgo) groups[3].sessions.push(s);
        else if (t >= fifteenDaysAgo) groups[4].sessions.push(s);
        else if (t >= thirtyDaysAgo) groups[5].sessions.push(s);
        // 超过 30 天：交给后端自动归档（此处不显示；归档后见「归档目录」）。
    }
    var result = groups.filter(function (g) { return g.sessions.length > 0; });
    if (pinnedSessions.length) {
        // key 带 time: 前缀，避免与旧的"置顶区段"折叠键互相干扰；
        // 标题复用既有 i18n 词条（置顶目录 → Pinned）。
        result.unshift({ key: 'time:pinned', title: '置顶目录', sessions: pinnedSessions });
    }
    return result;
}

/* ── 会话分组方式（侧栏「会话目录」的二级分组） ──────────────────────────
   time    ：置顶目录 / 今天 / 昨天 / 近三天 / 近7天 / 近半月 / 近一月（默认）
   workdir ：按会话自己的工作目录分组（服务端 work_dir / work_dir_label） */
/* localStorage 键：myagent-session-group-by（取值 time / workdir）。
   注意：getSessionGroupBy 可能在共享作用域初始化早期（settings.js 顶层）被调用，
   所以这里只用字面量，不引用本文件后面声明的 const，避免 TDZ。 */
function getSessionGroupBy() {
    try {
        return localStorage.getItem('myagent-session-group-by') === 'workdir'
            ? 'workdir'
            : 'time';
    } catch (e) {
        return 'time';
    }
}

function setSessionGroupBy(mode) {
    const next = mode === 'workdir' ? 'workdir' : 'time';
    try {
        localStorage.setItem('myagent-session-group-by', next);
    } catch (e) { /* 存储不可用：仅本次页面生效 */ }
    return next;
}

/** 服务端 work_dir_is_default=true 的会话归到这一组（key 固定，折叠状态可长期记忆） */
const SESSION_WORKDIR_DEFAULT_GROUP_KEY = 'workdir:__default__';

/** 会话的工作目录绝对路径；旧后端没有该字段时返回空串（此时按"默认工作目录"处理）。 */
function selectSessionWorkDir(session) {
    if (!session || typeof session.work_dir !== 'string') return '';
    return session.work_dir.trim();
}

/** 分组的身份键：去掉结尾分隔符并对大小写归一（Windows 路径不区分大小写）。 */
function sessionWorkDirIdentity(session) {
    return selectSessionWorkDir(session).replace(/[\\/]+$/, '').toLowerCase();
}

/** 组标题：优先服务端 work_dir_label，其次路径末级目录名，最后退回完整路径。 */
function sessionWorkDirGroupLabel(session) {
    if (session && typeof session.work_dir_label === 'string' && session.work_dir_label.trim()) {
        return session.work_dir_label.trim();
    }
    var abs = selectSessionWorkDir(session).replace(/[\\/]+$/, '');
    if (!abs) return '';
    var parts = abs.replace(/\\/g, '/').split('/').filter(Boolean);
    return parts.length ? parts[parts.length - 1] : abs;
}

/* ── 工作目录分组：自定义顺序 / 自定义名称 / 每组"前 5 个"配额 ───────────── */

/** 手动拖拽出的工作目录顺序（分组 key 数组，localStorage 持久化）。 */
function getWorkDirOrder() {
    try {
        const raw = localStorage.getItem('myagent-workdir-order');
        const parsed = raw ? JSON.parse(raw) : [];
        return Array.isArray(parsed)
            ? parsed.filter(function (k) { return typeof k === 'string' && k; })
            : [];
    } catch (e) {
        return [];
    }
}

function setWorkDirOrder(keys) {
    try {
        localStorage.setItem('myagent-workdir-order', JSON.stringify(Array.isArray(keys) ? keys : []));
    } catch (e) { /* 存储不可用：仅本次页面生效 */ }
}

/** 工作目录自定义显示名（分组 key → 名称；空名 = 恢复默认）。 */
function getWorkDirCustomLabel(key) {
    if (!key) return '';
    try {
        const raw = localStorage.getItem('myagent-workdir-labels');
        const map = raw ? JSON.parse(raw) : null;
        return (map && typeof map[key] === 'string') ? map[key].trim() : '';
    } catch (e) {
        return '';
    }
}

function setWorkDirCustomLabel(key, name) {
    if (!key) return;
    try {
        const raw = localStorage.getItem('myagent-workdir-labels');
        const map = (raw ? JSON.parse(raw) : null) || {};
        const next = String(name == null ? '' : name).trim();
        if (next) map[key] = next;
        else delete map[key];
        localStorage.setItem('myagent-workdir-labels', JSON.stringify(map));
    } catch (e) { /* ignore */ }
}

/* 「每个工作目录默认显示前 5 个会话」：运行中的行不占名额（学 DSH：
   provisional / running 行免配额）；点「显示更多」→ 10 个，再点「展开全部」→ 全部。
   每次目录从折叠态重新展开都会重置档位（内存态，刷新亦重置）。 */
const SESSION_GROUP_COLLAPSED_LIMIT = 5;
const SESSION_GROUP_REVEAL_STEP = 10;
var sessionGroupRevealStage = Object.create(null);   // 0=前5 / 1=前10 / 2=全部（未记录视为 0）

function sessionGroupRevealStageOf(key) {
    return (key && sessionGroupRevealStage[key]) ? sessionGroupRevealStage[key] : 0;
}

/** 展开档位前进一步：5 → 10 → 全部。 */
function advanceSessionGroupReveal(key) {
    if (!key) return;
    sessionGroupRevealStage[key] = Math.min(2, sessionGroupRevealStageOf(key) + 1);
}

/** 重置档位（目录从折叠态重新展开时调用：每次展开都从"前 5 个"重新生效）。 */
function resetSessionGroupReveal(key) {
    if (key) delete sessionGroupRevealStage[key];
}

/** 返回 { rows, hiddenCount, stage }：workdir 组按档位截断；搜索态不截断。 */
function sessionGroupSessionsVisible(group, opts) {
    const sessions = (group && group.sessions) || [];
    if (!sessions.length) return { rows: sessions, hiddenCount: 0, stage: 0 };
    if (opts && opts.noLimit) return { rows: sessions, hiddenCount: 0, stage: 0 };
    const stage = sessionGroupRevealStageOf(group.key);
    if (stage >= 2) return { rows: sessions, hiddenCount: 0, stage };
    const quota = stage >= 1 ? SESSION_GROUP_REVEAL_STEP : SESSION_GROUP_COLLAPSED_LIMIT;
    const rows = [];
    let idleCount = 0;
    for (let i = 0; i < sessions.length; i += 1) {
        const s = sessions[i];
        const running = (typeof isSessionRunning === 'function') && isSessionRunning(s.id);
        const busy = running || (Number(s.subagent_running || 0) > 0);
        if (busy) { rows.push(s); continue; }
        if (idleCount < quota) { rows.push(s); idleCount += 1; }
    }
    // 严格分级（5 → 10 → 全部）：不再因"当前会话在组里"而提前整组展开——
    // 那会让同一功能在不同组间表现不一致（用户反馈"有时直接显示全部"）。
    return { rows: rows, hiddenCount: sessions.length - rows.length, stage };
}

function selectNormalSessionWorkDirGroups(normalList) {
    var byKey = Object.create(null);
    var groups = [];
    for (var i = 0; i < normalList.length; i += 1) {
        var s = normalList[i];
        var isDefault = !!s.work_dir_is_default || !sessionWorkDirIdentity(s);
        var key = isDefault
            ? SESSION_WORKDIR_DEFAULT_GROUP_KEY
            : ('workdir:' + sessionWorkDirIdentity(s));
        var group = byKey[key];
        if (!group) {
            var customLabel = getWorkDirCustomLabel(key);
            group = {
                key: key,
                // 自定义名称优先（默认组也可以改显示名，但身份仍是"默认"）；
                // 默认组标题走 i18n（'默认工作目录'）；具名组标题是目录名（不翻译）。
                title: customLabel || (isDefault ? '默认工作目录' : sessionWorkDirGroupLabel(s)),
                translatableTitle: isDefault && !customLabel,
                tip: selectSessionWorkDir(s),
                isWorkDirGroup: true,
                isDefaultWorkDir: isDefault,
                activityMs: 0,
                order: groups.length,
                sessions: [],
            };
            byKey[key] = group;
            groups.push(group);
        }
        group.sessions.push(s);
        if (!group.tip) group.tip = selectSessionWorkDir(s);
        var t = sessionActivityTimeMs(s);
        if (t > group.activityMs) group.activityMs = t;
    }
    // 组顺序：默认工作目录组在前；其余优先手动拖拽顺序（未安排的在后面按最近活动倒序）；
    // 时间相同保持服务端首次出现顺序。
    const orderList = getWorkDirOrder();
    const orderIndex = Object.create(null);
    orderList.forEach(function (key2, index) { orderIndex[key2] = index; });
    groups.sort(function (a, b) {
        const ai = orderIndex[a.key];
        const bi = orderIndex[b.key];
        const hasA = ai !== undefined;
        const hasB = bi !== undefined;
        if (hasA && hasB) return ai - bi;
        if (hasA !== hasB) return hasA ? -1 : 1;
        if (b.activityMs !== a.activityMs) return b.activityMs - a.activityMs;
        return a.order - b.order;
    });
    return groups;
}

/** 「会话目录」二级分组：组内顺序沿用服务端排序（不重新排）。 */
function selectNormalSessionGroups(normalList) {
    return getSessionGroupBy() === 'workdir'
        ? selectNormalSessionWorkDirGroups(normalList)
        : selectNormalSessionTimeGroups(normalList);
}

/* ── 侧栏列表的搜索与归档筛选（视图选项菜单用） ─────────────────────────
   search ：标题 / 最近提问的子串过滤，纯前端（不新增后端接口）
   filter ：show=显示归档区段（历史行为，默认）/ hide=不渲染归档 / only=只看归档 */
function getSessionListSearchQuery() {
    return String(sessionListSearchQuery || '').trim();
}

function setSessionListSearchQuery(query) {
    sessionListSearchQuery = String(query == null ? '' : query);
    return sessionListSearchQuery;
}

function getSessionArchiveFilter() {
    try {
        var raw = localStorage.getItem('myagent-session-archive-filter');
        return (raw === 'show' || raw === 'only') ? raw : 'hide';
    } catch (e) {
        return 'hide';
    }
}

function setSessionArchiveFilter(filter) {
    const next = (filter === 'show' || filter === 'only') ? filter : 'hide';
    try {
        localStorage.setItem('myagent-session-archive-filter', next);
    } catch (e) { /* 存储不可用：仅本次页面生效 */ }
    return next;
}

/** 会话是否命中当前搜索词（标题或最近提问子串，大小写不敏感）。 */
function sessionMatchesListSearch(sess) {
    var q = getSessionListSearchQuery();
    if (!q) return true;
    if (!sess) return false;
    var needle = q.toLowerCase();
    var name = String(sess.name == null ? '' : sess.name).toLowerCase();
    if (name.indexOf(needle) >= 0) return true;
    var preview = String(sess.last_user_preview == null ? '' : sess.last_user_preview).toLowerCase();
    if (preview.indexOf(needle) >= 0) return true;
    var label = String(sess.work_dir_label == null ? '' : sess.work_dir_label).toLowerCase();
    if (label.indexOf(needle) >= 0) return true;
    // 重命名后的显示名同样参与匹配（和用户看到的标题一致）。
    var isDefaultGroup = !!sess.work_dir_is_default || !sessionWorkDirIdentity(sess);
    var groupKeyForLabel = isDefaultGroup
        ? SESSION_WORKDIR_DEFAULT_GROUP_KEY
        : ('workdir:' + sessionWorkDirIdentity(sess));
    var customLabel = getWorkDirCustomLabel(groupKeyForLabel).toLowerCase();
    if (customLabel && customLabel.indexOf(needle) >= 0) return true;
    return false;
}

function selectSessionsMatchingSearch(list) {
    var q = getSessionListSearchQuery();
    if (!q) return list;
    return list.filter(function (s) { return sessionMatchesListSearch(s); });
}

function selectSessionSections() {
    const normalList = [];
    const allSessions = selectAllSessions();
    for (let i = 0; i < allSessions.length; i += 1) {
        const s = allSessions[i];
        if (!s || !s.id || !!s.archived) continue;
        // 置顶不再单独成区：置顶会话留在它自己的时间 / 工作目录分组里。
        // 服务端排序本来就是"置顶优先"，所以它们在各自组内自然排在最前
        // —— 即"工作目录模式下没有专门的置顶目录，只在每个项目内置顶"。
        normalList.push(s);
    }
    const archiveFilter = getSessionArchiveFilter();
    return {
        // 兼容旧调用方：置顶区已取消（渲染层不会再单独成区）。
        pinned: [],
        normal: selectSessionsMatchingSearch(normalList),
        normalGroups: selectNormalSessionGroups(selectSessionsMatchingSearch(normalList)),
        archived: archiveFilter === 'hide' ? [] : selectSessionsMatchingSearch(selectArchivedSessions()),
        // 'only' 时只渲染归档区段；'hide' 连归档区段入口一起隐藏。
        archiveFilter: archiveFilter,
        showPinnedSection: false,
        showNormalSection: archiveFilter !== 'only',
        showArchivedSection: archiveFilter !== 'hide',
    };
}

function selectArchivedDisplayCount() {
    return sessionStore.archivedCount;
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

