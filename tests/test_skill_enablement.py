import json
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

import agent_tools


def test_skill_can_be_disabled_and_reenabled_without_deleting_files(monkeypatch, tmp_path):
    skills_dir = tmp_path / "skills"
    skill_dir = skills_dir / "demo"
    skill_dir.mkdir(parents=True)
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text(
        "---\nname: demo\ndescription: Demo skill\n---\n\nFollow the demo instructions.\n",
        encoding="utf-8",
    )
    state_path = tmp_path / "skill_states.json"
    monkeypatch.setattr(agent_tools, "SKILLS_DIR", skills_dir)
    monkeypatch.setattr(agent_tools, "SKILL_STATE_PATH", state_path)
    monkeypatch.setattr(agent_tools, "_plugin_skill_directories", lambda: {})
    monkeypatch.setattr(agent_tools, "_plugin_instruction_entries", lambda: [])
    agent_tools.invalidate_skills_cache()

    assert [skill["name"] for skill in agent_tools.discover_skills()] == ["demo"]
    assert agent_tools.set_skill_enabled("demo", False) is True

    assert agent_tools.discover_skills() == []
    disabled = agent_tools.discover_skills(include_disabled=True)
    assert len(disabled) == 1
    assert disabled[0]["name"] == "demo"
    assert disabled[0]["enabled"] is False
    assert "demo" not in agent_tools.get_skills_catalog()
    assert "not found" in agent_tools.activate_skill("demo")
    assert skill_file.is_file()
    assert json.loads(state_path.read_text(encoding="utf-8"))["skills"]["demo"]["enabled"] is False

    assert agent_tools.set_skill_enabled("demo", True) is True

    assert [skill["name"] for skill in agent_tools.discover_skills()] == ["demo"]
    assert "demo" in agent_tools.get_skills_catalog()
    assert "Follow the demo instructions." in agent_tools.activate_skill("demo")
    assert json.loads(state_path.read_text(encoding="utf-8"))["skills"] == {}
