"""Conservative reachability GC and portable, verified image bundles."""
import json
import os
import re
import stat
import time
import tempfile
import zipfile
from pathlib import Path

from .errors import AttachmentError
from .local import atomic_write, checked_id, digest
from .locking import attachment_lock
from .registry import AttachmentRegistry

IDENTITY_RE = re.compile(r"sha256:[0-9a-f]{64}")


def referenced_ids(value):
    return set(IDENTITY_RE.findall(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)))


def collect_references(roots):
    identities = set()
    for root in roots:
        root = Path(root)
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_symlink() or not path.is_file() or path.suffix not in {".json", ".jsonl", ".md", ".txt"}:
                continue
            # A read error must stop GC, never turn into an empty reference set.
            with path.open(encoding="utf-8", errors="replace") as source:
                for line in source:
                    identities.update(IDENTITY_RE.findall(line))
    return identities


def garbage_collect(store, reference_roots, *, dry_run=True, grace_seconds=7 * 86400):
    if grace_seconds < 0:
        raise ValueError("GC grace period must be nonnegative")
    registry = AttachmentRegistry(store)
    with attachment_lock(store.root.parent, "catalog"):
        protected = collect_references(reference_roots) | registry.protected()
        candidates, removed = [], []
        for metadata in sorted(store.root.glob("*/*/image.json")):
            identity = "sha256:" + metadata.parent.name
            if identity in protected or time.time() - metadata.stat().st_mtime < grace_seconds:
                continue
            ref = store.ref_by_id(identity)
            path = Path(store.image_host_path(ref))
            candidates.append({"attachmentId": identity, "bytes": ref["bytes"]})
            if not dry_run:
                # Only the two known files inside a validated object directory.
                # Never recursively delete a caller-provided directory.
                for entry in (path, metadata):
                    if entry.is_symlink() or not entry.resolve().is_relative_to(store.root.resolve()):
                        raise AttachmentError("Invalid attachment object path", "INVALID_ATTACHMENT_REF")
                    entry.chmod(stat.S_IREAD | stat.S_IWRITE)
                    entry.unlink()
                registry.forget(identity)
                removed.append(identity)
        return {"dryRun": dry_run, "protectedCount": len(protected), "candidates": candidates,
                "removed": removed, "candidateBytes": sum(i["bytes"] for i in candidates)}


def add_bundle(archive, store, identities, *, prefix="attachments"):
    manifest = []
    for identity in sorted(set(identities)):
        ref = store.ref_by_id(identity)
        image = store.read_image_sync(ref)
        name = f"{prefix}/{checked_id(identity)}/{Path(store.image_host_path(ref)).name}"
        archive.writestr(name, image.data)
        manifest.append({"ref": ref, "path": name})
    archive.writestr(f"{prefix}/manifest.json", json.dumps({"version": 1, "images": manifest}, ensure_ascii=False))
    return manifest


def import_bundle(store, source, *, prefix="attachments"):
    with zipfile.ZipFile(source) as archive, tempfile.TemporaryDirectory(prefix="myagent-image-restore-") as staging:
        info = archive.getinfo(f"{prefix}/manifest.json")
        if info.file_size > 4 * 1024 * 1024:
            raise AttachmentError("Attachment manifest too large", "IMAGES_TOO_LARGE")
        manifest = json.loads(archive.read(info))
        if not isinstance(manifest, dict) or manifest.get("version") != 1 or not isinstance(manifest.get("images"), list):
            raise AttachmentError("Invalid attachment manifest", "INVALID_ATTACHMENT_REF")
        images = []
        seen = set()
        total = 0
        for item in manifest["images"]:
            if not isinstance(item, dict) or not isinstance(item.get("ref"), dict):
                raise AttachmentError("Invalid attachment manifest entry", "INVALID_ATTACHMENT_REF")
            ref = {key: item["ref"].get(key) for key in ("attachmentId", "mediaType", "bytes", "width", "height")}
            target = Path(store.image_host_path(ref))
            if ref.get("attachmentId") in seen:
                raise AttachmentError("Duplicate attachment in bundle", "INVALID_ATTACHMENT_REF")
            seen.add(ref.get("attachmentId"))
            expected = f"{prefix}/{checked_id(ref['attachmentId'])}/{target.name}"
            if item.get("path") != expected:
                raise AttachmentError("Invalid attachment bundle path", "INVALID_ATTACHMENT_REF")
            info = archive.getinfo(expected)
            total += info.file_size
            if info.file_size > store.limits.max_image_bytes or total > int(os.getenv("ATTACHMENT_STORE_MAX_BYTES", str(10 * 1024 ** 3))):
                raise AttachmentError("Attachment bundle too large", "IMAGES_TOO_LARGE")
            data = archive.read(info)
            store.validate_image(data, ref["mediaType"])
            from .normalization import verify_normalized
            verify_normalized(data, ref["mediaType"], (ref["width"], ref["height"]), ref["mediaType"] == "image/webp")
            if len(data) != ref["bytes"] or digest(data) != ref["attachmentId"]:
                raise AttachmentError("Attachment bundle digest mismatch", "ATTACHMENT_CORRUPT")
            staged = Path(staging) / checked_id(ref["attachmentId"])
            staged.write_bytes(data)
            images.append((ref, target, staged))
        created = []
        with attachment_lock(store.root.parent, "catalog"):
            try:
                occupied = store.occupied_bytes()
                incoming = sum(staged.stat().st_size for _, path, staged in images if not path.exists())
                if occupied + incoming > int(os.getenv("ATTACHMENT_STORE_MAX_BYTES", str(10 * 1024 ** 3))):
                    raise AttachmentError("Attachment storage quota exceeded", "ATTACHMENT_QUOTA_EXCEEDED")
                for ref, path, staged in images:
                    if path.exists():
                        store.read_image_sync(ref)
                    entries = [] if path.exists() else [(path, staged.read_bytes())]
                    metadata = path.parent / "image.json"
                    if not metadata.exists():
                        entries.append((metadata, json.dumps(ref).encode()))
                    else:
                        stored_ref = json.loads(metadata.read_text())
                        if not isinstance(stored_ref, dict) or any(stored_ref.get(key) != value for key, value in ref.items()):
                            raise AttachmentError("Existing attachment metadata is corrupt", "ATTACHMENT_CORRUPT")
                    for dest, body in entries:
                        created.append(dest)
                        atomic_write(dest, body, readonly=True)
            except Exception:
                for dest in reversed(created):
                    if dest.exists():
                        dest.chmod(stat.S_IREAD | stat.S_IWRITE)
                        dest.unlink()
                raise
        return [ref for ref, _, _ in images]
