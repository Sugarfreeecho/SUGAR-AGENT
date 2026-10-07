// ═══════════════════════════════════════════════════════════
// SugarAgent · 智能会话 — 完整逻辑
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
const LS_UI_FONT_SIZE = 'myagent-font-size-px';
const LS_UI_THEME = 'myagent-theme';
const LS_SESSION_LIST_MODE = 'myagent-session-list-mode';
/** 三档字号（rem 基准）：相对此前整体收紧一档（原大→现中、原中→现小） */
/** 三档 root 字号(px)：在「降一档」基准上整体 ×1.2 */
const UI_FONT_PX = [14, 16, 17];
/** 可输入字号（学 DSH 的整数 px 步进，那边 12–17；这里按现有观感把上限放到 20） */
const UI_FONT_MIN = 12;
const UI_FONT_MAX = 20;
function clampFontPx(px) {
    return Math.max(UI_FONT_MIN, Math.min(UI_FONT_MAX, Math.round(px)));
}
function levelForFontPx(px) {
    var hit = UI_FONT_PX.indexOf(px);
    if (hit >= 0) return hit;
    return px <= 15 ? 0 : (px <= 16 ? 1 : 2);
}
function getStoredFontLevel() {
    var n = parseInt(localStorage.getItem(LS_UI_FONT), 10);
    if (isNaN(n) || n < 0 || n > 2) return 1;
    return n;
}
/** 字号以 px 键为准，缺省回落到旧三档（0/1/2 → 14/16/17） */
function getStoredFontPx() {
    var raw = parseInt(localStorage.getItem(LS_UI_FONT_SIZE), 10);
    if (!isNaN(raw)) return clampFontPx(raw);
    return UI_FONT_PX[getStoredFontLevel()];
}

function getStoredSessionListMode() {
    var m = localStorage.getItem(LS_SESSION_LIST_MODE);
    return m === 'compact' ? 'compact' : 'detailed';
}

function getUiThemeCanvasBackground() {
    return getComputedStyle(document.documentElement).getPropertyValue('--export-bg').trim() || '#ffffff';
}


function applyFontSize(px, persist) {
    var next = clampFontPx(px);
    document.documentElement.style.fontSize = next + 'px';
    document.documentElement.setAttribute('data-font-size', String(next));
    document.documentElement.setAttribute('data-font-level', String(levelForFontPx(next)));
    if (persist) {
        localStorage.setItem(LS_UI_FONT_SIZE, String(next));
        localStorage.setItem(LS_UI_FONT, String(levelForFontPx(next)));   /* 旧档位键同步，别让别的读者读到过期值 */
    }
    return next;
}

function applyUiTheme(theme, persist) {
    var next = theme === 'dark' || theme === 'purple' ? theme : 'light';
    document.documentElement.classList.remove('theme-light', 'theme-dark', 'theme-purple');
    document.documentElement.classList.add('theme-' + next);
    document.documentElement.setAttribute('data-theme', next);
    if (persist) localStorage.setItem(LS_UI_THEME, next === 'dark' ? 'deep-dark' : next);
}

function applySessionListMode(mode, persist) {
    var next = mode === 'compact' ? 'compact' : 'detailed';
    document.documentElement.setAttribute('data-session-list-mode', next);
    if (persist) localStorage.setItem(LS_SESSION_LIST_MODE, next);
    // 视图选项菜单里的同名项对勾要保持一致。
    if (typeof syncSessionViewMenu === 'function') syncSessionViewMenu();
}

/**
 * 会话目录的二级分组方式：时间 / 工作目录。
 * 取值与持久化在 state/session-selectors.js（getSessionGroupBy / setSessionGroupBy），
 * 侧栏与设置面板的按钮共用同一状态（都带 data-session-group-by）。
 */
function syncSessionGroupControls(mode) {
    var current = mode || ((typeof getSessionGroupBy === 'function') ? getSessionGroupBy() : 'time');
    document.querySelectorAll('[data-session-group-by]').forEach(function (btn) {
        var active = String(btn.getAttribute('data-session-group-by') || '') === current;
        btn.classList.toggle('is-active', active);
        btn.setAttribute('aria-pressed', active ? 'true' : 'false');
    });
}

function applySessionGroupBy(mode, persist) {
    var next = mode === 'workdir' ? 'workdir' : 'time';
    if (persist && typeof setSessionGroupBy === 'function') setSessionGroupBy(next);
    syncSessionGroupControls(next);
    if (typeof syncSessionViewMenu === 'function') syncSessionViewMenu();
    // 分组方式已进渲染键（布局键），这里仍强制重绘一次，切换立即生效。
    if (typeof renderSessionListIfChanged === 'function') renderSessionListIfChanged(true);
}

function restoreUiPreferences() {
    applyFontSize(getStoredFontPx(), false);
    var t = localStorage.getItem(LS_UI_THEME);
    if (t === 'deep-dark') applyUiTheme('dark', false);
    else if (t === 'dark' || t === 'purple') applyUiTheme('purple', false);
    else applyUiTheme('light', false);
    applySessionListMode(getStoredSessionListMode(), false);
    syncSessionGroupControls();
}
restoreUiPreferences();

// ═══════════════════════════════════════════════════════════
// 设置中心浮层（替代旧的「界面设置」弹窗）
//   齿轮 → 应用内浮层打开 /settings（iframe，聊天状态不丢）
//   关闭：ESC / 点遮罩 / 浮层内点「返回聊天」（postMessage）
// ═══════════════════════════════════════════════════════════
function settingsCenterUrl(section) {
    var query = new URLSearchParams();
    query.set('embedded', '1');
    if (typeof currentSessionId !== 'undefined' && currentSessionId) query.set('session_id', String(currentSessionId));
    if (window.__WORK_DIR__) query.set('workspace', String(window.__WORK_DIR__));
    var hash = section ? ('#' + String(section)) : '';
    return '/settings?' + query.toString() + hash;
}

function openSettingsCenter(section) {
    var overlay = document.getElementById('settings-center-overlay');
    var frame = document.getElementById('settings-center-frame');
    if (!overlay || !frame) return;
    if (window.__settingsCenterReady === true) {
        mountSettingsCenter(section);
        return;
    }
    /* 首次点击先探活：进程还没挂 /settings 路由时给出重启提示，避免空白浮层 */
    fetch('/settings', { method: 'GET', credentials: 'same-origin', cache: 'no-store' })
        .then(function (res) {
            /* 该服务不允许 HEAD，405 也算路由存在 */
            if (!res.ok && res.status !== 405) throw new Error('settings center unavailable');
            window.__settingsCenterReady = true;
            mountSettingsCenter(section);
        })
        .catch(function () {
            window.__settingsCenterReady = false;
            if (typeof showUiAlert === 'function') {
                showUiAlert({
                    title: '设置中心',
                    message: '设置中心需要重启 Agent 后可用：请用托盘菜单「重启」，然后重新打开本页。',
                    variant: 'error',
                });
            }
        });
}

function mountSettingsCenter(section) {
    var overlay = document.getElementById('settings-center-overlay');
    var frame = document.getElementById('settings-center-frame');
    if (!overlay || !frame) return;
    frame.src = settingsCenterUrl(section);
    overlay.hidden = false;
    overlay.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
    window.__settingsCenterOpen = true;
    try { if (!window.__settingsCenterKeyHandler) {
        window.__settingsCenterKeyHandler = function (ev) {
            if (ev.key === 'Escape' && window.__settingsCenterOpen) {
                ev.preventDefault();
                closeSettingsCenter();
            }
        };
        document.addEventListener('keydown', window.__settingsCenterKeyHandler);
    } } catch (e) {}
}

function closeSettingsCenter() {
    var frame = document.getElementById('settings-center-frame');
    var settings = frame && frame.contentWindow && frame.contentWindow.MyAgentSettings;
    if (settings && typeof settings.requestClose === 'function') {
        settings.requestClose();
        return;
    }
    finishClosingSettingsCenter();
}

function finishClosingSettingsCenter() {
    var overlay = document.getElementById('settings-center-overlay');
    var frame = document.getElementById('settings-center-frame');
    if (!overlay) return;
    overlay.hidden = true;
    overlay.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
    window.__settingsCenterOpen = false;
    if (frame) frame.src = 'about:blank';
    if (window.__settingsCenterKeyHandler) {
        document.removeEventListener('keydown', window.__settingsCenterKeyHandler);
        window.__settingsCenterKeyHandler = null;
    }
    /* 回到聊天页时按最新的主题/字号/会话列表偏好重绘一次 */
    try { restoreUiPreferences(); } catch (e) {}
    try { document.dispatchEvent(new CustomEvent('myagent:settings-closed')); } catch (e) {}
}

window.addEventListener('message', function (event) {
    if (event.origin !== window.location.origin) return;
    var frame = document.getElementById('settings-center-frame');
    if (!frame || event.source !== frame.contentWindow) return;
    var data = event.data || {};
    if (data.type === 'myagent:settings-close') { finishClosingSettingsCenter(); return; }
    /* 设置中心里改主题/字号/会话列表/语言 → 聊天页当场跟着变（浮层不用关） */
    if (data.type === 'myagent:settings-prefs') applyHostPrefs(data.prefs);
});

function applyHostPrefs(prefs) {
    if (prefs && Object.prototype.hasOwnProperty.call(prefs, 'permissionMode') && typeof setNewSessionPermissionMode === 'function') {
        setNewSessionPermissionMode(prefs.permissionMode);
        if (!currentSessionId && typeof refreshPermissionModeSelector === 'function') refreshPermissionModeSelector('');
    }
    try { restoreUiPreferences(); } catch (e) { /* ignore */ }
    /* 「会话分组」是列表渲染输入：设置中心改分组时同步对勾并立即重绘（与侧栏视图菜单共用同一状态键）。 */
    if (prefs && Object.prototype.hasOwnProperty.call(prefs, 'groupby') && typeof syncSessionGroupControls === 'function') {
        syncSessionGroupControls();
        if (typeof renderSessionListIfChanged === 'function') renderSessionListIfChanged(true);
    }
    var lang = prefs && prefs.lang;
    if (lang && typeof applyUiLanguage === 'function') {
        var next = lang === 'en' ? 'en' : 'zh-CN';
        if (typeof uiLanguage === 'undefined' || uiLanguage !== next) applyUiLanguage(next, false);
    }
}

/* 兜底：别的窗口/标签页写了同一批偏好键时也跟随（storage 事件不会回传给写入方自己） */
window.addEventListener('storage', function (event) {
    var key = event && event.key;
    if (!key) return;
    if (key === LS_UI_THEME || key === LS_UI_FONT || key === LS_SESSION_LIST_MODE) {
        try { restoreUiPreferences(); } catch (e) { /* ignore */ }
    } else if (key === 'myagent-session-group-by') {
        try {
            if (typeof syncSessionGroupControls === 'function') syncSessionGroupControls();
            if (typeof renderSessionListIfChanged === 'function') renderSessionListIfChanged(true);
        } catch (e) { /* ignore */ }
    } else if (key === 'myagent-new-session-permission-mode' && typeof setNewSessionPermissionMode === 'function') {
        setNewSessionPermissionMode(event.newValue || '');
        if (!currentSessionId && typeof refreshPermissionModeSelector === 'function') refreshPermissionModeSelector('');
    } else if (key === 'myagent-language' && typeof applyUiLanguage === 'function') {
        var next = event.newValue === 'en' ? 'en' : 'zh-CN';
        if (typeof uiLanguage === 'undefined' || uiLanguage !== next) applyUiLanguage(next, false);
    }
});

function initUiSettingsControls() {
    var gear = document.getElementById('sidebar-settings-btn');
    var overlay = document.getElementById('settings-center-overlay');
    if (gear) {
        gear.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            openSettingsCenter();
        });
    }
    if (overlay) {
        overlay.addEventListener('click', function (e) {
            if (e.target === overlay) closeSettingsCenter();
        });
    }
    var languageBtn = document.getElementById('sidebar-language-btn');
    if (languageBtn) {
        languageBtn.addEventListener('click', function () {
            applyUiLanguage(uiLanguage === 'en' ? 'zh-CN' : 'en', true);
        });
    }
}
initUiSettingsControls();

/* 其它入口（插件卡片、命令行入口等）可调用 window.myagentOpenSettings('mcp') */
window.myagentOpenSettings = openSettingsCenter;
window.myagentCloseSettings = closeSettingsCenter;
