"""Where does MyAgent's wall time go, at the run/round level?

Per-request phases only cover the model call. The harness also spends time BETWEEN model
calls: prompt assembly, tool execution, state persistence, event emission, and whatever
else sits in the round loop. Those show up as run-level `round_gap_ms` / `startup_ms` /
`wall_ms` and as the difference between wall time and the sum of its parts.

This builds a time budget per run so the harness's own share is visible, and compares it
against DSH's sessionStats composition (llmMs / toolMs) for the same model.

Usage: python ttft-probe/time_budget.py
"""
from __future__ import annotations

import glob
import json
import os
import statistics
import sys
from collections import defaultdict

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
SESSIONS = r"D:\AI\AI Agent\MyAgent Developer\workspace\sessions"
MODEL = "deepseek/deepseek-v4.1-flash"


def med(v):
    return statistics.median(v) if v else float("nan")


def pick(v, p):
    if not v:
        return float("nan")
    s = sorted(v)
    return s[min(len(s) - 1, int(p * len(s)))]


def sum_event(ph, key):
    ev = ph.get("events") if isinstance(ph, dict) else None
    if isinstance(ev, dict) and isinstance(ev.get(key), (int, float)):
        return float(ev[key])
    return 0.0


runs = []
for path in glob.glob(os.path.join(SESSIONS, "*", "execution_metrics.json")):
    try:
        data = json.load(open(path, encoding="utf-8"))
    except Exception:
        continue
    sid = data.get("session_id") or os.path.basename(os.path.dirname(path))
    for run in data.get("runs", []):
        reqs = []
        for q in run.get("requests", []):
            u = q.get("usage") or {}
            if (q.get("model") or u.get("model")) != MODEL:
                continue
            reqs.append(q)
        if not reqs:
            continue
        acc = defaultdict(float)
        for q in reqs:
            ph = q.get("phases") or {}
            acc["pre_api"] += (ph.get("pre_api") or {}).get("total_ms") or 0
            acc["api_send"] += (ph.get("api_send") or {}).get("total_ms") or 0
            acc["first_token"] += (ph.get("first_token") or {}).get("total_ms") or 0
            acc["llm_output"] += (ph.get("llm_output") or {}).get("total_ms") or 0
            acc["tool_execution"] += (ph.get("tool_execution") or {}).get("total_ms") or 0
            acc["round_postprocess"] += (ph.get("round_postprocess") or {}).get("total_ms") or 0
            acc["other_phases"] += sum(
                (v.get("total_ms") or 0) for k, v in ph.items()
                if k not in {"pre_api", "api_send", "first_token", "llm_output",
                             "tool_execution", "round_postprocess", "llm_stream",
                             "network_transport", "final_pipeline"}
                and isinstance(v, dict)
            )
        runs.append({
            "sid": sid,
            "reqs": len(reqs),
            "wall_ms": run.get("wall_ms"),
            "startup_ms": run.get("startup_ms"),
            "round_gap_ms": run.get("round_gap_ms"),
            "status": run.get("status"),
            **acc,
        })

print(f"runs with {MODEL}: {len(runs)}")

# ---- composition -----------------------------------------------------------------
tot = lambda k: sum(r[k] for r in runs)
llm_server = tot("first_token") + tot("llm_output")
print("\n=== MyAgent time budget, summed over all runs (ms) ===")
print(f"  sum of run wall_ms        : {tot('wall_ms'):12,.0f}")
print(f"  LLM wait (first_token)    : {tot('first_token'):12,.0f}")
print(f"  LLM generation            : {tot('llm_output'):12,.0f}")
print(f"  = LLM total               : {llm_server:12,.0f}")
print(f"  tool execution            : {tot('tool_execution'):12,.0f}")
print(f"  pre_api (assembly)        : {tot('pre_api'):12,.0f}")
print(f"  api_send                  : {tot('api_send'):12,.0f}")
print(f"  round_postprocess         : {tot('round_postprocess'):12,.0f}")
print(f"  other phases              : {tot('other_phases'):12,.0f}")

wall = tot("wall_ms")
accounted = llm_server + tot("tool_execution") + tot("pre_api") + tot("api_send") + tot("round_postprocess") + tot("other_phases")
print(f"\n  accounted                 : {accounted:12,.0f}  ({accounted / wall * 100:.1f}% of wall)")
print(f"  UNACCOUNTED               : {wall - accounted:12,.0f}  ({(wall - accounted) / wall * 100:.1f}% of wall)")

# ---- run-level overhead fields ----------------------------------------------------
print("\n=== run-level overhead fields ===")
print(f"  {'field':16s} {'n':>5s} {'sum ms':>14s} {'median':>10s} {'p90':>10s} {'max':>12s}")
for key in ("startup_ms", "round_gap_ms", "wall_ms"):
    v = [r[key] for r in runs if isinstance(r.get(key), (int, float))]
    if v:
        print(f"  {key:16s} {len(v):5d} {sum(v):14,.0f} {med(v):10,.0f} {pick(v, 0.9):10,.0f} {max(v):12,.0f}")

# ---- per-session composition, biggest sessions ------------------------------------
print("\n=== per-run composition (top 12 runs by wall time) ===")
print(f"  {'session':14s} {'reqs':>5s} {'wall s':>8s} {'LLM%':>6s} {'tool%':>6s} "
      f"{'assembl%':>8s} {'post%':>6s} {'unacc%':>7s}")
for r in sorted([x for x in runs if x.get("wall_ms")], key=lambda x: -x["wall_ms"])[:12]:
    w = r["wall_ms"]
    llm = r["first_token"] + r["llm_output"]
    un = w - (llm + r["tool_execution"] + r["pre_api"] + r["api_send"]
              + r["round_postprocess"] + r["other_phases"])
    print(f"  {r['sid'][:14]:14s} {r['reqs']:5d} {w / 1000:8.1f} {llm / w * 100:5.1f}% "
          f"{r['tool_execution'] / w * 100:5.1f}% {r['pre_api'] / w * 100:7.2f}% "
          f"{r['round_postprocess'] / w * 100:5.2f}% {un / w * 100:6.1f}%")

# ---- DSH comparison ---------------------------------------------------------------
data = json.loads(open(os.path.join(HERE, "ttft_stats.json"), encoding="utf-8").read())
rows = data["rows"]
print("\n=== DSH composition for reference (from session logs) ===")
llm = sum(r.get("llmMs") or 0 for r in rows)
ttft = sum(r.get("ttftMs") or 0 for r in rows)
dec = sum(r.get("decodeMs") or 0 for r in rows)
print(f"  sum llmMs                 : {llm:12,.0f}")
print(f"  sum ttftMs                : {ttft:12,.0f}")
print(f"  sum decodeMs              : {dec:12,.0f}")
print(f"  steps                     : {len(rows)}")
print(f"  llm per step (median)     : {med([r.get('llmMs') or 0 for r in rows]):12,.0f}")
print("\n  NOTE: DSH's toolMs is not in ttft_stats.json; use the session projection for that.")
