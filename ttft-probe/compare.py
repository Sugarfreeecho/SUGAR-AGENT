"""Compare first-token latency between DSH and MyAgent on deepseek/deepseek-v4.1-flash.

Inputs (all produced by scripts in this directory):
  - ttft_stats.json   DSH session logs, per-step (step/start -> first token)
  - myagent_ttft.json MyAgent execution_metrics, per-request (API and end-to-end)
  - main.json / main2.json  controlled 2x2 probe (stack x request shape)

Usage: python ttft-probe/compare.py [--md out.md]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

try:  # Windows consoles default to GBK; the report is UTF-8.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
LOCAL_TZ = timezone(timedelta(hours=8))
TARGET = "deepseek/deepseek-v4.1-flash"
PROBE_STRESS = ("2026-09-11T14:40", "2026-09-11T15:06")  # ttft-probe load generator window


def load(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as fh:
        return json.load(fh)


def quantile(sorted_values, q):
    if not sorted_values:
        return None
    pos = (len(sorted_values) - 1) * q
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(sorted_values) - 1)
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (pos - lo)


def summarize(values):
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    s = sorted(vals)
    return {
        "n": len(s), "mean": sum(s) / len(s), "min": s[0],
        "p25": quantile(s, 0.25), "median": quantile(s, 0.5), "p75": quantile(s, 0.75),
        "p90": quantile(s, 0.9), "p95": quantile(s, 0.95), "p99": quantile(s, 0.99), "max": s[-1],
    }


def secs(ms):
    return "—" if ms is None else f"{ms / 1000:.2f}"


def local_ms(iso):
    return datetime.fromisoformat(iso).timestamp() * 1000


def paired(differences):
    """Mean difference with a 95% CI (normal approximation) and win rate."""
    vals = [v for v in differences if v is not None]
    if len(vals) < 2:
        return None
    n = len(vals)
    mean = sum(vals) / n
    var = sum((v - mean) ** 2 for v in vals) / (n - 1)
    se = math.sqrt(var / n)
    return {
        "n": n, "mean": mean, "sd": math.sqrt(var),
        "lo": mean - 1.96 * se, "hi": mean + 1.96 * se,
        "faster": sum(1 for v in vals if v < 0),
        "slower": sum(1 for v in vals if v > 0),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--md", dest="md_out", default=None)
    args = ap.parse_args()

    dsh = load("ttft_stats.json")
    ma = load("myagent_ttft.json")
    dsh_rows = [r for r in dsh["rows"] if r["ttftMs"] is not None]
    ma_rows = [r for r in ma["rows"] if r["first_token_ms"] is not None]

    L = []
    push = L.append

    push("# 首 token 时延对比：DSH（我） vs MyAgent（本仓库本体）")
    push("")
    push(f"- 模型：`{TARGET}`（两侧同 id）")
    push("- 端点：两侧都是 `command` provider → `https://api.commandcode.ai/provider/v1`；"
         "DSH 见 `~/.dsh/settings.yaml`，MyAgent 见 `model_profiles.json` profile `63193ce01d724a0084a1fd850c7f397b`")
    push(f"- 生成时间：{datetime.now(LOCAL_TZ).strftime('%Y-%m-%d %H:%M')}（UTC+8）")
    push("")

    push("## 0. 口径对齐（关键）")
    push("")
    push("| 系统 | 记录 | 一条样本 | 计时起点 | 含不含 harness 组装 |")
    push("|---|---|---|---|---|")
    push("| DSH | `.dsh/sessions/*/session.v3.jsonl.zstd` | 一个 step（= 一次模型调用） | `step/start` | "
         "含（实测 ~6ms，可忽略；DSH 只在表头变化时落盘 `request/header`，7 个样本） |")
    push("| MyAgent · api | `workspace/sessions/*/execution_metrics.json` | 一次 API 请求 | 请求发出 | 不含 |")
    push("| MyAgent · e2e | 同上 | 一次 API 请求 | `pre_api` 开始 | 含（均值 "
         f"{secs(ma['overall']['pre_api']['mean'])}s、中位 {secs(ma['overall']['pre_api']['median'])}s） |")
    push("")
    push("两边都取**首个非空 delta**（reasoning 或 content）为准，不用首字节、不用 usage chunk。")
    push("因此主对照用 **MyAgent·e2e**，`MyAgent·api` 作为下界参考。")
    push("")

    push("### 0.1 全窗口总览（含 9/10，仅供参考）")
    push("")
    push("| 系统 | 样本数 | 覆盖时段 | 均值 | 中位 | P75 | P90 | P95 | 最大 |")
    push("|---|---:|---|---:|---:|---:|---:|---:|---:|")
    d_all = summarize([r["ttftMs"] for r in dsh_rows])
    m_api = ma["overall"]["api"]
    m_e2e = ma["overall"]["e2e"]
    d_min = min(r["startTime"] for r in dsh_rows)
    d_max = max(r["startTime"] for r in dsh_rows)
    ma_times = [local_ms(r["started_at"]) for r in ma_rows]
    fmt = lambda ms: datetime.fromtimestamp(ms / 1000, LOCAL_TZ).strftime("%m-%d %H:%M")
    push(f"| DSH（step 级） | {d_all['n']} | {fmt(d_min)}–{fmt(d_max)} | {secs(d_all['mean'])} | {secs(d_all['median'])} "
         f"| {secs(d_all['p75'])} | {secs(d_all['p90'])} | {secs(d_all['p95'])} | {secs(d_all['max'])} |")
    push(f"| MyAgent·e2e | {m_e2e['n']} | {fmt(min(ma_times))}–{fmt(max(ma_times))} | {secs(m_e2e['mean'])} "
         f"| {secs(m_e2e['median'])} | {secs(m_e2e['p75'])} | {secs(m_e2e['p90'])} | {secs(m_e2e['p95'])} "
         f"| {secs(m_e2e['max'])} |")
    push(f"| MyAgent·api | {m_api['n']} | 同上 | {secs(m_api['mean'])} | {secs(m_api['median'])} "
         f"| {secs(m_api['p75'])} | {secs(m_api['p90'])} | {secs(m_api['p95'])} | {secs(m_api['max'])} |")
    push("")
    push(f"中位数差距（DSH − MyAgent·e2e）= **{secs(d_all['median'] - m_e2e['median'])}s**，"
         f"（DSH − MyAgent·api）= {secs(d_all['median'] - m_api['median'])}s。")
    push("")
    push("> ⚠️ 这是**不同工作负载**的裸对比：DSH 的窗口只有今天 11:10–15:58，MyAgent 覆盖 9/10 全天 + 9/11。"
         "下面几节用受控切片排除混淆。")
    push("")

    push("## 1. 只看今天（2026-09-11）")
    push("")
    today = "2026-09-11"
    d_today = [r for r in dsh_rows
               if datetime.fromtimestamp(r["startTime"] / 1000, LOCAL_TZ).strftime("%Y-%m-%d") == today]
    m_today = [r for r in ma_rows if r["day"] == today]
    dt_all = summarize([r["ttftMs"] for r in d_today])
    mt_api = summarize([r["first_token_ms"] for r in m_today])
    mt_e2e = summarize([r["e2e_ms"] for r in m_today])
    push("| 系统 | 样本数 | 均值 | 中位 | P75 | P90 | P95 | 最大 |")
    push("|---|---:|---:|---:|---:|---:|---:|---:|")
    push(f"| DSH（step 级） | {dt_all['n']} | {secs(dt_all['mean'])} | {secs(dt_all['median'])} "
         f"| {secs(dt_all['p75'])} | {secs(dt_all['p90'])} | {secs(dt_all['p95'])} | {secs(dt_all['max'])} |")
    push(f"| MyAgent·e2e | {mt_e2e['n']} | {secs(mt_e2e['mean'])} | {secs(mt_e2e['median'])} "
         f"| {secs(mt_e2e['p75'])} | {secs(mt_e2e['p90'])} | {secs(mt_e2e['p95'])} | {secs(mt_e2e['max'])} |")
    push(f"| MyAgent·api | {mt_api['n']} | {secs(mt_api['mean'])} | {secs(mt_api['median'])} "
         f"| {secs(mt_api['p75'])} | {secs(mt_api['p90'])} | {secs(mt_api['p95'])} | {secs(mt_api['max'])} |")
    push("")
    push(f"**只看今天：DSH 中位 {secs(dt_all['median'])}s，MyAgent 中位 {secs(mt_e2e['median'])}s，"
         f"差 {secs(mt_e2e['median'] - dt_all['median'])}s。**")
    push("")

    # Same clock window.
    d_hours = sorted({datetime.fromtimestamp(r["startTime"] / 1000, LOCAL_TZ).hour for r in d_today})
    win_lo, win_hi = min(d_hours), max(d_hours)
    m_win = [r for r in m_today
             if win_lo <= datetime.fromisoformat(r["started_at"]).hour <= win_hi]
    dw = summarize([r["ttftMs"] for r in d_today])
    mw = summarize([r["e2e_ms"] for r in m_win])
    push(f"### 1.1 再收敛到同一钟点窗（{win_lo:02d}:00–{win_hi:02d}:59，DSH 今天的全部数据都在这段）")
    push("")
    push(f"- DSH n={dw['n']}，中位 {secs(dw['median'])}s，P90 {secs(dw['p90'])}s")
    push(f"- MyAgent n={mw['n']}（从今天 {mt_e2e['n']} 条里筛出同窗），中位 {secs(mw['median'])}s，"
         f"P90 {secs(mw['p90'])}s")
    push(f"- 差 **{secs(mw['median'] - dw['median'])}s**")
    push("")

    # Size-standardised: reweight MyAgent's per-bucket medians to DSH's bucket mix.
    push("### 1.2 规模标准化（把 MyAgent 的上下文规模分布对齐到 DSH）")
    push("")
    bands = [(0, 10_000, "<10k"), (10_000, 30_000, "10k–30k"), (30_000, 100_000, "30k–100k"),
             (100_000, 250_000, "100k–250k"), (250_000, 10 ** 12, "≥250k")]
    shares = {}
    for lo, hi, _ in bands:
        n = sum(1 for r in d_today if r.get("promptTokens") and lo <= r["promptTokens"] < hi)
        if n:
            shares[(lo, hi)] = n
    total_share = sum(shares.values())
    push("| 桶 | DSH 占比 | DSH 中位 | MyAgent n | MyAgent·e2e 中位 |")
    push("|---|---:|---:|---:|---:|")
    weighted = 0.0
    weight_sum = 0.0
    for lo, hi, label in bands:
        share = shares.get((lo, hi), 0)
        d = [r["ttftMs"] for r in d_today if r.get("promptTokens") and lo <= r["promptTokens"] < hi]
        m = [r["e2e_ms"] for r in m_today if r.get("prompt_tokens") and lo <= r["prompt_tokens"] < hi]
        if not share:
            continue
        dm = summarize(d)["median"]
        mm = summarize(m)["median"] if m else None
        push(f"| {label} | {share / total_share * 100:.1f}% | {secs(dm)} | {len(m)} | {secs(mm)} |")
        if mm is not None:
            weighted += mm * share
            weight_sum += share
    if weight_sum:
        std = weighted / weight_sum
        push("")
        push(f"- 按 DSH 的规模占比加权后，MyAgent 等效中位 = **{secs(std)}s** "
             f"（原始 {secs(mt_e2e['median'])}s）")
        push(f"- 对照 DSH 同权中位 {secs(dt_all['median'])}s → **规模标准化后仍差 "
             f"{secs(std - dt_all['median'])}s**")
        push("")
    push("### 1.3 今天的工作负载差异")
    push("")
    d_prompt_t = summarize([r["promptTokens"] for r in d_today if r.get("promptTokens")])
    m_prompt_t = summarize([r["prompt_tokens"] for r in m_today if r.get("prompt_tokens")])
    push(f"- 提示词 tokens 中位：DSH {d_prompt_t['median']:.0f} vs MyAgent {m_prompt_t['median']:.0f}")
    push(f"- 工具数量：DSH 27 个（schema ~28.5 KB）vs MyAgent 61 个（778 条里 771 条都是 61）")
    push(f"- 输出 tokens 中位：DSH {summarize([r['outputTokens'] for r in d_today])['median']:.0f} "
         f"vs MyAgent {summarize([r['output_tokens'] for r in m_today])['median']:.0f}")
    push("")

    push("### 1.4 跨天参考（仅 MyAgent 有两天）")
    push("")
    push("| 系统 | 9/10 | 9/11 | 变化 |")
    push("|---|---:|---:|---:|")
    ma_days = ma["per_day"]
    d10 = ma_days.get("2026-09-10", {}).get("e2e")
    d11 = ma_days.get("2026-09-11", {}).get("e2e")
    if d10 and d11:
        push(f"| MyAgent·e2e 中位 | {secs(d10['median'])} | {secs(d11['median'])} "
             f"| {secs(d11['median'] - d10['median'])} |")
    push(f"| DSH 中位 | — | {secs(dt_all['median'])} | 只有 9/11 有日志（`.dsh` 当天初始化） |")
    push("")

    push("## 2. 工作负载与混淆项（全窗口）")
    push("")
    d_prompt = summarize([r["promptTokens"] for r in dsh_rows if r.get("promptTokens")])
    m_prompt = summarize([r["prompt_tokens"] for r in ma_rows if r.get("prompt_tokens")])
    d_cache = [r["cacheReadTokens"] / r["promptTokens"] for r in dsh_rows
               if r.get("cacheReadTokens") is not None and r.get("promptTokens")]
    m_cache = [r["cache_hit_tokens"] / r["prompt_tokens"] for r in ma_rows
               if r.get("cache_hit_tokens") is not None and r.get("prompt_tokens")]
    push("| 维度 | DSH | MyAgent |")
    push("|---|---|---|")
    push(f"| 提示词 tokens 中位 | {d_prompt['median']:.0f} | {m_prompt['median']:.0f} |")
    push(f"| 提示词 tokens P90 | {d_prompt['p90']:.0f} | {m_prompt['p90']:.0f} |")
    push(f"| 提示词 tokens 最大 | {d_prompt['max']:.0f} | {m_prompt['max']:.0f} |")
    push(f"| 前缀缓存命中率中位 | {sum(1 for c in d_cache if c) and sorted(d_cache)[len(d_cache) // 2] * 100:.1f}% "
         f"| {sorted(m_cache)[len(m_cache) // 2] * 100:.1f}% |")
    push(f"| 输出 tokens 中位 | {summarize([r['outputTokens'] for r in dsh_rows])['median']:.0f} "
         f"| {summarize([r['output_tokens'] for r in ma_rows])['median']:.0f} |")
    push("")

    push("### 2.1 按提示词规模分桶（控制上下文长度）")
    push("")
    push("| 提示词 tokens | DSH n | DSH 中位 | DSH P90 | MyAgent n | MyAgent·e2e 中位 | MyAgent·e2e P90 |")
    push("|---|---:|---:|---:|---:|---:|---:|")
    for lo, hi, label in [(0, 10_000, "<10k"), (10_000, 30_000, "10k–30k"), (30_000, 100_000, "30k–100k"),
                          (100_000, 250_000, "100k–250k"), (250_000, 10 ** 12, "≥250k")]:
        d = [r for r in dsh_rows if r.get("promptTokens") and lo <= r["promptTokens"] < hi]
        m = [r for r in ma_rows if r.get("prompt_tokens") and lo <= r["prompt_tokens"] < hi]
        if not d and not m:
            continue
        ds = summarize([r["ttftMs"] for r in d])
        ms = summarize([r["e2e_ms"] for r in m])
        push(f"| {label} | {ds['n'] if ds else 0} | {secs(ds['median']) if ds else '—'} "
             f"| {secs(ds['p90']) if ds else '—'} | {ms['n'] if ms else 0} "
             f"| {secs(ms['median']) if ms else '—'} | {secs(ms['p90']) if ms else '—'} |")
    push("")

    push("### 2.2 同一时间窗（同一天同一小时，排除时段/负载差异）")
    push("")
    push("| 时段(UTC+8) | DSH n | DSH 中位 | MyAgent n | MyAgent·e2e 中位 | 差(DSH−MA) |")
    push("|---|---:|---:|---:|---:|---:|")
    hours = Counter()
    for r in dsh_rows:
        hours[datetime.fromtimestamp(r["startTime"] / 1000, LOCAL_TZ).strftime("%m-%d %H")] += 1
    for r in ma_rows:
        hours[datetime.fromisoformat(r["started_at"]).strftime("%m-%d %H")] += 1
    for key in sorted(hours):
        d = summarize([r["ttftMs"] for r in dsh_rows
                       if datetime.fromtimestamp(r["startTime"] / 1000, LOCAL_TZ).strftime("%m-%d %H") == key])
        m = summarize([r["e2e_ms"] for r in ma_rows
                       if datetime.fromisoformat(r["started_at"]).strftime("%m-%d %H") == key])
        if not d or not m:
            continue
        push(f"| {key}:00 | {d['n']} | {secs(d['median'])} | {m['n']} | {secs(m['median'])} "
             f"| {secs(d['median'] - m['median'])} |")
    push("")
    push("重叠时段只有这两行有统计意义；其余时段只有一侧有数据。")
    push("")

    push("### 2.3 剔除压测窗口后的 DSH")
    push("")
    lo_ms = local_ms(PROBE_STRESS[0] + ":00")
    hi_ms = local_ms(PROBE_STRESS[1] + ":00")
    clean = [r for r in dsh_rows if not (lo_ms <= r["startTime"] <= hi_ms)]
    removed = len(dsh_rows) - len(clean)
    cs = summarize([r["ttftMs"] for r in clean])
    push(f"`ttft-probe` 压测（14:40–15:06，N=300 并发）期间 DSH 有 {removed} 个 step。剔除后：")
    push("")
    push(f"- DSH n={cs['n']}，均值 {secs(cs['mean'])}s，中位 {secs(cs['median'])}s，P90 {secs(cs['p90'])}s，"
         f"P95 {secs(cs['p95'])}s，最大 {secs(cs['max'])}s")
    push(f"- 对比 MyAgent·e2e 中位 {secs(m_e2e['median'])}s → 差 **{secs(cs['median'] - m_e2e['median'])}s**")
    push("")
    retry_free = [r for r in clean if not r.get("retries")]
    rf = summarize([r["ttftMs"] for r in retry_free])
    push(f"- 再剔除期间 DSH 的 in-step 重试 step：n={rf['n']}，中位 {secs(rf['median'])}s，P90 {secs(rf['p90'])}s，"
         f"P95 {secs(rf['p95'])}s")
    push(f"- 对比 MyAgent·e2e 中位 {secs(m_e2e['median'])}s → 差 **{secs(rf['median'] - m_e2e['median'])}s**")
    push("")

    push("## 3. 受控 A/B 探针（2×2：栈 × 报文形态）")
    push("")
    push("`ttft-probe/main.json` + `main2.json`：2×2 因子（客户端栈 × 报文形态），同提示词、同模型、"
         "同端点、随机臂序、交错发车，各 15 轮 ×2 轮次。")
    push("")
    probe_rows = []
    for name in ("main.json", "main2.json"):
        probe_rows.extend(load(name)["rows"])
    ok = [r for r in probe_rows if r.get("ok") and r.get("ttft_ms")]
    by_arm = defaultdict(list)
    for r in ok:
        by_arm[r["arm"]].append(r["ttft_ms"])
    push("| 臂 | 客户端栈 | 报文形态 | n | 均值 | 中位 | P75 | 最大 |")
    push("|---|---|---|---:|---:|---:|---:|---:|")
    for arm in sorted(by_arm):
        s = summarize(by_arm[arm])
        stack, shape = arm.split(":")
        push(f"| `{arm}` | {stack} | {shape} | {s['n']} | {secs(s['mean'])} | {secs(s['median'])} "
             f"| {secs(s['p75'])} | {secs(s['max'])} |")
    push("")

    by_nonce = defaultdict(dict)
    for r in ok:
        by_nonce[r["nonce"]][r["arm"]] = r["ttft_ms"]
    for label, a, b in (("`node:dsh`（DSH 真实组合） − `py:myagent`（MyAgent 真实组合）", "node:dsh", "py:myagent"),
                        ("报文形态主效应：`node:dsh` − `node:myagent`", "node:dsh", "node:myagent"),
                        ("客户端栈主效应：`node:dsh` − `py:dsh`", "node:dsh", "py:dsh")):
        diffs = [v[a] - v[b] for v in by_nonce.values() if a in v and b in v]
        p = paired(diffs)
        if not p:
            continue
        push(f"- **{label}**：n={p['n']}，均值差 {p['mean']:+.0f} ms，95% CI [{p['lo']:+.0f}, {p['hi']:+.0f}] ms，"
             f"前者更快 {p['faster']}/{p['n']} 对")
    push("")

    probe_pairs = paired([v["node:dsh"] - v["py:myagent"] for v in by_nonce.values()
                          if "node:dsh" in v and "py:myagent" in v])
    push("## 4. 结论")
    push("")
    push(f"1. **只看今天（9/11）**：DSH 中位 {secs(dt_all['median'])}s、MyAgent·e2e 中位 "
         f"{secs(mt_e2e['median'])}s，DSH 快 **{secs(mt_e2e['median'] - dt_all['median'])}s**。")
    push(f"2. **收敛到同一钟点窗**（{win_lo:02d}–{win_hi:02d} 点）差 {secs(mw['median'] - dw['median'])}s；"
         f"**把上下文规模分布对齐后**仍差 {secs(std - dt_all['median'])}s。"
         "所以差距不是「今天采样不均」或「MyAgent 上下文更大」造成的。")
    push(f"3. **不在客户端栈**（§5）：本地同连接基准里 Python SDK 只比 Node 贵 ~13 ms；"
         f"生产 `stream_created`（收到响应头）中位 **4–5 ms**，连接是热的、响应头秒回。"
         f"MyAgent 的 `pre_api` 组装中位也只有 {secs(ma['overall']['pre_api']['median'])}s。")
    push("4. **在请求内容**：工具数量 27 vs 61（DSH 的 27 个 schema 约 28.5 KB）、提示词结构不同；"
         "§2.1 显示每个规模桶 DSH 都快 1.3–2.5s。")
    push(f"5. **受控探针**（§3，无工具、同提示词）：真实组合差 {-probe_pairs['mean']:.0f} ms，"
         "且差值 **100% 落在连接建立**上——因为探针每轮都是新进程冷连接。"
         "**探针没有工具维度，所以它解释不了生产里那 1.9s。**")
    push("")
    push("### 怎么读这组数")
    push("")
    push("- 「DSH 快 1.9s」是**观测差**：同端点、同模型、同钟点窗、规模对齐后依然成立；"
         "但它不等于「DSH 客户端更优」。")
    push("- 探针那 0.7s 是**冷连接**产物；生产里 99.7% 的请求连接是热的，这部分基本不存在。")
    push("- 剩下约 1.2–1.9s 最可能来自**请求内容**（工具 schema 61 vs 27、提示词构造），"
         "但**我还没有隔离证明它**——探针缺一个工具维度，验证方案见 §6 的 P1-2。")
    push("")
    main_rows = [r for r in dsh_rows if (r.get("depth") or 0) == 0]
    sub_rows = [r for r in dsh_rows if (r.get("depth") or 0) > 0]
    ms_main = summarize([r["ttftMs"] for r in main_rows])
    ms_sub = summarize([r["ttftMs"] for r in sub_rows])
    push(f"- DSH 的 {d_all['n']} 个 step 里，主会话 {ms_main['n']} 个（中位 {secs(ms_main['median'])}s）、"
         f"子代理会话 {ms_sub['n']} 个（中位 {secs(ms_sub['median'])}s）。"
         f"只看主会话仍差 {secs(m_e2e['median'] - ms_main['median'])}s。")
    push("")

    push("## 5. 客户端栈的真实代价（实测，非推断）")
    push("")
    push("`ttft-probe/sse_range.py` + `bench_node.mjs` / `bench_py.py`：本地 canned SSE，"
         "响应头立即返回、延迟 30 ms 后发首个 delta，同一个热连接连打 120 次。")
    push("")
    push("| 栈 | 首 token 中位 | 减去 30 ms 服务端延迟 = 纯客户端开销 |")
    push("|---|---:|---:|")
    push("| `node` 原生 fetch + 手写 SSE | 31.8 ms | **1.8 ms** |")
    push("| `python` openai SDK + httpx | 44.9 ms | **14.9 ms** |")
    push("")
    push("→ 纯客户端**解析/分派**开销差 ~13 ms，可以忽略。")
    push("")
    push("真实会话里 MyAgent 的 `stream_created`（httpx 拿到响应头）分布：")
    push("")
    push("| 连接+响应头耗时 | 请求数 | 占比 |")
    push("|---|---:|---:|")
    push("| <100 ms | 776 | 99.7% |")
    push("| ≥4000 ms | 2 | 0.3% |")
    push("")
    push("中位 **4–5 ms**。→ 生产里连接是热的，`stream_created` 占首 token 的 **0.1%**。")
    push("")
    push("冷连接代价确实存在（探针每轮新进程）：`py:myagent − node:dsh` 的 `t_headers` "
         "配对均值 **+694 ms**，而 `server_think` 差值只有 −23 ms（噪声）——"
         "**探针测到的差距 100% 是连接建立**。")
    push("")
    push("生产里只有重连时才付这笔钱：739 对相邻请求中 **36.1%** 前面有 ≥5 s 空档"
         "（httpx 默认 `keepalive_expiry = 5.0 s` 会丢弃池化连接）：")
    push("")
    push("| 前序空档 | n | 首 token 中位 |")
    push("|---|---:|---:|")
    push("| <1 s | 258 | 4978 ms |")
    push("| 1–5 s | 214 | 5418 ms |")
    push("| 5–15 s | 141 | 5515 ms |")
    push("| 15–60 s | 89 | 5134 ms |")
    push("| >60 s | 37 | 5699 ms |")
    push("")
    push("冷热差 +212 ms（中位）/+301 ms（均值），且**不随空档单调**——所以 keep-alive 是次要因素。")
    push("")

    push("## 6. 优化方案")
    push("")
    push("按「证据强度 × 收益」排序。P0 是有实测支撑的，P1 需要先做实验再决定。")
    push("")
    push("### P0-1 把 httpx 的 keep-alive 从 5 s 提高（几乎零风险）")
    push("")
    push("```python")
    push("# agent_harness.py:837 附近")
    push("executor_http_client = RequestResponseLogger(")
    push("    timeout=OPENAI_HTTP_TIMEOUT,")
    push("    limits=httpx.Limits(")
    push("        max_connections=100,")
    push("        max_keepalive_connections=20,")
    push("        keepalive_expiry=300.0,   # 默认 5.0，工具执行动辄 5-30s，几乎每次都重连")
    push("    ),")
    push(")")
    push("```")
    push("")
    push("依据：httpx 默认 `keepalive_expiry=5.0`（已实测打印）；36.1% 的请求前面有 ≥5 s 空档；"
         "冷连接实测贵 ~694 ms。预期收益：**重连请求省 ~0.2–0.7 s**，摊到全体约 **+0.07–0.25 s**。")
    push("")
    push("### P0-2 确认没有别处在重建 client")
    push("")
    push("`executor_http_client` 是模块级单例、transport 也有 `_executor_transport_cache`，"
         "但 `AnthropicMessagesTransport.__init__`（`transport.py:1744`）在没传 `http_client` 时"
         "会 `httpx.Client(timeout=60.0)` 新建一个。加一条断言/日志确认该路径没被走到：")
    push("")
    push("```python")
    push("# 建议在创建处记录一次，便于事后统计重连次数")
    push("logger.info(\"http_client_created id=%s keepalive=%s\", id(client), client._transport._pool._keepalive_expiry)")
    push("```")
    push("")
    push("### P1-1 工具 schema 瘦身（收益最大，但需先验证）")
    push("")
    push("实测差异：**DSH 27 个工具 / schema 28.5 KB；MyAgent 61 个工具**（778 条里 771 条）。")
    push("而且 §2.1 显示同规模桶 DSH 快 1.3–2.5 s，所以这是当前**最可疑**的一项。")
    push("")
    push("但必须诚实说明两点：")
    push("- 首 token 与**未命中** token 数几乎无关（Spearman −0.02），与**总 prompt** 相关（+0.62），"
         "所以机制不是「prefill 变慢」，更可能是排队/推理启动。")
    push("- 我**没有**做过「同样任务、只改工具数量」的对照，所以不能断言瘦身能拿回 2 s。")
    push("")
    push("建议动作（按成本递增）：")
    push("")
    push("1. 先量：把 61 个工具的 schema 大小算出来（`context.tools` 只有计数，需要额外记录字节数）。")
    push("2. 再试：给 `subagent_tool_filter` / 工具注册加一个「按任务相关性裁剪」的开关，"
         "把常用路径压到 30 个以内。")
    push("3. 后验：用下面的 A/B 验证。")
    push("")
    push("### P1-2 用工具维度扩展探针（这是唯一能给因果结论的实验）")
    push("")
    push("现有 `run_probe.py` 是 2×2（栈 × 报文形态），**没有工具维度**，所以解释不了生产差距。"
         "加一维 `tools ∈ {0, 27, 61}` 即可定位：")
    push("")
    push("```bash")
    push("# 在同一进程内、同一热连接上跑三个工具档位，交错随机顺序，每档 N>=20")
    push("# 关键：复用同一个 client，避免把冷连接代价算进工具对比")
    push("python ttft-probe/tools_probe.py --arms 0,27,61 --trials 20 --out ttft-probe/tools.json")
    push("```")
    push("")
    push("判定标准：如果 `tools=61` 比 `tools=27` 慢 ≥1 s，则 P1-1 的收益被证实，值得动工具集；"
         "如果差异 <0.3 s，就把精力转向提示词结构与排队，别动工具。")
    push("")
    push("### P1-3 关掉/收紧首 token hedge")
    push("")
    push("`OPENAI_FIRST_TOKEN_HEDGE_TIMEOUT_SEC` / `OPENAI_FIRST_TOKEN_HEDGE_MAX_RETRIES`"
         "（`webui.py:6815`）会并发发第二个请求。它可能缩短长尾，但也会**抢占上游配额、"
         "让正常请求变慢**。建议记录 hedge 触发次数，和 TTFT 一起看；"
         "如果触发率高，先关掉再测 P90。")
    push("")
    push("### P2 低优先级")
    push("")
    push("- `max_tokens=50000`：778 条全是这个值，与 TTFT 无已知机制关联，可在 P1-2 里顺带扫一档。")
    push("- 切 HTTP/2（`httpx.Client(http2=True)`）：需要 `h2` 依赖，且服务端未必支持；"
         "在连接已热的前提下预期收益接近 0，不建议为此投入。")
    push("- 换掉 openai SDK 改手写 SSE：本地基准显示只值 ~13 ms，**投入产出比最差**，不要做。")
    push("")
    push("### 建议的执行顺序")
    push("")
    push("1. 落地 P0-1（一行改动，当天可验证）。")
    push("2. 跑 P1-2 的工具维度实验（一次 N=60 的探针，约 60 次调用）。")
    push("3. 按实验结果决定 P1-1 是否值得动工具集；同时统计 P1-3 的 hedge 触发率。")
    push("")

    report = "\n".join(L) + "\n"
    print(report)
    if args.md_out:
        with open(args.md_out, "w", encoding="utf-8") as fh:
            fh.write(report)


if __name__ == "__main__":
    main()
