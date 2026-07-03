import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

import agent_loop  # noqa: E402


def test_long_tool_result_is_saved_and_ui_matches_llm(tmp_path, monkeypatch):
    monkeypatch.setattr(agent_loop, "LLM_CONTEXT_TRUNCATE_KEEP_CHARS", 40)
    monkeypatch.setattr(
        agent_loop,
        "safe_work_path",
        lambda raw: tmp_path / str(raw).lstrip("/\\"),
    )

    state = {}
    raw = "A" * 45 + "TAIL_SHOULD_NOT_APPEAR"

    _log, llm_view, ui_view = agent_loop._tool_result_details_for_views(
        raw,
        "run_shell",
        state,
    )

    assert ui_view == llm_view
    assert "返回结果已被截断" in llm_view
    assert "完整结果已落盘保存在 /.tool_results/" in llm_view
    assert llm_view.count("返回结果已被截断") == 2
    assert "A" * 20 in llm_view
    assert "TAIL_SHOULD_NOT_APPEAR" not in llm_view

    saved = state["_temporary_write_files"][0]
    assert Path(saved).read_text(encoding="utf-8") == raw


def test_short_tool_result_is_not_truncated_for_ui_or_llm(monkeypatch):
    monkeypatch.setattr(agent_loop, "LLM_CONTEXT_TRUNCATE_KEEP_CHARS", 40)

    state = {}
    raw = "short result"

    _log, llm_view, ui_view = agent_loop._tool_result_details_for_views(
        raw,
        "grep",
        state,
    )

    assert llm_view == raw
    assert ui_view == raw
    assert "_temporary_write_files" not in state
