from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_theme_picker_exposes_light_dark_and_purple_variants() -> None:
    for relative_path in ("frontend/index.html", "frontend/src/shell-body.html"):
        markup = (ROOT / relative_path).read_text(encoding="utf-8")
        assert 'id="settings-theme-light"' in markup
        assert 'id="settings-theme-dark"' in markup
        assert 'id="settings-theme-purple"' in markup
        assert ">紫色</button>" in markup


def test_theme_storage_keeps_legacy_dark_as_purple() -> None:
    settings = (ROOT / "frontend/src/app/modules/settings.js").read_text(encoding="utf-8")
    bootstrap = (ROOT / "frontend/index.html").read_text(encoding="utf-8")

    assert "t === 'dark' || t === 'purple'" in settings
    assert "applyUiTheme('purple', false)" in settings
    assert "next === 'dark' ? 'deep-dark' : next" in settings
    assert "savedTheme === 'deep-dark' ? 'theme-dark'" in bootstrap
    assert "savedTheme === 'dark' || savedTheme === 'purple' ? 'theme-purple'" in bootstrap


def test_neutral_dark_theme_uses_reference_palette() -> None:
    styles = (ROOT / "frontend/src/styles/app.css").read_text(encoding="utf-8")

    dark = styles.split(":root.theme-dark {", 1)[1].split("}", 1)[0]
    assert "--space-bg: #151517;" in dark
    assert "--surface-glass2: rgba(44, 44, 46, 0.98);" in dark
    assert "--text-primary: #f9fafb;" in dark
    assert "--accent-1: #679efe;" in dark
    assert "--export-bg: #151517;" in dark


def test_theme_labels_are_translated() -> None:
    translations = (ROOT / "frontend/src/app/modules/i18n.js").read_text(encoding="utf-8")
    assert "'深色': 'Dark'" in translations
    assert "'紫色': 'Purple'" in translations


def test_neutral_dark_message_content_uses_blue_accents() -> None:
    styles = (ROOT / "frontend/src/styles/app.css").read_text(encoding="utf-8")

    dark = styles.split(":root.theme-dark {", 1)[1].split("}", 1)[0]
    assert "--content-accent-text: #82b6e6;" in dark
    assert ":root.theme-dark .message :not(pre) > code" in styles
    assert ":root.theme-dark .message a {" in styles
    assert ":root.theme-dark .message blockquote { border-left-color: var(--accent-1); }" in styles
    inline_code = styles.split(":root.theme-dark .message :not(pre) > code {", 1)[1].split("}", 1)[0]
    assert "color: var(--content-accent-text);" in inline_code
    link = styles.split(":root.theme-dark .message a {", 1)[1].split("}", 1)[0]
    assert "color: var(--content-accent-text);" in link
    table_header = styles.split(":root.theme-dark .message th {", 1)[1].split("}", 1)[0]
    assert "color: var(--content-accent-text);" in table_header
    assert "background: rgba(var(--accent-rgb), 0.14);" in table_header
    assert "border-color: rgba(var(--accent-rgb), 0.28);" in table_header


def test_neutral_dark_process_replies_blend_into_the_process_panel() -> None:
    styles = (ROOT / "frontend/src/styles/app.css").read_text(encoding="utf-8")

    process_body = styles.split(":root.theme-dark .process-aggregate-body {", 1)[1].split("}", 1)[0]
    assert "background: rgba(21, 21, 23, 0.62);" in process_body

    reply_group = styles.split(
        ":root.theme-dark .process-aggregate-body .feed-item.feed--llm,", 1
    )[1].split("}", 1)[0]
    assert "margin: 0;" in reply_group
    assert "border-left-width: 2px;" in reply_group
    assert "border-radius: 0;" in reply_group
    assert "box-shadow: none;" in reply_group

    response = styles.split(":root.theme-dark .feed-item.feed--llm2,", 1)[1].split("}", 1)[0]
    assert "--feed-item-bg: transparent;" in response
    assert "border-left-color: rgba(130, 182, 230, 0.68);" in response
    assert "background: transparent;" in response
    assert "linear-gradient" not in response
