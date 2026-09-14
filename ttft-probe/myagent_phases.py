"""Where does MyAgent's time actually go? Enumerate every recorded phase.

MyAgent records a rich per-request breakdown (pre_api, api_send, llm_stream, network,
runtime writes) in workspace/sessions/*/execution_metrics.json. This inventories every
phase and event key that appears, then aggregates each one's absolute cost and how it
scales with context length -- the goal being to locate the harness's own overhead rather
than attribute it upstream.

Usage: python ttft-probe/myagent_phases.py
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

WORKSPACE = r"D:\AI\AI Agent\MyAgent Developer"
SESSIONS = os.path.join(WORKSPACE, "workspace", "sessions")
MODEL = "deepseek/deepseek-v4.1-flash"


def med(v):
    return statistics.median(v) if v else float("nan")


def pick(v, p):
    if not v:
        return float("nan")
    s = sorted(v)
    return s[min(len(s) - 1, int(p * len(s)))]


def ols(xs, ys):
    n = len(xs)
    if n < 5:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if not sxx:
        return None
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    b = sxy / sxx
    return my - b * mx, b


rows = []
for path in glob.glob(os.path.join(SESSIONS, "*", "execution_metrics.json")):
    try:
        data = json.load(open(path, encoding="utf-8"))
    except Exception:
        continue
    sid = data.get("session_id") or os.path.basename(os.path.dirname(path))
    for run in data.get("runs", []):
        for q in run.get("requests", []):
            u = q.get("usage") or {}
            if (q.get("model") or u.get("model")) != MODEL:
                continue
            rows.append({
                "sid": sid,
                "prompt": u.get("prompt_tokens"),
                "out_tok": u.get("completion_tokens"),
                "ttft": q.get("first_token_ms"),
                "dur": q.get("duration_ms"),
                "phases": q.get("phases") or {},
                "network": q.get("network") or {},
                "top_keys": sorted(q.keys()),
            })

print(f"requests on {MODEL}: {len(rows)}")

# ---- inventory -------------------------------------------------------------------
phase_keys = defaultdict(set)
for r in rows:
    for name, ph in r["phases"].items():
        if isinstance(ph, dict):
            for k, v in ph.items():
                if k == "events" and isinstance(v, dict):
                    for ek in v:
                        phase_keys[name].add("events." + ek)
                elif not isinstance(v, (dict, list)):
                    phase_keys[name].add(k)

print("\n=== phase inventory (what exists, and how often) ===")
for name in sorted(phase_keys):
    present = sum(1 for r in rows if name in r["phases"])
    total_present = sum(1 for r in rows if isinstance(r["phases"].get(name), dict)
                        and r["phases"][name].get("total_ms") is not None)
    print(f"\n  [{name}]  present in {present}/{len(rows)}, total_ms in {total_present}")
    for k in sorted(phase_keys[name]):
        print(f"      {k}")

# ---- aggregate the phase totals --------------------------------------------------
print("\n=== phase total_ms: absolute cost and context scaling ===")
print(f"  {'phase':22s} {'n':>5s} {'median':>9s} {'p90':>9s} {'max':>9s} "
      f"{'ms/1k ctx':>10s}  {'share of TTFT':>13s}")
ttft_med = med([r["ttft"] for r in rows if r["ttft"]])
for name in sorted(phase_keys):
    vals, cs = [], []
    for r in rows:
        ph = r["phases"].get(name)
        if isinstance(ph, dict) and ph.get("total_ms") is not None:
            vals.append(ph["total_ms"])
            if r["prompt"] and r["ttft"] is not None:
                cs.append((r["prompt"] / 1000.0, ph["total_ms"]))
    if not vals:
        continue
    fit = ols([c[0] for c in cs], [c[1] for c in cs]) if len(cs) >= 5 else None
    slope = fit[1] if fit else float("nan")
    print(f"  {name:22s} {len(vals):5d} {med(vals):9.0f} {pick(vals, 0.9):9.0f} {max(vals):9.0f} "
          f"{slope:10.2f}  {med(vals) / ttft_med * 100:12.1f}%")

# ---- llm_stream event timeline ---------------------------------------------------
print("\n=== llm_stream segment durations (median ms, by consecutive event gap) ===")
seg = defaultdict(list)
for r in rows:
    events = ((r["phases"].get("llm_stream") or {}).get("events")) or []
    if not isinstance(events, list):
        continue
    pts = []
    for e in events:
        if isinstance(e, dict) and e.get("step") and isinstance(e.get("ms_since_api_start"), (int, float)):
            pts.append((str(e["step"]), float(e["ms_since_api_start"])))
    pts.sort(key=lambda x: x[1])
    for (a, ta), (b, tb) in zip(pts, pts[1:]):
        seg[f"{a} -> {b}"].append(tb - ta)
if seg:
    print(f"  {'segment':52s} {'n':>5s} {'median':>9s} {'p90':>9s} {'max':>10s}")
    for key in sorted(seg, key=lambda k: -med(seg[k])):
        v = seg[key]
        print(f"  {key:52s} {len(v):5d} {med(v):9.1f} {pick(v, 0.9):9.1f} {max(v):10.1f}")

# ---- network keys ----------------------------------------------------------------
if any(r["network"] for r in rows):
    print("\n=== network block ===")
    nk = sorted({k for r in rows for k in r["network"]})
    print(f"  {'key':38s} {'n':>5s} {'median':>10s} {'p90':>10s} {'max':>10s}")
    for k in nk:
        v = [r["network"][k] for r in rows if isinstance(r["network"].get(k), (int, float))]
        if v:
            print(f"  {k:38s} {len(v):5d} {med(v):10.1f} {pick(v, 0.9):10.1f} {max(v):10.1f}")

# ---- the pure generation window MyAgent measures itself --------------------------
print("\n=== MyAgent's own generation window (usage._timing) ===")
gen = []
for r in rows:
    events = ((r["phases"].get("llm_stream") or {}).get("events")) or []
    for e in events if isinstance(events, list) else []:
        if isinstance(e, dict) and e.get("step") == "usage_chunk":
            pass
found = defaultdict(int)
for r in rows:
    for name, ph in r["phases"].items():
        if isinstance(ph, dict):
            for k in ph:
                found[f"{name}.{k}"] += 1
print("  (usage _timing is attached to the usage payload, not a phase; keys seen:)")
for k in sorted(found):
    if "timing" in k or "generation" in k:
        print(f"    {k}: {found[k]}")
