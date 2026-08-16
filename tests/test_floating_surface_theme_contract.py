from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_all_themes_define_distinct_floating_surfaces() -> None:
    styles = (ROOT / "frontend/src/styles/app.css").read_text(encoding="utf-8")

    assert "--floating-surface: rgba(41, 41, 63, 0.98);" in styles
    assert "--floating-surface: rgba(44, 44, 46, 0.99);" in styles
    assert "--floating-surface: rgba(255, 255, 255, 0.99);" in styles
    assert styles.count("--floating-border:") == 3
    assert styles.count("--floating-shadow:") == 3
    assert styles.count("--floating-hover:") == 3
    assert styles.count("--floating-selected:") == 3


def test_floating_components_share_the_theme_surface_contract() -> None:
    styles = (ROOT / "frontend/src/styles/app.css").read_text(encoding="utf-8")
    picker = (ROOT / "frontend/src/vendor/myagent_path_picker.js").read_text(encoding="utf-8")

    shared_surface_selectors = (
        "#ui-hover-tooltip",
        ".followup-mode-menu",
        ".skill-picker-popover",
        ".composer-model-menu",
        ".composer-permission-menu",
        ".copy-toast",
        ".rewrite-undo-toast",
        ".ui-modal-select-menu",
    )
    for selector in shared_surface_selectors:
        block = styles.split(selector + " {", 1)[1].split("}", 1)[0]
        assert "var(--floating-surface)" in block

    raised_surface_selectors = (
        ".session-more-menu",
        ".msg-copy-popover",
        ".subagent-card-menu-pop",
    )
    for selector in raised_surface_selectors:
        block = styles.split(selector + " {", 1)[1].split("}", 1)[0]
        assert "var(--floating-surface-raised)" in block

    assert "background:var(--floating-surface," in picker
    assert "border:1px solid var(--floating-border," in picker
    assert "box-shadow:var(--floating-shadow," in picker


def test_tooltip_has_no_theme_specific_hard_coded_background() -> None:
    styles = (ROOT / "frontend/src/styles/app.css").read_text(encoding="utf-8")

    tooltip = styles.split("#ui-hover-tooltip {", 1)[1].split("}", 1)[0]
    assert "background: var(--floating-surface);" in tooltip
    assert "border: 1px solid var(--floating-border);" in tooltip
    assert "box-shadow: var(--floating-shadow);" in tooltip
    assert ":root.theme-light #ui-hover-tooltip" not in styles
