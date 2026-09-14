"""Was MyAgent serving more concurrent LLM requests than DSH?

Upstream queueing is a mechanism that would produce a real server-side gap with the
same model, endpoint and credential, and it is invisible in per-request records. Both
harnesses log enough to rebuild in-flight intervals:
  MyAgent: started_at .. started_at+duration_ms  (and .. first_token)
  DSH:     step/start .. assistant/message       (and .. first token)
This counts, at each request's own TTFT window, how many other LLM calls were already
in flight, and reports the distribution for each side.

Usage: python ttft-probe/concurrency_check.py
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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

HERE = os.path.dirname(os.path.abspath(__file__))
WORKSPACE = r"D:\AI\AI Agent\MyAgent Developer"
SESSIONS = os.path.join(WORKSPACE, "workspace", "sessions")
MODEL = "deepseek/deepseek-v4.1-flash"
LOCAL_TZ = timezone(timedelta(hours=8))
SESSIONS_ROOT = os.path.join(
    os.environ.get("USERPROFILE", ""), ".dsh", "sessions",
    "--D-AI-AI~0020Agent-MyAgent~0020Developer--",
)


def median(v):
    return statistics.median(v) if v else float("nan")


def parse_dt(v):
    if not v:
        return None
    try:
        return datetime.fromisoformat(v.replace("Z", "+00:00")).timestamp() * 1000
    except Exception:
        return None


def myagent_intervals():
    out = []
    for path in glob.glob(os.path.join(SESSIONS, "*", "execution_metrics.json")):
        try:
            data = json.loads(open(path, encoding="utf-8").read())
        except Exception:
            continue
        for run in data.get("runs", []):
            for req in run.get("requests", []):
                model = req.get("model") or (req.get("usage") or {}).get("model")
                if model != MODEL or req.get("first_token_ms") is None:
                    continue
                start = parse_dt(req.get("started_at"))
                if start is None:
                    continue
                ttft = req["first_token_ms"]
                dur = req.get("duration_ms") or ttft
                out.append({
                    "start": start,
                    "ttft_end": start + ttft,
                    "gen_end": start + dur,
                    "ttft": ttft,
                })
    return out


def dsh_intervals():
    """DSH intervals come from ttft_stats.json, which already carries the boundaries."""
    data = json.loads(open(os.path.join(HERE, "ttft_stats.json"), encoding="utf-8").read())
    out = []
    for r in data["rows"]:
        if r.get("ttftMs") is None:
            continue
        start = r["startTime"]
        out.append({
            "start": start,
            "ttft_end": r.get("firstTokenTime") or start + r["ttftMs"],
            "gen_end": r.get("endTime") or start + (r.get("llmMs") or r["ttftMs"]),
            "ttft": r["ttftMs"],
        })
    return out


def concurrency(intervals, key):
    """For each interval, how many OTHER intervals are in flight when it starts."""
    starts = sorted(i["start"] for i in intervals)
    counts = []
    for iv in intervals:
        # in flight when this request begins = started before, still running
        n = sum(1 for other in intervals
                if other is not iv and other["start"] < iv["start"] <= other[key])
        counts.append(n)
    return counts


def report(label, intervals):
    if not intervals:
        print(f"{label}: no intervals")
        return
    ttft_c = concurrency(intervals, "ttft_end")
    gen_c = concurrency(intervals, "gen_end")
    print(f"\n--- {label} (n={len(intervals)}) ---")
    print(f"  concurrency during the TTFT window : mean {statistics.mean(ttft_c):.2f} "
          f"median {median(ttft_c):.0f} max {max(ttft_c)}")
    print(f"  concurrency during full generation  : mean {statistics.mean(gen_c):.2f} "
          f"median {median(gen_c):.0f} max {max(gen_c)}")
    dist = {}
    for c in ttft_c:
        dist[c] = dist.get(c, 0) + 1
    total = len(ttft_c)
    print("  share by in-flight count at TTFT start:")
    for k in sorted(dist):
        print(f"    {k} other request(s): {dist[k]:5d}  {dist[k] / total * 100:5.1f}%")

    # TTFT as a function of concurrency
    print(f"  {'others in flight':>18s} {'n':>5s} {'ttft median':>12s}")
    buckets = {}
    for iv, c in zip(intervals, ttft_c):
        if iv["ttft"] is None:
            continue
        buckets.setdefault(min(c, 4), []).append(iv["ttft"])
    for k in sorted(buckets):
        label_k = f"{k}+" if k == 4 else str(k)
        print(f"  {label_k:>18s} {len(buckets[k]):5d} {median(buckets[k]):12.0f}")


def main():
    ma = myagent_intervals()
    ds = dsh_intervals()
    print(f"MyAgent intervals: {len(ma)}   DSH intervals: {len(ds)}")
    report("MyAgent", ma)
    report("DSH", ds)

    print("\n=== overlap in wall-clock time ===")
    for label, iv in (("MyAgent", ma), ("DSH", ds)):
        if not iv:
            continue
        lo = min(i["start"] for i in iv)
        hi = max(i["gen_end"] for i in iv)
        print(f"  {label}: {datetime.fromtimestamp(lo / 1000, LOCAL_TZ):%m-%d %H:%M} .. "
              f"{datetime.fromtimestamp(hi / 1000, LOCAL_TZ):%m-%d %H:%M}")


if __name__ == "__main__":
    main()
