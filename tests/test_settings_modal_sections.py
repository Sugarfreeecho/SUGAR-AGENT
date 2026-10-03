from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_redundant_settings_sections_are_removed() -> None:
    for relative_path in ("frontend/index.html", "frontend/src/shell-body.html"):
        markup = (ROOT / relative_path).read_text(encoding="utf-8")
        assert 'id="settings-ask-user-off"' not in markup
        assert 'id="settings-ask-user-on"' not in markup
        assert 'id="settings-ask-user-status"' not in markup
        assert 'id="settings-execution-dashboard"' not in markup


def test_runtime_footer_remains_the_dashboard_entrypoint() -> None:
    markup = (ROOT / "frontend/src/shell-body.html").read_text(encoding="utf-8")

    assert 'id="sidebar-runtime-link"' in markup
    assert 'href="/execution-dashboard"' not in markup
    manifest = (ROOT / "plugins/execution-dashboard/.myagent-plugin/plugin.json").read_text(encoding="utf-8")
    assert '"navigation"' in manifest


def test_gear_entry_opens_the_settings_center_overlay() -> None:
    """左上角齿轮不再弹「界面设置」弹窗，改为应用内浮层打开 /settings。"""
    for relative_path in ("frontend/index.html", "frontend/src/shell-body.html"):
        markup = (ROOT / relative_path).read_text(encoding="utf-8")
        assert 'id="settings-modal-root"' not in markup
        assert 'id="sidebar-settings-btn"' in markup
        assert 'id="settings-center-overlay"' in markup
        assert 'id="settings-center-frame"' in markup
        # 旧的「高级设置」= 额外标签页，已随弹窗移除
        assert 'id="settings-env-advanced"' not in markup
        assert 'window.open(' not in markup

    settings = (ROOT / "frontend/src/app/modules/settings.js").read_text(encoding="utf-8")
    assert "openSettingsCenter" in settings
    assert "settingsCenterUrl" in settings
    assert "'/settings?'" in settings
    assert "embedded" in settings
    assert "myagent:settings-close" in settings
    assert "/setup/env" not in settings
    # 主题/字号/会话列表仍然在聊天页生效（公共函数保留）
    assert "function applyUiTheme(" in settings
    assert "function applyFontLevel(" in settings
    assert "function applySessionListMode(" in settings


def test_settings_center_page_closes_itself_when_embedded() -> None:
    core = (ROOT / "app/templates/static/settings/core.js").read_text(encoding="utf-8")
    css = (ROOT / "app/templates/static/settings/settings.css").read_text(encoding="utf-8")

    assert "const EMBEDDED = !!BOOT.embedded || isFramed();" in core
    assert "window.self !== window.top" in core
    assert "myagent:settings-close" in core
    assert "leaveSettings" in core
    assert ".st-embedded .st-stage { background: transparent; }" in css


def test_settings_center_pushes_prefs_to_host_in_realtime() -> None:
    """设置中心里改主题/字号/会话列表/语言，聊天页当场跟着变（不用关浮层）。"""
    core = (ROOT / "app/templates/static/settings/core.js").read_text(encoding="utf-8")
    sections = (ROOT / "app/templates/static/settings/sections_basic.js").read_text(encoding="utf-8")
    settings = (ROOT / "frontend/src/app/modules/settings.js").read_text(encoding="utf-8")

    # 设置中心：写入共用偏好键的同时回推宿主
    assert "myagent:settings-prefs" in core
    assert "const PREF_KEYS = {" in core
    assert "function setPref(name, value)" in core
    assert "notifyHostPrefs();" in core
    assert "reload, showSection, notifyHostPrefs, setPref," in core
    for pref in ("theme", "list", "lang"):
        assert "A.setPref('%s'" % pref in sections
    # 字号改成 px 之后一次写两个键（px + 旧档位），走 setPrefs 只回推一次
    assert "A.setPrefs({ fontPx: String(next), font: String(levelForPx(next)) });" in sections
    assert "function setPrefs(patch)" in core

    # 宿主聊天页：收到偏好消息立即应用，另有 storage 兜底
    assert "if (data.type === 'myagent:settings-prefs') applyHostPrefs(data.prefs);" in settings
    assert "function applyHostPrefs(prefs)" in settings
    assert "restoreUiPreferences();" in settings
    assert "addEventListener('storage', function (event)" in settings


def test_overlay_iframe_keeps_a_transparent_canvas() -> None:
    """深色/紫色主题下父页面 color-scheme:dark 会被 iframe 继承，
    浏览器随即给 iframe 文档画不透明底色、把聊天页整块盖住（浮层背景变成假的）。
    因此 .settings-center-frame 必须显式 color-scheme: normal。"""
    css = (ROOT / "frontend/src/styles/app.css").read_text(encoding="utf-8")
    start = css.index(".settings-center-frame {")
    block = css[start:css.index("}", start)]

    assert "background: transparent;" in block
    assert "color-scheme: normal;" in block
