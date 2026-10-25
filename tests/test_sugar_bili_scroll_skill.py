"""The Skill helper only uses documented local management APIs."""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "plugins/sugar-bili-scroll/skills/bili-scroll"
spec = importlib.util.spec_from_file_location("bili_skill_manage", SKILL / "scripts/manage.py")
manage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manage)


def test_doctor_is_read_only_and_does_not_print_credentials(monkeypatch, capsys):
    seen = []
    def call(base, path, method="GET", body=None):
        seen.append((path, method, body))
        if path.endswith("/status"):
            return {"ok": True, "logged_in": True, "account_uid": "999", "tasks": [],
                    "cookie": "never-print", "transcribe": False}
        if path.endswith("/inbound"):
            return {"enabled": False, "jobs": [{"text": "private-message"}]}
        if path == "/api/mcp/tools":
            return {"servers": [{"server": manage.SERVER, "connected": True, "tool_count": 14}]}
        return {"ok": True, "enabled": True, "state": "ready", "checks": []}
    monkeypatch.setattr(manage, "request", call)
    assert manage.main(["doctor"]) == 0
    output = capsys.readouterr().out
    assert all(method == "GET" for _, method, _ in seen)
    assert "never-print" not in output and "private-message" not in output
    assert json.loads(output)["inbound_enabled"] is False


@pytest.mark.parametrize("registered", [True, False])
def test_register_reports_actual_discovery(monkeypatch, registered):
    seen = []
    def call(base, path, method="GET", body=None):
        seen.append((path, method))
        return {"ok": True, "registered": registered, "server": {"server": manage.SERVER}}
    monkeypatch.setattr(manage, "request", call)
    assert manage.execute("register", "http://localhost:8192")["ok"] is registered
    assert seen == [("/api/mcp/servers/sugar-bili-scroll/bili/register", "POST")]


def test_disable_and_uninstall_do_not_touch_files_or_purge_data(monkeypatch):
    seen = []
    def call(base, path, method="GET", body=None):
        seen.append((path, method, body))
        return {"ok": True, "recoverable": True}
    monkeypatch.setattr(manage, "request", call)
    manage.execute("disable", "http://localhost:8192")
    manage.execute("uninstall", "http://localhost:8192")
    assert seen == [("/api/plugins/sugar-bili-scroll/enabled", "POST", {"enabled": False}),
                    ("/api/plugins/sugar-bili-scroll", "DELETE", None)]


def test_uninstall_failure_is_not_reported_as_success(monkeypatch, capsys):
    def call(*args, **kwargs):
        raise RuntimeError("outside the writable install directory")
    monkeypatch.setattr(manage, "request", call)
    assert manage.main(["uninstall"]) == 1
    assert json.loads(capsys.readouterr().out)["ok"] is False


def test_helper_refuses_remote_origins():
    with pytest.raises(SystemExit):
        manage.main(["--base-url", "https://example.com"])


def test_skill_references_and_admin_guide_match_host_behavior():
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    for name in ["agent-admin", "tool-use", "user-config", "features"]:
        assert f"references/{name}.md" in text
        assert (SKILL / "references" / (name + ".md")).is_file()
    admin = (SKILL / "references/agent-admin.md").read_text(encoding="utf-8")
    assert "DELETE 会拒绝" in admin and "数据" in admin
    assert "会创建诊断会话" in admin
