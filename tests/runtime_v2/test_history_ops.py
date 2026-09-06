import tempfile
import threading
import time
import unittest
from pathlib import Path

from app.runtime_v2 import (
    RuntimeHistoryOps,
    RuntimeMirror,
    RuntimeModelProjection,
    RuntimeUiProjection,
    SessionExtensionStateStore,
)
from app.runtime_v2.blob_store import BlobStore


class RuntimeHistoryOpsTests(unittest.TestCase):
    def test_responses_compaction_survives_append_and_is_cleared_by_replacement(self):
        with tempfile.TemporaryDirectory() as tmp:
            ops = RuntimeHistoryOps(tmp)
            ops.append_model_message("s1", "user", "first")
            generation = ops.snapshots.read("s1")["model_history_generation"]
            checkpoint = {
                "schema_version": 1,
                "issuer": "issuer-1",
                "model": "gpt-test",
                "source_history_generation": generation,
                "covered_item_count": 1,
                "covered_prefix_hash": "hash",
                "covered_item_hashes": ["item-hash"],
                "compacted_output_items": [],
                "usage": {},
                "source_estimated_tokens": 100,
                "created_at": "2026-08-25T00:00:00.000Z",
            }
            ops.commit_responses_compaction("s1", checkpoint, reason="automatic")
            ops.append_model_message("s1", "user", "second")

            context = RuntimeModelProjection(tmp).read_request_context("s1")
            self.assertEqual(context["responses_compaction"]["issuer"], "issuer-1")
            self.assertEqual(context["history_generation"], generation)

            ops.replace_model_history(
                "s1",
                [{"type": "user", "content": "rewritten"}],
                reason="manual_rewrite",
            )
            rewritten = RuntimeModelProjection(tmp).read_request_context("s1")
            self.assertEqual(rewritten["responses_compaction"], {})
            self.assertGreater(rewritten["history_generation"], generation)

    def test_model_history_replacement_strips_responses_continuation_anchor(self):
        with tempfile.TemporaryDirectory() as tmp:
            ops = RuntimeHistoryOps(tmp)
            ops.replace_model_history(
                "s1",
                [{
                    "type": "assistant",
                    "content": "answer",
                    "additional_kwargs": {
                        "_myagent_responses": {
                            "schema_version": 2,
                            "issuer": "issuer-1",
                            "response_id": "resp_old",
                            "continuation_anchor": {"response_id": "resp_old"},
                            "canonical_output_items": [{
                                "schema_version": 1,
                                "issuer": "issuer-1",
                                "replayability": "native",
                                "raw_item": {
                                    "type": "message",
                                    "role": "assistant",
                                    "content": [],
                                },
                            }],
                        }
                    },
                }],
                reason="automatic_compaction",
            )

            message = RuntimeModelProjection(tmp).read_message_dicts("s1")[0]
            state = message["additional_kwargs"]["_myagent_responses"]
            self.assertNotIn("response_id", state)
            self.assertNotIn("continuation_anchor", state)
            self.assertEqual(state["state_mode"], "stateless")
            self.assertEqual(len(state["canonical_output_items"]), 1)

    def test_large_branch_materializes_under_ten_seconds(self):
        with tempfile.TemporaryDirectory() as tmp:
            ops = RuntimeHistoryOps(tmp)
            model_messages = [
                {"type": "user" if i % 2 == 0 else "assistant", "content": f"model-{i}"}
                for i in range(200)
            ]
            rows = [{
                "type": "model_history_replaced",
                "payload": {"messages": model_messages, "reason": "test_seed"},
            }]
            for i in range(1300):
                rows.append({"type": "message_user", "payload": {"content": f"user-{i}"}})
                rows.append({"type": "message_assistant_final", "payload": {"content": f"answer-{i}"}})
            source_events = ops.event_log.append_batch("source", rows)

            started = time.perf_counter()
            ops.create_branch(
                "branch",
                source_session_id="source",
                branch_from_seq=source_events[-1].seq,
            )
            elapsed = time.perf_counter() - started

            self.assertLess(elapsed, 10.0, f"large branch took {elapsed:.3f}s")
            self.assertEqual(len(RuntimeUiProjection(tmp).read_ui_events("branch")), 2600)
            self.assertEqual(len(ops.snapshots.read("branch")["model_messages"]), 200)

    def test_concurrent_commits_keep_snapshot_at_log_tail(self):
        with tempfile.TemporaryDirectory() as tmp:
            barrier = threading.Barrier(8)

            def append_one(index):
                barrier.wait()
                RuntimeHistoryOps(tmp).append_model_message("s1", "user", str(index))

            threads = [threading.Thread(target=append_one, args=(i,)) for i in range(8)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            ops = RuntimeHistoryOps(tmp)
            events = ops.event_log.read_all("s1")
            snapshot = ops.snapshots.read("s1")
            self.assertEqual(snapshot["last_seq"], events[-1].seq)
            self.assertEqual(len(snapshot["model_messages"]), 8)

    def test_truncate_does_not_hide_messages_appended_after_operation(self):
        with tempfile.TemporaryDirectory() as tmp:
            mirror = RuntimeMirror(tmp)
            u1 = mirror.mirror_ui_event("s1", {"type": "user", "content": "u1"})
            a1 = mirror.mirror_ui_event("s1", {"type": "final", "content": "a1"})
            u2 = mirror.mirror_ui_event("s1", {"type": "user", "content": "old"})
            RuntimeHistoryOps(tmp).truncate_visible_history_before_seq(
                "s1", target_seq=u2.seq, keep_to_seq=a1.seq
            )
            mirror.mirror_ui_event("s1", {"type": "user", "content": "new"})

            snapshot = RuntimeHistoryOps(tmp).snapshots.read("s1")
            self.assertEqual(
                [row["payload"]["content"] for row in snapshot["visible_messages"]],
                ["u1", "a1", "new"],
            )

    def test_standalone_rewrite_updates_matching_model_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            ops = RuntimeHistoryOps(tmp)
            ops.append_model_message("s1", "user", "old")
            ui = RuntimeMirror(tmp).mirror_ui_event("s1", {"type": "user", "content": "old"})
            ops.rewrite_message("s1", ui.seq, "new")
            snapshot = ops.snapshots.read("s1")
            self.assertEqual(snapshot["model_messages"][0]["payload"]["content"], "new")

    def test_model_replace_commits_summary_in_same_event_and_can_clear_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            ops = RuntimeHistoryOps(tmp)
            ops.replace_model_history("s1", [{"type": "user", "content": "u"}], summary="summary")
            self.assertEqual(ops.snapshots.read("s1")["context"]["summary"]["summary"], "summary")
            ops.replace_model_history("s1", [], summary="")
            self.assertEqual(ops.snapshots.read("s1")["context"]["summary"]["summary"], "")

    def test_atomic_user_turn_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            ops = RuntimeHistoryOps(tmp)
            ops.commit_user_turn("s1", "agent text", ui_content="visible", operation_id="client-1")
            ops.commit_user_turn("s1", "agent text", ui_content="visible", operation_id="client-1")
            self.assertEqual(len(ops.event_log.read_all("s1")), 1)
            self.assertEqual(RuntimeUiProjection(tmp).read_ui_events("s1")[0]["content"], "visible")
            self.assertEqual(ops.snapshots.read("s1")["model_messages"][0]["payload"]["content"], "agent text")

    def test_atomic_final_is_idempotent_and_updates_both_projections(self):
        with tempfile.TemporaryDirectory() as tmp:
            ops = RuntimeHistoryOps(tmp)
            ops.commit_assistant_final("s1", "done", operation_id="final-1")
            ops.commit_assistant_final("s1", "done", operation_id="final-1")
            snapshot = ops.snapshots.read("s1")
            self.assertEqual(len(ops.event_log.read_all("s1")), 1)
            self.assertEqual(RuntimeUiProjection(tmp).read_ui_events("s1")[0]["content"], "done")
            self.assertEqual(snapshot["model_messages"][0]["payload"]["content"], "done")

    def test_atomic_final_keeps_model_content_separate_from_ui_media_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            ops = RuntimeHistoryOps(tmp)
            ops.append_model_message(
                "s1",
                "assistant",
                "![preview](preview.png)",
                metadata={"is_assistant_response": True},
            )
            ops.commit_assistant_final(
                "s1",
                "![preview](preview.png)",
                ui_content="![preview](<.sugaragent/history-media/hash.png>)",
            )

            ui = RuntimeUiProjection(tmp).read_ui_events("s1")
            snapshot = ops.snapshots.read("s1")
            self.assertEqual(
                ui[0]["content"],
                "![preview](<.sugaragent/history-media/hash.png>)",
            )
            self.assertEqual(
                snapshot["messages"][0]["payload"]["content"],
                "![preview](<.sugaragent/history-media/hash.png>)",
            )
            self.assertEqual(
                snapshot["model_messages"][0]["payload"]["content"],
                "![preview](preview.png)",
            )

    def test_atomic_final_promotes_matching_model_response_without_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            ops = RuntimeHistoryOps(tmp)
            ops.append_model_message(
                "s1",
                "assistant",
                "done",
                metadata={"is_assistant_response": True},
                run_id="run-1",
            )
            ops.commit_assistant_final(
                "s1", "done", operation_id="final-1", run_id="run-1"
            )

            snapshot = ops.snapshots.read("s1")
            self.assertEqual(len(snapshot["model_messages"]), 1)
            self.assertTrue(snapshot["model_messages"][0]["payload"]["metadata"]["is_final"])
            self.assertFalse(snapshot["model_messages"][0]["payload"]["metadata"]["is_assistant_response"])
            self.assertEqual(
                [event.type for event in ops.event_log.read_all("s1")],
                ["model_assistant", "assistant_final_committed"],
            )
            reconciled = ops.reconcile_model_history(
                "s1",
                [{
                    "type": "assistant",
                    "content": "done",
                    "metadata": {"is_assistant_response": False, "is_final": True},
                }],
                reason="finish",
            )
            self.assertIsNone(reconciled)
            self.assertNotIn(
                "model_history_replaced",
                [event.type for event in ops.event_log.read_all("s1")],
            )

    def test_reconcile_model_history_uses_tail_truncate(self):
        with tempfile.TemporaryDirectory() as tmp:
            ops = RuntimeHistoryOps(tmp)
            ops.append_model_message("s1", "user", "u")
            ops.append_model_message("s1", "assistant", "a")
            ops.append_model_message("s1", "tool", "unfinished", tool_call_id="tc")

            event = ops.reconcile_model_history(
                "s1",
                [{"type": "user", "content": "u"}, {"type": "assistant", "content": "a"}],
                reason="sanitize",
            )

            self.assertEqual(event.type, "model_tail_truncated")
            self.assertEqual(
                [row["payload"]["content"] for row in ops.snapshots.read("s1")["model_messages"]],
                ["u", "a"],
            )

    def test_reconcile_model_history_uses_prefix_compaction(self):
        with tempfile.TemporaryDirectory() as tmp:
            ops = RuntimeHistoryOps(tmp)
            for role, content in (("user", "old"), ("assistant", "old answer"), ("user", "keep")):
                ops.append_model_message("s1", role, content)

            event = ops.reconcile_model_history(
                "s1",
                [{"type": "system", "content": "summary"}, {"type": "user", "content": "keep"}],
                reason="auto_context_policy",
                summary="summary",
            )

            self.assertEqual(event.type, "model_prefix_compacted")
            snapshot = ops.snapshots.read("s1")
            self.assertEqual(
                [row["payload"]["content"] for row in snapshot["model_messages"]],
                ["summary", "keep"],
            )
            self.assertEqual(snapshot["context"]["summary"]["summary"], "summary")

    def test_reconcile_model_history_appends_missing_suffix_in_one_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            ops = RuntimeHistoryOps(tmp)
            ops.append_model_message("s1", "user", "u")
            event = ops.reconcile_model_history(
                "s1",
                [{"type": "user", "content": "u"}, {"type": "assistant", "content": "a"}],
                reason="subagent_run_finished",
            )
            self.assertEqual(event.type, "model_messages_appended")
            self.assertEqual(
                [row["payload"]["content"] for row in ops.snapshots.read("s1")["model_messages"]],
                ["u", "a"],
            )

    def test_model_read_repairs_snapshot_left_behind_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            ops = RuntimeHistoryOps(tmp)
            ops.append_model_message("s1", "user", "first")
            # Simulate a crash after the fact append and before snapshot update.
            ops.event_log.append("s1", "model_user", {"role": "user", "content": "second"})

            projection = RuntimeHistoryOps(tmp)
            snapshot = projection.snapshots.read_consistent(
                "s1", projection.event_log, projection.projector
            )

            self.assertEqual(
                [row["payload"]["content"] for row in snapshot["model_messages"]],
                ["first", "second"],
            )
            self.assertEqual(ops.snapshots.read("s1")["last_seq"], 2)
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
            ui_events = RuntimeUiProjection(tmp).read_ui_events("s1")
            self.assertEqual([ev["content"] for ev in ui_events], ["new"])

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
            self.assertEqual([m["role"] for m in snapshot["model_messages"]], ["system"])
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

    def test_truncate_visible_history_before_seq_keeps_prior_visible_messages(self):
        with tempfile.TemporaryDirectory() as tmp:
            mirror = RuntimeMirror(tmp)
            e1 = mirror.mirror_ui_event("s1", {"type": "user", "content": "u1"})
            e2 = mirror.mirror_ui_event("s1", {"type": "final", "content": "a1"})
            e3 = mirror.mirror_ui_event("s1", {"type": "user", "content": "u2"})
            mirror.mirror_ui_event("s1", {"type": "final", "content": "a2"})

            ops = RuntimeHistoryOps(tmp)
            op = ops.truncate_visible_history_before_seq("s1", target_seq=e3.seq, keep_to_seq=e2.seq)
            snapshot = ops.snapshots.read("s1")
            events = RuntimeUiProjection(tmp).read_ui_events("s1")

            self.assertEqual(op.payload["to_seq"], e2.seq)
            self.assertNotIn("to_ui_index", op.payload)
            self.assertEqual([m["payload"]["content"] for m in snapshot["visible_messages"]], ["u1", "a1"])
            self.assertEqual([ev["runtime_seq"] for ev in events], [e1.seq, e2.seq])

    def test_truncate_keeps_ui_and_model_prefixes_aligned_after_rewrite(self):
        """A rewritten turn starts from one shared retained boundary.

        The old tail must not reappear in the UI, a branch, or a later model
        replacement that represents the new run's canonical context.
        """
        with tempfile.TemporaryDirectory() as tmp:
            ops = RuntimeHistoryOps(tmp)
            mirror = RuntimeMirror(tmp)
            ops.append_model_message("source", "user", "u1")
            e1 = mirror.mirror_ui_event("source", {"type": "user", "content": "u1"})
            ops.append_model_message("source", "assistant", "a1")
            e2 = mirror.mirror_ui_event("source", {"type": "final", "content": "a1"})
            ops.append_model_message("source", "user", "old u2")
            e3 = mirror.mirror_ui_event("source", {"type": "user", "content": "old u2"})
            ops.append_model_message("source", "assistant", "old a2")
            mirror.mirror_ui_event("source", {"type": "final", "content": "old a2"})

            ops.truncate_visible_history_before_seq(
                "source", target_seq=e3.seq, keep_to_seq=e2.seq
            )
            self.assertEqual(
                [event["content"] for event in RuntimeUiProjection(tmp).read_ui_events("source")],
                ["u1", "a1"],
            )
            self.assertEqual(
                [row["payload"]["content"] for row in ops.snapshots.read("source")["model_messages"]],
                ["u1", "a1"],
            )

            # The post-rewrite runtime owns this exact model context.  An old
            # truncation must not apply a second heuristic trim to it.
            ops.replace_model_history("source", [
                {"type": "user", "content": "u1"},
                {"type": "assistant", "content": "a1"},
                {"type": "user", "content": "new u2"},
                {"type": "assistant", "content": "new a2"},
            ], reason="rewrite_new_run")
            self.assertEqual(
                [row["payload"]["content"] for row in ops.snapshots.read("source")["model_messages"]],
                ["u1", "a1", "new u2", "new a2"],
            )

            ops.create_branch("branch", source_session_id="source", branch_from_seq=e2.seq)
            self.assertEqual(
                [event["content"] for event in RuntimeUiProjection(tmp).read_ui_events("branch")],
                ["u1", "a1"],
            )
            self.assertEqual(
                [row["payload"]["content"] for row in ops.snapshots.read("branch")["model_messages"]],
                ["u1", "a1"],
            )

    def test_stopped_run_rewrite_restores_pre_send_context_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            ops = RuntimeHistoryOps(tmp)
            mirror = RuntimeMirror(tmp)
            ops.replace_model_history(
                "s1",
                [{"type": "user", "content": "earlier"}],
                reason="baseline",
                summary="summary before send",
            )
            target = ops.commit_user_turn("s1", "message that will be rewritten")
            self.assertIsNotNone(target)
            ops.replace_model_history(
                "s1",
                [
                    {"type": "system", "content": "compressed tail"},
                    {"type": "user", "content": "message that will be rewritten"},
                ],
                reason="auto_context_policy",
                summary="summary produced after send",
            )
            mirror.mirror_run_interrupted("s1", "run-1", {"reason": "user"})

            ops.truncate_visible_history_before_seq(
                "s1",
                target_seq=target.seq,
                keep_to_seq=target.seq - 1,
                reason="runtime_v2_truncate",
            )
            snapshot = ops.snapshots.read("s1")

            self.assertEqual(snapshot["context"]["summary"]["summary"], "summary before send")
            self.assertEqual(
                [row["payload"]["content"] for row in snapshot["model_messages"]],
                ["earlier"],
            )

    def test_stopped_run_rewrite_restores_pre_send_provider_token_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            ops = RuntimeHistoryOps(tmp)
            mirror = RuntimeMirror(tmp)
            ops.append_model_message("s1", "user", "earlier")
            mirror.mirror_ui_event("s1", {"type": "user", "content": "earlier"})
            mirror.mirror_ui_event("s1", {
                "type": "cache_stats",
                "input_tokens": 88000,
                "threshold": 128000,
                "model": "model-a",
            })
            target = ops.commit_user_turn("s1", "rewrite me")
            mirror.mirror_ui_event("s1", {
                "type": "cache_stats",
                "input_tokens": 91000,
                "threshold": 128000,
                "model": "model-a",
            })

            ops.truncate_visible_history_before_seq(
                "s1",
                target_seq=target.seq,
                keep_to_seq=target.seq - 1,
                reason="runtime_v2_truncate",
            )
            tokens = ops.snapshots.read("s1")["context"]["tokens"]

            self.assertEqual(tokens["estimated"], 88000)
            self.assertEqual(tokens["token_source"], "provider_exact")
            self.assertFalse(tokens.get("stale", False))

    def test_stopped_run_rewrite_restores_pre_send_todo_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            ops = RuntimeHistoryOps(tmp)
            before = {
                "has_plan": True,
                "items": [{"id": "1", "text": "before", "status": "in_progress"}],
                "done": 0,
                "total": 1,
            }
            after = {
                "has_plan": True,
                "items": [{"id": "2", "text": "after", "status": "in_progress"}],
                "done": 0,
                "total": 1,
            }
            (Path(tmp) / "s1").mkdir()
            extensions = SessionExtensionStateStore(tmp)
            extensions.set_latest("s1", "session-todo", "plan", before)
            target = ops.commit_user_turn("s1", "rewrite me")
            extensions.set_latest("s1", "session-todo", "plan", after)

            ops.truncate_visible_history_before_seq(
                "s1",
                target_seq=target.seq,
                keep_to_seq=target.seq - 1,
                reason="runtime_v2_truncate",
            )
            todo = ops.snapshots.read("s1")["extensions"]["session-todo"]["plan"]["value"]

            self.assertEqual(todo["items"][0]["text"], "before")
            self.assertEqual(todo["total"], 1)

    def test_model_replacement_invalidates_old_tokens_until_new_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            ops = RuntimeHistoryOps(tmp)
            mirror = RuntimeMirror(tmp)
            ops.append_model_message("s1", "user", "before")
            mirror.mirror_ui_event("s1", {
                "type": "cache_stats",
                "input_tokens": 90000,
                "threshold": 128000,
                "model": "model-a",
            })

            ops.replace_model_history(
                "s1",
                [{"type": "user", "content": "compressed"}],
                reason="auto_context_policy",
                summary="summary",
            )
            stale = ops.snapshots.read("s1")["context"]["tokens"]
            self.assertTrue(stale["stale"])
            self.assertEqual(stale["stale_reason"], "model_history_replaced")

            ops.checkpoint_context_tokens("s1", {
                "estimated": 12000,
                "threshold": 128000,
                "token_source": "provider_calibrated",
                "reason": "post_compress_checkpoint",
            })
            fresh = ops.snapshots.read("s1")["context"]["tokens"]
            self.assertEqual(fresh["estimated"], 12000)
            self.assertEqual(fresh["token_source"], "provider_calibrated")
            self.assertFalse(fresh["stale"])

    def test_branch_and_nested_branch_inherit_provider_token_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            ops = RuntimeHistoryOps(tmp)
            mirror = RuntimeMirror(tmp)
            ops.append_model_message("root", "user", "u1")
            mirror.mirror_ui_event("root", {"type": "user", "content": "u1"})
            mirror.mirror_ui_event("root", {
                "type": "cache_stats",
                "input_tokens": 64000,
                "threshold": 128000,
                "model": "model-a",
            })
            ops.append_model_message("root", "assistant", "a1")
            final = mirror.mirror_ui_event("root", {"type": "final", "content": "a1"})

            ops.create_branch("branch", "root", final.seq)
            branch_final = next(
                event for event in RuntimeUiProjection(tmp).read_ui_events("branch")
                if event.get("type") == "final"
            )
            ops.create_branch("nested", "branch", int(branch_final["runtime_seq"]))

            for sid in ("branch", "nested"):
                tokens = ops.snapshots.read(sid)["context"]["tokens"]
                self.assertEqual(tokens["estimated"], 64000)
                self.assertEqual(tokens["token_source"], "provider_exact")

    def test_rewrite_before_first_summary_clears_post_send_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            ops = RuntimeHistoryOps(tmp)
            target = ops.commit_user_turn("s1", "rewrite me")
            self.assertIsNotNone(target)
            ops.replace_model_history(
                "s1",
                [{"type": "user", "content": "rewrite me"}],
                reason="auto_context_policy",
                summary="created after send",
            )

            op = ops.truncate_visible_history_before_seq(
                "s1",
                target_seq=target.seq,
                keep_to_seq=0,
                reason="runtime_v2_truncate",
            )
            snapshot = ops.snapshots.read("s1")

            self.assertEqual(op.payload["restore_context_summary"]["summary"], "")
            self.assertEqual(snapshot["context"]["summary"]["summary"], "")
            self.assertEqual(snapshot["model_messages"], [])

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

    def test_branch_of_branch_restores_model_context_at_seeded_ui_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            ops = RuntimeHistoryOps(tmp)
            mirror = RuntimeMirror(tmp)
            ops.append_model_message("root", "user", "u1")
            mirror.mirror_ui_event("root", {"type": "user", "content": "u1"})
            ops.append_model_message("root", "assistant", "a1")
            first_final = mirror.mirror_ui_event("root", {"type": "final", "content": "a1"})
            ops.append_model_message("root", "user", "u2")
            mirror.mirror_ui_event("root", {"type": "user", "content": "u2"})
            ops.append_model_message("root", "assistant", "a2")
            last_final = mirror.mirror_ui_event("root", {"type": "final", "content": "a2"})

            ops.create_branch("parent-branch", "root", last_final.seq)
            seeded_events = RuntimeUiProjection(tmp).read_ui_events("parent-branch")
            seeded_first_final = next(
                event for event in seeded_events
                if event.get("type") == "final" and event.get("content") == "a1"
            )
            ops.create_branch(
                "child-branch",
                "parent-branch",
                int(seeded_first_final["runtime_seq"]),
            )

            child_snapshot = ops.snapshots.read("child-branch")
            self.assertEqual(
                [row["payload"]["content"] for row in child_snapshot["model_messages"]],
                ["u1", "a1"],
            )
            child_events = RuntimeUiProjection(tmp).read_ui_events("child-branch")
            self.assertEqual([event["content"] for event in child_events], ["u1", "a1"])

    def test_branch_of_branch_keeps_rewrite_of_inherited_seed_in_model_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            ops = RuntimeHistoryOps(tmp)
            mirror = RuntimeMirror(tmp)
            ops.append_model_message("root", "user", "old")
            mirror.mirror_ui_event("root", {"type": "user", "content": "old"})
            ops.append_model_message("root", "assistant", "answer")
            root_final = mirror.mirror_ui_event("root", {"type": "final", "content": "answer"})

            ops.create_branch("parent", "root", root_final.seq)
            parent_events = RuntimeUiProjection(tmp).read_ui_events("parent")
            seeded_user = next(event for event in parent_events if event.get("type") == "user")
            seeded_final = next(event for event in parent_events if event.get("type") == "final")
            ops.rewrite_message("parent", int(seeded_user["runtime_seq"]), "new")

            ops.create_branch("child", "parent", int(seeded_final["runtime_seq"]))
            child_snapshot = ops.snapshots.read("child")
            child_events = RuntimeUiProjection(tmp).read_ui_events("child")

            self.assertEqual([event["content"] for event in child_events], ["new", "answer"])
            self.assertEqual(
                [row["payload"]["content"] for row in child_snapshot["model_messages"]],
                ["new", "answer"],
            )

    def test_branch_inherits_todo_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            ops = RuntimeHistoryOps(tmp)
            mirror = RuntimeMirror(tmp)
            (Path(tmp) / "root").mkdir()
            SessionExtensionStateStore(tmp).set_latest("root", "session-todo", "plan", {
                "has_plan": True,
                "items": [{"id": "1", "text": "branch task", "status": "pending"}],
                "done": 0,
                "total": 1,
            })
            final = mirror.mirror_ui_event("root", {"type": "final", "content": "answer"})

            ops.create_branch("branch", "root", final.seq)

            todo = ops.snapshots.read("branch")["extensions"]["session-todo"]["plan"]["value"]
            self.assertEqual(todo["items"][0]["text"], "branch task")

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

    def test_branch_seeds_rewritten_visible_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            mirror = RuntimeMirror(tmp)
            mirror.mirror_ui_event("source", {"type": "user", "content": "old"})
            mirror.mirror_ui_event("source", {"type": "final", "content": "a1"})
            ops = RuntimeHistoryOps(tmp)
            ops.rewrite_message("source", target_seq=1, content="new")

            ops.create_branch("branch", source_session_id="source", branch_from_seq=2)

            branch_events = RuntimeUiProjection(tmp).read_ui_events("branch")

            self.assertEqual([ev["content"] for ev in branch_events], ["new", "a1"])

    def test_branch_seed_omits_deleted_visible_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            mirror = RuntimeMirror(tmp)
            mirror.mirror_ui_event("source", {"type": "user", "content": "u1"})
            mirror.mirror_ui_event("source", {"type": "final", "content": "a1"})
            ops = RuntimeHistoryOps(tmp)
            ops.delete_message("source", target_seq=1)

            ops.create_branch("branch", source_session_id="source", branch_from_seq=2)

            branch_events = RuntimeUiProjection(tmp).read_ui_events("branch")

            self.assertEqual([ev["content"] for ev in branch_events], ["a1"])

    def test_branch_copies_blob_refs_for_seeded_tool_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            ref = BlobStore(f"{tmp}/source").put_text("large result")
            mirror = RuntimeMirror(tmp)
            mirror.append("source", "tool_finished", {
                "type": "tool_call",
                "tool": "read_file",
                "result_ref": ref,
            })

            RuntimeHistoryOps(tmp).create_branch("branch", source_session_id="source", branch_from_seq=1)

            branch_events = RuntimeUiProjection(tmp).read_ui_events("branch")

            self.assertEqual(branch_events[0]["result"], "large result")

    def test_bulk_branch_preserves_subagent_sidecar_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            mirror = RuntimeMirror(tmp)
            source_event = mirror.mirror_ui_event("source", {
                "type": "subagent_started",
                "agent_id": "agent-1",
                "task_id": "agent-1",
            })

            RuntimeHistoryOps(tmp).create_branch(
                "branch",
                source_session_id="source",
                branch_from_seq=source_event.seq,
            )

            child_log = RuntimeHistoryOps(tmp).event_log.session_dir("branch") / "subagents" / "agent-1" / "events.jsonl"
            self.assertTrue(child_log.is_file())
            self.assertIn("subagent_started", child_log.read_text(encoding="utf-8"))

    def test_reference_branch_batches_context_and_extension_inheritance(self):
        with tempfile.TemporaryDirectory() as tmp:
            ops = RuntimeHistoryOps(tmp)
            ops.append_model_message("parent", "user", "task")
            ops.commit_context_summary("parent", "summary", source_seq=1)
            ops.checkpoint_context_tokens(
                "parent", {"estimated": 42, "token_source": "test"}
            )
            SessionExtensionStateStore(tmp).set_latest(
                "parent", "demo", "state", {"enabled": True}
            )
            anchor = ops.event_log.next_seq("parent") - 1
            calls = []
            original = ops.event_log._append_many_unlocked

            def record_batch(session_id, rows):
                materialized = list(rows)
                calls.append((session_id, [row["type"] for row in materialized]))
                return original(session_id, materialized)

            ops.event_log._append_many_unlocked = record_batch
            reference = ops.create_reference_branch(
                "child", "parent", anchor, name="worker"
            )
            child = ops.snapshots.read("child")

            self.assertEqual(reference.type, "history_branch_created")
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0][0], "child")
            self.assertEqual(
                calls[0][1],
                [
                    "history_branch_created",
                    "context_summary_committed",
                    "context_tokens",
                    "extension_state_changed",
                ],
            )
            self.assertEqual(child["context"]["summary"]["summary"], "summary")
            self.assertEqual(child["context"]["tokens"]["estimated"], 42)
            self.assertEqual(
                child["extensions"]["demo"]["state"]["value"],
                {"enabled": True},
            )


if __name__ == "__main__":
    unittest.main()
