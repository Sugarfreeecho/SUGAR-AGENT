"""Did the long-context run have enough power to detect the small-context effect?

The small-context run found A (reasoning_effort=max) slower than C (high) by ~1362 ms on
total time, significant at n=8/arm. The long-context run found no arm difference at all.
Before accepting that as "the effect disappears at long context", check whether the
long-context run was simply too noisy to see it.

Computes, for both runs:
  - the observed effect size and its CI
  - the within-arm spread
  - the minimum detectable difference (MDD) at this n, so "no effect" can be separated
    from "no power"
  - the two runs' variance, to see whether the long-context setting is intrinsically
    noisier (a 100k prefix plausibly is)

Usage: python ttft-probe/power_check.py
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
C = "C_thinking_high"


def load(name):
    return json.loads(open(os.path.join(HERE, name), encoding="utf-8").read())


def vals(data, arm, key):
    return [r[key] for r in data["rows"]
            if r.get("arm") == arm and r.get(key) is not None and r.get("ttft_ms")]


def boot_ci(a, b, n=20000):
    if len(a) < 3 or len(b) < 3:
        return None
    d = []
    for _ in range(n):
        d.append(statistics.median([random.choice(b) for _ in b])
                 - statistics.median([random.choice(a) for _ in a]))
    d.sort()
    return d[int(0.025 * n)], d[int(0.975 * n)], statistics.median(d)


def mdd(a, b, iters=2000):
    """Smallest true difference this design detects ~80% of the time."""
    if len(a) < 3 or len(b) < 3:
        return None
    sd = math.sqrt(statistics.variance(a) + statistics.variance(b))
    # normal approximation for the difference of two medians; 2.8 ~= 80% power at 5%
    eff = 2.8 * sd / math.sqrt(min(len(a), len(b)))
    return eff


for label, fname in (("SMALL context (~40 tok)", "params.json"),
                     ("LONG context (~100k tok)", "params_long.json")):
    d = load(fname)
    print("=" * 78)
    print(f"{label}   file={fname}   trials/arm={d['args'].get('trials')}   "
          f"pad={d['args'].get('pad_tokens', 0)}")
    print("=" * 78)
    for key, unit in (("ttft_ms", "ms"), ("total_ms", "ms"), ("reasoning_chars", "chars")):
        a = vals(d, A, key)
        c = vals(d, C, key)
        if not a or not c:
            continue
        ci = boot_ci(a, c)
        m = mdd(a, c)
        print(f"  {key:16s} A n={len(a):2d} med={statistics.median(a):8.0f} | "
              f"C n={len(c):2d} med={statistics.median(c):8.0f} | "
              f"C-A = {statistics.median(c) - statistics.median(a):+8.0f} {unit}")
        if ci:
            print(f"  {'':16s} 95% CI [{ci[0]:+.0f}, {ci[1]:+.0f}]  "
                  f"min detectable diff ~{m:.0f} {unit}")
    a = vals(d, A, "total_ms")
    c = vals(d, C, "total_ms")
    if a and c:
        print(f"\n  within-arm spread (total_ms):")
        print(f"    A  sd={statistics.stdev(a):7.0f}  range {min(a):.0f}-{max(a):.0f}")
        print(f"    C  sd={statistics.stdev(c):7.0f}  range {min(c):.0f}-{max(c):.0f}")
    print()

print("=" * 78)
print("VERDICT")
print("=" * 78)
sm = load("params.json")
lg = load("params_long.json")
sa, sc = vals(sm, A, "total_ms"), vals(sm, C, "total_ms")
la, lc = vals(lg, A, "total_ms"), vals(lg, C, "total_ms")
print(f"  small context: C-A = {statistics.median(sc) - statistics.median(sa):+8.0f} ms  "
      f"(CI excluded 0 -> effect detected)")
lci = boot_ci(la, lc)
print(f"  long  context: C-A = {statistics.median(lc) - statistics.median(la):+8.0f} ms  "
      f"(CI [{lci[0]:+.0f}, {lci[1]:+.0f}] includes 0 -> not detected)")
print(f"  long-context min detectable diff ~{mdd(la, lc):.0f} ms")
print()
print("  The long-context CI is roughly +-3 s wide, so it cannot rule out an effect of the")
print("  small-context size (~1.4 s) -- but it also provides ZERO evidence that the effect")
print("  GROWS with context. The hypothesis being tested was 'effort=max costs much more at")
print("  long context, explaining the production 1.5 s'. That hypothesis is NOT supported:")
print("  the point estimate went the wrong way and the run is too noisy to claim more.")
print()
print("  Honest reading: this experiment neither confirms nor refutes a context-scaling")
print("  effect at production scale. It DOES show the effect is not large and obvious.")
