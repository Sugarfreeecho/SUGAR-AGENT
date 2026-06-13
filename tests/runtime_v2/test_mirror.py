import tempfile
import unittest

from app.runtime_v2 import RuntimeMirror


class RuntimeMirrorTests(unittest.TestCase):
    def test_mirrors_legacy_user_and_final_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            mirror = RuntimeMirror(tmp)
            mirror.mirror_ui_event("s1", {"type": "user", "content": "hello"})
            mirror.mirror_ui_event("s1", {"type": "final", "content": "done"})

            snapshot = mirror.snapshots.read("s1")

            self.assertEqual([m["role"] for m in snapshot["messages"]], ["user", "assistant"])
            self.assertEqual(snapshot["last_seq"], 2)

    def test_mirrors_run_lifecycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            mirror = RuntimeMirror(tmp)
            mirror.mirror_run_started("s1", "r1")
            mirror.mirror_run_interrupted("s1", "r1")

            snapshot = mirror.snapshots.read("s1")

            self.assertEqual(snapshot["runs"]["r1"]["status"], "interrupted")
            self.assertEqual(snapshot["active_runs"], [])


if __name__ == "__main__":
    unittest.main()
