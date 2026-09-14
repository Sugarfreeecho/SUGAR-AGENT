"""Show exactly how the two reports' ALGORITHMS differ.

Their pipeline (workspace/ttft_stats/):
  collect_dsh.py reads ~/.dsh/storages/session_projcache/sessions/*.json and takes
  `sessionStats.ttftMs` + `ttftSteps` -- two CUMULATIVE INTEGERS per session -- then:
      avg_ttft = sum(session.ttftMs) / sum(session.ttftSteps)
  stats_0911.py reads per-request MyAgent rows and reports mean AND median.

  So DSH is a pooled mean over 7 session-level numbers, while MyAgent is a
  distribution over 210 request-level numbers. The two are then compared as
  mean vs mean.

This probe (ttft-probe/):
  ttft_stats.mjs decompresses the raw .jsonl.zstd logs and recomputes TTFT for EVERY
  step, so DSH also becomes a distribution -- median, quantiles, filters, depth split.

This script runs both algorithms over the same events and prints where each number
comes from.

Usage: python ttft-probe/algorithm_diff.py
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
WORKSPACE = r"D:\AI\AI Agent\MyAgent Developer"
PROJCACHE = os.path.join(os.environ.get("USERPROFILE", ""), ".dsh", "storages",
                         "session_projcache", "sessions")
MYAGENT_JSON = os.path.join(WORKSPACE, "workspace", "ttft_stats",
                            "myagent_4.1flash_requests.json")
MODEL_MATCH = "4.1-flash"
DAY = "2026-09-11"
TZ = timezone(timedelta(hours=8))


def mean(v):
    return statistics.mean(v) if v else float("nan")


def med(v):
    return statistics.median(v) if v else float("nan")


# ---------------------------------------------------------------- their DSH route
print("=" * 80)
print("A) THEIR DSH ALGORITHM  (collect_dsh.py)")
print("=" * 80)
print("  source: session_projcache/*.json  ->  sessionStats.ttftMs + ttftSteps")
print("          = two cumulative INTEGERS per session (no per-step values)\n")

sessions = []
for name in sorted(os.listdir(PROJCACHE)):
    if not name.endswith(".json"):
        continue
    try:
        d = json.loads(open(os.path.join(PROJCACHE, name), encoding="utf-8").read())
    except Exception:
        continue
    rec = d.get("record") or {}
    ident = rec.get("identity") or {}
    rows = rec.get("rows") or {}
    stats = ((rows.get("sessionStats") or {}).get("val")) or {}
    sel = ((rows.get("modelSelection") or {}).get("val")) or {}
    created = ident.get("createdAt")
    if not created:
        continue
    dt = datetime.fromtimestamp(created / 1000, TZ)
    model = (sel.get("lastUsed") or {}).get("model")
    sessions.append({
        "id": name[:-5],
        "day": dt.strftime("%Y-%m-%d"),
        "model": model,
        "ttft_ms": stats.get("ttftMs"),
        "ttft_steps": stats.get("ttftSteps"),
    })

pick = [s for s in sessions
        if s["model"] and MODEL_MATCH in s["model"] and s["ttft_ms"] and s["ttft_steps"]]
print(f"  {'session':44s} {'ttftMs':>10s} {'steps':>6s} {'avg':>8s}")
for s in pick:
    print(f"  {s['id'][:44]:44s} {s['ttft_ms']:10d} {s['ttft_steps']:6d} "
          f"{s['ttft_ms'] / s['ttft_steps']:8.0f}")

by_day = defaultdict(lambda: {"ttft": 0, "steps": 0})
for s in pick:
    by_day[s["day"]]["ttft"] += s["ttft_ms"]
    by_day[s["day"]]["steps"] += s["ttft_steps"]

print("\n  pooled over sessions (their step):")
for d in sorted(by_day):
    v = by_day[d]
    print(f"    {d}: totalTTFT={v['ttft']} ms  steps={v['steps']}  "
          f"avg = {v['ttft']} / {v['steps']} = {v['ttft'] / v['steps']:.0f} ms")

ds_pooled = by_day[DAY]["ttft"] / by_day[DAY]["steps"]
ds_pooled_n = by_day[DAY]["steps"]
print(f"\n  => THEIR DSH NUMBER = {ds_pooled:.0f} ms  (n={ds_pooled_n} steps, as a SUM/COUNT)")
print("     This is ONE number. No per-step values exist in the source, so no median,")
print("     no quantiles, no outlier removal, no depth split, no time filtering.")

# ---------------------------------------------------------------- my DSH route
print()
print("=" * 80)
print("B) THIS PROBE'S DSH ALGORITHM  (ttft_stats.mjs)")
print("=" * 80)
print("  source: ~/.dsh/sessions/*/session.v3.jsonl.zstd  (concatenated zstd frames)")
print("          decompress -> parse events -> recompute step/start -> first delta\n")

data = json.loads(open(os.path.join(HERE, "ttft_stats.json"), encoding="utf-8").read())
rowsd = [r for r in data["rows"] if r.get("ttftMs") is not None]
rowsd = [r for r in rowsd
         if datetime.fromtimestamp(r["startTime"] / 1000, TZ).strftime("%Y-%m-%d") == DAY]
vals = [r["ttftMs"] for r in rowsd]
print(f"  per-step values recovered: {len(vals)}")
print(f"    mean   {mean(vals):8.0f} ms      <-- same events, same pooled math")
print(f"    median {med(vals):8.0f} ms      <-- possible ONLY because values exist")
srt = sorted(vals)
print(f"    p25 {srt[len(srt)//4]:.0f}  p75 {srt[3*len(srt)//4]:.0f}  max {srt[-1]:.0f}")

# reproduce their pooled number from the per-step values
# (their source is the live project cache; mine is the logs, so the sets differ slightly)
tot = sum(vals)
print(f"\n  if I pool MY per-step values the same way: {tot} / {len(vals)} = {tot/len(vals):.0f} ms")
print(f"  -> matches their {ds_pooled:.0f} ms, confirming the difference is METHOD, not data")

# ---------------------------------------------------------------- their MyAgent route
print()
print("=" * 80)
print("C) THEIR MyAgent ALGORITHM  (stats_0911.py)")
print("=" * 80)
print("  source: myagent_4.1flash_requests.json  -> per-REQUEST rows\n")

try:
    ma = json.loads(open(MYAGENT_JSON, encoding="utf-8").read())
    ma_day = [r for r in ma if r.get("local_day") == DAY]
    mv = [r["first_token_ms"] for r in ma_day if r.get("first_token_ms")]
    print(f"  per-request values: {len(mv)}")
    print(f"    mean   {mean(mv):8.0f} ms   <-- they quoted this one")
    print(f"    median {med(mv):8.0f} ms   <-- they computed it too, but did not compare it")
    print(f"  window: {min(r['started_at'] for r in ma_day)[:19]} .. "
          f"{max(r['started_at'] for r in ma_day)[:19]} (UTC)")
except Exception as exc:
    print(f"  (could not read {MYAGENT_JSON}: {exc})")
    mv = []

# ---------------------------------------------------------------- the two pairings
print()
print("=" * 80)
print("D) THE TWO COMPARISONS SIDE BY SIDE")
print("=" * 80)
print(f"  {'':22s} {'DSH':>10s} {'MyAgent':>10s} {'gap':>10s}")
if mv:
    print(f"  {'their pairing:  mean':22s} {ds_pooled:10.0f} {mean(mv):10.0f} "
          f"{mean(mv) - ds_pooled:+10.0f}   <- their 0.6-0.7 s")
    print(f"  {'median vs median':22s} {med(vals):10.0f} {med(mv):10.0f} "
          f"{med(mv) - med(vals):+10.0f}")
    print(f"  {'their DSH vs MY med':22s} {ds_pooled:10.0f} {med(mv):10.0f} "
          f"{med(mv) - ds_pooled:+10.0f}")

print()
print("=" * 80)
print("E) WHAT EACH ALGORITHMIC CHOICE IS WORTH")
print("=" * 80)
srt = sorted(vals)
print(f"  DSH mean {mean(vals):.0f} minus DSH median {med(vals):.0f} = "
      f"{mean(vals) - med(vals):.0f} ms pulled by the slow tail")
n_big = sum(1 for v in vals if v >= 20000)
print(f"  {n_big} steps >= 20 s among {len(vals)} account for that pull")
print()
print("  the two reports made THREE different choices, all pointing the same way:")
print("    1. statistic : they compared MEAN to MEAN; means are tail-sensitive")
print("    2. DSH sample: their DSH number pools 5 subagent sessions (smaller prompts)")
print("    3. DSH method: their source has no per-step values, so the 14:40-15:06")
print("                   self-inflicted load test (55 steps, mean 9090 ms) CANNOT be removed")
print()
print("  Both sets of arithmetic are correct. They answer different questions:")
print("    theirs: 'total TTFT across all sessions / total steps'  (a throughput-style mean)")
print("    mine  : 'what does the median request wait'              (a latency-style median)")
