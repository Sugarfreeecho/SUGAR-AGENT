import asyncio
from pathlib import Path

import pytest

from app.human_interaction.service import (
    HumanInteractionService,
    HumanInteractionValidationError,
    ask_user_enabled,
)
from app.runtime_v2.ui_projection import RuntimeUiProjection


@pytest.fixture(autouse=True)
def _enable_ask_user_for_interaction_tests(monkeypatch):
    monkeypatch.setenv("ASK_USER_ENABLED", "1")


def _service(tmp_path):
    return HumanInteractionService(tmp_path, path_resolver=lambda sid: tmp_path / sid)


def _questions():
    return {
        "questions": [
            {
                "header": "实现范围",
                "question": "这次按哪个范围实现？",
                "options": [
                    {"label": "完整闭环（推荐）", "description": "包含持久化、恢复和前端。"},
                    {"label": "仅后端", "description": "只实现服务端能力。"},
                ],
                "multi_select": False,
            }
        ],
        "metadata": {"source": "test"},
    }


def test_question_request_resolve_and_rebuild(tmp_path):
    service = _service(tmp_path)
    created = service.create_question(
        "session-1", _questions(), run_id="run-1", tool_call_id="call-1", interaction_id="ask-1"
    )

    assert created["status"] == "pending"
    assert created["questions"][0]["question_id"] == "q1"
    assert created["questions"][0]["options"][0]["option_id"] == "q1o1"
    assert service.pending_counts("session-1") == {"questions": 1, "approvals": 0, "total": 1}

    resolved = service.resolve_question(
        "session-1",
        "ask-1",
        {"answers": [{"question_id": "q1", "selected_option_ids": ["q1o1"]}]},
        resolver={"channel": "test"},
    )
    duplicate = service.resolve_question(
        "session-1",
        "ask-1",
        {"answers": [{"question_id": "q1", "selected_option_ids": ["q1o2"]}]},
    )

    assert resolved["status"] == "resolved"
    assert resolved["answers"][0]["selected_labels"] == ["完整闭环（推荐）"]
    assert duplicate["answers"] == resolved["answers"]
    assert service.pending_counts("session-1")["total"] == 0

    rebuilt = service.mirror.projector.project(service.mirror.event_log.read_all("session-1"))
    assert rebuilt["interactions"]["ask-1"]["status"] == "resolved"
    assert rebuilt["pending_interactions"] == []

    projection = RuntimeUiProjection(tmp_path, path_resolver=lambda sid: tmp_path / sid)
    event_types = [row["type"] for row in projection.read_ui_events_fast("session-1")]
    assert event_types[-2:] == ["interaction_requested", "interaction_resolved"]


def test_question_validation_rejects_other_and_bad_answers(tmp_path):
    service = _service(tmp_path)
    invalid = _questions()
    invalid["questions"][0]["options"][1]["label"] = "Other"
    with pytest.raises(HumanInteractionValidationError, match="supplied by the UI"):
        service.create_question("session-1", invalid)

    service.create_question("session-1", _questions(), interaction_id="ask-1")
    with pytest.raises(HumanInteractionValidationError, match="unknown option"):
        service.resolve_question(
            "session-1",
            "ask-1",
            {"answers": [{"question_id": "q1", "selected_option_ids": ["missing"]}]},
        )


def test_question_header_allows_fifty_characters(tmp_path):
    service = _service(tmp_path)
    request = _questions()
    request["questions"][0]["header"] = "x" * 50
    created = service.create_question("session-1", request)
    assert created["questions"][0]["header"] == "x" * 50

    request["questions"][0]["header"] = "x" * 51
    with pytest.raises(HumanInteractionValidationError, match="exceeds 50 characters"):
        service.create_question("session-2", request)


@pytest.mark.parametrize("value", ["0", "false", "NO", "Off"])
def test_ask_user_switch_blocks_new_questions_but_not_approvals(tmp_path, monkeypatch, value):
    monkeypatch.setenv("ASK_USER_ENABLED", value)
    service = _service(tmp_path)

    assert ask_user_enabled() is False
    with pytest.raises(HumanInteractionValidationError, match="ASK_USER_ENABLED"):
        service.create_question("session-1", _questions())

    approval = service.create_approval("session-1", approval_id="approval-1")
    assert approval["status"] == "pending"


def test_ask_user_switch_defaults_disabled(monkeypatch):
    monkeypatch.delenv("ASK_USER_ENABLED", raising=False)
    assert ask_user_enabled() is False


def test_agent_loop_filters_ask_user_tool_when_switch_is_disabled():
    source = (Path(__file__).resolve().parents[1] / "app/agent_loop.py").read_text(encoding="utf-8")
    assert "if not ask_user_enabled():" in source
    assert ') != "ask_user"' in source


def test_approval_is_durable_and_terminal_transition_is_idempotent(tmp_path):
    service = _service(tmp_path)
    created = service.create_approval(
        "session-1",
        approval_id="approval-1",
        metadata={"tool": "run_shell", "title": "允许执行？"},
        tool_call_id="call-1",
    )
    assert created["status"] == "pending"
    assert service.pending_counts("session-1") == {"questions": 0, "approvals": 1, "total": 1}

    resolved = service.resolve_approval("session-1", "approval-1", "allow_once")
    duplicate = service.resolve_approval("session-1", "approval-1", "deny")
    assert resolved["decision"] == "allow_once"
    assert duplicate["decision"] == "allow_once"
    assert service.pending_counts("session-1")["total"] == 0


def test_dangerous_approval_rejects_session_and_always_grants(tmp_path):
    service = _service(tmp_path)
    created = service.create_approval(
        "session-1",
        approval_id="danger-1",
        metadata={
            "tool": "run_shell",
            "title": "危险命令，需要确认",
            "force_approval": True,
            "approval_level": "danger",
        },
    )
    assert created["force_approval"] is True

    with pytest.raises(HumanInteractionValidationError, match="allow_once or deny"):
        service.resolve_approval("session-1", "danger-1", "allow_session")
    with pytest.raises(HumanInteractionValidationError, match="allow_once or deny"):
        service.resolve_approval("session-1", "danger-1", "allow_always")
    resolved = service.resolve_approval("session-1", "danger-1", "allow_once")
    assert resolved["decision"] == "allow_once"


def test_non_dangerous_approval_still_supports_session_grant(tmp_path):
    service = _service(tmp_path)
    service.create_approval(
        "session-1",
        approval_id="normal-1",
        metadata={"tool": "write_file", "force_approval": False},
    )
    resolved = service.resolve_approval("session-1", "normal-1", "allow_session")
    assert resolved["decision"] == "allow_session"


def test_resolved_approval_keeps_rule_metadata_for_rule_creation(tmp_path):
    """allow_always resolves through the same record that carries
    rule_action/rule_pattern so webui can persist the durable rule,
    including for auto-review override cards."""
    service = _service(tmp_path)
    service.create_approval(
        "session-1",
        approval_id="rule-1",
        metadata={
            "tool": "run_shell",
            "force_approval": False,
            "allow_always_available": True,
            "rule_action": "process.exec",
            "rule_pattern": "git push:*",
        },
    )
    resolved = service.resolve_approval("session-1", "rule-1", "allow_always")
    assert resolved["decision"] == "allow_always"
    assert resolved["rule_action"] == "process.exec"
    assert resolved["rule_pattern"] == "git push:*"


def test_frontend_human_interaction_contract_is_wired():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    module = (root / "frontend/src/app/modules/human-interactions.js").read_text(encoding="utf-8")
    shell = (root / "frontend/src/shell-body.html").read_text(encoding="utf-8")
    index_html = (root / "frontend/index.html").read_text(encoding="utf-8")
    dispatch = (root / "frontend/src/app/modules/event-dispatch.js").read_text(encoding="utf-8")
    rendering = (root / "frontend/src/app/modules/message-rendering.js").read_text(encoding="utf-8")
    assert "refreshHumanInteractions" in module
    assert "sessionStorage" in module
    assert "selected_option_ids" in module
    assert "syncHumanInteractionSessionSummary(sid);" in module
    assert 'id="human-interaction-banner"' in shell
    # frontend/index.html is Vite's real entrypoint. Checking only the shell
    # fragment can pass while the banner is absent from the served page.
    assert 'id="human-interaction-banner"' in index_html
    assert "renderHumanInteractionEvent" in dispatch
    assert "function humanInteractionToolSlot" in module
    assert "attachHumanInteractionCardsForToolCall" in module
    assert "attachHumanInteractionCardsForToolCall" in rendering
    assert "attachAllHumanInteractionCards" in module
    assert "允许一次" in module
    assert "本任务内允许相同请求" in module
    assert "始终允许此类操作" in module
    assert "resolveHumanApproval(card, 'allow_session')" in module
    assert "if (!forced)" in module
    # Tool rows fold as a whole (command + approval card). They default to a
    # compact preview; a row with a pending approval renders expanded, clicking
    # the command text toggles the same row fold, and the banner focus expands
    # both a collapsed row and the outer process block.
    assert "feed-row-collapse" in rendering
    assert "row.classList.toggle('is-collapsed')" in rendering
    assert "collapsedRow.classList.remove('is-collapsed')" in module
    assert "row.classList.add('is-collapsed')" in rendering
    assert "row.dataset.manualToggle = '1'" in rendering
    assert "function handleToolRowChunkClick" in rendering
    assert "row.classList.contains('feed--tool')" in rendering
    assert "collapsedAgg.classList.remove('is-collapsed')" in module
    assert "function toolCallHasPendingApproval" in module
    assert "function autoExpandToolRow" in module
    assert "function collapseAutoExpandedToolRow" in module
    assert "autoExpandToolRow(slot.closest('.feed-item'))" in module
    assert "collapseAutoExpandedToolRow(stream, toolCallId)" in module
    # History replay must route tool_call events through the same upsert path
    # as live SSE so the tool row carries data-tool-call-id and approval cards
    # can be re-anchored after a page refresh.
    assert "upsertToolCallResult(ctx, event, runSessionId)" in dispatch
    assert "appendLog(ctx, event.raw_content, 'tool-call'" not in dispatch
    upsert_fn = rendering.split("function upsertToolCallResult", 1)[1].split(
        "function trimSurroundingBlankLines", 1
    )[0]
    assert "createProcessFeedRow(ctx, 'tool-call', text, so, runSessionId, tid)" in upsert_fn
    assert "attachHumanInteractionCardsForToolCall(ctx && ctx.stream, tid)" in upsert_fn
    css = (root / "frontend/src/styles/app.css").read_text(encoding="utf-8")
    slot_card = css.split(".human-interaction-tool-slot .human-interaction-card {", 1)[1].split("}", 1)[0]
    assert "width: min(720px, calc(100% - 1rem));" in slot_card
    assert "margin: 0.65rem auto;" in slot_card
    assert "width: 100%; margin: 0.65rem 0 0;" not in slot_card
    assert ".feed-row-collapse {" in css
    assert ".feed-item.is-collapsed .human-interaction-tool-slot { display: none; }" in css
    assert ".feed-item.is-collapsed .feed-chunk {" in css
    tool_scroller = css.split(".feed-item.feed--tool .feed-chunk-scroller {", 1)[1].split("}", 1)[0]
    assert "max-height: none;" in tool_scroller
    assert "overflow: visible;" in tool_scroller
    assert ".feed-item.feed--tool .feed-chunk { cursor: default; }" not in css
    badge_update = module.split("function updateHumanInteractionSessionBadge", 1)[1].split(
        "function updateAllHumanInteractionSessionBadges", 1
    )[0]
    assert "if (count <= 0)" in badge_update
    assert "if (badge) badge.remove();" in badge_update
    assert "hasQuestions && hasApprovals" in badge_update
    assert "String(count)" in badge_update
    assert "function showHumanQuestionReview" in module
    assert "function validateHumanQuestionPane" in module
    assert "aria-busy" in module
    assert "confirmAndCancelPendingHumanQuestionsForMessage" in module
    sse = (root / "frontend/src/app/modules/sse-handling.js").read_text(encoding="utf-8")
    assert "submitComposerWithPendingQuestionGuard" in sse
    assert "取消问题并发送" in module
    settings = (root / "frontend/src/app/modules/settings.js").read_text(encoding="utf-8")
    webui = (root / "app/webui.py").read_text(encoding="utf-8")
    assert 'id="settings-ask-user-on"' in shell
    assert 'id="settings-ask-user-on"' in index_html
    assert "saveAskUserFeature" in settings
    assert '"/api/features/ask-user"' in webui


def test_tool_pending_is_emitted_before_approval_dialog():
    """The tool row must exist before the approval card renders so the card
    anchors inside the row instead of jumping from the bottom of the stream."""

    root = Path(__file__).resolve().parents[1]
    source = (root / "app/agent_loop.py").read_text(encoding="utf-8")
    core = source.split("async def _execute_one_core", 1)[1]
    pending_call = core.index("await _emit_tool_pending_sse(")
    approval_wait = core.index("wait_tool_ui_approval_after_emit(")
    assert pending_call < approval_wait
    pre_approval = core[: core.index("if sec_decision.outcome == DecisionOutcome.ASK or hook_approval_spec:")]
    assert 'tool_name not in ("context_manage", "ask_user")' in pre_approval
    # The old post-approval emit was removed in favor of the pre-approval row.
    assert "Arguments are closed and any required approval has completed" not in source


def test_stale_approval_is_not_resolved_without_a_live_waiter(tmp_path):
    from app import tool_approval_gate

    assert tool_approval_gate.has_live_approval_waiter("missing-session", "missing-approval") is False
    assert tool_approval_gate.resolve_tool_approval("missing-session", "missing-approval", True) is False


def test_approval_card_is_not_emitted_when_durable_persistence_fails(monkeypatch):
    import human_interaction
    from app import tool_approval_gate

    class _BrokenService:
        def create_approval(self, *_args, **_kwargs):
            raise OSError("approval store is unavailable")

    emitted = []

    async def emit_card():
        emitted.append(True)

    monkeypatch.setattr(human_interaction, "get_human_interaction_service", lambda: _BrokenService())

    with pytest.raises(tool_approval_gate.ApprovalPersistenceError, match="could not be saved"):
        asyncio.run(
            tool_approval_gate.wait_tool_ui_approval_after_emit(
                "session-persist-failure",
                "approval-persist-failure",
                emit_card,
                metadata={"_durable": True, "tool": "run_shell"},
            )
        )

    assert emitted == []
    assert not tool_approval_gate.has_live_approval_waiter(
        "session-persist-failure", "approval-persist-failure"
    )


def test_pending_approval_refresh_restores_card_badge_and_banner_contract(tmp_path):
    service = _service(tmp_path)
    service.create_approval(
        "session-refresh",
        approval_id="approval-refresh",
        metadata={"tool": "run_shell", "title": "Approval required"},
    )

    # Reconstructing the service simulates a browser/server refresh: the
    # approval must come from the durable event log, not an in-memory waiter.
    restored = _service(tmp_path)
    assert restored.pending_counts("session-refresh") == {
        "questions": 0,
        "approvals": 1,
        "total": 1,
    }
    pending = restored.list("session-refresh", kind="approval", status="pending")
    assert [row["approval_id"] for row in pending] == ["approval-refresh"]

    root = Path(__file__).resolve().parents[1]
    layout = (root / "frontend/src/app/modules/layout-panels.js").read_text(encoding="utf-8")
    restore_call = "await refreshHumanInteractions(targetSession, { render: false });"
    switch_call = "if (targetSession) await switchSession(targetSession);"
    assert layout.index(restore_call) < layout.index(switch_call)

    interactions = (root / "frontend/src/app/modules/human-interactions.js").read_text(encoding="utf-8")
    refresh_body = interactions.split("async function refreshHumanInteractions", 1)[1]
    assert "syncHumanInteractionSessionSummary(sid);" in refresh_body
    assert "renderPendingHumanInteractions(sid);" in refresh_body
    render_body = interactions.split("function renderPendingHumanInteractions", 1)[1].split(
        "async function refreshHumanInteractions", 1
    )[0]
    assert "renderHumanInteractionRecord(record, sid, stream)" in render_body
    assert "updateHumanInteractionBanner(sid);" in render_body
