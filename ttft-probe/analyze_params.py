"""Analyse params_probe.py: is reasoning_effort a real, client-side lever?

Arms: A = MyAgent's saved profile (thinking enabled + reasoning_effort=max),
      B = DSH's route (no thinking and no reasoning_effort field),
      C = thinking enabled + reasoning_effort=high,
      D = thinking explicitly disabled.

Reports bootstrap CIs for the arm differences and checks whether the effect is monotonic
in reasoning effort, which matters more than any single pairwise comparison at this n.

Usage: python ttft-probe/analyze_params.py [params.json]
"""
from __future__ import annotations

import json
import os
import random
import statistics
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
PATH = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "params.json")
random.seed(20260911)


def median(v):
    return statistics.median(v) if v else float("nan")


def pick(v, p):
    if not v:
        return float("nan")
    s = sorted(v)
    return s[min(len(s) - 1, int(p * len(s)))]


def boot(a, b, stat=statistics.median, n=10000):
    if len(a) < 3 or len(b) < 3:
        return None
    d = []
    for _ in range(n):
        d.append(stat([random.choice(b) for _ in b]) - stat([random.choice(a) for _ in a]))
    d.sort()
    return {
        "mean": stat(b) - stat(a),
        "lo": d[int(0.025 * n)],
        "hi": d[int(0.975 * n)],
        "p_gt0": sum(1 for x in d if x > 0) / n,
    }


def ci(c):
    if not c:
        return "n/a"
    star = " *" if (c["lo"] > 0 or c["hi"] < 0) else ""
    return f"{c['mean']:+8.0f} [{c['lo']:+7.0f}, {c['hi']:+7.0f}] p(>0)={c['p_gt0']:.3f}{star}"


data = json.loads(open(PATH, encoding="utf-8").read())
rows = [r for r in data["rows"] if r.get("ttft_ms")]
print(f"file: {PATH}")
print(f"usable rows: {len(rows)} of {len(data['rows'])}")

arms = []
seeen = set()
for r in data["rows"]:
    if r["arm"] not in seeen:
        seeen.add(r["arm"])
        arms.append(r["arm"])

# Report in the intended, meaningful order rather than encounter/alphabetical order.
PREFERRED = ["A_myagent_thinking_max", "B_dsh_no_thinking_field",
             "C_thinking_high", "D_thinking_disabled"]
arms = [a for a in PREFERRED if a in seeen] + [a for a in arms if a not in PREFERRED]

by = {a: [r for r in rows if r["arm"] == a] for a in arms}

print("\n=== per arm (medians) ===")
print(f"  {'arm':26s} {'n':>3s} {'ttft':>7s} {'total':>7s} {'reason ch':>10s} {'out tok':>8s} {'tps':>7s}")
for a in arms:
    v = by[a]
    print(f"  {a:26s} {len(v):3d} {median([r['ttft_ms'] for r in v]):7.0f} "
          f"{median([r['total_ms'] for r in v]):7.0f} "
          f"{median([r['reasoning_chars'] for r in v]):10.0f} "
          f"{median([r['out_tokens'] for r in v if r.get('out_tokens')]):8.0f} "
          f"{median([r['tps'] for r in v if r.get('tps')]):7.1f}")

A = "A_myagent_thinking_max" if "A_myagent_thinking_max" in by else arms[0]
print(f"\n=== vs {A} (MyAgent's actual profile params) ===")
print("  time to first token (ms, positive = slower than A):")
for a in arms:
    if a == A:
        continue
    print(f"    {a:26s} {ci(boot([r['ttft_ms'] for r in by[A]], [r['ttft_ms'] for r in by[a]]))}")
print("  TOTAL request time (ms, positive = slower than A):")
for a in arms:
    if a == A:
        continue
    print(f"    {a:26s} {ci(boot([r['total_ms'] for r in by[A]], [r['total_ms'] for r in by[a]]))}")
print("  reasoning characters (positive = A thought more than the other arm):")
for a in arms:
    if a == A:
        continue
    print(f"    {a:26s} {ci(boot([r['reasoning_chars'] for r in by[A]], [r['reasoning_chars'] for r in by[a]]))}")
print("  output tokens (positive = A emitted more):")
for a in arms:
    if a == A:
        continue
    print(f"    {a:26s} {ci(boot([r['out_tokens'] for r in by[A] if r.get('out_tokens')], [r['out_tokens'] for r in by[a] if r.get('out_tokens')]))}")
print("\n  (* marks a CI that excludes zero)")

print("\n=== is the effect monotonic in effort? (strongest evidence at this n) ===")
order = [a for a in ("A_myagent_thinking_max", "C_thinking_high",
                     "B_dsh_no_thinking_field", "D_thinking_disabled") if a in by]
if len(order) >= 3:
    print(f"  {'arm (effort order)':30s} {'reason ch':>10s} {'out tok':>8s} {'total ms':>9s}")
    for a in order:
        v = by[a]
        print(f"  {a:30s} {median([r['reasoning_chars'] for r in v]):10.0f} "
              f"{median([r['out_tokens'] for r in v if r.get('out_tokens')]):8.0f} "
              f"{median([r['total_ms'] for r in v]):9.0f}")
    rc = [median([r["reasoning_chars"] for r in by[a]]) for a in order]
    tt = [median([r["total_ms"] for r in by[a]]) for a in order]
    mono_r = all(x >= y for x, y in zip(rc, rc[1:]))
    mono_t = all(x >= y for x, y in zip(tt, tt[1:]))
    print(f"\n  reasoning chars monotonic decreasing with effort: {mono_r}")
    print(f"  total time     monotonic decreasing with effort: {mono_t}")

print("\n=== per-token speed, to separate 'more work' from 'slower tokens' ===")
for a in arms:
    v = [r["tps"] for r in by[a] if r.get("tps")]
    print(f"  {a:26s} tok/s median {median(v):6.1f}  p25 {pick(v, 0.25):6.1f}  p75 {pick(v, 0.75):6.1f}")

print("\n=== reading ===")
print("  If total time falls monotonically with lower effort while tok/s stays flat, the")
print("  harness is not being served slower -- it is asking for more thinking, and thinking")
print("  costs wall time. That makes reasoning_effort a client-side performance dial.")
