"""Decompose probe latency by stack/shape into connection (t_headers) vs server think."""
import glob
import json
import os
import statistics
import sys
from collections import defaultdict

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
rows = []
for path in glob.glob(os.path.join(HERE, "*.json")):
    name = os.path.basename(path)
    if name in ("ttft_stats.json", "myagent_ttft.json"):
        continue
    try:
        data = json.load(open(path, encoding="utf-8"))
    except Exception:
        continue
    for r in data.get("rows", []):
        if r.get("ok") and r.get("ttft_ms"):
            r["_src"] = name
            rows.append(r)

by_arm = defaultdict(list)
for r in rows:
    by_arm[r["arm"]].append(r)

print(f"{'arm':16s} {'n':>3s} {'t_headers':>10s} {'server_think':>13s} {'ttft':>9s}")
for arm in sorted(by_arm):
    v = by_arm[arm]
    th = [r["t_headers_ms"] for r in v if r.get("t_headers_ms")]
    st = [r["server_think_ms"] for r in v if r.get("server_think_ms") is not None]
    tt = [r["ttft_ms"] for r in v]
    print(f"{arm:16s} {len(v):3d} {statistics.median(th):10.0f} "
          f"{statistics.median(st) if st else float('nan'):13.0f} {statistics.median(tt):9.0f}")

print()
print("per-source breakdown:")
by_src = defaultdict(lambda: defaultdict(list))
for r in rows:
    by_src[r["_src"]][r["arm"]].append(r)

for src in sorted(by_src):
    print(f"\n--- {src} ---")
    for arm in sorted(by_src[src]):
        v = by_src[src][arm]
        th = [r["t_headers_ms"] for r in v if r.get("t_headers_ms")]
        st = [r["server_think_ms"] for r in v if r.get("server_think_ms") is not None]
        print(f"  {arm:16s} n={len(v):3d} headers_med={statistics.median(th):7.0f} "
              f"think_med={statistics.median(st) if st else float('nan'):7.0f}")

# Paired decomposition on nonces that have both real-stack arms.
print()
print("paired decomposition (node:dsh vs py:myagent):")
by_nonce = defaultdict(dict)
for r in rows:
    by_nonce[r["nonce"]][r["arm"]] = r
d_headers, d_think, d_ttft = [], [], []
for nonce, arms in by_nonce.items():
    if "node:dsh" in arms and "py:myagent" in arms:
        a, b = arms["node:dsh"], arms["py:myagent"]
        if a.get("t_headers_ms") and b.get("t_headers_ms"):
            d_headers.append(b["t_headers_ms"] - a["t_headers_ms"])
        if a.get("server_think_ms") is not None and b.get("server_think_ms") is not None:
            d_think.append(b["server_think_ms"] - a["server_think_ms"])
        d_ttft.append(b["ttft_ms"] - a["ttft_ms"])


def show(label, vals):
    if not vals:
        return
    vals = sorted(vals)
    mean = sum(vals) / len(vals)
    print(f"  {label:34s} n={len(vals):3d} mean={mean:+7.0f} ms  median={statistics.median(vals):+7.0f} ms")


show("py:myagent - node:dsh  t_headers", d_headers)
show("py:myagent - node:dsh  server_think", d_think)
show("py:myagent - node:dsh  ttft (total)", d_ttft)
