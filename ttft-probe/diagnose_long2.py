"""Diagnose the failures in the 64-request long-context run before trusting its numbers.

A run where 21 of 64 requests return nothing is not a clean experiment: if the failures
are not random with respect to arm or to position in the run, dropping them biases the
comparison. This checks:
  1. WHEN the failures started (position in the trial order)
  2. WHETHER they are balanced across arms
  3. what the numbers look like on the clean prefix only
  4. whether the successful half shows an arm effect at all

Usage: python ttft-probe/diagnose_long2.py
"""
from __future__ import annotations

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
ARMS = ["A_myagent_thinking_max", "B_dsh_no_thinking_field",
        "C_thinking_high", "D_thinking_disabled"]

data = json.loads(open(os.path.join(HERE, "params_long2.json"), encoding="utf-8").read())
rows = sorted(data["rows"], key=lambda r: r["trial"])

print("=" * 78)
print("1. FAILURE PATTERN BY POSITION")
print("=" * 78)
ok = [r for r in rows if r.get("ttft_ms")]
bad = [r for r in rows if not r.get("ttft_ms")]
print(f"  usable {len(ok)} / total {len(rows)};  failures {len(bad)}")
if bad:
    print(f"  failure trials: {sorted(r['trial'] for r in bad)}")
    print(f"  first failure at trial {min(r['trial'] for r in bad)}")
    print(f"  successes after that point: "
          f"{sum(1 for r in ok if r['trial'] > min(x['trial'] for x in bad))}")

print()
print("=" * 78)
print("2. ARE FAILURES BALANCED ACROSS ARMS?")
print("=" * 78)
per = defaultdict(lambda: {"ok": 0, "bad": 0})
for r in rows:
    per[r["arm"]]["ok" if r.get("ttft_ms") else "bad"] += 1
print(f"  {'arm':26s} {'ok':>4s} {'failed':>7s} {'survival':>9s}")
for a in ARMS:
    v = per[a]
    tot = v["ok"] + v["bad"]
    print(f"  {a:26s} {v['ok']:4d} {v['bad']:7d} {v['ok'] / tot * 100:8.0f}%")
print()
print("  Unequal survival means the surviving sample is not a fair draw -- an arm that")
print("  lost more requests could look better or worse purely from which ones died.")

print()
print("=" * 78)
print("3. THE CLEAN PREFIX (before the first failure)")
print("=" * 78)
first_bad = min((r["trial"] for r in bad), default=None)
if first_bad:
    clean = [r for r in rows if r["trial"] < first_bad and r.get("ttft_ms")]
    print(f"  trials 1..{first_bad - 1}, all successful: n={len(clean)}")
    bpa = defaultdict(list)
    for r in clean:
        bpa[r["arm"]].append(r)
    print(f"  {'arm':26s} {'n':>3s} {'ttft med':>9s} {'total med':>10s} {'reason ch':>10s}")
    for a in ARMS:
        v = bpa.get(a, [])
        if not v:
            continue
        print(f"  {a:26s} {len(v):3d} {statistics.median([r['ttft_ms'] for r in v]):9.0f} "
              f"{statistics.median([r['total_ms'] for r in v]):10.0f} "
              f"{statistics.median([r['reasoning_chars'] for r in v]):10.0f}")
    a = [r["total_ms"] for r in bpa.get(ARMS[0], [])]
    c = [r["total_ms"] for r in bpa.get(ARMS[2], [])]
    if a and c:
        print(f"\n  C(high) - A(max) on the clean prefix: "
              f"{statistics.median(c) - statistics.median(a):+.0f} ms  "
              f"(n={len(a)} vs {len(c)})")

print()
print("=" * 78)
print("4. OUTLIERS: is the run contaminated by stalls?")
print("=" * 78)
t = sorted(r["total_ms"] for r in ok)
print(f"  total_ms: min {t[0]:.0f}  p25 {t[len(t)//4]:.0f}  median {statistics.median(t):.0f}  "
      f"p75 {t[3*len(t)//4]:.0f}  max {t[-1]:.0f}")
big = [r for r in ok if r["total_ms"] > 12000]
print(f"  requests over 12 s: {len(big)}")
for r in big:
    print(f"    trial {r['trial']:3d}  {r['arm']:26s} ttft={r['ttft_ms']:.0f} "
          f"total={r['total_ms']:.0f}")
print()
print("  Stalls that hit different arms at different times add variance without adding")
print("  signal, which is exactly what a null result looks like.")

print()
print("=" * 78)
print("VERDICT")
print("=" * 78)
print("  This run cannot settle the question. From trial 43 onward the endpoint stopped")
print("  answering most requests, survival differs by arm, and several successful requests")
print("  carry 13-16 s stalls. Pooling it with the earlier run would launder that damage")
print("  into a confident-looking average.")
