import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.agent_goal import GoalError, GoalManager, goal_enabled


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
            with self.assertRaisesRegex(GoalError, f"{expected}/3"):
                self.manager.update_status("s1", "blocked", "missing credential", report_id=f"run-{expected}")
            self.assertEqual(self.manager.get("s1")["status"], "active")
        goal = self.manager.update_status("s1", "blocked", "missing credential", report_id="run-3")
        self.assertEqual(goal["status"], "blocked")

    def test_same_run_cannot_increment_blocker_streak(self):
        self.manager.create("s1", "Ship goal support")
        for _ in range(2):
            with self.assertRaisesRegex(GoalError, "1/3"):
                self.manager.update_status("s1", "blocked", "missing credential", report_id="same-run")

    def test_budget_pauses_and_user_can_resume(self):
        self.manager.create("s1", "Budgeted goal", token_budget=10)
        goal = self.manager.record_run("s1", 12)
        self.assertEqual(goal["status"], "paused")
        self.assertEqual(goal["remaining_tokens"], 0)
        resumed = self.manager.user_action("s1", "resume")
        self.assertEqual(resumed["status"], "active")

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


if __name__ == "__main__":
    unittest.main()
