import hashlib
import json
import os
from dataclasses import asdict
from io import BytesIO

from PIL import Image, __version__ as pillow_version

from .encoding import QUALITIES, encode_image
from .errors import AttachmentError
from .local import atomic_write
from .locking import attachment_lock
from .metrics import count
from .normalization import dimensions, verify_normalized
from .types import RequestImageAttachment
from .validation import verify_once

TRANSFORM_VERSION = "myagent-request-image-v2"


def _trim_cache(store, incoming, keep):
    quota = int(os.getenv("ATTACHMENT_CACHE_MAX_BYTES", str(512 * 1024 ** 2)))
    if incoming > quota:
        raise AttachmentError("Request image exceeds cache quota", "ATTACHMENT_QUOTA_EXCEEDED")
    objects = [p for p in store.cache_root.glob("[0-9a-f][0-9a-f]/*") if p.is_file() and len(p.name) == 64 and all(c in "0123456789abcdef" for c in p.name)]
    occupied = sum(p.stat().st_size for p in objects)
    for path in sorted(objects, key=lambda p: p.stat().st_mtime):
        if occupied + incoming <= quota:
            break
        if path == keep:
            continue
        try:
            size = path.stat().st_size
            path.unlink()
            path.with_suffix(".sha256").unlink(missing_ok=True)
            occupied -= size
            count("cache.evicted")
        except OSError:
            continue
    if occupied + incoming > quota:
        raise AttachmentError("Request cache quota exceeded", "ATTACHMENT_QUOTA_EXCEEDED")


def read_request_image(store, ref, policy):
    descriptor = json.dumps([TRANSFORM_VERSION, pillow_version, ref["attachmentId"], asdict(policy), QUALITIES], separators=(",", ":"))
    key = hashlib.sha256(descriptor.encode()).hexdigest()
    with attachment_lock(store.cache_root, key):
        source = store.read_image_sync(ref)
        path = store.cache_root / key[:2] / key
        size = dimensions(ref["width"], ref["height"], policy.max_pixels)
        try:
            data = path.read_bytes()
            meta = json.loads(path.with_suffix(".sha256").read_text())
            if hashlib.sha256(data).hexdigest() != meta["sha256"]:
                raise ValueError()
            media_type, alpha = meta["mediaType"], meta["hasAlpha"]
            verify_once(("variant", meta["sha256"], media_type, size, alpha), lambda: verify_normalized(data, media_type, size, alpha))
            count("cache.hit")
            return RequestImageAttachment("sha256:" + key, dict(ref), data, media_type, *size, has_alpha=alpha)
        except (OSError, ValueError, KeyError, TypeError, AttachmentError):
            count("cache.miss")
        with Image.open(BytesIO(source.data)) as image:
            if image.size != size:
                image = image.resize(size, Image.Resampling.LANCZOS)
            if image.mode == "RGBA" and image.getchannel("A").getextrema()[0] == 255:
                image = image.convert("RGB")
            alpha = image.mode == "RGBA"
            media_type = "image/webp" if alpha else "image/jpeg"
            if (ref["width"], ref["height"]) == size and len(source.data) <= policy.max_bytes:
                data, media_type = source.data, ref["mediaType"]
            else:
                image.info.clear()
                data, media_type = encode_image(image, policy.max_bytes)
            verify_normalized(data, media_type, size, alpha)
        try:
            with attachment_lock(store.cache_root, "cache-catalog"):
                _trim_cache(store, max(0, len(data) - (path.stat().st_size if path.exists() else 0)), path)
                atomic_write(path, data)
                atomic_write(path.with_suffix(".sha256"), json.dumps({"sha256": hashlib.sha256(data).hexdigest(), "mediaType": media_type, "hasAlpha": alpha}).encode())
        except OSError:
            raise AttachmentError("Request image cache write failed", "ATTACHMENT_WRITE_FAILED") from None
        return RequestImageAttachment("sha256:" + key, dict(ref), data, media_type, *size, has_alpha=alpha)
