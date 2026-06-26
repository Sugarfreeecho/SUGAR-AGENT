from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("RUNTIME_VERSION", "2")

from app.runtime_v2 import RuntimeHistoryOps, RuntimeMirror, RuntimeModelProjection, RuntimeUiProjection  # noqa: E402
from app.runtime_v2.snapshot_store import SnapshotStore  # noqa: E402


@dataclass
class SessionAudit:
    session_id: str
    legacy_ui_count: int
    runtime_v2_ui_count: int
    legacy_model_count: int
    runtime_v2_model_count: int
    ui_ok: bool
    model_ok: bool
    runtime_v2_active_run_count: int = 0
    runtime_v2_active_runs: List[dict] | None = None
    repaired_ui: int = 0
    repaired_model: int = 0
    repaired_runs: int = 0
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "legacy_ui_count": self.legacy_ui_count,
            "runtime_v2_ui_count": self.runtime_v2_ui_count,
            "legacy_model_count": self.legacy_model_count,
            "runtime_v2_model_count": self.runtime_v2_model_count,
            "ui_ok": self.ui_ok,
            "model_ok": self.model_ok,
            "runtime_v2_active_run_count": self.runtime_v2_active_run_count,
            "runtime_v2_active_runs": self.runtime_v2_active_runs or [],
            "repaired_ui": self.repaired_ui,
            "repaired_model": self.repaired_model,
            "repaired_runs": self.repaired_runs,
            "error": self.error,
        }


def load_json_list(path: Path) -> List[dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return []
    return data if isinstance(data, list) else []


def normalize_event_signature(event: dict) -> tuple[str, str]:
    event_type = str(event.get("type") or "")
    content = event.get("content")
    if content is None:
        content = event.get("result")
    if content is None:
        content = event.get("message")
    return event_type, str(content or "")[:500]


def normalize_message_signature(message: dict) -> tuple[str, str, str]:
    msg_type = str(message.get("type") or message.get("role") or "")
    msg_type = {
        "human": "user",
        "llm": "assistant",
        "ai": "assistant",
        "agent": "assistant",
    }.get(msg_type, msg_type)
    content = str(message.get("content") or "")[:500]
    tool_call_id = str(message.get("tool_call_id") or "")
    return msg_type, content, tool_call_id


def signatures_match(left: Iterable[dict], right: Iterable[dict], *, kind: str) -> bool:
    if kind == "ui":
        a = [normalize_event_signature(item) for item in left if isinstance(item, dict)]
        b = [normalize_event_signature(item) for item in right if isinstance(item, dict)]
    else:
        a = [normalize_message_signature(item) for item in left if isinstance(item, dict)]
        b = [normalize_message_signature(item) for item in right if isinstance(item, dict)]
    return a == b


def audit_session(
    sessions_dir: Path,
    session_id: str,
    *,
    repair_ui: bool = False,
    repair_model: bool = False,
    repair_runs: bool = False,
) -> SessionAudit:
    session_dir = sessions_dir / session_id
    legacy_ui = load_json_list(session_dir / "ui_events.json")
    legacy_model = load_json_list(session_dir / "llm_history.json")
    ui_projection = RuntimeUiProjection(sessions_dir)
    model_projection = RuntimeModelProjection(sessions_dir)

    try:
        v2_ui = ui_projection.read_ui_events_fast(session_id)
        v2_model = model_projection.read_message_dicts(session_id)
        ui_ok = len(legacy_ui) == len(v2_ui) and signatures_match(legacy_ui, v2_ui, kind="ui")
        model_ok = len(legacy_model) == len(v2_model) and signatures_match(legacy_model, v2_model, kind="model")

        repaired_ui = 0
        repaired_model = 0
        repaired_runs = 0
        if repair_ui and legacy_ui and not ui_ok:
            repaired_ui = ui_projection.replace_from_legacy(session_id, legacy_ui, reason="runtime_audit_repair")
            v2_ui = ui_projection.read_ui_events_fast(session_id)
            ui_ok = len(legacy_ui) == len(v2_ui) and signatures_match(legacy_ui, v2_ui, kind="ui")
        if repair_model and legacy_model and not model_ok:
            RuntimeHistoryOps(sessions_dir).replace_model_history(
                session_id,
                legacy_model,
                reason="runtime_audit_repair",
            )
            repaired_model = len(legacy_model)
            v2_model = model_projection.read_message_dicts(session_id)
            model_ok = len(legacy_model) == len(v2_model) and signatures_match(legacy_model, v2_model, kind="model")
        snapshot = SnapshotStore(sessions_dir).read(session_id)
        active_runs = snapshot.get("active_runs") if isinstance(snapshot, dict) else []
        if not isinstance(active_runs, list):
            active_runs = []
        if repair_runs and active_runs:
            mirror = RuntimeMirror(sessions_dir)
            for run in active_runs:
                run_id = str((run or {}).get("run_id") or "").strip() if isinstance(run, dict) else ""
                mirror.mirror_run_interrupted(
                    session_id,
                    run_id or None,
                    {"reason": "runtime_audit_repair", "previous_status": (run or {}).get("status") if isinstance(run, dict) else ""},
                )
                repaired_runs += 1
            snapshot = SnapshotStore(sessions_dir).read(session_id)
            active_runs = snapshot.get("active_runs") if isinstance(snapshot, dict) else []
            if not isinstance(active_runs, list):
                active_runs = []

        return SessionAudit(
            session_id=session_id,
            legacy_ui_count=len(legacy_ui),
            runtime_v2_ui_count=len(v2_ui),
            legacy_model_count=len(legacy_model),
            runtime_v2_model_count=len(v2_model),
            ui_ok=ui_ok,
            model_ok=model_ok,
            runtime_v2_active_run_count=len(active_runs),
            runtime_v2_active_runs=[dict(run) for run in active_runs if isinstance(run, dict)],
            repaired_ui=repaired_ui,
            repaired_model=repaired_model,
            repaired_runs=repaired_runs,
        )
    except Exception as exc:
        return SessionAudit(
            session_id=session_id,
            legacy_ui_count=len(legacy_ui),
            runtime_v2_ui_count=0,
            legacy_model_count=len(legacy_model),
            runtime_v2_model_count=0,
            ui_ok=False,
            model_ok=False,
            runtime_v2_active_run_count=0,
            runtime_v2_active_runs=[],
            error=f"{type(exc).__name__}: {exc}",
        )


def iter_session_ids(sessions_dir: Path, only: Optional[str]) -> List[str]:
    if only:
        return [only]
    if not sessions_dir.exists():
        return []
    return sorted(path.name for path in sessions_dir.iterdir() if path.is_dir())


def summarize(rows: List[SessionAudit]) -> Dict[str, Any]:
    return {
        "checked": len(rows),
        "ui_mismatch": sum(1 for row in rows if not row.ui_ok),
        "model_mismatch": sum(1 for row in rows if not row.model_ok),
        "runtime_v2_active_run_sessions": sum(1 for row in rows if row.runtime_v2_active_run_count > 0),
        "runtime_v2_active_runs": sum(row.runtime_v2_active_run_count for row in rows),
        "errors": sum(1 for row in rows if row.error),
        "repaired_ui": sum(row.repaired_ui for row in rows),
        "repaired_model": sum(row.repaired_model for row in rows),
        "repaired_runs": sum(row.repaired_runs for row in rows),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit V1 legacy files against Runtime V2 projections.")
    parser.add_argument("--sessions-dir", default=str(ROOT / "workspace" / "sessions"))
    parser.add_argument("--session-id", default="")
    parser.add_argument("--repair-ui", action="store_true")
    parser.add_argument("--repair-model", action="store_true")
    parser.add_argument("--repair-runs", action="store_true", help="Append interrupted run events for Runtime V2 active runs.")
    parser.add_argument("--only-mismatches", action="store_true")
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    sessions_dir = Path(args.sessions_dir)
    rows = [
        audit_session(
            sessions_dir,
            session_id,
            repair_ui=bool(args.repair_ui),
            repair_model=bool(args.repair_model),
            repair_runs=bool(args.repair_runs),
        )
        for session_id in iter_session_ids(sessions_dir, args.session_id.strip() or None)
    ]
    output_rows = rows
    if args.only_mismatches:
        output_rows = [
            row for row in rows
            if row.error or not row.ui_ok or not row.model_ok or row.runtime_v2_active_run_count > 0
        ]
    payload = {
        "sessions_dir": str(sessions_dir),
        "summary": summarize(rows),
        "sessions": [row.to_dict() for row in output_rows],
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 1 if payload["summary"]["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
