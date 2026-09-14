"""Does TTFT really grow with context, or is that a session/time artifact?

The header/tools experiment (header_probe.py) found no arm difference at ~30 tokens of
prompt, where BOTH harnesses sit at a ~3.4 s floor. Yet in production DSH holds ~3.0 s at
116k tokens while MyAgent reaches ~5.0 s. Before blaming context length, rule out the
obvious confound: MyAgent's high-context requests may simply cluster in slow sessions or
slow time windows.

This regresses TTFT on prompt size WITHIN each session, so session identity, tool set,
model route and time period are all held fixed.

Usage: python ttft-probe/within_session.py
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
WORKSPACE = r"D:\AI\AI Agent\MyAgent Developer"
SESSIONS = os.path.join(WORKSPACE, "workspace", "sessions")
MODEL = "deepseek/deepseek-v4.1-flash"
LOCAL_TZ = timezone(timedelta(hours=8))


def median(v):
    return statistics.median(v) if v else float("nan")


def ols(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if not sxx:
        return None
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    b = sxy / sxx
    a = my - b * mx
    ss_tot = sum((y - my) ** 2 for y in ys)
    ss_res = sum((y - (a + b * x)) ** 2 for x, y in zip(xs, ys))
    return a, b, (1 - ss_res / ss_tot if ss_tot else 0.0)


def myagent_sessions():
    out = defaultdict(list)
    for path in glob.glob(os.path.join(SESSIONS, "*", "execution_metrics.json")):
        try:
            data = json.loads(open(path, encoding="utf-8").read())
        except Exception:
            continue
        sid = data.get("session_id") or os.path.basename(os.path.dirname(path))
        for run in data.get("runs", []):
            for req in run.get("requests", []):
                usage = req.get("usage") or {}
                model = req.get("model") or usage.get("model")
                if model != MODEL or req.get("first_token_ms") is None:
                    continue
                prompt = usage.get("prompt_tokens")
                if not prompt:
                    continue
                stamp = req.get("started_at")
                day = None
                try:
                    day = datetime.fromisoformat(stamp.replace("Z", "+00:00")) \
                        .astimezone(LOCAL_TZ).strftime("%Y-%m-%d")
                except Exception:
                    pass
                out[sid].append({"prompt": prompt, "ttft": req["first_token_ms"], "day": day})
    return out


def dsh_sessions():
    data = json.loads(open(os.path.join(HERE, "ttft_stats.json"), encoding="utf-8").read())
    out = defaultdict(list)
    for r in data["rows"]:
        if r.get("ttftMs") is None or r.get("retries") or not r.get("promptTokens"):
            continue
        out[r["sessionId"]].append({"prompt": r["promptTokens"], "ttft": r["ttftMs"]})
    return out


def report(label, sessions):
    print(f"\n=== {label}: within-session TTFT vs context ===")
    print(f"  {'session':26s} {'n':>4s} {'ctx min':>8s} {'ctx max':>8s} {'slope ms/1k':>12s} "
          f"{'R2':>6s} {'ttft lo-ctx':>11s} {'ttft hi-ctx':>11s}")
    slopes = []
    for sid, rows in sorted(sessions.items(), key=lambda kv: -len(kv[1])):
        if len(rows) < 12:
            continue
        xs = [r["prompt"] for r in rows]
        ys = [r["ttft"] for r in rows]
        if max(xs) - min(xs) < 20_000:
            continue
        fit = ols(xs, ys)
        if not fit:
            continue
        a, b, r2 = fit
        lo = [r["ttft"] for r in rows if r["prompt"] <= statistics.median(xs)]
        hi = [r["ttft"] for r in rows if r["prompt"] > statistics.median(xs)]
        slopes.append(b * 1000)
        print(f"  {sid[:26]:26s} {len(rows):4d} {min(xs):8d} {max(xs):8d} {b * 1000:12.2f} "
              f"{r2:6.3f} {median(lo):11.0f} {median(hi):11.0f}")
    if slopes:
        print(f"\n  slope across sessions: median {median(slopes):.2f} ms per 1k tokens "
              f"(min {min(slopes):.2f}, max {max(slopes):.2f})")
    return slopes


def main():
    ma = myagent_sessions()
    ds = dsh_sessions()
    ma_slopes = report("MyAgent", ma)
    ds_slopes = report("DSH", ds)

    print("\n=== interpretation ===")
    if ma_slopes:
        print(f"  MyAgent within-session slope median = {median(ma_slopes):.2f} ms/1k tokens")
    if ds_slopes:
        print(f"  DSH     within-session slope median = {median(ds_slopes):.2f} ms/1k tokens")
    print("\n  A consistently positive within-session slope means the context effect is real and")
    print("  not a between-session/time artifact. If slopes straddle zero, the production gap")
    print("  must come from something that differs BETWEEN sessions instead.")

    print("\n=== the floor: what is the fastest either side ever goes? ===")
    for label, sessions in (("MyAgent", ma), ("DSH", ds)):
        allv = [r["ttft"] for rows in sessions.values() for r in rows]
        s = sorted(allv)
        print(f"  {label:8s} n={len(s):4d} min={s[0]:6.0f} p05={s[int(0.05 * len(s))]:6.0f} "
              f"p10={s[int(0.10 * len(s))]:6.0f} median={median(s):6.0f}")


if __name__ == "__main__":
    main()
