from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

LAYOUT = ROOT / "frontend/src/app/modules/layout-panels.js"
STYLES = ROOT / "frontend/src/styles/app.css"


def _layout() -> str:
    return LAYOUT.read_text(encoding="utf-8")


def test_side_panels_use_real_content_and_panel_geometry() -> None:
    layout = _layout()

    assert "function mainContentColumnRect" in layout
    assert ".chat-stream > .msg-wrap" in layout
    assert "leftAvailable >= preferredPanelWidth + COLLISION_GAP" in layout
    assert "rightAvailable >= preferredPanelWidth + COLLISION_GAP" in layout
    assert "LAYOUT_COLLAPSE_AT" not in layout
    assert "LAYOUT_EXPAND_AT" not in layout


def test_panel_wide_narrow_follows_the_composer_switch() -> None:
    """收起/展开必须与输入区侧控件的折叠同源，不能再比输入区更早把卡片收起。"""

    layout = _layout()
    styles = STYLES.read_text(encoding="utf-8")

    # 宽/窄状态直接读输入区写入的 content-column-expanded
    assert "content-column-expanded" in layout
    assert "var narrowLayout = !!(mainCenterEl && mainCenterEl.classList.contains('content-column-expanded'))" in layout
    # 同一判据：期望宽度 + 同一个 8px 间距，且不计 dock 偏移
    assert "var todoFits = !narrowLayout && leftAvailable >= preferredPanelWidth + COLLISION_GAP;" in layout
    assert "var tocFits = !narrowLayout && rightAvailable >= preferredPanelWidth + COLLISION_GAP;" in layout
    # 临界带里先缩窄、后收起：宽度下限取 --side-panel-min-width
    assert "Math.max(minPanelWidth, Math.floor(leftAvailable - todoDockOffset - RECOVERY_GAP))" in layout
    assert "Math.max(minPanelWidth, Math.floor(rightAvailable - tocDockOffset - RECOVERY_GAP))" in layout
    assert "--side-panel-min-width" in styles
    # 输入区宽窄切换后立即带动两侧卡
    assert "runPanelAutoCollapseCheck();" in layout


def test_each_side_tracks_and_recovers_independently() -> None:
    layout = _layout()

    assert "panelAutoCollapsedTodo" in layout
    assert "panelAutoCollapsedToc" in layout
    assert "todoOpen && !todoFits" in layout
    assert "tocOpen && !tocFits" in layout
    assert "stage.dataset.todoContentOverlap" in layout
    assert "stage.dataset.tocContentOverlap" in layout
    assert "schedulePanelRecoveryCheck(440)" in layout


def test_manual_reopen_overrides_the_auto_collapse_until_space_recovers() -> None:
    layout = _layout()

    assert "panelManualOverlapTodo = isOpening" in layout
    assert "panelManualOverlapToc = isOpening" in layout
    assert "!todoFits && !panelManualOverlapTodo" in layout
    assert "!tocFits && !panelManualOverlapToc" in layout
    assert "panelManualOverlapTodo && (!todoPanelHasVisibleContent() || todoFits)" in layout
    assert "panelManualOverlapToc && (!(tocList && tocList.children.length) || tocFits)" in layout


def test_panel_transitions_and_plugin_content_are_observed() -> None:
    layout = _layout()

    assert "panelAutoCollapseObserver.observe(todo)" in layout
    assert "panelAutoCollapseObserver.observe(toc)" in layout
    assert "(pluginPanels && !pluginPanels.hidden && pluginPanels.children.length)" in layout


def test_goal_refresh_does_not_override_manual_or_automatic_collapse() -> None:
    layout = _layout()
    goal_ui = (ROOT / "frontend/src/app/modules/toc-todo.js").read_text(encoding="utf-8")

    assert "panelUserCollapsedTodo = !isOpening" in layout
    assert "!panelUserCollapsedTodo && !panelAutoCollapsedTodo" in layout
    assert "syncTodoPanelContentVisibility(hasVisibleCard)" in goal_ui
    assert "root.classList.toggle('is-open', hasVisibleCard)" not in goal_ui
