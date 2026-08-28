import asyncio
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


class _JsonRequest:
    def __init__(self, payload):
        self._payload = payload

    async def json(self):
        return self._payload


def _response_json(response) -> dict:
    return json.loads(response.body.decode("utf-8"))


def test_agent_team_config_is_fail_closed():
    from agent_team import AgentTeamDisabledError, agent_team_enabled, require_agent_team_enabled

    for environ in ({}, {"AGENT_TEAM_ENABLED": ""}, {"AGENT_TEAM_ENABLED": "unexpected"}):
        assert agent_team_enabled(environ) is False
        try:
            require_agent_team_enabled(environ)
        except AgentTeamDisabledError:
            pass
        else:
            raise AssertionError("disabled Agent Team operation was not rejected")

    for value in ("1", "true", "TRUE", "yes", "on"):
        assert agent_team_enabled({"AGENT_TEAM_ENABLED": value}) is True
        require_agent_team_enabled({"AGENT_TEAM_ENABLED": value})


def test_agent_team_feature_api_persists_and_applies_immediately(tmp_path, monkeypatch):
    source = (ROOT / "app/webui.py").read_text(encoding="utf-8")
    assert "/api/features/agent-team" not in source
    manifest = json.loads((ROOT / "plugins/agent-team/.myagent-plugin/plugin.json").read_text(encoding="utf-8"))
    assert manifest["id"] == "agent-team"
    assert manifest["capabilities"]["trusted_host"]["entry"] == "host.py"


def test_agent_team_feature_api_rejects_non_boolean():
    source = (ROOT / "app/agent_extensions.py").read_text(encoding="utf-8")
    assert "def set_plugin_enabled(plugin_id: str, enabled: bool)" in source


def test_advanced_env_does_not_synthesize_agent_team_defaults(tmp_path, monkeypatch):
    import webui

    env_path = tmp_path / ".env"
    monkeypatch.setattr(webui, "dotenv_file_path", lambda: env_path)
    payload = _response_json(asyncio.run(webui.get_env_snapshot()))
    values = {
        row["key"]: row["value"]
        for group in payload["groups"]
        for row in group["vars"]
    }
    assert values["SECURITY_ENABLED"] == "1"
    assert values["EGRESS_HELPER_ENABLED"] == "1"
    assert not any(key.startswith("AGENT_TEAM_") for key in values)


def test_agent_team_controls_are_present_and_wired():
    shell = (ROOT / "frontend/src/shell-body.html").read_text(encoding="utf-8")
    settings = (ROOT / "frontend/src/app/modules/settings.js").read_text(encoding="utf-8")
    index = (ROOT / "frontend/src/app/index.js").read_text(encoding="utf-8")
    assert "agent-team" not in shell.lower()
    assert "agent-team" not in settings.lower()
    assert "agentTeamSource" not in index
    assert (ROOT / "plugins/agent-team/web/index.html").is_file()
