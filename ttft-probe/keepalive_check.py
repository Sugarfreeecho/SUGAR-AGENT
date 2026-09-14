"""Does the httpx 5s keep-alive expiry show up in production MyAgent sessions?

httpx's default `Limits(keepalive_expiry=5.0)` drops a pooled connection after five
idle seconds, so any request preceded by a longer gap pays a fresh TCP+TLS
handshake. Node's undici keeps connections far longer. If that mechanism is real,
MyAgent's first-token latency should jump for requests that follow a >5s idle gap.

Usage: python ttft-probe/keepalive_check.py
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

WORKSPACE = r"D:\AI\AI Agent\MyAgent Developer"
SESSIONS = os.path.join(WORKSPACE, "workspace", "sessions")
LOCAL_TZ = timezone(timedelta(hours=8))
MODEL = "deepseek/deepseek-v4.1-flash"


def parse(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def median(values):
    return statistics.median(values) if values else float("nan")


def main():
    rows = []
    for path in glob.glob(os.path.join(SESSIONS, "*", "execution_metrics.json")):
        try:
            data = json.loads(open(path, encoding="utf-8").read())
        except Exception:
            continue
        session_id = data.get("session_id") or os.path.basename(os.path.dirname(path))
        for run in data.get("runs", []):
            reqs = []
            for req in run.get("requests", []):
                model = req.get("model") or (req.get("usage") or {}).get("model")
                if model != MODEL:
                    continue
                started = parse(req.get("started_at"))
                if started is None or req.get("first_token_ms") is None:
                    continue
                reqs.append({
                    "session": session_id,
                    "iter": req.get("react_iter"),
                    "started": started,
                    "duration_ms": req.get("duration_ms"),
                    "first_token_ms": req["first_token_ms"],
                })
            reqs.sort(key=lambda r: r["started"])
            for prev, cur in zip(reqs, reqs[1:]):
                if prev["duration_ms"] is None:
                    continue
                finish = prev["started"] + timedelta(milliseconds=prev["duration_ms"])
                gap_ms = (cur["started"] - finish).total_seconds() * 1000
                if gap_ms < -5000:  # overlapping/subagent interleave, not sequential
                    continue
                cur["gap_ms"] = max(0.0, gap_ms)
                rows.append(cur)

    print(f"sequential request pairs on {MODEL}: {len(rows)}")
    print()
    buckets = [(0, 1000, "gap <1s   (hot conn)"),
               (1000, 5000, "gap 1-5s  (within httpx keepalive)"),
               (5000, 15000, "gap 5-15s (httpx drops conn)"),
               (15000, 60000, "gap 15-60s"),
               (60000, 10 ** 12, "gap >60s")]
    print(f"{'bucket':34s} {'n':>5s} {'gap med':>9s} {'ttft med':>9s} {'ttft mean':>10s} {'ttft p90':>9s}")
    for lo, hi, label in buckets:
        v = [r for r in rows if lo <= r["gap_ms"] < hi]
        if not v:
            continue
        tt = sorted(r["first_token_ms"] for r in v)
        p90 = tt[min(len(tt) - 1, int(0.9 * len(tt)))]
        print(f"{label:34s} {len(v):5d} {median([r['gap_ms'] for r in v]):9.0f} "
              f"{median(tt):9.0f} {statistics.mean(tt):10.0f} {p90:9.0f}")

    hot = [r["first_token_ms"] for r in rows if r["gap_ms"] < 5000]
    cold = [r["first_token_ms"] for r in rows if r["gap_ms"] >= 5000]
    print()
    if hot and cold:
        print(f"gap<5s  : n={len(hot):4d} median={median(hot):7.0f} ms mean={statistics.mean(hot):7.0f} ms")
        print(f"gap>=5s : n={len(cold):4d} median={median(cold):7.0f} ms mean={statistics.mean(cold):7.0f} ms")
        print(f"delta (cold - hot): median {median(cold) - median(hot):+.0f} ms, "
              f"mean {statistics.mean(cold) - statistics.mean(hot):+.0f} ms")
        share = len(cold) / (len(hot) + len(cold)) * 100
        print(f"share of requests that follow a >=5s gap: {share:.1f}%")

    # Reconnect cost implied per request.
    print()
    print("interpretation: if a >=5s gap forces a new TLS handshake, the cold-hot delta")
    print("estimates that handshake's cost; multiply by the >=5s share for the drag on the mean.")


if __name__ == "__main__":
    main()
