/* 公共左侧栏（会话状态面板）· 方案 B（页签）
 *
 * 一条栏 = 头部 + 页签条 + 页签内容。内容按 session.panel 的 group 声明分组
 * （缺省「插件」组），「改动」页签由改动审查插件通过 MyAgentPubar.registerPane 注册。
 * 显隐、徽标、活动页签记忆与键盘切换集中在本模块；开合 / 避让 / 自动折叠仍由
 * layout-panels.js 负责——本模块只通过 hasContent() 向其提供“是否有内容”的统一判定。
 *
 * 本文件以普通脚本片段装载（index.js 的 uiSources，与其它 modules/*.js 相同），
 * 不要使用 import / export；测试通过 data:URL 注入导出（见 tests/js/public_sidebar_runtime.mjs）。
 */

var PUBAR_ROOT_ID = 'chat-todo-plan';
var PUBAR_ACTIVE_TAB_KEY = 'pubar-active-tab';
var PUBAR_DEFAULT_GROUP_ID = 'plugins';
var PUBAR_DEFAULT_GROUP_LABEL = '插件';
var PUBAR_DEFAULT_ORDER = 30;
var PUBAR_ORDER_FALLBACK = 100;
var PUBAR_PULSE_MS = 1600;
var PUBAR_AUTO_SWITCH_COALESCE_MS = 150;
var PUBAR_SESSION_SWITCH_SUPPRESS_MS = 4000;
var PUBAR_ID_PATTERN = /^[a-z][a-z0-9._-]{0,63}$/;

var pubarPanes = [];
var pubarActiveId = null;
var pubarRootEl = null;
var pubarTabsEl = null;
var pubarPanesEl = null;
var pubarInitialized = false;
var pubarSuppressAutoSwitchUntil = 0;
var pubarAutoSwitchTimer = null;
var pubarAutoSwitchTarget = null;
var pubarNarrowStripEl = null;
var pubarNarrowPopoverEl = null;
var pubarNarrowTitleEl = null;
var pubarNarrowBodyEl = null;
var pubarNarrowOpenId = null;
var pubarNarrowConfigs = {};
var pubarNarrowClassObserver = null;

function pubarFindPane(id) {
    for (var i = 0; i < pubarPanes.length; i += 1) {
        if (pubarPanes[i].id === id) return pubarPanes[i];
    }
    return null;
}

function pubarCountVisibleChildren(host) {
    var children = (host && host.children) || [];
    var count = 0;
    for (var i = 0; i < children.length; i += 1) {
        if (!children[i].hidden) count += 1;
    }
    return count;
}

function pubarPaneHasContent(pane) {
    if (!pane) return false;
    if (pane.owner === 'external') return pane.explicitVisible === true;
    return pubarCountVisibleChildren(pane.host) > 0;
}

function pubarSortPaneDom() {
    if (!pubarTabsEl || !pubarPanesEl) return;
    pubarPanes.slice().sort(function (a, b) { return a.order - b.order; })
        .forEach(function (pane) {
            pubarTabsEl.appendChild(pane.tab);
            pubarPanesEl.appendChild(pane.host);
        });
}

function pubarEnsurePane(rawId, meta) {
    var id = String(rawId || '').trim();
    if (!PUBAR_ID_PATTERN.test(id)) id = PUBAR_DEFAULT_GROUP_ID;
    var existing = pubarFindPane(id);
    if (existing) return existing;
    meta = meta || {};
    var order = Number(meta.order);
    if (!Number.isFinite(order)) order = id === PUBAR_DEFAULT_GROUP_ID ? PUBAR_DEFAULT_ORDER : PUBAR_ORDER_FALLBACK;
    var label = String(meta.label || '').trim();
    if (!label) label = id === PUBAR_DEFAULT_GROUP_ID ? PUBAR_DEFAULT_GROUP_LABEL : id;

    var host = document.createElement('section');
    host.className = 'pubar-pane';
    host.hidden = true;
    host.setAttribute('data-pubar-pane', id);
    host.setAttribute('role', 'tabpanel');
    host.setAttribute('id', 'pubar-pane-' + id);
    host.setAttribute('aria-labelledby', 'pubar-tab-' + id);

    var tab = document.createElement('button');
    tab.type = 'button';
    tab.className = 'pubar-tab';
    tab.hidden = true;
    tab.setAttribute('role', 'tab');
    tab.setAttribute('data-pubar-tab', id);
    tab.setAttribute('id', 'pubar-tab-' + id);
    tab.setAttribute('aria-controls', 'pubar-pane-' + id);
    tab.setAttribute('aria-selected', 'false');
    tab.setAttribute('tabindex', '-1');
    var labelEl = document.createElement('span');
    labelEl.className = 'pubar-tab-label';
    labelEl.textContent = label;
    var countEl = document.createElement('span');
    countEl.className = 'pubar-tab-count';
    countEl.hidden = true;
    tab.appendChild(labelEl);
    tab.appendChild(countEl);
    tab.addEventListener('click', function () {
        pubarAutoSwitchTarget = null;
        pubarActivate(id);
    });

    var pane = {
        id: id, label: label, order: order,
        host: host, tab: tab, labelEl: labelEl, countEl: countEl,
        owner: 'group', explicitVisible: null, visible: false, count: 0,
        lastCount: 0, wasVisible: false, pulseTimer: null,
    };
    pubarPanes.push(pane);
    pubarSortPaneDom();
    return pane;
}

function pubarUpdateCount(pane) {
    var value = Math.max(0, Math.floor(Number(pane.count) || 0));
    var show = pane.visible && (pane.owner === 'external' ? value > 0 : value > 1);
    pane.countEl.hidden = !show;
    pane.countEl.textContent = show ? String(value) : '';
}

function pubarReadStoredActive() {
    try {
        if (typeof localStorage === 'undefined') return '';
        return String(localStorage.getItem(PUBAR_ACTIVE_TAB_KEY) || '');
    } catch (error) { return ''; }
}

function pubarWriteStoredActive(id) {
    try {
        if (typeof localStorage !== 'undefined') localStorage.setItem(PUBAR_ACTIVE_TAB_KEY, id);
    } catch (error) { /* 忽略存储异常 */ }
}

function pubarSetActive(id) {
    var pane = id ? pubarFindPane(id) : null;
    if (pane && !pubarPaneHasContent(pane)) pane = null;
    var previous = pubarActiveId;
    pubarActiveId = pane ? pane.id : null;
    for (var i = 0; i < pubarPanes.length; i += 1) {
        var entry = pubarPanes[i];
        var active = entry === pane;
        entry.host.hidden = !active;
        entry.tab.classList.toggle('is-active', active);
        entry.tab.setAttribute('aria-selected', active ? 'true' : 'false');
        entry.tab.setAttribute('tabindex', active ? '0' : '-1');
    }
    if (pane && pane.id !== previous) pubarWriteStoredActive(pane.id);
}

function pubarPulseTab(pane) {
    if (pane.pulseTimer) {
        clearTimeout(pane.pulseTimer);
        pane.pulseTimer = null;
    }
    pane.tab.classList.remove('is-pulse');
    pane.tab.classList.add('is-pulse');
    pane.pulseTimer = setTimeout(function () {
        pane.pulseTimer = null;
        pane.tab.classList.remove('is-pulse');
    }, PUBAR_PULSE_MS);
}

/* 自动跟随：新内容出现时切换到该页签；会话切换抑制期内回退为脉冲提示。 */
function pubarFollowActivity(pane) {
    if (!pane || pane.id === pubarActiveId) return;
    if (Date.now() < pubarSuppressAutoSwitchUntil) {
        pubarPulseTab(pane);
        return;
    }
    pubarAutoSwitchTarget = pane.id;
    if (pubarAutoSwitchTimer) return;
    pubarAutoSwitchTimer = setTimeout(function () {
        pubarAutoSwitchTimer = null;
        var target = pubarAutoSwitchTarget;
        pubarAutoSwitchTarget = null;
        if (!target || Date.now() < pubarSuppressAutoSwitchUntil) return;
        var next = pubarFindPane(target);
        if (next && pubarPaneHasContent(next) && next.id !== pubarActiveId) {
            pubarSetActive(next.id);
            if (next.pulseTimer) {
                clearTimeout(next.pulseTimer);
                next.pulseTimer = null;
            }
            next.tab.classList.remove('is-pulse');
        }
    }, PUBAR_AUTO_SWITCH_COALESCE_MS);
}

function pubarPaneFromActivityTarget(target) {
    if (target && typeof target.closest === 'function') {
        var host = target.closest('.pubar-pane');
        return host ? pubarFindPane(String(host.getAttribute('data-pubar-pane') || '')) : null;
    }
    if (target != null) return pubarFindPane(String(target));
    return null;
}

/* 插件渲染器入口：通知某元素所属页签发生了“实质更新”（渲染器自行判定，避免秒级刷新误报）。
 * 渲染器可能在尚未挂载的文档片段中提前上报（closest 找不到宿主）：延迟一拍、内容提交后再补解析。 */
function pubarNotifyActivity(target) {
    var pane = pubarPaneFromActivityTarget(target);
    if (pane) {
        if (pubarPaneHasContent(pane)) pubarFollowActivity(pane);
        return;
    }
    if (target && typeof target.closest === 'function') {
        setTimeout(function () {
            var later = pubarPaneFromActivityTarget(target);
            if (later && pubarPaneHasContent(later)) pubarFollowActivity(later);
        }, 120);
    }
}

/* 非活动页签出现新内容：自动切换（抑制期内脉冲提示）。整栏从“空”开始的首次成批出现不算“新内容”。 */
function pubarTrackNewContent() {
    var anyWasVisible = false;
    for (var i = 0; i < pubarPanes.length; i += 1) {
        if (pubarPanes[i].wasVisible) anyWasVisible = true;
    }
    pubarPanes.forEach(function (pane) {
        var grew = pane.visible && pane.count > pane.lastCount;
        var appeared = pane.visible && !pane.wasVisible;
        if (anyWasVisible && (grew || appeared) && pane.id !== pubarActiveId) {
            pubarFollowActivity(pane);
        }
        pane.wasVisible = pane.visible;
        pane.lastCount = pane.count;
    });
}

function pubarSync() {
    if (!pubarInitialized) return false;
    var i;
    var visiblePanes = [];
    for (i = 0; i < pubarPanes.length; i += 1) {
        var pane = pubarPanes[i];
        pane.visible = pubarPaneHasContent(pane);
        if (pane.owner !== 'external') pane.count = pubarCountVisibleChildren(pane.host);
        if (pane.visible) visiblePanes.push(pane);
    }
    if (pubarTabsEl) pubarTabsEl.hidden = visiblePanes.length < 2;
    for (i = 0; i < pubarPanes.length; i += 1) {
        pubarPanes[i].tab.hidden = !pubarPanes[i].visible;
        pubarUpdateCount(pubarPanes[i]);
    }
    var nextActive = null;
    var current = pubarActiveId ? pubarFindPane(pubarActiveId) : null;
    if (current && current.visible) nextActive = current.id;
    if (!nextActive) {
        var stored = pubarFindPane(pubarReadStoredActive());
        if (stored && stored.visible) nextActive = stored.id;
    }
    if (!nextActive && visiblePanes.length) nextActive = visiblePanes[0].id;
    pubarSetActive(nextActive);
    pubarTrackNewContent();
    if (typeof syncExtensionPanelVisibility === 'function') syncExtensionPanelVisibility();
    else if (typeof notifyPanelContentChanged === 'function') notifyPanelContentChanged();
    pubarRenderNarrowStrip();
    return visiblePanes.length > 0;
}

function pubarHasContent() {
    for (var i = 0; i < pubarPanes.length; i += 1) {
        if (pubarPaneHasContent(pubarPanes[i])) return true;
    }
    return false;
}

function pubarGetActiveId() {
    return pubarActiveId;
}

function pubarActivate(id) {
    var pane = id ? pubarFindPane(id) : null;
    if (!pane || !pubarPaneHasContent(pane)) return false;
    pubarSetActive(pane.id);
    if (pane.pulseTimer) {
        clearTimeout(pane.pulseTimer);
        pane.pulseTimer = null;
    }
    pane.tab.classList.remove('is-pulse');
    return true;
}

/* ── 窄态条目区（输入框上方）：左栏收起时承载「会话状态」条目；点击条目不展开左栏，而是打开浮窗 ── */
var PUBAR_NARROW_ICONS = {
    pane: '<rect x="4" y="5" width="16" height="14" rx="2.5"/><path d="M4 9.5h16"/>',
    grid: '<rect x="4" y="4" width="6.5" height="6.5" rx="1.5"/><rect x="13.5" y="4" width="6.5" height="6.5" rx="1.5"/><rect x="4" y="13.5" width="6.5" height="6.5" rx="1.5"/><rect x="13.5" y="13.5" width="6.5" height="6.5" rx="1.5"/>',
    check: '<circle cx="12" cy="12" r="8.2"/><path d="M8.3 12.4l2.6 2.6 4.9-5.2"/>',
    target: '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3.4"/>',
    diff: '<path d="M5 7h14M5 12h14M5 17h6"/><path d="M17.5 16.5h4M19.5 14.5v4" stroke-width="1.6"/>',
    pause: '<path d="M9 5v14M15 5v14"/>',
    play: '<path d="m8 5 11 7-11 7Z"/>',
    edit: '<path d="m4 20 4.5-1 10-10a2.1 2.1 0 0 0-3-3l-10 10Z"/><path d="m14 7 3 3"/>',
    trash: '<path d="M4 7h16M9 7V4h6v3M7 7l1 13h8l1-13M10 11v5M14 11v5"/>',
    chevron: '<path d="M18 15l-6-6-6 6"/>',
};

function pubarNarrowIcon(name) {
    var body = PUBAR_NARROW_ICONS[String(name || '')] || PUBAR_NARROW_ICONS.pane;
    return '<svg viewBox="0 0 24 24" aria-hidden="true">' + body + '</svg>';
}

function pubarNarrowConfigOf(pane) {
    var configured = pubarNarrowConfigs[pane.id] || {};
    var summary = configured.summary != null ? String(configured.summary) : '';
    if (!summary && !configured.summaryHtml && pane.owner !== 'external' && pane.count > 1) {
        summary = pane.count + ' 个面板';
    }
    return {
        icon: configured.icon || (pane.id === PUBAR_DEFAULT_GROUP_ID ? 'grid' : 'pane'),
        label: configured.label || pane.label,
        summary: summary,
        summaryHtml: configured.summaryHtml || '',
        summaryTip: configured.summaryTip || '',
        chip: configured.chip || null,
        actions: configured.actions || [],
    };
}

function pubarNarrowHasOpen(paneId) {
    return !!pubarNarrowOpenId && pubarNarrowOpenId === paneId;
}

function pubarBuildNarrowItem(pane, config) {
    config = config || pubarNarrowConfigOf(pane);
    var item = document.createElement('div');
    item.className = 'pni';
    item.setAttribute('data-pubar-narrow-item', pane.id);
    if (pubarNarrowHasOpen(pane.id)) item.setAttribute('data-open', '1');
    var main = document.createElement('button');
    main.type = 'button';
    main.className = 'pni-main';
    main.setAttribute('aria-expanded', pubarNarrowHasOpen(pane.id) ? 'true' : 'false');
    main.setAttribute('aria-label', config.label);
    var icon = document.createElement('span');
    icon.className = 'pni-ico';
    icon.innerHTML = pubarNarrowIcon(config.icon);
    var label = document.createElement('strong');
    label.className = 'pni-label';
    label.textContent = config.label;
    main.append(icon, label);
    if (config.chip && config.chip.text) {
        var chip = document.createElement('span');
        chip.className = 'pni-chip'
            + (config.chip.tone === 'green' ? ' pni-chip--green' : '')
            + (config.chip.tone === 'neutral' ? ' pni-chip--neutral' : '');
        chip.textContent = String(config.chip.text);
        main.appendChild(chip);
    }
    var summary = document.createElement('span');
    summary.className = 'pni-summary';
    if (config.summaryHtml) summary.innerHTML = String(config.summaryHtml);
    else summary.textContent = config.summary;
    main.appendChild(summary);
    if (typeof setUiHoverTip === 'function') {
        setUiHoverTip(main, [config.label, config.chip && config.chip.text,
            config.summaryTip || summary.textContent].filter(Boolean).join('\n'));
    }
    main.addEventListener('click', function () { pubarOpenNarrowPopover(pane.id); });
    item.appendChild(main);
    var actions = document.createElement('span');
    actions.className = 'pni-actions';
    (config.actions || []).forEach(function (action, actionIndex) {
        if (!action || action.hidden) return;
        var btn = document.createElement('button');
        btn.type = 'button';
        if (action.label) {
            btn.className = 'pni-btn pni-btn--text';
            btn.textContent = String(action.label);
        } else {
            btn.className = 'pni-btn';
            btn.innerHTML = pubarNarrowIcon(action.icon);
        }
        var actionTip = action.tip || action.label;
        if (actionTip) {
            btn.setAttribute('aria-label', String(actionTip));
            if (typeof setUiHoverTip === 'function') setUiHoverTip(btn, actionTip);
        }
        btn.addEventListener('click', function (event) {
            event.preventDefault();
            event.stopPropagation();
            // 外观相同也可能换了回调；复用按钮时仍取最新动作。
            var latest = pubarNarrowConfigOf(pane).actions[actionIndex];
            if (latest && typeof latest.onClick === 'function') latest.onClick(pane.id);
        });
        actions.appendChild(btn);
    });
    if (actions.children.length) item.appendChild(actions);
    /* 展开箭头固定在条目最右缘（动作按钮之后），保证所有条目箭头纵向对齐 */
    var chevron = document.createElement('span');
    chevron.className = 'pni-chev';
    chevron.innerHTML = pubarNarrowIcon('chevron');
    item.appendChild(chevron);
    item.addEventListener('click', function (event) {
        var target = event && event.target;
        if (target && typeof target.closest === 'function' && target.closest('button')) return;
        pubarOpenNarrowPopover(pane.id);
    });
    return item;
}

function pubarNarrowSignature(pane, config) {
    return JSON.stringify([pane.id, pubarNarrowHasOpen(pane.id), config.icon, config.label,
        config.summary, config.summaryHtml, config.summaryTip, config.chip,
        config.actions.map(function (action) {
            return action ? [action.hidden, action.icon, action.label, action.tip] : null;
        })]);
}

function pubarRenderNarrowStrip() {
    if (!pubarNarrowStripEl) return;
    if (pubarRootEl && pubarRootEl.classList.contains('is-open')) {
        pubarCloseNarrowPopover();
        pubarNarrowStripEl.hidden = true;
        return;
    }
    if (pubarNarrowOpenId) {
        var openPane = pubarFindPane(pubarNarrowOpenId);
        if (!openPane || !pubarPaneHasContent(openPane)) pubarCloseNarrowPopover();
    }
    var panes = pubarPanes.filter(function (pane) { return pane.visible; })
        .sort(function (a, b) { return a.order - b.order; });
    if (!panes.length) {
        pubarNarrowStripEl.hidden = true;
        return;
    }
    var strip = pubarNarrowStripEl;
    panes.forEach(function (pane, index) {
        var config = pubarNarrowConfigOf(pane);
        var signature = pubarNarrowSignature(pane, config);
        if (!pane.narrowItem || pane.narrowSignature !== signature) {
            var previous = pane.narrowItem;
            pane.narrowItem = pubarBuildNarrowItem(pane, config);
            pane.narrowSignature = signature;
            if (previous && previous.parentNode === strip) strip.removeChild(previous);
        }
        if (strip.children[index] !== pane.narrowItem) {
            strip.insertBefore(pane.narrowItem, strip.children[index] || null);
        }
    });
    while (strip.children.length > panes.length) strip.removeChild(strip.lastElementChild);
    strip.hidden = false;
}

function pubarOpenNarrowPopover(id) {
    var pane = pubarFindPane(id);
    if (!pane || !pubarPaneHasContent(pane) || !pubarNarrowPopoverEl || !pubarNarrowBodyEl) return false;
    if (pubarRootEl && pubarRootEl.classList.contains('is-open')) return false;
    if (pubarNarrowOpenId === pane.id) {
        pubarCloseNarrowPopover();
        return true;
    }
    pubarCloseNarrowPopover();
    pubarNarrowOpenId = pane.id;
    pubarSetActive(pane.id);
    if (pubarNarrowTitleEl) pubarNarrowTitleEl.textContent = pane.label;
    pane.host.classList.add('is-narrow-floating');
    pane.host.hidden = false;
    /* 直接搬移页签宿主：插件持续向同一宿主渲染，浮窗内内容始终是实时的。 */
    pubarNarrowBodyEl.appendChild(pane.host);
    pubarNarrowPopoverEl.hidden = false;
    pubarRenderNarrowStrip();
    return true;
}

function pubarCloseNarrowPopover() {
    if (!pubarNarrowOpenId) {
        if (pubarNarrowPopoverEl) pubarNarrowPopoverEl.hidden = true;
        return;
    }
    var pane = pubarFindPane(pubarNarrowOpenId);
    pubarNarrowOpenId = null;
    if (pubarNarrowPopoverEl) pubarNarrowPopoverEl.hidden = true;
    if (pane) {
        pane.host.classList.remove('is-narrow-floating');
        if (pubarPanesEl) {
            pubarPanesEl.appendChild(pane.host);
            pubarSortPaneDom();
        }
        pubarSetActive(pubarActiveId);
    }
    if (pubarNarrowStripEl && !pubarNarrowStripEl.hidden) pubarRenderNarrowStrip();
}

/* 插件/外壳为某个页签配置窄态条目外观（label / 图标 / 计数摘要 / 状态胶囊 / 行内动作按钮）。 */
function pubarConfigureNarrow(id, config) {
    var pane = pubarFindPane(String(id || '').trim());
    if (!pane) return false;
    if (config && typeof config === 'object') pubarNarrowConfigs[pane.id] = config;
    else delete pubarNarrowConfigs[pane.id];
    pubarRenderNarrowStrip();
    return true;
}

/** Update a live status label while preserving narrow-item buttons and focus. */
function pubarUpdateNarrowChip(id, text) {
    var pane = pubarFindPane(String(id || '').trim());
    var config = pane && pubarNarrowConfigs[pane.id];
    if (!config || !config.chip) return false;
    config.chip.text = String(text || '');
    var item = pubarNarrowStripEl && pubarNarrowStripEl.querySelector('[data-pubar-narrow-item="' + pane.id + '"]');
    var chip = item && item.querySelector('.pni-chip');
    if (chip && chip.textContent !== config.chip.text) chip.textContent = config.chip.text;
    var main = item && item.querySelector('.pni-main');
    if (main && typeof setUiHoverTip === 'function') {
        var summary = item.querySelector('.pni-summary');
        setUiHoverTip(main, [config.label || pane.label, config.chip.text,
            config.summaryTip || (summary && summary.textContent)].filter(Boolean).join('\n'));
    }
    /* 只改文字、结构未变：同步记忆签名，避免下一次 pubarRenderNarrowStrip（面板重渲染都会调用，
       流式期间每个插件更新一次）把条目判定成“内容已变”而整条重建。重建会丢掉悬停/过渡状态，
       并让 backdrop-filter 重新合成，视觉上就是每秒一次的抖动与残影。
       仅当活体 DOM 确实已显示新文字（胶囊存在且内容一致）时才记忆，否则保留旧签名让下次正确重建。 */
    if (item && chip && chip.textContent === config.chip.text) {
        /* 必须走与 pubarRenderNarrowStrip 相同的归一化入口，否则 summaryHtml 等缺省字段
           （undefined vs ""）会让签名永远不相等，反而每帧都重建。 */
        pane.narrowSignature = pubarNarrowSignature(pane, pubarNarrowConfigOf(pane));
    }
    return true;
}

/* 宿主渲染管线入口：取/建分组的页签与内容宿主（宿主缺省隐藏，内容出现后由 sync 显示）。 */
function pubarPaneHostFor(groupId, meta) {
    if (!pubarInitialized) return null;
    return pubarEnsurePane(groupId, meta).host;
}

/* 外部内容注册（改动审查等）：返回句柄；setVisible / setCount 驱动页签显隐与徽标。 */
function pubarRegisterPane(options) {
    options = options || {};
    if (!pubarInitialized) return null;
    var id = String(options.id || '').trim();
    if (!PUBAR_ID_PATTERN.test(id)) return null;
    var pane = pubarFindPane(id) || pubarEnsurePane(id, { label: options.label, order: options.order });
    pane.owner = 'external';
    if (options.order != null && Number.isFinite(Number(options.order))) pane.order = Number(options.order);
    if (options.label != null) {
        pane.label = String(options.label);
        pane.labelEl.textContent = pane.label;
    }
    if (pane.explicitVisible !== true) pane.explicitVisible = false;
    return {
        host: pane.host,
        setVisible: function (visible) {
            var next = visible === true;
            if (pane.explicitVisible === next && pane.visible === next) return;
            pane.explicitVisible = next;
            pubarSync();
        },
        setCount: function (count) {
            var next = Math.max(0, Math.floor(Number(count) || 0));
            if (pane.count === next) return;
            pane.count = next;
            pubarUpdateCount(pane);
            pubarSync();
        },
        setLabel: function (label) {
            if (label == null) return;
            pane.label = String(label);
            pane.labelEl.textContent = pane.label;
        },
        setNarrow: function (config) { pubarConfigureNarrow(id, config); },
        remove: function () { pubarRemovePane(id); },
    };
}

function pubarRemovePane(id) {
    var pane = pubarFindPane(id);
    if (!pane) return;
    if (pubarNarrowOpenId === id) pubarCloseNarrowPopover();
    if (pane.pulseTimer) {
        clearTimeout(pane.pulseTimer);
        pane.pulseTimer = null;
    }
    if (pane.tab.parentNode) pane.tab.parentNode.removeChild(pane.tab);
    if (pane.host.parentNode) pane.host.parentNode.removeChild(pane.host);
    pubarPanes.splice(pubarPanes.indexOf(pane), 1);
    if (pubarActiveId === id) pubarActiveId = null;
    pubarSync();
}

/* 会话切换：清空分组页签的动态内容（外部页签由注册方自行重置），再统一重算显隐。 */
function pubarResetForSession() {
    pubarSuppressAutoSwitchUntil = Date.now() + PUBAR_SESSION_SWITCH_SUPPRESS_MS;
    pubarAutoSwitchTarget = null;
    pubarCloseNarrowPopover();
    pubarPanes.forEach(function (pane) {
        if (pane.owner === 'external') return;
        if (typeof pane.host.replaceChildren === 'function') pane.host.replaceChildren();
        else pane.host.textContent = '';
        pane.count = 0;
        pane.lastCount = 0;
        pane.wasVisible = false;
    });
    pubarSync();
}

function pubarOnTabsKeydown(event) {
    var key = event && event.key;
    if (!key) return;
    /* 键盘遍历必须与页签条显示顺序一致（按 order 排序，而非注册顺序） */
    var visible = pubarPanes.slice().sort(function (a, b) { return a.order - b.order; })
        .filter(function (pane) { return pane.visible; });
    if (visible.length < 2) return;
    var currentIndex = -1;
    for (var i = 0; i < visible.length; i += 1) {
        if (visible[i].id === pubarActiveId) currentIndex = i;
    }
    var nextIndex = null;
    if (key === 'ArrowLeft' || key === 'ArrowUp') nextIndex = currentIndex <= 0 ? visible.length - 1 : currentIndex - 1;
    else if (key === 'ArrowRight' || key === 'ArrowDown') nextIndex = currentIndex < 0 || currentIndex >= visible.length - 1 ? 0 : currentIndex + 1;
    else if (key === 'Home') nextIndex = 0;
    else if (key === 'End') nextIndex = visible.length - 1;
    if (nextIndex == null) return;
    event.preventDefault();
    pubarAutoSwitchTarget = null;
    pubarActivate(visible[nextIndex].id);
    if (typeof visible[nextIndex].tab.focus === 'function') visible[nextIndex].tab.focus();
}

function initPublicSidebar() {
    if (pubarInitialized) return true;
    if (typeof document === 'undefined') return false;
    var root = document.getElementById(PUBAR_ROOT_ID);
    if (!root) return false;
    var tabs = root.querySelector('.pubar-tabs');
    var panes = root.querySelector('.pubar-panes');
    if (!tabs || !panes) return false;
    pubarRootEl = root;
    pubarTabsEl = tabs;
    pubarPanesEl = panes;
    pubarNarrowStripEl = document.getElementById('pubar-narrow-strip');
    pubarNarrowPopoverEl = document.getElementById('pubar-narrow-popover');
    pubarNarrowTitleEl = pubarNarrowPopoverEl ? pubarNarrowPopoverEl.querySelector('.pnp-title') : null;
    pubarNarrowBodyEl = pubarNarrowPopoverEl ? pubarNarrowPopoverEl.querySelector('.pnp-body') : null;
    if (pubarNarrowPopoverEl) {
        var narrowCloseBtn = pubarNarrowPopoverEl.querySelector('.pnp-close');
        if (narrowCloseBtn) {
            if (typeof setUiHoverTip === 'function') setUiHoverTip(narrowCloseBtn, narrowCloseBtn.getAttribute('aria-label') || '关闭');
            narrowCloseBtn.addEventListener('click', function () { pubarCloseNarrowPopover(); });
        }
    }
    document.addEventListener('mousedown', function (event) {
        if (!pubarNarrowOpenId) return;
        var target = event && event.target;
        if (pubarNarrowPopoverEl && target && pubarNarrowPopoverEl.contains(target)) return;
        if (pubarNarrowStripEl && target && pubarNarrowStripEl.contains(target)) return;
        pubarCloseNarrowPopover();
    }, true);
    document.addEventListener('keydown', function (event) {
        if (event && event.key === 'Escape' && pubarNarrowOpenId) pubarCloseNarrowPopover();
    });
    if (typeof MutationObserver === 'function') {
        pubarNarrowClassObserver = new MutationObserver(function () {
            if (root.classList.contains('is-open')) pubarCloseNarrowPopover();
            pubarRenderNarrowStrip();
        });
        pubarNarrowClassObserver.observe(root, { attributes: true, attributeFilter: ['class'] });
    }
    tabs.addEventListener('keydown', pubarOnTabsKeydown);
    document.addEventListener('myagent:plugin-session-ui-rendered', function () { pubarSync(); });
    pubarInitialized = true;
    if (typeof globalThis !== 'undefined') {
        globalThis.MyAgentPubar = {
            ready: true,
            paneHostFor: pubarPaneHostFor,
            registerPane: pubarRegisterPane,
            removePane: pubarRemovePane,
            hasContent: pubarHasContent,
            activate: pubarActivate,
            getActive: pubarGetActiveId,
            notifyActivity: pubarNotifyActivity,
            sync: pubarSync,
            resetForSession: pubarResetForSession,
            configureNarrow: pubarConfigureNarrow,
            updateNarrowChip: pubarUpdateNarrowChip,
            closeNarrow: pubarCloseNarrowPopover,
        };
    }
    document.dispatchEvent(new CustomEvent('myagent:public-sidebar-ready'));
    if (typeof requestAnimationFrame === 'function') {
        requestAnimationFrame(function () { pubarSync(); });
    } else {
        pubarSync();
    }
    return true;
}

if (typeof document !== 'undefined') {
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initPublicSidebar);
    } else {
        initPublicSidebar();
    }
}
