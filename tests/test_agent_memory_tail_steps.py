"""截尾（tail budget）以「步」为单位：不拆开 assistant(tool_calls) 与其 tool 结果。"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


def _hist(am, tool_content=400):
    A, T, U = am.AssistantMessage, am.ToolMessage, am.UserMessage
    return [
        U("start"),
        A("", tool_calls=[{"id": "c1", "name": "run_shell", "args": {}}]),
        T("x" * tool_content, tool_call_id="c1"),
        A("", tool_calls=[{"id": "c2", "name": "read_file", "args": {}}]),
        T("y" * tool_content, tool_call_id="c2"),
        A("final answer"),
    ]


def _assert_chain_valid_from_start(am, tail, mt):
    assert tail, f"mt={mt}: tail unexpectedly empty"
    assert not isinstance(tail[0], am.ToolMessage), f"mt={mt}: tail starts with a tool message"
    seen_ids = set()
    for m in tail:
        if isinstance(m, am.AssistantMessage):
            for tc in m.tool_calls or []:
                tid = str((tc or {}).get("id") or (tc or {}).get("tool_call_id") or "")
                if tid:
                    seen_ids.add(tid)
        elif isinstance(m, am.ToolMessage):
            assert str(m.tool_call_id) in seen_ids, f"mt={mt}: orphan tool {m.tool_call_id}"


def test_tail_budget_scan_cut_points_keeps_step_boundary():
    import agent_memory as am
    from agent_harness import estimate_tokens

    hist = _hist(am)
    total = estimate_tokens(hist)
    cuts = {0, 1}
    for frac in (0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1):
        cuts.add(int(total * frac))
    for i in range(len(hist) + 1):
        suffix = estimate_tokens(hist[i:])
        cuts.add(suffix)
        cuts.add(suffix + 1)

    for mt in sorted(cuts):
        tail, dropped = am._llm_history_tail_within_token_budget_with_start(hist, mt)
        if not tail:
            assert dropped == len(hist), f"mt={mt}: full drop must report all messages dropped"
            continue
        _assert_chain_valid_from_start(am, tail, mt)


def test_tail_budget_cut_that_used_to_land_on_tool_now_keeps_whole_step():
    """旧实现会把切点落在这条 tool 上（[T2, final] 恰好装入预算）；修复后必须整步对齐。"""
    import agent_memory as am
    from agent_harness import estimate_tokens

    hist = _hist(am)
    mt = estimate_tokens(hist[4:]) + 1  # 恰好够 [T2, final]
    assert estimate_tokens(hist[3:]) > mt, "precondition: [A2, T2, final] exceeds budget"

    tail, dropped = am._llm_history_tail_within_token_budget_with_start(hist, mt)

    assert dropped == 5
    assert len(tail) == 1
    assert isinstance(tail[0], am.AssistantMessage)
    assert str(tail[0].content) == "final answer"


def test_tail_budget_skips_leading_orphan_tool_step():
    import agent_memory as am
    from agent_harness import estimate_tokens

    A, T = am.AssistantMessage, am.ToolMessage
    hist = [
        T("ghost" * 100, tool_call_id="ghost"),
        A("", tool_calls=[{"id": "c1", "name": "x", "args": {}}]),
        T("z" * 100, tool_call_id="c1"),
        A("done"),
    ]
    tail, dropped = am._llm_history_tail_within_token_budget_with_start(
        hist, estimate_tokens(hist) + 100
    )
    assert dropped == 1
    assert len(tail) == 3
    assert isinstance(tail[0], am.AssistantMessage)


def test_tail_budget_full_keep_and_full_drop_semantics():
    import agent_memory as am
    from agent_harness import estimate_tokens

    hist = _hist(am)
    total = estimate_tokens(hist)
    tail, dropped = am._llm_history_tail_within_token_budget_with_start(hist, total + 1)
    assert dropped == 0
    assert len(tail) == len(hist)
    assert isinstance(tail[0], am.UserMessage)

    assert estimate_tokens(hist[-1:]) > 0, "precondition: last step must cost tokens"
    tail2, dropped2 = am._llm_history_tail_within_token_budget_with_start(hist, 0)
    assert tail2 == []
    assert dropped2 == len(hist)


def test_tail_fallback_max_rounds_output_never_leads_with_tool():
    import agent_memory as am
    from agent_harness import estimate_tokens

    hist = _hist(am, tool_content=5000)
    mt = estimate_tokens(hist[4:]) + 1
    assert estimate_tokens(hist[3:]) > mt, "precondition: [A2, T2, final] exceeds budget"

    out, used_fallback, dropped = am.compress_tail_fallback(
        hist, reason="max_rounds", max_tokens=mt
    )

    assert used_fallback is True
    assert dropped is True
    assert isinstance(out[0], am.SystemMessage)
    assert "Conversation truncated" in str(out[0].content)
    _assert_chain_valid_from_start(am, out[1:], mt)
