import json
from pathlib import Path

from app.plugins import load_plugin, plugin_ui_contributions, project_plugin_session_ui
from app.plugins.ui import plugin_session_action_definition


ROOT = Path(__file__).resolve().parents[1]


def _plugin(
    tmp_path: Path,
    navigation,
    *,
    extra_ui=None,
    system_builtin: bool = False,
) -> object:
    root = tmp_path / "ui-plugin"
    manifest = root / ".myagent-plugin" / "plugin.json"
    manifest.parent.mkdir(parents=True)
    (root / "web").mkdir()
    (root / "web" / "index.html").write_text("plugin", encoding="utf-8")
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "id": "ui.demo",
                "name": "UI Demo",
                "version": "1.0.0",
                "system_builtin": system_builtin,
                "capabilities": {
                    "web": {"entry": "web/index.html", "assets": "web"},
                    "ui": {"navigation": navigation, **dict(extra_ui or {})},
                },
            }
        ),
        encoding="utf-8",
    )
    return load_plugin(root)


def test_navigation_contribution_uses_host_owned_destination(tmp_path):
    plugin = _plugin(
        tmp_path,
        [
            {
                "id": "arena",
                "label": "Arena <script>",
                "description": "Play safely",
                "order": -50_000,
                "href": "https://evil.example/steal",
                "html": "<img src=x onerror=alert(1)>",
            }
        ],
    )

    assert plugin_ui_contributions(plugin) == (
        {
            "id": "arena",
            "plugin_id": "ui.demo",
            "slot": "navigation",
            "label": "Arena <script>",
            "description": "Play safely",
            "order": -10_000,
            "href": "/plugins/ui.demo",
            "target": "plugin-page",
        },
    )


def test_ui_only_session_todo_plugin_is_a_supported_native_plugin():
    plugin = load_plugin(ROOT / "plugins" / "session-todo")

    assert plugin.compatibility.status == "native"
    assert "ui" in plugin.compatibility.supported_components
    slots = {row["slot"] for row in plugin_ui_contributions(plugin)}
    assert slots == {"session.badge", "session.panel"}
    panel = next(
        row for row in plugin_ui_contributions(plugin)
        if row["slot"] == "session.panel"
    )
    assert panel["visible_when"] == {"path": "/has_plan", "when": "truthy"}
    assert plugin_session_action_definition(
        [plugin], "session-todo", "clear-plan"
    ) == {
        "plugin_id": "session-todo",
        "namespace": "plan",
        "action_id": "clear-plan",
        "operation": "set_state",
        "state_value": {
            "schema_version": 1,
            "has_plan": False,
            "items": [],
            "done": 0,
            "total": 0,
            "cleared": True,
        },
    }


def test_todo_panel_is_not_projected_after_plan_is_cleared():
    plugin = load_plugin(ROOT / "plugins" / "session-todo")
    cleared = {
        "extensions": {
            "session-todo": {
                "plan": {
                    "revision": 2,
                    "value": {
                        "schema_version": 1,
                        "has_plan": False,
                        "items": [],
                        "done": 0,
                        "total": 0,
                        "cleared": True,
                    },
                }
            }
        }
    }

    projected = project_plugin_session_ui([plugin], ["s1"], lambda _sid: cleared)

    assert projected["s1"] == {"badges": [], "panels": []}


def test_bundled_goal_and_todo_panels_publish_versioned_plugin_renderers():
    for plugin_id in ("agent-goal", "session-todo"):
        plugin = load_plugin(ROOT / "plugins" / plugin_id)
        panel = next(
            row for row in plugin_ui_contributions(plugin)
            if row["slot"] == "session.panel"
        )
        prefix = f"/plugin-assets/{plugin_id}/session-panel"
        assert panel["renderer"]["module"].startswith(prefix + ".js?v=")
        assert panel["renderer"]["style"].startswith(prefix + ".css?v=")

    goal = load_plugin(ROOT / "plugins" / "agent-goal")
    badges = {
        row["id"]: row for row in plugin_ui_contributions(goal)
        if row["slot"] == "session.badge"
    }
    assert badges["active-goal"]["display"] == "activity"
    assert badges["review-goal"]["label"] == "待审核"
    assert badges["review-goal"]["variant"] == "success"
    assert badges["review-goal"]["path"] == "/review_status"
    assert badges["review-goal"]["equals"] == "pending"


def test_bundled_goal_ui_does_not_project_an_approved_deleted_goal():
    plugin = load_plugin(ROOT / "plugins" / "agent-goal")
    snapshot = {
        "extensions": {
            "agent-goal": {
                "goal": {
                    "revision": 9,
                    "value": {
                        "id": "goal-approved",
                        "objective": "Finished work",
                        "status": "completed",
                        "review_status": "approved",
                        "deleted": True,
                    },
                }
            }
        }
    }

    projected = project_plugin_session_ui([plugin], ["s1"], lambda _sid: snapshot)

    assert projected["s1"] == {"badges": [], "panels": []}


def test_bundled_goal_ui_projects_active_and_pending_review_states():
    plugin = load_plugin(ROOT / "plugins" / "agent-goal")

    def project(value):
        snapshot = {
            "extensions": {
                "agent-goal": {"goal": {"revision": 1, "value": value}}
            }
        }
        return project_plugin_session_ui([plugin], ["s1"], lambda _sid: snapshot)["s1"]

    active = project({"id": "g1", "objective": "Work", "status": "active"})
    pending = project({
        "id": "g1", "objective": "Work", "status": "completed",
        "review_status": "pending",
    })

    assert [row["id"] for row in active["badges"]] == ["active-goal"]
    assert [row["id"] for row in active["panels"]] == ["current-goal"]
    assert [row["id"] for row in pending["badges"]] == ["review-goal"]
    assert [row["id"] for row in pending["panels"]] == ["current-goal"]


def test_user_plugin_cannot_claim_host_page_renderer_trust(tmp_path):
    plugin = _plugin(
        tmp_path,
        [],
        system_builtin=True,
        extra_ui={
            "session.panel": [{
                "id": "unsafe", "namespace": "job", "title": "Unsafe",
                "renderer": {"module": "session-panel.js", "style": "session-panel.css"},
                "fields": [{"path": "/value", "label": "Value"}],
            }],
        },
    )
    (plugin.root / "web" / "session-panel.js").write_text("export {};", encoding="utf-8")
    (plugin.root / "web" / "session-panel.css").write_text("body {}", encoding="utf-8")

    panel = next(
        row for row in plugin_ui_contributions(plugin)
        if row["slot"] == "session.panel"
    )
    assert "renderer" not in panel


def test_invalid_duplicate_and_oversized_navigation_rows_are_ignored(tmp_path):
    plugin = _plugin(
        tmp_path,
        [
            {"id": "Bad ID", "label": "invalid id"},
            {"id": "ok", "label": ""},
            {"id": "ok", "label": "valid"},
            {"id": "ok", "label": "duplicate"},
            {"id": "too-long", "label": "x" * 65},
            {"id": "long-description", "label": "valid", "description": "x" * 201},
        ],
    )

    assert plugin_ui_contributions(plugin) == (
        {
            "id": "ok",
            "plugin_id": "ui.demo",
            "slot": "navigation",
            "label": "valid",
            "description": "",
            "order": 100,
            "href": "/plugins/ui.demo",
            "target": "plugin-page",
        },
    )


def test_navigation_requires_a_declared_web_entry(tmp_path):
    plugin = _plugin(tmp_path, True)
    raw = dict(plugin.raw_manifest)
    raw["capabilities"] = {"ui": {"navigation": True}}
    object.__setattr__(plugin, "raw_manifest", raw)

    assert plugin_ui_contributions(plugin) == ()


def test_extension_snapshot_only_exposes_loaded_plugin_ui(tmp_path, monkeypatch):
    from app import agent_extensions
    from app.plugins import PluginManager

    discovery = tmp_path / "plugins"
    _plugin(discovery, [{"id": "main", "label": "UI Demo", "order": 25}])
    manager = PluginManager([discovery], tmp_path / "plugin-state.json")
    monkeypatch.setattr(agent_extensions, "plugin_manager", lambda: manager)
    monkeypatch.setattr(
        agent_extensions,
        "hook_snapshot",
        lambda: {
            "path": "",
            "definitions": [],
            "errors": [],
            "loaded_sources": [],
        },
    )
    monkeypatch.setenv("PLUGINS_ENABLED", "1")
    agent_extensions.invalidate_extension_caches()

    enabled = agent_extensions.extensions_snapshot()
    assert enabled["ui_contributions"] == [
        {
            "id": "main",
            "plugin_id": "ui.demo",
            "slot": "navigation",
            "label": "UI Demo",
            "description": "",
            "order": 25,
            "href": "/plugins/ui.demo",
            "target": "plugin-page",
        }
    ]
    assert enabled["plugins"][0]["ui"] == enabled["ui_contributions"]

    agent_extensions.set_plugin_enabled("ui.demo", False)
    disabled = agent_extensions.extensions_snapshot()
    assert disabled["ui_contributions"] == []
    assert disabled["plugins"][0]["loaded"] is False
    assert disabled["plugins"][0]["ui"] == []


def test_bundled_system_plugin_stays_active_but_is_hidden_from_catalog(
    tmp_path, monkeypatch
):
    from app import agent_extensions
    from app.plugins import PluginManager

    discovery = tmp_path / "bundled-plugins"
    _plugin(
        discovery,
        [{"id": "main", "label": "System UI"}],
        system_builtin=True,
    )
    manager = PluginManager([discovery], tmp_path / "plugin-state.json")
    monkeypatch.setattr(agent_extensions, "plugin_manager", lambda: manager)
    monkeypatch.setattr(agent_extensions, "_bundled_plugins_root", lambda: discovery)
    monkeypatch.setattr(
        agent_extensions,
        "hook_snapshot",
        lambda: {"path": "", "definitions": [], "errors": [], "loaded_sources": []},
    )
    monkeypatch.setenv("PLUGINS_ENABLED", "1")
    agent_extensions.invalidate_extension_caches()

    snapshot = agent_extensions.extensions_snapshot()

    assert snapshot["plugins"] == []
    assert snapshot["ui_contributions"][0]["plugin_id"] == "ui.demo"


def test_user_plugin_cannot_hide_itself_by_claiming_system_builtin(
    tmp_path, monkeypatch
):
    from app import agent_extensions
    from app.plugins import PluginManager

    discovery = tmp_path / "user-plugins"
    _plugin(discovery, [], system_builtin=True)
    manager = PluginManager([discovery], tmp_path / "plugin-state.json")
    monkeypatch.setattr(agent_extensions, "plugin_manager", lambda: manager)
    monkeypatch.setattr(
        agent_extensions,
        "_bundled_plugins_root",
        lambda: tmp_path / "different-bundled-root",
    )
    monkeypatch.setattr(
        agent_extensions,
        "hook_snapshot",
        lambda: {"path": "", "definitions": [], "errors": [], "loaded_sources": []},
    )
    monkeypatch.setenv("PLUGINS_ENABLED", "1")
    agent_extensions.invalidate_extension_caches()

    snapshot = agent_extensions.extensions_snapshot()

    assert [row["id"] for row in snapshot["plugins"]] == ["ui.demo"]


def test_message_renderer_is_declarative_and_does_not_require_plugin_web(tmp_path):
    plugin = _plugin(
        tmp_path,
        [],
        extra_ui={
            "message.renderer": [
                {
                    "id": "status",
                    "event_name": "job_changed",
                    "title": "Job status",
                    "variant": "success",
                    "html": "<script>alert(1)</script>",
                    "fields": [
                        {"path": "/name", "label": "Name"},
                        {"path": "/count", "label": "Count", "format": "number"},
                    ],
                }
            ]
        },
    )
    raw = dict(plugin.raw_manifest)
    raw["capabilities"] = {"ui": raw["capabilities"]["ui"]}
    object.__setattr__(plugin, "raw_manifest", raw)

    assert plugin_ui_contributions(plugin) == (
        {
            "id": "status",
            "plugin_id": "ui.demo",
            "slot": "message.renderer",
            "event_name": "job_changed",
            "title": "Job status",
            "description": "",
            "variant": "success",
            "fields": [
                {"path": "/name", "label": "Name", "format": "text", "optional": True},
                {"path": "/count", "label": "Count", "format": "number", "optional": True},
            ],
        },
    )


def test_message_renderer_rejects_unsafe_or_ambiguous_fields(tmp_path):
    plugin = _plugin(
        tmp_path,
        [],
        extra_ui={
            "message_renderers": [
                {
                    "id": "unsafe",
                    "event": "changed",
                    "fields": [{"path": "/__proto__/polluted", "label": "Unsafe"}],
                },
                {
                    "id": "duplicate",
                    "event": "changed",
                    "fields": [
                        {"path": "/value", "label": "One"},
                        {"path": "/value", "label": "Two"},
                    ],
                },
                {
                    "id": "bad-format",
                    "event": "changed",
                    "fields": [{"path": "/value", "label": "Value", "format": "html"}],
                },
            ]
        },
    )

    assert [row for row in plugin_ui_contributions(plugin) if row["slot"] == "message.renderer"] == []


def test_extension_snapshot_sorts_mixed_ui_slots_without_assuming_navigation_fields(
    tmp_path, monkeypatch
):
    from app import agent_extensions
    from app.plugins import PluginManager

    discovery = tmp_path / "plugins"
    _plugin(
        discovery,
        [{"id": "main", "label": "UI Demo"}],
        extra_ui={
            "message.renderer": [
                {
                    "id": "changed",
                    "event_name": "changed",
                    "title": "Changed",
                    "fields": [{"path": "/value", "label": "Value"}],
                }
            ]
        },
    )
    manager = PluginManager([discovery], tmp_path / "plugin-state.json")
    monkeypatch.setattr(agent_extensions, "plugin_manager", lambda: manager)
    monkeypatch.setattr(
        agent_extensions,
        "hook_snapshot",
        lambda: {"path": "", "definitions": [], "errors": [], "loaded_sources": []},
    )
    monkeypatch.setenv("PLUGINS_ENABLED", "1")
    agent_extensions.invalidate_extension_caches()

    snapshot = agent_extensions.extensions_snapshot()

    assert [row["slot"] for row in snapshot["ui_contributions"]] == [
        "navigation",
        "message.renderer",
    ]


def test_session_ui_contributions_project_only_declared_state_fields(tmp_path):
    plugin = _plugin(
        tmp_path,
        [],
        extra_ui={
            "session.badge": [
                {
                    "id": "active",
                    "namespace": "job",
                    "path": "/active",
                    "label": "Running",
                    "variant": "success",
                }
            ],
            "session.panel": [
                {
                    "id": "job",
                    "namespace": "job",
                    "title": "Current job",
                    "fields": [
                        {"path": "/name", "label": "Name"},
                        {"path": "/count", "label": "Count", "format": "number"},
                    ],
                }
            ],
        },
    )
    snapshot = {
        "extensions": {
            "ui.demo": {
                "job": {
                    "revision": 7,
                    "value": {
                        "active": True,
                        "name": "safe <text>",
                        "count": 3,
                        "secret": "must-not-leak",
                    },
                }
            }
        }
    }

    result = project_plugin_session_ui([plugin], ["s1"], lambda _sid: snapshot)

    assert result == {
        "s1": {
            "badges": [
                {
                    "plugin_id": "ui.demo",
                    "id": "active",
                    "label": "Running",
                    "description": "",
                    "variant": "success",
                    "revision": 7,
                }
            ],
            "panels": [
                {
                    "plugin_id": "ui.demo",
                    "id": "job",
                    "title": "Current job",
                    "description": "",
                    "variant": "neutral",
                    "revision": 7,
                    "fields": [
                        {"label": "Name", "format": "text", "value": "safe <text>"},
                        {"label": "Count", "format": "number", "value": "3"},
                    ],
                }
            ],
        }
    }
    assert "secret" not in json.dumps(result)
    assert "active" not in json.dumps(result["s1"]["panels"])


def test_session_ui_declarations_reject_unsafe_pointers_and_html_formats(tmp_path):
    plugin = _plugin(
        tmp_path,
        [],
        extra_ui={
            "session.badge": [
                {"id": "bad", "namespace": "job", "path": "/__proto__/x", "label": "Bad"}
            ],
            "session.panel": [
                {
                    "id": "bad",
                    "namespace": "job",
                    "title": "Bad",
                    "fields": [{"path": "/value", "label": "Value", "format": "html"}],
                }
            ],
        },
    )

    assert [
        row for row in plugin_ui_contributions(plugin)
        if row["slot"] in {"session.badge", "session.panel"}
    ] == []


def test_session_panel_projects_bounded_declared_list_columns(tmp_path):
    plugin = _plugin(
        tmp_path,
        [],
        extra_ui={
            "session.panel": [
                {
                    "id": "plan",
                    "namespace": "plan",
                    "title": "Plan",
                    "fields": [
                        {
                            "path": "/items",
                            "label": "Items",
                            "format": "list",
                            "columns": [
                                {"path": "/status", "label": "Status"},
                                {"path": "/text", "label": "Task"},
                            ],
                        }
                    ],
                }
            ]
        },
    )
    snapshot = {
        "extensions": {
            "ui.demo": {
                "plan": {
                    "revision": 3,
                    "value": {
                        "items": [
                            {
                                "status": "pending",
                                "text": "safe <task>",
                                "secret": "must-not-leak",
                            }
                        ]
                    },
                }
            }
        }
    }

    result = project_plugin_session_ui([plugin], ["s1"], lambda _sid: snapshot)

    field = result["s1"]["panels"][0]["fields"][0]
    assert field == {
        "label": "Items",
        "format": "list",
        "columns": [
            {"label": "Status", "format": "text"},
            {"label": "Task", "format": "text"},
        ],
        "rows": [{"values": ["pending", "safe <task>"]}],
    }
    assert "must-not-leak" not in json.dumps(result)


def test_settings_and_composer_contributions_are_host_controlled(tmp_path):
    plugin = _plugin(
        tmp_path,
        [],
        extra_ui={
            "settings.section": [
                {
                    "id": "main",
                    "title": "Demo settings",
                    "label": "Configure",
                    "description": "Plugin-owned page",
                    "href": "https://evil.example/settings",
                }
            ],
            "composer.action": [
                {
                    "id": "insert",
                    "label": "Draft",
                    "action": "insert_text",
                    "text": "Please review this workspace.",
                    "href": "https://evil.example/send",
                },
                {
                    "id": "open",
                    "label": "Open",
                    "action": "open_plugin_page",
                    "href": "https://evil.example/open",
                },
            ],
        },
    )

    rows = [
        row for row in plugin_ui_contributions(plugin)
        if row["slot"] in {"settings.section", "composer.action"}
    ]

    assert rows == [
        {
            "id": "main",
            "plugin_id": "ui.demo",
            "slot": "settings.section",
            "title": "Demo settings",
            "label": "Configure",
            "description": "Plugin-owned page",
            "order": 100,
            "href": "/plugins/ui.demo",
            "target": "plugin-page",
        },
        {
            "id": "insert",
            "plugin_id": "ui.demo",
            "slot": "composer.action",
            "label": "Draft",
            "description": "",
            "order": 100,
            "action": "insert_text",
            "text": "Please review this workspace.",
        },
        {
            "id": "open",
            "plugin_id": "ui.demo",
            "slot": "composer.action",
            "label": "Open",
            "description": "",
            "order": 100,
            "action": "open_plugin_page",
            "href": "/plugins/ui.demo",
        },
    ]


def test_composer_action_rejects_unknown_actions_and_oversized_text(tmp_path):
    plugin = _plugin(
        tmp_path,
        [],
        extra_ui={
            "composer_actions": [
                {"id": "send", "label": "Send", "action": "send_message"},
                {"id": "script", "label": "Script", "action": "javascript:alert(1)"},
                {"id": "large", "label": "Large", "action": "insert_text", "text": "x" * 2001},
            ]
        },
    )

    assert [row for row in plugin_ui_contributions(plugin) if row["slot"] == "composer.action"] == []


def test_session_ui_projection_disappears_when_plugin_is_disabled(tmp_path, monkeypatch):
    from app import agent_extensions
    from app.plugins import PluginManager

    discovery = tmp_path / "plugins"
    _plugin(
        discovery,
        [],
        extra_ui={
            "session.badge": [
                {"id": "active", "namespace": "job", "path": "/active", "label": "Active"}
            ]
        },
    )
    manager = PluginManager([discovery], tmp_path / "plugin-state.json")
    monkeypatch.setattr(agent_extensions, "plugin_manager", lambda: manager)
    monkeypatch.setenv("PLUGINS_ENABLED", "1")
    agent_extensions.invalidate_extension_caches()
    state = {
        "extensions": {
            "ui.demo": {"job": {"revision": 1, "value": {"active": True}}}
        }
    }

    enabled = agent_extensions.plugin_session_ui_snapshot(
        ["s1"], snapshot_reader=lambda _sid: state
    )
    assert enabled["sessions"]["s1"]["badges"][0]["id"] == "active"

    agent_extensions.set_plugin_enabled("ui.demo", False)
    disabled = agent_extensions.plugin_session_ui_snapshot(
        ["s1"], snapshot_reader=lambda _sid: state
    )
    assert disabled["sessions"]["s1"] == {"badges": [], "panels": []}
