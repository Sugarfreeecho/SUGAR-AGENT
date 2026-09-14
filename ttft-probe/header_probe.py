"""The closing experiment: do the request HEADERS and/or TOOLS change how the gateway
serves us?

Every client-side cause has been measured away (see why.md 2), yet MyAgent's requests
still get ~1.9 s later first tokens AND 20-27% slower token generation at matched
context, same endpoint, same credential. The only remaining difference the server can
see is the request head/body. This isolates the two candidates on ONE warm connection:

  A: no x-opencode headers, no tools      (closest to DSH production)
  B: x-opencode headers,    no tools      (tests header-based routing)
  C: no x-opencode headers, 61 tools      (tests tool-payload weight)
  D: x-opencode headers,    61 tools      (closest to MyAgent production)

It measures BOTH time-to-first-token and full decode throughput, because the earlier
probe aborted right after the first token and so never saw a decode difference.

Costs real API calls: arms x trials requests. Review before running.

Usage:
  python ttft-probe/header_probe.py --dry-run
  python ttft-probe/header_probe.py --trials 10 --out ttft-probe/header.json
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

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

MODEL = os.environ.get("PROBE_MODEL", "deepseek/deepseek-v4.1-flash")
BASE = os.environ.get("PROBE_BASE_URL", "https://api.commandcode.ai/provider/v1")
KEY = os.environ.get("COMMAND_API_KEY") or os.environ.get("PROBE_API_KEY") or ""
PROMPT = os.environ.get("PROBE_PROMPT", "Reply with the single word: ok")

# The exact header set MyAgent's transport attaches (see app/llm/transport.py:1901).
MYAGENT_HEADERS = {
    "x-opencode-client": "myagent",
    "x-opencode-session": "ses-myagent-6d1f4b2e8a90c3",
    "x-opencode-project": "myagent-workspace",
    "x-opencode-request": "req-myagent-0a3c9e1d7f52",
    "User-Agent": "my-coding-agent/1.0",
}

_PAD_SENTENCES = (
    "The build pipeline resolves dependencies before it compiles any source file.",
    "A cache entry is only reusable while the preceding tokens stay byte identical.",
    "Tool schemas are serialised ahead of the conversation history in the request body.",
    "Retry policy counts transport failures separately from provider error codes.",
    "Session persistence writes one compressed frame per durable event batch.",
    "The scheduler admits a step only after the previous step's tools have settled.",
    "Token accounting distinguishes cached reads from newly prefilled input.",
    "A stream is complete once the provider emits its final usage record.",
)


def build_pad(target_tokens: int) -> str:
    """A deterministic, byte-identical filler block used to reach a target context size.

    Identical across every request and arm so the upstream prefix cache can actually hit;
    ~4 characters per token is the usual English ratio.
    """
    if target_tokens <= 0:
        return ""
    target_chars = target_tokens * 4
    parts = []
    length = 0
    i = 0
    while length < target_chars:
        line = f"[{i:06d}] {_PAD_SENTENCES[i % len(_PAD_SENTENCES)]}"
        parts.append(line)
        length += len(line) + 1
        i += 1
    return "\n".join(parts)



def synthetic_tool(index: int) -> dict:
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


def arm_specs(tool_count: int) -> list[dict]:
    tools = [synthetic_tool(i) for i in range(tool_count)]
    return [
        {"arm": "A_nohead_notools", "headers": False, "tools": []},
        {"arm": "B_head_notools", "headers": True, "tools": []},
        {"arm": f"C_nohead_{tool_count}tools", "headers": False, "tools": tools},
        {"arm": f"D_head_{tool_count}tools", "headers": True, "tools": tools},
    ]


def build_client(with_headers: bool) -> OpenAI:
    """One client per header setting; each keeps its own warm connection."""
    http_client = httpx.Client(
        timeout=180.0,
        limits=httpx.Limits(max_connections=10, max_keepalive_connections=10, keepalive_expiry=300.0),
    )
    ctor: dict = {
        "api_key": KEY or "unset",
        "base_url": BASE,
        "http_client": http_client,
        "max_retries": 0,
        "timeout": 180.0,
    }
    if with_headers:
        ctor["default_headers"] = dict(MYAGENT_HEADERS)
    return OpenAI(**ctor)


def one(client: OpenAI, tools: list[dict], pad: str = "") -> dict:
    messages: list[dict] = []
    if pad:
        messages.append({"role": "system", "content": pad})
    messages.append({"role": "user", "content": PROMPT})
    kwargs: dict = {
        "model": MODEL,
        "messages": messages,
        "stream": True,
        "stream_options": {"include_usage": True},
        "reasoning_effort": "max",
        "extra_body": {"thinking": {"type": "enabled"}},
        "max_tokens": 50000,
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"

    t0 = time.perf_counter()
    stream = client.chat.completions.create(**kwargs)
    t_headers = time.perf_counter()
    ttft = None
    out_tokens = None
    usage_seen: dict = {}
    for chunk in stream:
        usage = getattr(chunk, "usage", None)
        if usage is not None:
            out_tokens = getattr(usage, "completion_tokens", None) or out_tokens
            usage_seen["prompt_tokens"] = getattr(usage, "prompt_tokens", None)
            usage_seen["completion_tokens"] = getattr(usage, "completion_tokens", None)
            # Cache accounting: DeepSeek-style top-level field, or the OpenAI nested form.
            hit = getattr(usage, "prompt_cache_hit_tokens", None)
            if hit is None:
                details = getattr(usage, "prompt_tokens_details", None)
                if details is not None:
                    hit = getattr(details, "cached_tokens", None)
            if hit is not None:
                usage_seen["cache_hit_tokens"] = hit
        if ttft is None:
            for choice in (getattr(chunk, "choices", None) or []):
                delta = getattr(choice, "delta", None)
                if delta and (getattr(delta, "reasoning_content", None)
                              or getattr(delta, "reasoning", None)
                              or getattr(delta, "content", None)):
                    ttft = time.perf_counter()
                    break
    t_end = time.perf_counter()
    stream.close()

    decode_ms = None if ttft is None else (t_end - ttft) * 1000
    return {
        "ttft_ms": None if ttft is None else (ttft - t0) * 1000,
        "t_headers_ms": (t_headers - t0) * 1000,
        "total_ms": (t_end - t0) * 1000,
        "decode_ms": decode_ms,
        "out_tokens": out_tokens,
        "tps": (out_tokens / (decode_ms / 1000.0)) if (out_tokens and decode_ms and decode_ms > 0) else None,
        **usage_seen,
    }


def median(v):
    return statistics.median(v) if v else float("nan")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=10, help="rounds per arm")
    ap.add_argument("--tools", type=int, default=61, help="tool count for the C/D arms")
    ap.add_argument("--warmup", type=int, default=2)
    ap.add_argument("--pad-tokens", type=int, default=0,
                    help="fixed filler prefix size; identical in every request so the "
                         "upstream prefix cache can hit. 0 = no padding (short-context mode).")
    ap.add_argument("--seed", type=int, default=20260911)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    specs = arm_specs(args.tools)
    pad = build_pad(args.pad_tokens)
    if args.dry_run:
        print("arms and payload weight:")
        for s in specs:
            print(f"  {s['arm']:24s} headers={str(s['headers']):5s} "
                  f"tools={len(s['tools']):3d} schema={len(json.dumps(s['tools'])):7d} chars")
        if pad:
            print(f"\npad: {args.pad_tokens} target tokens -> {len(pad)} chars "
                  f"(~{len(pad) // 4} tokens by the 4 chars/token rule)")
            print("  identical across every request and arm, so repeated calls should hit the")
            print("  upstream prefix cache; only the FIRST call per distinct prefix pays full prefill")
        n_req = len(specs) * args.trials
        ctx = (len(pad) + 400) // 4
        print(f"\nwould send {n_req} requests ({len(specs)} arms x {args.trials} trials) "
              f"plus {args.warmup} warmups")
        print(f"context per request ~{ctx} tokens")
        print(f"worst case input tokens (no cache hits at all): {n_req * ctx:,}")
        print(f"likely case (prefix cache hits after the first call per arm): "
              f"~{len(specs) * ctx:,} full-price + {n_req * ctx:,} cached reads")
        return 0

    if not KEY:
        print("error: no API key (set COMMAND_API_KEY or PROBE_API_KEY)", file=sys.stderr)
        return 2

    clients = {True: build_client(True), False: build_client(False)}
    for spec in specs[:2]:
        try:
            one(clients[spec["headers"]], spec["tools"], pad)
        except Exception:
            pass

    rng = random.Random(args.seed)
    order = [i for _ in range(args.trials) for i in range(len(specs))]
    rng.shuffle(order)

    rows = []
    for n, idx in enumerate(order, 1):
        spec = specs[idx]
        try:
            r = one(clients[spec["headers"]], spec["tools"], pad)
        except Exception as exc:
            r = {"error": str(exc)[:200]}
        r.update({"arm": spec["arm"], "headers": spec["headers"], "tools": len(spec["tools"]), "trial": n})
        rows.append(r)
        tt = r.get("ttft_ms")
        tps = r.get("tps")
        print(f"  [{n:3d}/{len(order)}] {spec['arm']:24s} "
              f"ttft={tt if tt is None else round(tt)} ms  "
              f"tps={tps if tps is None else round(tps, 1)}")

    print("\n=== per arm ===")
    print(f"  {'arm':24s} {'n':>3s} {'ttft med':>9s} {'tps med':>8s} {'total med':>10s}")
    for spec in specs:
        v = [r for r in rows if r.get("arm") == spec["arm"] and r.get("ttft_ms")]
        if not v:
            continue
        print(f"  {spec['arm']:24s} {len(v):3d} {median([r['ttft_ms'] for r in v]):9.0f} "
              f"{median([r['tps'] for r in v if r.get('tps')]):8.1f} "
              f"{median([r['total_ms'] for r in v]):10.0f}")

    base = [r for r in rows if r.get("arm") == specs[0]["arm"] and r.get("ttft_ms")]
    print("\n=== deltas vs arm A ===")
    for spec in specs[1:]:
        v = [r for r in rows if r.get("arm") == spec["arm"] and r.get("ttft_ms")]
        if not v or not base:
            continue
        print(f"  {spec['arm']:24s} ttft {median([r['ttft_ms'] for r in v]) - median([r['ttft_ms'] for r in base]):+8.0f} ms"
              f"   tps {median([r['tps'] for r in v if r.get('tps')]) - median([r['tps'] for r in base if r.get('tps')]):+7.1f}")
    print("\n  B >> A  -> the x-opencode headers change routing (cheap fix on MyAgent's side)")
    print("  C >> A  -> the tool payload is the cost (tool trimming)")
    print("  all ~=  -> the gateway schedules the account, not the request")

    if args.out:
        Path(args.out).write_text(json.dumps({"args": vars(args), "rows": rows}, indent=2), encoding="utf-8")
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
