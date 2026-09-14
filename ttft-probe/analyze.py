"""Analyze TTFT probe results: per-arm distributions, paired CIs, order effects.

Usage: python analyze.py main.json [more.json ...]
"""
from __future__ import annotations

import json
import math
import random
import statistics
import sys

# two-sided 95% t critical values, df 1..30
T95 = [12.706, 4.303, 3.182, 2.776, 2.571, 2.447, 2.365, 2.306, 2.262, 2.228,
       2.201, 2.179, 2.160, 2.145, 2.131, 2.120, 2.110, 2.101, 2.093, 2.086,
       2.080, 2.074, 2.069, 2.064, 2.060, 2.056, 2.052, 2.048, 2.045, 2.042]


def t95(df: int) -> float:
    if df <= 0:
        return float("nan")
    return T95[df - 1] if df <= 30 else 1.96


def pct(values, q):
    if not values:
        return float("nan")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = q * (len(ordered) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(ordered) - 1)
    return ordered[lo] * (1 - (pos - lo)) + ordered[hi] * (pos - lo)


def describe(vals: list[float]) -> dict:
    return {
        "n": len(vals),
        "min": min(vals),
        "p25": pct(vals, 0.25),
        "median": statistics.median(vals),
        "p75": pct(vals, 0.75),
        "max": max(vals),
        "mean": statistics.mean(vals),
        "sd": statistics.stdev(vals) if len(vals) > 1 else 0.0,
    }


def arm_table(rows, key, arms):
    print(f"\n--- {key} ---")
    hdr = f"{'arm':<16}{'n':>4}{'min':>8}{'p25':>8}{'med':>8}{'p75':>8}{'max':>8}{'mean':>8}{'sd':>8}"
    print(hdr)
    print("-" * len(hdr))
    for arm in arms:
        vals = [r[key] for r in rows if r["arm"] == arm and r.get("ok") and r.get(key) is not None]
        if not vals:
            print(f"{arm:<16}{0:>4}  (no data)")
            continue
        d = describe(vals)
        print(f"{arm:<16}{d['n']:>4}{d['min']:>8.0f}{d['p25']:>8.0f}{d['median']:>8.0f}"
              f"{d['p75']:>8.0f}{d['max']:>8.0f}{d['mean']:>8.0f}{d['sd']:>8.0f}")


def bootstrap_ci(diffs, iters=20000, alpha=0.05, seed=7):
    rng = random.Random(seed)
    n = len(diffs)
    means = []
    for _ in range(iters):
        means.append(statistics.mean(rng.choices(diffs, k=n)))
    means.sort()
    return means[int(alpha / 2 * iters)], means[int((1 - alpha / 2) * iters)]


def paired(rows, key, a, b, equiv_ms=150.0):
    by_trial: dict[int, dict[str, float]] = {}
    for row in rows:
        if row.get("ok") and row.get(key) is not None:
            by_trial.setdefault(row["trial"], {})[row["arm"]] = row[key]
    diffs = [p[a] - p[b] for p in by_trial.values() if a in p and b in p]
    label = f"{a} - {b}"
    if len(diffs) < 2:
        print(f"\n[{key}] {label}: insufficient pairs (n={len(diffs)})")
        return None
    n = len(diffs)
    mean = statistics.mean(diffs)
    sd = statistics.stdev(diffs)
    se = sd / math.sqrt(n)
    half = t95(n - 1) * se
    lo, hi = mean - half, mean + half
    blo, bhi = bootstrap_ci(diffs)
    wins = sum(1 for d in diffs if d < 0)
    ties = sum(1 for d in diffs if d == 0)
    print(f"\n[{key}] {label}")
    print(f"  n={n}  mean diff={mean:+.1f}ms  sd={sd:.1f}  se={se:.1f}")
    print(f"  95% CI (t)        = [{lo:+.1f}, {hi:+.1f}] ms")
    print(f"  95% CI (bootstrap)= [{blo:+.1f}, {bhi:+.1f}] ms")
    print(f"  {a} faster in {wins}/{n} pairs, ties {ties}")
    # minimum detectable difference at this n (80% power, two-sided .05)
    mdd = (t95(n - 1) + 0.84) * se
    print(f"  minimum detectable diff @80% power = {mdd:.0f}ms "
          f"(this run can only resolve effects larger than that)")
    if lo > -equiv_ms and hi < equiv_ms:
        print(f"  => CI inside \u00b1{equiv_ms:.0f}ms: equivalent for practical purposes")
    elif lo > 0 or hi < 0:
        print("  => CI excludes 0: a difference is supported")
    else:
        print("  => CI includes 0 and exceeds the equivalence band: inconclusive")
    return {"a": a, "b": b, "key": key, "n": n, "mean": mean, "sd": sd,
            "ci": [lo, hi], "mdd": mdd, "wins": wins}


def order_effect(rows, key):
    groups: dict[int, list[float]] = {}
    for row in rows:
        if row.get("ok") and row.get(key) is not None:
            groups.setdefault(row.get("order_pos", -1), []).append(row[key])
    if len(groups) < 2:
        return
    print(f"\n--- {key} by within-trial order position (checks cache/drift leakage) ---")
    for pos in sorted(groups):
        vals = groups[pos]
        print(f"  pos {pos}: n={len(vals):>3}  mean={statistics.mean(vals):>8.0f}ms  "
              f"median={statistics.median(vals):>8.0f}ms")


def main() -> int:
    paths = sys.argv[1:] or ["main.json"]
    all_rows = []
    arms = []
    trial_offset = 0
    for path in paths:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        print(f"# {path}  label={data.get('label','')!r}")
        local_max = 0
        for row in data["rows"]:
            # trials are only unique within a file; offset so pooled paired
            # analysis cannot join two different runs' same-numbered trials
            row["run"] = path
            row["trial"] = row["trial"] + trial_offset
            local_max = max(local_max, row["trial"])
            all_rows.append(row)
            if row["arm"] not in arms:
                arms.append(row["arm"])
        trial_offset = local_max + 1

    ok = [r for r in all_rows if r.get("ok")]
    print(f"\ntotal requests={len(all_rows)}  ok={len(ok)}  failed={len(all_rows) - len(ok)}")
    fails = [r for r in all_rows if not r.get("ok")]
    for row in fails:
        print(f"  FAIL t{row['trial']} {row['arm']}: {str(row.get('error'))[:160]}")

    kinds = {}
    for row in ok:
        kinds[(row["arm"], row.get("first_kind"))] = kinds.get((row["arm"], row.get("first_kind")), 0) + 1
    print("\nfirst-delta channel seen (must match across arms for a fair TTFT compare):")
    for (arm, kind), count in sorted(kinds.items()):
        print(f"  {arm:<16} {kind}: {count}")

    for key in ("ttft_ms", "t_headers_ms", "server_think_ms"):
        arm_table(ok, key, arms)

    print("\n================ paired comparisons ================")
    summary = []
    pairs = [("node:dsh", "py:myagent"), ("node:dsh", "node:myagent"),
             ("py:dsh", "py:myagent"), ("node:dshjson", "node:dsh"),
             ("node:dsh", "py:dsh"), ("node:myagent", "py:myagent")]
    for a, b in pairs:
        if a in arms and b in arms:
            for key in ("ttft_ms", "t_headers_ms"):
                res = paired(ok, key, a, b)
                if res:
                    summary.append(res)
    order_effect(ok, "ttft_ms")
    order_effect(ok, "t_headers_ms")
    return 0


if __name__ == "__main__":
    sys.exit(main())
