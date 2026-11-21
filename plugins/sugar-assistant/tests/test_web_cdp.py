"""CDP 接管模式：不需要二次扫码，直接使用已登录的 Edge。"""

from sugar_assistant import web_sender


def test_available_reports_cdp_unreachable():
    cfg = {"enabled": True, "tenant": "x.feishu.cn", "profile": "unused",
           "cdp_url": "http://127.0.0.1:9", "headless": True, "timeout_ms": 1000, "allow": []}
    ok, why = web_sender.WebSender(cfg).available()
    assert not ok and "CDP" in why


def test_config_has_cdp_default(monkeypatch, tmp_path):
    monkeypatch.setattr(web_sender, "_config_path", lambda: str(tmp_path / "web.json"))
    cfg = web_sender.load_config()
    assert cfg["cdp_url"] == ""
