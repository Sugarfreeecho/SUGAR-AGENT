import json
import time

from sugar_assistant import web_sender


def _sample():
    stamp = time.strftime("%Y-%m-%d %H:%M", time.localtime())  # 用当前时间，避免用例随时间失效
    return {
        "ok": True,
        "data": {
            "messages": [
                {"content": "木薯煮糖水？那我周日有口福了", "message_id": "om_ok",
                 "create_time": stamp,
                 "sender": {"id": "ou_me", "sender_type": "user"}},
                {"content": "别人说的", "message_id": "om_other",
                 "create_time": stamp,
                 "sender": {"id": "ou_other", "sender_type": "user"}},
            ]
        },
    }


def _patch(monkeypatch, payload):
    monkeypatch.setattr(web_sender, "self_open_id", lambda: "ou_me")
    monkeypatch.setattr(web_sender, "_cli", lambda args, timeout=120: json.dumps(payload, ensure_ascii=False))


def test_verify_matches_self_message(monkeypatch):
    _patch(monkeypatch, _sample())
    hit = web_sender.verify_sent("oc_x", "木薯煮糖水？那我周日有口福了", time.time() - 60)
    assert hit == "om_ok"


def test_verify_ignores_other_sender(monkeypatch):
    _patch(monkeypatch, _sample())
    assert web_sender.verify_sent("oc_x", "别人说的", time.time() - 60) == ""


def test_verify_ignores_stale_message(monkeypatch):
    _patch(monkeypatch, _sample())
    stale = time.time() + 3600
    assert web_sender.verify_sent("oc_x", "木薯煮糖水？那我周日有口福了", stale) == ""


def test_available_requires_tenant_and_profile(monkeypatch):
    cfg = {"enabled": True, "tenant": "", "profile": "x", "headless": True, "timeout_ms": 1000, "allow": []}
    ok, why = web_sender.WebSender(cfg).available()
    assert not ok and "租户" in why

