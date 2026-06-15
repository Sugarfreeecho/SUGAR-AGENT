import tempfile
import unittest

from app.runtime_v2 import RuntimeMirror, RuntimeUiProjection


class RuntimeUiProjectionTests(unittest.TestCase):
    def test_projects_runtime_events_to_legacy_ui_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            mirror = RuntimeMirror(tmp)
            mirror.mirror_ui_event("s1", {"type": "user", "content": "hello"})
            mirror.mirror_ui_event("s1", {"type": "status", "content": "thinking"})
            mirror.mirror_ui_event("s1", {"type": "tool_call", "tool": "shell", "result": "ok"})
            mirror.mirror_ui_event("s1", {"type": "final", "content": "done"})

            events = RuntimeUiProjection(tmp).read_ui_events("s1")

            self.assertEqual([ev["type"] for ev in events], ["user", "status", "tool_call", "final"])
            self.assertEqual(events[1]["content"], "thinking")
            self.assertEqual(events[2]["result"], "ok")

    def test_backfills_legacy_events_when_runtime_log_is_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            projection = RuntimeUiProjection(tmp)
            count = projection.ensure_backfilled_from_legacy("s1", [
                {"type": "user", "content": "hello"},
                {"type": "validate_final", "result": "PASS"},
                {"type": "final", "content": "done"},
            ])

            events = projection.read_ui_events("s1")

            self.assertEqual(count, 3)
            self.assertEqual([ev["type"] for ev in events], ["user", "validate_final", "final"])

    def test_read_ui_events_backfills_with_loader(self):
        with tempfile.TemporaryDirectory() as tmp:
            projection = RuntimeUiProjection(tmp)

            events = projection.read_ui_events("s1", legacy_loader=lambda: [
                {"type": "user", "content": "hello"},
                {"type": "final", "content": "done"},
            ])

            self.assertEqual([ev["type"] for ev in events], ["user", "final"])
            self.assertFalse(projection.needs_legacy_backfill("s1"))

    def test_read_ui_events_replaces_partial_runtime_projection(self):
        with tempfile.TemporaryDirectory() as tmp:
            mirror = RuntimeMirror(tmp)
            mirror.mirror_ui_event("s1", {"type": "user", "content": "partial"})
            projection = RuntimeUiProjection(tmp)

            events = projection.read_ui_events("s1", legacy_loader=lambda: [
                {"type": "user", "content": "legacy user"},
                {"type": "status", "content": "legacy status"},
                {"type": "final", "content": "legacy final"},
            ])

            self.assertEqual([ev["content"] for ev in events], [
                "legacy user",
                "legacy status",
                "legacy final",
            ])
            self.assertEqual(len(projection.read_ui_events_fast("s1")), 3)

    def test_pages_by_turns_from_runtime_projection(self):
        with tempfile.TemporaryDirectory() as tmp:
            mirror = RuntimeMirror(tmp)
            for index in range(4):
                mirror.mirror_ui_event("s1", {"type": "user", "content": f"u{index}"})
                mirror.mirror_ui_event("s1", {"type": "final", "content": f"a{index}"})

            page = RuntimeUiProjection(tmp).read_ui_page("s1", turns=2)

            self.assertEqual(page["total"], 8)
            self.assertTrue(page["has_older"])
            self.assertEqual([ev["content"] for ev in page["events"]], ["u2", "a2", "u3", "a3"])

    def test_legacy_truncate_observation_limits_projected_ui_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            mirror = RuntimeMirror(tmp)
            mirror.mirror_ui_event("s1", {"type": "user", "content": "u1"})
            mirror.mirror_ui_event("s1", {"type": "final", "content": "a1"})
            mirror.mirror_ui_event("s1", {"type": "user", "content": "u2"})
            mirror.mirror_ui_event("s1", {"type": "final", "content": "a2"})
            mirror.append("s1", "legacy_truncate_observed", {
                "before_index": 2,
                "old_event_count": 4,
                "new_event_count": 2,
            })

            events = RuntimeUiProjection(tmp).read_ui_events("s1")

            self.assertEqual([ev["content"] for ev in events], ["u1", "a1"])

    def test_backfills_when_runtime_log_has_only_history_ops(self):
        with tempfile.TemporaryDirectory() as tmp:
            mirror = RuntimeMirror(tmp)
            mirror.append("branch", "history_branch_created", {
                "source_session_id": "source",
                "branch_from_seq": 2,
            })
            projection = RuntimeUiProjection(tmp)
            count = projection.ensure_backfilled_from_legacy("branch", [
                {"type": "user", "content": "u1"},
                {"type": "final", "content": "a1"},
            ])

            events = projection.read_ui_events("branch")

            self.assertEqual(count, 2)
            self.assertEqual([ev["content"] for ev in events], ["u1", "a1"])

    def test_does_not_backfill_when_runtime_has_projectable_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            mirror = RuntimeMirror(tmp)
            mirror.mirror_ui_event("s1", {"type": "user", "content": "runtime"})
            projection = RuntimeUiProjection(tmp)

            self.assertFalse(projection.needs_legacy_backfill("s1"))
            count = projection.ensure_backfilled_from_legacy("s1", [
                {"type": "user", "content": "legacy"},
            ])

            events = projection.read_ui_events("s1")

            self.assertEqual(count, 0)
            self.assertEqual([ev["content"] for ev in events], ["runtime"])


if __name__ == "__main__":
    unittest.main()
