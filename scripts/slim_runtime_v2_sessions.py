"""Batch storage slimming for Runtime V2 sessions.

Order of operations per session (all reversible or rebuildable):
  1. compact events.jsonl into one baseline fact (keeps a backup by default)
  2. compact finished subagent logs
  3. drop rebuildable execution_recovery.chk checkpoints
  4. rewrite latest.json with the new projector (history_ops summaries)

The snapshot rewrite is what applies the new history_ops encoding to sessions
that are never opened again; without it an archived session keeps its old
270 MiB snapshot forever.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.runtime_v2 import (  # noqa: E402
    RuntimeProjector,
    RuntimeV2LogCompactionService,
    SessionEventLog,
    SnapshotStore,
)
from app.runtime_v2.versions import PROJECTOR_VERSION  # noqa: E402


def dir_size(path: Path) -> int:
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                pass
    return total


def refresh_snapshot(sessions_dir: Path, session_id: str, *, dry_run: bool) -> dict:
    """Rebuild latest.json with the current projector version."""
    log = SessionEventLog(sessions_dir)
    store = SnapshotStore(sessions_dir)
    path = store.path(session_id)
    before = path.stat().st_size if path.exists() else 0
    if dry_run:
        return {"action": "refresh_snapshot", "dry_run": True, "bytes_before": before}
    events = log.read_all(session_id)
    snapshot = RuntimeProjector().project(events)
    store.write(session_id, snapshot)
    after = path.stat().st_size if path.exists() else 0
    return {
        "action": "refresh_snapshot",
        "projector_version": PROJECTOR_VERSION,
        "bytes_before": before,
        "bytes_after": after,
    }


def slim_session(
    sessions_dir: Path,
    session_id: str,
    *,
    keep_backup: bool,
    dry_run: bool,
    skip_compact: bool,
) -> dict:
    session_dir = sessions_dir / session_id
    before = dir_size(session_dir)
    report: dict = {"session_id": session_id, "bytes_before": before, "steps": []}
    service = RuntimeV2LogCompactionService(sessions_dir)

    if not skip_compact:
        try:
            if dry_run:
                event_path = session_dir / "events.jsonl"
                report["steps"].append({
                    "action": "compact",
                    "dry_run": True,
                    "bytes_before": event_path.stat().st_size if event_path.exists() else 0,
                })
            else:
                report["steps"].append({"action": "compact", **service.compact(session_id, keep_backup=keep_backup)})
        except Exception as exc:
            report["steps"].append({"action": "compact", "error": str(exc)})

        if not dry_run:
            for row in service.compact_subagents(session_id, keep_backup=keep_backup):
                report["steps"].append({"action": "compact_subagent", **row})

    if not dry_run:
        report["steps"].append({"action": "prune_derived", **service.prune_derived(session_id)})

    try:
        report["steps"].append(refresh_snapshot(sessions_dir, session_id, dry_run=dry_run))
    except Exception as exc:
        report["steps"].append({"action": "refresh_snapshot", "error": str(exc)})

    report["bytes_after"] = before if dry_run else dir_size(session_dir)
    report["saved"] = report["bytes_before"] - report["bytes_after"]
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sessions_dir", type=Path)
    parser.add_argument("session_ids", nargs="*")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--min-bytes", type=int, default=0)
    parser.add_argument("--no-backup", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-compact", action="store_true")
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()

    sessions_dir = args.sessions_dir.resolve()
    ids = list(dict.fromkeys(str(x) for x in args.session_ids if str(x)))
    if args.all:
        for child in sorted(sessions_dir.iterdir()):
            if not (child / "events.jsonl").is_file():
                continue
            if dir_size(child) >= max(0, args.min_bytes):
                ids.append(child.name)
        ids = list(dict.fromkeys(ids))
    if not ids:
        parser.error("provide session ids or --all")

    reports = []
    grand_before = grand_after = 0
    for session_id in ids:
        started = time.time()
        try:
            report = slim_session(
                sessions_dir,
                session_id,
                keep_backup=not args.no_backup,
                dry_run=args.dry_run,
                skip_compact=args.skip_compact,
            )
        except Exception as exc:
            report = {"session_id": session_id, "error": str(exc)}
        report["seconds"] = round(time.time() - started, 1)
        reports.append(report)
        grand_before += report.get("bytes_before") or 0
        grand_after += report.get("bytes_after") or 0
        print(json.dumps({
            "session": session_id[:8],
            "MiB_before": round((report.get("bytes_before") or 0) / 1048576, 1),
            "MiB_after": round((report.get("bytes_after") or 0) / 1048576, 1),
            "saved_MiB": round((report.get("saved") or 0) / 1048576, 1),
            "seconds": report.get("seconds"),
            "error": report.get("error"),
        }, ensure_ascii=False), flush=True)

    print(json.dumps({
        "total_MiB_before": round(grand_before / 1048576, 1),
        "total_MiB_after": round(grand_after / 1048576, 1),
        "saved_MiB": round((grand_before - grand_after) / 1048576, 1),
        "sessions": len(reports),
    }, ensure_ascii=False))
    if args.json_out:
        args.json_out.write_text(json.dumps(reports, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
