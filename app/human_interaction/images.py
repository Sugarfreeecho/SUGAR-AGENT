"""Admit ask-card images once; persist attachment references, never image bytes."""
from __future__ import annotations

import re

MAX_IMAGES_PER_QUESTION = 4
MAX_IMAGES_PER_REQUEST = 8
MAX_IMAGE_BYTES = 2 * 1024 * 1024
MAX_REQUEST_IMAGE_BYTES = 8 * 1024 * 1024
_IDENTITY = re.compile(r"sha256:[0-9a-f]{64}")
_DATA_URL = re.compile(r"data:(image/(?:png|jpeg|webp|gif));base64,([A-Za-z0-9+/]*={0,2})")


def normalize_images(raw, field: str) -> list[dict]:
    if raw is None:
        return []
    if not isinstance(raw, list) or len(raw) > MAX_IMAGES_PER_QUESTION:
        raise ValueError(f"{field} must be an array of at most {MAX_IMAGES_PER_QUESTION} images")
    images = []
    for image in raw:
        if not isinstance(image, dict):
            raise ValueError(f"{field} items must be objects")
        identity, data_url = image.get("attachment_id"), image.get("data_url")
        if bool(identity) == bool(data_url):
            raise ValueError(f"{field} requires exactly one of attachment_id or data_url")
        if identity and (not isinstance(identity, str) or not _IDENTITY.fullmatch(identity)):
            raise ValueError(f"{field} has an invalid attachment_id")
        if data_url and (not isinstance(data_url, str)
                         or len(data_url) > ((MAX_IMAGE_BYTES + 2) // 3) * 4 + 64
                         or not _DATA_URL.fullmatch(data_url)):
            raise ValueError(f"{field} requires a PNG/JPEG/WebP/GIF base64 data URL within 2 MiB")
        alt, caption = image.get("alt"), image.get("caption", "")
        if not isinstance(alt, str) or not alt.strip() or len(alt) > 200:
            raise ValueError(f"{field}.alt is required and must not exceed 200 characters")
        if not isinstance(caption, str) or len(caption) > 500:
            raise ValueError(f"{field}.caption must not exceed 500 characters")
        images.append({**({"attachment_id": identity} if identity else {"data_url": data_url}),
                       "alt": alt.strip(), "caption": caption.strip()})
    return images


def admit_question_images(questions: list[dict]) -> None:
    images = [image for question in questions for image in question.get("images", [])]
    if not images:
        return
    if len(images) > MAX_IMAGES_PER_REQUEST:
        raise ValueError(f"ask_user supports at most {MAX_IMAGES_PER_REQUEST} images in total")
    from attachments import AttachmentError, SaveImageAttachment, get_attachment_store
    from attachments.encoding import decode_base64

    store = get_attachment_store()
    pending, positions, references = [], [], {}
    total_bytes = 0
    try:
        for index, image in enumerate(images):
            if image.get("attachment_id"):
                ref = store.ref_by_id(image["attachment_id"])
                size = ref["bytes"]
                references[index] = ref
            else:
                match = _DATA_URL.fullmatch(image["data_url"])
                data = decode_base64(match[2])
                size = len(data)
                pending.append(SaveImageAttachment(data, match[1]))
                positions.append(index)
            total_bytes += size
            if size > MAX_IMAGE_BYTES or total_bytes > MAX_REQUEST_IMAGE_BYTES:
                raise ValueError("ask_user images exceed 2 MiB per image or 8 MiB per request")
        # Validate the entire batch before committing any new image.
        references.update(zip(positions, store.save_images_sync(pending) if pending else []))
    except AttachmentError as exc:
        raise ValueError(f"ask_user image unavailable: {exc.code}") from exc
    for index, image in enumerate(images):
        image.pop("attachment_id", None)
        image.pop("data_url", None)
        image["attachment"] = references[index]
