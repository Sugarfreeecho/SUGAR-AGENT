"""How much wall time does request-body size actually cost at this endpoint?

Motivation: MyAgent records `network.request_bytes` as 0 for every request, so the time
spent uploading the request body has never been separated from "server think time" -- it
sits inside `first_token`. The two harnesses may package very differently (61 tool schemas
vs 27), so upload could be part of the gap. Nobody has measured it.

Method: raw TLS socket, hand-built HTTP/1.1 POST, so no HTTP client library can blur the
phases. A filler field carries the extra bytes. Steps:
  1. confirm the endpoint IGNORES the filler (prompt_tokens must not move)
  2. scale the filler and time, separately:
       t_connect   TLS handshake
       t_send      time for sendall(body) to return
       t_firstbyte time from request start until the first response byte
  The slope of t_firstbyte against body size is the upload cost per byte; the intercept is
  everything else. If the slope is small, packaging is not the explanation.

Costs real API calls: sizes x trials. The prompt itself is tiny; only bytes move.

Usage:
  python ttft-probe/upload_probe.py --dry-run
  python ttft-probe/upload_probe.py --sizes 0,262144,1048576 --trials 3 --out ttft-probe/upload.json
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import ssl
import statistics
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

MODEL = os.environ.get("PROBE_MODEL", "deepseek/deepseek-v4.1-flash")
BASE = os.environ.get("PROBE_BASE_URL", "https://api.commandcode.ai/provider/v1")
KEY = os.environ.get("COMMAND_API_KEY") or os.environ.get("PROBE_API_KEY") or ""


def build_body(pad_bytes: int) -> bytes:
    """A valid chat-completions body plus an ignored filler of the requested size."""
    body = {
        "model": MODEL,
        "messages": [{"role": "user", "content": "Say OK."}],
        "stream": True,
        "stream_options": {"include_usage": True},
        "max_tokens": 16,
    }
    if pad_bytes:
        # base64-ish filler; kept in a field the gateway has no schema for
        body["x_probe_pad"] = "A" * pad_bytes
    return json.dumps(body, separators=(",", ":")).encode("utf-8")


def one(pad_bytes: int) -> dict:
    parts = urlsplit(BASE)
    host = parts.hostname
    port = parts.port or 443
    path = (parts.path or "/") + "/chat/completions"
    if not path.startswith("/"):
        path = "/" + path

    body = build_body(pad_bytes)
    headers = (
        f"POST {path} HTTP/1.1\r\n"
        f"Host: {host}\r\n"
        f"authorization: Bearer {KEY}\r\n"
        "content-type: application/json\r\n"
        "accept: text/event-stream\r\n"
        f"content-length: {len(body)}\r\n"
        "connection: close\r\n"
        "\r\n"
    ).encode("ascii")

    ctx = ssl.create_default_context()
    t0 = time.perf_counter()
    raw = socket.create_connection((host, port), timeout=180)
    t_connect = time.perf_counter()
    sock = ctx.wrap_socket(raw, server_hostname=host)
    t_tls = time.perf_counter()
    sock.sendall(headers)
    t_sent_headers = time.perf_counter()
    sock.sendall(body)
    t_sent_body = time.perf_counter()

    first = b""
    first_byte_at = None
    usage_text = b""
    deadline = time.perf_counter() + 180
    while time.perf_counter() < deadline:
        try:
            chunk = sock.recv(65536)
        except socket.timeout:
            break
        if not chunk:
            break
        if first_byte_at is None:
            first_byte_at = time.perf_counter()
        first += chunk
        if b'"usage"' in chunk:
            usage_text += chunk
        if len(first) > 2_000_000 or b"\r\n0\r\n\r\n" in chunk:
            break
    t_end = time.perf_counter()
    try:
        sock.close()
    except Exception:
        pass

    status = first.split(b"\r\n", 1)[0].decode("latin-1", "replace") if first else ""
    prompt_tokens = None
    for line in (first + usage_text).split(b"\n"):
        if line.startswith(b"data: ") and b'"usage"' in line:
            try:
                obj = json.loads(line[6:].decode("utf-8", "replace"))
                u = obj.get("usage") or {}
                if u.get("prompt_tokens"):
                    prompt_tokens = u["prompt_tokens"]
            except Exception:
                pass

    def ms(a, b):
        return (b - a) * 1000.0

    return {
        "pad_bytes": pad_bytes,
        "body_bytes": len(body),
        "status": status,
        "prompt_tokens": prompt_tokens,
        "t_connect_ms": ms(t0, t_connect),
        "t_tls_ms": ms(t_connect, t_tls),
        "t_headers_ms": ms(t_tls, t_sent_headers),
        "t_body_send_ms": ms(t_sent_headers, t_sent_body),
        "t_first_byte_ms": None if first_byte_at is None else ms(t0, first_byte_at),
        "t_total_ms": ms(t0, t_end),
        "response_bytes": len(first),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sizes", default="0,262144,1048576",
                    help="comma-separated filler sizes in bytes")
    ap.add_argument("--trials", type=int, default=3)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    sizes = [int(x) for x in args.sizes.split(",") if x.strip()]

    if args.dry_run:
        print("would measure these request-body sizes:")
        for s in sizes:
            print(f"  filler {s:>9,} bytes -> body {len(build_body(s)):>9,} bytes")
        print(f"\nwould send {len(sizes) * args.trials} requests "
              f"({len(sizes)} sizes x {args.trials} trials)")
        print("prompt is tiny ('Say OK.'), so only transfer size moves")
        return 0

    if not KEY:
        print("error: no API key (set COMMAND_API_KEY or PROBE_API_KEY)", file=sys.stderr)
        return 2

    rows = []
    for trial in range(args.trials):
        for s in sizes:
            try:
                r = one(s)
            except Exception as exc:
                r = {"pad_bytes": s, "error": str(exc)[:200]}
            r["trial"] = trial
            rows.append(r)
            tb = r.get("t_first_byte_ms")
            print(f"  [t{trial} {s:>9,}B] body={r.get('body_bytes'):>9,} "
                  f"status={r.get('status', '')[:12]:12s} "
                  f"body_send={r.get('t_body_send_ms', 0):7.1f}ms "
                  f"first_byte={'-' if tb is None else round(tb):>6}ms "
                  f"prompt_tok={r.get('prompt_tokens')}")

    ok = [r for r in rows if r.get("t_first_byte_ms") and r.get("prompt_tokens")]
    print("\n=== per size ===")
    print(f"  {'filler B':>10s} {'n':>3s} {'prompt tok':>10s} {'body send':>10s} "
          f"{'first byte':>11s} {'total':>9s}")
    for s in sizes:
        v = [r for r in ok if r["pad_bytes"] == s]
        if not v:
            continue
        print(f"  {s:10,} {len(v):3d} "
              f"{statistics.median([r['prompt_tokens'] for r in v]):10.0f} "
              f"{statistics.median([r['t_body_send_ms'] for r in v]):10.1f} "
              f"{statistics.median([r['t_first_byte_ms'] for r in v]):11.0f} "
              f"{statistics.median([r['t_total_ms'] for r in v]):9.0f}")

    print("\n=== did the filler get ignored? ===")
    ptoks = {r["pad_bytes"]: r["prompt_tokens"] for r in ok}
    if len(set(ptoks.values())) == 1:
        print(f"  yes: prompt_tokens stayed at {list(ptoks.values())[0]} across all sizes")
        print("  -> the bytes travelled on the wire without becoming tokens, so the slope")
        print("     below is transfer cost only")
    else:
        print(f"  NO -- prompt_tokens moved: {ptoks}")
        print("  -> the filler was tokenised, so the slope mixes transfer with prefill")

    if len(ok) >= 4:
        xs = [r["body_bytes"] / 1024.0 for r in ok]
        ys = [r["t_first_byte_ms"] for r in ok]
        n = len(xs)
        mx, my = sum(xs) / n, sum(ys) / n
        sxx = sum((x - mx) ** 2 for x in xs)
        if sxx:
            b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
            a = my - b * mx
            print("\n=== upload cost per byte ===")
            print(f"  first_byte_ms = {a:.0f} + {b:.4f} * KiB(body)")
            print(f"  slope = {b:.4f} ms per KiB  =  {b * 1024:.3f} ms per MiB")
            print(f"  implied throughput ~ {1024 / b / 1000:.1f} MiB/s" if b > 0 else "  slope <= 0")
            for kb in (100, 500, 1000, 2000):
                print(f"    a {kb:>5} KiB body costs {b * kb:8.1f} ms of upload")

    if args.out:
        Path(args.out).write_text(json.dumps({"args": vars(args), "rows": rows}, indent=2),
                                  encoding="utf-8")
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
