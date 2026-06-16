from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .event_log import SessionEventLog
from .event_schema import RuntimeEvent
from .projector import RuntimeProjector
from .snapshot_store import SnapshotStore


class RuntimeSubagentStore:
    """Parent-local subagent event storage.

    Layout:
      {parent_session}/subagents/{agent_id}/events.jsonl
      {parent_session}/subagents/{agent_id}/snapshots/latest.json
      {parent_session}/subagents/{agent_id}/metadata.json
    """

    def __init__(self, sessions_dir: str | Path):
        self.sessions_dir = Path(sessions_dir)
        self.projector = RuntimeProjector()

    def root_for_parent(self, parent_session_id: str) -> Path:
        return self.sessions_dir / self._safe_id(parent_session_id) / "subagents"

    def agent_dir(self, parent_session_id: str, agent_id: str) -> Path:
        return self.root_for_parent(parent_session_id) / self._safe_id(agent_id)

    def task_index_path(self, parent_session_id: str) -> Path:
        return self.root_for_parent(parent_session_id) / "tasks.json"

    def pending_results_path(self, parent_session_id: str) -> Path:
        return self.root_for_parent(parent_session_id) / "pending_results.json"

    def append_event(self, parent_session_id: str, agent_id: str, event_type: str, payload: Optional[dict] = None, run_id: Optional[str] = None) -> RuntimeEvent:
        root = self.root_for_parent(parent_session_id)
        log = SessionEventLog(root)
        event = log.append(agent_id, event_type, payload=payload or {}, run_id=run_id)
        snapshots = SnapshotStore(root)
        snapshot = self.projector.project_incremental(snapshots.read(agent_id), event)
        snapshots.write(agent_id, snapshot)
        return event

    def write_metadata(self, parent_session_id: str, agent_id: str, metadata: dict) -> None:
        path = self.agent_dir(parent_session_id, agent_id) / "metadata.json"
        self._write_json(path, metadata)

    def read_metadata(self, parent_session_id: str, agent_id: str) -> dict:
        path = self.agent_dir(parent_session_id, agent_id) / "metadata.json"
        if not path.is_file():
            return {}
        try:
            with path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}

    def read_snapshot(self, parent_session_id: str, agent_id: str) -> dict:
        return SnapshotStore(self.root_for_parent(parent_session_id)).read(agent_id)

    def list_tasks(self, parent_session_id: str) -> List[dict]:
        rows = self._read_json_list(self.task_index_path(parent_session_id))
        for row in rows:
            if not isinstance(row, dict):
                continue
            tid = str(row.get("task_id") or row.get("agent_id") or row.get("id") or "").strip()
            if not tid:
                continue
            metadata = self.read_metadata(parent_session_id, tid)
            if metadata:
                merged = dict(metadata)
                merged.update(row)
                row.clear()
                row.update(merged)
        return rows

    def upsert_task(self, parent_session_id: str, task_id: str, patch: Dict[str, Any]) -> None:
        tid = str(task_id or "").strip()
        if not tid:
            return
        path = self.task_index_path(parent_session_id)
        rows = self._read_json_list(path)
        now = datetime.now(timezone.utc).isoformat()
        update = {k: v for k, v in dict(patch or {}).items() if v is not None}
        found = False
        for row in rows:
            row_id = str(row.get("task_id") or row.get("agent_id") or row.get("id") or "").strip()
            if row_id != tid:
                continue
            row.update(update)
            row["task_id"] = tid
            row["updated_at"] = now
            found = True
            self.write_metadata(parent_session_id, tid, row)
            break
        if not found:
            row = {"task_id": tid, "created_at": now, "updated_at": now}
            row.update(update)
            rows.append(row)
            self.write_metadata(parent_session_id, tid, row)
        self._write_json(path, rows)

    def write_task_output(self, parent_session_id: str, task_id: str, text: str) -> str:
        tid = str(task_id or "").strip() or "subagent"
        path = self.agent_dir(parent_session_id, tid) / "output.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(text or ""), encoding="utf-8")
        self.upsert_task(parent_session_id, tid, {"output_file": str(path)})
        return str(path)

    def read_task_output(self, parent_session_id: str, task_id: str) -> Dict[str, Any]:
        tid = str(task_id or "").strip()
        if not tid:
            return {"ok": False, "error": "missing task_id"}
        task = next(
            (
                x
                for x in self.list_tasks(parent_session_id)
                if str(x.get("task_id") or x.get("agent_id") or x.get("id") or "") == tid
            ),
            None,
        )
        output_file = str((task or {}).get("output_file") or "").strip()
        path = Path(output_file) if output_file else self.agent_dir(parent_session_id, tid) / "output.md"
        try:
            path = path.expanduser().resolve()
            path.relative_to(self.root_for_parent(parent_session_id).resolve())
        except Exception:
            return {"ok": False, "error": "invalid output path"}
        if not path.is_file():
            return {"ok": False, "error": "output not found"}
        try:
            return {"ok": True, "task_id": tid, "path": str(path), "content": path.read_text(encoding="utf-8")}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def append_pending_result(self, parent_session_id: str, entry: Dict[str, Any]) -> None:
        path = self.pending_results_path(parent_session_id)
        rows = self._read_json_list(path)
        rows.append(dict(entry or {}))
        self._write_json(path, rows)

    def list_pending_results(self, parent_session_id: str) -> List[dict]:
        return self._read_json_list(self.pending_results_path(parent_session_id))

    def save_pending_results(self, parent_session_id: str, rows: List[dict]) -> None:
        self._write_json(self.pending_results_path(parent_session_id), [x for x in rows if isinstance(x, dict)])

    def remove_parent_rows(self, parent_session_id: str, child_session_id: str) -> None:
        child_id = str(child_session_id or "").strip()
        if not child_id:
            return
        for path in (self.task_index_path(parent_session_id), self.pending_results_path(parent_session_id)):
            rows = self._read_json_list(path)
            if not rows:
                continue
            kept = [
                row for row in rows
                if str(row.get("agent_id") or row.get("task_id") or row.get("id") or "") != child_id
            ]
            if len(kept) != len(rows):
                self._write_json(path, kept)

    @staticmethod
    def _safe_id(value: str) -> str:
        safe = str(value or "").strip()
        if not safe or any(part in safe for part in ("/", "\\", "..")):
            raise ValueError("invalid id")
        return safe

    def _read_json_list(self, path: Path) -> List[dict]:
        if not path.is_file():
            return []
        try:
            with path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception:
            return []
        if not isinstance(data, list):
            return []
        return [x for x in data if isinstance(x, dict)]

    def _write_json(self, path: Path, data: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        tmp.replace(path)
