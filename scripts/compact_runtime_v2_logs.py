from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.runtime_v2 import RuntimeV2LogCompactionService


def main() -> int:
    parser = argparse.ArgumentParser(description="Safely compact inactive Runtime V2 event logs.")
    parser.add_argument("sessions_dir", type=Path)
    parser.add_argument("session_ids", nargs="*")
    parser.add_argument("--all", action="store_true", help="compact every root session above --min-bytes")
    parser.add_argument("--min-bytes", type=int, default=16 * 1024 * 1024)
    parser.add_argument("--no-backup", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    session_ids = list(dict.fromkeys(str(value) for value in args.session_ids if str(value)))
    if args.all:
        threshold = max(0, int(args.min_bytes))
        for child in args.sessions_dir.iterdir() if args.sessions_dir.exists() else []:
            event_path = child / "events.jsonl"
            if child.is_dir() and event_path.is_file() and event_path.stat().st_size >= threshold:
                session_ids.append(child.name)
        session_ids = list(dict.fromkeys(session_ids))
    if not session_ids:
        parser.error("provide at least one session_id or use --all")

    service = RuntimeV2LogCompactionService(args.sessions_dir)
    failed = False
    for session_id in session_ids:
        try:
            result = service.compact(
                session_id,
                keep_backup=not args.no_backup,
                force=bool(args.force),
            )
        except Exception as exc:
            failed = True
            result = {"compacted": False, "session_id": session_id, "error": str(exc)}
        else:
            result = {"session_id": session_id, **result}
        print(json.dumps(result, ensure_ascii=False))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
