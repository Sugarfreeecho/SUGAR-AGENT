from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_sidebar_runtime_footer_is_present_in_source_markup() -> None:
    for relative_path in ("frontend/index.html", "frontend/src/shell-body.html"):
        markup = (ROOT / relative_path).read_text(encoding="utf-8")
        assert 'class="sidebar-runtime"' in markup
        assert 'id="sidebar-runtime-link"' in markup
        assert 'href="/execution-dashboard"' not in markup
        assert 'id="sidebar-runtime-status"' in markup
        assert 'id="sidebar-runtime-version"' in markup
    assert (ROOT / "plugins/execution-dashboard/web/index.html").is_file()


def test_sidebar_runtime_status_tracks_session_connectivity() -> None:
    source = (ROOT / "frontend/src/app/modules/session-management.js").read_text(encoding="utf-8")

    assert "function updateSidebarRuntimeStatus(nextStatus)" in source
    assert "function startRuntimeStatusHeartbeat()" in source
    assert "'/api/runtime-status'" in source
    assert "Runtime 繁忙" in source
    assert "Runtime 待处理" in source
    assert "updateSidebarRuntimeStatus(true);" in source
    assert "updateSidebarRuntimeStatus(false);" in source


def test_sidebar_uses_dated_product_version() -> None:
    import re

    pattern = re.compile(r'class="sidebar-runtime-version">(v4\.\d{8})</span>')
    versions = []
    for relative_path in ("frontend/index.html", "frontend/src/shell-body.html"):
        markup = (ROOT / relative_path).read_text(encoding="utf-8")
        match = pattern.search(markup)
        assert match, f"{relative_path} missing dated sidebar-runtime-version"
        versions.append(match.group(1))
    assert len(set(versions)) == 1, f"version mismatch across markup: {versions}"


def test_sidebar_runtime_footer_has_theme_aware_styles() -> None:
    styles = (ROOT / "frontend/src/styles/app.css").read_text(encoding="utf-8")

    assert ".sidebar-runtime {" in styles
    assert ".sidebar-runtime-link:hover" in styles
    assert ".sidebar-runtime.is-busy .sidebar-runtime-dot" in styles
    assert ".sidebar-runtime.is-waiting .sidebar-runtime-dot" in styles
    assert ".sidebar-runtime.is-offline .sidebar-runtime-dot" in styles
    assert ":root.theme-light .sidebar-runtime" in styles
