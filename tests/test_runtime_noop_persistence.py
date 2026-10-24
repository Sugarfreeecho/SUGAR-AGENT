import asyncio
from types import SimpleNamespace

import pytest


def test_unchanged_summary_persist_does_not_reopen_write_fence(monkeypatch):
    import agent_loop as agent
    monkeypatch.setattr(agent, "_runtime_v2_is_primary", lambda: True)
    monkeypatch.setattr(agent, "_RUNTIME_V2_COMMITTED_SUMMARY", {"s": "summary"})
    monkeypatch.setattr(agent, "_state_run_has_write_fence", lambda state: pytest.fail("no fact to write"))
    monkeypatch.setattr(agent, "derive_dialogue_from_assistant_history", lambda history: ["derived"])
    state = {"session_id": "s", "llm_history": [], "key_context": "summary"}
    agent._persist_session_messages(state)
    assert state["dialogue"] == ["derived"]


def test_changed_summary_still_refuses_a_lost_fence(monkeypatch):
    import agent_loop as agent
    monkeypatch.setattr(agent, "_runtime_v2_is_primary", lambda: True)
    monkeypatch.setattr(agent, "_RUNTIME_V2_COMMITTED_SUMMARY", {"s": "old"})
    checks = []
    monkeypatch.setattr(agent, "_state_run_has_write_fence", lambda state: checks.append(True) or False)
    monkeypatch.setattr(agent, "_runtime_v2_react_history_ops", lambda: pytest.fail("stale summary wrote facts"))
    agent._persist_session_messages({"session_id": "s", "llm_history": [], "key_context": "new"})
    assert checks == [True]
    assert agent._RUNTIME_V2_COMMITTED_SUMMARY == {"s": "old"}


def test_changed_summary_is_durable_after_fresh_fence_check(tmp_path, monkeypatch):
    import agent_loop as agent
    from runtime_v2 import RuntimeHistoryOps
    ops = RuntimeHistoryOps(tmp_path)
    ops.append_model_message("s", "user", "question")
    monkeypatch.setenv("RUNTIME_V2_ASYNC_SNAPSHOT_CHECKPOINTS", "false")
    monkeypatch.setattr(agent, "_runtime_v2_is_primary", lambda: True)
    monkeypatch.setattr(agent, "_RUNTIME_V2_COMMITTED_SUMMARY", {})
    monkeypatch.setattr(agent, "session_manager", SimpleNamespace(sessions_dir=tmp_path))
    monkeypatch.setattr(agent, "_runtime_v2_react_history_ops", lambda: ops)
    checks = []
    monkeypatch.setattr(agent, "_state_run_has_write_fence", lambda state: checks.append(True) or True)
    agent._persist_session_messages({"session_id": "s", "llm_history": [], "key_context": "new"})
    assert checks == [True]
    assert ops.event_log.read_all("s")[-1].type == "context_summary_committed"
    assert agent._RUNTIME_V2_COMMITTED_SUMMARY == {"s": "new"}


def test_legacy_persistence_still_checks_ownership(monkeypatch):
    import agent_loop as agent
    monkeypatch.setattr(agent, "_runtime_v2_is_primary", lambda: False)
    monkeypatch.setattr(agent, "_state_run_has_write_fence", lambda state: False)
    monkeypatch.setattr(agent, "session_manager", SimpleNamespace(update_session=lambda *a, **k: pytest.fail("stale legacy write")))
    agent._persist_session_messages({"session_id": "s", "llm_history": []})


def test_hook_dispatch_reuses_its_loaded_catalog_and_force_still_reloads(tmp_path, monkeypatch):
    import agent_extensions as extensions
    from plugins import PluginManager
    monkeypatch.setenv("PLUGINS_ENABLED", "0")
    loaded = PluginManager([tmp_path / "plugins"], tmp_path / "plugin-state.json").load_enabled()
    loads = []
    monkeypatch.setattr(extensions, "load_plugins", lambda **k: loads.append(k) or loaded)
    monkeypatch.setattr(extensions, "_runtime_hook_definitions", lambda value: ())
    monkeypatch.setattr(extensions, "_project_root", lambda: tmp_path)
    monkeypatch.setenv("HOOKS_PATH", str(tmp_path / "hooks.json"))
    async def exercise():
        await extensions.dispatch_hook("PostToolUse", {"tool_name": "read_file"})
        assert loads == [{"refresh_loop": asyncio.get_running_loop()}]
        extensions.hook_manager_for_current_loop(force=True, runtime_definitions=(), loaded=loaded)
        assert loads[-1] == {"force": True}
    asyncio.run(exercise())


def test_completed_tool_batch_is_durable_before_return_and_fence_loss_stops_it(tmp_path, monkeypatch):
    import agent_loop as agent
    from runtime_v2 import RuntimeHistoryOps
    ops = RuntimeHistoryOps(tmp_path)
    monkeypatch.setattr(agent, "_runtime_v2_is_primary", lambda: True)
    monkeypatch.setattr(agent, "_runtime_v2_react_history_ops", lambda: ops)
    messages = [agent.ToolMessage(content="first", tool_call_id="a"),
                agent.ToolMessage(content="second", tool_call_id="b")]
    state = {"session_id": "s", "_runtime_v2_run_id": "r"}
    monkeypatch.setattr(agent, "_state_run_has_write_fence", lambda state: False)
    with pytest.raises(asyncio.CancelledError):
        agent._persist_completed_tool_batch(state, messages)
    assert not ops.event_log.event_path("s").exists()
    monkeypatch.setattr(agent, "_state_run_has_write_fence", lambda state: True)
    assert agent._persist_completed_tool_batch(state, messages)
    assert [e.payload["tool_call_id"] for e in ops.event_log.read_all("s")] == ["a", "b"]
    assert state["_last_tool_result_committed_perf"] > 0
    assert not agent._persist_completed_tool_batch(state, messages[:1])
