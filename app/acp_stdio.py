"""Run SugarAgent's standard ACP v1 stdio adapter against its local backend."""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys


async def serve(url):
    import acp
    from acp_bridge.backend import RuntimeBackend
    from acp_bridge.server import SugarACPAgent

    backend = RuntimeBackend(url)
    agent = SugarACPAgent(backend)
    try:
        await backend.request("GET", "/api/acp/status")
        # Python SDK 0.12 still gates list/resume/close behind this switch,
        # although DSH's SDK exposes these methods on the standard ACP v1 wire.
        await acp.run_agent(agent, use_unstable_protocol=True,
                            stdio_buffer_limit_bytes=8 * 1024 * 1024)
    finally:
        try:
            await agent.shutdown()
        finally:
            await backend.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server-url", default="http://127.0.0.1:8192",
                        help="Origin of an already running SugarAgent backend")
    args = parser.parse_args()
    logging.basicConfig(stream=sys.stderr, level=logging.WARNING)
    try:
        asyncio.run(serve(args.server_url))
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        # HTTP/SDK errors can contain credentials and payloads. Keep stdout pure
        # and expose only a diagnostic category to the launching editor.
        print(f"ACP startup or shutdown failed ({type(exc).__name__}); check backend and ACP Agents plugin.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
