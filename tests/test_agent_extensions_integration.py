import json
import asyncio
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


def test_global_hook_switch_prevents_project_and_plugin_execution(tmp_path, monkeypatch):
    import agent_extensions

    sentinel = tmp_path / "must-not-exist.txt"
    _write_json(
        tmp_path / "hooks.json",
        {
            "version": 1,
            "hooks": {
                "PreToolUse": [
                    {
                        "id": "disabled-hook",
                        "matcher": "run_shell",
                        "command": f'echo executed > "{sentinel}"',
                        "failure_policy": "block",
                    }
                ]
            },
        },
    )
    monkeypatch.setattr(agent_extensions, "_project_root", lambda: tmp_path)
    monkeypatch.setenv("HOOKS_ENABLED", "0")
    monkeypatch.setenv("HOOKS_PATH", str(tmp_path / "hooks.json"))
    monkeypatch.setenv("PLUGINS_ENABLED", "0")
    agent_extensions.invalidate_extension_caches()

    result = asyncio.run(
        agent_extensions.dispatch_hook(
            "PreToolUse",
            {"tool_name": "run_shell", "tool_input": {"command": "echo unsafe"}},
        )
    )

    assert result.enabled is False
    assert result.skipped is True
    assert not sentinel.exists()


def test_extensions_management_page_and_routes_are_wired():
    html = (ROOT / "app/templates/extensions_config.html").read_text(encoding="utf-8")
    webui = (ROOT / "app/webui.py").read_text(encoding="utf-8")
    frontend = (ROOT / "frontend/src/app/modules/settings.js").read_text(encoding="utf-8")

    assert "HOOKS_ENABLED" in html and "PLUGINS_ENABLED" in html
    assert '@fastapi_app.get("/api/extensions")' in webui
    assert '@fastapi_app.post("/api/extensions/reload")' in webui
    assert '@fastapi_app.post("/api/plugins/{plugin_id}/enabled")' in webui
    assert "settings-extensions" not in frontend
    advanced = (ROOT / "app/templates/advance_config.html").read_text(encoding="utf-8")
    setup_i18n = (ROOT / "app/templates/static/setup_i18n.js").read_text(encoding="utf-8")
    assert advanced.count('data-settings-tab=') == 2
    assert advanced.count('data-settings-panel=') == 2
    assert 'data-settings-tab="model"' in advanced
    assert 'data-settings-tab="advanced"' in advanced
    assert 'data-advanced-tab="env"' in advanced
    assert 'data-advanced-tab="mcp"' in advanced
    assert 'data-advanced-tab="extensions"' in advanced
    assert 'data-advanced-panel="mcp"' in advanced
    assert 'h==="#extensions"' in advanced
    assert "async function loadExtensions()" in advanced
    assert "async function loadMcpConfig()" in advanced
    assert 'fetch("/api/mcp_config"' in advanced
    assert "'扩展管理':'Extension management'" in setup_i18n
    assert "'已注册 Hooks':'Registered hooks'" in setup_i18n
    assert "'插件状态已更新。':'Plugin state updated.'" in setup_i18n
    assert 'id="wizard-language-toggle"' in advanced
    assert 'extText("正在加载扩展…","Loading extensions…")' in advanced


def test_advanced_env_api_synthesizes_feature_switches_when_missing(tmp_path, monkeypatch):
    import webui

    env_path = tmp_path / ".env"
    env_path.write_text(
        "EXECUTOR_LLM=test-model\nOPENAI_API_KEY=legacy-key\nWORK_DIR=./workspace\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(webui, "dotenv_file_path", lambda: env_path)

    response = asyncio.run(webui.get_env_snapshot())
    payload = json.loads(response.body)
    variables = {
        row["key"]: row
        for group in payload["groups"]
        for row in group["vars"]
    }

    assert variables["GOAL_ENABLED"]["value"] == "1"
    assert variables["HOOKS_ENABLED"]["value"] == "1"
    assert variables["PLUGINS_ENABLED"]["value"] == "1"
    assert "EXECUTOR_LLM" not in variables
    assert "OPENAI_API_KEY" not in variables


def test_setup_gate_depends_only_on_usable_model_profile(monkeypatch):
    import webui

    monkeypatch.setattr(webui.model_profiles, "sorted_profiles", lambda _root: [])
    assert webui._is_configured() is False

    monkeypatch.setattr(
        webui.model_profiles,
        "sorted_profiles",
        lambda _root: [{
            "id": "profile-a",
            "model": "model-a",
            "llm_type": "openai",
            "base_url": "https://api.example.com/v1",
            "api_key": "key",
            "context_window": 128000,
            "max_output_tokens": 8192,
        }],
    )
    assert webui._is_configured() is True


def test_setup_saves_model_to_profile_not_dotenv(tmp_path, monkeypatch):
    import webui

    class Request:
        async def json(self):
            return {
                "llm_provider": "openai",
                "llm_base_url": "https://api.example.com/v1",
                "api_key": "profile-key",
                "model_name": "model-a",
                "context_window": "128000",
                "max_output_tokens": "8192",
                "work_dir": "./workspace",
                "search_provider": "duckduckgo",
            }

    env_path = tmp_path / ".env"
    monkeypatch.setattr(webui, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(webui, "dotenv_file_path", lambda: env_path)
    monkeypatch.setattr(webui, "refresh_executor_client_from_env", lambda: None)
    monkeypatch.setattr(webui, "_invalidate_executor_config_cache", lambda *_args: None)

    result = asyncio.run(webui.save_config(Request()))

    assert result["ok"] is True
    env_text = env_path.read_text(encoding="utf-8")
    assert "WORK_DIR=./workspace" in env_text
    assert "EXECUTOR_LLM" not in env_text
    assert "OPENAI_API_KEY" not in env_text
    profiles = webui.model_profiles.sorted_profiles(tmp_path)
    assert len(profiles) == 1
    assert profiles[0]["model"] == "model-a"
    assert profiles[0]["api_key"] == "profile-key"


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
