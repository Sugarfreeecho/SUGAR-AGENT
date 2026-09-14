"""Do the request PARAMETERS explain the gap? (thinking mode + reasoning_effort)

MyAgent's profile sends `extra_body={"thinking":{"type":"enabled"}}` plus top-level
`reasoning_effort="max"` and `max_tokens=50000`. DSH's route declares no
`reasoningEfforts` for this model, so it sends neither field and takes the provider's
own default. The earlier 2x2 probe never varied this: BOTH of its shapes carried
thinking enabled and effort max.

This arms the comparison on exactly that difference, on one warm connection, with the
prompt and tools held fixed. It measures TTFT and full-generation cost, and counts the
reasoning text that actually arrives, so "more thinking" is observed rather than assumed.

Costs real API calls: arms x trials. Review before running.

Usage:
  python ttft-probe/params_probe.py --dry-run
  python ttft-probe/params_probe.py --trials 8 --out ttft-probe/params.json
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
PROMPT = os.environ.get(
    "PROBE_PROMPT",
    "A farmer has 17 sheep. All but 9 run away. How many are left? "
    "Then list three ways to verify the answer.",
)

# What MyAgent's saved profile sends (model_profiles.json: thinking_mode=enabled,
# reasoning_effort=max, max_output_tokens=50000).
MYAGENT_PARAMS = {
    "extra_body": {"thinking": {"type": "enabled"}},
    "reasoning_effort": "max",
    "max_tokens": 50000,
}
# What DSH sends: neither field, provider default thinking.
DSH_PARAMS = {"max_tokens": 50000}

ARMS = [
    ("A_myagent_thinking_max", MYAGENT_PARAMS),
    ("B_dsh_no_thinking_field", DSH_PARAMS),
    ("C_thinking_high", {"extra_body": {"thinking": {"type": "enabled"}},
                         "reasoning_effort": "high", "max_tokens": 50000}),
    ("D_thinking_disabled", {"extra_body": {"thinking": {"type": "disabled"}},
                             "max_tokens": 50000}),
]

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
    """Deterministic filler, byte-identical across every arm so the prefix cache can hit.

    Reusing one pad means the prefill work is shared and the measured difference is the
    generation-side cost of the thinking setting rather than input processing.
    """
    if target_tokens <= 0:
        return ""
    target_chars = target_tokens * 4
    parts, length, i = [], 0, 0
    while length < target_chars:
        line = f"[{i:06d}] {_PAD_SENTENCES[i % len(_PAD_SENTENCES)]}"
        parts.append(line)
        length += len(line) + 1
        i += 1
    return "\n".join(parts)


def build_client() -> OpenAI:
    http_client = httpx.Client(
        timeout=180.0,
        limits=httpx.Limits(max_connections=10, max_keepalive_connections=10, keepalive_expiry=300.0),
    )
    return OpenAI(api_key=KEY or "unset", base_url=BASE, http_client=http_client,
                  max_retries=0, timeout=180.0)


def one(client: OpenAI, params: dict, pad: str = "") -> dict:
    messages: list[dict] = []
    if pad:
        messages.append({"role": "system", "content": pad})
    messages.append({"role": "user", "content": PROMPT})
    kwargs: dict = {
        "model": MODEL,
        "messages": messages,
        "stream": True,
        "stream_options": {"include_usage": True},
        **params,
    }
    t0 = time.perf_counter()
    stream = client.chat.completions.create(**kwargs)
    t_headers = time.perf_counter()
    ttft = None
    ttft_kind = None
    reasoning_chars = 0
    content_chars = 0
    out_tokens = None
    usage: dict = {}
    for chunk in stream:
        u = getattr(chunk, "usage", None)
        if u is not None:
            out_tokens = getattr(u, "completion_tokens", None) or out_tokens
            usage["prompt_tokens"] = getattr(u, "prompt_tokens", None)
            usage["completion_tokens"] = getattr(u, "completion_tokens", None)
            # Cache accounting proves the shared pad actually hit the prefix cache.
            hit = getattr(u, "prompt_cache_hit_tokens", None)
            if hit is None:
                details = getattr(u, "prompt_tokens_details", None)
                if details is not None:
                    hit = getattr(details, "cached_tokens", None)
            if hit is not None:
                usage["cache_hit_tokens"] = hit
        for choice in (getattr(chunk, "choices", None) or []):
            d = getattr(choice, "delta", None)
            if d is None:
                continue
            r = getattr(d, "reasoning_content", None) or getattr(d, "reasoning", None)
            c = getattr(d, "content", None)
            if r:
                reasoning_chars += len(r)
                if ttft is None:
                    ttft, ttft_kind = time.perf_counter(), "reasoning"
            if c:
                content_chars += len(c)
                if ttft is None:
                    ttft, ttft_kind = time.perf_counter(), "content"
    t_end = time.perf_counter()
    stream.close()

    decode_ms = None if ttft is None else (t_end - ttft) * 1000
    return {
        "ttft_ms": None if ttft is None else (ttft - t0) * 1000,
        "first_kind": ttft_kind,
        "t_headers_ms": (t_headers - t0) * 1000,
        "total_ms": (t_end - t0) * 1000,
        "decode_ms": decode_ms,
        "out_tokens": out_tokens,
        "reasoning_chars": reasoning_chars,
        "content_chars": content_chars,
        "tps": (out_tokens / (decode_ms / 1000.0)) if (out_tokens and decode_ms and decode_ms > 0) else None,
        **usage,
    }


def median(v):
    return statistics.median(v) if v else float("nan")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=8)
    ap.add_argument("--warmup", type=int, default=1)
    ap.add_argument("--pad-tokens", type=int, default=0,
                    help="fixed filler prefix, identical in every arm so prefill is shared "
                         "and the measured difference is the thinking setting's own cost")
    ap.add_argument("--seed", type=int, default=20260911)
    ap.add_argument("--arms", default=None,
                    help="comma-separated arm letters to run, e.g. A,B,C (default: all)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    pad = build_pad(args.pad_tokens)

    global ARMS
    if args.arms:
        want = {a.strip().upper() for a in args.arms.split(",") if a.strip()}
        ARMS = [a for a in ARMS if a[0][0].upper() in want]
        if not ARMS:
            print(f"error: --arms {args.arms!r} matched no arm", file=sys.stderr)
            return 2

    if args.dry_run:
        print("arms and request parameters:")
        for name, params in ARMS:
            print(f"  {name:26s} {json.dumps(params, ensure_ascii=False)}")
        n_req = len(ARMS) * args.trials
        ctx = (len(pad) + 200) // 4
        print(f"\ncontext per request ~{ctx} tokens"
              + ("" if not pad else f"  (pad {args.pad_tokens} target tokens -> {len(pad)} chars)"))
        print(f"would send {n_req} requests ({len(ARMS)} arms x {args.trials} trials) "
              f"plus {args.warmup} warmups")
        if pad:
            print(f"worst case input tokens (no cache hits): {n_req * ctx:,}")
            print(f"expected (pad shared across arms, so it hits after the first call): "
                  f"~{len(ARMS) * ctx:,} full-price + {n_req * ctx:,} cached reads")
        else:
            print("small context (~40 tokens), so this is cheap")
        return 0

    if not KEY:
        print("error: no API key (set COMMAND_API_KEY or PROBE_API_KEY)", file=sys.stderr)
        return 2

    client = build_client()
    try:
        one(client, ARMS[0][1], pad)
    except Exception as exc:
        print(f"warmup failed: {exc}", file=sys.stderr)

    rng = random.Random(args.seed)
    order = [i for _ in range(args.trials) for i in range(len(ARMS))]
    rng.shuffle(order)

    rows = []
    for n, idx in enumerate(order, 1):
        name, params = ARMS[idx]
        try:
            r = one(client, params, pad)
        except Exception as exc:
            r = {"error": str(exc)[:200]}
        r.update({"arm": name, "trial": n})
        rows.append(r)
        tt = r.get("ttft_ms")
        print(f"  [{n:3d}/{len(order)}] {name:26s} ttft={'-' if tt is None else round(tt):>6} ms  "
              f"total={'-' if r.get('total_ms') is None else round(r['total_ms']):>6} ms  "
              f"reason_chars={r.get('reasoning_chars', 0):>5}  "
              f"out_tok={r.get('out_tokens') or '-'}")

    print("\n=== per arm ===")
    print(f"  {'arm':26s} {'n':>3s} {'ttft med':>9s} {'total med':>10s} {'out tok':>8s} "
          f"{'reason chars':>13s} {'tps':>7s}")
    for name, _ in ARMS:
        v = [r for r in rows if r.get("arm") == name and r.get("ttft_ms")]
        if not v:
            continue
        print(f"  {name:26s} {len(v):3d} {median([r['ttft_ms'] for r in v]):9.0f} "
              f"{median([r['total_ms'] for r in v]):10.0f} "
              f"{median([r['out_tokens'] for r in v if r.get('out_tokens')]):8.0f} "
              f"{median([r['reasoning_chars'] for r in v]):13.0f} "
              f"{median([r['tps'] for r in v if r.get('tps')]):7.1f}")

    if any(r.get("prompt_tokens") for r in rows):
        print("\n=== context and cache accounting (did the shared pad hit?) ===")
        print(f"  {'arm':26s} {'prompt tok':>10s} {'cache hit':>10s} {'hit share':>9s}")
        for name, _ in ARMS:
            v = [r for r in rows if r.get("arm") == name and r.get("prompt_tokens")]
            if not v:
                continue
            pt = median([r["prompt_tokens"] for r in v])
            hitv = [r["cache_hit_tokens"] for r in v if r.get("cache_hit_tokens") is not None]
            share = median([r["cache_hit_tokens"] / r["prompt_tokens"] for r in v
                            if r.get("cache_hit_tokens") is not None and r.get("prompt_tokens")])
            print(f"  {name:26s} {pt:10.0f} {median(hitv):10.0f} {share * 100:8.1f}%")
        missed = sum(1 for r in rows if not r.get("cache_hit_tokens"))
        print(f"\n  requests with no cache hit: {missed} of {len(rows)}")
        print("  (every arm reuses the SAME pad text, so a high hit share means prefill was")
        print("   shared and the arm differences below are generation-side, not input-side)")

    print("\n=== reasoning actually emitted? (0 means the model did not think) ===")
    for name, _ in ARMS:
        v = [r for r in rows if r.get("arm") == name and r.get("ttft_ms")]
        if not v:
            continue
        thought = sum(1 for r in v if (r.get("reasoning_chars") or 0) > 0)
        firsts = {}
        for r in v:
            firsts[r.get("first_kind")] = firsts.get(r.get("first_kind"), 0) + 1
        print(f"  {name:26s} thought in {thought}/{len(v)} requests; first delta kind: {firsts}")

    print("\n=== reading ===")
    a = [r for r in rows if r.get("arm") == ARMS[0][0] and r.get("ttft_ms")]
    b = [r for r in rows if r.get("arm") == ARMS[1][0] and r.get("ttft_ms")]
    if a and b:
        print(f"  A (MyAgent params) - B (DSH params):")
        print(f"    TTFT  {median([r['ttft_ms'] for r in a]) - median([r['ttft_ms'] for r in b]):+8.0f} ms")
        print(f"    total {median([r['total_ms'] for r in a]) - median([r['total_ms'] for r in b]):+8.0f} ms")
        print(f"    out tokens {median([r['out_tokens'] for r in a if r.get('out_tokens')]) - median([r['out_tokens'] for r in b if r.get('out_tokens')]):+8.0f}")
    print("  If A is materially slower AND emits more reasoning, the effort setting is a causal,")
    print("  client-side lever -- and 'max' is a MyAgent profile choice, not a provider behaviour.")

    if args.out:
        Path(args.out).write_text(json.dumps({"args": vars(args), "rows": rows}, indent=2), encoding="utf-8")
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
