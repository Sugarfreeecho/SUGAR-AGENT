"""Create immutable, content-addressed copies of local images used in chat Markdown."""

from __future__ import annotations

import hashlib
import os
import re
import uuid
from pathlib import Path
from urllib.parse import unquote, urlsplit


IMAGE_SUFFIXES = frozenset({
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg",
    ".ico", ".tif", ".tiff", ".avif", ".jfif",
})

_FENCE_RE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})")
_TITLE_RE = re.compile(
    r"\s+(?:\"(?:\\.|[^\"])*\"|'(?:\\.|[^'])*'|\((?:\\.|[^)])*\))\s*$"
)


def _unescape_markdown_destination(value: str) -> str:
    return re.sub(r"\\([\\`*{}\[\]()#+\-.!_> ])", r"\1", value)


def _local_image_path(destination: str, work_dir: Path) -> Path | None:
    raw = _unescape_markdown_destination(unquote(str(destination or "").strip()))
    if not raw or raw.startswith("#"):
        return None
    if raw.lower().startswith("file://"):
        parts = urlsplit(raw)
        if parts.netloc and parts.netloc.lower() != "localhost":
            raw = f"//{parts.netloc}{parts.path}"
        else:
            raw = parts.path
        raw = unquote(raw)
        if os.name == "nt" and re.match(r"^/[A-Za-z]:/", raw):
            raw = raw[1:]
    elif re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", raw) and not re.match(r"^[A-Za-z]:[\\/]", raw):
        return None

    is_windows_absolute = bool(re.match(r"^[A-Za-z]:[\\/]", raw) or raw.startswith("\\\\"))
    candidate = Path(raw).expanduser()
    if not (candidate.is_absolute() or is_windows_absolute):
        candidate = work_dir / raw.lstrip("/\\")
    try:
        candidate = Path(os.path.abspath(str(candidate))).resolve()
    except (OSError, RuntimeError, ValueError):
        return None
    if candidate.suffix.lower() not in IMAGE_SUFFIXES or not candidate.is_file():
        return None
    return candidate


def _snapshot_image(source: Path, work_dir: Path) -> str:
    target_dir = work_dir / ".sugaragent" / "history-media"
    target_dir.mkdir(parents=True, exist_ok=True)
    temporary = target_dir / f".{uuid.uuid4().hex}.tmp"
    digest = hashlib.sha256()
    try:
        with source.open("rb") as reader, temporary.open("xb") as writer:
            while True:
                chunk = reader.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
                writer.write(chunk)
            writer.flush()
            os.fsync(writer.fileno())
        target = target_dir / f"{digest.hexdigest()}{source.suffix.lower()}"
        if target.exists():
            temporary.unlink()
        else:
            os.replace(temporary, target)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
    return target.relative_to(work_dir).as_posix()


def _destination_span(body: str) -> tuple[int, int, str] | None:
    start = len(body) - len(body.lstrip())
    if start >= len(body):
        return None
    if body[start] == "<":
        end = body.find(">", start + 1)
        return (start, end + 1, body[start + 1:end]) if end >= 0 else None
    if body[start] in {'"', "'"}:
        quote = body[start]
        index = start + 1
        while index < len(body):
            if body[index] == quote and body[index - 1] != "\\":
                return start, index + 1, body[start + 1:index]
            index += 1
        return None
    end = len(body.rstrip())
    title = _TITLE_RE.search(body[start:end])
    if title:
        end = start + title.start()
    destination = body[start:end].rstrip()
    return (start, start + len(destination), destination) if destination else None


def _closing_paren(line: str, start: int) -> int:
    depth = 1
    quote = ""
    angle = False
    index = start
    while index < len(line):
        char = line[index]
        if char == "\\":
            index += 2
            continue
        if angle:
            angle = char != ">"
        elif quote:
            if char == quote:
                quote = ""
        elif char == "<":
            angle = True
        elif char in {'"', "'"}:
            quote = char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return -1


def _rewrite_line(line: str, work_dir: Path) -> str:
    output: list[str] = []
    cursor = 0
    index = 0
    while index < len(line):
        if line[index] == "`":
            run = len(line[index:]) - len(line[index:].lstrip("`"))
            marker = "`" * run
            closing = line.find(marker, index + run)
            index = len(line) if closing < 0 else closing + run
            continue
        if not line.startswith("![", index) or (index > 0 and line[index - 1] == "\\"):
            index += 1
            continue
        alt_end = index + 2
        while alt_end < len(line):
            if line[alt_end] == "\\":
                alt_end += 2
                continue
            if line[alt_end] == "]":
                break
            alt_end += 1
        open_paren = alt_end + 1
        while open_paren < len(line) and line[open_paren].isspace() and line[open_paren] not in "\r\n":
            open_paren += 1
        if alt_end >= len(line) or open_paren >= len(line) or line[open_paren] != "(":
            index += 2
            continue
        close_paren = _closing_paren(line, open_paren + 1)
        if close_paren < 0:
            index += 2
            continue
        body = line[open_paren + 1:close_paren]
        span = _destination_span(body)
        replacement = None
        if span:
            source = _local_image_path(span[2], work_dir)
            if source is not None:
                try:
                    replacement = _snapshot_image(source, work_dir)
                except OSError:
                    replacement = None
        if replacement:
            body = body[:span[0]] + f"<{replacement}>" + body[span[1]:]
            output.append(line[cursor:open_paren + 1])
            output.append(body)
            output.append(")")
            cursor = close_paren + 1
        index = close_paren + 1
    if not output:
        return line
    output.append(line[cursor:])
    return "".join(output)


def snapshot_workspace_images(content: str, work_dir: os.PathLike[str] | str) -> str:
    """Copy local Markdown images once and rewrite their UI-facing destinations."""
    text = str(content or "")
    root = Path(work_dir).resolve()
    lines = text.splitlines(keepends=True)
    fenced = False
    fence_char = ""
    rewritten: list[str] = []
    for line in lines:
        fence = _FENCE_RE.match(line)
        if fence:
            marker = fence.group(1)
            if not fenced:
                fenced = True
                fence_char = marker[0]
            elif marker[0] == fence_char:
                fenced = False
                fence_char = ""
            rewritten.append(line)
        elif fenced:
            rewritten.append(line)
        else:
            rewritten.append(_rewrite_line(line, root))
    return "".join(rewritten)
