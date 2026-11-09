"""Single authoritative pass: how the fix changes the 10/01→now red approvals."""
import importlib.util, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app"))
from security.runtime import classify_tool  # noqa: E402

spec = importlib.util.spec_from_file_location("audit", ROOT / "scripts" / "audit_red_approvals.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

DEC = json.JSONDecoder()
BASE = ROOT / "workspace" / "sessions"


def extract(msg):
    i = msg.find('"command": ')
    if i < 0:
        return ""
    try:
        v, _ = DEC.raw_decode(msg[i + len('"command": '):])
        return v if isinstance(v, str) else ""
    except ValueError:
        return ""


def ws_for(label):
    try:
        if "/subagents/" in label:
            parent, agent = label.split("/subagents/")
            pdir = next(d for d in BASE.iterdir() if d.name.startswith(parent))
            adir = next((d for d in (pdir / "subagents").iterdir() if d.name.startswith(agent)), None)
            meta = (adir or pdir) / "metadata.json"
        else:
            sdir = next(d for d in BASE.iterdir() if d.name.startswith(label))
            meta = sdir / "metadata.json"
        raw = str(json.loads(meta.read_text(encoding="utf-8")).get("work_dir") or "").strip()
        return Path(raw).resolve() if raw and Path(raw).is_dir() else ROOT / "workspace"
    except (StopIteration, OSError, ValueError):
        return ROOT / "workspace"


seen, rows = set(), []
for label, log in audit.iter_sessions(BASE):
    with log.open("r", encoding="utf-8", errors="replace") as fh:
        head = fh.readline()
    gen = audit.from_baseline(log, "2026-10-01") if '"runtime_snapshot_compacted"' in head \
        else audit.from_events(log, "2026-10-01")
    for ts, seq, rec in gen:
        if str(rec.get("approval_level")) != "danger":
            continue
        aid = str(rec.get("approval_id") or "")
        if aid in seen:
            continue
        seen.add(aid)
        cmd = extract(str(rec.get("message") or ""))
        try:
            meta = dict(classify_tool("run_shell", {"command": cmd}, ws_for(label)).metadata or {}) if cmd else {}
        except Exception:
            meta = {}
        rows.append({"label": label[:8], "ts": ts, "aid": aid, "meta": meta})

total = len(rows)
false_pos = [r for r in rows if r["meta"] and not r["meta"].get("destructive")]
downgraded = [r for r in rows if r["meta"].get("destructive") and r["meta"].get("workspace_delete")]
still_red = [r for r in rows if r["meta"].get("destructive") and not r["meta"].get("workspace_delete")]
unknown = [r for r in rows if not r["meta"]]

print("distinct red approvals (2026-10-01 → now):", total)
print()
print("  现在会变成黄色（工作区内删除）:", len(downgraded))
print("  不再是红色（误报，已非 destructive）:", len(false_pos))
print("  仍然红色（工作区外/系统级）:", len(still_red))
print("  命令无法解析:", len(unknown))
print()
print("剩余红色的命中类别:")
from collections import Counter
c = Counter()
for r in still_red:
    for k in (r["meta"].get("destructive_kinds") or []):
        c[k] += 1
for k, v in c.most_common():
    print(f"  {v:3d}  {k}")
print()
print("降级样本:")
for r in downgraded[:5]:
    print(f"  [{r['label']}] {r['ts'][:16]} {r['meta'].get('destructive_labels')}")
