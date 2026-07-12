from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.runtime_v2 import RuntimeV2RootEventLogRepairService  # noqa: E402


def _root_session_ids(sessions_dir: Path) -> list[str]:
    if not sessions_dir.is_dir():
        return []
    return sorted(
        path.name
        for path in sessions_dir.iterdir()
        if (
            path.is_dir()
            and _is_canonical_uuid(path.name)
            and (path / "events.jsonl").is_file()
        )
    )


def _is_canonical_uuid(value: str) -> bool:
    try:
        return str(UUID(str(value))) == str(value).lower()
    except (ValueError, AttributeError):
        return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Dry-run audit or explicitly repair historical Runtime V2 root event logs. "
            "Normal session paths never invoke this service."
        )
    )
    parser.add_argument("--sessions-dir", default=str(ROOT / "workspace" / "sessions"))
    parser.add_argument(
        "--session-id",
        action="append",
        default=[],
        help="root session id to inspect; repeat for multiple sessions",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="write verified repair; requires at least one explicit --session-id",
    )
    parser.add_argument("--only-dirty", action="store_true")
    args = parser.parse_args()

    sessions_dir = Path(args.sessions_dir).resolve()
    requested = [str(value or "").strip() for value in args.session_id if str(value or "").strip()]
    if args.apply and not requested:
        parser.error("--apply requires at least one explicit --session-id")
    session_ids = requested or _root_session_ids(sessions_dir)
    service = RuntimeV2RootEventLogRepairService(sessions_dir)
    results = [service.repair(session_id, apply=bool(args.apply)) for session_id in session_ids]
    if args.only_dirty:
        results = [row for row in results if row.get("repair_required") or row.get("conflicts")]
    payload = {
        "ok": not any(row.get("action") in {"refused", "rolled_back", "rollback_failed"} for row in results),
        "apply": bool(args.apply),
        "sessions_dir": str(sessions_dir),
        "checked": len(session_ids),
        "dirty": sum(1 for row in results if row.get("repair_required")),
        "repaired": sum(1 for row in results if row.get("applied")),
        "refused": sum(1 for row in results if row.get("action") == "refused"),
        "rolled_back": sum(1 for row in results if row.get("action") in {"rolled_back", "rollback_failed"}),
        "results": results,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
