import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


def test_parse_compress_output_reuses_recap_when_summary_missing():
    import agent_memory

    recap, summary = agent_memory._parse_compress_dialogue_output(
        "<recap>保留历史前情</recap>"
    )

    assert recap == "保留历史前情"
    assert summary == "保留历史前情"


def test_parse_compress_output_reuses_summary_when_recap_missing():
    import agent_memory

    recap, summary = agent_memory._parse_compress_dialogue_output(
        "<summary>保留关键要点</summary>"
    )

    assert recap == "保留关键要点"
    assert summary == "保留关键要点"


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
