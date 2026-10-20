from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))


def write_skill(root, directory, name, body):
    path = root / directory
    path.mkdir(parents=True)
    (path / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {body}\n---\n\n{body}\n", encoding="utf-8")
    return path


@pytest.fixture
def skill_catalog(monkeypatch, tmp_path):
    import agent_extensions
    import agent_tools

    project = tmp_path / "skills"
    project.mkdir()
    directories = {}
    instructions = {}
    monkeypatch.setattr(agent_tools, "SKILLS_DIR", project)
    monkeypatch.setattr(agent_tools, "SKILL_STATE_PATH", tmp_path / "skill_states.json")
    monkeypatch.setattr(agent_tools, "_plugin_skill_directories", lambda: dict(directories))
    monkeypatch.setattr(agent_extensions, "plugin_instruction_resources", lambda: dict(instructions))
    monkeypatch.setattr(agent_extensions, "plugin_registry_signature", lambda: repr(instructions))
    agent_tools.invalidate_skills_cache()
    yield agent_tools, project, directories, instructions
    agent_tools.invalidate_skills_cache()


def test_plugin_skill_defaults_to_local_name_and_accepts_legacy_activation(skill_catalog, tmp_path):
    skills, _, directories, _ = skill_catalog
    directories["docs:review"] = write_skill(tmp_path, "plugin", "review", "Review documentation")
    entry, = skills.discover_skills()
    assert entry["name"] == "review" and entry["source_name"] == "docs:review"
    assert "Review documentation" in skills.activate_skill("review")
    assert "Review documentation" in skills.activate_skill("docs:review")
    assert "<name>review</name>" in skills.get_skills_catalog()
    assert "<name>docs:review</name>" not in skills.get_skills_catalog()


def test_skill_collisions_keep_project_name_and_all_plugin_instructions(skill_catalog, tmp_path):
    skills, project, directories, _ = skill_catalog
    write_skill(project, "review", "review", "Project instructions")
    directories.update({
        "docs:review": write_skill(tmp_path, "docs", "review", "Docs instructions"),
        "mail:review": write_skill(tmp_path, "mail", "review", "Mail instructions"),
    })
    entries = skills.discover_skills()
    assert {entry["name"] for entry in entries} == {"review", "docs:review", "mail:review"}
    assert "Project instructions" in skills.activate_skill("review")
    assert "Docs instructions" in skills.activate_skill("docs:review")
    assert "Mail instructions" in skills.activate_skill("mail:review")
    directories.clear()
    directories.update({"mail:review": tmp_path / "mail",
                        "docs:review": tmp_path / "docs"})
    skills.invalidate_skills_cache()
    assert {entry["name"] for entry in skills.discover_skills()} == {"review", "docs:review", "mail:review"}


def test_skill_enablement_follows_source_when_display_name_changes(skill_catalog, tmp_path):
    skills, _, directories, _ = skill_catalog
    directories["docs:review"] = write_skill(tmp_path, "docs", "review", "Docs instructions")
    skills.SKILL_STATE_PATH.write_text('{"skills":{"docs:review":{"enabled":false}}}', encoding="utf-8")
    assert skills.discover_skills() == []
    assert skills.discover_skills(include_disabled=True)[0]["name"] == "review"
    assert skills.set_skill_enabled("review", True)
    assert skills.set_skill_enabled("review", False)
    assert json.loads(skills.SKILL_STATE_PATH.read_text())["skills"] == {"docs:review": {"enabled": False}}
    directories["mail:review"] = write_skill(tmp_path, "mail", "review", "Mail instructions")
    assert [entry["name"] for entry in skills.discover_skills()] == ["mail:review"]
    assert "not found" in skills.activate_skill("docs:review")
    assert skills.set_skill_enabled("docs:review", True)
    assert {entry["name"] for entry in skills.discover_skills()} == {"docs:review", "mail:review"}


def test_same_plugin_skill_and_agent_stay_distinct_and_toggle_independently(skill_catalog, tmp_path):
    skills, _, directories, instructions = skill_catalog
    directories["docs:review"] = write_skill(tmp_path, "docs", "review", "Skill body")
    agent = tmp_path / "review.md"
    agent.write_text("Agent body", encoding="utf-8")
    instructions["docs:review"] = ("agent", agent)
    assert {entry["name"] for entry in skills.discover_skills()} == {"docs:skill:review", "docs:agent:review"}
    assert "not found" in skills.activate_skill("docs:review")
    assert skills.set_skill_enabled("docs:review", False) is False
    assert skills.set_skill_enabled("docs:skill:review", False)
    assert [entry["name"] for entry in skills.discover_skills()] == ["docs:agent:review"]
    assert "not found" in skills.activate_skill("docs:review")
    assert "Agent body" in skills.activate_skill("docs:agent:review")
    assert skills.set_skill_enabled("docs:agent:review", False)
    assert skills.discover_skills() == []
    assert skills.set_skill_enabled("docs:agent:review", True)
    assert [entry["name"] for entry in skills.discover_skills()] == ["docs:agent:review"]


def test_duplicate_project_frontmatter_names_do_not_overwrite_instructions(skill_catalog):
    skills, project, _, _ = skill_catalog
    write_skill(project, "first", "review", "First body")
    write_skill(project, "second", "review", "Second body")
    entries = skills.discover_skills()
    assert len(entries) == 2 and len({entry["name"] for entry in entries}) == 2
    assert {entry["body"] for entry in entries} == {"First body", "Second body"}


def hook(plugin, *, hook_id="guard", event="PreToolUse", source=None):
    from hooks import CommandSpec, HookDefinition

    return HookDefinition(id=hook_id, event=event, plugin_id=plugin,
        source_id=source or (f"plugin-runtime:{plugin}" if plugin else "project"),
        command=CommandSpec(command="echo guard"), handler_type="plugin" if plugin else "command",
        handler_ref=hook_id if plugin else "")


def test_hook_names_change_only_on_collision_and_extend_preserves_original_ids(tmp_path):
    from hooks import HookManager

    first, second = hook("docs"), hook("mail")
    manager = HookManager(tmp_path, include_project=False, definitions=[first])
    assert manager.definitions[0].id == "guard"
    manager.extend_definitions([second])
    assert {row.id for row in manager.definitions} == {"docs:guard", "mail:guard"}
    assert all(row.execution_id == "guard" and row.handler_ref == "guard" for row in manager.definitions)
    manager.register(hook(None))
    assert {row.id for row in manager.definitions} == {"guard", "docs:guard", "mail:guard"}
    reversed_manager = HookManager(tmp_path, include_project=False, definitions=[second, first])
    assert {row.plugin_id: row.id for row in reversed_manager.definitions} == {"mail": "mail:guard", "docs": "docs:guard"}


def test_hook_events_disambiguate_ids_within_one_plugin(tmp_path):
    from hooks import HookManager

    manager = HookManager(tmp_path, include_project=False,
        definitions=[hook("docs"), hook("docs", event="PostToolUse")])
    assert {row.id for row in manager.definitions} == {"docs:PreToolUse:guard", "docs:PostToolUse:guard"}


def test_generated_hook_ids_use_local_names_but_keep_legacy_execution_identity(tmp_path):
    from hooks import HookSource, load_hook_sources

    loaded = load_hook_sources(tmp_path, include_project=False, plugin_sources=[HookSource(
        "plugin:docs:hooks", tmp_path, plugin_id="docs",
        config={"hooks": {"PreToolUse": [{"command": "echo guard"}]}})])
    definition, = loaded.definitions
    assert definition.id == "PreToolUse:0:0"
    assert definition.execution_id == "plugin:docs:hooks:PreToolUse:0:0"


def test_renamed_hooks_invoke_original_handlers_and_keep_security_binding(tmp_path):
    from hooks import HookManager
    from plugins.host_hooks import PluginAwareHookExecutor
    from security.runtime import classify_hook

    calls = []

    class Registry:
        def invoke_hook(self, plugin, signature, event, handler, payload, plugins):
            calls.append((plugin, handler, payload["hook"]["id"], payload["hook"]["name"]))
            return {"additional_context": plugin}

    first = hook("docs")
    single = HookManager(tmp_path, include_project=False, definitions=[first]).definitions[0]
    manager = HookManager(tmp_path, include_project=False, definitions=[first, hook("mail")],
        executor=PluginAwareHookExecutor(tmp_path, Registry(), lambda: ()))
    renamed = next(row for row in manager.definitions if row.plugin_id == "docs")
    assert classify_hook(single, {}, tmp_path).metadata["config_digest"] == classify_hook(renamed, {}, tmp_path).metadata["config_digest"]
    result = asyncio.run(manager.dispatch("PreToolUse", {"tool_name": "read_file", "tool_input": {}}))
    assert result.executed_hooks == 2
    assert set(calls) == {("docs", "guard", "guard", "docs:guard"), ("mail", "guard", "guard", "mail:guard")}
    assert {row.hook_id for row in result.results} == {"docs:guard", "mail:guard"}
