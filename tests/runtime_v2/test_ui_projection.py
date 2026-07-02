import tempfile
import unittest

from app.runtime_v2 import RuntimeMirror, RuntimeUiProjection
from app.runtime_v2.blob_store import BlobStore


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

    def test_read_ui_events_replaces_expanded_runtime_projection(self):
        with tempfile.TemporaryDirectory() as tmp:
            mirror = RuntimeMirror(tmp)
            mirror.mirror_ui_event("s1", {"type": "user", "content": "duplicate user"})
            mirror.mirror_ui_event("s1", {"type": "final", "content": "duplicate final"})
            projection = RuntimeUiProjection(tmp)

            events = projection.read_ui_events("s1", legacy_loader=lambda: [
                {"type": "user", "content": "legacy user"},
            ])

            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["content"], "legacy user")

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

    def test_tail_page_does_not_drop_dense_process_events_inside_recent_turns(self):
        with tempfile.TemporaryDirectory() as tmp:
            mirror = RuntimeMirror(tmp)
            mirror.mirror_ui_event("s1", {"type": "user", "content": "older"})
            mirror.mirror_ui_event("s1", {"type": "status", "content": "older process"})
            mirror.mirror_ui_event("s1", {"type": "final", "content": "older answer"})
            mirror.mirror_ui_event("s1", {"type": "user", "content": "dense"})
            for index in range(650):
                mirror.mirror_ui_event("s1", {"type": "status", "content": f"process {index}"})
            mirror.mirror_ui_event("s1", {"type": "final", "content": "dense answer"})

            page = RuntimeUiProjection(tmp).read_ui_page("s1", turns=1)

            self.assertEqual(page["total"], 655)
            self.assertEqual(page["range_start"], 3)
            self.assertEqual(page["range_end"], 655)
            self.assertTrue(page["has_older"])
            self.assertEqual(len(page["events"]), 652)
            self.assertEqual(page["events"][0]["content"], "dense")
            self.assertEqual(page["events"][1]["content"], "process 0")
            self.assertEqual(page["events"][-1]["content"], "dense answer")

    def test_pages_by_turns_backfill_when_runtime_projection_is_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            projection = RuntimeUiProjection(tmp)

            page = projection.read_ui_page(
                "s1",
                turns=2,
                legacy_loader=lambda: [
                    {"type": "user", "content": "u0"},
                    {"type": "final", "content": "a0"},
                    {"type": "user", "content": "u1"},
                    {"type": "final", "content": "a1"},
                    {"type": "user", "content": "u2"},
                    {"type": "final", "content": "a2"},
                ],
            )

            self.assertEqual(page["total"], 6)
            self.assertEqual([ev["content"] for ev in page["events"]], ["u1", "a1", "u2", "a2"])

    def test_pages_after_ui_index_from_runtime_projection(self):
        with tempfile.TemporaryDirectory() as tmp:
            mirror = RuntimeMirror(tmp)
            for index in range(3):
                mirror.mirror_ui_event("s1", {"type": "user", "content": f"u{index}"})
                mirror.mirror_ui_event("s1", {"type": "final", "content": f"a{index}"})

            page = RuntimeUiProjection(tmp).read_ui_page("s1", after_index=1, limit=3)

            self.assertEqual(page["total"], 6)
            self.assertEqual(page["range_start"], 2)
            self.assertEqual(page["range_end"], 5)
            self.assertTrue(page["has_newer"])
            self.assertEqual([ev["content"] for ev in page["events"]], ["u1", "a1", "u2"])

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

    def test_native_visible_range_ui_index_limits_projected_ui_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            mirror = RuntimeMirror(tmp)
            mirror.mirror_ui_event("s1", {"type": "user", "content": "u1"})
            mirror.mirror_ui_event("s1", {"type": "final", "content": "a1"})
            mirror.mirror_ui_event("s1", {"type": "user", "content": "u2"})
            mirror.mirror_ui_event("s1", {"type": "final", "content": "a2"})
            mirror.append("s1", "visible_range_changed", {
                "to_ui_index": 2,
                "reason": "test",
            })
            projection = RuntimeUiProjection(tmp)

            events = projection.read_ui_events("s1")
            count, latest_seq = projection.count_ui_events_light("s1")
            page = projection.read_ui_page("s1", turns=2)

            self.assertEqual([ev["content"] for ev in events], ["u1", "a1"])
            self.assertEqual(count, 2)
            self.assertGreater(latest_seq, 0)
            self.assertEqual([ev["content"] for ev in page["events"]], ["u1", "a1"])

    def test_user_turns_are_available_from_projection_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            mirror = RuntimeMirror(tmp)
            mirror.mirror_ui_event("s1", {"type": "user", "content": "first question"})
            mirror.mirror_ui_event("s1", {"type": "final", "content": "answer"})
            mirror.mirror_ui_event("s1", {"type": "user", "content": "second question"})
            projection = RuntimeUiProjection(tmp)

            self.assertEqual(projection.read_user_turns_light("s1"), [
                {"event_index": 0, "preview": "first question"},
                {"event_index": 2, "preview": "second question"},
            ])
            index = projection._read_or_build_ui_index("s1")
            self.assertEqual(index["user_turns"], [
                {"event_index": 0, "preview": "first question"},
                {"event_index": 2, "preview": "second question"},
            ])

    def test_user_steer_stays_process_event_and_is_not_toc_turn(self):
        with tempfile.TemporaryDirectory() as tmp:
            mirror = RuntimeMirror(tmp)
            mirror.mirror_ui_event("s1", {"type": "user", "content": "first question"})
            mirror.mirror_ui_event("s1", {"type": "user_steer", "content": "follow up", "steer": True})
            projection = RuntimeUiProjection(tmp)

            events = projection.read_ui_events("s1")

            self.assertEqual(events[1]["type"], "user_steer")
            self.assertTrue(events[1]["steer"])
            self.assertEqual(projection.read_user_turns_light("s1"), [
                {"event_index": 0, "preview": "first question"},
            ])

    def test_maps_visible_ui_index_to_runtime_seq(self):
        with tempfile.TemporaryDirectory() as tmp:
            mirror = RuntimeMirror(tmp)
            e1 = mirror.mirror_ui_event("s1", {"type": "user", "content": "u1"})
            e2 = mirror.mirror_ui_event("s1", {"type": "final", "content": "a1"})
            mirror.mirror_ui_event("s1", {"type": "user", "content": "u2"})
            mirror.append("s1", "visible_range_changed", {
                "to_ui_index": 2,
                "reason": "test",
            })
            projection = RuntimeUiProjection(tmp)

            self.assertEqual(projection.ui_index_to_runtime_seq("s1", 0), e1.seq)
            self.assertEqual(projection.ui_index_to_runtime_seq("s1", 1), e2.seq)
            self.assertIsNone(projection.ui_index_to_runtime_seq("s1", 2))
            self.assertEqual(projection.runtime_seq_to_ui_end_index("s1", e1.seq), 1)
            self.assertEqual(projection.runtime_seq_to_ui_end_index("s1", e2.seq), 2)
            self.assertIsNone(projection.runtime_seq_to_ui_end_index("s1", 3))

    def test_projected_ui_events_include_runtime_seq(self):
        with tempfile.TemporaryDirectory() as tmp:
            mirror = RuntimeMirror(tmp)
            e1 = mirror.mirror_ui_event("s1", {"type": "user", "content": "u1"})
            e2 = mirror.mirror_ui_event("s1", {"type": "final", "content": "a1"})

            events = RuntimeUiProjection(tmp).read_ui_events("s1")

            self.assertEqual(events[0]["runtime_seq"], e1.seq)
            self.assertEqual(events[0]["runtime_event_type"], "message_user")
            self.assertEqual(events[1]["runtime_seq"], e2.seq)
            self.assertEqual(events[1]["runtime_event_type"], "message_assistant_final")

    def test_visible_range_to_seq_limits_projected_ui_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            mirror = RuntimeMirror(tmp)
            e1 = mirror.mirror_ui_event("s1", {"type": "user", "content": "u1"})
            e2 = mirror.mirror_ui_event("s1", {"type": "final", "content": "a1"})
            e3 = mirror.mirror_ui_event("s1", {"type": "user", "content": "u2"})
            mirror.mirror_ui_event("s1", {"type": "final", "content": "a2"})
            mirror.append("s1", "visible_range_changed", {
                "to_seq": e2.seq,
                "reason": "test",
            })
            projection = RuntimeUiProjection(tmp)

            events = projection.read_ui_events("s1")
            count, latest_seq = projection.count_ui_events_light("s1")

            self.assertEqual([ev["content"] for ev in events], ["u1", "a1"])
            self.assertEqual(count, 2)
            self.assertGreater(latest_seq, e3.seq)
            self.assertEqual(projection.previous_visible_runtime_seq_before("s1", e1.seq), 0)
            self.assertEqual(projection.previous_visible_runtime_seq_before("s1", e2.seq), e1.seq)
            self.assertIsNone(projection.previous_visible_runtime_seq_before("s1", e3.seq))

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

    def test_ui_projection_cache_invalidates_when_log_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            mirror = RuntimeMirror(tmp)
            projection = RuntimeUiProjection(tmp)
            mirror.mirror_ui_event("s1", {"type": "user", "content": "first"})

            first = projection.read_ui_events_fast("s1")
            mirror.mirror_ui_event("s1", {"type": "final", "content": "second"})
            second = projection.read_ui_events_fast("s1")

            self.assertEqual([ev["content"] for ev in first], ["first"])
            self.assertEqual([ev["content"] for ev in second], ["first", "second"])

    def test_hydrates_blob_refs_for_large_tool_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            ref = BlobStore(f"{tmp}/s1").put_text("large result")
            mirror = RuntimeMirror(tmp)
            mirror.append("s1", "tool_finished", {
                "type": "tool_call",
                "tool": "read_file",
                "result_ref": ref,
            })

            events = RuntimeUiProjection(tmp).read_ui_events("s1")

            self.assertEqual(events[0]["result"], "large result")


if __name__ == "__main__":
    unittest.main()
