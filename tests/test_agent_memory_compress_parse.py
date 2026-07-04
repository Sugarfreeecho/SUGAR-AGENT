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
