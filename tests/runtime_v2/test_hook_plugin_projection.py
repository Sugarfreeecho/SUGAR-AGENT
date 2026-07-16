import tempfile
import unittest

from app.runtime_v2 import RuntimeHistoryOps, RuntimeProjector, RuntimeUiProjection
from app.runtime_v2.event_schema import CORE_EVENT_TYPES, RuntimeEvent


HOOK_EVENT_TYPES = [
    "hook_started",
    "hook_progress",
    "hook_finished",
    "hook_failed",
    "hook_blocked",
    "hook_timed_out",
    "hook_input_modified",
]


class HookPluginRuntimeProjectionTests(unittest.TestCase):
    def test_hook_and_plugin_events_are_core_runtime_events(self):
        self.assertTrue(set(HOOK_EVENT_TYPES).issubset(CORE_EVENT_TYPES))
        self.assertIn("plugin_state_changed", CORE_EVENT_TYPES)
        self.assertIn("plugin_reloaded", CORE_EVENT_TYPES)

    def test_projector_keeps_compact_recent_hook_audit_and_stats(self):
        events = []
        for seq, event_type in enumerate(HOOK_EVENT_TYPES, start=1):
            events.append(RuntimeEvent(
                seq=seq,
                type=event_type,
                session_id="s1",
                run_id="r1",
                payload={
                    "hook_id": "quality-gate",
                    "hook_event": "PreToolUse",
                    "event": "PreToolUse",
                    "source_id": "project",
                    "success": event_type == "hook_finished",
                    "stdout": "x" * 100_000,
                    "stderr": "y" * 100_000,
                    "stdout_ref": {"blob_ref": "blobs/hook-output.txt"},
                    "reason": "checked",
                },
            ))

        snapshot = RuntimeProjector().project(events)

        recent = snapshot["hooks"]["recent"]
        stats = snapshot["hooks"]["stats"]
        self.assertEqual([row["type"] for row in recent], HOOK_EVENT_TYPES)
        self.assertTrue(all("stdout" not in row and "stderr" not in row for row in recent))
        self.assertEqual(recent[0]["stdout_ref"]["blob_ref"], "blobs/hook-output.txt")
        self.assertEqual(recent[0]["event"], "PreToolUse")
        self.assertEqual(recent[0]["source_id"], "project")
        self.assertEqual(stats["total"], len(HOOK_EVENT_TYPES))
        self.assertEqual(stats["started"], 1)
        self.assertEqual(stats["progress"], 1)
        self.assertEqual(stats["finished"], 1)
        self.assertEqual(stats["failed"], 1)
        self.assertEqual(stats["blocked"], 1)
        self.assertEqual(stats["timed_out"], 1)
        self.assertEqual(stats["input_modified"], 1)
        for event_type in HOOK_EVENT_TYPES:
            self.assertEqual(stats["by_type"][event_type], 1)

    def test_projector_bounds_recent_hook_rows_without_losing_stats(self):
        snapshot = RuntimeProjector().project([
            RuntimeEvent(
                seq=seq,
                type="hook_progress",
                session_id="s1",
                payload={"hook_id": "audit", "progress": seq},
            )
            for seq in range(1, 56)
        ])

        self.assertEqual(len(snapshot["hooks"]["recent"]), 50)
        self.assertEqual(snapshot["hooks"]["recent"][0]["seq"], 6)
        self.assertEqual(snapshot["hooks"]["stats"]["total"], 55)
        self.assertEqual(snapshot["hooks"]["stats"]["progress"], 55)

    def test_plugin_reload_merges_and_updates_latest_plugin_state(self):
        snapshot = RuntimeProjector().project([
            RuntimeEvent(
                seq=1,
                type="plugin_state_changed",
                session_id="s1",
                timestamp="2026-01-01T00:00:00.000Z",
                payload={
                    "plugin_id": "quality-gates",
                    "state": {"enabled": True, "version": "1.0.0"},
                    "source": "project",
                },
            ),
            RuntimeEvent(
                seq=2,
                type="plugin_reloaded",
                session_id="s1",
                timestamp="2026-01-01T00:01:00.000Z",
                payload={
                    "plugin_id": "quality-gates",
                    "state": {"version": "1.1.0"},
                    "reason": "manifest_changed",
                },
            ),
        ])

        plugin = snapshot["plugins"]["quality-gates"]
        self.assertTrue(plugin["enabled"])
        self.assertEqual(plugin["version"], "1.1.0")
        self.assertEqual(plugin["source"], "project")
        self.assertEqual(plugin["reason"], "manifest_changed")
        self.assertEqual(plugin["last_event"], "plugin_reloaded")
        self.assertEqual(plugin["last_reloaded_at"], "2026-01-01T00:01:00.000Z")
        self.assertEqual(plugin["reload_count"], 1)
        self.assertEqual(plugin["seq"], 2)

    def test_history_ops_append_hook_event_and_update_plugin_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            ops = RuntimeHistoryOps(tmp)
            hook_event = ops.append_hook_event(
                "s1",
                "hook_blocked",
                {"hook_id": "protect-prod", "reason": "production command"},
                run_id="r1",
            )
            plugin_event = ops.update_plugin_state(
                "s1",
                "quality-gates",
                {"enabled": True, "version": "1.0.0"},
            )
            reload_event = ops.update_plugin_state(
                "s1",
                "quality-gates",
                {"version": "1.1.0"},
                event_type="plugin_reloaded",
                reason="manual_reload",
            )

            snapshot = ops.snapshots.read("s1")
            self.assertEqual(hook_event.run_id, "r1")
            self.assertEqual(plugin_event.type, "plugin_state_changed")
            self.assertEqual(reload_event.type, "plugin_reloaded")
            self.assertEqual(snapshot["hooks"]["stats"]["blocked"], 1)
            self.assertEqual(snapshot["plugins"]["quality-gates"]["version"], "1.1.0")
            self.assertTrue(snapshot["plugins"]["quality-gates"]["enabled"])
            self.assertEqual(
                [event.type for event in ops.event_log.read_all("s1")],
                ["hook_blocked", "plugin_state_changed", "plugin_reloaded"],
            )

    def test_history_ops_rejects_unknown_audit_types_and_missing_plugin_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            ops = RuntimeHistoryOps(tmp)
            with self.assertRaises(ValueError):
                ops.append_hook_event("s1", "hook_unknown", {})
            with self.assertRaises(ValueError):
                ops.update_plugin_state("s1", "", {"enabled": True})
            with self.assertRaises(ValueError):
                ops.update_plugin_state(
                    "s1",
                    "plugin",
                    {},
                    event_type="plugin_installed",
                )

    def test_ui_projection_maps_hook_lifecycle_events_without_payload_type_collision(self):
        projected = RuntimeUiProjection.events_to_ui([
            RuntimeEvent(
                seq=index,
                type=event_type,
                session_id="s1",
                payload={"type": "command", "hook_id": "audit"},
            )
            for index, event_type in enumerate(HOOK_EVENT_TYPES, start=1)
        ])

        self.assertEqual([event["type"] for event in projected], HOOK_EVENT_TYPES)
        self.assertEqual(
            [event["hook_runtime_event"] for event in projected],
            HOOK_EVENT_TYPES,
        )
        self.assertEqual([event["runtime_seq"] for event in projected], list(range(1, 8)))


if __name__ == "__main__":
    unittest.main()
