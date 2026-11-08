"""Reclaim change-review workspace baselines that nothing references.

A baseline is a full zip of the work root taken before a run edits files. The
plugin is supposed to drop it in ``finish_run`` once the records are durable,
but an interrupted or superseded run leaves the zip behind with no ``pending``
entry pointing at it. Those orphans are pure dead weight: 2.8 GiB across one
workspace, with a single 922 MiB zip in an archived session.

Safety rules (all must hold before a zip is removed):
  * the baseline key is not in ``pending`` (no in-flight review needs it)
  * the key is not in ``deferred_sweeps``
  * no ``pending`` row references its ``baseline_key``
  * the owning session has no active run
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def load_index(path: Path) -> dict | None:
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def referenced_keys(index: dict) -> set[str]:
    """Every baseline key still needed by an in-flight review."""
    keys: set[str] = set()
    for name in ("pending", "deferred_sweeps"):
        rows = index.get(name)
        if isinstance(rows, dict):
            keys.update(str(key) for key in rows)
    pending = index.get("pending")
    if isinstance(pending, dict):
        for item in pending.values():
            if isinstance(item, dict) and item.get("baseline_key"):
                keys.add(str(item["baseline_key"]))
    return keys


def session_is_idle(session_dir: Path) -> bool:
    """Idle means no *currently running* run, not merely a stale pointer.

    ``metadata.json`` keeps ``active_run_id`` after a run finishes, so the
    authoritative signal is the projected ``active_runs`` list in the snapshot.
    A session with no snapshot is treated as idle only when its event log has no
    unterminated run.
    """
    try:
        with (session_dir / "metadata.json").open("r", encoding="utf-8") as fh:
            meta = json.load(fh)
    except (OSError, ValueError):
        meta = {}
    if isinstance(meta, dict) and meta.get("archived"):
        return True
    snapshot_path = session_dir / "snapshots" / "latest.json"
    try:
        import ijson

        with snapshot_path.open("rb") as fh:
            for key, value in ijson.kvitems(fh, ""):
                if key == "active_runs":
                    return not value
    except Exception:
        pass
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sessions_dir", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--min-bytes", type=int, default=1024 * 1024)
    args = parser.parse_args()

    sessions_dir = args.sessions_dir.resolve()
    total_freed = 0
    removed = 0
    for index_path in sorted(sessions_dir.glob("*/change_reviews/index.json")):
        session_dir = index_path.parent.parent
        index = load_index(index_path)
        if index is None:
            continue
        if not session_is_idle(session_dir):
            print(json.dumps({"session": session_dir.name[:8], "skipped": "active run"}))
            continue
        baselines = index.get("baselines")
        if not isinstance(baselines, dict):
            continue
        keep = referenced_keys(index)
        stale = []
        for key, row in baselines.items():
            if not isinstance(row, dict):
                continue
            if str(key) in keep:
                continue
            baseline_id = str(row.get("baseline_id") or "")
            if not baseline_id:
                continue
            zip_path = index_path.parent / "baselines" / f"{baseline_id}.zip"
            if not zip_path.is_file():
                continue
            size = zip_path.stat().st_size
            if size < args.min_bytes:
                continue
            stale.append((key, baseline_id, zip_path, size))
        if not stale:
            continue
        freed = sum(item[3] for item in stale)
        print(json.dumps({
            "session": session_dir.name[:8],
            "stale_baselines": len(stale),
            "MiB": round(freed / 1048576, 1),
            "dry_run": args.dry_run,
        }, ensure_ascii=False))
        if args.dry_run:
            continue
        for key, baseline_id, zip_path, _size in stale:
            try:
                zip_path.unlink()
            except OSError:
                continue
            baselines.pop(key, None)
            removed += 1
            total_freed += _size
        tmp = index_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(index, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        os.replace(tmp, index_path)

    print(json.dumps({
        "removed_zips": removed,
        "freed_MiB": round(total_freed / 1048576, 1),
        "dry_run": args.dry_run,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
