"""Stable argparse/JSON command contract for users and other agents."""
from __future__ import annotations

import argparse
import getpass
import json
import math
import os
import sys
import uuid
from pathlib import Path

from .client import ControlClient, base_url
from .errors import ControlError, envelope


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ControlError("invalid_arguments", message)


COMMANDS = {
    "auth": ("login", "status", "logout"),
    "session": ("create", "list", "get", "read", "search", "send", "attach", "fork", "stop", "continue", "recover", "update", "archive", "unarchive", "delete", "export", "import"),
    "config": ("get", "set", "preview", "reset"),
    "tools": ("list", "describe"),
    "preset": ("list", "get", "create", "update", "delete", "apply"),
    "schedule": ("create", "list", "get", "update", "pause", "resume", "run", "delete"),
    "event": ("create", "list", "get", "update", "pause", "resume", "test", "delete"),
    "execution": ("list", "get", "wait", "cancel"),
}


def parser():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--base-url", default=argparse.SUPPRESS)
    common.add_argument("--human", action="store_true", default=argparse.SUPPRESS)
    common.add_argument("--idempotency-key", default=argparse.SUPPRESS)
    p = Parser(description="Manage sessions, configuration, schedules and events on an existing SugarAgent backend.", parents=[common])
    groups = p.add_subparsers(dest="group", required=True, parser_class=Parser)
    for group, commands in COMMANDS.items():
        g = groups.add_parser(group, parents=[common])
        sub = g.add_subparsers(dest="command", required=True, parser_class=Parser)
        for command in commands:
            leaf = sub.add_parser(command, parents=[common])
            options(leaf)
        if group == "event":
            sources = sub.add_parser("source", parents=[common])
            source_sub = sources.add_subparsers(dest="source_command", required=True, parser_class=Parser)
            for command in ("create", "list", "get", "update", "disable", "test"):
                options(source_sub.add_parser(command, parents=[common]))
    options(groups.add_parser("doctor", parents=[common]))
    return p


def options(p):
    p.add_argument("--id")
    p.add_argument("--session-id")
    p.add_argument("--file", help="UTF-8 JSON parameters or configuration")
    p.add_argument("--stdin", action="store_true", help="Read one JSON object from stdin")
    p.add_argument("--message")
    p.add_argument("--message-file")
    p.add_argument("--name")
    p.add_argument("--work-dir")
    p.add_argument("--query")
    p.add_argument("--limit", type=int)
    p.add_argument("--before-index", type=int)
    p.add_argument("--after-seq", type=int)
    p.add_argument("--cursor", default=None)
    p.add_argument("--generation")
    p.add_argument("--expected-revision", type=int)
    p.add_argument("--mode", choices=["queue", "append", "interrupt"])
    p.add_argument("--include-archived", action="store_true", default=None)
    p.add_argument("--follow", action="store_true")
    p.add_argument("--wait", action="store_true")
    p.add_argument("--timeout", type=float, default=30)
    p.add_argument("--output")
    p.add_argument("--archive", help="Upload a local session ZIP for session import")


def read_object(args):
    if args.file and args.stdin:
        raise ControlError("invalid_arguments", "Use --file or --stdin, not both")
    try:
        if args.file:
            value = json.loads(Path(args.file).read_text(encoding="utf-8-sig"))
        elif args.stdin:
            value = json.load(sys.stdin)
        else:
            value = {}
    except (ValueError, OSError) as exc:
        raise ControlError("invalid_arguments", "Cannot read JSON input: " + str(exc)) from exc
    if not isinstance(value, dict):
        raise ControlError("invalid_arguments", "JSON input must be an object")
    return value


def request(args):
    data = read_object(args)
    group, command = args.group, getattr(args, "command", "")
    if group == "config" and command == "set" and "config" not in data:
        data = {"config": data}
    if group == "preset" and command in {"create", "update"} and "config" not in data:
        data = {"config": data}
    session_commands = {"get", "read", "send", "attach", "fork", "stop", "continue", "recover", "update", "archive", "unarchive", "delete", "export"}
    if args.id:
        data["session_id" if group in {"session", "config"} and (group == "config" or command in session_commands) else "id"] = args.id
    if args.session_id:
        data["session_id"] = args.session_id
    for name in ("name", "work_dir", "query", "limit", "before_index", "after_seq", "expected_revision", "mode", "include_archived"):
        value = getattr(args, name, None)
        if value is not None:
            data[name] = value
    if args.cursor is not None:
        data["cursor"] = args.cursor
    if args.message is not None and args.message_file:
        raise ControlError("invalid_arguments", "Use --message or --message-file")
    if args.message_file:
        data["message"] = Path(args.message_file).read_text(encoding="utf-8-sig")
    elif args.message is not None:
        data["message"] = args.message
    if group == "session":
        command = {"read": "history", "stop": "interrupt", "unarchive": "archive"}.get(command, command)
        if args.command == "unarchive":
            data["archived"] = False
        return "session." + command, data
    if group == "config":
        if command == "reset":
            data["config"] = {}
        return "session.config." + {"set": "update", "reset": "update"}.get(command, command), data
    if group == "tools":
        return "tool_catalog." + command, data
    if group == "preset":
        return "config_preset." + command, data
    if group in {"schedule", "event"}:
        if group == "event" and command == "source":
            return "event_source." + args.source_command, data
        data["kind_filter"] = "event" if group == "event" else "schedule"
        return "automation." + command, data
    if group == "execution":
        if command == "list":
            return "automation.history", data
        if command == "wait":
            data["timeout"] = args.timeout
        return "operation." + command, data
    return "system.health" if group == "doctor" else "auth." + command, data


def output(value, human=False):
    if human:
        print(json.dumps(value.get("data", value), ensure_ascii=False, indent=2), flush=True)
    else:
        print(json.dumps(value, ensure_ascii=False, separators=(",", ":")), flush=True)


def exit_code(error):
    if error.code == "wait_timeout":
        return 7
    if error.code == "backend_unavailable":
        return 6
    if error.status in {401, 403}:
        return 3
    if error.status == 404:
        return 4
    if error.status in {409, 425}:
        return 5
    return 2 if error.status in {400, 413, 422} else 1


def main(argv=None):
    rid = str(uuid.uuid4())
    client = None
    args = None
    try:
        args = parser().parse_args(argv)
        client = ControlClient(base_url(getattr(args, "base_url", None)))
        human = getattr(args, "human", False)
        if args.group == "auth" and args.command == "login":
            payload = read_object(args)
            if not payload:
                if not sys.stdin.isatty():
                    raise ControlError("invalid_arguments", "auth login requires --stdin/--file with bootstrap_token or pairing_code")
                value = getpass.getpass("Bootstrap key or pairing code: ")
                payload = {"pairing_code" if len(value.replace("-", "")) == 12 else "bootstrap_token": value}
            output(envelope(client.login(payload), request_id=rid), human)
            return 0
        if args.group == "auth" and args.command == "logout":
            output(client.logout(), human)
            return 0
        method, params = request(args)
        if not math.isfinite(args.timeout) or args.timeout < 0:
            raise ControlError("invalid_arguments", "timeout must be a non-negative finite number")
        if args.output and method != "session.export":
            raise ControlError("invalid_arguments", "--output is supported by session export")
        if args.follow and not (params.get("session_id") or method == "session.create"):
            raise ControlError("invalid_arguments", "--follow requires a session target")
        if args.archive:
            if method != "session.import" or params:
                raise ControlError("invalid_arguments", "Use session import --archive FILE without JSON parameters")
            result = client.import_archive(args.archive, key=getattr(args, "idempotency_key", None))
        else:
            result = client.rpc(method, params, key=getattr(args, "idempotency_key", None), request_id=rid)
        if args.output:
            result["data"]["local_path"] = client.export_archive(result["operation_id"], args.output)
        if args.group == "session" and args.command == "attach" or args.follow:
            output(result, human)
            sid = params.get("session_id") or result["data"].get("session_id")
            for event in client.follow(sid, cursor=int(args.cursor) if args.cursor is not None else None, generation=args.generation):
                output(event, human)
            return 0
        if args.wait and result.get("operation_id"):
            result = client.rpc("operation.wait", {"id": result["data"].get("execution_id", result["operation_id"]), "timeout": args.timeout})
        output(result, human)
        return 1 if (method == "operation.wait" or args.wait) and result["data"].get("status") in {"failed", "stopped", "interrupted", "unknown", "rejected", "cancelled"} else 0
    except KeyboardInterrupt:
        return 0
    except (ControlError, OSError, ValueError) as exc:
        error = exc if isinstance(exc, ControlError) else ControlError("invalid_arguments", str(exc))
        output(envelope(request_id=rid, error=error), getattr(args, "human", False))
        return exit_code(error)
    finally:
        if client:
            client.close()
