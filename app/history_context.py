"""Durable compressed-history archives and model-facing history retrieval.

The active model context is intentionally lossy.  This module keeps the exact
rows removed by local compaction in immutable per-session JSONL archives and
provides bounded search/read operations across those archives and Runtime V2
``events.jsonl`` files.
"""
from __future__ import annotations

import json
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

from agent_messages import AssistantMessage, SystemMessage, ToolMessage, UserMessage


ARCHIVE_DIR_NAME = "history_context_archives"
_ARCHIVE_LOCK = threading.RLock()
_REF_RE = re.compile(
    r"^history:(?P<session>[0-9a-fA-F-]{32,36}):"
    r"(?:(?:archive:(?P<archive>[A-Za-z0-9_.-]+)(?::item:(?P<item>[A-Za-z0-9_.-]+))?)|"
    r"(?:event:(?P<seq>\d+)))$"
)


def _content_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError):
        return str(value or "")


def _message_record(message: Any, index: int) -> dict[str, Any]:
    item_id = f"m{index + 1:06d}"
    if isinstance(message, UserMessage):
        role = "user"
    elif isinstance(message, AssistantMessage):
        role = "assistant"
    elif isinstance(message, ToolMessage):
        role = "tool"
    elif isinstance(message, SystemMessage):
        role = "system"
    else:
        role = "other"
    row: dict[str, Any] = {
        "kind": "message",
        "item_id": item_id,
        "index": int(index),
        "role": role,
        "content": getattr(message, "content", ""),
    }
    if isinstance(message, AssistantMessage):
        calls = list(getattr(message, "tool_calls", None) or [])
        if calls:
            row["tool_calls"] = calls
        additional = getattr(message, "additional_kwargs", None) or {}
        if isinstance(additional, Mapping):
            reasoning = (
                additional.get("reasoning_content")
                or additional.get("reasoning")
                or additional.get("reasoning_text")
            )
            if reasoning:
                row["reasoning"] = reasoning
    elif isinstance(message, ToolMessage):
        row["tool_call_id"] = str(getattr(message, "tool_call_id", "") or "")
    metadata = getattr(message, "metadata", None)
    if isinstance(metadata, Mapping) and metadata:
        row["metadata"] = dict(metadata)
    return row


def _archive_path(session_manager: Any, session_id: str, archive_id: str) -> Path:
    session_dir = Path(session_manager._resolve_session_path(session_id)).resolve()
    path = (session_dir / ARCHIVE_DIR_NAME / f"{archive_id}.jsonl").resolve()
    path.relative_to(session_dir)
    return path


def archive_messages(
    session_manager: Any,
    session_id: str,
    messages: Iterable[Any],
    *,
    reason: str,
) -> dict[str, Any]:
    """Write one immutable archive and return its id plus model-safe refs."""
    rows = [_message_record(message, index) for index, message in enumerate(messages)]
    if not rows:
        return {"archive_id": "", "message_count": 0, "rows": []}
    now = datetime.now(timezone.utc)
    archive_id = now.strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid.uuid4().hex[:8]
    path = _archive_path(session_manager, session_id, archive_id)
    meta = {
        "kind": "meta",
        "version": 1,
        "archive_id": archive_id,
        "session_id": str(session_id),
        "created_at": now.isoformat(),
        "reason": str(reason or "context_compaction"),
        "message_count": len(rows),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    payload = "\n".join(
        json.dumps(item, ensure_ascii=False, separators=(",", ":"), default=str)
        for item in [meta, *rows]
    ) + "\n"
    with _ARCHIVE_LOCK:
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(path)
    for row in rows:
        row["ref"] = archive_item_ref(session_id, archive_id, row["item_id"])
    return {
        "archive_id": archive_id,
        "ref": archive_ref(session_id, archive_id),
        "message_count": len(rows),
        "rows": rows,
        "path": str(path),
    }


def archive_item_ref(session_id: str, archive_id: str, item_id: str) -> str:
    return f"history:{session_id}:archive:{archive_id}:item:{item_id}"


def archive_ref(session_id: str, archive_id: str) -> str:
    return f"history:{session_id}:archive:{archive_id}"


def event_ref(session_id: str, seq: int) -> str:
    return f"history:{session_id}:event:{int(seq)}"


def _assistant_call_label(call: Any) -> tuple[str, str]:
    if isinstance(call, Mapping):
        return (
            str(call.get("name") or "unknown"),
            str(call.get("id") or call.get("tool_call_id") or ""),
        )
    return (
        str(getattr(call, "name", "") or "unknown"),
        str(getattr(call, "id", "") or getattr(call, "tool_call_id", "") or ""),
    )


def active_excerpt(archive: Mapping[str, Any], *, max_chars: int = 8_000) -> str:
    """Render a chronological excerpt with durable refs for omitted fields."""
    entries: list[dict[str, Any]] = []
    rows = list(archive.get("rows") or [])
    for row in rows:
        role = str(row.get("role") or "other")
        ref = str(row.get("ref") or "")
        content = _content_text(row.get("content"))
        if role == "user":
            entries.append({"text": f"用户: {content}", "verbatim": True, "ref": ref, "chars": len(content), "label": "用户正文"})
            continue
        if role == "assistant":
            if row.get("reasoning"):
                entries.append({"text": f"[推理已归档 ref={ref} field=reasoning]", "verbatim": False})
            entries.append({"text": f"助手: {content}", "verbatim": True, "ref": ref, "chars": len(content), "label": "助手正文"})
            for call in row.get("tool_calls") or []:
                name, call_id = _assistant_call_label(call)
                entries.append({
                    "text": f"[工具调用已归档 ref={ref} tool={name} call_id={call_id or '-'}]",
                    "verbatim": False,
                })
            continue
        if role == "tool":
            entries.append({
                "text": (
                    f"[工具结果已归档 ref={ref} call_id={row.get('tool_call_id') or '-'} "
                    f"chars={len(content)}]"
                ),
                "verbatim": False,
            })
            continue
        entries.append({"text": f"[{role} 消息已归档 ref={ref} chars={len(content)}]", "verbatim": False})

    def render() -> str:
        return "\n".join(str(entry.get("text") or "") for entry in entries).strip()

    limit = max(400, int(max_chars or 8_000))
    text = render()
    if len(text) <= limit:
        return text
    # Preserve the maximum number of complete user/assistant entries.  When
    # their text alone cannot fit, archive the largest bodies first instead of
    # cutting a message in half and producing misleading fragments.
    candidates = sorted(
        (entry for entry in entries if entry.get("verbatim")),
        key=lambda entry: int(entry.get("chars") or 0),
        reverse=True,
    )
    for entry in candidates:
        entry["text"] = (
            f"[{entry.get('label') or '正文'}过长，已归档 ref={entry.get('ref') or '-'} "
            f"chars={entry.get('chars') or 0}]"
        )
        entry["verbatim"] = False
        text = render()
        if len(text) <= limit:
            return text
    return text[:limit].rstrip()


def _iter_archive_paths(session_dir: Path) -> Iterable[Path]:
    archive_dir = session_dir / ARCHIVE_DIR_NAME
    if not archive_dir.is_dir():
        return ()
    try:
        return tuple(sorted(archive_dir.glob("*.jsonl"), key=lambda p: p.name, reverse=True))
    except OSError:
        return ()


def _session_dirs(session_manager: Any, current_session_id: str, scope: str) -> list[tuple[str, Path]]:
    if scope == "current":
        return [(current_session_id, Path(session_manager._resolve_session_path(current_session_id)).resolve())]
    root = Path(session_manager.sessions_dir).resolve()
    found: list[tuple[str, Path, int]] = []
    try:
        candidates = root.rglob("events.jsonl")
        for event_path in candidates:
            session_dir = event_path.parent.resolve()
            sid = session_dir.name
            try:
                session_manager._normalize_session_id(sid)
                session_dir.relative_to(root)
                stamp = int(event_path.stat().st_mtime_ns)
            except (AttributeError, OSError, ValueError):
                continue
            found.append((sid, session_dir, stamp))
    except OSError:
        pass
    if not any(sid == current_session_id for sid, _path, _stamp in found):
        try:
            current_dir = Path(session_manager._resolve_session_path(current_session_id)).resolve()
            found.append((current_session_id, current_dir, 0))
        except (OSError, ValueError):
            pass
    found.sort(key=lambda item: item[2], reverse=True)
    return [(sid, path) for sid, path, _stamp in found]


def _search_snippet(text: str, terms: list[str], max_chars: int = 700) -> str:
    folded = text.casefold()
    positions = [folded.find(term) for term in terms if folded.find(term) >= 0]
    center = min(positions) if positions else 0
    half = max_chars // 2
    start = max(0, center - half)
    end = min(len(text), start + max_chars)
    snippet = text[start:end]
    if start:
        snippet = "…" + snippet
    if end < len(text):
        snippet += "…"
    return snippet


def _read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                try:
                    row = json.loads(line)
                except (TypeError, ValueError):
                    continue
                if isinstance(row, dict):
                    yield row
    except OSError:
        return


def _matching_jsonl(path: Path, terms: list[str]) -> Iterable[tuple[dict[str, Any], str]]:
    """Filter raw JSONL before decoding; global history search stays bounded by I/O."""
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                folded = line.casefold()
                if not all(term in folded for term in terms):
                    continue
                try:
                    row = json.loads(line)
                except (TypeError, ValueError):
                    continue
                if isinstance(row, dict):
                    yield row, line.rstrip("\r\n")
    except OSError:
        return


def _search_session(session_id: str, session_dir: Path, terms: list[str], remaining: int) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for path in _iter_archive_paths(session_dir):
        archive_id = path.stem
        for row, searchable in _matching_jsonl(path, terms):
            if row.get("kind") != "message":
                continue
            results.append({
                "ref": archive_item_ref(session_id, archive_id, str(row.get("item_id") or "")),
                "session_id": session_id,
                "source": "compressed_archive",
                "role": row.get("role"),
                "snippet": _search_snippet(searchable, terms),
                "source_file": str(path),
            })
            if len(results) >= remaining:
                return results
    event_path = session_dir / "events.jsonl"
    for event, searchable in _matching_jsonl(event_path, terms):
        seq = int(event.get("seq") or 0)
        results.append({
            "ref": event_ref(session_id, seq),
            "session_id": session_id,
            "source": "events",
            "event_type": event.get("type"),
            "timestamp": event.get("timestamp"),
            "snippet": _search_snippet(searchable, terms),
            "source_file": str(event_path),
        })
        if len(results) >= remaining:
            return results
    return results


def _read_ref(session_manager: Any, current_session_id: str, scope: str, ref: str, offset: int, max_chars: int) -> dict[str, Any]:
    match = _REF_RE.match(str(ref or "").strip())
    if not match:
        raise ValueError("invalid history_context ref")
    session_id = str(match.group("session") or "")
    if scope != "global" and session_id != current_session_id:
        raise ValueError("current scope cannot read another session")
    session_dir = Path(session_manager._resolve_session_path(session_id)).resolve()
    value: Optional[dict[str, Any]] = None
    source_file = ""
    if match.group("seq") is not None:
        wanted = int(match.group("seq"))
        path = session_dir / "events.jsonl"
        source_file = str(path)
        value = next((row for row in _read_jsonl(path) if int(row.get("seq") or 0) == wanted), None)
    else:
        archive_id = str(match.group("archive") or "")
        item_id = str(match.group("item") or "")
        path = _archive_path(session_manager, session_id, archive_id)
        source_file = str(path)
        if item_id:
            value = next((row for row in _read_jsonl(path) if str(row.get("item_id") or "") == item_id), None)
        else:
            archive_rows = list(_read_jsonl(path))
            value = {"archive_id": archive_id, "records": archive_rows} if archive_rows else None
    if value is None:
        raise ValueError("history_context ref not found")
    rendered = json.dumps(value, ensure_ascii=False, indent=2, default=str)
    start = max(0, int(offset or 0))
    limit = min(50_000, max(200, int(max_chars or 8_000)))
    chunk = rendered[start : start + limit]
    return {
        "ref": ref,
        "session_id": session_id,
        "content": chunk,
        "offset": start,
        "next_offset": start + len(chunk) if start + len(chunk) < len(rendered) else None,
        "total_chars": len(rendered),
        "source_file": source_file,
    }


def history_context(
    session_manager: Any,
    current_session_id: str,
    *,
    action: str = "search",
    scope: str = "current",
    query: str = "",
    ref: str = "",
    limit: int = 10,
    offset: int = 0,
    max_chars: int = 8_000,
) -> dict[str, Any]:
    action_name = str(action or "search").strip().lower()
    scope_name = str(scope or "current").strip().lower()
    if scope_name not in {"current", "global"}:
        raise ValueError("scope must be current or global")
    if action_name == "read":
        return _read_ref(
            session_manager,
            current_session_id,
            scope_name,
            ref,
            offset,
            max_chars,
        )
    if action_name != "search":
        raise ValueError("action must be search or read")
    normalized_query = " ".join(str(query or "").split())
    if not normalized_query:
        raise ValueError("search requires a non-empty query")
    terms = [term.casefold() for term in normalized_query.split() if term]
    result_limit = min(50, max(1, int(limit or 10)))
    results: list[dict[str, Any]] = []
    scanned_sessions = 0
    for session_id, session_dir in _session_dirs(session_manager, current_session_id, scope_name):
        scanned_sessions += 1
        results.extend(
            _search_session(
                session_id,
                session_dir,
                terms,
                result_limit - len(results),
            )
        )
        if len(results) >= result_limit:
            break
    return {
        "action": "search",
        "scope": scope_name,
        "query": normalized_query,
        "results": results,
        "result_count": len(results),
        "scanned_sessions": scanned_sessions,
    }


__all__ = [
    "ARCHIVE_DIR_NAME",
    "active_excerpt",
    "archive_ref",
    "archive_item_ref",
    "archive_messages",
    "event_ref",
    "history_context",
]
