"""Local SugarAgent management helper. Never calls a Bilibili send endpoint."""
import argparse
import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

PLUGIN = "sugar-bili-scroll"
SERVER = PLUGIN + "/bili"


def request(base, path, method="GET", body=None):
    headers = {"Accept": "application/json"}
    if method != "GET":
        headers["Origin"] = base
        headers["Content-Type"] = "application/json"
    payload = json.dumps(body).encode() if body is not None else None
    req = Request(base + path, data=payload, headers=headers, method=method)
    try:
        with urlopen(req, timeout=30) as response:
            data = json.load(response)
        if not isinstance(data, dict):
            raise ValueError("Host returned a non-object JSON response")
        return data
    except HTTPError as exc:
        try:
            data = json.load(exc)
            message = str(data.get("error") or data.get("detail") or exc.reason)
        except (ValueError, AttributeError):
            message = str(exc.reason)
        raise RuntimeError(f"HTTP {exc.code}: {message}") from None
    except URLError as exc:
        raise RuntimeError(f"Cannot connect to SugarAgent: {exc.reason}") from None


def execute(command, base):
    if command == "register":
        result = request(base, "/api/mcp/servers/" + SERVER + "/register", "POST")
        return {"ok": result.get("ok") is True and result.get("registered") is True,
                "action": command, "server": result.get("server"),
                "registered": result.get("registered", False)}
    if command in {"disable", "uninstall"}:
        path = f"/api/plugins/{PLUGIN}"
        result = request(base, path + "/enabled", "POST", {"enabled": False}) if command == "disable" else request(base, path, "DELETE")
        return {key: result[key] for key in ("ok", "action", "plugin_id", "trash_path", "recoverable", "error") if key in result}
    status = request(base, f"/api/{PLUGIN}/status")
    inbound = request(base, f"/api/{PLUGIN}/inbound")
    tools = request(base, "/api/mcp/tools")
    server = next((row for row in tools.get("servers", []) if row.get("server") == SERVER), {})
    summary = {"ok": status.get("ok") is True, "logged_in": status.get("logged_in", False),
        "account_uid": status.get("account_uid", ""), "auth_expired": status.get("auth_expired", False),
        "busy": status.get("busy", False), "task_count": len(status.get("tasks", [])),
        "inbound_enabled": inbound.get("enabled", False), "mcp": server,
        "asr_ready": status.get("asr_ready", False), "transcribe": status.get("transcribe", False)}
    if command == "doctor":
        availability = request(base, f"/api/plugins/{PLUGIN}/availability")
        issues = []
        if availability.get("state") not in {"ready", "degraded"}:
            issues.append("Plugin is disabled or unavailable; inspect availability checks")
        if not server.get("connected") or int(server.get("tool_count") or 0) != 14:
            issues.append("MCP is not connected with all 14 tools; inspect registration/approval and backend version")
        if not summary["logged_in"]:
            issues.append("No valid active Bilibili login")
        if summary["transcribe"] and not summary["asr_ready"]:
            issues.append("Transcription is enabled but its engine is not ready")
        summary.update(ok=summary["ok"] and not issues, issues=issues,
            availability=availability)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["status", "doctor", "register", "disable", "uninstall"], nargs="?", default="doctor")
    parser.add_argument("--base-url", default="http://127.0.0.1:" + (os.getenv("MYAGENT_SERVER_PORT") or "8192"))
    args = parser.parse_args(argv)
    base = args.base_url.rstrip("/")
    parsed = urlsplit(base)
    if (parsed.scheme not in {"http", "https"} or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
            or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment):
        parser.error("base-url must be a loopback SugarAgent origin without credentials or a path")
    try:
        result = execute(args.command, base)
    except (RuntimeError, ValueError) as exc:
        result = {"ok": False, "action": args.command, "error": str(exc)}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
