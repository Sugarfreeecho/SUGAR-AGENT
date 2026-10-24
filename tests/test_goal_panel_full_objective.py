"""左栏「会话状态」的 goal 页签：Goal 描述受公共浮层高度约束，不再自带文本/高度上限。"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

GOAL_CSS = ROOT / "plugins/agent-goal/web/session-panel.css"
GOAL_JS = ROOT / "plugins/agent-goal/web/session-panel.js"
APP_CSS = ROOT / "frontend/src/styles/app.css"


def _rule(styles: str, selector: str) -> str:
    head, _, tail = styles.partition(selector + " {")
    assert tail, f"{selector} 规则缺失"
    return tail.split("}", 1)[0]


def test_goal_objective_has_no_text_cap_of_its_own() -> None:
    styles = GOAL_CSS.read_text(encoding="utf-8")
    objective = _rule(styles, ".agent-goal-panel-host .chat-goal-objective")

    assert "-webkit-line-clamp" not in objective
    assert "line-clamp" not in objective
    assert "overflow:hidden" not in objective
    assert "display:block" in objective
    assert "white-space:pre-wrap" in objective


def test_goal_panel_leaves_the_height_limit_to_the_shared_side_panel() -> None:
    styles = GOAL_CSS.read_text(encoding="utf-8")
    card = _rule(styles, ".agent-goal-panel-host .chat-goal-card")

    # 卡片自身不设高度/文本上限（只有 flex 与 min-height 归零）
    assert "max-height" not in card
    assert "line-clamp" not in card
    # 统一上限仍由会话状态浮层的公共变量提供
    app_styles = APP_CSS.read_text(encoding="utf-8")
    assert "--side-panel-max-height: 70vh;" in app_styles
    assert "max-height: min(var(--side-panel-max-height, 70vh), max(0px, calc(100% - 2rem)));" in app_styles
    assert ".pubar-panes {" in app_styles
    assert "overflow-y: auto;" in _rule(app_styles, ".pubar-panes")


def test_panel_shows_the_whole_objective_and_only_the_narrow_strip_summarizes() -> None:
    source = GOAL_JS.read_text(encoding="utf-8")

    assert "objective.textContent = full;" in source
    assert "objective.textContent = objectiveSummary(full);" not in source
    # 输入框上方的窄态条目仍然用短摘要
    assert "summary: objectiveSummary(full)," in source


def test_goal_action_row_stays_pinned_while_the_objective_scrolls() -> None:
    styles = GOAL_CSS.read_text(encoding="utf-8")
    actions = _rule(styles, ".agent-goal-panel-host .chat-goal-actions")
    card = _rule(styles, ".agent-goal-panel-host .chat-goal-card")

    # 按钮行常驻：贴在会话状态浮层可视底边，滚到底再回落到原位
    assert "position:sticky" in actions
    assert "bottom:0" in actions
    assert "background:var(--floating-surface)" in actions
    # .workspace-side-panel 的 overflow:hidden 会截断 sticky 的滚动容器，必须放开
    assert "overflow:visible" in card
