"""Is the openai SDK's create(stream=True) lazy?

Serves SSE whose response headers are delayed by HEADER_DELAY_MS, then times the
SDK's create() return against the first chunk. If create() returns in ~1ms while the
first chunk arrives after the delay, create() did not wait for headers and any
'stream_created' timestamp is not a connect/headers measurement.

Usage: python ttft-probe/header_delay_test.py [port] [header_delay_ms]
"""
from __future__ import annotations

import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8796
HEADER_DELAY_MS = float(sys.argv[2]) if len(sys.argv) > 2 else 800.0

CONTENT = (
    'data: {"id":"c","object":"chat.completion.chunk","created":0,"model":"m",'
    '"choices":[{"index":0,"delta":{"content":"hi"},"finish_reason":null}]}\n\n'
)
DONE = "data: [DONE]\n\n"


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def do_POST(self):
        length = int(self.headers.get("content-length") or 0)
        if length:
            self.rfile.read(length)
        time.sleep(HEADER_DELAY_MS / 1000.0)  # delay BEFORE headers
        self.send_response(200)
        self.send_header("content-type", "text/event-stream")
        self.send_header("transfer-encoding", "chunked")
        self.end_headers()
        try:
            self._chunk(CONTENT)
            self._chunk(DONE)
            self.wfile.write(b"0\r\n\r\n")
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _chunk(self, text: str) -> None:
        payload = text.encode("utf-8")
        self.wfile.write(f"{len(payload):X}\r\n".encode("ascii"))
        self.wfile.write(payload)
        self.wfile.write(b"\r\n")
        self.wfile.flush()


def main() -> int:
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    from openai import OpenAI

    client = OpenAI(api_key="x", base_url=f"http://127.0.0.1:{PORT}/v1", max_retries=0)

    t0 = time.perf_counter()
    stream = client.chat.completions.create(
        model="m",
        messages=[{"role": "user", "content": "hi"}],
        stream=True,
        stream_options={"include_usage": True},
    )
    t_create = time.perf_counter()
    t_first = None
    for chunk in stream:
        if getattr(chunk, "choices", None):
            delta = chunk.choices[0].delta
            if getattr(delta, "content", None):
                t_first = time.perf_counter()
                break
    stream.close()

    print(json.dumps({
        "header_delay_ms": HEADER_DELAY_MS,
        "create_return_ms": round((t_create - t0) * 1000, 1),
        "first_chunk_ms": None if t_first is None else round((t_first - t0) * 1000, 1),
        "verdict": ("create() DID wait for headers"
                    if (t_create - t0) * 1000 >= HEADER_DELAY_MS * 0.5
                    else "create() returned BEFORE headers -> stream_created is not a connect metric"),
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
