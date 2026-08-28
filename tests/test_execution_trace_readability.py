import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_execution_trace_rows_have_readable_text_weight_and_size() -> None:
    styles = (ROOT / "frontend/src/styles/app.css").read_text(encoding="utf-8")

    row_selector = (
        ':root[data-frontend-version="v2"] .process-aggregate:not(.subagent-grid-card) '
        "> .process-aggregate-body > .feed-item .feed-chunk-scroller"
    )
    label_selector = (
        ':root[data-frontend-version="v2"] .process-aggregate:not(.subagent-grid-card) '
        "> .process-aggregate-body > .feed-item .feed-label"
    )

    assert ".feed-chunk-scroller {\n    font-size: 0.74rem; font-weight: 500;" in styles
    assert ".feed-row .feed-label {" in styles
    assert "min-width: 0; font-size: 0.69rem; font-weight: 700;" in styles
    assert ":root.theme-light .feed-row .feed-label { color: var(--text-secondary); font-weight: 700; }" in styles
    assert row_selector in styles
    assert "font-size: 0.74rem;\n    font-weight: 500;\n    line-height: 1.6;" in styles
    assert label_selector in styles
    assert "font-size: 0.69rem;\n    font-weight: 700;" in styles
    assert "color-mix(in srgb, var(--process-v2-text-muted) 72%, var(--process-v2-text))" in styles


def test_goal_judge_result_has_a_dedicated_execution_trace_row() -> None:
    dispatcher = (ROOT / "frontend/src/app/modules/event-dispatch.js").read_text(encoding="utf-8")
    renderer = (ROOT / "frontend/src/app/modules/message-rendering.js").read_text(encoding="utf-8")
    styles = (ROOT / "frontend/src/styles/app.css").read_text(encoding="utf-8")

    manifest = json.loads((ROOT / "plugins/agent-goal/.myagent-plugin/plugin.json").read_text(encoding="utf-8"))
    renderer_slot = manifest["capabilities"]["ui"]["message.renderer"][0]
    assert renderer_slot["event_name"] == "judge_result"
    assert "applyPluginExtensionEventView" in dispatcher
    assert "renderPluginExtensionEvent" in dispatcher
