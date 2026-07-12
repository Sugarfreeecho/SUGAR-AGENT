from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from agent_harness import session_manager  # noqa: E402
from runtime_v2 import RuntimeV2SubagentRepairService  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit or explicitly repair Runtime V2 nested-subagent split logs."
    )
    parser.add_argument("--apply", action="store_true", help="write the merged log and archive each ghost")
    parser.add_argument("--child", default="", help="repair only one child session id")
    parser.add_argument("--limit", type=int, default=0, help="maximum child rows to inspect")
    args = parser.parse_args()

    service = RuntimeV2SubagentRepairService(
        session_manager.repository.sessions_dir,
        path_resolver=session_manager._resolve_session_path,
    )
    rows = list(session_manager._load_subagent_index().items())
    if args.child:
        rows = [row for row in rows if row[0] == args.child]
    if args.limit > 0:
        rows = rows[: args.limit]
    results = [
        service.repair(parent_id, child_id, apply=args.apply, archive_ghost=True)
        for child_id, parent_id in rows
    ]
    refused = sum(1 for row in results if str(row.get("action") or "").startswith("refused"))
    pending_archive = sum(1 for row in results if row.get("action") == "committed_pending_archive")
    failed = sum(1 for row in results if row.get("ok") is False)
    payload = {
        "ok": failed == 0,
        "apply": bool(args.apply),
        "checked": len(results),
        "split_brain": sum(1 for row in results if row.get("split_brain")),
        "repaired": sum(1 for row in results if row.get("applied")),
        "refused": refused,
        "committed_pending_archive": pending_archive,
        "failed": failed,
        "results": results,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
