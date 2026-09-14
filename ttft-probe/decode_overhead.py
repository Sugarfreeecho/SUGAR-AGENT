"""Does the decode window contain non-decode overhead? (checks the tok/s finding)

Decode throughput was computed as output_tokens / (duration - first_token). If that
window carries a constant overhead (post-stream handoff, queue drain), tok/s would be
understated and would look flat across context lengths, which is what the raw numbers
showed. Regressing decode_ms on output_tokens separates the two:
  slope     = true ms per token
  intercept = fixed overhead inside the window

Usage: python ttft-probe/decode_overhead.py
"""
from __future__ import annotations

import glob
import json
import os
import statistics
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
WORKSPACE = r"D:\AI\AI Agent\MyAgent Developer"
SESSIONS = os.path.join(WORKSPACE, "workspace", "sessions")
MODEL = "deepseek/deepseek-v4.1-flash"


def ols(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    b = sxy / sxx if sxx else 0.0
    a = my - b * mx
    ss_tot = sum((y - my) ** 2 for y in ys)
    ss_res = sum((y - (a + b * x)) ** 2 for x, y in zip(xs, ys))
    return a, b, (1 - ss_res / ss_tot if ss_tot else 0.0)


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
                out_tok, prompt = usage.get("completion_tokens"), usage.get("prompt_tokens")
                if not (ttft and dur and out_tok and prompt) or out_tok < 50:
                    continue
                events = ((req.get("phases") or {}).get("llm_stream") or {}).get("events") or []
                steps = {str(e.get("step")): e.get("ms_since_api_start") for e in events}
                out.append({
                    "prompt": prompt, "out_tok": out_tok,
                    "decode_ms": dur - ttft,
                    "stream_exhausted": steps.get("stream_exhausted"),
                    "turn_ready": steps.get("turn_ready"),
                    "duration_ms": dur,
                })
    return out


def dsh():
    data = json.loads(open(os.path.join(HERE, "ttft_stats.json"), encoding="utf-8").read())
    out = []
    for r in data["rows"]:
        if not (r.get("decodeMs") and r.get("outputTokens") and r.get("promptTokens")):
            continue
        if r["outputTokens"] < 50:
            continue
        out.append({"prompt": r["promptTokens"], "out_tok": r["outputTokens"],
                    "decode_ms": r["decodeMs"]})
    return out


def main():
    ma = myagent()
    ds = dsh()

    print("=== decode_ms = intercept + slope * output_tokens ===")
    for label, rows in (("MyAgent", ma), ("DSH", ds)):
        xs = [r["out_tok"] for r in rows]
        ys = [r["decode_ms"] for r in rows]
        a, b, r2 = ols(xs, ys)
        print(f"  {label:8s} n={len(rows):4d}  intercept={a:8.0f} ms   slope={b:6.2f} ms/token "
              f"({1000 / b:5.1f} tok/s)   R2={r2:.3f}")

    print("\n=== is there a gap between the last chunk and the recorded finish? ===")
    both = [r for r in ma if r["stream_exhausted"] is not None and r["turn_ready"] is not None]
    if both:
        gaps = [r["turn_ready"] - r["stream_exhausted"] for r in both]
        print(f"  MyAgent turn_ready - stream_exhausted: n={len(gaps)} median {statistics.median(gaps):.0f} ms "
              f"p90 {sorted(gaps)[min(len(gaps) - 1, int(0.9 * len(gaps)))]:.0f} ms max {max(gaps)} ms")
    devs = [r["duration_ms"] - r["stream_exhausted"] for r in ma
            if r["stream_exhausted"] is not None]
    if devs:
        print(f"  MyAgent duration_ms - stream_exhausted: n={len(devs)} median {statistics.median(devs):.0f} ms "
              f"max {max(devs)} ms")

    print("\n=== same comparison restricted to a narrow context band (120k-160k) ===")
    lo, hi = 120_000, 160_000
    for label, rows in (("MyAgent", ma), ("DSH", ds)):
        v = [r for r in rows if lo <= r["prompt"] < hi]
        if len(v) < 8:
            continue
        a, b, r2 = ols([r["out_tok"] for r in v], [r["decode_ms"] for r in v])
        print(f"  {label:8s} n={len(v):4d}  intercept={a:8.0f} ms   slope={b:6.2f} ms/token "
              f"({1000 / b:5.1f} tok/s)   R2={r2:.3f}")

    print("\n  A large positive intercept with a matching slope would mean the tok/s gap is")
    print("  an accounting artifact; a matching intercept with a different slope means the")
    print("  tokens really do come out slower.")


if __name__ == "__main__":
    main()
