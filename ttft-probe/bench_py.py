"""Local-range bench: N sequential requests on one warm connection, openai SDK.

Env: BENCH_URL, BENCH_N, BENCH_SHAPE, BENCH_WARMUP
"""
from __future__ import annotations

import json
import os
import statistics
import sys
import time

import httpx
from openai import OpenAI

URL_ = os.environ["BENCH_URL"]          # e.g. http://127.0.0.1:8791/v1
N = int(os.environ.get("BENCH_N") or 200)
SHAPE = os.environ.get("BENCH_SHAPE", "myagent")
WARMUP = int(os.environ.get("BENCH_WARMUP") or 5)

_marks: dict[str, float] = {}


def _on_response(response: httpx.Response) -> None:
    _marks["t_headers"] = time.perf_counter()


def build_client() -> OpenAI:
    http_client = httpx.Client(timeout=30.0, event_hooks={"response": [_on_response]})
    ctor: dict = {
        "api_key": "bench",
        "base_url": URL_,
        "http_client": http_client,
        "max_retries": 0,
        "timeout": 30.0,
    }
    if SHAPE == "myagent":
        ctor["default_headers"] = {
            "x-opencode-client": "myagent",
            "x-opencode-session": "ses-myagent-6d1f4b2e8a90c3",
            "x-opencode-project": "myagent-workspace",
            "x-opencode-request": "req-myagent-0a3c9e1d7f52",
            "User-Agent": "my-coding-agent/1.0",
        }
    return OpenAI(**ctor)


def kwargs() -> dict:
    base: dict = {
        "model": "bench",
        "messages": [{"role": "user", "content": "ping"}],
        "stream": True,
        "stream_options": {"include_usage": True},
        "extra_body": {"thinking": {"type": "enabled"}},
        "reasoning_effort": "max",
        "max_tokens": 50000 if SHAPE == "myagent" else 256000,
    }
    if SHAPE == "myagent":
        base["parallel_tool_calls"] = True
        base["temperature"] = 0.7
    return base


def first_delta(delta) -> bool:
    return bool(
        getattr(delta, "reasoning_content", None)
        or getattr(delta, "reasoning", None)
        or getattr(delta, "content", None)
    )


def one(client: OpenAI) -> dict:
    _marks.clear()
    t0 = time.perf_counter()
    stream = client.chat.completions.create(**kwargs())
    t_headers = _marks.get("t_headers", t0)
    ttft = None
    for chunk in stream:                    # full drain keeps the connection reusable
        if ttft is None:
            for choice in (getattr(chunk, "choices", None) or []):
                if first_delta(getattr(choice, "delta", None)):
                    ttft = time.perf_counter()
                    break
    stream.close()
    t_done = time.perf_counter()
    return {
        "ttft": None if ttft is None else (ttft - t0) * 1000,
        "t_headers": (t_headers - t0) * 1000,
        "total": (t_done - t0) * 1000,
    }


def main() -> int:
    client = build_client()
    for _ in range(WARMUP):
        one(client)
    rows = [one(client) for _ in range(N)]
    ttfts = [r["ttft"] for r in rows if r["ttft"] is not None]
    hdrs = [r["t_headers"] for r in rows]
    totals = [r["total"] for r in rows]

    def q(a, p):
        s = sorted(a)
        return s[min(len(s) - 1, int(p * len(s)))]

    print(json.dumps({
        "stack": "python-openai-sdk", "shape": SHAPE, "n": len(ttfts),
        "ttft": {"mean": statistics.mean(ttfts), "p50": q(ttfts, 0.5), "p90": q(ttfts, 0.9),
                 "min": min(ttfts), "max": max(ttfts),
                 "sd": statistics.stdev(ttfts) if len(ttfts) > 1 else 0.0},
        "headers": {"mean": statistics.mean(hdrs),
                    "sd": statistics.stdev(hdrs) if len(hdrs) > 1 else 0.0},
        "total": {"mean": statistics.mean(totals),
                  "sd": statistics.stdev(totals) if len(totals) > 1 else 0.0},
        "samples": ttfts[:20],
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
