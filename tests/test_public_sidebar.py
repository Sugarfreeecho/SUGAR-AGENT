import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_public_sidebar_runtime():
    result = subprocess.run(
        ["node", str(ROOT / "tests/js/public_sidebar_runtime.mjs")], cwd=ROOT,
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_public_sidebar_shell_markup_in_both_sources():
    for relative in ("frontend/index.html", "frontend/src/shell-body.html"):
        html = (ROOT / relative).read_text(encoding="utf-8")
        assert html.count('class="pubar-head"') == 1
        assert html.count('class="pubar-tabs" role="tablist"') == 1
        assert html.count('class="pubar-panes"') == 1
        assert 'class="pubar-collapse"' not in html  # 头部不再设折叠按钮，开合仅经右缘把手
        assert html.count('id="plugin-session-panels"') == 1
        assert html.count('id="todo-edge-tab"') == 1
        assert 'aria-label="折叠会话状态面板"' in html  # 语义保留在把手上
        assert html.count('id="pubar-narrow-strip"') == 1  # 窄态条目区（输入框上方）
        assert html.count('id="pubar-narrow-popover"') == 1  # 条目点击弹出的专用浮窗
        assert "data-pubar-pane" not in html  # 页签内容宿主由 JS 创建，标记保持最小


def test_public_sidebar_module_is_wired_into_the_bootstrapper():
    source = (ROOT / "frontend/src/app/modules/public-sidebar.js").read_text(encoding="utf-8")
    index = (ROOT / "frontend/src/app/index.js").read_text(encoding="utf-8")

    assert "globalThis.MyAgentPubar" in source
    assert "function pubarPaneHostFor" in source
    assert "function pubarRegisterPane" in source
    assert "function pubarHasContent" in source
    assert "function pubarResetForSession" in source
    assert "function pubarNotifyActivity" in source
    assert "myagent:public-sidebar-ready" in source
    assert "function pubarRenderNarrowStrip" in source
    assert "function pubarOpenNarrowPopover" in source
    assert "function pubarConfigureNarrow" in source
    assert "configureNarrow: pubarConfigureNarrow" in source
    assert "chat-goal-card" not in source
    assert "chat-todo-plan-panel" not in source
    assert "change-review" not in source
    assert "import publicSidebarSource from './modules/public-sidebar.js?raw';" in index
    assert "publicSidebarSource," in index


def test_plugin_session_panels_route_through_group_hosts():
    source = (ROOT / "frontend/src/app/plugin-ui-slots.js").read_text(encoding="utf-8")

    assert "globalThis.MyAgentPubar && typeof globalThis.MyAgentPubar.paneHostFor === 'function'" in source
    assert "pubarApi.paneHostFor(" in source
    assert "group ? group.id : 'plugins'" in source
    assert "if (group) model.group = group;" in source
    assert "const usedFallbackHost = fragments.has(host);" in source
    assert "visiblePanelCount" in source


def test_layout_and_session_hooks_prefer_the_public_sidebar():
    layout = (ROOT / "frontend/src/app/modules/layout-panels.js").read_text(encoding="utf-8")
    toc = (ROOT / "frontend/src/app/modules/toc-todo.js").read_text(encoding="utf-8")

    assert "globalThis.MyAgentPubar.hasContent()" in layout
    assert "(pluginPanels && !pluginPanels.hidden && pluginPanels.children.length)" in layout
    assert "todoTab.classList.toggle('visible', todoPanelHasVisibleContent());" in layout
    assert "pubar.hasContent()" in toc
    assert "globalThis.MyAgentPubar.resetForSession()" in toc
    assert "syncTodoPanelContentVisibility(hasVisibleCard)" in toc


def test_change_review_renders_into_the_changes_pane_with_bar_fallback():
    source = (ROOT / "plugins/change-review/web/change-review.js").read_text(encoding="utf-8")
    styles = (ROOT / "plugins/change-review/web/change-review.css").read_text(encoding="utf-8")

    assert "globalThis.MyAgentPubar" in source
    assert "registerPane" in source
    assert "id: 'changes'" in source
    assert "pubarHandle.setVisible" in source
    assert "pubarHandle.setCount" in source
    assert "function viewedTurnRange" in source
    assert "viewportFallbackAllowed" in source
    assert "pickReviewedTurnKey" in source
    assert "change-review-drawer" in source  # 公共栏不可用时的回退路径保留
    assert "buildCard" in source
    assert "#chat-todo-plan .pubar-pane .change-review-card" in styles


def test_sidebar_groups_and_labels_are_declared():
    todo = json.loads((ROOT / "plugins/session-todo/.myagent-plugin/plugin.json").read_text(encoding="utf-8"))
    goal = json.loads((ROOT / "plugins/agent-goal/.myagent-plugin/plugin.json").read_text(encoding="utf-8"))
    assert todo["capabilities"]["ui"]["session.panel"][0]["group"] == {
        "id": "plan", "label": "计划", "order": 10,
    }
    assert goal["capabilities"]["ui"]["session.panel"][0]["group"] == {
        "id": "goal", "label": "目标", "order": 20,
    }

    i18n = (ROOT / "frontend/src/app/modules/i18n.js").read_text(encoding="utf-8")
    assert "'会话状态': 'Session status'" in i18n
    assert "'计划': 'Plan'" in i18n
    assert "'目标': 'Goal'" in i18n
    assert "'插件': 'Plugins'" in i18n
    assert "'改动': 'Changes'" in i18n
