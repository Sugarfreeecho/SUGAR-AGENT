from __future__ import annotations

import re
import shlex
from pathlib import Path
from typing import Iterable
from urllib.parse import urlsplit

from .models import CommandSegment, EgressDestination, EgressIntent, ShellAnalysis


_URL_RE = re.compile(r"(?i)\b(?P<url>(?:https?|ftp|ftps|ssh|sftp)://[^\s\"'<>|;]+)")
_REMOTE_RE = re.compile(r"^(?:(?P<user>[^@\s:]+)@)?(?P<host>[A-Za-z0-9._-]+):(?P<path>.+)$")
_ENV_RE = re.compile(r"(?:\$\{?[A-Za-z_][A-Za-z0-9_]*\}?|\$env:[A-Za-z_][A-Za-z0-9_]*|%[A-Za-z_][A-Za-z0-9_]*%)", re.I)
_DYNAMIC_RE = re.compile(
    r"(?i)(?:\$\(|`[^`]+`|\beval\b|invoke-expression|\biex\b|-(?:enc|encodedcommand)\b|"
    r"\b(?:python|python3|node|ruby|perl)\s+(?:-c|-e)\b)"
)
_NETWORK_CODE_RE = re.compile(
    r"(?i)(?:https?://|\b(?:socket|tcpclient|udpclient|requests\.|urllib\.|httpx\.|aiohttp\.|"
    r"axios\.|net\.connect|http\.request|https\.request)\b|fetch\s*\(|\.connect\s*\()"
)
_SENSITIVE_RE = re.compile(
    r"(?i)(?:^|[/\\])(?:\.env(?:\.[\w.-]+)?|id_rsa|id_ed25519|credentials\.json|login data)$|"
    r"(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|secret)"
)
_UPLOAD_FLAGS = {
    "-d", "--data", "--data-raw", "--data-binary", "--data-urlencode", "--json",
    "-f", "--form", "--form-string", "-t", "--upload-file",
}
_WRAPPERS = {"command", "env", "sudo", "doas", "nohup", "timeout", "time", "nice", "stdbuf"}
_LOCAL_DATA_COMMANDS = {"echo", "printf", "write-output", "cat", "type", "get-content"}


def _split_segments(command: str) -> list[tuple[str, str]]:
    """Split shell control operators without treating quoted operators as syntax."""
    rows: list[tuple[str, str]] = []
    start = 0
    quote = ""
    escape = False
    i = 0
    previous_op = ""
    while i < len(command):
        ch = command[i]
        if escape:
            escape = False
            i += 1
            continue
        if ch == "\\" and quote != "'":
            escape = True
            i += 1
            continue
        if quote:
            if ch == quote:
                quote = ""
            i += 1
            continue
        if ch in "'\"":
            quote = ch
            i += 1
            continue
        op = ""
        if command.startswith("&&", i) or command.startswith("||", i):
            op = command[i:i + 2]
        elif ch in ";|\n\r":
            op = "|" if ch == "|" else ";"
        if op:
            text = command[start:i].strip()
            if text:
                rows.append((text, previous_op))
            previous_op = op
            i += len(op)
            start = i
            continue
        i += 1
    tail = command[start:].strip()
    if tail:
        rows.append((tail, previous_op))
    return rows


def _tokens(text: str) -> list[str]:
    try:
        return shlex.split(text, posix=True)
    except ValueError:
        return re.findall(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|[^\s]+', text)


def _clean_token(token: str) -> str:
    return str(token or "").strip().strip("\"'").rstrip(",)")


def _basename(token: str) -> str:
    return Path(_clean_token(token).replace("\\", "/")).name.lower().removesuffix(".exe")


def _command_tokens(tokens: list[str]) -> tuple[str, list[str]]:
    index = 0
    while index < len(tokens):
        value = _clean_token(tokens[index])
        low = _basename(value)
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", value):
            index += 1
            continue
        if low in _WRAPPERS:
            index += 1
            if low in {"timeout", "nice", "stdbuf"}:
                while index < len(tokens) and _clean_token(tokens[index]).startswith("-"):
                    index += 1
            continue
        return low, tokens[index + 1:]
    return "", []


def _destinations(tokens: Iterable[str]) -> tuple[EgressDestination, ...]:
    found: list[EgressDestination] = []
    seen: set[tuple[str, int | None, str, str]] = set()
    for raw in tokens:
        value = _clean_token(raw)
        for match in _URL_RE.finditer(value):
            url = match.group("url")
            try:
                parsed = urlsplit(url)
            except ValueError:
                continue
            if not parsed.hostname:
                continue
            port = parsed.port
            if port is None:
                port = 443 if parsed.scheme.lower() in {"https", "ftps"} else 80 if parsed.scheme.lower() == "http" else None
            item = EgressDestination(parsed.hostname.lower(), port, parsed.scheme.lower(), parsed.path or "/")
            key = (item.host, item.port, item.scheme, item.resource)
            if key not in seen:
                found.append(item)
                seen.add(key)
    return tuple(found)


def _display_source(value: str, *, inline: bool = False) -> str:
    value = _clean_token(value)
    if _ENV_RE.search(value):
        return "environment variable"
    if "=@" in value:
        value = value.split("=@", 1)[1]
    elif value.startswith("@"):
        value = value[1:]
    if inline:
        return "inline request data"
    if _SENSITIVE_RE.search(value):
        return "<sensitive file>"
    return value or "stdin"


def _sources_from_flags(args: list[str], flags: set[str], *, inline_flags: set[str] | None = None) -> list[str]:
    result: list[str] = []
    inline_flags = inline_flags or set()
    for i, raw in enumerate(args):
        low = _clean_token(raw).lower()
        key, sep, attached = low.partition("=")
        if key not in flags:
            continue
        value = attached if sep else (_clean_token(args[i + 1]) if i + 1 < len(args) else "stdin")
        result.append(_display_source(value, inline=key in inline_flags and "@" not in value))
    return result


def _git_subcommand(args: list[str]) -> tuple[str, list[str]]:
    i = 0
    takes_value = {"-c", "-C", "--git-dir", "--work-tree", "--namespace", "--config-env"}
    while i < len(args):
        token = _clean_token(args[i])
        if token in takes_value:
            i += 2
            continue
        if any(token.startswith(name + "=") for name in takes_value if name.startswith("--")):
            i += 1
            continue
        if token.startswith("-"):
            i += 1
            continue
        return token.lower(), args[i + 1:]
    return "", []


def _remoteish(value: str) -> bool:
    value = _clean_token(value)
    return bool(_URL_RE.search(value) or (_REMOTE_RE.match(value) and not re.match(r"^[A-Za-z]:", value)) or re.match(r"^[A-Za-z][\w.-]{1,}:", value))


def _remote_destination(value: str) -> EgressDestination | None:
    cleaned = _clean_token(value)
    match = _REMOTE_RE.match(cleaned)
    if not match or re.match(r"^[A-Za-z]:", cleaned):
        return None
    return EgressDestination(match.group("host").lower(), 22, "ssh", match.group("path"))


def _segment(text: str, previous_op: str) -> CommandSegment:
    tokens = _tokens(text)
    executable, args = _command_tokens(tokens)
    low_args = [_clean_token(item).lower() for item in args]
    dynamic = bool(_DYNAMIC_RE.search(text))
    intent = EgressIntent.NONE
    family = executable
    operation = ""
    sources: list[str] = []
    destinations = _destinations(tokens)

    if executable in {"curl", "curl.exe"}:
        family = "curl"
        method = ""
        for i, value in enumerate(low_args):
            if value in {"-x", "--request"} and i + 1 < len(low_args): method = low_args[i + 1].upper()
            if value.startswith("--request="): method = value.split("=", 1)[1].upper()
        sources = _sources_from_flags(
            args,
            _UPLOAD_FLAGS,
            inline_flags={"-d", "--data", "--data-raw", "--data-binary", "--data-urlencode", "--json", "-f", "--form", "--form-string"},
        )
        upload = bool(sources or any(v in _UPLOAD_FLAGS or any(v.startswith(flag + "=") for flag in _UPLOAD_FLAGS) for v in low_args) or method in {"POST", "PUT", "PATCH"})
        intent = EgressIntent.UPLOAD if upload else EgressIntent.READ
        operation = "upload" if upload else (method.lower() if method else "get")
    elif executable in {"wget"}:
        family = "wget"
        flags = {"--post-data", "--post-file", "--body-data", "--body-file", "--method"}
        sources = _sources_from_flags(args, flags, inline_flags={"--post-data", "--body-data", "--method"})
        upload = bool(sources or any(v.startswith(("--post-", "--body-")) for v in low_args) or any(v in {"post", "put", "patch"} for v in low_args))
        intent, operation = (EgressIntent.UPLOAD, "upload") if upload else (EgressIntent.READ, "download")
    elif executable in {"invoke-webrequest", "invoke-restmethod", "iwr", "irm"}:
        family = "powershell-web"
        flags = {"-body", "-infile", "-form"}
        sources = _sources_from_flags(args, flags, inline_flags={"-body", "-form"})
        upload = bool(sources or any(v in {"post", "put", "patch"} for v in low_args))
        intent, operation = (EgressIntent.UPLOAD, "upload") if upload else (EgressIntent.READ, "get")
    elif re.search(r"(?i)\b(?:system\.net\.)?webclient\s*\([^)]*\)\s*\.\s*upload(?:file|string|data|values)\b", text):
        family, operation, intent = "webclient", "upload", EgressIntent.UPLOAD
    elif re.search(r"(?i)\b(?:system\.net\.)?webclient\s*\([^)]*\)\s*\.\s*download", text):
        family, operation, intent = "webclient", "download", EgressIntent.READ
    elif executable == "git":
        subcommand, rest = _git_subcommand(args)
        family, operation = "git", subcommand
        if subcommand == "push":
            intent = EgressIntent.UPLOAD
            if rest: destinations = destinations or (EgressDestination(_clean_token(rest[0]).lower(), 22 if ":" in _clean_token(rest[0]) else None, "git", ""),)
            sources = ["git objects/refs"]
        elif subcommand in {"clone", "fetch", "pull", "ls-remote"}:
            intent = EgressIntent.READ
            if rest: destinations = destinations or (EgressDestination(_clean_token(rest[0]).lower(), None, "git", ""),)
        elif subcommand in {"send-email"}:
            intent, sources = EgressIntent.UPLOAD, ["git patches"]
    elif executable in {"scp", "sftp", "rsync"}:
        family = executable
        positional = [v for v in args if not _clean_token(v).startswith("-")]
        if len(positional) >= 2:
            src_remote, dst_remote = _remoteish(positional[-2]), _remoteish(positional[-1])
            if dst_remote and not src_remote:
                intent, operation, sources = EgressIntent.UPLOAD, "upload", [_clean_token(positional[-2])]
                remote_target = _remote_destination(positional[-1])
                if remote_target: destinations = destinations or (remote_target,)
            elif src_remote and not dst_remote:
                intent, operation = EgressIntent.READ, "download"
                remote_target = _remote_destination(positional[-2])
                if remote_target: destinations = destinations or (remote_target,)
            else:
                intent, operation = EgressIntent.UNKNOWN, "transfer"
        else:
            intent, operation = EgressIntent.INTERACTIVE, "session"
    elif executable == "rclone":
        operation = low_args[0] if low_args else ""
        family = "rclone"
        positional = [v for v in args[1:] if not _clean_token(v).startswith("-")]
        if operation in {"copy", "copyto", "sync", "move", "moveto"} and len(positional) >= 2:
            src_remote, dst_remote = _remoteish(positional[-2]), _remoteish(positional[-1])
            intent = EgressIntent.UPLOAD if dst_remote and not src_remote else EgressIntent.READ if src_remote and not dst_remote else EgressIntent.UNKNOWN
            if intent == EgressIntent.UPLOAD: sources = [_clean_token(positional[-2])]
        elif operation in {"ls", "lsd", "lsl", "cat", "size", "check"}:
            intent = EgressIntent.READ
        else:
            intent = EgressIntent.UNKNOWN
    elif executable == "aws" and len(low_args) >= 2 and low_args[0] == "s3" and low_args[1] in {"cp", "sync", "mv"}:
        family, operation = "aws-s3", low_args[1]
        positional = [v for v in args[2:] if not _clean_token(v).startswith("-")]
        if len(positional) >= 2:
            intent = EgressIntent.UPLOAD if _clean_token(positional[-1]).lower().startswith("s3://") else EgressIntent.READ
            if intent == EgressIntent.UPLOAD: sources = [_clean_token(positional[-2])]
    elif executable in {"gsutil"} and low_args and low_args[0] in {"cp", "rsync", "mv"}:
        family, operation = "gsutil", low_args[0]
        positional = [v for v in args[1:] if not _clean_token(v).startswith("-")]
        intent = EgressIntent.UPLOAD if positional and _clean_token(positional[-1]).lower().startswith("gs://") else EgressIntent.READ
        if intent == EgressIntent.UPLOAD and len(positional) >= 2: sources = [_clean_token(positional[-2])]
    elif executable == "gcloud" and len(low_args) >= 3 and low_args[:2] == ["storage", "cp"]:
        family, operation = "gcloud-storage", "cp"
        intent = EgressIntent.UPLOAD if _clean_token(args[-1]).lower().startswith("gs://") else EgressIntent.READ
        if intent == EgressIntent.UPLOAD: sources = [_clean_token(args[-2])]
    elif executable in {"az", "azcopy"}:
        family = executable
        joined = " ".join(low_args)
        if executable == "az" and "storage blob upload" in joined:
            intent, operation = EgressIntent.UPLOAD, "storage-blob-upload"
            sources = _sources_from_flags(args, {"--file", "-f"})
        elif executable == "azcopy" and low_args and low_args[0] in {"copy", "sync"}:
            operation = low_args[0]
            intent = EgressIntent.UPLOAD if len(args) >= 3 and _remoteish(args[-1]) else EgressIntent.READ
            if intent == EgressIntent.UPLOAD: sources = [_clean_token(args[-2])]
        else:
            intent = EgressIntent.UNKNOWN if destinations else EgressIntent.NONE
    elif executable == "gh" and len(low_args) >= 2 and low_args[:2] == ["release", "upload"]:
        family, operation, intent = "gh-release", "upload", EgressIntent.UPLOAD
        sources = [_clean_token(v) for v in args[3:] if not _clean_token(v).startswith("-")]
    elif executable == "docker" and low_args and low_args[0] in {"push", "pull"}:
        family, operation = "docker", low_args[0]
        intent = EgressIntent.UPLOAD if operation == "push" else EgressIntent.READ
        if intent == EgressIntent.UPLOAD: sources = ["container image"]
    elif executable in {"npm", "pnpm", "yarn"} and low_args:
        family, operation = executable, low_args[0]
        if operation == "publish": intent, sources = EgressIntent.UPLOAD, ["package contents"]
        elif operation in {"install", "add", "update"}: intent = EgressIntent.READ
    elif executable == "twine" and low_args and low_args[0] == "upload":
        family, operation, intent = "twine", "upload", EgressIntent.UPLOAD
        sources = [_clean_token(v) for v in args[1:] if not _clean_token(v).startswith("-")]
    elif executable in {"ssh", "ftp", "telnet", "nc", "ncat"}:
        family, operation, intent = executable, "interactive", EgressIntent.INTERACTIVE
    elif executable in {"powershell", "pwsh", "cmd", "bash", "sh", "zsh"}:
        command_flags = {"-command", "-c", "/c"}
        nested_text = ""
        for i, value in enumerate(low_args):
            if value in command_flags and i + 1 < len(args):
                nested_text = _clean_token(args[i + 1])
                break
        if nested_text:
            nested = analyze_shell_command(nested_text)
            family, operation, intent = executable, f"nested:{nested.operation or 'command'}", nested.intent
            destinations, sources = nested.destinations, list(nested.data_sources)
            dynamic = True
        elif _NETWORK_CODE_RE.search(text):
            family, operation, intent = executable, "dynamic-network", EgressIntent.UNKNOWN
    elif _NETWORK_CODE_RE.search(text) and executable not in _LOCAL_DATA_COMMANDS:
        family, operation, intent = executable or "dynamic", "dynamic-network", EgressIntent.UNKNOWN
    elif destinations and executable not in _LOCAL_DATA_COMMANDS:
        family, operation, intent = executable or "unknown", "unknown-network", EgressIntent.UNKNOWN

    if previous_op == "|" and intent == EgressIntent.UPLOAD and "stdin" not in sources:
        sources.append("stdin")
    if intent in {EgressIntent.READ, EgressIntent.UPLOAD} and ("$(" in text or _ENV_RE.search(text)):
        dynamic = True
        if intent == EgressIntent.UPLOAD and not sources: sources.append("dynamic input")
    return CommandSegment(text, executable, family, operation, intent, destinations, tuple(dict.fromkeys(sources)), dynamic)


def analyze_shell_command(command: object, shell_kind: str = "auto") -> ShellAnalysis:
    text = str(command or "")
    parse_errors: list[str] = []
    try:
        segments = tuple(_segment(part, op) for part, op in _split_segments(text))
    except Exception as exc:
        segments = (CommandSegment(text=text, family="unknown", operation="parse-error", intent=EgressIntent.UNKNOWN, dynamic=True),)
        parse_errors.append(type(exc).__name__)

    priority = {
        EgressIntent.NONE: 0,
        EgressIntent.READ: 1,
        EgressIntent.INTERACTIVE: 2,
        EgressIntent.UNKNOWN: 3,
        EgressIntent.UPLOAD: 4,
    }
    intent = max((row.intent for row in segments), key=lambda item: priority[item], default=EgressIntent.NONE)
    destinations: list[EgressDestination] = []
    sources: list[str] = []
    for row in segments:
        for item in row.destinations:
            if item not in destinations: destinations.append(item)
        for item in row.data_sources:
            if item not in sources: sources.append(item)
    sensitive = any(_SENSITIVE_RE.search(_clean_token(item)) for item in sources) or bool(
        intent == EgressIntent.UPLOAD and _SENSITIVE_RE.search(text)
    )
    sources = list(dict.fromkeys(_display_source(item) for item in sources))
    relevant = [row for row in segments if row.intent != EgressIntent.NONE]
    unknown_target = bool(intent != EgressIntent.NONE and not destinations)
    confidence = "low" if parse_errors or any(row.dynamic for row in relevant) or intent == EgressIntent.UNKNOWN else "high"
    family = relevant[0].family if len(relevant) == 1 else "mixed" if relevant else ""
    operation = relevant[0].operation if len(relevant) == 1 else "mixed" if relevant else ""
    return ShellAnalysis(
        intent=intent,
        segments=segments,
        destinations=tuple(destinations),
        data_sources=tuple(sources),
        confidence=confidence,
        command_family=family,
        operation=operation,
        sensitive_source=sensitive,
        unknown_target=unknown_target,
        parse_errors=tuple(parse_errors),
    )


def egress_rule_fingerprint(analysis: ShellAnalysis) -> str | None:
    if analysis.intent != EgressIntent.UPLOAD or analysis.sensitive_source or analysis.unknown_target:
        return None
    targets = sorted({item.host for item in analysis.destinations if item.host})
    if not targets:
        return None
    return f"egress:upload:{analysis.command_family}:{analysis.operation}:{','.join(targets)}"
