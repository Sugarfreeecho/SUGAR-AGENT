from dataclasses import dataclass
from typing import Literal, TypedDict


class _RequiredImageRef(TypedDict):
    attachmentId: str
    mediaType: str
    bytes: int
    width: int
    height: int


class ImageAttachmentRef(_RequiredImageRef, total=False):
    name: str
    originalDimensions: dict
    source: dict


class _RequiredTextPart(TypedDict):
    type: Literal["text"]
    text: str


class TextPart(_RequiredTextPart, total=False):
    imagesAdmitted: bool


class ImagePart(TypedDict):
    type: Literal["image"]
    attachment: ImageAttachmentRef


CoreContent = str | list[TextPart | ImagePart]


class FileAttachmentRef(TypedDict):
    attachmentId: str
    name: str
    bytes: int


@dataclass(frozen=True)
class SaveImageAttachment:
    data: bytes
    media_type: str
    name: str = ""
    source: dict | None = None


@dataclass(frozen=True)
class ImageRequestPolicy:
    max_pixels: int = 2048 * 2048
    max_bytes: int = 4 * 1024 * 1024

    def __post_init__(self):
        if any(type(v) is not int or v <= 0 for v in (self.max_pixels, self.max_bytes)):
            raise ValueError("Image request limits must be positive integers")


@dataclass(frozen=True)
class ImageAttachmentLimits:
    max_image_bytes: int = 20 * 1024 * 1024
    max_images_per_message: int = 20
    max_message_image_bytes: int = 200 * 1024 * 1024
    max_image_pixels: int = 64_000_000
    max_image_dimension: int = 8192

    def __post_init__(self):
        if any(type(value) is not int or value <= 0 for value in self.__dict__.values()):
            raise ValueError("Attachment admission limits must be positive integers")


@dataclass(frozen=True)
class StoredImageAttachment:
    ref: ImageAttachmentRef
    data: bytes


@dataclass(frozen=True)
class RequestImageAttachment:
    variant_id: str
    attachment: ImageAttachmentRef
    data: bytes
    media_type: str
    width: int
    height: int
    depth: str = "uchar"
    space: str = "srgb"
    has_alpha: bool = False

    @property
    def bytes(self):
        return len(self.data)
