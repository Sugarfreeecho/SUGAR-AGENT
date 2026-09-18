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
# Hot-path memo for the default store. ``get_attachment_store()`` is called once
# per message while projecting a request, so recomputing the key meant 8 env
# reads plus a Path.resolve() (a real getfinalpathname syscall on Windows) for
# every message even on a cache hit. The environment is therefore captured once
# and reused; embedders and tests that change it call
# ``invalidate_attachment_env_cache()``.
_DEFAULT_ENV_KEY: tuple | None = None
_DEFAULT_STORE = None
_DEFAULT_STORE_KEY = None


def _invalidate_default_store_cache() -> None:
    global _DEFAULT_ENV_KEY, _DEFAULT_STORE, _DEFAULT_STORE_KEY, _STORE_CACHE
    _DEFAULT_ENV_KEY = None
    _DEFAULT_STORE = None
    _DEFAULT_STORE_KEY = None
    _STORE_CACHE = {}


def invalidate_attachment_env_cache() -> None:
    """Re-read attachment configuration on the next store lookup.

    Test suites and embedders that mutate the relevant environment variables
    must call this; the application itself reads them once at startup.
    """
    global _DEFAULT_WORK_DIR
    _DEFAULT_WORK_DIR = None
    _invalidate_default_store_cache()
    try:
        from .remote import invalidate_remote_policy_cache
        invalidate_remote_policy_cache()
    except Exception:
        pass


def _default_work_dir() -> Path:
    """Resolve the default work dir, caching only the environment-free case.

    An explicitly set ``WORK_DIR`` is honoured on every call: it is the cheap
    branch, and caching it would pin the first value seen for the process'
    lifetime -- exactly what test suites and embedders rely on being able to
    change. The expensive branch (deriving the app-workspace default and running
    ``Path.resolve()``, a real getfinalpathname syscall on Windows) is computed
    once.
    """
    global _DEFAULT_WORK_DIR
    env_dir = os.getenv("WORK_DIR")
    if env_dir:
        path = Path(env_dir)
        if not path.is_absolute():
            path = Path(__file__).resolve().parents[2] / path
        return path
    if _DEFAULT_WORK_DIR is not None:
        return _DEFAULT_WORK_DIR
    _DEFAULT_WORK_DIR = (Path(__file__).resolve().parents[2] / "workspace").resolve()
    return _DEFAULT_WORK_DIR


def configure_attachment_workspace(work_dir):
    """Application composition root for legacy callers without an explicit store."""
    global _DEFAULT_WORK_DIR
    _DEFAULT_WORK_DIR = Path(work_dir).resolve()
    _invalidate_default_store_cache()


def _store_settings(work_dir):
    """Read the attachment limits and compose the store cache key."""
    return (
        str(work_dir),
        _integer("ATTACHMENT_MAX_IMAGE_BYTES", 20 * 1024 * 1024),
        _integer("ATTACHMENT_MAX_IMAGES_PER_MESSAGE", 20),
        _integer("ATTACHMENT_MAX_MESSAGE_IMAGE_BYTES", 200 * 1024 * 1024),
        _integer("ATTACHMENT_MAX_IMAGE_PIXELS", 64_000_000),
        _integer("ATTACHMENT_MAX_IMAGE_DIMENSION", 8192),
        _integer("ATTACHMENT_NORMALIZATION_MAX_PIXELS", 2048 ** 2),
        _integer("ATTACHMENT_NORMALIZATION_MAX_BYTES", 4 * 1024 * 1024),
        _integer("ATTACHMENT_NORMALIZATION_MAX_DIMENSION", 8192),
    )


def _build_store(key):
    (work_dir, max_image_bytes, max_images, max_message_bytes, max_pixels,
     max_dimension, norm_pixels, norm_bytes, norm_dimension) = key
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


def get_attachment_store(work_dir=None):
    """Return a cached attachment store; store construction resolves paths.

    Explicit execution contexts pass their own work_dir. The default is set by
    application startup, without inspecting imported application modules.

    This runs once per message while projecting a request, so the default branch
    is memoized behind a single ``WORK_DIR`` read: recomputing the full key cost
    nine environment reads plus, historically, a ``Path.resolve()`` syscall per
    message even on a hit.
    """
    global _DEFAULT_STORE, _DEFAULT_STORE_KEY
    if work_dir is None:
        raw_work_dir = os.getenv("WORK_DIR")
        if _DEFAULT_STORE is not None and raw_work_dir == _DEFAULT_STORE_KEY:
            return _DEFAULT_STORE
        key = _store_settings(_default_work_dir())
        store = _STORE_CACHE.get(key) or _build_store(key)
        _DEFAULT_STORE = store
        _DEFAULT_STORE_KEY = raw_work_dir
        return store
    key = _store_settings(work_dir)
    return _STORE_CACHE.get(key) or _build_store(key)


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
