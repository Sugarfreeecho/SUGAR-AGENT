"""Framework-neutral gateway for isolated plugin pages, assets, and HTTP APIs."""
from __future__ import annotations

import base64
import binascii
import json
import threading
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Mapping
from urllib.parse import urlsplit

from agent_extensions import load_plugins
from plugins import PluginRuntimeError, get_plugin_runtime_registry
from plugins.models import PluginDefinition
from plugins.security import PluginSecurityError, normalize_namespace
from plugins.web import plugin_web_manifest, resolve_plugin_asset
from plugin_host_services import (
    PluginHostServiceError,
    consume_session_run_grant,
    execute_host_actions,
)


MAX_PLUGIN_REQUEST_BODY = 1024 * 1024
MAX_PLUGIN_RESPONSE_BODY = 5 * 1024 * 1024
_REQUEST_HEADERS = frozenset({"accept", "content-type", "if-none-match"})
_RESPONSE_HEADERS = frozenset({"cache-control", "content-type", "etag", "location"})
_concurrency_lock = threading.Lock()
_plugin_concurrency: Dict[str, threading.BoundedSemaphore] = {}


class PluginWebError(RuntimeError):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = int(status)
        self.code = str(code)


@dataclass(frozen=True)
class PluginHttpResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes


def validate_plugin_write_origin(
    method: str,
    *,
    origin: str,
    scheme: str,
    host: str,
    fetch_site: str = "",
    require_origin: bool = False,
) -> None:
    if str(method or "GET").upper() in {"GET", "HEAD", "OPTIONS"}:
        return
    site = str(fetch_site or "").strip().lower()
    if site and site not in {"same-origin", "none"}:
        raise PluginWebError(403, "cross_origin_denied", "Cross-origin plugin write denied")
    raw_origin = str(origin or "").strip()
    if not raw_origin:
        if require_origin:
            raise PluginWebError(
                403,
                "origin_required",
                "A same-origin browser request is required",
            )
        return
    parsed = urlsplit(raw_origin)
    if parsed.scheme.lower() != str(scheme or "").lower() or parsed.netloc.lower() != str(host or "").lower():
        raise PluginWebError(403, "cross_origin_denied", "Cross-origin plugin write denied")


def _enabled_plugin(plugin_id: str) -> PluginDefinition:
    namespace = normalize_namespace(plugin_id)
    loaded = load_plugins(force=True)
    plugin = next(
        (item for item in loaded.plugins if item.plugin_id == namespace),
        None,
    )
    if plugin is None:
        raise PluginWebError(404, "plugin_not_found", "Plugin is not enabled")
    return plugin


def plugin_page(plugin_id: str) -> Path:
    plugin = _enabled_plugin(plugin_id)
    try:
        manifest = plugin_web_manifest(plugin)
    except (OSError, PluginSecurityError) as exc:
        raise PluginWebError(404, "web_entry_unavailable", str(exc)) from exc
    if manifest is None or manifest.entry is None:
        raise PluginWebError(404, "web_entry_unavailable", "Plugin has no Web entry")
    return manifest.entry


def plugin_asset(plugin_id: str, asset_path: str) -> Path:
    plugin = _enabled_plugin(plugin_id)
    try:
        return resolve_plugin_asset(plugin, asset_path)
    except (OSError, PluginSecurityError) as exc:
        raise PluginWebError(404, "asset_not_found", "Plugin asset was not found") from exc


def _clean_path(value: str) -> str:
    raw = "/" + str(value or "").lstrip("/").replace("\\", "/")
    path = PurePosixPath(raw)
    if ".." in path.parts or "\x00" in raw:
        raise PluginWebError(400, "invalid_path", "Plugin API path is invalid")
    return "/" + "/".join(part for part in path.parts if part != "/")


def _clean_query(query: Mapping[str, Any]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in list(query.items())[:100]:
        name = str(key)[:256]
        if isinstance(value, (list, tuple)):
            result[name] = [str(item)[:4096] for item in value[:100]]
        else:
            result[name] = str(value)[:4096]
    return result


def _clean_headers(headers: Mapping[str, Any]) -> Dict[str, str]:
    return {
        str(key).lower(): str(value)[:8192]
        for key, value in headers.items()
        if str(key).lower() in _REQUEST_HEADERS
    }


def _validated_response(value: Any) -> PluginHttpResponse:
    if not isinstance(value, Mapping):
        raise PluginWebError(502, "invalid_plugin_response", "Plugin response must be an object")
    try:
        status = int(value.get("status") or 200)
    except (TypeError, ValueError) as exc:
        raise PluginWebError(502, "invalid_plugin_response", "Plugin status is invalid") from exc
    if status < 200 or status > 599:
        raise PluginWebError(502, "invalid_plugin_response", "Plugin status is out of range")
    raw_headers = value.get("headers") or {}
    if not isinstance(raw_headers, Mapping):
        raise PluginWebError(502, "invalid_plugin_response", "Plugin headers must be an object")
    headers = {}
    for key, item in raw_headers.items():
        name = str(key).lower()
        if name not in _RESPONSE_HEADERS:
            continue
        header_value = str(item)[:8192]
        if "\r" in header_value or "\n" in header_value:
            raise PluginWebError(502, "invalid_plugin_response", "Plugin header is invalid")
        if name == "location" and (
            header_value.startswith("//") or "://" in header_value
        ):
            raise PluginWebError(502, "invalid_plugin_response", "External redirects are denied")
        headers[name] = header_value
    if "json" in value:
        body = json.dumps(value.get("json"), ensure_ascii=False).encode("utf-8")
        headers.setdefault("content-type", "application/json; charset=utf-8")
    elif "body_base64" in value:
        try:
            body = base64.b64decode(str(value.get("body_base64") or ""), validate=True)
        except (ValueError, binascii.Error) as exc:
            raise PluginWebError(502, "invalid_plugin_response", "Plugin body is invalid base64") from exc
    else:
        body = str(value.get("body") or "").encode("utf-8")
        headers.setdefault("content-type", "text/plain; charset=utf-8")
    if len(body) > MAX_PLUGIN_RESPONSE_BODY:
        raise PluginWebError(502, "response_too_large", "Plugin response is too large")
    return PluginHttpResponse(status, headers, body)


def invoke_plugin_http(
    plugin_id: str,
    *,
    method: str,
    path: str,
    query: Mapping[str, Any],
    headers: Mapping[str, Any],
    body: bytes,
    session_run_grant: str = "",
) -> PluginHttpResponse:
    verb = str(method or "GET").upper()
    if verb not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
        raise PluginWebError(405, "method_not_allowed", "Plugin HTTP method is not allowed")
    if len(body) > MAX_PLUGIN_REQUEST_BODY:
        raise PluginWebError(413, "request_too_large", "Plugin request body is too large")
    plugin = _enabled_plugin(plugin_id)
    request = {
        "method": verb,
        "path": _clean_path(path),
        "query": _clean_query(query),
        "headers": _clean_headers(headers),
        "body_base64": base64.b64encode(body).decode("ascii"),
    }
    content_type = str(request["headers"].get("content-type") or "").lower()
    if body and "application/json" in content_type:
        try:
            request["json"] = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PluginWebError(400, "invalid_json", "Request JSON is invalid") from exc
    with _concurrency_lock:
        semaphore = _plugin_concurrency.setdefault(
            plugin.plugin_id,
            threading.BoundedSemaphore(8),
        )
    if not semaphore.acquire(blocking=False):
        raise PluginWebError(429, "plugin_busy", "Plugin Web concurrency limit reached")
    try:
        try:
            value = get_plugin_runtime_registry().handle_http(
                plugin.plugin_id,
                request,
                load_plugins(force=True).plugins,
            )
        except PluginRuntimeError as exc:
            raise PluginWebError(502, "plugin_runtime_error", str(exc)) from exc
    finally:
        semaphore.release()
    try:
        actions = value.get("_host_actions") if isinstance(value, Mapping) else None
        needs_session_grant = any(
            isinstance(action, Mapping)
            and str(action.get("service") or "").strip() == "sessions.run_many"
            for action in (actions if isinstance(actions, list) else [])
        )
        trusted_session_ids = (
            consume_session_run_grant(plugin, session_run_grant)
            if needs_session_grant
            else frozenset()
        )
        execute_host_actions(
            plugin,
            actions,
            trusted_session_ids=tuple(trusted_session_ids),
        )
    except PluginHostServiceError as exc:
        raise PluginWebError(exc.status, exc.code, str(exc)) from exc
    return _validated_response(value)


__all__ = [
    "MAX_PLUGIN_REQUEST_BODY",
    "PluginHttpResponse",
    "PluginWebError",
    "invoke_plugin_http",
    "plugin_asset",
    "plugin_page",
    "validate_plugin_write_origin",
]
