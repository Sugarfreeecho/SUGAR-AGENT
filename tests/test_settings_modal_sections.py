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
    assert 'href="/execution-dashboard"' in markup
