import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from app.agent_goal import GoalError, GoalManager, goal_enabled


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
        self.assertEqual(self.manager.get("s1")["id"], created["id"])
        with self.assertRaises(GoalError):
            self.manager.create("s1", "Another goal")

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

    def test_completed_goal_allows_replacement(self):
        first = self.manager.create("s1", "First")
        self.manager.update_status("s1", "completed")
        second = self.manager.create("s1", "Second")
        self.assertNotEqual(first["id"], second["id"])

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
    agent_loop = (ROOT / "app" / "agent_loop.py").read_text(encoding="utf-8")
    goal_branch = agent_loop.split(
        'if tool_name in {"create_goal", "get_goal", "update_goal"}:', 1
    )[1].split('if tool_name == "update_todo":', 1)[0]
    assert '"type": "goal_state"' in goal_branch
    assert '"ephemeral": True' in goal_branch
    assert "await _push_stream_event(" in goal_branch

    frontend = (
        ROOT / "frontend" / "src" / "app" / "modules" / "sse-handling.js"
    ).read_text(encoding="utf-8")
    live_handler = frontend.split("if (parsed.type === 'goal_state')", 1)[1].split(
        "if (parsed.type === 'user_steer'", 1
    )[0]
    assert "renderGoalCard(goal)" in live_handler
    assert "continue;" in live_handler
    assert "completedTool === 'create_goal'" in frontend
    assert "completedTool === 'update_goal'" in frontend


if __name__ == "__main__":
    unittest.main()
