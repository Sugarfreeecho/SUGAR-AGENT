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
    import webui

    env_path = tmp_path / ".env"
    env_path.write_text("EXISTING=value\n", encoding="utf-8")
    monkeypatch.setattr(webui, "dotenv_file_path", lambda: env_path)

    monkeypatch.delenv("AGENT_TEAM_ENABLED", raising=False)

    initial = _response_json(asyncio.run(webui.get_agent_team_feature()))
    assert initial["enabled"] is False
    assert initial["experimental"] is True

    enabled = _response_json(
        asyncio.run(webui.set_agent_team_feature(_JsonRequest({"enabled": True})))
    )
    assert enabled == {"ok": True, "enabled": True}
    assert "EXISTING=value" in env_path.read_text(encoding="utf-8")
    assert "AGENT_TEAM_ENABLED=1" in env_path.read_text(encoding="utf-8")

    disabled = _response_json(
        asyncio.run(webui.set_agent_team_feature(_JsonRequest({"enabled": False})))
    )
    assert disabled == {"ok": True, "enabled": False}
    assert env_path.read_text(encoding="utf-8").count("AGENT_TEAM_ENABLED=") == 1
    assert "AGENT_TEAM_ENABLED=0" in env_path.read_text(encoding="utf-8")


def test_agent_team_feature_api_rejects_non_boolean():
    import webui

    response = asyncio.run(webui.set_agent_team_feature(_JsonRequest({"enabled": "yes"})))
    assert response.status_code == 400
    assert _response_json(response)["error"] == "enabled must be boolean"


def test_advanced_env_exposes_agent_team_defaults(tmp_path, monkeypatch):
    import webui

    env_path = tmp_path / ".env"
    monkeypatch.setattr(webui, "dotenv_file_path", lambda: env_path)
    payload = _response_json(asyncio.run(webui.get_env_snapshot()))
    values = {
        row["key"]: row["value"]
        for group in payload["groups"]
        for row in group["vars"]
    }
    assert values["AGENT_TEAM_ENABLED"] == "0"
    assert values["AGENT_TEAM_MAX_MEMBERS"] == "4"
    assert values["AGENT_TEAM_MAX_MESSAGES"] == "2000"
    assert values["AGENT_TEAM_PERMISSION_TOOLS"] == "delete_file,web_download"


def test_agent_team_controls_are_present_and_wired():
    shell = (ROOT / "frontend/src/shell-body.html").read_text(encoding="utf-8")
    settings = (ROOT / "frontend/src/app/modules/settings.js").read_text(encoding="utf-8")
    panel = (ROOT / "frontend/src/app/modules/agent-team.js").read_text(encoding="utf-8")
    index = (ROOT / "frontend/src/app/index.js").read_text(encoding="utf-8")

    assert 'id="settings-agent-team-off"' in shell
    assert 'id="settings-agent-team-on"' in shell
    assert "fetch('/api/features/agent-team'" in settings
    assert "void saveAgentTeamFeature(false)" in settings
    assert "void saveAgentTeamFeature(true)" in settings
    assert 'id="settings-agent-team-manage"' in shell
    assert 'id="agent-team-modal-root"' in shell
    assert "async function refreshAgentTeamPanel()" in panel
    assert "resolveAgentTeamPermission" in panel
    assert "agentTeamSource" in index
