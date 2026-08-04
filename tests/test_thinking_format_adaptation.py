"""按目标模型自适应思考字段格式的回归测试。

覆盖：
- _profile_thinking_format 的显式配置与模型名推断（mimo 只看模型名，不看 oczen）；
- messages_to_openai_params 在 deepseek/reasoning/think_blocks/none 下的字段与 <think> 处理；
- _remap_serialized_reasoning_format 对 fallback 候选的逐候选转换。
"""

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from agent_harness import (  # noqa: E402
    _profile_thinking_format,
    _remap_serialized_reasoning_format,
)
from agent_messages import AssistantMessage  # noqa: E402
from agent_openai import messages_to_openai_params  # noqa: E402


def _assistant(
    content: str = "",
    *,
    reasoning_content: object = None,
    reasoning: object = None,
    tool_calls: object = None,
    reasoning_field: str = "",
) -> AssistantMessage:
    ak = {}
    if reasoning_content is not None:
        ak["reasoning_content"] = reasoning_content
    if reasoning is not None:
        ak["reasoning"] = reasoning
    if reasoning_field:
        ak["reasoning_field"] = reasoning_field
    return AssistantMessage(
        content=content,
        tool_calls=tool_calls,
        additional_kwargs=ak,
    )


def _field_keys(msg: dict) -> list:
    return [k for k in msg if k not in ("role", "content", "tool_calls")]


class TestProfileThinkingFormat:
    def test_explicit_config_wins(self):
        profile = {"model": "mimo-v2.5-free", "base_url": "https://opencode.ai/zen/v1", "thinking_format": "none"}
        assert _profile_thinking_format(profile) == "none"

    def test_deepseek_by_model_name(self):
        assert _profile_thinking_format({"model": "deepseek-v4-flash", "base_url": "https://api.deepseek.com"}) == "deepseek"
        assert _profile_thinking_format({"model": "deepseek-v4-flash-free", "base_url": "https://opencode.ai/zen/v1"}) == "deepseek"

    def test_mimo_by_model_name_not_oczen(self):
        # mimo 识别只依据模型名；oczen 供应商名/URL 不作为识别依据
        assert _profile_thinking_format({"model": "mimo-v2.5-free", "base_url": "https://opencode.ai/zen/v1"}) == "reasoning"

    def test_unknown_defaults_to_deepseek(self):
        assert _profile_thinking_format({"model": "some-unknown", "base_url": "https://example.com/v1"}) == "deepseek"


class TestSerializeThinkingFormat:
    def test_deepseek_emits_reasoning_content_and_strips_think(self):
        msg = _assistant(
            "answer <think>hidden</think>",
            reasoning_content="trace",
            reasoning_field="reasoning",
            tool_calls=[{"name": "run_shell", "args": {}, "id": "call_1"}],
        )
        out = messages_to_openai_params([msg], thinking_format="deepseek")[0]
        assert out["content"] == "answer"
        assert _field_keys(out) == ["reasoning_content"]
        assert out["tool_calls"][0]["id"] == "call_1"
        assert out["reasoning_content"] == "trace"

    def test_deepseek_ignores_stored_reasoning_field_name(self):
        # 历史轮次由 mimo 产生（reasoning_field=reasoning），发往 DeepSeek 时仍输出 reasoning_content
        msg = _assistant(
            "answer",
            reasoning_content="trace",
            reasoning_field="reasoning",
            tool_calls=[{"name": "run_shell", "args": {}, "id": "call_1"}],
        )
        out = messages_to_openai_params([msg], thinking_format="deepseek")[0]
        assert "reasoning" not in out
        assert out.get("reasoning_content") == "trace"

    def test_deepseek_keeps_empty_string_field(self):
        # DeepSeek 接受空串但拒绝缺失字段
        msg = _assistant("answer", reasoning_content="")
        out = messages_to_openai_params([msg], thinking_format="deepseek")[0]
        assert out.get("reasoning_content") == ""

    def test_reasoning_emits_reasoning_field(self):
        msg = _assistant("answer <think>hidden</think>", reasoning_content="trace")
        out = messages_to_openai_params([msg], thinking_format="reasoning")[0]
        assert out["content"] == "answer"
        assert _field_keys(out) == ["reasoning"]
        assert out["reasoning"] == "trace"

    def test_think_blocks_keeps_content_and_drops_field(self):
        msg = _assistant("answer <think>keep</think>", reasoning_content="trace")
        out = messages_to_openai_params([msg], thinking_format="think_blocks")[0]
        assert out["content"] == "answer <think>keep</think>"
        assert _field_keys(out) == []

    def test_none_strips_everything(self):
        msg = _assistant("answer <think>hidden</think>", reasoning_content="trace")
        out = messages_to_openai_params([msg], thinking_format="none")[0]
        assert out["content"] == "answer"
        assert _field_keys(out) == []

    def test_default_is_deepseek(self):
        msg = _assistant("answer", reasoning_content="trace")
        out = messages_to_openai_params([msg])[0]
        assert out.get("reasoning_content") == "trace"


class TestRemapSerializedReasoning:
    def _canonical(self):
        return [
            {"role": "user", "content": "hi"},
            {
                "role": "assistant",
                "content": "answer <think>hidden</think>",
                "reasoning_content": "trace",
                "tool_calls": [{"id": "call_1"}],
            },
        ]

    def test_remap_to_deepseek(self):
        out = _remap_serialized_reasoning_format(self._canonical(), "deepseek")
        assert out[1]["content"] == "answer"
        assert out[1]["reasoning_content"] == "trace"
        assert "reasoning" not in out[1]

    def test_remap_to_reasoning(self):
        out = _remap_serialized_reasoning_format(self._canonical(), "reasoning")
        assert out[1]["content"] == "answer"
        assert out[1]["reasoning"] == "trace"
        assert "reasoning_content" not in out[1]

    def test_remap_to_think_blocks_keeps_content(self):
        out = _remap_serialized_reasoning_format(self._canonical(), "think_blocks")
        assert out[1]["content"] == "answer <think>hidden</think>"
        assert "reasoning_content" not in out[1]
        assert "reasoning" not in out[1]

    def test_remap_to_none(self):
        out = _remap_serialized_reasoning_format(self._canonical(), "none")
        assert out[1]["content"] == "answer"
        assert "reasoning_content" not in out[1]
        assert "reasoning" not in out[1]

    def test_non_assistant_messages_untouched(self):
        out = _remap_serialized_reasoning_format(self._canonical(), "none")
        assert out[0] == {"role": "user", "content": "hi"}

    def test_empty_string_reasoning_survives(self):
        msgs = [{"role": "assistant", "content": "answer", "reasoning_content": ""}]
        out = _remap_serialized_reasoning_format(msgs, "deepseek")
        assert out[0]["reasoning_content"] == ""
