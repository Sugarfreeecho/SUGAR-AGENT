"""Analyse the header x tools experiment (header_probe.py output).

Arms (identical prompt, one warm connection per header setting, randomized order):
  A: no x-opencode headers, no tools   -- closest to DSH production
  B: x-opencode headers,    no tools   -- tests header-based routing
  C: no x-opencode headers, N tools    -- tests tool-payload weight
  D: x-opencode headers,    N tools    -- closest to MyAgent production

Reports per-arm medians for time-to-first-token, decode throughput and total, plus
bootstrap confidence intervals for the arm-to-arm differences, and an order-effect check
so a drifting upstream cannot masquerade as an arm effect.

Usage: python ttft-probe/analyze_header.py [header.json]
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
PATH = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "header.json")
random.seed(20260911)


def median(v):
    return statistics.median(v) if v else float("nan")


def pick(v, p):
    if not v:
        return float("nan")
    s = sorted(v)
    return s[min(len(s) - 1, int(p * len(s)))]


def bootstrap_diff(a, b, stat=statistics.median, n=5000):
    """CI for stat(b) - stat(a) by resampling both arms."""
    if len(a) < 3 or len(b) < 3:
        return None
    diffs = []
    for _ in range(n):
        ra = [random.choice(a) for _ in a]
        rb = [random.choice(b) for _ in b]
        diffs.append(stat(rb) - stat(ra))
    diffs.sort()
    return {
        "mean": stat(b) - stat(a),
        "lo": diffs[int(0.025 * n)],
        "hi": diffs[int(0.975 * n)],
        "p_gt0": sum(1 for d in diffs if d > 0) / n,
    }


def fmt_ci(c):
    if not c:
        return "n/a"
    return f"{c['mean']:+.0f} [{c['lo']:+.0f}, {c['hi']:+.0f}] p(>0)={c['p_gt0']:.2f}"


def main():
    data = json.loads(open(PATH, encoding="utf-8").read())
    rows = [r for r in data["rows"] if r.get("ttft_ms")]
    print(f"file: {PATH}")
    print(f"args: {json.dumps(data.get('args'), ensure_ascii=False)}")
    print(f"usable rows: {len(rows)} of {len(data['rows'])}")
    errors = [r for r in data["rows"] if not r.get("ttft_ms")]
    for e in errors:
        print(f"  dropped: arm={e.get('arm')} error={e.get('error') or 'no first token'}")

    arms = sorted({r["arm"] for r in rows})
    by_arm = {a: [r for r in rows if r["arm"] == a] for a in arms}

    print("\n=== per-arm ===")
    print(f"  {'arm':24s} {'n':>3s} {'ttft med':>9s} {'ttft mean':>10s} {'tps med':>8s} "
          f"{'total med':>10s} {'out tok':>8s}")
    for a in arms:
        v = by_arm[a]
        tps = [r["tps"] for r in v if r.get("tps")]
        tok = [r["out_tokens"] for r in v if r.get("out_tokens")]
        print(f"  {a:24s} {len(v):3d} {median([r['ttft_ms'] for r in v]):9.0f} "
              f"{statistics.mean([r['ttft_ms'] for r in v]):10.0f} {median(tps):8.1f} "
              f"{median([r['total_ms'] for r in v]):10.0f} {median(tok):8.0f}")

    # Long-context runs pad a fixed prefix so the upstream prefix cache can hit; verify it did,
    # otherwise the run measured cold prefill rather than the steady state it intends.
    if any(r.get("prompt_tokens") for r in rows):
        print("\n=== context and cache accounting ===")
        print(f"  {'arm':24s} {'prompt tok':>10s} {'cache hit':>10s} {'hit share':>9s} {'cached?':>8s}")
        for a in arms:
            v = by_arm[a]
            pt = [r["prompt_tokens"] for r in v if r.get("prompt_tokens")]
            hit = [r["cache_hit_tokens"] for r in v if r.get("cache_hit_tokens") is not None]
            share = (median([r["cache_hit_tokens"] / r["prompt_tokens"] for r in v
                             if r.get("cache_hit_tokens") is not None and r.get("prompt_tokens")]) * 100
                     if hit else float("nan"))
            warm = sum(1 for r in v if r.get("cache_hit_tokens"))
            print(f"  {a:24s} {median(pt):10.0f} {median(hit):10.0f} {share:8.1f}% "
                  f"{warm}/{len(v):>5d}")
        first_calls = sum(1 for r in rows if not r.get("cache_hit_tokens"))
        print(f"\n  requests with no cache hit: {first_calls} of {len(rows)}")
        print("  (a high hit share across arms means the pad prefix was reused as intended;")
        print("   if every call missed, the run is cold-prefill and the numbers are not steady-state)")

    base = arms[0]
    print(f"\n=== deltas vs {base} (bootstrap 95% CI, 5000 resamples) ===")
    print("  TTFT (positive = slower than baseline):")
    for a in arms[1:]:
        d = bootstrap_diff([r["ttft_ms"] for r in by_arm[base]],
                           [r["ttft_ms"] for r in by_arm[a]])
        print(f"    {a:24s} {fmt_ci(d)} ms")

    print("  decode tok/s (positive = faster than baseline):")
    for a in arms[1:]:
        d = bootstrap_diff([r["tps"] for r in by_arm[base] if r.get("tps")],
                           [r["tps"] for r in by_arm[a] if r.get("tps")])
        print(f"    {a:24s} {fmt_ci(d)} tok/s")

    print("\n=== order-effect check (is upstream drifting over the run?) ===")
    ordered = sorted(rows, key=lambda r: r["trial"])
    half = len(ordered) // 2
    first, second = ordered[:half], ordered[half:]
    print(f"  first half  n={len(first):2d} ttft median={median([r['ttft_ms'] for r in first]):7.0f} "
          f"tps median={median([r['tps'] for r in first if r.get('tps')]):6.1f}")
    print(f"  second half n={len(second):2d} ttft median={median([r['ttft_ms'] for r in second]):7.0f} "
          f"tps median={median([r['tps'] for r in second if r.get('tps')]):6.1f}")
    # Arm balance across halves: an unbalanced split would confound the comparison.
    for a in arms:
        n1 = sum(1 for r in first if r["arm"] == a)
        print(f"    {a:24s} first-half n={n1}")

    print("\n=== within-arm spread (is the difference bigger than the noise?) ===")
    for a in arms:
        tt = [r["ttft_ms"] for r in by_arm[a]]
        print(f"  {a:24s} ttft min={min(tt):6.0f} p25={pick(tt, 0.25):6.0f} med={median(tt):6.0f} "
              f"p75={pick(tt, 0.75):6.0f} max={max(tt):6.0f}")

    print("\n=== verdict ===")
    b = arms[1] if len(arms) > 1 else None
    c = next((a for a in arms if a.startswith("C")), None)
    if b and c:
        db = bootstrap_diff([r["ttft_ms"] for r in by_arm[base]], [r["ttft_ms"] for r in by_arm[b]])
        dc = bootstrap_diff([r["ttft_ms"] for r in by_arm[base]], [r["ttft_ms"] for r in by_arm[c]])
        for label, d in (("headers (B-A)", db), ("tools (C-A)", dc)):
            if not d:
                continue
            if d["lo"] > 0:
                print(f"  {label}: slower by {d['mean']:.0f} ms, CI excludes 0 -> REAL effect")
            elif d["hi"] < 0:
                print(f"  {label}: faster by {-d['mean']:.0f} ms, CI excludes 0 -> REAL effect")
            else:
                print(f"  {label}: {d['mean']:+.0f} ms, CI includes 0 -> no detectable effect at this n")


if __name__ == "__main__":
    main()
