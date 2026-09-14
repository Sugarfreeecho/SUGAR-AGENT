"""Does the idle gap before a request drive TTFT, once context length is controlled?

The 100k-context probe showed ~140 UNCACHED tokens still costing ~4.9 s of TTFT, i.e. the
cost tracks TOTAL context, not prefill work. That points at the backend having to
re-establish the long KV for the prefix rather than recompute it -- which would mean a
request arriving after a long idle gap pays to bring the cache back, while one arriving
immediately behind its predecessor finds it resident.

Production records let this be tested for free, within a session:

  TTFT ~ b1*prompt_tokens + b2*gap           (gap = idle ms since the previous request)

A positive, significant b2 while b1 stays as-is is evidence for the residency mechanism.
Only intra-session pairs are used, so session identity, tools and route are held fixed.

Usage: python ttft-probe/gap_residual.py
"""
from __future__ import annotations

import glob
import json
import math
import os
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
SESSIONS = r"D:\AI\AI Agent\MyAgent Developer\workspace\sessions"
MODEL = "deepseek/deepseek-v4.1-flash"
TZ = timezone(timedelta(hours=8))


def med(v):
    return statistics.median(v) if v else float("nan")


def mv_ols(rows, y_key, x_keys):
    """Multivariate least squares with an intercept, via normal equations."""
    n = len(rows)
    k = len(x_keys) + 1
    X = [[1.0] + [r[x] for x in x_keys] for r in rows]
    y = [r[y_key] for r in rows]
    A = [[sum(X[i][a] * X[i][b] for i in range(n)) for b in range(k)] for a in range(k)]
    B = [sum(X[i][a] * y[i] for i in range(n)) for a in range(k)]
    # Gaussian elimination with partial pivoting
    M = [row[:] + [B[i]] for i, row in enumerate(A)]
    for c in range(k):
        p = max(range(c, k), key=lambda r: abs(M[r][c]))
        if abs(M[p][c]) < 1e-12:
            return None
        M[c], M[p] = M[p], M[c]
        piv = M[c][c]
        M[c] = [v / piv for v in M[c]]
        for r in range(k):
            if r != c and M[r][c]:
                f = M[r][c]
                M[r] = [a - f * b for a, b in zip(M[r], M[c])]
    coef = [M[i][k] for i in range(k)]
    ybar = sum(y) / n
    ss_tot = sum((v - ybar) ** 2 for v in y)
    ss_res = sum((y[i] - sum(coef[j] * X[i][j] for j in range(k))) ** 2 for i in range(n))
    return coef, (1 - ss_res / ss_tot if ss_tot else 0.0)


def tstat(rows, y_key, x_keys, idx):
    """Crude t statistic for one coefficient: refit without it and compare residual SS."""
    coef, _ = mv_ols(rows, y_key, x_keys)
    if not coef:
        return None
    n = len(rows)
    k = len(x_keys) + 1
    res = [rows[i][y_key] - (coef[0] + sum(coef[j + 1] * rows[i][x_keys[j]] for j in range(len(x_keys))))
           for i in range(n)]
    s2 = sum(r * r for r in res) / max(1, n - k)
    # standard error via the (X'X)^-1 diagonal
    X = [[1.0] + [r[x] for x in x_keys] for r in rows]
    A = [[sum(X[i][a] * X[i][b] for i in range(n)) for b in range(k)] for a in range(k)]
    M = [row[:] + [1.0 if i == j else 0.0 for j in range(k)] for i, row in enumerate(A)]
    for c in range(k):
        p = max(range(c, k), key=lambda r: abs(M[r][c]))
        if abs(M[p][c]) < 1e-12:
            return None
        M[c], M[p] = M[p], M[c]
        piv = M[c][c]
        M[c] = [v / piv for v in M[c]]
        for r in range(k):
            if r != c and M[r][c]:
                f = M[r][c]
                M[r] = [a - f * b for a, b in zip(M[r], M[c])]
    inv_diag = [M[i][k + i] for i in range(k)]
    se = math.sqrt(max(0.0, s2 * inv_diag[idx]))
    return coef[idx] / se if se else None


# ---- collect MyAgent intra-session pairs -------------------------------------------
sessions = defaultdict(list)
for p in glob.glob(os.path.join(SESSIONS, "*", "execution_metrics.json")):
    try:
        d = json.load(open(p, encoding="utf-8"))
    except Exception:
        continue
    sid = d.get("session_id") or os.path.basename(os.path.dirname(p))
    for run in d.get("runs", []):
        for q in run.get("requests", []):
            u = q.get("usage") or {}
            if (q.get("model") or u.get("model")) != MODEL or not q.get("first_token_ms"):
                continue
            if not u.get("prompt_tokens"):
                continue
            try:
                start = datetime.fromisoformat(q["started_at"].replace("Z", "+00:00"))
            except Exception:
                continue
            sessions[sid].append({
                "start": start,
                "prompt": u["prompt_tokens"],
                "ttft": q["first_token_ms"],
                "dur": q.get("duration_ms") or 0,
            })

rows = []
for sid, reqs in sessions.items():
    reqs.sort(key=lambda r: r["start"])
    for prev, cur in zip(reqs, reqs[1:]):
        gap = (cur["start"] - prev["start"]).total_seconds() * 1000 - prev["dur"]
        if gap < -5000 or gap > 600_000:
            continue
        rows.append({"ttft": cur["ttft"], "prompt": cur["prompt"] / 1000.0,
                     "gap": max(0.0, gap) / 1000.0, "sid": sid})

print(f"MyAgent intra-session pairs: {len(rows)}")
if len(rows) < 30:
    print("not enough pairs")
    raise SystemExit(0)

fit = mv_ols(rows, "ttft", ["prompt", "gap"])
if not fit:
    print("fit failed")
    raise SystemExit(0)
coef, r2 = fit
t_prompt = tstat(rows, "ttft", ["prompt", "gap"], 1)
t_gap = tstat(rows, "ttft", ["prompt", "gap"], 2)
print("\nTTFT(ms) = a + b1*prompt(1k tok) + b2*gap(s)")
print(f"  intercept a = {coef[0]:9.0f} ms")
print(f"  b1 (prompt) = {coef[1]:9.1f} ms per 1k tok   t = {t_prompt:6.2f}"
      f"   {'SIGNIFICANT' if t_prompt and abs(t_prompt) > 2 else 'not significant'}")
print(f"  b2 (gap)    = {coef[2]:9.1f} ms per second  t = {t_gap:6.2f}"
      f"   {'SIGNIFICANT' if t_gap and abs(t_gap) > 2 else 'not significant'}")
print(f"  R2 = {r2:.3f}")

print("\nraw gap buckets (context NOT controlled, shown for contrast):")
print(f"  {'gap':>12s} {'n':>5s} {'prompt med':>11s} {'ttft med':>9s}")
for lo, hi, lbl in [(0, 1, "<1s"), (1, 5, "1-5s"), (5, 15, "5-15s"),
                    (15, 60, "15-60s"), (60, 600, ">60s")]:
    v = [r for r in rows if lo <= r["gap"] < hi]
    if v:
        print(f"  {lbl:>12s} {len(v):5d} {med([r['prompt'] for r in v]) * 1000:11.0f} "
              f"{med([r['ttft'] for r in v]):9.0f}")

print("\n  A significant positive b2 means the idle gap itself costs TTFT at fixed context,")
print("  which supports the KV-residency reading of the long-context probe result.")
