"""本机令牌与审批卡片身份。"""
from __future__ import annotations

import pytest

import local_access as la


@pytest.fixture(autouse=True)
def isolated_state(monkeypatch, tmp_path):
    monkeypatch.setenv("MYAGENT_SESSION_CONTROL_HOME", str(tmp_path / "state"))
    monkeypatch.delenv("MYAGENT_LOCAL_TOKEN_STRICT", raising=False)
    la.reset_cache()
    yield
    la.reset_cache()


def test_token_is_stable_and_persisted(tmp_path):
    first = la.local_token()
    assert len(first) >= 32
    la.reset_cache()
    assert la.local_token() == first
    assert la.token_path().read_text(encoding="utf-8").strip() == first


def test_reads_and_non_session_paths_are_untouched():
    assert la.check_request("GET", "/sessions", {}) == ""
    assert la.check_request("POST", "/api/skills", {}) == ""


def test_plain_local_client_is_allowed_by_default():
    assert la.check_request("POST", "/sessions", {}) == ""


def test_cross_site_write_is_blocked():
    headers = {"sec-fetch-site": "cross-site", "origin": "http://evil.example"}
    assert la.check_request("POST", "/sessions", headers) == "local_cross_site_blocked"


def test_strict_mode_requires_token_for_browser_calls(monkeypatch):
    monkeypatch.setenv("MYAGENT_LOCAL_TOKEN_STRICT", "1")
    headers = {"sec-fetch-site": "same-origin", "origin": "http://127.0.0.1:8192"}
    assert la.check_request("POST", "/sessions", headers) == "local_token_required"
    token = la.local_token()
    assert la.check_request("POST", "/sessions", {**headers, la.TOKEN_HEADER: token}) == ""
    assert la.check_request("POST", "/sessions", {**headers, la.TOKEN_HEADER: "wrong"}) == "local_token_mismatch"


def test_cookie_token_is_accepted(monkeypatch):
    monkeypatch.setenv("MYAGENT_LOCAL_TOKEN_STRICT", "1")
    token = la.local_token()
    headers = {"sec-fetch-site": "same-origin", "origin": "http://127.0.0.1:8192"}
    assert la.check_request("POST", "/sessions", headers, {la.COOKIE_NAME: token}) == ""


def test_approval_card_carries_turn_actor():
    import session_permissions as sp
    from tool_approval_gate import approval_turn_actor

    sp.set_turn_actor("s-approval", level="group", subject="ou_1", channel="feishu")
    try:
        actor = approval_turn_actor("s-approval")
        assert actor == {"level": "group", "subject": "ou_1", "channel": "feishu"}
    finally:
        sp.clear_turn_actor("s-approval")


def test_approval_card_defaults_to_owner_without_registration():
    from tool_approval_gate import approval_turn_actor

    assert approval_turn_actor("never-registered")["level"] == "owner"
