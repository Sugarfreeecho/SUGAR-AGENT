"""TTFT probe: openai SDK + httpx, the way MyAgent's transport does it.

Env contract matches node_probe.mjs. Prints exactly one JSON line.

The httpx client is instrumented with request/response event hooks -- the same
trick MyAgent's RequestResponseLogger(httpx.Client) uses -- without changing the
request path the SDK takes. PROBE_DUMP=1 swaps in an offline MockTransport so
the exact SDK-generated request can be inspected without spending a call.
"""
from __future__ import annotations

import json
import os
import sys
import time

import httpx
from openai import OpenAI

SHAPE = os.environ.get("PROBE_SHAPE", "myagent")
BASE = (os.environ.get("PROBE_BASE_URL") or "").rstrip("/")
KEY = os.environ.get("PROBE_API_KEY") or ""
MODEL = os.environ.get("PROBE_MODEL") or ""
PROMPT = os.environ.get("PROBE_PROMPT") or "hi"
MAX_TOKENS_RAW = os.environ.get("PROBE_MAX_TOKENS") or ""
MAX_TOKENS = int(MAX_TOKENS_RAW) if MAX_TOKENS_RAW else None
TIMEOUT_MS = float(os.environ.get("PROBE_TIMEOUT_MS") or 120000)
GRACE_MS = float(os.environ.get("PROBE_GRACE_MS") or 250)
WARM = os.environ.get("PROBE_WARM") == "1"
VERIFY = os.environ.get("PROBE_VERIFY", "1") == "1"
DUMP = os.environ.get("PROBE_DUMP") == "1"

SESSION_HEX = "6d1f4b2e8a90c3"

_marks: dict[str, float] = {}
_captured: dict = {}

_MOCK_SSE = (
    b'data: {"id":"c","object":"chat.completion.chunk","model":"m",'
    b'"choices":[{"index":0,"delta":{"content":"a"},"finish_reason":null}]}\n\n'
    b"data: [DONE]\n\n"
)


def _on_request(request: httpx.Request) -> None:
    _captured["url"] = str(request.url)
    _captured["headers"] = dict(request.headers)
    try:
        _captured["body"] = json.loads(request.content.decode("utf-8"))
    except Exception:
        _captured["body"] = request.content.decode("utf-8", errors="replace")


def _on_response(response: httpx.Response) -> None:
    _marks["t_headers"] = time.perf_counter()


def _mock_handler(request: httpx.Request) -> httpx.Response:
    _on_request(request)
    return httpx.Response(
        200,
        headers={"content-type": "text/event-stream"},
        content=_MOCK_SSE,
    )


def build_client() -> OpenAI:
    kwargs: dict = {
        "timeout": TIMEOUT_MS / 1000.0,
        "event_hooks": {"response": [_on_response], "request": [_on_request]},
    }
    if DUMP:
        kwargs["transport"] = httpx.MockTransport(_mock_handler)
    elif not VERIFY:
        kwargs["verify"] = False
    http_client = httpx.Client(**kwargs)
    ctor: dict = {
        "api_key": KEY,
        "base_url": BASE,
        "http_client": http_client,
        "max_retries": 0,
        "timeout": TIMEOUT_MS / 1000.0,
    }
    if SHAPE == "myagent":
        ctor["default_headers"] = {
            "x-opencode-client": "myagent",
            "x-opencode-session": f"ses-myagent-{SESSION_HEX}",
            "x-opencode-project": "myagent-workspace",
            "x-opencode-request": "req-myagent-0a3c9e1d7f52",
            "User-Agent": "my-coding-agent/1.0",
        }
    return OpenAI(**ctor)


def build_kwargs() -> dict:
    kwargs: dict = {
        "model": MODEL,
        "messages": [{"role": "user", "content": PROMPT}],
        "stream": True,
        "stream_options": {"include_usage": True},
        "extra_body": {"thinking": {"type": "enabled"}},
        "reasoning_effort": "max",
    }
    if MAX_TOKENS is not None:
        kwargs["max_tokens"] = MAX_TOKENS
    if SHAPE == "myagent":
        kwargs["parallel_tool_calls"] = True
        kwargs["temperature"] = 0.7
    return kwargs


def first_kind(delta) -> str | None:
    if delta is None:
        return None
    if getattr(delta, "reasoning_content", None):
        return "reasoning_content"
    if getattr(delta, "reasoning", None):
        return "reasoning"
    if getattr(delta, "content", None):
        return "content"
    if getattr(delta, "tool_calls", None):
        return "tool_calls"
    return None


def one_request(client: OpenAI) -> dict:
    _marks.clear()
    t0 = time.perf_counter()
    try:
        stream = client.chat.completions.create(**build_kwargs())
    except Exception as exc:
        status = getattr(exc, "status_code", None)
        body = getattr(exc, "message", None) or str(exc)
        return {
            "ok": False,
            "http_status": status,
            "error": str(body)[:600],
            "t_headers_ms": round((_marks.get("t_headers", t0) - t0) * 1000, 1),
        }

    t_headers = _marks.get("t_headers", t0)
    t_first = None
    kind = None
    n_chunks = 0
    aborted = False

    try:
        for chunk in stream:
            n_chunks += 1
            if t_first is None:
                for choice in (getattr(chunk, "choices", None) or []):
                    k = first_kind(getattr(choice, "delta", None))
                    if k:
                        t_first = time.perf_counter()
                        kind = k
                        break
            if t_first is not None and (time.perf_counter() - t_first) * 1000 > GRACE_MS:
                aborted = True
                break
    except Exception:
        aborted = True
    finally:
        try:
            stream.close()
        except Exception:
            pass

    return {
        "ok": True,
        "t_headers_ms": round((t_headers - t0) * 1000, 1),
        "ttft_ms": None if t_first is None else round((t_first - t0) * 1000, 1),
        "server_think_ms": (None if t_first is None else round((t_first - t_headers) * 1000, 1)),
        "first_kind": kind,
        "chunks": n_chunks,
        "aborted": aborted,
    }


def main() -> int:
    client = build_client()
    if DUMP:
        try:
            list(client.chat.completions.create(**build_kwargs()))
        except Exception:
            pass
        headers = dict(_captured.get("headers") or {})
        for name in list(headers):
            if name.lower() in {"authorization", "x-api-key"}:
                headers[name] = "Bearer <redacted>"
        print(json.dumps(
            {
                "stack": "python-openai-sdk",
                "shape": SHAPE,
                "url": _captured.get("url"),
                "headers": headers,
                "body": _captured.get("body"),
            },
            indent=2,
            ensure_ascii=False,
        ))
        return 0

    if WARM:
        try:
            one_request(client)
        except Exception:
            pass
    result = one_request(client)
    print(json.dumps({"stack": "python-openai-sdk", "shape": SHAPE, **result}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
