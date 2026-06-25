import tempfile
import unittest

from app.runtime_v2 import RuntimeHistoryOps, RuntimeMirror, RuntimeUiProjection


class RuntimeHistoryOpsTests(unittest.TestCase):
    def test_rewrite_and_delete_project_visible_messages_without_rewriting_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            mirror = RuntimeMirror(tmp)
            mirror.mirror_ui_event("s1", {"type": "user", "content": "old"})
            mirror.mirror_ui_event("s1", {"type": "final", "content": "answer"})

            ops = RuntimeHistoryOps(tmp)
            ops.rewrite_message("s1", 1, "new")
            ops.delete_message("s1", 2)

            snapshot = ops.snapshots.read("s1")
            events = ops.event_log.read_all("s1")

            self.assertEqual([ev.type for ev in events], [
                "message_user",
                "message_assistant_final",
                "message_rewritten",
                "message_deleted",
            ])
            self.assertEqual(len(snapshot["messages"]), 2)
            self.assertEqual(len(snapshot["visible_messages"]), 1)
            self.assertEqual(snapshot["visible_messages"][0]["payload"]["content"], "new")
            self.assertTrue(snapshot["visible_messages"][0]["rewritten"])

    def test_compaction_changes_model_messages_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            mirror = RuntimeMirror(tmp)
            mirror.mirror_ui_event("s1", {"type": "user", "content": "u1"})
            mirror.mirror_ui_event("s1", {"type": "final", "content": "a1"})
            mirror.mirror_ui_event("s1", {"type": "user", "content": "u2"})

            ops = RuntimeHistoryOps(tmp)
            ops.compact_history("s1", summary="summary", compacted_before_seq=3)

            snapshot = ops.snapshots.read("s1")

            self.assertEqual(len(snapshot["visible_messages"]), 3)
            self.assertEqual([m["role"] for m in snapshot["model_messages"]], ["system", "user"])
            self.assertEqual(snapshot["model_messages"][0]["payload"]["kind"], "history_compaction")

    def test_visible_range_hides_without_deleting_source_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            mirror = RuntimeMirror(tmp)
            mirror.mirror_ui_event("s1", {"type": "user", "content": "u1"})
            mirror.mirror_ui_event("s1", {"type": "final", "content": "a1"})
            mirror.mirror_ui_event("s1", {"type": "user", "content": "u2"})

            ops = RuntimeHistoryOps(tmp)
            ops.change_visible_range("s1", from_seq=3)

            snapshot = ops.snapshots.read("s1")

            self.assertEqual(len(snapshot["messages"]), 3)
            self.assertEqual(len(snapshot["visible_messages"]), 1)
            self.assertEqual(snapshot["visible_messages"][0]["payload"]["content"], "u2")

    def test_model_history_replace_changes_model_projection_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            mirror = RuntimeMirror(tmp)
            mirror.mirror_ui_event("s1", {"type": "user", "content": "visible user"})
            mirror.mirror_ui_event("s1", {"type": "final", "content": "visible final"})

            ops = RuntimeHistoryOps(tmp)
            ops.append_model_message("s1", "user", "old model")
            ops.replace_model_history("s1", [
                {"type": "system", "content": "summary"},
                {"type": "user", "content": "recent user"},
            ], reason="compact")

            snapshot = ops.snapshots.read("s1")

            self.assertEqual([m["payload"]["content"] for m in snapshot["visible_messages"]], [
                "visible user",
                "visible final",
            ])
            self.assertEqual([m["role"] for m in snapshot["model_messages"]], ["system", "user"])
            self.assertEqual(snapshot["model_messages"][1]["payload"]["content"], "recent user")

    def test_legacy_observation_does_not_change_projected_messages(self):
        with tempfile.TemporaryDirectory() as tmp:
            mirror = RuntimeMirror(tmp)
            mirror.mirror_ui_event("s1", {"type": "user", "content": "u1"})
            mirror.mirror_ui_event("s1", {"type": "final", "content": "a1"})

            ops = RuntimeHistoryOps(tmp)
            ops.observe_legacy_truncate(
                "s1",
                before_index=1,
                old_event_count=2,
                new_event_count=1,
            )

            snapshot = ops.snapshots.read("s1")
            events = ops.event_log.read_all("s1")

            self.assertEqual([ev.type for ev in events], [
                "message_user",
                "message_assistant_final",
                "legacy_truncate_observed",
            ])
            self.assertEqual(len(snapshot["messages"]), 2)
            self.assertEqual(len(snapshot["visible_messages"]), 2)
            self.assertEqual(snapshot["legacy_observations"][0]["type"], "legacy_truncate_observed")

    def test_branch_records_source_and_seeds_visible_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            mirror = RuntimeMirror(tmp)
            mirror.mirror_ui_event("source", {"type": "user", "content": "u1"})
            mirror.mirror_ui_event("source", {"type": "final", "content": "a1"})
            mirror.mirror_ui_event("source", {"type": "user", "content": "u2"})

            ops = RuntimeHistoryOps(tmp)
            ops.observe_legacy_branch(
                "source",
                source_session_id="source",
                new_session_id="branch",
                before_index=2,
                new_event_count=2,
                name="branch name",
            )
            ops.create_branch("branch", source_session_id="source", branch_from_seq=2, name="branch name")

            source_snapshot = ops.snapshots.read("source")
            branch_snapshot = ops.snapshots.read("branch")
            branch_events = RuntimeUiProjection(tmp).read_ui_events("branch")

            self.assertEqual(source_snapshot["legacy_observations"][0]["payload"]["new_session_id"], "branch")
            self.assertEqual(branch_snapshot["history_ops"][0]["type"], "history_branch_created")
            self.assertEqual([m["payload"]["content"] for m in branch_snapshot["visible_messages"]], ["u1", "a1"])
            self.assertEqual([ev["content"] for ev in branch_events], ["u1", "a1"])

    def test_branch_does_not_duplicate_existing_legacy_seed(self):
        with tempfile.TemporaryDirectory() as tmp:
            mirror = RuntimeMirror(tmp)
            mirror.mirror_ui_event("source", {"type": "user", "content": "u1"})
            mirror.mirror_ui_event("source", {"type": "final", "content": "a1"})
            projection = RuntimeUiProjection(tmp)
            projection.replace_from_legacy("branch", [
                {"type": "user", "content": "u1"},
                {"type": "final", "content": "a1"},
            ], reason="legacy_branch_seed")

            RuntimeHistoryOps(tmp).create_branch("branch", source_session_id="source", branch_from_seq=2)

            branch_events = RuntimeUiProjection(tmp).read_ui_events("branch")

            self.assertEqual([ev["content"] for ev in branch_events], ["u1", "a1"])


if __name__ == "__main__":
    unittest.main()
