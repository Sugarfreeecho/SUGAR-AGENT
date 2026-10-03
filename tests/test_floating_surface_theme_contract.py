from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def _selector_declarations(styles: str, selector: str) -> dict[str, str]:
    # CSS allows the same selector to split scrollbar and surface declarations.
    blocks = re.findall(r"(?m)^\s*" + re.escape(selector) + r"\s*\{([^{}]*)\}", styles)
    assert blocks, f"Missing CSS rule for {selector}"
    declarations = {}
    for block in blocks:
        for declaration in block.split(";"):
            name, separator, value = declaration.partition(":")
            if separator:
                declarations[name.strip()] = value.strip()
    return declarations


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
        declarations = _selector_declarations(styles, selector)
        assert declarations["background"] == "var(--floating-surface)", selector

    raised_surface_selectors = (
        ".session-more-menu",
        ".msg-copy-popover",
    )
    for selector in raised_surface_selectors:
        declarations = _selector_declarations(styles, selector)
        assert declarations["background"] == "var(--floating-surface-raised)", selector

    assert "background:var(--floating-surface," in picker
    assert "border:1px solid var(--floating-border," in picker
    assert "box-shadow:var(--floating-shadow," in picker


def test_tooltip_has_no_theme_specific_hard_coded_background() -> None:
    styles = (ROOT / "frontend/src/styles/app.css").read_text(encoding="utf-8")

    tooltip = _selector_declarations(styles, "#ui-hover-tooltip")
    assert tooltip["background"] == "var(--floating-surface)"
    assert tooltip["border"] == "1px solid var(--floating-border)"
    assert tooltip["box-shadow"] == "var(--floating-shadow)"
    assert ":root.theme-light #ui-hover-tooltip" not in styles
