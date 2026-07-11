import tempfile
import threading
import unittest
import multiprocessing

from app.runtime_v2 import SessionEventLog


def _append_events_in_process(args):
    root, count = args
    log = SessionEventLog(root)
    for _ in range(count):
        log.append("s1", "message_user", {})


class SessionEventLogTests(unittest.TestCase):
    def test_append_and_read_after_seq(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = SessionEventLog(tmp)
            first = log.append("s1", "message_user", {"content": "hello"})
            second = log.append("s1", "run_started", {"run": "r1"}, run_id="r1")

            self.assertEqual(first.seq, 1)
            self.assertEqual(second.seq, 2)
            self.assertTrue(log.event_path("s1").exists())
            self.assertEqual([ev.seq for ev in log.read_after_seq("s1", 1)], [2])

    def test_repair_drops_bad_lines_and_renumbers(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = SessionEventLog(tmp)
            log.append("s1", "message_user", {})
            path = log.event_path("s1")
            with path.open("a", encoding="utf-8") as fh:
                fh.write("{bad json}\n")
            log.append("s1", "run_finished", {})

            result = log.repair("s1")
            events = log.read_all("s1")

            self.assertEqual(result["dropped"], 1)
            self.assertEqual([ev.seq for ev in events], [1, 2])

    def test_repair_preserves_published_seq_and_history_targets(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = SessionEventLog(tmp)
            log.append("s1", "legacy_ui_event", {"type": "status"})
            user = log.append("s1", "message_user", {"content": "u"})
            log.append("s1", "message_assistant_final", {"content": "a"})
            log.append("s1", "message_deleted", {"target_seq": user.seq})
            path = log.event_path("s1")
            lines = path.read_text(encoding="utf-8").splitlines()
            lines[0] = "{bad json}"
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")

            result = log.repair("s1")
            events = log.read_all("s1")

            self.assertEqual(result["dropped"], 1)
            self.assertEqual([ev.seq for ev in events], [2, 3, 4])
            self.assertEqual(events[-1].payload["target_seq"], 2)

    def test_reads_skip_bad_lines_without_repair(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = SessionEventLog(tmp)
            log.append("s1", "message_user", {})
            path = log.event_path("s1")
            with path.open("a", encoding="utf-8") as fh:
                fh.write("bad json\n")
            log.append("s1", "run_finished", {})

            events = log.read_all("s1")

            self.assertEqual([ev.seq for ev in events], [1, 2])

    def test_concurrent_append_keeps_monotonic_seq(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = SessionEventLog(tmp)

            def append_one(index):
                log.append("s1", "message_user", {"index": index})

            threads = [threading.Thread(target=append_one, args=(i,)) for i in range(12)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            events = log.read_all("s1")
            self.assertEqual(len(events), 12)
            self.assertEqual([ev.seq for ev in events], list(range(1, 13)))

    def test_multiprocess_append_keeps_unique_monotonic_seq(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctx = multiprocessing.get_context("spawn")
            with ctx.Pool(3) as pool:
                pool.map(_append_events_in_process, [(tmp, 6)] * 3)
            events = SessionEventLog(tmp).read_all("s1")
            self.assertEqual([ev.seq for ev in events], list(range(1, 19)))

    def test_on_demand_reads_support_latest_and_before_seq(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = SessionEventLog(tmp)
            for i in range(6):
                log.append("s1", "message_user", {"index": i})

            self.assertEqual([ev.seq for ev in log.read_latest("s1", 2)], [5, 6])
            self.assertEqual([ev.seq for ev in log.read_before_seq("s1", 5, 2)], [3, 4])

    def test_next_seq_recovers_from_tail_and_ignores_partial_last_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = SessionEventLog(tmp)
            log.append_batch("s1", [
                {"type": "message_user", "payload": {}},
                {"type": "message_assistant_final", "payload": {}},
            ])
            path = log.event_path("s1")
            with path.open("ab") as fh:
                fh.write(b'{"seq":999')
            SessionEventLog._seq_cache.clear()

            self.assertEqual(SessionEventLog(tmp).next_seq("s1"), 3)


if __name__ == "__main__":
    unittest.main()
