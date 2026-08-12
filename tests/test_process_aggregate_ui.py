from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_collapsed_process_brief_does_not_render_status_rows():
    rendering = (ROOT / "frontend/src/app/modules/message-rendering.js").read_text(
        encoding="utf-8"
    )
    brief_renderer = rendering.split("function updateProcessBrief(agg)", 1)[1].split(
        "function syncProcessAggregateHeightUi", 1
    )[0]

    assert "body.querySelector('.feed-item.feed--st" not in brief_renderer
    assert ":not(.feed--st)" in brief_renderer
    assert "tAny || '本段过程已折叠'" in brief_renderer
