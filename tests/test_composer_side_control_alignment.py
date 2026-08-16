from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_composer_side_controls_are_centered_in_available_slots() -> None:
    styles = (ROOT / "frontend/src/styles/app.css").read_text(encoding="utf-8")

    assert "--composer-input-width: var(--content-column-width, min(68cqi, 100%));" in styles
    assert "right: calc(var(--composer-panel-end-gutter) + (100% - var(--composer-panel-end-gutter) - var(--composer-input-width)) / 4);" in styles
    assert "transform: translate(50%, -50%);" in styles
    assert "left: calc((100% - var(--composer-panel-end-gutter) - var(--composer-input-width)) / 4);" in styles
    assert "transform: translate(-50%, -50%);" in styles


def test_composer_side_controls_stack_when_measured_space_is_insufficient() -> None:
    styles = (ROOT / "frontend/src/styles/app.css").read_text(encoding="utf-8")
    layout = (ROOT / "frontend/src/app/modules/layout-panels.js").read_text(encoding="utf-8")

    assert ".panel.composer-side-controls-stacked" in styles
    assert '". composer ."' in styles
    assert '". controls ."' in styles
    assert "grid-template-columns: minmax(0, 1fr) var(--composer-input-width) minmax(0, 1fr);" in styles
    assert ".composer-permission-bar {\n    grid-area: controls;\n    justify-self: start;" in styles
    assert ".composer-model-bar {\n    grid-area: controls;\n    justify-self: end;" in styles
    assert "function syncComposerSideControlLayout()" in layout
    assert "naturalComposerWidth = Math.min(mainCenterRect.width * 0.68" in layout
    assert "preferredWidth + safeGap > leftAvailable" in layout
    assert "preferredWidth + safeGap > rightAvailable" in layout
    assert "mainCenter.classList.toggle('content-column-expanded', overlaps)" in layout
    assert "panel.dataset.composerControlsOverlap" in layout
    assert "new ResizeObserver(scheduleComposerSideControlLayout)" in layout
    assert "new MutationObserver(scheduleComposerSideControlLayout)" in layout


def test_content_column_uses_side_space_after_controls_stack() -> None:
    styles = (ROOT / "frontend/src/styles/app.css").read_text(encoding="utf-8")

    assert "--content-column-width: min(68cqi, 100%);" in styles
    assert ".main-center.content-column-expanded" in styles
    assert "--content-column-width: min(calc(100cqi - 2rem), 100%);" in styles
    assert "width: var(--content-column-width, min(68cqi, 100%));" in styles
    assert "--composer-input-width: var(--content-column-width, min(68cqi, 100%));" in styles


def test_operation_toast_follows_the_real_composer_height() -> None:
    styles = (ROOT / "frontend/src/styles/app.css").read_text(encoding="utf-8")
    layout = (ROOT / "frontend/src/app/modules/layout-panels.js").read_text(encoding="utf-8")

    assert "bottom: calc(var(--toast-composer-height, 4.75rem) + 0.75rem)" in styles
    assert "function syncToastComposerOffset()" in layout
    assert "Math.ceil(panel.getBoundingClientRect().height) + 'px'" in layout
    assert "new ResizeObserver(syncToastComposerOffset)" in layout
    assert "toastComposerHeightObserver.observe(panel)" in layout
    assert "initToastComposerOffset();" in layout
