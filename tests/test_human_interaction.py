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


def test_frontend_human_interaction_contract_is_wired():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    module = (root / "frontend/src/app/modules/human-interactions.js").read_text(encoding="utf-8")
    shell = (root / "frontend/src/shell-body.html").read_text(encoding="utf-8")
    dispatch = (root / "frontend/src/app/modules/event-dispatch.js").read_text(encoding="utf-8")
    assert "refreshHumanInteractions" in module
    assert "sessionStorage" in module
    assert "selected_option_ids" in module
    assert 'id="human-interaction-banner"' in shell
    assert "renderHumanInteractionEvent" in dispatch


def test_stale_approval_is_not_resolved_without_a_live_waiter(tmp_path):
    from app import tool_approval_gate

    assert tool_approval_gate.has_live_approval_waiter("missing-session", "missing-approval") is False
    assert tool_approval_gate.resolve_tool_approval("missing-session", "missing-approval", True) is False
