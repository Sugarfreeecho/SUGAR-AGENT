"""Combine both long-context runs and report the pooled verdict.

Run 1 (params_long.json)  : 4 arms x 6 trials, underpowered on its own.
Run 2 (params_long2.json) : 4 arms x 16 trials, sized for ~80% power on a 1.4 s effect.

Pooling is legitimate here: both used the same deterministic pad, the same prompt, the
same arms, one warm connection, and randomized order. Pooled n per arm should be enough
to say whether reasoning_effort=max costs more at long context.

Usage: python ttft-probe/analyze_long_pooled.py
"""
from __future__ import annotations

import json
import math
import os
import random
import statistics
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
random.seed(20260911)
A = "A_myagent_thinking_max"
B = "B_dsh_no_thinking_field"
C = "C_thinking_high"
D = "D_thinking_disabled"


def load(name):
    p = os.path.join(HERE, name)
    if not os.path.exists(p):
        return None
    return json.loads(open(p, encoding="utf-8").read())


def rows_of(data, arm, key):
    if data is None:
        return []
    return [r[key] for r in data["rows"]
            if r.get("arm") == arm and r.get(key) is not None and r.get("ttft_ms")]


def boot_ci(a, b, n=20000):
    if len(a) < 4 or len(b) < 4:
        return None
    d = sorted(statistics.median([random.choice(b) for _ in b])
               - statistics.median([random.choice(a) for _ in a]) for _ in range(n))
    return d[int(0.025 * n)], d[int(0.975 * n)], statistics.median(d)


def mean_ci(a, b, n=20000):
    if len(a) < 4 or len(b) < 4:
        return None
    d = sorted(statistics.mean([random.choice(b) for _ in b])
               - statistics.mean([random.choice(a) for _ in a]) for _ in range(n))
    return d[int(0.025 * n)], d[int(0.975 * n)], statistics.mean(d)


def mdd(a, b):
    if len(a) < 4 or len(b) < 4:
        return None
    sd = math.sqrt(statistics.variance(a) + statistics.variance(b))
    return 2.8 * sd / math.sqrt(min(len(a), len(b)))


runs = [("run1 (6 trials)", load("params_long.json")),
        ("run2 (16 trials)", load("params_long2.json"))]

print("=" * 80)
print("LONG-CONTEXT PARAMETER EXPERIMENTS (100k shared pad)")
print("=" * 80)

# run2 lost everything from trial 43 on (the endpoint stopped answering), and the
# casualties are unevenly spread across arms, so only its clean prefix is usable.
def usable_rows(d, cutoff=None):
    if d is None:
        return []
    out = [r for r in d["rows"] if r.get("ttft_ms")]
    if cutoff is not None:
        out = [r for r in out if r["trial"] <= cutoff]
    return out


bad2 = [r["trial"] for r in (load("params_long2.json") or {"rows": []})["rows"]
        if not r.get("ttft_ms")]
cut2 = (min(bad2) - 1) if bad2 else None
if cut2:
    print(f"  run2: usable prefix = trials 1..{cut2} "
          f"({sum(1 for r in load('params_long2.json')['rows'] if r['trial'] <= cut2)} requests); "
          f"later trials dropped as endpoint failures")

pooled = {}
for label, d in runs:
    if d is None:
        print(f"  {label}: not found")
        continue
    rows_ = usable_rows(d, cut2 if "run2" in label else None)
    n = {}
    for arm in (A, B, C, D):
        v = [r for r in rows_ if r["arm"] == arm]
        n[arm[0]] = len(v)
        for k in ("ttft_ms", "total_ms", "reasoning_chars", "out_tokens", "tps"):
            pooled.setdefault(arm, {}).setdefault(k, [])
            pooled[arm][k].extend(r[k] for r in v if r.get(k) is not None)
    print(f"  {label}: per-arm n = {n}")

if not pooled:
    print("no data")
    raise SystemExit(0)

print()
print("=" * 80)
print("POOLED RESULTS")
print("=" * 80)
print(f"  {'arm':26s} {'n':>3s} {'ttft med':>9s} {'total med':>10s} {'total mean':>11s} "
      f"{'reason ch':>10s} {'out tok':>8s} {'tps':>7s}")
for arm in (A, B, C, D):
    if arm not in pooled:
        continue
    t = pooled[arm]["total_ms"]
    tt = pooled[arm]["ttft_ms"]
    if not t:
        continue
    print(f"  {arm:26s} {len(t):3d} {statistics.median(tt):9.0f} {statistics.median(t):10.0f} "
          f"{statistics.mean(t):11.0f} "
          f"{statistics.median(pooled[arm]['reasoning_chars']):10.0f} "
          f"{statistics.median(pooled[arm]['out_tokens']):8.0f} "
          f"{statistics.median(pooled[arm]['tps']):7.1f}")

print()
print("=" * 80)
print("VS A (MyAgent: thinking=enabled, reasoning_effort=max)")
print("=" * 80)
print(f"  {'comparison':34s} {'median diff':>22s} {'mean diff':>22s}")
for other in (C, B, D):
    a = pooled[A]["total_ms"]
    b = pooled[other]["total_ms"]
    cm = boot_ci(a, b)
    cmean = mean_ci(a, b)
    if not cm:
        continue
    tag = f"{other[:22]} - A"
    star = " *" if (cm[0] > 0 or cm[1] < 0) else ""
    star2 = " *" if (cmean[0] > 0 or cmean[1] < 0) else ""
    print(f"  {tag:34s} {cm[2]:+9.0f} [{cm[0]:+7.0f},{cm[1]:+7.0f}]{star:2s} "
          f"{cmean[2]:+9.0f} [{cmean[0]:+7.0f},{cmean[1]:+7.0f}]{star2}")

for other in (C,):
    a = pooled[A]["ttft_ms"]
    b = pooled[other]["ttft_ms"]
    c = boot_ci(a, b)
    if c:
        print(f"\n  TTFT only, {other} - A: {c[2]:+.0f} ms  CI [{c[0]:+.0f}, {c[1]:+.0f}]  "
              f"min detectable ~{mdd(a, b):.0f} ms")

print()
print("=" * 80)
print("SIDE BY SIDE WITH THE SMALL-CONTEXT RESULT")
print("=" * 80)
sm = load("params.json")
if sm:
    sa, sc = rows_of(sm, A, "total_ms"), rows_of(sm, C, "total_ms")
    la, lc = pooled[A]["total_ms"], pooled[C]["total_ms"]
    print(f"  {'context':22s} {'A med':>8s} {'C med':>8s} {'C-A':>9s} {'95% CI':>20s} {'verdict':>12s}")
    for label, a, b in (("small (~40 tok)", sa, sc), ("long (~100k tok)", la, lc)):
        ci = boot_ci(a, b)
        if not ci:
            continue
        verdict = "DETECTED" if (ci[0] > 0 or ci[1] < 0) else "not detected"
        print(f"  {label:22s} {statistics.median(a):8.0f} {statistics.median(b):8.0f} "
              f"{statistics.median(b) - statistics.median(a):+9.0f} "
              f"{f'[{ci[0]:+.0f}, {ci[1]:+.0f}]':>20s} {verdict:>12s}")
    print()
    print("  HYPOTHESIS TESTED: 'effort=max costs much more at long context, explaining the")
    print("  production 1.5 s gap.'  A context-scaling effect would show a LARGER C-A gap at")
    print("  100k than at 40 tokens.")
