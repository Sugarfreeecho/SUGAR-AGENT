import sys
from pathlib import Path

import pytest

from session_control.errors import ControlError
from session_control.policy import Principal, validate_policy

sys.path.insert(0, str(Path(__file__).parent))
from test_session_control import composed, run_async  # noqa: E402,F401


def _plugin_principal(root):
    return Principal("sugar-assistant", policy=validate_policy({"scope": "workspace"}, workspace=str(root)))


@run_async
async def test_group_session_shared_from_same_source(composed):
    c = composed
    response = await c.control.service.execute(
        c.admin, "session.create", {"work_dir": str(c.root)}, idempotency_key="mk-group")
    sid = response[0]["session_id"]
    meta = c.manager._load_metadata(sid)
    meta["origin"] = "sugar-assistant"
    meta["created_by"] = "sugar:feishu:first"
    c.manager._save_metadata(sid, meta)

    principal = _plugin_principal(c.root)
    # 同来源群成员：应放行
    c.service._enforce_actor_scope(
        principal, {"_level": "group", "_subject": "sugar:feishu:second",
                    "_source": {"id": "sugar-assistant"}}, sid)

    # 不同来源：仍拒绝
    meta["origin"] = "control"
    c.manager._save_metadata(sid, meta)
    with pytest.raises(ControlError) as exc:
        c.service._enforce_actor_scope(
            principal, {"_level": "group", "_subject": "sugar:feishu:second",
                        "_source": {"id": "sugar-assistant"}}, sid)
    assert exc.value.code == "scope_denied"
