"""TCP+TLS handshake cost to the real host, fresh connection per attempt.

Python's socket + ssl path, which is what httpx uses underneath.
Env: TLS_HOST, TLS_N, TLS_VERIFY
"""
from __future__ import annotations

import json
import os
import socket
import ssl
import statistics
import sys
import time

HOST = os.environ["TLS_HOST"]
PORT = int(os.environ.get("TLS_PORT") or 443)
N = int(os.environ.get("TLS_N") or 15)
VERIFY = os.environ.get("TLS_VERIFY", "1") == "1"


def once() -> dict:
    t0 = time.perf_counter()
    try:
        raw = socket.create_connection((HOST, PORT), timeout=20)
    except OSError:
        return {"tcp": None, "tls": None, "total": None}
    t_tcp = time.perf_counter()
    ctx = ssl.create_default_context()
    if not VERIFY:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    try:
        tls_sock = ctx.wrap_socket(raw, server_hostname=HOST)
    except ssl.SSLError:
        raw.close()
        return {"tcp": (t_tcp - t0) * 1000, "tls": None, "total": None}
    t_done = time.perf_counter()
    tls_sock.close()
    return {
        "tcp": (t_tcp - t0) * 1000,
        "tls": (t_done - t_tcp) * 1000,
        "total": (t_done - t0) * 1000,
    }


def main() -> int:
    rows = [once() for _ in range(N)]
    totals = [r["total"] for r in rows if r["total"] is not None]
    tcps = [r["tcp"] for r in rows if r["tcp"] is not None]
    tlss = [r["tls"] for r in rows if r["tls"] is not None]

    def sd(a):
        return statistics.stdev(a) if len(a) > 1 else 0.0

    print(json.dumps({
        "stack": "python-ssl", "host": HOST, "n": len(totals), "verify": VERIFY,
        "total": {"mean": statistics.mean(totals), "sd": sd(totals),
                  "min": min(totals), "max": max(totals)},
        "tcp": {"mean": statistics.mean(tcps), "sd": sd(tcps)},
        "tls": {"mean": statistics.mean(tlss), "sd": sd(tlss)},
        "samples": [round(v, 1) for v in totals],
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
