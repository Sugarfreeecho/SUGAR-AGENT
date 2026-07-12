let modelProfilesCache = null;
const modelProfilesRefreshPromises = Object.create(null);
const modelProfileBusyBySession = Object.create(null);
const modelProfileIdBySession = Object.create(null);
let modelProfileSelectionEpoch = 0;
let activeModelProfileId = '__env__';

function h(str) {
    return String(str == null ? '' : str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function profileLabel(profile) {
    if (!profile) return '默认方案';
    return String(profile.name || profile.model || '未命名方案');
}

function profileMeta(profile) {
    if (!profile) return '';
    var model = profile.model || '';
    var ctx = profile.context_window ? profile.context_window + ' ctx' : '';
    var out = profile.max_output_tokens ? profile.max_output_tokens + ' out' : '';
    return [model, ctx, out].filter(Boolean).join(' · ');
}

function els() {
    return {
        control: document.getElementById('model-profile-control'),
        trigger: document.getElementById('model-profile-trigger'),
        current: document.getElementById('model-profile-current'),
        menu: document.getElementById('model-profile-menu'),
    };
}

async function loadModelProfilesForSwitcher() {
    const response = await fetch('/api/model_profiles', { credentials: 'same-origin' });
    const data = await response.json();
    if (!data || !data.ok) throw new Error((data && data.error) || '模型配置加载失败');
    modelProfilesCache = data;
    return data;
}

function allProfiles() {
    if (!modelProfilesCache) return [];
    var defaultProfile = modelProfilesCache.default_profile || { id: '__env__', name: '', model: '' };
    var profiles = modelProfilesCache.profiles || [];
    return profiles.length ? profiles : [defaultProfile];
}

function activeProfile() {
    var list = allProfiles();
    for (var i = 0; i < list.length; i += 1) {
        if (String(list[i].id || '__env__') === String(activeModelProfileId || '__env__')) return list[i];
    }
    return list[0] || null;
}

function activeProfileContextWindow() {
    var profile = activeProfile();
    var n = profile && profile.context_window != null ? Number(profile.context_window) : 0;
    return Number.isFinite(n) && n > 0 ? Math.floor(n) : null;
}

function closeModelMenu() {
    var e = els();
    if (e.menu) e.menu.classList.remove('is-open');
    if (e.trigger) {
        e.trigger.classList.remove('is-open');
        e.trigger.setAttribute('aria-expanded', 'false');
    }
}

function openModelMenu() {
    var e = els();
    if (!e.menu || !e.trigger) return;
    constrainModelMenuToTitlebar();
    e.menu.classList.add('is-open');
    e.trigger.classList.add('is-open');
    e.trigger.setAttribute('aria-expanded', 'true');
}

function constrainModelMenuToTitlebar() {
    var e = els();
    if (!e.menu || !e.trigger) return;
    var titlebar = document.querySelector('.titlebar');
    var titlebarBottom = titlebar ? titlebar.getBoundingClientRect().bottom : 44;
    var triggerTop = e.trigger.getBoundingClientRect().top;
    var available = Math.max(1, Math.floor(triggerTop - titlebarBottom - 8));
    var rootSize = parseFloat(getComputedStyle(document.documentElement).fontSize || '16') || 16;
    var cap = Math.floor(44 * rootSize);
    e.menu.style.setProperty('--composer-popover-max-height', Math.min(cap, available) + 'px');
}

function renderModelProfileControl() {
    var e = els();
    if (!e.trigger || !e.current || !e.menu) return;
    var active = activeProfile();
    e.current.textContent = active ? profileLabel(active) : '未加载模型配置';
    e.trigger.removeAttribute('title');
    e.trigger.removeAttribute('data-ui-tip');
    var profiles = allProfiles();
    if (!profiles.length) {
        e.menu.innerHTML = '<button type="button" class="composer-model-option" disabled><span class="composer-model-option-name">没有可用模型配置</span></button>';
        return;
    }
    var html = '';
    for (var i = 0; i < profiles.length; i += 1) {
        var p = profiles[i] || {};
        var id = String(p.id || '__env__');
        var activeCls = id === String(activeModelProfileId || '__env__') ? ' is-active' : '';
        html += '<button type="button" class="composer-model-option' + activeCls + '" role="option" data-profile-id="' + h(id) + '">'
            + '<span class="composer-model-option-name">' + h(profileLabel(p)) + '</span>'
            + '<span class="composer-model-option-meta">' + h(profileMeta(p) || (id === '__env__' ? (p.model || '') : '')) + '</span>'
            + '</button>';
    }
    if (!(modelProfilesCache.profiles || []).length) {
        html += '<button type="button" class="composer-model-option" disabled><span class="composer-model-option-meta">暂无已保存模型配置，可到模型配置页中保存</span></button>';
    }
    e.menu.innerHTML = html;
    e.menu.querySelectorAll('[data-profile-id]').forEach((btn) => {
        btn.addEventListener('click', () => {
            setCurrentSessionModelProfile(btn.getAttribute('data-profile-id') || '__env__');
            closeModelMenu();
        });
    });
}

function renderModelProfileLoadingMenu() {
    var e = els();
    if (!e.menu) return;
    e.menu.innerHTML = '<button type="button" class="composer-model-option" disabled>'
        + '<span class="composer-model-option-name">正在加载模型配置</span>'
        + '<span class="composer-model-option-meta">请稍候</span>'
        + '</button>';
}

async function refreshModelProfileSelector(sessionId, opts) {
    const sid = String(sessionId || currentSessionId || '');
    const requestEpoch = ++modelProfileSelectionEpoch;
    var e = els();
    opts = opts || {};
    if (!e.control) return;
    if (!opts.silent && e.current) e.current.textContent = '正在加载模型配置';
    try {
        await loadModelProfilesForSwitcher();
        var selectedProfileId = modelProfileIdBySession[sid]
            || modelProfilesCache.new_session_default_profile_id
            || '__env__';
        if (sid) {
            var r = await fetch('/sessions/' + encodeURIComponent(sid) + '/model_profile', { credentials: 'same-origin' });
            var j = await r.json();
            if (j && j.ok && j.profile_id) {
                selectedProfileId = String(j.profile_id);
                modelProfileIdBySession[sid] = selectedProfileId;
            }
        }
        if (sid !== String(currentSessionId || '') || requestEpoch !== modelProfileSelectionEpoch) return;
        activeModelProfileId = selectedProfileId;
        renderModelProfileControl();
    } catch (err) {
        if (sid !== String(currentSessionId || '') || requestEpoch !== modelProfileSelectionEpoch) return;
        if (e.current) e.current.textContent = '模型配置加载失败';
        if (e.menu) e.menu.innerHTML = '<button type="button" class="composer-model-option" disabled><span class="composer-model-option-name">模型配置加载失败</span><span class="composer-model-option-meta">' + h(err.message || err) + '</span></button>';
    }
}

function refreshModelProfileSelectorInBackground(sessionId, opts) {
    const sid = String(sessionId || currentSessionId || '');
    const existing = modelProfilesRefreshPromises[sid];
    if (existing && existing.epoch === modelProfileSelectionEpoch) return existing.promise;
    const promise = refreshModelProfileSelector(sid, opts)
        .catch(function (err) {
            console.error('refresh model profiles failed:', err);
        })
        .finally(function () {
            if (modelProfilesRefreshPromises[sid] === entry) {
                delete modelProfilesRefreshPromises[sid];
            }
        });
    const entry = { promise: promise, epoch: modelProfileSelectionEpoch };
    modelProfilesRefreshPromises[sid] = entry;
    return promise;
}

async function setCurrentSessionModelProfile(profileId) {
    const sid = String(currentSessionId || '');
    const selectedProfileId = String(profileId || '__env__');
    if (!sid || modelProfileBusyBySession[sid]) return;
    modelProfileBusyBySession[sid] = true;
    try {
        var response = await fetch('/sessions/' + encodeURIComponent(sid) + '/model_profile', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin',
            body: JSON.stringify({ profile_id: selectedProfileId }),
        });
        var data = await response.json();
        if (!data || !data.ok) throw new Error((data && data.error) || '切换失败');
        modelProfileIdBySession[sid] = selectedProfileId;
        if (sid !== String(currentSessionId || '')) return;
        modelProfileSelectionEpoch += 1;
        activeModelProfileId = selectedProfileId;
        renderModelProfileControl();
        var cachedTokens = selectContextTokens(sid);
        var nextThreshold = activeProfileContextWindow();
        if (cachedTokens && cachedTokens.estimated != null) {
            recordContextTokens(
                sid,
                cachedTokens.estimated,
                nextThreshold != null ? nextThreshold : cachedTokens.threshold
            );
        } else {
            scheduleContextTokensAfterPaint(sid);
        }
    } catch (err) {
        if (sid === String(currentSessionId || '')) {
            appendLogVisible('模型配置切换失败: ' + String(err.message || err), 'error-log');
            await refreshModelProfileSelector(sid);
        }
    } finally {
        delete modelProfileBusyBySession[sid];
    }
}

function initModelProfileSwitcher() {
    var e = els();
    if (!e.control || !e.trigger || !e.menu) return;
    e.trigger.addEventListener('click', async () => {
        var willOpen = !e.menu.classList.contains('is-open');
        if (!willOpen) {
            closeModelMenu();
            return;
        }
        if (modelProfilesCache) renderModelProfileControl();
        else renderModelProfileLoadingMenu();
        openModelMenu();
        refreshModelProfileSelectorInBackground(currentSessionId, { silent: true });
    });
    document.addEventListener('click', (ev) => {
        if (!e.control.contains(ev.target)) closeModelMenu();
    });
    document.addEventListener('keydown', (ev) => {
        if (ev.key === 'Escape') closeModelMenu();
    });
    window.addEventListener('resize', () => {
        var fresh = els();
        if (fresh.menu && fresh.menu.classList.contains('is-open')) constrainModelMenuToTitlebar();
    });
    refreshModelProfileSelectorInBackground(currentSessionId);
}

initModelProfileSwitcher();
window.refreshModelProfileSelector = refreshModelProfileSelector;
window.loadModelProfilesForSwitcher = loadModelProfilesForSwitcher;
