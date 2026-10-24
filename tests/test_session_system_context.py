import importlib.util
import json
import tempfile
from pathlib import Path
from queue import Queue

import httpx
import pytest
from openai import OpenAI

from session_system_context import MAX_SYSTEM_CONTEXT_BYTES, SYSTEM_CONTEXT_HEADING


@pytest.fixture
def sessions(monkeypatch):
    import agent_harness as harness
    import agent_loop
    import agent_tools
    import webui

    with tempfile.TemporaryDirectory(prefix="sc-") as directory:
        root = Path(directory).resolve()
        manager = harness.SessionManager(root / "sessions", root / "index.json")
        for module in (harness, agent_loop, agent_tools, webui):
            monkeypatch.setattr(module, "WORK_DIR", root)
            if hasattr(module, "session_manager"):
                monkeypatch.setattr(module, "session_manager", manager)
        monkeypatch.setattr(webui, "_is_configured", lambda: True)
        monkeypatch.setattr(webui, "_is_session_stream_active", lambda sid: False)
        monkeypatch.setattr(webui, "_has_local_worker_activity", lambda sid: False)
        yield manager


def prefix(manager, sid):
    import agent_loop

    return agent_loop._build_static_segments_for_session(sid, manager._load_metadata(sid), "zh-CN")


def test_context_persists_without_model_history_and_is_session_local(sessions):
    import agent_harness as harness

    sid, dialogue, work, history, key_context, metadata = sessions.get_or_create_session(system_context="固定章程")
    other = sessions.get_or_create_session()[0]
    assert dialogue == work == history == [] and key_context == ""
    assert metadata["system_context"] == "固定章程"
    fresh = harness.SessionManager(sessions.sessions_dir, sessions.index_file)
    assert fresh.get_or_create_session(sid)[-1]["system_context"] == "固定章程"
    assert prefix(fresh, sid)[-1] == SYSTEM_CONTEXT_HEADING + "固定章程"
    assert all("固定章程" not in segment for segment in prefix(fresh, other))


@pytest.mark.parametrize("value", [None, 1, {}, [], "汉" * (MAX_SYSTEM_CONTEXT_BYTES // 3 + 1)],
                         ids=["null", "integer", "object", "array", "oversized-utf8"])
def test_invalid_context_rejected_before_creation_and_update(sessions, value):
    count = len(list(sessions.sessions_dir.glob("*")))
    with pytest.raises(ValueError, match="system_context"):
        sessions.get_or_create_session(system_context=value)
    assert len(list(sessions.sessions_dir.glob("*"))) == count
    sid = sessions.get_or_create_session(system_context="keep")[0]
    with pytest.raises(ValueError, match="system_context"):
        sessions.set_session_system_context(sid, value)
    assert sessions._load_metadata(sid)["system_context"] == "keep"


def test_update_clear_bypass_static_and_system_message_caches(sessions):
    import agent_loop

    sid = sessions.get_or_create_session(system_context="old charter")[0]
    old_meta = sessions._load_metadata(sid)
    old_key = agent_loop._session_static_cache_key(sid, old_meta)
    old_prefix = prefix(sessions, sid)
    state = {}
    old_messages = agent_loop._request_system_messages(state, list(old_prefix))
    assert agent_loop._request_system_messages(state, list(old_prefix))[-1] is old_messages[-1]
    sessions.set_session_system_context(sid, "new charter")
    new_meta = sessions._load_metadata(sid)
    assert agent_loop._session_static_cache_key(sid, new_meta) != old_key
    new_messages = agent_loop._request_system_messages(state, list(prefix(sessions, sid)))
    assert new_messages[-1].content == SYSTEM_CONTEXT_HEADING + "new charter"
    assert all("old charter" not in m.content for m in new_messages)
    # Repeating an unchanged value must not rewrite metadata.
    assert sessions.set_session_system_context(sid, "new charter")["updated_at"] == new_meta["updated_at"]
    sessions.set_session_system_context(sid, "")
    assert len(prefix(sessions, sid)) == len(old_prefix) - 1
    with pytest.raises(FileNotFoundError):
        sessions.set_session_system_context("00000000-0000-0000-0000-000000000000", "context")


def test_child_and_fork_inherit_once_then_update_and_clear_independently(sessions):
    parent = sessions.get_or_create_session(system_context="parent charter")[0]
    child = sessions.create_subagent_session(parent, "child", "explore", 1)
    fork = sessions.fork_subagent_from_parent(parent, "fork", "generalPurpose", 1,
        parent_runtime_config={"system_segments": list(prefix(sessions, parent)), "system_context": "parent charter"})
    for sid in (child, fork):
        assert sum("parent charter" in s for s in prefix(sessions, sid)) == 1
    sessions.set_session_system_context(parent, "parent changed")
    assert prefix(sessions, child)[-1] == SYSTEM_CONTEXT_HEADING + "parent charter"
    assert prefix(sessions, fork)[-1] == SYSTEM_CONTEXT_HEADING + "parent charter"
    sessions.set_session_system_context(fork, "fork changed")
    assert sum("fork changed" in s for s in prefix(sessions, fork)) == 1
    assert all("parent charter" not in s for s in prefix(sessions, fork))
    sessions.set_session_system_context(fork, "")
    assert all(not s.startswith(SYSTEM_CONTEXT_HEADING) for s in prefix(sessions, fork))
    assert prefix(sessions, parent)[-1] == SYSTEM_CONTEXT_HEADING + "parent changed"


def test_compaction_preserves_instructions_outside_history(sessions):
    from runtime_v2 import RuntimeHistoryOps, RuntimeModelProjection

    sid = sessions.get_or_create_session(system_context="not compressible")[0]
    ops = RuntimeHistoryOps(sessions.sessions_dir, path_resolver=sessions._resolve_session_path)
    ops.append_model_message(sid, "user", "round one")
    ops.replace_model_history(sid, [], reason="test_compaction")
    assert RuntimeModelProjection(sessions.sessions_dir, path_resolver=sessions._resolve_session_path).read_message_dicts(sid) == []
    assert prefix(sessions, sid)[-1] == SYSTEM_CONTEXT_HEADING + "not compressible"


def test_token_estimates_and_breakdown_use_same_context_and_invalidate_cache(sessions, monkeypatch):
    import agent_loop
    import agent_tokenizer as tokenizer

    sid = sessions.get_or_create_session()[0]
    baseline = tokenizer.estimate_full_input_tokens_for_llm_history(sid, [], "")
    text = "固定章程中的约束必须保持。" * 100
    sessions.set_session_system_context(sid, text)
    assert tokenizer.build_session_system_segments(sid) == prefix(sessions, sid)
    added = tokenizer.estimate_full_input_tokens_for_llm_history(sid, [], "")
    assert added > baseline
    lanes = agent_loop.compute_context_breakdown_for_llm_history(sid, "", total_tokens=added)
    assert lanes["system_tokens"] == added
    captured = []
    monkeypatch.setattr(tokenizer, "estimate_full_input_tokens_for_messages",
                        lambda sid, messages, **kw: (captured.extend(messages), (added, "local"))[1])
    assert tokenizer.estimate_hybrid_input_tokens_for_llm_history(sid, [], "") == (added, "local")
    assert captured[-1].content == SYSTEM_CONTEXT_HEADING + text
    sessions.set_session_system_context(sid, "")
    assert tokenizer.estimate_full_input_tokens_for_llm_history(sid, [], "") == baseline


def test_create_and_update_http_contract(sessions, monkeypatch):
    from fastapi.testclient import TestClient
    import webui

    client = TestClient(webui.fastapi_app)
    response = client.post("/sessions", json={"system_context": "api charter"})
    assert response.status_code == 200, response.text
    sid = response.json()["session_id"]
    assert sessions._load_metadata(sid)["system_context"] == "api charter"
    url = f"/sessions/{sid}/system-context"
    assert client.put(url, json={"system_context": "replacement"}).status_code == 200
    assert prefix(sessions, sid)[-1] == SYSTEM_CONTEXT_HEADING + "replacement"
    assert client.put(url, json={"system_context": ""}).status_code == 200
    assert client.put(url, content="{").status_code == 400
    assert client.put(url, json=[]).status_code == 422
    for value in (None, 1, {}, "x" * (MAX_SYSTEM_CONTEXT_BYTES + 1)):
        assert client.post("/sessions", json={"system_context": value}).status_code == 422
        assert client.put(url, json={"system_context": value}).status_code == 422
    unknown = "00000000-0000-0000-0000-000000000000"
    assert client.put(f"/sessions/{unknown}/system-context", json={"system_context": "x"}).status_code == 404
    monkeypatch.setattr(webui, "_is_session_stream_active", lambda sid: True)
    assert client.put(url, json={"system_context": "busy"}).status_code == 409
    assert sessions._load_metadata(sid)["system_context"] == ""


@pytest.mark.parametrize("direct", [False, True])
@pytest.mark.parametrize("mode", ["append", "replace"])
def test_actual_http_body_contains_one_system_charter_and_short_user_round(sessions, monkeypatch, direct, mode):
    import agent_loop
    from agent_harness import RequestResponseLogger, ExecutorLLMClient
    from agent_messages import UserMessage
    from agent_openai import run_chat_completion_stream_worker
    from llm.transport import OpenAICompatibleTransport

    monkeypatch.setenv("LLM_STREAM_PREFER_DIRECT", "1" if direct else "0")
    sid = sessions.get_or_create_session(system_context="固定章程测试正文", system_context_mode=mode)[0]
    bodies = []
    def handle(request):
        bodies.append(json.loads(request.content))
        event = {"id": "c", "object": "chat.completion.chunk", "choices": [{"index": 0, "delta": {"content": "ok"}, "finish_reason": None}]}
        return httpx.Response(200, headers={"content-type": "text/event-stream"},
                              text="data: " + json.dumps(event) + "\n\ndata: [DONE]\n\n")
    with RequestResponseLogger(transport=httpx.MockTransport(handle)) as http:
        sdk = OpenAI(api_key="test", base_url="http://system-context.fixture.invalid/v1", http_client=http, max_retries=0)
        facade = ExecutorLLMClient([{"provider": "openai-compatible", "client": sdk,
            "transport": OpenAICompatibleTransport(sdk), "model": "test-model", "input_modalities": ["text"]}])
        for _ in range(2):
            outgoing = agent_loop._request_system_messages({}, list(prefix(sessions, sid)))
            outgoing.append(UserMessage(content="只含这一轮的参数"))
            queue = Queue()
            run_chat_completion_stream_worker(queue, facade, "test-model", outgoing, temperature=0, max_tokens=16)
            assert any(row[0] == "turn" for row in list(queue.queue))
    assert len(bodies) == 2
    for body in bodies:
        charter = [m for m in body["messages"] if "固定章程测试正文" in str(m["content"])]
        assert len(charter) == 1 and charter[0]["role"] == "system"
        if mode == "replace":
            systems = [m["content"] for m in body["messages"] if m["role"] == "system"]
            assert len(systems) == 2 and systems[0] == "固定章程测试正文"
            assert systems[1].startswith("## Environment")
            assert "run_shell" not in systems[1] and "Skills catalog" not in systems[1]
        assert [m["content"] for m in body["messages"] if m["role"] == "user"] == ["只含这一轮的参数"]


def test_bili_existing_and_new_sessions_use_system_context_and_refresh_charter(sessions, monkeypatch):
    path = Path(__file__).resolve().parents[1] / "plugins/sugar-bili-scroll/host.py"
    spec = importlib.util.spec_from_file_location("test_bili_system_context_host", path)
    host = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(host)
    home = sessions.sessions_dir.parent / "duty-home"
    home.mkdir()
    (home / "duty.md").write_text("独特的章程正文，家目录 <家目录>", encoding="utf-8")
    monkeypatch.setattr(host, "_home", lambda: home)
    monkeypatch.setattr(host, "_write_settings", lambda value: None)
    sid = host._ensure_session({})
    assert sessions._load_metadata(sid)["system_context"] == host.build_system_context()
    assert str(home) in host.build_system_context() and "<家目录>" not in host.build_system_context()
    prompt = host.build_prompt({})
    assert "独特的章程正文" not in prompt and "本轮参数" in prompt
    assert not (home / "charter-sent.json").exists()
    (home / "duty.md").write_text("修改过的章程", encoding="utf-8")
    assert host._ensure_session({"duty_session_id": sid}) == sid
    assert prefix(sessions, sid)[0] == host.build_system_context()
    assert sessions._load_metadata(sid)["system_context_mode"] == "replace"
    legacy = sessions.get_or_create_session()[0]
    assert host._ensure_session({"duty_session_id": legacy}) == legacy
    assert "修改过的章程" in sessions._load_metadata(legacy)["system_context"]


def test_replace_mode_skips_host_templates_and_matches_token_estimates(sessions, monkeypatch):
    import agent_loop
    import agent_tokenizer as tokenizer
    sid = sessions.get_or_create_session(system_context="独立完整提示词", system_context_mode="replace")[0]
    def forbidden(*args, **kwargs):
        pytest.fail("replacement mode must not load ordinary host prompt or skills")
    monkeypatch.setattr(agent_loop, "build_static_system_segments", forbidden)
    monkeypatch.setattr(agent_loop, "get_skills_catalog", forbidden)
    monkeypatch.setattr(tokenizer, "build_static_system_segments", forbidden)
    assert prefix(sessions, sid) == tokenizer.build_session_system_segments(sid)
    assert prefix(sessions, sid)[0] == "独立完整提示词"
    assert tokenizer.estimate_full_input_tokens_for_llm_history(sid, [], "") > 0
    fresh = type(sessions)(sessions.sessions_dir, sessions.index_file)
    assert fresh._load_metadata(sid)["system_context_mode"] == "replace"


def test_mode_switch_with_same_text_invalidates_cache_and_preserves_other_sessions(sessions):
    import agent_loop
    sid = sessions.get_or_create_session(system_context="同一份文字")[0]
    other = sessions.get_or_create_session()[0]
    old_key = agent_loop._session_static_cache_key(sid, sessions._load_metadata(sid))
    other_prefix = prefix(sessions, other)
    sessions.set_session_system_context(sid, "同一份文字", mode="replace")
    assert agent_loop._session_static_cache_key(sid, sessions._load_metadata(sid)) != old_key
    assert prefix(sessions, sid)[0] == "同一份文字"
    assert prefix(sessions, other) == other_prefix
    sessions.set_session_system_context(sid, "后续修改")
    assert sessions._load_metadata(sid)["system_context_mode"] == "replace"
    with pytest.raises(ValueError, match="must not be empty"):
        sessions.set_session_system_context(sid, "")
    sessions.set_session_system_context(sid, "", mode="append")
    assert len(prefix(sessions, sid)) == len(other_prefix)


@pytest.mark.parametrize("mode", [None, "", "invalid", 1, {}, []])
def test_invalid_mode_rejected_before_creation(sessions, mode):
    before = list(sessions.sessions_dir.glob("*/metadata.json"))
    with pytest.raises(ValueError, match="system_context_mode"):
        sessions.get_or_create_session(system_context="提示词", system_context_mode=mode)
    assert list(sessions.sessions_dir.glob("*/metadata.json")) == before


def test_replace_mode_survives_compaction_child_and_fork(sessions):
    from runtime_v2 import RuntimeHistoryOps
    parent = sessions.get_or_create_session(system_context="完整插件角色", system_context_mode="replace")[0]
    child = sessions.create_subagent_session(parent, "child", "explore", 1)
    fork = sessions.fork_subagent_from_parent(parent, "fork", "generalPurpose", 1,
        parent_runtime_config={"system_segments": list(prefix(sessions, parent)),
                               "system_context": "完整插件角色", "system_context_mode": "replace"})
    ops = RuntimeHistoryOps(sessions.sessions_dir, path_resolver=sessions._resolve_session_path)
    ops.append_model_message(parent, "user", "你好")
    ops.replace_model_history(parent, [], reason="test")
    assert prefix(sessions, parent)[0] == "完整插件角色"
    for sid in (child, fork):
        meta = sessions._load_metadata(sid)
        assert meta["system_context_mode"] == "replace"
        assert sum(segment == "完整插件角色" for segment in prefix(sessions, sid)) == 1
        assert not any("## 角色与回答原则" in segment for segment in prefix(sessions, sid))
    sessions.set_session_system_context(fork, "改回普通会话", mode="append")
    assert any("## 角色与回答原则" in segment for segment in prefix(sessions, fork))


def test_replace_mode_http_create_update_validation(sessions):
    from fastapi.testclient import TestClient
    import webui
    client = TestClient(webui.fastapi_app)
    assert client.post("/sessions", json={"system_context_mode": "replace"}).status_code == 422
    assert client.post("/sessions", json={"system_context_mode": "invalid"}).status_code == 422
    response = client.post("/sessions", json={"system_context": "专属角色", "system_context_mode": "replace"})
    assert response.status_code == 200
    sid = response.json()["session_id"]
    assert prefix(sessions, sid)[0] == "专属角色"
    url = f"/sessions/{sid}/system-context"
    response = client.put(url, json={"system_context": "专属新角色"})
    assert response.json()["system_context_mode"] == "replace"
    assert client.put(url, json={"system_context": ""}).status_code == 422
    assert client.put(url, json={"system_context": "", "system_context_mode": "append"}).status_code == 200
