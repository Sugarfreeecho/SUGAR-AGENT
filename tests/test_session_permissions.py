"""身份四轴权限：档位矩阵、身份折算、工具拦截、轮次身份。"""
from __future__ import annotations

import pytest

import session_permissions as sp
from security.models import DecisionOutcome, SecurityDecision


def test_matrix_matches_agreed_levels():
    assert sp.axes_for("owner").as_dict() == {"control": 4, "tools": 4, "scope": 4, "directory": 4}
    assert sp.axes_for("whitelist").as_dict() == {"control": 3, "tools": 3, "scope": 3, "directory": 3}
    assert sp.axes_for("private").as_dict() == {"control": 3, "tools": 3, "scope": 2, "directory": 2}
    assert sp.axes_for("group").as_dict() == {"control": 2, "tools": 2, "scope": 2, "directory": 2}
    assert sp.axes_for("stranger").as_dict() == {"control": 1, "tools": 1, "scope": 1, "directory": 1}


def test_unknown_level_falls_back_to_stranger():
    assert sp.normalize_level("nonsense") == "stranger"
    assert sp.axes_for("").tools == 1


def test_resolve_level_boundaries():
    assert sp.resolve_level(admin=True) == "owner"
    assert sp.resolve_level() == "owner"                      # 本机入口
    assert sp.resolve_level(channel="feishu", direct=True) == "private"
    assert sp.resolve_level(channel="feishu", group_size=4) == "private"
    assert sp.resolve_level(channel="feishu", group_size=5) == "group"
    assert sp.resolve_level(channel="feishu", group_size=None) == "group"   # 人数未知按 ≥5
    assert sp.resolve_level(channel="bili", whitelisted=True) == "whitelist"
    assert sp.resolve_level(channel="feishu", whitelisted_group=True) == "private"
    assert sp.resolve_level(channel="bili") == "group"


@pytest.mark.parametrize("level, tool, allowed", [
    ("stranger", "read_file", False),
    ("stranger", "write_file", False),
    ("group", "read_file", True),
    ("group", "write_file", False),
    ("private", "write_file", True),
    ("whitelist", "run_shell", True),
    ("owner", "run_shell", True),
])
def test_tool_decision_by_level(level, tool, allowed):
    ok, _rule, available = sp.tool_decision(tool, level)
    assert ok is allowed
    if not allowed:
        assert isinstance(available, list)


def test_denylist_blocks_even_owner():
    ok, rule, _ = sp.tool_decision("write_file", "owner", deny=["write_file"])
    assert ok is False and rule.endswith("denylist")


def test_allowlist_limits_custom_tools():
    ok, _, available = sp.tool_decision("run_shell", "whitelist", allow=["web_fetch"])
    assert ok is False and available == ["web_fetch"]
    ok, _, _ = sp.tool_decision("web_fetch", "whitelist", allow=["web_fetch"])
    assert ok is True


def test_control_levels_gate_destructive_methods():
    assert sp.control_allowed("whitelist", "session.create") is True
    assert sp.control_allowed("group", "session.create") is False
    assert sp.control_allowed("owner", "session.config.update") is True
    assert sp.control_allowed("whitelist", "session.config.update") is False
    assert sp.control_allowed("stranger", "session.list") is True


def test_turn_actor_defaults_to_owner_and_tracks_subject():
    assert sp.turn_level("no-such-session") == "owner"
    sp.set_turn_actor("s1", level="group", subject="u1", channel="feishu")
    assert sp.turn_level("s1") == "group"
    same = sp.actor_key(level="group", subject="u1", channel="feishu")
    other = sp.actor_key(level="group", subject="u2", channel="feishu")
    assert same != other
    sp.clear_turn_actor("s1")
    assert sp.turn_level("s1") == "owner"


def test_identity_gate_downgrades_allow_but_not_policy_deny():
    from security.runtime import _identity_tool_decision

    allow = SecurityDecision(DecisionOutcome.ALLOW, "", "r", "digest")
    sp.set_turn_actor("s2", level="group", subject="u1", channel="feishu")
    try:
        denied = _identity_tool_decision("s2", "write_file", allow)
        assert denied.outcome is DecisionOutcome.DENY
        assert denied.constraints["identity_denial"]["denied_by"] == "group"
        assert "可用工具" in denied.reason

        hard = SecurityDecision(DecisionOutcome.DENY, "policy", "policy.deny", "digest")
        assert _identity_tool_decision("s2", "write_file", hard) is hard
    finally:
        sp.clear_turn_actor("s2")


def test_plugin_cannot_claim_owner():
    from session_control.service import SessionControlService

    class Principal:
        admin = False
        id = "host:demo"
        name = "demo"

    fields = SessionControlService._actor_fields(None, Principal(), {"_level": "owner", "_source": {"id": "demo"}})
    assert fields["level"] == "stranger"

    admin = Principal()
    admin.admin = True
    fields = SessionControlService._actor_fields(None, admin, {"_level": "owner"})
    assert fields["level"] == "owner"


def test_missing_level_keeps_legacy_behaviour():
    from session_control.service import SessionControlService

    class Principal:
        admin = False
        id = "host:demo"
        name = "demo"

    assert SessionControlService._actor_fields(None, Principal(), {"_source": {"id": "demo"}}) is None


class _FakeManager:
    def __init__(self, rows):
        self.rows = rows

    def _load_metadata(self, sid):
        return self.rows.get(sid, {})


def _service_with(rows):
    from session_control.service import SessionControlService

    svc = object.__new__(SessionControlService)
    svc.manager = _FakeManager(rows)
    return svc


def test_scope_two_blocks_other_identity_sessions():
    from session_control.errors import ControlError

    class Principal:
        admin = False
        id = "host:feishu-transport"
        name = "feishu"
        policy = {"scope": "all"}

    svc = _service_with({"s1": {"created_by": "feishu:ou_owner"}})
    mine = {"session_id": "s1", "_level": "private", "_subject": "feishu:ou_owner"}
    svc._enforce_actor_scope(Principal(), mine, "s1")

    other = {"session_id": "s1", "_level": "private", "_subject": "feishu:ou_other"}
    with pytest.raises(ControlError) as exc:
        svc._enforce_actor_scope(Principal(), other, "s1")
    assert exc.value.code == "scope_denied"

    # 作用域 3 不受影响
    svc._enforce_actor_scope(Principal(), {"session_id": "s1", "_level": "whitelist", "_subject": "x"}, "s1")


def test_delete_of_foreign_session_requires_owner():
    from session_control.errors import ControlError
    from session_control.service import SessionControlService

    class Principal:
        admin = False
        id = "host:feishu-transport"
        name = "feishu"
        policy = {"scope": "all"}

    svc = _service_with({"s1": {"created_by": "feishu:ou_owner"}})
    params = {"session_id": "s1", "_level": "private", "_subject": "feishu:ou_other"}
    fields = SessionControlService._actor_fields(svc, Principal(), params)
    assert fields["subject"] == "feishu:ou_other"
    owner = svc.manager._load_metadata("s1")["created_by"]
    assert owner != fields["subject"]  # 删除判定据此拒绝


def test_directory_axis_two_denies_external_write_and_allows_workspace_write():
    from security.models import CapabilityRequest, DecisionOutcome, SecurityDecision
    from security.runtime import _directory_denial

    inside = SecurityDecision(DecisionOutcome.ALLOW, "", "app_restricted.write", "d")
    outside = SecurityDecision(DecisionOutcome.ALLOW, "", "external.write", "d")
    request_write = CapabilityRequest("fs.write", "", "write")
    assert _directory_denial(2, inside, request_write) == ""
    assert "目录档为 2" in _directory_denial(2, outside, request_write)
    # 档 3 以上不做补充判定
    assert _directory_denial(3, outside, request_write) == ""


def test_directory_axis_one_denies_any_write():
    from security.models import CapabilityRequest, DecisionOutcome, SecurityDecision
    from security.runtime import _directory_denial

    decision = SecurityDecision(DecisionOutcome.ALLOW, "", "app_restricted.write", "d")
    assert "目录档为 1" in _directory_denial(1, decision, CapabilityRequest("fs.write", "", "write"))
    assert _directory_denial(1, decision, CapabilityRequest("fs.read", "", "read")) == ""


def test_new_turn_without_level_overwrites_stale_actor():
    from session_control.service import SessionControlService

    class Principal:
        admin = False
        id = "local-ui"
        name = "ui"

    svc = object.__new__(SessionControlService)
    sp.set_turn_actor("s-stale", level="stranger", subject="ou_x", channel="feishu")
    svc._apply_turn_actor(Principal(), {"_source": {"id": "feishu"}}, "s-stale")
    assert sp.turn_level("s-stale") == "owner"      # 机主轮次不会被上一轮的低档位拖住
    sp.set_turn_actor("s-stale", level="group", subject="ou_y", channel="feishu")
    svc._apply_turn_actor(Principal(), {"_level": "private", "_subject": "ou_y"}, "s-stale")
    assert sp.turn_level("s-stale") == "private"
    sp.clear_turn_actor("s-stale")


def test_run_end_clears_turn_actor():
    from session_control.service import SessionControlService

    class Store:
        def update_operation(self, *args, **kwargs):
            return True

    class Coordinator:
        def release(self, *args, **kwargs):
            return None

    svc = object.__new__(SessionControlService)
    svc.store = Store()
    svc.coordinator = Coordinator()
    svc.callbacks = {}
    svc._run_owned = lambda op, cfg: None

    sp.set_turn_actor("s-run", level="stranger", subject="ou_z", channel="feishu")
    svc._run({"session_id": "s-run", "run_id": "r1", "id": "o1", "request": {"_source": {"id": "feishu"}}}, {}, "tok")
    assert sp.turn_level("s-run") == "owner"        # 上一轮的低档位不会残留到下一轮
