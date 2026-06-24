let modelProfilesCache = null;
let modelProfileBusy = false;
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

function closeModelMenu() {
    var e = els();
    if (e.menu) e.menu.classList.remove('is-open');
    if (e.trigger) {
        e.trigger.classList.remove('is-open');
        e.trigger.setAttribute('aria-expanded', 'false');
    }
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
        html += '<button type="button" class="composer-model-option" disabled><span class="composer-model-option-meta">暂无已保存模型配置，可到高级设置中保存</span></button>';
    }
    e.menu.innerHTML = html;
    e.menu.querySelectorAll('[data-profile-id]').forEach((btn) => {
        btn.addEventListener('click', () => {
            setCurrentSessionModelProfile(btn.getAttribute('data-profile-id') || '__env__');
            closeModelMenu();
        });
    });
}

async function refreshModelProfileSelector(sessionId, opts) {
    var sid = sessionId || currentSessionId;
    var e = els();
    opts = opts || {};
    if (!e.control) return;
    if (!opts.silent && e.current) e.current.textContent = '正在加载模型配置';
    try {
        await loadModelProfilesForSwitcher();
        activeModelProfileId = modelProfilesCache.new_session_default_profile_id || '__env__';
        if (sid) {
            var r = await fetch('/sessions/' + encodeURIComponent(sid) + '/model_profile', { credentials: 'same-origin' });
            var j = await r.json();
            if (j && j.ok && j.profile_id) activeModelProfileId = j.profile_id;
        }
        renderModelProfileControl();
    } catch (err) {
        if (e.current) e.current.textContent = '模型配置加载失败';
        if (e.menu) e.menu.innerHTML = '<button type="button" class="composer-model-option" disabled><span class="composer-model-option-name">模型配置加载失败</span><span class="composer-model-option-meta">' + h(err.message || err) + '</span></button>';
    }
}

async function setCurrentSessionModelProfile(profileId) {
    if (!currentSessionId || modelProfileBusy) return;
    modelProfileBusy = true;
    try {
        var response = await fetch('/sessions/' + encodeURIComponent(currentSessionId) + '/model_profile', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin',
            body: JSON.stringify({ profile_id: profileId || '__env__' }),
        });
        var data = await response.json();
        if (!data || !data.ok) throw new Error((data && data.error) || '切换失败');
        activeModelProfileId = profileId || '__env__';
        renderModelProfileControl();
        scheduleContextTokensAfterPaint(currentSessionId);
    } catch (err) {
        appendLogVisible('模型配置切换失败: ' + String(err.message || err), 'error-log');
        await refreshModelProfileSelector(currentSessionId);
    } finally {
        modelProfileBusy = false;
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
        await refreshModelProfileSelector(currentSessionId, { silent: true });
        e.menu.classList.add('is-open');
        e.trigger.classList.add('is-open');
        e.trigger.setAttribute('aria-expanded', 'true');
    });
    document.addEventListener('click', (ev) => {
        if (!e.control.contains(ev.target)) closeModelMenu();
    });
    document.addEventListener('keydown', (ev) => {
        if (ev.key === 'Escape') closeModelMenu();
    });
    refreshModelProfileSelector(currentSessionId);
}

initModelProfileSwitcher();
window.refreshModelProfileSelector = refreshModelProfileSelector;
window.loadModelProfilesForSwitcher = loadModelProfilesForSwitcher;
