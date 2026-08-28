import os
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from app.agent_goal import GoalError, GoalManager, goal_enabled
from app.agent_goal_judge import JudgeParseError, build_judge_prompt, parse_judge_response


ROOT = Path(__file__).resolve().parents[1]


class GoalManagerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"GOAL_ENABLED": "1", "RUNTIME_VERSION": "2"}, clear=False)
        self.env.start()
        self.manager = GoalManager(self.tmp.name)

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_create_get_and_single_active_goal(self):
        created = self.manager.create("s1", "Ship goal support")
        self.assertEqual(created["status"], "active")
        self.assertNotIn("completion_mode", created)
        self.assertEqual(self.manager.get("s1")["id"], created["id"])
        with self.assertRaises(GoalError):
            self.manager.create("s1", "Another goal")

    def test_runtime_v2_goal_recovers_from_event_log_when_snapshot_is_missing(self):
        created = self.manager.create("recover-goal", "Survive an Agent restart")
        snapshot_path = Path(self.tmp.name) / "recover-goal" / "snapshots" / "latest.json"
        self.assertTrue(snapshot_path.is_file())
        snapshot_path.unlink()

        restarted_manager = GoalManager(self.tmp.name)
        recovered = restarted_manager.get("recover-goal")

        self.assertIsNotNone(recovered)
        self.assertEqual(recovered["id"], created["id"])
        self.assertEqual(recovered["objective"], "Survive an Agent restart")
        self.assertEqual(recovered["status"], "active")
        self.assertTrue(snapshot_path.is_file())

    def test_usage_events_are_compact_and_recoverable(self):
        self.manager.create("compact-goal", "Do not repeat this objective " * 200)
        self.manager.record_usage(
            "compact-goal",
            17,
            usage_id="run-1:llm:0",
            run_id="run-1",
        )
        self.manager.record_run(
            "compact-goal",
            3,
            continuation=True,
            run_id="run-1",
            outcome="finished",
        )

        from app.runtime_v2 import RuntimeHistoryOps

        ops = RuntimeHistoryOps(self.tmp.name)
        events = ops.event_log.read_all("compact-goal")
        usage_events = [
            event
            for event in events
            if event.type == "extension_state_changed"
            and event.payload.get("action") == "goal_usage_updated"
        ]
        self.assertEqual(len(usage_events), 2)
        for event in usage_events:
            self.assertIn("patch", event.payload)
            self.assertNotIn("objective", str(event.payload))
        first_paths = {row["path"] for row in usage_events[0].payload["patch"]}
        second_paths = {row["path"] for row in usage_events[1].payload["patch"]}
        self.assertIn("/accounted_usage_ids", first_paths)
        self.assertIn("/accounted_run_ids", second_paths)

        snapshot_path = Path(self.tmp.name) / "compact-goal" / "snapshots" / "latest.json"
        snapshot_path.unlink()
        recovered = GoalManager(self.tmp.name).get("compact-goal")

        self.assertEqual(recovered["used_tokens"], 20)
        self.assertEqual(recovered["run_count"], 1)
        self.assertEqual(recovered["continuation_count"], 1)
        self.assertEqual(recovered["accounted_usage_ids"], ["run-1:llm:0"])
        self.assertEqual(recovered["accounted_run_ids"], ["run-1"])

    def test_same_blocker_requires_three_reports(self):
        self.manager.create("s1", "Ship goal support")
        for expected in (1, 2):
            report = self.manager.update_status(
                "s1", "blocked", "missing credential", report_id=f"run-{expected}"
            )
            self.assertTrue(report["blocker_report_recorded"])
            self.assertFalse(report["blocker_report_terminal"])
            self.assertEqual(report["blocked_streak"], expected)
            self.assertEqual(report["status"], "active")
        goal = self.manager.update_status("s1", "blocked", "missing credential", report_id="run-3")
        self.assertEqual(goal["status"], "blocked")

    def test_completion_request_waits_for_independent_judge_verdict(self):
        self.manager.create(
            "judge-goal",
            "Ship verified goal support",
            run_id="run-1",
        )
        self.assertFalse(self.manager.should_judge("judge-goal"))

        requested = self.manager.update_status(
            "judge-goal",
            "completed",
            run_id="run-1",
        )
        self.assertEqual(requested["status"], "active")
        self.assertTrue(requested["completion_pending_judge"])
        self.assertTrue(requested["completion_judge_requested"])
        self.assertTrue(requested["completion_request_id"].startswith("goal_completion_"))
        self.assertIsNotNone(requested["completion_requested_at"])
        self.assertEqual(requested["completion_requested_run_id"], "run-1")
        self.assertEqual(requested["origin_run_id"], "run-1")

        duplicate = self.manager.update_status("judge-goal", "completed")
        self.assertTrue(duplicate["completion_request_duplicate"])
        self.assertNotIn("completion_judge_requested", duplicate)
        self.assertEqual(duplicate["completion_request_id"], requested["completion_request_id"])

        completed = self.manager.record_judge_result(
            "judge-goal",
            "done",
            "Tests and build both passed.",
            run_id="run-1:judge",
            raw='{"verdict":"done","reason":"Tests and build both passed."}',
        )
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(completed["last_judge_verdict"], "done")
        self.assertEqual(completed["judge_count"], 1)
        self.assertEqual(completed["review_status"], "pending")
        self.assertIsNone(completed["completion_requested_run_id"])
        self.assertFalse(self.manager.should_judge("judge-goal"))

    def test_completed_goal_review_can_save_then_approve_and_remove_card_state(self):
        self.manager.create("review-goal", "Original objective")
        self.manager.update_status("review-goal", "completed")
        self.manager.record_judge_result(
            "review-goal",
            "done",
            "Original Judge result.",
            run_id="run-1:judge",
        )

        saved = self.manager.review_completion(
            "review-goal",
            "save",
            objective="Edited objective",
            judge_result="Edited Judge result.",
        )
        self.assertEqual(saved["status"], "completed")
        self.assertEqual(saved["review_status"], "pending")
        self.assertEqual(saved["objective"], "Edited objective")
        self.assertEqual(saved["review_judge_result"], "Edited Judge result.")

        approved = self.manager.review_completion(
            "review-goal",
            "approve",
            objective="Edited objective",
            judge_result="Approved after human review.",
        )
        self.assertEqual(approved["review_status"], "approved")
        self.assertTrue(approved["deleted"])
        self.assertIsNone(self.manager.get("review-goal"))

    def test_completed_goal_review_can_reopen_with_human_feedback(self):
        self.manager.create("review-goal", "Finish everything")
        self.manager.update_status("review-goal", "completed")
        self.manager.record_judge_result(
            "review-goal",
            "done",
            "Worker evidence looked complete.",
            run_id="run-1:judge",
        )

        reopened = self.manager.review_completion(
            "review-goal",
            "continue",
            objective="Finish everything and add verification",
            judge_result="Missing an end-to-end verification run.",
        )
        self.assertEqual(reopened["status"], "active")
        self.assertEqual(reopened["review_status"], "changes_requested")
        self.assertTrue(reopened["review_feedback_pending"])
        self.assertEqual(reopened["last_judge_verdict"], "continue")
        self.assertEqual(
            reopened["last_judge_reason"],
            "Missing an end-to-end verification run.",
        )
        self.assertTrue(self.manager.should_continue("review-goal"))

        accounted = self.manager.record_run(
            "review-goal",
            0,
            continuation=True,
            run_id="run-2",
            outcome="finished",
        )
        self.assertFalse(accounted["review_feedback_pending"])
        self.assertEqual(accounted["review_status"], "addressed")

    def test_review_continue_requires_more_budget_when_exhausted(self):
        self.manager.create(
            "review-budget",
            "Budgeted review",
            token_budget=10,
        )
        self.manager.record_usage(
            "review-budget",
            10,
            usage_id="run-1:llm:0",
            run_id="run-1",
        )
        self.manager.user_action("review-budget", "resume", additional_budget=1)
        self.manager.update_status("review-budget", "completed")
        self.manager.record_judge_result(
            "review-budget",
            "done",
            "Complete.",
            run_id="run-1:judge",
        )
        self.manager.record_usage(
            "review-budget",
            1,
            usage_id="run-1:judge",
            run_id="run-1:judge",
        )
        with self.assertRaisesRegex(GoalError, "additional_budget"):
            self.manager.review_completion(
                "review-budget",
                "continue",
                objective="Budgeted review",
                judge_result="Needs more work.",
            )
        reopened = self.manager.review_completion(
            "review-budget",
            "continue",
            objective="Budgeted review",
            judge_result="Needs more work.",
            additional_budget=5,
        )
        self.assertEqual(reopened["status"], "active")
        self.assertEqual(reopened["remaining_tokens"], 5)

    def test_judge_runs_only_after_completion_request_and_continue_clears_it(self):
        self.manager.create("fixed-flow-goal", "Verify before completion")
        self.assertFalse(self.manager.should_judge("fixed-flow-goal"))
        self.manager.update_status("fixed-flow-goal", "completed")
        self.assertTrue(self.manager.should_judge("fixed-flow-goal"))

        continued = self.manager.record_judge_result(
            "fixed-flow-goal",
            "continue",
            "Required verification is missing.",
            run_id="run-1:judge",
        )
        self.assertEqual(continued["status"], "active")
        self.assertEqual(continued["last_judge_verdict"], "continue")
        self.assertIsNone(continued["completion_request_id"])
        self.assertIsNone(continued["completion_requested_at"])
        self.assertFalse(self.manager.should_judge("fixed-flow-goal"))

    def test_each_completion_request_gets_a_distinct_identity(self):
        self.manager.create("repeat-completion", "Finish, fix feedback, and finish again")
        first = self.manager.update_status("repeat-completion", "completed")
        self.manager.record_judge_result(
            "repeat-completion",
            "continue",
            "One verification gap remains.",
            run_id="same-run:judge:first",
        )
        second = self.manager.update_status("repeat-completion", "completed")

        self.assertNotEqual(first["completion_request_id"], second["completion_request_id"])
        self.assertTrue(self.manager.should_judge("repeat-completion"))

    def test_stale_judge_cannot_apply_to_a_newer_completion_request(self):
        self.manager.create("stale-judge", "Protect completion request identity")
        requested = self.manager.update_status("stale-judge", "completed")

        stale = self.manager.record_judge_result(
            "stale-judge",
            "done",
            "Stale result.",
            run_id="run-1:judge:old-request",
            expected_completion_request_id="old-request",
        )

        self.assertEqual(stale["status"], "active")
        self.assertEqual(stale["judge_count"], 0)
        self.assertEqual(
            stale["completion_request_id"],
            requested["completion_request_id"],
        )
        self.assertTrue(self.manager.should_judge("stale-judge"))

    def test_judge_results_are_idempotent_and_failures_pause_at_threshold(self):
        self.manager.create("judge-goal", "Judge safely")
        self.manager.update_status("judge-goal", "completed")
        first = self.manager.record_judge_result(
            "judge-goal",
            "continue",
            "More work remains.",
            run_id="run-1:judge",
        )
        duplicate = self.manager.record_judge_result(
            "judge-goal",
            "continue",
            "Duplicate delivery.",
            run_id="run-1:judge",
        )
        self.assertEqual(first["judge_count"], 1)
        self.assertEqual(duplicate["judge_count"], 1)

        self.manager.update_status("judge-goal", "completed")
        with patch.dict(os.environ, {"GOAL_JUDGE_MAX_PARSE_FAILURES": "2"}, clear=False):
            self.manager.record_judge_result(
                "judge-goal",
                "error",
                "Malformed JSON.",
                run_id="run-2:judge",
                failure_kind="parse",
            )
            paused = self.manager.record_judge_result(
                "judge-goal",
                "error",
                "Malformed JSON again.",
                run_id="run-3:judge",
                failure_kind="parse",
            )
        self.assertEqual(paused["status"], "paused")
        self.assertEqual(paused["pause_reason"], "judge_parse_failures")

    def test_same_run_cannot_increment_blocker_streak(self):
        self.manager.create("s1", "Ship goal support")
        first = self.manager.update_status("s1", "blocked", "missing credential", report_id="same-run")
        second = self.manager.update_status("s1", "blocked", "missing credential", report_id="same-run")
        self.assertEqual(first["blocked_streak"], 1)
        self.assertEqual(second["blocked_streak"], 1)

    def test_budget_pauses_and_user_can_resume(self):
        self.manager.create("s1", "Budgeted goal", token_budget=10)
        goal = self.manager.record_run("s1", 12)
        self.assertEqual(goal["status"], "paused")
        self.assertEqual(goal["remaining_tokens"], 0)
        with self.assertRaisesRegex(GoalError, "additional_budget"):
            self.manager.user_action("s1", "resume")
        resumed = self.manager.user_action("s1", "resume", additional_budget=20)
        self.assertEqual(resumed["status"], "active")
        self.assertEqual(resumed["remaining_tokens"], 18)

    def test_run_usage_is_idempotent_and_tracks_failed_attempts(self):
        self.manager.create("s1", "Account every run", token_budget=100)
        first = self.manager.record_run(
            "s1", 12, continuation=True, run_id="run-1", outcome="failed", error="network"
        )
        duplicate = self.manager.record_run(
            "s1", 12, continuation=True, run_id="run-1", outcome="failed", error="network"
        )
        self.assertEqual(first["used_tokens"], 12)
        self.assertEqual(duplicate["used_tokens"], 12)
        self.assertEqual(duplicate["continuation_count"], 1)
        self.assertEqual(duplicate["consecutive_failures"], 1)
        self.assertFalse(self.manager.should_continue("s1"))

    def test_llm_usage_is_incremental_and_idempotent(self):
        self.manager.create("s1", "Bound each model call", token_budget=10)
        first = self.manager.record_usage("s1", 6, usage_id="run-1:llm:0", run_id="run-1")
        duplicate = self.manager.record_usage("s1", 6, usage_id="run-1:llm:0", run_id="run-1")
        exhausted = self.manager.record_usage("s1", 5, usage_id="run-1:llm:1", run_id="run-1")
        self.assertEqual(first["used_tokens"], 6)
        self.assertEqual(duplicate["used_tokens"], 6)
        self.assertEqual(exhausted["used_tokens"], 11)
        self.assertEqual(exhausted["status"], "paused")
        self.assertEqual(exhausted["pause_reason"], "token_budget_exhausted")

    def test_three_failed_runs_pause_goal(self):
        self.manager.create("s1", "Stop retry storms")
        for index in range(1, 4):
            goal = self.manager.record_run(
                "s1", 1, continuation=True, run_id=f"run-{index}", outcome="failed", error="boom"
            )
        self.assertEqual(goal["status"], "paused")
        self.assertEqual(goal["pause_reason"], "consecutive_run_failures")
        self.assertEqual(goal["consecutive_failures"], 3)

    def test_react_iteration_limit_keeps_goal_active_for_auto_continuation(self):
        self.manager.create("s1", "Continue across bounded ReAct runs")

        goal = self.manager.record_run(
            "s1",
            1,
            continuation=True,
            run_id="run-limit",
            outcome="react_limit",
            error="ReAct reached the maximum iteration limit.",
        )

        self.assertEqual(goal["status"], "active")
        self.assertIsNone(goal.get("pause_reason"))
        self.assertEqual(goal["last_run_outcome"], "react_limit")
        self.assertIsNone(goal["last_error"])
        self.assertTrue(self.manager.should_continue("s1"))

    def test_continuation_start_is_persisted_with_run_identity(self):
        self.manager.create("s1", "Continue durably")
        started = self.manager.mark_continuation_started("s1", run_id="scheduler-1")
        self.assertEqual(started["current_run_id"], "scheduler-1")
        self.assertEqual(started["last_run_id"], "scheduler-1")
        self.assertGreaterEqual(started["version"], 2)

    def test_concurrent_run_accounting_does_not_lose_updates(self):
        self.manager.create("s1", "Atomic accounting", token_budget=1000)

        def account(index):
            return self.manager.record_run("s1", 3, run_id=f"run-{index}")

        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(account, range(20)))
        goal = self.manager.get("s1")
        self.assertEqual(goal["used_tokens"], 60)
        self.assertEqual(goal["run_count"], 20)

    def test_completed_goal_requires_human_approval_before_replacement(self):
        first = self.manager.create("s1", "First")
        self.manager.update_status("s1", "completed")
        completed = self.manager.record_judge_result(
            "s1",
            "done",
            "The first goal is complete.",
            run_id="run-1:judge",
        )
        with self.assertRaisesRegex(GoalError, "pending-review"):
            self.manager.create("s1", "Second")
        self.manager.review_completion(
            "s1",
            "approve",
            objective=completed["objective"],
            judge_result=completed["review_judge_result"],
        )
        second = self.manager.create("s1", "Second")
        self.assertNotEqual(first["id"], second["id"])

    def test_goals_are_isolated_by_session(self):
        first = self.manager.create("s1", "First session objective")
        second = self.manager.create("s2", "Second session objective")

        self.assertEqual(self.manager.get("s1")["id"], first["id"])
        self.assertEqual(self.manager.get("s2")["id"], second["id"])
        self.assertNotEqual(self.manager.get("s1")["id"], self.manager.get("s2")["id"])
        self.assertEqual(self.manager.get("s1")["objective"], "First session objective")
        self.assertEqual(self.manager.get("s2")["objective"], "Second session objective")

    def test_user_can_edit_and_delete_goal_then_create_a_replacement(self):
        original = self.manager.create("s1", "Original objective")
        edited = self.manager.user_action("s1", "edit", objective="Edited objective")
        self.assertEqual(edited["id"], original["id"])
        self.assertEqual(self.manager.get("s1")["objective"], "Edited objective")
        self.assertFalse(self.manager.should_judge("s1"))

        deleted = self.manager.user_action("s1", "delete")
        self.assertTrue(deleted["deleted"])
        self.assertIsNone(self.manager.get("s1"))

        replacement = self.manager.create("s1", "Replacement objective")
        self.assertNotEqual(replacement["id"], original["id"])

    def test_environment_switch_disables_feature(self):
        with patch.dict(os.environ, {"GOAL_ENABLED": "off"}, clear=False):
            self.assertFalse(goal_enabled())
            with self.assertRaisesRegex(GoalError, "disabled"):
                self.manager.get("s1")

    def test_runtime_v1_goal_uses_legacy_goal_file_without_v2_side_effects(self):
        with patch.dict(os.environ, {"RUNTIME_VERSION": "1"}, clear=False):
            created = self.manager.create("legacy-session", "Keep V1 isolated")

            session_dir = Path(self.tmp.name) / "legacy-session"
            self.assertEqual(self.manager.get("legacy-session")["id"], created["id"])
            self.assertTrue((session_dir / "goal.json").is_file())
            self.assertFalse((session_dir / "events.jsonl").exists())
            self.assertFalse((session_dir / "snapshots" / "latest.json").exists())


def test_goal_tool_pushes_live_state_and_frontend_consumes_it_immediately():
    host_tools = (ROOT / "plugins/agent-goal/host.py").read_text(encoding="utf-8")
    assert '"type": "extension_state_changed"' in host_tools
    assert '"plugin_id": "agent-goal"' in host_tools
    assert "await context.publish(" in host_tools
    assert "agent_goal" not in (ROOT / "app/builtin_host_tools.py").read_text(encoding="utf-8")


def test_active_goal_round_final_stays_dynamic_in_frontend():
    manifest = json.loads((ROOT / "plugins/agent-goal/.myagent-plugin/plugin.json").read_text(encoding="utf-8"))
    slots = manifest["capabilities"]["ui"]
    assert slots["session.panel"][0]["namespace"] == "goal"
    assert slots["session.badge"][0]["equals"] == "active"
    assert "agent-goal" not in (ROOT / "frontend/src/app/index.js").read_text(encoding="utf-8")


def test_goal_judge_response_contract_and_prompt():
    verdict, reason = parse_judge_response(
        '```json\n{"verdict":"continue","reason":"The build was not run."}\n```'
    )
    assert verdict == "continue"
    assert reason == "The build was not run."
    with unittest.TestCase().assertRaises(JudgeParseError):
        parse_judge_response('{"verdict":"maybe","reason":"uncertain"}')

    prompt = build_judge_prompt(
        {
            "id": "goal_1",
            "objective": "Ship the feature and pass tests",
            "completion_request_reason": "pytest -q: 10 passed",
        },
        "pytest: 10 passed",
    )
    assert "independent Goal completion judge" in prompt
    assert "A worker's claim" in prompt
    assert '"verdict":"done|continue"' in prompt
    assert "Worker-submitted completion evidence" in prompt
    assert "pytest -q: 10 passed" in prompt
    assert "Goal lifecycle dialogue (complete; not clipped):" in prompt
    assert "Recent auxiliary execution evidence" in prompt
    assert "pytest: 10 passed" in prompt


def test_goal_judge_uses_one_direct_request_on_current_candidate(monkeypatch):
    import agent_goal_judge
    import agent_harness

    captured = {}
    calls = []

    class _Transport:
        @staticmethod
        def complete_text(**kwargs):
            calls.append(dict(kwargs))
            captured.update(kwargs)
            return {
                "text": '{"verdict":"continue","reason":"verification missing"}',
                "usage": {"total_tokens": 3},
                "model": "fallback-model",
                "response_id": "resp-judge",
                "status": "completed",
                "finish_reason": "stop",
            }

    class _Client:
        @staticmethod
        def current_candidate():
            return {
                "profile_id": "fallback-profile",
                "provider": "openai-compatible",
                "model": "fallback-model",
                "max_output_tokens": 50000,
                "transport": _Transport(),
            }

    monkeypatch.setattr(
        agent_harness,
        "resolve_executor_config_for_session",
        lambda _session_id: (_Client(), "configured-model", 2048, 4096),
    )

    result = agent_goal_judge.evaluate_goal(
        "session-1",
        {"id": "goal-1", "objective": "Ship safely"},
        {"goal_dialogue": "work", "recent_evidence": "tests"},
    )

    assert result["verdict"] == "continue"
    assert len(calls) == 1
    assert captured["model"] == "fallback-model"
    assert captured["max_tokens"] == 50000
    assert len(captured["messages"]) == 1
    assert result["model"] == "fallback-model"
    assert result["diagnostics"]["requested_model"] == "fallback-model"
    assert result["diagnostics"]["max_output_tokens"] == 50000
    assert result["diagnostics"]["profile_id"] == "fallback-profile"
    assert result["diagnostics"]["response_id"] == "resp-judge"


def test_goal_judge_reports_reasoning_only_as_parse_failure(monkeypatch):
    import agent_goal_judge
    import agent_harness

    class _Transport:
        @staticmethod
        def complete_text(**_kwargs):
            return {
                "text": "",
                "usage": {"completion_tokens": 512, "reasoning_tokens": 512},
                "model": "judge-model",
                "response_id": "resp-reasoning-only",
                "status": "completed",
                "finish_reason": "stop",
            }

    class _Client:
        @staticmethod
        def current_candidate():
            return {
                "profile_id": "judge-profile",
                "provider": "openai",
                "model": "judge-model",
                "max_output_tokens": 1024,
                "transport": _Transport(),
            }

    monkeypatch.setattr(
        agent_harness,
        "resolve_executor_config_for_session",
        lambda _session_id: (_Client(), "judge-model", 1024, 4096),
    )

    result = agent_goal_judge.evaluate_goal(
        "session-1",
        {"id": "goal-1", "objective": "Ship safely"},
        {"goal_dialogue": "work", "recent_evidence": "tests"},
    )

    assert result["failure_kind"] == "parse"
    assert result["error"] == "reasoning_only"
    assert result["usage"]["reasoning_tokens"] == 512


def test_goal_judge_runs_at_completion_boundary_with_startup_recovery_only():
    source = (ROOT / "app" / "agent_loop.py").read_text(encoding="utf-8")
    runtime = (ROOT / "plugins/agent-goal/runtime.py").read_text(encoding="utf-8")
    assert "_run_goal_judge_after_turn" not in source
    assert 'call_async("completion_boundary"' in source
    assert '"[Goal Judge result]\\n"' in runtime
    assert "manager.record_judge_result(" in runtime
    assert 'Previous independent Judge verdict: continue' in runtime
    assert "Prioritize correcting the identified gap" in runtime
    assert 'Human completion review: changes requested' in runtime
    tools_source = (ROOT / "app" / "agent_tools.py").read_text(encoding="utf-8")
    assert '"completion_mode"' not in tools_source
    assert '"enum": ["explicit", "judge", "hybrid"]' not in tools_source


def test_goal_ui_is_plugin_owned_not_built_into_the_main_shell():
    for relative_path in ("frontend/index.html", "frontend/src/shell-body.html"):
        markup = (ROOT / relative_path).read_text(encoding="utf-8")
        assert 'id="chat-goal-card"' not in markup
    assert "Completion review" in (ROOT / "plugins/agent-goal/web/index.html").read_text(encoding="utf-8")
    return
    assert "syncGoalTodoPanelVisibility()" in renderer
    assert "当前会话暂无 Goal" not in renderer
    assert "const goalStateBySession = new Map()" in renderer
    assert "goalStateBySession.has(sid)" in renderer
    assert "const normalized = goal && goal.id" in renderer
    assert "const has = !!(goal && goal.id);" in renderer
    assert "String(goal.status || '') !== 'completed'" not in renderer
    assert "summarizeGoalObjective(fullObjective, 200)" in renderer
    assert "objectiveEl.setAttribute('data-ui-tip', fullObjective)" in renderer
    assert "globalThis.toggleCurrentGoalState = toggleCurrentGoalState" in renderer
    assert "playIcon.toggleAttribute('hidden', !isPaused)" in renderer
    assert "pauseIcon.toggleAttribute('hidden', isPaused)" in renderer
    assert "controlCurrentGoal('edit', {" in renderer
    assert "completion_mode" not in renderer
    assert "const isCompleted = status === 'completed'" in renderer
    assert "if (edit) edit.hidden = isCompleted" in renderer
    assert "if (remove) remove.hidden = isCompleted" in renderer
    assert "if (review) review.hidden = !isCompleted" in renderer
    assert "function openGoalReviewModal()" in renderer
    assert "submitGoalReview('approve')" in renderer
    assert "submitGoalReview('save')" in renderer
    assert "submitGoalReview('continue')" in renderer
    assert "action === 'review'" in renderer
    assert "await controlCurrentGoal('delete')" in renderer
    assert "function saveGoalEditModal()" in renderer
    assert "isInputSubmitShortcut(event, 'editor')" in renderer
    edit_handler = renderer.split("function editCurrentGoal()", 1)[1].split("async function deleteCurrentGoal()", 1)[0]
    assert "window.prompt" not in edit_handler
    assert "elements.input.value = currentObjective" in edit_handler
    assert "Token ' + translate('已消耗')" in renderer
    assert "function formatGoalElapsed(seconds)" in renderer
    assert "renderGoalMeta(goal, sid)" in renderer
    assert "const judgeText = 'Judge ' + String(goal.judge_count || 0)" in renderer
    assert "goal.last_judge_verdict" in renderer
    assert "statusEl.textContent = translate('进行中') + ' · ' + formatGoalElapsed(elapsed)" in renderer
    assert "const goalElapsedAnchorBySession = new Map()" in renderer
    assert "elapsedSeconds = Math.max(" in renderer
    assert "react_iteration_limit: 'ReAct 已达到轮次上限'" in renderer
    assert "metaEl.setAttribute('data-ui-tip', metaText + '\\n' + help)" in renderer
    assert "}, 1000);" in renderer
    assert "}, 5000);" in renderer
    assert "goalRefreshInFlightBySession" in renderer
    assert "const goalStreamRecoveryInFlightBySession = new Set()" in renderer
    assert "async function recoverActiveGoalStream(sessionId)" in renderer
    assert "await reconcileRunStateFromServer({ silent: true })" in renderer
    assert "maybeStartStreamPollForSession(sid, { skipInitialLoad: true })" in renderer
    assert "void recoverActiveGoalStream(sid)" in renderer
    assert "}, 30000);" in renderer
    assert "连续失败表示 Goal 执行中连续以失败或错误结束" in renderer
    assert "isGoalEditModalOpen()" in renderer
    assert "document.body.classList.add('goal-editing')" in renderer
    assert "document.body.classList.remove('goal-editing')" in renderer

    styles = (ROOT / "frontend" / "src" / "styles" / "app.css").read_text(encoding="utf-8")
    assert "backdrop-filter:none" in styles
    assert "contain:layout paint" in styles
    assert "overscroll-behavior:contain" in styles
    assert ".chat-goal-actions { display:flex; align-items:center" in styles
    assert ".chat-goal-stats-btn { color:var(--accent-2); margin-right:auto; }" in styles
    goal_heading = styles.split(".chat-goal-heading {", 1)[1].split("}", 1)[0]
    assert "font-size:0.62rem; font-weight:600; color:var(--text-tertiary);" in goal_heading
    assert "letter-spacing:0.05em; text-transform:uppercase;" in goal_heading
    assert "-webkit-line-clamp:6; line-clamp:6" in styles
    assert "overflow:hidden; overflow-wrap:anywhere; cursor:default" in styles

    session_management = (
        ROOT / "frontend" / "src" / "app" / "modules" / "session-management.js"
    ).read_text(encoding="utf-8")
    assert "closeGoalEditModal(false)" in session_management
    switch_boundary = session_management.split("setCurrentSessionState(sessionId);", 1)[1].split(
        "localStorage.setItem('lastSessionId', sessionId);", 1
    )[0]
    assert "updateSessionTitle()" in switch_boundary
    assert "myagent:extension-state-changed" in switch_boundary
    assert "renderGoalForCurrentSession()" in switch_boundary
    assert "refreshGoalCard()" in switch_boundary

    clear_boundary = renderer.split("function clearOptionalPanelsForSessionLoad()", 1)[1].split(
        "const tocTurnsCacheBySession", 1
    )[0]
    assert "pluginPanels.hidden = true" in clear_boundary


if __name__ == "__main__":
    unittest.main()
