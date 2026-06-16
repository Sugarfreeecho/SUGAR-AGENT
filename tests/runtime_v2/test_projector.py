import asyncio
import tempfile
import unittest

from app.runtime_v2 import RuntimeGateway, RuntimeHistoryOps, RuntimeModelProjection, RuntimeProjector
from app.runtime_v2.event_schema import RuntimeEvent


class RuntimeProjectorTests(unittest.TestCase):
    def test_project_run_terminal_state(self):
        projector = RuntimeProjector()
        events = [
            RuntimeEvent(seq=1, type="run_started", session_id="s1", run_id="r1"),
            RuntimeEvent(seq=2, type="run_failed", session_id="s1", run_id="r1", payload={"error": "boom"}),
        ]
        snapshot = projector.project(events)

        self.assertEqual(snapshot["last_seq"], 2)
        self.assertEqual(snapshot["runs"]["r1"]["status"], "failed")
        self.assertEqual(snapshot["runs"]["r1"]["error"], "boom")
        self.assertEqual(snapshot["active_runs"], [])

    def test_projects_context_tokens_and_todo_snapshot(self):
        projector = RuntimeProjector()
        events = [
            RuntimeEvent(seq=1, type="context_tokens", session_id="s1", payload={"estimated": 123, "threshold": 1000}),
            RuntimeEvent(seq=2, type="todo_updated", session_id="s1", payload={
                "has_plan": True,
                "items": [{"id": "t1", "text": "Do it", "status": "pending"}],
                "done": 0,
                "total": 1,
            }),
        ]

        snapshot = projector.project(events)

        self.assertEqual(snapshot["context"]["tokens"]["estimated"], 123)
        self.assertEqual(snapshot["context"]["tokens"]["seq"], 1)
        self.assertEqual(snapshot["todo"]["total"], 1)
        self.assertEqual(snapshot["todo"]["seq"], 2)
        self.assertEqual(snapshot["context"]["todo"]["items"][0]["id"], "t1")

    def test_gateway_rebuilds_and_reads_snapshot(self):
        async def scenario():
            with tempfile.TemporaryDirectory() as tmp:
                gateway = RuntimeGateway(tmp)
                await gateway.append_event("s1", "message_user", {"content": "hello"})
                await gateway.start_run("s1", run_id="r1")
                await gateway.finish_run("s1", "r1")

                snapshot = gateway.rebuild_session_state("s1")
                cached = gateway.read_snapshot("s1")

                self.assertEqual(snapshot["last_seq"], 3)
                self.assertEqual(cached["last_seq"], 3)
                self.assertEqual(cached["messages"][0]["role"], "user")
                self.assertEqual(cached["runs"]["r1"]["status"], "finished")

        asyncio.run(scenario())

    def test_projects_native_model_messages_with_tool_order(self):
        projector = RuntimeProjector()
        events = [
            RuntimeEvent(seq=1, type="message_user", session_id="s1", payload={"content": "visible"}),
            RuntimeEvent(seq=2, type="model_user", session_id="s1", payload={"role": "user", "content": "model u"}),
            RuntimeEvent(seq=3, type="model_assistant", session_id="s1", payload={
                "role": "assistant",
                "content": "",
                "tool_calls": [{"name": "read_file", "args": {"path": "a"}, "id": "tc1"}],
            }),
            RuntimeEvent(seq=4, type="model_tool", session_id="s1", payload={
                "role": "tool",
                "content": "tool result",
                "tool_call_id": "tc1",
            }),
            RuntimeEvent(seq=5, type="model_assistant", session_id="s1", payload={
                "role": "assistant",
                "content": "done",
                "metadata": {"is_final": True},
            }),
        ]

        snapshot = projector.project(events)

        self.assertEqual(len(snapshot["visible_messages"]), 1)
        self.assertEqual([m["role"] for m in snapshot["model_messages"]], ["user", "assistant", "tool", "assistant"])
        self.assertEqual(snapshot["model_messages"][1]["payload"]["tool_calls"][0]["id"], "tc1")
        self.assertEqual(snapshot["model_messages"][2]["payload"]["tool_call_id"], "tc1")

    def test_model_projection_reads_message_dicts(self):
        with tempfile.TemporaryDirectory() as tmp:
            ops = RuntimeHistoryOps(tmp)
            ops.append_model_message("s1", "user", "hello")
            ops.append_model_message(
                "s1",
                "assistant",
                "",
                tool_calls=[{"name": "read_file", "args": {"path": "a"}, "id": "tc1"}],
                additional_kwargs={"reasoning_content": "why"},
            )
            ops.append_model_message("s1", "tool", "result", tool_call_id="tc1")

            messages = RuntimeModelProjection(tmp).read_message_dicts("s1")

            self.assertEqual([m["type"] for m in messages], ["user", "assistant", "tool"])
            self.assertEqual(messages[1]["tool_calls"][0]["id"], "tc1")
            self.assertEqual(messages[1]["additional_kwargs"]["reasoning_content"], "why")
            self.assertEqual(messages[2]["tool_call_id"], "tc1")

    def test_model_projection_backfills_legacy_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            projection = RuntimeModelProjection(tmp)

            count = projection.ensure_backfilled_from_legacy("s1", [
                {"type": "user", "content": "legacy"},
                {"type": "assistant", "content": "answer", "metadata": {"is_final": True}},
            ])
            second = projection.ensure_backfilled_from_legacy("s1", [
                {"type": "user", "content": "ignored"},
            ])
            messages = projection.read_message_dicts("s1")

            self.assertEqual(count, 2)
            self.assertEqual(second, 0)
            self.assertEqual([m["content"] for m in messages], ["legacy", "answer"])


if __name__ == "__main__":
    unittest.main()
