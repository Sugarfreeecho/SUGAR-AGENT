import json
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_plugin_ui_slot_frontend_runtime_and_safe_text_rendering():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is required for frontend runtime checks")
    result = subprocess.run(
        [node, str(ROOT / "tests/js/plugin_ui_slots_runtime.mjs")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "plugin UI slot runtime checks passed" in result.stdout

    source = (ROOT / "frontend/src/app/plugin-ui-slots.js").read_text(encoding="utf-8")
    dispatcher = (ROOT / "frontend/src/app/modules/event-dispatch.js").read_text(
        encoding="utf-8"
    )
    assert "title.textContent = item.title" in source
    assert "button.textContent = item.label" in source
    assert "innerHTML" not in source
    assert "normalizePluginSessionPanelRenderers" in source
    assert "normalizePluginChatExtensions" in source
    assert "import(/* @vite-ignore */ definition.moduleUrl)" in source
    assert "globalThis.fetch.bind(globalThis)" in source
    assert "String(raw.href || '') !== expectedHref" in source
    assert "Object.prototype.hasOwnProperty.call(current, part)" in source
    assert "await refreshPluginSessionUi([sessionId]);" in source
    assert "sessionUiLatestGeneration" in source
    assert "attributes: true" not in source
    assert "without exposing\n            // an undeclared plugin payload" in source
    assert "content.textContent = String(view.content" in dispatcher
    assert "row._pluginExtensionEvent = event" in dispatcher
    assert "innerHTML" not in dispatcher.split("function applyPluginExtensionEventView", 1)[1].split(
        "function renderEvent", 1
    )[0]


def test_session_panels_clear_containers_whose_panels_disappeared():
    """面板从 payload 消失（如计划清空）时，原容器必须被清空。

    回归：renderSessionPanels 只重建「本次仍有面板」的容器，导致清空后的旧卡片
    永久留在左侧会话状态面板里（表现为“当前计划不刷新”）。
    """
    node = shutil.which("node")
    if not node:
        pytest.skip("node is required for frontend runtime checks")
    result = subprocess.run(
        [node, str(ROOT / "tests/js/session_panel_container_cleanup_runtime.mjs")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "session panel container cleanup runtime checks passed" in result.stdout

    source = (ROOT / "frontend/src/app/plugin-ui-slots.js").read_text(encoding="utf-8")
    assert "pluginSessionPanelContainers.forEach(function (container) {" in source
    assert "if (fragments.has(container)) return;" in source
    assert "pluginSessionPanelContainers = new Set(fragments.keys());" in source
    assert "pluginSessionPanelCleanupContainers.get(cleanup) !== container" in source


def test_change_review_frontend_is_plugin_owned_and_uses_safe_text_diff_rendering():
    source = (ROOT / "plugins/change-review/web/change-review.js").read_text(encoding="utf-8")
    styles = (ROOT / "plugins/change-review/web/change-review.css").read_text(encoding="utf-8")
    message_rendering = (ROOT / "frontend/src/app/modules/message-rendering.js").read_text(
        encoding="utf-8"
    )
    event_dispatch = (ROOT / "frontend/src/app/modules/event-dispatch.js").read_text(
        encoding="utf-8"
    )
    right_column = (ROOT / "frontend/src/app/modules/dock/embedder/right-column.js").read_text(
        encoding="utf-8"
    )
    dock_styles = (ROOT / "frontend/src/styles/dock.css").read_text(encoding="utf-8")
    app_styles = (ROOT / "frontend/src/styles/app.css").read_text(encoding="utf-8")
    assert "installChatExtension" in source
    assert "openChangeReview" in source
    assert "registerChangeReviewRows" in source
    assert "file_changes_restored" in source
    assert "myagent:tool-call-rendered" in source
    assert "ResizeObserver" in source
    assert "✏️" not in source
    assert "change-review-view" in source
    assert "change-review-sheet" not in source
    assert "openSheet" not in source
    assert "closeSheet" not in source
    assert "switchSessionView" in source
    assert "sessionObserver" in source
    assert "aggregateSessionId" in source
    assert "aggregateIsCurrent" in source
    assert "rootSessionId" in source
    assert "resetForSession(next)" in source
    assert "document.getElementById('chat-stream')" in source
    assert "root.querySelectorAll('.feed-item.feed--tool')" in source
    assert "document.querySelectorAll('.feed-item.feed--tool')" not in source
    assert "rootSessionIdForRenderedNode" in message_rendering
    assert "rootSessionId: rootSessionIdForRenderedNode" in message_rendering
    assert "rootSessionId: typeof rootSessionIdForRenderedNode" in event_dispatch
    assert "document.querySelectorAll('.change-review-process-badge')" in source
    assert "Rescan when a real tool row was inserted, or when a process" in source
    assert "{ deferRender: true }" in source
    assert "if (hasInsertedRows) scheduleScanExisting();" in source
    assert "syncActiveAggregateToViewport" in source
    assert "chooseVisibleChangeReviewIndex" in source
    assert "document.addEventListener('scroll', viewportListener, true)" in source
    assert "document.removeEventListener('scroll', viewportListener, true)" in source
    assert "if (shouldSync || hasUserTurnBoundary) syncActiveAggregateToViewport();" in source
    assert "new ResizeObserver(function ()" in source
    assert "scheduleScanExisting();" in source
    assert "if (!options.deferRender) {" in source
    assert "requestAnimationFrame" in source
    assert ".change-review-bar[hidden]" in styles
    assert ".change-review-sheet" not in styles
    assert "change-review-stat-added" in styles and "change-review-stat-removed" in styles
    assert "event.type === 'user'" in right_column
    assert "user_steer" in right_column
    assert "dock-turn-select" in right_column
    assert "dockRightChangeGroup" in right_column
    assert "dockRightBulkChangeAction" in right_column
    assert "openChangeReview" in right_column
    assert "myagent:change-review-state" in right_column
    assert "operation_id" in right_column
    assert "host.hidden = !expanded" not in right_column
    assert "host.classList.add('is-collapsed')" in right_column
    assert "body.classList.toggle('is-open', opening)" in right_column
    assert "nextDiffLine + 240" in right_column
    assert "requestAnimationFrame(renderDiffChunk)" in right_column
    assert ".dock-rightbar.is-collapsed" in dock_styles
    assert "transform: translate3d(100%, 0, 0)" in dock_styles
    assert "contain: layout paint" in dock_styles
    assert ".dock-change-body.is-open" in dock_styles
    assert "html.theme-light .dock-change-diff" in dock_styles
    assert "--code-surface-bg: #f5f7fb" in app_styles
    assert "change-review" not in (ROOT / "frontend/index.html").read_text(encoding="utf-8")


def test_change_review_association_covers_the_whole_current_turn():
    source = (ROOT / "plugins/change-review/web/change-review.js").read_text(encoding="utf-8")

    assert "function latestTurnRange" in source
    assert "function nodeWithinTurnRange" in source
    assert "function turnRangeAggregate" in source
    assert "关联区域 = 当前轮的用户问题 → 对应 final 卡片" in source

    viewport = source.split("function viewportAggregate", 1)[1].split(
        "function syncActiveAggregateToViewport", 1
    )[0]
    assert "viewedTurnRange(stream, users)" in viewport  # 关联按“正在查看的轮”
    assert "pickReviewedTurnKey" in viewport
    assert "viewportFallbackAllowed" in viewport  # 收起兜底仅在查看最新轮时生效
    assert "nodeWithinTurnRange(aggregate, latest)" in viewport

    render_section = source.split("function render()", 1)[1].split("function scheduleRender", 1)[0]
    assert "rows.length" in render_section
    assert "isExpanded" not in render_section

    scan = source.split("function scanExisting", 1)[1].split("function resetForSession", 1)[0]
    assert "nodeWithinTurnRange(row, range)" in scan
    assert "rangeAggregate" in scan


def test_change_review_prefers_the_expanded_process_visible_in_the_viewport():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is required for frontend runtime checks")
    result = subprocess.run(
        [node, str(ROOT / "tests/js/change_review_visibility_runtime.mjs")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "change review visibility runtime checks passed" in result.stdout


def test_change_review_stats_treat_missing_line_counts_as_unmeasured():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is required for frontend runtime checks")
    result = subprocess.run(
        [node, str(ROOT / "tests/js/change_review_stats_runtime.mjs")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "change review stats runtime checks passed" in result.stdout


def test_plugin_navigation_host_is_removed_from_both_html_sources():
    for relative in ("frontend/index.html", "frontend/src/shell-body.html"):
        html = (ROOT / relative).read_text(encoding="utf-8")
        assert 'id="plugin-navigation"' not in html
        assert html.count('id="plugin-session-panels"') == 1
        assert html.count('id="plugin-composer-actions"') == 1
        # 「界面设置」弹窗已由设置中心取代：插件贡献的设置槽位改在设置中心的「插件」分区里汇总
        assert 'id="settings-modal-root"' not in html
        assert 'id="plugin-settings-sections"' not in html


def test_plugin_settings_contributions_surface_in_the_settings_center():
    section = (ROOT / "app/templates/static/settings/sections_ext.js").read_text(encoding="utf-8")

    assert "ui_contributions" in section
    assert "settings.section" in section
    assert "renderPluginSettingsSections" not in section


def test_plugin_navigation_renderer_is_not_mounted_in_main_ui():
    source = (ROOT / "frontend/src/app/plugin-ui-slots.js").read_text(encoding="utf-8")
    styles = (ROOT / "frontend/src/styles/app.css").read_text(encoding="utf-8")

    assert "renderPluginNavigation" not in source
    assert ".plugin-navigation" not in styles


def test_todo_plan_items_clamp_to_three_lines_with_hover_tip():
    source = (ROOT / "plugins/session-todo/web/session-panel.js").read_text(encoding="utf-8")
    styles = (ROOT / "plugins/session-todo/web/session-panel.css").read_text(encoding="utf-8")
    core = (ROOT / "frontend/src/app/modules/toc-todo.js").read_text(encoding="utf-8")

    assert "-webkit-line-clamp:3" in styles
    assert ".todo-plan-text" in styles
    assert "el.scrollHeight <= el.clientHeight + 1" in source
    assert "setAttribute('data-ui-tip'" in source
    assert "globalThis.bindUiHoverTip" in source
    assert "globalThis.bindUiHoverTip = bindUiHoverTip;" in core


def test_todo_in_progress_icon_uses_play_glyph_like_dsh_and_zcode():
    source = (ROOT / "plugins/session-todo/web/session-panel.js").read_text(encoding="utf-8")

    # 进行中 = 描边播放三角（DSH 用 IconPlayOutlineRegular，ZCode 侧栏用 “[>]” + 强调色）
    assert "M8.6 6.6 17.6 12 8.6 17.4Z" in source
    # 旧的 3/4 缺口弧环已退役
    assert "A8.2 8.2 0 1 1 3.8 12" not in source
    # 待办/完成的圆环族保持不变
    assert 'circle cx="12" cy="12" r="8.2"' in source


def test_change_review_section_typography_matches_the_plan_section():
    styles = (ROOT / "plugins/change-review/web/change-review.css").read_text(encoding="utf-8")

    # 节头标题与计划节头 .workspace-side-panel-title 同 token / 字号 / 字重 / 字距
    assert "var(--workspace-side-panel-title)" in styles
    assert "font: 650 0.62rem/1.3 var(--sans);" in styles
    # 节头右上统计与计划统计 .chat-todo-plan-stats 同规格
    assert "font: 500 0.56rem/1.3 var(--sans);" in styles
    # 列表与计划列表 .workspace-side-panel-list 同间隙
    assert "gap: 0.22rem;" in styles
    # 条目内边距 = 计划条目 .workspace-side-panel-item 的 0.38rem 0.4rem
    assert ".pubar-pane .change-review-file-head { padding: 0; }" in styles
    assert ".pubar-pane .change-review-file-toggle { padding: 0.38rem 0.4rem; }" in styles
    # 路径文字字号 / 字重 / 行高对齐计划条目文字（400 0.68rem/1.45）
    assert "font: 400 0.68rem/1.45 var(--mono);" in styles


def test_pubar_narrow_strip_items_are_wired_by_plugins():
    todo = (ROOT / "plugins/session-todo/web/session-panel.js").read_text(encoding="utf-8")
    goal = (ROOT / "plugins/agent-goal/web/session-panel.js").read_text(encoding="utf-8")
    review = (ROOT / "plugins/change-review/web/change-review.js").read_text(encoding="utf-8")

    assert "configureNarrow('plan'" in todo
    assert "configureNarrow('goal'" in goal
    assert "toggle.click()" in goal and "remove.click()" in goal
    assert "narrowSummaryHtml" in review and "setNarrow" in review


def test_game_arena_declares_navigation_without_core_frontend_coupling():
    manifest_text = (ROOT / "plugins/game-arena/.myagent-plugin/plugin.json").read_text(
        encoding="utf-8"
    )
    manifest = json.loads(manifest_text)
    assert '"ui"' in manifest_text
    assert '"label": "Game Arena"' in manifest_text
    assert '"composer.action"' not in manifest_text
    assert '"open-arena"' not in manifest_text
    assert manifest["capabilities"]["ui"]["settings.section"] == []
    assert "settings_schema" in manifest
    for relative in (
        "frontend/index.html",
        "frontend/src/shell-body.html",
        "frontend/src/app/index.js",
        "frontend/src/app/plugin-ui-slots.js",
    ):
        assert "Game Arena" not in (ROOT / relative).read_text(encoding="utf-8")


def test_goal_and_todo_specialized_ui_remains_owned_by_plugins():
    source = (ROOT / "frontend/src/app/plugin-ui-slots.js").read_text(encoding="utf-8")
    shell = (ROOT / "frontend/src/shell-body.html").read_text(encoding="utf-8")
    assert "chat-goal-card" not in source
    assert "chat-todo-plan-panel" not in source
    assert "chat-goal-card" not in shell
    assert "chat-todo-plan-panel" not in shell
    for plugin_id in ("agent-goal", "session-todo"):
        root = ROOT / "plugins" / plugin_id / "web"
        assert (root / "session-panel.js").is_file()
        assert (root / "session-panel.css").is_file()
    todo_renderer = (
        ROOT / "plugins/session-todo/web/session-panel.js"
    ).read_text(encoding="utf-8")
    goal_renderer = (
        ROOT / "plugins/agent-goal/web/session-panel.js"
    ).read_text(encoding="utf-8")
    assert "total === 0 || done >= total" in todo_renderer
    assert "panel.hidden = true" in todo_renderer
    assert "data.goal.deleted !== true" in goal_renderer
    assert "hideGoalPanel()" in goal_renderer
    assert "visiblePanelCount" in source
