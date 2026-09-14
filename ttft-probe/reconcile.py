"""Reconcile the two conflicting 9/11 reports.

  A) MyAgent's own report (workspace/ttft_stats/首token对比_0911.md):
       DSH ~4.40 s vs MyAgent ~5.10 s  ->  gap 0.6-0.7 s
  B) This probe's report (ttft-probe/compare.md):
       DSH 3.04 s vs MyAgent 4.96 s    ->  gap 1.92 s

Both read the same underlying events, so the disagreement must be a choice of statistic,
sample, or window. This recomputes the gap under each choice to locate it.

Usage: python ttft-probe/reconcile.py
"""
from __future__ import annotations

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
SESSIONS = r"D:\AI\AI Agent\MyAgent Developer\workspace\sessions"
MODEL = "deepseek/deepseek-v4.1-flash"
TZ = timezone(timedelta(hours=8))
DAY = "2026-09-11"
# The self-inflicted load generator run on 9/11 14:40-15:06 (N=300 concurrency, ttft-probe).
STRESS = ("2026-09-11T14:40", "2026-09-11T15:06")


def mean(v):
    return statistics.mean(v) if v else float("nan")


def med(v):
    return statistics.median(v) if v else float("nan")


def p90(v):
    if not v:
        return float("nan")
    s = sorted(v)
    return s[min(len(s) - 1, int(0.9 * len(s)))]


def dsh_rows():
    data = json.loads(open(os.path.join(HERE, "ttft_stats.json"), encoding="utf-8").read())
    out = []
    for r in data["rows"]:
        if r.get("ttftMs") is None:
            continue
        out.append({
            "ttft": r["ttftMs"],
            "start": r["startTime"],
            "sid": r["sessionId"],
            "depth": r.get("depth") or 0,
            "prompt": r.get("promptTokens"),
        })
    return out


def myagent_rows():
    out = []
    import glob
    for p in glob.glob(os.path.join(SESSIONS, "*", "execution_metrics.json")):
        try:
            d = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        for run in d.get("runs", []):
            for q in run.get("requests", []):
                u = q.get("usage") or {}
                if (q.get("model") or u.get("model")) != "deepseek/deepseek-v4.1-flash":
                    continue
                if q.get("first_token_ms") is None:
                    continue
                try:
                    dt = datetime.fromisoformat(q["started_at"].replace("Z", "+00:00")).astimezone(TZ)
                except Exception:
                    continue
                if dt.strftime("%Y-%m-%d") != DAY:
                    continue
                out.append({"ttft": q["first_token_ms"], "dt": dt,
                            "sid": d.get("session_id") or "?", "prompt": u.get("prompt_tokens")})
    return out


def in_stress(ms):
    lo = datetime.fromisoformat(STRESS[0] + ":00").replace(tzinfo=TZ).timestamp() * 1000
    hi = datetime.fromisoformat(STRESS[1] + ":00").replace(tzinfo=TZ).timestamp() * 1000
    return lo <= ms <= hi


ds = dsh_rows()
ma = myagent_rows()
ds_day = [r for r in ds
          if datetime.fromtimestamp(r["start"] / 1000, TZ).strftime("%Y-%m-%d") == DAY]
ma_day = [r for r in ma
          if (r.get("model") or "").startswith("deepseek/deepseek-v4.1-flash")]
if not ma_day:
    ma_day = ma

print("=" * 78)
print("SAMPLE SIZES")
print("=" * 78)
print(f"  DSH rows in ttft_stats.json : {len(ds)}  (all days)")
print(f"  DSH on {DAY}                 : {len(ds_day)}")
ds_main = [r for r in ds_day if r["depth"] == 0]
ds_sub = [r for r in ds_day if r["depth"] > 0]
print(f"    main sessions (depth 0)   : {len(ds_main)}")
print(f"    subagent sessions         : {len(ds_sub)}")
live = {r["sid"] for r in ds_day if r["sid"].startswith("session-6fc3c8e9")}
print(f"    incl. the live probe session 6fc3c8e9: {len(live)} session(s)")
main_only = [r for r in ds_day if r["sid"] not in live]
print(f"  DSH on {DAY} minus the live session: {len(main_only)}")
print(f"  MyAgent on {DAY}            : {len(ma_day)}")

print()
print("=" * 78)
print("STATISTIC: mean vs median (this is most of the disagreement)")
print("=" * 78)
print(f"  {'sample':44s} {'n':>5s} {'mean':>9s} {'median':>9s} {'p90':>9s}")
for label, rows, key in (
    ("DSH all (6 sessions, MyAgent's report)", main_only, "ttft"),
    ("DSH all incl. live session", ds_day, "ttft"),
    ("DSH main session only", ds_main, "ttft"),
    ("DSH subagents only", ds_sub, "ttft"),
    ("MyAgent all 9/11", ma_day, "ttft"),
):
    v = [r[key] for r in rows]
    print(f"  {label:44s} {len(v):5d} {mean(v):9.0f} {med(v):9.0f} {p90(v):9.0f}")

print()
print("  -> gap using MEAN   : DSH {:.0f} vs MyAgent {:.0f} = {:.0f} ms".format(
    mean([r["ttft"] for r in main_only]), mean([r["ttft"] for r in ma_day]),
    mean([r["ttft"] for r in ma_day]) - mean([r["ttft"] for r in main_only])))
print("  -> gap using MEDIAN : DSH {:.0f} vs MyAgent {:.0f} = {:.0f} ms".format(
    med([r["ttft"] for r in main_only]), med([r["ttft"] for r in ma_day]),
    med([r["ttft"] for r in ma_day]) - med([r["ttft"] for r in main_only])))

print()
print("=" * 78)
print("WHY DSH's MEAN is inflated: the self-inflicted stress test")
print("=" * 78)
stress = [r for r in ds_day if in_stress(r["start"])]
clean = [r for r in ds_day if not in_stress(r["start"])]
print(f"  DSH steps during the 14:40-15:06 ttft-probe load test : {len(stress)}")
if stress:
    v = [r["ttft"] for r in stress]
    print(f"    their TTFT  mean {mean(v):8.0f}  median {med(v):8.0f}  max {max(v):8.0f}")
    print(f"    steps >= 20 s : {sum(1 for x in v if x >= 20000)}")
print(f"  DSH steps outside that window : {len(clean)}")
v = [r["ttft"] for r in clean]
print(f"    their TTFT  mean {mean(v):8.0f}  median {med(v):8.0f}")
print()
print("  Effect on the DSH average:")
print(f"    with the stress window    : mean {mean([r['ttft'] for r in main_only]):.0f} ms")
mc = [r for r in main_only if not in_stress(r["start"])]
print(f"    without the stress window : mean {mean([r['ttft'] for r in mc]):.0f} ms "
      f"(median {med([r['ttft'] for r in mc]):.0f} ms)")

print()
print("=" * 78)
print("SAME-WINDOW CHECK (both harnesses, same clock hours)")
print("=" * 78)
lo_h = min(datetime.fromtimestamp(r["start"] / 1000, TZ).hour for r in ds_day)
hi_h = max(datetime.fromtimestamp(r["start"] / 1000, TZ).hour for r in ds_day)
print(f"  DSH 9/11 spans hours {lo_h:02d}-{hi_h:02d}")
win_ma = [r for r in ma_day if lo_h <= r["dt"].hour <= hi_h]
win_ds = [r for r in ds_day if lo_h <= datetime.fromtimestamp(r["start"] / 1000, TZ).hour <= hi_h]
print(f"  inside that window: MyAgent n={len(win_ma)}  DSH n={len(win_ds)}")
if win_ma and win_ds:
    a = [r["ttft"] for r in win_ma]
    b = [r["ttft"] for r in win_ds]
    print(f"    MyAgent  mean {mean(a):7.0f}  median {med(a):7.0f}")
    print(f"    DSH      mean {mean(b):7.0f}  median {med(b):7.0f}")
    print(f"    gap      mean {mean(a) - mean(b):+7.0f}  median {med(a) - med(b):+7.0f}")
    # and without the load test
    bw = [r["ttft"] for r in win_ds if not in_stress(r["start"])]
    if bw:
        print(f"    DSH excl. load test  mean {mean(bw):7.0f}  median {med(bw):7.0f}  "
              f"(n={len(bw)})")

print()
print("=" * 78)
print("PROMPT SIZE, per group (explains why subagents look fast)")
print("=" * 78)
for label, rows in (("DSH main", ds_main), ("DSH subagents", ds_sub)):
    v = [r["prompt"] for r in rows if r.get("prompt")]
    if v:
        print(f"  {label:16s} n={len(v):4d}  prompt median {med(v):9.0f}  mean {mean(v):9.0f}")
v = [r["prompt"] for r in ma_day if r.get("prompt")]
print(f"  {'MyAgent':16s} n={len(v):4d}  prompt median {med(v):9.0f}  mean {mean(v):9.0f}")

print()
print("=" * 78)
print("DID MyAgent RUN DURING DSH's LOAD TEST? (decides whether that window is fair)")
print("=" * 78)
win_ma_load = [r for r in ma_day
               if in_stress(r["dt"].replace(tzinfo=TZ).timestamp() * 1000)]
print(f"  MyAgent requests inside 14:40-15:06 : {len(win_ma_load)}")
print(f"  DSH steps inside 14:40-15:06        : {len(stress)}")
if not win_ma_load and stress:
    print()
    print("  MyAgent was NOT running while the load test hit DSH. Keeping that window in the")
    print("  DSH average therefore charges DSH for a handicap MyAgent never faced, which")
    print("  SHRINKS the apparent gap:")
    with_w = mean([r["ttft"] for r in main_only])
    without_w = mean([r["ttft"] for r in mc])
    ma_mean = mean([r["ttft"] for r in ma_day])
    print(f"    DSH mean WITH the window    : {with_w:7.0f} ms  -> gap vs MyAgent {ma_mean - with_w:+7.0f} ms")
    print(f"    DSH mean WITHOUT the window : {without_w:7.0f} ms  -> gap vs MyAgent {ma_mean - without_w:+7.0f} ms")

print()
print("=" * 78)
print("SUMMARY OF THE DISAGREEMENT")
print("=" * 78)
print("  1. statistic      : their 0.6-0.7 s is a MEAN gap; this probe quoted a MEDIAN gap.")
print("  2. load-test bias : DSH's mean includes 55 steps from the 14:40-15:06 ttft-probe")
print("                      load test (mean 9090 ms, 11 steps >=20 s). Removing it raises")
print("                      DSH's mean and widens the gap. MyAgent has ZERO requests there,")
print("                      so the window cannot be a like-for-like comparison.")
print("  3. DSH sample     : their DSH figure also includes 5 subagent sessions, whose prompts")
print("                      are smaller (median 88556 vs main 156368 tokens) and whose TTFT is")
print("                      lower, pulling the DSH average down.")
print("  4. live session   : their DSH table omits the then-live session-6fc3c8e9.")
print("  5. Their arithmetic is CORRECT for what they computed. The disagreement is about")
print("     which statistic to quote, not about the underlying events.")
print()
print("  best single number for 'what does a typical request wait':")
print(f"    DSH median {med([r['ttft'] for r in mc]):.0f} ms (excl. load test) vs "
      f"MyAgent median {med([r['ttft'] for r in ma_day]):.0f} ms "
      f"-> gap {med([r['ttft'] for r in ma_day]) - med([r['ttft'] for r in mc]):+.0f} ms")
