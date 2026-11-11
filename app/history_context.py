"""Durable compressed-history archives and model-facing history retrieval.

The active model context is intentionally lossy.  This module keeps the exact
rows removed by local compaction in immutable per-session JSONL archives and
provides bounded search/read operations across those archives and Runtime V2
``events.jsonl`` files.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
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
    r"(?:event:(?P<seq>\d+)(?::ui:(?P<ui>\d+))?))$"
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


def _clean_json(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)
    except (TypeError, ValueError):
        return str(value or "")


def _clean_message_text(row: Mapping[str, Any]) -> str:
    """Render only the model-useful meaning of one archived message."""
    role = str(row.get("role") or "other")
    content = _content_text(row.get("content")).strip()
    if role == "user":
        return f"用户：{content}" if content else "用户：（空）"
    if role == "assistant":
        lines = [f"助手：{content}" if content else "助手：（无正文）"]
        reasoning = _content_text(row.get("reasoning")).strip()
        if reasoning:
            lines.append(f"推理：{reasoning}")
        for call in row.get("tool_calls") or []:
            name, call_id = _assistant_call_label(call)
            suffix = f"，call_id={call_id}" if call_id else ""
            lines.append(f"工具调用：{name}{suffix}")
            args = call.get("args") if isinstance(call, Mapping) else getattr(call, "args", None)
            if args not in (None, "", {}, []):
                lines.append(f"参数：{_clean_json(args)}")
        return "\n".join(lines)
    if role == "tool":
        call_id = str(row.get("tool_call_id") or "").strip()
        suffix = f"，call_id={call_id}" if call_id else ""
        return f"工具结果{suffix}：{content}" if content else f"工具结果{suffix}：（空）"
    if role == "system":
        return f"系统：{content}" if content else "系统：（空）"
    return f"消息：{content}" if content else ""


def _clean_event_text(event: Mapping[str, Any]) -> str:
    """Project a Runtime V2 event to readable semantic text, not storage JSON."""
    event_type = str(event.get("type") or "").strip()
    payload = event.get("payload")
    if not isinstance(payload, Mapping):
        return ""

    messages = payload.get("messages")
    if isinstance(messages, list):
        rendered = []
        for message in messages:
            if isinstance(message, Mapping):
                rendered_text = _clean_message_text(message)
                if rendered_text:
                    rendered.append(rendered_text)
        if rendered:
            return "\n\n".join(rendered)

    role_by_type = {
        "message_user": "用户",
        "user_turn_committed": "用户",
        "model_user": "用户",
        "assistant_final_committed": "助手",
        "message_assistant_final": "助手",
        "model_assistant": "助手",
        "model_system": "系统",
        "model_tool": "工具结果",
        "context_summary_committed": "上下文摘要",
        "context_summary_finished": "上下文摘要",
        "run_failed": "运行错误",
        "tool_failed": "工具错误",
        "tool_finished": "工具结果",
    }
    label = role_by_type.get(event_type, "记录")
    value: Any = None
    for key in (
        "content",
        "ui_content",
        "summary",
        "result",
        "output",
        "error",
        "message",
        "reason",
        "prompt",
        "query",
    ):
        candidate = payload.get(key)
        if candidate not in (None, "", {}, []):
            value = candidate
            break
    tool_name = str(payload.get("tool") or payload.get("name") or "").strip()
    call_id = str(payload.get("tool_call_id") or payload.get("call_id") or "").strip()
    if value is None and not tool_name:
        return ""
    details = []
    if tool_name:
        details.append(f"工具={tool_name}")
    if call_id:
        details.append(f"call_id={call_id}")
    suffix = f"（{'，'.join(details)}）" if details else ""
    text = _clean_json(value).strip() if value is not None else ""
    return f"{label}{suffix}：{text}" if text else f"{label}{suffix}"


def _ui_text(value: Any) -> str:
    """Extract display text; rules live in the shared corpus module."""
    from session_corpus import text_of

    return text_of(value)


def _ui_row_text(row: Mapping[str, Any]) -> str:
    """Render one retained UI row; identical rules in both search corpora."""
    from session_corpus import ui_row_text

    return ui_row_text(row, labelled=True)


def _snapshot_ui_rows(event: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Return retained UI rows of a compacted session snapshot."""
    if str(event.get("type") or "") != "runtime_snapshot_compacted":
        return []
    payload = event.get("payload")
    if not isinstance(payload, Mapping):
        return []
    rows = payload.get("ui_events")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, Mapping)]


def active_excerpt(archive: Mapping[str, Any], *, max_chars: int = 8_000) -> str:
    """Render a chronological excerpt with durable refs for omitted fields."""
    entries: list[dict[str, Any]] = []
    rows = list(archive.get("rows") or [])
    for row in rows:
        role = str(row.get("role") or "other")
        ref = str(row.get("ref") or "")
        content = _content_text(row.get("content"))
        if role == "user":
            label = "插件上下文" if (row.get("metadata") or {}).get("plugin_context") else "用户"
            entries.append({"text": f"{label}: {content}", "verbatim": True, "ref": ref, "chars": len(content), "label": label + "正文"})
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
        # Sessions live one level below the root. A scandir walk plus the
        # cached stat avoids the per-file resolve()/stat() cost of rglob,
        # which dominated global queries on large libraries.
        with os.scandir(root) as entries:
            for entry in entries:
                if not entry.is_dir():
                    continue
                sid = entry.name
                try:
                    session_manager._normalize_session_id(sid)
                    event_path = Path(entry.path) / "events.jsonl"
                    if not event_path.is_file():
                        continue
                    stamp = int(event_path.stat().st_mtime_ns)
                except (AttributeError, OSError, ValueError):
                    continue
                found.append((sid, Path(entry.path), stamp))
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


_SCAN_CHUNK = 4 * 1024 * 1024


def _file_may_contain(path: Path, terms: list[str]) -> bool:
    """Reject a whole file without a per-line Python loop.

    Only presence matters here: a term missing from the entire file cannot
    match any line.  Chunk overlap keeps terms that straddle a boundary.
    """
    lowered = [term.lower().encode("ascii") for term in terms if term.isascii()]
    literal = [term.encode("utf-8") for term in terms
               if not term.isascii() and term == term.casefold()]
    if any(not term.isascii() and term != term.casefold() for term in terms):
        return True  # Needs decoded casefolding; the line scan decides.
    pending = set(range(len(lowered))) | set(range(len(lowered), len(lowered) + len(literal)))
    lowered_index = {index: term for index, term in enumerate(lowered)}
    literal_index = {len(lowered) + index: term for index, term in enumerate(literal)}
    overlap = max([len(term) for term in lowered + literal] or [1]) - 1
    tail = b""
    try:
        with path.open("rb") as handle:
            while pending:
                chunk = handle.read(_SCAN_CHUNK)
                if not chunk:
                    return False
                window = tail + chunk
                haystack = window.lower() if lowered_index else b""
                for index in list(pending):
                    if index in lowered_index:
                        found = lowered_index[index] in haystack
                    else:
                        found = literal_index[index] in window
                    if found:
                        pending.discard(index)
                tail = window[-overlap:] if overlap > 0 else b""
    except OSError:
        return True
    return True


def _matching_events(path: Path, terms: list[str]) -> Iterable[tuple[int, Optional[int], str]]:
    """Scan raw events, expanding compacted snapshots into their retained rows.

    A ``runtime_snapshot_compacted`` payload holds the only copy of a compacted
    session's dialogue, so a raw-line filter alone hides every message in it.
    """
    # Prefilter on bytes before decoding: casefold() blocks on the GIL for the
    # whole line, while bytes.lower() stays in C and skips most lines outright.
    lowered_terms = [term.lower().encode("ascii") for term in terms if term.isascii()]
    literal_terms = [term.encode("utf-8") for term in terms if not term.isascii() and term == term.casefold()]
    folded_terms = [term for term in terms if not term.isascii() and term != term.casefold()]
    try:
        if path.stat().st_size > _SCAN_CHUNK and not _file_may_contain(path, terms):
            return
    except OSError:
        return
    try:
        with path.open("rb") as handle:
            for raw in handle:
                lowered = raw.lower() if lowered_terms else b""
                if not all(term in lowered for term in lowered_terms):
                    continue
                if not all(term in raw for term in literal_terms):
                    continue
                line = raw.decode("utf-8", errors="replace")
                if folded_terms and not all(term in line.casefold() for term in folded_terms):
                    continue
                try:
                    event = json.loads(line)
                except (TypeError, ValueError):
                    continue
                if not isinstance(event, dict):
                    continue
                seq = int(event.get("seq") or 0)
                rows = _snapshot_ui_rows(event)
                if rows:
                    for index, row in enumerate(rows):
                        text = _ui_row_text(row)
                        if text and all(term in text.casefold() for term in terms):
                            yield seq, index, text
                    continue
                text = _clean_event_text(event)
                if text and all(term in text.casefold() for term in terms):
                    yield seq, None, text
    except OSError:
        return


def _render_event_row(event: Mapping[str, Any]) -> tuple[str, str]:
    return str(int(event.get("seq") or 0)), _clean_event_text(event)


_MAINTENANCE_LOCK = threading.Lock()
_maintenance_done = False


def _maintenance_once(root: Path) -> None:
    """Remove the retired per-file caches, once per process."""
    global _maintenance_done
    with _MAINTENANCE_LOCK:
        if _maintenance_done:
            return
        _maintenance_done = True
    # Targeted patterns only: a recursive rglob over the subagent tree costs
    # seconds on a large library, and these are the only places caches lived.
    for pattern in (
        "*/.history-search/*.sqlite3*",
        "*/history_context_archives/.history-search/*.sqlite3*",
        "*/subagents/*/.history-search/*.sqlite3*",
        "*/subagents/*/history_context_archives/.history-search/*.sqlite3*",
    ):
        for db in Path(root).glob(pattern):
            try:
                db.unlink()
            except OSError:
                pass


def _archive_renderer(path: Path):
    archive_id = path.stem

    def render(row):
        if str(row.get("kind") or "") != "message":
            return "", ""
        return f"archive:{archive_id}:item:{row.get('item_id') or ''}", _clean_message_text(row)

    return render


def _indexed_file(
    session_dir: Path,
    path: Path,
    terms: list[str],
    limit: int,
    *,
    kind: str = "events",
) -> Optional[list[tuple[str, str]]]:
    """Per-file hits from the single global index, or None when unavailable."""
    from history_global_index import path_is_indexed, search as index_search, warm

    root = session_dir.parent
    render = _archive_renderer(path) if kind == "archive" else _render_event_row
    if not path_is_indexed(root, path):
        try:
            warm(
                root,
                [(path, render, _ui_row_text if kind == "events" else None)],
                budget_bytes=16 * 1024 * 1024,
            )
        except Exception:
            pass
        return None
    rows = index_search(root, terms, limit=max(1, limit), path=str(path))
    if rows is None:
        return None
    return _verify_spans(
        str(path),
        [(start, end, ref, stored) for _path, start, end, ref, _folded, stored in rows],
        terms,
        kind=kind,
    )


def _search_session(
    session_id: str,
    session_dir: Path,
    terms: list[str],
    remaining: int,
    *,
    global_scope: bool,
    include_source: bool,
    prefetched: Optional[list[tuple[str, str]]] = None,
    skip_events: bool = False,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    seen_content: set[str] = set()

    def add_hit(ref: str, clean_text: str, source_path: Path) -> bool:
        if not clean_text or not all(term in clean_text.casefold() for term in terms):
            return False
        content_key = " ".join(clean_text.split()).casefold()
        if content_key in seen_content:
            return False
        seen_content.add(content_key)
        result: dict[str, Any] = {
            "ref": ref,
            "content": _search_snippet(clean_text, terms),
        }
        if global_scope:
            result["session_id"] = session_id
        if include_source:
            result["source_file"] = str(source_path)
        results.append(result)
        return len(results) >= remaining

    for path in _iter_archive_paths(session_dir):
        archive_id = path.stem

        def render_archive(row):
            text = _clean_message_text(row) if row.get("kind") == "message" else ""
            return str(row.get("item_id") or ""), text

        indexed = _indexed_file(session_dir, path, terms, remaining - len(results), kind="archive")
        if indexed is not None:
            for ref, clean_text in indexed:
                if add_hit(ref, clean_text, path):
                    return results
            continue
        for row, _raw in _matching_jsonl(path, terms):
            item_id, clean_text = render_archive(row)
            if add_hit(archive_item_ref(session_id, archive_id, item_id), clean_text, path):
                return results
    event_path = session_dir / "events.jsonl"

    def add_event(ref: str, clean_text: str) -> bool:
        return add_hit(ref, clean_text, event_path)

    if prefetched is not None:
        for ref, clean_text in prefetched:
            if add_event(ref, clean_text):
                return results
        return results
    if skip_events:
        return results

    candidates: Optional[Iterable] = None
    if remaining - len(results) > 0:
        # One index answers both scopes; the raw scan remains the authority
        # whenever a file is not covered yet.
        indexed = _indexed_file(session_dir, event_path, terms, remaining - len(results))
        if indexed is not None:
            for ref, text in indexed:
                if add_event(ref, text):
                    return results
            return results
        candidates = _matching_events(event_path, terms)
    for seq, ui_index, clean_text in candidates or ():
        ref = event_ref(session_id, int(seq))
        if ui_index is not None:
            ref = f"{ref}:ui:{int(ui_index)}"
        if add_event(ref, clean_text):
            return results
    return results


def _read_ref(
    session_manager: Any,
    current_session_id: str,
    scope: str,
    ref: str,
    offset: int,
    max_chars: int,
    *,
    include_source: bool,
) -> dict[str, Any]:
    match = _REF_RE.match(str(ref or "").strip())
    if not match:
        raise ValueError("invalid history_context ref")
    session_id = str(match.group("session") or "")
    if scope != "global" and session_id != current_session_id:
        raise ValueError("current scope cannot read another session")
    session_dir = Path(session_manager._resolve_session_path(session_id)).resolve()
    rendered = ""
    source_file = ""
    if match.group("seq") is not None:
        wanted = int(match.group("seq"))
        path = session_dir / "events.jsonl"
        source_file = str(path)
        value = None
        try:
            from runtime_v2 import SessionEventLog

            log = SessionEventLog(session_dir.parent, path_resolver=lambda _sid: session_dir)
            events = log.read_by_seqs(session_id, [wanted])
            if events:
                value = events[0].to_dict()
        except Exception:
            # Legacy/non-runtime rows remain readable through the original path.
            pass
        if value is None:
            value = next((row for row in _read_jsonl(path) if int(row.get("seq") or 0) == wanted), None)
        if value is not None:
            if match.group("ui") is not None:
                index = int(match.group("ui"))
                payload = value.get("payload")
                rows = payload.get("ui_events") if isinstance(payload, Mapping) else None
                row = rows[index] if isinstance(rows, list) and 0 <= index < len(rows) else None
                if isinstance(row, Mapping):
                    rendered = _ui_row_text(row)
            if not rendered:
                rendered = _clean_event_text(value)
    else:
        archive_id = str(match.group("archive") or "")
        item_id = str(match.group("item") or "")
        path = _archive_path(session_manager, session_id, archive_id)
        source_file = str(path)
        if item_id:
            value = next((row for row in _read_jsonl(path) if str(row.get("item_id") or "") == item_id), None)
            if value is not None:
                rendered = _clean_message_text(value)
        else:
            rendered_rows = [
                text
                for row in _read_jsonl(path)
                if row.get("kind") == "message"
                for text in [_clean_message_text(row)]
                if text
            ]
            rendered = "\n\n".join(rendered_rows)
    if not rendered:
        raise ValueError("history_context ref not found")
    start = max(0, int(offset or 0))
    limit = min(50_000, max(200, int(max_chars or 8_000)))
    chunk = rendered[start : start + limit]
    result: dict[str, Any] = {"content": chunk}
    next_offset = start + len(chunk) if start + len(chunk) < len(rendered) else None
    if next_offset is not None:
        result["next_offset"] = next_offset
    if include_source:
        result["source_file"] = source_file
    return result


def _verify_spans(
    path: str, items, terms: list[str], *, kind: str = "events"
) -> list[tuple[str, str]]:
    """Re-read each candidate line and re-render it before trusting a hit."""
    found: list[tuple[str, str]] = []
    parent = Path(path).parent
    session_id = parent.parent.name if kind == "archive" else parent.name
    cache: dict[tuple[int, int], Any] = {}
    try:
        with open(path, "rb") as handle:
            for start, end, ref, stored in items:
                key = (start, end)
                if stored is not None:
                    # Snapshot rows keep their rendered text: re-deriving it
                    # would mean re-parsing a line that can be hundreds of MB.
                    if all(term in stored.casefold() for term in terms):
                        if ":" in ref:
                            seq_text, ui_text = ref.split(":", 1)
                            full_ref = f"{event_ref(session_id, int(seq_text))}:ui:{int(ui_text)}"
                        else:
                            full_ref = event_ref(session_id, int(ref))
                        found.append((full_ref, stored))
                    continue
                if key not in cache:
                    handle.seek(start)
                    raw = handle.read(end - start)
                    try:
                        cache[key] = json.loads(raw.decode("utf-8", errors="replace"))
                    except (TypeError, ValueError):
                        cache[key] = None
                    if len(cache) > 2:
                        cache.pop(next(iter(cache)))
                event = cache[key]
                if not isinstance(event, dict):
                    continue
                if kind == "archive":
                    text = _clean_message_text(event) if event.get("kind") == "message" else ""
                    if text and all(term in text.casefold() for term in terms):
                        found.append((f"history:{session_id}:{ref}", text))
                    continue
                if ":" in ref:
                    seq_text, ui_text = ref.split(":", 1)
                    index = int(ui_text)
                    payload = event.get("payload")
                    rows = payload.get("ui_events") if isinstance(payload, Mapping) else None
                    row = rows[index] if isinstance(rows, list) and 0 <= index < len(rows) else None
                    text = _ui_row_text(row) if isinstance(row, Mapping) else ""
                    full_ref = f"{event_ref(session_id, int(seq_text))}:ui:{index}"
                else:
                    text = _clean_event_text(event)
                    full_ref = event_ref(session_id, int(ref))
                if text and all(term in text.casefold() for term in terms):
                    found.append((full_ref, text))
    except OSError:
        return []
    return found


def _global_prefetch(
    root: Path,
    session_dirs: list[tuple[str, Path]],
    terms: list[str],
    limit: int,
) -> tuple[Optional[dict[str, list[tuple[str, str]]]], set[str]]:
    """Index-backed candidates per source file, plus files fully covered by it."""
    from history_global_index import indexed_paths, search as index_search

    try:
        rows = index_search(root, terms, limit=limit)
    except Exception:
        return None, set()
    if rows is None:
        return None, set()
    indexed = indexed_paths(root)
    grouped: dict[str, list] = {}
    for path, start, end, ref, _folded, stored in rows:
        grouped.setdefault(path, []).append((start, end, ref, stored))
    hits: dict[str, list[tuple[str, str]]] = {}
    for path, items in grouped.items():
        if path not in indexed:
            continue  # Changed since projection; the scan owns it.
        verified = _verify_spans(path, items, terms)
        if verified:
            hits[path] = verified
    return hits, indexed


def _search_sessions_parallel(
    session_dirs: list[tuple[str, Path]],
    terms: list[str],
    result_limit: int,
    *,
    include_source: bool,
) -> list[dict[str, Any]]:
    """Global scan over independent files; ordered batches keep newest-first order."""
    from concurrent.futures import ThreadPoolExecutor

    results: list[dict[str, Any]] = []
    batch = 8
    with ThreadPoolExecutor(max_workers=batch, thread_name_prefix="history-search") as pool:
        for start in range(0, len(session_dirs), batch):
            chunk = session_dirs[start:start + batch]
            futures = [
                pool.submit(
                    _search_session,
                    session_id,
                    session_dir,
                    terms,
                    max(1, result_limit - len(results)),
                    global_scope=True,
                    include_source=include_source,
                )
                for session_id, session_dir in chunk
            ]
            for future in futures:
                results.extend(future.result())
                if len(results) >= result_limit:
                    return results[:result_limit]
    return results[:result_limit]


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
    include_source: bool = False,
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
            include_source=bool(include_source),
        )
    if action_name != "search":
        raise ValueError("action must be search or read")
    normalized_query = " ".join(str(query or "").split())
    if not normalized_query:
        raise ValueError("search requires a non-empty query")
    terms = [term.casefold() for term in normalized_query.split() if term]
    result_limit = min(50, max(1, int(limit or 10)))
    results: list[dict[str, Any]] = []
    session_dirs = _session_dirs(session_manager, current_session_id, scope_name)
    if scope_name == "global":
        root = Path(session_manager.sessions_dir)
        _maintenance_once(root)
    if scope_name == "global" and len(session_dirs) > 8:
        prefetched, indexed = _global_prefetch(root, session_dirs, terms, result_limit * 4)
        if prefetched is None:
            results = _search_sessions_parallel(
                session_dirs,
                terms,
                result_limit,
                include_source=bool(include_source),
            )
        else:
            for session_id, session_dir in session_dirs:
                path = str(session_dir / "events.jsonl")
                results.extend(
                    _search_session(
                        session_id,
                        session_dir,
                        terms,
                        result_limit - len(results),
                        global_scope=True,
                        include_source=bool(include_source),
                        prefetched=prefetched.get(path),
                        skip_events=path in indexed,
                    )
                )
                if len(results) >= result_limit:
                    break
    else:
        for session_id, session_dir in session_dirs:
            results.extend(
                _search_session(
                    session_id,
                    session_dir,
                    terms,
                    result_limit - len(results),
                    global_scope=scope_name == "global",
                    include_source=bool(include_source),
                )
            )
            if len(results) >= result_limit:
                break
    results = results[:result_limit]
    response: dict[str, Any] = {"results": results}
    if not results:
        response["message"] = "未找到匹配的会话内容"
    if include_source and not results:
        source_files: list[str] = []
        for _session_id, session_dir in session_dirs:
            event_path = session_dir / "events.jsonl"
            if event_path.is_file():
                source_files.append(str(event_path))
            source_files.extend(str(path) for path in _iter_archive_paths(session_dir))
            if len(source_files) >= 20:
                break
        response["source_files"] = source_files[:20]
    return response


__all__ = [
    "ARCHIVE_DIR_NAME",
    "active_excerpt",
    "archive_ref",
    "archive_item_ref",
    "archive_messages",
    "event_ref",
    "history_context",
]
