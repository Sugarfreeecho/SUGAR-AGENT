"""Durable requests to present content, open settings or notify the user."""
from __future__ import annotations

import copy
import json
import logging
import os
import re
import uuid
from functools import partial
from pathlib import Path
from urllib.parse import urlsplit

from agent_fact_commit import run_fact_commit
from runtime_v2.event_schema import now_iso
from tool_registry import ToolOutcome

_KINDS = {"webpage", "text", "image", "file", "plugin", "notice", "settings", "notification"}
_SETTINGS_SECTIONS = {"general", "models", "skills", "plugins", "hooks", "mcp", "usage", "security", "env", "paths"}
_PLUGIN_ID = re.compile(r"[a-z0-9][a-z0-9._-]{0,127}")
logger = logging.getLogger(__name__)


def _text(arguments, key, maximum, *, required=False):
    value = arguments.get(key, "")
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()):
        raise ValueError(f"{key} must be {'a nonempty' if required else 'a'} string within {maximum} characters")
    return value


def _plugin_pages():
    from agent_extensions import plugin_catalog_snapshot
    return [row for row in plugin_catalog_snapshot().get("ui_contributions", [])
            if row.get("slot") in {"details.tab", "navigation"} and row.get("target") == "plugin-page"]


def _settings_section(section):
    if section in _SETTINGS_SECTIONS:
        return section
    if section.startswith("plugin:"):
        from agent_extensions import plugin_catalog_snapshot
        for row in plugin_catalog_snapshot().get("ui_contributions", []):
            if row.get("slot") == "settings.section" and section == f"plugin:{row.get('plugin_id')}:{row.get('id')}":
                return section
    raise ValueError("section is not an available settings tab: general, models, skills, plugins, hooks, mcp, usage, security, env, paths or a declared plugin:<id>:<section>")


def prepare_presentation(arguments, *, workspace):
    kind = _text(arguments, "kind", 20, required=True)
    if kind not in _KINDS:
        raise ValueError("kind must be webpage, text, image, file, plugin, notice, settings or notification")
    title = _text(arguments, "title", 100, required=True).strip()
    out = {"kind": kind, "title": title}
    if kind in {"notice", "notification"}:
        out["text"] = _text(arguments, "text", 4000 if kind == "notice" else 2000, required=True)
        if kind == "notice":
            out["level"] = arguments.get("level", "info")
            if out["level"] not in {"info", "success", "warning", "error"}:
                raise ValueError("level must be info, success, warning or error")
            duration = arguments.get("duration_ms", 8000)
            if type(duration) is not int or (duration != 0 and not 1000 <= duration <= 30000):
                raise ValueError("duration_ms must be 0 (until dismissed) or 1000–30000")
            out["duration_ms"] = duration
    elif kind == "settings":
        out["section"] = _settings_section(_text(arguments, "section", 264).strip() or "general")
    elif kind == "webpage":
        url = _text(arguments, "url", 4096, required=True).strip()
        parsed = urlsplit(url)
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                or parsed.username or parsed.password or "\\" in url or any(c.isspace() for c in url)):
            raise ValueError("url must be an absolute HTTP(S) URL without credentials")
        parsed.port  # Validate invalid/out-of-range ports before publishing.
        out["url"] = url
    elif kind == "text":
        out["text"] = _text(arguments, "text", 65536, required=True)
        out["format"] = arguments.get("format", "text")
        if out["format"] not in {"text", "markdown"}:
            raise ValueError("format must be text or markdown")
    elif kind == "image":
        from human_interaction.images import normalize_images, admit_question_images
        image = {key: arguments[key] for key in ("attachment_id", "data_url", "alt", "caption") if key in arguments}
        question = {"images": normalize_images([image], "image")}
        admit_question_images([question])
        out["image"] = question["images"][0]
    elif kind == "file":
        raw = _text(arguments, "path", 4096, required=True)
        root = Path(workspace).resolve()
        path = Path(raw).expanduser()
        path = (path if path.is_absolute() else root / path).resolve()
        if not path.is_relative_to(root):
            raise ValueError("file must be inside the current session workspace; use read_file and an image attachment for an external image")
        if not path.is_file():
            raise ValueError("file does not exist in the session workspace")
        out["path"] = str(path)
    else:
        plugin_id = _text(arguments, "plugin_id", 128).strip()
        page_id = _text(arguments, "page_id", 128).strip()
        if page_id and not plugin_id:
            raise ValueError("page_id requires plugin_id")
        if plugin_id:
            if not _PLUGIN_ID.fullmatch(plugin_id):
                raise ValueError("invalid plugin_id")
            pages = [row for row in _plugin_pages() if row.get("plugin_id") == plugin_id
                     and (not page_id or row.get("id") == page_id)]
            if not pages:
                raise ValueError("plugin page is unavailable; use kind=plugin without plugin_id to open the available plugin catalogue")
            out.update(plugin_id=plugin_id, page_id=pages[0]["id"])
    return out


def _notification_claim(manager, session_id, identity):
    """An exclusive durable receipt gives at-most-once native dispatch per call.

    A crash between claiming and the OS acknowledgement stays unknown; reopening
    history never resends an ambiguous notification.
    """
    directory = Path(manager._resolve_session_path(session_id)) / "presentations"
    directory.mkdir(exist_ok=True)  # Never recreate a deleted parent session.
    path = directory / ("notification-" + identity + ".json")
    try:
        with path.open("x", encoding="utf-8") as stream:
            json.dump({"status": "unknown"}, stream)
            stream.flush()
            os.fsync(stream.fileno())
        return path, None
    except FileExistsError:
        try:
            receipt = json.loads(path.read_text(encoding="utf-8"))
            status = receipt.get("status", "unknown") if isinstance(receipt, dict) else "unknown"
            if status not in ("requested", "unavailable", "failed", "unknown"):
                status = "unknown"
        except (ValueError, OSError):
            status = "unknown"
        return path, status


def _notification_receipt(path, status):
    with path.open("w", encoding="utf-8") as stream:
        json.dump({"status": status}, stream)
        stream.flush()
        os.fsync(stream.fileno())


async def _dispatch_notification(manager, context, presentation):
    path, previous = await run_fact_commit(_notification_claim, manager, context.session_id,
                                           presentation["presentation_id"], trace_state=context.state)
    if previous is not None:
        return previous
    from notification_providers import notification_provider_ids, notify_user
    if "desktop-notifications" not in notification_provider_ids():
        status = "unavailable"
    else:
        # System notification means the native desktop provider only. Other
        # registered channels must not receive a message as a side effect.
        failures = await notify_user(presentation["title"], presentation["text"], context.session_id,
                                     provider_ids=("desktop-notifications",))
        status = "failed" if failures else "requested"
    await run_fact_commit(_notification_receipt, path, status, trace_state=context.state)
    return status


async def invoke_show_user(context, arguments):
    import asyncio

    manager = context.service("session_manager")
    workspace = context.service("security_workspace")
    try:
        target = await asyncio.to_thread(prepare_presentation, dict(arguments), workspace=workspace)
        stop = context.services.get("run_interrupt_check")
        if stop and stop():
            return ToolOutcome.failed("interrupted", "Display request was interrupted")
        identity = (uuid.uuid5(uuid.NAMESPACE_URL, f"show_user:{context.session_id}:{context.run_id}:{context.tool_call_id}").hex
                    if context.tool_call_id else uuid.uuid4().hex)
        presentation = {**target, "presentation_id": identity, "session_id": context.session_id, "created_at": now_iso()}
        event = {"type": "show_user", "session_id": context.session_id, "run_id": context.run_id,
                 "tool_call_id": context.tool_call_id, "react_iter": int(context.state.get("_current_react_iter") or 0),
                 "presentation": presentation, "content": target["title"]}
        # Settle the durable display fact before publishing. Stream delivery
        # alone cannot promise a visible browser or a successfully loaded page.
        await run_fact_commit(partial(manager.append_ui_event, context.session_id, event, require_commit=True),
                              trace_state=context.state)
        if target["kind"] == "notification":
            status = await _dispatch_notification(manager, context, presentation)
            presentation["notification_status"] = status
            await run_fact_commit(partial(manager.append_ui_event, context.session_id, event, require_commit=True),
                                  trace_state=context.state)
        try:
            await context.publish({**event, "_runtime_v2_committed": True})
        except Exception:
            # The request is already saved. A disconnected browser must not
            # turn the completed fact into a failed/repeated tool invocation.
            logger.warning("show_user live delivery unavailable session=%s", context.session_id, exc_info=True)
        return ToolOutcome.completed(json.dumps({"status": "display_requested", "presentation_id": identity,
            "kind": target["kind"], "title": target["title"], "requires_answer": False,
            **({"notification_status": presentation["notification_status"]} if target["kind"] == "notification" else {})}, ensure_ascii=False))
    except (ValueError, TypeError) as exc:
        return ToolOutcome.failed("invalid_presentation", str(exc))
    except (OSError, RuntimeError) as exc:
        return ToolOutcome.failed("presentation_failed", str(exc))


def saved_presentation(manager, session_id, presentation_id):
    for event in reversed(manager.get_ui_events_for_display(session_id)):
        record = event.get("presentation") if event.get("type") == "show_user" else None
        if isinstance(record, dict) and record.get("presentation_id") == presentation_id:
            return copy.deepcopy(record)
    raise LookupError("presentation not found")
