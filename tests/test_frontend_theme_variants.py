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


def test_execution_process_panel_styles_are_the_single_skin() -> None:
    styles = (ROOT / "frontend/src/styles/app.css").read_text(encoding="utf-8")

    assert ':root .process-aggregate:not(.subagent-grid-card)' in styles
    assert "--process-panel: #1b1b1d;" in styles
    assert ".is-collapsed .process-aggregate-brief," in styles
    assert "display: none !important;" in styles
    assert "> .process-aggregate-body > .feed-item:nth-child(even)" not in styles
    assert "--process-row-status: #1c1c1e;" in styles
    assert "--process-row-thinking: #1e2226;" in styles
    assert "--process-row-reply: #20252b;" in styles
    assert "--process-row-tool: #202022;" in styles
    stats = styles.split(
        ':root .process-aggregate:not(.subagent-grid-card) .process-aggregate-stats {',
        1,
    )[1].split("}", 1)[0]
    assert "font-family: var(--sans);" in stats
    assert "font-size: 0.58rem;" in stats
    assert "gap: 1rem;" in stats
    top = styles.split(
        ':root .process-aggregate:not(.subagent-grid-card) > .process-aggregate-top {',
        1,
    )[1].split("}", 1)[0]
    assert "padding: 0.7rem 0.82rem;" in top
    collapsed_top = styles.split(
        ':root .process-aggregate:not(.subagent-grid-card).is-collapsed > .process-aggregate-top {',
        1,
    )[1].split("}", 1)[0]
    assert "padding-top: 0.62rem;" in collapsed_top
    assert "padding-bottom: 0.62rem;" in collapsed_top
    title_wrap = styles.split(
        ':root .process-aggregate:not(.subagent-grid-card) .process-aggregate-title-wrap {',
        1,
    )[1].split("}", 1)[0]
    assert "gap: 0.12rem;" in title_wrap
    chevron = styles.split(
        ':root .process-aggregate:not(.subagent-grid-card) .process-chev {',
        1,
    )[1].split("}", 1)[0]
    assert "position: absolute;" in chevron
    assert "top: 50%;" in chevron
    assert "transform: translateY(-50%);" in chevron
    assert "background:" not in chevron
    assert "border:" not in chevron
    assert ".process-chev::before" in styles
    chevron_shape = styles.split(
        ':root .process-aggregate:not(.subagent-grid-card) .process-chev::before {',
        1,
    )[1].split("}", 1)[0]
    assert "transform: rotate(45deg);" in chevron_shape
    assert "translateY" not in chevron_shape
    assert "@keyframes processProgress" in styles
    assert "data-frontend-version" not in styles


def test_execution_process_copy_uses_execution_process() -> None:
    rendering = (ROOT / "frontend/src/app/modules/message-rendering.js").read_text(encoding="utf-8")
    translations = (ROOT / "frontend/src/app/modules/i18n.js").read_text(encoding="utf-8")
    subagent = (ROOT / "frontend/src/app/modules/subagent.js").read_text(encoding="utf-8")

    assert '<span class="process-aggregate-title">执行过程</span>' in rendering
    assert "'执行过程': 'Execution process'" in translations
    assert "展开执行过程高度" in rendering
    assert "收起执行过程高度" in rendering
    assert "展开查看执行过程" in subagent
    assert '<span class="process-aggregate-title">执行轨迹</span>' not in rendering
