import tempfile
import unittest
from pathlib import Path

from app.runtime_v2 import RuntimeHistoryOps, RuntimeMirror
from scripts.audit_runtime_versions import audit_session, load_json_list, signatures_match


class RuntimeAuditToolTests(unittest.TestCase):
    def test_audit_detects_and_repairs_ui_and_model_mismatch(self):
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
            RuntimeMirror(root).mirror_ui_event(sid, {"type": "user", "content": "partial"})

            before = audit_session(root, sid)

            self.assertFalse(before.ui_ok)
            self.assertFalse(before.model_ok)

            after = audit_session(root, sid, repair_ui=True, repair_model=True)

            self.assertTrue(after.ui_ok)
            self.assertTrue(after.model_ok)
            self.assertEqual(after.repaired_ui, 2)
            self.assertEqual(after.repaired_model, 2)

    def test_load_json_list_supports_bom(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rows.json"
            path.write_text('\ufeff[{"type":"user"}]', encoding="utf-8")

            self.assertEqual(load_json_list(path), [{"type": "user"}])

    def test_model_signatures_normalize_legacy_langchain_roles(self):
        self.assertTrue(signatures_match(
            [{"type": "human", "content": "u"}, {"type": "llm", "content": "a"}],
            [{"type": "user", "content": "u"}, {"type": "assistant", "content": "a"}],
            kind="model",
        ))

    def test_audit_reports_and_repairs_runtime_v2_active_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sid = "s1"
            (root / sid).mkdir()
            RuntimeMirror(root).mirror_run_started(sid, "r1")

            before = audit_session(root, sid)

            self.assertEqual(before.runtime_v2_active_run_count, 1)

            after = audit_session(root, sid, repair_runs=True)

            self.assertEqual(after.repaired_runs, 1)
            self.assertEqual(after.runtime_v2_active_run_count, 0)


if __name__ == "__main__":
    unittest.main()
