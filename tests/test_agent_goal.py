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
    assert "setGoalStateForSession(eventSessionId, goal)" in live_handler
    assert "continue;" in live_handler
    assert "completedTool === 'create_goal'" in frontend
    assert "completedTool === 'update_goal'" in frontend


def test_goal_card_is_present_in_the_vite_entry_and_shell_source():
    for relative_path in ("frontend/index.html", "frontend/src/shell-body.html"):
        markup = (ROOT / relative_path).read_text(encoding="utf-8")
        assert 'id="chat-goal-card"' in markup
        assert 'id="chat-goal-status"' in markup
        assert 'id="chat-goal-objective"' in markup
        assert 'id="chat-goal-meta"' in markup
        assert 'class="chat-goal-icon-btn chat-goal-stats-btn"' in markup
        assert markup.index('id="chat-goal-meta"') < markup.index('id="chat-goal-toggle"')
        assert 'id="chat-goal-toggle"' in markup
        assert 'id="chat-goal-edit"' in markup
        assert 'id="chat-goal-delete"' in markup
        assert 'class="chat-goal-icon-pause"' in markup
        assert 'class="chat-goal-icon-play"' in markup
        assert 'id="goal-edit-modal-root"' in markup
        assert 'id="goal-edit-textarea"' in markup
        assert 'maxlength="12000"' in markup
        assert 'id="goal-edit-char-count"' in markup
        assert 'id="goal-edit-save"' in markup
        assert 'id="chat-todo-card"' in markup
        assert markup.index('id="chat-goal-card"') < markup.index('id="chat-todo-card"')

    renderer = (
        ROOT / "frontend" / "src" / "app" / "modules" / "toc-todo.js"
    ).read_text(encoding="utf-8")
    assert "card.hidden = !has" in renderer
    assert "todoCard.hidden = !has" in renderer
    assert "syncGoalTodoPanelVisibility()" in renderer
    assert "当前会话暂无 Goal" not in renderer
    assert "const goalStateBySession = new Map()" in renderer
    assert "goalStateBySession.has(sid)" in renderer
    assert "String(goal.status || '') !== 'completed'" in renderer
    assert "summarizeGoalObjective(fullObjective, 200)" in renderer
    assert "objectiveEl.setAttribute('data-ui-tip', fullObjective)" in renderer
    assert "globalThis.toggleCurrentGoalState = toggleCurrentGoalState" in renderer
    assert "playIcon.toggleAttribute('hidden', !isPaused)" in renderer
    assert "pauseIcon.toggleAttribute('hidden', isPaused)" in renderer
    assert "controlCurrentGoal('edit', { objective: objective })" in renderer
    assert "await controlCurrentGoal('delete')" in renderer
    assert "function saveGoalEditModal()" in renderer
    assert "event.ctrlKey || event.metaKey" in renderer
    edit_handler = renderer.split("function editCurrentGoal()", 1)[1].split("async function deleteCurrentGoal()", 1)[0]
    assert "window.prompt" not in edit_handler
    assert "elements.input.value = currentObjective" in edit_handler
    assert "Token ' + translate('已消耗')" in renderer
    assert "function formatGoalElapsed(seconds)" in renderer
    assert "renderGoalMeta(goal, sid)" in renderer
    assert "statusEl.textContent = translate('进行中') + ' · ' + formatGoalElapsed(elapsed)" in renderer
    assert "metaEl.setAttribute('data-ui-tip', metaText + '\\n' + help)" in renderer
    assert "}, 1000);" in renderer
    assert "}, 5000);" in renderer
    assert "goalRefreshInFlightBySession" in renderer
    assert "const goalStreamRecoveryInFlightBySession = new Set()" in renderer
    assert "async function recoverActiveGoalStream(sessionId)" in renderer
    assert "await reconcileRunStateFromServer({ silent: true })" in renderer
    assert "maybeStartStreamPollForSession(sid, { skipInitialLoad: true })" in renderer
    assert "void recoverActiveGoalStream(sid)" in renderer
    assert "}, 2000);" in renderer
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
    assert "-webkit-line-clamp:6; line-clamp:6" in styles
    assert "overflow:hidden; overflow-wrap:anywhere; cursor:default" in styles

    session_management = (
        ROOT / "frontend" / "src" / "app" / "modules" / "session-management.js"
    ).read_text(encoding="utf-8")
    assert "closeGoalEditModal(false)" in session_management
    switch_boundary = session_management.split("setCurrentSessionState(sessionId);", 1)[1][:300]
    assert "renderGoalForCurrentSession()" in switch_boundary
    assert "refreshGoalCard()" in switch_boundary


if __name__ == "__main__":
    unittest.main()
