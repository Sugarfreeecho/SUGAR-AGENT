"""回归：思考（reasoning）流式分片必须保留原始空白，与回复（content）口径一致。

背景与方案见 workspace/思考换行排查/思考换行修复方案.md：
DeepSeek 系渠道按「逐词分片、空白挂词首词尾」推流，若采集层对每段 delta
都 strip()，思考文本会丢光空格与换行，而回复文本不会。
"""
from types import SimpleNamespace

from app.agent_openai import _extract_reasoning_text_and_field


def _delta(text):
    return SimpleNamespace(reasoning_content=text, reasoning=None, content=None)


def test_reasoning_delta_keeps_word_leading_space():
    text, field = _extract_reasoning_text_and_field(_delta(" user"), keep_ws=True)
    assert field == "reasoning_content"
    assert text == " user"


def test_whitespace_only_delta_is_not_dropped():
    text, _ = _extract_reasoning_text_and_field(_delta("\n\n"), keep_ws=True)
    assert text == "\n\n"


def test_stream_reassembly_matches_original_text():
    pieces = ["The", " user", " wants", " me", " to", " reply", ".\n\n", "Next", " para", "."]
    joined = ""
    for p in pieces:
        text, _ = _extract_reasoning_text_and_field(_delta(p), keep_ws=True)
        assert text is not None
        joined += text
    assert joined == "The user wants me to reply.\n\nNext para."


def test_default_mode_still_edges_strip():
    text, _ = _extract_reasoning_text_and_field(_delta("  hello  "))
    assert text == "hello"
