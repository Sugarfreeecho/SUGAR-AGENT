import tempfile
import unittest

from app.runtime_v2 import BlobStore, RuntimeSubagentStore


class RuntimeStorageLayoutTests(unittest.TestCase):
    def test_blob_store_writes_content_addressed_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = BlobStore(tmp)
            ref = store.put_text("large text")

            self.assertTrue(ref["blob_ref"].startswith("blobs/"))
            self.assertEqual(store.read_text(ref["blob_ref"]), "large text")

    def test_subagent_store_writes_under_parent_subagents_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = RuntimeSubagentStore(tmp)
            event = store.append_event("parent", "agent1", "message_user", {"content": "sub"})
            store.write_metadata("parent", "agent1", {"name": "subagent"})
            snapshot = store.read_snapshot("parent", "agent1")

            self.assertEqual(event.seq, 1)
            self.assertEqual(snapshot["messages"][0]["payload"]["content"], "sub")
            self.assertTrue((store.agent_dir("parent", "agent1") / "events.jsonl").exists())
            self.assertTrue((store.agent_dir("parent", "agent1") / "metadata.json").exists())

    def test_subagent_store_tracks_tasks_pending_and_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = RuntimeSubagentStore(tmp)
            store.upsert_task("parent", "agent1", {"status": "running"})
            store.upsert_task("parent", "agent1", {"status": "finished", "has_final": True})
            output_path = store.write_task_output("parent", "agent1", "final text")
            store.append_pending_result("parent", {"agent_id": "agent1", "status": "finished"})

            tasks = store.list_tasks("parent")
            pending = store.list_pending_results("parent")
            output = store.read_task_output("parent", "agent1")

            self.assertEqual(len(tasks), 1)
            self.assertEqual(tasks[0]["status"], "finished")
            self.assertEqual(tasks[0]["output_file"], output_path)
            self.assertEqual(pending[0]["agent_id"], "agent1")
            self.assertTrue(output["ok"])
            self.assertEqual(output["content"], "final text")

            store.save_pending_results("parent", [])
            store.remove_parent_rows("parent", "agent1")

            self.assertEqual(store.list_pending_results("parent"), [])
            self.assertEqual(store.list_tasks("parent"), [])


if __name__ == "__main__":
    unittest.main()
