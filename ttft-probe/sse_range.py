"""Local SSE benchmark range.

A canned OpenAI-style SSE endpoint on 127.0.0.1. It answers immediately with
response headers, waits FIRST_BYTE_DELAY_MS, then streams one delta and [DONE].
TTFT measured against it therefore contains only client-stack cost plus the
fixed delay -- no gateway queueing, no upstream model, no cross-border network.
That makes it powerful enough to resolve sub-millisecond differences that the
real provider's ~1s jitter completely buries.

Run: python sse_range.py [port]
"""
from __future__ import annotations

import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

FIRST_BYTE_DELAY_MS = float(sys.argv[2]) if len(sys.argv) > 2 else 30.0

DELTA = (
    'data: {"id":"c","object":"chat.completion.chunk","created":0,'
    '"model":"m","choices":[{"index":0,"delta":{"role":"assistant","content":""},'
    '"finish_reason":null}]}\n\n'
)
# a second, non-empty delta is what both harnesses count as the first token
CONTENT = (
    'data: {"id":"c","object":"chat.completion.chunk","created":0,'
    '"model":"m","choices":[{"index":0,"delta":{"content":"hi"},'
    '"finish_reason":null}]}\n\n'
)
USAGE = (
    'data: {"id":"c","object":"chat.completion.chunk","created":0,"model":"m",'
    '"choices":[],"usage":{"prompt_tokens":1,"completion_tokens":1,"total_tokens":2}}\n\n'
)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):  # silence
        pass

    def do_POST(self):
        length = int(self.headers.get("content-length") or 0)
        if length:
            self.rfile.read(length)
        self.send_response(200)
        self.send_header("content-type", "text/event-stream")
        self.send_header("cache-control", "no-cache")
        self.send_header("transfer-encoding", "chunked")
        self.end_headers()
        try:
            self._chunk(DELTA)
            time.sleep(FIRST_BYTE_DELAY_MS / 1000.0)
            self._chunk(CONTENT)
            self._chunk(USAGE)
            self._chunk("data: [DONE]\n\n")
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
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8791
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(json.dumps({"listening": f"http://127.0.0.1:{port}", "delay_ms": FIRST_BYTE_DELAY_MS}))
    sys.stdout.flush()
    server.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
