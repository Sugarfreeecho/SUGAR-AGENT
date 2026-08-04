"""Built-in trusted domains shared by approval, MCP, and model recognition.

Huawei domains are trusted by default: websites, APIs, shell network commands
and MCP endpoints under these domains do not require approval. The list is
deliberately small and label-bound so lookalike domains such as
``evilhuawei.com`` never match.
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit


HUAWEI_DOMAINS: frozenset[str] = frozenset(
    {
        "huawei.com",
        "huaweicloud.com",
        "myhuaweicloud.com",
    }
)

TRUSTED_DOMAINS: frozenset[str] = HUAWEI_DOMAINS

_URL_TOKEN = re.compile(r"(?i)https?://[^\s\"'<>`|;&]+")
_SHELL_CONTROL = re.compile(r"[;&|`\n]|\$\(|\b(?:eval|iex)\b", re.I)
_WRAPPER_TOKENS = frozenset(
    {"sudo", "doas", "env", "nohup", "nice", "timeout", "stdbuf"}
)
_NETWORK_FIRST_TOOLS = frozenset(
    {
        "curl",
        "wget",
        "iwr",
        "irm",
        "invoke-webrequest",
        "invoke-restmethod",
        "git",
        "pip",
        "pip3",
        "npm",
        "pnpm",
        "yarn",
    }
)


def normalize_host(host: object) -> str:
    """Normalize a hostname for matching (lowercase, no port, no www).

    Accepts bare hostnames, ``host:port`` and full URLs such as
    ``http://ai.threecloud.huawei.com/path``.
    """
    text = str(host or "").strip().lower().rstrip(".")
    if not text:
        return ""
    if "://" in text:
        try:
            parsed = urlsplit(text)
        except ValueError:
            return ""
        if not parsed.hostname:
            return ""
        text = parsed.hostname
    elif text.startswith("["):
        end = text.find("]")
        if end > 0:
            text = text[1:end]
    elif text.count(":") == 1:
        text = text.rsplit(":", 1)[0]
    return text.removeprefix("www.")


def _host_matches(host: object, domains: frozenset[str]) -> bool:
    normalized = normalize_host(host)
    if not normalized:
        return False
    if normalized in domains:
        return True
    parts = normalized.split(".")
    for i in range(1, len(parts) - 1):
        if ".".join(parts[i:]) in domains:
            return True
    return False


def is_trusted_host(host: object) -> bool:
    """True for ``huawei.com``, ``myhuaweicloud.com`` and any subdomain."""
    return _host_matches(host, TRUSTED_DOMAINS)


def is_huawei_host(host: object) -> bool:
    return _host_matches(host, HUAWEI_DOMAINS)


def _url_hostname(url: str) -> str | None:
    try:
        parsed = urlsplit(url)
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None
    return parsed.hostname


def is_trusted_url(url: object) -> bool:
    host = _url_hostname(str(url or ""))
    return bool(host) and is_trusted_host(host)


def network_urls_in(text: object) -> list[str]:
    return _URL_TOKEN.findall(str(text or ""))


def all_network_urls_trusted(text: object) -> bool:
    urls = network_urls_in(text)
    return bool(urls) and all(is_trusted_url(url) for url in urls)


def _first_command_token(text: str) -> str:
    tokens = text.split()
    if not tokens:
        return ""
    first = tokens[0].strip("\"'").lower()
    while first in _WRAPPER_TOKENS and len(tokens) > 1:
        tokens = tokens[1:]
        first = tokens[0].strip("\"'").lower()
    return first


def trusted_network_command(command: object) -> bool:
    """Conservative check for a single shell command that only contacts trusted hosts.

    Auto-allow only simple, non-chained network commands (``curl``, ``wget``,
    ``git clone``, package managers with a trusted index URL, ...) where every
    URL in the command is a trusted domain. Pipes, separators, dynamic code
    and bare host arguments still require approval.
    """
    text = str(command or "").strip()
    if not text:
        return False
    if _SHELL_CONTROL.search(text):
        return False
    if not all_network_urls_trusted(text):
        return False
    return _first_command_token(text) in _NETWORK_FIRST_TOOLS
