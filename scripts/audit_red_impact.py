"""Replay historical red approvals through the current classifier.

Answers "does the current rule set still block these, and if so why" for one
machine's own history. Read-only: nothing is written except stdout.

    python scripts/audit_red_impact.py --since 2026-10-01
    python scripts/audit_red_impact.py --sessions-dir /path/to/sessions --verbose
"""
from __future__ import annotations

import argparse
import collections
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app"))
from security.models import PERMISSION_PRESETS, PermissionMode  # noqa: E402
from security.policy import PolicyEngine  # noqa: E402
from security.runtime import classify_tool, forced_approval_for  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "audit_red_approvals", ROOT / "scripts" / "audit_red_approvals.py"
)
audit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(audit)

DEC = json.JSONDecoder()


def extract_command(message: str) -> str:
    """Recover the executed command from the card's preview text.

    The card stores ``run_shell("command": "<json string>", ...)``; the command
    itself is a JSON string literal, so raw_decode handles the escaping. A
    truncated preview cannot be parsed and yields "".
    """
    idx = message.find('"command": ')
    if idx < 0:
        return ""
    try:
        value, _ = DEC.raw_decode(message[idx + len('"command": '):])
    except ValueError:
        return ""
    return value if isinstance(value, str) else ""


def session_workspace(label: str, sessions_dir: Path) -> Path:
    """The work root that was active for this session.

    ``classify_tool`` decides "outside the workspace" against the session's own
    root; using one global root mislabels every sandboxed session.
    """
    fallback = sessions_dir.parent
    try:
        if "/subagents/" in label:
            parent, agent = label.split("/subagents/")
            parent_dir = next(d for d in sessions_dir.iterdir() if d.name.startswith(parent))
            sub = parent_dir / "subagents"
            agent_dir = next((d for d in sub.iterdir() if d.name.startswith(agent)), None) \
                if sub.is_dir() else None
            meta_path = (agent_dir or parent_dir) / "metadata.json"
        else:
            session_dir = next(d for d in sessions_dir.iterdir() if d.name.startswith(label))
            meta_path = session_dir / "metadata.json"
        raw = str(json.loads(meta_path.read_text(encoding="utf-8")).get("work_dir") or "").strip()
    except (StopIteration, OSError, ValueError, TypeError):
        return fallback
    if raw and Path(raw).is_dir():
        return Path(raw).resolve()
    return fallback


def collect(sessions_dir: Path, since: str, until: str = "") -> list[dict]:
    seen: set[str] = set()
    rows: list[dict] = []
    for label, log in audit.iter_sessions(sessions_dir):
        with log.open("r", encoding="utf-8", errors="replace") as fh:
            head = fh.readline()
        generator = (
            audit.from_baseline(log, since)
            if '"runtime_snapshot_compacted"' in head
            else audit.from_events(log, since)
        )
        for ts, _seq, rec in generator:
            if until and ts and ts[:10] > until:
                continue
            if not audit.is_red(rec):
                continue
            aid = str(rec.get("approval_id") or "")
            if aid and aid in seen:
                continue
            seen.add(aid)
            command = extract_command(str(rec.get("message") or ""))
            workspace = session_workspace(label, sessions_dir)
            try:
                request = (
                    classify_tool("run_shell", {"command": command}, workspace)
                    if command
                    else None
                )
                meta = dict(request.metadata or {}) if request else {}
            except Exception:  # noqa: BLE001 - a bad record must not stop the sweep
                request = None
                meta = {}
            # Replay through the policy engine, not the raw metadata flags: the
            # question is "would this still be a forced red approval today",
            # and only the engine knows which rule ids are forced.
            rule_id = ""
            forced = False
            if request is not None:
                try:
                    decision = PolicyEngine(workspace).decide(
                        request,
                        PERMISSION_PRESETS[PermissionMode.ASK_FOR_APPROVAL],
                    )
                    rule_id = str(decision.rule_id or "")
                    forced = forced_approval_for(decision)
                except Exception:  # noqa: BLE001
                    rule_id, forced = "", False
            rows.append({
                "session": label[:8], "timestamp": ts, "approval_id": aid,
                "command": command, "meta": meta, "rule_id": rule_id, "forced": forced,
            })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sessions-dir", type=Path, default=ROOT / "workspace" / "sessions")
    parser.add_argument("--since", default="2026-10-01")
    parser.add_argument("--until", default="", help="inclusive upper bound (YYYY-MM-DD)")
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--verbose", action="store_true", help="list every still-red approval")
    args = parser.parse_args()

    sessions_dir = args.sessions_dir.resolve()
    rows = collect(sessions_dir, args.since, args.until)

    unparsed = [r for r in rows if not r["meta"]]
    still_red = [r for r in rows if r["meta"] and r["forced"]]
    downgraded = [r for r in rows if r["meta"] and not r["forced"] and r["rule_id"]]
    false_positive = [r for r in rows if r["meta"] and not r["rule_id"]]

    window = f"since {args.since}" + (f" until {args.until}" if args.until else "")
    print(f"{window} | sessions {sessions_dir}")
    print(f"distinct red approvals: {len(rows)}")
    print()
    print(f"  仍为红色（系统级 / 根目录）        : {len(still_red)}")
    print(f"  降级为普通审批（黄色）              : {len(downgraded)}")
    print(f"  不再需要审批（误报 / 已放行）      : {len(false_positive)}")
    print(f"  命令无法解析（卡片文本被截断）      : {len(unparsed)}")
    print()
    print("仍为红色的命中类别:")
    kinds = collections.Counter()
    for row in still_red:
        for kind in (row["meta"].get("destructive_kinds") or []):
            kinds[kind] += 1
    for kind, count in kinds.most_common():
        print(f"  {count:4d}  {kind}")

    if false_positive:
        print()
        print("误报样本（新规则已不再拦截）:")
        for row in false_positive[:8]:
            print(f"  [{row['session']}] {row['timestamp'][:16]} "
                  f"{' '.join(row['command'].split())[:110]}")

    if args.verbose:
        print()
        print("仍为红色的明细:")
        for row in still_red:
            labels = "、".join(row["meta"].get("destructive_labels") or [])
            print(f"  [{row['session']}] {row['timestamp'][:16]} {labels}")
            print(f"      {' '.join(row['command'].split())[:160]}")

    if args.json_out:
        args.json_out.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
