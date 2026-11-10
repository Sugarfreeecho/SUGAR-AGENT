"""Validated deep-link targets for notifications and UI activation.

A notification can point at more than a conversation: a plugin page or one
settings tab.  The target travels through the OS toast, the desktop shell and
the activation heartbeat, so every hop must be able to reject arbitrary UI
state.  Shape checks live here (also used by the tray launcher); catalog checks
stay on the backend, which knows which plugin pages are currently enabled.
"""
from __future__ import annotations

import re
from urllib.parse import parse_qs

PLUGIN_ID = re.compile(r"[a-z0-9][a-z0-9._-]{0,127}")
SETTINGS_SECTIONS = {
    "general", "models", "skills", "plugins", "hooks", "mcp", "usage",
    "security", "schedules", "env", "paths",
}
_PLUGIN_SECTION = re.compile(
    r"plugin:[a-z0-9][a-z0-9._-]{0,127}:[a-z0-9][a-z0-9._-]{0,127}"
)
_SECTION_PARAM = re.compile(
    r"(?:general|models|skills|plugins|hooks|mcp|usage|security|schedules|env|paths"
    r"|plugin:[a-z0-9][a-z0-9._-]{0,127}:[a-z0-9][a-z0-9._-]{0,127})"
)


def plugin_pages():
    """Return currently available plugin-page contributions.

    Disabled or undeclared plugins are absent from the catalog, so a stale
    notification cannot open a page the user has turned off.
    """

    from agent_extensions import plugin_catalog_snapshot

    return [
        row for row in plugin_catalog_snapshot().get("ui_contributions", [])
        if row.get("slot") in {"details.tab", "navigation"}
        and row.get("target") == "plugin-page"
    ]


def settings_section(section: str) -> str:
    """Validate a built-in or declared plugin settings tab."""

    if section in SETTINGS_SECTIONS:
        return section
    if section.startswith("plugin:"):
        from agent_extensions import plugin_catalog_snapshot

        for row in plugin_catalog_snapshot().get("ui_contributions", []):
            if (row.get("slot") == "settings.section"
                    and section == f"plugin:{row.get('plugin_id')}:{row.get('id')}"):
                return section
    raise ValueError(
        "section is not an available settings tab: general, models, skills, plugins, "
        "hooks, mcp, usage, security, schedules, env, paths or a declared "
        "plugin:<id>:<section>"
    )


def plugin_target(plugin_id: str, page_id: str = "") -> dict:
    """Resolve an enabled plugin page, defaulting to its first declared page."""

    if not PLUGIN_ID.fullmatch(plugin_id or ""):
        raise ValueError("invalid plugin_id")
    if page_id and not PLUGIN_ID.fullmatch(page_id):
        raise ValueError("invalid page_id")
    pages = [
        row for row in plugin_pages()
        if row.get("plugin_id") == plugin_id and (not page_id or row.get("id") == page_id)
    ]
    if not pages:
        raise ValueError(
            "plugin page is unavailable; use kind=plugin without plugin_id to open "
            "the available plugin catalogue"
        )
    return {"kind": "plugin", "plugin_id": plugin_id, "page_id": str(pages[0]["id"])}


def settings_target(section: str) -> dict:
    return {"kind": "settings", "section": settings_section(section or "general")}


def sanitize_target(value) -> dict | None:
    """Return a shape-valid target without consulting the plugin catalog.

    Used by the tray and desktop shell, which can start before the backend has
    loaded plugins.  The backend still re-validates against live declarations.
    """

    if not isinstance(value, dict):
        return None
    kind = str(value.get("kind") or "").strip()
    if kind == "plugin":
        plugin_id = str(value.get("plugin_id") or "").strip()
        page_id = str(value.get("page_id") or "").strip()
        if not PLUGIN_ID.fullmatch(plugin_id) or (page_id and not PLUGIN_ID.fullmatch(page_id)):
            return None
        target = {"kind": "plugin", "plugin_id": plugin_id}
        if page_id:
            target["page_id"] = page_id
        return target
    if kind == "settings":
        section = str(value.get("section") or "").strip()
        if not _SECTION_PARAM.fullmatch(section):
            return None
        return {"kind": "settings", "section": section}
    return None


def normalize_target(value) -> dict | None:
    """Validate a target against the currently enabled plugin declarations."""

    target = sanitize_target(value)
    if target is None:
        return None
    if target["kind"] == "plugin":
        return plugin_target(target["plugin_id"], target.get("page_id", ""))
    return settings_target(target["section"])


def target_from_query(query: str) -> dict | None:
    """Read a target from ``plugin``/``page``/``section`` query parameters."""

    try:
        values = parse_qs(str(query or ""))
    except ValueError:
        return None

    def first(name: str) -> str:
        candidates = values.get(name) or []
        return str(candidates[0] if candidates else "").strip()

    plugin_id = first("plugin")
    if plugin_id:
        return sanitize_target({
            "kind": "plugin", "plugin_id": plugin_id, "page_id": first("page"),
        })
    section = first("section")
    if section:
        return sanitize_target({"kind": "settings", "section": section})
    return None


def target_query_params(target) -> dict[str, str]:
    """Map a target onto the browser deep-link query parameters."""

    target = sanitize_target(target)
    if target is None:
        return {}
    if target["kind"] == "plugin":
        params = {"open_plugin": target["plugin_id"]}
        if target.get("page_id"):
            params["open_page"] = target["page_id"]
        return params
    return {"open_settings": target["section"]}


def target_env(target) -> dict[str, str]:
    """Environment variables consumed by the Windows toast script."""

    target = sanitize_target(target)
    if target is None:
        return {}
    if target["kind"] == "plugin":
        env = {"SUGARAGENT_NOTIFY_PLUGIN": target["plugin_id"]}
        if target.get("page_id"):
            env["SUGARAGENT_NOTIFY_PAGE"] = target["page_id"]
        return env
    return {"SUGARAGENT_NOTIFY_SECTION": target["section"]}


__all__ = [
    "PLUGIN_ID",
    "SETTINGS_SECTIONS",
    "normalize_target",
    "plugin_pages",
    "plugin_target",
    "sanitize_target",
    "settings_section",
    "settings_target",
    "target_env",
    "target_from_query",
    "target_query_params",
]
