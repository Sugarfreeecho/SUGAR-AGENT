// ═══════════════════════════════════════════════════════════
// General Agent · 智能会话 — 完整逻辑
// ═══════════════════════════════════════════════════════════

const chatContainer = document.getElementById('chat-container');
const messageInput = document.getElementById('message-input');
const sendBtn = document.getElementById('send-btn');
const pickPathBtn = document.getElementById('pick-path-btn');
if (window.MyAgentPathPicker && pickPathBtn && messageInput) {
    MyAgentPathPicker.attachChatPicker(pickPathBtn, messageInput);
}
if (messageInput) {
    messageInput.addEventListener('myagent:file-upload-state', function () {
        if (typeof setSendButtonState === 'function') setSendButtonState();
    });
    messageInput.addEventListener('myagent:file-paste-error', function (event) {
        const detail = event && event.detail ? event.detail : {};
        if (typeof showUiAlert === 'function') {
            showUiAlert({
                title: '文件上传失败',
                message: String(detail.message || '无法上传所选文件或剪贴板中的图片。'),
                variant: 'error',
            });
        }
    });
}
const sessionsList = document.getElementById('sessions-list');
const newSessionBtn = document.getElementById('new-session-btn');
const offscreenRoot = document.getElementById('session-offscreen-buffers');

const LS_UI_FONT = 'myagent-font-level';
const LS_UI_THEME = 'myagent-theme';
const LS_SESSION_LIST_MODE = 'myagent-session-list-mode';
/** 三档字号（rem 基准）：相对此前整体收紧一档（原大→现中、原中→现小） */
/** 三档 root 字号(px)：在「降一档」基准上整体 ×1.2 */
const UI_FONT_PX = [14, 16, 17];
var settingsModalKeyHandler = null;
var agentTeamFeatureSaving = false;
var askUserFeatureSaving = false;

function setAgentTeamFeatureUi(enabled, options) {
    options = options || {};
    var off = document.getElementById('settings-agent-team-off');
    var on = document.getElementById('settings-agent-team-on');
    var status = document.getElementById('settings-agent-team-status');
    var manage = document.getElementById('settings-agent-team-manage');
    var known = typeof enabled === 'boolean';
    if (off) {
        off.classList.toggle('is-active', known && !enabled);
        off.disabled = !!options.busy;
    }
    if (on) {
        on.classList.toggle('is-active', known && enabled);
        on.disabled = !!options.busy;
    }
    if (status) {
        status.classList.toggle('is-error', !!options.error);
        if (options.message) status.textContent = options.message;
        else if (options.busy) status.textContent = '正在保存…';
        else if (enabled) status.textContent = '已启用；Agent Team 入口和团队运行时可用。';
        else if (known) status.textContent = '已关闭；现有 task/subagent 行为不受影响。';
        else status.textContent = '正在读取状态…';
    }
    if (manage) manage.disabled = !known || !enabled || !!options.busy;
}

async function refreshAgentTeamFeature() {
    setAgentTeamFeatureUi(null, { busy: agentTeamFeatureSaving });
    try {
        var response = await fetch('/api/features/agent-team', { cache: 'no-store' });
        var data = await response.json();
        if (!response.ok || !data || data.ok !== true) {
            throw new Error((data && data.error) || ('HTTP ' + response.status));
        }
        window.__MYAGENT_FEATURES__ = window.__MYAGENT_FEATURES__ || {};
        window.__MYAGENT_FEATURES__.agentTeam = data.enabled === true;
        setAgentTeamFeatureUi(data.enabled === true);
    } catch (error) {
        setAgentTeamFeatureUi(null, {
            error: true,
            message: '读取失败：' + String(error && error.message ? error.message : error),
        });
    }
}

async function saveAgentTeamFeature(enabled) {
    if (agentTeamFeatureSaving) return;
    agentTeamFeatureSaving = true;
    setAgentTeamFeatureUi(enabled, { busy: true });
    try {
        var response = await fetch('/api/features/agent-team', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled: enabled === true }),
        });
        var data = await response.json();
        if (!response.ok || !data || data.ok !== true) {
            throw new Error((data && data.error) || ('HTTP ' + response.status));
        }
        window.__MYAGENT_FEATURES__ = window.__MYAGENT_FEATURES__ || {};
        window.__MYAGENT_FEATURES__.agentTeam = data.enabled === true;
        setAgentTeamFeatureUi(data.enabled === true);
    } catch (error) {
        setAgentTeamFeatureUi(null, {
            error: true,
            message: '保存失败：' + String(error && error.message ? error.message : error),
        });
    } finally {
        agentTeamFeatureSaving = false;
        var off = document.getElementById('settings-agent-team-off');
        var on = document.getElementById('settings-agent-team-on');
        if (off) off.disabled = false;
        if (on) on.disabled = false;
    }
}

function setAskUserFeatureUi(enabled, options) {
    options = options || {};
    var off = document.getElementById('settings-ask-user-off');
    var on = document.getElementById('settings-ask-user-on');
    var status = document.getElementById('settings-ask-user-status');
    var known = typeof enabled === 'boolean';
    if (off) {
        off.classList.toggle('is-active', known && !enabled);
        off.disabled = !!options.busy;
    }
    if (on) {
        on.classList.toggle('is-active', known && enabled);
        on.disabled = !!options.busy;
    }
    if (status) {
        status.classList.toggle('is-error', !!options.error);
        if (options.message) status.textContent = options.message;
        else if (options.busy) status.textContent = '正在保存…';
        else if (enabled) status.textContent = '已启用；Agent 可在确实需要选择时暂停并向你提问。';
        else if (known) status.textContent = '已关闭；Agent 不会创建结构化提问卡片。';
        else status.textContent = '正在读取状态…';
    }
}

async function refreshAskUserFeature() {
    setAskUserFeatureUi(null, { busy: askUserFeatureSaving });
    try {
        var response = await fetch('/api/features/ask-user', { cache: 'no-store' });
        var data = await response.json();
        if (!response.ok || !data || data.ok !== true) throw new Error((data && data.error) || ('HTTP ' + response.status));
        window.__MYAGENT_FEATURES__ = window.__MYAGENT_FEATURES__ || {};
        window.__MYAGENT_FEATURES__.askUser = data.enabled === true;
        setAskUserFeatureUi(data.enabled === true);
    } catch (error) {
        setAskUserFeatureUi(null, { error: true, message: '读取失败：' + String(error && error.message ? error.message : error) });
    }
}

async function saveAskUserFeature(enabled) {
    if (askUserFeatureSaving) return;
    askUserFeatureSaving = true;
    setAskUserFeatureUi(enabled, { busy: true });
    try {
        var response = await fetch('/api/features/ask-user', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled: enabled === true }),
        });
        var data = await response.json();
        if (!response.ok || !data || data.ok !== true) throw new Error((data && data.error) || ('HTTP ' + response.status));
        window.__MYAGENT_FEATURES__ = window.__MYAGENT_FEATURES__ || {};
        window.__MYAGENT_FEATURES__.askUser = data.enabled === true;
        setAskUserFeatureUi(data.enabled === true);
    } catch (error) {
        setAskUserFeatureUi(null, { error: true, message: '保存失败：' + String(error && error.message ? error.message : error) });
    } finally {
        askUserFeatureSaving = false;
    }
}

function getStoredFontLevel() {
    var n = parseInt(localStorage.getItem(LS_UI_FONT), 10);
    if (isNaN(n) || n < 0 || n > 2) return 1;
    return n;
}

function getStoredSessionListMode() {
    var m = localStorage.getItem(LS_SESSION_LIST_MODE);
    return m === 'compact' ? 'compact' : 'detailed';
}

function syncSettingsModalForm() {
    var lvl = getStoredFontLevel();
    for (var i = 0; i < 3; i++) {
        var b = document.getElementById('settings-font-' + i);
        if (b) b.classList.toggle('is-active', i === lvl);
    }
    var light = document.documentElement.classList.contains('theme-light');
    var bd = document.getElementById('settings-theme-dark');
    var bl = document.getElementById('settings-theme-light');
    if (bd) bd.classList.toggle('is-active', !light);
    if (bl) bl.classList.toggle('is-active', light);
    var compact = getStoredSessionListMode() === 'compact';
    var sc = document.getElementById('settings-session-compact');
    var sd = document.getElementById('settings-session-detailed');
    if (sc) sc.classList.toggle('is-active', compact);
    if (sd) sd.classList.toggle('is-active', !compact);
}

function applyFontLevel(level, persist) {
    level = Math.max(0, Math.min(2, level));
    document.documentElement.style.fontSize = UI_FONT_PX[level] + 'px';
    document.documentElement.setAttribute('data-font-level', String(level));
    if (persist) localStorage.setItem(LS_UI_FONT, String(level));
    syncSettingsModalForm();
}

function applyUiTheme(theme, persist) {
    var light = theme === 'light';
    document.documentElement.classList.toggle('theme-light', light);
    if (persist) localStorage.setItem(LS_UI_THEME, light ? 'light' : 'dark');
    syncSettingsModalForm();
}

function applySessionListMode(mode, persist) {
    var next = mode === 'compact' ? 'compact' : 'detailed';
    document.documentElement.setAttribute('data-session-list-mode', next);
    if (persist) localStorage.setItem(LS_SESSION_LIST_MODE, next);
    syncSettingsModalForm();
}

function restoreUiPreferences() {
    applyFontLevel(getStoredFontLevel(), false);
    var t = localStorage.getItem(LS_UI_THEME);
    applyUiTheme(t === 'dark' ? 'dark' : 'light', false);
    applySessionListMode(getStoredSessionListMode(), false);
}
restoreUiPreferences();

function openSettingsModal() {
    var root = document.getElementById('settings-modal-root');
    var panel = root && root.querySelector('.settings-modal');
    if (!root || !panel) return;
    syncSettingsModalForm();
    void refreshAgentTeamFeature();
    void refreshAskUserFeature();
    root.classList.add('is-open');
    root.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
    try { panel.focus(); } catch (e) {}
    settingsModalKeyHandler = function (ev) {
        if (ev.key === 'Escape') { ev.preventDefault(); closeSettingsModal(); }
    };
    document.addEventListener('keydown', settingsModalKeyHandler);
}

function closeSettingsModal() {
    var root = document.getElementById('settings-modal-root');
    if (!root) return;
    root.classList.remove('is-open');
    root.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
    if (settingsModalKeyHandler) {
        document.removeEventListener('keydown', settingsModalKeyHandler);
        settingsModalKeyHandler = null;
    }
}

function initUiSettingsControls() {
    var root = document.getElementById('settings-modal-root');
    var gear = document.getElementById('sidebar-settings-btn');
    var closeBtn = document.getElementById('settings-modal-close');
    if (!root) return;
    if (gear) {
        gear.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            openSettingsModal();
        });
    }
    if (closeBtn) closeBtn.addEventListener('click', function () { closeSettingsModal(); });
    root.addEventListener('click', function (e) {
        if (e.target === root) closeSettingsModal();
    });
    var pan = root.querySelector('.settings-modal');
    if (pan) pan.addEventListener('click', function (e) { e.stopPropagation(); });
    for (var i = 0; i < 3; i++) {
        (function (idx) {
            var b = document.getElementById('settings-font-' + idx);
            if (b) b.addEventListener('click', function () { applyFontLevel(idx, true); });
        })(i);
    }
    var bd = document.getElementById('settings-theme-dark');
    var bl = document.getElementById('settings-theme-light');
    if (bd) bd.addEventListener('click', function () { applyUiTheme('dark', true); });
    if (bl) bl.addEventListener('click', function () { applyUiTheme('light', true); });
    var sc = document.getElementById('settings-session-compact');
    var sd = document.getElementById('settings-session-detailed');
    if (sc) sc.addEventListener('click', function () { applySessionListMode('compact', true); });
    if (sd) sd.addEventListener('click', function () { applySessionListMode('detailed', true); });
    var agentTeamOff = document.getElementById('settings-agent-team-off');
    var agentTeamOn = document.getElementById('settings-agent-team-on');
    if (agentTeamOff) agentTeamOff.addEventListener('click', function () { void saveAgentTeamFeature(false); });
    if (agentTeamOn) agentTeamOn.addEventListener('click', function () { void saveAgentTeamFeature(true); });
    var askUserOff = document.getElementById('settings-ask-user-off');
    var askUserOn = document.getElementById('settings-ask-user-on');
    if (askUserOff) askUserOff.addEventListener('click', function () { void saveAskUserFeature(false); });
    if (askUserOn) askUserOn.addEventListener('click', function () { void saveAskUserFeature(true); });
    var agentTeamManage = document.getElementById('settings-agent-team-manage');
    if (agentTeamManage) agentTeamManage.addEventListener('click', function () {
        closeSettingsModal();
        if (typeof openAgentTeamModal === 'function') void openAgentTeamModal();
    });
    var languageBtn = document.getElementById('sidebar-language-btn');
    if (languageBtn) {
        languageBtn.addEventListener('click', function () {
            applyUiLanguage(uiLanguage === 'en' ? 'zh-CN' : 'en', true);
        });
    }
    var envAdv = document.getElementById('settings-env-advanced');
    if (envAdv) {
        envAdv.addEventListener('click', function () {
            closeSettingsModal();
            var query = new URLSearchParams();
            if (currentSessionId) query.set('session_id', String(currentSessionId));
            if (window.__WORK_DIR__) query.set('workspace', String(window.__WORK_DIR__));
            var settingsUrl = '/setup/env' + (query.toString() ? ('?' + query.toString()) : '');
            var w = window.open(settingsUrl, 'myagent-env');
            if (w) {
                try { w.focus(); } catch (e) {}
            } else {
                window.location.href = settingsUrl;
            }
        });
    }
    var dashboardBtn = document.getElementById('settings-execution-dashboard');
    if (dashboardBtn) dashboardBtn.addEventListener('click', function () {
        closeSettingsModal();
        var w = window.open('/execution-dashboard', 'myagent-execution-dashboard');
        if (w) { try { w.focus(); } catch (e) {} }
        else window.location.href = '/execution-dashboard';
    });
}
initUiSettingsControls();
