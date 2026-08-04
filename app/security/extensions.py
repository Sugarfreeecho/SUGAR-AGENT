from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit

from trusted_domains import is_trusted_host, is_trusted_url

from .runtime import security_store


_BASE_ENV = {
    "PATH",
    "PATHEXT",
    "SYSTEMROOT",
    "WINDIR",
    "COMSPEC",
    "TEMP",
    "TMP",
    "HOME",
    "USERPROFILE",
    "HOMEDRIVE",
    "HOMEPATH",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
}
_SECRET_MARKERS = (
    "API_KEY",
    "SECRET",
    "PASSWORD",
    "TOKEN",
    "PRIVATE",
    "CREDENTIAL",
    "COOKIE",
)
MCP_REGISTRATION_APPROVAL_ENV = "MCP_REGISTRATION_APPROVAL_ENABLED"


def minimal_extension_environment(
    *,
    allow_names: list[str] | tuple[str, ...] | None = None,
    explicit: Mapping[str, Any] | None = None,
) -> dict[str, str]:
    """Build a minimal environment for trusted extension processes."""
    allowed = set(_BASE_ENV)
    for name in allow_names or ():
        normalized = str(name or "").strip().upper()
        if normalized:
            allowed.add(normalized)
    env = {
        key: value
        for key, value in os.environ.items()
        if key.upper() in allowed
    }
    # Explicit values are part of the trusted configuration digest and may
    # intentionally contain credentials needed by the extension.
    env.update({str(key): str(value) for key, value in (explicit or {}).items()})
    for key in list(env):
        upper = key.upper()
        if any(marker in upper for marker in _SECRET_MARKERS) and key not in (explicit or {}):
            env.pop(key, None)
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return env


def _digest(value: Any) -> str:
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), default=str,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def plugin_descriptor(plugin: Any) -> dict[str, Any]:
    permissions = dict(getattr(plugin, "permissions", {}) or {})
    declared_permissions = {
        str(key): value
        for key, value in permissions.items()
        if str(key).lower() not in {"env", "environment"}
    }
    explicit_env = permissions.get("env") or permissions.get("environment") or {}
    if isinstance(explicit_env, Mapping):
        declared_permissions["configured_environment"] = sorted(
            str(key) for key in explicit_env
        )
    return {
        "kind": "plugin",
        "extension_id": str(getattr(plugin, "plugin_id", "") or ""),
        "name": str(getattr(plugin, "name", "") or getattr(plugin, "plugin_id", "")),
        "source": str(getattr(plugin, "manifest_path", "") or getattr(plugin, "root", "")),
        "content_digest": str(getattr(plugin, "content_signature", "") or ""),
        "config_digest": "",
        # Store and display declarations, never configured environment values.
        "capabilities": declared_permissions,
        "runtime": str(getattr(getattr(plugin, "runtime", None), "runtime_type", "") or ""),
    }


def mcp_descriptor(alias: str, config: Mapping[str, Any]) -> dict[str, Any]:
    cfg = dict(config or {})
    transport = str(cfg.get("transport") or "").strip().lower()
    if not transport:
        transport = "stdio" if cfg.get("command") else "streamable-http"
    url = str(cfg.get("url") or "")
    try:
        parsed = urlsplit(url)
        port = f":{parsed.port}" if parsed.port is not None else ""
        endpoint = (
            f"{parsed.scheme}://{parsed.hostname or ''}{port}{parsed.path}"
            if parsed.scheme else ""
        )
    except ValueError:
        endpoint = ""
    digest = _digest(cfg)
    raw_allowlist = cfg.get("env_allowlist") or cfg.get("environmentAllowlist") or []
    environment_allowlist = (
        sorted(str(item) for item in raw_allowlist)
        if isinstance(raw_allowlist, (list, tuple))
        else []
    )
    return {
        "kind": "mcp",
        "extension_id": str(alias or ""),
        "name": str(alias or ""),
        "source": endpoint or str(cfg.get("command") or ""),
        "content_digest": digest,
        "config_digest": digest,
        "capabilities": {
            "transport": transport,
            "network": transport in {"sse", "http", "streamable-http", "streamable_http"},
            "working_directory": str(
                cfg.get("cwd") or cfg.get("working_dir") or ""
            ),
            "argument_count": len(cfg.get("args") or [])
            if isinstance(cfg.get("args"), (list, tuple))
            else 0,
            "configured_environment": sorted(
                str(key) for key in (cfg.get("env") or {})
            ) if isinstance(cfg.get("env"), dict) else [],
            "environment_allowlist": environment_allowlist,
        },
        "runtime": transport,
    }


def descriptor_is_trusted(descriptor: Mapping[str, Any]) -> bool:
    return security_store().extension_is_trusted(
        kind=str(descriptor.get("kind") or ""),
        extension_id=str(descriptor.get("extension_id") or ""),
        content_digest=str(descriptor.get("content_digest") or ""),
        config_digest=str(descriptor.get("config_digest") or ""),
    )


def _descriptor_source_is_trusted(descriptor: Mapping[str, Any]) -> bool:
    source = str(descriptor.get("source") or "")
    return is_trusted_url(source) or is_trusted_host(source)


def mcp_registration_approval_enabled() -> bool:
    """Whether MCP registration requires one human confirmation per config.

    ``MCP_REGISTRATION_APPROVAL_ENABLED`` defaults to off: MCP servers start
    without a registration prompt. Set it to ``1``/``true``/``yes``/``on`` to
    restore the one-time per-config human confirmation gate.
    """
    value = (os.getenv(MCP_REGISTRATION_APPROVAL_ENV) or "0").strip().lower()
    return value not in ("0", "false", "no", "off")


def mcp_registration_is_approved(descriptor: Mapping[str, Any]) -> bool:
    if str(descriptor.get("kind") or "").strip().lower() != "mcp":
        return False
    if not mcp_registration_approval_enabled():
        return True
    if _descriptor_source_is_trusted(descriptor):
        return True
    return descriptor_is_trusted(descriptor)


def descriptor_decision(descriptor: Mapping[str, Any]) -> str:
    """Return the decision for the descriptor's exact current digests.

    ``pending`` includes both first-seen extensions and extensions whose
    executable content/configuration changed after an earlier decision.
    """
    if descriptor.get("kind") == "mcp" and not mcp_registration_approval_enabled():
        return "trusted"
    if descriptor.get("kind") == "mcp" and _descriptor_source_is_trusted(descriptor):
        return "trusted"
    row = security_store().get_extension_trust(
        kind=str(descriptor.get("kind") or ""),
        extension_id=str(descriptor.get("extension_id") or ""),
    )
    if not row:
        return "pending"
    if (
        str(row.get("content_digest") or "")
        != str(descriptor.get("content_digest") or "")
        or str(row.get("config_digest") or "")
        != str(descriptor.get("config_digest") or "")
    ):
        return "pending"
    return "trusted" if row.get("decision") == "trusted" else "rejected"


def _decorate_decision(descriptor: dict[str, Any]) -> dict[str, Any]:
    decision = descriptor_decision(descriptor)
    descriptor["trusted"] = decision == "trusted"
    descriptor["decision"] = decision
    if descriptor.get("kind") == "mcp":
        descriptor["registration_status"] = (
            "registered" if decision == "trusted" else decision
        )
    return descriptor


def extension_candidates() -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    try:
        from agent_extensions import load_plugins

        for plugin in load_plugins(force=True).plugins:
            descriptor = plugin_descriptor(plugin)
            candidates.append(_decorate_decision(descriptor))
    except Exception:
        pass
    try:
        import agent_mcp

        servers, _ = agent_mcp._load_servers_dict_from_config()
        for alias, config in (servers or {}).items():
            if not isinstance(config, Mapping):
                continue
            descriptor = mcp_descriptor(str(alias), config)
            candidates.append(_decorate_decision(descriptor))
    except Exception:
        pass
    return sorted(candidates, key=lambda item: (item["kind"], item["extension_id"]))


def current_extension_descriptor(kind: str, extension_id: str) -> dict[str, Any] | None:
    kind = str(kind or "").strip().lower()
    extension_id = str(extension_id or "").strip()
    for descriptor in extension_candidates():
        if descriptor["kind"] == kind and descriptor["extension_id"] == extension_id:
            return descriptor
    return None


def trust_current_extension(kind: str, extension_id: str) -> dict[str, Any]:
    descriptor = current_extension_descriptor(kind, extension_id)
    if descriptor is None:
        raise ValueError("extension is not currently installed or configured")
    security_store().set_extension_trust(
        kind=descriptor["kind"],
        extension_id=descriptor["extension_id"],
        source=descriptor["source"],
        content_digest=descriptor["content_digest"],
        config_digest=descriptor["config_digest"],
        capabilities=dict(descriptor.get("capabilities") or {}),
        decision="trusted",
    )
    descriptor["trusted"] = True
    descriptor["decision"] = "trusted"
    if descriptor["kind"] == "mcp":
        descriptor["registration_status"] = "registered"
    return descriptor


def decide_current_mcp_registration(
    extension_id: str,
    *,
    config_digest: str,
    approved: bool,
) -> dict[str, Any]:
    """Record a human registration decision for one exact MCP config.

    Registration approval authorizes starting/connecting the server and
    discovering its tools. Individual tool calls remain subject to the normal
    central capability policy.
    """
    descriptor = current_extension_descriptor("mcp", extension_id)
    if descriptor is None:
        raise ValueError("MCP server is not currently configured")
    expected = str(config_digest or "").strip()
    actual = str(descriptor.get("config_digest") or "")
    if not expected or expected != actual:
        raise ValueError("MCP configuration changed; review the current configuration")
    security_store().set_extension_trust(
        kind="mcp",
        extension_id=descriptor["extension_id"],
        source=descriptor["source"],
        content_digest=descriptor["content_digest"],
        config_digest=actual,
        capabilities=dict(descriptor.get("capabilities") or {}),
        decision="trusted" if approved else "revoked",
    )
    descriptor["trusted"] = bool(approved)
    descriptor["decision"] = "trusted" if approved else "rejected"
    descriptor["registration_status"] = "registered" if approved else "rejected"
    return descriptor


def mcp_registration_candidates() -> list[dict[str, Any]]:
    return [item for item in extension_candidates() if item.get("kind") == "mcp"]


def revoke_extension(kind: str, extension_id: str) -> bool:
    return security_store().revoke_extension_trust(kind, extension_id)
