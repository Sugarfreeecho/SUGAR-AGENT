"""Uncached prefill at matched context: the last plausible mechanism.

TTFT grows with TOTAL prompt tokens but (measured earlier) not with UNCACHED tokens,
which is odd if prefill compute were the cause. This checks the uncached remainder at
matched context between the two harnesses on the same day.

Usage: python ttft-probe/uncached_matched.py
"""
from __future__ import annotations

import glob
import json
import os
import statistics
import sys
from datetime import datetime, timezone, timedelta

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
SESSIONS = r"D:\AI\AI Agent\MyAgent Developer\workspace\sessions"
MODEL = "deepseek/deepseek-v4.1-flash"
TZ = timezone(timedelta(hours=8))
DAY = "2026-09-11"


def med(v):
    return statistics.median(v) if v else float("nan")


ma = []
for p in glob.glob(os.path.join(SESSIONS, "*", "execution_metrics.json")):
    try:
        d = json.load(open(p, encoding="utf-8"))
    except Exception:
        continue
    for run in d.get("runs", []):
        for q in run.get("requests", []):
            u = q.get("usage") or {}
            if (q.get("model") or u.get("model")) != MODEL or not q.get("first_token_ms"):
                continue
            pt, hit = u.get("prompt_tokens"), u.get("prompt_cache_hit_tokens")
            if not pt or hit is None:
                continue
            day = None
            try:
                day = datetime.fromisoformat(q["started_at"].replace("Z", "+00:00")) \
                    .astimezone(TZ).strftime("%Y-%m-%d")
            except Exception:
                pass
            ma.append(dict(day=day, ttft=q["first_token_ms"], pt=pt, miss=pt - hit))

dsj = json.load(open(os.path.join(HERE, "ttft_stats.json"), encoding="utf-8"))
ds = []
for r in dsj["rows"]:
    if r.get("ttftMs") is None or r.get("retries"):
        continue
    pt, hit = r.get("promptTokens"), r.get("cacheReadTokens")
    if not pt or hit is None:
        continue
    ds.append(dict(ttft=r["ttftMs"], pt=pt, miss=pt - hit))

ma11 = [r for r in ma if r["day"] == DAY]
print(f"same-day samples: MyAgent {len(ma11)}, DSH {len(ds)}")
print("\nmatched-context UNCACHED tokens and TTFT")
print(f"  {'prompt bin':>14s} {'DSH n':>6s} {'DSH miss':>9s} {'DSH ttft':>9s} "
      f"{'MA n':>6s} {'MA miss':>9s} {'MA ttft':>9s}")
lo = 0
while lo < 300_000:
    hi = lo + 40_000
    a = [r for r in ds if lo <= r["pt"] < hi]
    b = [r for r in ma11 if lo <= r["pt"] < hi]
    if len(a) >= 8 and len(b) >= 8:
        print(f"  {lo // 1000:5d}k-{hi // 1000:3d}k {len(a):6d} {med([r['miss'] for r in a]):9.0f} "
              f"{med([r['ttft'] for r in a]):9.0f} {len(b):6d} {med([r['miss'] for r in b]):9.0f} "
              f"{med([r['ttft'] for r in b]):9.0f}")
    lo = hi

print("\nmedian cache-hit share:")
for label, rows in (("MyAgent 9/11", ma11), ("DSH 9/11", ds)):
    share = [1 - r["miss"] / r["pt"] for r in rows if r["pt"]]
    print(f"  {label:14s} {med(share) * 100:5.2f}%")
