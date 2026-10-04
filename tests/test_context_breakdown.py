"""Top-right context panel: three-lane breakdown contract.

The hover panel mirrors the DSH ContextMeter composition (system prompt / tool
definitions / conversation), so the lanes must add up to the same total the meter
shows, price only the leading system run, and be served even for checkpoints that
predate the lanes.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


def _json_response_payload(response):
    return json.loads(response.body.decode("utf-8"))


def test_breakdown_lanes_add_up_to_the_total_they_describe():
    import agent_tokenizer
    from agent_harness import SystemMessage, UserMessage

    system = [SystemMessage(content="You are a careful agent. " * 40)]
    tools = [{"type": "function", "function": {"name": "demo", "parameters": {"type": "object"}}}]
    history = system + [UserMessage(content="hello there")]
    total = agent_tokenizer.message_token_estimator(history) + (
        agent_tokenizer.count_tool_definition_tokens(tools)
    )

    lanes = agent_tokenizer.build_context_breakdown(system, total, tools)

    assert set(lanes) == {"system_tokens", "tools_tokens", "message_tokens"}
    assert lanes["tools_tokens"] == agent_tokenizer.count_tool_definition_tokens(tools)
    assert sum(lanes.values()) == total
    assert lanes["system_tokens"] > 0
    assert lanes["message_tokens"] > 0


def test_breakdown_clamps_when_the_total_is_smaller_than_the_priced_lanes():
    import agent_tokenizer
    from agent_harness import SystemMessage

    system = [SystemMessage(content="prompt " * 50)]
    tools = [{"type": "function", "function": {"name": "demo"}}]

    lanes = agent_tokenizer.build_context_breakdown(system, 1, tools)

    assert lanes["message_tokens"] == 0
    assert lanes["system_tokens"] > 1


def test_breakdown_prices_no_system_messages_as_zero():
    import agent_tokenizer

    lanes = agent_tokenizer.build_context_breakdown(None, 900, None)

    assert lanes == {"system_tokens": 0, "tools_tokens": 0, "message_tokens": 900}


def test_breakdown_only_prices_the_leading_system_run():
    """A system note injected mid-history belongs to the conversation lane."""
    import agent_loop
    from agent_harness import AssistantMessage, SystemMessage, UserMessage

    messages = [
        SystemMessage(content="static prompt"),
        SystemMessage(content="key context"),
        UserMessage(content="hello"),
        SystemMessage(content="[background job 1] notice"),
        AssistantMessage(content="answer"),
    ]

    leading = agent_loop._leading_system_messages(messages)

    assert [message.content for message in leading] == ["static prompt", "key context"]


def test_history_breakdown_prices_static_segments_plus_key_context(monkeypatch):
    import agent_loop
    import agent_tokenizer
    import agent_tools
    from agent_harness import SystemMessage

    monkeypatch.setattr(agent_loop, "build_env_static", lambda _sid=None: "environment block")
    monkeypatch.setattr(
        agent_loop,
        "build_static_system_segments",
        lambda catalog, env, language="zh-CN": ["identity", "tool contract"],
    )
    monkeypatch.setattr(agent_loop, "key_context_body_for_system_prompt", lambda text: text)
    monkeypatch.setattr(agent_tools, "get_skills_catalog", lambda: "")

    lanes = agent_loop.compute_context_breakdown_for_llm_history(
        "s1", "summary body", "zh-CN", None, 12345
    )
    expected_system = agent_tokenizer.message_token_estimator([
        SystemMessage(content="identity"),
        SystemMessage(content="tool contract"),
        SystemMessage(content="summary body"),
    ])

    assert lanes["system_tokens"] == expected_system
    assert lanes["tools_tokens"] == 0
    assert lanes["message_tokens"] == 12345 - expected_system


def test_context_tokens_endpoint_backfills_a_snapshot_without_lanes(monkeypatch):
    import runtime_v2
    import webui

    tools = [{"type": "function", "function": {"name": "demo"}}]
    captured = {}

    monkeypatch.setattr(runtime_v2, "runtime_v2_primary", lambda: True)
    monkeypatch.setattr(webui, "get_context_token_mode", lambda: "hybrid")
    monkeypatch.setattr(webui, "_runtime_v2_context_snapshot", lambda _sid: {
        "tokens": {"estimated": 5000, "threshold": 10000, "token_source": "provider_exact"},
    })
    monkeypatch.setattr(
        webui,
        "build_combined_tool_definitions_for_session",
        lambda _sid: asyncio.sleep(0, result=tools),
    )

    def fake_backfill(sid, total, tool_definitions=None):
        captured["sid"] = sid
        captured["total"] = total
        captured["tools"] = tool_definitions
        return {"system_tokens": 1000, "tools_tokens": 500, "message_tokens": 3500}

    monkeypatch.setattr(webui, "backfill_context_breakdown_for_session", fake_backfill)

    payload = _json_response_payload(asyncio.run(webui.get_session_context_tokens("s1")))

    # The stored total and its scale are served unchanged; only the lanes are added.
    assert payload["estimated"] == 5000
    assert payload["token_source"] == "provider_exact"
    assert payload["breakdown"] == {
        "system_tokens": 1000,
        "tools_tokens": 500,
        "message_tokens": 3500,
    }
    assert captured == {"sid": "s1", "total": 5000, "tools": tools}


def test_context_tokens_endpoint_serves_a_stored_breakdown_without_recomputing(monkeypatch):
    import runtime_v2
    import webui

    lanes = {"system_tokens": 10, "tools_tokens": 20, "message_tokens": 30}

    monkeypatch.setattr(runtime_v2, "runtime_v2_primary", lambda: True)
    monkeypatch.setattr(webui, "get_context_token_mode", lambda: "hybrid")
    monkeypatch.setattr(webui, "_runtime_v2_context_snapshot", lambda _sid: {
        "tokens": {"estimated": 60, "threshold": 1000, "breakdown": dict(lanes)},
    })
    monkeypatch.setattr(
        webui,
        "build_combined_tool_definitions_for_session",
        lambda _sid: (_ for _ in ()).throw(AssertionError("lanes present: no tool build")),
    )
    monkeypatch.setattr(
        webui,
        "backfill_context_breakdown_for_session",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("lanes present: no backfill")),
    )

    payload = _json_response_payload(asyncio.run(webui.get_session_context_tokens("s1")))

    assert payload["breakdown"] == lanes
    assert payload["estimated"] == 60


def test_backfill_never_raises_out_of_a_status_read(monkeypatch):
    """A broken projection/legacy read degrades to "no lanes", not a failed meter."""
    import agent_loop

    monkeypatch.setattr(
        agent_loop,
        "_runtime_v2_is_primary",
        lambda: True,
    )
    monkeypatch.setattr(
        agent_loop,
        "_load_runtime_v2_context_summary",
        lambda _sid: (_ for _ in ()).throw(OSError("corrupt projection")),
    )

    assert agent_loop.backfill_context_breakdown_for_session("s1", 100, None) is None


def test_context_breakdown_markup_is_in_both_shells():
    for relative in ("frontend/index.html", "frontend/src/shell-body.html"):
        html = (ROOT / relative).read_text(encoding="utf-8")
        assert html.count('id="ctx-breakdown"') == 1
        assert html.count('class="ctx-card-bar"') == 1
        assert html.count('class="ctx-card-note"') == 1
        for lane in ("system_tokens", "tools_tokens", "message_tokens"):
            assert html.count(f'data-lane="{lane}"') == 1
        for label in ("系统提示词", "工具定义", "对话消息"):
            assert label in html


def test_frontend_passes_the_breakdown_through_the_token_store():
    reducer = (ROOT / "frontend/src/app/state/session-event-reducer.js").read_text(encoding="utf-8")
    store = (ROOT / "frontend/src/app/state/context-store.js").read_text(encoding="utf-8")
    snapshot = (ROOT / "frontend/src/app/modules/session-management.js").read_text(encoding="utf-8")
    scroll = (ROOT / "frontend/src/app/modules/session-scroll-history.js").read_text(encoding="utf-8")

    assert "event.estimated, event.threshold, event.breakdown" in reducer
    assert "breakdown: breakdown != null ? breakdown" in store
    assert "snapshot.context_tokens.breakdown" in snapshot
    assert "recordContextTokens(sid, j.estimated, j.threshold, j.breakdown)" in scroll
    # The card only takes over when lanes exist; otherwise the plain tip stays.
    assert "el.removeAttribute('data-ui-tip')" in scroll
    assert "ctx-card-seg ctx-lane-" in scroll


def test_context_breakdown_card_runtime():
    result = subprocess.run(
        ["node", str(ROOT / "tests/js/context_breakdown_card_runtime.cjs")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
