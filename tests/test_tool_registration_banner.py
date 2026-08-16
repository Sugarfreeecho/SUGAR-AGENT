from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _function_block(source: str, start: str, end: str) -> str:
    return source[source.index(start) : source.index(end, source.index(start))]


def test_mcp_registration_failures_use_the_global_warning_banner() -> None:
    picker = (ROOT / "frontend/src/app/modules/skill-picker.js").read_text(encoding="utf-8")
    registration = _function_block(
        picker,
        "async function registerMcpServer",
        "function refreshSkillPickerSkills",
    )

    assert registration.count("showGlobalWarningBanner(") == 2
    assert "MCP 注册未完成：" in registration
    assert "MCP 注册失败：" in registration
    assert "appendLogVisible(" not in registration


def test_registration_banner_reuses_the_full_access_banner_surface() -> None:
    permissions = (ROOT / "frontend/src/app/modules/permissions.js").read_text(encoding="utf-8")
    styles = (ROOT / "frontend/src/styles/app.css").read_text(encoding="utf-8")

    assert "function showGlobalWarningBanner(message, options)" in permissions
    assert "notice.className = 'permission-global-warning-toast';" in permissions
    assert "notice.setAttribute('role', 'alert');" in permissions
    assert "notice.setAttribute('aria-live', 'assertive');" in permissions
    assert ".permission-global-warning-toast {" in styles
    assert "overflow-wrap: anywhere;" in styles


def test_pending_and_settings_registration_failures_use_banner_not_modal() -> None:
    permissions = (ROOT / "frontend/src/app/modules/permissions.js").read_text(encoding="utf-8")
    pending = _function_block(
        permissions,
        "async function promptPendingMcpRegistrations",
        "async function setExtensionTrust",
    )
    trust = _function_block(
        permissions,
        "async function setExtensionTrust",
        "async function refreshSecurityExtensions",
    )

    assert "showGlobalWarningBanner(" in pending
    assert "showUiAlert(" not in pending
    assert trust.count("showGlobalWarningBanner(") == 2
