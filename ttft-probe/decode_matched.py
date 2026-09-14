"""Decode throughput at matched context length: same model, different serving?

Decode rate falls with context length (attention over a longer KV), so a raw tok/s
comparison is confounded when the two sides carry different prompt sizes. This bins
both sides by prompt tokens and compares tok/s within each bin.

If tok/s still differs at matched context, the two harnesses' requests are not being
served by equivalent backends -- which no client-side change can fix.

Usage: python ttft-probe/decode_matched.py
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
WORKSPACE = r"D:\AI\AI Agent\MyAgent Developer"
SESSIONS = os.path.join(WORKSPACE, "workspace", "sessions")
MODEL = "deepseek/deepseek-v4.1-flash"
LOCAL_TZ = timezone(timedelta(hours=8))
DAY = sys.argv[1] if len(sys.argv) > 1 else None  # e.g. 2026-09-11


def median(v):
    return statistics.median(v) if v else float("nan")


def myagent():
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
                if model != MODEL:
                    continue
                ttft, dur = req.get("first_token_ms"), req.get("duration_ms")
                prompt, out_tok = usage.get("prompt_tokens"), usage.get("completion_tokens")
                if not (ttft and dur and prompt and out_tok) or out_tok < 50:
                    continue
                decode_ms = dur - ttft
                if decode_ms <= 0:
                    continue
                if DAY:
                    stamp = req.get("started_at")
                    try:
                        day = datetime.fromisoformat(stamp.replace("Z", "+00:00")) \
                            .astimezone(LOCAL_TZ).strftime("%Y-%m-%d")
                    except Exception:
                        continue
                    if day != DAY:
                        continue
                out.append({"prompt": prompt, "ttft": ttft,
                            "tps": out_tok / (decode_ms / 1000.0), "out_tok": out_tok})
    return out


def dsh():
    data = json.loads(open(os.path.join(HERE, "ttft_stats.json"), encoding="utf-8").read())
    out = []
    for r in data["rows"]:
        ttft, decode_ms = r.get("ttftMs"), r.get("decodeMs")
        prompt, out_tok = r.get("promptTokens"), r.get("outputTokens")
        if not (ttft and decode_ms and prompt and out_tok) or out_tok < 50:
            continue
        if DAY:
            stamp = r.get("startTime")
            if stamp is None:
                continue
            day = datetime.fromtimestamp(stamp / 1000, LOCAL_TZ).strftime("%Y-%m-%d")
            if day != DAY:
                continue
        out.append({"prompt": prompt, "ttft": ttft,
                    "tps": out_tok / (decode_ms / 1000.0), "out_tok": out_tok})
    return out


def main():
    ma = myagent()
    ds = dsh()
    print(f"samples with a usable decode window: MyAgent {len(ma)}, DSH {len(ds)}")

    print("\n=== decode tok/s at matched context length ===")
    print(f"  {'prompt bin':>14s} {'DSH n':>6s} {'DSH tps':>8s} {'MA n':>6s} {'MA tps':>8s} "
          f"{'ratio MA/DSH':>13s}")
    lo = 0
    while lo < 300_000:
        hi = lo + 40_000
        d = [r["tps"] for r in ds if lo <= r["prompt"] < hi]
        m = [r["tps"] for r in ma if lo <= r["prompt"] < hi]
        if len(d) >= 8 and len(m) >= 8:
            dm, mm = median(d), median(m)
            print(f"  {lo // 1000:5d}k-{hi // 1000:3d}k {len(d):6d} {dm:8.1f} {len(m):6d} {mm:8.1f} "
                  f"{mm / dm * 100:12.1f}%")
        lo = hi

    print("\n=== does context length explain MyAgent's slower decode? ===")
    for label, rows in (("MyAgent", ma), ("DSH", ds)):
        print(f"  {label}:")
        for lo, hi in [(0, 60_000), (60_000, 120_000), (120_000, 180_000),
                       (180_000, 240_000), (240_000, 10 ** 9)]:
            v = [r["tps"] for r in rows if lo <= r["prompt"] < hi]
            if v:
                print(f"    {lo // 1000:4d}k-{min(hi, 999000) // 1000:4d}k  n={len(v):4d}  "
                      f"tok/s median={median(v):7.1f}")

    print("\n=== output length (decode duration driver) ===")
    for label, rows in (("MyAgent", ma), ("DSH", ds)):
        print(f"  {label}: output tokens median {median([r['out_tok'] for r in rows]):.0f}")

    print("\ninterpretation: a persistent tok/s gap at the SAME context length, with the")
    print("same model id, endpoint and credential, means the requests are not being served")
    print("by equivalent backends. That is outside both harnesses' code.")


if __name__ == "__main__":
    main()
