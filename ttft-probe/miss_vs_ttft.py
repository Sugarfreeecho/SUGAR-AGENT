"""Does uncached prefill drive first-token latency in both harnesses?

Both records carry a prompt size and a cache-hit count, so the uncached remainder is
recoverable per request (MyAgent) and per step (DSH). If first-token latency tracks the
uncached remainder rather than total size, the lever is prompt/cache stability and
payload weight, not the HTTP client.

Usage: python ttft-probe/miss_vs_ttft.py
"""
from __future__ import annotations

import glob
import json
import math
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


def spearman(xs, ys):
    if len(xs) < 5:
        return None
    def rank(values):
        order = sorted(range(len(values)), key=lambda i: values[i])
        ranks = [0.0] * len(values)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for k in range(i, j + 1):
                ranks[order[k]] = avg
            i = j + 1
        return ranks
    rx, ry = rank(xs), rank(ys)
    n = len(xs)
    mx = my = (n + 1) / 2
    num = sum((rx[i] - mx) * (ry[i] - my) for i in range(n))
    dx = math.sqrt(sum((rx[i] - mx) ** 2 for i in range(n)))
    dy = math.sqrt(sum((ry[i] - my) ** 2 for i in range(n)))
    return num / (dx * dy) if dx and dy else None


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
                hit = usage.get("prompt_cache_hit_tokens")
                out.append({
                    "ttft": req["first_token_ms"],
                    "prompt": prompt,
                    "hit": hit,
                    "miss": None if prompt is None or hit is None else max(0, prompt - hit),
                    "tools": (req.get("context") or {}).get("tools"),
                })
    return out


def dsh_rows():
    path = os.path.join(HERE, "ttft_stats.json")
    data = json.loads(open(path, encoding="utf-8").read())
    out = []
    for r in data["rows"]:
        if r.get("ttftMs") is None or r.get("retries"):
            continue
        prompt = r.get("promptTokens")
        hit = r.get("cacheReadTokens")
        out.append({
            "ttft": r["ttftMs"],
            "prompt": prompt,
            "hit": hit,
            "miss": None if prompt is None or hit is None else max(0, prompt - hit),
        })
    return out


def report(label, rows):
    print(f"\n=== {label} (n={len(rows)}) ===")
    for key, title in (("prompt", "total prompt tokens"), ("miss", "UNCACHED tokens")):
        xs = [r[key] for r in rows if r.get(key) is not None]
        ys = [r["ttft"] for r in rows if r.get(key) is not None]
        rho = spearman(xs, ys)
        print(f"  spearman(TTFT, {title:22s}) = {rho:+.3f}" if rho is not None
              else f"  spearman(TTFT, {title}) = n/a")

    print(f"  {'uncached bucket':>22s} {'n':>5s} {'miss med':>9s} {'ttft med':>9s} {'ttft p90':>9s}")
    for lo, hi, label_ in [(0, 500, "0-500"), (500, 2000, "500-2k"), (2000, 8000, "2k-8k"),
                           (8000, 30000, "8k-30k"), (30000, 10 ** 12, ">=30k")]:
        v = [r for r in rows if r.get("miss") is not None and lo <= r["miss"] < hi]
        if not v:
            continue
        tt = [r["ttft"] for r in v]
        print(f"  {label_:>22s} {len(v):5d} {median([r['miss'] for r in v]):9.0f} "
              f"{median(tt):9.0f} {pick(tt, 0.9):9.0f}")


def main():
    ma = myagent_rows()
    dsh = dsh_rows()
    report("MyAgent (per request)", ma)
    report("DSH (per step)", dsh)

    print("\n=== MyAgent: does tool count track latency at similar prompt size? ===")
    band = [r for r in ma if r.get("prompt") and 100_000 <= r["prompt"] < 250_000]
    for tools in sorted({r.get("tools") for r in band if r.get("tools")}):
        v = [r["ttft"] for r in band if r.get("tools") == tools]
        if v:
            print(f"  tools={tools:3d}: n={len(v):4d} ttft median={median(v):7.0f} p90={pick(v, 0.9):7.0f}")
    print("\n  (MyAgent sent 61 tools for 771 of 778 requests; DSH sent 27.)")


if __name__ == "__main__":
    main()
