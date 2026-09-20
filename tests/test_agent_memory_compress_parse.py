import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


def test_parse_compress_output_requires_summary_tag():
    import agent_memory

    recap, summary = agent_memory._parse_compress_dialogue_output(
        "<recap>history recap</recap>"
    )

    assert recap == "history recap"
    assert summary == ""


def test_parse_compress_output_requires_recap_tag():
    import agent_memory

    recap, summary = agent_memory._parse_compress_dialogue_output(
        "<summary>key facts</summary>"
    )

    assert recap == ""
    assert summary == "key facts"


def test_compress_quality_rejects_draft_planning_inside_valid_tags():
    import agent_memory

    issue = agent_memory._compress_dialogue_quality_issue(
        "（草稿）先覆盖旧摘要。再想想开头几句。",
        "- stable fact",
    )

    assert "draft marker" in issue


def test_compress_executor_retries_draft_then_accepts_finished_answer(monkeypatch):
    import agent_memory

    outputs = iter([
        "<recap>（草稿）再想想开头几句。</recap><summary>- provisional</summary>",
        "<recap>finished recap</recap><summary>- finished key</summary>",
    ])
    calls = []
    monkeypatch.setattr(agent_memory, "load_prompt_template", lambda *_args: "compress")

    def fake_complete(messages, session_id=""):
        calls.append(messages)
        return next(outputs)

    monkeypatch.setattr(agent_memory, "executor_chat_complete", fake_complete)

    recap, key = agent_memory._run_compress_executor_dialogue(
        "",
        [agent_memory.UserMessage(content="old")],
    )

    assert (recap, key) == ("finished recap", "- finished key")
    assert len(calls) == 2
    assert "不要写草稿" in str(calls[1][-1].content)


def test_round_policy_can_fall_through_from_user_turn_to_react_steps():
    import agent_memory

    work = [agent_memory.UserMessage(content="one long turn")]
    for idx in range(12):
        work.append(agent_memory.AssistantMessage(content=f"step {idx}"))

    prefix2, _tail2 = agent_memory._split_prefix_tail_for_summary_round(work, 2, 1)
    prefix3, tail3 = agent_memory._split_prefix_tail_for_summary_round(work, 3, 1)

    assert prefix2 == []
    assert [m.content for m in prefix3] == ["step 0", "step 1"]
    assert isinstance(tail3[0], agent_memory.UserMessage)
    assert len([m for m in tail3 if isinstance(m, agent_memory.AssistantMessage)]) == 10


def test_compress_flow_uses_react_step_round_when_user_round_has_no_prefix(monkeypatch):
    import agent_memory

    history = [agent_memory.UserMessage(content="one long turn")]
    history.extend(
        agent_memory.AssistantMessage(content=f"step {idx}")
        for idx in range(12)
    )
    invoked_rounds = []

    monkeypatch.setattr(agent_memory, "_full_pack_tokens_for_session_preview", lambda *_a, **_k: 1000)
    monkeypatch.setattr(agent_memory, "_full_pack_tokens_compress_work", lambda *_a, **_k: 1000)
    monkeypatch.setattr(
        agent_memory,
        "_compress_ratio_reached",
        lambda *_a, **_k: bool(invoked_rounds),
    )
    monkeypatch.setattr(agent_memory, "_upsert_compress_summary_key_context", lambda *_a, **_k: "key")

    def fake_round(_key, prefix, tail, **kwargs):
        invoked_rounds.append(kwargs["round_idx"])
        assert len(prefix) == 2
        assert isinstance(tail[0], agent_memory.UserMessage)
        return "recap", "key", []

    monkeypatch.setattr(agent_memory, "_compress_summary_round", fake_round)

    _out, _key, changed, _hints, used_summary, _recap = agent_memory._compress_unified_in_place(
        history,
        "session-1",
        "",
        force_user_compact=True,
    )

    assert invoked_rounds == [3]
    assert changed is True
    assert used_summary is True


def test_phase_d_shrinks_orphan_tool_messages():
    import agent_memory

    msg = agent_memory.ToolMessage(content="x" * 1000, tool_call_id="missing")
    work, changed = agent_memory._apply_phase_d([msg], 1)

    assert changed is True
    assert len(str(work[0].content)) < 1000


def test_phase_e_shrinks_incomplete_non_user_block():
    import agent_memory

    work = [
        agent_memory.ToolMessage(content="x" * 1000, tool_call_id="orphan"),
        agent_memory.AssistantMessage(content="y" * 1000),
    ]

    out, changed = agent_memory._apply_phase_e(work, len(work))

    assert changed is True
    assert len(str(out[0].content)) < 1000
    assert len(str(out[1].content)) < 1000


def test_context_policy_stops_before_compaction_when_run_is_interrupted():
    import agent_memory

    history = [agent_memory.UserMessage(content="keep me")]
    out, key_context, changed, _hints, used_summary, recap = agent_memory.run_context_policy(
        history,
        "facts",
        "s1",
        force_user_compact=True,
        should_stop=lambda: True,
    )

    assert [message.content for message in out] == ["keep me"]
    assert key_context == "facts"
    assert changed is False
    assert used_summary is False
    assert recap is None


def test_max_rounds_fallback_without_dropping_does_not_mark_truncated():
    import agent_memory

    hist = [agent_memory.UserMessage(content="short")]

    out, changed, dropped = agent_memory.compress_tail_fallback(
        hist,
        reason="max_rounds",
        max_tokens=100_000,
    )

    assert changed is True
    assert dropped is False
    assert len(out) == 1
    assert str(out[0].content) == "short"
    assert not any("Conversation truncated" in str(getattr(m, "content", "")) for m in out)


def test_context_window_override_drives_auto_compress_entry(monkeypatch):
    import agent_memory

    hist = [
        agent_memory.UserMessage(content="one"),
        agent_memory.AssistantMessage(content="answer"),
        agent_memory.UserMessage(content="two"),
        agent_memory.AssistantMessage(content="answer"),
    ]

    monkeypatch.setattr(agent_memory, "CONTEXT_WINDOW", 1_000_000)
    monkeypatch.setattr(agent_memory, "_full_pack_tokens_for_session_preview", lambda *a, **k: 100)

    assert agent_memory.context_will_attempt_compress(
        hist,
        "00000000-0000-0000-0000-000000000001",
        force_user_compact=False,
        key_context="",
    ) is False
    assert agent_memory.context_will_attempt_compress(
        hist,
        "00000000-0000-0000-0000-000000000001",
        force_user_compact=False,
        key_context="",
        context_window=50,
    ) is True


def test_compress_completion_uses_local_entry_baseline_not_context_window(monkeypatch):
    import agent_memory

    monkeypatch.setattr(
        agent_memory,
        "_full_pack_tokens_compress_work",
        lambda *_args, **_kwargs: 55,
    )

    # N / A = 55 / 100 is already below 60%, even if a separately measured
    # auto-entry T was above a much larger model context window.
    assert agent_memory._compress_ratio_reached("s1", [], "", 100) is True
    assert agent_memory._compress_ratio_reached("s1", [], "", 90) is False


def test_compress_executor_stream_delta_is_forwarded_live(monkeypatch):
    import agent_memory

    order = []

    monkeypatch.setattr(agent_memory, "load_prompt_template", lambda _name: "compress")

    def fake_stream(_msgs, on_content_delta=None, session_id=""):
        if on_content_delta:
            on_content_delta("<recap>live")
        order.append("executor_after_delta")
        return "<recap>live recap</recap><summary>live key</summary>"

    monkeypatch.setattr(agent_memory, "executor_chat_complete_stream", fake_stream)

    recap, key = agent_memory._run_compress_executor_dialogue(
        "",
        [
            agent_memory.UserMessage(content="old"),
            agent_memory.AssistantMessage(content="answer"),
        ],
        stream_sink=lambda piece: order.append("sink:" + piece),
        session_id="00000000-0000-0000-0000-000000000001",
    )

    assert recap == "live recap"
    assert key == "live key"
    assert order[:2] == ["sink:<recap>live", "executor_after_delta"]


def test_compress_round_archives_prefix_and_exposes_retrieval_ref(monkeypatch):
    import agent_memory

    captured = []
    archive = {
        "archive_id": "archive-1",
        "ref": "history:00000000-0000-0000-0000-000000000001:archive:archive-1",
        "rows": [],
    }

    def fake_archive(_manager, session_id, messages, *, reason):
        captured.append((session_id, list(messages), reason))
        return archive

    monkeypatch.setattr(agent_memory, "archive_messages", fake_archive)
    monkeypatch.setattr(
        agent_memory,
        "_run_compress_executor_dialogue",
        lambda *_args, **_kwargs: ("finished recap", "- key"),
    )

    summary, key, _micro = agent_memory._compress_summary_round(
        "",
        [agent_memory.UserMessage(content="old question")],
        [agent_memory.UserMessage(content="recent question")],
        session_id="00000000-0000-0000-0000-000000000001",
        round_idx=2,
    )

    assert captured[0][2] == "context_summary_round_2"
    assert "history_context(action=read)" in summary
    assert archive["ref"] in summary
    assert key == "- key"
