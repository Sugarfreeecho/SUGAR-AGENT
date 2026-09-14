"""Durable images in core history; image bytes only in transient wire projections."""
import os
import warnings
from pathlib import Path

from .errors import AttachmentError
from .local import LocalAttachmentStore
from .store import AttachmentStore
from .types import *
from .request_budget import RequestImageOffloadPolicy


def _integer(name, default):
    raw = os.getenv(name)
    return int(raw) if raw is not None and raw.strip() else default


_STORE_CACHE: dict = {}
_DEFAULT_WORK_DIR = None


def configure_attachment_workspace(work_dir):
    """Application composition root for legacy callers without an explicit store."""
    global _DEFAULT_WORK_DIR
    _DEFAULT_WORK_DIR = Path(work_dir).resolve()


def get_attachment_store(work_dir=None):
    """Return a cached attachment store; store construction resolves paths.

    Explicit execution contexts pass their own work_dir. The default is set by
    application startup, without inspecting imported application modules.
    """

    if work_dir is None:
        work_dir = os.getenv("WORK_DIR") or _DEFAULT_WORK_DIR or Path(__file__).resolve().parents[2] / "workspace"
        if not Path(work_dir).is_absolute():
            work_dir = Path(__file__).resolve().parents[2] / work_dir
    max_image_bytes = _integer("ATTACHMENT_MAX_IMAGE_BYTES", 20 * 1024 * 1024)
    max_images = _integer("ATTACHMENT_MAX_IMAGES_PER_MESSAGE", 20)
    max_message_bytes = _integer("ATTACHMENT_MAX_MESSAGE_IMAGE_BYTES", 200 * 1024 * 1024)
    max_pixels = _integer("ATTACHMENT_MAX_IMAGE_PIXELS", 64_000_000)
    max_dimension = _integer("ATTACHMENT_MAX_IMAGE_DIMENSION", 8192)
    norm_pixels = _integer("ATTACHMENT_NORMALIZATION_MAX_PIXELS", 2048 ** 2)
    norm_bytes = _integer("ATTACHMENT_NORMALIZATION_MAX_BYTES", 4 * 1024 * 1024)
    norm_dimension = _integer("ATTACHMENT_NORMALIZATION_MAX_DIMENSION", 8192)
    key = (
        str(work_dir),
        max_image_bytes,
        max_images,
        max_message_bytes,
        max_pixels,
        max_dimension,
        norm_pixels,
        norm_bytes,
        norm_dimension,
    )
    cached = _STORE_CACHE.get(key)
    if cached is not None:
        return cached
    limits = ImageAttachmentLimits(
        max_image_bytes,
        max_images,
        max_message_bytes,
        max_pixels,
        max_dimension,
    )
    store = LocalAttachmentStore(work_dir, limits, ImageRequestPolicy(
        norm_pixels,
        norm_bytes,
    ), norm_dimension)
    if len(_STORE_CACHE) >= 16:
        _STORE_CACHE.clear()
    _STORE_CACHE[key] = store
    return store


def request_policy(client=None):
    raw = getattr(client, "_myagent_image_request_policy", None) or {}
    return ImageRequestPolicy(
        int(raw.get("maxPixels", _integer("MULTIMODAL_REQUEST_IMAGE_MAX_PIXELS", 2048 ** 2))),
        int(raw.get("maxBytes", _integer("MULTIMODAL_REQUEST_IMAGE_MAX_BYTES", 4 * 1024 * 1024))),
    )


def budget_policy(client=None):
    raw = getattr(client, "_myagent_image_request_policy", None) or {}
    legacy = os.getenv("MULTIMODAL_INLINE_MAX_BYTES")
    if legacy:
        warnings.warn("MULTIMODAL_INLINE_MAX_BYTES is deprecated; use MULTIMODAL_MAX_INLINE_REQUEST_IMAGE_BYTES", FutureWarning, stacklevel=2)
    return RequestImageOffloadPolicy(
        int(raw.get("maxInlineRequestImageBytes", _integer("MULTIMODAL_MAX_INLINE_REQUEST_IMAGE_BYTES", int(legacy) if legacy else 20 * 1024 * 1024))),
        raw.get("maxImagesPerRequest", _integer("MULTIMODAL_MAX_IMAGES_PER_REQUEST", None)),
        int(raw.get("byteQuantum", _integer("MULTIMODAL_IMAGE_BYTE_QUANTUM", 10 * 1024 * 1024))),
        int(raw.get("countQuantum", _integer("MULTIMODAL_IMAGE_COUNT_QUANTUM", 20))),
    )


def prompt_language():
    return "en" if os.getenv("PROMPT_LANGUAGE") == "en" else "zh-CN"
