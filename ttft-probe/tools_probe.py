"""Tool-count axis probe: does tool-schema weight actually move first-token latency?

The existing 2x2 probe (run_probe.py) has stack x request-shape axes but NO tools axis,
so it cannot explain the production gap. This runs one client, one warm connection, and
cycles the same prompt through several tool-schema sizes in randomized order, so the
only thing changing between arms is the tool block.

NOT YET RUN: it spends real API calls (arms x trials). Review the arms first.

Usage:
  python ttft-probe/tools_probe.py --trials 20 --arms 0,27,61
  python ttft-probe/tools_probe.py --trials 20 --arms 0,27,61 --dry-run   # prints payload sizes only
"""
from __future__ import annotations

import argparse
import json
import os
import random
import statistics
import sys
import time
from pathlib import Path

import httpx
from openai import OpenAI

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = Path(__file__).parent
MODEL = os.environ.get("PROBE_MODEL", "deepseek/deepseek-v4.1-flash")
BASE = os.environ.get("PROBE_BASE_URL", "https://api.commandcode.ai/provider/v1")
KEY = os.environ.get("COMMAND_API_KEY") or os.environ.get("PROBE_API_KEY") or ""
PROMPT = "Reply with the single word: ok"


def synthetic_tool(index: int) -> dict:
    """A tool schema of realistic weight (~1 KB), unique per index."""
    return {
        "type": "function",
        "function": {
            "name": f"tool_{index:02d}_operation",
            "description": (
                f"Performs operation {index} against the workspace. Use this when the user asks "
                "for the corresponding capability; it accepts a path, optional recursion depth, "
                "an encoding hint, and a result limit."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute or workspace-relative path."},
                    "recursive": {"type": "boolean", "description": "Descend into directories."},
                    "depth": {"type": "integer", "description": "Maximum recursion depth.", "minimum": 0},
                    "encoding": {"type": "string", "enum": ["utf-8", "utf-16", "latin-1"]},
                    "limit": {"type": "integer", "description": "Maximum results to return."},
                    "pattern": {"type": "string", "description": "Optional glob or regex filter."},
                },
                "required": ["path"],
                "additionalProperties": False,
            },
        },
    }


def arm_tools(count: int) -> list[dict]:
    return [synthetic_tool(i) for i in range(count)]


def build_client() -> OpenAI:
    http_client = httpx.Client(
        timeout=120.0,
        limits=httpx.Limits(max_connections=10, max_keepalive_connections=10, keepalive_expiry=300.0),
    )
    return OpenAI(api_key=KEY, base_url=BASE, http_client=http_client, max_retries=0, timeout=120.0)


def one(client: OpenAI, tools: list[dict]) -> dict:
    kwargs: dict = {
        "model": MODEL,
        "messages": [{"role": "user", "content": PROMPT}],
        "stream": True,
        "stream_options": {"include_usage": True},
        "reasoning_effort": "max",
        "max_tokens": 50000,
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
    t0 = time.perf_counter()
    stream = client.chat.completions.create(**kwargs)
    t_headers = time.perf_counter()
    ttft = None
    for chunk in stream:
        if ttft is None:
            for choice in (getattr(chunk, "choices", None) or []):
                delta = getattr(choice, "delta", None)
                if delta and (getattr(delta, "reasoning_content", None)
                              or getattr(delta, "reasoning", None)
                              or getattr(delta, "content", None)):
                    ttft = time.perf_counter()
                    break
    stream.close()
    return {
        "ttft_ms": None if ttft is None else (ttft - t0) * 1000,
        "t_headers_ms": (t_headers - t0) * 1000,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", default="0,27,61", help="comma-separated tool counts")
    ap.add_argument("--trials", type=int, default=20)
    ap.add_argument("--warmup", type=int, default=3)
    ap.add_argument("--seed", type=int, default=20260911)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    arms = [int(x) for x in args.arms.split(",") if x.strip()]
    toolsets = {n: arm_tools(n) for n in arms}

    print("payload weight per arm:")
    for n in arms:
        chars = len(json.dumps(toolsets[n]))
        print(f"  tools={n:3d}: schema {chars:7d} chars (~{chars // 4:6d} tokens estimated)")
    if args.dry_run:
        print("\ndry run: no requests sent")
        return 0

    if not KEY:
        print("\nerror: no API key (set COMMAND_API_KEY or PROBE_API_KEY)", file=sys.stderr)
        return 2

    client = build_client()
    for _ in range(args.warmup):
        one(client, toolsets[arms[0]])

    rng = random.Random(args.seed)
    order = [n for _ in range(args.trials) for n in arms]
    rng.shuffle(order)

    rows = []
    for i, n in enumerate(order):
        try:
            r = one(client, toolsets[n])
        except Exception as exc:
            rows.append({"tools": n, "error": str(exc)[:200]})
            continue
        r["tools"] = n
        r["trial"] = i
        rows.append(r)
        print(f"  [{i + 1}/{len(order)}] tools={n:3d} ttft={r['ttft_ms']:.0f} ms "
              f"headers={r['t_headers_ms']:.0f} ms")

    print("\n=== summary ===")
    by_arm = {}
    for n in arms:
        v = [r["ttft_ms"] for r in rows if r.get("tools") == n and r.get("ttft_ms") is not None]
        if not v:
            continue
        by_arm[n] = v
        s = sorted(v)
        print(f"tools={n:3d}: n={len(v):3d} mean={statistics.mean(v):7.0f} "
              f"median={statistics.median(v):7.0f} p90={s[min(len(s) - 1, int(0.9 * len(s)))]:7.0f}")

    if 0 in by_arm and arms[-1] in by_arm:
        a, b = by_arm[0], by_arm[arms[-1]]
        print(f"\nmean delta (tools={arms[-1]} - tools=0): {statistics.mean(b) - statistics.mean(a):+.0f} ms")
    if len(arms) >= 2:
        lo, hi = arms[0], arms[-1]
        if lo in by_arm and hi in by_arm:
            print(f"mean delta (tools={hi} - tools={lo}): "
                  f"{statistics.mean(by_arm[hi]) - statistics.mean(by_arm[lo]):+.0f} ms")
            print("\nverdict: if this delta is >=1000 ms, trimming the tool set is worth doing;")
            print("if <300 ms, look at prompt structure / queueing instead.")

    if args.out:
        Path(args.out).write_text(json.dumps({"args": vars(args), "rows": rows}, indent=2), encoding="utf-8")
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
