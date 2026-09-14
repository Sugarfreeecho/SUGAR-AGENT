"""Is MyAgent merely slower to the FIRST token, or served slower overall?

If the gap were only about time-to-first-token (prefill, queueing at admission), decode
throughput would match once tokens start flowing. If MyAgent's requests land on a
slower/contended backend, its decode rate would be lower too.

Also checks whether either TTFT distribution is bimodal, which is what routing the same
model id to heterogeneous upstream pools looks like.

Usage: python ttft-probe/decode_compare.py
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


def median(v):
    return statistics.median(v) if v else float("nan")


def pick(v, p):
    if not v:
        return float("nan")
    s = sorted(v)
    return s[min(len(s) - 1, int(p * len(s)))]


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
                if model != MODEL or req.get("first_token_ms") is None:
                    continue
                dur = req.get("duration_ms")
                out_tok = usage.get("completion_tokens")
                ttft = req["first_token_ms"]
                decode_ms = None if dur is None else max(0, dur - ttft)
                tps = None
                if decode_ms and out_tok and decode_ms > 0:
                    tps = out_tok / (decode_ms / 1000.0)
                out.append({"ttft": ttft, "decode_ms": decode_ms, "out_tok": out_tok, "tps": tps,
                            "prompt": usage.get("prompt_tokens")})
    return out


def dsh():
    data = json.loads(open(os.path.join(HERE, "ttft_stats.json"), encoding="utf-8").read())
    out = []
    for r in data["rows"]:
        if r.get("ttftMs") is None:
            continue
        decode_ms = r.get("decodeMs")
        out_tok = r.get("outputTokens")
        tps = None
        if decode_ms and out_tok and decode_ms > 0:
            tps = out_tok / (decode_ms / 1000.0)
        out.append({"ttft": r["ttftMs"], "decode_ms": decode_ms, "out_tok": out_tok, "tps": tps,
                    "prompt": r.get("promptTokens")})
    return out


def hist(label, values, lo, hi, width):
    print(f"\n  {label} histogram ({width}ms bins):")
    total = len(values)
    b = lo
    while b < hi:
        n = sum(1 for v in values if b <= v < b + width)
        bar = "#" * int(round(n / max(1, total) * 220))
        print(f"    {b:6d}-{b + width:6d} {n:5d} {n / total * 100:5.1f}% {bar}")
        b += width


def main():
    ma = myagent()
    ds = dsh()

    print("=== TTFT distribution shape (bimodality check) ===")
    hist("MyAgent", [r["ttft"] for r in ma], 0, 12000, 400)
    hist("DSH", [r["ttft"] for r in ds], 0, 12000, 400)

    print("\n=== decode throughput (tok/s) once tokens start flowing ===")
    print(f"  {'system':10s} {'n':>5s} {'tok/s med':>10s} {'tok/s p25':>10s} {'tok/s p75':>10s} {'out tok med':>12s}")
    for label, rows in (("MyAgent", ma), ("DSH", ds)):
        tps = [r["tps"] for r in rows if r["tps"] and r["tps"] > 0]
        toks = [r["out_tok"] for r in rows if r["out_tok"]]
        print(f"  {label:10s} {len(tps):5d} {median(tps):10.1f} {pick(tps, 0.25):10.1f} "
              f"{pick(tps, 0.75):10.1f} {median(toks):12.0f}")

    print("\n=== time split per request (median) ===")
    for label, rows in (("MyAgent", ma), ("DSH", ds)):
        tt = [r["ttft"] for r in rows]
        dm = [r["decode_ms"] for r in rows if r["decode_ms"]]
        print(f"  {label:10s} ttft {median(tt):7.0f} ms   decode {median(dm):8.0f} ms   "
              f"ttft share {median(tt) / (median(tt) + median(dm)) * 100:5.1f}%")

    print("\n  If tok/s matches but TTFT does not, the gap is admission/prefill, not the backend's speed.")
    print("  If tok/s is also lower, MyAgent's requests are being served by a slower/contended backend.")


if __name__ == "__main__":
    main()
