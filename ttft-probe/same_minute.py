"""Tightest observational control: compare the two harnesses within the same minutes.

If both harnesses issue requests in the same wall-clock minutes, upstream load, gateway
state and backend pool conditions are as close to identical as observation allows. This
prints every 5-minute window where both sides have samples, so the gap can be read off
under matched conditions rather than across different hours of the day.

Usage: python ttft-probe/same_minute.py [window_minutes]
"""
from __future__ import annotations

import glob
import json
import os
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone, timedelta

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
SESSIONS = r"D:\AI\AI Agent\MyAgent Developer\workspace\sessions"
MODEL = "deepseek/deepseek-v4.1-flash"
TZ = timezone(timedelta(hours=8))
WIN = int(sys.argv[1]) if len(sys.argv) > 1 else 5


def med(v):
    return statistics.median(v) if v else float("nan")


def key5(ms):
    dt = datetime.fromtimestamp(ms / 1000, TZ)
    return dt.strftime("%m-%d %H:") + f"{(dt.minute // WIN) * WIN:02d}"


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
            try:
                start = datetime.fromisoformat(q["started_at"].replace("Z", "+00:00"))
            except Exception:
                continue
            ma.append({
                "ms": start.timestamp() * 1000,
                "ttft": q["first_token_ms"],
                "pt": u.get("prompt_tokens"),
                "sid": (run.get("session_id") or os.path.basename(os.path.dirname(p)))[:10],
            })

dsj = json.load(open(os.path.join(HERE, "ttft_stats.json"), encoding="utf-8"))
ds = []
for r in dsj["rows"]:
    if r.get("ttftMs") is None or r.get("retries"):
        continue
    ds.append({"ms": r["startTime"], "ttft": r["ttftMs"],
               "pt": r.get("promptTokens"), "sid": r["sessionId"][:10]})

buckets = defaultdict(lambda: {"ma": [], "ds": []})
for r in ma:
    buckets[key5(r["ms"])]["ma"].append(r)
for r in ds:
    buckets[key5(r["ms"])]["ds"].append(r)

shared = sorted(k for k, v in buckets.items() if v["ma"] and v["ds"])
print(f"{WIN}-minute windows where BOTH harnesses issued requests: {len(shared)}")
print(f"(MyAgent total {len(ma)} samples, DSH total {len(ds)} samples)\n")
print(f"  {'window':14s} {'MA n':>5s} {'MA ttft':>8s} {'MA ctx':>8s} "
      f"{'DSH n':>6s} {'DSH ttft':>9s} {'DSH ctx':>8s} {'gap':>8s}")

rows = []
for k in shared:
    a, b = buckets[k]["ma"], buckets[k]["ds"]
    gap = med([r["ttft"] for r in b]) - med([r["ttft"] for r in a])
    rows.append(gap)
    print(f"  {k:14s} {len(a):5d} {med([r['ttft'] for r in a]):8.0f} "
          f"{med([r['pt'] for r in a if r['pt']]):8.0f} {len(b):6d} "
          f"{med([r['ttft'] for r in b]):9.0f} {med([r['pt'] for r in b if r['pt']]):8.0f} "
          f"{gap:+8.0f}")

if rows:
    print(f"\n  across {len(rows)} shared windows: median gap {med(rows):+.0f} ms, "
          f"mean {statistics.mean(rows):+.0f} ms")
    print(f"  DSH faster in {sum(1 for g in rows if g < 0)}/{len(rows)} windows")
    weights = [min(len(buckets[k]['ma']), len(buckets[k]['ds'])) for k in shared]
    wsum = sum(weights)
    if wsum:
        print(f"  sample-weighted mean gap "
              f"{sum(g * w for g, w in zip(rows, weights)) / wsum:+.0f} ms")
