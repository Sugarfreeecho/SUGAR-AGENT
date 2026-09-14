"""Collect MyAgent per-request first-token latency from execution_metrics.json.

MyAgent records `first_token_ms` as `first_delta.ms_since_api_start` (= API request
sent -> first delta) and `phases.pre_api.total_ms` as the harness-side prompt build
before that request. DSH's session-stats TTFT instead spans `step/start` -> first
token, so it already includes the harness-side build. Both bases are emitted here so
the two harnesses can be compared on like-for-like terms.

Usage: python ttft-probe/myagent_ttft.py [--model <id>] [--json out.json] [--md out.md]
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta

WORKSPACE = r"D:\AI\AI Agent\MyAgent Developer"
SESSIONS = os.path.join(WORKSPACE, "workspace", "sessions")
LOCAL_TZ = timezone(timedelta(hours=8))


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--model", default="deepseek/deepseek-v4.1-flash")
    p.add_argument("--json", dest="json_out", default=None)
    p.add_argument("--md", dest="md_out", default=None)
    return p.parse_args()


def local_dt(value: str | None):
    if not value:
        return None
    try:
        text = value.replace("Z", "+00:00")
        return datetime.fromisoformat(text).astimezone(LOCAL_TZ)
    except Exception:
        return None


def quantile(sorted_values, q):
    if not sorted_values:
        return None
    pos = (len(sorted_values) - 1) * q
    lo, hi = int(pos), min(int(pos) + 1, len(sorted_values) - 1)
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (pos - lo)


def summarize(values):
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    s = sorted(vals)
    return {
        "n": len(s),
        "mean": sum(s) / len(s),
        "min": s[0],
        "p25": quantile(s, 0.25),
        "median": quantile(s, 0.5),
        "p75": quantile(s, 0.75),
        "p90": quantile(s, 0.9),
        "p95": quantile(s, 0.95),
        "p99": quantile(s, 0.99),
        "max": s[-1],
    }


def secs(ms):
    return "—" if ms is None else f"{ms / 1000:.2f}"


def collect(model_filter: str):
    rows = []
    missing_first = 0
    missing_pre = 0
    other_models = Counter()
    files = glob.glob(os.path.join(SESSIONS, "*", "execution_metrics.json"))
    for path in files:
        try:
            data = json.loads(open(path, encoding="utf-8").read())
        except Exception:
            continue
        session_id = data.get("session_id") or os.path.basename(os.path.dirname(path))
        for run in data.get("runs", []):
            for req in run.get("requests", []):
                model = req.get("model")
                if not model:
                    events = ((req.get("phases") or {}).get("llm_stream") or {}).get("events") or []
                    for ev in events:
                        if ev.get("model"):
                            model = ev["model"]
                            break
                if model != model_filter:
                    other_models[model] += 1
                    continue
                first = req.get("first_token_ms")
                if first is None:
                    missing_first += 1
                pre = ((req.get("phases") or {}).get("pre_api") or {}).get("total_ms")
                if pre is None:
                    missing_pre += 1
                started = local_dt(req.get("started_at"))
                usage = req.get("usage") or {}
                ctx = req.get("context") or {}
                rows.append({
                    "session": session_id,
                    "run_id": run.get("run_id"),
                    "react_iter": req.get("react_iter"),
                    "status": req.get("status"),
                    "started_at": started.isoformat() if started else None,
                    "day": started.strftime("%Y-%m-%d") if started else None,
                    "hour": started.hour if started else None,
                    "first_token_ms": first,
                    "pre_api_ms": pre,
                    "e2e_ms": None if first is None or pre is None else pre + first,
                    "duration_ms": req.get("duration_ms"),
                    "prompt_tokens": usage.get("prompt_tokens"),
                    "cache_hit_tokens": usage.get("prompt_cache_hit_tokens"),
                    "output_tokens": usage.get("completion_tokens"),
                    "estimated_tokens": ctx.get("estimated_tokens"),
                    "messages": ctx.get("messages"),
                    "tools": ctx.get("tools"),
                    "wall_ms": run.get("wall_ms"),
                    "user_preview": (run.get("user_preview") or "")[:60],
                })
    return rows, missing_first, missing_pre, other_models, len(files)


def main():
    args = parse_args()
    rows, missing_first, missing_pre, other_models, nfiles = collect(args.model)
    rows = [r for r in rows if r["first_token_ms"] is not None]

    lines = []
    push = lines.append
    push("# MyAgent first-token latency (per API request)")
    push("")
    push(f"- Metrics files scanned: {nfiles} (`{SESSIONS}\\*\\execution_metrics.json`)")
    push(f"- Model filter: `{args.model}`")
    push(f"- Requests on the filtered model with a recorded first token: {len(rows)}")
    push(f"- Dropped (no `first_token_ms`): {missing_first}; missing `pre_api.total_ms`: {missing_pre}")
    push("- Bases: **api** = `first_token_ms` (request sent -> first delta); "
         "**e2e** = `pre_api.total_ms + first_token_ms` (harness build included, comparable to DSH `ttftMs`)")
    push("")

    by_day = defaultdict(list)
    for r in rows:
        by_day[r["day"]].append(r)

    push("## Per-day")
    push("")
    push("| day | requests | api mean | api median | api p90 | api max | e2e mean | e2e median | e2e p90 | e2e max |")
    push("|---|---|---|---|---|---|---|---|---|---|")
    for day in sorted(by_day):
        rs = by_day[day]
        a = summarize([r["first_token_ms"] for r in rs])
        e = summarize([r["e2e_ms"] for r in rs])
        push(f"| {day} | {len(rs)} | {secs(a['mean'])} | {secs(a['median'])} | {secs(a['p90'])} | {secs(a['max'])} "
             f"| {secs(e['mean'])} | {secs(e['median'])} | {secs(e['p90'])} | {secs(e['max'])} |")
    a = summarize([r["first_token_ms"] for r in rows])
    e = summarize([r["e2e_ms"] for r in rows])
    push(f"| **all** | {len(rows)} | {secs(a['mean'])} | {secs(a['median'])} | {secs(a['p90'])} | {secs(a['max'])} "
         f"| {secs(e['mean'])} | {secs(e['median'])} | {secs(e['p90'])} | {secs(e['max'])} |")
    push("")
    push("All figures seconds.")
    push("")
    push("## Prompt-build share of the wait (`pre_api.total_ms`)")
    push("")
    pre = summarize([r["pre_api_ms"] for r in rows])
    push(f"- mean {secs(pre['mean'])}s, median {secs(pre['median'])}s, p90 {secs(pre['p90'])}s, max {secs(pre['max'])}s "
         f"of a {secs(e['mean'])}s end-to-end mean")
    push("")

    push("## Per-session")
    push("")
    push("| day | session | requests | api mean | api median | api p90 | e2e mean | topic |")
    push("|---|---|---|---|---|---|---|---|")
    by_sess = defaultdict(list)
    for r in rows:
        by_sess[(r["day"], r["session"])].append(r)
    for key in sorted(by_sess):
        rs = by_sess[key]
        a = summarize([r["first_token_ms"] for r in rs])
        e = summarize([r["e2e_ms"] for r in rs])
        push(f"| {key[0]} | {key[1]} | {len(rs)} | {secs(a['mean'])} | {secs(a['median'])} | {secs(a['p90'])} "
             f"| {secs(e['mean'])} | {rs[0]['user_preview']} |")
    push("")

    push("## Histogram (api basis, ms)")
    push("")
    buckets = [(0, 3000), (3000, 4000), (4000, 5000), (5000, 6000), (6000, 8000), (8000, 10000),
               (10000, 15000), (15000, 10 ** 12)]
    for lo, hi in buckets:
        n = sum(1 for r in rows if lo <= r["first_token_ms"] < hi)
        label = f"{lo}-{hi}" if hi < 10 ** 12 else f">={lo}"
        push(f"- {label}: {n}")
    push("")

    push("## By hour (local)")
    push("")
    push("| hour | requests | api median | e2e median | api max |")
    push("|---|---|---|---|---|")
    by_hour = defaultdict(list)
    for r in rows:
        by_hour[r["hour"]].append(r)
    for hour in sorted(by_hour, key=lambda x: (x is None, x)):
        rs = by_hour[hour]
        hs = summarize([r["first_token_ms"] for r in rs])
        he = summarize([r["e2e_ms"] for r in rs])
        push(f"| {hour:02d}:00 | {len(rs)} | {secs(hs['median'])} | {secs(he['median'])} | {secs(hs['max'])} |")
    push("")

    push("## Slowest requests (api basis, top 15)")
    push("")
    push("| session | iter | started (local) | api s | pre_api s | e2e s | prompt tokens | output tokens |")
    push("|---|---|---|---|---|---|---|---|")
    for r in sorted(rows, key=lambda x: -x["first_token_ms"])[:15]:
        push(f"| {r['session']} | {r['react_iter']} | {r['started_at']} | {secs(r['first_token_ms'])} "
             f"| {secs(r['pre_api_ms'])} | {secs(r['e2e_ms'])} | {r['prompt_tokens']} | {r['output_tokens']} |")
    push("")

    report = "\n".join(lines) + "\n"
    print(report)

    a = summarize([r["first_token_ms"] for r in rows])
    e = summarize([r["e2e_ms"] for r in rows])

    if args.json_out:
        payload = {
            "model": args.model,
            "generated_at": datetime.now(LOCAL_TZ).isoformat(),
            "workspace": WORKSPACE,
            "counts": {"requests": len(rows), "dropped_no_first_token": missing_first},
            "per_day": {d: {"api": summarize([r["first_token_ms"] for r in rs]),
                            "e2e": summarize([r["e2e_ms"] for r in rs]),
                            "n": len(rs)}
                        for d, rs in by_day.items()},
            "overall": {"api": a, "e2e": e, "pre_api": pre},
            "rows": rows,
        }
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
    if args.md_out:
        with open(args.md_out, "w", encoding="utf-8") as fh:
            fh.write(report)


if __name__ == "__main__":
    main()
