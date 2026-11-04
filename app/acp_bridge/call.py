"""A bounded ACP caller for terminal tools that need the actual task result."""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import sys
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from session_control.client import ControlClient
from session_control.errors import ControlError
from .client import AgentTarget
from .peer import peer_transport


@dataclass(frozen=True)
class LocalTarget(AgentTarget):
    token: str = field(default="", repr=False)

    def environment(self):
        return {**super().environment(), "MYAGENT_CONTROL_TOKEN": self.token,
                "MYAGENT_CONTROL_TASK": "acp-call"}


def save_result(path, value):
    if path is None:
        return
    destination = Path(path).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix="acp-result-", dir=destination.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
        os.replace(name, destination)
    finally:
        if os.path.exists(name):
            os.unlink(name)


async def call(target, prompt, cwd, *, session_id=None, emit=None, result_file=None):
    """Wait for the correlated prompt receipt; preserve partial text on failure."""
    result = {"request_id": str(uuid.uuid4()), "agent": target.name,
              "session_id": session_id, "session_action": "resume" if session_id else "new",
              "status": "connecting", "output": "", "truncated": False,
              "permission_requested": False, "connected": False}

    def publish(event):
        if emit:
            emit({"event": event, **result})

    async def progress(event):
        if event["type"] == "message":
            result["output"] += event["text"]
            result["truncated"] = event["truncated"]
            if emit:
                emit({"event": "progress", "request_id": result["request_id"],
                      "session_id": result["session_id"], "text": event["text"]})
        elif event["type"] == "permission":
            result["permission_requested"] = True

    async def execute():
        async with peer_transport(target, cwd) as peer:
            if session_id:
                result["session_action"] = await peer.resume(session_id)
            else:
                result["session_id"] = await peer.new_session()
            result.update(status="running", connected=True)
            publish("started")
            response = await peer.prompt(result["session_id"], prompt, progress)
            result.update(response)
            result["status"] = {"end_turn": "succeeded", "cancelled": "cancelled"}.get(
                response["stop_reason"], "incomplete")
            # Close the ACP session handle explicitly; native history remains.
            await peer.close_session(result["session_id"])

    try:
        await asyncio.wait_for(execute(), target.timeout)
    except asyncio.TimeoutError:
        if result["status"] not in {"succeeded", "cancelled", "incomplete"}:
            result.update(status="timed_out", error={"category": "TimeoutError"})
        else:
            result["cleanup_error"] = {"category": "TimeoutError"}
    except asyncio.CancelledError:
        result.update(status="cancelled", error={"category": "CancelledError"})
        raise
    except Exception as exc:
        # Exception bodies can contain tokens, HTTP headers or remote prompts.
        if result["status"] not in {"succeeded", "cancelled", "incomplete"}:
            result.update(status="failed", error={"category": type(exc).__name__})
        else:
            result["cleanup_error"] = {"category": type(exc).__name__}
    finally:
        result["connected"] = False
        save_result(result_file, result)
        publish("completed")
    return result


def main(argv=None):
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server-url", default="http://127.0.0.1:8192")
    parser.add_argument("--cwd", default=str(Path.cwd()))
    parser.add_argument("--session-id", help="Resume this session; omitted means new")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--prompt")
    source.add_argument("--prompt-file", help="Read a UTF-8 prompt file")
    source.add_argument("--stdin", action="store_true", help="Read prompt text through EOF")
    parser.add_argument("--timeout", type=float, default=600)
    parser.add_argument("--result-file", help="Atomically save status and final result as JSON")
    args = parser.parse_args(argv)

    def emit(value):
        print(json.dumps(value, ensure_ascii=False), flush=True)

    try:
        parsed = urlsplit(args.server_url)
        if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
                or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in {"", "/"}):
            raise ValueError("server-url must be a loopback HTTP origin")
        if not math.isfinite(args.timeout) or not 1 <= args.timeout <= 86400:
            raise ValueError("timeout must be between 1 and 86400 seconds")
        cwd = Path(args.cwd).expanduser().resolve()
        if not cwd.is_dir():
            raise ValueError("cwd must be an existing directory")
        if args.prompt_file:
            prompt = Path(args.prompt_file).read_text(encoding="utf-8-sig")
        elif args.stdin:
            prompt = sys.stdin.read(200001)
        else:
            prompt = args.prompt
        if not prompt.strip() or len(prompt) > 200000:
            raise ValueError("prompt must contain between 1 and 200000 characters")
        client = ControlClient(args.server_url)
        try:
            client.headers()  # Validate identity before starting a subprocess.
            target = LocalTarget("sugaragent", sys.executable,
                (str(Path(__file__).resolve().parents[1] / "acp_stdio.py"), "--server-url", args.server_url),
                timeout=args.timeout, token=client.token)
        finally:
            client.close()
        result = asyncio.run(call(target, prompt, str(cwd), session_id=args.session_id,
                                  emit=emit, result_file=args.result_file))
        return 0 if result["status"] == "succeeded" else 7 if result["status"] == "timed_out" else 1
    except (ControlError, OSError, ValueError) as exc:
        emit({"event": "completed", "status": "failed", "connected": False,
              "error": {"category": type(exc).__name__, "code": getattr(exc, "code", "invalid_arguments")}})
        return 2
    except KeyboardInterrupt:
        return 130
