from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_side_panels_use_real_content_and_panel_geometry() -> None:
    layout = (ROOT / "frontend/src/app/modules/layout-panels.js").read_text(encoding="utf-8")

    assert "function mainContentColumnRect" in layout
    assert ".chat-stream > .msg-wrap" in layout
    assert "todoRect.right + COLLISION_GAP > contentRect.left" in layout
    assert "tocRect.left - COLLISION_GAP < contentRect.right" in layout
    assert "LAYOUT_COLLAPSE_AT" not in layout
    assert "LAYOUT_EXPAND_AT" not in layout


def test_each_side_tracks_and_recovers_independently() -> None:
    layout = (ROOT / "frontend/src/app/modules/layout-panels.js").read_text(encoding="utf-8")

    assert "panelAutoCollapsedTodo" in layout
    assert "panelAutoCollapsedToc" in layout
    assert "todoDockOffset + preferredPanelWidth + RECOVERY_GAP" in layout
    assert "tocDockOffset + preferredPanelWidth + RECOVERY_GAP" in layout
    assert "stage.dataset.todoContentOverlap" in layout
    assert "stage.dataset.tocContentOverlap" in layout
    assert "schedulePanelRecoveryCheck(440)" in layout


def test_manual_reopen_overrides_the_auto_collapse_until_space_recovers() -> None:
    layout = (ROOT / "frontend/src/app/modules/layout-panels.js").read_text(encoding="utf-8")

    assert "panelManualOverlapTodo = isOpening" in layout
    assert "panelManualOverlapToc = isOpening" in layout
    assert "todoOverlaps && todo && !panelManualOverlapTodo" in layout
    assert "tocOverlaps && toc && !panelManualOverlapToc" in layout
    assert "panelManualOverlapTodo && (!todoPanelHasVisibleContent() || todoHasRecoveryRoom)" in layout
    assert "panelManualOverlapToc && (!(tocList && tocList.children.length) || tocHasRecoveryRoom)" in layout


def test_panel_transitions_and_plugin_content_are_observed() -> None:
    layout = (ROOT / "frontend/src/app/modules/layout-panels.js").read_text(encoding="utf-8")

    assert "panelAutoCollapseObserver.observe(todo)" in layout
    assert "panelAutoCollapseObserver.observe(toc)" in layout
    assert "(pluginPanels && !pluginPanels.hidden && pluginPanels.children.length)" in layout


def test_goal_refresh_does_not_override_manual_or_automatic_collapse() -> None:
    layout = (ROOT / "frontend/src/app/modules/layout-panels.js").read_text(encoding="utf-8")
    goal_ui = (ROOT / "frontend/src/app/modules/toc-todo.js").read_text(encoding="utf-8")

    assert "panelUserCollapsedTodo = !isOpening" in layout
    assert "!panelUserCollapsedTodo && !panelAutoCollapsedTodo" in layout
    assert "syncTodoPanelContentVisibility(hasVisibleCard)" in goal_ui
    assert "root.classList.toggle('is-open', hasVisibleCard)" not in goal_ui
