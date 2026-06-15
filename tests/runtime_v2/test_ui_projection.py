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


if __name__ == "__main__":
    unittest.main()
