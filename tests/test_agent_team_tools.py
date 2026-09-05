import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


def _team_definition():
    from agent_extensions import bundled_host_tool_definitions

    return next(
        row
        for row in bundled_host_tool_definitions(session_meta={})
        if (row.get("function") or {}).get("name") == "team"
    )


def test_team_tool_schema_and_feature_gate_are_wired():
    from agent_extensions import bundled_host_tool_definitions

    definition = _team_definition()
    actions = definition["function"]["parameters"]["properties"]["action"]["enum"]
    assert {"create", "spawn_member", "dispatch", "send_message", "shutdown"} <= set(actions)

    assert not any((row.get("function") or {}).get("name") == "team" for row in
        bundled_host_tool_definitions(session_meta={"is_subagent": True, "subagent_type": "generalPurpose"}))
    assert any((row.get("function") or {}).get("name") == "team" for row in
        bundled_host_tool_definitions(session_meta={
                "is_subagent": True,
                "subagent_type": "generalPurpose",
                "agent_team_member_id": "member_1",
        }))

    loop = (APP_DIR / "agent_loop.py").read_text(encoding="utf-8")
    # The team tool lives in plugins/agent-team; agent_loop may pass the
    # session-identity field name through, but must not import/invoke it.
    assert "import agent_team" not in loop
    assert "from agent_team" not in loop
    host_tools = (APP_DIR / "builtin_host_tools.py").read_text(encoding="utf-8")
    assert '_invoke_team' not in host_tools
    assert '"task",\n            _invoke_task' in host_tools
    assert '_invoke_team' in (ROOT / "plugins/agent-team/host.py").read_text(encoding="utf-8")


def test_team_tool_uses_session_derived_identity(tmp_path, monkeypatch):
    from agent_team.service import AgentTeamService
    from agent_team import tools as team_tools

    monkeypatch.setenv("AGENT_TEAM_ENABLED", "1")
    service = AgentTeamService(tmp_path)
    monkeypatch.setattr(team_tools, "_service", lambda: service)

    created = json.loads(
        asyncio.run(team_tools.execute_team_tool({"action": "create"}, session_id="root"))
    )
    assert created["data"]["status"] == "active"
    member = service.add_member("root", name="Coder", role="implementation")

    sent = json.loads(
        asyncio.run(
            team_tools.execute_team_tool(
                {
                    "action": "send_message",
                    "recipient_ids": ["lead"],
                    "content": "ready",
                },
                session_id="child",
                session_meta={
                    "is_subagent": True,
                    "agent_team_root_session_id": "root",
                    "agent_team_member_id": member["member_id"],
                },
            )
        )
    )
    assert sent["data"]["sender_id"] == member["member_id"]
    assert service.list_inbox("root", "lead")[0]["content"] == "ready"


def test_spawned_member_is_bound_to_one_persistent_child_session(tmp_path, monkeypatch):
    import agent_harness
    from agent_team import tools as team_tools
    from agent_team.service import AgentTeamService

    monkeypatch.setenv("AGENT_TEAM_ENABLED", "1")
    service = AgentTeamService(tmp_path)
    service.create_team("root")
    saved = {}

    class FakeSessionManager:
        def create_subagent_session(self, *args, **kwargs):
            return "persistent-child"

        def _load_metadata(self, child_id):
            return {"is_subagent": True, "parent_session_id": "root"}

        def _save_metadata(self, child_id, metadata):
            saved[child_id] = dict(metadata)

    monkeypatch.setattr(agent_harness, "session_manager", FakeSessionManager())
    result = json.loads(
        asyncio.run(
            team_tools._spawn_member(
                service,
                "root",
                name="Coder",
                role="implementation",
                prompt="Own backend work",
                model_profile_id="",
                readonly=False,
            )
        )
    )
    member = result["data"]
    assert member["child_session_id"] == "persistent-child"
    assert member["state"] == "idle"
    assert saved["persistent-child"]["agent_team_member_id"] == member["member_id"]
    assert saved["persistent-child"]["agent_team_root_session_id"] == "root"


def test_dispatch_reuses_the_same_member_session(tmp_path, monkeypatch):
    import agent_subagent
    from agent_team import tools as team_tools
    from agent_team.service import AgentTeamService

    monkeypatch.setenv("AGENT_TEAM_ENABLED", "1")
    service = AgentTeamService(tmp_path)
    service.create_team("root")
    member = service.add_member("root", name="Coder", role="implementation")
    service.bind_member_session("root", member["member_id"], "persistent-child")
    calls = []

    async def fake_run_subagent_task(*, tool_args, **kwargs):
        calls.append(dict(tool_args))
        return "done"

    monkeypatch.setattr(agent_subagent, "run_subagent_task", fake_run_subagent_task)
    for assignment in ("first", "second"):
        result = json.loads(
            asyncio.run(
                team_tools._dispatch_member(
                    service,
                    "root",
                    member_id=member["member_id"],
                    prompt=assignment,
                    task_id="",
                    run_in_background=False,
                    parent_key_context="",
                    emit=None,
                    parent_run_id="run",
                )
            )
        )
        assert result["data"]["child_session_id"] == "persistent-child"

    assert [call["resume"] for call in calls] == ["persistent-child", "persistent-child"]
    assert all(call["action"] == "resume" for call in calls)
    assert service.read_team("root")["members"][member["member_id"]]["state"] == "idle"


def test_dispatch_auto_completes_claimed_task_and_unlocks_dependency(tmp_path, monkeypatch):
    import agent_harness
    import agent_subagent
    from agent_team import tools as team_tools
    from agent_team.service import AgentTeamService

    monkeypatch.setenv("AGENT_TEAM_ENABLED", "1")
    service = AgentTeamService(tmp_path)
    service.create_team("root")
    member = service.add_member("root", name="Coder", role="implementation")
    service.bind_member_session("root", member["member_id"], "persistent-child")
    service.set_member_state("root", member["member_id"], "idle")
    first = service.create_task("root", title="first")
    second = service.create_task(
        "root",
        title="second",
        depends_on=[first["task_id"]],
    )
    service.claim_task("root", first["task_id"], member["member_id"])

    async def fake_run_subagent_task(**_kwargs):
        return "completed output"

    class _SessionManager:
        @staticmethod
        def _load_metadata(_child_id):
            return {"subagent_run_status": "completed"}

    monkeypatch.setattr(agent_subagent, "run_subagent_task", fake_run_subagent_task)
    monkeypatch.setattr(agent_harness, "session_manager", _SessionManager())
    asyncio.run(
        team_tools._dispatch_member(
            service,
            "root",
            member_id=member["member_id"],
            prompt="",
            task_id=first["task_id"],
            run_in_background=False,
            parent_key_context="",
            emit=None,
            parent_run_id="run",
            auto_continue=False,
        )
    )

    team = service.read_team("root")
    assert team["tasks"][first["task_id"]]["status"] == "completed"
    assert team["tasks"][first["task_id"]]["result"] == "completed output"
    assert service.claim_next_task("root", member["member_id"])["task_id"] == second["task_id"]


def test_member_workspace_writes_are_serialized():
    from agent_team.policy import workspace_write_lock

    meta = {
        "agent_team_root_session_id": "root",
        "agent_team_member_id": "member",
    }

    assert workspace_write_lock(meta, "write_file") is workspace_write_lock(meta, "run_shell")
    assert workspace_write_lock(meta, "read_file") is None


def test_workspace_lock_wait_cancellation_does_not_leak():
    from agent_team.policy import acquire_workspace_write_lock
    import threading

    async def scenario():
        lock = threading.Lock()
        lock.acquire()
        waiter = asyncio.create_task(acquire_workspace_write_lock(lock))
        await asyncio.sleep(0.02)
        waiter.cancel()
        lock.release()
        try:
            await waiter
        except asyncio.CancelledError:
            pass
        else:
            raise AssertionError("cancelled lock waiter did not preserve cancellation")
        assert lock.acquire(blocking=False) is True
        lock.release()

    asyncio.run(scenario())
