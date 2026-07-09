let skillPickerCache = null;
let skillPickerRefreshPromise = null;
let selectedSkillNames = [];
const LS_SKILL_DRAFT_PREFIX = 'myagent-skill-draft:';

function skillPickerEls() {
    return {
        row: document.querySelector('.composer-row'),
        button: document.getElementById('skill-picker-btn'),
        popover: document.getElementById('skill-picker-popover'),
    };
}

function skillPickerEscape(str) {
    return String(str == null ? '' : str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function selectedSkillSet() {
    var out = {};
    selectedSkillNames.forEach(function (name) { out[String(name)] = true; });
    return out;
}

function skillDraftStorageKey(sessionId) {
    return LS_SKILL_DRAFT_PREFIX + String(sessionId || '');
}

function persistSkillPickerDraft(sessionId) {
    if (!sessionId) return;
    try {
        var key = skillDraftStorageKey(sessionId);
        if (selectedSkillNames.length) localStorage.setItem(key, JSON.stringify(selectedSkillNames));
        else localStorage.removeItem(key);
    } catch (e) { /* ignore */ }
}

function readStoredSkillPickerDraft(sessionId) {
    if (!sessionId) return [];
    try {
        var raw = localStorage.getItem(skillDraftStorageKey(sessionId));
        var parsed = raw ? JSON.parse(raw) : [];
        if (!Array.isArray(parsed)) return [];
        return parsed.map(function (item) { return String(item || '').trim(); }).filter(Boolean);
    } catch (e) {
        return [];
    }
}

function removeStoredSkillPickerDraft(sessionId) {
    if (!sessionId) return;
    try { localStorage.removeItem(skillDraftStorageKey(sessionId)); } catch (e) { /* ignore */ }
}

function syncSkillPickerButton() {
    var e = skillPickerEls();
    if (!e.button) return;
    var count = selectedSkillNames.length;
    e.button.classList.toggle('is-active', count > 0);
    e.button.textContent = count > 0 ? ('SKILL ' + count) : 'SKILL';
    e.button.setAttribute('data-ui-tip', count > 0 ? ('已选择 ' + count + ' 个 Skill') : '选择 Skill');
}

function closeSkillPicker() {
    var e = skillPickerEls();
    if (e.popover) e.popover.classList.remove('is-open');
    if (e.button) e.button.setAttribute('aria-expanded', 'false');
}

function openSkillPicker() {
    var e = skillPickerEls();
    if (!e.popover || !e.button) return;
    constrainSkillPickerToTitlebar();
    e.popover.classList.add('is-open');
    e.button.setAttribute('aria-expanded', 'true');
}

function constrainSkillPickerToTitlebar() {
    var e = skillPickerEls();
    if (!e.popover || !e.row) return;
    var titlebar = document.querySelector('.titlebar');
    var titlebarBottom = titlebar ? titlebar.getBoundingClientRect().bottom : 44;
    var rowTop = e.row.getBoundingClientRect().top;
    var available = Math.max(1, Math.floor(rowTop - titlebarBottom - 10));
    var rootSize = parseFloat(getComputedStyle(document.documentElement).fontSize || '16') || 16;
    var cap = Math.floor(44 * rootSize);
    e.popover.style.setProperty('--composer-popover-max-height', Math.min(cap, available) + 'px');
}

function renderSkillPickerLoading() {
    var e = skillPickerEls();
    if (!e.popover) return;
    e.popover.innerHTML = '<div class="skill-picker-empty">正在加载 Skill</div>';
}

function renderSkillPickerError(err) {
    var e = skillPickerEls();
    if (!e.popover) return;
    e.popover.innerHTML = '<div class="skill-picker-empty">Skill 加载失败：' + skillPickerEscape(err && err.message ? err.message : err) + '</div>';
}

function renderSkillPicker() {
    var e = skillPickerEls();
    if (!e.popover) return;
    var skills = (skillPickerCache && skillPickerCache.skills) || [];
    if (!skills.length) {
        e.popover.innerHTML = '<div class="skill-picker-empty">当前没有已注册 Skill</div>';
        return;
    }
    var active = selectedSkillSet();
    var selectedCount = selectedSkillNames.length;
    var html = '<div class="skill-picker-head">'
        + '<div class="skill-picker-title">选择 Skill <span class="skill-picker-total">已选 ' + skillPickerEscape(selectedCount) + ' / 共 ' + skillPickerEscape(skills.length) + '</span></div>'
        + '<button type="button" class="skill-picker-clear">清空</button>'
        + '</div>'
        + '<div class="skill-picker-list">';
    skills.forEach(function (skill) {
        var name = String(skill && skill.name || '');
        var checked = active[name] ? ' checked' : '';
        html += '<label class="skill-picker-option">'
            + '<input type="checkbox" value="' + skillPickerEscape(name) + '"' + checked + '>'
            + '<span class="skill-picker-option-body">'
            + '<span class="skill-picker-option-name">' + skillPickerEscape(name) + '</span>'
            + '<span class="skill-picker-option-desc">' + skillPickerEscape(skill && skill.description || '') + '</span>'
            + '</span>'
            + '</label>';
    });
    html += '</div>';
    e.popover.innerHTML = html;
    e.popover.querySelectorAll('input[type="checkbox"]').forEach(function (checkbox) {
        checkbox.addEventListener('change', function () {
            var name = String(checkbox.value || '');
            var set = selectedSkillSet();
            if (checkbox.checked) set[name] = true;
            else delete set[name];
            selectedSkillNames = Object.keys(set).filter(Boolean);
            persistSkillPickerDraft(currentSessionId);
            syncSkillPickerButton();
            renderSkillPicker();
        });
    });
    var clear = e.popover.querySelector('.skill-picker-clear');
    if (clear) {
        clear.addEventListener('click', function () {
            selectedSkillNames = [];
            persistSkillPickerDraft(currentSessionId);
            syncSkillPickerButton();
            renderSkillPicker();
        });
    }
}

async function loadSkillPickerSkills() {
    const response = await fetch('/api/skills', { credentials: 'same-origin' });
    const data = await response.json();
    if (!data || !data.ok) throw new Error((data && data.error) || 'Skill 加载失败');
    skillPickerCache = data;
    return data;
}

function refreshSkillPickerSkills() {
    if (skillPickerRefreshPromise) return skillPickerRefreshPromise;
    skillPickerRefreshPromise = loadSkillPickerSkills()
        .then(function () { renderSkillPicker(); })
        .catch(function (err) { renderSkillPickerError(err); })
        .finally(function () { skillPickerRefreshPromise = null; });
    return skillPickerRefreshPromise;
}

function consumeSelectedSkillsForSend() {
    var out = selectedSkillNames.slice();
    selectedSkillNames = [];
    removeStoredSkillPickerDraft(currentSessionId);
    syncSkillPickerButton();
    closeSkillPicker();
    if (skillPickerCache) renderSkillPicker();
    return out;
}

function setSelectedSkillsForCurrentSession(skills) {
    selectedSkillNames = Array.isArray(skills)
        ? skills.map(function (item) { return String(item || '').trim(); }).filter(Boolean)
        : [];
    persistSkillPickerDraft(currentSessionId);
    syncSkillPickerButton();
    if (skillPickerCache) renderSkillPicker();
}

function stashSkillPickerDraft(sessionId) {
    persistSkillPickerDraft(sessionId);
}

function restoreSkillPickerDraft(sessionId) {
    selectedSkillNames = readStoredSkillPickerDraft(sessionId);
    syncSkillPickerButton();
    closeSkillPicker();
    if (skillPickerCache) renderSkillPicker();
}

function initSkillPicker() {
    var e = skillPickerEls();
    if (!e.button || !e.popover) return;
    syncSkillPickerButton();
    e.button.addEventListener('click', function (ev) {
        ev.preventDefault();
        ev.stopPropagation();
        var willOpen = !e.popover.classList.contains('is-open');
        if (!willOpen) {
            closeSkillPicker();
            return;
        }
        if (skillPickerCache) renderSkillPicker();
        else renderSkillPickerLoading();
        openSkillPicker();
        refreshSkillPickerSkills();
    });
    document.addEventListener('click', function (ev) {
        var fresh = skillPickerEls();
        if (!fresh.row || !fresh.row.contains(ev.target)) closeSkillPicker();
    });
    document.addEventListener('keydown', function (ev) {
        if (ev.key === 'Escape') closeSkillPicker();
    });
    window.addEventListener('resize', function () {
        var fresh = skillPickerEls();
        if (fresh.popover && fresh.popover.classList.contains('is-open')) constrainSkillPickerToTitlebar();
    });
}

initSkillPicker();
window.consumeSelectedSkillsForSend = consumeSelectedSkillsForSend;
window.setSelectedSkillsForCurrentSession = setSelectedSkillsForCurrentSession;
window.refreshSkillPickerSkills = refreshSkillPickerSkills;
window.stashSkillPickerDraft = stashSkillPickerDraft;
window.restoreSkillPickerDraft = restoreSkillPickerDraft;
