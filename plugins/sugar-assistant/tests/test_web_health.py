import os

from sugar_assistant import panel, web_sender


def test_available_rejects_profile_without_cookies(tmp_path, monkeypatch):
    profile = tmp_path / "profile"
    profile.mkdir()
    cfg = {"enabled": True, "tenant": "x.feishu.cn", "profile": str(profile),
           "headless": True, "timeout_ms": 1000, "allow": []}
    ok, why = web_sender.WebSender(cfg).available()
    assert not ok and "Cookie" in why


def test_warning_when_user_mode_without_web(monkeypatch):
    monkeypatch.setattr(panel, "web_status", lambda: {"enabled": False, "available": False, "reason": ""})
    monkeypatch.setattr(panel, "web_api_status", lambda: {"ready": False})
    monkeypatch.setattr("sugar_assistant.identity.current", lambda: "user")
    warns = panel.config_warnings()
    assert any("账户主身份" in w for w in warns)


def test_warning_when_web_enabled_but_unavailable(monkeypatch):
    monkeypatch.setattr(panel, "web_status", lambda: {"enabled": True, "available": False, "reason": "no cookies"})
    monkeypatch.setattr("sugar_assistant.identity.current", lambda: "bot")
    warns = panel.config_warnings()
    assert any("no cookies" in w for w in warns)
