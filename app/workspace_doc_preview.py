"""Read-only previews for office documents in the details column.

The details column already renders text, images and media itself; the document
page used to hand every other file to the system app. This module turns the
common office containers (Word / PowerPoint / Excel) and delimited text
(CSV / TSV) into plain HTML fragments so the column can show them inline, and
keeps PDF with the browser's own viewer.

Everything here is read-only. OOXML containers are parsed with the standard
library (``zipfile`` + a defused XML parser) and workbooks with ``openpyxl``;
no dependency is required beyond what the desktop build already ships. The
generated markup only contains escaped text and our own elements — document
XML is never forwarded to the browser, and embedded images are served one part
at a time through :func:`read_preview_media` instead of being inlined.

Known simplifications (surfaced in the UI as "simplified preview"):

* Word: styles are flattened to headings/paragraphs/lists, images stay inline,
  headers/footers and text boxes are omitted.
* PowerPoint: placeholders inherit geometry and type defaults from the layout
  and master, but master decorations, animations and transitions are omitted;
  charts and SmartArt become placeholder boxes.
* Excel: the visible window is capped (rows/columns/sheets) and only cached
  formula results are shown.
"""

from __future__ import annotations

import html
import csv
import io
import mimetypes
import posixpath
import re
import threading
import zipfile
from collections import OrderedDict
from datetime import date, datetime, time as clock_time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from xml.etree.ElementTree import Element

from defusedxml.ElementTree import fromstring as _safe_xml_fromstring

__all__ = [
    "PREVIEW_SUFFIXES",
    "PreviewError",
    "build_preview",
    "preview_kind",
    "read_preview_media",
    "clear_preview_cache",
]

# Suffixes handled inline. PDF is intentionally absent: the browser's own
# viewer renders it far better than anything we could rasterise without
# shipping a PDF engine to the desktop build.
PREVIEW_SUFFIXES = {
    ".docx": "docx",
    ".pptx": "pptx",
    ".xlsx": "xlsx",
    ".xlsm": "xlsx",
    ".csv": "csv",
    ".tsv": "csv",
}

# Package folders whose media parts may be served to the browser.
PREVIEW_MEDIA_PREFIXES = ("word/media/", "ppt/media/", "xl/media/")
PREVIEW_MEDIA_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tif", ".tiff"}

MAX_DOCUMENT_BYTES = 60 * 1024 * 1024
MAX_ARCHIVE_ENTRIES = 5000
MAX_ARCHIVE_UNCOMPRESSED = 240 * 1024 * 1024
MAX_XML_PART_BYTES = 24 * 1024 * 1024
MAX_MEDIA_PART_BYTES = 12 * 1024 * 1024
MAX_DOCX_BLOCKS = 6000
MAX_DECK_SLIDES = 60
MAX_DECK_SHAPES = 400
MAX_SHEET_ROWS = 400
MAX_SHEET_COLUMNS = 64
MAX_SHEETS = 24
MAX_SHEET_CELLS = 30000
MAX_CSV_BYTES = 20 * 1024 * 1024
MAX_CSV_ROWS = 500
MAX_CSV_COLUMNS = 60
MAX_CSV_CELL_CHARS = 2000
MAX_TEXT_CHARS = 40000

NS_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
NS_P = "http://schemas.openxmlformats.org/presentationml/2006/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
NS_V = "urn:schemas-microsoft-com:vml"

_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_REL_NS_STRICT = "http://purl.oclc.org/ooxml/package/relationships"

_HIGHLIGHT_COLORS = {
    "yellow": "#fff3a3",
    "green": "#c6efce",
    "cyan": "#c9f7f7",
    "magenta": "#ffc7ff",
    "blue": "#cfe2ff",
    "red": "#ffc7ce",
    "darkBlue": "#9db9e8",
    "darkCyan": "#9ee0e0",
    "darkGreen": "#a9d08e",
    "darkMagenta": "#d9a3d9",
    "darkRed": "#e6a0a0",
    "darkYellow": "#d9c46a",
    "gray25": "#e6e6e6",
    "gray50": "#bfbfbf",
}


class PreviewError(Exception):
    """A preview cannot be produced; ``status_code`` is the HTTP status to use."""

    def __init__(self, message: str, status_code: int = 422):
        super().__init__(message)
        self.message = message
        self.status_code = int(status_code)


def preview_kind(path: Path | str) -> str:
    """Return ``docx``/``pptx``/``xlsx`` for a supported path, else ``""``."""
    suffix = Path(str(path)).suffix.lower()
    return PREVIEW_SUFFIXES.get(suffix, "")


# ── cache ────────────────────────────────────────────────────────────────────
# Parsing a large deck costs a few hundred milliseconds, and the column
# re-opens / refreshes documents often. Entries are keyed by identity + mtime,
# so a saved file invalidates itself; callers must treat the result as
# read-only (it is serialised to JSON immediately).
_CACHE_LIMIT = 6
_CACHE: "OrderedDict[Tuple[str, int, int], Dict[str, Any]]" = OrderedDict()
_CACHE_LOCK = threading.Lock()


def clear_preview_cache() -> None:
    """Drop cached previews (tests and long-lived servers after an update)."""
    with _CACHE_LOCK:
        _CACHE.clear()


def build_preview(path: Path | str) -> Dict[str, Any]:
    """Build (or reuse) the preview payload for one document."""
    resolved = Path(path)
    try:
        stat = resolved.stat()
    except OSError as exc:
        raise PreviewError("文件不可读", 404) from exc
    if not resolved.is_file():
        raise PreviewError("不是文件", 404)
    if stat.st_size > MAX_DOCUMENT_BYTES:
        raise PreviewError("文件过大，无法内嵌预览", 413)
    kind = preview_kind(resolved)
    if not kind:
        raise PreviewError("不支持的文件类型", 415)
    key = (str(resolved.resolve()), int(stat.st_mtime_ns), int(stat.st_size))
    with _CACHE_LOCK:
        cached = _CACHE.get(key)
        if cached is not None:
            _CACHE.move_to_end(key)
            return cached
    payload = _build_payload(resolved, kind, stat.st_size)
    with _CACHE_LOCK:
        _CACHE[key] = payload
        _CACHE.move_to_end(key)
        while len(_CACHE) > _CACHE_LIMIT:
            _CACHE.popitem(last=False)
    return payload


def read_preview_media(path: Path | str, part: str) -> Tuple[bytes, str]:
    """Return one embedded image part of a document, with its media type."""
    clean = str(part or "").strip().replace("\\", "/")
    if not clean or clean.startswith("/") or ".." in clean.split("/"):
        raise PreviewError("非法的图片部件", 400)
    if not any(clean.startswith(prefix) for prefix in PREVIEW_MEDIA_PREFIXES):
        raise PreviewError("非法的图片部件", 400)
    suffix = posixpath.splitext(clean)[1].lower()
    if suffix not in PREVIEW_MEDIA_SUFFIXES:
        raise PreviewError("不支持的图片格式", 415)
    document = Path(path)
    try:
        size = document.stat().st_size
    except OSError as exc:
        raise PreviewError("文件不可读", 404) from exc
    if size > MAX_DOCUMENT_BYTES:
        raise PreviewError("文件过大", 413)
    with _open_archive(document) as archive:
        try:
            info = archive.getinfo(clean)
        except KeyError as exc:
            raise PreviewError("图片部件不存在", 404) from exc
        if info.file_size > MAX_MEDIA_PART_BYTES:
            raise PreviewError("图片过大", 413)
        data = archive.read(clean)
    media_type = mimetypes.guess_type(clean)[0] or "application/octet-stream"
    if not media_type.startswith("image/"):
        raise PreviewError("不支持的图片格式", 415)
    return data, media_type


# ── shared helpers ───────────────────────────────────────────────────────────


def _build_payload(path: Path, kind: str, size: int) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "ok": True,
        "kind": kind,
        "name": path.name,
        "size": int(size),
        "notes": [],
    }
    if kind == "csv":
        table = _build_csv(path)
        payload["table"] = table
        payload["notes"] = table.get("notes", [])
        payload["truncated"] = bool(table.get("truncated"))
        return payload
    if kind == "xlsx":
        workbook = _build_workbook(path)
        payload["workbook"] = workbook
        payload["notes"] = workbook.get("notes", [])
        payload["truncated"] = bool(workbook.get("notes"))
        return payload
    with _open_archive(path) as archive:
        if kind == "docx":
            document = _build_docx(archive)
            payload["document"] = document
            payload["notes"] = document.get("notes", [])
            payload["truncated"] = bool(document.get("truncated"))
        elif kind == "pptx":
            deck = _build_deck(archive)
            payload["deck"] = deck
            payload["notes"] = deck.get("notes", [])
            payload["truncated"] = bool(deck.get("truncated"))
        else:  # pragma: no cover - guarded by preview_kind
            raise PreviewError("不支持的文件类型", 415)
    return payload


def _open_archive(path: Path) -> zipfile.ZipFile:
    try:
        archive = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError) as exc:
        raise PreviewError("文件不是有效的 Office 文档", 422) from exc
    try:
        infos = archive.infolist()
        if len(infos) > MAX_ARCHIVE_ENTRIES:
            raise PreviewError("文档结构过于复杂", 422)
        total = 0
        for info in infos:
            total += max(0, int(info.file_size))
            if total > MAX_ARCHIVE_UNCOMPRESSED:
                raise PreviewError("文档解压后过大", 413)
    except Exception:
        archive.close()
        raise
    return archive


def _read_xml(archive: zipfile.ZipFile, name: str, *, required: bool = True) -> Optional[Element]:
    try:
        info = archive.getinfo(name)
    except KeyError:
        if required:
            raise PreviewError("文档缺少必要内容", 422)
        return None
    if info.file_size > MAX_XML_PART_BYTES:
        raise PreviewError("文档内容过大", 413)
    try:
        return _safe_xml_fromstring(archive.read(name))
    except Exception as exc:  # defusedxml raises several parse/forbid errors
        if required:
            raise PreviewError("文档内容无法解析", 422) from exc
        return None


def _rels(archive: zipfile.ZipFile, part: str) -> Dict[str, Tuple[str, bool]]:
    """Map relationship id → (target part or URL, is_external) for one part."""
    folder, name = posixpath.split(part)
    rels_name = posixpath.join(folder, "_rels", name + ".rels") if folder else "_rels/" + name + ".rels"
    root = _read_xml(archive, rels_name, required=False)
    if root is None:
        return {}
    out: Dict[str, Tuple[str, bool]] = {}
    for rel in root:
        rid = rel.get("Id") or ""
        target = rel.get("Target") or ""
        if not rid or not target:
            continue
        external = (rel.get("TargetMode") or "").lower() == "external"
        if not external:
            base = folder
            target = posixpath.normpath(posixpath.join(base, target.lstrip("/")))
        out[rid] = (target, external)
    return out


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _w(tag: str) -> str:
    return "{%s}%s" % (NS_W, tag)


def _a(tag: str) -> str:
    return "{%s}%s" % (NS_A, tag)


def _p(tag: str) -> str:
    return "{%s}%s" % (NS_P, tag)


def _esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def _text(value: Optional[str], limit: int = MAX_TEXT_CHARS) -> str:
    clean = str(value or "")
    return clean if len(clean) <= limit else clean[:limit]


def _val(el: Optional[Element], name: str) -> str:
    if el is None:
        return ""
    child = el.find(_w(name))
    if child is None:
        return ""
    return str(child.get(_w("val")) or "")


def _on(el: Optional[Element], name: str) -> bool:
    if el is None:
        return False
    child = el.find(_w(name))
    if child is None:
        return False
    return str(child.get(_w("val")) or "1").lower() not in ("0", "false", "off", "none")


def _px(value: float) -> str:
    return ("%.1f" % value).rstrip("0").rstrip(".")


def _media_html(part: str, *, width: Optional[float] = None, height: Optional[float] = None,
                extra_style: str = "", css_class: str = "dp-image") -> str:
    rules = []
    if width:
        rules.append("width:min(100%%, %.0fpx)" % max(8.0, width))
    if height:
        rules.append("height:%.0fpx" % max(8.0, height))
    if extra_style:
        rules.append(extra_style)
    style = (' style="%s"' % ";".join(rules)) if rules else ""
    return '<img class="%s" data-doc-part="%s" alt="" loading="lazy"%s>' % (
        css_class, _esc(part), style)


# ── Word ─────────────────────────────────────────────────────────────────────


def _build_docx(archive: zipfile.ZipFile) -> Dict[str, Any]:
    root = _read_xml(archive, "word/document.xml")
    rels = _rels(archive, "word/document.xml")
    styles = _docx_styles(archive)
    numbering = _docx_numbering(archive)
    renderer = _DocxRenderer(archive, rels, styles, numbering)
    body = root.find(_w("body"))
    if body is None:
        raise PreviewError("文档没有正文", 422)
    renderer.walk(body)
    renderer.close_lists()
    notes: List[str] = []
    if renderer.truncated:
        notes.append("document-truncated")
    if renderer.media_skipped:
        notes.append("media-skipped")
    document: Dict[str, Any] = {
        "html": "".join(renderer.parts),
        "truncated": renderer.truncated,
        "notes": notes,
    }
    core = _read_xml(archive, "docProps/core.xml", required=False)
    if core is not None:
        for child in core:
            if _local(child.tag) == "title" and (child.text or "").strip():
                document["title"] = _text(child.text.strip(), 200)
    return document


def _docx_styles(archive: zipfile.ZipFile) -> Dict[str, Dict[str, Any]]:
    root = _read_xml(archive, "word/styles.xml", required=False)
    styles: Dict[str, Dict[str, Any]] = {}
    if root is None:
        return styles
    for style in root.findall(_w("style")):
        style_id = style.get(_w("styleId")) or ""
        if not style_id:
            continue
        name_el = style.find(_w("name"))
        name = str(name_el.get(_w("val")) or "") if name_el is not None else ""
        level = 0
        num_id = ""
        num_level = ""
        ppr = style.find(_w("pPr"))
        if ppr is not None:
            outline = ppr.find(_w("outlineLvl"))
            if outline is not None and str(outline.get(_w("val")) or "").isdigit():
                level = min(6, max(1, int(outline.get(_w("val"))) + 1))
            num = ppr.find(_w("numPr"))
            if num is not None:
                num_id = _val(num, "numId")
                num_level = _val(num, "ilvl")
        styles[style_id] = {
            "name": name or style_id,
            "level": level,
            "numId": "" if num_id == "0" else num_id,
            "ilvl": num_level,
        }
    return styles


def _docx_numbering(archive: zipfile.ZipFile) -> Dict[str, Dict[int, str]]:
    """numId → level → number format (``bullet`` when unknown)."""
    root = _read_xml(archive, "word/numbering.xml", required=False)
    if root is None:
        return {}
    formats: Dict[str, Dict[int, str]] = {}
    for abstract in root.findall(_w("abstractNum")):
        aid = abstract.get(_w("abstractNumId")) or ""
        levels: Dict[int, str] = {}
        for lvl in abstract.findall(_w("lvl")):
            ilvl = lvl.get(_w("ilvl")) or "0"
            fmt = lvl.find(_w("numFmt"))
            levels[int(ilvl)] = str(fmt.get(_w("val")) or "bullet") if fmt is not None else "bullet"
        formats[aid] = levels
    out: Dict[str, Dict[int, str]] = {}
    for num in root.findall(_w("num")):
        num_id = num.get(_w("numId")) or ""
        aid_el = num.find(_w("abstractNumId"))
        if aid_el is not None:
            out[num_id] = formats.get(str(aid_el.get(_w("val")) or ""), {})
    return out


class _DocxRenderer:
    def __init__(self, archive: zipfile.ZipFile, rels: Dict[str, Tuple[str, bool]],
                 styles: Dict[str, Dict[str, Any]], numbering: Dict[str, Dict[int, str]]):
        self.archive = archive
        self.rels = rels
        self.styles = styles
        self.numbering = numbering
        self.parts: List[str] = []
        self.lists: List[Dict[str, Any]] = []
        self.blocks = 0
        self.truncated = False
        self.media_skipped = False

    # -- block flow ---------------------------------------------------------
    def walk(self, container: Element) -> None:
        for child in container:
            tag = _local(child.tag)
            if tag == "p":
                self.paragraph(child)
            elif tag == "tbl":
                self.close_lists()
                self.table(child)
            elif tag == "sdt":
                content = child.find(_w("sdtContent"))
                if content is not None:
                    self.walk(content)
            elif tag == "customXml":
                self.walk(child)
            # sectPr / bookmarks / proofing marks carry no visible content.

    def close_lists(self) -> None:
        while self.lists:
            entry = self.lists.pop()
            if entry.get("li"):
                self.parts.append("</li>")
            self.parts.append("</%s>" % entry["tag"])

    def paragraph(self, paragraph: Element) -> None:
        if self.blocks >= MAX_DOCX_BLOCKS:
            self.truncated = True
            return
        self.blocks += 1
        ppr = paragraph.find(_w("pPr"))
        style_id = _val(ppr, "pStyle")
        heading = self._heading_level(style_id, ppr)
        num = ppr.find(_w("numPr")) if ppr is not None else None
        num_id = _val(num, "numId") if num is not None else ""
        num_level = _val(num, "ilvl") if num is not None else ""
        if num_id != "0" and not num_id and style_id:
            # Word stores list membership on the paragraph style (python-docx's
            # "List Bullet"/"List Number" styles do), not on the paragraph.
            style = self.styles.get(style_id) or {}
            num_id = str(style.get("numId") or "")
            num_level = num_level or str(style.get("ilvl") or "")
        if num_id and num_id != "0":
            try:
                level = max(0, min(8, int(num_level or 0)))
            except ValueError:
                level = 0
            fmt = self.numbering.get(num_id, {}).get(level, "bullet")
            tag = "ul" if fmt in ("bullet", "none") or not fmt else "ol"
            self._open_item(tag, level)
            self.parts.append(self.inline(paragraph))
            return
        self.close_lists()
        inner = self.inline(paragraph)
        style = self._paragraph_style(ppr)
        if heading:
            tag = "h%d" % heading
            self.parts.append("<%s%s>%s</%s>" % (tag, style, inner or "&nbsp;", tag))
        else:
            self.parts.append("<p%s>%s</p>" % (style, inner or "&nbsp;"))

    def _open_item(self, tag: str, level: int) -> None:
        while self.lists and self.lists[-1]["level"] > level:
            entry = self.lists.pop()
            if entry.get("li"):
                self.parts.append("</li>")
            self.parts.append("</%s>" % entry["tag"])
        if self.lists and self.lists[-1]["level"] == level:
            entry = self.lists[-1]
            if entry.get("li"):
                self.parts.append("</li>")
            if entry["tag"] != tag:
                self.parts.append("</%s>" % entry["tag"])
                self.lists.pop()
        if not self.lists or self.lists[-1]["level"] != level:
            self.parts.append("<%s>" % tag)
            self.lists.append({"tag": tag, "level": level, "li": False})
        self.parts.append("<li>")
        self.lists[-1]["li"] = True

    def _heading_level(self, style_id: str, ppr: Optional[Element]) -> int:
        if ppr is not None:
            outline = ppr.find(_w("outlineLvl"))
            if outline is not None and str(outline.get(_w("val")) or "").isdigit():
                return min(6, max(1, int(outline.get(_w("val"))) + 1))
        if not style_id:
            return 0
        style = self.styles.get(style_id) or {}
        level = int(style.get("level") or 0)
        if level:
            return min(6, max(1, level))
        name = str(style.get("name") or style_id).strip().lower()
        match = re.match(r"^(?:heading|标题)\s*([1-9])", name)
        if match:
            return min(6, int(match.group(1)))
        if name in ("title", "标题"):
            return 1
        if name in ("subtitle", "副标题"):
            return 2
        return 0

    def _paragraph_style(self, ppr: Optional[Element]) -> str:
        if ppr is None:
            return ""
        rules: List[str] = []
        align = _val(ppr, "jc")
        if align:
            rules.append("text-align:" + {
                "both": "justify", "distribute": "justify", "center": "center",
                "right": "right", "end": "right", "start": "left", "left": "left",
            }.get(align, "left"))
        ind = ppr.find(_w("ind"))
        if ind is not None:
            left = ind.get(_w("left")) or ind.get(_w("start")) or ""
            if left.isdigit() and int(left) > 0:
                rules.append("margin-left:%spx" % _px(int(left) / 15.0))
        spacing = ppr.find(_w("spacing"))
        if spacing is not None:
            before = spacing.get(_w("before")) or ""
            after = spacing.get(_w("after")) or ""
            if before.isdigit():
                rules.append("margin-top:%spx" % _px(int(before) / 15.0))
            if after.isdigit():
                rules.append("margin-bottom:%spx" % _px(int(after) / 15.0))
        return (' style="%s"' % ";".join(rules)) if rules else ""

    # -- inline content -----------------------------------------------------
    def inline(self, container: Element) -> str:
        out: List[str] = []
        for child in container:
            tag = _local(child.tag)
            if tag == "r":
                out.append(self.run(child))
            elif tag == "hyperlink":
                inner = self.inline(child)
                href = ""
                rid = child.get("{%s}id" % NS_R)
                if rid:
                    target, external = self.rels.get(rid, ("", False))
                    if external and re.match(r"^(?:https?|mailto|tel):", target, re.I):
                        href = target
                if href:
                    out.append('<a href="%s" target="_blank" rel="noreferrer">%s</a>' % (_esc(href), inner))
                else:
                    out.append(inner)
            elif tag in ("ins", "fldSimple", "smartTag", "customXml"):
                out.append(self.inline(child))
            elif tag == "sdt":
                content = child.find(_w("sdtContent"))
                if content is not None:
                    out.append(self.inline(content))
            # w:del carries deleted revisions, w:pPr is handled by the caller.
        return "".join(out)

    def run(self, run: Element) -> str:
        rpr = run.find(_w("rPr"))
        style = self._run_style(rpr)
        pieces: List[str] = []
        for child in run:
            tag = _local(child.tag)
            if tag == "t":
                pieces.append(_esc(_text(child.text)))
            elif tag == "tab":
                pieces.append("\u2003")
            elif tag == "br":
                if str(child.get("{%s}type" % NS_W) or "") == "page":
                    pieces.append('<span class="dp-pagebreak"></span>')
                else:
                    pieces.append("<br>")
            elif tag == "noBreakHyphen":
                pieces.append("\u2011")
            elif tag == "drawing":
                pieces.append(self._drawing(child))
            elif tag == "pict":
                pieces.append(self._pict(child))
        inner = "".join(pieces)
        if not inner:
            return ""
        return ('<span style="%s">%s</span>' % (style, inner)) if style else inner

    def _run_style(self, rpr: Optional[Element]) -> str:
        if rpr is None:
            return ""
        rules: List[str] = []
        if _on(rpr, "b"):
            rules.append("font-weight:600")
        if _on(rpr, "i"):
            rules.append("font-style:italic")
        underline = rpr.find(_w("u"))
        if underline is not None and str(underline.get(_w("val")) or "single").lower() != "none":
            rules.append("text-decoration:underline")
        if _on(rpr, "strike") or _on(rpr, "dstrike"):
            rules.append("text-decoration:line-through")
        color = _val(rpr, "color")
        if color and color.lower() != "auto" and re.fullmatch(r"[0-9A-Fa-f]{6}", color):
            rules.append("color:#" + color)
        size = _val(rpr, "sz")
        if size.isdigit():
            points = int(size) / 2.0
            rules.append("font-size:%spx" % _px(min(96.0, max(6.0, points * 4 / 3))))
        highlight = _val(rpr, "highlight")
        if highlight in _HIGHLIGHT_COLORS:
            rules.append("background-color:" + _HIGHLIGHT_COLORS[highlight])
        vert = _val(rpr, "vertAlign")
        if vert == "superscript":
            rules.append("vertical-align:super;font-size:0.78em")
        elif vert == "subscript":
            rules.append("vertical-align:sub;font-size:0.78em")
        return ";".join(rules)

    def _part_from_rel(self, rid: str) -> str:
        target, external = self.rels.get(rid, ("", False))
        if external or not target.startswith("word/media/"):
            return ""
        try:
            info = self.archive.getinfo(target)
        except KeyError:
            return ""
        if info.file_size > MAX_MEDIA_PART_BYTES:
            self.media_skipped = True
            return ""
        suffix = posixpath.splitext(target)[1].lower()
        if suffix not in PREVIEW_MEDIA_SUFFIXES:
            return ""
        return target

    def _drawing(self, drawing: Element) -> str:
        blip = next(iter(drawing.iter(_a("blip"))), None)
        if blip is None:
            return ""
        part = self._part_from_rel(str(blip.get("{%s}embed" % NS_R) or ""))
        if not part:
            return ""
        width = None
        extent = next(iter(drawing.iter("{%s}extent" % NS_WP)), None)
        if extent is not None:
            try:
                width = int(extent.get("cx") or 0) / 9525.0
            except ValueError:
                width = None
        return _media_html(part, width=width)

    def _pict(self, pict: Element) -> str:
        image = next(iter(pict.iter("{%s}imagedata" % NS_V)), None)
        if image is None:
            return ""
        part = self._part_from_rel(str(image.get("{%s}id" % NS_R) or ""))
        return _media_html(part) if part else ""

    # -- tables -------------------------------------------------------------
    def table(self, table: Element) -> None:
        rows = table.findall(_w("tr"))
        if not rows:
            return
        grid = table.find(_w("tblGrid"))
        widths: List[int] = []
        if grid is not None:
            for col in grid.findall(_w("gridCol")):
                try:
                    widths.append(int(col.get(_w("w")) or 0))
                except ValueError:
                    widths.append(0)
        cells_by_row: List[List[Dict[str, Any]]] = []
        max_cols = 0
        for row in rows:
            cells: List[Dict[str, Any]] = []
            for tc in row.findall(_w("tc")):
                tcpr = tc.find(_w("tcPr"))
                span = 1
                vmerge: Optional[str] = None
                if tcpr is not None:
                    gs = tcpr.find(_w("gridSpan"))
                    if gs is not None:
                        try:
                            span = max(1, min(64, int(gs.get(_w("val")) or 1)))
                        except ValueError:
                            span = 1
                    vm = tcpr.find(_w("vMerge"))
                    if vm is not None:
                        vmerge = "continue" if str(vm.get(_w("val")) or "continue") == "continue" else "restart"
                cells.append({"tc": tc, "span": span, "vmerge": vmerge, "rowspan": 1})
            cells_by_row.append(cells)
            max_cols = max(max_cols, sum(cell["span"] for cell in cells))
        if max_cols <= 0:
            return

        slots_by_row: List[List[Optional[Dict[str, Any]]]] = []
        for index, cells in enumerate(cells_by_row):
            slots: List[Optional[Dict[str, Any]]] = []
            col = 0
            for cell in cells:
                while col < len(slots) and slots[col] is not None:
                    col += 1
                if cell["vmerge"] == "continue" and index > 0:
                    above = slots_by_row[index - 1]
                    owner = above[col] if col < len(above) else None
                    if owner is not None:
                        owner["rowspan"] += 1
                        for offset in range(cell["span"]):
                            while len(slots) <= col + offset:
                                slots.append(None)
                            slots[col + offset] = owner
                        col += cell["span"]
                        continue
                cell["col"] = col
                for offset in range(cell["span"]):
                    while len(slots) <= col + offset:
                        slots.append(None)
                    slots[col + offset] = cell
                col += cell["span"]
            slots_by_row.append(slots)

        out: List[str] = ['<div class="dp-table-wrap"><table class="dp-table">']
        if widths and sum(widths) > 0:
            total = float(sum(widths[:max_cols]))
            out.append("<colgroup>")
            for width in widths[:max_cols]:
                out.append('<col style="width:%.2f%%">' % (100.0 * width / total))
            out.append("</colgroup>")
        out.append("<tbody>")
        for index, cells in enumerate(cells_by_row):
            out.append("<tr>")
            rendered = 0
            for cell in cells:
                if cell["vmerge"] == "continue":
                    continue
                attrs: List[str] = []
                if cell["span"] > 1:
                    attrs.append(' colspan="%d"' % cell["span"])
                if cell["rowspan"] > 1:
                    attrs.append(' rowspan="%d"' % cell["rowspan"])
                style = self._cell_style(cell["tc"])
                if style:
                    attrs.append(' style="%s"' % style)
                inner = self._cell_html(cell["tc"])
                out.append("<td%s>%s</td>" % ("".join(attrs), inner))
                rendered += cell["span"]
            padding = max_cols - len(slots_by_row[index])
            if padding > 0:
                out.append("<td></td>" * padding)
            out.append("</tr>")
        out.append("</tbody></table></div>")
        self.parts.append("".join(out))

    def _cell_style(self, cell: Element) -> str:
        tcpr = cell.find(_w("tcPr"))
        if tcpr is None:
            return ""
        rules: List[str] = []
        shd = tcpr.find(_w("shd"))
        if shd is not None:
            fill = str(shd.get(_w("fill")) or "")
            if re.fullmatch(r"[0-9A-Fa-f]{6}", fill) and fill.upper() != "FFFFFF":
                rules.append("background:#" + fill)
        valign = _val(tcpr, "vAlign")
        if valign in ("top", "center", "bottom"):
            rules.append("vertical-align:" + ("middle" if valign == "center" else valign))
        width = tcpr.find(_w("tcW"))
        if width is not None:
            kind = str(width.get(_w("type")) or "")
            raw = str(width.get(_w("w")) or "")
            if kind == "dxa" and raw.isdigit() and int(raw) > 0:
                rules.append("width:%spx" % _px(min(900.0, int(raw) / 15.0)))
            elif kind == "pct" and raw.isdigit():
                rules.append("width:%.1f%%" % (int(raw) / 50.0))
        return ";".join(rules)

    def _cell_html(self, cell: Element) -> str:
        self.close_lists()
        saved_parts = self.parts
        self.parts = []
        self.walk(cell)
        self.close_lists()
        inner = "".join(self.parts)
        self.parts = saved_parts
        return inner


# ── PowerPoint ───────────────────────────────────────────────────────────────

_OFFICE_THEME_COLORS = [
    "FFFFFF", "000000", "EEECE1", "1F497D", "4F81BD", "C0504D",
    "9BBB59", "8064A2", "4BACC6", "F79646",
]


def _build_deck(archive: zipfile.ZipFile) -> Dict[str, Any]:
    presentation = _read_xml(archive, "ppt/presentation.xml")
    slide_size = presentation.find(_p("sldSz"))
    try:
        slide_cx = int(slide_size.get("cx") or 12192000) if slide_size is not None else 12192000
        slide_cy = int(slide_size.get("cy") or 6858000) if slide_size is not None else 6858000
    except ValueError:
        slide_cx, slide_cy = 12192000, 6858000
    slide_cx = max(914400, slide_cx)
    slide_cy = max(914400, slide_cy)
    # The deck is laid out on a 960px-wide logical canvas; the renderer scales
    # that canvas to the column width, so 16:9 decks map 1pt to 1px.
    width = 960.0
    scale = width * 12700.0 / float(slide_cx)
    height = slide_cy / 12700.0 * scale

    theme = _pptx_theme(archive, presentation)
    rels = _rels(archive, "ppt/presentation.xml")
    slide_parts: List[str] = []
    id_list = presentation.find(_p("sldIdLst"))
    if id_list is not None:
        for item in id_list.findall(_p("sldId")):
            rid = item.get("{%s}id" % NS_R) or ""
            target = rels.get(rid, ("", False))[0]
            if target:
                slide_parts.append(target)
    if not slide_parts:
        for name in archive.namelist():
            match = re.fullmatch(r"ppt/slides/slide(\d+)\.xml", name)
            if match:
                slide_parts.append((int(match.group(1)), name))
        slide_parts = [name for _index, name in sorted(slide_parts)]

    cached_layouts: Dict[str, Dict[str, Any]] = {}
    notes: List[str] = []
    slides: List[Dict[str, Any]] = []
    truncated = len(slide_parts) > MAX_DECK_SLIDES
    for part in slide_parts[:MAX_DECK_SLIDES]:
        try:
            slides.append(_build_slide(archive, part, theme, scale, cached_layouts))
        except PreviewError:
            raise
        except Exception:
            slides.append({"html": "", "background": "#ffffff"})
    if truncated:
        notes.append("slides-truncated")
    media_skipped = False
    for slide in slides:
        if slide.pop("_media_skipped", False):
            media_skipped = True
    if media_skipped:
        notes.append("media-skipped")
    deck: Dict[str, Any] = {
        "width": round(width, 2),
        "height": round(height, 2),
        "slides": slides,
        "truncated": truncated,
        "notes": notes,
    }
    return deck


def _pptx_theme(archive: zipfile.ZipFile, presentation: Element) -> Dict[str, Any]:
    colors: Dict[str, str] = {}
    fonts: Dict[str, str] = {"major": "Arial", "minor": "Arial"}
    theme_part = "ppt/theme/theme1.xml"
    rels = _rels(archive, "ppt/presentation.xml")
    for rid, (target, external) in rels.items():
        if not external and target.endswith(".xml") and "theme" in target:
            theme_part = target
            break
    root = _read_xml(archive, theme_part, required=False)
    if root is not None:
        scheme = root.find(".//" + _a("clrScheme"))
        if scheme is not None:
            for entry in scheme:
                key = _local(entry.tag)
                color = None
                for child in entry:
                    tag = _local(child.tag)
                    if tag == "srgbClr":
                        color = str(child.get("val") or "")
                    elif tag == "sysClr":
                        color = str(child.get("lastClr") or "")
                    if color:
                        break
                if color and re.fullmatch(r"[0-9A-Fa-f]{6}", color):
                    colors[key] = "#" + color.upper()
        font_scheme = root.find(".//" + _a("fontScheme"))
        if font_scheme is not None:
            for key in ("major", "minor"):
                node = font_scheme.find(_a(key + "Font"))
                latin = node.find(_a("latin")) if node is not None else None
                if latin is not None and latin.get("typeface"):
                    fonts[key] = str(latin.get("typeface"))
    for key, value in (("dk1", "#000000"), ("lt1", "#FFFFFF"), ("dk2", "#1F497D"),
                       ("lt2", "#EEECE1"), ("accent1", "#4F81BD"), ("accent2", "#C0504D"),
                       ("accent3", "#9BBB59"), ("accent4", "#8064A2"), ("accent5", "#4BACC6"),
                       ("accent6", "#F79646"), ("hlink", "#0000FF"), ("folHlink", "#800080")):
        colors.setdefault(key, value)
    return {"colors": colors, "fonts": fonts}


def _build_slide(archive: zipfile.ZipFile, part: str, theme: Dict[str, Any],
                 scale: float, layout_cache: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    root = _read_xml(archive, part)
    rels = _rels(archive, part)
    context = _SlideContext(archive, rels, theme, scale, layout_cache, part)
    tree = root.find("%s/%s" % (_p("cSld"), _p("spTree")))
    background = _slide_background(root, theme)
    parts: List[str] = []
    if tree is not None:
        context.render_children(tree, None, parts, [0])
    return {
        "html": "".join(parts),
        "background": background,
        "_media_skipped": context.media_skipped,
    }


def _slide_background(root: Element, theme: Dict[str, Any]) -> str:
    node = root.find(".//" + _p("bg"))
    if node is None:
        return "#ffffff"
    solid = node.find(".//" + _a("solidFill"))
    if solid is not None:
        color = _color_from_fill(solid, theme)
        if color:
            return color
    bg_ref = node.find(_p("bgRef"))
    if bg_ref is not None:
        try:
            index = int(bg_ref.get("idx") or 0)
        except ValueError:
            index = 0
        if index == 1:
            return str(theme["colors"].get("lt1", "#ffffff"))
        color = _color_from_fill(bg_ref, theme)
        if color:
            return color
    # Layout / master backgrounds are rare; fall back to white so black text
    # stays readable on the canvas.
    return "#ffffff"


def _color_from_fill(node: Optional[Element], theme: Dict[str, Any]) -> str:
    if node is None:
        return ""
    for child in node:
        tag = _local(child.tag)
        if tag == "srgbClr":
            value = str(child.get("val") or "")
        elif tag == "schemeClr":
            value = str(theme["colors"].get(str(child.get("val") or ""), "") or "").lstrip("#")
        elif tag == "sysClr":
            value = str(child.get("lastClr") or "")
        elif tag == "prstClr":
            value = _PRESET_COLORS.get(str(child.get("val") or ""), "")
        else:
            continue
        if value and re.fullmatch(r"[0-9A-Fa-f]{6}", value):
            return _apply_color_transforms("#" + value.upper(), child)
    return ""


_PRESET_COLORS = {
    "black": "000000", "white": "FFFFFF", "red": "FF0000", "green": "008000",
    "blue": "0000FF", "yellow": "FFFF00", "gray": "808080", "grey": "808080",
    "orange": "FFA500", "purple": "800080", "silver": "C0C0C0",
}


def _apply_color_transforms(value: str, node: Element) -> str:
    rgb = value.lstrip("#")
    try:
        r, g, b = int(rgb[0:2], 16), int(rgb[2:4], 16), int(rgb[4:6], 16)
    except ValueError:
        return value
    for child in node:
        tag = _local(child.tag)
        try:
            amount = int(child.get("val") or 0) / 100000.0
        except ValueError:
            continue
        if tag == "lumMod":
            r, g, b = int(r * amount), int(g * amount), int(b * amount)
        elif tag == "lumOff":
            r, g, b = int(r + 255 * amount), int(g + 255 * amount), int(b + 255 * amount)
        elif tag == "tint":
            r, g, b = int(r + (255 - r) * amount), int(g + (255 - g) * amount), int(b + (255 - b) * amount)
        elif tag == "shade":
            r, g, b = int(r * amount), int(g * amount), int(b * amount)
    return "#%02X%02X%02X" % (max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))


class _SlideContext:
    """Rendering state for one slide: rels, theme, geometry inheritance."""

    def __init__(self, archive: zipfile.ZipFile, rels: Dict[str, Tuple[str, bool]],
                 theme: Dict[str, Any], scale: float, layout_cache: Dict[str, Dict[str, Any]],
                 slide_part: str):
        self.archive = archive
        self.rels = rels
        self.theme = theme
        self.scale = scale
        self.layout_cache = layout_cache
        self.slide_part = slide_part
        self.media_skipped = False
        layout_part = ""
        for target, external in rels.values():
            if not external and "slideLayout" in target:
                layout_part = target
                break
        self.layout = self._layout_context(layout_part)

    def _layout_context(self, layout_part: str) -> Dict[str, Any]:
        if not layout_part:
            return {"placeholders": {}, "master": {}, "tx_styles": None, "background": ""}
        cached = self.layout_cache.get(layout_part)
        if cached is not None:
            return cached
        layout_root = _read_xml(self.archive, layout_part, required=False)
        placeholders = _placeholder_map(layout_root.find("%s/%s" % (_p("cSld"), _p("spTree")))) if layout_root is not None else {}
        master_part = ""
        for target, external in _rels(self.archive, layout_part).values():
            if not external and "slideMaster" in target:
                master_part = target
                break
        master_root = _read_xml(self.archive, master_part, required=False) if master_part else None
        master_placeholders = _placeholder_map(
            master_root.find("%s/%s" % (_p("cSld"), _p("spTree")))) if master_root is not None else {}
        tx_styles = master_root.find(_p("txStyles")) if master_root is not None else None
        context = {"placeholders": placeholders, "master": master_placeholders,
                   "tx_styles": tx_styles, "master_part": master_part}
        self.layout_cache[layout_part] = context
        return context

    # -- shape tree ---------------------------------------------------------
    def render_children(self, container: Element, transform: Optional[Tuple[float, float, float, float]],
                        out: List[str], depth: List[int]) -> None:
        for child in container:
            tag = _local(child.tag)
            if tag == "sp":
                self.render_shape(child, transform, out)
            elif tag == "pic":
                self.render_picture(child, transform, out)
            elif tag == "graphicFrame":
                self.render_graphic_frame(child, transform, out)
            elif tag == "grpSp":
                if depth[0] < 3:
                    depth[0] += 1
                    self.render_children(child, self._group_transform(child, transform), out, depth)
                    depth[0] -= 1

    def _group_transform(self, group: Element, parent: Optional[Tuple[float, float, float, float]]):
        xfrm = group.find("%s/%s" % (_p("grpSpPr"), _a("xfrm")))
        if xfrm is None:
            return parent
        off = xfrm.find(_a("off"))
        ext = xfrm.find(_a("ext"))
        ch_off = xfrm.find(_a("chOff"))
        ch_ext = xfrm.find(_a("chExt"))
        if off is None or ext is None or ch_off is None or ch_ext is None:
            return parent
        try:
            ox, oy = float(off.get("x") or 0), float(off.get("y") or 0)
            ex, ey = float(ext.get("cx") or 0), float(ext.get("cy") or 0)
            cx, cy = float(ch_off.get("x") or 0), float(ch_off.get("y") or 0)
            cex, cey = float(ch_ext.get("cx") or 0), float(ch_ext.get("cy") or 0)
        except ValueError:
            return parent
        if cex <= 0 or cey <= 0:
            return parent
        sx, sy = ex / cex, ey / cey
        # Child EMU → group EMU, then composed with the parent mapping.
        ax, bx, ay, by = parent or (0.0, 1.0, 0.0, 1.0)
        return (ax + bx * (ox - cx * sx), bx * sx, ay + by * (oy - cy * sy), by * sy)

    # -- shapes -------------------------------------------------------------
    def _xfrm(self, shape: Element, layout: Optional[Element], master: Optional[Element],
              transform: Optional[Tuple[float, float, float, float]]):
        for node in (shape, layout, master):
            if node is None:
                continue
            xfrm = node.find("%s/%s" % (_p("spPr"), _a("xfrm")))
            if xfrm is None:
                tx_body = node.find(_p("txBody"))
                xfrm = tx_body.find(_a("xfrm")) if tx_body is not None else None
            if xfrm is None:
                continue
            off = xfrm.find(_a("off"))
            ext = xfrm.find(_a("ext"))
            if off is None or ext is None:
                continue
            try:
                box = _transform_box(
                    float(off.get("x") or 0), float(off.get("y") or 0),
                    float(ext.get("cx") or 0), float(ext.get("cy") or 0), transform)
            except ValueError:
                continue
            if box is not None:
                return _box_to_px(box, self.scale)
        return None

    def render_shape(self, shape: Element, transform, out: List[str]) -> None:
        ph = shape.find("%s/%s/%s" % (_p("nvSpPr"), _p("nvPr"), _p("ph")))
        layout_ph = master_ph = None
        if ph is not None:
            layout_ph = _pick_placeholder(self.layout["placeholders"], ph)
            master_ph = _pick_placeholder(self.layout["master"], ph)
        box = self._xfrm(shape, layout_ph, master_ph, transform)
        if box is None or box["w"] <= 0 or box["h"] <= 0:
            return
        sp_pr = shape.find(_p("spPr"))
        fill = _color_from_fill(sp_pr.find(_a("solidFill")), self.theme) if sp_pr is not None else ""
        line_node = sp_pr.find("%s/%s" % (_a("ln"), _a("solidFill"))) if sp_pr is not None else None
        line = _color_from_fill(line_node, self.theme) if line_node is not None else ""
        geom = sp_pr.find(_a("prstGeom")) if sp_pr is not None else None
        preset = str(geom.get("prst") or "") if geom is not None else ""
        if preset == "line":
            return
        body = shape.find(_p("txBody"))
        body_prs = self._body_prs(shape, layout_ph, master_ph)
        anchor = _first_attr(body_prs, "anchor") or "t"
        defaults = self._defaults(ph, layout_ph, master_ph, body)
        paragraphs: List[str] = []
        if body is not None:
            paragraphs = self._paragraphs(body, defaults)
        if not paragraphs and not fill and not line:
            return
        rules = [
            "left:%.1fpx" % box["x"], "top:%.1fpx" % box["y"],
            "width:%.1fpx" % box["w"], "height:%.1fpx" % box["h"],
            "justify-content:" + {"ctr": "center", "b": "flex-end"}.get(anchor, "flex-start"),
        ]
        if fill:
            rules.append("background:" + fill)
        if line:
            rules.append("border:1px solid " + line)
        if preset in ("roundRect", "ellipse"):
            rules.append("border-radius:" + ("50%" if preset == "ellipse" else "10px"))
        for key, name in (("lIns", "padding-left"), ("rIns", "padding-right"),
                          ("tIns", "padding-top"), ("bIns", "padding-bottom")):
            raw = _first_attr(body_prs, key)
            try:
                value = int(raw) if raw else 0
            except ValueError:
                value = 0
            if value:
                rules.append("%s:%.1fpx" % (name, value / 12700.0 * self.scale))
        out.append('<div class="dp-shape" style="%s">%s</div>' % (";".join(rules), "".join(paragraphs)))

    def _body_prs(self, shape: Optional[Element], layout: Optional[Element],
                  master: Optional[Element]) -> List[Element]:
        out: List[Element] = []
        for node in (shape, layout, master):
            if node is None:
                continue
            body = node.find(_p("txBody"))
            if body is None:
                continue
            pr = body.find(_a("bodyPr"))
            if pr is not None:
                out.append(pr)
        return out

    def _defaults(self, ph: Optional[Element], layout_ph: Optional[Element],
                  master_ph: Optional[Element], body: Optional[Element]) -> Dict[str, Any]:
        """Nearest-first level styles: shape → layout → master → master txStyles."""
        if ph is None:
            # A free text box is not a placeholder: it inherits neither the
            # layout's geometry nor the body placeholder's bullets/sizes.
            sources: List[Optional[Element]] = []
            if body is not None:
                sources.append(body.find(_a("lstStyle")))
            return {"sources": sources, "kind": "body"}
        kind = str(ph.get("type") or "body") if ph is not None else "body"
        style_tag = "titleStyle" if kind in ("title", "ctrTitle") else "bodyStyle"
        tx_style = None
        tx_styles = self.layout.get("tx_styles")
        if tx_styles is not None:
            tx_style = tx_styles.find(_p(style_tag))
        sources: List[Optional[Element]] = []
        if body is not None:
            sources.append(body.find(_a("lstStyle")))
        for node in (layout_ph, master_ph):
            if node is not None:
                tx = node.find(_p("txBody"))
                sources.append(tx.find(_a("lstStyle")) if tx is not None else None)
        if tx_style is not None:
            sources.append(tx_style)
        return {"sources": sources, "kind": kind}

    def _level_defaults(self, sources: List[Optional[Element]], level: int) -> Tuple[Optional[Element], Optional[Element]]:
        """Return (pPr, defRPr) for a paragraph level, nearest source first."""
        for source in sources:
            if source is None:
                continue
            level_pr = source.find(_a("lvl%dpPr" % (level + 1)))
            if level_pr is not None:
                return level_pr, level_pr.find(_a("defRPr"))
        return None, None

    def _paragraphs(self, body: Element, defaults: Dict[str, Any]) -> List[str]:
        sources = defaults["sources"]
        out: List[str] = []
        for paragraph in body.findall(_a("p")):
            ppr = paragraph.find(_a("pPr"))
            try:
                level = max(0, min(8, int(ppr.get("lvl") or 0))) if ppr is not None else 0
            except ValueError:
                level = 0
            level_pr, level_rpr = self._level_defaults(sources, level)
            align = _first_attr((ppr, level_pr), "algn")
            align = {"l": "left", "ctr": "center", "r": "right", "just": "justify"}.get(align, "")
            rules: List[str] = []
            if align:
                rules.append("text-align:" + align)
            margin = 0.0
            margin_source = next((node for node in (ppr, level_pr)
                                  if node is not None and node.get("marL") not in (None, "")), None)
            if margin_source is not None:
                try:
                    margin = float(margin_source.get("marL") or 0) / 12700.0 * self.scale
                except ValueError:
                    margin = 0.0
            if margin > 0:
                rules.append("margin-left:%.1fpx" % margin)
            bullet_marker = _bullet_marker(ppr, level_pr)
            spacing = _line_spacing(ppr, level_pr)
            if spacing:
                rules.append("line-height:" + spacing)
            runs: List[str] = []
            for child in paragraph:
                tag = _local(child.tag)
                if tag == "r":
                    runs.append(self._run(child, level_rpr))
                elif tag == "br":
                    runs.append("<br>")
                elif tag == "fld":
                    runs.append(_esc(_text(child.text)))
            if not runs:
                runs.append("&nbsp;")
            marker = ('<span class="dp-bullet" aria-hidden="true">%s</span>' % bullet_marker) if bullet_marker else ""
            out.append('<p class="dp-para" style="%s">%s%s</p>' % (";".join(rules), marker, "".join(runs)))
        return out

    def _run(self, run: Element, level_rpr: Optional[Element]) -> str:
        rpr = run.find(_a("rPr"))
        rules: List[str] = []
        size = None
        for node in (rpr, level_rpr):
            if node is None:
                continue
            raw = node.get("sz")
            if raw and raw.isdigit():
                size = int(raw) / 100.0
                break
        if size is None:
            size = 18.0
        rules.append("font-size:%spx" % _px(min(200.0, max(4.0, size * self.scale))))
        bold = _first_attr((rpr, level_rpr), "b")
        if bold in ("1", "true"):
            rules.append("font-weight:700")
        italic = _first_attr((rpr, level_rpr), "i")
        if italic in ("1", "true"):
            rules.append("font-style:italic")
        underline = _first_attr((rpr, level_rpr), "u")
        if underline and underline != "none":
            rules.append("text-decoration:underline")
        fill_node = None
        for node in (rpr, level_rpr):
            if node is not None and node.find(_a("solidFill")) is not None:
                fill_node = node.find(_a("solidFill"))
                break
        color = _color_from_fill(fill_node, self.theme)
        if color:
            rules.append("color:" + color)
        face = ""
        for node in (rpr, level_rpr):
            latin = node.find(_a("latin")) if node is not None else None
            if latin is not None and latin.get("typeface"):
                face = str(latin.get("typeface"))
                break
        if face:
            if face == "+mj-lt":
                face = str(self.theme["fonts"].get("major") or "")
            elif face == "+mn-lt":
                face = str(self.theme["fonts"].get("minor") or "")
            if face:
                rules.append("font-family:%s" % _css_font(face))
        value = _esc(_text(run.findtext(_a("t"))))
        return '<span style="%s">%s</span>' % (";".join(rules), value)

    def render_picture(self, picture: Element, transform, out: List[str]) -> None:
        sp_pr = picture.find(_p("spPr"))
        xfrm = sp_pr.find(_a("xfrm")) if sp_pr is not None else None
        box = self._xfrm_from(xfrm, transform)
        if box is None:
            return
        blip = picture.find("%s/%s" % (_p("blipFill"), _a("blip")))
        if blip is None:
            return
        part = self._media_part(str(blip.get("{%s}embed" % NS_R) or ""))
        if not part:
            return
        out.append('<img class="dp-image" data-doc-part="%s" alt="" style="position:absolute;left:%.1fpx;top:%.1fpx;width:%.1fpx;height:%.1fpx">'
                   % (_esc(part), box["x"], box["y"], box["w"], box["h"]))

    def _xfrm_from(self, xfrm: Optional[Element], transform=None):
        if xfrm is None:
            return None
        off = xfrm.find(_a("off"))
        ext = xfrm.find(_a("ext"))
        if off is None or ext is None:
            return None
        try:
            box = _transform_box(
                float(off.get("x") or 0), float(off.get("y") or 0),
                float(ext.get("cx") or 0), float(ext.get("cy") or 0), transform)
        except ValueError:
            return None
        return _box_to_px(box, self.scale) if box is not None else None

    def _media_part(self, rid: str) -> str:
        target, external = self.rels.get(rid, ("", False))
        if external or not target.startswith("ppt/media/"):
            return ""
        try:
            info = self.archive.getinfo(target)
        except KeyError:
            return ""
        if info.file_size > MAX_MEDIA_PART_BYTES:
            self.media_skipped = True
            return ""
        if posixpath.splitext(target)[1].lower() not in PREVIEW_MEDIA_SUFFIXES:
            return ""
        return target

    def render_graphic_frame(self, frame: Element, transform, out: List[str]) -> None:
        xfrm = frame.find(_p("xfrm"))
        box = self._xfrm_from(xfrm, transform)
        if box is None:
            return
        graphic = frame.find("%s/%s" % (_a("graphic"), _a("graphicData")))
        if graphic is None:
            return
        table = graphic.find(_a("tbl"))
        if table is None:
            uri = str(graphic.get("uri") or "")
            label = "图表" if "chart" in uri else ("图示" if "diagram" in uri else "对象")
            out.append('<div class="dp-shape dp-placeholder" style="left:%.1fpx;top:%.1fpx;width:%.1fpx;height:%.1fpx">%s</div>'
                       % (box["x"], box["y"], box["w"], box["h"], label))
            return
        out.append(self._graphic_table(table, box))

    def _graphic_table(self, table: Element, box) -> str:
        grid = table.find(_a("tblGrid"))
        grid_cols = grid.findall(_a("gridCol")) if grid is not None else []
        widths: List[float] = []
        for col in grid_cols:
            try:
                widths.append(float(col.get("w") or 0))
            except ValueError:
                widths.append(0.0)
        total = sum(widths) or 1.0
        rows = table.findall(_a("tr"))
        pieces = ['<div class="dp-shape dp-table" style="left:%.1fpx;top:%.1fpx;width:%.1fpx;height:%.1fpx">'
                  % (box["x"], box["y"], box["w"], box["h"])]
        pieces.append('<table class="dp-table"><colgroup>')
        for width in widths:
            pieces.append('<col style="width:%.2f%%">' % (100.0 * width / total))
        pieces.append("</colgroup><tbody>")
        for row in rows:
            height = ""
            try:
                height = ' style="height:%.1fpx"' % (
                    float(row.get("h") or 0) / 12700.0 * self.scale)
            except ValueError:
                height = ""
            pieces.append("<tr%s>" % height)
            for cell in row.findall(_a("tc")):
                cell_pr = cell.find(_a("tcPr"))
                style = ""
                fill = ""
                if cell_pr is not None:
                    fill = _color_from_fill(cell_pr.find(_a("solidFill")), self.theme)
                if fill:
                    style = ' style="background:%s"' % fill
                tx_body = cell.find(_a("txBody"))
                pieces.append("<td%s>%s</td>" % (
                    style,
                    "".join(self._paragraphs(tx_body, {"sources": []})) if tx_body is not None else "",
                ))
            pieces.append("</tr>")
        pieces.append("</tbody></table></div>")
        return "".join(pieces)


def _placeholder_map(tree: Optional[Element]) -> Dict[Tuple[str, str], Element]:
    out: Dict[Tuple[str, str], Element] = {}
    if tree is None:
        return out
    for shape in tree.findall(_p("sp")):
        ph = shape.find("%s/%s/%s" % (_p("nvSpPr"), _p("nvPr"), _p("ph")))
        if ph is None:
            continue
        out.setdefault((str(ph.get("type") or "obj"), str(ph.get("idx") or "")), shape)
    return out


def _pick_placeholder(mapping: Dict[Tuple[str, str], Element], ph: Element) -> Optional[Element]:
    kind = str(ph.get("type") or "obj")
    idx = str(ph.get("idx") or "")
    for key in ((kind, idx), (kind, ""), ("obj", idx), ("body", idx), ("obj", "")):
        if key in mapping:
            return mapping[key]
    return None


def _bullet_marker(ppr: Optional[Element], level_pr: Optional[Element]) -> str:
    for node in (ppr, level_pr):
        if node is None:
            continue
        if node.find(_a("buNone")) is not None:
            return ""
        char = node.find(_a("buChar"))
        if char is not None:
            return _esc(str(char.get("char") or "•"))
        if node.find(_a("buAutoNum")) is not None:
            return "•"
    return ""


def _line_spacing(ppr: Optional[Element], level_pr: Optional[Element]) -> str:
    for node in (ppr, level_pr):
        if node is None:
            continue
        spacing = node.find(_a("lnSpc"))
        if spacing is None:
            continue
        pct = spacing.find(_a("spcPct"))
        if pct is not None:
            try:
                return "%.2f" % (int(pct.get("val") or 100000) / 100000.0)
            except ValueError:
                return ""
    return ""


def _first_attr(nodes: Iterable[Optional[Element]], name: str) -> str:
    for node in nodes:
        if node is None:
            continue
        value = node.get(name)
        if value not in (None, ""):
            return str(value)
    return ""


def _transform_box(x: float, y: float, width: float, height: float,
                   transform: Optional[Tuple[float, float, float, float]]):
    """Map a shape box from child EMU into slide EMU through group transforms."""
    if width <= 0 or height <= 0:
        return None
    ax, bx, ay, by = transform or (0.0, 1.0, 0.0, 1.0)
    return {
        "x": ax + bx * x,
        "y": ay + by * y,
        "w": width * bx,
        "h": height * by,
    }


def _box_to_px(box: Dict[str, float], scale: float) -> Dict[str, float]:
    factor = scale / 12700.0
    return {
        "x": box["x"] * factor,
        "y": box["y"] * factor,
        "w": box["w"] * factor,
        "h": box["h"] * factor,
    }


def _css_font(face: str) -> str:
    # The value sits inside a double-quoted style attribute, so the family
    # name must use single quotes (or none) to keep the attribute intact, and
    # a document-supplied face must not be able to inject other declarations.
    safe = re.sub(r"[^0-9A-Za-z _\-\u4e00-\u9fff]", "", str(face or ""))[:64].strip()
    return "'%s', sans-serif" % safe if safe else "sans-serif"


# ── delimited text ───────────────────────────────────────────────────────────


def _decode_csv_bytes(raw: bytes) -> Tuple[str, str]:
    """Decode a delimited file as UTF-8 (with or without BOM), UTF-16 or GBK."""
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig", "replace"), "utf-8-sig"
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        return raw.decode("utf-16", "replace"), "utf-16"
    for encoding in ("utf-8", "gb18030"):
        try:
            return raw.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace"), "utf-8?"


def _csv_cell(value: Any) -> str:
    text = _text(value, MAX_CSV_CELL_CHARS)
    return _esc(text).replace("\r\n", "<br>").replace("\r", "<br>").replace("\n", "<br>")


def _build_csv(path: Path) -> Dict[str, Any]:
    """Turn a CSV/TSV file into one scrollable table (capped rows/columns)."""
    try:
        with path.open("rb") as handle:
            raw = handle.read(MAX_CSV_BYTES + 1)
    except OSError as exc:
        raise PreviewError("文件不可读", 404) from exc
    truncated_bytes = len(raw) > MAX_CSV_BYTES
    text, encoding = _decode_csv_bytes(raw[:MAX_CSV_BYTES])
    if truncated_bytes and "\n" in text:
        text = text.rsplit("\n", 1)[0]
    fallback = "\t" if path.suffix.lower() == ".tsv" else ","
    delimiter = fallback
    try:
        delimiter = csv.Sniffer().sniff(text[:65536], delimiters=",;\t|").delimiter
    except csv.Error:
        pass
    notes: List[str] = []
    rows: List[List[str]] = []
    columns_truncated = False
    truncated = False
    try:
        reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter, strict=False)
        for index, row in enumerate(reader):
            if index >= MAX_CSV_ROWS:
                truncated = True
                break
            if len(row) > MAX_CSV_COLUMNS:
                columns_truncated = True
                row = row[:MAX_CSV_COLUMNS]
            rows.append([str(value) for value in row])
    except csv.Error:
        truncated = True
    if truncated_bytes:
        truncated = True
    column_count = min(MAX_CSV_COLUMNS, max((len(row) for row in rows), default=0))
    pieces: List[str] = ['<div class="dp-sheet-wrap"><table class="dp-sheet dp-csv"><tbody>']
    for index, row in enumerate(rows):
        pieces.append('<tr class="dp-csv-head">' if index == 0 else "<tr>")
        for column in range(column_count):
            value = row[column] if column < len(row) else ""
            pieces.append("<td>%s</td>" % _csv_cell(value))
        pieces.append("</tr>")
    pieces.append("</tbody></table></div>")
    if truncated:
        notes.append("rows-truncated")
    if columns_truncated:
        notes.append("columns-truncated")
    return {
        "html": "".join(pieces) if rows else "",
        "rows": len(rows),
        "cols": column_count,
        "delimiter": delimiter,
        "encoding": encoding,
        "truncated": bool(notes),
        "notes": notes,
    }


# ── Excel ────────────────────────────────────────────────────────────────────


def _build_workbook(path: Path) -> Dict[str, Any]:
    try:
        from openpyxl import load_workbook
        from openpyxl.utils import column_index_from_string, get_column_letter
    except Exception as exc:  # pragma: no cover - openpyxl ships with the app
        raise PreviewError("缺少表格解析组件", 501) from exc
    try:
        workbook = load_workbook(filename=str(path), data_only=True, keep_links=False)
    except Exception as exc:
        raise PreviewError("工作簿无法读取", 422) from exc
    sheets: List[Dict[str, Any]] = []
    notes: List[str] = []
    remaining_cells = MAX_SHEET_CELLS
    workbook_cut = len(workbook.worksheets) > MAX_SHEETS
    try:
        active_name = str(workbook.active.title) if workbook.active is not None else ""
    except Exception:
        active_name = ""
    for worksheet in workbook.worksheets[:MAX_SHEETS]:
        sheet, used = _build_sheet(
            worksheet, remaining_cells, column_index_from_string, get_column_letter, active_name)
        remaining_cells -= used
        sheets.append(sheet)
        if remaining_cells <= 0:
            break
    if workbook_cut:
        notes.append("sheets-truncated")
    if any(sheet.get("truncated") for sheet in sheets):
        notes.append("rows-truncated")
    return {
        "sheets": sheets,
        "active": next((sheet["name"] for sheet in sheets if sheet.get("active")),
                       sheets[0]["name"] if sheets else ""),
        "notes": notes,
    }


def _build_sheet(worksheet, remaining_cells: int, column_index_from_string, get_column_letter,
                 active_name: str = "") -> Tuple[Dict[str, Any], int]:
    try:
        max_row = min(int(worksheet.max_row or 0), MAX_SHEET_ROWS)
        max_col = min(int(worksheet.max_column or 0), MAX_SHEET_COLUMNS)
    except (TypeError, ValueError):
        max_row = max_col = 0
    truncated = bool((worksheet.max_row or 0) > max_row or (worksheet.max_column or 0) > max_col)
    sheet: Dict[str, Any] = {
        "name": str(worksheet.title),
        "hidden": str(getattr(worksheet, "sheet_state", "visible")) != "visible",
        "active": str(worksheet.title) == active_name,
        "truncated": truncated,
        "rows": max_row,
        "cols": max_col,
        "freezeRow": 0,
        "freezeCol": 0,
        "html": "",
    }
    if max_row <= 0 or max_col <= 0:
        sheet["html"] = ""
        return sheet, 0
    freeze = str(getattr(worksheet, "freeze_panes", "") or "")
    match = re.match(r"^([A-Za-z]+)(\d+)$", freeze)
    if match:
        sheet["freezeRow"] = max(0, int(match.group(2)) - 1)
        try:
            sheet["freezeCol"] = max(0, column_index_from_string(match.group(1).upper()) - 1)
        except ValueError:
            sheet["freezeCol"] = 0

    merged: Dict[Tuple[int, int], Tuple[int, int]] = {}
    covered = set()
    ranges = getattr(getattr(worksheet, "merged_cells", None), "ranges", ()) or ()
    for merge in list(ranges)[:2000]:
        min_row, min_col, end_row, end_col = merge.min_row, merge.min_col, merge.max_row, merge.max_col
        if min_row > max_row or min_col > max_col:
            continue
        end_row = min(end_row, max_row)
        end_col = min(end_col, max_col)
        merged[(min_row, min_col)] = (end_row - min_row + 1, end_col - min_col + 1)
        for row in range(min_row, end_row + 1):
            for col in range(min_col, end_col + 1):
                if (row, col) != (min_row, min_col):
                    covered.add((row, col))

    widths: List[float] = []
    for col in range(1, max_col + 1):
        try:
            raw = worksheet.column_dimensions[get_column_letter(col)].width
            width = float(raw) if raw else 0.0
        except Exception:
            width = 0.0
        widths.append(max(42.0, min(360.0, width * 7.2 + 6)) if width else 72.0)

    rows_html: List[str] = []
    used_cells = 0
    out_of_budget = False
    for row_index, row_cells in enumerate(
            worksheet.iter_rows(min_row=1, max_row=max_row, max_col=max_col), start=1):
        if out_of_budget:
            break
        pieces: List[str] = ['<tr style="height:%s">' % _row_height(worksheet, row_index)]
        for cell in row_cells:
            col_index = int(cell.column or 0)
            if col_index < 1 or col_index > max_col:
                continue
            if (row_index, col_index) in covered:
                continue
            if used_cells >= remaining_cells:
                out_of_budget = True
                truncated = True
                break
            used_cells += 1
            attrs: List[str] = []
            span = merged.get((row_index, col_index))
            if span:
                if span[0] > 1:
                    attrs.append(' rowspan="%d"' % span[0])
                if span[1] > 1:
                    attrs.append(' colspan="%d"' % span[1])
            style = _cell_style(cell)
            if style:
                attrs.append(' style="%s"' % style)
            classes = []
            if sheet["freezeRow"] and row_index < sheet["freezeRow"] + 1:
                classes.append("dp-frozen-row")
            if sheet["freezeCol"] and col_index < sheet["freezeCol"] + 1:
                classes.append("dp-frozen-col")
            if classes:
                attrs.append(' class="%s"' % " ".join(classes))
            text = _format_cell_value(cell.value, getattr(cell, "number_format", "") or "")
            pieces.append("<td%s>%s</td>" % ("".join(attrs), text))
        pieces.append("</tr>")
        rows_html.append("".join(pieces))
    if out_of_budget:
        truncated = True

    sheet["truncated"] = truncated
    sheet["html"] = (
        '<div class="dp-sheet-wrap"><table class="dp-sheet"><colgroup>'
        + "".join('<col style="width:%dpx">' % round(width) for width in widths)
        + "</colgroup><tbody>" + "".join(rows_html) + "</tbody></table></div>"
    )
    return sheet, used_cells


def _row_height(worksheet, row_index: int) -> str:
    try:
        raw = worksheet.row_dimensions[row_index].height
        height = float(raw) if raw else 0.0
    except Exception:
        height = 0.0
    if height <= 0:
        return "22px"
    return "%dpx" % max(18, min(180, round(height * 4 / 3)))


def _cell_style(cell) -> str:
    rules: List[str] = []
    try:
        font = cell.font
        if font is not None:
            if font.bold:
                rules.append("font-weight:600")
            if font.italic:
                rules.append("font-style:italic")
            color = _xlsx_color(getattr(font, "color", None))
            if color and color.upper() not in ("#000000", "#000000FF"):
                rules.append("color:" + color)
        fill = cell.fill
        if fill is not None and getattr(fill, "patternType", None) == "solid":
            color = _xlsx_color(getattr(fill, "fgColor", None))
            if color and color.upper() not in ("#FFFFFF", "#00000000"):
                rules.append("background:" + color)
        alignment = cell.alignment
        if alignment is not None:
            if alignment.horizontal in ("center", "right", "justify"):
                rules.append("text-align:" + alignment.horizontal)
            if alignment.vertical in ("top", "center", "bottom"):
                rules.append("vertical-align:" + ("middle" if alignment.vertical == "center" else alignment.vertical))
            if alignment.wrap_text:
                rules.append("white-space:pre-wrap")
    except Exception:
        pass
    return ";".join(rules)


def _xlsx_color(color) -> str:
    if color is None:
        return ""
    try:
        kind = getattr(color, "type", None)
        if kind == "rgb":
            rgb = str(getattr(color, "rgb", "") or "")
            if re.fullmatch(r"[0-9A-Fa-f]{8}", rgb):
                rgb = rgb[2:]
            if re.fullmatch(r"[0-9A-Fa-f]{6}", rgb):
                return "#" + rgb.upper()
        if kind == "theme":
            index = int(getattr(color, "theme", 0) or 0)
            return "#" + _OFFICE_THEME_COLORS[index % len(_OFFICE_THEME_COLORS)]
        if kind == "indexed":
            from openpyxl.styles.colors import COLOR_INDEX
            index = int(getattr(color, "indexed", 0) or 0)
            if 0 <= index < len(COLOR_INDEX):
                rgb = str(COLOR_INDEX[index] or "")
                if re.fullmatch(r"[0-9A-Fa-f]{8}", rgb):
                    rgb = rgb[2:]
                if re.fullmatch(r"[0-9A-Fa-f]{6}", rgb):
                    return "#" + rgb.upper()
    except Exception:
        return ""
    return ""


def _format_cell_value(value: Any, number_format: str) -> str:
    if value is None:
        return ""
    fmt = str(number_format or "")
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, datetime):
        return _esc(value.strftime("%Y-%m-%d %H:%M" if ("h" in fmt.lower() or ":" in fmt) else "%Y-%m-%d"))
    if isinstance(value, date):
        return _esc(value.strftime("%Y-%m-%d"))
    if isinstance(value, clock_time):
        return _esc(value.strftime("%H:%M"))
    if isinstance(value, (int, float)):
        if isinstance(value, float) and value.is_integer():
            value = int(value)
        if "%" in fmt:
            return _esc(("%.2f" % (float(value) * 100)).rstrip("0").rstrip(".") + "%")
        if isinstance(value, int):
            return _esc(("%d" % value) if "," not in fmt else ("{:,}".format(value)))
        text = ("%.6f" % float(value)).rstrip("0").rstrip(".")
        if "," in fmt:
            whole, _, frac = text.partition(".")
            whole = "{:,}".format(int(whole))
            text = whole + ("." + frac if frac else "")
        return _esc(text)
    text = _text(str(value))
    return _esc(text).replace("\n", "<br>")
