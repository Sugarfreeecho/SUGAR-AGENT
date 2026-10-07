function renderSessionListFromStore() {
    if (!sessionsList) return Object.create(null);
    const nextStreamMap = Object.create(null);
    const sections = selectSessionSections();
    const allSessions = selectAllSessions();
    const searching = !!getSessionListSearchQuery();

    sessionsList.innerHTML = '';

    function appendSection(sectionKey, title, list, opts) {
        var options = opts || {};
        // 搜索态下归档区段的计数用命中条数，避免"3 条命中 / 12 条总数"的误导。
        var displayCount = (sectionKey === 'archived' && !searching)
            ? selectArchivedDisplayCount()
            : list.length;
        if (!displayCount) return;
        var expanded = sessionSectionExpanded(sectionKey);
        var sec = document.createElement('div');
        sec.className = 'session-section' + (expanded ? '' : ' is-collapsed');
        sec.dataset.section = sectionKey;

        var body = document.createElement('div');
        body.className = 'session-section-body';
        if (sectionKey === 'normal' && Array.isArray(sections.normalGroups) && sections.normalGroups.length) {
            for (let g = 0; g < sections.normalGroups.length; g += 1) {
                appendSessionGroupBlock(body, sections.normalGroups[g], allSessions, nextStreamMap);
            }
        } else {
            for (let j = 0; j < list.length; j += 1) {
                body.appendChild(buildAndBindSessionRow(list[j], allSessions, nextStreamMap));
            }
        }
        if (sectionKey === 'archived') appendArchiveLoadButton(body);
        sec.appendChild(body);
        sessionsList.appendChild(sec);

        // 「会话目录」的标题与三个图标在侧栏静态头（session-list-head）里，不再进滚动列表；
        // 置顶 / 归档仍保留列表内的折叠头。
        if (!options.headless) {
            var toggle = document.createElement('button');
            toggle.type = 'button';
            toggle.className = 'session-section-toggle';
            toggle.setAttribute('aria-expanded', expanded ? 'true' : 'false');
            toggle.innerHTML = '<span class="session-section-toggle-label">' + escapeHtml(title) + '</span>'
                + '<span class="session-section-meta">'
                + '<span class="session-section-count">' + String(displayCount) + '</span>'
                // 一级目录（归档目录）与侧栏列表头同款箭头：用同一枚 SVG，避免一个用字形、一个用图标
                + '<span class="session-section-chev" aria-hidden="true">'
                + ((typeof SIDEBAR_ICON_SVG !== 'undefined' && SIDEBAR_ICON_SVG.chevron) ? SIDEBAR_ICON_SVG.chevron : '▾')
                + '</span>'
                + '</span>';
            toggle.addEventListener('click', function (e) {
                e.preventDefault();
                sec.classList.toggle('is-collapsed');
                var isExpanded = !sec.classList.contains('is-collapsed');
                persistSessionSectionExpanded(sectionKey, isExpanded);
                toggle.setAttribute('aria-expanded', isExpanded ? 'true' : 'false');
            });
            sec.insertBefore(toggle, body);
        }
    }

    if (sections.showPinnedSection !== false) appendSection('pinned', '置顶目录', sections.pinned);
    if (sections.showNormalSection !== false) {
        appendSection('normal', '会话目录', sections.normal, { headless: true });
    }
    if (sections.showArchivedSection !== false) appendSection('archived', '归档目录', sections.archived);
    if (searching && !sessionsList.children.length) {
        var empty = document.createElement('div');
        empty.className = 'session-list-empty';
        empty.setAttribute('role', 'status');
        empty.textContent = '没有匹配的会话';
        sessionsList.appendChild(empty);
    }
    normalizeTruncatedSessionNames(sessionsList);
    if (typeof syncSessionListHead === 'function') {
        syncSessionListHead(sections, { searching: searching });
    }
    return nextStreamMap;
}

/**
 * 名字被 CSS 截断、且原名以全角右括号结尾时，改成"在括号内截断"：
 * 去掉收尾括号并自己补省略号，避免出现 `…）…`（右括号的字形外沿会与省略号挤在一起，
 * 放大后看起来像一个无法辨认的重叠字形）。完整名字仍在 data-original 与整行 tooltip 里。
 */
function normalizeTruncatedSessionNames(root) {
    if (!root || !root.querySelectorAll) return;
    var names = root.querySelectorAll('.session-name');
    // 两阶段：先"读"（测量+判断）后"写"（改文本）——避免读 scrollWidth → 写 → 再读造成的强制重排抖动。
    var fixes = [];
    for (var i = 0; i < names.length; i += 1) {
        var el = names[i];
        var full = String(el.getAttribute('data-original') || '');
        if (!full) continue;
        // scrollWidth > clientWidth ⇒ 该行确实被省略号截断
        if (el.scrollWidth <= el.clientWidth) continue;
        var trimmed = full.replace(/[）)】」』]+$/, '');
        if (trimmed === full || !trimmed) continue;
        fixes.push([el, trimmed]);
    }
    for (var j = 0; j < fixes.length; j += 1) {
        fixes[j][0].textContent = fixes[j][1] + '\u2026';
    }
}

/**
 * 「会话目录」的二级分组（时间 / 工作目录共用）。
 * 标题沿用 .session-time-group-title 风格；折叠状态按分组 key 走 sessionSectionExpanded，
 * 因此切换分组方式后各自的折叠状态互不干扰、刷新后仍保留。
 */
function appendSessionGroupBlock(body, group, allSessions, nextStreamMap) {
    if (!body || !group) return;
    var groupKey = String(group.key || group.title || '');
    var expanded = sessionSectionExpanded(groupKey);
    var wrap = document.createElement('div');
    wrap.className = 'session-group' + (expanded ? '' : ' is-collapsed');
    wrap.dataset.groupKey = groupKey;
    var workDirPath = group.isWorkDirGroup ? String(group.tip || '') : '';

    var headRow = document.createElement('div');
    headRow.className = 'session-group-head';

    var head = document.createElement('button');
    head.type = 'button';
    head.className = 'session-time-group-title'
        + (group.isWorkDirGroup ? ' session-time-group-title--workdir' : '');
    head.setAttribute('aria-expanded', expanded ? 'true' : 'false');
    if (group.tip) {
        head.setAttribute('title', String(group.tip));
        head.setAttribute('data-ui-tip', String(group.tip));
    }
    // 具名工作目录的标题是用户目录名：交给 i18n 层时明确跳过，避免被误译。
    if (group.isWorkDirGroup && !group.translatableTitle) head.setAttribute('data-i18n-skip', '1');
    head.innerHTML = '<span class="session-time-group-ico" aria-hidden="true">'
        + (group.isWorkDirGroup ? SESSION_GROUP_FOLDER_SVG : '')
        + '</span>'
        + '<span class="session-time-group-label">' + escapeHtml(group.title || '') + '</span>'
        // 折叠箭头用 SVG（字形外沿=盒子外沿），才能和主按钮/相对时间落在同一条右基准线上；
        // 文本 "▾" 的字形会因字体侧边距内缩 3-4px。
        + '<span class="session-time-group-chev" aria-hidden="true">' + sessionGroupChevronSvg() + '</span>';
    head.addEventListener('click', function (e) {
        e.preventDefault();
        wrap.classList.toggle('is-collapsed');
        var isExpanded = !wrap.classList.contains('is-collapsed');
        persistSessionSectionExpanded(groupKey, isExpanded);
        head.setAttribute('aria-expanded', isExpanded ? 'true' : 'false');
        // 每次从折叠态重新展开：展开档位重置为"前 5 个"（用户要求"每次展开都生效"）。
        if (isExpanded
                && typeof sessionGroupRevealStageOf === 'function' && sessionGroupRevealStageOf(groupKey) > 0
                && typeof resetSessionGroupReveal === 'function') {
            resetSessionGroupReveal(groupKey);
            if (typeof renderSessionListIfChanged === 'function') renderSessionListIfChanged(false);
        }
    });
    if (typeof bindUiHoverTip === 'function') bindUiHoverTip(head);

    // 工作目录分组头 hover 浮出两个动作：在该目录新建会话 / 目录的更多操作。
    if (group.isWorkDirGroup && workDirPath && typeof buildSessionGroupActions === 'function') {
        headRow.appendChild(head);
        headRow.appendChild(buildSessionGroupActions(group, workDirPath));
    } else {
        headRow.appendChild(head);
    }

    // 工作目录分组支持拖拽排序（render 后由管理模块绑定 Pointer 拖拽）。
    if (group.isWorkDirGroup && typeof bindSessionGroupDrag === 'function') {
        bindSessionGroupDrag(wrap, headRow, group);
    }

    var groupBody = document.createElement('div');
    groupBody.className = 'session-group-body';
    // 「每个工作目录默认显示前 5 个会话」：其余收起，点「显示更多」展开（搜索态不限额）。
    var searching = (typeof getSessionListSearchQuery === 'function') ? !!getSessionListSearchQuery() : false;
    var visible = (group.isWorkDirGroup && typeof sessionGroupSessionsVisible === 'function')
        ? sessionGroupSessionsVisible(group, { noLimit: searching })
        : { rows: group.sessions, hiddenCount: 0 };
    for (var i = 0; i < visible.rows.length; i += 1) {
        groupBody.appendChild(buildAndBindSessionRow(visible.rows[i], allSessions, nextStreamMap));
    }
    if (visible.hiddenCount > 0) {
        var moreBtn = document.createElement('button');
        moreBtn.type = 'button';
        moreBtn.className = 'session-group-more';
        moreBtn.setAttribute('data-group-more', String(group.key || ''));
        // 档位文案：前 5 →「显示更多」（到 10）→「展开全部」。
        var secondStage = visible.stage >= 1;
        moreBtn.setAttribute('aria-label',
            (secondStage ? '展开其余全部 ' : '显示更多 ') + visible.hiddenCount + ' 个会话');
        moreBtn.textContent = (secondStage ? '展开全部（' : '显示更多（') + visible.hiddenCount + '）';
        moreBtn.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            if (typeof advanceSessionGroupReveal === 'function') advanceSessionGroupReveal(group.key);
            if (typeof renderSessionListIfChanged === 'function') renderSessionListIfChanged(false);
        });
        groupBody.appendChild(moreBtn);
    }
    wrap.appendChild(headRow);
    wrap.appendChild(groupBody);
    body.appendChild(wrap);
}

// 16px：随二级目录字号一起放大（字号 0.58→0.82rem，图标 11→16px 同比例），与折叠箭头同级
var SESSION_GROUP_FOLDER_SVG = window.MyAgentIcons.svg('folder', 'session-group-folder-icon');
/**
 * 二级目录的折叠箭头：**与一级目录（列表头 / 归档目录）同款同尺寸**——
 * 直接复用同一枚图标资源，避免"一级小而二级大"（以前这里用贴满 viewBox 的自定义折线，
 * 是为了让字形外沿压住旧的右基准线；现在箭头紧跟标题，不再需要那个特例）。
 */
function sessionGroupChevronSvg() {
    if (typeof SIDEBAR_ICON_SVG !== 'undefined' && SIDEBAR_ICON_SVG && SIDEBAR_ICON_SVG.chevron) {
        return SIDEBAR_ICON_SVG.chevron;
    }
    return '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m7 10 5 5 5-5"></path></svg>';
}

function appendArchiveLoadButton(body) {
    var loadBtn = document.createElement('button');
    loadBtn.type = 'button';
    loadBtn.className = 'session-archive-load-btn';
    loadBtn.textContent = !sessionStore.archivedLoaded
        ? '加载归档目录'
        : (sessionStore.hasMoreArchivedSessions() ? '加载更多' : '刷新归档目录');
    loadBtn.addEventListener('click', async function (e) {
        e.preventDefault();
        e.stopPropagation();
        loadBtn.disabled = true;
        loadBtn.textContent = '加载中...';
        try {
            await loadArchivedSessions({ forceRender: true });
        } catch (err) {
            console.error('加载归档目录失败:', err);
            loadBtn.disabled = false;
            loadBtn.textContent = !sessionStore.archivedLoaded
                ? '加载归档目录'
                : (sessionStore.hasMoreArchivedSessions() ? '加载更多' : '刷新归档目录');
        }
    });
    body.appendChild(loadBtn);
    requestAnimationFrame(maybeAutoLoadMoreArchivedSessions);
}

var ARCHIVED_AUTO_LOAD_BOTTOM_PX = 32;

/** 滚动到归档目录底部附近时自动加载下一页；按钮仍保留为状态提示和手动兜底。 */
function maybeAutoLoadMoreArchivedSessions() {
    if (!sessionsList || !sessionStore.archivedLoaded || !sessionStore.hasMoreArchivedSessions()) return;
    var loadBtn = sessionsList.querySelector('.session-archive-load-btn');
    if (!loadBtn || loadBtn.disabled) return;
    var archiveSection = loadBtn.closest('.session-section');
    if (!archiveSection || archiveSection.classList.contains('is-collapsed')) return;
    var distanceToBottom = sessionsList.scrollHeight - sessionsList.scrollTop - sessionsList.clientHeight;
    if (distanceToBottom > ARCHIVED_AUTO_LOAD_BOTTOM_PX) return;
    loadBtn.click();
}

(function bindArchivedSessionsAutoLoaderOnce() {
    if (!sessionsList || window.__myAgentArchivedSessionsAutoLoader) return;
    window.__myAgentArchivedSessionsAutoLoader = true;
    sessionsList.addEventListener('scroll', maybeAutoLoadMoreArchivedSessions, { passive: true });
})();

function renderSessionTitleFromStore() {
    updateSessionTitle();
}
