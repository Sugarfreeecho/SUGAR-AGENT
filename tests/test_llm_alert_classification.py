# -*- coding: utf-8 -*-
"""Focused tests for LLM error classification (17bea699 alert-spec follow-up).

覆盖：
- 连接类错误 -> NET
- 预算错误（包裹连接 cause）-> NET（而非"未知错误"）
- 独立预算错误 -> BUDGET（不再是 OTHER）
- 无法识别的错误 -> OTHER 兜底
"""

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


class _FakeConnectionError(Exception):
    """Mimics openai.APIConnectionError's message shape for text-based classification."""


def _classify(exc):
    import agent_loop

    return agent_loop._classify_api_error(exc)


def test_connection_error_maps_to_net():
    result = _classify(_FakeConnectionError("Connection error."))
    assert result["code"] == "NET"
    assert result["retry"] == 0
    assert "网络" in result["title"] or "网络" in result["msg"]


def test_budget_wrapped_connection_prefers_net():
    """17bea699 core regression: outer budget RuntimeError carries connection cause."""
    outer = RuntimeError("LLM request budget exhausted before model fallback")
    outer.__cause__ = _FakeConnectionError("Connection error.")
    result = _classify(outer)
    assert result["code"] == "NET", (
        "链路层面的连接错误必须优先于预算错误，才能给出可操作提示"
    )


def test_bare_budget_error_maps_to_budget():
    result = _classify(RuntimeError("LLM request budget exhausted before model fallback"))
    assert result["code"] == "BUDGET"
    assert result["retry"] == 1
    assert "预算" in result["title"]


def test_unknown_error_falls_back_to_other():
    result = _classify(ValueError("something odd happened"))
    assert result["code"] == "OTHER"


def test_priority_specific_code_beats_budget():
    outer = RuntimeError("LLM request budget exhausted before model fallback")
    outer.__cause__ = _FakeConnectionError("read timeout while connecting to provider")
    result = _classify(outer)
    assert result["code"] in {"NET"}


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
