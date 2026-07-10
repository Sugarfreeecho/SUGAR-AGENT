import tempfile
import unittest
from pathlib import Path

from app.runtime_v2 import RuntimeHistoryOps, RuntimeMirror
from scripts.audit_runtime_versions import audit_session, inspect_event_log, load_json_list, signatures_match, summarize


class RuntimeAuditToolTests(unittest.TestCase):
    def test_structural_audit_reports_bad_and_duplicate_sequences(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.jsonl"
            path.write_text(
                '{"seq":1,"type":"message_user","session_id":"s","payload":{}}\n'
                '{bad}\n'
                '{"seq":1,"type":"message_user","session_id":"s","payload":{}}\n',
                encoding="utf-8",
            )
            result = inspect_event_log(path)
            self.assertEqual(result["bad_lines"], 1)
            self.assertEqual(result["duplicate_seqs"], 1)
            self.assertEqual(result["non_monotonic_seqs"], 1)

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

    def test_audit_treats_pure_runtime_v2_sessions_as_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sid = "s1"
            (root / sid).mkdir()
            RuntimeMirror(root).mirror_ui_event(sid, {"type": "user", "content": "v2 user"})
            RuntimeHistoryOps(root).replace_model_history(
                sid,
                [{"type": "user", "content": "v2 user"}],
                reason="test",
            )

            row = audit_session(root, sid)
            summary = summarize([row])

            self.assertTrue(row.ui_ok)
            self.assertTrue(row.model_ok)
            self.assertEqual(row.ui_status, "v2_only")
            self.assertEqual(row.model_status, "v2_only")
            self.assertEqual(summary["ui_mismatch"], 0)
            self.assertEqual(summary["model_mismatch"], 0)
            self.assertEqual(summary["ui_v2_only"], 1)
            self.assertEqual(summary["model_v2_only"], 1)

    def test_audit_treats_runtime_v2_ahead_of_legacy_prefix_as_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sid = "s1"
            session = root / sid
            session.mkdir()
            (session / "ui_events.json").write_text(
                '[{"type":"user","content":"u"}]',
                encoding="utf-8",
            )
            (session / "llm_history.json").write_text(
                '[{"type":"user","content":"u"}]',
                encoding="utf-8",
            )
            mirror = RuntimeMirror(root)
            mirror.mirror_ui_event(sid, {"type": "user", "content": "u"})
            mirror.mirror_ui_event(sid, {"type": "final", "content": "a"})
            RuntimeHistoryOps(root).replace_model_history(
                sid,
                [
                    {"type": "user", "content": "u"},
                    {"type": "assistant", "content": "a"},
                ],
                reason="test",
            )

            row = audit_session(root, sid)
            summary = summarize([row])

            self.assertTrue(row.ui_ok)
            self.assertTrue(row.model_ok)
            self.assertEqual(row.ui_status, "v2_ahead")
            self.assertEqual(row.model_status, "v2_ahead")
            self.assertEqual(summary["ui_mismatch"], 0)
            self.assertEqual(summary["model_mismatch"], 0)
            self.assertEqual(summary["ui_v2_ahead"], 1)
            self.assertEqual(summary["model_v2_ahead"], 1)

    def test_audit_reports_first_signature_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sid = "s1"
            session = root / sid
            session.mkdir()
            (session / "ui_events.json").write_text(
                '[{"type":"user","content":"legacy"}]',
                encoding="utf-8",
            )
            RuntimeMirror(root).mirror_ui_event(sid, {"type": "user", "content": "runtime"})

            row = audit_session(root, sid)

            self.assertFalse(row.ui_ok)
            self.assertEqual(row.ui_first_mismatch["index"], 0)
            self.assertEqual(row.ui_first_mismatch["legacy"], ["user", "legacy"])
            self.assertEqual(row.ui_first_mismatch["runtime_v2"], ["user", "runtime"])

    def test_audit_ignores_state_only_ui_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sid = "s1"
            session = root / sid
            session.mkdir()
            (session / "ui_events.json").write_text(
                '[{"type":"user","content":"u"}]',
                encoding="utf-8",
            )
            mirror = RuntimeMirror(root)
            mirror.mirror_ui_event(sid, {"type": "cache_stats", "input": 1})
            mirror.mirror_ui_event(sid, {"type": "context_tokens", "estimated": 1})
            mirror.mirror_ui_event(sid, {"type": "user", "content": "u"})

            row = audit_session(root, sid)

            self.assertTrue(row.ui_ok)
            self.assertEqual(row.ui_status, "match")

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
