import tempfile
import unittest

from app.runtime_v2 import RuntimeHistoryOps, RuntimeMirror, RuntimeUiProjection
from app.runtime_v2.blob_store import BlobStore


class RuntimeUiProjectionTests(unittest.TestCase):
    def test_goal_history_projection_omits_repeated_heavy_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            goal = {
                "id": "goal-1",
                "objective": "large objective " * 1000,
                "version": 7,
                "status": "active",
                "used_tokens": 123,
                "token_budget": 1000,
                "accounted_usage_ids": [f"usage-{index}" for index in range(500)],
                "accounted_run_ids": [f"run-{index}" for index in range(100)],
            }
            RuntimeHistoryOps(tmp).update_goal("s1", goal)

            event = RuntimeUiProjection(tmp).read_ui_events("s1")[0]

            self.assertEqual(event["type"], "goal_state")
            self.assertEqual(event["goal_event"], "goal_updated")
            self.assertEqual(event["id"], "goal-1")
            self.assertEqual(event["version"], 7)
            self.assertEqual(event["status"], "active")
            self.assertEqual(event["used_tokens"], 123)
            self.assertEqual(event["token_budget"], 1000)
            self.assertEqual(event["runtime_seq"], 1)
            self.assertNotIn("objective", event)
            self.assertNotIn("accounted_usage_ids", event)
            self.assertNotIn("accounted_run_ids", event)

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

    def test_blank_llm_rows_are_not_projected_into_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            mirror = RuntimeMirror(tmp)
            mirror.mirror_ui_event("s1", {"type": "user", "content": "hello"})
            mirror.mirror_ui_event("s1", {"type": "llm_reasoning", "content": " \n "})
            mirror.mirror_ui_event("s1", {"type": "llm_response", "content": ""})
            mirror.mirror_ui_event("s1", {"type": "llm_response", "content": "visible"})

            events = RuntimeUiProjection(tmp).read_ui_events("s1")

            self.assertEqual([event["type"] for event in events], ["user", "llm_response"])
            self.assertEqual(events[-1]["content"], "visible")

    def test_repairs_legacy_tool_before_llm_order_and_preserves_tool_call_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            mirror = RuntimeMirror(tmp)
            mirror.mirror_ui_event("s1", {"type": "user", "content": "question"})
            second_tool = mirror.append("s1", "tool_started", {
                "type": "tool_call",
                "tool": "second",
                "react_iter": 1,
                "tool_call_index": 1,
            })
            first_tool = mirror.append("s1", "tool_started", {
                "type": "tool_call",
                "tool": "first",
                "react_iter": 1,
                "tool_call_index": 0,
            })
            response = mirror.append("s1", "ui_event", {
                "type": "llm_response",
                "content": "response",
                "react_iter": 1,
            })
            reasoning = mirror.append("s1", "ui_event", {
                "type": "llm_reasoning",
                "content": "reasoning",
                "react_iter": 1,
            })
            projection = RuntimeUiProjection(tmp)

            events = projection.read_ui_events("s1")
            page = projection.read_ui_page("s1", turns=1)
            index = projection._read_or_build_ui_index("s1")

            self.assertEqual(
                [(event["type"], event.get("tool")) for event in events[1:]],
                [
                    ("llm_reasoning", None),
                    ("llm_response", None),
                    ("tool_call", "first"),
                    ("tool_call", "second"),
                ],
            )
            expected_seqs = [reasoning.seq, response.seq, first_tool.seq, second_tool.seq]
            self.assertEqual([event["runtime_seq"] for event in events[1:]], expected_seqs)
            self.assertEqual([event["runtime_seq"] for event in page["events"][1:]], expected_seqs)
            self.assertEqual(index["runtime_seqs"][1:], expected_seqs)

    def test_incremental_projection_repairs_inverted_process_batch(self):
        with tempfile.TemporaryDirectory() as tmp:
            mirror = RuntimeMirror(tmp)
            first = mirror.mirror_ui_event("s1", {"type": "user", "content": "question"})
            mirror.append("s1", "tool_started", {
                "type": "tool_call",
                "tool": "shell",
                "react_iter": 2,
            })
            mirror.append("s1", "ui_event", {
                "type": "llm_response",
                "content": "response",
                "react_iter": 2,
            })
            mirror.append("s1", "ui_event", {
                "type": "llm_reasoning",
                "content": "reasoning",
                "react_iter": 2,
            })

            page = RuntimeUiProjection(tmp).read_ui_after_runtime_seq(
                "s1", after_runtime_seq=first.seq
            )

            self.assertFalse(page["requires_reprojection"])
            self.assertEqual(
                [event["type"] for event in page["events"]],
                ["llm_reasoning", "llm_response", "tool_call"],
            )

    def test_ui_index_rebuilds_when_late_llm_row_must_precede_indexed_tool(self):
        with tempfile.TemporaryDirectory() as tmp:
            mirror = RuntimeMirror(tmp)
            mirror.mirror_ui_event("s1", {"type": "user", "content": "question"})
            tool = mirror.append("s1", "tool_started", {
                "type": "tool_call",
                "tool": "shell",
                "react_iter": 1,
            })
            projection = RuntimeUiProjection(tmp)
            initial = projection._read_or_build_ui_index("s1")
            self.assertEqual(initial["runtime_seqs"][-1], tool.seq)

            response = mirror.append("s1", "ui_event", {
                "type": "llm_response",
                "content": "late response",
                "react_iter": 1,
            })
            repaired = projection._read_or_build_ui_index("s1")

            self.assertEqual(repaired["runtime_seqs"][-2:], [response.seq, tool.seq])

    def test_index_based_history_op_targets_normalized_react_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            mirror = RuntimeMirror(tmp)
            mirror.mirror_ui_event("s1", {"type": "user", "content": "question"})
            mirror.append("s1", "tool_started", {
                "type": "tool_call",
                "tool": "shell",
                "react_iter": 1,
            })
            response = mirror.append("s1", "ui_event", {
                "type": "llm_response",
                "content": "response",
                "react_iter": 1,
            })
            mirror.append("s1", "visible_range_changed", {
                "to_ui_index": 2,
                "reason": "test normalized prefix",
            })

            events = RuntimeUiProjection(tmp).read_ui_events("s1")

            self.assertEqual([event["type"] for event in events], ["user", "llm_response"])
            self.assertEqual(events[-1]["runtime_seq"], response.seq)

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

    def test_read_ui_events_does_not_replace_partial_runtime_projection(self):
        with tempfile.TemporaryDirectory() as tmp:
            mirror = RuntimeMirror(tmp)
            mirror.mirror_ui_event("s1", {"type": "user", "content": "partial"})
            projection = RuntimeUiProjection(tmp)

            events = projection.read_ui_events("s1", legacy_loader=lambda: [
                {"type": "user", "content": "legacy user"},
                {"type": "status", "content": "legacy status"},
                {"type": "final", "content": "legacy final"},
            ])

            self.assertEqual([ev["content"] for ev in events], ["partial"])
            self.assertEqual(len(projection.read_ui_events_fast("s1")), 1)

    def test_read_ui_events_does_not_replace_expanded_runtime_projection(self):
        with tempfile.TemporaryDirectory() as tmp:
            mirror = RuntimeMirror(tmp)
            mirror.mirror_ui_event("s1", {"type": "user", "content": "duplicate user"})
            mirror.mirror_ui_event("s1", {"type": "final", "content": "duplicate final"})
            projection = RuntimeUiProjection(tmp)

            events = projection.read_ui_events("s1", legacy_loader=lambda: [
                {"type": "user", "content": "legacy user"},
            ])

            self.assertEqual(len(events), 2)
            self.assertEqual([ev["content"] for ev in events], ["duplicate user", "duplicate final"])

    def test_sync_from_legacy_reports_v2_ahead_without_replacing(self):
        with tempfile.TemporaryDirectory() as tmp:
            mirror = RuntimeMirror(tmp)
            mirror.mirror_ui_event("s1", {"type": "user", "content": "legacy user"})
            mirror.mirror_ui_event("s1", {"type": "final", "content": "runtime tail"})
            projection = RuntimeUiProjection(tmp)

            result = projection.sync_from_legacy_if_needed("s1", lambda: [
                {"type": "user", "content": "legacy user"},
            ])

            self.assertEqual(result["action"], "v2_ahead")
            self.assertEqual(result["written"], 0)
            self.assertEqual([ev["content"] for ev in projection.read_ui_events_fast("s1")], [
                "legacy user",
                "runtime tail",
            ])

    def test_sync_from_legacy_reports_mismatch_without_replacing(self):
        with tempfile.TemporaryDirectory() as tmp:
            mirror = RuntimeMirror(tmp)
            mirror.mirror_ui_event("s1", {"type": "user", "content": "runtime"})
            projection = RuntimeUiProjection(tmp)

            result = projection.sync_from_legacy_if_needed("s1", lambda: [
                {"type": "user", "content": "legacy"},
            ])

            self.assertEqual(result["action"], "mismatch")
            self.assertEqual(result["written"], 0)
            self.assertEqual([ev["content"] for ev in projection.read_ui_events_fast("s1")], ["runtime"])

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

    def test_event_budget_moves_start_only_to_a_complete_turn_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            mirror = RuntimeMirror(tmp)
            for turn, process_count in enumerate((10, 6, 1, 0)):
                mirror.mirror_ui_event("s1", {"type": "user", "content": f"u{turn}"})
                for index in range(process_count):
                    mirror.mirror_ui_event(
                        "s1",
                        {"type": "status", "content": f"p{turn}-{index}"},
                    )
                mirror.mirror_ui_event("s1", {"type": "final", "content": f"a{turn}"})

            page = RuntimeUiProjection(tmp).read_ui_page(
                "s1",
                turns=5,
                event_budget=5,
            )

            self.assertEqual(page["total"], 25)
            self.assertEqual(page["requested_range_start"], 0)
            self.assertEqual(page["range_start"], 20)
            self.assertTrue(page["event_budget_applied"])
            self.assertTrue(page["has_older"])
            self.assertEqual(
                [event["content"] for event in page["events"]],
                ["u2", "p2-0", "a2", "u3", "a3"],
            )

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

            page = RuntimeUiProjection(tmp).read_ui_page("s1", turns=1, event_budget=500)

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
            mirror.mirror_ui_event("s1", {
                "type": "user_steer",
                "content": "follow up",
                "steer": True,
                "steer_id": "steer-1",
                "client_id": "client-1",
                "steer_mode": "append",
            })
            projection = RuntimeUiProjection(tmp)

            events = projection.read_ui_events("s1")

            self.assertEqual(events[1]["type"], "user_steer")
            self.assertTrue(events[1]["steer"])
            self.assertEqual(events[1]["steer_id"], "steer-1")
            self.assertEqual(events[1]["client_id"], "client-1")
            self.assertEqual(events[1]["steer_mode"], "append")
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

    def test_visible_index_mapping_respects_deleted_and_rewritten_messages(self):
        with tempfile.TemporaryDirectory() as tmp:
            mirror = RuntimeMirror(tmp)
            e1 = mirror.mirror_ui_event("s1", {"type": "user", "content": "u1"})
            e2 = mirror.mirror_ui_event("s1", {"type": "final", "content": "a1"})
            e3 = mirror.mirror_ui_event("s1", {"type": "user", "content": "u2"})
            ops = RuntimeHistoryOps(tmp)
            deleted = ops.delete_message("s1", e1.seq)
            rewritten = ops.rewrite_message("s1", e3.seq, "u2-new")
            projection = RuntimeUiProjection(tmp)

            events = projection.read_ui_events("s1")
            count, latest_seq = projection.count_ui_events_light("s1")
            index = projection._read_or_build_ui_index("s1")

            self.assertEqual([ev["content"] for ev in events], ["a1", "u2-new"])
            self.assertEqual(projection.ui_index_to_runtime_seq("s1", 0), e2.seq)
            self.assertEqual(projection.ui_index_to_runtime_seq("s1", 1), e3.seq)
            self.assertIsNone(projection.runtime_seq_to_ui_end_index("s1", e1.seq))
            self.assertEqual(projection.runtime_seq_to_ui_end_index("s1", e3.seq), 2)
            self.assertEqual(projection.previous_visible_runtime_seq_before("s1", e3.seq), e2.seq)
            self.assertEqual(count, 2)
            self.assertEqual(latest_seq, 0)
            self.assertEqual(index["user_turns"], [{"event_index": 1, "preview": "u2-new"}])
            self.assertGreater(rewritten.seq, deleted.seq)

    def test_recent_turn_page_falls_back_to_full_projection_after_history_ops(self):
        with tempfile.TemporaryDirectory() as tmp:
            mirror = RuntimeMirror(tmp)
            mirror.mirror_ui_event("s1", {"type": "user", "content": "u1"})
            e2 = mirror.mirror_ui_event("s1", {"type": "final", "content": "a1"})
            e3 = mirror.mirror_ui_event("s1", {"type": "user", "content": "u2"})
            mirror.mirror_ui_event("s1", {"type": "final", "content": "a2"})
            ops = RuntimeHistoryOps(tmp)
            ops.delete_message("s1", e2.seq)
            ops.rewrite_message("s1", e3.seq, "u2-new")
            projection = RuntimeUiProjection(tmp)

            page = projection.read_ui_page("s1", turns=1)

            self.assertEqual([event["content"] for event in page["events"]], ["u2-new", "a2"])
            self.assertNotIn(page.get("source"), {"runtime_v2_tail", "runtime_v2_tail_index"})

    def test_recent_turn_page_uses_seq_index_when_history_ops_are_outside_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            mirror = RuntimeMirror(tmp)
            old_user = mirror.mirror_ui_event("s1", {"type": "user", "content": "old"})
            mirror.mirror_ui_event("s1", {"type": "final", "content": "old-answer"})
            RuntimeHistoryOps(tmp).rewrite_message("s1", old_user.seq, "old-new")
            for index in range(30):
                mirror.mirror_ui_event("s1", {"type": "user", "content": f"u{index}"})
                mirror.mirror_ui_event("s1", {"type": "final", "content": f"a{index}"})

            page = RuntimeUiProjection(tmp).read_ui_page("s1", turns=5)

            self.assertEqual(page.get("source"), "runtime_v2_seq_index")
            self.assertEqual(page["events"][0]["content"], "u25")
            self.assertEqual(page["events"][-1]["content"], "a29")

    def test_recent_turn_page_does_not_drop_user_when_event_appends_after_index_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            mirror = RuntimeMirror(tmp)
            mirror.mirror_ui_event("s1", {"type": "user", "content": "keep-user"})
            mirror.mirror_ui_event("s1", {"type": "status", "content": "working"})
            projection = RuntimeUiProjection(tmp)
            index = projection._read_or_build_ui_index("s1")
            self.assertEqual(index["total"], 2)

            original_read_after = projection.event_log.read_after_seq
            appended = False

            def append_during_indexed_read(session_id, after_seq):
                nonlocal appended
                if not appended:
                    appended = True
                    mirror.mirror_ui_event("s1", {"type": "llm_response", "content": "new-tail"})
                return original_read_after(session_id, after_seq)

            projection.event_log.read_after_seq = append_during_indexed_read
            page = projection.read_ui_page("s1", turns=50)

            self.assertEqual(page.get("source"), "runtime_v2_seq_index")
            self.assertEqual(page["total"], 2)
            self.assertEqual(
                [(event["type"], event["content"]) for event in page["events"]],
                [("user", "keep-user"), ("status", "working")],
            )
            self.assertEqual(
                [event["content"] for event in projection.read_ui_events("s1")],
                ["keep-user", "working", "new-tail"],
            )

    def test_live_runtime_seq_projection_reads_only_new_facts(self):
        with tempfile.TemporaryDirectory() as tmp:
            mirror = RuntimeMirror(tmp)
            first = mirror.mirror_ui_event("s1", {"type": "user", "content": "u1"})
            mirror.append("s1", "run_heartbeat", {}, run_id="r1")
            mirror.mirror_ui_event("s1", {"type": "final", "content": "a1"})

            page = RuntimeUiProjection(tmp).read_ui_after_runtime_seq(
                "s1",
                after_runtime_seq=first.seq,
            )

            self.assertFalse(page["requires_reprojection"])
            self.assertEqual([event["content"] for event in page["events"]], ["a1"])
            self.assertEqual(page["last_runtime_seq"], 3)

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
