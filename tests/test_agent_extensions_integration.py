import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _make_full_plugin(discovery: Path) -> Path:
    root = discovery / "bundle"
    _write_json(
        root / ".myagent-plugin" / "plugin.json",
        {
            "schema_version": 1,
            "id": "demo.bundle",
            "name": "Demo Bundle",
            "version": "1.0.0",
            "skills": ["./skills"],
            "hooks": "./hooks/hooks.json",
            "mcp_servers": {
                "servers": {"echo": {"command": "demo-mcp", "args": []}}
            },
            "agents": ["./agents"],
            "prompts": ["./prompts"],
        },
    )
    skill = root / "skills" / "review" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(
        "---\nname: review\ndescription: Review safely\n---\n\nReview instructions.",
        encoding="utf-8",
    )
    _write_json(root / "hooks" / "hooks.json", {"version": 1, "hooks": {}})
    (root / "agents").mkdir()
    (root / "agents" / "reviewer.md").write_text("Review as an agent.", encoding="utf-8")
    (root / "prompts").mkdir()
    (root / "prompts" / "finish.md").write_text("Finish the task.", encoding="utf-8")
    return root


def test_plugin_components_merge_into_host_registries(tmp_path, monkeypatch):
    import agent_extensions
    import agent_mcp
    import agent_tools
    from plugins import PluginManager

    discovery = tmp_path / "plugins"
    _make_full_plugin(discovery)
    manager = PluginManager([discovery], tmp_path / "plugin-state.json")
    monkeypatch.setenv("PLUGINS_ENABLED", "1")
    monkeypatch.setenv("HOOKS_ENABLED", "1")
    monkeypatch.setattr(agent_extensions, "plugin_manager", lambda: manager)
    monkeypatch.setattr(agent_extensions, "_project_root", lambda: tmp_path)
    monkeypatch.setattr(agent_tools, "SKILLS_DIR", tmp_path / "project-skills")
    monkeypatch.setattr(agent_mcp, "_config_path", lambda: tmp_path / "missing-mcp.json")
    agent_extensions.invalidate_extension_caches()
    agent_tools.invalidate_skills_cache()

    loaded = agent_extensions.load_plugins(force=True)
    assert set(loaded.skill_directories) == {"demo.bundle:review"}
    assert set(loaded.mcp_servers) == {"demo.bundle/echo"}
    assert len(loaded.hook_sources) == 1

    discovered = {item["name"]: item for item in agent_tools.discover_skills()}
    assert discovered["demo.bundle:review"]["source"] == "plugin"
    assert discovered["demo.bundle:reviewer"]["source"] == "plugin_agent"
    assert discovered["demo.bundle:finish"]["source"] == "plugin_prompt"
    assert "Review as an agent" in agent_tools.activate_skill("demo.bundle:reviewer")

    servers, error = agent_mcp._load_servers_dict_from_config()
    assert error is None
    assert servers["demo.bundle/echo"]["command"] == "demo-mcp"
    assert agent_extensions.hook_snapshot()["loaded_sources"] == [
        "plugin:demo.bundle:hooks"
    ]


def test_global_plugin_switch_removes_every_component(tmp_path, monkeypatch):
    import agent_extensions
    from plugins import PluginManager

    discovery = tmp_path / "plugins"
    _make_full_plugin(discovery)
    manager = PluginManager([discovery], tmp_path / "plugin-state.json")
    monkeypatch.setattr(agent_extensions, "plugin_manager", lambda: manager)
    agent_extensions.invalidate_extension_caches()

    monkeypatch.setenv("PLUGINS_ENABLED", "1")
    assert agent_extensions.load_plugins().plugins
    # A switch change must invalidate the effective cache key immediately,
    # without waiting for the hot-path TTL.
    monkeypatch.setenv("PLUGINS_ENABLED", "0")

    loaded = agent_extensions.load_plugins()
    assert loaded.globally_enabled is False
    assert loaded.plugins == ()
    assert loaded.skill_directories == {}
    assert loaded.hook_sources == ()
    assert loaded.mcp_servers == {}
    assert agent_extensions.plugin_instruction_resources() == {}


def test_extensions_management_page_and_routes_are_wired():
    html = (ROOT / "app/templates/extensions_config.html").read_text(encoding="utf-8")
    webui = (ROOT / "app/webui.py").read_text(encoding="utf-8")
    frontend = (ROOT / "frontend/src/app/modules/settings.js").read_text(encoding="utf-8")

    assert "HOOKS_ENABLED" in html and "PLUGINS_ENABLED" in html
    assert '@fastapi_app.get("/api/extensions")' in webui
    assert '@fastapi_app.post("/api/extensions/reload")' in webui
    assert '@fastapi_app.post("/api/plugins/{plugin_id}/enabled")' in webui
    assert "window.open('/setup/extensions'" in frontend


def test_agent_loop_wires_hooks_before_safety_approval_and_across_lifecycles():
    source = (ROOT / "app/agent_loop.py").read_text(encoding="utf-8")
    wrapper = source.split("async def execute_one(tool_call):", 1)[1].split(
        "# ---------- 2.6 调用 LLM", 1
    )[0]
    core = source.split("async def _execute_one_core(tool_call):", 1)[1].split(
        "async def execute_one(tool_call):", 1
    )[0]

    assert wrapper.index('"PreToolUse"') < wrapper.index("_execute_one_core(call)")
    assert 'call["args"] = tool_args' in wrapper
    assert 'call["_hook_approval_spec"]' in wrapper
    assert 'hook_approval_spec = tool_call.get("_hook_approval_spec")' in core
    assert "hook_approval_spec or _tool_ui_approval_spec" in core
    for event in (
        "PostToolUse",
        "PostToolUseFailure",
        "SubagentStart",
        "SubagentStop",
        "PreCompact",
        "PostCompact",
        "GoalCreated",
        "GoalBeforeContinue",
        "GoalCompleted",
        "GoalBlocked",
        "SessionStart",
        "SessionEnd",
        "UserPromptSubmit",
        "Stop",
        "RunFailed",
    ):
        assert f'"{event}"' in source
