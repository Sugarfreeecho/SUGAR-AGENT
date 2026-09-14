"""Decompose MyAgent's real-session first-token latency into connect+headers vs server think.

MyAgent records a `llm_stream` event timeline per request with `ms_since_api_start`:
  request_serialized@0 -> stream_created@X -> first_chunk@Y -> first_delta@Y
`stream_created` is when the HTTP stream object exists, i.e. response headers have
arrived; the SDK has already paid DNS + TCP + TLS + request upload by then. So
`stream_created` is the client+network half and `first_delta - stream_created` is the
server half. This prints that split for the target model.

Usage: python ttft-probe/myagent_split.py
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


def median(values):
    return statistics.median(values) if values else float("nan")


def pick(values, p):
    if not values:
        return float("nan")
    s = sorted(values)
    return s[min(len(s) - 1, int(p * len(s)))]


def main():
    rows = []
    for path in glob.glob(os.path.join(SESSIONS, "*", "execution_metrics.json")):
        try:
            data = json.loads(open(path, encoding="utf-8").read())
        except Exception:
            continue
        session_id = data.get("session_id") or os.path.basename(os.path.dirname(path))
        for run in data.get("runs", []):
            for req in run.get("requests", []):
                events = ((req.get("phases") or {}).get("llm_stream") or {}).get("events") or []
                if not events:
                    continue
                model = None
                for ev in events:
                    if ev.get("model"):
                        model = ev["model"]
                        break
                model = req.get("model") or model or (req.get("usage") or {}).get("model")
                if model != MODEL:
                    continue
                by_step = {str(ev.get("step")): ev.get("ms_since_api_start") for ev in events}
                first_delta = req.get("first_token_ms")
                if first_delta is None:
                    first_delta = by_step.get("first_delta")
                if first_delta is None:
                    continue
                started = req.get("started_at")
                day = None
                if started:
                    try:
                        day = datetime.fromisoformat(started.replace("Z", "+00:00")) \
                            .astimezone(LOCAL_TZ).strftime("%Y-%m-%d")
                    except Exception:
                        day = None
                rows.append({
                    "session": session_id,
                    "day": day,
                    "stream_created": by_step.get("stream_created"),
                    "first_chunk": by_step.get("first_chunk"),
                    "first_delta": first_delta,
                    "turn_ready": by_step.get("turn_ready"),
                    "request_serialized": by_step.get("request_serialized"),
                    "create_attempt_start": by_step.get("create_attempt_start"),
                    "tools": (req.get("context") or {}).get("tools"),
                    "messages": (req.get("context") or {}).get("messages"),
                    "max_output_tokens": (req.get("context") or {}).get("max_output_tokens"),
                    "prompt_tokens": (req.get("usage") or {}).get("prompt_tokens"),
                })

    print(f"requests on {MODEL} with a stream timeline: {len(rows)}")
    if not rows:
        return

    def report(label, subset):
        if not subset:
            return
        sc = [r["stream_created"] for r in subset if r["stream_created"] is not None]
        fd = [r["first_delta"] for r in subset]
        server = [r["first_delta"] - r["stream_created"] for r in subset
                  if r["stream_created"] is not None]
        print(f"\n--- {label} (n={len(subset)}) ---")
        print(f"  stream_created (connect+headers): median {median(sc):7.0f}  p90 {pick(sc, 0.9):7.0f} "
              f"mean {statistics.mean(sc) if sc else float('nan'):7.0f}  max {max(sc) if sc else float('nan'):7.0f}")
        print(f"  first_delta (total TTFT)        : median {median(fd):7.0f}  p90 {pick(fd, 0.9):7.0f} "
              f"mean {statistics.mean(fd):7.0f}")
        print(f"  server half (fd - stream_created): median {median(server):7.0f}  p90 {pick(server, 0.9):7.0f} "
              f"mean {statistics.mean(server) if server else float('nan'):7.0f}")
        if sc and fd:
            share = median(sc) / median(fd) * 100
            print(f"  connect+headers share of TTFT   : {share:.1f}%")

    report("all days", rows)
    by_day = defaultdict(list)
    for r in rows:
        by_day[r["day"]].append(r)
    for day in sorted(by_day, key=lambda d: (d is None, d)):
        report(f"day {day}", by_day[day])

    # Distribution of the connect+headers half.
    sc = sorted(r["stream_created"] for r in rows if r["stream_created"] is not None)
    print("\nconnect+headers histogram (ms):")
    for lo, hi in [(0, 100), (100, 250), (250, 500), (500, 1000), (1000, 2000), (2000, 4000), (4000, 10 ** 9)]:
        n = sum(1 for v in sc if lo <= v < hi)
        label = f"{lo}-{hi}" if hi < 10 ** 9 else f">={lo}"
        print(f"  {label:12s} {n:5d}  {n / len(sc) * 100:5.1f}%")

    tool_counts = [r["tools"] for r in rows if r.get("tools")]
    max_tokens = sorted({r["max_output_tokens"] for r in rows if r.get("max_output_tokens")})
    print(f"\ntools per request: median {median(tool_counts):.0f}, min {min(tool_counts)}, max {max(tool_counts)}")
    print(f"max_output_tokens values seen: {max_tokens}")


if __name__ == "__main__":
    main()
