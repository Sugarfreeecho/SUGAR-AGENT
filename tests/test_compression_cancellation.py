"""Stopping compression releases its session lock without limiting generation time."""
import sys
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))


@pytest.mark.parametrize("streaming", [False, True])
def test_summary_can_be_cancelled_while_worker_keeps_generating(monkeypatch, streaming):
    import agent_harness

    release, exited = threading.Event(), threading.Event()
    worker_kwargs = []

    def worker(sync_q, *_args, **kwargs):
        worker_kwargs.append(kwargs)
        try:
            while not release.wait(0.005):
                sync_q.put(("reasoning", "still generating"))
        finally:
            exited.set()

    monkeypatch.setattr(agent_harness, "resolve_executor_config_for_session", lambda _sid: (None, "fixture", 200, 1000))
    monkeypatch.setattr(agent_harness, "run_chat_completion_stream_worker", worker)
    started = time.monotonic()
    complete = agent_harness.executor_chat_complete_stream if streaming else agent_harness.executor_chat_complete
    try:
        with pytest.raises(InterruptedError):
            complete([], should_stop=lambda: time.monotonic() - started >= 0.03)
        assert time.monotonic() - started < 1
        assert "request_timeout" not in worker_kwargs[0]
        assert worker_kwargs[0]["should_abort"]()
    finally:
        release.set()
        assert exited.wait(2)


def test_cancelled_summary_does_not_start_another_request(monkeypatch):
    import agent_memory

    monkeypatch.setattr(agent_memory, "load_prompt_template", lambda *_args: "compress")
    monkeypatch.setattr(agent_memory, "executor_chat_complete", lambda *_a, **_k: pytest.fail("unexpected request"))
    assert agent_memory._run_compress_executor_dialogue(
        "previous key", [agent_memory.UserMessage(content="source history")], should_stop=lambda: True,
    ) == ("", "")


def test_empty_summary_key_preserves_existing_key(monkeypatch):
    import agent_memory as memory

    history = [message for i in range(4) for message in (
        memory.UserMessage(content=f"question {i}"), memory.AssistantMessage(content=f"answer {i}"),
    )]
    calls = []
    monkeypatch.setattr(memory, "CONTEXT_WINDOW", 1000)
    monkeypatch.setattr(memory, "CONTEXT_MICRO_WORK_ROUNDS", 0)
    monkeypatch.setattr(memory, "_full_pack_tokens_for_session_preview", lambda *_a, **_k: 1500)
    monkeypatch.setattr(memory, "_full_pack_tokens_compress_work", lambda _s, messages, _k, **_kw: 1500 if len(messages) == 8 else 250)
    monkeypatch.setattr(memory, "_compress_ratio_reached", lambda *_a, **_k: bool(calls))
    monkeypatch.setattr(memory, "_upsert_compress_summary_key_context", lambda *_a, **_k: pytest.fail("must preserve previous key"))

    def summarize(_key, _prefix, _tail, **kwargs):
        calls.append(kwargs)
        return "fallback excerpt", "", []

    monkeypatch.setattr(memory, "_compress_summary_round", summarize)
    _out, key, changed, _hints, _used, _recap = memory._compress_unified_in_place(
        history, "fixture", "previous key", force_user_compact=True,
    )
    assert len(calls) == 1 and changed
    assert key == "previous key"


def test_cancelled_compaction_releases_lock_and_drops_late_output(monkeypatch):
    import agent_harness
    import agent_loop
    import agent_memory

    release, exited, stop = threading.Event(), threading.Event(), threading.Event()
    frames = []
    monkeypatch.setattr(agent_memory, "load_prompt_template", lambda *_a: "compress")
    monkeypatch.setattr(agent_harness, "resolve_executor_config_for_session", lambda _s: (None, "fixture", 200, 1000))

    def worker(sync_q, *_a, **_kw):
        try:
            sync_q.put(("reasoning", "working"))
            stop.set()
            release.wait(2)
            sync_q.put(("content", "late response"))
            sync_q.put(None)
        finally:
            exited.set()

    def policy(history, key, sid, **kwargs):
        return agent_memory._run_compress_executor_dialogue(
            key, history, session_id=sid,
            stream_sink=lambda piece: frames.append(piece),
            hint_sink=kwargs["hint_sink"], should_stop=kwargs["should_stop"],
        )

    monkeypatch.setattr(agent_harness, "run_chat_completion_stream_worker", worker)
    monkeypatch.setattr(agent_loop, "run_context_policy", policy)
    try:
        agent_loop._run_context_policy_serialized(
            [agent_memory.UserMessage(content="source")], "previous key", "cancel-fixture",
            force_user_compact=True, hint_sink=frames.append, should_stop=stop.is_set,
        )
        lock = agent_loop._context_policy_lock_for_session("cancel-fixture")
        assert lock.acquire(blocking=False)
        lock.release()
        before = list(frames)
        release.set()
        assert exited.wait(2)
        assert frames == before
    finally:
        release.set()
