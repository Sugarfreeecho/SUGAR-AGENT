import tempfile
import unittest
from pathlib import Path

from app.runtime_v2 import RuntimeHistoryOps, RuntimeMirror
from scripts.benchmark_runtime_versions import benchmark_session, page_events


class RuntimeBenchmarkToolTests(unittest.TestCase):
    def test_page_events_by_turns(self):
        events = [
            {"type": "user", "content": "u1"},
            {"type": "final", "content": "a1"},
            {"type": "user", "content": "u2"},
            {"type": "final", "content": "a2"},
            {"type": "user", "content": "u3"},
        ]

        page = page_events(events, turns=2)

        self.assertEqual([item["content"] for item in page["events"]], ["u2", "a2", "u3"])
        self.assertEqual(page["total"], 5)

    def test_benchmark_session_returns_v1_and_v2_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sid = "s1"
            session = root / sid
            session.mkdir()
            (session / "ui_events.json").write_text(
                '[{"type":"user","content":"u"},{"type":"final","content":"a"}]',
                encoding="utf-8",
            )
            (session / "llm_history.json").write_text(
                '[{"type":"user","content":"u"},{"type":"assistant","content":"a"}]',
                encoding="utf-8",
            )
            mirror = RuntimeMirror(root)
            mirror.mirror_ui_event(sid, {"type": "user", "content": "u"})
            mirror.mirror_ui_event(sid, {"type": "final", "content": "a"})
            RuntimeHistoryOps(root).replace_model_history(
                sid,
                [{"type": "user", "content": "u"}, {"type": "assistant", "content": "a"}],
            )

            result = benchmark_session(root, sid, repeats=1, turns=1)

            self.assertEqual(result["legacy_ui_count"], 2)
            self.assertEqual(result["runtime_v2_ui_count"], 2)
            self.assertIn("v1_ui_full", result["benchmarks"])
            self.assertIn("v2_ui_full", result["benchmarks"])


if __name__ == "__main__":
    unittest.main()
