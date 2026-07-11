from __future__ import annotations

import uuid
from pathlib import Path
from typing import Optional

from .event_log import SessionEventLog
from .event_schema import RuntimeEvent
from .projector import RuntimeProjector
from .run_registry import RunRegistry
from .snapshot_store import SnapshotStore
from .stream_publisher import StreamPublisher


class RuntimeGateway:
    def __init__(
        self,
        root: str | Path,
        event_log: Optional[SessionEventLog] = None,
        run_registry: Optional[RunRegistry] = None,
        publisher: Optional[StreamPublisher] = None,
    ):
        self.root = Path(root)
        self.event_log = event_log or SessionEventLog(self.root)
        self.run_registry = run_registry or RunRegistry()
        self.publisher = publisher or StreamPublisher()
        self.projector = RuntimeProjector()
        self.snapshots = SnapshotStore(self.root)

    async def append_event(
        self,
        session_id: str,
        event_type: str,
        payload: Optional[dict] = None,
        run_id: Optional[str] = None,
    ) -> RuntimeEvent:
        with self.event_log.session_transaction(session_id):
            event = self.event_log._append_unlocked(session_id, event_type, payload=payload, run_id=run_id)
            snapshot = self.snapshots.read(session_id)
            if int(snapshot.get("last_seq") or 0) != int(event.seq) - 1:
                snapshot = self.projector.project(self.event_log.read_all(session_id))
            else:
                snapshot = self.projector.project_incremental(snapshot, event)
            self.snapshots.stamp_event_log(session_id, snapshot, self.event_log.event_path(session_id))
            self.snapshots.write(session_id, snapshot)
        await self.publisher.publish(event)
        return event

    async def start_run(self, session_id: str, run_id: Optional[str] = None, payload: Optional[dict] = None) -> RuntimeEvent:
        run_id = run_id or str(uuid.uuid4())
        state = self.run_registry.start(session_id, run_id)
        data = {"run": state.to_dict()}
        if payload:
            data.update(payload)
        return await self.append_event(session_id, "run_started", data, run_id=run_id)

    async def heartbeat_run(self, session_id: str, run_id: str) -> RuntimeEvent:
        state = self.run_registry.heartbeat(run_id)
        payload = {"run": state.to_dict() if state else {"run_id": run_id, "missing": True}}
        return await self.append_event(session_id, "run_heartbeat", payload, run_id=run_id)

    async def record_runtime_resume(self, session_id: str, run_id: str, suspended_seconds: float, payload: Optional[dict] = None) -> RuntimeEvent:
        state = self.run_registry.record_resume(run_id, suspended_seconds)
        data = {
            "suspended_seconds": max(0.0, float(suspended_seconds or 0.0)),
            "run": state.to_dict() if state else {"run_id": run_id, "missing": True},
        }
        if payload:
            data.update(payload)
        return await self.append_event(session_id, "runtime_resumed", data, run_id=run_id)

    async def finish_run(self, session_id: str, run_id: str, payload: Optional[dict] = None) -> RuntimeEvent:
        state = self.run_registry.finish(run_id)
        data = {"run": state.to_dict() if state else {"run_id": run_id, "missing": True}}
        if payload:
            data.update(payload)
        return await self.append_event(session_id, "run_finished", data, run_id=run_id)

    async def fail_run(self, session_id: str, run_id: str, error: str, payload: Optional[dict] = None) -> RuntimeEvent:
        state = self.run_registry.fail(run_id, error)
        data = {"error": error, "run": state.to_dict() if state else {"run_id": run_id, "missing": True}}
        if payload:
            data.update(payload)
        return await self.append_event(session_id, "run_failed", data, run_id=run_id)

    async def interrupt_run(self, session_id: str, run_id: str, payload: Optional[dict] = None) -> RuntimeEvent:
        state = self.run_registry.interrupt(run_id)
        data = {"run": state.to_dict() if state else {"run_id": run_id, "missing": True}}
        if payload:
            data.update(payload)
        return await self.append_event(session_id, "run_interrupted", data, run_id=run_id)

    def read_after_seq(self, session_id: str, after_seq: int) -> list[RuntimeEvent]:
        return self.event_log.read_after_seq(session_id, after_seq)

    def state(self) -> dict:
        return self.run_registry.snapshot()

    def rebuild_session_state(self, session_id: str) -> dict:
        snapshot = self.projector.project(self.event_log.read_all(session_id))
        self.snapshots.stamp_event_log(session_id, snapshot, self.event_log.event_path(session_id))
        self.snapshots.write(session_id, snapshot)
        return snapshot

    def read_snapshot(self, session_id: str) -> dict:
        return self.snapshots.read_consistent(session_id, self.event_log, self.projector)
