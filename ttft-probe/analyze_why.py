"""Why is first-token latency different for the same model? Characterise the gap.

Three questions answered from existing records only (no API calls):
  1. Is the gap a constant offset or proportional to context? (regression + fine bins)
  2. Within MyAgent, is the gap server-side or client-side? (already known: server-side)
  3. MyAgent sent 61 tools for 771 of 778 requests but 35 tools for 7 -- are those 7
     faster at matched context size? That is the only free within-MyAgent evidence
     for the tool-weight hypothesis.

Usage: python ttft-probe/analyze_why.py
"""
from __future__ import annotations

import glob
import json
import math
import os
import statistics
import sys
from collections import defaultdict

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
WORKSPACE = r"D:\AI\AI Agent\MyAgent Developer"
SESSIONS = os.path.join(WORKSPACE, "workspace", "sessions")
MODEL = "deepseek/deepseek-v4.1-flash"


def median(v):
    return statistics.median(v) if v else float("nan")


def ols(xs, ys):
    """Least squares y = a + b x, plus R^2."""
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    b = sxy / sxx if sxx else 0.0
    a = my - b * mx
    ss_tot = sum((y - my) ** 2 for y in ys)
    ss_res = sum((y - (a + b * x)) ** 2 for x, y in zip(xs, ys))
    return a, b, (1 - ss_res / ss_tot if ss_tot else 0.0)


def myagent_rows():
    out = []
    for path in glob.glob(os.path.join(SESSIONS, "*", "execution_metrics.json")):
        try:
            data = json.loads(open(path, encoding="utf-8").read())
        except Exception:
            continue
        for run in data.get("runs", []):
            for req in run.get("requests", []):
                usage = req.get("usage") or {}
                model = req.get("model") or usage.get("model")
                if model != MODEL or req.get("first_token_ms") is None:
                    continue
                prompt = usage.get("prompt_tokens")
                if not prompt:
                    continue
                events = ((req.get("phases") or {}).get("llm_stream") or {}).get("events") or []
                steps = {str(e.get("step")): e.get("ms_since_api_start") for e in events}
                out.append({
                    "session": run.get("session_id") or os.path.basename(os.path.dirname(path)),
                    "started": req.get("started_at"),
                    "ttft": req["first_token_ms"],
                    "prompt": prompt,
                    "hit": usage.get("prompt_cache_hit_tokens"),
                    "tools": (req.get("context") or {}).get("tools"),
                    "messages": (req.get("context") or {}).get("messages"),
                    "stream_created": steps.get("stream_created"),
                })
    return out


def dsh_rows():
    data = json.loads(open(os.path.join(HERE, "ttft_stats.json"), encoding="utf-8").read())
    out = []
    for r in data["rows"]:
        if r.get("ttftMs") is None or r.get("retries") or not r.get("promptTokens"):
            continue
        out.append({
            "session": r["sessionId"],
            "depth": r.get("depth") or 0,
            "ttft": r["ttftMs"],
            "prompt": r["promptTokens"],
            "tools": 27,
        })
    return out


def main():
    ma = myagent_rows()
    ds = dsh_rows()
    print(f"MyAgent rows: {len(ma)}   DSH rows: {len(ds)}")

    print("\n=== 1. Is the gap a constant offset or proportional to context? ===")
    print("OLS: ttft_ms = a + b * prompt_tokens")
    for label, rows in (("MyAgent", ma), ("DSH    ", ds)):
        xs = [r["prompt"] for r in rows]
        ys = [r["ttft"] for r in rows]
        a, b, r2 = ols(xs, ys)
        print(f"  {label}: intercept a = {a:8.0f} ms   slope b = {b * 1000:6.3f} ms per 1k tok   R2 = {r2:.3f}")

    print("\n  implied gap decomposition (DSH - MyAgent):")
    ax, bx, _ = ols([r["prompt"] for r in ma], [r["ttft"] for r in ma])
    ay, by, _ = ols([r["prompt"] for r in ds], [r["ttft"] for r in ds])
    print(f"    constant part (intercept difference) = {ay - ax:+8.0f} ms")
    print(f"    proportional part at 120k tokens     = {((by - bx) * 120_000):+8.0f} ms")
    print(f"    total at 120k tokens                 = {(ay - ax) + (by - bx) * 120_000:+8.0f} ms")

    print("\n=== 2. Matched-context bins (20k wide) ===")
    print(f"  {'prompt bin':>14s} {'DSH n':>6s} {'DSH med':>8s} {'MA n':>6s} {'MA med':>8s} {'gap':>8s}")
    lo = 0
    while lo < 300_000:
        hi = lo + 20_000
        d = [r["ttft"] for r in ds if lo <= r["prompt"] < hi]
        m = [r["ttft"] for r in ma if lo <= r["prompt"] < hi]
        if len(d) >= 8 and len(m) >= 8:
            print(f"  {lo // 1000:5d}k-{hi // 1000:3d}k {len(d):6d} {median(d):8.0f} "
                  f"{len(m):6d} {median(m):8.0f} {median(m) - median(d):+8.0f}")
        lo = hi

    print("\n=== 3. Within MyAgent: the 35-tool requests vs the 61-tool requests ===")
    by_tools = defaultdict(list)
    for r in ma:
        by_tools[r["tools"]].append(r)
    for tools in sorted(t for t in by_tools if t):
        v = by_tools[tools]
        print(f"\n  tools={tools}: n={len(v)}  prompt median={median([r['prompt'] for r in v]):.0f}")
        for r in sorted(v, key=lambda r: r["prompt"])[:12]:
            print(f"    {r['started']}  ttft={r['ttft']:6.0f} ms  prompt={r['prompt']:7d}  "
                  f"sess={r['session'][:12]}")
    if 35 in by_tools and 61 in by_tools:
        low = [r for r in by_tools[35]]
        low_lo = min(r["prompt"] for r in low)
        low_hi = max(r["prompt"] for r in low)
        band = [r for r in by_tools[61] if low_lo <= r["prompt"] <= low_hi]
        print(f"\n  matched band {low_lo}-{low_hi} tokens:")
        print(f"    tools=35 : n={len(low):3d} ttft median={median([r['ttft'] for r in low]):7.0f} ms")
        print(f"    tools=61 : n={len(band):3d} ttft median={median([r['ttft'] for r in band]):7.0f} ms")
        if band:
            print(f"    delta (61 - 35) = {median([r['ttft'] for r in band]) - median([r['ttft'] for r in low]):+.0f} ms")

    print("\n=== 4. Client-side share of MyAgent TTFT (from the timeline) ===")
    sc = [r["stream_created"] for r in ma if r["stream_created"] is not None]
    tt = [r["ttft"] for r in ma if r["stream_created"] is not None]
    print(f"  stream_created median = {median(sc):.0f} ms of a {median(tt):.0f} ms TTFT "
          f"({median(sc) / median(tt) * 100:.2f}%)")
    print("  -> MyAgent's own request build + connect + headers is not the gap.")


if __name__ == "__main__":
    main()
