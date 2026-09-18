"""Explicit message-level admission: gather first, commit once, preserve order."""
import asyncio
import re
from dataclasses import dataclass
from pathlib import Path

from .encoding import decode_base64
from .errors import AttachmentError
from .remote import RemoteImagePolicy, download_image
from .store import AttachmentStore
from .types import SaveImageAttachment

REMOTE_IMAGE_RE = re.compile(
    r'!\[[^\]]*\]\((?P<markdown>https?://[^\s)]+)\)'
    r'|(?P<bare>https?://[^\s<>"\']+?\.(?:png|jpe?g|gif|webp|bmp)(?:\?[^\s<>"\']*)?(?:#[^\s<>"\']*)?)', re.I)


@dataclass(frozen=True)
class AdmissionContext:
    store: AttachmentStore
    remote_policy: RemoteImagePolicy | None = None
    verify_refs: bool = True


def _holds_no_admissible_block(value) -> bool:
    """Whether a content value provably admits nothing, whatever the store's limits.

    Only block kinds that can never reference, stage, or inherit an attachment
    count as provably empty, so the fast path cannot hide a real admission.
    """
    if isinstance(value, str):
        return True
    if not isinstance(value, list):
        return False
    for block in value:
        if not isinstance(block, dict):
            return False
        if block.get("type") in {"image", "image_url", "input_image", "local_file"}:
            return False
        if block.get("attachment") or block.get("data") or block.get("source"):
            return False
        nested = block.get("content")
        if nested is not None and not _holds_no_admissible_block(nested):
            return False
    return True


def admit_content(content, context, *, scan_paths=False, scan_remote=False, strict=False):
    from .content import DATA_IMAGE_RE, IMAGE_PATH_RE, scan_enabled

    # Fast path: a message with no image-capable block and no scanned token in
    # its text is already its own admitted form. This runs once per message
    # while projecting a request, so the full pipeline below (store limits,
    # remote policy, recursive block rewrite) must not be paid for plain text.
    if _holds_no_admissible_block(content):
        if isinstance(content, str):
            if not DATA_IMAGE_RE.search(content) and not (
                scan_remote and REMOTE_IMAGE_RE.search(content)
            ) and not (scan_paths and scan_enabled() and IMAGE_PATH_RE.search(content)):
                return content
        elif scan_remote or scan_paths:
            probes = [(str(block.get("text") or ""), block.get("content"))
                      for block in content if isinstance(block, dict)]
            hit = False
            for text, nested in probes:
                if DATA_IMAGE_RE.search(text):
                    hit = True
                    break
                if scan_remote and REMOTE_IMAGE_RE.search(text):
                    hit = True
                    break
                if scan_paths and scan_enabled() and IMAGE_PATH_RE.search(text):
                    hit = True
                    break
                if nested is not None and not _holds_no_admissible_block(nested):
                    hit = True
                    break
            if not hit:
                return content
        else:
            hit = False
            for block in content:
                if not isinstance(block, dict):
                    continue
                if DATA_IMAGE_RE.search(str(block.get("text") or "")):
                    hit = True
                    break
            if not hit:
                return content

    store = context.store
    policy = context.remote_policy or RemoteImagePolicy.from_env()
    pending, placeholders, references = [], [], []
    error = None
    known_paths, remote_sources = set(), {}

    def existing(blocks):
        for block in blocks if isinstance(blocks, list) else []:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "image" and block.get("attachment"):
                try:
                    known_paths.add(store.image_host_path(block["attachment"]))
                except AttachmentError:
                    pass  # visit() reports it with the rest of the batch.
            if block.get("type") == "local_file":
                local = block.get("local_file")
                known_paths.add(str(local.get("path") if isinstance(local, dict) else local or block.get("path") or ""))
            existing(block.get("content"))
    existing(content)

    def unavailable(exc):
        nonlocal error
        error = exc if isinstance(exc, AttachmentError) else AttachmentError("Image cannot be admitted", "ATTACHMENT_CORRUPT")
        return {"type": "text", "text": f"[image unavailable: {error.code}]"}

    def stage(source):
        if len(pending) + len(references) >= store.limits.max_images_per_message:
            raise AttachmentError("Too many images in message", "TOO_MANY_IMAGES")
        part = {"type": "image"}
        pending.append(source)
        placeholders.append(part)
        return part

    def reference(ref):
        from .locking import attachment_lock
        from .registry import AttachmentRegistry
        store.image_host_path(ref)
        if context.verify_refs:
            with attachment_lock(store.root.parent, "catalog"):
                store.read_image_sync(ref)
                AttachmentRegistry(store).grant("local", [ref["attachmentId"]])
        references.append(ref)
        return {"type": "image", "attachment": dict(ref)}

    def path_part(path):
        path = Path(path)
        if path.parent.parent.parent == store.root and path.name.startswith("image."):
            return reference(store.ref_by_id("sha256:" + path.parent.name))
        return stage(store.prepare_path(path))

    def data_part(media, data):
        if not isinstance(data, str) or len(data) > ((store.limits.max_image_bytes + 2) // 3) * 4:
            raise AttachmentError("Invalid or oversized image encoding", "IMAGES_TOO_LARGE")
        return stage(SaveImageAttachment(decode_base64(data), media))

    def remote_part(url):
        if policy.mode == "disabled":
            return {"type": "text", "text": url, "imagesAdmitted": True}
        if policy.mode == "passthrough":
            return {"type": "image_url", "image_url": {"url": url}}
        if url not in remote_sources:
            remote_sources[url] = download_image(url, store.limits, policy)
        return stage(remote_sources[url])

    def visit(value):
        source = [{"type": "text", "text": value}] if isinstance(value, str) else value
        if not isinstance(source, list):
            return value
        out = []
        for block in source:
            if not isinstance(block, dict):
                out.append({"type": "text", "text": str(block)})
                continue
            kind = block.get("type")
            try:
                if kind == "text":
                    text = str(block.get("text") or "")
                    matches = [(m.start(), m.end(), "data", m) for m in DATA_IMAGE_RE.finditer(text)]
                    if scan_remote and not block.get("imagesAdmitted"):
                        matches.extend((m.start(), m.end(), "remote", m) for m in REMOTE_IMAGE_RE.finditer(text))
                    position = 0
                    for start, end, source_kind, match in sorted(matches):
                        if start < position:
                            continue
                        if start > position:
                            out.append({"type": "text", "text": text[position:start], "imagesAdmitted": True})
                        try:
                            out.append(data_part(*match.groups()) if source_kind == "data" else remote_part(match.group("markdown") or match.group("bare")))
                        except (AttachmentError, OSError, ValueError) as exc:
                            out.append(unavailable(exc))
                        position = end
                    tail = text[position:]
                    if tail or not position:
                        out.append({**block, "text": tail, **({"imagesAdmitted": True} if matches else {})})
                    if scan_paths and scan_enabled():
                        for match in IMAGE_PATH_RE.finditer(text):
                            path = match.group("qp") or match.group("up")
                            if path not in known_paths and Path(path).is_file():
                                known_paths.add(path)
                                out.append(path_part(path))
                elif kind == "local_file":
                    local = block.get("local_file")
                    path = str(local.get("path") if isinstance(local, dict) else local or block.get("path") or "")
                    out.append(path_part(path) if Path(path).is_file() and Path(path).suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"} else block)
                elif kind in {"image_url", "input_image"}:
                    value = block.get("image_url") or ""
                    url = value.get("url", "") if isinstance(value, dict) else value
                    match = DATA_IMAGE_RE.fullmatch(url)
                    if match:
                        out.append(data_part(*match.groups()))
                    elif url.startswith(("https://", "http://")):
                        out.append(remote_part(url))
                    else:
                        raise AttachmentError("Invalid image URL", "UNSUPPORTED_IMAGE_TYPE")
                elif kind == "image":
                    if block.get("attachment"):
                        out.append(reference(block["attachment"]))
                    elif isinstance(block.get("source"), dict):
                        image_source = block["source"]
                        out.append(remote_part(image_source["url"]) if image_source.get("type") == "url" else data_part(image_source.get("media_type"), image_source.get("data", "")))
                    else:
                        out.append(data_part(block.get("mediaType") or block.get("mimeType"), block.get("data", "")))
                elif isinstance(block.get("content"), list):
                    out.append({**block, "content": visit(block["content"])})
                else:
                    out.append(block)
            except (AttachmentError, OSError, ValueError, KeyError, TypeError) as exc:
                out.append(unavailable(exc))
        return out

    result = visit(content)
    try:
        if error:
            raise error
        if len(pending) + len(references) > store.limits.max_images_per_message:
            raise AttachmentError("Too many images in message", "TOO_MANY_IMAGES")
        if sum(len(s.data) for s in pending) + sum(r["bytes"] for r in references) > store.limits.max_message_image_bytes:
            raise AttachmentError("Message image bytes exceeded", "IMAGES_TOO_LARGE")
        refs = store.save_images_sync(pending) if pending else []
        for block, ref in zip(placeholders, refs):
            block["attachment"] = ref
    except AttachmentError as exc:
        from .metrics import count
        count("admission.rejected")
        if strict:
            raise
        for block in placeholders:
            block.clear()
            block.update(type="text", text=f"[image unavailable: {exc.code}; entire image batch rejected]")
        # Existing references remain valid, but the failing input cannot silently
        # bypass limits by supplying only references.
        if not placeholders and references:
            return [{"type": "text", "text": f"[image unavailable: {exc.code}]"}]
        def reject_images(value):
            if not isinstance(value, list):
                return value
            return [{"type": "text", "text": f"[image unavailable: {exc.code}; entire image batch rejected]"}
                    if block.get("type") == "image" else {**block, "content": reject_images(block["content"])}
                    if isinstance(block.get("content"), list) else block for block in value]
        result = reject_images(result)
    if isinstance(content, str) and result == [{"type": "text", "text": content}]:
        return content
    return result


async def admit_content_async(content, context, **kwargs):
    return await asyncio.to_thread(admit_content, content, context, **kwargs)
