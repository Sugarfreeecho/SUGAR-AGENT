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


def test_plugin_navigation_host_is_removed_from_both_html_sources():
    for relative in ("frontend/index.html", "frontend/src/shell-body.html"):
        html = (ROOT / relative).read_text(encoding="utf-8")
        assert 'id="plugin-navigation"' not in html
        assert html.count('id="plugin-session-panels"') == 1
        assert html.count('id="plugin-settings-sections"') == 1
        assert html.count('id="plugin-composer-actions"') == 1


def test_plugin_navigation_renderer_is_not_mounted_in_main_ui():
    source = (ROOT / "frontend/src/app/plugin-ui-slots.js").read_text(encoding="utf-8")
    styles = (ROOT / "frontend/src/styles/app.css").read_text(encoding="utf-8")

    assert "renderPluginNavigation" not in source
    assert ".plugin-navigation" not in styles


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
