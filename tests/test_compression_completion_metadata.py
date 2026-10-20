"""A token-limited summary must not be mistaken for a plain XML format error."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))


def test_executor_stream_preserves_length_finish_and_usage(monkeypatch):
    import agent_harness

    def worker(sync_q, *_args, **_kwargs):
        sync_q.put(("content", "<recap>unfinished"))
        sync_q.put(("usage", {"completion_tokens": 16384, "prompt_tokens": 129942}))
        sync_q.put(("finish", {"finish_reason": "length", "model": "deepseek-v4.1-flash-free"}))
        sync_q.put(None)

    monkeypatch.setattr(agent_harness, "resolve_executor_config_for_session", lambda _s: (None, "fixture", 20000, 180000))
    monkeypatch.setattr(agent_harness, "run_chat_completion_stream_worker", worker)
    info = {}
    text = agent_harness.executor_chat_complete_stream([], completion_info=info)
    assert text == "<recap>unfinished"
    assert info == {"finish_reason": "length", "model": "deepseek-v4.1-flash-free",
                    "usage": {"completion_tokens": 16384, "prompt_tokens": 129942}}


def test_executor_buffered_complete_response_keeps_finish_metadata(monkeypatch):
    from types import SimpleNamespace
    import agent_harness

    def worker(sync_q, *_a, **_kw):
        sync_q.put(("complete_response", SimpleNamespace(
            model="fixture", usage=SimpleNamespace(completion_tokens=16384, prompt_tokens=100, total_tokens=16484),
            choices=[SimpleNamespace(finish_reason="length", message=SimpleNamespace(
                content="partial", reasoning_content="thinking", tool_calls=None))],
        )))
        sync_q.put(None)

    monkeypatch.setattr(agent_harness, "resolve_executor_config_for_session", lambda _s: (None, "fixture", 20000, 180000))
    monkeypatch.setattr(agent_harness, "run_chat_completion_stream_worker", worker)
    info = {}
    assert agent_harness.executor_chat_complete_stream([], completion_info=info) == "partial"
    assert info["finish_reason"] == "length" and info["usage"]["completion_tokens"] == 16384


def test_executor_nonstream_preserves_finish_metadata(monkeypatch):
    import agent_harness

    monkeypatch.setattr(agent_harness, "executor_one_shot_complete", lambda *_a, **_k: {
        "text": "partial", "finish_reason": "length", "usage": {"completion_tokens": 16384}, "model": "fixture",
    })
    info = {}
    assert agent_harness.executor_chat_complete([], completion_info=info) == "partial"
    assert info["finish_reason"] == "length" and info["usage"]["completion_tokens"] == 16384


def test_truncated_summary_retry_reduces_output_target_and_completes(monkeypatch):
    import agent_memory

    calls, frames = [], []
    monkeypatch.setattr(agent_memory, "load_prompt_template", lambda *_a: "compress")

    def complete(messages, **kwargs):
        calls.append(messages)
        assert "timeout" not in kwargs
        if len(calls) == 1:
            kwargs["completion_info"].update(finish_reason="length", usage={"completion_tokens": 16384})
            return "<recap>unfinished"
        assert "输出 token 上限" in messages[-1].content
        assert "8192 token" in messages[-1].content
        assert "闭合两个标签" in messages[-1].content
        kwargs["completion_info"].update(finish_reason="stop", usage={"completion_tokens": 1000})
        return "<recap>finished recap</recap><summary>- finished key</summary>"

    monkeypatch.setattr(agent_memory, "executor_chat_complete", complete)
    result = agent_memory._run_compress_executor_dialogue(
        "old key", [agent_memory.UserMessage(content="history")], hint_sink=frames.append,
    )
    assert result == ("finished recap", "- finished key")
    assert len(calls) == 2
    assert any("输出达到 token 上限" in str(frame) for frame in frames)


def test_length_finish_with_complete_summary_needs_no_retry(monkeypatch):
    import agent_memory

    calls = []
    monkeypatch.setattr(agent_memory, "load_prompt_template", lambda *_a: "compress")

    def complete(_messages, **kwargs):
        calls.append(1)
        kwargs["completion_info"].update(finish_reason="length")
        return "<recap>finished recap</recap><summary>- finished key</summary>"

    monkeypatch.setattr(agent_memory, "executor_chat_complete", complete)
    assert agent_memory._run_compress_executor_dialogue("", [agent_memory.UserMessage(content="history")]) == (
        "finished recap", "- finished key",
    )
    assert len(calls) == 1
